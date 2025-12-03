"""Feature engineering for time series forecasting."""

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature engineering for energy load forecasting."""

    @staticmethod
    def create_temporal_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
        """Create temporal features from timestamp.

        Args:
            df: Input DataFrame
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with temporal features
        """
        df = df.copy()

        if timestamp_col not in df.columns:
            logger.error(f"Timestamp column {timestamp_col} not found")
            return df

        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])

        ts = df[timestamp_col]

        # Time components
        df["hour"] = ts.dt.hour
        df["day_of_week"] = ts.dt.dayofweek
        df["day_of_month"] = ts.dt.day
        df["day_of_year"] = ts.dt.dayofyear
        df["week_of_year"] = ts.dt.isocalendar().week
        df["month"] = ts.dt.month
        df["quarter"] = ts.dt.quarter
        df["year"] = ts.dt.year

        # Binary features
        df["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)
        df["is_month_start"] = ts.dt.is_month_start.astype(int)
        df["is_month_end"] = ts.dt.is_month_end.astype(int)
        df["is_quarter_start"] = ts.dt.is_quarter_start.astype(int)
        df["is_quarter_end"] = ts.dt.is_quarter_end.astype(int)

        # Time of day categories
        df["time_of_day"] = pd.cut(
            ts.dt.hour,
            bins=[0, 6, 12, 18, 24],
            labels=["night", "morning", "afternoon", "evening"],
            include_lowest=True,
        )

        logger.info("Created temporal features")
        return df

    @staticmethod
    def create_cyclical_features(
        df: pd.DataFrame, columns: List[str], periods: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """Create cyclical (sin/cos) encoding of temporal features.

        Args:
            df: Input DataFrame
            columns: Columns to encode cyclically
            periods: Period for each column (e.g., 24 for hour, 7 for day_of_week)

        Returns:
            DataFrame with cyclical features
        """
        df = df.copy()

        # Default periods
        default_periods = {
            "hour": 24,
            "day_of_week": 7,
            "day_of_month": 31,
            "day_of_year": 365,
            "week_of_year": 52,
            "month": 12,
        }

        for i, col in enumerate(columns):
            if col not in df.columns:
                logger.warning(f"Column {col} not found")
                continue

            period = periods[i] if periods and i < len(periods) else default_periods.get(col, 24)

            df[f"{col}_sin"] = np.sin(2 * np.pi * df[col] / period)
            df[f"{col}_cos"] = np.cos(2 * np.pi * df[col] / period)

        logger.info(f"Created cyclical features for {len(columns)} columns")
        return df

    @staticmethod
    def create_interaction_features(
        df: pd.DataFrame, feature_pairs: List[tuple]
    ) -> pd.DataFrame:
        """Create interaction features between feature pairs.

        Args:
            df: Input DataFrame
            feature_pairs: List of tuples with feature pairs to interact

        Returns:
            DataFrame with interaction features
        """
        df = df.copy()

        for feat1, feat2 in feature_pairs:
            if feat1 not in df.columns or feat2 not in df.columns:
                logger.warning(f"Feature pair ({feat1}, {feat2}) not found")
                continue

            # Multiplication interaction
            df[f"{feat1}_x_{feat2}"] = df[feat1] * df[feat2]

            # Ratio interaction (with safety check)
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = df[feat1] / df[feat2]
                ratio = np.where(np.isfinite(ratio), ratio, 0)
                df[f"{feat1}_div_{feat2}"] = ratio

        logger.info(f"Created interaction features for {len(feature_pairs)} pairs")
        return df

    @staticmethod
    def create_demand_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create energy demand specific features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with demand features
        """
        df = df.copy()

        # Peak hours (typically 9 AM - 9 PM)
        if "hour" in df.columns:
            df["is_peak_hour"] = df["hour"].between(9, 21).astype(int)

        # Working hours (9 AM - 6 PM on weekdays)
        if "hour" in df.columns and "is_weekend" in df.columns:
            df["is_working_hour"] = (
                (df["hour"].between(9, 18)) & (df["is_weekend"] == 0)
            ).astype(int)

        # Summer months (high AC usage)
        if "month" in df.columns:
            df["is_summer"] = df["month"].isin([3, 4, 5, 6]).astype(int)

        # Winter months (high heating usage)
        if "month" in df.columns:
            df["is_winter"] = df["month"].isin([11, 12, 1, 2]).astype(int)

        # Monsoon months (India)
        if "month" in df.columns:
            df["is_monsoon"] = df["month"].isin([6, 7, 8, 9]).astype(int)

        logger.info("Created demand-specific features")
        return df

    @staticmethod
    def create_weather_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create weather-derived features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with weather features
        """
        df = df.copy()

        # Temperature categories
        if "temperature_c" in df.columns:
            df["temp_category"] = pd.cut(
                df["temperature_c"],
                bins=[-np.inf, 10, 20, 30, np.inf],
                labels=["cold", "moderate", "warm", "hot"],
            )

            # Temperature comfort index (simplified)
            if "humidity_pct" in df.columns:
                # Heat index approximation
                T = df["temperature_c"]
                RH = df["humidity_pct"]
                df["heat_index"] = T + 0.5555 * (6.11 * np.exp(5417.7530 * (1/273.16 - 1/(273.15+T))) * (RH/100) - 10)

        # Humidity categories
        if "humidity_pct" in df.columns:
            df["humidity_category"] = pd.cut(
                df["humidity_pct"],
                bins=[0, 30, 60, 100],
                labels=["dry", "moderate", "humid"],
            )

        # Wind categories
        if "wind_speed_ms" in df.columns:
            df["wind_category"] = pd.cut(
                df["wind_speed_ms"],
                bins=[0, 3, 7, 12, np.inf],
                labels=["calm", "moderate", "strong", "very_strong"],
            )

        logger.info("Created weather-derived features")
        return df

    @staticmethod
    def create_price_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create price-derived features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with price features
        """
        df = df.copy()

        if "price_inr_mwh" not in df.columns:
            return df

        # Price volatility (rolling std)
        df["price_volatility_24h"] = df["price_inr_mwh"].rolling(24).std()

        # Price change
        df["price_change"] = df["price_inr_mwh"].diff()
        df["price_change_pct"] = df["price_inr_mwh"].pct_change()

        # Price categories
        df["price_category"] = pd.cut(
            df["price_inr_mwh"],
            bins=[0, 2000, 4000, 6000, np.inf],
            labels=["low", "medium", "high", "very_high"],
        )

        logger.info("Created price-derived features")
        return df

    def create_all_features(
        self,
        df: pd.DataFrame,
        include_temporal: bool = True,
        include_cyclical: bool = True,
        include_demand: bool = True,
        include_weather: bool = True,
        include_price: bool = True,
    ) -> pd.DataFrame:
        """Create all feature engineering transformations.

        Args:
            df: Input DataFrame
            include_temporal: Include temporal features
            include_cyclical: Include cyclical encoding
            include_demand: Include demand-specific features
            include_weather: Include weather features
            include_price: Include price features

        Returns:
            DataFrame with all features
        """
        logger.info("Starting feature engineering pipeline")

        if include_temporal:
            df = self.create_temporal_features(df)

        if include_cyclical:
            cyclical_cols = ["hour", "day_of_week", "month"]
            cyclical_cols = [col for col in cyclical_cols if col in df.columns]
            if cyclical_cols:
                df = self.create_cyclical_features(df, cyclical_cols)

        if include_demand:
            df = self.create_demand_features(df)

        if include_weather:
            df = self.create_weather_features(df)

        if include_price:
            df = self.create_price_features(df)

        logger.info(f"Feature engineering complete. Output shape: {df.shape}")
        return df
