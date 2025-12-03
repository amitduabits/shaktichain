"""Custom metric collectors for SHAKTI-CHAIN ML.

Collectors gather metrics from various sources:
- Prediction tracking and accuracy
- Feature pipeline monitoring
- Drift detection
- Performance tracking
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

from .metrics import get_metrics

logger = logging.getLogger(__name__)


@dataclass
class PredictionRecord:
    """Record of a prediction for tracking."""

    model: str
    timestamp: datetime
    prediction: float
    actual: Optional[float] = None
    features: Optional[Dict[str, float]] = None
    confidence: Optional[float] = None
    horizon: Optional[str] = None
    city: Optional[str] = None


class PredictionCollector:
    """Collect and track predictions for accuracy monitoring.

    Stores recent predictions and computes rolling accuracy metrics
    when actuals become available.

    Example:
        >>> collector = PredictionCollector(window_size=1000)
        >>> collector.record_prediction("load_forecast", 100.5, horizon="1h")
        >>> collector.record_actual("load_forecast", timestamp, 102.3)
        >>> accuracy = collector.get_accuracy("load_forecast")
    """

    def __init__(
        self,
        window_size: int = 10000,
        max_staleness_hours: int = 48,
    ):
        """Initialize collector.

        Args:
            window_size: Maximum predictions to keep in memory
            max_staleness_hours: Drop predictions older than this
        """
        self.window_size = window_size
        self.max_staleness = timedelta(hours=max_staleness_hours)

        # Store predictions by model
        self._predictions: Dict[str, Deque[PredictionRecord]] = {}

        # Index for fast lookup by timestamp
        self._by_timestamp: Dict[str, Dict[datetime, PredictionRecord]] = {}

        # Cached accuracy metrics
        self._accuracy_cache: Dict[str, Dict[str, float]] = {}
        self._cache_timestamp: Dict[str, datetime] = {}

    def record_prediction(
        self,
        model: str,
        prediction: float,
        timestamp: Optional[datetime] = None,
        confidence: Optional[float] = None,
        horizon: Optional[str] = None,
        city: Optional[str] = None,
        features: Optional[Dict[str, float]] = None,
    ):
        """Record a new prediction."""
        timestamp = timestamp or datetime.now()

        record = PredictionRecord(
            model=model,
            timestamp=timestamp,
            prediction=prediction,
            confidence=confidence,
            horizon=horizon,
            city=city,
            features=features,
        )

        # Initialize storage if needed
        if model not in self._predictions:
            self._predictions[model] = deque(maxlen=self.window_size)
            self._by_timestamp[model] = {}

        # Store
        self._predictions[model].append(record)
        self._by_timestamp[model][timestamp] = record

        # Update metrics
        metrics = get_metrics()
        metrics.model.track_prediction(
            model=model,
            value=prediction,
            confidence=confidence,
            output_type="point",
        )

        # Cleanup old entries
        self._cleanup(model)

    def record_actual(
        self,
        model: str,
        timestamp: datetime,
        actual: float,
    ) -> bool:
        """Record actual value for a prediction.

        Returns:
            True if matching prediction found
        """
        if model not in self._by_timestamp:
            return False

        # Find closest prediction
        record = self._by_timestamp[model].get(timestamp)

        if record is None:
            # Try to find within tolerance
            tolerance = timedelta(minutes=5)
            for ts, rec in self._by_timestamp[model].items():
                if abs(ts - timestamp) <= tolerance and rec.actual is None:
                    record = rec
                    break

        if record is None:
            return False

        record.actual = actual

        # Update accuracy metrics
        error = abs(record.prediction - actual)
        mape = error / (abs(actual) + 1e-6)

        metrics = get_metrics()
        metrics.business.track_forecast_error(
            model=model,
            horizon=record.horizon or "unknown",
            city=record.city or "unknown",
            error=mape,
        )

        # Invalidate cache
        self._accuracy_cache.pop(model, None)

        return True

    def get_accuracy(
        self,
        model: str,
        metric: str = "mape",
        window_hours: int = 24,
    ) -> Optional[float]:
        """Get rolling accuracy for a model.

        Args:
            model: Model name
            metric: Accuracy metric ("mape", "rmse", "mae")
            window_hours: Window for rolling calculation

        Returns:
            Accuracy metric value
        """
        if model not in self._predictions:
            return None

        cutoff = datetime.now() - timedelta(hours=window_hours)

        # Filter records with actuals
        records = [
            r for r in self._predictions[model]
            if r.actual is not None and r.timestamp >= cutoff
        ]

        if not records:
            return None

        predictions = np.array([r.prediction for r in records])
        actuals = np.array([r.actual for r in records])

        if metric == "mape":
            return float(np.mean(np.abs(predictions - actuals) / (np.abs(actuals) + 1e-6)))
        elif metric == "rmse":
            return float(np.sqrt(np.mean((predictions - actuals) ** 2)))
        elif metric == "mae":
            return float(np.mean(np.abs(predictions - actuals)))
        else:
            raise ValueError(f"Unknown metric: {metric}")

    def get_statistics(self, model: str) -> Dict[str, Any]:
        """Get prediction statistics for a model."""
        if model not in self._predictions:
            return {}

        records = list(self._predictions[model])
        if not records:
            return {}

        predictions = np.array([r.prediction for r in records])
        with_actuals = [r for r in records if r.actual is not None]

        stats = {
            "total_predictions": len(records),
            "with_actuals": len(with_actuals),
            "prediction_mean": float(np.mean(predictions)),
            "prediction_std": float(np.std(predictions)),
            "prediction_min": float(np.min(predictions)),
            "prediction_max": float(np.max(predictions)),
        }

        if with_actuals:
            stats.update({
                "mape_24h": self.get_accuracy(model, "mape", 24),
                "rmse_24h": self.get_accuracy(model, "rmse", 24),
                "mae_24h": self.get_accuracy(model, "mae", 24),
            })

        return stats

    def _cleanup(self, model: str):
        """Remove stale predictions."""
        cutoff = datetime.now() - self.max_staleness

        # Remove from deque (will auto-truncate due to maxlen)
        # Remove from timestamp index
        stale_keys = [
            ts for ts in self._by_timestamp[model]
            if ts < cutoff
        ]
        for ts in stale_keys:
            del self._by_timestamp[model][ts]


@dataclass
class FeatureStats:
    """Statistics for a feature."""

    name: str
    last_updated: datetime
    mean: float
    std: float
    min_val: float
    max_val: float
    missing_rate: float
    sample_count: int


class FeatureCollector:
    """Collect and monitor feature statistics.

    Tracks feature values, staleness, and missing rates.

    Example:
        >>> collector = FeatureCollector()
        >>> collector.update("temperature", [25.5, 26.1, 24.8])
        >>> stats = collector.get_stats("temperature")
        >>> staleness = collector.get_staleness("temperature")
    """

    def __init__(self, window_size: int = 1000):
        """Initialize collector.

        Args:
            window_size: Number of values to keep per feature
        """
        self.window_size = window_size
        self._values: Dict[str, Deque[float]] = {}
        self._last_updated: Dict[str, datetime] = {}
        self._missing_counts: Dict[str, int] = {}
        self._total_counts: Dict[str, int] = {}

    def update(
        self,
        feature_name: str,
        values: List[float],
        missing_count: int = 0,
    ):
        """Update feature with new values.

        Args:
            feature_name: Feature name
            values: New feature values
            missing_count: Count of missing values in batch
        """
        if feature_name not in self._values:
            self._values[feature_name] = deque(maxlen=self.window_size)
            self._missing_counts[feature_name] = 0
            self._total_counts[feature_name] = 0

        # Add values
        for v in values:
            self._values[feature_name].append(v)

        # Update counts
        self._total_counts[feature_name] += len(values) + missing_count
        self._missing_counts[feature_name] += missing_count

        # Update timestamp
        self._last_updated[feature_name] = datetime.now()

        # Update metrics
        if values:
            arr = np.array(list(self._values[feature_name]))
            metrics = get_metrics()
            metrics.feature.update_feature_stats(
                feature_name=feature_name,
                mean=float(np.mean(arr)),
                std=float(np.std(arr)),
                min_val=float(np.min(arr)),
                max_val=float(np.max(arr)),
            )

            # Check bounds
            self._check_bounds(feature_name, values)

    def _check_bounds(self, feature_name: str, values: List[float]):
        """Check for out of bounds values."""
        # Define expected bounds (could be configurable)
        bounds = {
            "temperature": (-10, 55),
            "humidity": (0, 100),
            "load": (0, 50000),
            "price": (0, 50),
            "soc": (0, 1),
            "grid_frequency": (49, 51),
        }

        if feature_name not in bounds:
            return

        low, high = bounds[feature_name]
        metrics = get_metrics()

        for v in values:
            if v < low:
                metrics.feature.track_oob(feature_name, "low")
            elif v > high:
                metrics.feature.track_oob(feature_name, "high")

    def get_stats(self, feature_name: str) -> Optional[FeatureStats]:
        """Get statistics for a feature."""
        if feature_name not in self._values:
            return None

        values = list(self._values[feature_name])
        if not values:
            return None

        arr = np.array(values)
        total = self._total_counts.get(feature_name, len(values))
        missing = self._missing_counts.get(feature_name, 0)

        return FeatureStats(
            name=feature_name,
            last_updated=self._last_updated.get(feature_name, datetime.now()),
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min_val=float(np.min(arr)),
            max_val=float(np.max(arr)),
            missing_rate=missing / total if total > 0 else 0.0,
            sample_count=len(values),
        )

    def get_staleness(self, feature_name: str) -> float:
        """Get staleness in seconds for a feature."""
        if feature_name not in self._last_updated:
            return float("inf")

        delta = datetime.now() - self._last_updated[feature_name]
        staleness = delta.total_seconds()

        # Update metric
        metrics = get_metrics()
        metrics.feature.update_staleness(feature_name, staleness)

        return staleness

    def get_all_stats(self) -> Dict[str, FeatureStats]:
        """Get statistics for all features."""
        return {
            name: stats
            for name in self._values
            if (stats := self.get_stats(name)) is not None
        }


class DriftCollector:
    """Collect and monitor feature drift.

    Compares recent feature distributions to reference distributions
    to detect data drift.

    Example:
        >>> collector = DriftCollector()
        >>> collector.set_reference("temperature", reference_data)
        >>> collector.update("temperature", new_data)
        >>> drift = collector.get_drift("temperature")
    """

    def __init__(
        self,
        window_size: int = 1000,
        drift_threshold: float = 0.1,
    ):
        """Initialize collector.

        Args:
            window_size: Window for current distribution
            drift_threshold: Threshold for drift alerts
        """
        self.window_size = window_size
        self.drift_threshold = drift_threshold

        self._reference: Dict[str, np.ndarray] = {}
        self._current: Dict[str, Deque[float]] = {}
        self._drift_scores: Dict[str, Dict[str, float]] = {}

    def set_reference(self, feature_name: str, data: np.ndarray):
        """Set reference distribution for a feature.

        Args:
            feature_name: Feature name
            data: Reference data array
        """
        self._reference[feature_name] = np.array(data)

        if feature_name not in self._current:
            self._current[feature_name] = deque(maxlen=self.window_size)

    def update(self, feature_name: str, values: List[float]):
        """Update current distribution and compute drift.

        Args:
            feature_name: Feature name
            values: New values
        """
        if feature_name not in self._current:
            self._current[feature_name] = deque(maxlen=self.window_size)

        for v in values:
            self._current[feature_name].append(v)

        # Compute drift if we have reference and enough data
        if (
            feature_name in self._reference and
            len(self._current[feature_name]) >= 100
        ):
            self._compute_drift(feature_name)

    def _compute_drift(self, feature_name: str):
        """Compute drift scores for a feature."""
        reference = self._reference[feature_name]
        current = np.array(list(self._current[feature_name]))

        scores = {}

        # KS test (Kolmogorov-Smirnov)
        try:
            from scipy import stats
            ks_stat, _ = stats.ks_2samp(reference, current)
            scores["ks"] = float(ks_stat)
        except ImportError:
            scores["ks"] = 0.0

        # PSI (Population Stability Index)
        scores["psi"] = self._compute_psi(reference, current)

        # Wasserstein distance (normalized)
        try:
            from scipy import stats
            w_dist = stats.wasserstein_distance(reference, current)
            # Normalize by reference std
            ref_std = np.std(reference)
            scores["wasserstein"] = float(w_dist / (ref_std + 1e-6))
        except ImportError:
            scores["wasserstein"] = 0.0

        self._drift_scores[feature_name] = scores

        # Update metrics
        metrics = get_metrics()
        for drift_type, score in scores.items():
            metrics.feature.update_drift(feature_name, score, drift_type)

    def _compute_psi(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        bins: int = 10,
    ) -> float:
        """Compute Population Stability Index."""
        # Create bins from reference
        _, bin_edges = np.histogram(reference, bins=bins)

        # Get proportions
        ref_counts, _ = np.histogram(reference, bins=bin_edges)
        cur_counts, _ = np.histogram(current, bins=bin_edges)

        ref_props = ref_counts / len(reference)
        cur_props = cur_counts / len(current)

        # Avoid division by zero
        ref_props = np.clip(ref_props, 0.001, None)
        cur_props = np.clip(cur_props, 0.001, None)

        # PSI formula
        psi = np.sum((cur_props - ref_props) * np.log(cur_props / ref_props))

        return float(psi)

    def get_drift(self, feature_name: str) -> Optional[Dict[str, float]]:
        """Get drift scores for a feature."""
        return self._drift_scores.get(feature_name)

    def is_drifting(self, feature_name: str) -> bool:
        """Check if feature is drifting."""
        scores = self.get_drift(feature_name)
        if not scores:
            return False

        # Check if any score exceeds threshold
        return any(
            score > self.drift_threshold
            for score in scores.values()
        )

    def get_all_drift(self) -> Dict[str, Dict[str, float]]:
        """Get drift scores for all features."""
        return dict(self._drift_scores)


class PerformanceCollector:
    """Collect and aggregate performance metrics over time.

    Tracks latency, throughput, and error rates with time-series
    aggregation.

    Example:
        >>> collector = PerformanceCollector()
        >>> collector.record_request("/trading/action", 15.5, success=True)
        >>> stats = collector.get_stats("/trading/action", window_minutes=5)
    """

    def __init__(
        self,
        window_minutes: int = 60,
        bucket_seconds: int = 60,
    ):
        """Initialize collector.

        Args:
            window_minutes: Total window to keep
            bucket_seconds: Aggregation bucket size
        """
        self.window_minutes = window_minutes
        self.bucket_seconds = bucket_seconds
        self.max_buckets = (window_minutes * 60) // bucket_seconds

        # Buckets keyed by (endpoint, bucket_timestamp)
        self._buckets: Dict[Tuple[str, int], Dict[str, Any]] = {}

    def record_request(
        self,
        endpoint: str,
        latency_ms: float,
        success: bool = True,
    ):
        """Record a request.

        Args:
            endpoint: Endpoint name
            latency_ms: Latency in milliseconds
            success: Whether request succeeded
        """
        bucket_ts = int(time.time()) // self.bucket_seconds * self.bucket_seconds
        key = (endpoint, bucket_ts)

        if key not in self._buckets:
            self._buckets[key] = {
                "count": 0,
                "success": 0,
                "error": 0,
                "latencies": [],
            }

        bucket = self._buckets[key]
        bucket["count"] += 1
        bucket["latencies"].append(latency_ms)

        if success:
            bucket["success"] += 1
        else:
            bucket["error"] += 1

        # Cleanup old buckets
        self._cleanup()

    def _cleanup(self):
        """Remove old buckets."""
        cutoff = int(time.time()) - (self.window_minutes * 60)

        stale_keys = [
            key for key in self._buckets
            if key[1] < cutoff
        ]
        for key in stale_keys:
            del self._buckets[key]

    def get_stats(
        self,
        endpoint: str,
        window_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get aggregated stats for an endpoint.

        Args:
            endpoint: Endpoint name
            window_minutes: Window for aggregation (default: all)

        Returns:
            Aggregated statistics
        """
        window_minutes = window_minutes or self.window_minutes
        cutoff = int(time.time()) - (window_minutes * 60)

        # Collect relevant buckets
        all_latencies = []
        total_count = 0
        total_success = 0
        total_error = 0

        for (ep, bucket_ts), bucket in self._buckets.items():
            if ep == endpoint and bucket_ts >= cutoff:
                all_latencies.extend(bucket["latencies"])
                total_count += bucket["count"]
                total_success += bucket["success"]
                total_error += bucket["error"]

        if not all_latencies:
            return {}

        latencies = np.array(all_latencies)

        return {
            "count": total_count,
            "success_count": total_success,
            "error_count": total_error,
            "error_rate": total_error / total_count if total_count > 0 else 0.0,
            "rps": total_count / (window_minutes * 60),
            "latency_mean_ms": float(np.mean(latencies)),
            "latency_std_ms": float(np.std(latencies)),
            "latency_p50_ms": float(np.percentile(latencies, 50)),
            "latency_p95_ms": float(np.percentile(latencies, 95)),
            "latency_p99_ms": float(np.percentile(latencies, 99)),
            "latency_min_ms": float(np.min(latencies)),
            "latency_max_ms": float(np.max(latencies)),
        }

    def get_time_series(
        self,
        endpoint: str,
        metric: str = "p99",
        window_minutes: Optional[int] = None,
    ) -> List[Tuple[int, float]]:
        """Get time series data for an endpoint metric.

        Args:
            endpoint: Endpoint name
            metric: Metric to extract ("count", "error_rate", "p50", "p95", "p99")
            window_minutes: Window for data

        Returns:
            List of (timestamp, value) tuples
        """
        window_minutes = window_minutes or self.window_minutes
        cutoff = int(time.time()) - (window_minutes * 60)

        series = []

        for (ep, bucket_ts), bucket in sorted(self._buckets.items()):
            if ep == endpoint and bucket_ts >= cutoff:
                latencies = np.array(bucket["latencies"]) if bucket["latencies"] else np.array([0])

                if metric == "count":
                    value = bucket["count"]
                elif metric == "error_rate":
                    value = bucket["error"] / bucket["count"] if bucket["count"] > 0 else 0
                elif metric == "p50":
                    value = float(np.percentile(latencies, 50))
                elif metric == "p95":
                    value = float(np.percentile(latencies, 95))
                elif metric == "p99":
                    value = float(np.percentile(latencies, 99))
                else:
                    value = float(np.mean(latencies))

                series.append((bucket_ts, value))

        return series
