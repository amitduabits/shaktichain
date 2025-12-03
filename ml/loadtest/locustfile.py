"""Locust load testing for SHAKTI-CHAIN ML Service.

Performance targets:
| Endpoint         | p50    | p95    | p99    | RPS  |
|------------------|--------|--------|--------|------|
| /forecast/load   | 100ms  | 200ms  | 500ms  | 100  |
| /forecast/price  | 50ms   | 100ms  | 200ms  | 200  |
| /trading/action  | 20ms   | 50ms   | 100ms  | 500  |
| /anomaly/score   | 30ms   | 80ms   | 150ms  | 300  |

Usage:
    # Start locust web UI
    locust -f locustfile.py --host=http://localhost:8000

    # Headless mode with specific users
    locust -f locustfile.py --host=http://localhost:8000 \
        --headless -u 100 -r 10 -t 5m

    # Run specific scenarios
    locust -f locustfile.py --host=http://localhost:8000 \
        --tags forecast

    # Generate HTML report
    locust -f locustfile.py --host=http://localhost:8000 \
        --headless -u 100 -r 10 -t 5m --html=report.html
"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from locust import HttpUser, between, events, tag, task
from locust.runners import MasterRunner, WorkerRunner

# Test data generators
CITIES = ["delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad"]
MARKETS = ["day_ahead", "real_time", "ancillary"]


def generate_timestamp(offset_hours: int = 0) -> str:
    """Generate ISO format timestamp."""
    dt = datetime.now() + timedelta(hours=offset_hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def generate_load_forecast_request() -> Dict[str, Any]:
    """Generate random load forecast request."""
    return {
        "timestamp": generate_timestamp(),
        "horizon_hours": random.choice([6, 12, 24, 48]),
        "city": random.choice(CITIES),
        "resolution_minutes": random.choice([15, 30, 60]),
        "model_version": "production",
        "include_confidence": random.choice([True, False]),
        "confidence_level": 0.95,
    }


def generate_price_forecast_request() -> Dict[str, Any]:
    """Generate random price forecast request."""
    horizon = random.choice([6, 12, 24])
    return {
        "timestamp": generate_timestamp(),
        "horizon_hours": horizon,
        "market": random.choice(MARKETS),
        "load_forecast": [random.uniform(80, 120) for _ in range(horizon)],
        "model_version": "production",
        "include_volatility": True,
        "include_quantiles": True,
        "quantiles": [0.1, 0.5, 0.9],
    }


def generate_trading_action_request() -> Dict[str, Any]:
    """Generate random trading action request."""
    return {
        "timestamp": generate_timestamp(),
        "battery_state": {
            "soc": random.uniform(0.2, 0.9),
            "capacity_kwh": random.choice([50, 75, 100]),
            "max_charge_rate_kw": random.choice([10, 15, 22]),
            "max_discharge_rate_kw": random.choice([10, 15, 22]),
            "efficiency": random.uniform(0.9, 0.95),
            "degradation_cost": random.uniform(0.1, 0.3),
        },
        "market_state": {
            "current_price": random.uniform(3.0, 8.0),
            "price_forecast": [random.uniform(3.0, 8.0) for _ in range(12)],
            "volatility": random.uniform(0.05, 0.25),
            "spread": random.uniform(0.01, 0.05),
        },
        "risk_tolerance": random.uniform(0.3, 0.8),
        "model_version": "production",
    }


def generate_anomaly_score_request() -> Dict[str, Any]:
    """Generate random anomaly score request."""
    return {
        "trade": {
            "trade_id": f"trade_{random.randint(1000, 9999)}",
            "price": random.uniform(3.0, 8.0),
            "quantity": random.uniform(10, 500),
            "energy_kwh": random.uniform(10, 500),
            "timestamp": generate_timestamp(-random.randint(0, 24)),
        },
        "delivery": {
            "delivery_id": f"del_{random.randint(1000, 9999)}",
            "claimed_kwh": random.uniform(10, 100),
            "actual_kwh": random.uniform(8, 102),
            "timestamp": generate_timestamp(-random.randint(0, 12)),
        },
        "account": {
            "account_id": f"acc_{random.randint(100, 999)}",
            "reputation": random.uniform(0.5, 1.0),
            "total_trades": random.randint(10, 1000),
            "created_at": "2023-01-15T00:00:00",
        },
        "model_version": "production",
    }


def generate_explain_forecast_request() -> Dict[str, Any]:
    """Generate random forecast explanation request."""
    return {
        "timestamp": generate_timestamp(),
        "features": {
            "temperature": random.uniform(20, 45),
            "humidity": random.uniform(30, 90),
            "hour_sin": random.uniform(-1, 1),
            "hour_cos": random.uniform(-1, 1),
            "is_weekend": random.choice([0, 1]),
            "is_holiday": random.choice([0, 1]),
            "load_lag_1h": random.uniform(80, 120),
            "load_lag_24h": random.uniform(80, 120),
        },
        "model_type": random.choice(["load", "price"]),
        "model_version": "production",
        "top_k": 5,
        "include_visualization": False,
    }


def generate_batch_trading_request(batch_size: int = 10) -> Dict[str, Any]:
    """Generate batch trading request."""
    return {
        "requests": [generate_trading_action_request() for _ in range(batch_size)]
    }


# ============================================================================
# Locust User Classes
# ============================================================================


class V2GMLUser(HttpUser):
    """Standard V2G ML user with realistic task distribution."""

    wait_time = between(0.1, 0.5)
    weight = 10  # Most common user type

    def on_start(self):
        """Setup before starting tasks."""
        self.request_count = 0

    @tag("forecast", "load")
    @task(10)
    def forecast_load(self):
        """Test load forecasting endpoint."""
        with self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            catch_response=True,
            name="/forecast/load",
        ) as response:
            self._validate_response(response, "forecast_load")

    @tag("forecast", "price")
    @task(5)
    def forecast_price(self):
        """Test price forecasting endpoint."""
        with self.client.post(
            "/forecast/price",
            json=generate_price_forecast_request(),
            catch_response=True,
            name="/forecast/price",
        ) as response:
            self._validate_response(response, "forecast_price")

    @tag("trading")
    @task(20)
    def trading_action(self):
        """Test trading action endpoint - highest frequency."""
        with self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            catch_response=True,
            name="/trading/action",
        ) as response:
            self._validate_response(response, "trading_action")

    @tag("anomaly")
    @task(3)
    def anomaly_score(self):
        """Test anomaly scoring endpoint."""
        with self.client.post(
            "/anomaly/score",
            json=generate_anomaly_score_request(),
            catch_response=True,
            name="/anomaly/score",
        ) as response:
            self._validate_response(response, "anomaly_score")

    @tag("explain")
    @task(1)
    def explain_forecast(self):
        """Test forecast explanation endpoint."""
        with self.client.post(
            "/explain/forecast",
            json=generate_explain_forecast_request(),
            catch_response=True,
            name="/explain/forecast",
        ) as response:
            self._validate_response(response, "explain_forecast")

    def _validate_response(self, response, endpoint_name: str):
        """Validate response and mark success/failure."""
        self.request_count += 1

        if response.status_code == 200:
            try:
                data = response.json()
                if "error" in data:
                    response.failure(f"API error: {data['error']}")
                else:
                    response.success()
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
        elif response.status_code == 422:
            response.failure(f"Validation error: {response.text[:200]}")
        elif response.status_code >= 500:
            response.failure(f"Server error: {response.status_code}")
        else:
            response.failure(f"Unexpected status: {response.status_code}")


class HighFrequencyTradingUser(HttpUser):
    """High-frequency trading user - rapid trading requests."""

    wait_time = between(0.01, 0.05)  # Very fast
    weight = 3

    @tag("trading", "hft")
    @task
    def rapid_trading(self):
        """Rapid-fire trading requests."""
        with self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            catch_response=True,
            name="/trading/action [HFT]",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status: {response.status_code}")


class BatchProcessingUser(HttpUser):
    """Batch processing user - larger batch requests."""

    wait_time = between(1, 3)
    weight = 1

    @tag("batch", "trading")
    @task(5)
    def batch_trading(self):
        """Batch trading requests."""
        batch_sizes = [5, 10, 20, 50]
        batch_size = random.choice(batch_sizes)

        with self.client.post(
            "/trading/batch",
            json=generate_batch_trading_request(batch_size),
            catch_response=True,
            name=f"/trading/batch [{batch_size}]",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status: {response.status_code}")

    @tag("batch", "forecast")
    @task(2)
    def batch_forecast(self):
        """Multiple sequential forecasts (simulating batch)."""
        cities = random.sample(CITIES, 3)
        for city in cities:
            req = generate_load_forecast_request()
            req["city"] = city
            self.client.post("/forecast/load", json=req, name="/forecast/load [batch]")


class ExplainabilityUser(HttpUser):
    """User focused on model explanations."""

    wait_time = between(2, 5)
    weight = 1

    @tag("explain")
    @task(3)
    def explain_forecast(self):
        """Get forecast explanations."""
        with self.client.post(
            "/explain/forecast",
            json=generate_explain_forecast_request(),
            catch_response=True,
            name="/explain/forecast",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status: {response.status_code}")

    @tag("explain")
    @task(2)
    def explain_trading(self):
        """Get trading explanations."""
        state = {
            "spot_price": random.uniform(3.0, 8.0),
            "price_velocity_1m": random.uniform(-0.5, 0.5),
            "volatility_1h": random.uniform(0.05, 0.25),
            "order_imbalance": random.uniform(-0.5, 0.5),
            "grid_load": random.uniform(20000, 30000),
            "grid_frequency": random.uniform(49.9, 50.1),
            "soc": random.uniform(0.2, 0.9),
        }
        with self.client.post(
            "/explain/trading",
            json={
                "state": state,
                "model_version": "production",
                "include_counterfactual": True,
            },
            catch_response=True,
            name="/explain/trading",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status: {response.status_code}")

    @tag("explain")
    @task(1)
    def model_summary(self):
        """Get model summary."""
        model_type = random.choice(["load", "price", "trading"])
        with self.client.get(
            f"/explain/model-summary/{model_type}",
            name="/explain/model-summary",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status: {response.status_code}")


class SpikeTestUser(HttpUser):
    """User for spike/stress testing."""

    wait_time = between(0, 0.01)  # No wait - maximum load
    weight = 0  # Only use explicitly

    @task
    def rapid_requests(self):
        """Rapid requests across all endpoints."""
        endpoint = random.choice([
            ("/forecast/load", generate_load_forecast_request),
            ("/forecast/price", generate_price_forecast_request),
            ("/trading/action", generate_trading_action_request),
            ("/anomaly/score", generate_anomaly_score_request),
        ])
        self.client.post(endpoint[0], json=endpoint[1](), name=f"{endpoint[0]} [spike]")


# ============================================================================
# Custom Event Handlers
# ============================================================================


# Performance tracking
performance_data = {
    "start_time": None,
    "samples": [],
    "failures": [],
}


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    performance_data["start_time"] = time.time()
    print("\n" + "=" * 60)
    print("SHAKTI-CHAIN ML Load Test Starting")
    print("=" * 60)
    print(f"Host: {environment.host}")
    if hasattr(environment, "parsed_options"):
        print(f"Users: {environment.parsed_options.num_users}")
        print(f"Spawn rate: {environment.parsed_options.spawn_rate}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    duration = time.time() - performance_data["start_time"]
    print("\n" + "=" * 60)
    print("SHAKTI-CHAIN ML Load Test Complete")
    print("=" * 60)
    print(f"Duration: {duration:.1f}s")
    print("=" * 60 + "\n")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Track each request for detailed analysis."""
    performance_data["samples"].append({
        "name": name,
        "response_time": response_time,
        "timestamp": time.time(),
        "success": exception is None and (response is None or response.status_code == 200),
    })

    # Keep only last 10000 samples to prevent memory issues
    if len(performance_data["samples"]) > 10000:
        performance_data["samples"] = performance_data["samples"][-10000:]


