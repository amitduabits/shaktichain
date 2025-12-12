"""
Throughput Measurer for SHAKTI-CHAIN System Performance Testing (Domain 3).

Measures and tracks transactions per second (TPS) with sliding window
and various statistical aggregations.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class ThroughputMeasurement:
    """
    Single throughput measurement.

    Attributes:
        timestamp: Time of measurement
        window_seconds: Duration of measurement window
        transactions_processed: Number of transactions in window
        tps: Transactions per second
        concurrent_users: Number of concurrent users during measurement
        latency_p50_ms: Median latency during window (optional)
        latency_p99_ms: 99th percentile latency (optional)
    """
    timestamp: float
    window_seconds: float
    transactions_processed: int
    tps: float
    concurrent_users: int
    latency_p50_ms: Optional[float] = None
    latency_p99_ms: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "window_seconds": self.window_seconds,
            "transactions_processed": self.transactions_processed,
            "tps": float(self.tps),
            "concurrent_users": self.concurrent_users,
            "latency_p50_ms": float(self.latency_p50_ms) if self.latency_p50_ms else None,
            "latency_p99_ms": float(self.latency_p99_ms) if self.latency_p99_ms else None,
        }


@dataclass
class ThroughputStatistics:
    """
    Aggregated throughput statistics.

    Attributes:
        mean_tps: Mean TPS across all measurements
        std_tps: Standard deviation of TPS
        min_tps: Minimum TPS observed
        max_tps: Maximum TPS observed
        p50_tps: Median TPS
        p90_tps: 90th percentile TPS
        p95_tps: 95th percentile TPS
        p99_tps: 99th percentile TPS
        total_transactions: Total transactions processed
        total_duration_seconds: Total measurement duration
        num_measurements: Number of measurement windows
    """
    mean_tps: float
    std_tps: float
    min_tps: float
    max_tps: float
    p50_tps: float
    p90_tps: float
    p95_tps: float
    p99_tps: float
    total_transactions: int
    total_duration_seconds: float
    num_measurements: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_tps": float(self.mean_tps),
            "std_tps": float(self.std_tps),
            "min_tps": float(self.min_tps),
            "max_tps": float(self.max_tps),
            "p50_tps": float(self.p50_tps),
            "p90_tps": float(self.p90_tps),
            "p95_tps": float(self.p95_tps),
            "p99_tps": float(self.p99_tps),
            "total_transactions": self.total_transactions,
            "total_duration_seconds": float(self.total_duration_seconds),
            "num_measurements": self.num_measurements,
        }


class ThroughputMeasurer:
    """
    Measure and track transaction throughput.

    Uses sliding window for real-time TPS calculation and
    aggregates statistics over measurement period.
    """

    def __init__(
        self,
        window_size: float = 1.0,
        max_history: int = 10000,
    ):
        """
        Initialize throughput measurer.

        Args:
            window_size: Size of measurement window in seconds
            max_history: Maximum number of measurements to retain
        """
        self.window_size = window_size
        self.max_history = max_history
        self.measurements: List[ThroughputMeasurement] = []
        self._transaction_times: Deque[float] = deque(maxlen=max_history * 10)
        self._window_start: Optional[float] = None
        self._window_count: int = 0
        self._current_users: int = 0
        self._latencies: List[float] = []

    def record_transaction(
        self,
        latency_ms: Optional[float] = None,
    ):
        """
        Record a single transaction.

        Args:
            latency_ms: Optional latency of the transaction in milliseconds
        """
        current_time = time.time()
        self._transaction_times.append(current_time)

        if latency_ms is not None:
            self._latencies.append(latency_ms)

        if self._window_start is None:
            self._window_start = current_time

        self._window_count += 1

        # Check if window is complete
        if current_time - self._window_start >= self.window_size:
            self._complete_window(current_time)

    def _complete_window(self, current_time: float):
        """Complete current measurement window and start new one."""
        if self._window_start is None:
            return

        window_duration = current_time - self._window_start
        tps = self._window_count / window_duration if window_duration > 0 else 0

        # Calculate latency percentiles for window
        latency_p50 = None
        latency_p99 = None
        if self._latencies:
            latency_arr = np.array(self._latencies)
            latency_p50 = float(np.percentile(latency_arr, 50))
            latency_p99 = float(np.percentile(latency_arr, 99))

        measurement = ThroughputMeasurement(
            timestamp=current_time,
            window_seconds=window_duration,
            transactions_processed=self._window_count,
            tps=tps,
            concurrent_users=self._current_users,
            latency_p50_ms=latency_p50,
            latency_p99_ms=latency_p99,
        )

        self.measurements.append(measurement)

        # Trim history if needed
        if len(self.measurements) > self.max_history:
            self.measurements = self.measurements[-self.max_history:]

        # Reset window
        self._window_start = current_time
        self._window_count = 0
        self._latencies = []

    def measure(
        self,
        transaction_count: int,
        duration_seconds: Optional[float] = None,
    ) -> ThroughputMeasurement:
        """
        Record a batch measurement.

        Args:
            transaction_count: Number of transactions processed
            duration_seconds: Duration of measurement (uses window_size if not specified)

        Returns:
            ThroughputMeasurement for this batch
        """
        current_time = time.time()
        duration = duration_seconds or self.window_size
        tps = transaction_count / duration if duration > 0 else 0

        measurement = ThroughputMeasurement(
            timestamp=current_time,
            window_seconds=duration,
            transactions_processed=transaction_count,
            tps=tps,
            concurrent_users=self._current_users,
        )

        self.measurements.append(measurement)
        return measurement

    def set_concurrent_users(self, count: int):
        """Set current number of concurrent users."""
        self._current_users = count

    def get_statistics(self) -> ThroughputStatistics:
        """
        Calculate aggregate statistics across all measurements.

        Returns:
            ThroughputStatistics with aggregated metrics
        """
        if not self.measurements:
            return ThroughputStatistics(
                mean_tps=0, std_tps=0, min_tps=0, max_tps=0,
                p50_tps=0, p90_tps=0, p95_tps=0, p99_tps=0,
                total_transactions=0, total_duration_seconds=0,
                num_measurements=0,
            )

        tps_values = np.array([m.tps for m in self.measurements])
        total_tx = sum(m.transactions_processed for m in self.measurements)
        total_duration = sum(m.window_seconds for m in self.measurements)

        return ThroughputStatistics(
            mean_tps=float(np.mean(tps_values)),
            std_tps=float(np.std(tps_values)),
            min_tps=float(np.min(tps_values)),
            max_tps=float(np.max(tps_values)),
            p50_tps=float(np.percentile(tps_values, 50)),
            p90_tps=float(np.percentile(tps_values, 90)),
            p95_tps=float(np.percentile(tps_values, 95)),
            p99_tps=float(np.percentile(tps_values, 99)),
            total_transactions=total_tx,
            total_duration_seconds=total_duration,
            num_measurements=len(self.measurements),
        )

    def get_current_tps(self, lookback_seconds: float = 5.0) -> float:
        """
        Get current TPS based on recent transactions.

        Args:
            lookback_seconds: How far back to look for transactions

        Returns:
            Current TPS estimate
        """
        current_time = time.time()
        cutoff_time = current_time - lookback_seconds

        # Count transactions in lookback window
        count = sum(1 for t in self._transaction_times if t >= cutoff_time)

        return count / lookback_seconds

    def get_tps_time_series(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get TPS values as time series.

        Returns:
            Tuple of (timestamps, tps_values) arrays
        """
        if not self.measurements:
            return np.array([]), np.array([])

        timestamps = np.array([m.timestamp for m in self.measurements])
        tps_values = np.array([m.tps for m in self.measurements])

        return timestamps, tps_values

    def clear(self):
        """Clear all measurements and reset state."""
        self.measurements = []
        self._transaction_times.clear()
        self._window_start = None
        self._window_count = 0
        self._current_users = 0
        self._latencies = []


