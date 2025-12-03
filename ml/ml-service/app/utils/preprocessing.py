"""Preprocessing utilities for ML Service.

Provides:
- Feature normalization
- Input validation
- Feature engineering
- Missing value handling
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class FeatureNormalizer:
    """Normalize features for model input."""

    def __init__(self, method: str = "standard"):
        """Initialize normalizer.

        Args:
            method: Normalization method ('standard', 'minmax', 'robust')
        """
        self.method = method
        self.params: Dict[str, Dict[str, float]] = {}

    def fit(self, feature_name: str, values: np.ndarray):
        """Fit normalizer to data.

        Args:
            feature_name: Feature name
            values: Feature values
        """
        if self.method == "standard":
            self.params[feature_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values) + 1e-8),
            }
        elif self.method == "minmax":
            self.params[feature_name] = {
                "min": float(np.min(values)),
                "max": float(np.max(values) + 1e-8),
            }
        elif self.method == "robust":
            self.params[feature_name] = {
                "median": float(np.median(values)),
                "iqr": float(np.percentile(values, 75) - np.percentile(values, 25) + 1e-8),
            }

    def transform(self, feature_name: str, value: float) -> float:
        """Transform a single value.

        Args:
            feature_name: Feature name
            value: Value to transform

        Returns:
            Normalized value
        """
        if feature_name not in self.params:
            return value

        params = self.params[feature_name]

        if self.method == "standard":
            return (value - params["mean"]) / params["std"]
        elif self.method == "minmax":
            return (value - params["min"]) / (params["max"] - params["min"])
        elif self.method == "robust":
            return (value - params["median"]) / params["iqr"]

        return value

    def inverse_transform(self, feature_name: str, value: float) -> float:
        """Inverse transform a normalized value.

        Args:
            feature_name: Feature name
            value: Normalized value

        Returns:
            Original scale value
        """
        if feature_name not in self.params:
            return value

        params = self.params[feature_name]

        if self.method == "standard":
            return value * params["std"] + params["mean"]
        elif self.method == "minmax":
            return value * (params["max"] - params["min"]) + params["min"]
        elif self.method == "robust":
            return value * params["iqr"] + params["median"]

        return value


class TimeFeatureEncoder:
    """Encode datetime features."""

    @staticmethod
    def encode_cyclical(value: float, period: float) -> Tuple[float, float]:
        """Encode value as cyclical features (sin, cos).

        Args:
            value: Value to encode
            period: Period of the cycle

        Returns:
            (sin_component, cos_component)
        """
        angle = 2 * np.pi * value / period
        return float(np.sin(angle)), float(np.cos(angle))

    @staticmethod
    def encode_datetime(dt: datetime) -> Dict[str, float]:
        """Encode datetime as multiple features.

        Args:
            dt: Datetime to encode

        Returns:
            Dictionary of encoded features
        """
        hour_sin, hour_cos = TimeFeatureEncoder.encode_cyclical(dt.hour, 24)
        dow_sin, dow_cos = TimeFeatureEncoder.encode_cyclical(dt.weekday(), 7)
        month_sin, month_cos = TimeFeatureEncoder.encode_cyclical(dt.month - 1, 12)
        day_sin, day_cos = TimeFeatureEncoder.encode_cyclical(dt.day - 1, 31)

        return {
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "dow_sin": dow_sin,
            "dow_cos": dow_cos,
            "month_sin": month_sin,
            "month_cos": month_cos,
            "day_sin": day_sin,
            "day_cos": day_cos,
            "is_weekend": float(dt.weekday() >= 5),
            "is_morning_peak": float(6 <= dt.hour <= 10),
            "is_evening_peak": float(17 <= dt.hour <= 21),
            "is_night": float(dt.hour <= 6 or dt.hour >= 22),
        }


class InputValidator:
    """Validate model inputs."""

    @staticmethod
    def validate_numeric(
        value: Any,
        name: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> float:
        """Validate numeric input.

        Args:
            value: Value to validate
            name: Parameter name for error messages
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Validated float value

        Raises:
            ValueError: If validation fails
        """
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be numeric, got {type(value)}")

        if np.isnan(val) or np.isinf(val):
            raise ValueError(f"{name} must be finite, got {val}")

        if min_val is not None and val < min_val:
            raise ValueError(f"{name} must be >= {min_val}, got {val}")

        if max_val is not None and val > max_val:
            raise ValueError(f"{name} must be <= {max_val}, got {val}")

        return val

    @staticmethod
    def validate_array(
        values: Any,
        name: str,
        expected_length: Optional[int] = None,
        min_length: int = 1,
    ) -> np.ndarray:
        """Validate array input.

        Args:
            values: Values to validate
            name: Parameter name for error messages
            expected_length: Expected exact length
            min_length: Minimum length

        Returns:
            Validated numpy array
        """
        try:
            arr = np.array(values, dtype=np.float32)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be array-like")

        if arr.ndim != 1:
            arr = arr.flatten()

        if len(arr) < min_length:
            raise ValueError(f"{name} must have at least {min_length} elements")

        if expected_length and len(arr) != expected_length:
            raise ValueError(f"{name} must have exactly {expected_length} elements")

        if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
            raise ValueError(f"{name} contains NaN or Inf values")

        return arr

    @staticmethod
    def validate_datetime(value: Any, name: str) -> datetime:
        """Validate datetime input.

        Args:
            value: Value to validate
            name: Parameter name

        Returns:
            Validated datetime
        """
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"{name} must be valid ISO datetime string")

        raise ValueError(f"{name} must be datetime or ISO string")


class MissingValueHandler:
    """Handle missing values in inputs."""

    def __init__(self, strategy: str = "mean"):
        """Initialize handler.

        Args:
            strategy: Imputation strategy ('mean', 'median', 'zero', 'forward')
        """
        self.strategy = strategy
        self.fill_values: Dict[str, float] = {}

    def fit(self, feature_name: str, values: np.ndarray):
        """Compute fill value from training data.

        Args:
            feature_name: Feature name
            values: Training values (may contain NaN)
        """
        valid_values = values[~np.isnan(values)]

        if len(valid_values) == 0:
            self.fill_values[feature_name] = 0.0
            return

        if self.strategy == "mean":
            self.fill_values[feature_name] = float(np.mean(valid_values))
        elif self.strategy == "median":
            self.fill_values[feature_name] = float(np.median(valid_values))
        elif self.strategy == "zero":
            self.fill_values[feature_name] = 0.0
        else:
            self.fill_values[feature_name] = float(valid_values[-1])

    def fill(self, feature_name: str, value: Optional[float]) -> float:
        """Fill missing value.

        Args:
            feature_name: Feature name
            value: Value (may be None or NaN)

        Returns:
            Filled value
        """
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return self.fill_values.get(feature_name, 0.0)
        return value


class FeaturePipeline:
    """Complete feature preprocessing pipeline."""

    def __init__(self):
        """Initialize pipeline."""
        self.normalizer = FeatureNormalizer(method="standard")
        self.time_encoder = TimeFeatureEncoder()
        self.validator = InputValidator()
        self.missing_handler = MissingValueHandler(strategy="mean")

    def preprocess_forecast_input(
        self,
        timestamp: datetime,
        horizon_hours: int,
        city: str,
        historical_load: Optional[List[float]] = None,
    ) -> np.ndarray:
        """Preprocess forecast input.

        Args:
            timestamp: Start timestamp
            horizon_hours: Forecast horizon
            city: City name
            historical_load: Historical load values

        Returns:
            Preprocessed feature array
        """
        # Validate inputs
        timestamp = self.validator.validate_datetime(timestamp, "timestamp")
        horizon_hours = int(self.validator.validate_numeric(
            horizon_hours, "horizon_hours", min_val=1, max_val=168
        ))

        features = []

        for h in range(horizon_hours):
            t = timestamp + timedelta(hours=h)
            time_features = self.time_encoder.encode_datetime(t)

            # City encoding (simplified one-hot)
            city_map = {'delhi': 0, 'mumbai': 1, 'bangalore': 2, 'chennai': 3, 'kolkata': 4, 'hyderabad': 5}
            city_idx = city_map.get(city.lower(), 0)

            feature_vector = [
                time_features["hour_sin"],
                time_features["hour_cos"],
                time_features["dow_sin"],
                time_features["dow_cos"],
                time_features["month_sin"],
                time_features["month_cos"],
                time_features["is_weekend"],
                time_features["is_morning_peak"],
                time_features["is_evening_peak"],
                city_idx / 5,  # Normalized city index
            ]

            # Add historical lag features if available
            if historical_load and len(historical_load) >= 24:
                # Last 24 hours as features
                lag_features = [
                    historical_load[-24] / 1000,  # Normalize
                    historical_load[-12] / 1000,
                    historical_load[-1] / 1000,
                    np.mean(historical_load[-24:]) / 1000,
                ]
                feature_vector.extend(lag_features)

            features.append(feature_vector)

        return np.array(features, dtype=np.float32)

    def preprocess_trading_input(
        self,
        battery_soc: float,
        battery_capacity: float,
        current_price: float,
        price_forecast: List[float],
        timestamp: datetime,
    ) -> np.ndarray:
        """Preprocess trading agent input.

        Args:
            battery_soc: State of charge (0-1)
            battery_capacity: Battery capacity kWh
            current_price: Current price INR/kWh
            price_forecast: Future price predictions
            timestamp: Current timestamp

        Returns:
            Preprocessed feature array
        """
        # Validate
        battery_soc = self.validator.validate_numeric(
            battery_soc, "battery_soc", min_val=0, max_val=1
        )
        current_price = self.validator.validate_numeric(
            current_price, "current_price", min_val=0
        )

        # Time features
        time_features = self.time_encoder.encode_datetime(timestamp)

        # Price features
        if price_forecast:
            price_forecast = list(price_forecast)[:24]  # Limit to 24 hours
            while len(price_forecast) < 24:
                price_forecast.append(price_forecast[-1] if price_forecast else current_price)
        else:
            price_forecast = [current_price] * 24

        price_arr = np.array(price_forecast)
        price_mean = np.mean(price_arr)
        price_std = np.std(price_arr) + 1e-8
        price_max = np.max(price_arr)
        price_min = np.min(price_arr)

        features = [
            # Battery state
            battery_soc,
            battery_capacity / 100,  # Normalize

            # Current price (normalized)
            current_price / 10,
            (current_price - price_mean) / price_std,
            (current_price - price_min) / (price_max - price_min + 1e-8),

            # Price statistics
            price_mean / 10,
            price_std / 10,
            (price_max - price_min) / 10,

            # Time features
            time_features["hour_sin"],
            time_features["hour_cos"],
            time_features["dow_sin"],
            time_features["dow_cos"],
            time_features["is_weekend"],
            time_features["is_morning_peak"],
            time_features["is_evening_peak"],
        ]

        # Add price forecast (normalized)
        features.extend([p / 10 for p in price_forecast[:12]])

        return np.array(features, dtype=np.float32)

    def preprocess_anomaly_input(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Preprocess anomaly detection input.

        Args:
            entity_type: Type of entity ('trade', 'delivery', 'account')
            entity_data: Entity data dictionary
            context: Optional context data

        Returns:
            Preprocessed feature array
        """
        features = []

        if entity_type == "trade":
            price = self.missing_handler.fill("price", entity_data.get("price"))
            quantity = self.missing_handler.fill("quantity", entity_data.get("quantity"))

            features.extend([
                price / 10,
                quantity / 100,
                entity_data.get("energy_kwh", quantity * 10) / 1000,
            ])

            # Time features
            timestamp = entity_data.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                time_features = self.time_encoder.encode_datetime(timestamp)
                features.extend([
                    time_features["hour_sin"],
                    time_features["hour_cos"],
                    time_features["is_night"],
                ])
            else:
                features.extend([0, 0, 0])

        elif entity_type == "delivery":
            claimed = self.missing_handler.fill("claimed_kwh", entity_data.get("claimed_kwh"))
            actual = self.missing_handler.fill("actual_kwh", entity_data.get("actual_kwh", claimed))

            features.extend([
                claimed / 100,
                actual / 100,
                abs(claimed - actual) / (claimed + 1e-8),
            ])

        elif entity_type == "account":
            features.extend([
                entity_data.get("reputation", 0.5),
                entity_data.get("total_trades", 0) / 100,
                entity_data.get("total_volume", 0) / 10000,
            ])

        # Context features
        if context:
            features.extend([
                context.get("account_age_days", 30) / 365,
                context.get("avg_trade_size", 50) / 100,
                context.get("trade_frequency", 1) / 10,
            ])
        else:
            features.extend([0.5, 0.5, 0.5])

        # Pad to fixed size
        while len(features) < 20:
            features.append(0)

        return np.array(features[:20], dtype=np.float32)
