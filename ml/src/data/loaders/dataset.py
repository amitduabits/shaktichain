"""PyTorch datasets for time series forecasting."""

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)


class TimeSeriesDataset(Dataset):
    """PyTorch dataset for time series forecasting."""

    def __init__(
        self,
        data: pd.DataFrame,
        sequence_length: int,
        prediction_horizon: int,
        feature_columns: list,
        target_columns: list,
        stride: int = 1,
    ):
        """Initialize time series dataset.

        Args:
            data: DataFrame with features and targets
            sequence_length: Length of input sequence
            prediction_horizon: Length of prediction
            feature_columns: List of feature column names
            target_columns: List of target column names
            stride: Stride for creating sequences
        """
        self.data = data
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.feature_columns = feature_columns
        self.target_columns = target_columns
        self.stride = stride

        # Extract features and targets as numpy arrays
        self.features = data[feature_columns].values.astype(np.float32)
        self.targets = data[target_columns].values.astype(np.float32)

        # Calculate valid indices
        self.indices = self._calculate_indices()

        logger.info(
            f"Created TimeSeriesDataset with {len(self)} samples, "
            f"seq_len={sequence_length}, horizon={prediction_horizon}"
        )

    def _calculate_indices(self) -> list:
        """Calculate valid starting indices for sequences.

        Returns:
            List of valid indices
        """
        max_idx = len(self.data) - self.sequence_length - self.prediction_horizon
        indices = list(range(0, max_idx + 1, self.stride))
        return indices

    def __len__(self) -> int:
        """Get dataset length.

        Returns:
            Number of samples
        """
        return len(self.indices)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get a sample from the dataset.

        Args:
            idx: Sample index

        Returns:
            Tuple of (features, targets) tensors
        """
        start_idx = self.indices[idx]
        end_idx = start_idx + self.sequence_length
        target_start = end_idx
        target_end = target_start + self.prediction_horizon

        # Extract sequence and target
        features = self.features[start_idx:end_idx]
        targets = self.targets[target_start:target_end]

        # Convert to tensors
        features_tensor = torch.from_numpy(features)
        targets_tensor = torch.from_numpy(targets)

        return features_tensor, targets_tensor


class SlidingWindowDataset(Dataset):
    """Dataset with sliding window for time series."""

    def __init__(
        self,
        data: np.ndarray,
        window_size: int,
        horizon: int,
        stride: int = 1,
    ):
        """Initialize sliding window dataset.

        Args:
            data: Input data array
            window_size: Size of sliding window
            horizon: Prediction horizon
            stride: Stride for sliding window
        """
        self.data = data
        self.window_size = window_size
        self.horizon = horizon
        self.stride = stride

        self.num_samples = (len(data) - window_size - horizon) // stride + 1

    def __len__(self) -> int:
        """Get dataset length.

        Returns:
            Number of samples
        """
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get a sample from the dataset.

        Args:
            idx: Sample index

        Returns:
            Tuple of (input, target) tensors
        """
        start = idx * self.stride
        end = start + self.window_size
        target_end = end + self.horizon

        x = torch.from_numpy(self.data[start:end]).float()
        y = torch.from_numpy(self.data[end:target_end]).float()

        return x, y


class MultiVariateTimeSeriesDataset(Dataset):
    """Dataset for multivariate time series with multiple targets."""

    def __init__(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        sequence_length: int,
        prediction_horizon: int,
        stride: int = 1,
    ):
        """Initialize multivariate dataset.

        Args:
            features: Feature array of shape (n_samples, n_features)
            targets: Target array of shape (n_samples, n_targets)
            sequence_length: Length of input sequence
            prediction_horizon: Length of prediction
            stride: Stride for creating sequences
        """
        self.features = features
        self.targets = targets
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.stride = stride

        # Calculate number of samples
        self.num_samples = (
            len(features) - sequence_length - prediction_horizon
        ) // stride + 1

    def __len__(self) -> int:
        """Get dataset length.

        Returns:
            Number of samples
        """
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get a sample from the dataset.

        Args:
            idx: Sample index

        Returns:
            Tuple of (features, targets) tensors
        """
        start = idx * self.stride
        end = start + self.sequence_length
        target_end = end + self.prediction_horizon

        x = torch.from_numpy(self.features[start:end]).float()
        y = torch.from_numpy(self.targets[end:target_end]).float()

        return x, y


class SequenceToSequenceDataset(Dataset):
    """Dataset for sequence-to-sequence models."""

    def __init__(
        self,
        encoder_data: np.ndarray,
        decoder_data: np.ndarray,
        encoder_length: int,
        decoder_length: int,
        stride: int = 1,
    ):
        """Initialize seq2seq dataset.

        Args:
            encoder_data: Encoder input data
            decoder_data: Decoder output data
            encoder_length: Length of encoder sequence
            decoder_length: Length of decoder sequence
            stride: Stride for creating sequences
        """
        self.encoder_data = encoder_data
        self.decoder_data = decoder_data
        self.encoder_length = encoder_length
        self.decoder_length = decoder_length
        self.stride = stride

        self.num_samples = (
            len(encoder_data) - encoder_length - decoder_length
        ) // stride + 1

    def __len__(self) -> int:
        """Get dataset length.

        Returns:
            Number of samples
        """
        return self.num_samples

    def __getitem__(
        self, idx: int
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get a sample from the dataset.

        Args:
            idx: Sample index

        Returns:
            Tuple of (encoder_input, decoder_input, decoder_target) tensors
        """
        start = idx * self.stride
        enc_end = start + self.encoder_length
        dec_end = enc_end + self.decoder_length

        encoder_input = torch.from_numpy(self.encoder_data[start:enc_end]).float()
        decoder_input = torch.from_numpy(
            self.decoder_data[enc_end:dec_end - 1]
        ).float()
        decoder_target = torch.from_numpy(
            self.decoder_data[enc_end + 1:dec_end]
        ).float()

        return encoder_input, decoder_input, decoder_target
