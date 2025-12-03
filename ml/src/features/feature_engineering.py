"""Advanced feature engineering for load forecasting.

Creates comprehensive features for time series forecasting including:
- Temporal features with cyclical encoding
- Lag features
- Rolling statistics
- Weather-derived features
- Interaction features
"""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class FeatureEngineering:
    """Comprehensive feature engineering for energy load forecasting.

    This class implements a fit/transform pattern similar to scikit-learn
    transformers, allowing features to be learned from training data and
    applied consistently to validation and test sets.
    """

    def __init__(
        self,
        # Temporal features
        include_temporal: bool = True,
        cyclical_features: List[str] = None,

        # Lag features
        include_lags: bool = True,
        lag_hours: List[int] = None,
        lag_columns: List[str] = None,

        # Rolling features
        include_rolling: bool = True,
        rolling_windows: List[int] = None,
        rolling_statistics: List[str] = None,
        rolling_columns: List[str] = None,

        # Weather features
        include_weather: bool = True,

        # Derived features
        include_derived: bool = True,
        include_interactions: bool = True,

        # Scaling
        scale_features: bool = True,
    ):
        """Initialize feature engineering.

        Args:
            include_temporal: Include temporal features
            cyclical_features: Features for cyclical encoding
            include_lags: Include lag features
            lag_hours: Hours for lag features
            lag_columns: Columns to create lags for
            include_rolling: Include rolling statistics
            rolling_windows: Window sizes for rolling features
            rolling_statistics: Statistics to compute (mean, std, min, max)
            rolling_columns: Columns for rolling statistics
            include_weather: Include weather-derived features
            include_derived: Include derived features
            include_interactions: Include interaction features
            scale_features: Whether to scale numerical features
        """
        # Configuration
        self.include_temporal = include_temporal
        self.cyclical_features = cyclical_features or ["hour", "day_of_week", "month"]

        self.include_lags = include_lags
        self.lag_hours = lag_hours or [1, 2, 3, 6, 12, 24, 48, 168, 8760]
        self.lag_columns = lag_columns or ["load_mw", "price_inr_mwh"]

        self.include_rolling = include_rolling
        self.rolling_windows = rolling_windows or [24, 168]
        self.rolling_statistics = rolling_statistics or ["mean", "std", "min", "max"]
        self.rolling_columns = rolling_columns or ["load_mw"]

        self.include_weather = include_weather
        self.include_derived = include_derived
        self.include_interactions = include_interactions
        self.scale_features = scale_features

        # State (learned during fit)
        self.is_fitted = False
        self.feature_names_: List[str] = []
        self.scalers_: Dict[str, StandardScaler] = {}
        self.feature_statistics_: Dict[str, Any] = {}

        # Base temperature for degree days (comfortable temperature)
        self.base_temperature = 18.0  # °C

    def _create_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create temporal features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with temporal features
        """
        if not self.include_temporal:
            return df

        df = df.copy()

        if "timestamp" not in df.columns:
            logger.warning("No timestamp column found")
            return df

        # Ensure datetime
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        ts = df["timestamp"]

        # Basic temporal features
        df["hour"] = ts.dt.hour
        df["day_of_week"] = ts.dt.dayofweek
        df["day_of_month"] = ts.dt.day
        df["day_of_year"] = ts.dt.dayofyear
        df["week_of_year"] = ts.dt.isocalendar().week.astype(int)
        df["month"] = ts.dt.month
        df["quarter"] = ts.dt.quarter
        df["year"] = ts.dt.year

        # Boolean features
        df["is_weekend"] = ts.dt.dayofweek.isin([5, 6]).astype(int)
        df["is_month_start"] = ts.dt.is_month_start.astype(int)
        df["is_month_end"] = ts.dt.is_month_end.astype(int)
        df["is_quarter_start"] = ts.dt.is_quarter_start.astype(int)
        df["is_quarter_end"] = ts.dt.is_quarter_end.astype(int)

        # Cyclical encoding
        for feature in self.cyclical_features:
            if feature not in df.columns:
                continue

            # Determine period
            periods = {
                "hour": 24,
                "day_of_week": 7,
                "day_of_month": 31,
                "day_of_year": 365,
                "week_of_year": 52,
                "month": 12,
            }

            period = periods.get(feature, 24)

            df[f"{feature}_sin"] = np.sin(2 * np.pi * df[feature] / period)
            df[f"{feature}_cos"] = np.cos(2 * np.pi * df[feature] / period)

        logger.info(f"Created temporal features")
        return df

    def _create_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create lag features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with lag features
        """
        if not self.include_lags:
            return df

        df = df.copy()

        for column in self.lag_columns:
            if column not in df.columns:
                logger.warning(f"Column {column} not found for lag features")
                continue

            for lag_hours in self.lag_hours:
                col_name = f"{column}_lag_{lag_hours}h"
                df[col_name] = df[column].shift(lag_hours)

        logger.info(f"Created lag features for {len(self.lag_columns)} columns")
        return df

    def _create_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create rolling window features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with rolling features
        """
        if not self.include_rolling:
            return df

        df = df.copy()

        for column in self.rolling_columns:
            if column not in df.columns:
                logger.warning(f"Column {column} not found for rolling features")
                continue

            for window in self.rolling_windows:
                for stat in self.rolling_statistics:
                    col_name = f"{column}_rolling_{stat}_{window}h"

                    if stat == "mean":
                        df[col_name] = df[column].rolling(window=window, min_periods=1).mean()
                    elif stat == "std":
                        df[col_name] = df[column].rolling(window=window, min_periods=1).std()
                    elif stat == "min":
                        df[col_name] = df[column].rolling(window=window, min_periods=1).min()
                    elif stat == "max":
                        df[col_name] = df[column].rolling(window=window, min_periods=1).max()
                    elif stat == "median":
                        df[col_name] = df[column].rolling(window=window, min_periods=1).median()

        logger.info(f"Created rolling features for {len(self.rolling_columns)} columns")
        return df

    def _create_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create weather-derived features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with weather features
        """
        if not self.include_weather:
            return df

        df = df.copy()

        # Find temperature columns (could be multiple locations)
        temp_cols = [col for col in df.columns if "temperature_c" in col.lower()]
        humidity_cols = [col for col in df.columns if "humidity" in col.lower()]

        for temp_col in temp_cols:
            location = temp_col.replace("temperature_c_", "").replace("temperature_c", "")

            # Heating Degree Days (HDD)
            # Days when heating is needed (temp < base_temp)
            hdd_col = f"hdd_{location}" if location else "hdd"
            df[hdd_col] = np.maximum(self.base_temperature - df[temp_col], 0)

            # Cooling Degree Days (CDD)
            # Days when cooling is needed (temp > base_temp)
            cdd_col = f"cdd_{location}" if location else "cdd"
            df[cdd_col] = np.maximum(df[temp_col] - self.base_temperature, 0)

            # Apparent temperature (heat index) if humidity available
            matching_humidity = [h for h in humidity_cols if location in h]
            if matching_humidity:
                humidity_col = matching_humidity[0]

                # Simplified heat index formula
                T = df[temp_col]
                RH = df[humidity_col]

                # Heat index (simplified Steadman formula)
                heat_index = (
                    T + 0.5555 * (
                        6.11 * np.exp(5417.7530 * (1/273.16 - 1/(273.15 + T)))
                        * (RH/100) - 10
                    )
                )

                apparent_col = f"apparent_temp_{location}" if location else "apparent_temp"
                df[apparent_col] = heat_index

                # Discomfort index
                discomfort_col = f"discomfort_{location}" if location else "discomfort"
                df[discomfort_col] = T - 0.55 * (1 - RH/100) * (T - 14.5)

        logger.info("Created weather-derived features")
        return df

    def _create_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create derived and difference features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with derived features
        """
        if not self.include_derived:
            return df

        df = df.copy()

        # Load-based features
        load_cols = [col for col in df.columns if "load_mw" in col and "lag" not in col and "rolling" not in col]

        for load_col in load_cols:
            # Differences
            df[f"{load_col}_diff_1h"] = df[load_col].diff(1)
            df[f"{load_col}_diff_24h"] = df[load_col].diff(24)

            # Percentage changes
            df[f"{load_col}_pct_change_1h"] = df[load_col].pct_change(1)
            df[f"{load_col}_pct_change_24h"] = df[load_col].pct_change(24)

        # Price-based features (if available)
        price_cols = [col for col in df.columns if "price" in col and "lag" not in col and "rolling" not in col]

        for price_col in price_cols:
            df[f"{price_col}_diff_1h"] = df[price_col].diff(1)
            df[f"{price_col}_pct_change_1h"] = df[price_col].pct_change(1)

        # Time-based indicators
        if "hour" in df.columns:
            # Peak hours (high demand: 18:00-22:00)
            df["is_peak_hour"] = df["hour"].isin(range(18, 23)).astype(int)

            # Shoulder hours (medium demand: 06:00-09:00, 16:00-18:00)
            df["is_shoulder_hour"] = (
                df["hour"].isin(list(range(6, 10)) + list(range(16, 18)))
            ).astype(int)

            # Off-peak hours (low demand: 22:00-06:00)
            df["is_offpeak_hour"] = (
                df["hour"].isin(list(range(0, 6)) + list(range(22, 24)))
            ).astype(int)

            # Working hours (09:00-18:00 on weekdays)
            if "is_weekend" in df.columns:
                df["is_working_hour"] = (
                    (df["hour"].between(9, 18)) & (df["is_weekend"] == 0)
                ).astype(int)

        logger.info("Created derived features")
        return df

    def _create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with interaction features
        """
        if not self.include_interactions:
            return df

        df = df.copy()

        # Temperature-Load interaction
        temp_cols = [col for col in df.columns if "temperature_c" in col.lower() and "lag" not in col]
        load_cols = [col for col in df.columns if "load_mw" in col and "lag" not in col and "rolling" not in col]

        for temp_col in temp_cols:
            for load_col in load_cols:
                if temp_col in df.columns and load_col in df.columns:
                    location = temp_col.replace("temperature_c_", "").replace("temperature_c", "")
                    load_region = load_col.replace("load_mw_", "").replace("load_mw", "")

                    interaction_name = f"temp_load_interaction"
                    if location:
                        interaction_name += f"_{location}"
                    if load_region:
                        interaction_name += f"_{load_region}"

                    df[interaction_name] = df[temp_col] * df[load_col]

        # Hour-Temperature interaction (time of day affects temperature impact)
        if "hour" in df.columns:
            for temp_col in temp_cols:
                location = temp_col.replace("temperature_c_", "").replace("temperature_c", "")
                interaction_name = f"hour_temp_interaction"
                if location:
                    interaction_name += f"_{location}"

                df[interaction_name] = df["hour"] * df[temp_col]

        # Weekend-Hour interaction
        if "is_weekend" in df.columns and "hour" in df.columns:
            df["weekend_hour_interaction"] = df["is_weekend"] * df["hour"]

        logger.info("Created interaction features")
        return df

    def fit(self, df: pd.DataFrame) -> "FeatureEngineering":
        """Fit the feature engineering pipeline.

        Learns statistics from the training data that will be used
        during transform (e.g., scaling parameters).

        Args:
            df: Training DataFrame

        Returns:
            self
        """
        logger.info("Fitting feature engineering pipeline...")

        # Create all features
        df_transformed = self._transform_impl(df, is_fitting=True)

        # Learn scaling parameters if needed
        if self.scale_features:
            numeric_cols = df_transformed.select_dtypes(include=[np.number]).columns.tolist()

            # Exclude certain columns from scaling
            exclude_cols = ["timestamp", "year", "is_weekend", "is_holiday", "is_peak_hour"]
            numeric_cols = [col for col in numeric_cols if col not in exclude_cols and not col.startswith("is_")]

            for col in numeric_cols:
                if col in df_transformed.columns:
                    scaler = StandardScaler()
                    scaler.fit(df_transformed[[col]])
                    self.scalers_[col] = scaler

            logger.info(f"Fitted scalers for {len(self.scalers_)} features")

        # Store feature names
        self.feature_names_ = df_transformed.columns.tolist()

        # Store statistics
        self.feature_statistics_ = {
            "n_features": len(self.feature_names_),
            "n_temporal": sum(1 for f in self.feature_names_ if any(x in f for x in ["hour", "day", "month", "quarter"])),
            "n_lag": sum(1 for f in self.feature_names_ if "lag" in f),
            "n_rolling": sum(1 for f in self.feature_names_ if "rolling" in f),
            "n_weather": sum(1 for f in self.feature_names_ if any(x in f for x in ["hdd", "cdd", "apparent"])),
            "n_derived": sum(1 for f in self.feature_names_ if any(x in f for x in ["diff", "pct_change"])),
            "n_interaction": sum(1 for f in self.feature_names_ if "interaction" in f),
        }

        self.is_fitted = True
        logger.info("Feature engineering fitted successfully")
        logger.info(f"Total features: {self.feature_statistics_['n_features']}")

        return self

    def _transform_impl(self, df: pd.DataFrame, is_fitting: bool = False) -> pd.DataFrame:
        """Internal transform implementation.

        Args:
            df: Input DataFrame
            is_fitting: Whether this is called during fit

        Returns:
            Transformed DataFrame
        """
        df = df.copy()

        # Create features in order
        df = self._create_temporal_features(df)
        df = self._create_lag_features(df)
        df = self._create_rolling_features(df)
        df = self._create_weather_features(df)
        df = self._create_derived_features(df)
        df = self._create_interaction_features(df)

        return df

    def transform(self, df: pd.DataFrame, scale: bool = True) -> pd.DataFrame:
        """Transform DataFrame with fitted feature engineering.

        Args:
            df: Input DataFrame
            scale: Whether to apply scaling

        Returns:
            Transformed DataFrame with all features
        """
        if not self.is_fitted:
            raise ValueError("FeatureEngineering must be fitted before transform. Call fit() first.")

        logger.info("Transforming data with feature engineering...")

        # Create features
        df_transformed = self._transform_impl(df, is_fitting=False)

        # Apply scaling if requested
        if scale and self.scale_features and self.scalers_:
            for col, scaler in self.scalers_.items():
                if col in df_transformed.columns:
                    df_transformed[col] = scaler.transform(df_transformed[[col]])

        logger.info(f"Transformed to {len(df_transformed.columns)} features")
        return df_transformed

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit and transform in one step.

        Args:
            df: Input DataFrame

        Returns:
            Transformed DataFrame
        """
        return self.fit(df).transform(df)

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names.

        Returns:
            List of feature names
        """
        if not self.is_fitted:
            raise ValueError("FeatureEngineering must be fitted first")

        return self.feature_names_.copy()

    def get_feature_statistics(self) -> Dict[str, Any]:
        """Get feature statistics.

        Returns:
            Dictionary of feature statistics
        """
        if not self.is_fitted:
            raise ValueError("FeatureEngineering must be fitted first")

        return self.feature_statistics_.copy()

    def save(self, path: Path) -> None:
        """Save fitted feature engineering to file.

        Args:
            path: Path to save to
        """
        if not self.is_fitted:
            raise ValueError("FeatureEngineering must be fitted before saving")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "config": {
                "include_temporal": self.include_temporal,
                "cyclical_features": self.cyclical_features,
                "include_lags": self.include_lags,
                "lag_hours": self.lag_hours,
                "lag_columns": self.lag_columns,
                "include_rolling": self.include_rolling,
                "rolling_windows": self.rolling_windows,
                "rolling_statistics": self.rolling_statistics,
                "rolling_columns": self.rolling_columns,
                "include_weather": self.include_weather,
                "include_derived": self.include_derived,
                "include_interactions": self.include_interactions,
                "scale_features": self.scale_features,
                "base_temperature": self.base_temperature,
            },
            "state": {
                "is_fitted": self.is_fitted,
                "feature_names_": self.feature_names_,
                "scalers_": self.scalers_,
                "feature_statistics_": self.feature_statistics_,
            }
        }

        with open(path, "wb") as f:
            pickle.dump(state, f)

        logger.info(f"Saved feature engineering to {path}")

    @classmethod
    def load(cls, path: Path) -> "FeatureEngineering":
        """Load fitted feature engineering from file.

        Args:
            path: Path to load from

        Returns:
            Loaded FeatureEngineering instance
        """
        path = Path(path)

        with open(path, "rb") as f:
            state = pickle.load(f)

        # Create instance with saved config
        instance = cls(**state["config"])

        # Restore state
        instance.is_fitted = state["state"]["is_fitted"]
        instance.feature_names_ = state["state"]["feature_names_"]
        instance.scalers_ = state["state"]["scalers_"]
        instance.feature_statistics_ = state["state"]["feature_statistics_"]

        logger.info(f"Loaded feature engineering from {path}")
        return instance