@events.request_failure.add_listener
def on_failure(request_type, name, response_time, response, exception, **kwargs):
    """Track failures."""
    performance_data["failures"].append({
        "name": name,
        "response_time": response_time,
        "timestamp": time.time(),
        "error": str(exception) if exception else "HTTP Error",
    })


# ============================================================================
# Custom Shape for Realistic Load Patterns
# ============================================================================


class StagesShape:
    """
    Custom load shape for staged testing.

    Stages:
    1. Warm-up: Gradually increase to baseline
    2. Steady state: Maintain baseline load
    3. Peak: Simulate peak hours
    4. Spike: Brief traffic spike
    5. Recovery: Return to baseline
    6. Cool-down: Gradually decrease
    """

    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 2},     # Warm-up
        {"duration": 120, "users": 50, "spawn_rate": 5},    # Ramp to baseline
        {"duration": 180, "users": 50, "spawn_rate": 5},    # Steady state
        {"duration": 60, "users": 100, "spawn_rate": 10},   # Peak ramp
        {"duration": 120, "users": 100, "spawn_rate": 10},  # Peak steady
        {"duration": 30, "users": 200, "spawn_rate": 50},   # Spike
        {"duration": 60, "users": 100, "spawn_rate": 10},   # Recovery
        {"duration": 120, "users": 50, "spawn_rate": 5},    # Back to baseline
        {"duration": 60, "users": 10, "spawn_rate": 5},     # Cool-down
    ]

    def tick(self):
        """Return current stage configuration."""
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            run_time -= stage["duration"]

        return None  # End test


