"""
Prometheus metrics module for V2G Marketplace.

Provides application and business metrics with Prometheus exposition format.
"""

import os
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    multiprocess,
    REGISTRY,
)


# Create a custom registry for application metrics
METRICS_REGISTRY = REGISTRY


# === Application Metrics ===

# Request metrics
REQUEST_COUNT = Counter(
    "v2g_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=METRICS_REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "v2g_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
    registry=METRICS_REGISTRY,
)

REQUEST_IN_PROGRESS = Gauge(
    "v2g_http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=METRICS_REGISTRY,
)

# Error metrics
ERROR_COUNT = Counter(
    "v2g_errors_total",
    "Total errors by type",
    ["error_type", "endpoint"],
    registry=METRICS_REGISTRY,
)

# Active simulations gauge
ACTIVE_SIMULATIONS = Gauge(
    "v2g_active_simulations",
    "Number of currently running simulations",
    registry=METRICS_REGISTRY,
)

# Database metrics
DB_QUERY_LATENCY = Histogram(
    "v2g_db_query_duration_seconds",
    "Database query latency in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=METRICS_REGISTRY,
)

DB_CONNECTION_POOL = Gauge(
    "v2g_db_connections",
    "Number of database connections",
    ["state"],
    registry=METRICS_REGISTRY,
)


# === Business Metrics ===

# Simulation metrics
SIMULATIONS_CREATED = Counter(
    "v2g_simulations_created_total",
    "Total simulations created",
    registry=METRICS_REGISTRY,
)

SIMULATIONS_COMPLETED = Counter(
    "v2g_simulations_completed_total",
    "Total simulations completed",
    ["status"],  # completed, failed
    registry=METRICS_REGISTRY,
)

SIMULATION_AGENTS = Histogram(
    "v2g_simulation_agents",
    "Number of agents per simulation",
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000),
    registry=METRICS_REGISTRY,
)

SIMULATION_DURATION = Histogram(
    "v2g_simulation_duration_seconds",
    "Simulation execution duration in seconds",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
    registry=METRICS_REGISTRY,
)

# Energy trading metrics
ENERGY_TRADED_TOTAL = Counter(
    "v2g_energy_traded_kwh_total",
    "Total energy traded in simulations (kWh)",
    registry=METRICS_REGISTRY,
)

MARKET_CLEARING_PRICE = Gauge(
    "v2g_market_clearing_price",
    "Latest market clearing price",
    registry=METRICS_REGISTRY,
)

MARKET_VOLUME = Gauge(
    "v2g_market_volume_kwh",
    "Latest market period volume (kWh)",
    registry=METRICS_REGISTRY,
)

# User metrics
USER_REGISTRATIONS = Counter(
    "v2g_user_registrations_total",
    "Total user registrations",
    registry=METRICS_REGISTRY,
)

USER_LOGINS = Counter(
    "v2g_user_logins_total",
    "Total user login attempts",
    ["status"],  # success, failed
    registry=METRICS_REGISTRY,
)

ACTIVE_USERS = Gauge(
    "v2g_active_users",
    "Number of active users (with valid sessions)",
    registry=METRICS_REGISTRY,
)

# Token metrics (for SHAKTI token model)
TOKEN_TRANSACTIONS = Counter(
    "v2g_token_transactions_total",
    "Total token transactions",
    ["type"],  # transfer, stake, unstake, burn
    registry=METRICS_REGISTRY,
)

TOKEN_VOLUME = Counter(
    "v2g_token_volume_total",
    "Total token volume traded",
    registry=METRICS_REGISTRY,
)


# === Service Info ===

SERVICE_INFO = Info(
    "v2g_service",
    "V2G Marketplace service information",
    registry=METRICS_REGISTRY,
)


# === Daily Aggregation Metrics ===

class DailyMetrics:
    """Track daily aggregated metrics."""

    def __init__(self):
        self._simulations_today = 0
        self._energy_today = 0.0
        self._last_reset = datetime.now(timezone.utc).date()

    def _check_reset(self):
        """Reset counters if day changed."""
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset:
            self._simulations_today = 0
            self._energy_today = 0.0
            self._last_reset = today

    def record_simulation(self, energy_kwh: float = 0.0):
        """Record a simulation for today."""
        self._check_reset()
        self._simulations_today += 1
        self._energy_today += energy_kwh

    @property
    def simulations_today(self) -> int:
        """Get simulations run today."""
        self._check_reset()
        return self._simulations_today

    @property
    def energy_today(self) -> float:
        """Get energy traded today (kWh)."""
        self._check_reset()
        return self._energy_today


# Global daily metrics instance
daily_metrics = DailyMetrics()


# === Metric Helper Functions ===