class ThroughputBenchmarker:
    """
    Run throughput benchmarks at different load levels.

    Provides structured approach to measuring system capacity.
    """

    def __init__(self):
        """Initialize benchmarker."""
        self.results: Dict[int, ThroughputStatistics] = {}
        self.raw_measurements: Dict[int, List[ThroughputMeasurement]] = {}

    def add_benchmark_result(
        self,
        concurrent_users: int,
        measurements: List[ThroughputMeasurement],
    ):
        """
        Add benchmark results for a specific load level.

        Args:
            concurrent_users: Number of concurrent users
            measurements: List of measurements at this load level
        """
        self.raw_measurements[concurrent_users] = measurements

        # Calculate statistics
        if measurements:
            tps_values = np.array([m.tps for m in measurements])
            total_tx = sum(m.transactions_processed for m in measurements)
            total_duration = sum(m.window_seconds for m in measurements)

            stats = ThroughputStatistics(
                mean_tps=float(np.mean(tps_values)),
                std_tps=float(np.std(tps_values)),
                min_tps=float(np.min(tps_values)),
                max_tps=float(np.max(tps_values)),
                p50_tps=float(np.percentile(tps_values, 50)),
                p90_tps=float(np.percentile(tps_values, 90)),
                p95_tps=float(np.percentile(tps_values, 95)),
                p99_tps=float(np.percentile(tps_values, 99)),
                total_transactions=total_tx,
                total_duration_seconds=total_duration,
                num_measurements=len(measurements),
            )
            self.results[concurrent_users] = stats

    def get_scalability_data(self) -> List[Tuple[int, float, float]]:
        """
        Get data for scalability analysis.

        Returns:
            List of (concurrent_users, mean_tps, std_tps) tuples
        """
        data = []
        for users in sorted(self.results.keys()):
            stats = self.results[users]
            data.append((users, stats.mean_tps, stats.std_tps))
        return data

    def find_max_sustainable_tps(
        self,
        latency_threshold_ms: Optional[float] = None,
    ) -> Tuple[int, float]:
        """
        Find maximum sustainable TPS across all load levels.

        Args:
            latency_threshold_ms: Optional latency threshold to consider

        Returns:
            Tuple of (optimal_concurrent_users, max_tps)
        """
        if not self.results:
            return (0, 0.0)

        best_users = 0
        best_tps = 0.0

        for users, stats in self.results.items():
            # Check latency constraint if provided
            if latency_threshold_ms is not None:
                measurements = self.raw_measurements.get(users, [])
                if measurements:
                    latencies = [m.latency_p99_ms for m in measurements if m.latency_p99_ms]
                    if latencies and np.mean(latencies) > latency_threshold_ms:
                        continue

            if stats.mean_tps > best_tps:
                best_tps = stats.mean_tps
                best_users = users

        return (best_users, best_tps)

    def to_dict(self) -> dict:
        """Convert all results to dictionary."""
        return {
            str(users): stats.to_dict()
            for users, stats in self.results.items()
        }


