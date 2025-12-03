"""Price prediction data module for SHAKTI-CHAIN."""

import pytorch_lightning as pl
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import logging

from ..features.price_features import PriceFeatureEngineering, PriceFeatureConfig

logger = logging.getLogger(__name__)


class PriceDataset(Dataset):
    """Dataset for price prediction with load forecast integration.

    Args:
        data: DataFrame with price and feature data
        feature_cols: List of feature column names
        target_col: Target price column name
        load_forecast_cols: Load forecast column names (optional)
        encoder_length: Historical context length
        decoder_length: Forecast horizon
        stride: Step size between samples
    """

    def __init__(
        self,
        data: pd.DataFrame,
        feature_cols: List[str],
        target_col: str = "price_inr_mwh",
        load_forecast_cols: Optional[List[str]] = None,
        encoder_length: int = 168,
        decoder_length: int = 48,
        stride: int = 1,
    ):
        self.data = data.copy()
        self.feature_cols = feature_cols
        self.target_col = target_col
        self.load_forecast_cols = load_forecast_cols or []
        self.encoder_length = encoder_length
        self.decoder_length = decoder_length
        self.stride = stride

        # Ensure data is sorted by time
        if "timestamp" in self.data.columns:
            self.data = self.data.sort_values("timestamp").reset_index(drop=True)

        # Validate columns
        self._validate_columns()

        # Calculate number of samples
        self.total_length = encoder_length + decoder_length
        self.num_samples = max(0, (len(self.data) - self.total_length) // stride + 1)

        logger.info(f"Created price dataset with {self.num_samples} samples")

    def _validate_columns(self):
        """Validate that required columns exist."""
        missing = []
        for col in self.feature_cols:
            if col not in self.data.columns:
                missing.append(f"feature: {col}")
        if self.target_col not in self.data.columns:
            missing.append(f"target: {self.target_col}")
        for col in self.load_forecast_cols:
            if col not in self.data.columns:
                missing.append(f"load_forecast: {col}")
        if missing:
            raise ValueError(f"Missing columns: {missing}")

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """Get a single sample.

        Returns:
            Dictionary with:
                - features: (encoder_length, num_features)
                - load_forecast: (decoder_length, num_load_features) if available
                - target: (decoder_length,)
                - spike_labels: (decoder_length,) if 'is_spike' in data
        """
        start_idx = idx * self.stride
        encoder_end = start_idx + self.encoder_length
        decoder_end = encoder_end + self.decoder_length

        encoder_data = self.data.iloc[start_idx:encoder_end]
        decoder_data = self.data.iloc[encoder_end:decoder_end]

        # Historical features
        features = torch.tensor(
            encoder_data[self.feature_cols].values,
            dtype=torch.float32,
        )

        # Target prices
        target = torch.tensor(
            decoder_data[self.target_col].values,
            dtype=torch.float32,
        )

        result = {
            "features": features,
            "target": target,
        }

        # Load forecast if available
        if self.load_forecast_cols:
            load_forecast = torch.tensor(
                decoder_data[self.load_forecast_cols].values,
                dtype=torch.float32,
            )
            result["load_forecast"] = load_forecast

        # Spike labels if available
        if "is_spike" in self.data.columns:
            spike_labels = torch.tensor(
                decoder_data["is_spike"].values,
                dtype=torch.float32,
            )
            result["spike_labels"] = spike_labels

        # Regime labels if available
        if "regime_high" in self.data.columns:
            # Create regime labels: 0=low, 1=normal, 2=high
            regime_low = decoder_data["regime_low"].values if "regime_low" in self.data.columns else np.zeros(len(decoder_data))
            regime_high = decoder_data["regime_high"].values
            regime_labels = np.where(regime_low, 0, np.where(regime_high, 2, 1))
            result["regime_labels"] = torch.tensor(regime_labels, dtype=torch.long)

        return result


class PriceDataModule(pl.LightningDataModule):
    """Lightning DataModule for price prediction.

    Handles IEX price data loading, feature engineering, and data splitting
    with proper temporal ordering.

    Args:
        data_path: Path to price data parquet file
        target_col: Target price column name
        load_col: Load column name
        encoder_length: Historical context length
        decoder_length: Forecast horizon
        batch_size: Batch size
        num_workers: Number of data loading workers
        train_start: Training start date
        train_end: Training end date
        val_start: Validation start date
        val_end: Validation end date
        test_start: Test start date
        test_end: Test end date
        feature_config: PriceFeatureConfig or None
        load_forecast_cols: Load forecast columns from TFT model
    """

    def __init__(
        self,
        data_path: str,
        target_col: str = "price_inr_mwh",
        load_col: str = "load_mw",
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
        feature_config: Optional[PriceFeatureConfig] = None,
        load_forecast_cols: Optional[List[str]] = None,
        stride_train: int = 1,
        stride_val: int = 24,
        stride_test: int = 24,
    ):
        super().__init__()
        self.save_hyperparameters()

        self.data_path = Path(data_path)
        self.target_col = target_col
        self.load_col = load_col
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

        # Feature engineering
        self.feature_config = feature_config or PriceFeatureConfig()
        self.feature_engineer = PriceFeatureEngineering(
            config=self.feature_config,
            target_col=target_col,
            load_col=load_col,
        )

        # Load forecast columns
        self.load_forecast_cols = load_forecast_cols or []

        # Strides
        self.stride_train = stride_train
        self.stride_val = stride_val
        self.stride_test = stride_test

        # Datasets
        self.train_dataset = None
        self.val_dataset = None
        self.test_dataset = None
        self.feature_cols = None

    def prepare_data(self):
        """Check data exists."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

    def setup(self, stage: Optional[str] = None):
        """Setup datasets."""
        logger.info(f"Loading data from {self.data_path}")
        data = pd.read_parquet(self.data_path)

        # Ensure timestamp
        if "timestamp" not in data.columns:
            raise ValueError("Data must have 'timestamp' column")

        data["timestamp"] = pd.to_datetime(data["timestamp"])
        data = data.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Loaded {len(data):,} rows")

        # Split by date
        train_mask = (data["timestamp"] >= self.train_start) & (data["timestamp"] <= self.train_end)
        val_mask = (data["timestamp"] >= self.val_start) & (data["timestamp"] <= self.val_end)
        test_mask = (data["timestamp"] >= self.test_start) & (data["timestamp"] <= self.test_end)

        train_data = data[train_mask].copy()
        val_data = data[val_mask].copy()
        test_data = data[test_mask].copy()

        logger.info(f"Train: {len(train_data):,}, Val: {len(val_data):,}, Test: {len(test_data):,}")

        # Fit feature engineering on training data
        self.feature_engineer.fit(train_data)

        # Transform all data
        train_features = self.feature_engineer.transform(train_data, normalize=True)
        val_features = self.feature_engineer.transform(val_data, normalize=True)
        test_features = self.feature_engineer.transform(test_data, normalize=True)

        # Get feature columns
        self.feature_cols = self.feature_engineer.get_feature_names()
        logger.info(f"Using {len(self.feature_cols)} features")

        # Create datasets
        if stage == "fit" or stage is None:
            self.train_dataset = PriceDataset(
                data=train_features,
                feature_cols=self.feature_cols,
                target_col=self.target_col,
                load_forecast_cols=self.load_forecast_cols,
                encoder_length=self.encoder_length,
                decoder_length=self.decoder_length,
                stride=self.stride_train,
            )

            self.val_dataset = PriceDataset(
                data=val_features,
                feature_cols=self.feature_cols,
                target_col=self.target_col,
                load_forecast_cols=self.load_forecast_cols,
                encoder_length=self.encoder_length,
                decoder_length=self.decoder_length,
                stride=self.stride_val,
            )

        if stage == "test" or stage is None:
            self.test_dataset = PriceDataset(
                data=test_features,
                feature_cols=self.feature_cols,
                target_col=self.target_col,
                load_forecast_cols=self.load_forecast_cols,
                encoder_length=self.encoder_length,
                decoder_length=self.decoder_length,
                stride=self.stride_test,
            )

    def train_dataloader(self) -> DataLoader:
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
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=True,
            persistent_workers=self.num_workers > 0,
        )

    def test_dataloader(self) -> DataLoader:
        return DataLoader(
            self.test_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=True,
            persistent_workers=self.num_workers > 0,
        )

    def get_feature_info(self) -> Dict[str, Any]:
        """Get feature information for model configuration."""
        return {
            "input_size": len(self.feature_cols),
            "load_forecast_size": len(self.load_forecast_cols),
            "feature_cols": self.feature_cols,
            "encoder_length": self.encoder_length,
            "decoder_length": self.decoder_length,
        }
