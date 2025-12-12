"""
Statistical Hypothesis Tests for Benchmarking (Domain 8).

Implements hypothesis tests for H8.1-H8.6:
- H8.1: SHAKTI ROI > Fixed Tariff ROI (independent t-test)
- H8.2: McAfee efficiency > Uniform efficiency (two-sample t-test)
- H8.3: SHAKTI welfare >= 95% of CDA (TOST equivalence)
- H8.4: SHAKTI cost < Brooklyn cost (two-sample t-test)
- H8.5: SAC reward >= 95% of SOTA RL (TOST equivalence)
- H8.6: SHAKTI is Pareto optimal (hypervolume indicator)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from .pareto_analyzer import ParetoAnalyzer, SystemMetrics, ParetoResult

logger = logging.getLogger(__name__)


@dataclass
class HypothesisResult:
    """
    Result of a single hypothesis test.

    Attributes:
        hypothesis_id: Hypothesis identifier (e.g., "H8.1")
        description: Human-readable description
        passed: Whether the hypothesis passed
        statistic: Test statistic value
        p_value: P-value of the test
        effect_size: Effect size measure (Cohen's d or similar)
        confidence_interval: 95% CI for the effect
        details: Additional test details
    """
    hypothesis_id: str
    description: str
    passed: bool
    statistic: float
    p_value: float
    effect_size: float
    confidence_interval: Tuple[float, float]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "passed": self.passed,
            "statistic": float(self.statistic),
            "p_value": float(self.p_value),
            "effect_size": float(self.effect_size),
            "confidence_interval": (float(self.confidence_interval[0]), float(self.confidence_interval[1])),
            "details": self.details,
        }


@dataclass
class BenchmarkHypothesisResults:
    """
    Results for all benchmark hypothesis tests.

    Attributes:
        results: Dict mapping hypothesis ID to result
        summary: Summary statistics
        all_passed: Whether all hypotheses passed
    """
    results: Dict[str, HypothesisResult] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    all_passed: bool = False

    def to_dict(self) -> dict:
        return {
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "summary": self.summary,
            "all_passed": self.all_passed,
        }

    def __getitem__(self, key: str) -> HypothesisResult:
        return self.results[key]


def tost_test(
    sample1: np.ndarray,
    sample2: np.ndarray,
    equivalence_margin: float = 0.05,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Two One-Sided Tests for equivalence.

    Tests if mean(sample1) is within margin of mean(sample2).

    H0: |mu1 - mu2| >= margin (not equivalent)
    H1: |mu1 - mu2| < margin (equivalent)

    Args:
        sample1: First sample (e.g., SHAKTI values)
        sample2: Second sample (e.g., baseline values)
        equivalence_margin: Equivalence margin as fraction of sample2 mean
        alpha: Significance level

    Returns:
        Dict with equivalence result and statistics
    """
    sample1 = np.asarray(sample1)
    sample2 = np.asarray(sample2)

    mean1 = np.mean(sample1)
    mean2 = np.mean(sample2)
    diff = mean1 - mean2

    # Standard error of difference
    var1 = np.var(sample1, ddof=1)
    var2 = np.var(sample2, ddof=1)
    se = np.sqrt(var1 / len(sample1) + var2 / len(sample2))

    # Margin in absolute terms
    margin = equivalence_margin * abs(mean2)

    # Degrees of freedom (Welch-Satterthwaite)
    df = ((var1 / len(sample1) + var2 / len(sample2)) ** 2 /
          ((var1 / len(sample1)) ** 2 / (len(sample1) - 1) +
           (var2 / len(sample2)) ** 2 / (len(sample2) - 1)))

    # Test 1: diff > -margin (lower bound)
    t1 = (diff + margin) / se
    p1 = 1 - stats.t.cdf(t1, df=df)

    # Test 2: diff < margin (upper bound)
    t2 = (diff - margin) / se
    p2 = stats.t.cdf(t2, df=df)

    # Pooled std for effect size
    pooled_std = np.sqrt((var1 + var2) / 2)
    effect_size = diff / pooled_std if pooled_std > 0 else 0

    return {
        'equivalent': p1 < alpha and p2 < alpha,
        'p_value': max(p1, p2),
        'effect_size': effect_size,
        'difference': diff,
        'margin': margin,
        't1': t1,
        't2': t2,
        'p1': p1,
        'p2': p2,
        'mean1': mean1,
        'mean2': mean2,
    }


class BenchmarkHypothesisTester:
    """
    Statistical hypothesis tester for benchmarking.

    Tests H8.1-H8.6 using appropriate statistical methods.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        bonferroni_correction: bool = True,
    ):
        """
        Initialize hypothesis tester.

        Args:
            alpha: Significance level
            bonferroni_correction: Apply Bonferroni correction
        """
        self.alpha = alpha
        self.bonferroni_correction = bonferroni_correction
        self.n_hypotheses = 6

    def _get_adjusted_alpha(self) -> float:
        """Get alpha adjusted for multiple testing."""
        if self.bonferroni_correction:
            return self.alpha / self.n_hypotheses
        return self.alpha

    def test_h8_1_vs_fixed_tariff(
        self,
        shakti_roi: np.ndarray,
        fixed_tariff_roi: np.ndarray,
    ) -> HypothesisResult:
        """
        Test H8.1: ROI(SHAKTI) > ROI(Fixed Tariff).

        H1: ROI(SHAKTI) > ROI(Fixed Tariff)
        H0: ROI(SHAKTI) <= ROI(Fixed Tariff)
        Test: Independent samples t-test (one-tailed)

        Args:
            shakti_roi: SHAKTI ROI values
            fixed_tariff_roi: Fixed tariff ROI values

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        shakti_roi = np.asarray(shakti_roi)
        fixed_tariff_roi = np.asarray(fixed_tariff_roi)

        # One-tailed t-test (SHAKTI > Fixed)
        t_stat, two_tailed_p = stats.ttest_ind(shakti_roi, fixed_tariff_roi)
        p_value = two_tailed_p / 2 if t_stat > 0 else 1 - two_tailed_p / 2

        # Effect size (Cohen's d)
        pooled_std = np.sqrt((np.var(shakti_roi, ddof=1) + np.var(fixed_tariff_roi, ddof=1)) / 2)
        effect_size = (np.mean(shakti_roi) - np.mean(fixed_tariff_roi)) / pooled_std if pooled_std > 0 else 0

        # Confidence interval for difference
        diff = np.mean(shakti_roi) - np.mean(fixed_tariff_roi)
        se = np.sqrt(np.var(shakti_roi, ddof=1) / len(shakti_roi) +
                    np.var(fixed_tariff_roi, ddof=1) / len(fixed_tariff_roi))
        df = len(shakti_roi) + len(fixed_tariff_roi) - 2
        ci_margin = stats.t.ppf(1 - adj_alpha / 2, df) * se
        ci = (diff - ci_margin, diff + ci_margin)

        passed = p_value < adj_alpha and np.mean(shakti_roi) > np.mean(fixed_tariff_roi)

        return HypothesisResult(
            hypothesis_id="H8.1",
            description="ROI(SHAKTI) > ROI(Fixed Tariff)",
            passed=passed,
            statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "mean_shakti_roi": float(np.mean(shakti_roi)),
                "mean_fixed_roi": float(np.mean(fixed_tariff_roi)),
                "difference": diff,
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h8_2_vs_uniform_auction(
        self,
        mcafee_efficiency: np.ndarray,
        uniform_efficiency: np.ndarray,
    ) -> HypothesisResult:
        """
        Test H8.2: McAfee efficiency > Uniform efficiency.

        H1: McAfee efficiency > Uniform efficiency
        H0: McAfee <= Uniform
        Test: Two-sample t-test (one-tailed)

        Args:
            mcafee_efficiency: McAfee mechanism efficiency values
            uniform_efficiency: Uniform auction efficiency values

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        mcafee_eff = np.asarray(mcafee_efficiency)
        uniform_eff = np.asarray(uniform_efficiency)

        # One-tailed t-test
        t_stat, two_tailed_p = stats.ttest_ind(mcafee_eff, uniform_eff)
        p_value = two_tailed_p / 2 if t_stat > 0 else 1 - two_tailed_p / 2

        # Effect size
        pooled_std = np.sqrt((np.var(mcafee_eff, ddof=1) + np.var(uniform_eff, ddof=1)) / 2)
        effect_size = (np.mean(mcafee_eff) - np.mean(uniform_eff)) / pooled_std if pooled_std > 0 else 0

        # Confidence interval
        diff = np.mean(mcafee_eff) - np.mean(uniform_eff)
        se = np.sqrt(np.var(mcafee_eff, ddof=1) / len(mcafee_eff) +
                    np.var(uniform_eff, ddof=1) / len(uniform_eff))
        df = len(mcafee_eff) + len(uniform_eff) - 2
        ci_margin = stats.t.ppf(1 - adj_alpha / 2, df) * se
        ci = (diff - ci_margin, diff + ci_margin)

        passed = p_value < adj_alpha and np.mean(mcafee_eff) > np.mean(uniform_eff)

        return HypothesisResult(
            hypothesis_id="H8.2",
            description="McAfee efficiency > Uniform efficiency",
            passed=passed,
            statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "mean_mcafee": float(np.mean(mcafee_eff)),
                "mean_uniform": float(np.mean(uniform_eff)),
                "difference": diff,
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h8_3_vs_cda(
        self,
        shakti_welfare: np.ndarray,
        cda_welfare: np.ndarray,
        equivalence_margin: float = 0.05,
    ) -> HypothesisResult:
        """
        Test H8.3: SHAKTI welfare >= 95% of CDA.

        H1: SHAKTI welfare >= 95% of CDA welfare
        H0: SHAKTI < 95% of CDA
        Test: TOST equivalence test

        Args:
            shakti_welfare: SHAKTI welfare values
            cda_welfare: CDA welfare values
            equivalence_margin: Margin for equivalence (default 5%)

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        shakti_w = np.asarray(shakti_welfare)
        cda_w = np.asarray(cda_welfare)

        # Calculate ratio
        mean_shakti = np.mean(shakti_w)
        mean_cda = np.mean(cda_w)
        ratio = mean_shakti / mean_cda if mean_cda > 0 else 0

        # TOST test
        tost_result = tost_test(shakti_w, cda_w, equivalence_margin, adj_alpha)

        # Check if ratio >= 0.95
        passed = ratio >= 0.95 and tost_result['equivalent']

        # Effect size
        effect_size = tost_result['effect_size']

        # CI for ratio (using delta method approximation)
        se_ratio = ratio * np.sqrt(
            np.var(shakti_w, ddof=1) / (len(shakti_w) * mean_shakti**2) +
            np.var(cda_w, ddof=1) / (len(cda_w) * mean_cda**2)
        ) if mean_shakti > 0 and mean_cda > 0 else 0

        z = stats.norm.ppf(1 - adj_alpha / 2)
        ci = (ratio - z * se_ratio, ratio + z * se_ratio)

        return HypothesisResult(
            hypothesis_id="H8.3",
            description="SHAKTI welfare >= 95% of CDA",
            passed=passed,
            statistic=ratio,
            p_value=tost_result['p_value'],
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "mean_shakti_welfare": float(mean_shakti),
                "mean_cda_welfare": float(mean_cda),
                "welfare_ratio": ratio,
                "equivalence_margin": equivalence_margin,
                "tost_equivalent": tost_result['equivalent'],
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h8_4_vs_brooklyn(
        self,
        shakti_cost: np.ndarray,
        brooklyn_cost: np.ndarray,
    ) -> HypothesisResult:
        """
        Test H8.4: SHAKTI cost < Brooklyn cost.

        H1: SHAKTI cost < Brooklyn cost
        H0: SHAKTI >= Brooklyn
        Test: Two-sample t-test (one-tailed)

        Args:
            shakti_cost: SHAKTI transaction costs
            brooklyn_cost: Brooklyn transaction costs

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        shakti_c = np.asarray(shakti_cost)
        brooklyn_c = np.asarray(brooklyn_cost)

        # One-tailed t-test (SHAKTI < Brooklyn, so reversed)
        t_stat, two_tailed_p = stats.ttest_ind(shakti_c, brooklyn_c)
        p_value = two_tailed_p / 2 if t_stat < 0 else 1 - two_tailed_p / 2

        # Effect size (negative if SHAKTI is cheaper)
        pooled_std = np.sqrt((np.var(shakti_c, ddof=1) + np.var(brooklyn_c, ddof=1)) / 2)
        effect_size = (np.mean(shakti_c) - np.mean(brooklyn_c)) / pooled_std if pooled_std > 0 else 0

        # Confidence interval
        diff = np.mean(shakti_c) - np.mean(brooklyn_c)
        se = np.sqrt(np.var(shakti_c, ddof=1) / len(shakti_c) +
                    np.var(brooklyn_c, ddof=1) / len(brooklyn_c))
        df = len(shakti_c) + len(brooklyn_c) - 2
        ci_margin = stats.t.ppf(1 - adj_alpha / 2, df) * se
        ci = (diff - ci_margin, diff + ci_margin)

        passed = p_value < adj_alpha and np.mean(shakti_c) < np.mean(brooklyn_c)

        return HypothesisResult(
            hypothesis_id="H8.4",
            description="SHAKTI cost < Brooklyn cost",
            passed=passed,
            statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "mean_shakti_cost": float(np.mean(shakti_c)),
                "mean_brooklyn_cost": float(np.mean(brooklyn_c)),
                "cost_savings": float(np.mean(brooklyn_c) - np.mean(shakti_c)),
                "cost_savings_pct": float((np.mean(brooklyn_c) - np.mean(shakti_c)) / np.mean(brooklyn_c) * 100) if np.mean(brooklyn_c) > 0 else 0,
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h8_5_vs_sota_rl(
        self,
        sac_reward: np.ndarray,
        sota_rl_reward: np.ndarray,
        equivalence_margin: float = 0.05,
    ) -> HypothesisResult:
        """
        Test H8.5: SAC reward >= 95% of SOTA RL.

        H1: SAC reward >= 95% of SOTA RL reward
        H0: SAC < 95%
        Test: TOST equivalence test

        Args:
            sac_reward: SAC agent reward values
            sota_rl_reward: SOTA RL agent reward values
            equivalence_margin: Margin for equivalence

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        sac_r = np.asarray(sac_reward)
        sota_r = np.asarray(sota_rl_reward)

        # Calculate ratio
        mean_sac = np.mean(sac_r)
        mean_sota = np.mean(sota_r)
        ratio = mean_sac / mean_sota if mean_sota > 0 else 0

        # TOST test
        tost_result = tost_test(sac_r, sota_r, equivalence_margin, adj_alpha)

        # Check if ratio >= 0.95
        passed = ratio >= 0.95 and tost_result['equivalent']

        # Effect size
        effect_size = tost_result['effect_size']

        # CI for ratio
        se_ratio = ratio * np.sqrt(
            np.var(sac_r, ddof=1) / (len(sac_r) * mean_sac**2) +
            np.var(sota_r, ddof=1) / (len(sota_r) * mean_sota**2)
        ) if mean_sac > 0 and mean_sota > 0 else 0

        z = stats.norm.ppf(1 - adj_alpha / 2)
        ci = (ratio - z * se_ratio, ratio + z * se_ratio)

        return HypothesisResult(
            hypothesis_id="H8.5",
            description="SAC reward >= 95% of SOTA RL",
            passed=passed,
            statistic=ratio,
            p_value=tost_result['p_value'],
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "mean_sac_reward": float(mean_sac),
                "mean_sota_reward": float(mean_sota),
                "reward_ratio": ratio,
                "equivalence_margin": equivalence_margin,
                "tost_equivalent": tost_result['equivalent'],
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h8_6_pareto_optimal(
        self,
        systems: List[SystemMetrics],
        shakti_name: str = "SHAKTI-CHAIN",
    ) -> HypothesisResult:
        """
        Test H8.6: SHAKTI is Pareto optimal.

        H1: SHAKTI is Pareto optimal
        H0: SHAKTI is dominated
        Test: Hypervolume indicator

        Args:
            systems: List of system metrics
            shakti_name: Name of SHAKTI system

        Returns:
            HypothesisResult
        """
        analyzer = ParetoAnalyzer(systems)
        result = analyzer.analyze()

        is_pareto = shakti_name in result.pareto_optimal

        # Calculate SHAKTI's contribution
        contribution = result.contributions.get(shakti_name, 0)
        total_contribution = sum(result.contributions.values())
        contribution_ratio = contribution / total_contribution if total_contribution > 0 else 0

        # Get SHAKTI's rank
        rank = result.rankings.get(shakti_name, len(systems))

        # Effect size: relative hypervolume contribution
        effect_size = contribution_ratio

        # CI (not directly applicable, use contribution bounds)
        ci = (contribution_ratio * 0.8, min(1.0, contribution_ratio * 1.2))

        return HypothesisResult(
            hypothesis_id="H8.6",
            description="SHAKTI is Pareto optimal",
            passed=is_pareto,
            statistic=result.hypervolume,
            p_value=0.0 if is_pareto else 1.0,  # Deterministic test
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "is_pareto_optimal": is_pareto,
                "pareto_front": result.pareto_optimal,
                "hypervolume": result.hypervolume,
                "contribution": contribution,
                "contribution_ratio": contribution_ratio,
                "rank": rank,
                "n_systems": len(systems),
            },
        )

    def run_all_tests(
        self,
        shakti_roi: np.ndarray,
        fixed_tariff_roi: np.ndarray,
        mcafee_efficiency: np.ndarray,
        uniform_efficiency: np.ndarray,
        shakti_welfare: np.ndarray,
        cda_welfare: np.ndarray,
        shakti_cost: np.ndarray,
        brooklyn_cost: np.ndarray,
        sac_reward: np.ndarray,
        sota_rl_reward: np.ndarray,
        systems: List[SystemMetrics],
    ) -> BenchmarkHypothesisResults:
        """
        Run all hypothesis tests.

        Args:
            shakti_roi: SHAKTI ROI values
            fixed_tariff_roi: Fixed tariff ROI values
            mcafee_efficiency: McAfee efficiency values
            uniform_efficiency: Uniform efficiency values
            shakti_welfare: SHAKTI welfare values
            cda_welfare: CDA welfare values
            shakti_cost: SHAKTI cost values
            brooklyn_cost: Brooklyn cost values
            sac_reward: SAC reward values
            sota_rl_reward: SOTA RL reward values
            systems: System metrics for Pareto analysis

        Returns:
            BenchmarkHypothesisResults
        """
        results = BenchmarkHypothesisResults()

        # H8.1: vs Fixed Tariff
        results.results["H8.1"] = self.test_h8_1_vs_fixed_tariff(shakti_roi, fixed_tariff_roi)

        # H8.2: vs Uniform Auction
        results.results["H8.2"] = self.test_h8_2_vs_uniform_auction(mcafee_efficiency, uniform_efficiency)

        # H8.3: vs CDA
        results.results["H8.3"] = self.test_h8_3_vs_cda(shakti_welfare, cda_welfare)

        # H8.4: vs Brooklyn
        results.results["H8.4"] = self.test_h8_4_vs_brooklyn(shakti_cost, brooklyn_cost)

        # H8.5: vs SOTA RL
        results.results["H8.5"] = self.test_h8_5_vs_sota_rl(sac_reward, sota_rl_reward)

        # H8.6: Pareto optimal
        results.results["H8.6"] = self.test_h8_6_pareto_optimal(systems)

        # Summary
        n_passed = sum(1 for r in results.results.values() if r.passed)
        results.all_passed = n_passed == len(results.results)
        results.summary = {
            "n_hypotheses": len(results.results),
            "n_passed": n_passed,
            "pass_rate": n_passed / len(results.results),
            "alpha": self.alpha,
            "bonferroni_corrected": self.bonferroni_correction,
        }

        return results


def run_benchmark_hypothesis_tests(
    shakti_roi: np.ndarray,
    fixed_tariff_roi: np.ndarray,
    mcafee_efficiency: np.ndarray,
    uniform_efficiency: np.ndarray,
    shakti_welfare: np.ndarray,
    cda_welfare: np.ndarray,
    shakti_cost: np.ndarray,
    brooklyn_cost: np.ndarray,
    sac_reward: np.ndarray,
    sota_rl_reward: np.ndarray,
    systems: List[SystemMetrics],
    alpha: float = 0.05,
) -> BenchmarkHypothesisResults:
    """
    Convenience function to run all benchmark hypothesis tests.

    Args:
        All test data arrays
        alpha: Significance level

    Returns:
        BenchmarkHypothesisResults
    """
    tester = BenchmarkHypothesisTester(alpha=alpha)
    return tester.run_all_tests(
        shakti_roi=shakti_roi,
        fixed_tariff_roi=fixed_tariff_roi,
        mcafee_efficiency=mcafee_efficiency,
        uniform_efficiency=uniform_efficiency,
        shakti_welfare=shakti_welfare,
        cda_welfare=cda_welfare,
        shakti_cost=shakti_cost,
        brooklyn_cost=brooklyn_cost,
        sac_reward=sac_reward,
        sota_rl_reward=sota_rl_reward,
        systems=systems,
    )