def simulate_throughput_measurement(
    target_tps: int,
    duration_seconds: int,
    noise_factor: float = 0.1,
    seed: Optional[int] = None,
) -> Tuple[List[ThroughputMeasurement], ThroughputStatistics]:
    """
    Simulate throughput measurements for testing.

    Args:
        target_tps: Target TPS to simulate
        duration_seconds: Duration of simulation
        noise_factor: Gaussian noise factor
        seed: Random seed

    Returns:
        Tuple of (measurements, statistics)
    """
    rng = np.random.default_rng(seed)

    measurements = []
    current_time = time.time()

    for i in range(duration_seconds):
        # Generate TPS with noise
        actual_tps = target_tps * (1 + rng.normal(0, noise_factor))
        actual_tps = max(0, actual_tps)

        # Occasional dips
        if rng.random() < 0.02:
            actual_tps *= rng.uniform(0.5, 0.8)

        tx_count = int(actual_tps)

        # Generate latency (log-normal)
        latency_p50 = 10 * (1 + rng.normal(0, 0.1))
        latency_p99 = latency_p50 * (3 + rng.normal(0, 0.5))

        measurement = ThroughputMeasurement(
            timestamp=current_time + i,
            window_seconds=1.0,
            transactions_processed=tx_count,
            tps=actual_tps,
            concurrent_users=100,
            latency_p50_ms=latency_p50,
            latency_p99_ms=latency_p99,
        )
        measurements.append(measurement)

    # Calculate statistics
    tps_values = np.array([m.tps for m in measurements])
    total_tx = sum(m.transactions_processed for m in measurements)

    stats = ThroughputStatistics(
        mean_tps=float(np.mean(tps_values)),
        std_tps=float(np.std(tps_values)),
        min_tps=float(np.min(tps_values)),
        max_tps=float(np.max(tps_values)),
        p50_tps=float(np.percentile(tps_values, 50)),
        p90_tps=float(np.percentile(tps_values, 90)),
        p95_tps=float(np.percentile(tps_values, 95)),
        p99_tps=float(np.percentile(tps_values, 99)),
        total_transactions=total_tx,
        total_duration_seconds=float(duration_seconds),
        num_measurements=len(measurements),
    )

    return measurements, stats
