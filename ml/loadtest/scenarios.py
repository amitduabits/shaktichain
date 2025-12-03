"""Specialized load testing scenarios for SHAKTI-CHAIN ML.

Scenarios:
1. Capacity test - Find maximum RPS per endpoint
2. Endurance test - Sustained load over time
3. Spike test - Handle sudden traffic spikes
4. Stress test - Find breaking point
5. Soak test - Long-running stability test
"""

import random
import time
from datetime import datetime

from locust import HttpUser, LoadTestShape, between, events, task

from locustfile import (
    generate_anomaly_score_request,
    generate_load_forecast_request,
    generate_price_forecast_request,
    generate_trading_action_request,
)


# ============================================================================
# Scenario 1: Capacity Test
# ============================================================================


class CapacityTestUser(HttpUser):
    """
    Capacity test - incrementally increase load to find maximum RPS.

    Run with:
        locust -f scenarios.py --class-picker CapacityTestUser \
            --host=http://localhost:8000 --headless -u 500 -r 10 -t 10m
    """

    wait_time = between(0.05, 0.1)

    @task(20)
    def trading_capacity(self):
        """Test trading endpoint capacity."""
        self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            name="/trading/action [capacity]",
        )

    @task(10)
    def forecast_capacity(self):
        """Test forecast endpoint capacity."""
        self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            name="/forecast/load [capacity]",
        )

    @task(5)
    def anomaly_capacity(self):
        """Test anomaly endpoint capacity."""
        self.client.post(
            "/anomaly/score",
            json=generate_anomaly_score_request(),
            name="/anomaly/score [capacity]",
        )


class CapacityTestShape(LoadTestShape):
    """
    Step-up load shape for capacity testing.
    Increases load every 60 seconds.
    """

    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 5},
        {"duration": 120, "users": 25, "spawn_rate": 5},
        {"duration": 180, "users": 50, "spawn_rate": 10},
        {"duration": 240, "users": 100, "spawn_rate": 10},
        {"duration": 300, "users": 150, "spawn_rate": 15},
        {"duration": 360, "users": 200, "spawn_rate": 20},
        {"duration": 420, "users": 300, "spawn_rate": 25},
        {"duration": 480, "users": 400, "spawn_rate": 30},
        {"duration": 540, "users": 500, "spawn_rate": 30},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            run_time -= stage["duration"]
        return None


# ============================================================================
# Scenario 2: Endurance Test
# ============================================================================


class EnduranceTestUser(HttpUser):
    """
    Endurance test - sustained load over extended period.

    Run with:
        locust -f scenarios.py --class-picker EnduranceTestUser \
            --host=http://localhost:8000 --headless -u 50 -r 5 -t 30m
    """

    wait_time = between(0.5, 1.0)

    def on_start(self):
        self.start_time = time.time()
        self.request_count = 0

    @task(10)
    def trading_endurance(self):
        self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            name="/trading/action [endurance]",
        )
        self.request_count += 1

    @task(5)
    def forecast_endurance(self):
        self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            name="/forecast/load [endurance]",
        )
        self.request_count += 1

    @task(3)
    def price_endurance(self):
        self.client.post(
            "/forecast/price",
            json=generate_price_forecast_request(),
            name="/forecast/price [endurance]",
        )
        self.request_count += 1

    @task(2)
    def anomaly_endurance(self):
        self.client.post(
            "/anomaly/score",
            json=generate_anomaly_score_request(),
            name="/anomaly/score [endurance]",
        )
        self.request_count += 1


# ============================================================================
# Scenario 3: Spike Test
# ============================================================================


class SpikeTestUser(HttpUser):
    """
    Spike test - handle sudden traffic bursts.

    Run with:
        locust -f scenarios.py --class-picker SpikeTestUser \
            --host=http://localhost:8000 --headless -t 5m
    """

    wait_time = between(0.01, 0.05)

    @task
    def spike_request(self):
        endpoint = random.choice([
            ("/trading/action", generate_trading_action_request),
            ("/forecast/load", generate_load_forecast_request),
        ])
        self.client.post(endpoint[0], json=endpoint[1](), name=f"{endpoint[0]} [spike]")


class SpikeTestShape(LoadTestShape):
    """
    Spike pattern - baseline with periodic spikes.
    """

    def tick(self):
        run_time = self.get_run_time()

        # Baseline: 20 users
        # Spike every 60 seconds: 200 users for 10 seconds
        cycle_position = run_time % 60

        if cycle_position < 10:
            # Spike period
            return (200, 100)  # Rapid spawn
        else:
            # Baseline period
            return (20, 5)


# ============================================================================
# Scenario 4: Stress Test
# ============================================================================


class StressTestUser(HttpUser):
    """
    Stress test - find breaking point.

    Run with:
        locust -f scenarios.py --class-picker StressTestUser \
            --host=http://localhost:8000 --headless -t 15m
    """

    wait_time = between(0, 0.01)  # No delay

    @task(5)
    def stress_trading(self):
        self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            name="/trading/action [stress]",
        )

    @task(2)
    def stress_forecast(self):
        self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            name="/forecast/load [stress]",
        )

    @task(1)
    def stress_anomaly(self):
        self.client.post(
            "/anomaly/score",
            json=generate_anomaly_score_request(),
            name="/anomaly/score [stress]",
        )


class StressTestShape(LoadTestShape):
    """
    Continuously increasing load until failure.
    """

    def tick(self):
        run_time = self.get_run_time()

        # Increase users linearly: 10 users per minute
        users = int(10 + (run_time / 60) * 20)

        # Cap at 1000 users
        if users > 1000:
            return None

        return (users, 20)


# ============================================================================
# Scenario 5: Soak Test
# ============================================================================


