"""
Hypothesis Tests for SHAKTI-CHAIN Token Economics (Domain 4).

Implements statistical tests for token economics validation:
- H4.1: Supply CV < 5% over 30-day periods (Bootstrap CI)
- H4.2: |Mint_rate - Burn_rate| / Avg_rate < 10% (Paired t-test)
- H4.3: |V_actual - V_predicted| / V_predicted < 20% (Paired t-test)
- H4.4: Redemption rate = 1.0 +/- 1% (One-sample t-test)
- H4.5: Annual inflation < 10% (One-sample t-test)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

from .token_supply_tracker import TokenSupplyTracker, RollingStabilityResult
from .mint_burn_analyzer import MintBurnAnalyzer, EquilibriumTestResult
from .velocity_calculator import VelocityCalculator, VelocityTestResult
from .peg_stability_tester import PegStabilityTester, PegTestResult
from .inflation_monitor import InflationMonitor, InflationTestResult

logger = logging.getLogger(__name__)


@dataclass
class TokenHypothesisResult:
    """
    Result of a token economics hypothesis test.

    Attributes:
        hypothesis_id: Identifier (H4.1, H4.2, etc.)
        description: Hypothesis description
        null_hypothesis: H0 statement
        alternative_hypothesis: H1 statement
        test_statistic: Test statistic value
        p_value: P-value
        passed: Whether hypothesis is supported
        decision: 'reject_null' or 'fail_to_reject'
        effect_size: Effect size if applicable
        confidence_interval: (lower, upper) bounds
        sample_size: Number of observations
        observed_value: Observed metric value
        threshold: Threshold for the test
        additional_info: Extra test-specific info
    """
    hypothesis_id: str
    description: str
    null_hypothesis: str
    alternative_hypothesis: str
    test_statistic: float
    p_value: float
    passed: bool
    decision: str
    effect_size: float
    confidence_interval: Tuple[float, float]
    sample_size: int
    observed_value: float
    threshold: float
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "test_statistic": float(self.test_statistic),
            "p_value": float(self.p_value),
            "passed": self.passed,
            "decision": self.decision,
            "effect_size": float(self.effect_size),
            "confidence_interval": (float(self.confidence_interval[0]), float(self.confidence_interval[1])),
            "sample_size": self.sample_size,
            "observed_value": float(self.observed_value),
            "threshold": float(self.threshold),
            "additional_info": self.additional_info,
        }


class TokenHypothesisTester:
    """
    Run hypothesis tests for token economics validation.

    Tests:
    - H4.1: Supply stability (CV < 5%)
    - H4.2: Mint-burn equilibrium (< 10% difference)
    - H4.3: Velocity prediction (Fisher equation, < 20% error)
    - H4.4: Peg stability (rate = 1.0 +/- 1%)
    - H4.5: No hyperinflation (annual < 10%)
    """

    def __init__(
        self,
        alpha: float = 0.05,
        bootstrap_iterations: int = 10000,
    ):
        """
        Initialize hypothesis tester.

        Args:
            alpha: Significance level
            bootstrap_iterations: Bootstrap iterations for CI estimation
        """
        self.alpha = alpha
        self.bootstrap_iterations = bootstrap_iterations

    def run_all_tests(
        self,
        supply_tracker: TokenSupplyTracker,
        mint_burn_analyzer: MintBurnAnalyzer,
        velocity_calculator: VelocityCalculator,
        peg_tester: PegStabilityTester,
        inflation_monitor: InflationMonitor,
    ) -> Dict[str, TokenHypothesisResult]:
        """
        Run all token economics hypothesis tests.

        Args:
            supply_tracker: TokenSupplyTracker with data
            mint_burn_analyzer: MintBurnAnalyzer with events
            velocity_calculator: VelocityCalculator with measurements
            peg_tester: PegStabilityTester with redemptions
            inflation_monitor: InflationMonitor with data

        Returns:
            Dictionary mapping hypothesis ID to TokenHypothesisResult
        """
        results = {}

        # H4.1: Supply stability
        results["H4.1"] = self.test_supply_stability(supply_tracker)

        # H4.2: Mint-burn equilibrium
        results["H4.2"] = self.test_mint_burn_equilibrium(mint_burn_analyzer)

        # H4.3: Velocity prediction
        results["H4.3"] = self.test_velocity_prediction(velocity_calculator)

        # H4.4: Peg stability
        results["H4.4"] = self.test_peg_stability(peg_tester)

        # H4.5: No hyperinflation
        results["H4.5"] = self.test_inflation(inflation_monitor)

        return results

    def test_supply_stability(
        self,
        tracker: TokenSupplyTracker,
        cv_threshold: float = 0.05,
        window_days: int = 30,
    ) -> TokenHypothesisResult:
        """
        Test H4.1: Supply CV < 5% over 30-day periods.

        Uses bootstrap CI for coefficient of variation.

        Args:
            tracker: TokenSupplyTracker with data
            cv_threshold: CV threshold (default 5%)
            window_days: Window size in days

        Returns:
            TokenHypothesisResult
        """
        stability_result = tracker.calculate_rolling_stability(
            window_days=window_days,
            cv_threshold=cv_threshold,
        )

        cv_values = stability_result.cv_values
        n = len(cv_values)

        if n < 2:
            return TokenHypothesisResult(
                hypothesis_id="H4.1",
                description="Token Supply Stability",
                null_hypothesis="CV >= 5% over 30-day periods",
                alternative_hypothesis="CV < 5% over 30-day periods",
                test_statistic=0,
                p_value=1.0,
                passed=True,
                decision="fail_to_reject",
                effect_size=0,
                confidence_interval=(0, 0),
                sample_size=n,
                observed_value=0,
                threshold=cv_threshold,
                additional_info={"reason": "Insufficient data"},
            )

        # Bootstrap CI for mean CV
        bootstrap_means = []
        for _ in range(self.bootstrap_iterations):
            bootstrap_sample = np.random.choice(cv_values, size=n, replace=True)
            bootstrap_means.append(np.mean(bootstrap_sample))

        bootstrap_means = np.array(bootstrap_means)
        ci_lower = float(np.percentile(bootstrap_means, 2.5))
        ci_upper = float(np.percentile(bootstrap_means, 97.5))

        mean_cv = float(np.mean(cv_values))

        # P-value: proportion of bootstrap samples >= threshold
        p_value = float(np.mean(bootstrap_means >= cv_threshold))

        # Hypothesis passes if CI upper bound < threshold
        passed = ci_upper < cv_threshold

        # Effect size: how far is mean from threshold
        effect_size = (cv_threshold - mean_cv) / np.std(cv_values) if np.std(cv_values) > 0 else 0

        return TokenHypothesisResult(
            hypothesis_id="H4.1",
            description="Token Supply Stability",
            null_hypothesis="CV >= 5% over 30-day periods",
            alternative_hypothesis="CV < 5% over 30-day periods",
            test_statistic=mean_cv,
            p_value=p_value,
            passed=passed,
            decision="reject_null" if passed else "fail_to_reject",
            effect_size=float(effect_size),
            confidence_interval=(ci_lower, ci_upper),
            sample_size=n,
            observed_value=mean_cv,
            threshold=cv_threshold,
            additional_info={
                "max_cv": float(stability_result.max_cv),
                "windows_above_threshold": stability_result.windows_above_threshold,
                "window_days": window_days,
            },
        )

    def test_mint_burn_equilibrium(
        self,
        analyzer: MintBurnAnalyzer,
        tolerance: float = 0.10,
    ) -> TokenHypothesisResult:
        """
        Test H4.2: |Mint_rate - Burn_rate| / Avg_rate < 10%.

        Uses paired t-test on daily rates.

        Args:
            analyzer: MintBurnAnalyzer with events
            tolerance: Maximum allowed relative difference (default 10%)

        Returns:
            TokenHypothesisResult
        """
        equilibrium_result = analyzer.test_equilibrium(
            tolerance=tolerance,
            alpha=self.alpha,
        )

        # Effect size: standardized difference
        daily_stats = analyzer.calculate_daily_rates()
        if len(daily_stats) > 1:
            mint_rates = np.array([s.mint_volume for s in daily_stats])
            burn_rates = np.array([s.burn_volume for s in daily_stats])
            differences = mint_rates - burn_rates
            pooled_std = np.std(differences, ddof=1)
            effect_size = float(np.mean(differences) / pooled_std) if pooled_std > 0 else 0
        else:
            effect_size = 0

        passed = equilibrium_result.is_equilibrium

        return TokenHypothesisResult(
            hypothesis_id="H4.2",
            description="Mint-Burn Equilibrium",
            null_hypothesis="|Mint_rate - Burn_rate| / Avg_rate >= 10%",
            alternative_hypothesis="|Mint_rate - Burn_rate| / Avg_rate < 10%",
            test_statistic=equilibrium_result.t_statistic,
            p_value=equilibrium_result.p_value,
            passed=passed,
            decision="reject_null" if passed else "fail_to_reject",
            effect_size=effect_size,
            confidence_interval=(equilibrium_result.ci_lower, equilibrium_result.ci_upper),
            sample_size=equilibrium_result.sample_size,
            observed_value=equilibrium_result.rate_difference,
            threshold=tolerance,
            additional_info={
                "mean_mint_rate": equilibrium_result.mean_mint_rate,
                "mean_burn_rate": equilibrium_result.mean_burn_rate,
            },
        )

    def test_velocity_prediction(
        self,
        calculator: VelocityCalculator,
        tolerance: float = 0.20,
    ) -> TokenHypothesisResult:
        """
        Test H4.3: |V_actual - V_predicted| / V_predicted < 20%.

        Tests Fisher equation validity with paired t-test.

        Args:
            calculator: VelocityCalculator with measurements
            tolerance: Maximum allowed relative error (default 20%)

        Returns:
            TokenHypothesisResult
        """
        velocity_result = calculator.test_fisher_equation(
            tolerance=tolerance,
            alpha=self.alpha,
        )

        passed = velocity_result.is_valid

        return TokenHypothesisResult(
            hypothesis_id="H4.3",
            description="Token Velocity Prediction (Fisher Equation)",
            null_hypothesis="|V_actual - V_predicted| / V_predicted >= 20%",
            alternative_hypothesis="|V_actual - V_predicted| / V_predicted < 20%",
            test_statistic=velocity_result.t_statistic,
            p_value=velocity_result.p_value,
            passed=passed,
            decision="reject_null" if passed else "fail_to_reject",
            effect_size=velocity_result.r_squared,
            confidence_interval=(
                velocity_result.mean_actual_velocity - velocity_result.mean_absolute_error,
                velocity_result.mean_actual_velocity + velocity_result.mean_absolute_error,
            ),
            sample_size=velocity_result.sample_size,
            observed_value=velocity_result.mean_absolute_error,
            threshold=tolerance,
            additional_info={
                "mean_actual_velocity": velocity_result.mean_actual_velocity,
                "mean_predicted_velocity": velocity_result.mean_predicted_velocity,
                "correlation": velocity_result.correlation,
                "r_squared": velocity_result.r_squared,
            },
        )

    def test_peg_stability(
        self,
        tester: PegStabilityTester,
        tolerance: float = 0.01,
    ) -> TokenHypothesisResult:
        """
        Test H4.4: Redemption rate = 1.0 +/- 1%.

        Uses one-sample t-test with equivalence margin.

        Args:
            tester: PegStabilityTester with redemptions
            tolerance: Maximum allowed deviation (default 1%)

        Returns:
            TokenHypothesisResult
        """
        peg_result = tester.test_peg_accuracy(
            tolerance=tolerance,
            alpha=self.alpha,
        )

        # Effect size: deviation from target in std units
        if peg_result.std_rate > 0:
            effect_size = float(peg_result.deviation_from_target / peg_result.std_rate)
        else:
            effect_size = 0

        passed = peg_result.is_stable

        return TokenHypothesisResult(
            hypothesis_id="H4.4",
            description="Token-kWh Peg Stability",
            null_hypothesis="Redemption rate deviation > 1% from 1.0",
            alternative_hypothesis="Redemption rate = 1.0 +/- 1%",
            test_statistic=peg_result.t_statistic,
            p_value=peg_result.p_value,
            passed=passed,
            decision="reject_null" if passed else "fail_to_reject",
            effect_size=effect_size,
            confidence_interval=(peg_result.ci_lower, peg_result.ci_upper),
            sample_size=peg_result.sample_size,
            observed_value=peg_result.mean_rate,
            threshold=tolerance,
            additional_info={
                "target_rate": peg_result.target_rate,
                "deviation_from_target": peg_result.deviation_from_target,
                "std_rate": peg_result.std_rate,
            },
        )

    def test_inflation(
        self,
        monitor: InflationMonitor,
        threshold: float = 0.10,
    ) -> TokenHypothesisResult:
        """
        Test H4.5: Annual inflation < 10%.

        Uses one-sample t-test on annualized rates.

        Args:
            monitor: InflationMonitor with data
            threshold: Maximum annual inflation (default 10%)

        Returns:
            TokenHypothesisResult
        """
        inflation_result = monitor.test_inflation(
            threshold=threshold,
            alpha=self.alpha,
        )

        # Effect size: how far is mean from threshold in std units
        if inflation_result.std_inflation > 0:
            effect_size = float((threshold - inflation_result.mean_annual_inflation) / inflation_result.std_inflation)
        else:
            effect_size = 0

        passed = inflation_result.is_acceptable

        return TokenHypothesisResult(
            hypothesis_id="H4.5",
            description="No Hyperinflation",
            null_hypothesis="Annual inflation >= 10%",
            alternative_hypothesis="Annual inflation < 10%",
            test_statistic=inflation_result.t_statistic,
            p_value=inflation_result.p_value,
            passed=passed,
            decision="reject_null" if passed else "fail_to_reject",
            effect_size=effect_size,
            confidence_interval=(inflation_result.ci_lower, inflation_result.ci_upper),
            sample_size=inflation_result.sample_size,
            observed_value=inflation_result.mean_annual_inflation,
            threshold=threshold,
            additional_info={
                "max_inflation": inflation_result.max_inflation,
                "min_inflation": inflation_result.min_inflation,
                "std_inflation": inflation_result.std_inflation,
            },
        )

    def generate_summary_report(
        self,
        results: Dict[str, TokenHypothesisResult],
    ) -> str:
        """
        Generate a formatted summary report.

        Args:
            results: Dictionary of hypothesis results

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 80,
            "TOKEN ECONOMICS HYPOTHESIS TESTS - SUMMARY REPORT",
            "=" * 80,
            "",
            f"Significance Level: alpha = {self.alpha}",
            "",
            "-" * 80,
        ]

        for h_id in sorted(results.keys()):
            result = results[h_id]

            status = "PASS" if result.passed else "FAIL"
            lines.extend([
                "",
                f"{h_id}: {result.description}",
                f"  Status: {status}",
                f"  Test: {result.null_hypothesis} vs {result.alternative_hypothesis}",
                f"  Observed: {result.observed_value:.4f}, Threshold: {result.threshold:.4f}",
                f"  Statistic: {result.test_statistic:.4f}, p-value: {result.p_value:.6f}",
                f"  95% CI: [{result.confidence_interval[0]:.4f}, {result.confidence_interval[1]:.4f}]",
                f"  Sample Size: {result.sample_size}",
                f"  Decision: {result.decision}",
            ])

            # Add hypothesis-specific info
            if h_id == "H4.1":
                info = result.additional_info
                lines.append(f"  Conclusion: Mean CV = {result.observed_value*100:.2f}% "
                           f"(max: {info.get('max_cv', 0)*100:.2f}%). "
                           f"{'Meets' if result.passed else 'Does not meet'} 5% stability threshold.")

            elif h_id == "H4.2":
                info = result.additional_info
                lines.append(f"  Conclusion: Rate difference = {result.observed_value*100:.2f}%. "
                           f"Mint: {info.get('mean_mint_rate', 0):.2f}, "
                           f"Burn: {info.get('mean_burn_rate', 0):.2f}. "
                           f"{'In' if result.passed else 'Not in'} equilibrium.")

            elif h_id == "H4.3":
                info = result.additional_info
                lines.append(f"  Conclusion: Mean prediction error = {result.observed_value*100:.2f}%. "
                           f"R^2 = {info.get('r_squared', 0):.4f}, "
                           f"correlation = {info.get('correlation', 0):.4f}. "
                           f"Fisher equation {'valid' if result.passed else 'not valid'}.")

            elif h_id == "H4.4":
                info = result.additional_info
                lines.append(f"  Conclusion: Mean rate = {result.observed_value:.4f} "
                           f"(deviation: {info.get('deviation_from_target', 0)*100:.3f}%). "
                           f"Peg is {'stable' if result.passed else 'not stable'}.")

            elif h_id == "H4.5":
                info = result.additional_info
                lines.append(f"  Conclusion: Mean annual inflation = {result.observed_value*100:.2f}% "
                           f"(max: {info.get('max_inflation', 0)*100:.2f}%). "
                           f"{'Below' if result.passed else 'At or above'} 10% threshold.")

        # Summary
        passed_count = sum(1 for r in results.values() if r.passed)
        total_count = len(results)

        lines.extend([
            "",
            "-" * 80,
            f"OVERALL: {passed_count}/{total_count} hypotheses supported ({passed_count/total_count*100:.1f}%)",
            "=" * 80,
        ])

        return "\n".join(lines)
