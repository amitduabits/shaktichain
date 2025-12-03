#!/usr/bin/env python
"""
Main training script for SHAKTI-CHAIN TFT model.

Usage:
    python scripts/train_tft.py
    python scripts/train_tft.py --config configs/training/tft.yaml
    python scripts/train_tft.py training.learning_rate=0.0001 training.batch_size=32
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
import warnings
from datetime import datetime

import hydra
import mlflow
import pytorch_lightning as pl
import torch
from omegaconf import DictConfig, OmegaConf
from pytorch_lightning.callbacks import (
    EarlyStopping,
    LearningRateMonitor,
    ModelCheckpoint,
    RichProgressBar,
)
from pytorch_lightning.loggers import MLFlowLogger

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


def setup_mlflow(cfg: DictConfig) -> MLFlowLogger:
    """Setup MLflow logging.

    Args:
        cfg: Configuration object

    Returns:
        MLFlowLogger instance
    """
    mlflow_cfg = cfg.mlflow

    # Set tracking URI
    mlflow.set_tracking_uri(mlflow_cfg.tracking_uri)

    # Create experiment if it doesn't exist
    experiment = mlflow.get_experiment_by_name(mlflow_cfg.experiment_name)
    if experiment is None:
        mlflow.create_experiment(mlflow_cfg.experiment_name)

    # Generate run name if not provided
    run_name = mlflow_cfg.run_name
    if run_name is None:
        run_name = f"tft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Create MLflow logger
    mlflow_logger = MLFlowLogger(
        experiment_name=mlflow_cfg.experiment_name,
        tracking_uri=mlflow_cfg.tracking_uri,
        run_name=run_name,
        tags=dict(mlflow_cfg.tags) if mlflow_cfg.tags else None,
    )

    return mlflow_logger


def setup_callbacks(cfg: DictConfig) -> list:
    """Setup training callbacks.

    Args:
        cfg: Configuration object

    Returns:
        List of callbacks
    """
    callbacks = []
    callbacks_cfg = cfg.callbacks

    # Early stopping
    if callbacks_cfg.early_stopping.enabled:
        early_stopping = EarlyStopping(
            monitor=callbacks_cfg.early_stopping.monitor,
            patience=callbacks_cfg.early_stopping.patience,
            mode=callbacks_cfg.early_stopping.mode,
            min_delta=callbacks_cfg.early_stopping.min_delta,
            verbose=True,
        )
        callbacks.append(early_stopping)
        logger.info(f"Early stopping enabled: patience={callbacks_cfg.early_stopping.patience}")

    # Model checkpoint
    if callbacks_cfg.model_checkpoint.enabled:
        checkpoint_dir = Path(callbacks_cfg.model_checkpoint.dirpath)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = ModelCheckpoint(
            monitor=callbacks_cfg.model_checkpoint.monitor,
            mode=callbacks_cfg.model_checkpoint.mode,
            save_top_k=callbacks_cfg.model_checkpoint.save_top_k,
            save_last=callbacks_cfg.model_checkpoint.save_last,
            filename=callbacks_cfg.model_checkpoint.filename,
            dirpath=str(checkpoint_dir),
            verbose=True,
        )
        callbacks.append(checkpoint)
        logger.info(f"Model checkpointing enabled: {checkpoint_dir}")

    # Learning rate monitor
    if callbacks_cfg.learning_rate_monitor.enabled:
        lr_monitor = LearningRateMonitor(
            logging_interval=callbacks_cfg.learning_rate_monitor.logging_interval,
        )
        callbacks.append(lr_monitor)

    # Progress bar
    if cfg.logging.enable_progress_bar:
        callbacks.append(RichProgressBar())

    return callbacks


def create_model_config(cfg: DictConfig, feature_info: dict) -> dict:
    """Create model configuration from config and feature info.

    Args:
        cfg: Configuration object
        feature_info: Feature information from data module

    Returns:
        Model configuration dictionary
    """
    model_config = {
        "input_dims": {
            "static_input_size": feature_info["static_input_size"],
            "known_input_size": feature_info["known_input_size"],
            "observed_input_size": feature_info["observed_input_size"],
        },
        "sequence_lengths": {
            "encoder_length": cfg.data.encoder_length,
            "decoder_length": cfg.data.decoder_length,
        },
        "architecture": {
            "hidden_size": cfg.model.architecture.hidden_size,
            "lstm_layers": cfg.model.architecture.lstm_layers,
            "num_attention_heads": cfg.model.architecture.num_attention_heads,
            "dropout": cfg.model.architecture.dropout,
        },
        "output": {
            "output_size": feature_info["output_size"],
            "quantiles": list(cfg.model.output.quantiles),
        },
    }

    return model_config


def log_hyperparameters(cfg: DictConfig, model: TFTLightningModule, data_module: V2GDataModule):
    """Log hyperparameters to MLflow.

    Args:
        cfg: Configuration object
        model: TFT model
        data_module: Data module
    """
    # Flatten config for logging
    params = {
        # Training params
        "max_epochs": cfg.training.max_epochs,
        "learning_rate": cfg.training.learning_rate,
        "weight_decay": cfg.training.weight_decay,
        "optimizer": cfg.training.optimizer,
        "scheduler": cfg.training.scheduler,
        "batch_size": cfg.training.batch_size,
        "accumulate_grad_batches": cfg.training.accumulate_grad_batches,
        "gradient_clip_val": cfg.training.gradient_clip_val,
        "precision": cfg.training.precision,

        # Model params
        "hidden_size": cfg.model.architecture.hidden_size,
        "lstm_layers": cfg.model.architecture.lstm_layers,
        "num_attention_heads": cfg.model.architecture.num_attention_heads,
        "dropout": cfg.model.architecture.dropout,

        # Data params
        "encoder_length": cfg.data.encoder_length,
        "decoder_length": cfg.data.decoder_length,
        "train_start": cfg.data.train_start,
        "train_end": cfg.data.train_end,
        "val_start": cfg.data.val_start,
        "val_end": cfg.data.val_end,

        # Feature counts
        "num_known_features": len(cfg.features.known_future_features),
        "num_observed_features": len(cfg.features.observed_features),
        "num_static_features": len(cfg.features.static_features) if cfg.features.static_features else 0,
        "num_targets": len(cfg.features.target_columns),

        # Seed
        "seed": cfg.seed,
    }

    mlflow.log_params(params)
    logger.info("Logged hyperparameters to MLflow")


def evaluate_model(
    trainer: pl.Trainer,
    model: TFTLightningModule,
    data_module: V2GDataModule,
    cfg: DictConfig,
):
    """Evaluate model and log results.

    Args:
        trainer: PyTorch Lightning trainer
        model: Trained model
        data_module: Data module
        cfg: Configuration object
    """
    logger.info("Evaluating model on test set...")

    # Run test
    test_results = trainer.test(model, data_module)

    if test_results:
        test_metrics = test_results[0]

        # Log test metrics
        for key, value in test_metrics.items():
            mlflow.log_metric(f"final_{key}", value)

        # Check against target metrics
        target_cfg = cfg.target_metrics

        test_mape = test_metrics.get("test_mape", float("inf"))
        test_coverage = test_metrics.get("test_coverage_90", 0)

        logger.info(f"Test MAPE: {test_mape:.2f}% (target: <{target_cfg.mape_threshold}%)")
        logger.info(f"Test Coverage (90% PI): {test_coverage:.2%} (target: >{target_cfg.coverage_threshold:.0%})")

        # Check if targets are met
        mape_met = test_mape < target_cfg.mape_threshold
        coverage_met = test_coverage > target_cfg.coverage_threshold

        mlflow.log_metric("mape_target_met", int(mape_met))
        mlflow.log_metric("coverage_target_met", int(coverage_met))

        if mape_met and coverage_met:
            logger.info("All target metrics achieved!")
            mlflow.set_tag("target_metrics", "achieved")
        else:
            logger.warning("Some target metrics not achieved")
            mlflow.set_tag("target_metrics", "not_achieved")


def register_model(model: TFTLightningModule, cfg: DictConfig, run_id: str):
    """Register model in MLflow Model Registry.

    Args:
        model: Trained model
        cfg: Configuration object
        run_id: MLflow run ID
    """
    if not cfg.mlflow.register_model:
        return

    mlflow_cfg = cfg.mlflow

    # Log model
    mlflow.pytorch.log_model(
        model,
        "model",
        registered_model_name=mlflow_cfg.model_name,
    )

    # Transition to stage
    if mlflow_cfg.model_stage:
        client = mlflow.MlflowClient()
        latest_version = client.get_latest_versions(mlflow_cfg.model_name, stages=["None"])
        if latest_version:
            version = latest_version[0].version
            client.transition_model_version_stage(
                name=mlflow_cfg.model_name,
                version=version,
                stage=mlflow_cfg.model_stage,
            )
            logger.info(f"Model registered: {mlflow_cfg.model_name} v{version} -> {mlflow_cfg.model_stage}")


@hydra.main(version_base=None, config_path="../configs/training", config_name="tft")
def main(cfg: DictConfig):
    """Main training function.

    Args:
        cfg: Hydra configuration
    """
    # Print configuration
    logger.info("Configuration:")
    logger.info(OmegaConf.to_yaml(cfg))

    # Set seed for reproducibility
    pl.seed_everything(cfg.seed, workers=True)

    # Setup MLflow
    mlflow_logger = None
    if cfg.mlflow.enabled:
        mlflow_logger = setup_mlflow(cfg)
        logger.info(f"MLflow tracking URI: {cfg.mlflow.tracking_uri}")
        logger.info(f"MLflow experiment: {cfg.mlflow.experiment_name}")

    # Create data module
    logger.info("Creating data module...")
    data_module = V2GDataModule(
        data_path=cfg.data.data_path,
        target_columns=list(cfg.features.target_columns),
        known_future_features=list(cfg.features.known_future_features),
        observed_features=list(cfg.features.observed_features),
        static_features=list(cfg.features.static_features) if cfg.features.static_features else None,
        encoder_length=cfg.data.encoder_length,
        decoder_length=cfg.data.decoder_length,
        batch_size=cfg.training.batch_size,
        num_workers=cfg.data.num_workers,
        train_start=cfg.data.train_start,
        train_end=cfg.data.train_end,
        val_start=cfg.data.val_start,
        val_end=cfg.data.val_end,
        test_start=cfg.data.test_start,
        test_end=cfg.data.test_end,
        stride_train=cfg.data.stride_train,
        stride_val=cfg.data.stride_val,
        stride_test=cfg.data.stride_test,
    )

    # Setup data module to get feature info
    data_module.setup("fit")
    feature_info = data_module.get_feature_info()
    logger.info(f"Feature info: {feature_info}")

    # Calculate total training steps for OneCycleLR
    steps_per_epoch = len(data_module.train_dataloader())
    total_steps = cfg.training.max_epochs * steps_per_epoch
    logger.info(f"Steps per epoch: {steps_per_epoch}, Total steps: {total_steps}")

    # Create model configuration
    model_config = create_model_config(cfg, feature_info)

    # Create model
    logger.info("Creating TFT model...")
    model = TFTLightningModule(
        model_config=model_config,
        learning_rate=cfg.training.learning_rate,
        weight_decay=cfg.training.weight_decay,
        optimizer=cfg.training.optimizer,
        scheduler=cfg.training.scheduler,
        scheduler_config=dict(cfg.training.scheduler_config) if cfg.training.scheduler_config else None,
        normalized_loss=cfg.training.normalized_loss,
        log_attention_weights=cfg.logging.log_attention_weights,
        total_steps=total_steps,
        log_to_mlflow=cfg.mlflow.enabled,
    )

    # Log model summary
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Total parameters: {total_params:,}")
    logger.info(f"Trainable parameters: {trainable_params:,}")

    # Setup callbacks
    callbacks = setup_callbacks(cfg)

    # Create trainer
    logger.info("Creating trainer...")
    trainer = pl.Trainer(
        max_epochs=cfg.training.max_epochs,
        accelerator=cfg.hardware.accelerator,
        devices=cfg.hardware.devices,
        strategy=cfg.hardware.strategy,
        precision=cfg.training.precision,
        gradient_clip_val=cfg.training.gradient_clip_val,
        gradient_clip_algorithm=cfg.training.gradient_clip_algorithm,
        accumulate_grad_batches=cfg.training.accumulate_grad_batches,
        callbacks=callbacks,
        logger=mlflow_logger,
        log_every_n_steps=cfg.logging.log_every_n_steps,
        deterministic=cfg.deterministic,
        enable_progress_bar=cfg.logging.enable_progress_bar,
    )

    # Start MLflow run
    with mlflow.start_run(run_id=mlflow_logger.run_id if mlflow_logger else None):
        # Log hyperparameters
        if cfg.mlflow.enabled:
            log_hyperparameters(cfg, model, data_module)
            mlflow.log_param("total_params", total_params)
            mlflow.log_param("trainable_params", trainable_params)

        # Train model
        logger.info("Starting training...")
        trainer.fit(model, data_module)

        # Get best model path
        if callbacks:
            checkpoint_callback = next(
                (c for c in callbacks if isinstance(c, ModelCheckpoint)),
                None,
            )
            if checkpoint_callback and checkpoint_callback.best_model_path:
                logger.info(f"Best model: {checkpoint_callback.best_model_path}")
                logger.info(f"Best val_loss: {checkpoint_callback.best_model_score:.4f}")

                # Load best model for evaluation
                model = TFTLightningModule.load_from_checkpoint(
                    checkpoint_callback.best_model_path,
                    model_config=model_config,
                )

                if cfg.mlflow.enabled:
                    mlflow.log_metric("best_val_loss", checkpoint_callback.best_model_score.item())
                    mlflow.log_artifact(checkpoint_callback.best_model_path)

        # Evaluate on test set
        data_module.setup("test")
        evaluate_model(trainer, model, data_module, cfg)

        # Register model
        if cfg.mlflow.enabled:
            register_model(model, cfg, mlflow_logger.run_id)

    logger.info("Training completed!")


if __name__ == "__main__":
    main()
