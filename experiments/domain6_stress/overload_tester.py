"""
Overload Tester for SHAKTI-CHAIN Stress Testing (Domain 6).

Tests hypothesis H6.4: TPS >= 50% at 2x load (graceful degradation).
Simulates beyond-capacity scenarios and measures performance degradation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class LoadPattern(Enum):
    """Types of load patterns."""
    CONSTANT = "constant"         # Steady high load
    RAMP = "ramp"                 # Gradually increasing
    SPIKE = "spike"               # Sudden burst
    WAVE = "wave"                 # Oscillating load
    STEP = "step"                 # Step function increases


@dataclass
class LoadScenario:
    """
    Configuration for an overload scenario.

    Attributes:
        name: Scenario name
        load_multiplier: Multiple of base capacity (2.0 = 200%)
        pattern: Type of load pattern
        duration_seconds: Duration of test
        ramp_time_seconds: Time to reach peak load (for ramp pattern)
    """
    name: str
    load_multiplier: float
    pattern: LoadPattern
    duration_seconds: float
    ramp_time_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "load_multiplier": float(self.load_multiplier),
            "pattern": self.pattern.value,
            "duration_seconds": float(self.duration_seconds),
            "ramp_time_seconds": float(self.ramp_time_seconds),
        }


# Predefined overload scenarios
DOUBLE_LOAD = LoadScenario(
    name="Double Load (2x)",
    load_multiplier=2.0,
    pattern=LoadPattern.CONSTANT,
    duration_seconds=60.0,
)

TRIPLE_LOAD = LoadScenario(
    name="Triple Load (3x)",
    load_multiplier=3.0,
    pattern=LoadPattern.CONSTANT,
    duration_seconds=30.0,
)

GRADUAL_OVERLOAD = LoadScenario(
    name="Gradual Overload",
    load_multiplier=2.5,
    pattern=LoadPattern.RAMP,
    duration_seconds=60.0,
    ramp_time_seconds=30.0,
)

SPIKE_LOAD = LoadScenario(
    name="Load Spike",
    load_multiplier=5.0,
    pattern=LoadPattern.SPIKE,
    duration_seconds=10.0,
)

OVERLOAD_SCENARIOS = [
    DOUBLE_LOAD,
    TRIPLE_LOAD,
    GRADUAL_OVERLOAD,
    SPIKE_LOAD,
]


@dataclass
class OverloadResult:
    """
    Result of an overload test.

    Attributes:
        scenario: The load scenario tested
        baseline_tps: TPS at normal load
        overload_tps: TPS during overload
        tps_ratio: Overload TPS / Baseline TPS
        min_tps: Minimum TPS observed
        mean_latency_baseline: Mean latency at baseline (ms)
        mean_latency_overload: Mean latency during overload (ms)
        latency_p99: 99th percentile latency (ms)
        error_rate: Fraction of failed transactions
        queue_depth_max: Maximum transaction queue depth
        tps_series: TPS over time
        latency_series: Latency over time
    """
    scenario: LoadScenario
    baseline_tps: float
    overload_tps: float
    tps_ratio: float
    min_tps: float
    mean_latency_baseline: float
    mean_latency_overload: float
    latency_p99: float
    error_rate: float
    queue_depth_max: int
    tps_series: np.ndarray = field(default_factory=lambda: np.array([]))
    latency_series: np.ndarray = field(default_factory=lambda: np.array([]))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario.to_dict(),
            "baseline_tps": float(self.baseline_tps),
            "overload_tps": float(self.overload_tps),
            "tps_ratio": float(self.tps_ratio),
            "min_tps": float(self.min_tps),
            "mean_latency_baseline": float(self.mean_latency_baseline),
            "mean_latency_overload": float(self.mean_latency_overload),
            "latency_p99": float(self.latency_p99),
            "error_rate": float(self.error_rate),
            "queue_depth_max": self.queue_depth_max,
        }


@dataclass
class DegradationTestResult:
    """
    Result of graceful degradation hypothesis test (H6.4).

    Attributes:
        passed: Whether TPS >= threshold at target load
        mean_tps_ratio: Mean TPS ratio across simulations
        std_tps_ratio: Standard deviation
        tps_threshold: Required TPS ratio (default 50%)
        load_multiplier: Load multiplier tested
        t_statistic: T-test statistic
        p_value: P-value
        individual_results: Results from each simulation
    """
    passed: bool
    mean_tps_ratio: float
    std_tps_ratio: float
    tps_threshold: float
    load_multiplier: float
    t_statistic: float
    p_value: float
    individual_results: List[OverloadResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "mean_tps_ratio": float(self.mean_tps_ratio),
            "std_tps_ratio": float(self.std_tps_ratio),
            "tps_threshold": float(self.tps_threshold),
            "load_multiplier": float(self.load_multiplier),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "num_simulations": len(self.individual_results),
        }


class TransactionSimulator:
    """
    Simulate transaction processing under load.

    Models:
    - Processing capacity (max TPS)
    - Queue buildup under overload
    - Latency increase with load
    - Error rates under stress
    """

    def __init__(
        self,
        max_tps: float = 1000.0,
        base_latency_ms: float = 50.0,
        queue_capacity: int = 10000,
        seed: Optional[int] = None,
    ):
        """
        Initialize transaction simulator.

        Args:
            max_tps: Maximum transactions per second
            base_latency_ms: Base latency in milliseconds
            queue_capacity: Maximum queue size before drops
            seed: Random seed
        """
        self.max_tps = max_tps
        self.base_latency_ms = base_latency_ms
        self.queue_capacity = queue_capacity
        self.rng = np.random.default_rng(seed)

        self.queue_depth = 0
        self.total_processed = 0
        self.total_dropped = 0

    def reset(self):
        """Reset simulator state."""
        self.queue_depth = 0
        self.total_processed = 0
        self.total_dropped = 0

    def simulate_second(
        self,
        incoming_tps: float,
    ) -> Tuple[float, float, int, int]:
        """
        Simulate one second of transaction processing.

        Args:
            incoming_tps: Incoming transaction rate

        Returns:
            (actual_tps, latency_ms, processed, dropped)
        """
        # Add incoming transactions to queue
        incoming = int(incoming_tps + self.rng.uniform(-10, 10))
        self.queue_depth += incoming

        # Drop transactions if queue overflows
        dropped = 0
        if self.queue_depth > self.queue_capacity:
            dropped = self.queue_depth - self.queue_capacity
            self.queue_depth = self.queue_capacity

        # Process transactions (limited by max TPS)
        processed = min(self.queue_depth, int(self.max_tps))
        self.queue_depth -= processed

        # Calculate actual TPS
        actual_tps = processed

        # Calculate latency (increases with queue depth)
        queue_factor = 1 + (self.queue_depth / self.queue_capacity) * 5
        load_factor = max(1, incoming_tps / self.max_tps)
        latency = self.base_latency_ms * queue_factor * load_factor

        # Add randomness
        latency += self.rng.exponential(latency * 0.1)

        self.total_processed += processed
        self.total_dropped += dropped

        return actual_tps, latency, processed, dropped


class OverloadTester:
    """
    Test system behavior under beyond-capacity load.

    Tests H6.4: TPS >= 50% at 2x load.
    """

    def __init__(
        self,
        max_tps: float = 1000.0,
        base_latency_ms: float = 50.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize overload tester.

        Args:
            max_tps: Maximum TPS capacity
            base_latency_ms: Base latency in ms
            seed: Random seed
        """
        self.max_tps = max_tps
        self.base_latency_ms = base_latency_ms
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def generate_load_curve(
        self,
        scenario: LoadScenario,
        duration_seconds: int,
    ) -> np.ndarray:
        """
        Generate load curve for a scenario.

        Args:
            scenario: Load scenario configuration
            duration_seconds: Duration in seconds

        Returns:
            Array of incoming TPS values
        """
        base_tps = self.max_tps  # Normal load = max capacity
        peak_tps = base_tps * scenario.load_multiplier

        load_curve = np.zeros(duration_seconds)

        if scenario.pattern == LoadPattern.CONSTANT:
            load_curve[:] = peak_tps

        elif scenario.pattern == LoadPattern.RAMP:
            ramp_seconds = int(scenario.ramp_time_seconds)
            for i in range(duration_seconds):
                if i < ramp_seconds:
                    progress = (i + 1) / ramp_seconds
                    load_curve[i] = base_tps + (peak_tps - base_tps) * progress
                else:
                    load_curve[i] = peak_tps

        elif scenario.pattern == LoadPattern.SPIKE:
            # Spike in the middle
            spike_start = duration_seconds // 3
            spike_end = 2 * duration_seconds // 3
            load_curve[:] = base_tps
            load_curve[spike_start:spike_end] = peak_tps

        elif scenario.pattern == LoadPattern.WAVE:
            # Oscillating load
            for i in range(duration_seconds):
                wave = np.sin(2 * np.pi * i / (duration_seconds / 3))
                load_curve[i] = base_tps + (peak_tps - base_tps) * (wave + 1) / 2

        elif scenario.pattern == LoadPattern.STEP:
            # Step increases
            n_steps = 4
            step_size = (peak_tps - base_tps) / n_steps
            step_duration = duration_seconds // n_steps

            for step in range(n_steps):
                start = step * step_duration
                end = (step + 1) * step_duration
                load_curve[start:end] = base_tps + step_size * (step + 1)

        return load_curve

    def run_overload_test(
        self,
        scenario: LoadScenario,
    ) -> OverloadResult:
        """
        Run a single overload test.

        Args:
            scenario: Load scenario configuration

        Returns:
            OverloadResult
        """
        duration = int(scenario.duration_seconds)

        # First run baseline (normal load)
        baseline_duration = 10
        simulator = TransactionSimulator(
            max_tps=self.max_tps,
            base_latency_ms=self.base_latency_ms,
            seed=self.seed,
        )

        baseline_tps_list = []
        baseline_latency_list = []

        for _ in range(baseline_duration):
            tps, latency, _, _ = simulator.simulate_second(self.max_tps * 0.8)
            baseline_tps_list.append(tps)
            baseline_latency_list.append(latency)

        baseline_tps = np.mean(baseline_tps_list)
        baseline_latency = np.mean(baseline_latency_list)

        # Reset and run overload scenario
        simulator.reset()
        load_curve = self.generate_load_curve(scenario, duration)

        tps_series = []
        latency_series = []
        queue_depths = []
        total_dropped = 0

        for incoming in load_curve:
            tps, latency, processed, dropped = simulator.simulate_second(incoming)
            tps_series.append(tps)
            latency_series.append(latency)
            queue_depths.append(simulator.queue_depth)
            total_dropped += dropped

        tps_series = np.array(tps_series)
        latency_series = np.array(latency_series)

        # Calculate metrics
        overload_tps = np.mean(tps_series)
        tps_ratio = overload_tps / baseline_tps if baseline_tps > 0 else 0
        min_tps = np.min(tps_series)

        total_transactions = simulator.total_processed + total_dropped
        error_rate = total_dropped / total_transactions if total_transactions > 0 else 0

        return OverloadResult(
            scenario=scenario,
            baseline_tps=float(baseline_tps),
            overload_tps=float(overload_tps),
            tps_ratio=float(tps_ratio),
            min_tps=float(min_tps),
            mean_latency_baseline=float(baseline_latency),
            mean_latency_overload=float(np.mean(latency_series)),
            latency_p99=float(np.percentile(latency_series, 99)),
            error_rate=float(error_rate),
            queue_depth_max=max(queue_depths),
            tps_series=tps_series,
            latency_series=latency_series,
        )

    def test_graceful_degradation(
        self,
        load_multiplier: float = 2.0,
        tps_threshold: float = 0.50,
        n_simulations: int = 30,
        alpha: float = 0.05,
    ) -> DegradationTestResult:
        """
        Test H6.4: TPS >= threshold at given load multiplier.

        Args:
            load_multiplier: Target load multiplier (e.g., 2.0 for 2x)
            tps_threshold: Required TPS ratio (default 50%)
            n_simulations: Number of simulations
            alpha: Significance level

        Returns:
            DegradationTestResult
        """
        scenario = LoadScenario(
            name=f"Degradation Test ({load_multiplier}x)",
            load_multiplier=load_multiplier,
            pattern=LoadPattern.CONSTANT,
            duration_seconds=30.0,
        )

        results = []
        tps_ratios = []

        for sim_idx in range(n_simulations):
            sim_seed = self.seed + sim_idx if self.seed else None
            self.rng = np.random.default_rng(sim_seed)

            result = self.run_overload_test(scenario)
            results.append(result)
            tps_ratios.append(result.tps_ratio)

        tps_ratios = np.array(tps_ratios)
        mean_ratio = float(np.mean(tps_ratios))
        std_ratio = float(np.std(tps_ratios, ddof=1)) if len(tps_ratios) > 1 else 0.0

        # One-sample t-test: H0: mean < threshold, H1: mean >= threshold
        if std_ratio > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(tps_ratios, tps_threshold)
            # One-tailed test
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        else:
            t_stat = float('inf') if mean_ratio >= tps_threshold else float('-inf')
            p_value = 0.0 if mean_ratio >= tps_threshold else 1.0

        passed = mean_ratio >= tps_threshold and p_value < alpha

        return DegradationTestResult(
            passed=passed,
            mean_tps_ratio=mean_ratio,
            std_tps_ratio=std_ratio,
            tps_threshold=tps_threshold,
            load_multiplier=load_multiplier,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            individual_results=results,
        )

    def run_all_scenarios(self) -> Dict[str, OverloadResult]:
        """
        Run all predefined overload scenarios.

        Returns:
            Dictionary mapping scenario name to result
        """
        results = {}

        for scenario in OVERLOAD_SCENARIOS:
            logger.info(f"Running scenario: {scenario.name}")
            result = self.run_overload_test(scenario)
            results[scenario.name] = result

        return results


def simulate_overload_test(
    load_multiplier: float = 2.0,
    tps_threshold: float = 0.50,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> DegradationTestResult:
    """
    Run an overload graceful degradation test.

    Args:
        load_multiplier: Target load multiplier
        tps_threshold: Required TPS ratio
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        DegradationTestResult
    """
    tester = OverloadTester(seed=seed)

    return tester.test_graceful_degradation(
        load_multiplier=load_multiplier,
        tps_threshold=tps_threshold,
        n_simulations=n_simulations,
    )
