"""Advanced preprocessing pipeline with timezone and missing value handling."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import pytz
from scipy import interpolate

logger = logging.getLogger(__name__)


class AdvancedPreprocessor:
    """Advanced preprocessor for SHAKTI-CHAIN energy data."""

    def __init__(
        self,
        timezone: str = "Asia/Kolkata",
        interpolation_max_gap: int = 3,  # Max 3 hours for interpolation
        outlier_method: str = "sigma",  # sigma or iqr
        outlier_threshold: float = 3.0,
        capping_method: str = "clip",  # clip or winsorize
    ):
        """Initialize advanced preprocessor.

        Args:
            timezone: Target timezone (default: IST)
            interpolation_max_gap: Max hours to interpolate missing values
            outlier_method: Method for outlier detection
            outlier_threshold: Threshold for outlier detection
            capping_method: Method for capping outliers
        """
        self.timezone = timezone
        self.interpolation_max_gap = interpolation_max_gap
        self.outlier_method = outlier_method
        self.outlier_threshold = outlier_threshold
        self.capping_method = capping_method

    def normalize_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize all timestamps to IST.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with normalized timestamps
        """
        df = df.copy()

        if "timestamp" not in df.columns:
            logger.error("No timestamp column found")
            return df

        logger.info(f"Normalizing timestamps to {self.timezone}")

        # Convert to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Convert timezone
        tz = pytz.timezone(self.timezone)

        if df["timestamp"].dt.tz is None:
            # Assume UTC if no timezone
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

        # Convert to target timezone
        df["timestamp"] = df["timestamp"].dt.tz_convert(tz)

        logger.info(f"Timestamps normalized to {self.timezone}")
        return df

    def resample_to_hourly(
        self,
        df: pd.DataFrame,
        agg_method: str = "mean"
    ) -> pd.DataFrame:
        """Resample data to consistent hourly frequency.

        Args:
            df: Input DataFrame
            agg_method: Aggregation method (mean, median, sum)

        Returns:
            Resampled DataFrame
        """
        df = df.copy()

        if "timestamp" not in df.columns:
            logger.error("No timestamp column found")
            return df

        logger.info("Resampling to hourly frequency")

        # Set timestamp as index
        df = df.set_index("timestamp")

        # Resample
        if agg_method == "mean":
            df = df.resample("1H").mean()
        elif agg_method == "median":
            df = df.resample("1H").median()
        elif agg_method == "sum":
            df = df.resample("1H").sum()
        else:
            raise ValueError(f"Unknown aggregation method: {agg_method}")

        # Reset index
        df = df.reset_index()

        logger.info(f"Resampled to {len(df)} hourly records")
        return df

    def handle_missing_values_smart(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Handle missing values with smart interpolation.

        For gaps <= interpolation_max_gap hours: interpolate
        For gaps > interpolation_max_gap hours: flag and fill with method

        Args:
            df: Input DataFrame
            columns: Columns to process (None = all numeric)

        Returns:
            DataFrame with handled missing values
        """
        df = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        logger.info("Handling missing values with smart interpolation")

        # Ensure sorted by timestamp
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp")

        for column in columns:
            if column not in df.columns:
                continue

            # Find missing value gaps
            missing_mask = df[column].isnull()
            missing_count = missing_mask.sum()

            if missing_count == 0:
                continue

            logger.info(f"  {column}: {missing_count} missing values")

            # Create gap size column
            df["_gap_id"] = (missing_mask != missing_mask.shift()).cumsum()
            gap_sizes = df[missing_mask].groupby("_gap_id").size()

            # Interpolate small gaps
            small_gaps = gap_sizes[gap_sizes <= self.interpolation_max_gap].index

            for gap_id in small_gaps:
                gap_mask = (df["_gap_id"] == gap_id) & missing_mask

                # Time-based interpolation
                if "timestamp" in df.columns:
                    df.loc[gap_mask, column] = df[column].interpolate(
                        method="time",
                        limit=self.interpolation_max_gap
                    )[gap_mask]
                else:
                    df.loc[gap_mask, column] = df[column].interpolate(
                        method="linear",
                        limit=self.interpolation_max_gap
                    )[gap_mask]

            # Flag large gaps
            large_gaps = gap_sizes[gap_sizes > self.interpolation_max_gap].index

            if len(large_gaps) > 0:
                logger.warning(
                    f"  {column}: {len(large_gaps)} gaps larger than "
                    f"{self.interpolation_max_gap} hours"
                )

                # Create flag column
                flag_col = f"{column}_large_gap_filled"
                df[flag_col] = False

                for gap_id in large_gaps:
                    gap_mask = (df["_gap_id"] == gap_id) & missing_mask
                    df.loc[gap_mask, flag_col] = True

                    # Fill with forward fill then backward fill
                    df[column] = df[column].fillna(method="ffill", limit=24)
                    df[column] = df[column].fillna(method="bfill", limit=24)

            # Clean up
            df = df.drop(columns=["_gap_id"], errors="ignore")

        # Fill any remaining NaNs with median
        for column in columns:
            if df[column].isnull().any():
                median_val = df[column].median()
                df[column] = df[column].fillna(median_val)
                logger.warning(
                    f"  {column}: Filled remaining NaNs with median ({median_val})"
                )

        logger.info("Missing value handling complete")
        return df

    def detect_and_cap_outliers(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Detect and cap outliers.

        Args:
            df: Input DataFrame
            columns: Columns to process (None = all numeric)

        Returns:
            DataFrame with capped outliers
        """
        df = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        logger.info(f"Detecting and capping outliers using {self.outlier_method} method")

        for column in columns:
            if column not in df.columns:
                continue

            if self.outlier_method == "sigma":
                # Z-score method
                mean = df[column].mean()
                std = df[column].std()

                if std == 0:
                    continue

                z_scores = np.abs((df[column] - mean) / std)
                outliers = z_scores > self.outlier_threshold

                if outliers.any():
                    outlier_count = outliers.sum()
                    logger.info(f"  {column}: {outlier_count} outliers detected")

                    if self.capping_method == "clip":
                        # Clip to threshold
                        lower_bound = mean - self.outlier_threshold * std
                        upper_bound = mean + self.outlier_threshold * std

                        df[column] = df[column].clip(lower_bound, upper_bound)

                    elif self.capping_method == "winsorize":
                        # Replace with threshold values
                        df.loc[outliers, column] = np.where(
                            df.loc[outliers, column] > mean,
                            mean + self.outlier_threshold * std,
                            mean - self.outlier_threshold * std
                        )

            elif self.outlier_method == "iqr":
                # IQR method
                Q1 = df[column].quantile(0.25)
                Q3 = df[column].quantile(0.75)
                IQR = Q3 - Q1

                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outliers = (df[column] < lower_bound) | (df[column] > upper_bound)

                if outliers.any():
                    outlier_count = outliers.sum()
                    logger.info(f"  {column}: {outlier_count} outliers detected")

                    df[column] = df[column].clip(lower_bound, upper_bound)

        logger.info("Outlier capping complete")
        return df

    def add_data_quality_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add data quality flags.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with quality flags
        """
        df = df.copy()

        logger.info("Adding data quality flags")

        # Flag weekends
        if "timestamp" in df.columns:
            df["is_weekend"] = df["timestamp"].dt.dayofweek.isin([5, 6])

        # Flag night hours (low demand expected)
        if "timestamp" in df.columns:
            df["is_night"] = df["timestamp"].dt.hour.isin(range(0, 6))

        # Flag peak hours (high demand expected)
        if "timestamp" in df.columns:
            df["is_peak_hour"] = df["timestamp"].dt.hour.isin(
                list(range(9, 12)) + list(range(18, 23))
            )

        logger.info("Data quality flags added")
        return df

    def process(
        self,
        df: pd.DataFrame,
        normalize_tz: bool = True,
        resample: bool = True,
        handle_missing: bool = True,
        cap_outliers: bool = True,
        add_flags: bool = True,
    ) -> pd.DataFrame:
        """Run complete preprocessing pipeline.

        Args:
            df: Input DataFrame
            normalize_tz: Normalize timezone to IST
            resample: Resample to hourly frequency
            handle_missing: Handle missing values
            cap_outliers: Cap outliers
            add_flags: Add data quality flags

        Returns:
            Processed DataFrame
        """
        logger.info("Starting advanced preprocessing pipeline")
        logger.info(f"Input shape: {df.shape}")

        if normalize_tz:
            df = self.normalize_timezone(df)

        if resample:
            df = self.resample_to_hourly(df)

        if handle_missing:
            df = self.handle_missing_values_smart(df)

        if cap_outliers:
            df = self.detect_and_cap_outliers(df)

        if add_flags:
            df = self.add_data_quality_flags(df)

        logger.info(f"Output shape: {df.shape}")
        logger.info("Advanced preprocessing complete")

        return df