class SoakTestUser(HttpUser):
    """
    Soak test - long-running stability test (memory leaks, resource exhaustion).

    Run with:
        locust -f scenarios.py --class-picker SoakTestUser \
            --host=http://localhost:8000 --headless -u 30 -r 2 -t 4h
    """

    wait_time = between(1, 2)

    def on_start(self):
        self.memory_samples = []

    @task(10)
    def soak_trading(self):
        self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            name="/trading/action [soak]",
        )

    @task(5)
    def soak_forecast(self):
        self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            name="/forecast/load [soak]",
        )

    @task(3)
    def soak_price(self):
        self.client.post(
            "/forecast/price",
            json=generate_price_forecast_request(),
            name="/forecast/price [soak]",
        )

    @task(2)
    def soak_anomaly(self):
        self.client.post(
            "/anomaly/score",
            json=generate_anomaly_score_request(),
            name="/anomaly/score [soak]",
        )


# ============================================================================
# Scenario 6: Realistic Daily Pattern
# ============================================================================


class DailyPatternUser(HttpUser):
    """
    Simulates realistic daily usage pattern.

    Lower load at night, peak during morning and evening.
    """

    wait_time = between(0.1, 0.5)

    @task(20)
    def trading(self):
        self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            name="/trading/action [daily]",
        )

    @task(10)
    def forecast(self):
        self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            name="/forecast/load [daily]",
        )

    @task(5)
    def price(self):
        self.client.post(
            "/forecast/price",
            json=generate_price_forecast_request(),
            name="/forecast/price [daily]",
        )


class DailyPatternShape(LoadTestShape):
    """
    Simulates 24-hour pattern compressed into test duration.

    Each "hour" is 2.5 minutes of test time (60 minutes = 24 hours).
    """

    # Users per "hour" of day (0-23)
    hourly_pattern = [
        10, 8, 5, 5, 5, 8,       # 00:00 - 05:00 (night)
        15, 30, 50, 60, 55, 50,  # 06:00 - 11:00 (morning peak)
        45, 40, 45, 50, 55, 70,  # 12:00 - 17:00 (afternoon)
        80, 75, 60, 40, 25, 15,  # 18:00 - 23:00 (evening peak then decline)
    ]

    def tick(self):
        run_time = self.get_run_time()

        # Each "hour" = 150 seconds (2.5 min)
        hour_duration = 150
        current_hour = int(run_time / hour_duration) % 24

        # Complete after one full "day"
        if run_time > hour_duration * 24:
            return None

        users = self.hourly_pattern[current_hour]
        return (users, 10)


# ============================================================================
# Scenario 7: Endpoint Isolation Test
# ============================================================================


class TradingOnlyUser(HttpUser):
    """Test trading endpoint in isolation."""

    wait_time = between(0.02, 0.05)

    @task
    def trading_only(self):
        self.client.post(
            "/trading/action",
            json=generate_trading_action_request(),
            name="/trading/action [isolated]",
        )


class ForecastOnlyUser(HttpUser):
    """Test forecast endpoint in isolation."""

    wait_time = between(0.05, 0.1)

    @task
    def forecast_only(self):
        self.client.post(
            "/forecast/load",
            json=generate_load_forecast_request(),
            name="/forecast/load [isolated]",
        )


class AnomalyOnlyUser(HttpUser):
    """Test anomaly endpoint in isolation."""

    wait_time = between(0.03, 0.08)

    @task
    def anomaly_only(self):
        self.client.post(
            "/anomaly/score",
            json=generate_anomaly_score_request(),
            name="/anomaly/score [isolated]",
        )


# ============================================================================
# Event Handlers for Detailed Reporting
# ============================================================================


latency_samples = {
    "trading": [],
    "forecast": [],
    "anomaly": [],
    "price": [],
}


@events.request.add_listener
def track_latency(request_type, name, response_time, **kwargs):
    """Track latency per endpoint category."""
    if "trading" in name.lower():
        latency_samples["trading"].append(response_time)
    elif "forecast/load" in name.lower():
        latency_samples["forecast"].append(response_time)
    elif "forecast/price" in name.lower():
        latency_samples["price"].append(response_time)
    elif "anomaly" in name.lower():
        latency_samples["anomaly"].append(response_time)

    # Keep only last 10000 per category
    for key in latency_samples:
        if len(latency_samples[key]) > 10000:
            latency_samples[key] = latency_samples[key][-10000:]


@events.test_stop.add_listener
def generate_latency_report(environment, **kwargs):
    """Generate detailed latency report at test end."""
    print("\n" + "=" * 70)
    print("LATENCY REPORT")
    print("=" * 70)

    targets = {
        "trading": {"p50": 20, "p95": 50, "p99": 100},
        "forecast": {"p50": 100, "p95": 200, "p99": 500},
        "price": {"p50": 50, "p95": 100, "p99": 200},
        "anomaly": {"p50": 30, "p95": 80, "p99": 150},
    }

    for endpoint, samples in latency_samples.items():
        if not samples:
            continue

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        p50 = sorted_samples[int(n * 0.50)]
        p95 = sorted_samples[int(n * 0.95)]
        p99 = sorted_samples[int(n * 0.99)]

        target = targets.get(endpoint, {"p50": 100, "p95": 200, "p99": 500})

        print(f"\n{endpoint.upper()}:")
        print(f"  Samples: {n}")
        print(f"  p50: {p50:.1f}ms (target: {target['p50']}ms) {'✓' if p50 <= target['p50'] else '✗'}")
        print(f"  p95: {p95:.1f}ms (target: {target['p95']}ms) {'✓' if p95 <= target['p95'] else '✗'}")
        print(f"  p99: {p99:.1f}ms (target: {target['p99']}ms) {'✓' if p99 <= target['p99'] else '✗'}")

    print("\n" + "=" * 70)