# ============================================================================
# Utility Functions
# ============================================================================


def calculate_percentiles(response_times: List[float]) -> Dict[str, float]:
    """Calculate p50, p95, p99 percentiles."""
    if not response_times:
        return {"p50": 0, "p95": 0, "p99": 0}

    sorted_times = sorted(response_times)
    n = len(sorted_times)

    return {
        "p50": sorted_times[int(n * 0.50)],
        "p95": sorted_times[int(n * 0.95)],
        "p99": sorted_times[int(n * 0.99)],
    }


def generate_summary_report() -> str:
    """Generate summary report from collected data."""
    samples = performance_data["samples"]
    if not samples:
        return "No data collected"

    # Group by endpoint
    by_endpoint = {}
    for sample in samples:
        name = sample["name"]
        if name not in by_endpoint:
            by_endpoint[name] = []
        by_endpoint[name].append(sample["response_time"])

    report = ["=" * 60, "PERFORMANCE SUMMARY", "=" * 60, ""]

    for endpoint, times in sorted(by_endpoint.items()):
        percentiles = calculate_percentiles(times)
        success_rate = sum(1 for s in samples if s["name"] == endpoint and s["success"]) / len(times) * 100

        report.append(f"{endpoint}:")
        report.append(f"  Requests: {len(times)}")
        report.append(f"  p50: {percentiles['p50']:.1f}ms")
        report.append(f"  p95: {percentiles['p95']:.1f}ms")
        report.append(f"  p99: {percentiles['p99']:.1f}ms")
        report.append(f"  Success: {success_rate:.1f}%")
        report.append("")

    return "\n".join(report)
