"""
Recovery Analyzer for SHAKTI-CHAIN Stress Testing (Domain 6).

Provides comprehensive recovery metrics and analysis across all stress tests.
Consolidates recovery measurement from demand shocks, supply shocks, and failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class RecoveryType(Enum):
    """Types of recovery events to analyze."""
    DEMAND_SHOCK = "demand_shock"
    SUPPLY_SHOCK = "supply_shock"
    VOLATILITY_SPIKE = "volatility_spike"
    OVERLOAD = "overload"
    PARTITION = "partition"
    BYZANTINE_FAULT = "byzantine_fault"


@dataclass
class RecoveryMetrics:
    """
    Comprehensive recovery metrics.

    Attributes:
        recovery_type: Type of stress event
        time_to_recovery: Rounds/seconds to reach recovery threshold
        recovery_rate: Rate of metric improvement per round
        overshoot: Maximum deviation below recovery threshold
        steady_state_value: Final stable value
        pre_event_value: Value before stress event
        recovery_threshold: Target recovery level
        full_recovery_achieved: Whether full recovery reached
        recovery_curve: Values during recovery period
    """
    recovery_type: RecoveryType
    time_to_recovery: float
    recovery_rate: float
    overshoot: float
    steady_state_value: float
    pre_event_value: float
    recovery_threshold: float
    full_recovery_achieved: bool
    recovery_curve: np.ndarray = field(default_factory=lambda: np.array([]))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "recovery_type": self.recovery_type.value,
            "time_to_recovery": float(self.time_to_recovery),
            "recovery_rate": float(self.recovery_rate),
            "overshoot": float(self.overshoot),
            "steady_state_value": float(self.steady_state_value),
            "pre_event_value": float(self.pre_event_value),
            "recovery_threshold": float(self.recovery_threshold),
            "full_recovery_achieved": self.full_recovery_achieved,
        }


@dataclass
class RecoveryAnalysisResult:
    """
    Result of comprehensive recovery analysis.

    Attributes:
        mean_recovery_time: Average recovery time
        std_recovery_time: Standard deviation
        median_recovery_time: Median recovery time
        p95_recovery_time: 95th percentile
        recovery_success_rate: Fraction achieving recovery
        mean_recovery_rate: Average recovery rate
        metrics_by_type: Metrics grouped by recovery type
        overall_resilience_score: Composite resilience metric
    """
    mean_recovery_time: float
    std_recovery_time: float
    median_recovery_time: float
    p95_recovery_time: float
    recovery_success_rate: float
    mean_recovery_rate: float
    metrics_by_type: Dict[str, List[RecoveryMetrics]]
    overall_resilience_score: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_recovery_time": float(self.mean_recovery_time),
            "std_recovery_time": float(self.std_recovery_time),
            "median_recovery_time": float(self.median_recovery_time),
            "p95_recovery_time": float(self.p95_recovery_time),
            "recovery_success_rate": float(self.recovery_success_rate),
            "mean_recovery_rate": float(self.mean_recovery_rate),
            "overall_resilience_score": float(self.overall_resilience_score),
            "num_metrics_by_type": {
                k: len(v) for k, v in self.metrics_by_type.items()
            },
        }


class RecoveryAnalyzer:
    """
    Analyze recovery dynamics across different stress scenarios.

    Provides unified recovery metrics and resilience scoring.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize recovery analyzer.

        Args:
            seed: Random seed
        """
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.metrics: List[RecoveryMetrics] = []

    def measure_recovery(
        self,
        series: np.ndarray,
        event_start: int,
        pre_event_value: float,
        recovery_threshold: float = 0.9,
        recovery_type: RecoveryType = RecoveryType.SUPPLY_SHOCK,
    ) -> RecoveryMetrics:
        """
        Measure recovery from a stress event.

        Args:
            series: Time series of the metric (e.g., efficiency)
            event_start: Index when stress event started
            pre_event_value: Value before stress event
            recovery_threshold: Fraction of pre-event value to reach
            recovery_type: Type of stress event

        Returns:
            RecoveryMetrics
        """
        if len(series) <= event_start:
            return RecoveryMetrics(
                recovery_type=recovery_type,
                time_to_recovery=float('inf'),
                recovery_rate=0.0,
                overshoot=0.0,
                steady_state_value=0.0,
                pre_event_value=pre_event_value,
                recovery_threshold=recovery_threshold,
                full_recovery_achieved=False,
            )

        recovery_series = series[event_start:]
        target_value = pre_event_value * recovery_threshold

        # Find time to recovery
        time_to_recovery = len(recovery_series)
        full_recovery = False

        for i, val in enumerate(recovery_series):
            if val >= target_value:
                time_to_recovery = i
                full_recovery = True
                break

        # Calculate recovery rate (linear approximation)
        if time_to_recovery > 0 and time_to_recovery < len(recovery_series):
            min_value = np.min(recovery_series[:time_to_recovery + 1])
            recovery_rate = (target_value - min_value) / time_to_recovery
        else:
            recovery_rate = 0.0

        # Calculate overshoot (maximum deviation below pre-event)
        overshoot = pre_event_value - np.min(recovery_series)

        # Steady state value (last 10% of series)
        window = max(1, len(recovery_series) // 10)
        steady_state_value = np.mean(recovery_series[-window:])

        return RecoveryMetrics(
            recovery_type=recovery_type,
            time_to_recovery=float(time_to_recovery),
            recovery_rate=float(recovery_rate),
            overshoot=float(overshoot),
            steady_state_value=float(steady_state_value),
            pre_event_value=float(pre_event_value),
            recovery_threshold=recovery_threshold,
            full_recovery_achieved=full_recovery,
            recovery_curve=recovery_series,
        )

    def add_metric(self, metric: RecoveryMetrics):
        """Add a recovery metric to the analyzer."""
        self.metrics.append(metric)

    def analyze_all(self) -> RecoveryAnalysisResult:
        """
        Analyze all collected recovery metrics.

        Returns:
            RecoveryAnalysisResult with aggregate statistics
        """
        if not self.metrics:
            return RecoveryAnalysisResult(
                mean_recovery_time=0.0,
                std_recovery_time=0.0,
                median_recovery_time=0.0,
                p95_recovery_time=0.0,
                recovery_success_rate=0.0,
                mean_recovery_rate=0.0,
                metrics_by_type={},
                overall_resilience_score=0.0,
            )

        # Extract recovery times (only from successful recoveries)
        recovery_times = [
            m.time_to_recovery for m in self.metrics
            if m.full_recovery_achieved
        ]

        if not recovery_times:
            recovery_times = [m.time_to_recovery for m in self.metrics]

        # Group by type
        metrics_by_type: Dict[str, List[RecoveryMetrics]] = {}
        for m in self.metrics:
            key = m.recovery_type.value
            if key not in metrics_by_type:
                metrics_by_type[key] = []
            metrics_by_type[key].append(m)

        # Calculate statistics
        mean_time = float(np.mean(recovery_times))
        std_time = float(np.std(recovery_times)) if len(recovery_times) > 1 else 0.0
        median_time = float(np.median(recovery_times))
        p95_time = float(np.percentile(recovery_times, 95))

        success_count = sum(1 for m in self.metrics if m.full_recovery_achieved)
        success_rate = success_count / len(self.metrics)

        recovery_rates = [m.recovery_rate for m in self.metrics]
        mean_rate = float(np.mean(recovery_rates))

        # Calculate resilience score
        resilience_score = self._calculate_resilience_score(
            success_rate=success_rate,
            mean_recovery_time=mean_time,
            mean_overshoot=float(np.mean([m.overshoot for m in self.metrics])),
        )

        return RecoveryAnalysisResult(
            mean_recovery_time=mean_time,
            std_recovery_time=std_time,
            median_recovery_time=median_time,
            p95_recovery_time=p95_time,
            recovery_success_rate=success_rate,
            mean_recovery_rate=mean_rate,
            metrics_by_type=metrics_by_type,
            overall_resilience_score=resilience_score,
        )

    def _calculate_resilience_score(
        self,
        success_rate: float,
        mean_recovery_time: float,
        mean_overshoot: float,
        max_acceptable_time: float = 20.0,
        max_acceptable_overshoot: float = 0.5,
    ) -> float:
        """
        Calculate composite resilience score.

        Score is 0-100 based on:
        - Recovery success rate (40%)
        - Recovery time relative to acceptable max (30%)
        - Overshoot relative to acceptable max (30%)

        Args:
            success_rate: Fraction of successful recoveries
            mean_recovery_time: Average recovery time
            mean_overshoot: Average overshoot

        Returns:
            Resilience score (0-100)
        """
        # Success component
        success_component = success_rate * 40

        # Time component (inverse: faster is better)
        if mean_recovery_time <= max_acceptable_time:
            time_ratio = 1 - (mean_recovery_time / max_acceptable_time)
        else:
            time_ratio = 0
        time_component = time_ratio * 30

        # Overshoot component (inverse: smaller is better)
        if mean_overshoot <= max_acceptable_overshoot:
            overshoot_ratio = 1 - (mean_overshoot / max_acceptable_overshoot)
        else:
            overshoot_ratio = 0
        overshoot_component = overshoot_ratio * 30

        return success_component + time_component + overshoot_component

    def compare_recovery_types(self) -> Dict[str, Dict[str, float]]:
        """
        Compare recovery performance across different stress types.

        Returns:
            Dictionary with statistics per recovery type
        """
        metrics_by_type = {}

        for m in self.metrics:
            key = m.recovery_type.value
            if key not in metrics_by_type:
                metrics_by_type[key] = []
            metrics_by_type[key].append(m)

        comparison = {}

        for recovery_type, type_metrics in metrics_by_type.items():
            times = [m.time_to_recovery for m in type_metrics]
            rates = [m.recovery_rate for m in type_metrics]
            success = sum(1 for m in type_metrics if m.full_recovery_achieved)

            comparison[recovery_type] = {
                "count": len(type_metrics),
                "mean_time": float(np.mean(times)),
                "std_time": float(np.std(times)) if len(times) > 1 else 0.0,
                "mean_rate": float(np.mean(rates)),
                "success_rate": success / len(type_metrics),
            }

        return comparison

    def clear(self):
        """Clear all collected metrics."""
        self.metrics = []


def analyze_recovery_from_series(
    efficiency_series: np.ndarray,
    shock_round: int,
    pre_shock_rounds: int = 10,
    recovery_type: RecoveryType = RecoveryType.SUPPLY_SHOCK,
) -> RecoveryMetrics:
    """
    Convenience function to analyze recovery from an efficiency series.

    Args:
        efficiency_series: Efficiency values over time
        shock_round: Round when shock occurred
        pre_shock_rounds: Rounds before shock to average for baseline
        recovery_type: Type of shock event

    Returns:
        RecoveryMetrics
    """
    analyzer = RecoveryAnalyzer()

    # Calculate pre-shock baseline
    start = max(0, shock_round - pre_shock_rounds)
    pre_shock_value = np.mean(efficiency_series[start:shock_round])

    return analyzer.measure_recovery(
        series=efficiency_series,
        event_start=shock_round,
        pre_event_value=pre_shock_value,
        recovery_threshold=0.9,
        recovery_type=recovery_type,
    )


def calculate_resilience_score(
    recovery_results: List[RecoveryMetrics],
) -> float:
    """
    Calculate overall resilience score from recovery results.

    Args:
        recovery_results: List of recovery metrics

    Returns:
        Resilience score (0-100)
    """
    analyzer = RecoveryAnalyzer()
    for result in recovery_results:
        analyzer.add_metric(result)

    analysis = analyzer.analyze_all()
    return analysis.overall_resilience_score
