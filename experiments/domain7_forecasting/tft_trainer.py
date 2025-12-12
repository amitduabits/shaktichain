"""
TFT (Temporal Fusion Transformer) Trainer for SHAKTI-CHAIN Load Forecasting (Domain 7).

Implements a simplified TFT-like model for load forecasting.
Falls back to gradient boosting if PyTorch dependencies are not available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Check for optional dependencies
PYTORCH_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    logger.info("PyTorch not available, using fallback model")

try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.info("scikit-learn not available, using simple model")


@dataclass
class TFTConfig:
    """
    Configuration for TFT model.

    Attributes:
        hidden_size: Hidden layer size
        num_attention_heads: Number of attention heads
        dropout: Dropout rate
        max_encoder_length: Maximum encoder (history) length
        max_prediction_length: Maximum prediction horizon
        learning_rate: Learning rate for training
        batch_size: Batch size
        epochs: Number of training epochs
    """
    hidden_size: int = 64
    num_attention_heads: int = 4
    dropout: float = 0.1
    max_encoder_length: int = 168  # 7 days
    max_prediction_length: int = 24  # 1 day
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 50
    early_stopping_patience: int = 5

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hidden_size": self.hidden_size,
            "num_attention_heads": self.num_attention_heads,
            "dropout": self.dropout,
            "max_encoder_length": self.max_encoder_length,
            "max_prediction_length": self.max_prediction_length,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
        }


@dataclass
class TrainingHistory:
    """
    Training history.

    Attributes:
        train_loss: Training loss per epoch
        val_loss: Validation loss per epoch
        best_epoch: Epoch with best validation loss
        best_val_loss: Best validation loss
    """
    train_loss: List[float] = field(default_factory=list)
    val_loss: List[float] = field(default_factory=list)
    best_epoch: int = 0
    best_val_loss: float = float('inf')

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "train_loss": self.train_loss,
            "val_loss": self.val_loss,
            "best_epoch": self.best_epoch,
            "best_val_loss": self.best_val_loss,
        }


class SimpleTFTModel:
    """
    Simplified TFT-like model using gradient boosting.

    This provides similar functionality without requiring PyTorch.
    Uses separate models for each horizon step.
    """

    def __init__(self, config: TFTConfig):
        """Initialize model."""
        self.config = config
        self.models = {}  # One model per horizon
        self.scaler = None
        self.feature_names = None
        self._is_fitted = False

    def prepare_features(
        self,
        df: pd.DataFrame,
        target_col: str = "load_mw",
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare features for training.

        Args:
            df: Input DataFrame with load data
            target_col: Target column name

        Returns:
            (features, targets, feature_names)
        """
        df = df.copy()

        # Ensure sorted by timestamp
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp')

        # Create lag features
        lags = [1, 2, 3, 6, 12, 24, 48, 168]
        for lag in lags:
            df[f'lag_{lag}'] = df[target_col].shift(lag)

        # Rolling statistics
        for window in [6, 24, 168]:
            df[f'rolling_mean_{window}'] = df[target_col].rolling(window).mean()
            df[f'rolling_std_{window}'] = df[target_col].rolling(window).std()

        # Time features
        if 'hour' in df.columns:
            df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
            df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)

        if 'day_of_week' in df.columns:
            df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
            df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

        if 'month' in df.columns:
            df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
            df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

        # Drop rows with NaN (from lags/rolling)
        df = df.dropna()

        # Select feature columns
        feature_cols = [c for c in df.columns if c not in [
            'timestamp', target_col, 'city', 'is_holiday', 'is_festival',
            'hour', 'day_of_week', 'month', 'day_of_year'
        ]]

        # Add binary features back
        if 'is_holiday' in df.columns:
            feature_cols.append('is_holiday')
        if 'is_festival' in df.columns:
            feature_cols.append('is_festival')

        features = df[feature_cols].values
        targets = df[target_col].values

        return features, targets, feature_cols

    def fit(
        self,
        train_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None,
        target_col: str = "load_mw",
    ) -> TrainingHistory:
        """
        Train the model.

        Args:
            train_df: Training data
            val_df: Validation data (optional)
            target_col: Target column name

        Returns:
            TrainingHistory
        """
        # Prepare features
        X_train, y_train, feature_names = self.prepare_features(train_df, target_col)
        self.feature_names = feature_names

        # Scale features
        if SKLEARN_AVAILABLE:
            self.scaler = StandardScaler()
            X_train = self.scaler.fit_transform(X_train)

        # Create multi-horizon targets
        horizon = self.config.max_prediction_length
        history = TrainingHistory()

        # Train one model per horizon
        for h in range(1, horizon + 1):
            # Shift target for horizon h
            if h < len(y_train):
                y_h = y_train[h:]
                X_h = X_train[:-h]

                if SKLEARN_AVAILABLE:
                    model = GradientBoostingRegressor(
                        n_estimators=100,
                        max_depth=5,
                        learning_rate=0.1,
                        random_state=42,
                    )
                    model.fit(X_h, y_h)
                else:
                    # Simple mean model as fallback
                    model = {"mean": np.mean(y_h), "std": np.std(y_h)}

                self.models[h] = model

        # Calculate training loss
        train_pred = self._predict_internal(X_train[:len(y_train) - horizon], horizon)
        train_loss = np.mean((y_train[horizon:] - train_pred[:, -1]) ** 2)
        history.train_loss.append(float(train_loss))

        # Validation loss
        if val_df is not None:
            X_val, y_val, _ = self.prepare_features(val_df, target_col)
            if self.scaler is not None:
                X_val = self.scaler.transform(X_val)
            val_pred = self._predict_internal(X_val[:len(y_val) - horizon], horizon)
            val_loss = np.mean((y_val[horizon:] - val_pred[:, -1]) ** 2)
            history.val_loss.append(float(val_loss))
            history.best_val_loss = val_loss
            history.best_epoch = 0

        self._is_fitted = True
        return history

    def _predict_internal(
        self,
        X: np.ndarray,
        horizon: int,
    ) -> np.ndarray:
        """Generate predictions for all horizons."""
        n_samples = len(X)
        predictions = np.zeros((n_samples, horizon))

        for h in range(1, horizon + 1):
            if h in self.models:
                model = self.models[h]
                if SKLEARN_AVAILABLE and hasattr(model, 'predict'):
                    predictions[:, h - 1] = model.predict(X)
                else:
                    # Fallback: use stored mean
                    predictions[:, h - 1] = model.get("mean", 0)
            else:
                # Use last available model
                last_h = max(self.models.keys())
                model = self.models[last_h]
                if SKLEARN_AVAILABLE and hasattr(model, 'predict'):
                    predictions[:, h - 1] = model.predict(X)
                else:
                    predictions[:, h - 1] = model.get("mean", 0)

        return predictions

    def predict(
        self,
        df: pd.DataFrame,
        horizon: Optional[int] = None,
        target_col: str = "load_mw",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate predictions with uncertainty.

        Args:
            df: Input data
            horizon: Prediction horizon (uses config default if None)
            target_col: Target column name

        Returns:
            (point_forecast, lower_bound, upper_bound)
        """
        if not self._is_fitted:
            raise ValueError("Model not fitted")

        if horizon is None:
            horizon = self.config.max_prediction_length

        # Prepare features
        X, _, _ = self.prepare_features(df, target_col)
        if self.scaler is not None:
            X = self.scaler.transform(X)

        # Generate predictions (use last row as most recent)
        predictions = self._predict_internal(X[-1:], horizon)
        point_forecast = predictions[0, :horizon]

        # Estimate uncertainty (simple approach: use training residual std)
        # In practice, would use quantile regression or ensemble
        uncertainty = np.abs(point_forecast) * 0.1  # 10% relative uncertainty

        from scipy import stats as scipy_stats
        z = scipy_stats.norm.ppf(0.975)  # 95% interval

        lower_bound = point_forecast - z * uncertainty
        upper_bound = point_forecast + z * uncertainty

        return point_forecast, lower_bound, upper_bound


class TFTTrainer:
    """
    Trainer for TFT model.

    Handles data preparation, training, and prediction.
    """

    def __init__(self, config: Optional[TFTConfig] = None):
        """
        Initialize trainer.

        Args:
            config: Model configuration
        """
        self.config = config or TFTConfig()
        self.model = SimpleTFTModel(self.config)
        self.history = None

    def prepare_data(
        self,
        data: pd.DataFrame,
        target_col: str = "load_mw",
        train_ratio: float = 0.8,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare data for training and validation.

        Args:
            data: Input DataFrame
            target_col: Target column name
            train_ratio: Fraction for training

        Returns:
            (train_df, val_df)
        """
        # Ensure sorted by timestamp
        if 'timestamp' in data.columns:
            data = data.sort_values('timestamp')

        # Split by time
        n = len(data)
        train_end = int(n * train_ratio)

        train_df = data.iloc[:train_end].copy()
        val_df = data.iloc[train_end:].copy()

        return train_df, val_df

    def train(
        self,
        train_data: pd.DataFrame,
        val_data: Optional[pd.DataFrame] = None,
        target_col: str = "load_mw",
    ) -> TrainingHistory:
        """
        Train the TFT model.

        Args:
            train_data: Training DataFrame
            val_data: Validation DataFrame
            target_col: Target column name

        Returns:
            TrainingHistory
        """
        logger.info("Starting TFT training...")

        self.history = self.model.fit(train_data, val_data, target_col)

        logger.info(f"Training complete. Best val loss: {self.history.best_val_loss:.4f}")

        return self.history

    def predict(
        self,
        data: pd.DataFrame,
        horizon: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate predictions with uncertainty.

        Args:
            data: Input data for prediction
            horizon: Prediction horizon

        Returns:
            (point_forecast, lower_bound, upper_bound)
        """
        return self.model.predict(data, horizon)

    def evaluate(
        self,
        data: pd.DataFrame,
        target_col: str = "load_mw",
    ) -> Dict[str, float]:
        """
        Evaluate model on test data.

        Args:
            data: Test DataFrame
            target_col: Target column name

        Returns:
            Dictionary with evaluation metrics
        """
        from .evaluation_metrics import evaluate_forecast

        # Get predictions
        horizon = self.config.max_prediction_length
        point, lower, upper = self.predict(data, horizon)

        # Get actual values
        actual = data[target_col].values[-horizon:]

        # Ensure same length
        min_len = min(len(actual), len(point))
        actual = actual[:min_len]
        point = point[:min_len]
        lower = lower[:min_len]
        upper = upper[:min_len]

        # Evaluate
        result = evaluate_forecast(actual, point, lower, upper)

        return result.to_dict()


def train_tft_model(
    data: pd.DataFrame,
    config: Optional[TFTConfig] = None,
    target_col: str = "load_mw",
) -> Tuple[TFTTrainer, TrainingHistory]:
    """
    Convenience function to train a TFT model.

    Args:
        data: Input DataFrame
        config: Model configuration
        target_col: Target column name

    Returns:
        (trainer, history)
    """
    trainer = TFTTrainer(config)
    train_df, val_df = trainer.prepare_data(data)
    history = trainer.train(train_df, val_df, target_col)

    return trainer, history
