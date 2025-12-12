"""
Statistical Analyzer - Comprehensive hypothesis testing for SHAKTI-CHAIN experiments.

Implements various statistical tests including t-tests, ANOVA, chi-square,
bootstrap methods, and multiple comparison corrections.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional, Union

import numpy as np
from scipy import stats
from scipy.stats import (
    bootstrap,
    chi2_contingency,
    f_oneway,
    ks_2samp,
    mannwhitneyu,
    shapiro,
    ttest_1samp,
    ttest_ind,
    ttest_rel,
    wilcoxon,
)

logger = logging.getLogger(__name__)


class TestType(Enum):
    """Types of statistical tests."""
    ONE_SAMPLE_T = "one_sample_t"
    TWO_SAMPLE_T_INDEPENDENT = "two_sample_t_independent"
    TWO_SAMPLE_T_PAIRED = "two_sample_t_paired"
    ONE_WAY_ANOVA = "one_way_anova"
    CHI_SQUARE = "chi_square"
    EXACT_BINOMIAL = "exact_binomial"
    BOOTSTRAP_CI = "bootstrap_ci"
    ADF = "augmented_dickey_fuller"
    KS = "kolmogorov_smirnov"
    TOST = "tost_equivalence"
    MANN_WHITNEY = "mann_whitney_u"
    WILCOXON = "wilcoxon_signed_rank"
    SHAPIRO_WILK = "shapiro_wilk"


@dataclass
class HypothesisTest:
    """Result of a hypothesis test."""
    test_type: TestType
    test_name: str
    statistic: float
    p_value: float
    alpha: float
    reject_null: bool
    effect_size: Optional[float] = None
    confidence_interval: Optional[tuple[float, float]] = None
    power: Optional[float] = None
    sample_sizes: tuple[int, ...] = field(default_factory=tuple)
    additional_info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_type": self.test_type.value,
            "test_name": self.test_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "alpha": self.alpha,
            "reject_null": self.reject_null,
            "effect_size": self.effect_size,
            "confidence_interval": self.confidence_interval,
            "power": self.power,
            "sample_sizes": self.sample_sizes,
            "additional_info": self.additional_info,
        }


@dataclass
class PowerAnalysis:
    """Result of power analysis."""
    test_type: TestType
    effect_size: float
    alpha: float
    power: float
    sample_size: Optional[int] = None
    n_per_group: Optional[int] = None
    total_n: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_type": self.test_type.value,
            "effect_size": self.effect_size,
            "alpha": self.alpha,
            "power": self.power,
            "sample_size": self.sample_size,
            "n_per_group": self.n_per_group,
            "total_n": self.total_n,
        }


class StatisticalAnalyzer:
    """
    Comprehensive statistical analysis for SHAKTI-CHAIN experiments.

    Provides various hypothesis tests with proper effect sizes,
    confidence intervals, and multiple comparison corrections.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        alpha_critical: float = 0.01,
        bonferroni_correction: bool = True,
        benjamini_hochberg: bool = True,
        bootstrap_samples: int = 10000,
    ):
        self.alpha = alpha
        self.alpha_critical = alpha_critical
        self.bonferroni_correction = bonferroni_correction
        self.benjamini_hochberg = benjamini_hochberg
        self.bootstrap_samples = bootstrap_samples

    # =========================================================================
    # T-Tests
    # =========================================================================

    def one_sample_t_test(
        self,
        sample: np.ndarray,
        population_mean: float,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform one-sample t-test.

        Tests if sample mean differs from a known population mean.

        Args:
            sample: Sample data
            population_mean: Hypothesized population mean (μ₀)
            alternative: Alternative hypothesis direction
            alpha: Significance level (defaults to instance alpha)

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample = np.asarray(sample)
        n = len(sample)

        statistic, p_value = ttest_1samp(sample, population_mean, alternative=alternative)

        # Cohen's d effect size
        sample_std = np.std(sample, ddof=1)
        effect_size = (np.mean(sample) - population_mean) / sample_std if sample_std > 0 else 0

        # Confidence interval for mean
        se = sample_std / np.sqrt(n)
        t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1)
        ci = (np.mean(sample) - t_crit * se, np.mean(sample) + t_crit * se)

        return HypothesisTest(
            test_type=TestType.ONE_SAMPLE_T,
            test_name="One-Sample t-Test",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(effect_size),
            confidence_interval=ci,
            sample_sizes=(n,),
            additional_info={
                "sample_mean": float(np.mean(sample)),
                "sample_std": float(sample_std),
                "population_mean": population_mean,
                "alternative": alternative,
                "degrees_of_freedom": n - 1,
            },
        )

    def two_sample_t_test(
        self,
        sample1: np.ndarray,
        sample2: np.ndarray,
        paired: bool = False,
        equal_var: bool = True,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform two-sample t-test (independent or paired).

        Args:
            sample1: First sample
            sample2: Second sample
            paired: Whether samples are paired
            equal_var: Assume equal variances (ignored if paired)
            alternative: Alternative hypothesis direction
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample1 = np.asarray(sample1)
        sample2 = np.asarray(sample2)
        n1, n2 = len(sample1), len(sample2)

        if paired:
            if n1 != n2:
                raise ValueError("Paired samples must have equal length")
            statistic, p_value = ttest_rel(sample1, sample2, alternative=alternative)
            test_type = TestType.TWO_SAMPLE_T_PAIRED
            test_name = "Paired t-Test"

            # Effect size: Cohen's d for paired samples
            diff = sample1 - sample2
            effect_size = np.mean(diff) / np.std(diff, ddof=1) if np.std(diff, ddof=1) > 0 else 0
            df = n1 - 1
        else:
            statistic, p_value = ttest_ind(
                sample1, sample2, equal_var=equal_var, alternative=alternative
            )
            test_type = TestType.TWO_SAMPLE_T_INDEPENDENT
            test_name = "Independent t-Test" + (" (Welch's)" if not equal_var else "")

            # Cohen's d for independent samples
            pooled_std = np.sqrt(
                ((n1 - 1) * np.var(sample1, ddof=1) + (n2 - 1) * np.var(sample2, ddof=1)) /
                (n1 + n2 - 2)
            )
            effect_size = (np.mean(sample1) - np.mean(sample2)) / pooled_std if pooled_std > 0 else 0

            if equal_var:
                df = n1 + n2 - 2
            else:
                # Welch-Satterthwaite degrees of freedom
                v1, v2 = np.var(sample1, ddof=1), np.var(sample2, ddof=1)
                df = (v1/n1 + v2/n2)**2 / ((v1/n1)**2/(n1-1) + (v2/n2)**2/(n2-1))

        # Confidence interval for mean difference
        mean_diff = np.mean(sample1) - np.mean(sample2)
        if paired:
            se = np.std(sample1 - sample2, ddof=1) / np.sqrt(n1)
        else:
            se = np.sqrt(np.var(sample1, ddof=1)/n1 + np.var(sample2, ddof=1)/n2)

        t_crit = stats.t.ppf(1 - alpha / 2, df=df)
        ci = (mean_diff - t_crit * se, mean_diff + t_crit * se)

        return HypothesisTest(
            test_type=test_type,
            test_name=test_name,
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(effect_size),
            confidence_interval=ci,
            sample_sizes=(n1, n2),
            additional_info={
                "mean1": float(np.mean(sample1)),
                "mean2": float(np.mean(sample2)),
                "std1": float(np.std(sample1, ddof=1)),
                "std2": float(np.std(sample2, ddof=1)),
                "mean_difference": float(mean_diff),
                "paired": paired,
                "equal_var": equal_var if not paired else None,
                "alternative": alternative,
                "degrees_of_freedom": float(df),
            },
        )

    # =========================================================================
    # ANOVA
    # =========================================================================

    def one_way_anova(
        self,
        *groups: np.ndarray,
        alpha: Optional[float] = None,
        post_hoc: bool = True,
    ) -> HypothesisTest:
        """
        Perform one-way ANOVA with optional Tukey HSD post-hoc test.

        Args:
            *groups: Variable number of group arrays
            alpha: Significance level
            post_hoc: Whether to perform Tukey HSD if significant

        Returns:
            HypothesisTest result with post-hoc comparisons
        """
        alpha = alpha or self.alpha
        groups = [np.asarray(g) for g in groups]
        k = len(groups)  # Number of groups

        if k < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        # One-way ANOVA
        statistic, p_value = f_oneway(*groups)

        # Effect size: Eta-squared (η²)
        all_data = np.concatenate(groups)
        grand_mean = np.mean(all_data)
        ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in groups)
        ss_total = np.sum((all_data - grand_mean)**2)
        eta_squared = ss_between / ss_total if ss_total > 0 else 0

        # Omega-squared (less biased)
        n_total = len(all_data)
        df_between = k - 1
        df_within = n_total - k
        ms_within = (ss_total - ss_between) / df_within if df_within > 0 else 0
        omega_squared = (ss_between - df_between * ms_within) / (ss_total + ms_within)
        omega_squared = max(0, omega_squared)  # Can be negative

        additional_info = {
            "num_groups": k,
            "group_sizes": [len(g) for g in groups],
            "group_means": [float(np.mean(g)) for g in groups],
            "group_stds": [float(np.std(g, ddof=1)) for g in groups],
            "eta_squared": float(eta_squared),
            "omega_squared": float(omega_squared),
            "df_between": df_between,
            "df_within": df_within,
        }

        # Tukey HSD post-hoc if significant
        if post_hoc and p_value < alpha:
            tukey_results = self._tukey_hsd(groups, alpha)
            additional_info["tukey_hsd"] = tukey_results

        return HypothesisTest(
            test_type=TestType.ONE_WAY_ANOVA,
            test_name="One-Way ANOVA",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(eta_squared),
            sample_sizes=tuple(len(g) for g in groups),
            additional_info=additional_info,
        )

    def _tukey_hsd(
        self,
        groups: list[np.ndarray],
        alpha: float,
    ) -> list[dict]:
        """Perform Tukey HSD post-hoc test."""
        from scipy.stats import studentized_range

        k = len(groups)
        all_data = np.concatenate(groups)
        n_total = len(all_data)
        n_groups = [len(g) for g in groups]

        # Calculate MSE
        grand_mean = np.mean(all_data)
        ss_within = sum(np.sum((g - np.mean(g))**2) for g in groups)
        df_within = n_total - k
        mse = ss_within / df_within if df_within > 0 else 0

        results = []
        for i in range(k):
            for j in range(i + 1, k):
                mean_diff = np.mean(groups[i]) - np.mean(groups[j])

                # Standard error for unequal group sizes
                se = np.sqrt(mse * 0.5 * (1/n_groups[i] + 1/n_groups[j]))

                # q statistic
                q = abs(mean_diff) / se if se > 0 else 0

                # p-value from studentized range distribution
                try:
                    p_value = 1 - studentized_range.cdf(q, k, df_within)
                except Exception:
                    # Fallback if studentized_range not available
                    p_value = np.nan

                results.append({
                    "group1": i,
                    "group2": j,
                    "mean_difference": float(mean_diff),
                    "std_error": float(se),
                    "q_statistic": float(q),
                    "p_value": float(p_value),
                    "significant": p_value < alpha if not np.isnan(p_value) else False,
                })

        return results

    # =========================================================================
    # Chi-Square Test
    # =========================================================================

    def chi_square_test(
        self,
        observed: np.ndarray,
        expected: Optional[np.ndarray] = None,
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform chi-square test for independence or goodness of fit.

        Args:
            observed: Contingency table or observed frequencies
            expected: Expected frequencies (for goodness of fit)
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        observed = np.asarray(observed)

        if expected is None:
            # Contingency table test for independence
            chi2, p_value, dof, expected_freq = chi2_contingency(observed)
            test_name = "Chi-Square Test of Independence"

            # Cramér's V effect size
            n = np.sum(observed)
            min_dim = min(observed.shape[0] - 1, observed.shape[1] - 1)
            cramers_v = np.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else 0
            effect_size = cramers_v

            additional_info = {
                "expected_frequencies": expected_freq.tolist(),
                "cramers_v": float(cramers_v),
            }
        else:
            # Goodness of fit test
            expected = np.asarray(expected)
            chi2, p_value = stats.chisquare(observed.flatten(), f_exp=expected.flatten())
            dof = len(observed.flatten()) - 1
            test_name = "Chi-Square Goodness of Fit"

            # Cohen's w effect size
            n = np.sum(observed)
            w = np.sqrt(np.sum((observed.flatten() - expected.flatten())**2 / expected.flatten()) / n)
            effect_size = w

            additional_info = {
                "expected_frequencies": expected.tolist(),
                "cohens_w": float(w),
            }

        additional_info["degrees_of_freedom"] = int(dof)

        return HypothesisTest(
            test_type=TestType.CHI_SQUARE,
            test_name=test_name,
            statistic=float(chi2),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(effect_size),
            sample_sizes=(int(np.sum(observed)),),
            additional_info=additional_info,
        )

    # =========================================================================
    # Exact Binomial Test
    # =========================================================================

    def exact_binomial_test(
        self,
        successes: int,
        trials: int,
        null_probability: float = 0.5,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform exact binomial test.

        Args:
            successes: Number of successes
            trials: Total number of trials
            null_probability: Hypothesized probability under H₀
            alternative: Alternative hypothesis direction
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha

        # Use scipy.stats.binomtest (scipy >= 1.7)
        result = stats.binomtest(successes, trials, null_probability, alternative=alternative)
        p_value = result.pvalue
        statistic = successes  # The test statistic is the number of successes

        # Observed probability
        p_observed = successes / trials if trials > 0 else 0

        # Cohen's h effect size (difference between arcsine-transformed proportions)
        h = 2 * np.arcsin(np.sqrt(p_observed)) - 2 * np.arcsin(np.sqrt(null_probability))

        # Confidence interval for proportion
        ci = result.proportion_ci(confidence_level=1 - alpha)

        return HypothesisTest(
            test_type=TestType.EXACT_BINOMIAL,
            test_name="Exact Binomial Test",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(h),
            confidence_interval=(ci.low, ci.high),
            sample_sizes=(trials,),
            additional_info={
                "successes": successes,
                "trials": trials,
                "observed_probability": float(p_observed),
                "null_probability": null_probability,
                "alternative": alternative,
                "cohens_h": float(h),
            },
        )

    # =========================================================================
    # Bootstrap Confidence Intervals
    # =========================================================================

    def bootstrap_ci(
        self,
        data: np.ndarray,
        statistic: callable = np.mean,
        confidence_level: float = 0.95,
        n_bootstrap: Optional[int] = None,
        method: Literal["percentile", "basic", "BCa"] = "BCa",
    ) -> HypothesisTest:
        """
        Compute bootstrap confidence interval.

        Args:
            data: Sample data
            statistic: Statistic function to compute
            confidence_level: Confidence level (e.g., 0.95)
            n_bootstrap: Number of bootstrap samples
            method: Bootstrap CI method

        Returns:
            HypothesisTest result with confidence interval
        """
        data = np.asarray(data)
        n_bootstrap = n_bootstrap or self.bootstrap_samples

        # Compute observed statistic
        observed_stat = statistic(data)

        # Bootstrap
        def stat_func(x, axis):
            return statistic(x)

        try:
            result = bootstrap(
                (data,),
                stat_func,
                n_resamples=n_bootstrap,
                confidence_level=confidence_level,
                method=method.lower(),
            )
            ci = (result.confidence_interval.low, result.confidence_interval.high)
            se = result.standard_error
        except Exception as e:
            logger.warning(f"Bootstrap failed: {e}. Using percentile method.")
            # Fallback to manual bootstrap
            bootstrap_stats = []
            for _ in range(n_bootstrap):
                sample = np.random.choice(data, size=len(data), replace=True)
                bootstrap_stats.append(statistic(sample))

            alpha = 1 - confidence_level
            ci = (
                np.percentile(bootstrap_stats, 100 * alpha / 2),
                np.percentile(bootstrap_stats, 100 * (1 - alpha / 2)),
            )
            se = np.std(bootstrap_stats)

        return HypothesisTest(
            test_type=TestType.BOOTSTRAP_CI,
            test_name="Bootstrap Confidence Interval",
            statistic=float(observed_stat),
            p_value=np.nan,  # Not applicable for CI
            alpha=1 - confidence_level,
            reject_null=False,  # Not a hypothesis test
            confidence_interval=ci,
            sample_sizes=(len(data),),
            additional_info={
                "n_bootstrap": n_bootstrap,
                "method": method,
                "standard_error": float(se),
                "confidence_level": confidence_level,
            },
        )

    # =========================================================================
    # Augmented Dickey-Fuller Test
    # =========================================================================

    def adf_test(
        self,
        time_series: np.ndarray,
        max_lags: Optional[int] = None,
        regression: Literal["c", "ct", "ctt", "n"] = "c",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform Augmented Dickey-Fuller test for stationarity.

        H₀: Time series has a unit root (non-stationary)
        H₁: Time series is stationary

        Args:
            time_series: Time series data
            max_lags: Maximum number of lags to include
            regression: Type of regression ("c"=constant, "ct"=constant+trend)
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        time_series = np.asarray(time_series)

        try:
            from statsmodels.tsa.stattools import adfuller

            result = adfuller(
                time_series,
                maxlag=max_lags,
                regression=regression,
                autolag="AIC",
            )

            statistic = result[0]
            p_value = result[1]
            used_lags = result[2]
            n_obs = result[3]
            critical_values = result[4]
            icbest = result[5]

            additional_info = {
                "used_lags": int(used_lags),
                "n_observations": int(n_obs),
                "critical_values": {f"{k}%": float(v) for k, v in critical_values.items()},
                "ic_best": float(icbest),
                "regression": regression,
                "is_stationary": p_value < alpha,
            }

        except ImportError:
            logger.warning("statsmodels not available. Using simplified ADF.")
            # Simplified version without statsmodels
            diff = np.diff(time_series)
            lagged = time_series[:-1]

            # Simple OLS regression: Δy_t = α + β*y_{t-1} + ε_t
            X = np.column_stack([np.ones(len(lagged)), lagged])
            beta = np.linalg.lstsq(X, diff, rcond=None)[0]

            # t-statistic for β
            residuals = diff - X @ beta
            mse = np.sum(residuals**2) / (len(diff) - 2)
            se_beta = np.sqrt(mse * np.linalg.inv(X.T @ X)[1, 1])
            statistic = beta[1] / se_beta

            # Approximate p-value (this is a rough approximation)
            # ADF critical values are different from t-distribution
            p_value = 2 * (1 - stats.t.cdf(abs(statistic), df=len(diff) - 2))

            additional_info = {
                "note": "Simplified ADF (statsmodels not available)",
                "is_stationary": p_value < alpha,
            }

        return HypothesisTest(
            test_type=TestType.ADF,
            test_name="Augmented Dickey-Fuller Test",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            sample_sizes=(len(time_series),),
            additional_info=additional_info,
        )

    # =========================================================================
    # Kolmogorov-Smirnov Test
    # =========================================================================

    def ks_test(
        self,
        sample1: np.ndarray,
        sample2: Optional[np.ndarray] = None,
        cdf: Optional[str] = None,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform Kolmogorov-Smirnov test.

        Either compares two samples or tests if a sample follows a distribution.

        Args:
            sample1: First sample
            sample2: Second sample (for two-sample test)
            cdf: Distribution name for one-sample test (e.g., "norm")
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample1 = np.asarray(sample1)

        if sample2 is not None:
            # Two-sample test
            sample2 = np.asarray(sample2)
            statistic, p_value = ks_2samp(sample1, sample2, alternative=alternative)
            test_name = "Two-Sample Kolmogorov-Smirnov Test"
            sample_sizes = (len(sample1), len(sample2))
            additional_info = {
                "sample1_size": len(sample1),
                "sample2_size": len(sample2),
                "alternative": alternative,
            }
        elif cdf is not None:
            # One-sample test against a distribution
            result = stats.kstest(sample1, cdf, alternative=alternative)
            statistic, p_value = result.statistic, result.pvalue
            test_name = f"Kolmogorov-Smirnov Test against {cdf}"
            sample_sizes = (len(sample1),)
            additional_info = {
                "distribution": cdf,
                "alternative": alternative,
            }
        else:
            raise ValueError("Either sample2 or cdf must be provided")

        return HypothesisTest(
            test_type=TestType.KS,
            test_name=test_name,
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            sample_sizes=sample_sizes,
            additional_info=additional_info,
        )

    # =========================================================================
    # TOST Equivalence Test
    # =========================================================================

    def tost_equivalence_test(
        self,
        sample1: np.ndarray,
        sample2: np.ndarray,
        equivalence_margin: float,
        paired: bool = False,
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform Two One-Sided Tests (TOST) for equivalence.

        Tests if two samples are equivalent within a specified margin.

        H₀: |μ₁ - μ₂| ≥ δ (not equivalent)
        H₁: |μ₁ - μ₂| < δ (equivalent)

        Args:
            sample1: First sample
            sample2: Second sample
            equivalence_margin: Equivalence margin (δ)
            paired: Whether samples are paired
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample1 = np.asarray(sample1)
        sample2 = np.asarray(sample2)

        mean_diff = np.mean(sample1) - np.mean(sample2)
        delta = equivalence_margin

        # Lower bound test: H₀: μ₁ - μ₂ ≤ -δ
        if paired:
            _, p_lower = ttest_rel(sample1, sample2 + delta, alternative="greater")
            _, p_upper = ttest_rel(sample1, sample2 - delta, alternative="less")
        else:
            _, p_lower = ttest_ind(sample1, sample2 + delta, alternative="greater")
            _, p_upper = ttest_ind(sample1, sample2 - delta, alternative="less")

        # TOST p-value is the maximum of the two one-sided p-values
        p_value = max(p_lower, p_upper)

        # Effect size relative to equivalence margin
        effect_size = mean_diff / delta if delta > 0 else 0

        return HypothesisTest(
            test_type=TestType.TOST,
            test_name="TOST Equivalence Test",
            statistic=float(mean_diff),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(effect_size),
            confidence_interval=(-delta, delta),
            sample_sizes=(len(sample1), len(sample2)),
            additional_info={
                "mean_difference": float(mean_diff),
                "equivalence_margin": delta,
                "p_lower": float(p_lower),
                "p_upper": float(p_upper),
                "is_equivalent": p_value < alpha,
                "paired": paired,
            },
        )

    # =========================================================================
    # Non-parametric Tests
    # =========================================================================

    def mann_whitney_u_test(
        self,
        sample1: np.ndarray,
        sample2: np.ndarray,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform Mann-Whitney U test (Wilcoxon rank-sum test).

        Non-parametric alternative to independent two-sample t-test.

        Args:
            sample1: First sample
            sample2: Second sample
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample1 = np.asarray(sample1)
        sample2 = np.asarray(sample2)

        statistic, p_value = mannwhitneyu(sample1, sample2, alternative=alternative)

        # Effect size: rank-biserial correlation
        n1, n2 = len(sample1), len(sample2)
        r = 1 - (2 * statistic) / (n1 * n2)

        return HypothesisTest(
            test_type=TestType.MANN_WHITNEY,
            test_name="Mann-Whitney U Test",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(r),
            sample_sizes=(n1, n2),
            additional_info={
                "rank_biserial_r": float(r),
                "alternative": alternative,
            },
        )

    def wilcoxon_signed_rank_test(
        self,
        sample1: np.ndarray,
        sample2: Optional[np.ndarray] = None,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform Wilcoxon signed-rank test.

        Non-parametric alternative to paired t-test.

        Args:
            sample1: First sample (or differences if sample2 is None)
            sample2: Second sample (optional)
            alternative: Alternative hypothesis
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample1 = np.asarray(sample1)

        if sample2 is not None:
            sample2 = np.asarray(sample2)
            diff = sample1 - sample2
        else:
            diff = sample1

        # Remove zeros
        diff = diff[diff != 0]

        if len(diff) == 0:
            return HypothesisTest(
                test_type=TestType.WILCOXON,
                test_name="Wilcoxon Signed-Rank Test",
                statistic=0,
                p_value=1.0,
                alpha=alpha,
                reject_null=False,
                sample_sizes=(0,),
                additional_info={"error": "All differences are zero"},
            )

        statistic, p_value = wilcoxon(diff, alternative=alternative)

        # Effect size: matched-pairs rank-biserial correlation
        n = len(diff)
        r = 1 - (4 * statistic) / (n * (n + 1))

        return HypothesisTest(
            test_type=TestType.WILCOXON,
            test_name="Wilcoxon Signed-Rank Test",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            effect_size=float(r),
            sample_sizes=(n,),
            additional_info={
                "rank_biserial_r": float(r),
                "alternative": alternative,
                "n_nonzero_differences": n,
            },
        )

    # =========================================================================
    # Normality Test
    # =========================================================================

    def shapiro_wilk_test(
        self,
        sample: np.ndarray,
        alpha: Optional[float] = None,
    ) -> HypothesisTest:
        """
        Perform Shapiro-Wilk test for normality.

        H₀: Sample comes from a normal distribution
        H₁: Sample does not come from a normal distribution

        Args:
            sample: Sample data
            alpha: Significance level

        Returns:
            HypothesisTest result
        """
        alpha = alpha or self.alpha
        sample = np.asarray(sample)

        if len(sample) < 3:
            return HypothesisTest(
                test_type=TestType.SHAPIRO_WILK,
                test_name="Shapiro-Wilk Test",
                statistic=np.nan,
                p_value=np.nan,
                alpha=alpha,
                reject_null=False,
                sample_sizes=(len(sample),),
                additional_info={"error": "Sample too small (n < 3)"},
            )

        if len(sample) > 5000:
            sample = np.random.choice(sample, size=5000, replace=False)
            warnings.warn("Sample size > 5000, using random subset for Shapiro-Wilk")

        statistic, p_value = shapiro(sample)

        return HypothesisTest(
            test_type=TestType.SHAPIRO_WILK,
            test_name="Shapiro-Wilk Test",
            statistic=float(statistic),
            p_value=float(p_value),
            alpha=alpha,
            reject_null=p_value < alpha,
            sample_sizes=(len(sample),),
            additional_info={
                "is_normal": p_value >= alpha,
                "skewness": float(stats.skew(sample)),
                "kurtosis": float(stats.kurtosis(sample)),
            },
        )

    # =========================================================================
    # Power Analysis
    # =========================================================================

    def power_analysis_t_test(
        self,
        effect_size: float,
        n: Optional[int] = None,
        power: Optional[float] = None,
        alpha: Optional[float] = None,
        ratio: float = 1.0,
        alternative: Literal["two-sided", "less", "greater"] = "two-sided",
    ) -> PowerAnalysis:
        """
        Power analysis for t-tests.

        Compute power given n, or n given power.

        Args:
            effect_size: Cohen's d
            n: Sample size per group (if computing power)
            power: Target power (if computing n)
            alpha: Significance level
            ratio: Ratio of n2/n1 for two-sample test
            alternative: Alternative hypothesis

        Returns:
            PowerAnalysis result
        """
        alpha = alpha or self.alpha

        if n is not None and power is not None:
            raise ValueError("Specify either n or power, not both")

        if n is None and power is None:
            raise ValueError("Specify either n or power")

        try:
            from statsmodels.stats.power import TTestIndPower

            analysis = TTestIndPower()

            if n is not None:
                # Compute power
                computed_power = analysis.power(
                    effect_size=effect_size,
                    nobs1=n,
                    ratio=ratio,
                    alpha=alpha,
                    alternative=alternative,
                )
                return PowerAnalysis(
                    test_type=TestType.TWO_SAMPLE_T_INDEPENDENT,
                    effect_size=effect_size,
                    alpha=alpha,
                    power=float(computed_power),
                    n_per_group=n,
                    total_n=int(n * (1 + ratio)),
                )
            else:
                # Compute sample size
                n_required = analysis.solve_power(
                    effect_size=effect_size,
                    power=power,
                    ratio=ratio,
                    alpha=alpha,
                    alternative=alternative,
                )
                return PowerAnalysis(
                    test_type=TestType.TWO_SAMPLE_T_INDEPENDENT,
                    effect_size=effect_size,
                    alpha=alpha,
                    power=power,
                    n_per_group=int(np.ceil(n_required)),
                    total_n=int(np.ceil(n_required * (1 + ratio))),
                )

        except ImportError:
            # Simplified power calculation without statsmodels
            logger.warning("statsmodels not available. Using approximate power calculation.")

            if n is not None:
                # Approximate power using non-central t-distribution
                df = 2 * n - 2
                ncp = effect_size * np.sqrt(n / 2)  # Non-centrality parameter
                t_crit = stats.t.ppf(1 - alpha / 2, df)
                computed_power = 1 - stats.nct.cdf(t_crit, df, ncp) + stats.nct.cdf(-t_crit, df, ncp)

                return PowerAnalysis(
                    test_type=TestType.TWO_SAMPLE_T_INDEPENDENT,
                    effect_size=effect_size,
                    alpha=alpha,
                    power=float(computed_power),
                    n_per_group=n,
                    total_n=2 * n,
                )
            else:
                # Approximate sample size using iterative search
                for n_try in range(10, 10000):
                    df = 2 * n_try - 2
                    ncp = effect_size * np.sqrt(n_try / 2)
                    t_crit = stats.t.ppf(1 - alpha / 2, df)
                    p = 1 - stats.nct.cdf(t_crit, df, ncp) + stats.nct.cdf(-t_crit, df, ncp)
                    if p >= power:
                        return PowerAnalysis(
                            test_type=TestType.TWO_SAMPLE_T_INDEPENDENT,
                            effect_size=effect_size,
                            alpha=alpha,
                            power=power,
                            n_per_group=n_try,
                            total_n=2 * n_try,
                        )

                return PowerAnalysis(
                    test_type=TestType.TWO_SAMPLE_T_INDEPENDENT,
                    effect_size=effect_size,
                    alpha=alpha,
                    power=power,
                    n_per_group=10000,
                    total_n=20000,
                )

    # =========================================================================
    # Multiple Comparison Corrections
    # =========================================================================

    def bonferroni_correction(
        self,
        p_values: list[float],
        alpha: Optional[float] = None,
    ) -> dict:
        """
        Apply Bonferroni correction for multiple comparisons.

        Args:
            p_values: List of p-values
            alpha: Family-wise error rate

        Returns:
            Dictionary with corrected results
        """
        alpha = alpha or self.alpha
        m = len(p_values)

        adjusted_p = [min(p * m, 1.0) for p in p_values]
        adjusted_alpha = alpha / m

        return {
            "original_p_values": p_values,
            "adjusted_p_values": adjusted_p,
            "original_alpha": alpha,
            "adjusted_alpha": adjusted_alpha,
            "num_tests": m,
            "significant": [p < adjusted_alpha for p in p_values],
            "num_significant": sum(p < adjusted_alpha for p in p_values),
        }

    def benjamini_hochberg_correction(
        self,
        p_values: list[float],
        alpha: Optional[float] = None,
    ) -> dict:
        """
        Apply Benjamini-Hochberg procedure for controlling FDR.

        Args:
            p_values: List of p-values
            alpha: False discovery rate

        Returns:
            Dictionary with corrected results
        """
        alpha = alpha or self.alpha
        m = len(p_values)

        # Sort p-values and track original indices
        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]

        # Calculate adjusted p-values
        adjusted_p = np.zeros(m)
        for i in range(m):
            rank = i + 1
            adjusted_p[sorted_indices[i]] = sorted_p[i] * m / rank

        # Ensure monotonicity (cumulative minimum from the end)
        adjusted_p_final = np.zeros(m)
        adjusted_p_final[sorted_indices[-1]] = min(adjusted_p[sorted_indices[-1]], 1.0)
        for i in range(m - 2, -1, -1):
            idx = sorted_indices[i]
            next_idx = sorted_indices[i + 1]
            adjusted_p_final[idx] = min(adjusted_p[idx], adjusted_p_final[next_idx], 1.0)

        # Determine significance using BH procedure
        significant = [False] * m
        for i in range(m - 1, -1, -1):
            idx = sorted_indices[i]
            if sorted_p[i] <= (i + 1) / m * alpha:
                # This and all previous (smaller) p-values are significant
                for j in range(i + 1):
                    significant[sorted_indices[j]] = True
                break

        return {
            "original_p_values": p_values,
            "adjusted_p_values": adjusted_p_final.tolist(),
            "alpha": alpha,
            "num_tests": m,
            "significant": significant,
            "num_significant": sum(significant),
        }

    def run_multiple_tests(
        self,
        tests: list[HypothesisTest],
        correction: Literal["bonferroni", "benjamini-hochberg", "none"] = "bonferroni",
    ) -> dict:
        """
        Run multiple tests with correction.

        Args:
            tests: List of HypothesisTest results
            correction: Multiple comparison correction method

        Returns:
            Dictionary with all results and corrections
        """
        p_values = [t.p_value for t in tests]

        if correction == "bonferroni":
            correction_result = self.bonferroni_correction(p_values)
        elif correction == "benjamini-hochberg":
            correction_result = self.benjamini_hochberg_correction(p_values)
        else:
            correction_result = {
                "original_p_values": p_values,
                "adjusted_p_values": p_values,
                "significant": [t.reject_null for t in tests],
            }

        return {
            "tests": [t.to_dict() for t in tests],
            "correction_method": correction,
            "correction_result": correction_result,
        }
