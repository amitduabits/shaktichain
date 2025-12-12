"""
Hypothesis Tests for Market Mechanism Efficiency (Domain 1).

Implements statistical tests for validating SHAKTI-CHAIN McAfee double auction:
- H1.1: Allocative Efficiency ≥ 95% of Walrasian optimal
- H1.2: Buyer Individual Rationality (100% compliance)
- H1.3: Seller Individual Rationality (100% compliance)
- H1.4: Budget Balance (market maker revenue ≥ 0)
- H1.5: Price Discovery Accuracy (< 5% deviation from equilibrium)
- H1.6: Trade Volume Efficiency ≥ 90% of Walrasian optimal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from .efficiency_metrics import EfficiencyResults


@dataclass
class HypothesisResult:
    """
    Result of a hypothesis test.

    Attributes:
        hypothesis_id: Unique identifier (e.g., 'H1.1')
        description: Human-readable description
        null_hypothesis: H0 statement
        alternative_hypothesis: H1 statement
        test_name: Statistical test used
        test_statistic: Value of test statistic
        p_value: Probability under null hypothesis
        effect_size: Standardized effect size (Cohen's d, etc.)
        confidence_interval: CI for the parameter of interest
        sample_size: Number of observations
        decision: 'reject_null' or 'fail_to_reject_null'
        conclusion: Human-readable conclusion
        raw_data: The data used for the test
        assumptions_met: Dictionary of assumption checks
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
    raw_data: np.ndarray
    assumptions_met: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "test_name": self.test_name,
            "test_statistic": float(self.test_statistic),
            "p_value": float(self.p_value),
            "effect_size": float(self.effect_size),
            "confidence_interval": [float(self.confidence_interval[0]),
                                   float(self.confidence_interval[1])],
            "sample_size": self.sample_size,
            "decision": self.decision,
            "conclusion": self.conclusion,
            "assumptions_met": self.assumptions_met,
        }

    @property
    def passed(self) -> bool:
        """Check if hypothesis test supports the mechanism."""
        # For mechanism validation, we typically want to reject null
        # (null = mechanism doesn't meet threshold)
        return self.decision == "reject_null"


