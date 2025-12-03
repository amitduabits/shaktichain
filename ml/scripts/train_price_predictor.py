#!/usr/bin/env python
"""
Training script for SHAKTI-CHAIN price prediction model.

Usage:
    python scripts/train_price_predictor.py
    python scripts/train_price_predictor.py --architecture ensemble
    python scripts/train_price_predictor.py --data-path data/processed/price_data.parquet
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import logging
from datetime import datetime

import mlflow
import pytorch_lightning as pl
import torch
import yaml
from pytorch_lightning.callbacks import (
    EarlyStopping,
    LearningRateMonitor,
    ModelCheckpoint,
    RichProgressBar,
)
from pytorch_lightning.loggers import MLFlowLogger

from src.data.price_datamodule import PriceDataModule
from src.training.price_lightning_module import PricePredictorLightning
from src.features.price_features import PriceFeatureConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_model_config(
    architecture: str,
    input_size: int,
    load_forecast_size: int,
    hidden_size: int = 128,
    dropout: float = 0.1,
) -> dict:
    """Create model configuration.

    Args:
        architecture: Model architecture ('lstm', 'transformer', 'ensemble')
        input_size: Number of input features
        load_forecast_size: Size of load forecast
        hidden_size: Hidden layer size
        dropout: Dropout rate

    Returns:
        Model configuration dictionary
    """
    return {
        "architecture": architecture,
        "input_size": input_size,
        "load_forecast_size": load_forecast_size,
        "hidden_size": hidden_size,
        "quantiles": [0.1, 0.5, 0.9],
        "dropout": dropout,
        "num_layers": 2,
        "num_mdn_components": 3,
    }


def main():
    parser = argparse.ArgumentParser(description="Train SHAKTI-CHAIN price predictor")
    parser.add_argument("--data-path", type=str, default="data/processed/processed_data.parquet",
                        help="Path to data file")
    parser.add_argument("--architecture", type=str, default="lstm",
                        choices=["lstm", "transformer", "ensemble"],
                        help="Model architecture")
    parser.add_argument("--hidden-size", type=int, default=128,
                        help="Hidden layer size")
    parser.add_argument("--dropout", type=float, default=0.1,
                        help="Dropout rate")
    parser.add_argument("--learning-rate", type=float, default=1e-3,
                        help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=64,
                        help="Batch size")
    parser.add_argument("--max-epochs", type=int, default=100,
                        help="Maximum epochs")
    parser.add_argument("--patience", type=int, default=10,
                        help="Early stopping patience")
    parser.add_argument("--encoder-length", type=int, default=168,
                        help="Historical context length (hours)")
    parser.add_argument("--decoder-length", type=int, default=48,
                        help="Forecast horizon (hours)")
    parser.add_argument("--output-dir", type=str, default="checkpoints/price",
                        help="Output directory")
    parser.add_argument("--experiment-name", type=str, default="shakti-price-predictor",
                        help="MLflow experiment name")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")

    args = parser.parse_args()

    # Set seed
    pl.seed_everything(args.seed, workers=True)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create data module
    logger.info("Creating data module...")
    data_module = PriceDataModule(
        data_path=args.data_path,
        target_col="price_inr_mwh",
        load_col="load_mw",
        encoder_length=args.encoder_length,
        decoder_length=args.decoder_length,
        batch_size=args.batch_size,
        num_workers=4,
        train_start="2022-01-01",
        train_end="2023-12-31",
        val_start="2024-01-01",
        val_end="2024-06-30",
        test_start="2024-07-01",
        test_end="2024-12-31",
    )

    # Setup to get feature info
    data_module.setup("fit")
    feature_info = data_module.get_feature_info()
    logger.info(f"Feature info: {feature_info}")

    # Calculate total steps for OneCycleLR
    steps_per_epoch = len(data_module.train_dataloader())
    total_steps = args.max_epochs * steps_per_epoch
    logger.info(f"Steps per epoch: {steps_per_epoch}, Total steps: {total_steps}")

    # Create model config
    model_config = create_model_config(
        architecture=args.architecture,
        input_size=feature_info["input_size"],
        load_forecast_size=feature_info["load_forecast_size"],
        hidden_size=args.hidden_size,
        dropout=args.dropout,
    )

    # Create model
    logger.info(f"Creating {args.architecture} price predictor...")
    model = PricePredictorLightning(
        model_config=model_config,
        learning_rate=args.learning_rate,
        weight_decay=1e-5,
        optimizer="adam",
        scheduler="onecycle",
        total_steps=total_steps,
        loss_config={
            "spike_weight": 2.0,  # Emphasize spike detection
            "regime_weight": 0.5,
            "mdn_weight": 0.1,
        },
    )

    # Model summary
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Total parameters: {total_params:,}")

    # Setup MLflow
    mlflow.set_tracking_uri("mlruns")
    run_name = f"price_{args.architecture}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    mlflow_logger = MLFlowLogger(
        experiment_name=args.experiment_name,
        tracking_uri="mlruns",
        run_name=run_name,
    )

    # Callbacks
    callbacks = [
        EarlyStopping(
            monitor="val_loss",
            patience=args.patience,
            mode="min",
            verbose=True,
        ),
        ModelCheckpoint(
            dirpath=str(output_dir),
            filename=f"price_{args.architecture}" + "-{epoch:02d}-{val_mape:.2f}",
            monitor="val_mape",
            mode="min",
            save_top_k=3,
            save_last=True,
        ),
        LearningRateMonitor(logging_interval="step"),
        RichProgressBar(),
    ]

    # Trainer
    trainer = pl.Trainer(
        max_epochs=args.max_epochs,
        accelerator="auto",
        devices=1,
        precision="16-mixed",
        gradient_clip_val=1.0,
        accumulate_grad_batches=2,
        callbacks=callbacks,
        logger=mlflow_logger,
        log_every_n_steps=10,
        deterministic=False,
    )

    # Train
    with mlflow.start_run(run_id=mlflow_logger.run_id):
        # Log parameters
        mlflow.log_params({
            "architecture": args.architecture,
            "hidden_size": args.hidden_size,
            "dropout": args.dropout,
            "learning_rate": args.learning_rate,
            "batch_size": args.batch_size,
            "encoder_length": args.encoder_length,
            "decoder_length": args.decoder_length,
            "total_params": total_params,
        })

        logger.info("Starting training...")
        trainer.fit(model, data_module)

        # Get best model
        best_model_path = callbacks[1].best_model_path
        best_mape = callbacks[1].best_model_score

        if best_model_path:
            logger.info(f"Best model: {best_model_path}")
            logger.info(f"Best MAPE: {best_mape:.2f}%")

            mlflow.log_metric("best_val_mape", best_mape.item())
            mlflow.log_artifact(best_model_path)

            # Test
            logger.info("Running test evaluation...")
            data_module.setup("test")
            test_results = trainer.test(model, data_module)

            if test_results:
                for key, value in test_results[0].items():
                    mlflow.log_metric(f"final_{key}", value)

                # Check target metrics
                test_mape = test_results[0].get("test_mape", float("inf"))
                test_spike_recall = test_results[0].get("test_spike_recall", 0)
                test_direction_acc = test_results[0].get("test_direction_acc", 0)

                logger.info(f"\nTarget Metrics:")
                logger.info(f"  MAPE: {test_mape:.2f}% (target: <10%)")
                logger.info(f"  Spike Recall: {test_spike_recall * 100:.1f}% (target: >80%)")
                logger.info(f"  Direction Accuracy: {test_direction_acc:.1f}% (target: >65%)")

                mape_met = test_mape < 10
                spike_met = test_spike_recall > 0.8
                direction_met = test_direction_acc > 65

                mlflow.log_metric("mape_target_met", int(mape_met))
                mlflow.log_metric("spike_target_met", int(spike_met))
                mlflow.log_metric("direction_target_met", int(direction_met))

                if mape_met and spike_met and direction_met:
                    logger.info("All targets met!")
                    mlflow.set_tag("targets", "achieved")
                else:
                    logger.warning("Some targets not met")
                    mlflow.set_tag("targets", "not_achieved")

        # Register model
        mlflow.pytorch.log_model(
            model,
            "model",
            registered_model_name=f"shakti-price-{args.architecture}",
        )

    logger.info("Training complete!")
    logger.info(f"Checkpoints saved to: {output_dir}")


if __name__ == "__main__":
    main()
