"""Prometheus metrics for SHAKTI-CHAIN ML service.

Metrics categories:
1. Request metrics - API performance
2. Model metrics - Prediction tracking
3. Feature metrics - Data quality
4. Business metrics - Trading performance
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional Prometheus import
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        Summary,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
        multiprocess,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available. Metrics disabled.")


# Default buckets for latency histograms
LATENCY_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3,
    0.4, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0
)

# Buckets for prediction values
PREDICTION_BUCKETS = (
    0, 10, 25, 50, 75, 100, 150, 200, 300, 500, 1000
)


class RequestMetrics:
    """Request-level metrics for API endpoints."""

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        if not PROMETHEUS_AVAILABLE:
            return

        self.registry = registry or REGISTRY

        # Request counter
        self.request_total = Counter(
            "ml_request_total",
            "Total number of ML requests",
            ["endpoint", "method", "status"],
            registry=self.registry,
        )

        # Request latency histogram
        self.request_latency = Histogram(
            "ml_request_latency_seconds",
            "Request latency in seconds",
            ["endpoint"],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        # In-progress requests gauge
        self.requests_in_progress = Gauge(
            "ml_requests_in_progress",
            "Number of requests currently being processed",
            ["endpoint"],
            registry=self.registry,
        )

        # Request size
        self.request_size = Histogram(
            "ml_request_size_bytes",
            "Request payload size in bytes",
            ["endpoint"],
            buckets=(100, 500, 1000, 5000, 10000, 50000, 100000),
            registry=self.registry,
        )

        # Response size
        self.response_size = Histogram(
            "ml_response_size_bytes",
            "Response payload size in bytes",
            ["endpoint"],
            buckets=(100, 500, 1000, 5000, 10000, 50000, 100000),
            registry=self.registry,
        )

    def track_request(
        self,
        endpoint: str,
        method: str = "POST",
        status: str = "success",
        latency: float = 0.0,
        request_size: int = 0,
        response_size: int = 0,
    ):
        """Record a completed request."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.request_total.labels(
            endpoint=endpoint,
            method=method,
            status=status
        ).inc()

        self.request_latency.labels(endpoint=endpoint).observe(latency)

        if request_size > 0:
            self.request_size.labels(endpoint=endpoint).observe(request_size)
        if response_size > 0:
            self.response_size.labels(endpoint=endpoint).observe(response_size)

    @contextmanager
    def track_request_context(self, endpoint: str):
        """Context manager for tracking request lifecycle."""
        if not PROMETHEUS_AVAILABLE:
            yield
            return

        self.requests_in_progress.labels(endpoint=endpoint).inc()
        start_time = time.perf_counter()

        try:
            yield
            status = "success"
        except Exception:
            status = "error"
            raise
        finally:
            latency = time.perf_counter() - start_time
            self.requests_in_progress.labels(endpoint=endpoint).dec()
            self.request_total.labels(
                endpoint=endpoint,
                method="POST",
                status=status
            ).inc()
            self.request_latency.labels(endpoint=endpoint).observe(latency)


