"""PyTorch Lightning module for price prediction."""

import torch
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl
from typing import Dict, Any, Optional, List, Tuple
import logging
import numpy as np

try:
    from ..models.price_predictor import (
        PricePredictor,
        PricePrediction,
        LSTMPricePredictor,
        TransformerPricePredictor,
        EnsemblePricePredictor,
    )
except ImportError:
    try:
        from models.price_predictor import (
            PricePredictor,
            PricePrediction,
            LSTMPricePredictor,
            TransformerPricePredictor,
            EnsemblePricePredictor,
        )
    except ImportError:
        PricePredictor = None
        PricePrediction = Any
        LSTMPricePredictor = None
        TransformerPricePredictor = None
        EnsemblePricePredictor = None

logger = logging.getLogger(__name__)


class PriceLoss(nn.Module):
    """Combined loss function for price prediction.

    Components:
    1. Quantile loss for distribution
    2. MDN negative log-likelihood for variance
    3. Spike detection BCE loss
    4. Regime classification CE loss

    Args:
        quantiles: List of quantiles
        spike_weight: Weight for spike detection loss
        regime_weight: Weight for regime classification loss
        mdn_weight: Weight for MDN loss
    """

    def __init__(
        self,
        quantiles: List[float] = [0.1, 0.5, 0.9],
        spike_weight: float = 1.0,
        regime_weight: float = 0.5,
        mdn_weight: float = 0.1,
    ):
        super().__init__()
        self.quantiles = quantiles
        self.spike_weight = spike_weight
        self.regime_weight = regime_weight
        self.mdn_weight = mdn_weight

    def quantile_loss(
        self,
        predictions: Dict[float, torch.Tensor],
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """Calculate quantile (pinball) loss.

        Args:
            predictions: Quantile predictions {q: tensor}
            targets: True values

        Returns:
            Average quantile loss
        """
        losses = []
        for q, pred in predictions.items():
            errors = targets - pred
            loss = torch.max(q * errors, (q - 1) * errors)
            losses.append(loss.mean())
        return torch.stack(losses).mean()

    def gaussian_nll_loss(
        self,
        mean: torch.Tensor,
        variance: torch.Tensor,
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """Gaussian negative log-likelihood loss.

        Args:
            mean: Predicted mean
            variance: Predicted variance
            targets: True values

        Returns:
            NLL loss
        """
        # Clamp variance to prevent numerical issues
        variance = torch.clamp(variance, min=1e-6)

        # NLL for Gaussian
        nll = 0.5 * (torch.log(variance) + (targets - mean) ** 2 / variance)
        return nll.mean()

    def forward(
        self,
        prediction: PricePrediction,
        targets: torch.Tensor,
        spike_labels: Optional[torch.Tensor] = None,
        regime_labels: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """Calculate total loss.

        Args:
            prediction: PricePrediction from model
            targets: True price values
            spike_labels: True spike indicators (optional)
            regime_labels: True regime labels (optional)

        Returns:
            total_loss: Combined loss
            loss_dict: Dictionary of individual losses
        """
        loss_dict = {}

        # Quantile loss
        quantile_loss = self.quantile_loss(prediction.quantiles, targets)
        loss_dict["quantile_loss"] = quantile_loss

        # Gaussian NLL for variance estimation
        nll_loss = self.gaussian_nll_loss(prediction.mean, prediction.variance, targets)
        loss_dict["nll_loss"] = nll_loss

        # Spike detection loss
        spike_loss = torch.tensor(0.0, device=targets.device)
        if spike_labels is not None and prediction.spike_prob is not None:
            spike_loss = F.binary_cross_entropy(
                prediction.spike_prob,
                spike_labels,
                reduction="mean",
            )
            loss_dict["spike_loss"] = spike_loss

        # Regime classification loss
        regime_loss = torch.tensor(0.0, device=targets.device)
        if regime_labels is not None and prediction.regime_probs is not None:
            regime_loss = F.cross_entropy(
                prediction.regime_probs,
                regime_labels,
                reduction="mean",
            )
            loss_dict["regime_loss"] = regime_loss

        # Total loss
        total_loss = (
            quantile_loss +
            self.mdn_weight * nll_loss +
            self.spike_weight * spike_loss +
            self.regime_weight * regime_loss
        )
        loss_dict["total_loss"] = total_loss

        return total_loss, loss_dict


class PricePredictorLightning(pl.LightningModule):
    """Lightning module for price prediction.

    Args:
        model_config: Configuration for PricePredictor
        learning_rate: Learning rate
        weight_decay: Weight decay
        optimizer: Optimizer type
        scheduler: Scheduler type
        scheduler_config: Scheduler configuration
        loss_config: Loss function configuration
    """

    def __init__(
        self,
        model_config: Dict[str, Any],
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        optimizer: str = "adam",
        scheduler: Optional[str] = "onecycle",
        scheduler_config: Optional[Dict[str, Any]] = None,
        loss_config: Optional[Dict[str, Any]] = None,
        total_steps: Optional[int] = None,
    ):
        super().__init__()
        if PricePredictor is None:
            raise ImportError(
                "PricePredictor is unavailable. "
                "Ensure the model module is installed before instantiating PricePredictorLightning."
            )
        self.save_hyperparameters()

        # Create model
        self.model = PricePredictor(
            architecture=model_config.get("architecture", "lstm"),
            input_size=model_config["input_size"],
            load_forecast_size=model_config.get("load_forecast_size", 48),
            hidden_size=model_config.get("hidden_size", 128),
            quantiles=model_config.get("quantiles", [0.1, 0.5, 0.9]),
            dropout=model_config.get("dropout", 0.1),
        )

        # Loss function
        loss_config = loss_config or {}
        self.loss_fn = PriceLoss(
            quantiles=model_config.get("quantiles", [0.1, 0.5, 0.9]),
            spike_weight=loss_config.get("spike_weight", 1.0),
            regime_weight=loss_config.get("regime_weight", 0.5),
            mdn_weight=loss_config.get("mdn_weight", 0.1),
        )

        self.quantiles = model_config.get("quantiles", [0.1, 0.5, 0.9])
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.optimizer_type = optimizer
        self.scheduler_type = scheduler
        self.scheduler_config = scheduler_config or {}
        self.total_steps = total_steps

        # Best metrics tracking
        self.best_val_mape = float("inf")
        self.best_val_spike_recall = 0.0

    def forward(
        self,
        features: torch.Tensor,
        load_forecast: Optional[torch.Tensor] = None,
    ) -> PricePrediction:
        """Forward pass."""
        return self.model(features, load_forecast=load_forecast)

    def _calculate_metrics(
        self,
        prediction: PricePrediction,
        targets: torch.Tensor,
        spike_labels: Optional[torch.Tensor] = None,
        prefix: str = "train",
    ) -> Dict[str, torch.Tensor]:
        """Calculate evaluation metrics.

        Args:
            prediction: Model prediction
            targets: True values
            spike_labels: True spike indicators
            prefix: Metric name prefix

        Returns:
            Dictionary of metrics
        """
        metrics = {}

        # Point forecast metrics
        point_pred = prediction.point_forecast

        # MAE
        mae = torch.abs(point_pred - targets).mean()
        metrics[f"{prefix}_mae"] = mae

        # RMSE
        rmse = torch.sqrt(torch.mean((point_pred - targets) ** 2))
        metrics[f"{prefix}_rmse"] = rmse

        # MAPE
        epsilon = 1e-8
        mape = torch.mean(torch.abs(point_pred - targets) / (torch.abs(targets) + epsilon)) * 100
        metrics[f"{prefix}_mape"] = mape

        # Direction accuracy
        if targets.dim() > 1 and targets.size(-1) > 1:
            pred_direction = (point_pred[:, 1:] - point_pred[:, :-1]) > 0
            true_direction = (targets[:, 1:] - targets[:, :-1]) > 0
            direction_acc = (pred_direction == true_direction).float().mean() * 100
            metrics[f"{prefix}_direction_acc"] = direction_acc

        # Coverage (90% PI)
        if 0.1 in prediction.quantiles and 0.9 in prediction.quantiles:
            lower = prediction.quantiles[0.1]
            upper = prediction.quantiles[0.9]
            coverage = ((targets >= lower) & (targets <= upper)).float().mean()
            metrics[f"{prefix}_coverage_90"] = coverage

        # Spike detection metrics
        if spike_labels is not None and prediction.spike_prob is not None:
            spike_pred = (prediction.spike_prob > 0.5).float()

            # Spike recall (most important for risk)
            true_spikes = spike_labels.sum()
            if true_spikes > 0:
                spike_recall = (spike_pred * spike_labels).sum() / true_spikes
                metrics[f"{prefix}_spike_recall"] = spike_recall

            # Spike precision
            pred_spikes = spike_pred.sum()
            if pred_spikes > 0:
                spike_precision = (spike_pred * spike_labels).sum() / pred_spikes
                metrics[f"{prefix}_spike_precision"] = spike_precision

            # Spike F1
            if true_spikes > 0 and pred_spikes > 0:
                spike_f1 = 2 * spike_precision * spike_recall / (spike_precision + spike_recall + epsilon)
                metrics[f"{prefix}_spike_f1"] = spike_f1

        return metrics

    def training_step(self, batch: Dict[str, torch.Tensor], batch_idx: int):
        """Training step."""
        features = batch["features"]
        targets = batch["target"]
        load_forecast = batch.get("load_forecast")
        spike_labels = batch.get("spike_labels")
        regime_labels = batch.get("regime_labels")

        # Forward pass
        prediction = self(features, load_forecast=load_forecast)

        # Calculate loss
        loss, loss_dict = self.loss_fn(
            prediction, targets,
            spike_labels=spike_labels,
            regime_labels=regime_labels,
        )

        # Calculate metrics
        metrics = self._calculate_metrics(prediction, targets, spike_labels, prefix="train")

        # Log everything
        self.log_dict(loss_dict, on_step=True, on_epoch=True, prog_bar=False)
        self.log_dict(metrics, on_step=False, on_epoch=True, prog_bar=True)

        return loss

    def validation_step(self, batch: Dict[str, torch.Tensor], batch_idx: int):
        """Validation step."""
        features = batch["features"]
        targets = batch["target"]
        load_forecast = batch.get("load_forecast")
        spike_labels = batch.get("spike_labels")
        regime_labels = batch.get("regime_labels")

        # Forward pass
        prediction = self(features, load_forecast=load_forecast)

        # Calculate loss
        loss, loss_dict = self.loss_fn(
            prediction, targets,
            spike_labels=spike_labels,
            regime_labels=regime_labels,
        )

        # Calculate metrics
        metrics = self._calculate_metrics(prediction, targets, spike_labels, prefix="val")

        # Add val_ prefix to loss dict
        val_loss_dict = {f"val_{k}": v for k, v in loss_dict.items()}

        # Log everything
        self.log_dict(val_loss_dict, on_step=False, on_epoch=True, prog_bar=False)
        self.log_dict(metrics, on_step=False, on_epoch=True, prog_bar=True)
        self.log("val_loss", loss, on_step=False, on_epoch=True, prog_bar=True)

        return loss

    def test_step(self, batch: Dict[str, torch.Tensor], batch_idx: int):
        """Test step."""
        features = batch["features"]
        targets = batch["target"]
        load_forecast = batch.get("load_forecast")
        spike_labels = batch.get("spike_labels")
        regime_labels = batch.get("regime_labels")

        # Forward pass
        prediction = self(features, load_forecast=load_forecast)

        # Calculate loss
        loss, loss_dict = self.loss_fn(
            prediction, targets,
            spike_labels=spike_labels,
            regime_labels=regime_labels,
        )

        # Calculate metrics
        metrics = self._calculate_metrics(prediction, targets, spike_labels, prefix="test")

        # Add test_ prefix
        test_loss_dict = {f"test_{k}": v for k, v in loss_dict.items()}

        self.log_dict(test_loss_dict, on_step=False, on_epoch=True)
        self.log_dict(metrics, on_step=False, on_epoch=True, prog_bar=True)

        return loss

    def predict_step(
        self,
        batch: Dict[str, torch.Tensor],
        batch_idx: int,
        dataloader_idx: int = 0,
    ):
        """Prediction step."""
        features = batch["features"]
        load_forecast = batch.get("load_forecast")

        prediction = self(features, load_forecast=load_forecast)

        return {
            "point_forecast": prediction.point_forecast,
            "mean": prediction.mean,
            "variance": prediction.variance,
            "quantiles": prediction.quantiles,
            "spike_prob": prediction.spike_prob,
            "regime_probs": prediction.regime_probs,
            "targets": batch.get("target"),
        }

    def on_validation_epoch_end(self):
        """Track best metrics."""
        metrics = self.trainer.callback_metrics

        val_mape = metrics.get("val_mape")
        val_spike_recall = metrics.get("val_spike_recall")

        if val_mape is not None and val_mape < self.best_val_mape:
            self.best_val_mape = val_mape.item()

        if val_spike_recall is not None and val_spike_recall > self.best_val_spike_recall:
            self.best_val_spike_recall = val_spike_recall.item()

    def configure_optimizers(self):
        """Configure optimizers and schedulers."""
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
        else:
            raise ValueError(f"Unknown optimizer: {self.optimizer_type}")

        if self.scheduler_type is None:
            return optimizer

        if self.scheduler_type == "onecycle":
            if self.total_steps is None:
                raise ValueError("OneCycleLR requires total_steps")

            scheduler = torch.optim.lr_scheduler.OneCycleLR(
                optimizer,
                max_lr=self.learning_rate,
                total_steps=self.total_steps,
                pct_start=self.scheduler_config.get("pct_start", 0.3),
                anneal_strategy=self.scheduler_config.get("anneal_strategy", "cos"),
            )
            return {
                "optimizer": optimizer,
                "lr_scheduler": {
                    "scheduler": scheduler,
                    "interval": "step",
                    "frequency": 1,
                },
            }

        elif self.scheduler_type == "plateau":
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode="min",
                factor=self.scheduler_config.get("factor", 0.5),
                patience=self.scheduler_config.get("patience", 5),
            )
            return {
                "optimizer": optimizer,
                "lr_scheduler": {
                    "scheduler": scheduler,
                    "monitor": "val_loss",
                    "interval": "epoch",
                },
            }

        else:
            raise ValueError(f"Unknown scheduler: {self.scheduler_type}")
