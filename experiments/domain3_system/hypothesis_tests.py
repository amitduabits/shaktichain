"""
Hypothesis Tests for System Performance (Domain 3).

Implements statistical tests for validating SHAKTI-CHAIN system performance:
- H3.1: TPS >= 10,000
- H3.2: P95 latency < 100ms
- H3.3: 99.9% settlement finality within 30 seconds
- H3.4: O(n log n) or better scaling
- H3.5: Mean gas cost < 1 INR per transaction
- H3.6: System availability >= 99.9%
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from .throughput_measurer import ThroughputStatistics
from .latency_profiler import LatencyStatistics, bootstrap_percentile_ci
from .scalability_analyzer import ScalabilityAnalysisResult
from .gas_cost_tracker import GasCostStatistics
from .availability_monitor import AvailabilityMetrics, SettlementFinalityMetrics


@dataclass
class SystemHypothesisResult:
    """
    Result of a system performance hypothesis test.

    Attributes:
        hypothesis_id: Unique identifier (e.g., 'H3.1')
        description: Human-readable description
        null_hypothesis: H0 statement
        alternative_hypothesis: H1 statement
        test_name: Statistical test used
        test_statistic: Value of test statistic
        p_value: Probability under null hypothesis
        effect_size: Standardized effect size
        confidence_interval: CI for the parameter of interest
        sample_size: Number of observations
        decision: 'reject_null' or 'fail_to_reject_null'
        conclusion: Human-readable conclusion
        observed_value: The observed metric value
        threshold: The threshold being tested against
        assumptions_met: Dictionary of assumption checks
        additional_info: Extra information specific to the test
    """
    hypothesis_id: str
    description: str
    null_hypothesis: str
    alternative_hypothesis: str
    test_name: str
    test_statistic: float
    p_value: float
    effect_size: float
    confidence_interval: Tuple[float, float]
    sample_size: int
    decision: str
    conclusion: str
    observed_value: float
    threshold: float
    assumptions_met: Dict[str, bool] = field(default_factory=dict)
    additional_info: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "test_name": self.test_name,
            "test_statistic": float(self.test_statistic) if not np.isnan(self.test_statistic) else None,
            "p_value": float(self.p_value) if not np.isnan(self.p_value) else None,
            "effect_size": float(self.effect_size) if not np.isnan(self.effect_size) else None,
            "confidence_interval": [
                float(self.confidence_interval[0]) if not np.isnan(self.confidence_interval[0]) else None,
                float(self.confidence_interval[1]) if not np.isnan(self.confidence_interval[1]) else None,
            ],
            "sample_size": self.sample_size,
            "decision": self.decision,
            "conclusion": self.conclusion,
            "observed_value": float(self.observed_value),
            "threshold": float(self.threshold),
            "assumptions_met": self.assumptions_met,
            "additional_info": self.additional_info,
        }

    @property
    def passed(self) -> bool:
        """Check if hypothesis test supports the performance claim."""
        return self.decision == "reject_null"


class SystemHypothesisTester:
    """
    Statistical hypothesis tester for SHAKTI-CHAIN system performance.

    Performs rigorous statistical tests for throughput, latency,
    scalability, cost, and availability claims.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        bootstrap_iterations: int = 10000,
    ):
        """
        Initialize the hypothesis tester.

        Args:
            alpha: Significance level (default 0.05)
            bootstrap_iterations: Number of bootstrap resamples
        """
        self.alpha = alpha
        self.bootstrap_iterations = bootstrap_iterations

    def run_all_tests(
        self,
        tps_samples: np.ndarray,
        latency_samples: np.ndarray,
        finality_times: np.ndarray,
        scalability_result: ScalabilityAnalysisResult,
        gas_costs: np.ndarray,
        availability_metrics: AvailabilityMetrics,
    ) -> Dict[str, SystemHypothesisResult]:
        """
        Run all system performance hypothesis tests.

        Args:
            tps_samples: Array of TPS measurements
            latency_samples: Array of latency measurements (ms)
            finality_times: Array of settlement finality times (seconds)
            scalability_result: Result from scalability analysis
            gas_costs: Array of transaction costs (INR)
            availability_metrics: Availability metrics

        Returns:
            Dictionary mapping hypothesis ID to SystemHypothesisResult
        """
        results = {}

        # H3.1: TPS >= 10,000
        results["H3.1"] = self.test_throughput(tps_samples)

        # H3.2: P95 latency < 100ms
        results["H3.2"] = self.test_latency_p95(latency_samples)

        # H3.3: 99.9% finality within 30s
        results["H3.3"] = self.test_settlement_finality(finality_times)

        # H3.4: O(n log n) or better scaling
        results["H3.4"] = self.test_scalability(scalability_result)

        # H3.5: Mean gas cost < 1 INR
        results["H3.5"] = self.test_gas_cost(gas_costs)

        # H3.6: Availability >= 99.9%
        results["H3.6"] = self.test_availability(availability_metrics)

        return results

    def test_throughput(
        self,
        tps_samples: np.ndarray,
        threshold: float = 10000.0,
    ) -> SystemHypothesisResult:
        """
        Test H3.1: TPS >= 10,000.

        H0: mu(TPS) < 10,000
        H1: mu(TPS) >= 10,000

        Uses one-sample t-test (one-tailed, greater).

        Args:
            tps_samples: Array of TPS measurements
            threshold: TPS threshold (default 10,000)

        Returns:
            SystemHypothesisResult
        """
        n = len(tps_samples)
        if n == 0:
            return self._empty_result("H3.1", "TPS >= 10,000", threshold)

        mean_tps = np.mean(tps_samples)
        std_tps = np.std(tps_samples, ddof=1) if n > 1 else 0

        # One-sample t-test (one-tailed, greater)
        t_stat, two_tail_p = stats.ttest_1samp(tps_samples, threshold)
        p_value = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2

        # Effect size (Cohen's d)
        effect_size = (mean_tps - threshold) / std_tps if std_tps > 0 else float('inf')

        # Bootstrap CI
        ci = self._bootstrap_ci(tps_samples, np.mean)

        decision = "reject_null" if p_value < self.alpha and mean_tps >= threshold else "fail_to_reject_null"

        conclusion = (
            f"Mean TPS = {mean_tps:,.0f} (95% CI: [{ci[0]:,.0f}, {ci[1]:,.0f}]). "
            f"{'Meets' if decision == 'reject_null' else 'Does not meet'} {threshold:,.0f} TPS threshold "
            f"(p={p_value:.4f}, d={effect_size:.3f})"
        )

        return SystemHypothesisResult(
            hypothesis_id="H3.1",
            description="TPS >= 10,000",
            null_hypothesis="mu(TPS) < 10,000",
            alternative_hypothesis="mu(TPS) >= 10,000",
            test_name="One-sample t-test (one-tailed, greater)",
            test_statistic=float(t_stat),
            p_value=float(p_value),
            effect_size=float(effect_size),
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            observed_value=float(mean_tps),
            threshold=threshold,
            additional_info={
                "std_tps": float(std_tps),
                "min_tps": float(np.min(tps_samples)),
                "max_tps": float(np.max(tps_samples)),
                "median_tps": float(np.median(tps_samples)),
            },
        )

    def test_latency_p95(
        self,
        latency_samples: np.ndarray,
        threshold: float = 100.0,
    ) -> SystemHypothesisResult:
        """
        Test H3.2: P95 latency < 100ms.

        H0: P95(latency) >= 100ms
        H1: P95(latency) < 100ms

        Uses bootstrap CI for P95.

        Args:
            latency_samples: Array of latency measurements in ms
            threshold: P95 threshold in ms (default 100)

        Returns:
            SystemHypothesisResult
        """
        n = len(latency_samples)
        if n == 0:
            return self._empty_result("H3.2", "P95 latency < 100ms", threshold)

        p95 = float(np.percentile(latency_samples, 95))

        # Bootstrap CI for P95
        p95_estimate, ci_lower, ci_upper = bootstrap_percentile_ci(
            latency_samples,
            percentile=95,
            n_bootstrap=self.bootstrap_iterations,
            confidence=0.95,
        )

        # Decision based on upper CI bound
        decision = "reject_null" if ci_upper < threshold else "fail_to_reject_null"

        # Calculate p-value using bootstrap
        bootstrap_p95s = self._bootstrap_statistic(
            latency_samples,
            lambda x: np.percentile(x, 95),
            self.bootstrap_iterations,
        )
        p_value = np.mean(bootstrap_p95s >= threshold)

        # Effect size: how far below threshold
        mean_latency = np.mean(latency_samples)
        std_latency = np.std(latency_samples, ddof=1)
        effect_size = (threshold - p95) / std_latency if std_latency > 0 else float('inf')

        conclusion = (
            f"P95 latency = {p95:.2f}ms (95% CI: [{ci_lower:.2f}ms, {ci_upper:.2f}ms]). "
            f"{'Meets' if decision == 'reject_null' else 'Does not meet'} {threshold:.0f}ms threshold "
            f"(p={p_value:.4f})"
        )

        return SystemHypothesisResult(
            hypothesis_id="H3.2",
            description="P95 latency < 100ms",
            null_hypothesis="P95(latency) >= 100ms",
            alternative_hypothesis="P95(latency) < 100ms",
            test_name="Bootstrap CI for P95",
            test_statistic=float(p95),
            p_value=float(p_value),
            effect_size=float(effect_size),
            confidence_interval=(ci_lower, ci_upper),
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            observed_value=float(p95),
            threshold=threshold,
            additional_info={
                "mean_latency_ms": float(mean_latency),
                "median_latency_ms": float(np.median(latency_samples)),
                "p50_ms": float(np.percentile(latency_samples, 50)),
                "p90_ms": float(np.percentile(latency_samples, 90)),
                "p99_ms": float(np.percentile(latency_samples, 99)),
                "max_ms": float(np.max(latency_samples)),
            },
        )

    def test_settlement_finality(
        self,
        finality_times: np.ndarray,
        target_seconds: float = 30.0,
        required_rate: float = 0.999,
    ) -> SystemHypothesisResult:
        """
        Test H3.3: 99.9% settlement finality within 30 seconds.

        H0: P(finality <= 30s) < 0.999
        H1: P(finality <= 30s) >= 0.999

        Uses exact binomial test.

        Args:
            finality_times: Array of finality times in seconds
            target_seconds: Target finality time (default 30)
            required_rate: Required success rate (default 0.999)

        Returns:
            SystemHypothesisResult
        """
        n = len(finality_times)
        if n == 0:
            return self._empty_result("H3.3", "99.9% finality within 30s", required_rate * 100)

        # Count successes
        successes = int(np.sum(finality_times <= target_seconds))
        observed_rate = successes / n

        # Exact binomial test
        # H0: p < 0.999, H1: p >= 0.999
        # Use binom_test with alternative='greater'
        p_value = stats.binomtest(successes, n, required_rate, alternative='greater').pvalue

        # Wilson score interval for proportion
        ci = self._wilson_ci(successes, n)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        # Effect size (Cohen's h for proportions)
        effect_size = 2 * np.arcsin(np.sqrt(observed_rate)) - 2 * np.arcsin(np.sqrt(required_rate))

        conclusion = (
            f"Finality rate = {observed_rate*100:.3f}% ({successes}/{n} within {target_seconds}s). "
            f"95% CI: [{ci[0]*100:.3f}%, {ci[1]*100:.3f}%]. "
            f"{'Meets' if decision == 'reject_null' else 'Does not meet'} {required_rate*100:.1f}% threshold "
            f"(p={p_value:.4f})"
        )

        return SystemHypothesisResult(
            hypothesis_id="H3.3",
            description="99.9% finality within 30 seconds",
            null_hypothesis="P(finality <= 30s) < 0.999",
            alternative_hypothesis="P(finality <= 30s) >= 0.999",
            test_name="Exact binomial test",
            test_statistic=float(successes),
            p_value=float(p_value),
            effect_size=float(effect_size),
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            observed_value=float(observed_rate * 100),
            threshold=float(required_rate * 100),
            additional_info={
                "successes": successes,
                "failures": n - successes,
                "mean_finality_s": float(np.mean(finality_times)),
                "p95_finality_s": float(np.percentile(finality_times, 95)),
                "max_finality_s": float(np.max(finality_times)),
            },
        )

    def test_scalability(
        self,
        scalability_result: ScalabilityAnalysisResult,
    ) -> SystemHypothesisResult:
        """
        Test H3.4: O(n log n) or better scaling.

        H0: Complexity is worse than O(n log n)
        H1: Complexity is O(n log n) or better

        Uses regression model comparison (F-test).

        Args:
            scalability_result: Result from scalability analysis

        Returns:
            SystemHypothesisResult
        """
        # Get model fit results
        model_fits = scalability_result.model_fits
        best_model = scalability_result.best_model
        is_acceptable = scalability_result.is_acceptable

        # Determine if O(n log n) or better
        acceptable_models = ["O(1)", "O(log n)", "O(sqrt(n))", "O(n)", "O(n log n)"]

        # Get R-squared values
        r_squared_values = {
            name: fit.r_squared
            for name, fit in model_fits.items()
            if not np.isinf(fit.r_squared)
        }

        # Get best acceptable model
        best_acceptable = None
        best_acceptable_r2 = -np.inf
        for model in acceptable_models:
            if model in r_squared_values:
                if r_squared_values[model] > best_acceptable_r2:
                    best_acceptable_r2 = r_squared_values[model]
                    best_acceptable = model

        # Check if O(n^2) provides significantly better fit
        quadratic_r2 = r_squared_values.get("O(n^2)", -np.inf)

        # F-test for nested models (n log n vs n^2)
        f_test_key = "O(n log n) vs O(n^2)"
        f_test = scalability_result.f_test_results.get(f_test_key, {})
        f_test_p = f_test.get("p_value", 1.0)
        prefers_quadratic = f_test.get("prefer_complex", False)

        # Decision
        if is_acceptable and not prefers_quadratic:
            decision = "reject_null"
            p_value = 1 - best_acceptable_r2 if best_acceptable_r2 > 0 else 1.0
        else:
            decision = "fail_to_reject_null"
            p_value = f_test_p if prefers_quadratic else 0.5

        conclusion = (
            f"Best fitting model: {best_model}. "
            f"Complexity {'is' if is_acceptable else 'is NOT'} O(n log n) or better. "
            f"R^2 = {r_squared_values.get(best_model, 0):.4f}"
        )

        return SystemHypothesisResult(
            hypothesis_id="H3.4",
            description="O(n log n) or better scaling",
            null_hypothesis="Complexity is worse than O(n log n)",
            alternative_hypothesis="Complexity is O(n log n) or better",
            test_name="Regression model comparison (F-test)",
            test_statistic=float(best_acceptable_r2) if best_acceptable_r2 > -np.inf else np.nan,
            p_value=float(p_value),
            effect_size=float(best_acceptable_r2) if best_acceptable_r2 > -np.inf else 0,
            confidence_interval=(0.0, 1.0),
            sample_size=len(scalability_result.measurements),
            decision=decision,
            conclusion=conclusion,
            observed_value=0 if is_acceptable else 1,  # 0 = acceptable, 1 = not
            threshold=0,
            additional_info={
                "best_model": best_model,
                "r_squared_values": {k: float(v) for k, v in r_squared_values.items()},
                "f_test_results": scalability_result.f_test_results,
                "is_acceptable": is_acceptable,
            },
        )

    def test_gas_cost(
        self,
        gas_costs: np.ndarray,
        threshold: float = 1.0,
    ) -> SystemHypothesisResult:
        """
        Test H3.5: Mean gas cost < 1 INR per transaction.

        H0: mu(cost) >= 1 INR
        H1: mu(cost) < 1 INR

        Uses one-sample t-test (one-tailed, less).

        Args:
            gas_costs: Array of transaction costs in INR
            threshold: Cost threshold in INR (default 1.0)

        Returns:
            SystemHypothesisResult
        """
        n = len(gas_costs)
        if n == 0:
            return self._empty_result("H3.5", "Gas cost < 1 INR", threshold)

        mean_cost = np.mean(gas_costs)
        std_cost = np.std(gas_costs, ddof=1) if n > 1 else 0

        # One-sample t-test (one-tailed, less)
        t_stat, two_tail_p = stats.ttest_1samp(gas_costs, threshold)
        p_value = two_tail_p / 2 if t_stat < 0 else 1 - two_tail_p / 2

        # Effect size (Cohen's d)
        effect_size = (threshold - mean_cost) / std_cost if std_cost > 0 else float('inf')

        # Bootstrap CI
        ci = self._bootstrap_ci(gas_costs, np.mean)

        decision = "reject_null" if p_value < self.alpha and mean_cost < threshold else "fail_to_reject_null"

        conclusion = (
            f"Mean gas cost = {mean_cost:.4f} INR (95% CI: [{ci[0]:.4f}, {ci[1]:.4f}] INR). "
            f"{'Below' if decision == 'reject_null' else 'Not below'} {threshold:.2f} INR threshold "
            f"(p={p_value:.4f}, d={effect_size:.3f})"
        )

        return SystemHypothesisResult(
            hypothesis_id="H3.5",
            description="Mean gas cost < 1 INR per transaction",
            null_hypothesis="mu(cost) >= 1 INR",
            alternative_hypothesis="mu(cost) < 1 INR",
            test_name="One-sample t-test (one-tailed, less)",
            test_statistic=float(t_stat),
            p_value=float(p_value),
            effect_size=float(effect_size),
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            observed_value=float(mean_cost),
            threshold=threshold,
            additional_info={
                "std_cost": float(std_cost),
                "median_cost": float(np.median(gas_costs)),
                "max_cost": float(np.max(gas_costs)),
                "total_cost": float(np.sum(gas_costs)),
            },
        )

    def test_availability(
        self,
        availability_metrics: AvailabilityMetrics,
        threshold: float = 99.9,
    ) -> SystemHypothesisResult:
        """
        Test H3.6: System availability >= 99.9%.

        H0: Availability < 99.9%
        H1: Availability >= 99.9%

        Uses exact binomial test on downtime events.

        Args:
            availability_metrics: AvailabilityMetrics object
            threshold: Availability threshold percentage (default 99.9)

        Returns:
            SystemHypothesisResult
        """
        observed_availability = availability_metrics.availability_pct
        total_seconds = availability_metrics.monitoring_period_seconds
        downtime_seconds = availability_metrics.downtime_seconds
        n_events = availability_metrics.num_downtime_events

        # Convert to proportion for binomial test
        # Total "trials" = total_seconds, "successes" = uptime_seconds
        # But for large n, use normal approximation

        # Calculate proportion
        uptime_seconds = total_seconds - downtime_seconds
        observed_prop = uptime_seconds / total_seconds if total_seconds > 0 else 1.0
        threshold_prop = threshold / 100

        # For large sample (seconds), use z-test approximation
        # Or use exact binomial on minute/hour basis
        n_hours = int(total_seconds / 3600)
        if n_hours < 1:
            n_hours = 1

        # Approximate downtime hours
        downtime_hours = downtime_seconds / 3600
        uptime_hours = n_hours - downtime_hours

        # Binomial test: uptime_hours out of n_hours, testing against threshold_prop
        if n_hours > 0:
            # One-proportion z-test
            p0 = threshold_prop
            p_hat = observed_prop
            se = np.sqrt(p0 * (1 - p0) / n_hours)
            z_stat = (p_hat - p0) / se if se > 0 else 0
            p_value = 1 - stats.norm.cdf(z_stat)
        else:
            z_stat = 0
            p_value = 0.5

        # Wilson score CI for proportion
        ci = self._wilson_ci(int(uptime_hours), n_hours)
        ci = (ci[0] * 100, ci[1] * 100)  # Convert to percentage

        decision = "reject_null" if p_value < self.alpha and observed_availability >= threshold else "fail_to_reject_null"

        # Effect size (Cohen's h)
        effect_size = 2 * np.arcsin(np.sqrt(observed_prop)) - 2 * np.arcsin(np.sqrt(threshold_prop))

        conclusion = (
            f"Availability = {observed_availability:.3f}% "
            f"(95% CI: [{ci[0]:.3f}%, {ci[1]:.3f}%]). "
            f"{'Meets' if decision == 'reject_null' else 'Does not meet'} {threshold:.1f}% SLA "
            f"(p={p_value:.4f}, {n_events} downtime events)"
        )

        return SystemHypothesisResult(
            hypothesis_id="H3.6",
            description="System availability >= 99.9%",
            null_hypothesis="Availability < 99.9%",
            alternative_hypothesis="Availability >= 99.9%",
            test_name="One-proportion z-test",
            test_statistic=float(z_stat),
            p_value=float(p_value),
            effect_size=float(effect_size),
            confidence_interval=ci,
            sample_size=n_hours,
            decision=decision,
            conclusion=conclusion,
            observed_value=float(observed_availability),
            threshold=threshold,
            additional_info={
                "uptime_seconds": float(uptime_seconds),
                "downtime_seconds": float(downtime_seconds),
                "monitoring_hours": float(total_seconds / 3600),
                "num_downtime_events": n_events,
                "mtbf_hours": float(availability_metrics.mtbf_seconds / 3600),
                "mttr_minutes": float(availability_metrics.mttr_seconds / 60),
            },
        )

    def _bootstrap_ci(
        self,
        data: np.ndarray,
        statistic_func,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Compute bootstrap confidence interval."""
        n = len(data)
        if n == 0:
            return (0.0, 0.0)
        if n == 1:
            return (float(data[0]), float(data[0]))

        bootstrap_stats = np.empty(self.bootstrap_iterations)

        for i in range(self.bootstrap_iterations):
            resample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats[i] = statistic_func(resample)

        alpha = 1 - confidence
        lower = np.percentile(bootstrap_stats, 100 * alpha / 2)
        upper = np.percentile(bootstrap_stats, 100 * (1 - alpha / 2))

        return (float(lower), float(upper))

    def _bootstrap_statistic(
        self,
        data: np.ndarray,
        statistic_func,
        n_iterations: int,
    ) -> np.ndarray:
        """Generate bootstrap distribution of a statistic."""
        n = len(data)
        bootstrap_stats = np.empty(n_iterations)

        for i in range(n_iterations):
            resample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats[i] = statistic_func(resample)

        return bootstrap_stats

    def _wilson_ci(
        self,
        successes: int,
        n: int,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Calculate Wilson score confidence interval for proportion."""
        if n == 0:
            return (0.0, 1.0)

        p_hat = successes / n
        z = stats.norm.ppf(1 - (1 - confidence) / 2)

        denominator = 1 + z**2 / n
        center = (p_hat + z**2 / (2 * n)) / denominator
        margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denominator

        lower = max(0, center - margin)
        upper = min(1, center + margin)

        return (float(lower), float(upper))

    def _empty_result(
        self,
        hypothesis_id: str,
        description: str,
        threshold: float,
    ) -> SystemHypothesisResult:
        """Create an empty result for when there's no data."""
        return SystemHypothesisResult(
            hypothesis_id=hypothesis_id,
            description=description,
            null_hypothesis="",
            alternative_hypothesis="",
            test_name="No test (insufficient data)",
            test_statistic=np.nan,
            p_value=np.nan,
            effect_size=np.nan,
            confidence_interval=(np.nan, np.nan),
            sample_size=0,
            decision="fail_to_reject_null",
            conclusion="Insufficient data for hypothesis test",
            observed_value=0,
            threshold=threshold,
            assumptions_met={},
        )

    def generate_summary_report(
        self,
        results: Dict[str, SystemHypothesisResult],
    ) -> str:
        """Generate a human-readable summary report."""
        lines = [
            "=" * 80,
            "SYSTEM PERFORMANCE HYPOTHESIS TESTS - SUMMARY REPORT",
            "=" * 80,
            "",
            f"Significance Level: alpha = {self.alpha}",
            "",
            "-" * 80,
        ]

        passed = 0
        total = len(results)

        for h_id in sorted(results.keys()):
            result = results[h_id]
            status = "PASS" if result.passed else "FAIL"
            passed += 1 if result.passed else 0

            p_str = f"{result.p_value:.6f}" if not np.isnan(result.p_value) else "N/A"
            stat_str = f"{result.test_statistic:.4f}" if not np.isnan(result.test_statistic) else "N/A"

            lines.extend([
                f"\n{h_id}: {result.description}",
                f"  Status: {status}",
                f"  Test: {result.test_name}",
                f"  Observed: {result.observed_value:.4f}, Threshold: {result.threshold:.4f}",
                f"  Statistic: {stat_str}, p-value: {p_str}",
                f"  Sample Size: {result.sample_size}",
                f"  Conclusion: {result.conclusion}",
            ])

        pct = (passed / total * 100) if total > 0 else 0
        lines.extend([
            "",
            "-" * 80,
            f"OVERALL: {passed}/{total} hypotheses supported ({pct:.1f}%)",
            "=" * 80,
        ])

        return "\n".join(lines)