class ModelMetrics:
    """Model-level metrics for predictions and performance."""

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        if not PROMETHEUS_AVAILABLE:
            return

        self.registry = registry or REGISTRY

        # Prediction value distribution
        self.prediction_value = Histogram(
            "ml_prediction_value",
            "Distribution of prediction values",
            ["model", "output_type"],
            buckets=PREDICTION_BUCKETS,
            registry=self.registry,
        )

        # Prediction confidence
        self.prediction_confidence = Histogram(
            "ml_prediction_confidence",
            "Distribution of prediction confidence scores",
            ["model"],
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99),
            registry=self.registry,
        )

        # Inference latency per model
        self.inference_latency = Histogram(
            "ml_inference_latency_seconds",
            "Model inference latency in seconds",
            ["model", "backend"],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        # Model version info
        self.model_info = Info(
            "ml_model",
            "Model metadata",
            ["model"],
            registry=self.registry,
        )

        # Model last updated timestamp
        self.model_last_updated = Gauge(
            "ml_model_last_updated_timestamp",
            "Timestamp when model was last updated",
            ["model"],
            registry=self.registry,
        )

        # Batch size distribution
        self.batch_size = Histogram(
            "ml_batch_size",
            "Distribution of inference batch sizes",
            ["model"],
            buckets=(1, 2, 4, 8, 16, 32, 64, 128),
            registry=self.registry,
        )

        # Cache metrics
        self.cache_hits = Counter(
            "ml_cache_hits_total",
            "Total number of cache hits",
            ["model"],
            registry=self.registry,
        )

        self.cache_misses = Counter(
            "ml_cache_misses_total",
            "Total number of cache misses",
            ["model"],
            registry=self.registry,
        )

        # Prediction errors
        self.prediction_errors = Counter(
            "ml_prediction_errors_total",
            "Total number of prediction errors",
            ["model", "error_type"],
            registry=self.registry,
        )

    def track_prediction(
        self,
        model: str,
        value: float,
        confidence: Optional[float] = None,
        output_type: str = "point",
        latency: float = 0.0,
        backend: str = "pytorch",
        batch_size: int = 1,
    ):
        """Record a prediction."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.prediction_value.labels(
            model=model,
            output_type=output_type
        ).observe(value)

        if confidence is not None:
            self.prediction_confidence.labels(model=model).observe(confidence)

        self.inference_latency.labels(
            model=model,
            backend=backend
        ).observe(latency)

        self.batch_size.labels(model=model).observe(batch_size)

    def update_model_info(
        self,
        model: str,
        version: str,
        stage: str = "production",
        framework: str = "pytorch",
    ):
        """Update model metadata."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.model_info.labels(model=model).info({
            "version": version,
            "stage": stage,
            "framework": framework,
        })
        self.model_last_updated.labels(model=model).set_to_current_time()

    def track_cache(self, model: str, hit: bool):
        """Record cache hit/miss."""
        if not PROMETHEUS_AVAILABLE:
            return

        if hit:
            self.cache_hits.labels(model=model).inc()
        else:
            self.cache_misses.labels(model=model).inc()

    def track_error(self, model: str, error_type: str):
        """Record prediction error."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.prediction_errors.labels(
            model=model,
            error_type=error_type
        ).inc()


class FeatureMetrics:
    """Feature-level metrics for data quality monitoring."""

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        if not PROMETHEUS_AVAILABLE:
            return

        self.registry = registry or REGISTRY

        # Feature values
        self.feature_value = Gauge(
            "ml_feature_value",
            "Current feature value",
            ["feature_name", "stat"],  # stat: mean, min, max, std
            registry=self.registry,
        )

        # Feature staleness
        self.feature_staleness = Gauge(
            "ml_feature_staleness_seconds",
            "Time since feature was last updated",
            ["feature_name"],
            registry=self.registry,
        )

        # Feature last updated
        self.feature_last_updated = Gauge(
            "ml_feature_last_updated_timestamp",
            "Timestamp when feature was last updated",
            ["feature_name"],
            registry=self.registry,
        )

        # Feature drift score
        self.feature_drift = Gauge(
            "ml_feature_drift_score",
            "Feature drift score (0-1)",
            ["feature_name", "drift_type"],  # drift_type: ks, psi, wasserstein
            registry=self.registry,
        )

        # Missing feature rate
        self.feature_missing_rate = Gauge(
            "ml_feature_missing_rate",
            "Rate of missing values for feature",
            ["feature_name"],
            registry=self.registry,
        )

        # Feature out of bounds
        self.feature_oob = Counter(
            "ml_feature_out_of_bounds_total",
            "Total out of bounds feature values",
            ["feature_name", "bound_type"],  # bound_type: high, low
            registry=self.registry,
        )

    def update_feature_stats(
        self,
        feature_name: str,
        mean: float,
        std: float,
        min_val: float,
        max_val: float,
    ):
        """Update feature statistics."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.feature_value.labels(feature_name=feature_name, stat="mean").set(mean)
        self.feature_value.labels(feature_name=feature_name, stat="std").set(std)
        self.feature_value.labels(feature_name=feature_name, stat="min").set(min_val)
        self.feature_value.labels(feature_name=feature_name, stat="max").set(max_val)
        self.feature_last_updated.labels(feature_name=feature_name).set_to_current_time()

    def update_staleness(self, feature_name: str, staleness_seconds: float):
        """Update feature staleness."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.feature_staleness.labels(feature_name=feature_name).set(staleness_seconds)

    def update_drift(
        self,
        feature_name: str,
        drift_score: float,
        drift_type: str = "ks",
    ):
        """Update feature drift score."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.feature_drift.labels(
            feature_name=feature_name,
            drift_type=drift_type
        ).set(drift_score)

    def track_oob(self, feature_name: str, bound_type: str):
        """Record out of bounds value."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.feature_oob.labels(
            feature_name=feature_name,
            bound_type=bound_type
        ).inc()


class BusinessMetrics:
    """Business-level metrics for trading and operational performance."""

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        if not PROMETHEUS_AVAILABLE:
            return

        self.registry = registry or REGISTRY

        # Trading profit
        self.trading_profit = Counter(
            "ml_trading_profit_total",
            "Total trading profit in INR",
            ["direction"],  # direction: realized, unrealized
            registry=self.registry,
        )

        # Trading loss
        self.trading_loss = Counter(
            "ml_trading_loss_total",
            "Total trading loss in INR",
            ["direction"],
            registry=self.registry,
        )

        # Current P&L
        self.pnl_current = Gauge(
            "ml_pnl_current",
            "Current unrealized P&L",
            ["period"],  # period: daily, weekly, monthly
            registry=self.registry,
        )

        # Trading actions
        self.trading_actions = Counter(
            "ml_trading_actions_total",
            "Total trading actions by type",
            ["action_type"],  # action_type: buy, sell, hold
            registry=self.registry,
        )

        # Trade volume
        self.trade_volume = Counter(
            "ml_trade_volume_kwh_total",
            "Total traded energy in kWh",
            ["action_type"],
            registry=self.registry,
        )

        # Trade value
        self.trade_value = Counter(
            "ml_trade_value_inr_total",
            "Total trade value in INR",
            ["action_type"],
            registry=self.registry,
        )

        # Anomaly alerts
        self.anomaly_alerts = Counter(
            "ml_anomaly_alerts_total",
            "Total anomaly alerts by severity",
            ["severity", "anomaly_type"],
            registry=self.registry,
        )

        # Anomaly score distribution
        self.anomaly_score = Histogram(
            "ml_anomaly_score",
            "Distribution of anomaly scores",
            ["anomaly_type"],
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99),
            registry=self.registry,
        )

        # Forecast error
        self.forecast_error = Histogram(
            "ml_forecast_error",
            "Forecast error distribution (MAPE)",
            ["model", "horizon", "city"],
            buckets=(0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5),
            registry=self.registry,
        )

        # Forecast accuracy
        self.forecast_accuracy = Gauge(
            "ml_forecast_accuracy",
            "Rolling forecast accuracy",
            ["model", "horizon", "metric"],  # metric: mape, rmse, mae
            registry=self.registry,
        )

        # Battery SOC distribution
        self.battery_soc = Histogram(
            "ml_battery_soc",
            "Battery state of charge distribution",
            [],
            buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
            registry=self.registry,
        )

    def track_trade(
        self,
        action_type: str,
        volume_kwh: float,
        value_inr: float,
        profit: float = 0.0,
    ):
        """Record a trade."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.trading_actions.labels(action_type=action_type).inc()
        self.trade_volume.labels(action_type=action_type).inc(volume_kwh)
        self.trade_value.labels(action_type=action_type).inc(value_inr)

        if profit >= 0:
            self.trading_profit.labels(direction="realized").inc(profit)
        else:
            self.trading_loss.labels(direction="realized").inc(abs(profit))

    def track_anomaly(
        self,
        anomaly_type: str,
        severity: str,
        score: float,
    ):
        """Record anomaly detection result."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.anomaly_alerts.labels(
            severity=severity,
            anomaly_type=anomaly_type
        ).inc()
        self.anomaly_score.labels(anomaly_type=anomaly_type).observe(score)

    def track_forecast_error(
        self,
        model: str,
        horizon: str,
        city: str,
        error: float,
    ):
        """Record forecast error."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.forecast_error.labels(
            model=model,
            horizon=horizon,
            city=city
        ).observe(error)

    def update_pnl(self, period: str, value: float):
        """Update current P&L."""
        if not PROMETHEUS_AVAILABLE:
            return

        self.pnl_current.labels(period=period).set(value)


