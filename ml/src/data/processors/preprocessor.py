"""Data preprocessing pipeline."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """Preprocessor for time series data."""

    def __init__(
        self,
        missing_value_strategy: str = "interpolate",
        outlier_detection: bool = True,
        outlier_threshold: float = 3.0,
        normalization: str = "standard",
    ):
        """Initialize preprocessor.

        Args:
            missing_value_strategy: Strategy for handling missing values
            outlier_detection: Whether to detect and handle outliers
            outlier_threshold: Z-score threshold for outlier detection
            normalization: Normalization method (standard, minmax, robust)
        """
        self.missing_value_strategy = missing_value_strategy
        self.outlier_detection = outlier_detection
        self.outlier_threshold = outlier_threshold
        self.normalization = normalization

        # Initialize scalers
        self.scalers: Dict[str, Any] = {}
        if normalization == "standard":
            self.scaler_class = StandardScaler
        elif normalization == "minmax":
            self.scaler_class = MinMaxScaler
        elif normalization == "robust":
            self.scaler_class = RobustScaler
        else:
            raise ValueError(f"Unknown normalization method: {normalization}")

    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in DataFrame.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with missing values handled
        """
        df = df.copy()

        if self.missing_value_strategy == "interpolate":
            # Interpolate numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].interpolate(
                method="time", limit_direction="both"
            )

        elif self.missing_value_strategy == "forward_fill":
            df = df.fillna(method="ffill").fillna(method="bfill")

        elif self.missing_value_strategy == "drop":
            df = df.dropna()

        else:
            raise ValueError(
                f"Unknown missing value strategy: {self.missing_value_strategy}"
            )

        logger.info(f"Handled missing values using {self.missing_value_strategy}")
        return df

    def detect_outliers(
        self, df: pd.DataFrame, columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Detect and handle outliers using z-score method.

        Args:
            df: Input DataFrame
            columns: Columns to check for outliers (None = all numeric)

        Returns:
            DataFrame with outliers handled
        """
        if not self.outlier_detection:
            return df

        df = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        for col in columns:
            if col not in df.columns:
                continue

            # Calculate z-scores
            mean = df[col].mean()
            std = df[col].std()

            if std == 0:
                continue

            z_scores = np.abs((df[col] - mean) / std)

            # Identify outliers
            outliers = z_scores > self.outlier_threshold

            # Cap outliers at threshold
            if outliers.any():
                lower_bound = mean - self.outlier_threshold * std
                upper_bound = mean + self.outlier_threshold * std

                df.loc[outliers, col] = df.loc[outliers, col].clip(
                    lower_bound, upper_bound
                )

                logger.info(
                    f"Handled {outliers.sum()} outliers in column {col}"
                )

        return df

    def normalize(
        self, df: pd.DataFrame, columns: List[str], fit: bool = True
    ) -> pd.DataFrame:
        """Normalize specified columns.

        Args:
            df: Input DataFrame
            columns: Columns to normalize
            fit: Whether to fit the scaler (True for training, False for inference)

        Returns:
            DataFrame with normalized columns
        """
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                logger.warning(f"Column {col} not found in DataFrame")
                continue

            if fit:
                # Fit and transform
                scaler = self.scaler_class()
                df[col] = scaler.fit_transform(df[[col]])
                self.scalers[col] = scaler
            else:
                # Transform only
                if col not in self.scalers:
                    logger.warning(f"No scaler found for column {col}")
                    continue
                df[col] = self.scalers[col].transform(df[[col]])

        logger.info(f"Normalized {len(columns)} columns using {self.normalization}")
        return df

    def inverse_normalize(
        self, df: pd.DataFrame, columns: List[str]
    ) -> pd.DataFrame:
        """Inverse normalize specified columns.

        Args:
            df: Input DataFrame
            columns: Columns to inverse normalize

        Returns:
            DataFrame with denormalized columns
        """
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                continue

            if col in self.scalers:
                df[col] = self.scalers[col].inverse_transform(df[[col]])
            else:
                logger.warning(f"No scaler found for column {col}")

        return df

    def create_lag_features(
        self, df: pd.DataFrame, columns: List[str], lags: List[int]
    ) -> pd.DataFrame:
        """Create lag features.

        Args:
            df: Input DataFrame
            columns: Columns to create lags for
            lags: List of lag periods

        Returns:
            DataFrame with lag features
        """
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                continue

            for lag in lags:
                df[f"{col}_lag_{lag}"] = df[col].shift(lag)

        logger.info(
            f"Created lag features for {len(columns)} columns with lags {lags}"
        )
        return df

    def create_rolling_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        windows: List[int],
        statistics: List[str],
    ) -> pd.DataFrame:
        """Create rolling window features.

        Args:
            df: Input DataFrame
            columns: Columns to create rolling features for
            windows: List of window sizes
            statistics: List of statistics to compute (mean, std, min, max)

        Returns:
            DataFrame with rolling features
        """
        df = df.copy()

        for col in columns:
            if col not in df.columns:
                continue

            for window in windows:
                for stat in statistics:
                    feature_name = f"{col}_rolling_{window}_{stat}"

                    if stat == "mean":
                        df[feature_name] = df[col].rolling(window=window).mean()
                    elif stat == "std":
                        df[feature_name] = df[col].rolling(window=window).std()
                    elif stat == "min":
                        df[feature_name] = df[col].rolling(window=window).min()
                    elif stat == "max":
                        df[feature_name] = df[col].rolling(window=window).max()

        logger.info(
            f"Created rolling features for {len(columns)} columns "
            f"with windows {windows}"
        )
        return df

    def process(
        self,
        df: pd.DataFrame,
        fit: bool = True,
        normalize_columns: Optional[List[str]] = None,
        lag_config: Optional[Dict[str, Any]] = None,
        rolling_config: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Full preprocessing pipeline.

        Args:
            df: Input DataFrame
            fit: Whether to fit transformations
            normalize_columns: Columns to normalize
            lag_config: Configuration for lag features
            rolling_config: Configuration for rolling features

        Returns:
            Processed DataFrame
        """
        logger.info("Starting preprocessing pipeline")

        # Handle missing values
        df = self.handle_missing_values(df)

        # Detect outliers
        df = self.detect_outliers(df)

        # Create lag features
        if lag_config:
            df = self.create_lag_features(
                df,
                columns=lag_config.get("columns", []),
                lags=lag_config.get("lags", []),
            )

        # Create rolling features
        if rolling_config:
            df = self.create_rolling_features(
                df,
                columns=rolling_config.get("columns", []),
                windows=rolling_config.get("windows", []),
                statistics=rolling_config.get("statistics", []),
            )

        # Drop rows with NaN values created by lag/rolling features
        df = df.dropna()

        # Normalize
        if normalize_columns:
            df = self.normalize(df, columns=normalize_columns, fit=fit)

        logger.info(f"Preprocessing complete. Output shape: {df.shape}")
        return df
