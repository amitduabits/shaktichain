"""PyTorch Lightning module for training."""

import logging
from typing import Any, Dict, List, Optional

import pytorch_lightning as pl
import torch
import torch.nn as nn
from torchmetrics import MeanAbsoluteError, MeanSquaredError, R2Score

logger = logging.getLogger(__name__)


class ForecastingLightningModule(pl.LightningModule):
    """Lightning module for time series forecasting."""

    def __init__(
        self,
        model: nn.Module,
        learning_rate: float = 0.001,
        weight_decay: float = 0.0001,
        optimizer_type: str = "adam",
        scheduler_type: Optional[str] = "reduce_on_plateau",
        scheduler_config: Optional[Dict[str, Any]] = None,
        loss_fn: str = "mse",
    ):
        """Initialize lightning module.

        Args:
            model: PyTorch model
            learning_rate: Learning rate
            weight_decay: Weight decay
            optimizer_type: Optimizer type (adam, adamw, sgd)
            scheduler_type: Scheduler type
            scheduler_config: Scheduler configuration
            loss_fn: Loss function (mse, mae, huber)
        """
        super().__init__()
        self.model = model
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.optimizer_type = optimizer_type
        self.scheduler_type = scheduler_type
        self.scheduler_config = scheduler_config or {}

        # Loss function
        if loss_fn == "mse":
            self.loss_fn = nn.MSELoss()
        elif loss_fn == "mae":
            self.loss_fn = nn.L1Loss()
        elif loss_fn == "huber":
            self.loss_fn = nn.HuberLoss()
        else:
            raise ValueError(f"Unknown loss function: {loss_fn}")

        # Metrics
        self.train_mae = MeanAbsoluteError()
        self.val_mae = MeanAbsoluteError()
        self.test_mae = MeanAbsoluteError()

        self.train_mse = MeanSquaredError()
        self.val_mse = MeanSquaredError()
        self.test_mse = MeanSquaredError()

        self.val_r2 = R2Score()
        self.test_r2 = R2Score()

        # Save hyperparameters
        self.save_hyperparameters(ignore=["model"])

        logger.info("Initialized ForecastingLightningModule")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor

        Returns:
            Model predictions
        """
        return self.model(x)

    def training_step(self, batch: tuple, batch_idx: int) -> torch.Tensor:
        """Training step.

        Args:
            batch: Batch of data
            batch_idx: Batch index

        Returns:
            Loss value
        """
        x, y = batch
        y_hat = self(x)

        # Handle different output shapes
        if y_hat.dim() == 3 and y.dim() == 3:
            # Multi-horizon: (batch, horizon, features)
            loss = self.loss_fn(y_hat, y)
        elif y_hat.dim() == 2 and y.dim() == 3:
            # Flatten targets
            loss = self.loss_fn(y_hat, y.view(y.size(0), -1))
        else:
            loss = self.loss_fn(y_hat, y)

        # Update metrics
        self.train_mae(y_hat, y)
        self.train_mse(y_hat, y)

        # Log metrics
        self.log("train_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log("train_mae", self.train_mae, on_step=False, on_epoch=True)
        self.log("train_mse", self.train_mse, on_step=False, on_epoch=True)

        return loss

    def validation_step(self, batch: tuple, batch_idx: int) -> None:
        """Validation step.

        Args:
            batch: Batch of data
            batch_idx: Batch index
        """
        x, y = batch
        y_hat = self(x)

        # Calculate loss
        if y_hat.dim() == 3 and y.dim() == 3:
            loss = self.loss_fn(y_hat, y)
        elif y_hat.dim() == 2 and y.dim() == 3:
            loss = self.loss_fn(y_hat, y.view(y.size(0), -1))
        else:
            loss = self.loss_fn(y_hat, y)

        # Update metrics
        self.val_mae(y_hat, y)
        self.val_mse(y_hat, y)

        # Flatten for R2 calculation
        y_flat = y.view(-1)
        y_hat_flat = y_hat.view(-1)
        self.val_r2(y_hat_flat, y_flat)

        # Log metrics
        self.log("val_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log("val_mae", self.val_mae, on_step=False, on_epoch=True, prog_bar=True)
        self.log("val_mse", self.val_mse, on_step=False, on_epoch=True)
        self.log("val_rmse", torch.sqrt(self.val_mse.compute()), on_step=False, on_epoch=True)
        self.log("val_r2", self.val_r2, on_step=False, on_epoch=True)

    def test_step(self, batch: tuple, batch_idx: int) -> None:
        """Test step.

        Args:
            batch: Batch of data
            batch_idx: Batch index
        """
        x, y = batch
        y_hat = self(x)

        # Calculate loss
        if y_hat.dim() == 3 and y.dim() == 3:
            loss = self.loss_fn(y_hat, y)
        elif y_hat.dim() == 2 and y.dim() == 3:
            loss = self.loss_fn(y_hat, y.view(y.size(0), -1))
        else:
            loss = self.loss_fn(y_hat, y)

        # Update metrics
        self.test_mae(y_hat, y)
        self.test_mse(y_hat, y)

        # Flatten for R2 calculation
        y_flat = y.view(-1)
        y_hat_flat = y_hat.view(-1)
        self.test_r2(y_hat_flat, y_flat)

        # Log metrics
        self.log("test_loss", loss, on_step=False, on_epoch=True)
        self.log("test_mae", self.test_mae, on_step=False, on_epoch=True)
        self.log("test_mse", self.test_mse, on_step=False, on_epoch=True)
        self.log("test_rmse", torch.sqrt(self.test_mse.compute()), on_step=False, on_epoch=True)
        self.log("test_r2", self.test_r2, on_step=False, on_epoch=True)

    def predict_step(self, batch: tuple, batch_idx: int) -> torch.Tensor:
        """Prediction step.

        Args:
            batch: Batch of data
            batch_idx: Batch index

        Returns:
            Predictions
        """
        x, _ = batch
        return self(x)

    def configure_optimizers(self) -> Dict[str, Any]:
        """Configure optimizers and schedulers.

        Returns:
            Dictionary with optimizer and scheduler
        """
        # Optimizer
        if self.optimizer_type == "adam":
            optimizer = torch.optim.Adam(
                self.parameters(),
                lr=self.learning_rate,
                weight_decay=self.weight_decay,
            )
        elif self.optimizer_type == "adamw":
            optimizer = torch.optim.AdamW(
                self.parameters(),
                lr=self.learning_rate,
                weight_decay=self.weight_decay,
            )
        elif self.optimizer_type == "sgd":
            optimizer = torch.optim.SGD(
                self.parameters(),
                lr=self.learning_rate,
                weight_decay=self.weight_decay,
                momentum=0.9,
            )
        else:
            raise ValueError(f"Unknown optimizer: {self.optimizer_type}")

        # Scheduler
        if not self.scheduler_type:
            return {"optimizer": optimizer}

        if self.scheduler_type == "reduce_on_plateau":
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode=self.scheduler_config.get("mode", "min"),
                factor=self.scheduler_config.get("factor", 0.5),
                patience=self.scheduler_config.get("patience", 5),
                min_lr=self.scheduler_config.get("min_lr", 1e-6),
            )
            return {
                "optimizer": optimizer,
                "lr_scheduler": {
                    "scheduler": scheduler,
                    "monitor": "val_loss",
                },
            }

        elif self.scheduler_type == "cosine":
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=self.scheduler_config.get("T_max", 100),
                eta_min=self.scheduler_config.get("eta_min", 1e-6),
            )
            return {"optimizer": optimizer, "lr_scheduler": scheduler}

        elif self.scheduler_type == "step":
            scheduler = torch.optim.lr_scheduler.StepLR(
                optimizer,
                step_size=self.scheduler_config.get("step_size", 10),
                gamma=self.scheduler_config.get("gamma", 0.1),
            )
            return {"optimizer": optimizer, "lr_scheduler": scheduler}

        else:
            logger.warning(f"Unknown scheduler type: {self.scheduler_type}")
            return {"optimizer": optimizer}
