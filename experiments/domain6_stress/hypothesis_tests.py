"""
Hypothesis Tests for SHAKTI-CHAIN Stress Testing Domain (Domain 6).

Implements statistical tests for all stress testing hypotheses:
- H6.1: Peak Demand Performance (One-sample t-test)
- H6.2: Supply Shock Recovery (One-sample t-test)
- H6.3: High Volatility Stability (Exact count)
- H6.4: Graceful Degradation (One-sample t-test)
- H6.5: Network Partition Tolerance (Binary outcome)
- H6.6: Byzantine Fault Tolerance (Exact binomial)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from .peak_demand_simulator import PeakDemandSimulator, PeakDemandTestResult, simulate_peak_demand_test
from .supply_shock_simulator import SupplyShockSimulator, RecoveryTestResult, simulate_supply_shock_test
from .volatility_injector import VolatilityInjector, StabilityTestResult, simulate_volatility_test
from .overload_tester import OverloadTester, DegradationTestResult, simulate_overload_test
from .partition_simulator import NetworkPartitionSimulator, PartitionToleranceResult, simulate_partition_test
from .byzantine_tester import ByzantineTester, ByzantineToleranceResult, ByzantineStrategy, simulate_byzantine_test

logger = logging.getLogger(__name__)


@dataclass
class StressHypothesisResult:
    """
    Result of a single hypothesis test.

    Attributes:
        hypothesis_id: Hypothesis identifier (e.g., "H6.1")
        description: Human-readable description
        test_type: Statistical test used
        passed: Whether hypothesis passed
        observed_value: Observed test statistic or metric
        threshold: Threshold for passing
        test_statistic: Statistical test statistic
        p_value: P-value
        confidence_interval: Optional CI
        effect_size: Optional effect size
        decision: Statistical decision description
        additional_info: Extra information
    """
    hypothesis_id: str
    description: str
    test_type: str
    passed: bool
    observed_value: float
    threshold: float
    test_statistic: float
    p_value: float
    confidence_interval: Optional[tuple] = None
    effect_size: Optional[float] = None
    decision: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "test_type": self.test_type,
            "passed": self.passed,
            "observed_value": float(self.observed_value),
            "threshold": float(self.threshold),
            "test_statistic": float(self.test_statistic),
            "p_value": float(self.p_value),
            "confidence_interval": self.confidence_interval,
            "effect_size": float(self.effect_size) if self.effect_size else None,
            "decision": self.decision,
        }


class StressHypothesisTester:
    """
    Run all hypothesis tests for Domain 6: Stress Testing.

    Hypotheses:
    - H6.1: Peak Demand - Efficiency >= 90% at 2.5x demand
    - H6.2: Supply Shock Recovery - Recovery within 10 rounds
    - H6.3: Volatility Stability - No failure at 3σ variance
    - H6.4: Graceful Degradation - TPS >= 50% at 2x load
    - H6.5: Partition Tolerance - No inconsistency after heal
    - H6.6: Byzantine Tolerance - Correct operation with 30% Byzantine
    """

    def __init__(
        self,
        alpha: float = 0.05,
        seed: Optional[int] = None,
    ):
        """
        Initialize hypothesis tester.

        Args:
            alpha: Significance level
            seed: Random seed
        """
        self.alpha = alpha
        self.seed = seed

    def test_h6_1_peak_demand(
        self,
        peak_result: Optional[PeakDemandTestResult] = None,
        demand_multiplier: float = 2.5,
        efficiency_threshold: float = 0.90,
        n_simulations: int = 30,
    ) -> StressHypothesisResult:
        """
        Test H6.1: Efficiency >= 90% at 2.5x demand.

        Uses one-sample t-test.
        H0: Mean efficiency < threshold
        H1: Mean efficiency >= threshold

        Args:
            peak_result: Pre-computed peak demand result
            demand_multiplier: Target demand multiplier
            efficiency_threshold: Required efficiency
            n_simulations: Number of simulations if computing

        Returns:
            StressHypothesisResult
        """
        if peak_result is None:
            peak_result = simulate_peak_demand_test(
                demand_multiplier=demand_multiplier,
                efficiency_threshold=efficiency_threshold,
                n_simulations=n_simulations,
                seed=self.seed,
            )

        passed = peak_result.passed

        return StressHypothesisResult(
            hypothesis_id="H6.1",
            description="Peak Demand Performance",
            test_type="One-Sample t-Test",
            passed=passed,
            observed_value=peak_result.mean_efficiency,
            threshold=efficiency_threshold,
            test_statistic=peak_result.t_statistic,
            p_value=peak_result.p_value,
            effect_size=peak_result.mean_efficiency - efficiency_threshold,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "demand_multiplier": demand_multiplier,
                "std_efficiency": peak_result.std_efficiency,
            },
        )

    def test_h6_2_supply_shock_recovery(
        self,
        recovery_result: Optional[RecoveryTestResult] = None,
        recovery_threshold: int = 10,
        n_simulations: int = 30,
    ) -> StressHypothesisResult:
        """
        Test H6.2: Recovery within 10 rounds.

        Uses one-sample t-test on recovery time.
        H0: Mean recovery time > threshold
        H1: Mean recovery time <= threshold

        Args:
            recovery_result: Pre-computed recovery result
            recovery_threshold: Maximum acceptable recovery rounds
            n_simulations: Number of simulations if computing

        Returns:
            StressHypothesisResult
        """
        if recovery_result is None:
            recovery_result = simulate_supply_shock_test(
                supply_drop_fraction=0.4,
                recovery_threshold=recovery_threshold,
                n_simulations=n_simulations,
                seed=self.seed,
            )

        passed = recovery_result.passed

        return StressHypothesisResult(
            hypothesis_id="H6.2",
            description="Supply Shock Recovery",
            test_type="One-Sample t-Test",
            passed=passed,
            observed_value=recovery_result.mean_recovery_time,
            threshold=float(recovery_threshold),
            test_statistic=recovery_result.t_statistic,
            p_value=recovery_result.p_value,
            effect_size=recovery_threshold - recovery_result.mean_recovery_time,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "recovery_rate": recovery_result.recovery_rate,
                "std_recovery_time": recovery_result.std_recovery_time,
            },
        )

    def test_h6_3_volatility_stability(
        self,
        stability_result: Optional[StabilityTestResult] = None,
        variance_multiplier: float = 3.0,
        n_simulations: int = 30,
    ) -> StressHypothesisResult:
        """
        Test H6.3: No market failure at 3σ variance.

        Uses exact count (failure count = 0 for pass).
        H0: Failure occurs
        H1: No failure

        Args:
            stability_result: Pre-computed stability result
            variance_multiplier: Target variance multiplier
            n_simulations: Number of simulations if computing

        Returns:
            StressHypothesisResult
        """
        if stability_result is None:
            stability_result = simulate_volatility_test(
                variance_multiplier=variance_multiplier,
                n_simulations=n_simulations,
                seed=self.seed,
            )

        passed = stability_result.passed

        # Calculate p-value using exact binomial (probability of 0 failures)
        # Under H0, assume some base failure rate (e.g., 0.1)
        assumed_failure_rate = 0.1
        p_value = scipy_stats.binom.pmf(
            stability_result.failure_count,
            stability_result.total_simulations,
            assumed_failure_rate,
        )

        return StressHypothesisResult(
            hypothesis_id="H6.3",
            description="High Volatility Stability",
            test_type="Exact Count",
            passed=passed,
            observed_value=float(stability_result.failure_count),
            threshold=0.0,  # Zero failures required
            test_statistic=float(stability_result.failure_count),
            p_value=float(p_value),
            effect_size=stability_result.failure_rate,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "variance_multiplier": variance_multiplier,
                "mean_consecutive_zeros": stability_result.mean_consecutive_zeros,
            },
        )

    def test_h6_4_graceful_degradation(
        self,
        degradation_result: Optional[DegradationTestResult] = None,
        load_multiplier: float = 2.0,
        tps_threshold: float = 0.50,
        n_simulations: int = 30,
    ) -> StressHypothesisResult:
        """
        Test H6.4: TPS >= 50% at 2x load.

        Uses one-sample t-test.
        H0: Mean TPS ratio < threshold
        H1: Mean TPS ratio >= threshold

        Args:
            degradation_result: Pre-computed degradation result
            load_multiplier: Target load multiplier
            tps_threshold: Required TPS ratio
            n_simulations: Number of simulations if computing

        Returns:
            StressHypothesisResult
        """
        if degradation_result is None:
            degradation_result = simulate_overload_test(
                load_multiplier=load_multiplier,
                tps_threshold=tps_threshold,
                n_simulations=n_simulations,
                seed=self.seed,
            )

        passed = degradation_result.passed

        return StressHypothesisResult(
            hypothesis_id="H6.4",
            description="Graceful Degradation",
            test_type="One-Sample t-Test",
            passed=passed,
            observed_value=degradation_result.mean_tps_ratio,
            threshold=tps_threshold,
            test_statistic=degradation_result.t_statistic,
            p_value=degradation_result.p_value,
            effect_size=degradation_result.mean_tps_ratio - tps_threshold,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "load_multiplier": load_multiplier,
                "std_tps_ratio": degradation_result.std_tps_ratio,
            },
        )

    def test_h6_5_partition_tolerance(
        self,
        partition_result: Optional[PartitionToleranceResult] = None,
        n_simulations: int = 30,
    ) -> StressHypothesisResult:
        """
        Test H6.5: No inconsistency after partition heal.

        Binary outcome test.
        H0: Inconsistency occurs
        H1: No inconsistency

        Args:
            partition_result: Pre-computed partition result
            n_simulations: Number of simulations if computing

        Returns:
            StressHypothesisResult
        """
        if partition_result is None:
            partition_result = simulate_partition_test(
                partition_ratio=0.5,
                duration_seconds=30.0,
                n_simulations=n_simulations,
                seed=self.seed,
            )

        passed = partition_result.passed

        # Binary outcome: p-value is just the inconsistency rate
        p_value = partition_result.inconsistency_count / partition_result.total_simulations

        return StressHypothesisResult(
            hypothesis_id="H6.5",
            description="Network Partition Tolerance",
            test_type="Binary Outcome",
            passed=passed,
            observed_value=float(partition_result.inconsistency_count),
            threshold=0.0,  # Zero inconsistencies required
            test_statistic=float(partition_result.inconsistency_count),
            p_value=float(p_value),
            effect_size=partition_result.mean_reconciliation_time,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "mean_reconciliation_time": partition_result.mean_reconciliation_time,
                "mean_conflicts": partition_result.mean_conflicts,
            },
        )

    def test_h6_6_byzantine_tolerance(
        self,
        byzantine_result: Optional[ByzantineToleranceResult] = None,
        byzantine_fraction: float = 0.30,
        n_simulations: int = 30,
    ) -> StressHypothesisResult:
        """
        Test H6.6: Correct operation with 30% Byzantine.

        Uses exact binomial test.
        H0: Failure with < 30% Byzantine
        H1: Correct operation with 30% Byzantine

        Args:
            byzantine_result: Pre-computed Byzantine result
            byzantine_fraction: Byzantine node fraction to test
            n_simulations: Number of simulations if computing

        Returns:
            StressHypothesisResult
        """
        if byzantine_result is None:
            byzantine_result = simulate_byzantine_test(
                byzantine_fraction=byzantine_fraction,
                strategy=ByzantineStrategy.EQUIVOCATE,
                n_simulations=n_simulations,
                seed=self.seed,
            )

        passed = byzantine_result.passed

        # Exact binomial p-value
        # Under H0, assume some base success rate needed
        min_success_rate = 0.95
        p_value = scipy_stats.binom.sf(
            byzantine_result.success_count - 1,
            byzantine_result.total_simulations,
            min_success_rate,
        )

        return StressHypothesisResult(
            hypothesis_id="H6.6",
            description="Byzantine Fault Tolerance",
            test_type="Exact Binomial",
            passed=passed,
            observed_value=byzantine_result.success_rate,
            threshold=min_success_rate,
            test_statistic=float(byzantine_result.success_count),
            p_value=float(p_value),
            effect_size=byzantine_result.mean_agreement_rate,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "byzantine_fraction": byzantine_fraction,
                "success_count": byzantine_result.success_count,
                "total_simulations": byzantine_result.total_simulations,
            },
        )

    def run_all_tests(
        self,
        peak_result: Optional[PeakDemandTestResult] = None,
        recovery_result: Optional[RecoveryTestResult] = None,
        stability_result: Optional[StabilityTestResult] = None,
        degradation_result: Optional[DegradationTestResult] = None,
        partition_result: Optional[PartitionToleranceResult] = None,
        byzantine_result: Optional[ByzantineToleranceResult] = None,
    ) -> Dict[str, StressHypothesisResult]:
        """
        Run all hypothesis tests.

        Args:
            peak_result: Pre-computed peak demand result
            recovery_result: Pre-computed recovery result
            stability_result: Pre-computed stability result
            degradation_result: Pre-computed degradation result
            partition_result: Pre-computed partition result
            byzantine_result: Pre-computed Byzantine result

        Returns:
            Dictionary mapping hypothesis ID to result
        """
        results = {}

        logger.info("Testing H6.1: Peak Demand Performance...")
        results["H6.1"] = self.test_h6_1_peak_demand(peak_result)

        logger.info("Testing H6.2: Supply Shock Recovery...")
        results["H6.2"] = self.test_h6_2_supply_shock_recovery(recovery_result)

        logger.info("Testing H6.3: High Volatility Stability...")
        results["H6.3"] = self.test_h6_3_volatility_stability(stability_result)

        logger.info("Testing H6.4: Graceful Degradation...")
        results["H6.4"] = self.test_h6_4_graceful_degradation(degradation_result)

        logger.info("Testing H6.5: Network Partition Tolerance...")
        results["H6.5"] = self.test_h6_5_partition_tolerance(partition_result)

        logger.info("Testing H6.6: Byzantine Fault Tolerance...")
        results["H6.6"] = self.test_h6_6_byzantine_tolerance(byzantine_result)

        return results

    def generate_summary(
        self,
        results: Dict[str, StressHypothesisResult],
    ) -> str:
        """
        Generate summary of hypothesis test results.

        Args:
            results: Dictionary of hypothesis results

        Returns:
            Summary string
        """
        passed = sum(1 for r in results.values() if r.passed)
        total = len(results)

        lines = [
            "Domain 6: Stress Testing Hypothesis Test Summary",
            "=" * 50,
            f"Passed: {passed}/{total}",
            "",
            "Individual Results:",
        ]

        for h_id in sorted(results.keys()):
            result = results[h_id]
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  {h_id} ({result.description}): {status}")
            lines.append(f"      Observed: {result.observed_value:.4f}, Threshold: {result.threshold:.4f}")
            lines.append(f"      p-value: {result.p_value:.6f}")

        return "\n".join(lines)
