"""
Comprehensive Hypothesis Testing Module.

Provides statistical tests for SHAKTI-CHAIN experiment validation:
- One-sample t-test
- Two-sample t-test (independent)
- Paired t-test
- ANOVA (one-way)
- Proportion z-test
- Chi-square test
- Exact binomial test
- TOST equivalence test
- ADF test (stationarity)
- Kolmogorov-Smirnov test
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class TestType(Enum):
    """Types of statistical tests."""
    ONE_SAMPLE_T = "one_sample_t"
    TWO_SAMPLE_T = "two_sample_t"
    PAIRED_T = "paired_t"
    ANOVA = "anova"
    PROPORTION_Z = "proportion_z"
    CHI_SQUARE = "chi_square"
    BINOMIAL = "binomial"
    TOST = "tost"
    ADF = "adf"
    KS = "ks"
    MANN_WHITNEY = "mann_whitney"
    WILCOXON = "wilcoxon"
    KRUSKAL_WALLIS = "kruskal_wallis"


class Alternative(Enum):
    """Alternative hypothesis types."""
    TWO_SIDED = "two-sided"
    GREATER = "greater"
    LESS = "less"


@dataclass
class HypothesisTestResult:
    """
    Result of a hypothesis test.

    Attributes:
        test_name: Name of the test
        test_type: Type of test performed
        statistic: Test statistic value
        p_value: P-value
        passed: Whether hypothesis passed at alpha level
        alpha: Significance level
        effect_size: Effect size (Cohen's d, etc.)
        confidence_interval: CI for the effect
        sample_size: Total sample size
        degrees_freedom: Degrees of freedom
        power: Statistical power (if calculated)
        alternative: Alternative hypothesis type
        null_hypothesis: Description of H0
        alt_hypothesis: Description of H1
        interpretation: Human-readable interpretation
        additional_stats: Extra statistics
    """
    test_name: str
    test_type: TestType
    statistic: float
    p_value: float
    passed: bool
    alpha: float = 0.05
    effect_size: float = 0.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    sample_size: int = 0
    degrees_freedom: float = 0.0
    power: float = 0.0
    alternative: Alternative = Alternative.TWO_SIDED
    null_hypothesis: str = ""
    alt_hypothesis: str = ""
    interpretation: str = ""
    additional_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "test_type": self.test_type.value,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "passed": self.passed,
            "alpha": self.alpha,
            "effect_size": self.effect_size,
            "confidence_interval": self.confidence_interval,
            "sample_size": self.sample_size,
            "degrees_freedom": self.degrees_freedom,
            "power": self.power,
            "alternative": self.alternative.value,
            "null_hypothesis": self.null_hypothesis,
            "alt_hypothesis": self.alt_hypothesis,
            "interpretation": self.interpretation,
            "additional_stats": self.additional_stats,
        }


class HypothesisTester:
    """
    Comprehensive hypothesis testing class.

    Provides methods for various statistical tests with effect sizes,
    confidence intervals, and interpretations.
    """

    def __init__(self, alpha: float = 0.05):
        """
        Initialize tester.

        Args:
            alpha: Default significance level
        """
        self.alpha = alpha

    def one_sample_t_test(
        self,
        data: np.ndarray,
        popmean: float,
        alternative: Alternative = Alternative.TWO_SIDED,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform one-sample t-test.

        Tests if sample mean differs from population mean.

        Args:
            data: Sample data
            popmean: Population mean under H0
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        data = np.asarray(data)
        n = len(data)

        if n < 2:
            raise ValueError("Sample size must be at least 2")

        # Map alternative
        alt_map = {
            Alternative.TWO_SIDED: 'two-sided',
            Alternative.GREATER: 'greater',
            Alternative.LESS: 'less',
        }

        # Perform test
        result = stats.ttest_1samp(data, popmean, alternative=alt_map[alternative])

        # Calculate effect size (Cohen's d)
        sample_mean = np.mean(data)
        sample_std = np.std(data, ddof=1)
        cohens_d = (sample_mean - popmean) / sample_std if sample_std > 0 else 0

        # Confidence interval for the mean
        sem = sample_std / np.sqrt(n)
        if alternative == Alternative.TWO_SIDED:
            t_crit = stats.t.ppf(1 - alpha / 2, n - 1)
            ci = (sample_mean - t_crit * sem, sample_mean + t_crit * sem)
        elif alternative == Alternative.GREATER:
            t_crit = stats.t.ppf(1 - alpha, n - 1)
            ci = (sample_mean - t_crit * sem, float('inf'))
        else:
            t_crit = stats.t.ppf(1 - alpha, n - 1)
            ci = (float('-inf'), sample_mean + t_crit * sem)

        # Determine if passed
        passed = result.pvalue < alpha

        # Interpretation
        if passed:
            interpretation = f"Reject H0: Sample mean ({sample_mean:.4f}) significantly differs from {popmean}"
        else:
            interpretation = f"Fail to reject H0: No significant difference from {popmean}"

        return HypothesisTestResult(
            test_name="One-Sample t-Test",
            test_type=TestType.ONE_SAMPLE_T,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(cohens_d),
            confidence_interval=ci,
            sample_size=n,
            degrees_freedom=float(n - 1),
            alternative=alternative,
            null_hypothesis=f"mu = {popmean}",
            alt_hypothesis=f"mu != {popmean}" if alternative == Alternative.TWO_SIDED else
                          f"mu > {popmean}" if alternative == Alternative.GREATER else f"mu < {popmean}",
            interpretation=interpretation,
            additional_stats={
                "sample_mean": float(sample_mean),
                "sample_std": float(sample_std),
                "sem": float(sem),
            },
        )

    def two_sample_t_test(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        alternative: Alternative = Alternative.TWO_SIDED,
        equal_var: bool = False,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform independent two-sample t-test.

        Tests if two groups have different means.

        Args:
            group1: First group data
            group2: Second group data
            alternative: Alternative hypothesis
            equal_var: Assume equal variances (if False, use Welch's)
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        if n1 < 2 or n2 < 2:
            raise ValueError("Each group must have at least 2 samples")

        # Map alternative
        alt_map = {
            Alternative.TWO_SIDED: 'two-sided',
            Alternative.GREATER: 'greater',
            Alternative.LESS: 'less',
        }

        # Perform test
        result = stats.ttest_ind(group1, group2, equal_var=equal_var,
                                  alternative=alt_map[alternative])

        # Calculate effect size (Cohen's d)
        mean1, mean2 = np.mean(group1), np.mean(group2)
        std1, std2 = np.std(group1, ddof=1), np.std(group2, ddof=1)

        # Pooled standard deviation
        pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        cohens_d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0

        # Degrees of freedom (Welch-Satterthwaite if unequal variance)
        if equal_var:
            df = n1 + n2 - 2
        else:
            s1_n = std1**2 / n1
            s2_n = std2**2 / n2
            df = (s1_n + s2_n)**2 / (s1_n**2 / (n1 - 1) + s2_n**2 / (n2 - 1))

        # Confidence interval for difference in means
        diff = mean1 - mean2
        se_diff = np.sqrt(std1**2 / n1 + std2**2 / n2)

        if alternative == Alternative.TWO_SIDED:
            t_crit = stats.t.ppf(1 - alpha / 2, df)
            ci = (diff - t_crit * se_diff, diff + t_crit * se_diff)
        elif alternative == Alternative.GREATER:
            t_crit = stats.t.ppf(1 - alpha, df)
            ci = (diff - t_crit * se_diff, float('inf'))
        else:
            t_crit = stats.t.ppf(1 - alpha, df)
            ci = (float('-inf'), diff + t_crit * se_diff)

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Reject H0: Groups differ significantly (d = {cohens_d:.3f})"
        else:
            interpretation = f"Fail to reject H0: No significant difference between groups"

        return HypothesisTestResult(
            test_name="Two-Sample t-Test" + (" (Welch)" if not equal_var else ""),
            test_type=TestType.TWO_SAMPLE_T,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(cohens_d),
            confidence_interval=ci,
            sample_size=n1 + n2,
            degrees_freedom=float(df),
            alternative=alternative,
            null_hypothesis="mu1 = mu2",
            alt_hypothesis="mu1 != mu2" if alternative == Alternative.TWO_SIDED else
                          "mu1 > mu2" if alternative == Alternative.GREATER else "mu1 < mu2",
            interpretation=interpretation,
            additional_stats={
                "mean1": float(mean1),
                "mean2": float(mean2),
                "std1": float(std1),
                "std2": float(std2),
                "n1": n1,
                "n2": n2,
                "mean_diff": float(diff),
            },
        )

    def paired_t_test(
        self,
        before: np.ndarray,
        after: np.ndarray,
        alternative: Alternative = Alternative.TWO_SIDED,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform paired t-test.

        Tests if paired observations have different means.

        Args:
            before: First set of paired observations
            after: Second set of paired observations
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        before = np.asarray(before)
        after = np.asarray(after)

        if len(before) != len(after):
            raise ValueError("Paired samples must have equal length")

        n = len(before)
        if n < 2:
            raise ValueError("Sample size must be at least 2")

        # Calculate differences
        diff = after - before

        # Map alternative
        alt_map = {
            Alternative.TWO_SIDED: 'two-sided',
            Alternative.GREATER: 'greater',
            Alternative.LESS: 'less',
        }

        # Perform test
        result = stats.ttest_rel(after, before, alternative=alt_map[alternative])

        # Effect size (Cohen's d for paired data)
        mean_diff = np.mean(diff)
        std_diff = np.std(diff, ddof=1)
        cohens_d = mean_diff / std_diff if std_diff > 0 else 0

        # Confidence interval
        sem = std_diff / np.sqrt(n)
        if alternative == Alternative.TWO_SIDED:
            t_crit = stats.t.ppf(1 - alpha / 2, n - 1)
            ci = (mean_diff - t_crit * sem, mean_diff + t_crit * sem)
        elif alternative == Alternative.GREATER:
            t_crit = stats.t.ppf(1 - alpha, n - 1)
            ci = (mean_diff - t_crit * sem, float('inf'))
        else:
            t_crit = stats.t.ppf(1 - alpha, n - 1)
            ci = (float('-inf'), mean_diff + t_crit * sem)

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Reject H0: Significant paired difference (d = {cohens_d:.3f})"
        else:
            interpretation = f"Fail to reject H0: No significant paired difference"

        return HypothesisTestResult(
            test_name="Paired t-Test",
            test_type=TestType.PAIRED_T,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(cohens_d),
            confidence_interval=ci,
            sample_size=n,
            degrees_freedom=float(n - 1),
            alternative=alternative,
            null_hypothesis="mu_diff = 0",
            alt_hypothesis="mu_diff != 0" if alternative == Alternative.TWO_SIDED else
                          "mu_diff > 0" if alternative == Alternative.GREATER else "mu_diff < 0",
            interpretation=interpretation,
            additional_stats={
                "mean_diff": float(mean_diff),
                "std_diff": float(std_diff),
                "mean_before": float(np.mean(before)),
                "mean_after": float(np.mean(after)),
            },
        )

    def one_way_anova(
        self,
        *groups: np.ndarray,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform one-way ANOVA.

        Tests if multiple groups have different means.

        Args:
            *groups: Variable number of group arrays
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha

        if len(groups) < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        groups = [np.asarray(g) for g in groups]

        # Perform ANOVA
        result = stats.f_oneway(*groups)

        # Calculate eta-squared (effect size)
        k = len(groups)
        ns = [len(g) for g in groups]
        n_total = sum(ns)
        grand_mean = np.mean(np.concatenate(groups))

        # Sum of squares
        ss_between = sum(n * (np.mean(g) - grand_mean)**2 for n, g in zip(ns, groups))
        ss_total = sum(np.sum((g - grand_mean)**2) for g in groups)

        eta_squared = ss_between / ss_total if ss_total > 0 else 0

        # Degrees of freedom
        df_between = k - 1
        df_within = n_total - k

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Reject H0: At least one group mean differs (eta^2 = {eta_squared:.3f})"
        else:
            interpretation = f"Fail to reject H0: No significant differences between groups"

        return HypothesisTestResult(
            test_name="One-Way ANOVA",
            test_type=TestType.ANOVA,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(eta_squared),
            confidence_interval=(0.0, 1.0),  # eta-squared range
            sample_size=n_total,
            degrees_freedom=float(df_between),
            alternative=Alternative.TWO_SIDED,
            null_hypothesis="mu1 = mu2 = ... = muk",
            alt_hypothesis="At least one mu differs",
            interpretation=interpretation,
            additional_stats={
                "k_groups": k,
                "group_means": [float(np.mean(g)) for g in groups],
                "group_stds": [float(np.std(g, ddof=1)) for g in groups],
                "group_sizes": ns,
                "df_between": df_between,
                "df_within": df_within,
                "ss_between": float(ss_between),
                "ss_total": float(ss_total),
            },
        )

    def proportion_z_test(
        self,
        successes: int,
        n: int,
        p0: float,
        alternative: Alternative = Alternative.TWO_SIDED,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform proportion z-test.

        Tests if observed proportion differs from hypothesized proportion.

        Args:
            successes: Number of successes
            n: Total sample size
            p0: Hypothesized proportion
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha

        if n < 1:
            raise ValueError("Sample size must be at least 1")
        if not 0 <= p0 <= 1:
            raise ValueError("p0 must be between 0 and 1")

        p_hat = successes / n

        # Standard error under null
        se = np.sqrt(p0 * (1 - p0) / n)

        if se == 0:
            z_stat = 0
            p_value = 1.0
        else:
            z_stat = (p_hat - p0) / se

            if alternative == Alternative.TWO_SIDED:
                p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
            elif alternative == Alternative.GREATER:
                p_value = 1 - stats.norm.cdf(z_stat)
            else:
                p_value = stats.norm.cdf(z_stat)

        # Effect size (Cohen's h)
        cohens_h = 2 * (np.arcsin(np.sqrt(p_hat)) - np.arcsin(np.sqrt(p0)))

        # Confidence interval for proportion
        se_ci = np.sqrt(p_hat * (1 - p_hat) / n)
        if alternative == Alternative.TWO_SIDED:
            z_crit = stats.norm.ppf(1 - alpha / 2)
            ci = (max(0, p_hat - z_crit * se_ci), min(1, p_hat + z_crit * se_ci))
        elif alternative == Alternative.GREATER:
            z_crit = stats.norm.ppf(1 - alpha)
            ci = (max(0, p_hat - z_crit * se_ci), 1.0)
        else:
            z_crit = stats.norm.ppf(1 - alpha)
            ci = (0.0, min(1, p_hat + z_crit * se_ci))

        passed = p_value < alpha

        if passed:
            interpretation = f"Reject H0: Proportion ({p_hat:.3f}) significantly differs from {p0}"
        else:
            interpretation = f"Fail to reject H0: No significant difference from {p0}"

        return HypothesisTestResult(
            test_name="Proportion z-Test",
            test_type=TestType.PROPORTION_Z,
            statistic=float(z_stat),
            p_value=float(p_value),
            passed=passed,
            alpha=alpha,
            effect_size=float(cohens_h),
            confidence_interval=ci,
            sample_size=n,
            degrees_freedom=float('inf'),  # z-test
            alternative=alternative,
            null_hypothesis=f"p = {p0}",
            alt_hypothesis=f"p != {p0}" if alternative == Alternative.TWO_SIDED else
                          f"p > {p0}" if alternative == Alternative.GREATER else f"p < {p0}",
            interpretation=interpretation,
            additional_stats={
                "successes": successes,
                "observed_proportion": float(p_hat),
                "hypothesized_proportion": p0,
            },
        )

    def chi_square_test(
        self,
        observed: np.ndarray,
        expected: Optional[np.ndarray] = None,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform chi-square goodness-of-fit test.

        Args:
            observed: Observed frequencies
            expected: Expected frequencies (uniform if None)
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        observed = np.asarray(observed)

        if expected is None:
            expected = np.full_like(observed, np.sum(observed) / len(observed), dtype=float)
        else:
            expected = np.asarray(expected)

        # Perform test
        result = stats.chisquare(observed, expected)

        # Effect size (Cramer's V approximation for 1D)
        n = np.sum(observed)
        k = len(observed)
        chi2 = result.statistic
        cramers_v = np.sqrt(chi2 / (n * (k - 1))) if n > 0 and k > 1 else 0

        df = k - 1
        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Reject H0: Observed differs from expected (V = {cramers_v:.3f})"
        else:
            interpretation = f"Fail to reject H0: No significant deviation from expected"

        return HypothesisTestResult(
            test_name="Chi-Square Goodness-of-Fit",
            test_type=TestType.CHI_SQUARE,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(cramers_v),
            confidence_interval=(0.0, 1.0),
            sample_size=int(n),
            degrees_freedom=float(df),
            alternative=Alternative.TWO_SIDED,
            null_hypothesis="Observed follows expected distribution",
            alt_hypothesis="Observed differs from expected",
            interpretation=interpretation,
            additional_stats={
                "observed": observed.tolist(),
                "expected": expected.tolist(),
                "k_categories": k,
            },
        )

    def binomial_test(
        self,
        successes: int,
        n: int,
        p0: float,
        alternative: Alternative = Alternative.TWO_SIDED,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform exact binomial test.

        Tests if observed proportion differs from hypothesized proportion.

        Args:
            successes: Number of successes
            n: Total trials
            p0: Hypothesized probability
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha

        if n < 1:
            raise ValueError("n must be at least 1")
        if not 0 <= p0 <= 1:
            raise ValueError("p0 must be between 0 and 1")

        # Map alternative
        alt_map = {
            Alternative.TWO_SIDED: 'two-sided',
            Alternative.GREATER: 'greater',
            Alternative.LESS: 'less',
        }

        result = stats.binomtest(successes, n, p0, alternative=alt_map[alternative])

        p_hat = successes / n

        # Effect size (Cohen's h)
        cohens_h = 2 * (np.arcsin(np.sqrt(p_hat)) - np.arcsin(np.sqrt(p0)))

        # Get CI from binomtest
        ci = result.proportion_ci(confidence_level=1 - alpha)

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Reject H0: Observed proportion ({p_hat:.3f}) significantly differs from {p0}"
        else:
            interpretation = f"Fail to reject H0: No significant difference from {p0}"

        return HypothesisTestResult(
            test_name="Exact Binomial Test",
            test_type=TestType.BINOMIAL,
            statistic=float(successes),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(cohens_h),
            confidence_interval=(ci.low, ci.high),
            sample_size=n,
            degrees_freedom=0.0,  # Exact test
            alternative=alternative,
            null_hypothesis=f"p = {p0}",
            alt_hypothesis=f"p != {p0}" if alternative == Alternative.TWO_SIDED else
                          f"p > {p0}" if alternative == Alternative.GREATER else f"p < {p0}",
            interpretation=interpretation,
            additional_stats={
                "successes": successes,
                "trials": n,
                "observed_proportion": float(p_hat),
            },
        )

    def tost_equivalence_test(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        low: float,
        high: float,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform TOST (Two One-Sided Tests) equivalence test.

        Tests if two groups are equivalent within bounds.

        Args:
            group1: First group data
            group2: Second group data
            low: Lower equivalence bound
            high: Upper equivalence bound
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        if n1 < 2 or n2 < 2:
            raise ValueError("Each group must have at least 2 samples")

        mean1, mean2 = np.mean(group1), np.mean(group2)
        std1, std2 = np.std(group1, ddof=1), np.std(group2, ddof=1)
        diff = mean1 - mean2

        # Pooled SE
        se = np.sqrt(std1**2 / n1 + std2**2 / n2)

        # Welch-Satterthwaite degrees of freedom
        s1_n = std1**2 / n1
        s2_n = std2**2 / n2
        df = (s1_n + s2_n)**2 / (s1_n**2 / (n1 - 1) + s2_n**2 / (n2 - 1))

        # Two one-sided tests
        t_lower = (diff - low) / se if se > 0 else 0
        t_upper = (diff - high) / se if se > 0 else 0

        p_lower = 1 - stats.t.cdf(t_lower, df)  # Test that diff > low
        p_upper = stats.t.cdf(t_upper, df)       # Test that diff < high

        # TOST p-value is the maximum
        p_value = max(p_lower, p_upper)

        # Effect size
        pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        cohens_d = diff / pooled_std if pooled_std > 0 else 0

        # 90% CI (use 90% for TOST to match two one-sided alpha)
        t_crit = stats.t.ppf(1 - alpha, df)
        ci = (diff - t_crit * se, diff + t_crit * se)

        passed = p_value < alpha

        if passed:
            interpretation = f"Groups are equivalent within [{low}, {high}] (diff = {diff:.4f})"
        else:
            interpretation = f"Cannot conclude equivalence within [{low}, {high}]"

        return HypothesisTestResult(
            test_name="TOST Equivalence Test",
            test_type=TestType.TOST,
            statistic=float(min(abs(t_lower), abs(t_upper))),
            p_value=float(p_value),
            passed=passed,
            alpha=alpha,
            effect_size=float(cohens_d),
            confidence_interval=ci,
            sample_size=n1 + n2,
            degrees_freedom=float(df),
            alternative=Alternative.TWO_SIDED,
            null_hypothesis=f"diff <= {low} OR diff >= {high}",
            alt_hypothesis=f"{low} < diff < {high}",
            interpretation=interpretation,
            additional_stats={
                "mean_diff": float(diff),
                "equivalence_bounds": (low, high),
                "p_lower": float(p_lower),
                "p_upper": float(p_upper),
                "t_lower": float(t_lower),
                "t_upper": float(t_upper),
            },
        )

    def adf_test(
        self,
        data: np.ndarray,
        maxlag: Optional[int] = None,
        regression: str = 'c',
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform Augmented Dickey-Fuller test for stationarity.

        Args:
            data: Time series data
            maxlag: Maximum lag to include
            regression: Regression type ('c', 'ct', 'ctt', 'n')
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        data = np.asarray(data)
        n = len(data)

        if n < 10:
            raise ValueError("ADF test requires at least 10 observations")

        try:
            from statsmodels.tsa.stattools import adfuller
            result = adfuller(data, maxlag=maxlag, regression=regression)

            adf_stat = result[0]
            p_value = result[1]
            used_lag = result[2]
            nobs = result[3]
            critical_values = result[4]

            passed = p_value < alpha  # Reject null (non-stationary) = series is stationary

            if passed:
                interpretation = f"Series is stationary (ADF = {adf_stat:.4f})"
            else:
                interpretation = f"Series is non-stationary (ADF = {adf_stat:.4f})"

            return HypothesisTestResult(
                test_name="Augmented Dickey-Fuller Test",
                test_type=TestType.ADF,
                statistic=float(adf_stat),
                p_value=float(p_value),
                passed=passed,
                alpha=alpha,
                effect_size=0.0,  # Not applicable
                confidence_interval=(0.0, 0.0),
                sample_size=nobs,
                degrees_freedom=0.0,
                alternative=Alternative.LESS,
                null_hypothesis="Series has unit root (non-stationary)",
                alt_hypothesis="Series is stationary",
                interpretation=interpretation,
                additional_stats={
                    "used_lag": used_lag,
                    "critical_values": critical_values,
                },
            )
        except ImportError:
            logger.warning("statsmodels not available for ADF test")
            return HypothesisTestResult(
                test_name="Augmented Dickey-Fuller Test",
                test_type=TestType.ADF,
                statistic=0.0,
                p_value=1.0,
                passed=False,
                alpha=alpha,
                interpretation="statsmodels not available",
            )

    def ks_test(
        self,
        data: np.ndarray,
        cdf: str = 'norm',
        args: Tuple = (),
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform Kolmogorov-Smirnov test for distribution fit.

        Args:
            data: Sample data
            cdf: Distribution name (e.g., 'norm', 'expon')
            args: Distribution parameters
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        data = np.asarray(data)
        n = len(data)

        # Perform KS test
        result = stats.kstest(data, cdf, args=args)

        passed = result.pvalue >= alpha  # Don't reject = data fits distribution

        if passed:
            interpretation = f"Data fits {cdf} distribution (D = {result.statistic:.4f})"
        else:
            interpretation = f"Data does not fit {cdf} distribution (D = {result.statistic:.4f})"

        return HypothesisTestResult(
            test_name=f"Kolmogorov-Smirnov Test ({cdf})",
            test_type=TestType.KS,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(result.statistic),  # D statistic as effect
            confidence_interval=(0.0, 1.0),
            sample_size=n,
            degrees_freedom=0.0,
            alternative=Alternative.TWO_SIDED,
            null_hypothesis=f"Data follows {cdf} distribution",
            alt_hypothesis=f"Data does not follow {cdf} distribution",
            interpretation=interpretation,
            additional_stats={
                "distribution": cdf,
                "distribution_params": args,
            },
        )

    def mann_whitney_u_test(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        alternative: Alternative = Alternative.TWO_SIDED,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform Mann-Whitney U test (non-parametric).

        Tests if two groups have different distributions.

        Args:
            group1: First group data
            group2: Second group data
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        alt_map = {
            Alternative.TWO_SIDED: 'two-sided',
            Alternative.GREATER: 'greater',
            Alternative.LESS: 'less',
        }

        result = stats.mannwhitneyu(group1, group2, alternative=alt_map[alternative])

        # Effect size (rank-biserial correlation)
        u = result.statistic
        r = 1 - (2 * u) / (n1 * n2)  # Rank-biserial correlation

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Groups differ significantly (r = {r:.3f})"
        else:
            interpretation = f"No significant difference between groups"

        return HypothesisTestResult(
            test_name="Mann-Whitney U Test",
            test_type=TestType.MANN_WHITNEY,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(r),
            confidence_interval=(-1.0, 1.0),
            sample_size=n1 + n2,
            degrees_freedom=0.0,
            alternative=alternative,
            null_hypothesis="Groups have same distribution",
            alt_hypothesis="Groups have different distributions",
            interpretation=interpretation,
            additional_stats={
                "n1": n1,
                "n2": n2,
                "median1": float(np.median(group1)),
                "median2": float(np.median(group2)),
            },
        )

    def wilcoxon_signed_rank_test(
        self,
        x: np.ndarray,
        y: Optional[np.ndarray] = None,
        alternative: Alternative = Alternative.TWO_SIDED,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform Wilcoxon signed-rank test (non-parametric paired test).

        Args:
            x: First sample (or differences if y is None)
            y: Second sample (optional)
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha
        x = np.asarray(x)

        if y is not None:
            y = np.asarray(y)
            if len(x) != len(y):
                raise ValueError("Samples must have equal length")
            diff = x - y
        else:
            diff = x

        n = len(diff)

        alt_map = {
            Alternative.TWO_SIDED: 'two-sided',
            Alternative.GREATER: 'greater',
            Alternative.LESS: 'less',
        }

        result = stats.wilcoxon(diff, alternative=alt_map[alternative])

        # Effect size (matched-pairs rank-biserial correlation)
        # r = W / (n * (n + 1) / 2) - approximate
        w = result.statistic
        r = (4 * w) / (n * (n + 1)) - 1

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Significant difference (r = {r:.3f})"
        else:
            interpretation = f"No significant difference"

        return HypothesisTestResult(
            test_name="Wilcoxon Signed-Rank Test",
            test_type=TestType.WILCOXON,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(r),
            confidence_interval=(-1.0, 1.0),
            sample_size=n,
            degrees_freedom=0.0,
            alternative=alternative,
            null_hypothesis="Median difference = 0",
            alt_hypothesis="Median difference != 0",
            interpretation=interpretation,
            additional_stats={
                "median_diff": float(np.median(diff)),
            },
        )

    def kruskal_wallis_test(
        self,
        *groups: np.ndarray,
        alpha: Optional[float] = None,
    ) -> HypothesisTestResult:
        """
        Perform Kruskal-Wallis H-test (non-parametric ANOVA).

        Args:
            *groups: Variable number of group arrays
            alpha: Significance level

        Returns:
            HypothesisTestResult
        """
        alpha = alpha or self.alpha

        if len(groups) < 2:
            raise ValueError("Kruskal-Wallis requires at least 2 groups")

        groups = [np.asarray(g) for g in groups]

        result = stats.kruskal(*groups)

        # Effect size (epsilon-squared)
        k = len(groups)
        n = sum(len(g) for g in groups)
        h = result.statistic
        epsilon_sq = h / (n - 1)

        passed = result.pvalue < alpha

        if passed:
            interpretation = f"Groups differ significantly (epsilon^2 = {epsilon_sq:.3f})"
        else:
            interpretation = f"No significant differences between groups"

        return HypothesisTestResult(
            test_name="Kruskal-Wallis H-Test",
            test_type=TestType.KRUSKAL_WALLIS,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            passed=passed,
            alpha=alpha,
            effect_size=float(epsilon_sq),
            confidence_interval=(0.0, 1.0),
            sample_size=n,
            degrees_freedom=float(k - 1),
            alternative=Alternative.TWO_SIDED,
            null_hypothesis="All groups have same distribution",
            alt_hypothesis="At least one group differs",
            interpretation=interpretation,
            additional_stats={
                "k_groups": k,
                "group_medians": [float(np.median(g)) for g in groups],
                "group_sizes": [len(g) for g in groups],
            },
        )


def run_hypothesis_test(
    test_type: TestType,
    **kwargs,
) -> HypothesisTestResult:
    """
    Run a hypothesis test by type.

    Args:
        test_type: Type of test to run
        **kwargs: Test-specific arguments

    Returns:
        HypothesisTestResult
    """
    tester = HypothesisTester()

    test_methods = {
        TestType.ONE_SAMPLE_T: tester.one_sample_t_test,
        TestType.TWO_SAMPLE_T: tester.two_sample_t_test,
        TestType.PAIRED_T: tester.paired_t_test,
        TestType.ANOVA: tester.one_way_anova,
        TestType.PROPORTION_Z: tester.proportion_z_test,
        TestType.CHI_SQUARE: tester.chi_square_test,
        TestType.BINOMIAL: tester.binomial_test,
        TestType.TOST: tester.tost_equivalence_test,
        TestType.ADF: tester.adf_test,
        TestType.KS: tester.ks_test,
        TestType.MANN_WHITNEY: tester.mann_whitney_u_test,
        TestType.WILCOXON: tester.wilcoxon_signed_rank_test,
        TestType.KRUSKAL_WALLIS: tester.kruskal_wallis_test,
    }

    if test_type not in test_methods:
        raise ValueError(f"Unknown test type: {test_type}")

    return test_methods[test_type](**kwargs)
