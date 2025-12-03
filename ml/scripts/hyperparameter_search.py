#!/usr/bin/env python
"""
Hyperparameter search script using Optuna for SHAKTI-CHAIN TFT model.

Usage:
    python scripts/hyperparameter_search.py
    python scripts/hyperparameter_search.py --n-trials 100 --timeout 3600
    python scripts/hyperparameter_search.py --study-name tft_tuning --storage sqlite:///optuna.db
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import logging
import warnings
from datetime import datetime
from typing import Optional

import mlflow
import optuna
import pytorch_lightning as pl
import torch
import yaml
from optuna.integration import PyTorchLightningPruningCallback
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint

from src.data.datamodule import V2GDataModule
from src.training.tft_lightning_module import TFTLightningModule

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_base_config(config_path: str = "configs/training/tft.yaml") -> dict:
    """Load base configuration.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_objective(
    base_config: dict,
    data_module: V2GDataModule,
    feature_info: dict,
    max_epochs: int = 30,
    pruning: bool = True,
):
    """Create Optuna objective function.

    Args:
        base_config: Base configuration dictionary
        data_module: Data module for training
        feature_info: Feature information from data module
        max_epochs: Maximum epochs for each trial
        pruning: Whether to use pruning

    Returns:
        Objective function for Optuna
    """

    def objective(trial: optuna.Trial) -> float:
        """Optuna objective function.

        Args:
            trial: Optuna trial object

        Returns:
            Validation loss (to minimize)
        """
        # Hyperparameters to tune
        hidden_size = trial.suggest_categorical("hidden_size", [64, 128, 160, 256])
        lstm_layers = trial.suggest_int("lstm_layers", 1, 3)
        num_attention_heads = trial.suggest_categorical("num_attention_heads", [2, 4, 8])
        dropout = trial.suggest_float("dropout", 0.0, 0.3, step=0.05)

        learning_rate = trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True)
        weight_decay = trial.suggest_float("weight_decay", 1e-6, 1e-3, log=True)
        batch_size = trial.suggest_categorical("batch_size", [32, 64, 128])

        # Scheduler parameters
        scheduler = trial.suggest_categorical("scheduler", ["onecycle", "cosine", "plateau"])

        scheduler_config = {}
        if scheduler == "onecycle":
            scheduler_config["pct_start"] = trial.suggest_float("pct_start", 0.1, 0.5)
            scheduler_config["div_factor"] = trial.suggest_float("div_factor", 10.0, 50.0)
        elif scheduler == "plateau":
            scheduler_config["factor"] = trial.suggest_float("factor", 0.1, 0.5)
            scheduler_config["patience"] = trial.suggest_int("scheduler_patience", 3, 10)

        # Update data module batch size
        data_module.batch_size = batch_size

        # Calculate total steps
        steps_per_epoch = len(data_module.train_dataloader())
        total_steps = max_epochs * steps_per_epoch

        # Create model configuration
        model_config = {
            "input_dims": {
                "static_input_size": feature_info["static_input_size"],
                "known_input_size": feature_info["known_input_size"],
                "observed_input_size": feature_info["observed_input_size"],
            },
            "sequence_lengths": {
                "encoder_length": base_config["data"]["encoder_length"],
                "decoder_length": base_config["data"]["decoder_length"],
            },
            "architecture": {
                "hidden_size": hidden_size,
                "lstm_layers": lstm_layers,
                "num_attention_heads": num_attention_heads,
                "dropout": dropout,
            },
            "output": {
                "output_size": feature_info["output_size"],
                "quantiles": base_config["model"]["output"]["quantiles"],
            },
        }

        # Create model
        model = TFTLightningModule(
            model_config=model_config,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            optimizer="adam",
            scheduler=scheduler,
            scheduler_config=scheduler_config,
            normalized_loss=base_config["training"]["normalized_loss"],
            total_steps=total_steps,
            log_to_mlflow=False,  # Disable for faster trials
        )

        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=5,
                mode="min",
            ),
        ]

        if pruning:
            callbacks.append(
                PyTorchLightningPruningCallback(trial, monitor="val_loss")
            )

        # Create trainer
        trainer = pl.Trainer(
            max_epochs=max_epochs,
            accelerator="auto",
            devices=1,
            precision="16-mixed",
            gradient_clip_val=1.0,
            callbacks=callbacks,
            logger=False,
            enable_checkpointing=False,
            enable_progress_bar=False,
            enable_model_summary=False,
        )

        # Train
        try:
            trainer.fit(model, data_module)
        except Exception as e:
            logger.warning(f"Trial failed: {e}")
            raise optuna.TrialPruned()

        # Get validation metrics
        val_loss = trainer.callback_metrics.get("val_loss")
        val_mape = trainer.callback_metrics.get("val_mape")
        val_coverage = trainer.callback_metrics.get("val_coverage_90")

        if val_loss is None:
            raise optuna.TrialPruned()

        # Log additional metrics
        trial.set_user_attr("val_mape", val_mape.item() if val_mape else None)
        trial.set_user_attr("val_coverage_90", val_coverage.item() if val_coverage else None)
        trial.set_user_attr("num_params", sum(p.numel() for p in model.parameters()))

        return val_loss.item()

    return objective


