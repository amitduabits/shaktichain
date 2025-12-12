"""
Baseline Forecasting Models for SHAKTI-CHAIN Load Forecasting (Domain 7).

Implements baseline models for comparison:
- Naive Forecaster (last value)
- Seasonal Naive (same value from previous period)
- Moving Average
- ARIMA (optional, requires statsmodels)
- Prophet (optional, requires prophet)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BaseForecaster(ABC):
    """Abstract base class for forecasters."""

    @abstractmethod
    def fit(self, data: np.ndarray) -> None:
        """Fit the model to historical data."""
        pass

    @abstractmethod
    def predict(self, horizon: int) -> np.ndarray:
        """Generate point forecasts."""
        pass

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate forecasts with prediction intervals.

        Returns:
            (point_forecast, lower_bound, upper_bound)
        """
        point = self.predict(horizon)
        # Default: simple symmetric interval based on historical error
        return point, point * 0.9, point * 1.1


class NaiveForecaster(BaseForecaster):
    """
    Naive Forecaster: Predict same as last observed value.

    Simple baseline that assumes no change.
    """

    def __init__(self):
        self.last_value = None
        self.std = None

    def fit(self, data, target_col: str = "load_mw") -> None:
        """Store the last value."""
        if isinstance(data, pd.DataFrame):
            data = data[target_col].values
        data = np.asarray(data)
        self.last_value = data[-1]
        # Estimate standard deviation for intervals
        if len(data) > 1:
            diffs = np.diff(data)
            self.std = np.std(diffs)
        else:
            self.std = 0

    def predict(self, horizon: int) -> np.ndarray:
        """Predict last value for all horizon steps."""
        return np.full(horizon, self.last_value)

    def forecast(self, horizon: int) -> np.ndarray:
        """Alias for predict for compatibility."""
        return self.predict(horizon)

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate prediction intervals (widening over horizon)."""
        from scipy import stats as scipy_stats

        point = self.predict(horizon)
        z = scipy_stats.norm.ppf((1 + confidence) / 2)

        # Uncertainty grows with horizon
        horizon_std = self.std * np.sqrt(np.arange(1, horizon + 1))
        lower = point - z * horizon_std
        upper = point + z * horizon_std

        return point, lower, upper


class SeasonalNaiveForecaster(BaseForecaster):
    """
    Seasonal Naive Forecaster: Predict same value from previous seasonal period.

    For hourly data with daily seasonality, uses value from 24 hours ago.
    For hourly data with weekly seasonality, uses value from 168 hours ago.
    """

    def __init__(self, period: int = 24, season_length: int = None):
        """
        Initialize with seasonality period.

        Args:
            period: Seasonal period (e.g., 24 for daily, 168 for weekly)
            season_length: Alias for period (for compatibility)
        """
        self.period = season_length if season_length is not None else period
        self.history = None
        self.std = None

    def fit(self, data, target_col: str = "load_mw") -> None:
        """Store enough history for seasonal prediction."""
        if isinstance(data, pd.DataFrame):
            data = data[target_col].values
        data = np.asarray(data)
        self.history = data[-self.period:]

        # Estimate seasonal difference std
        if len(data) > self.period:
            seasonal_diffs = data[self.period:] - data[:-self.period]
            self.std = np.std(seasonal_diffs)
        else:
            self.std = np.std(data) * 0.1

    def predict(self, horizon: int) -> np.ndarray:
        """Predict using same values from previous period."""
        if self.history is None:
            raise ValueError("Model not fitted")

        predictions = np.zeros(horizon)
        for i in range(horizon):
            idx = i % self.period
            predictions[i] = self.history[idx]

        return predictions

    def forecast(self, horizon: int) -> np.ndarray:
        """Alias for predict for compatibility."""
        return self.predict(horizon)

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate prediction intervals."""
        from scipy import stats as scipy_stats

        point = self.predict(horizon)
        z = scipy_stats.norm.ppf((1 + confidence) / 2)

        # Constant uncertainty (seasonal assumption)
        lower = point - z * self.std
        upper = point + z * self.std

        return point, lower, upper


