"""V2G DataModule for SHAKTI-CHAIN TFT training."""

import pytorch_lightning as pl
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TimeSeriesDataset(Dataset):
    """Time series dataset with sliding window for TFT.

    Handles proper temporal splitting to avoid data leakage.

    Args:
        data: DataFrame with time series data
        target_columns: List of target column names
        known_future_features: Features known at prediction time (e.g., time, calendar)
        observed_features: Features only available historically (e.g., load, weather)
        static_features: Time-invariant features (optional)
        encoder_length: Number of historical time steps
        decoder_length: Number of future time steps to predict
        stride: Step size between consecutive samples
        min_encoder_length: Minimum encoder length (for variable length)
    """

    def __init__(
        self,
        data: pd.DataFrame,
        target_columns: List[str],
        known_future_features: List[str],
        observed_features: List[str],
        static_features: Optional[List[str]] = None,
        encoder_length: int = 168,
        decoder_length: int = 48,
        stride: int = 1,
        min_encoder_length: Optional[int] = None,
    ):
        self.data = data.copy()
        self.target_columns = target_columns
        self.known_future_features = known_future_features
        self.observed_features = observed_features
        self.static_features = static_features or []
        self.encoder_length = encoder_length
        self.decoder_length = decoder_length
        self.stride = stride
        self.min_encoder_length = min_encoder_length or encoder_length

        # Ensure data is sorted by time
        if "timestamp" in self.data.columns:
            self.data = self.data.sort_values("timestamp").reset_index(drop=True)

        # Calculate valid indices
        self.total_length = encoder_length + decoder_length
        self.num_samples = max(0, (len(self.data) - self.total_length) // stride + 1)

        # Validate features exist
        self._validate_features()

        logger.info(f"Created dataset with {self.num_samples} samples")
        logger.info(f"  Encoder length: {encoder_length}, Decoder length: {decoder_length}")
        logger.info(f"  Known features: {len(known_future_features)}, Observed features: {len(observed_features)}")

    def _validate_features(self):
        """Validate that all required features exist in data."""
        missing_features = []

        for col in self.target_columns:
            if col not in self.data.columns:
                missing_features.append(f"target: {col}")

        for col in self.known_future_features:
            if col not in self.data.columns:
                missing_features.append(f"known: {col}")

        for col in self.observed_features:
            if col not in self.data.columns:
                missing_features.append(f"observed: {col}")

        for col in self.static_features:
            if col not in self.data.columns:
                missing_features.append(f"static: {col}")

        if missing_features:
            raise ValueError(f"Missing features in data: {missing_features}")

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get a single sample.

        Returns:
            Dictionary with:
                - historical_observed: (encoder_length, num_observed)
                - historical_known: (encoder_length, num_known)
                - future_known: (decoder_length, num_known)
                - static_covariates: (num_static,) or None
                - target: (decoder_length, num_targets)
        """
        # Calculate start and end indices
        start_idx = idx * self.stride
        encoder_end = start_idx + self.encoder_length
        decoder_end = encoder_end + self.decoder_length

        # Extract data slices
        encoder_data = self.data.iloc[start_idx:encoder_end]
        decoder_data = self.data.iloc[encoder_end:decoder_end]

        # Historical observed features (only available in encoder period)
        historical_observed = torch.tensor(
            encoder_data[self.observed_features].values,
            dtype=torch.float32,
        )

        # Historical known features
        historical_known = torch.tensor(
            encoder_data[self.known_future_features].values,
            dtype=torch.float32,
        )

        # Future known features
        future_known = torch.tensor(
            decoder_data[self.known_future_features].values,
            dtype=torch.float32,
        )

        # Target values
        target = torch.tensor(
            decoder_data[self.target_columns].values,
            dtype=torch.float32,
        )

        # Static covariates (if any)
        if self.static_features:
            static_covariates = torch.tensor(
                encoder_data[self.static_features].iloc[0].values,
                dtype=torch.float32,
            )
        else:
            static_covariates = None

        return {
            "historical_observed": historical_observed,
            "historical_known": historical_known,
            "future_known": future_known,
            "static_covariates": static_covariates,
            "target": target,
        }


class V2GDataModule(pl.LightningDataModule):
    """PyTorch Lightning DataModule for V2G load forecasting.

    Handles data loading, preprocessing, and train/val/test splits with
    proper temporal ordering to avoid data leakage.

    Args:
        data_path: Path to processed data parquet file
        target_columns: List of target column names
        known_future_features: Features known at prediction time
        observed_features: Features only available historically
        static_features: Time-invariant features (optional)
        encoder_length: Number of historical time steps (default: 168 = 1 week)
        decoder_length: Number of future time steps to predict (default: 48 = 2 days)
        batch_size: Batch size for data loaders
        num_workers: Number of workers for data loading
        train_start: Start date for training data
        train_end: End date for training data
        val_start: Start date for validation data
        val_end: End date for validation data
        test_start: Start date for test data
        test_end: End date for test data
        stride_train: Stride for training samples (default: 1)
        stride_val: Stride for validation samples (default: 24)
        stride_test: Stride for test samples (default: 24)
    """

    def __init__(
        self,
        data_path: str,
        target_columns: List[str],
        known_future_features: List[str],
        observed_features: List[str],
        static_features: Optional[List[str]] = None,
        encoder_length: int = 168,
        decoder_length: int = 48,
        batch_size: int = 64,
        num_workers: int = 4,
        train_start: str = "2022-01-01",
        train_end: str = "2023-12-31",
        val_start: str = "2024-01-01",
        val_end: str = "2024-06-30",
        test_start: str = "2024-07-01",
        test_end: str = "2024-12-31",
        stride_train: int = 1,
        stride_val: int = 24,
        stride_test: int = 24,
    ):
        super().__init__()
        self.save_hyperparameters()

        self.data_path = Path(data_path)
        self.target_columns = target_columns
        self.known_future_features = known_future_features
        self.observed_features = observed_features
        self.static_features = static_features or []
        self.encoder_length = encoder_length
        self.decoder_length = decoder_length
        self.batch_size = batch_size
        self.num_workers = num_workers

        # Date ranges
        self.train_start = pd.Timestamp(train_start)
        self.train_end = pd.Timestamp(train_end)
        self.val_start = pd.Timestamp(val_start)
        self.val_end = pd.Timestamp(val_end)
        self.test_start = pd.Timestamp(test_start)
        self.test_end = pd.Timestamp(test_end)

        # Strides
        self.stride_train = stride_train
        self.stride_val = stride_val
        self.stride_test = stride_test

        # Datasets (will be created in setup)
        self.train_dataset = None
        self.val_dataset = None
        self.test_dataset = None

        # Feature statistics for normalization
        self.feature_means = None
        self.feature_stds = None

    def prepare_data(self):
        """Download or generate data. Called only on one GPU."""
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Data file not found: {self.data_path}. "
                "Please run data collection and preprocessing first."
            )

    def setup(self, stage: Optional[str] = None):
        """Set up datasets for training, validation, and testing.

        Args:
            stage: One of 'fit', 'validate', 'test', or 'predict'
        """
        # Load data
        logger.info(f"Loading data from {self.data_path}")
        data = pd.read_parquet(self.data_path)

        # Ensure timestamp column
        if "timestamp" not in data.columns:
            raise ValueError("Data must have a 'timestamp' column")

        data["timestamp"] = pd.to_datetime(data["timestamp"])
        data = data.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Loaded {len(data)} rows from {data['timestamp'].min()} to {data['timestamp'].max()}")

        # Split data by date
        train_mask = (data["timestamp"] >= self.train_start) & (data["timestamp"] <= self.train_end)
        val_mask = (data["timestamp"] >= self.val_start) & (data["timestamp"] <= self.val_end)
        test_mask = (data["timestamp"] >= self.test_start) & (data["timestamp"] <= self.test_end)

        train_data = data[train_mask].copy()
        val_data = data[val_mask].copy()
        test_data = data[test_mask].copy()

        logger.info(f"Train samples: {len(train_data)} ({self.train_start} to {self.train_end})")
        logger.info(f"Val samples: {len(val_data)} ({self.val_start} to {self.val_end})")
        logger.info(f"Test samples: {len(test_data)} ({self.test_start} to {self.test_end})")

        # Compute feature statistics from training data only (avoid data leakage)
        self._compute_statistics(train_data)

        # Normalize data
        train_data = self._normalize(train_data)
        val_data = self._normalize(val_data)
        test_data = self._normalize(test_data)

        # Create datasets
        if stage == "fit" or stage is None:
            self.train_dataset = TimeSeriesDataset(
                data=train_data,
                target_columns=self.target_columns,
                known_future_features=self.known_future_features,
                observed_features=self.observed_features,
                static_features=self.static_features,
                encoder_length=self.encoder_length,
                decoder_length=self.decoder_length,
                stride=self.stride_train,
            )

            self.val_dataset = TimeSeriesDataset(
                data=val_data,
                target_columns=self.target_columns,
                known_future_features=self.known_future_features,
                observed_features=self.observed_features,
                static_features=self.static_features,
                encoder_length=self.encoder_length,
                decoder_length=self.decoder_length,
                stride=self.stride_val,
            )

        if stage == "test" or stage is None:
            self.test_dataset = TimeSeriesDataset(
                data=test_data,
                target_columns=self.target_columns,
                known_future_features=self.known_future_features,
                observed_features=self.observed_features,
                static_features=self.static_features,
                encoder_length=self.encoder_length,
                decoder_length=self.decoder_length,
                stride=self.stride_test,
            )

    def _compute_statistics(self, train_data: pd.DataFrame):
        """Compute feature statistics from training data."""
        # Columns to normalize
        normalize_cols = (
            self.target_columns +
            self.observed_features +
            [f for f in self.known_future_features if not f.startswith("is_") and "_sin" not in f and "_cos" not in f]
        )

        # Only normalize numeric columns that exist
        numeric_cols = train_data.select_dtypes(include=[np.number]).columns
        normalize_cols = [c for c in normalize_cols if c in numeric_cols]

        self.feature_means = train_data[normalize_cols].mean()
        self.feature_stds = train_data[normalize_cols].std().replace(0, 1)  # Avoid division by zero

        logger.info(f"Computed statistics for {len(normalize_cols)} features")

    def _normalize(self, data: pd.DataFrame) -> pd.DataFrame:
        """Normalize features using training statistics."""
        if self.feature_means is None or self.feature_stds is None:
            return data

        data = data.copy()
        for col in self.feature_means.index:
            if col in data.columns:
                data[col] = (data[col] - self.feature_means[col]) / self.feature_stds[col]

        return data

    def denormalize_target(self, predictions: torch.Tensor) -> torch.Tensor:
        """Denormalize target predictions to original scale.

        Args:
            predictions: Normalized predictions

        Returns:
            Denormalized predictions
        """
        if self.feature_means is None:
            return predictions

        device = predictions.device
        for i, col in enumerate(self.target_columns):
            if col in self.feature_means.index:
                mean = torch.tensor(self.feature_means[col], device=device)
                std = torch.tensor(self.feature_stds[col], device=device)
                predictions[..., i] = predictions[..., i] * std + mean

        return predictions

    def train_dataloader(self) -> DataLoader:
        """Create training data loader."""
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=self.num_workers,
            pin_memory=True,
            drop_last=True,
            persistent_workers=self.num_workers > 0,
        )

    def val_dataloader(self) -> DataLoader:
        """Create validation data loader."""
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=True,
            persistent_workers=self.num_workers > 0,
        )

    def test_dataloader(self) -> DataLoader:
        """Create test data loader."""
        return DataLoader(
            self.test_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=True,
            persistent_workers=self.num_workers > 0,
        )

    def predict_dataloader(self) -> DataLoader:
        """Create prediction data loader (same as test)."""
        return self.test_dataloader()

    def get_feature_info(self) -> Dict[str, Any]:
        """Get feature information for model configuration.

        Returns:
            Dictionary with feature dimensions and names
        """
        return {
            "known_input_size": len(self.known_future_features),
            "observed_input_size": len(self.observed_features),
            "static_input_size": len(self.static_features),
            "output_size": len(self.target_columns),
            "known_future_features": self.known_future_features,
            "observed_features": self.observed_features,
            "static_features": self.static_features,
            "target_columns": self.target_columns,
            "encoder_length": self.encoder_length,
            "decoder_length": self.decoder_length,
        }