def run_hyperparameter_search(
    study_name: str = "tft_hyperparameter_search",
    storage: Optional[str] = None,
    n_trials: int = 50,
    timeout: Optional[int] = None,
    n_jobs: int = 1,
    config_path: str = "configs/training/tft.yaml",
    max_epochs_per_trial: int = 30,
    pruning: bool = True,
    seed: int = 42,
):
    """Run hyperparameter search.

    Args:
        study_name: Name for the Optuna study
        storage: Optuna storage URL (e.g., sqlite:///optuna.db)
        n_trials: Number of trials to run
        timeout: Timeout in seconds
        n_jobs: Number of parallel jobs
        config_path: Path to base configuration file
        max_epochs_per_trial: Maximum epochs per trial
        pruning: Whether to use pruning
        seed: Random seed
    """
    # Set seed
    pl.seed_everything(seed, workers=True)

    # Load base configuration
    logger.info(f"Loading configuration from {config_path}")
    base_config = load_base_config(config_path)

    # Create data module
    logger.info("Creating data module...")
    data_module = V2GDataModule(
        data_path=base_config["data"]["data_path"],
        target_columns=base_config["features"]["target_columns"],
        known_future_features=base_config["features"]["known_future_features"],
        observed_features=base_config["features"]["observed_features"],
        static_features=base_config["features"].get("static_features"),
        encoder_length=base_config["data"]["encoder_length"],
        decoder_length=base_config["data"]["decoder_length"],
        batch_size=base_config["training"]["batch_size"],
        num_workers=base_config["data"]["num_workers"],
        train_start=base_config["data"]["train_start"],
        train_end=base_config["data"]["train_end"],
        val_start=base_config["data"]["val_start"],
        val_end=base_config["data"]["val_end"],
        test_start=base_config["data"]["test_start"],
        test_end=base_config["data"]["test_end"],
        stride_train=base_config["data"]["stride_train"],
        stride_val=base_config["data"]["stride_val"],
        stride_test=base_config["data"]["stride_test"],
    )

    # Setup data module
    data_module.setup("fit")
    feature_info = data_module.get_feature_info()
    logger.info(f"Feature info: {feature_info}")

    # Create Optuna study
    sampler = optuna.samplers.TPESampler(seed=seed)
    pruner = optuna.pruners.MedianPruner(
        n_startup_trials=5,
        n_warmup_steps=5,
        interval_steps=1,
    ) if pruning else optuna.pruners.NopPruner()

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        load_if_exists=True,
    )

    # Create objective function
    objective = create_objective(
        base_config=base_config,
        data_module=data_module,
        feature_info=feature_info,
        max_epochs=max_epochs_per_trial,
        pruning=pruning,
    )

    # Run optimization
    logger.info(f"Starting hyperparameter search: {n_trials} trials, timeout={timeout}s")
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        n_jobs=n_jobs,
        show_progress_bar=True,
        gc_after_trial=True,
    )

    # Print results
    logger.info("\n" + "=" * 80)
    logger.info("HYPERPARAMETER SEARCH RESULTS")
    logger.info("=" * 80)

    logger.info(f"\nNumber of finished trials: {len(study.trials)}")

    # Best trial
    best_trial = study.best_trial
    logger.info(f"\nBest trial:")
    logger.info(f"  Value (val_loss): {best_trial.value:.6f}")
    logger.info(f"  MAPE: {best_trial.user_attrs.get('val_mape', 'N/A')}")
    logger.info(f"  Coverage (90% PI): {best_trial.user_attrs.get('val_coverage_90', 'N/A')}")
    logger.info(f"  Num parameters: {best_trial.user_attrs.get('num_params', 'N/A'):,}")

    logger.info("\n  Best hyperparameters:")
    for key, value in best_trial.params.items():
        logger.info(f"    {key}: {value}")

    # Save best configuration
    best_config = base_config.copy()
    best_config["model"]["architecture"]["hidden_size"] = best_trial.params["hidden_size"]
    best_config["model"]["architecture"]["lstm_layers"] = best_trial.params["lstm_layers"]
    best_config["model"]["architecture"]["num_attention_heads"] = best_trial.params["num_attention_heads"]
    best_config["model"]["architecture"]["dropout"] = best_trial.params["dropout"]
    best_config["training"]["learning_rate"] = best_trial.params["learning_rate"]
    best_config["training"]["weight_decay"] = best_trial.params["weight_decay"]
    best_config["training"]["batch_size"] = best_trial.params["batch_size"]
    best_config["training"]["scheduler"] = best_trial.params["scheduler"]

    # Save best config
    output_path = Path("configs/training/tft_best.yaml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(best_config, f, default_flow_style=False)
    logger.info(f"\nBest configuration saved to: {output_path}")

    # Top 10 trials
    logger.info("\nTop 10 trials:")
    trials_df = study.trials_dataframe()
    trials_df = trials_df.sort_values("value")
    print(trials_df.head(10)[["number", "value", "params_hidden_size", "params_learning_rate", "params_batch_size"]])

    # Optuna visualizations (if storage is provided)
    if storage:
        try:
            import optuna.visualization as vis

            # Optimization history
            fig = vis.plot_optimization_history(study)
            fig.write_html("hyperparameter_search_history.html")

            # Parameter importances
            fig = vis.plot_param_importances(study)
            fig.write_html("hyperparameter_importances.html")

            # Contour plot
            fig = vis.plot_contour(study, params=["hidden_size", "learning_rate"])
            fig.write_html("hyperparameter_contour.html")

            logger.info("Visualization plots saved to HTML files")
        except Exception as e:
            logger.warning(f"Failed to create visualizations: {e}")

    return study


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Hyperparameter search for SHAKTI-CHAIN TFT")
    parser.add_argument("--study-name", type=str, default="tft_hyperparameter_search",
                        help="Optuna study name")
    parser.add_argument("--storage", type=str, default=None,
                        help="Optuna storage URL (e.g., sqlite:///optuna.db)")
    parser.add_argument("--n-trials", type=int, default=50,
                        help="Number of trials")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Timeout in seconds")
    parser.add_argument("--n-jobs", type=int, default=1,
                        help="Number of parallel jobs")
    parser.add_argument("--config", type=str, default="configs/training/tft.yaml",
                        help="Path to base configuration")
    parser.add_argument("--max-epochs", type=int, default=30,
                        help="Maximum epochs per trial")
    parser.add_argument("--no-pruning", action="store_true",
                        help="Disable pruning")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")

    args = parser.parse_args()

    run_hyperparameter_search(
        study_name=args.study_name,
        storage=args.storage,
        n_trials=args.n_trials,
        timeout=args.timeout,
        n_jobs=args.n_jobs,
        config_path=args.config,
        max_epochs_per_trial=args.max_epochs,
        pruning=not args.no_pruning,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