class MovingAverageForecaster(BaseForecaster):
    """
    Moving Average Forecaster: Predict using average of recent values.
    """

    def __init__(self, window: int = 24):
        """
        Initialize with window size.

        Args:
            window: Number of recent values to average
        """
        self.window = window
        self.mean = None
        self.std = None

    def fit(self, data, target_col: str = "load_mw") -> None:
        """Calculate moving average statistics."""
        if isinstance(data, pd.DataFrame):
            data = data[target_col].values
        data = np.asarray(data)
        self.mean = np.mean(data[-self.window:])
        self.std = np.std(data[-self.window:])

    def predict(self, horizon: int) -> np.ndarray:
        """Predict using moving average."""
        return np.full(horizon, self.mean)

    def forecast(self, horizon: int) -> np.ndarray:
        """Alias for predict for compatibility."""
        return self.predict(horizon)

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate prediction intervals."""
        from scipy import stats as scipy_stats

        point = self.predict(horizon)
        z = scipy_stats.norm.ppf((1 + confidence) / 2)

        lower = point - z * self.std
        upper = point + z * self.std

        return point, lower, upper


class ExponentialSmoothingForecaster(BaseForecaster):
    """
    Simple Exponential Smoothing Forecaster.
    """

    def __init__(self, alpha: float = 0.3):
        """
        Initialize with smoothing parameter.

        Args:
            alpha: Smoothing parameter (0-1, higher = more weight on recent)
        """
        self.alpha = alpha
        self.level = None
        self.residuals = None

    def fit(self, data: np.ndarray) -> None:
        """Fit exponential smoothing."""
        data = np.asarray(data)
        n = len(data)

        # Initialize level
        self.level = data[0]
        fitted = np.zeros(n)

        for i in range(n):
            fitted[i] = self.level
            self.level = self.alpha * data[i] + (1 - self.alpha) * self.level

        self.residuals = data - fitted

    def predict(self, horizon: int) -> np.ndarray:
        """Predict using current level."""
        return np.full(horizon, self.level)

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate prediction intervals."""
        from scipy import stats as scipy_stats

        point = self.predict(horizon)
        z = scipy_stats.norm.ppf((1 + confidence) / 2)

        std = np.std(self.residuals) if self.residuals is not None else point[0] * 0.1
        lower = point - z * std
        upper = point + z * std

        return point, lower, upper


class ARIMAForecaster(BaseForecaster):
    """
    ARIMA Forecaster.

    Requires statsmodels package.
    """

    def __init__(self, order: Tuple[int, int, int] = (2, 1, 2)):
        """
        Initialize ARIMA model.

        Args:
            order: (p, d, q) order for ARIMA
        """
        self.order = order
        self.model = None
        self.fitted = None

    def fit(self, data: np.ndarray) -> None:
        """Fit ARIMA model."""
        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError:
            logger.warning("statsmodels not available, ARIMA will use fallback")
            self._fit_fallback(data)
            return

        data = np.asarray(data)

        try:
            self.model = ARIMA(data, order=self.order)
            self.fitted = self.model.fit()
        except Exception as e:
            logger.warning(f"ARIMA fitting failed: {e}, using fallback")
            self._fit_fallback(data)

    def _fit_fallback(self, data: np.ndarray):
        """Fallback to exponential smoothing if ARIMA fails."""
        self._fallback = ExponentialSmoothingForecaster()
        self._fallback.fit(data)

    def predict(self, horizon: int) -> np.ndarray:
        """Generate ARIMA forecasts."""
        if hasattr(self, '_fallback'):
            return self._fallback.predict(horizon)

        if self.fitted is None:
            raise ValueError("Model not fitted")

        return self.fitted.forecast(steps=horizon)

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate prediction intervals."""
        if hasattr(self, '_fallback'):
            return self._fallback.predict_interval(horizon, confidence)

        if self.fitted is None:
            raise ValueError("Model not fitted")

        alpha = 1 - confidence
        forecast = self.fitted.get_forecast(steps=horizon)
        conf_int = forecast.conf_int(alpha=alpha)

        point = forecast.predicted_mean
        lower = conf_int.iloc[:, 0].values
        upper = conf_int.iloc[:, 1].values

        return point, lower, upper


class ProphetForecaster(BaseForecaster):
    """
    Prophet Forecaster.

    Requires prophet package.
    """

    def __init__(
        self,
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = True,
    ):
        """
        Initialize Prophet model.

        Args:
            yearly_seasonality: Include yearly seasonality
            weekly_seasonality: Include weekly seasonality
            daily_seasonality: Include daily seasonality
        """
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.model = None
        self.last_timestamp = None

    def fit(self, data: np.ndarray, timestamps: Optional[pd.DatetimeIndex] = None) -> None:
        """
        Fit Prophet model.

        Args:
            data: Time series values
            timestamps: Optional timestamps (generates if None)
        """
        try:
            from prophet import Prophet
        except ImportError:
            logger.warning("prophet not available, using fallback")
            self._fit_fallback(data)
            return

        data = np.asarray(data)

        # Generate timestamps if not provided
        if timestamps is None:
            end = pd.Timestamp.now()
            timestamps = pd.date_range(end=end, periods=len(data), freq='h')

        self.last_timestamp = timestamps[-1]

        # Prepare data in Prophet format
        df = pd.DataFrame({
            'ds': timestamps,
            'y': data
        })

        try:
            self.model = Prophet(
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
            )
            self.model.fit(df)
        except Exception as e:
            logger.warning(f"Prophet fitting failed: {e}, using fallback")
            self._fit_fallback(data)

    def _fit_fallback(self, data: np.ndarray):
        """Fallback to seasonal naive if Prophet fails."""
        self._fallback = SeasonalNaiveForecaster(period=24)
        self._fallback.fit(data)

    def predict(self, horizon: int) -> np.ndarray:
        """Generate Prophet forecasts."""
        if hasattr(self, '_fallback'):
            return self._fallback.predict(horizon)

        if self.model is None:
            raise ValueError("Model not fitted")

        future = self.model.make_future_dataframe(periods=horizon, freq='h')
        forecast = self.model.predict(future)

        return forecast['yhat'].values[-horizon:]

    def predict_interval(
        self,
        horizon: int,
        confidence: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate prediction intervals."""
        if hasattr(self, '_fallback'):
            return self._fallback.predict_interval(horizon, confidence)

        if self.model is None:
            raise ValueError("Model not fitted")

        future = self.model.make_future_dataframe(periods=horizon, freq='h')
        forecast = self.model.predict(future)

        point = forecast['yhat'].values[-horizon:]
        lower = forecast['yhat_lower'].values[-horizon:]
        upper = forecast['yhat_upper'].values[-horizon:]

        return point, lower, upper


