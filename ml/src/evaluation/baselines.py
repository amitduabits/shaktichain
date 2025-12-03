"""Baseline forecasting models for SHAKTI-CHAIN."""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from abc import ABC, abstractmethod
import logging
import warnings

logger = logging.getLogger(__name__)


class BaselineModel(ABC):
    """Abstract base class for baseline forecasting models."""

    def __init__(self, name: str):
        self.name = name
        self.is_fitted = False

    @abstractmethod
    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "BaselineModel":
        """Fit the model.

        Args:
            y: Target time series with DatetimeIndex
            X: Optional exogenous features

        Returns:
            Self
        """
        pass

    @abstractmethod
    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Generate forecasts.

        Args:
            horizon: Number of steps to forecast
            X: Optional exogenous features for forecast period

        Returns:
            Array of predictions (horizon,)
        """
        pass

    def forecast(
        self,
        y: pd.Series,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Fit and forecast in one step.

        Args:
            y: Historical target series
            horizon: Number of steps to forecast
            X: Optional exogenous features

        Returns:
            Array of predictions
        """
        self.fit(y, X)
        return self.predict(horizon, X)


class NaiveModel(BaselineModel):
    """Naive forecasting model (yesterday same hour).

    Predicts using the value from 24 hours ago for each forecast step.
    """

    def __init__(self):
        super().__init__("Naive (Yesterday)")
        self.last_day = None

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "NaiveModel":
        """Fit by storing the last 24 hours of data.

        Args:
            y: Target time series with hourly frequency

        Returns:
            Self
        """
        if len(y) < 24:
            raise ValueError("Need at least 24 hours of data for Naive model")

        # Store last 24 hours
        self.last_day = y.iloc[-24:].values
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Predict using yesterday's values.

        Args:
            horizon: Number of hours to forecast

        Returns:
            Array of predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Repeat the last day pattern
        predictions = np.tile(self.last_day, (horizon // 24) + 1)[:horizon]
        return predictions


class SeasonalNaiveModel(BaselineModel):
    """Seasonal naive forecasting model (last week same hour).

    Predicts using the value from 168 hours (1 week) ago for each forecast step.
    """

    def __init__(self):
        super().__init__("Seasonal Naive (Last Week)")
        self.last_week = None

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "SeasonalNaiveModel":
        """Fit by storing the last week of data.

        Args:
            y: Target time series with hourly frequency

        Returns:
            Self
        """
        if len(y) < 168:
            raise ValueError("Need at least 168 hours (1 week) of data for Seasonal Naive model")

        # Store last week
        self.last_week = y.iloc[-168:].values
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Predict using last week's values.

        Args:
            horizon: Number of hours to forecast

        Returns:
            Array of predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Repeat the last week pattern
        predictions = np.tile(self.last_week, (horizon // 168) + 1)[:horizon]
        return predictions


class ARIMAModel(BaselineModel):
    """ARIMA forecasting model.

    Uses statsmodels ARIMA with automatic order selection or specified orders.

    Args:
        order: (p, d, q) order of the ARIMA model
        seasonal_order: (P, D, Q, s) seasonal order, s=24 for hourly data
        auto_order: Whether to use auto_arima for order selection
    """

    def __init__(
        self,
        order: Tuple[int, int, int] = (1, 1, 1),
        seasonal_order: Tuple[int, int, int, int] = (1, 0, 1, 24),
        auto_order: bool = False,
    ):
        super().__init__("ARIMA")
        self.order = order
        self.seasonal_order = seasonal_order
        self.auto_order = auto_order
        self.model = None
        self.fitted_model = None

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "ARIMAModel":
        """Fit ARIMA model.

        Args:
            y: Target time series
            X: Optional exogenous features (not used currently)

        Returns:
            Self
        """
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError:
            raise ImportError("statsmodels required for ARIMA. Install with: pip install statsmodels")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            if self.auto_order:
                try:
                    from pmdarima import auto_arima
                    auto_model = auto_arima(
                        y,
                        start_p=0, max_p=3,
                        start_q=0, max_q=3,
                        d=1, max_d=2,
                        seasonal=True, m=24,
                        start_P=0, max_P=2,
                        start_Q=0, max_Q=2,
                        D=1, max_D=1,
                        trace=False,
                        error_action='ignore',
                        suppress_warnings=True,
                        stepwise=True,
                        n_jobs=-1,
                    )
                    self.order = auto_model.order
                    self.seasonal_order = auto_model.seasonal_order
                    logger.info(f"Auto ARIMA selected order={self.order}, seasonal_order={self.seasonal_order}")
                except ImportError:
                    logger.warning("pmdarima not installed, using default orders")

            # Fit SARIMAX model
            self.model = SARIMAX(
                y,
                order=self.order,
                seasonal_order=self.seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            self.fitted_model = self.model.fit(disp=False)
            self.is_fitted = True

        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Generate ARIMA forecasts.

        Args:
            horizon: Number of steps to forecast

        Returns:
            Array of predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        forecast = self.fitted_model.forecast(steps=horizon)
        return forecast.values


class XGBoostModel(BaselineModel):
    """XGBoost forecasting model with feature engineering.

    Uses the same features as the TFT model for fair comparison.

    Args:
        lags: List of lag hours to use as features
        n_estimators: Number of boosting rounds
        max_depth: Maximum tree depth
        learning_rate: Boosting learning rate
    """

    def __init__(
        self,
        lags: List[int] = [1, 2, 3, 6, 12, 24, 48, 168],
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
    ):
        super().__init__("XGBoost")
        self.lags = lags
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.model = None
        self.feature_names = None
        self.last_values = None

    def _create_features(self, y: pd.Series) -> pd.DataFrame:
        """Create lag and time-based features.

        Args:
            y: Target time series with DatetimeIndex

        Returns:
            DataFrame with features
        """
        df = pd.DataFrame(index=y.index)

        # Lag features
        for lag in self.lags:
            df[f"lag_{lag}"] = y.shift(lag)

        # Time features
        df["hour"] = y.index.hour
        df["day_of_week"] = y.index.dayofweek
        df["month"] = y.index.month
        df["is_weekend"] = (y.index.dayofweek >= 5).astype(int)

        # Cyclical encoding
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

        # Rolling statistics
        df["rolling_mean_24"] = y.rolling(24).mean()
        df["rolling_std_24"] = y.rolling(24).std()
        df["rolling_mean_168"] = y.rolling(168).mean()

        return df

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "XGBoostModel":
        """Fit XGBoost model.

        Args:
            y: Target time series
            X: Optional additional features

        Returns:
            Self
        """
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost required. Install with: pip install xgboost")

        # Create features
        features = self._create_features(y)

        # Combine with external features if provided
        if X is not None:
            features = features.join(X, how="left")

        # Store feature names
        self.feature_names = features.columns.tolist()

        # Drop rows with NaN (from lag features)
        max_lag = max(self.lags)
        valid_idx = features.index[max_lag:]
        X_train = features.loc[valid_idx].dropna()
        y_train = y.loc[X_train.index]

        # Train XGBoost
        self.model = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        # Store last values for prediction
        self.last_values = y.iloc[-max(self.lags):].values
        self.last_index = y.index[-1]
        self.y_history = y.copy()

        self.is_fitted = True
        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Generate XGBoost forecasts.

        Args:
            horizon: Number of steps to forecast
            X: Optional additional features for forecast period

        Returns:
            Array of predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        predictions = []
        current_values = list(self.last_values)

        for h in range(horizon):
            # Create features for this step
            timestamp = self.last_index + pd.Timedelta(hours=h + 1)
            features = {}

            # Lag features
            for lag in self.lags:
                idx = -lag + h
                if idx < 0:
                    features[f"lag_{lag}"] = current_values[idx]
                else:
                    features[f"lag_{lag}"] = predictions[idx]

            # Time features
            features["hour"] = timestamp.hour
            features["day_of_week"] = timestamp.dayofweek
            features["month"] = timestamp.month
            features["is_weekend"] = int(timestamp.dayofweek >= 5)
            features["hour_sin"] = np.sin(2 * np.pi * timestamp.hour / 24)
            features["hour_cos"] = np.cos(2 * np.pi * timestamp.hour / 24)
            features["dow_sin"] = np.sin(2 * np.pi * timestamp.dayofweek / 7)
            features["dow_cos"] = np.cos(2 * np.pi * timestamp.dayofweek / 7)

            # Rolling statistics (approximate using available data)
            recent_24 = current_values[-24:] + predictions[-24:] if len(predictions) > 0 else current_values[-24:]
            recent_168 = current_values[-168:] + predictions if len(predictions) > 0 else current_values[-168:]
            features["rolling_mean_24"] = np.mean(recent_24[-24:])
            features["rolling_std_24"] = np.std(recent_24[-24:])
            features["rolling_mean_168"] = np.mean(recent_168[-168:])

            # Create DataFrame
            X_pred = pd.DataFrame([features])[self.feature_names]

            # Predict
            pred = self.model.predict(X_pred)[0]
            predictions.append(pred)

        return np.array(predictions)


class ProphetModel(BaselineModel):
    """Prophet forecasting model from Meta.

    Good for data with strong seasonality and holiday effects.

    Args:
        yearly_seasonality: Include yearly seasonality
        weekly_seasonality: Include weekly seasonality
        daily_seasonality: Include daily seasonality (important for hourly data)
        holidays: Optional DataFrame with holiday dates
    """

    def __init__(
        self,
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = True,
        holidays: Optional[pd.DataFrame] = None,
    ):
        super().__init__("Prophet")
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.holidays = holidays
        self.model = None

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "ProphetModel":
        """Fit Prophet model.

        Args:
            y: Target time series with DatetimeIndex
            X: Optional additional regressors

        Returns:
            Self
        """
        try:
            from prophet import Prophet
        except ImportError:
            raise ImportError("prophet required. Install with: pip install prophet")

        # Prepare data in Prophet format
        df = pd.DataFrame({
            "ds": y.index,
            "y": y.values,
        })

        # Initialize model
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            self.model = Prophet(
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
                holidays=self.holidays,
            )

            # Add regressors if provided
            if X is not None:
                for col in X.columns:
                    self.model.add_regressor(col)
                    df[col] = X[col].values

            # Fit
            self.model.fit(df)

        self.last_index = y.index[-1]
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Generate Prophet forecasts.

        Args:
            horizon: Number of steps to forecast
            X: Optional additional regressors for forecast period

        Returns:
            Array of predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Create future DataFrame
        future = self.model.make_future_dataframe(periods=horizon, freq="h")
        future = future.iloc[-horizon:]  # Keep only forecast period

        # Add regressors if provided
        if X is not None:
            for col in X.columns:
                future[col] = X[col].values[:horizon]

        # Predict
        forecast = self.model.predict(future)

        return forecast["yhat"].values


class PersistenceModel(BaselineModel):
    """Simple persistence model (last known value).

    Predicts the last known value for all horizons.
    """

    def __init__(self):
        super().__init__("Persistence")
        self.last_value = None

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "PersistenceModel":
        """Fit by storing the last value.

        Args:
            y: Target time series

        Returns:
            Self
        """
        self.last_value = y.iloc[-1]
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Predict using last known value.

        Args:
            horizon: Number of steps to forecast

        Returns:
            Array of predictions (all same value)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        return np.full(horizon, self.last_value)


class MovingAverageModel(BaselineModel):
    """Moving average forecasting model.

    Predicts using the average of the last N values.

    Args:
        window: Number of past values to average
    """

    def __init__(self, window: int = 24):
        super().__init__(f"Moving Average ({window}h)")
        self.window = window
        self.last_values = None

    def fit(self, y: pd.Series, X: Optional[pd.DataFrame] = None) -> "MovingAverageModel":
        """Fit by storing the last window values.

        Args:
            y: Target time series

        Returns:
            Self
        """
        if len(y) < self.window:
            raise ValueError(f"Need at least {self.window} values for Moving Average model")

        self.last_values = y.iloc[-self.window:].values
        self.is_fitted = True
        return self

    def predict(
        self,
        horizon: int,
        X: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Predict using moving average.

        Args:
            horizon: Number of steps to forecast

        Returns:
            Array of predictions
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Simple: use average of last window for all predictions
        avg = np.mean(self.last_values)
        return np.full(horizon, avg)


def get_all_baselines() -> Dict[str, BaselineModel]:
    """Get all baseline models.

    Returns:
        Dictionary mapping model names to model instances
    """
    return {
        "naive": NaiveModel(),
        "seasonal_naive": SeasonalNaiveModel(),
        "persistence": PersistenceModel(),
        "ma_24": MovingAverageModel(window=24),
        "ma_168": MovingAverageModel(window=168),
        "arima": ARIMAModel(),
        "xgboost": XGBoostModel(),
        "prophet": ProphetModel(),
    }


def get_simple_baselines() -> Dict[str, BaselineModel]:
    """Get simple baseline models (no external dependencies).

    Returns:
        Dictionary mapping model names to model instances
    """
    return {
        "naive": NaiveModel(),
        "seasonal_naive": SeasonalNaiveModel(),
        "persistence": PersistenceModel(),
        "ma_24": MovingAverageModel(window=24),
        "ma_168": MovingAverageModel(window=168),
    }
