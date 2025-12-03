"""Training script with MLflow tracking."""

import logging
import sys
from pathlib import Path

import hydra
import mlflow
import pytorch_lightning as pl
from omegaconf import DictConfig, OmegaConf
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
from pytorch_lightning.loggers import MLFlowLogger, TensorBoardLogger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loaders import TimeSeriesDataModule
from src.models import LSTMForecaster, TimeSeriesTransformer
from src.training.lightning_module import ForecastingLightningModule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_model(cfg: DictConfig) -> pl.LightningModule:
    """Create model from configuration.

    Args:
        cfg: Hydra configuration

    Returns:
        PyTorch Lightning module
    """
    model_type = cfg.model.type

    if model_type == "lstm":
        model = LSTMForecaster(
            input_size=cfg.model.architecture.input_size,
            hidden_size=cfg.model.architecture.hidden_size,
            num_layers=cfg.model.architecture.num_layers,
            output_size=cfg.model.architecture.get("output_size", cfg.model.forecasting.prediction_horizon),
            dropout=cfg.model.architecture.dropout,
            bidirectional=cfg.model.architecture.get("bidirectional", False),
        )

    elif model_type == "transformer":
        model = TimeSeriesTransformer(
            input_size=cfg.model.architecture.get("input_size", 32),
            d_model=cfg.model.architecture.d_model,
            nhead=cfg.model.architecture.nhead,
            num_layers=cfg.model.architecture.num_encoder_layers,
            dim_feedforward=cfg.model.architecture.dim_feedforward,
            prediction_horizon=cfg.model.forecasting.prediction_horizon,
            num_targets=len(cfg.model.forecasting.target_columns),
            dropout=cfg.model.architecture.dropout,
        )

    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Wrap in Lightning module
    lightning_model = ForecastingLightningModule(
        model=model,
        learning_rate=cfg.training.optimizer.lr,
        weight_decay=cfg.training.optimizer.weight_decay,
        optimizer_type=cfg.training.optimizer.type,
        scheduler_type=cfg.training.scheduler.type,
        scheduler_config=dict(cfg.training.scheduler),
        loss_fn=cfg.training.loss.type,
    )

    return lightning_model


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """Main training function.

    Args:
        cfg: Hydra configuration
    """
    logger.info("Starting training...")
    logger.info(f"Configuration:\n{OmegaConf.to_yaml(cfg)}")

    # Set seed
    pl.seed_everything(cfg.seed, workers=True)

    # Setup MLflow
    mlflow.set_tracking_uri(cfg.logging.mlflow.tracking_uri)
    mlflow.set_experiment(cfg.logging.mlflow.experiment_name)

    # Create data module
    logger.info("Creating data module...")

    # Load processed data path
    data_path = Path(cfg.paths.processed_data_dir) / "processed_data.parquet"

    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        logger.error("Please run preprocess_data.py first")
        return

    # Get feature columns (example - should come from preprocessing)
    feature_columns = [
        "load_mw",
        "frequency_hz",
        "price_inr_mwh",
        "temperature_c",
        "humidity_pct",
        "hour_sin",
        "hour_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "is_weekend",
        "is_holiday",
        "is_peak_hour",
    ]

    target_columns = cfg.model.forecasting.target_columns

    data_module = TimeSeriesDataModule(
        data_path=str(data_path),
        sequence_length=cfg.model.forecasting.sequence_length,
        prediction_horizon=cfg.model.forecasting.prediction_horizon,
        feature_columns=feature_columns,
        target_columns=target_columns,
        batch_size=cfg.data.loader.batch_size,
        num_workers=cfg.data.loader.num_workers,
        train_split=cfg.data.split.train_size,
        val_split=cfg.data.split.val_size,
        test_split=cfg.data.split.test_size,
        pin_memory=cfg.data.loader.pin_memory,
    )

    # Create model
    logger.info("Creating model...")
    model = create_model(cfg)

    # Create loggers
    loggers = []

    # MLflow logger
    mlflow_logger = MLFlowLogger(
        experiment_name=cfg.logging.mlflow.experiment_name,
        tracking_uri=cfg.logging.mlflow.tracking_uri,
        run_name=cfg.experiment.run_name,
        tags=dict(cfg.experiment.tags),
    )
    loggers.append(mlflow_logger)

    # TensorBoard logger
    if cfg.logging.tensorboard.enabled:
        tb_logger = TensorBoardLogger(
            save_dir=cfg.logging.tensorboard.save_dir,
            name=cfg.logging.tensorboard.name,
        )
        loggers.append(tb_logger)

    # Create callbacks
    callbacks = []

    # Model checkpoint
    checkpoint_callback = ModelCheckpoint(
        dirpath=Path(cfg.paths.models_dir) / cfg.experiment.run_name,
        filename=cfg.training.checkpoint.filename,
        monitor=cfg.training.checkpoint.monitor,
        mode=cfg.training.checkpoint.mode,
        save_top_k=cfg.training.checkpoint.save_top_k,
        save_last=cfg.training.checkpoint.save_last,
    )
    callbacks.append(checkpoint_callback)

    # Early stopping
    if cfg.training.early_stopping.enabled:
        early_stop_callback = EarlyStopping(
            monitor=cfg.training.early_stopping.monitor,
            patience=cfg.training.early_stopping.patience,
            mode=cfg.training.early_stopping.mode,
            min_delta=cfg.training.early_stopping.min_delta,
        )
        callbacks.append(early_stop_callback)

    # Create trainer
    logger.info("Creating trainer...")
    trainer = pl.Trainer(
        max_epochs=cfg.training.epochs,
        accelerator=cfg.training.accelerator,
        devices=cfg.training.devices,
        precision=cfg.training.precision,
        gradient_clip_val=cfg.training.gradient_clip_val,
        accumulate_grad_batches=cfg.training.accumulate_grad_batches,
        check_val_every_n_epoch=cfg.training.check_val_every_n_epoch,
        deterministic=cfg.training.deterministic,
        benchmark=cfg.training.benchmark,
        fast_dev_run=cfg.training.fast_dev_run,
        limit_train_batches=cfg.training.limit_train_batches,
        limit_val_batches=cfg.training.limit_val_batches,
        limit_test_batches=cfg.training.limit_test_batches,
        callbacks=callbacks,
        logger=loggers,
    )

    # Log hyperparameters
    if cfg.logging.log_hyperparameters:
        mlflow_logger.log_hyperparams(OmegaConf.to_container(cfg, resolve=True))

    # Train
    logger.info("Starting training...")
    trainer.fit(model, datamodule=data_module)

    # Test
    logger.info("Testing model...")
    trainer.test(model, datamodule=data_module)

    # Log best model to MLflow
    if cfg.logging.mlflow.log_model:
        logger.info("Logging model to MLflow...")
        mlflow.pytorch.log_model(model.model, "model")

    logger.info("Training complete!")
    logger.info(f"Best model checkpoint: {checkpoint_callback.best_model_path}")


if __name__ == "__main__":
    main()