def record_request(method: str, endpoint: str, status_code: int, duration: float):
    """Record HTTP request metrics."""
    # Normalize endpoint to avoid high cardinality
    normalized_endpoint = normalize_endpoint(endpoint)
    REQUEST_COUNT.labels(method=method, endpoint=normalized_endpoint, status_code=str(status_code)).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=normalized_endpoint).observe(duration)


def record_error(error_type: str, endpoint: str):
    """Record error metric."""
    normalized_endpoint = normalize_endpoint(endpoint)
    ERROR_COUNT.labels(error_type=error_type, endpoint=normalized_endpoint).inc()


def record_db_query(query_type: str, duration: float):
    """Record database query metric."""
    DB_QUERY_LATENCY.labels(query_type=query_type).observe(duration)


def record_simulation_created(n_agents: int):
    """Record simulation creation."""
    SIMULATIONS_CREATED.inc()
    SIMULATION_AGENTS.observe(n_agents)
    daily_metrics.record_simulation()


def record_simulation_completed(status: str, duration: float, volume_kwh: float = 0.0):
    """Record simulation completion."""
    SIMULATIONS_COMPLETED.labels(status=status).inc()
    SIMULATION_DURATION.observe(duration)
    if volume_kwh > 0:
        ENERGY_TRADED_TOTAL.inc(volume_kwh)
        daily_metrics.record_simulation(volume_kwh)


def record_market_period(clearing_price: float, volume_kwh: float):
    """Record market period metrics."""
    MARKET_CLEARING_PRICE.set(clearing_price)
    MARKET_VOLUME.set(volume_kwh)
    ENERGY_TRADED_TOTAL.inc(volume_kwh)


def record_user_registration():
    """Record user registration."""
    USER_REGISTRATIONS.inc()


def record_user_login(success: bool):
    """Record user login attempt."""
    status = "success" if success else "failed"
    USER_LOGINS.labels(status=status).inc()


def set_active_simulations(count: int):
    """Set the number of active simulations."""
    ACTIVE_SIMULATIONS.set(count)


def set_active_users(count: int):
    """Set the number of active users."""
    ACTIVE_USERS.set(count)


def normalize_endpoint(endpoint: str) -> str:
    """
    Normalize endpoint path to reduce cardinality.

    Replaces UUIDs and IDs with placeholders.
    """
    import re

    # Replace UUIDs
    endpoint = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '{id}',
        endpoint,
        flags=re.IGNORECASE
    )

    # Replace numeric IDs
    endpoint = re.sub(r'/\d+(?=/|$)', '/{id}', endpoint)

    return endpoint


# === Decorators ===

def track_request_metrics(endpoint: Optional[str] = None):
    """Decorator to track request metrics."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ep = endpoint or func.__name__
            method = "UNKNOWN"

            # Try to get request from kwargs or args
            request = kwargs.get("request")
            if request:
                method = getattr(request, "method", "UNKNOWN")
                ep = str(getattr(request, "url", ep))

            normalized_ep = normalize_endpoint(ep)

            # Track in-progress
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=normalized_ep).inc()

            start_time = time.perf_counter()
            status_code = 200

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                record_error(type(e).__name__, normalized_ep)
                raise
            finally:
                duration = time.perf_counter() - start_time
                REQUEST_IN_PROGRESS.labels(method=method, endpoint=normalized_ep).dec()
                record_request(method, normalized_ep, status_code, duration)

        return wrapper
    return decorator


def track_db_query(query_type: str):
    """Decorator to track database query metrics."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                record_db_query(query_type, duration)
        return wrapper
    return decorator


# === Metrics Endpoint ===

def get_metrics() -> tuple[bytes, str]:
    """
    Generate Prometheus metrics output.

    Returns:
        Tuple of (metrics_data, content_type).
    """
    # Check if running in multiprocess mode
    if "prometheus_multiproc_dir" in os.environ:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST

    return generate_latest(METRICS_REGISTRY), CONTENT_TYPE_LATEST


def init_service_info():
    """Initialize service info metric."""
    SERVICE_INFO.info({
        "version": os.environ.get("APP_VERSION", "0.1.0"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "service": "v2g-marketplace",
    })


# === Health Check Support ===

class HealthStatus:
    """Track health check status for metrics."""

    def __init__(self):
        self._db_healthy = True
        self._last_db_check = None

    def set_db_health(self, healthy: bool):
        """Set database health status."""
        self._db_healthy = healthy
        self._last_db_check = datetime.now(timezone.utc)

    @property
    def is_healthy(self) -> bool:
        """Overall health status."""
        return self._db_healthy

    def get_status(self) -> dict:
        """Get detailed health status."""
        return {
            "healthy": self._db_healthy,
            "database": {
                "healthy": self._db_healthy,
                "last_check": self._last_db_check.isoformat() if self._last_db_check else None,
            },
        }


# Global health status
health_status = HealthStatus()


# Initialize service info on module load
init_service_info()
