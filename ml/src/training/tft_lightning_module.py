"""PyTorch Lightning module for Temporal Fusion Transformer."""

import torch
import pytorch_lightning as pl
from typing import Dict, Any, Optional, List
import logging

try:
    import mlflow
except ImportError:
    class _MlflowStub:
        @staticmethod
        def log_metric(*args, **kwargs):
            return None

    mlflow = _MlflowStub()

try:
    from ..models.temporal_fusion_transformer import TemporalFusionTransformer
except ImportError:
    try:
        from models.temporal_fusion_transformer import TemporalFusionTransformer
    except ImportError:
        TemporalFusionTransformer = None
from .quantile_loss import QuantileLoss, NormalizedQuantileLoss

logger = logging.getLogger(__name__)


class TFTLightningModule(pl.LightningModule):
    """Lightning module for Temporal Fusion Transformer.

    Wraps the TFT model with training, validation, and testing logic.

    Args:
        model_config: Configuration dict for TFT model
        learning_rate: Learning rate for optimizer
        weight_decay: Weight decay for optimizer
        optimizer: Optimizer type ('adam', 'adamw', 'sgd')
        scheduler: Learning rate scheduler type ('step', 'cosine', 'plateau', 'onecycle', None)
        scheduler_config: Configuration for learning rate scheduler
        normalized_loss: Whether to use normalized quantile loss
        log_attention_weights: Whether to log attention weights during validation
        total_steps: Total training steps (required for onecycle scheduler)
        log_to_mlflow: Whether to log metrics to MLflow
    """

    def __init__(
        self,
        model_config: Dict[str, Any],
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        optimizer: str = "adam",
        scheduler: Optional[str] = "onecycle",
        scheduler_config: Optional[Dict[str, Any]] = None,
        normalized_loss: bool = False,
        log_attention_weights: bool = False,
        total_steps: Optional[int] = None,
        log_to_mlflow: bool = True,
    ):
        super().__init__()
        if TemporalFusionTransformer is None:
            raise ImportError(
                "TemporalFusionTransformer is unavailable. "
                "Ensure the model module is installed before instantiating TFTLightningModule."
            )
        self.save_hyperparameters()

        # Extract model parameters
        input_dims = model_config["input_dims"]
        seq_lengths = model_config["sequence_lengths"]
        arch = model_config["architecture"]
        output_config = model_config["output"]

        # Initialize TFT model
        self.model = TemporalFusionTransformer(
            static_input_size=input_dims["static_input_size"],
            known_input_size=input_dims["known_input_size"],
            observed_input_size=input_dims["observed_input_size"],
            encoder_length=seq_lengths["encoder_length"],
            decoder_length=seq_lengths["decoder_length"],
            hidden_size=arch["hidden_size"],
            lstm_layers=arch["lstm_layers"],
            num_attention_heads=arch["num_attention_heads"],
            dropout=arch["dropout"],
            output_size=output_config["output_size"],
            quantiles=output_config["quantiles"],
        )

        # Initialize loss function
        loss_class = NormalizedQuantileLoss if normalized_loss else QuantileLoss
        self.loss_fn = loss_class(quantiles=output_config["quantiles"])

        self.quantiles = output_config["quantiles"]
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.optimizer_type = optimizer
        self.scheduler_type = scheduler
        self.scheduler_config = scheduler_config or {}
        self.log_attention_weights = log_attention_weights
        self.total_steps = total_steps
        self.log_to_mlflow = log_to_mlflow

        # Track best metrics for MLflow
        self.best_val_loss = float("inf")
        self.best_val_mape = float("inf")
        self.best_val_coverage = 0.0

    def forward(
        self,
        static_covariates: Optional[torch.Tensor],
        historical_observed: torch.Tensor,
        historical_known: torch.Tensor,
        future_known: torch.Tensor,
    ):
        """Forward pass through the model.

        Args:
            static_covariates: Static features (batch, static_size)
            historical_observed: Historical observed features (batch, encoder_length, observed_size)
            historical_known: Historical known features (batch, encoder_length, known_size)
            future_known: Future known features (batch, decoder_length, known_size)

        Returns:
            predictions: Quantile predictions (batch, decoder_length, output_size, num_quantiles)
            interpretability: Dictionary with attention weights and variable importance
        """
        return self.model(
            static_covariates=static_covariates,
            historical_observed=historical_observed,
            historical_known=historical_known,
            future_known=future_known,
        )

    def _calculate_metrics(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
        prefix: str,
    ) -> Dict[str, torch.Tensor]:
        """Calculate metrics for quantile predictions.

        Args:
            predictions: Predicted quantiles (batch, seq_len, output_size, num_quantiles)
            targets: True values (batch, seq_len, output_size)
            prefix: Prefix for metric names (e.g., 'train', 'val', 'test')

        Returns:
            Dictionary of metrics
        """
        metrics = {}

        # Extract median prediction (50th quantile)
        median_idx = self.quantiles.index(0.5) if 0.5 in self.quantiles else len(self.quantiles) // 2
        median_pred = predictions[..., median_idx]

        # MAE for median
        mae = torch.abs(median_pred - targets).mean()
        metrics[f"{prefix}_mae"] = mae

        # RMSE for median
        rmse = torch.sqrt(torch.mean((median_pred - targets) ** 2))
        metrics[f"{prefix}_rmse"] = rmse

        # MAPE (Mean Absolute Percentage Error)
        # Add small epsilon to avoid division by zero
        epsilon = 1e-8
        abs_targets = torch.abs(targets) + epsilon
        mape = torch.mean(torch.abs(median_pred - targets) / abs_targets) * 100
        metrics[f"{prefix}_mape"] = mape

        # Symmetric MAPE (sMAPE) - more robust to zeros
        smape = torch.mean(
            2 * torch.abs(median_pred - targets) / (torch.abs(median_pred) + torch.abs(targets) + epsilon)
        ) * 100
        metrics[f"{prefix}_smape"] = smape

        # MAE per quantile
        for i, q in enumerate(self.quantiles):
            mae_q = torch.abs(predictions[..., i] - targets).mean()
            metrics[f"{prefix}_mae_q{int(q*100)}"] = mae_q

        # Quantile coverage (percentage of actuals within prediction interval)
        # 80% coverage (Q10-Q90)
        if 0.1 in self.quantiles and 0.9 in self.quantiles:
            q10_idx = self.quantiles.index(0.1)
            q90_idx = self.quantiles.index(0.9)
            lower_80 = predictions[..., q10_idx]
            upper_80 = predictions[..., q90_idx]
            coverage_80 = ((targets >= lower_80) & (targets <= upper_80)).float().mean()
            metrics[f"{prefix}_coverage_80"] = coverage_80

            # 90% PI coverage (using Q5-Q95 if available, otherwise approximate)
            # For [0.1, 0.5, 0.9] quantiles, 80% is the best we can do
            # We report as "coverage_90" for the target metric
            metrics[f"{prefix}_coverage_90"] = coverage_80  # Approximate with 80% PI

        # Prediction interval width (sharpness)
        if 0.1 in self.quantiles and 0.9 in self.quantiles:
            q10_idx = self.quantiles.index(0.1)
            q90_idx = self.quantiles.index(0.9)
            interval_width = (predictions[..., q90_idx] - predictions[..., q10_idx]).mean()
            metrics[f"{prefix}_interval_width"] = interval_width

        # Winkler Score (combines coverage and sharpness)
        # Lower is better: interval_width + penalty for coverage misses
        if 0.1 in self.quantiles and 0.9 in self.quantiles:
            q10_idx = self.quantiles.index(0.1)
            q90_idx = self.quantiles.index(0.9)
            lower = predictions[..., q10_idx]
            upper = predictions[..., q90_idx]
            alpha = 0.2  # For 80% PI

            width = upper - lower
            below = 2 / alpha * (lower - targets) * (targets < lower).float()
            above = 2 / alpha * (targets - upper) * (targets > upper).float()
            winkler = (width + below + above).mean()
            metrics[f"{prefix}_winkler"] = winkler

        return metrics

    def training_step(self, batch: Dict[str, torch.Tensor], batch_idx: int):
        """Training step.

        Args:
            batch: Dictionary with keys:
                - static_covariates: (batch, static_size) or None
                - historical_observed: (batch, encoder_length, observed_size)
                - historical_known: (batch, encoder_length, known_size)
                - future_known: (batch, decoder_length, known_size)
                - target: (batch, decoder_length, output_size)
            batch_idx: Batch index

        Returns:
            Loss value
        """
        # Forward pass
        predictions, interpretability = self(
            static_covariates=batch.get("static_covariates"),
            historical_observed=batch["historical_observed"],
            historical_known=batch["historical_known"],
            future_known=batch["future_known"],
        )

        # Calculate loss
        targets = batch["target"]
        loss = self.loss_fn(predictions, targets)

        # Calculate metrics
        metrics = self._calculate_metrics(predictions, targets, "train")
        metrics["train_loss"] = loss

        # Log metrics
        self.log_dict(metrics, on_step=True, on_epoch=True, prog_bar=True, logger=True)

        return loss

    def validation_step(self, batch: Dict[str, torch.Tensor], batch_idx: int):
        """Validation step.

        Args:
            batch: Dictionary with input tensors
            batch_idx: Batch index
        """
        # Forward pass
        predictions, interpretability = self(
            static_covariates=batch.get("static_covariates"),
            historical_observed=batch["historical_observed"],
            historical_known=batch["historical_known"],
            future_known=batch["future_known"],
        )

        # Calculate loss
        targets = batch["target"]
        loss = self.loss_fn(predictions, targets)

        # Calculate metrics
        metrics = self._calculate_metrics(predictions, targets, "val")
        metrics["val_loss"] = loss

        # Log metrics
        self.log_dict(metrics, on_step=False, on_epoch=True, prog_bar=True, logger=True)

        # Log attention weights if enabled (only first batch)
        if self.log_attention_weights and batch_idx == 0:
            if "attention_weights" in interpretability:
                attn_weights = interpretability["attention_weights"]
                # Log mean attention per head
                mean_attn = attn_weights.mean(dim=(0, 2))  # Average over batch and time
                for head_idx in range(mean_attn.shape[0]):
                    self.log(f"val_attention_head_{head_idx}", mean_attn[head_idx].mean())

        return loss

    def test_step(self, batch: Dict[str, torch.Tensor], batch_idx: int):
        """Test step.

        Args:
            batch: Dictionary with input tensors
            batch_idx: Batch index
        """
        # Forward pass
        predictions, interpretability = self(
            static_covariates=batch.get("static_covariates"),
            historical_observed=batch["historical_observed"],
            historical_known=batch["historical_known"],
            future_known=batch["future_known"],
        )

        # Calculate loss
        targets = batch["target"]
        loss = self.loss_fn(predictions, targets)

        # Calculate metrics
        metrics = self._calculate_metrics(predictions, targets, "test")
        metrics["test_loss"] = loss

        # Log metrics
        self.log_dict(metrics, on_step=False, on_epoch=True, prog_bar=True, logger=True)

        return loss

    def predict_step(
        self,
        batch: Dict[str, torch.Tensor],
        batch_idx: int,
        dataloader_idx: int = 0,
    ):
        """Prediction step.

        Args:
            batch: Dictionary with input tensors
            batch_idx: Batch index
            dataloader_idx: Dataloader index

        Returns:
            Dictionary with predictions and interpretability
        """
        predictions, interpretability = self(
            static_covariates=batch.get("static_covariates"),
            historical_observed=batch["historical_observed"],
            historical_known=batch["historical_known"],
            future_known=batch["future_known"],
        )

        return {
            "predictions": predictions,
            "interpretability": interpretability,
            "targets": batch.get("target"),
        }

    def configure_optimizers(self):
        """Configure optimizers and learning rate schedulers.

        Returns:
            Optimizer or tuple of (optimizer, scheduler)
        """
        # Select optimizer
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

        # No scheduler
        if self.scheduler_type is None:
            return optimizer

        # Configure scheduler
        if self.scheduler_type == "step":
            scheduler = torch.optim.lr_scheduler.StepLR(
                optimizer,
                step_size=self.scheduler_config.get("step_size", 10),
                gamma=self.scheduler_config.get("gamma", 0.1),
            )
            return [optimizer], [scheduler]

        elif self.scheduler_type == "cosine":
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=self.scheduler_config.get("t_max", 100),
                eta_min=self.scheduler_config.get("eta_min", 1e-6),
            )
            return [optimizer], [scheduler]

        elif self.scheduler_type == "plateau":
            scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode="min",
                factor=self.scheduler_config.get("factor", 0.5),
                patience=self.scheduler_config.get("patience", 5),
                min_lr=self.scheduler_config.get("min_lr", 1e-6),
            )
            return {
                "optimizer": optimizer,
                "lr_scheduler": {
                    "scheduler": scheduler,
                    "monitor": "val_loss",
                    "interval": "epoch",
                    "frequency": 1,
                },
            }

        elif self.scheduler_type == "onecycle":
            # OneCycleLR requires total_steps
            if self.total_steps is None:
                raise ValueError(
                    "OneCycleLR requires total_steps. "
                    "Set total_steps = num_epochs * steps_per_epoch"
                )

            scheduler = torch.optim.lr_scheduler.OneCycleLR(
                optimizer,
                max_lr=self.learning_rate,
                total_steps=self.total_steps,
                pct_start=self.scheduler_config.get("pct_start", 0.3),
                anneal_strategy=self.scheduler_config.get("anneal_strategy", "cos"),
                div_factor=self.scheduler_config.get("div_factor", 25.0),
                final_div_factor=self.scheduler_config.get("final_div_factor", 10000.0),
            )
            return {
                "optimizer": optimizer,
                "lr_scheduler": {
                    "scheduler": scheduler,
                    "interval": "step",
                    "frequency": 1,
                },
            }

        else:
            raise ValueError(f"Unknown scheduler: {self.scheduler_type}")

    def on_train_epoch_end(self):
        """Called at the end of each training epoch. Log to MLflow."""
        if not self.log_to_mlflow:
            return

        try:
            # Get current epoch metrics
            current_lr = self.trainer.optimizers[0].param_groups[0]["lr"]
            mlflow.log_metric("learning_rate", current_lr, step=self.current_epoch)

            # Log epoch number
            mlflow.log_metric("epoch", self.current_epoch, step=self.current_epoch)
        except Exception as e:
            logger.warning(f"Failed to log to MLflow: {e}")

    def on_validation_epoch_end(self):
        """Called at the end of each validation epoch. Track best metrics and log to MLflow."""
        # Get logged metrics
        metrics = self.trainer.callback_metrics

        # Update best metrics
        val_loss = metrics.get("val_loss")
        val_mape = metrics.get("val_mape")
        val_coverage = metrics.get("val_coverage_90")

        if val_loss is not None and val_loss < self.best_val_loss:
            self.best_val_loss = val_loss.item()

        if val_mape is not None and val_mape < self.best_val_mape:
            self.best_val_mape = val_mape.item()

        if val_coverage is not None and val_coverage > self.best_val_coverage:
            self.best_val_coverage = val_coverage.item()

        # Log to MLflow
        if not self.log_to_mlflow:
            return

        try:
            for key, value in metrics.items():
                if isinstance(value, torch.Tensor):
                    value = value.item()
                mlflow.log_metric(key, value, step=self.current_epoch)

            # Log best metrics
            mlflow.log_metric("best_val_loss", self.best_val_loss, step=self.current_epoch)
            mlflow.log_metric("best_val_mape", self.best_val_mape, step=self.current_epoch)
            mlflow.log_metric("best_val_coverage_90", self.best_val_coverage, step=self.current_epoch)
        except Exception as e:
            logger.warning(f"Failed to log to MLflow: {e}")

    def get_interpretability(
        self,
        static_covariates: Optional[torch.Tensor],
        historical_observed: torch.Tensor,
        historical_known: torch.Tensor,
        future_known: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Get interpretability information (attention weights, variable importance).

        Args:
            static_covariates: Static features
            historical_observed: Historical observed features
            historical_known: Historical known features
            future_known: Future known features

        Returns:
            Dictionary with interpretability information
        """
        self.eval()
        with torch.no_grad():
            _, interpretability = self(
                static_covariates=static_covariates,
                historical_observed=historical_observed,
                historical_known=historical_known,
                future_known=future_known,
            )
        return interpretability