class MLMetrics:
    """Unified metrics manager for SHAKTI-CHAIN ML."""

    _instance: Optional["MLMetrics"] = None

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        self.registry = registry or (REGISTRY if PROMETHEUS_AVAILABLE else None)

        self.request = RequestMetrics(self.registry)
        self.model = ModelMetrics(self.registry)
        self.feature = FeatureMetrics(self.registry)
        self.business = BusinessMetrics(self.registry)

        # Service info
        if PROMETHEUS_AVAILABLE:
            self.service_info = Info(
                "ml_service",
                "ML service information",
                registry=self.registry,
            )
            self.service_info.info({
                "name": "shakti-ml-service",
                "version": "1.0.0",
            })

    @classmethod
    def get_instance(cls) -> "MLMetrics":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in exposition format."""
        if not PROMETHEUS_AVAILABLE:
            return b""

        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        if not PROMETHEUS_AVAILABLE:
            return "text/plain"
        return CONTENT_TYPE_LATEST


def setup_metrics(registry: Optional["CollectorRegistry"] = None) -> MLMetrics:
    """Setup and return metrics instance."""
    return MLMetrics(registry)


def get_metrics() -> MLMetrics:
    """Get the current metrics instance."""
    return MLMetrics.get_instance()


# Decorators for easy instrumentation

def track_latency(endpoint: str):
    """Decorator to track request latency."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = get_metrics()
            with metrics.request.track_request_context(endpoint):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = get_metrics()
            with metrics.request.track_request_context(endpoint):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_inference(model: str, backend: str = "pytorch"):
    """Decorator to track model inference."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = get_metrics()
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                latency = time.perf_counter() - start
                metrics.model.inference_latency.labels(
                    model=model,
                    backend=backend
                ).observe(latency)
                return result
            except Exception as e:
                metrics.model.track_error(model, type(e).__name__)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = get_metrics()
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                latency = time.perf_counter() - start
                metrics.model.inference_latency.labels(
                    model=model,
                    backend=backend
                ).observe(latency)
                return result
            except Exception as e:
                metrics.model.track_error(model, type(e).__name__)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Import asyncio for decorator
import asyncio
