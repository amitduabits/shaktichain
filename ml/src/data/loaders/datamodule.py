"""PyTorch Lightning DataModule for time series."""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import pytorch_lightning as pl
from torch.utils.data import DataLoader

from .dataset import TimeSeriesDataset

logger = logging.getLogger(__name__)


class TimeSeriesDataModule(pl.LightningDataModule):
    """Lightning DataModule for time series forecasting."""

    def __init__(
        self,
        data_path: str,
        sequence_length: int,
        prediction_horizon: int,
        feature_columns: list,
        target_columns: list,
        batch_size: int = 64,
        num_workers: int = 4,
        train_split: float = 0.7,
        val_split: float = 0.15,
        test_split: float = 0.15,
        stride: int = 1,
        pin_memory: bool = True,
    ):
        """Initialize DataModule.

        Args:
            data_path: Path to processed data file
            sequence_length: Length of input sequence
            prediction_horizon: Length of prediction
            feature_columns: List of feature column names
            target_columns: List of target column names
            batch_size: Batch size
            num_workers: Number of workers for data loading
            train_split: Training data split ratio
            val_split: Validation data split ratio
            test_split: Test data split ratio
            stride: Stride for creating sequences
            pin_memory: Whether to pin memory
        """
        super().__init__()
        self.data_path = Path(data_path)
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.feature_columns = feature_columns
        self.target_columns = target_columns
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.train_split = train_split
        self.val_split = val_split
        self.test_split = test_split
        self.stride = stride
        self.pin_memory = pin_memory

        # Will be set in setup()
        self.train_dataset: Optional[TimeSeriesDataset] = None
        self.val_dataset: Optional[TimeSeriesDataset] = None
        self.test_dataset: Optional[TimeSeriesDataset] = None

    def setup(self, stage: Optional[str] = None) -> None:
        """Set up datasets.

        Args:
            stage: Current stage (fit, validate, test, predict)
        """
        # Load data
        logger.info(f"Loading data from {self.data_path}")
        data = pd.read_parquet(self.data_path)

        # Split data temporally
        n_samples = len(data)
        train_end = int(n_samples * self.train_split)
        val_end = int(n_samples * (self.train_split + self.val_split))

        train_data = data[:train_end]
        val_data = data[train_end:val_end]
        test_data = data[val_end:]

        logger.info(
            f"Data split - Train: {len(train_data)}, "
            f"Val: {len(val_data)}, Test: {len(test_data)}"
        )

        # Create datasets
        if stage == "fit" or stage is None:
            self.train_dataset = TimeSeriesDataset(
                train_data,
                self.sequence_length,
                self.prediction_horizon,
                self.feature_columns,
                self.target_columns,
                stride=self.stride,
            )

            self.val_dataset = TimeSeriesDataset(
                val_data,
                self.sequence_length,
                self.prediction_horizon,
                self.feature_columns,
                self.target_columns,
                stride=self.stride,
            )

        if stage == "test" or stage is None:
            self.test_dataset = TimeSeriesDataset(
                test_data,
                self.sequence_length,
                self.prediction_horizon,
                self.feature_columns,
                self.target_columns,
                stride=self.stride,
            )

    def train_dataloader(self) -> DataLoader:
        """Get training dataloader.

        Returns:
            Training DataLoader
        """
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            drop_last=False,
        )

    def val_dataloader(self) -> DataLoader:
        """Get validation dataloader.

        Returns:
            Validation DataLoader
        """
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            drop_last=False,
        )

    def test_dataloader(self) -> DataLoader:
        """Get test dataloader.

        Returns:
            Test DataLoader
        """
        return DataLoader(
            self.test_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            drop_last=False,
        )

    def predict_dataloader(self) -> DataLoader:
        """Get prediction dataloader.

        Returns:
            Prediction DataLoader
        """
        return self.test_dataloader()