class MechanismHypothesisTester:
    """
    Statistical hypothesis tester for McAfee double auction mechanism.

    Performs rigorous statistical tests with:
    - Multiple comparison corrections (Bonferroni, Holm)
    - Effect size calculations
    - Assumption checking (normality, homoscedasticity)
    - Bootstrap confidence intervals for non-parametric cases
    """

    def __init__(
        self,
        alpha: float = 0.05,
        min_samples: int = 30,
        bootstrap_iterations: int = 10000,
        correction_method: str = "holm",
    ):
        """
        Initialize the hypothesis tester.

        Args:
            alpha: Significance level (default 0.05)
            min_samples: Minimum samples for parametric tests
            bootstrap_iterations: Number of bootstrap resamples
            correction_method: Multiple comparison correction ('bonferroni', 'holm', 'none')
        """
        self.alpha = alpha
        self.min_samples = min_samples
        self.bootstrap_iterations = bootstrap_iterations
        self.correction_method = correction_method

    def run_all_tests(
        self,
        efficiency_results: List[EfficiencyResults],
    ) -> Dict[str, HypothesisResult]:
        """
        Run all hypothesis tests on collected efficiency results.

        Args:
            efficiency_results: List of EfficiencyResults from multiple runs

        Returns:
            Dictionary mapping hypothesis ID to HypothesisResult
        """
        results = {}

        # Extract data arrays from results
        allocative_efficiencies = np.array([r.allocative_efficiency for r in efficiency_results])
        buyer_ir_rates = np.array([r.buyer_ir_rate for r in efficiency_results])
        seller_ir_rates = np.array([r.seller_ir_rate for r in efficiency_results])
        budget_balances = np.array([r.budget_balanced for r in efficiency_results])
        market_maker_revenues = np.array([r.market_maker_revenue for r in efficiency_results])
        price_deviations = np.array([r.price_discovery_error for r in efficiency_results])
        volume_efficiencies = np.array([r.volume_efficiency for r in efficiency_results])

        # Run individual tests
        results["H1.1"] = self.test_allocative_efficiency(allocative_efficiencies)
        results["H1.2"] = self.test_buyer_ir(buyer_ir_rates)
        results["H1.3"] = self.test_seller_ir(seller_ir_rates)
        results["H1.4"] = self.test_budget_balance(budget_balances, market_maker_revenues)
        results["H1.5"] = self.test_price_discovery(price_deviations)
        results["H1.6"] = self.test_volume_efficiency(volume_efficiencies)

        # Apply multiple comparison correction
        if self.correction_method != "none":
            results = self._apply_correction(results)

        return results

    def test_allocative_efficiency(
        self,
        efficiencies: np.ndarray,
        threshold: float = 0.95,
    ) -> HypothesisResult:
        """
        Test H1.1: Allocative Efficiency ≥ 95% of Walrasian optimal.

        Uses one-sample t-test (or Wilcoxon if non-normal) against threshold.
        H0: μ < 0.95 (mechanism fails to achieve target efficiency)
        H1: μ ≥ 0.95 (mechanism achieves target efficiency)
        """
        n = len(efficiencies)
        mean_eff = np.mean(efficiencies)
        std_eff = np.std(efficiencies, ddof=1) if n > 1 else 0

        # Check normality assumption
        normality_met = self._check_normality(efficiencies)

        # Use appropriate test
        if normality_met and n >= self.min_samples:
            # One-sample t-test (one-tailed, greater)
            t_stat, two_tail_p = stats.ttest_1samp(efficiencies, threshold)
            # Convert to one-tailed p-value for greater alternative
            p_value = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test (one-tailed)"
            test_stat = t_stat
        else:
            # Wilcoxon signed-rank test against threshold
            shifted = efficiencies - threshold
            stat, two_tail_p = stats.wilcoxon(shifted, alternative='greater')
            p_value = two_tail_p
            test_name = "Wilcoxon signed-rank test (one-tailed)"
            test_stat = stat

        # Effect size (Cohen's d)
        effect_size = (mean_eff - threshold) / std_eff if std_eff > 0 else float('inf')

        # Bootstrap confidence interval
        ci = self._bootstrap_ci(efficiencies, np.mean)

        # Decision
        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        conclusion = (
            f"Allocative efficiency (mean={mean_eff:.4f}, 95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]) "
            f"{'meets' if decision == 'reject_null' else 'does not meet'} the 95% threshold "
            f"(p={p_value:.4f}, d={effect_size:.3f})"
        )

        return HypothesisResult(
            hypothesis_id="H1.1",
            description="Allocative Efficiency ≥ 95% of Walrasian optimal",
            null_hypothesis="μ(allocative_efficiency) < 0.95",
            alternative_hypothesis="μ(allocative_efficiency) ≥ 0.95",
            test_name=test_name,
            test_statistic=test_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=efficiencies,
            assumptions_met={"normality": normality_met},
        )

    def test_buyer_ir(
        self,
        ir_rates: np.ndarray,
        threshold: float = 1.0,
    ) -> HypothesisResult:
        """
        Test H1.2: Buyer Individual Rationality (100% compliance).

        H0: IR rate < 100% (some buyers trade at loss)
        H1: IR rate = 100% (no buyer trades at loss)

        Uses exact binomial test for proportion = 1.0.
        """
        n = len(ir_rates)
        successes = np.sum(ir_rates == 1.0)
        mean_rate = np.mean(ir_rates)

        # Exact binomial test
        # H0: p < 1.0, H1: p = 1.0
        # Test if all observations are 1.0
        p_value = stats.binom.pmf(successes, n, threshold) if successes == n else 1.0

        # For IR, we use a different approach: test mean against threshold
        if n >= self.min_samples:
            # One-sample t-test for mean = 1.0
            if np.std(ir_rates) > 0:
                t_stat, two_tail_p = stats.ttest_1samp(ir_rates, threshold)
                p_value_t = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2
                test_stat = t_stat
                test_name = "One-sample t-test (one-tailed)"
            else:
                # All values identical
                test_stat = float('inf') if mean_rate >= threshold else float('-inf')
                p_value_t = 0.0 if mean_rate >= threshold else 1.0
                test_name = "Exact comparison (zero variance)"
            p_value = p_value_t
        else:
            test_stat = successes
            test_name = "Exact binomial test"

        # Effect size
        std_rate = np.std(ir_rates, ddof=1) if n > 1 else 0
        effect_size = (mean_rate - threshold) / std_rate if std_rate > 0 else float('inf')

        # CI
        ci = self._bootstrap_ci(ir_rates, np.mean)

        decision = "reject_null" if mean_rate >= threshold - 1e-9 else "fail_to_reject_null"

        conclusion = (
            f"Buyer IR rate (mean={mean_rate:.4f}, 95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]) "
            f"{'achieves' if decision == 'reject_null' else 'fails to achieve'} 100% compliance "
            f"({successes}/{n} runs with perfect IR)"
        )

        return HypothesisResult(
            hypothesis_id="H1.2",
            description="Buyer Individual Rationality (100% compliance)",
            null_hypothesis="Buyer IR rate < 100%",
            alternative_hypothesis="Buyer IR rate = 100%",
            test_name=test_name,
            test_statistic=test_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=ir_rates,
            assumptions_met={"all_perfect": bool(successes == n)},
        )

    def test_seller_ir(
        self,
        ir_rates: np.ndarray,
        threshold: float = 1.0,
    ) -> HypothesisResult:
        """
        Test H1.3: Seller Individual Rationality (100% compliance).

        Same methodology as H1.2 but for sellers.
        """
        n = len(ir_rates)
        successes = np.sum(ir_rates == 1.0)
        mean_rate = np.mean(ir_rates)

        # Similar logic to buyer IR test
        if n >= self.min_samples:
            if np.std(ir_rates) > 0:
                t_stat, two_tail_p = stats.ttest_1samp(ir_rates, threshold)
                p_value = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2
                test_stat = t_stat
                test_name = "One-sample t-test (one-tailed)"
            else:
                test_stat = float('inf') if mean_rate >= threshold else float('-inf')
                p_value = 0.0 if mean_rate >= threshold else 1.0
                test_name = "Exact comparison (zero variance)"
        else:
            test_stat = successes
            p_value = stats.binom.pmf(successes, n, threshold) if successes == n else 1.0
            test_name = "Exact binomial test"

        std_rate = np.std(ir_rates, ddof=1) if n > 1 else 0
        effect_size = (mean_rate - threshold) / std_rate if std_rate > 0 else float('inf')

        ci = self._bootstrap_ci(ir_rates, np.mean)

        decision = "reject_null" if mean_rate >= threshold - 1e-9 else "fail_to_reject_null"

        conclusion = (
            f"Seller IR rate (mean={mean_rate:.4f}, 95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]) "
            f"{'achieves' if decision == 'reject_null' else 'fails to achieve'} 100% compliance "
            f"({successes}/{n} runs with perfect IR)"
        )

        return HypothesisResult(
            hypothesis_id="H1.3",
            description="Seller Individual Rationality (100% compliance)",
            null_hypothesis="Seller IR rate < 100%",
            alternative_hypothesis="Seller IR rate = 100%",
            test_name=test_name,
            test_statistic=test_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=ir_rates,
            assumptions_met={"all_perfect": bool(successes == n)},
        )

    def test_budget_balance(
        self,
        budget_balanced: np.ndarray,
        market_maker_revenues: np.ndarray,
    ) -> HypothesisResult:
        """
        Test H1.4: Budget Balance (market maker revenue ≥ 0).

        H0: P(budget_balanced) < 100% or μ(revenue) < 0
        H1: P(budget_balanced) = 100% and μ(revenue) ≥ 0

        Uses exact binomial test for proportion and t-test for revenue.
        """
        n = len(budget_balanced)
        balanced_count = np.sum(budget_balanced)
        balance_rate = balanced_count / n if n > 0 else 0

        mean_revenue = np.mean(market_maker_revenues)
        std_revenue = np.std(market_maker_revenues, ddof=1) if n > 1 else 0

        # Test 1: All runs budget balanced?
        all_balanced = balanced_count == n

        # Test 2: Mean revenue ≥ 0
        if n >= self.min_samples and std_revenue > 0:
            t_stat, two_tail_p = stats.ttest_1samp(market_maker_revenues, 0)
            p_value = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test on revenue (one-tailed)"
        else:
            t_stat = mean_revenue / std_revenue if std_revenue > 0 else float('inf')
            p_value = 0.0 if mean_revenue >= 0 else 1.0
            test_name = "Exact comparison (revenue ≥ 0)"

        effect_size = mean_revenue / std_revenue if std_revenue > 0 else float('inf')

        ci = self._bootstrap_ci(market_maker_revenues, np.mean)

        # Both conditions must be met
        decision = "reject_null" if all_balanced and mean_revenue >= 0 else "fail_to_reject_null"

        conclusion = (
            f"Budget balance: {balanced_count}/{n} runs balanced ({balance_rate:.1%}), "
            f"mean revenue={mean_revenue:.4f} (95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]). "
            f"Mechanism {'is' if decision == 'reject_null' else 'is NOT'} budget balanced."
        )

        return HypothesisResult(
            hypothesis_id="H1.4",
            description="Budget Balance (market maker revenue ≥ 0)",
            null_hypothesis="Budget not balanced (revenue < 0 or violations exist)",
            alternative_hypothesis="Budget balanced (revenue ≥ 0 in all runs)",
            test_name=test_name,
            test_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=market_maker_revenues,
            assumptions_met={
                "all_runs_balanced": all_balanced,
                "mean_revenue_positive": mean_revenue >= 0,
            },
        )

    def test_price_discovery(
        self,
        price_deviations: np.ndarray,
        threshold: float = 0.05,
    ) -> HypothesisResult:
        """
        Test H1.5: Price Discovery Accuracy (< 5% deviation from equilibrium).

        H0: μ(|price_deviation|) ≥ 0.05 (poor price discovery)
        H1: μ(|price_deviation|) < 0.05 (accurate price discovery)

        Uses one-sample t-test (one-tailed, less than).
        """
        # Use absolute deviations
        abs_deviations = np.abs(price_deviations)
        n = len(abs_deviations)
        mean_dev = np.mean(abs_deviations)
        std_dev = np.std(abs_deviations, ddof=1) if n > 1 else 0

        normality_met = self._check_normality(abs_deviations)

        if normality_met and n >= self.min_samples:
            # One-sample t-test (one-tailed, less)
            t_stat, two_tail_p = stats.ttest_1samp(abs_deviations, threshold)
            # Convert to one-tailed for "less than" alternative
            p_value = two_tail_p / 2 if t_stat < 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test (one-tailed, less)"
        else:
            # Wilcoxon test
            shifted = abs_deviations - threshold
            try:
                stat, two_tail_p = stats.wilcoxon(shifted, alternative='less')
                p_value = two_tail_p
                t_stat = stat
            except ValueError:
                # All zeros or identical values
                t_stat = 0
                p_value = 0.0 if mean_dev < threshold else 1.0
            test_name = "Wilcoxon signed-rank test (one-tailed, less)"

        # Effect size (negative Cohen's d indicates below threshold)
        effect_size = (threshold - mean_dev) / std_dev if std_dev > 0 else float('inf')

        ci = self._bootstrap_ci(abs_deviations, np.mean)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        conclusion = (
            f"Price deviation (mean={mean_dev:.4f}, 95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]) "
            f"{'is within' if decision == 'reject_null' else 'exceeds'} the 5% threshold "
            f"(p={p_value:.4f}, d={effect_size:.3f})"
        )

        return HypothesisResult(
            hypothesis_id="H1.5",
            description="Price Discovery Accuracy (< 5% deviation from equilibrium)",
            null_hypothesis="μ(|price_deviation|) ≥ 0.05",
            alternative_hypothesis="μ(|price_deviation|) < 0.05",
            test_name=test_name,
            test_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=abs_deviations,
            assumptions_met={"normality": normality_met},
        )

    def test_volume_efficiency(
        self,
        volume_efficiencies: np.ndarray,
        threshold: float = 0.90,
    ) -> HypothesisResult:
        """
        Test H1.6: Trade Volume Efficiency ≥ 90% of Walrasian optimal.

        H0: μ(volume_efficiency) < 0.90
        H1: μ(volume_efficiency) ≥ 0.90

        Same methodology as H1.1.
        """
        n = len(volume_efficiencies)
        mean_eff = np.mean(volume_efficiencies)
        std_eff = np.std(volume_efficiencies, ddof=1) if n > 1 else 0

        normality_met = self._check_normality(volume_efficiencies)

        if normality_met and n >= self.min_samples:
            t_stat, two_tail_p = stats.ttest_1samp(volume_efficiencies, threshold)
            p_value = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test (one-tailed)"
        else:
            shifted = volume_efficiencies - threshold
            try:
                stat, two_tail_p = stats.wilcoxon(shifted, alternative='greater')
                p_value = two_tail_p
                t_stat = stat
            except ValueError:
                t_stat = 0
                p_value = 0.0 if mean_eff >= threshold else 1.0
            test_name = "Wilcoxon signed-rank test (one-tailed)"

        effect_size = (mean_eff - threshold) / std_eff if std_eff > 0 else float('inf')

        ci = self._bootstrap_ci(volume_efficiencies, np.mean)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        conclusion = (
            f"Volume efficiency (mean={mean_eff:.4f}, 95% CI=[{ci[0]:.4f}, {ci[1]:.4f}]) "
            f"{'meets' if decision == 'reject_null' else 'does not meet'} the 90% threshold "
            f"(p={p_value:.4f}, d={effect_size:.3f})"
        )

        return HypothesisResult(
            hypothesis_id="H1.6",
            description="Trade Volume Efficiency ≥ 90% of Walrasian optimal",
            null_hypothesis="μ(volume_efficiency) < 0.90",
            alternative_hypothesis="μ(volume_efficiency) ≥ 0.90",
            test_name=test_name,
            test_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=volume_efficiencies,
            assumptions_met={"normality": normality_met},
        )

    def _check_normality(
        self,
        data: np.ndarray,
        alpha: float = 0.05,
    ) -> bool:
        """
        Check normality assumption using Shapiro-Wilk test.

        Returns True if data appears normally distributed.
        """
        if len(data) < 3:
            return False
        if len(data) > 5000:
            # Sample for large datasets
            data = np.random.choice(data, 5000, replace=False)

        try:
            _, p_value = stats.shapiro(data)
            return p_value > alpha
        except Exception:
            return False

    def _bootstrap_ci(
        self,
        data: np.ndarray,
        statistic_func,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """
        Compute bootstrap confidence interval.

        Args:
            data: Sample data
            statistic_func: Function to compute statistic (e.g., np.mean)
            confidence: Confidence level (default 0.95)

        Returns:
            (lower_bound, upper_bound) tuple
        """
        n = len(data)
        if n == 0:
            return (0.0, 0.0)
        if n == 1:
            return (data[0], data[0])

        bootstrap_stats = np.empty(self.bootstrap_iterations)

        for i in range(self.bootstrap_iterations):
            resample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats[i] = statistic_func(resample)

        alpha = 1 - confidence
        lower = np.percentile(bootstrap_stats, 100 * alpha / 2)
        upper = np.percentile(bootstrap_stats, 100 * (1 - alpha / 2))

        return (lower, upper)

    def _apply_correction(
        self,
        results: Dict[str, HypothesisResult],
    ) -> Dict[str, HypothesisResult]:
        """
        Apply multiple comparison correction to p-values.

        Args:
            results: Dictionary of hypothesis results

        Returns:
            Results with adjusted p-values and decisions
        """
        hypothesis_ids = list(results.keys())
        p_values = np.array([results[h].p_value for h in hypothesis_ids])
        n_tests = len(p_values)

        if self.correction_method == "bonferroni":
            adjusted_alpha = self.alpha / n_tests
            # P-values don't change, but we compare against adjusted alpha
            for h_id in hypothesis_ids:
                result = results[h_id]
                new_decision = "reject_null" if result.p_value < adjusted_alpha else "fail_to_reject_null"
                if new_decision != result.decision:
                    results[h_id] = HypothesisResult(
                        hypothesis_id=result.hypothesis_id,
                        description=result.description,
                        null_hypothesis=result.null_hypothesis,
                        alternative_hypothesis=result.alternative_hypothesis,
                        test_name=result.test_name + " (Bonferroni corrected)",
                        test_statistic=result.test_statistic,
                        p_value=result.p_value,
                        effect_size=result.effect_size,
                        confidence_interval=result.confidence_interval,
                        sample_size=result.sample_size,
                        decision=new_decision,
                        conclusion=result.conclusion.replace(
                            "meets" if new_decision == "fail_to_reject_null" else "does not meet",
                            "does not meet" if new_decision == "fail_to_reject_null" else "meets"
                        ),
                        raw_data=result.raw_data,
                        assumptions_met=result.assumptions_met,
                    )

        elif self.correction_method == "holm":
            # Holm-Bonferroni step-down procedure
            sorted_indices = np.argsort(p_values)
            adjusted_decisions = {}

            for rank, idx in enumerate(sorted_indices):
                h_id = hypothesis_ids[idx]
                adjusted_alpha = self.alpha / (n_tests - rank)
                result = results[h_id]

                if result.p_value >= adjusted_alpha:
                    # This and all remaining hypotheses fail to reject
                    for remaining_idx in sorted_indices[rank:]:
                        remaining_h_id = hypothesis_ids[remaining_idx]
                        adjusted_decisions[remaining_h_id] = "fail_to_reject_null"
                    break
                else:
                    adjusted_decisions[h_id] = "reject_null"

            # Fill in any remaining as reject_null
            for h_id in hypothesis_ids:
                if h_id not in adjusted_decisions:
                    adjusted_decisions[h_id] = "reject_null"

            # Update results
            for h_id, new_decision in adjusted_decisions.items():
                result = results[h_id]
                if new_decision != result.decision:
                    results[h_id] = HypothesisResult(
                        hypothesis_id=result.hypothesis_id,
                        description=result.description,
                        null_hypothesis=result.null_hypothesis,
                        alternative_hypothesis=result.alternative_hypothesis,
                        test_name=result.test_name + " (Holm corrected)",
                        test_statistic=result.test_statistic,
                        p_value=result.p_value,
                        effect_size=result.effect_size,
                        confidence_interval=result.confidence_interval,
                        sample_size=result.sample_size,
                        decision=new_decision,
                        conclusion=result.conclusion,
                        raw_data=result.raw_data,
                        assumptions_met=result.assumptions_met,
                    )

        return results

    def generate_summary_report(
        self,
        results: Dict[str, HypothesisResult],
    ) -> str:
        """
        Generate a human-readable summary report.

        Args:
            results: Dictionary of hypothesis test results

        Returns:
            Formatted string report
        """
        lines = [
            "=" * 80,
            "MARKET MECHANISM EFFICIENCY HYPOTHESIS TESTS - SUMMARY REPORT",
            "=" * 80,
            "",
            f"Significance Level: α = {self.alpha}",
            f"Multiple Comparison Correction: {self.correction_method}",
            "",
            "-" * 80,
        ]

        passed = 0
        total = len(results)

        for h_id in sorted(results.keys()):
            result = results[h_id]
            status = "✓ PASS" if result.passed else "✗ FAIL"
            passed += 1 if result.passed else 0

            lines.extend([
                f"\n{h_id}: {result.description}",
                f"  Status: {status}",
                f"  Test: {result.test_name}",
                f"  Statistic: {result.test_statistic:.4f}, p-value: {result.p_value:.6f}",
                f"  Effect Size: {result.effect_size:.4f}",
                f"  95% CI: [{result.confidence_interval[0]:.4f}, {result.confidence_interval[1]:.4f}]",
                f"  Sample Size: {result.sample_size}",
                f"  Conclusion: {result.conclusion}",
            ])

        lines.extend([
            "",
            "-" * 80,
            f"OVERALL: {passed}/{total} hypotheses supported ({passed/total*100:.1f}%)",
            "=" * 80,
        ])

        return "\n".join(lines)