@dataclass
class ModelComparison:
    """
    Result of comparing multiple forecasting models.

    Attributes:
        model_names: Names of models compared
        mape_values: MAPE for each model
        rmse_values: RMSE for each model
        best_model: Name of best performing model
        rankings: Ranking by MAPE (1 = best)
    """
    model_names: List[str]
    mape_values: Dict[str, float]
    rmse_values: Dict[str, float]
    best_model: str
    rankings: Dict[str, int]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "model_names": self.model_names,
            "mape_values": {k: float(v) for k, v in self.mape_values.items()},
            "rmse_values": {k: float(v) for k, v in self.rmse_values.items()},
            "best_model": self.best_model,
            "rankings": self.rankings,
        }


def compare_models(
    actual: np.ndarray,
    predictions: Dict[str, np.ndarray],
) -> ModelComparison:
    """
    Compare multiple forecasting models.

    Args:
        actual: Actual values
        predictions: Dictionary mapping model name to predictions

    Returns:
        ModelComparison with rankings
    """
    from .evaluation_metrics import mape, rmse

    model_names = list(predictions.keys())
    mape_values = {}
    rmse_values = {}

    for name, pred in predictions.items():
        mape_values[name] = mape(actual, pred)
        rmse_values[name] = rmse(actual, pred)

    # Rank by MAPE
    sorted_models = sorted(mape_values.keys(), key=lambda x: mape_values[x])
    rankings = {name: i + 1 for i, name in enumerate(sorted_models)}

    best_model = sorted_models[0]

    return ModelComparison(
        model_names=model_names,
        mape_values=mape_values,
        rmse_values=rmse_values,
        best_model=best_model,
        rankings=rankings,
    )


def get_all_baseline_models() -> Dict[str, BaseForecaster]:
    """
    Get all available baseline models.

    Returns:
        Dictionary mapping model name to model instance
    """
    return {
        "Naive": NaiveForecaster(),
        "SeasonalNaive_24h": SeasonalNaiveForecaster(period=24),
        "SeasonalNaive_168h": SeasonalNaiveForecaster(period=168),
        "MovingAverage_24h": MovingAverageForecaster(window=24),
        "ExponentialSmoothing": ExponentialSmoothingForecaster(alpha=0.3),
        "ARIMA": ARIMAForecaster(order=(2, 1, 2)),
    }


# Alias for get_all_baseline_models
BASELINE_MODELS = {
    "Naive": NaiveForecaster,
    "SeasonalNaive_24h": lambda: SeasonalNaiveForecaster(period=24),
    "SeasonalNaive_168h": lambda: SeasonalNaiveForecaster(period=168),
    "MovingAverage_24h": lambda: MovingAverageForecaster(window=24),
    "ExponentialSmoothing": lambda: ExponentialSmoothingForecaster(alpha=0.3),
    "ARIMA": lambda: ARIMAForecaster(order=(2, 1, 2)),
    "Prophet": ProphetForecaster,
}
