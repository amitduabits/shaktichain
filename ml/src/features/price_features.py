"""Price-specific feature engineering for SHAKTI-CHAIN.

Implements features tailored for electricity price forecasting:
- Price lags and rolling statistics
- Demand-supply ratio
- Grid stress indicators
- Fuel price features
- Load forecast integration
- Volatility features
- Regime indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PriceFeatureConfig:
    """Configuration for price feature engineering."""
    # Price lag features
    price_lags: List[int] = None  # Hours of lag
    # Rolling windows for statistics
    rolling_windows: List[int] = None  # Hours
    # Demand-supply features
    include_demand_supply: bool = True
    # Grid frequency features
    include_grid_frequency: bool = True
    # Fuel price features
    include_fuel_prices: bool = True
    # Volatility features
    include_volatility: bool = True
    # Regime indicators
    include_regime_indicators: bool = True
    # Load forecast features
    include_load_forecast: bool = True
    # Spike detection threshold (percentile)
    spike_threshold_percentile: float = 95.0
    # Base temperature for degree days
    base_temperature: float = 22.0

    def __post_init__(self):
        if self.price_lags is None:
            self.price_lags = [1, 2, 3, 6, 12, 24, 48, 168]  # Up to 1 week
        if self.rolling_windows is None:
            self.rolling_windows = [6, 12, 24, 48, 168]


class PriceFeatureEngineering:
    """Feature engineering for electricity price prediction.

    Creates features specifically designed for price forecasting:
    1. Price lags (1h to 168h)
    2. Rolling statistics (mean, std, min, max, percentiles)
    3. Demand-supply ratio
    4. Grid stress indicators
    5. Fuel price features
    6. Volatility features (EWMA, Parkinson)
    7. Regime indicators
    8. Load forecast features

    Args:
        config: PriceFeatureConfig or None for defaults
        target_col: Name of target price column
        load_col: Name of load column
    """

    def __init__(
        self,
        config: Optional[PriceFeatureConfig] = None,
        target_col: str = "price_inr_mwh",
        load_col: str = "load_mw",
    ):
        self.config = config or PriceFeatureConfig()
        self.target_col = target_col
        self.load_col = load_col

        # Statistics from training data
        self.price_mean = None
        self.price_std = None
        self.price_percentiles = None
        self.spike_threshold = None
        self.feature_means = None
        self.feature_stds = None

        self.is_fitted = False
        self.feature_names = []

    def fit(self, df: pd.DataFrame) -> "PriceFeatureEngineering":
        """Fit feature engineering on training data.

        Args:
            df: Training DataFrame with price data

        Returns:
            Self
        """
        logger.info("Fitting price feature engineering...")

        if self.target_col not in df.columns:
            raise ValueError(f"Target column '{self.target_col}' not found in data")

        price = df[self.target_col]

        # Calculate price statistics
        self.price_mean = price.mean()
        self.price_std = price.std()
        self.price_percentiles = {
            5: price.quantile(0.05),
            25: price.quantile(0.25),
            50: price.quantile(0.50),
            75: price.quantile(0.75),
            95: price.quantile(0.95),
            99: price.quantile(0.99),
        }

        # Spike threshold
        self.spike_threshold = price.quantile(self.config.spike_threshold_percentile / 100)
        logger.info(f"Spike threshold (P{self.config.spike_threshold_percentile}): {self.spike_threshold:.2f}")

        # Transform to get feature names
        df_features = self.transform(df, fitting=True)
        self.feature_names = [c for c in df_features.columns if c not in ["timestamp", self.target_col]]

        # Calculate feature statistics for normalization
        numeric_cols = df_features.select_dtypes(include=[np.number]).columns
        feature_cols = [c for c in numeric_cols if c != self.target_col]
        self.feature_means = df_features[feature_cols].mean()
        self.feature_stds = df_features[feature_cols].std().replace(0, 1)

        self.is_fitted = True
        logger.info(f"Created {len(self.feature_names)} price features")

        return self

    def transform(
        self,
        df: pd.DataFrame,
        normalize: bool = False,
        fitting: bool = False,
    ) -> pd.DataFrame:
        """Transform data to create price features.

        Args:
            df: Input DataFrame
            normalize: Whether to normalize features
            fitting: Whether this is during fitting (skip validation)

        Returns:
            DataFrame with price features
        """
        if not fitting and not self.is_fitted:
            raise ValueError("Feature engineering not fitted. Call fit() first.")

        df = df.copy()

        # Ensure timestamp is datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)

        # Create all feature groups
        df = self._create_price_lag_features(df)
        df = self._create_price_rolling_features(df)
        df = self._create_temporal_features(df)

        if self.config.include_volatility:
            df = self._create_volatility_features(df)

        if self.config.include_demand_supply and self.load_col in df.columns:
            df = self._create_demand_supply_features(df)

        if self.config.include_grid_frequency and "grid_frequency_hz" in df.columns:
            df = self._create_grid_frequency_features(df)

        if self.config.include_fuel_prices:
            df = self._create_fuel_price_features(df)

        if self.config.include_regime_indicators:
            df = self._create_regime_indicators(df)

        if self.config.include_load_forecast and "load_forecast" in df.columns:
            df = self._create_load_forecast_features(df)

        # Create spike indicator
        df = self._create_spike_features(df)

        # Normalize if requested
        if normalize and self.feature_means is not None:
            df = self._normalize_features(df)

        return df

    def _create_price_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create price lag features."""
        price = df[self.target_col]

        for lag in self.config.price_lags:
            df[f"price_lag_{lag}h"] = price.shift(lag)

        # Price differences
        df["price_diff_1h"] = price.diff(1)
        df["price_diff_24h"] = price.diff(24)
        df["price_diff_168h"] = price.diff(168)

        # Percentage changes
        df["price_pct_change_1h"] = price.pct_change(1) * 100
        df["price_pct_change_24h"] = price.pct_change(24) * 100

        # Same hour yesterday and last week
        df["price_same_hour_yesterday"] = price.shift(24)
        df["price_same_hour_last_week"] = price.shift(168)

        return df

    def _create_price_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create rolling statistics for price."""
        price = df[self.target_col]

        for window in self.config.rolling_windows:
            # Rolling mean
            df[f"price_rolling_mean_{window}h"] = price.rolling(window, min_periods=1).mean()

            # Rolling std
            df[f"price_rolling_std_{window}h"] = price.rolling(window, min_periods=1).std()

            # Rolling min/max
            df[f"price_rolling_min_{window}h"] = price.rolling(window, min_periods=1).min()
            df[f"price_rolling_max_{window}h"] = price.rolling(window, min_periods=1).max()

            # Rolling range
            df[f"price_rolling_range_{window}h"] = (
                df[f"price_rolling_max_{window}h"] - df[f"price_rolling_min_{window}h"]
            )

            # Rolling percentiles
            df[f"price_rolling_p25_{window}h"] = price.rolling(window, min_periods=1).quantile(0.25)
            df[f"price_rolling_p75_{window}h"] = price.rolling(window, min_periods=1).quantile(0.75)

        # Price relative to rolling mean (mean reversion indicator)
        df["price_vs_rolling_mean_24h"] = price / (df["price_rolling_mean_24h"] + 1e-8)
        df["price_vs_rolling_mean_168h"] = price / (df["price_rolling_mean_168h"] + 1e-8)

        return df

    def _create_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create temporal features for price patterns."""
        if "timestamp" not in df.columns:
            return df

        ts = df["timestamp"]

        # Hour of day (prices vary by hour)
        df["hour"] = ts.dt.hour
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

        # Day of week
        df["day_of_week"] = ts.dt.dayofweek
        df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

        # Month (seasonal patterns)
        df["month"] = ts.dt.month
        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

        # Time of day categories (peak pricing periods)
        df["is_peak_hour"] = df["hour"].isin([9, 10, 11, 12, 18, 19, 20, 21]).astype(int)
        df["is_morning_peak"] = df["hour"].isin([9, 10, 11, 12]).astype(int)
        df["is_evening_peak"] = df["hour"].isin([18, 19, 20, 21]).astype(int)
        df["is_night"] = df["hour"].isin(list(range(0, 6)) + [22, 23]).astype(int)

        # Weekend
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

        return df

    def _create_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create volatility features for price."""
        price = df[self.target_col]

        # EWMA volatility (exponentially weighted)
        for span in [6, 24, 168]:
            df[f"price_ewma_{span}h"] = price.ewm(span=span).mean()
            df[f"price_ewma_std_{span}h"] = price.ewm(span=span).std()

        # Realized volatility (annualized)
        returns = price.pct_change()
        df["realized_vol_24h"] = returns.rolling(24).std() * np.sqrt(24 * 365)
        df["realized_vol_168h"] = returns.rolling(168).std() * np.sqrt(24 * 365)

        # Parkinson volatility (using high-low range if available)
        if "price_high" in df.columns and "price_low" in df.columns:
            log_hl = np.log(df["price_high"] / (df["price_low"] + 1e-8))
            df["parkinson_vol_24h"] = np.sqrt(log_hl.rolling(24).apply(
                lambda x: (x ** 2).mean() / (4 * np.log(2))
            ))

        # Volatility of volatility
        df["vol_of_vol"] = df["realized_vol_24h"].rolling(24).std()

        # Price momentum
        df["price_momentum_6h"] = price - price.shift(6)
        df["price_momentum_24h"] = price - price.shift(24)

        # RSI-like indicator
        delta = price.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-8)
        df["price_rsi"] = 100 - (100 / (1 + rs))

        return df

    def _create_demand_supply_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create demand-supply features."""
        load = df[self.load_col]
        price = df[self.target_col]

        # Load features
        df["load_lag_1h"] = load.shift(1)
        df["load_rolling_mean_24h"] = load.rolling(24, min_periods=1).mean()
        df["load_pct_change_1h"] = load.pct_change(1) * 100

        # Load-price correlation features
        df["price_load_ratio"] = price / (load + 1e-8)
        df["price_load_ratio_rolling"] = df["price_load_ratio"].rolling(24, min_periods=1).mean()

        # Demand-supply ratio (if supply data available)
        if "supply_mw" in df.columns:
            df["demand_supply_ratio"] = load / (df["supply_mw"] + 1e-8)
            df["supply_margin"] = df["supply_mw"] - load
            df["supply_margin_pct"] = (df["supply_mw"] - load) / (df["supply_mw"] + 1e-8) * 100

        # Load percentile (indicates stress)
        load_percentile = load.rolling(168, min_periods=1).apply(
            lambda x: (x[-1] >= x).mean() * 100 if len(x) > 0 else 50
        )
        df["load_percentile_168h"] = load_percentile

        return df

    def _create_grid_frequency_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create grid frequency-based stress indicators."""
        freq = df["grid_frequency_hz"]

        # Grid frequency deviation from nominal (50 Hz)
        df["freq_deviation"] = freq - 50.0
        df["freq_deviation_abs"] = np.abs(df["freq_deviation"])

        # Rolling frequency statistics
        df["freq_rolling_mean_1h"] = freq.rolling(1, min_periods=1).mean()
        df["freq_rolling_std_1h"] = freq.rolling(1, min_periods=1).std()
        df["freq_rolling_min_1h"] = freq.rolling(1, min_periods=1).min()
        df["freq_rolling_max_1h"] = freq.rolling(1, min_periods=1).max()

        # Grid stress indicator
        # Low frequency (<49.5 Hz) indicates high stress
        df["grid_stress"] = (freq < 49.5).astype(int)
        df["grid_stress_severe"] = (freq < 49.2).astype(int)

        # Frequency stability (lower is more stable)
        df["freq_stability_1h"] = df["freq_rolling_max_1h"] - df["freq_rolling_min_1h"]

        return df

    def _create_fuel_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create fuel price features."""
        # Natural gas price
        if "natural_gas_price" in df.columns:
            gas = df["natural_gas_price"]
            df["gas_price_lag_24h"] = gas.shift(24)
            df["gas_price_rolling_mean_168h"] = gas.rolling(168, min_periods=1).mean()
            df["gas_price_pct_change_24h"] = gas.pct_change(24) * 100

        # Coal price
        if "coal_price" in df.columns:
            coal = df["coal_price"]
            df["coal_price_lag_24h"] = coal.shift(24)
            df["coal_price_rolling_mean_168h"] = coal.rolling(168, min_periods=1).mean()

        # Renewable generation share
        if "renewable_share" in df.columns:
            df["renewable_share_lag_1h"] = df["renewable_share"].shift(1)
            df["renewable_share_rolling_mean"] = df["renewable_share"].rolling(24, min_periods=1).mean()

        return df

    def _create_regime_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create regime indicators for price modeling."""
        price = df[self.target_col]

        # Price regime based on percentiles
        if self.price_percentiles is not None:
            df["regime_low"] = (price < self.price_percentiles[25]).astype(int)
            df["regime_normal"] = (
                (price >= self.price_percentiles[25]) &
                (price <= self.price_percentiles[75])
            ).astype(int)
            df["regime_high"] = (price > self.price_percentiles[75]).astype(int)
            df["regime_extreme"] = (price > self.price_percentiles[95]).astype(int)

        # Volatility regime
        vol = df.get("realized_vol_24h")
        if vol is not None:
            vol_median = vol.median()
            df["high_volatility_regime"] = (vol > vol_median * 1.5).astype(int)

        # Mean reversion indicator
        if self.price_mean is not None:
            df["above_mean"] = (price > self.price_mean).astype(int)
            df["far_from_mean"] = (np.abs(price - self.price_mean) > self.price_std * 2).astype(int)

        return df

    def _create_load_forecast_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create features from load forecast."""
        if "load_forecast" not in df.columns:
            return df

        forecast = df["load_forecast"]

        # Forecast error (if actual load available)
        if self.load_col in df.columns:
            df["load_forecast_error"] = df[self.load_col] - forecast
            df["load_forecast_error_pct"] = (
                (df[self.load_col] - forecast) / (df[self.load_col] + 1e-8) * 100
            )

        # Forecast uncertainty (if available)
        if "load_forecast_std" in df.columns:
            df["load_forecast_cv"] = df["load_forecast_std"] / (forecast + 1e-8)

        # Forecast percentile
        if "load_forecast_q10" in df.columns and "load_forecast_q90" in df.columns:
            df["load_forecast_range"] = df["load_forecast_q90"] - df["load_forecast_q10"]

        return df

    def _create_spike_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create spike detection features."""
        price = df[self.target_col]

        # Spike indicator
        if self.spike_threshold is not None:
            df["is_spike"] = (price > self.spike_threshold).astype(int)
        else:
            # Use rolling threshold
            rolling_p95 = price.rolling(168, min_periods=24).quantile(0.95)
            df["is_spike"] = (price > rolling_p95).astype(int)

        # Previous spikes
        df["spike_lag_1h"] = df["is_spike"].shift(1)
        df["spike_lag_24h"] = df["is_spike"].shift(24)
        df["spike_count_24h"] = df["is_spike"].rolling(24, min_periods=1).sum()

        # Time since last spike
        spike_indices = df[df["is_spike"] == 1].index
        df["hours_since_spike"] = np.nan
        for idx in df.index:
            prev_spikes = spike_indices[spike_indices < idx]
            if len(prev_spikes) > 0:
                df.loc[idx, "hours_since_spike"] = idx - prev_spikes[-1]
        df["hours_since_spike"] = df["hours_since_spike"].fillna(168)  # Default to 1 week

        return df

    def _normalize_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize features using training statistics."""
        df = df.copy()

        for col in self.feature_means.index:
            if col in df.columns:
                df[col] = (df[col] - self.feature_means[col]) / (self.feature_stds[col] + 1e-8)

        return df

    def get_feature_names(self) -> List[str]:
        """Get list of feature names."""
        return self.feature_names

    def get_feature_groups(self) -> Dict[str, List[str]]:
        """Get features grouped by category."""
        groups = {
            "price_lags": [f for f in self.feature_names if "price_lag" in f or "price_diff" in f],
            "price_rolling": [f for f in self.feature_names if "price_rolling" in f],
            "temporal": [f for f in self.feature_names if any(t in f for t in ["hour", "day", "month", "peak", "weekend"])],
            "volatility": [f for f in self.feature_names if any(v in f for v in ["vol", "ewma", "momentum", "rsi"])],
            "demand_supply": [f for f in self.feature_names if any(d in f for d in ["load", "supply", "demand"])],
            "grid": [f for f in self.feature_names if "freq" in f or "grid" in f],
            "regime": [f for f in self.feature_names if "regime" in f or "mean" in f],
            "spike": [f for f in self.feature_names if "spike" in f],
        }
        return groups

    def save(self, path: str) -> None:
        """Save fitted feature engineering state."""
        state = {
            "config": self.config,
            "target_col": self.target_col,
            "load_col": self.load_col,
            "price_mean": self.price_mean,
            "price_std": self.price_std,
            "price_percentiles": self.price_percentiles,
            "spike_threshold": self.spike_threshold,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
            "feature_names": self.feature_names,
            "is_fitted": self.is_fitted,
        }
        joblib.dump(state, path)
        logger.info(f"Saved price feature engineering to {path}")

    @classmethod
    def load(cls, path: str) -> "PriceFeatureEngineering":
        """Load fitted feature engineering from file."""
        state = joblib.load(path)

        instance = cls(
            config=state["config"],
            target_col=state["target_col"],
            load_col=state["load_col"],
        )
        instance.price_mean = state["price_mean"]
        instance.price_std = state["price_std"]
        instance.price_percentiles = state["price_percentiles"]
        instance.spike_threshold = state["spike_threshold"]
        instance.feature_means = state["feature_means"]
        instance.feature_stds = state["feature_stds"]
        instance.feature_names = state["feature_names"]
        instance.is_fitted = state["is_fitted"]

        logger.info(f"Loaded price feature engineering from {path}")
        return instance
