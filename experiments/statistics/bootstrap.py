"""
Bootstrap Methods Module.

Provides bootstrap-based statistical inference:
- Confidence intervals (percentile, BCa, basic, studentized)
- Bootstrap hypothesis testing
- Bootstrap effect sizes
- Permutation tests
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class BootstrapCIMethod(Enum):
    """Bootstrap confidence interval methods."""
    PERCENTILE = "percentile"
    BCa = "bca"  # Bias-corrected and accelerated
    BASIC = "basic"
    STUDENTIZED = "studentized"
    NORMAL = "normal"


@dataclass
class BootstrapResult:
    """
    Result of bootstrap analysis.

    Attributes:
        statistic_name: Name of the statistic
        observed: Observed statistic value
        bootstrap_distribution: Array of bootstrap estimates
        ci_method: CI method used
        confidence_level: Confidence level
        ci_lower: Lower bound of CI
        ci_upper: Upper bound of CI
        se: Bootstrap standard error
        bias: Bootstrap bias estimate
        n_bootstrap: Number of bootstrap samples
        n_original: Original sample size
        interpretation: Human-readable interpretation
        additional_info: Extra information
    """
    statistic_name: str
    observed: float
    bootstrap_distribution: np.ndarray
    ci_method: BootstrapCIMethod
    confidence_level: float
    ci_lower: float
    ci_upper: float
    se: float
    bias: float
    n_bootstrap: int
    n_original: int
    interpretation: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "statistic_name": self.statistic_name,
            "observed": self.observed,
            "bootstrap_distribution": self.bootstrap_distribution.tolist(),
            "ci_method": self.ci_method.value,
            "confidence_level": self.confidence_level,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "se": self.se,
            "bias": self.bias,
            "n_bootstrap": self.n_bootstrap,
            "n_original": self.n_original,
            "interpretation": self.interpretation,
            "additional_info": self.additional_info,
        }

    def summary(self) -> str:
        """Generate summary string."""
        return (
            f"{self.statistic_name}: {self.observed:.4f}\n"
            f"{self.confidence_level*100:.0f}% CI ({self.ci_method.value}): "
            f"[{self.ci_lower:.4f}, {self.ci_upper:.4f}]\n"
            f"SE: {self.se:.4f}, Bias: {self.bias:.4f}"
        )


@dataclass
class BootstrapTestResult:
    """
    Result of bootstrap hypothesis test.

    Attributes:
        test_name: Name of the test
        observed_statistic: Observed test statistic
        p_value: Bootstrap p-value
        null_distribution: Bootstrap null distribution
        alternative: Alternative hypothesis direction
        n_bootstrap: Number of bootstrap samples
        alpha: Significance level
        decision: Test decision
        interpretation: Human-readable interpretation
    """
    test_name: str
    observed_statistic: float
    p_value: float
    null_distribution: np.ndarray
    alternative: str
    n_bootstrap: int
    alpha: float
    decision: str
    interpretation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "observed_statistic": self.observed_statistic,
            "p_value": self.p_value,
            "null_distribution": self.null_distribution.tolist(),
            "alternative": self.alternative,
            "n_bootstrap": self.n_bootstrap,
            "alpha": self.alpha,
            "decision": self.decision,
            "interpretation": self.interpretation,
        }


class Bootstrap:
    """
    Bootstrap resampling methods.

    Provides non-parametric inference through resampling.
    """

    def __init__(
        self,
        n_bootstrap: int = 10000,
        confidence_level: float = 0.95,
        random_state: Optional[int] = None
    ):
        """
        Initialize bootstrap analyzer.

        Args:
            n_bootstrap: Number of bootstrap samples
            confidence_level: Confidence level for intervals
            random_state: Random seed for reproducibility
        """
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level
        self.rng = np.random.default_rng(random_state)

    def _resample(
        self,
        data: np.ndarray,
        n_samples: Optional[int] = None
    ) -> np.ndarray:
        """Generate a bootstrap sample."""
        n = len(data)
        if n_samples is None:
            n_samples = n
        indices = self.rng.integers(0, n, size=n_samples)
        return data[indices]

    def _bootstrap_distribution(
        self,
        data: np.ndarray,
        statistic: Callable[[np.ndarray], float],
        n_bootstrap: Optional[int] = None
    ) -> np.ndarray:
        """Generate bootstrap distribution of a statistic."""
        n_bootstrap = n_bootstrap or self.n_bootstrap
        boot_stats = np.zeros(n_bootstrap)

        for i in range(n_bootstrap):
            sample = self._resample(data)
            boot_stats[i] = statistic(sample)

        return boot_stats

    def confidence_interval(
        self,
        data: np.ndarray,
        statistic: Callable[[np.ndarray], float],
        statistic_name: str = "statistic",
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.BCa,
        confidence_level: Optional[float] = None,
    ) -> BootstrapResult:
        """
        Calculate bootstrap confidence interval.

        Args:
            data: Sample data
            statistic: Function to compute statistic
            statistic_name: Name of the statistic
            method: CI method (percentile, bca, basic, studentized, normal)
            confidence_level: Confidence level

        Returns:
            BootstrapResult
        """
        data = np.asarray(data).flatten()
        n = len(data)
        conf_level = confidence_level or self.confidence_level

        if isinstance(method, str):
            method = BootstrapCIMethod(method)

        # Observed statistic
        observed = statistic(data)

        # Bootstrap distribution
        boot_stats = self._bootstrap_distribution(data, statistic)

        # Bootstrap SE and bias
        se = np.std(boot_stats, ddof=1)
        bias = np.mean(boot_stats) - observed

        # Calculate CI based on method
        alpha = 1 - conf_level

        if method == BootstrapCIMethod.PERCENTILE:
            ci_lower, ci_upper = self._percentile_ci(boot_stats, alpha)

        elif method == BootstrapCIMethod.BCa:
            ci_lower, ci_upper = self._bca_ci(data, statistic, boot_stats, observed, alpha)

        elif method == BootstrapCIMethod.BASIC:
            ci_lower, ci_upper = self._basic_ci(boot_stats, observed, alpha)

        elif method == BootstrapCIMethod.STUDENTIZED:
            ci_lower, ci_upper = self._studentized_ci(data, statistic, observed, alpha)

        elif method == BootstrapCIMethod.NORMAL:
            ci_lower, ci_upper = self._normal_ci(observed, se, alpha, bias)

        else:
            raise ValueError(f"Unknown method: {method}")

        interpretation = (
            f"{statistic_name} = {observed:.4f} "
            f"({conf_level*100:.0f}% CI: [{ci_lower:.4f}, {ci_upper:.4f}])"
        )

        return BootstrapResult(
            statistic_name=statistic_name,
            observed=observed,
            bootstrap_distribution=boot_stats,
            ci_method=method,
            confidence_level=conf_level,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            se=se,
            bias=bias,
            n_bootstrap=self.n_bootstrap,
            n_original=n,
            interpretation=interpretation,
        )

    def _percentile_ci(
        self,
        boot_stats: np.ndarray,
        alpha: float
    ) -> Tuple[float, float]:
        """Percentile method CI."""
        lower = np.percentile(boot_stats, alpha/2 * 100)
        upper = np.percentile(boot_stats, (1 - alpha/2) * 100)
        return float(lower), float(upper)

    def _basic_ci(
        self,
        boot_stats: np.ndarray,
        observed: float,
        alpha: float
    ) -> Tuple[float, float]:
        """Basic (reverse percentile) method CI."""
        lower_pct = np.percentile(boot_stats, (1 - alpha/2) * 100)
        upper_pct = np.percentile(boot_stats, alpha/2 * 100)
        lower = 2 * observed - lower_pct
        upper = 2 * observed - upper_pct
        return float(lower), float(upper)

    def _bca_ci(
        self,
        data: np.ndarray,
        statistic: Callable[[np.ndarray], float],
        boot_stats: np.ndarray,
        observed: float,
        alpha: float
    ) -> Tuple[float, float]:
        """Bias-corrected and accelerated (BCa) method CI."""
        n = len(data)

        # Bias correction factor
        z0 = stats.norm.ppf(np.mean(boot_stats < observed))

        # Acceleration factor (jackknife estimate)
        jackknife_stats = np.zeros(n)
        for i in range(n):
            jack_sample = np.delete(data, i)
            jackknife_stats[i] = statistic(jack_sample)

        jack_mean = np.mean(jackknife_stats)
        num = np.sum((jack_mean - jackknife_stats) ** 3)
        denom = 6 * (np.sum((jack_mean - jackknife_stats) ** 2) ** 1.5)

        if denom == 0:
            a = 0
        else:
            a = num / denom

        # Adjusted percentiles
        z_alpha = stats.norm.ppf(alpha / 2)
        z_1_alpha = stats.norm.ppf(1 - alpha / 2)

        # Handle edge cases
        if np.isnan(z0) or np.isinf(z0):
            z0 = 0

        alpha1_adj = stats.norm.cdf(z0 + (z0 + z_alpha) / (1 - a * (z0 + z_alpha)))
        alpha2_adj = stats.norm.cdf(z0 + (z0 + z_1_alpha) / (1 - a * (z0 + z_1_alpha)))

        # Bound adjusted percentiles
        alpha1_adj = np.clip(alpha1_adj, 0.001, 0.999)
        alpha2_adj = np.clip(alpha2_adj, 0.001, 0.999)

        lower = np.percentile(boot_stats, alpha1_adj * 100)
        upper = np.percentile(boot_stats, alpha2_adj * 100)

        return float(lower), float(upper)

    def _studentized_ci(
        self,
        data: np.ndarray,
        statistic: Callable[[np.ndarray], float],
        observed: float,
        alpha: float
    ) -> Tuple[float, float]:
        """Studentized (bootstrap-t) method CI."""
        n = len(data)
        t_stats = []

        for _ in range(self.n_bootstrap):
            sample = self._resample(data)
            stat = statistic(sample)

            # Nested bootstrap for SE
            nested_stats = []
            for _ in range(100):  # Fewer nested samples
                nested_sample = self._resample(sample)
                nested_stats.append(statistic(nested_sample))

            se = np.std(nested_stats, ddof=1)
            if se > 0:
                t_stats.append((stat - observed) / se)

        t_stats = np.array(t_stats)
        se_observed = np.std(self._bootstrap_distribution(data, statistic, 500), ddof=1)

        t_lower = np.percentile(t_stats, (1 - alpha/2) * 100)
        t_upper = np.percentile(t_stats, alpha/2 * 100)

        lower = observed - t_lower * se_observed
        upper = observed - t_upper * se_observed

        return float(lower), float(upper)

    def _normal_ci(
        self,
        observed: float,
        se: float,
        alpha: float,
        bias: float = 0
    ) -> Tuple[float, float]:
        """Normal approximation CI (bias-corrected)."""
        z = stats.norm.ppf(1 - alpha / 2)
        corrected = observed - bias
        lower = corrected - z * se
        upper = corrected + z * se
        return float(lower), float(upper)

    def ci_mean(
        self,
        data: np.ndarray,
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.BCa,
    ) -> BootstrapResult:
        """Bootstrap CI for the mean."""
        return self.confidence_interval(
            data, np.mean, "mean", method
        )

    def ci_median(
        self,
        data: np.ndarray,
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.BCa,
    ) -> BootstrapResult:
        """Bootstrap CI for the median."""
        return self.confidence_interval(
            data, np.median, "median", method
        )

    def ci_std(
        self,
        data: np.ndarray,
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.BCa,
    ) -> BootstrapResult:
        """Bootstrap CI for the standard deviation."""
        return self.confidence_interval(
            data,
            lambda x: np.std(x, ddof=1),
            "std",
            method
        )

    def ci_correlation(
        self,
        x: np.ndarray,
        y: np.ndarray,
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.BCa,
    ) -> BootstrapResult:
        """Bootstrap CI for Pearson correlation."""
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        if len(x) != len(y):
            raise ValueError("Arrays must have equal length")

        data = np.column_stack([x, y])

        def corr_stat(d):
            return np.corrcoef(d[:, 0], d[:, 1])[0, 1]

        # Resample pairs
        boot_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            indices = self.rng.integers(0, len(data), size=len(data))
            sample = data[indices]
            boot_stats[i] = corr_stat(sample)

        observed = corr_stat(data)
        se = np.std(boot_stats, ddof=1)
        bias = np.mean(boot_stats) - observed

        alpha = 1 - self.confidence_level

        if isinstance(method, str):
            method = BootstrapCIMethod(method)

        if method == BootstrapCIMethod.PERCENTILE:
            ci_lower, ci_upper = self._percentile_ci(boot_stats, alpha)
        elif method == BootstrapCIMethod.BCa:
            # Simplified BCa for correlation
            z0 = stats.norm.ppf(np.mean(boot_stats < observed))
            if np.isnan(z0):
                z0 = 0
            z_alpha = stats.norm.ppf(alpha / 2)
            z_1_alpha = stats.norm.ppf(1 - alpha / 2)
            alpha1 = stats.norm.cdf(2*z0 + z_alpha)
            alpha2 = stats.norm.cdf(2*z0 + z_1_alpha)
            ci_lower = np.percentile(boot_stats, alpha1 * 100)
            ci_upper = np.percentile(boot_stats, alpha2 * 100)
        else:
            ci_lower, ci_upper = self._percentile_ci(boot_stats, alpha)

        return BootstrapResult(
            statistic_name="correlation",
            observed=observed,
            bootstrap_distribution=boot_stats,
            ci_method=method,
            confidence_level=self.confidence_level,
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            se=se,
            bias=bias,
            n_bootstrap=self.n_bootstrap,
            n_original=len(data),
            interpretation=f"Correlation = {observed:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}])",
        )

    def ci_mean_difference(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.BCa,
    ) -> BootstrapResult:
        """Bootstrap CI for difference in means."""
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()

        observed = np.mean(group1) - np.mean(group2)

        boot_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            s1 = self._resample(group1)
            s2 = self._resample(group2)
            boot_stats[i] = np.mean(s1) - np.mean(s2)

        se = np.std(boot_stats, ddof=1)
        bias = np.mean(boot_stats) - observed

        alpha = 1 - self.confidence_level

        if isinstance(method, str):
            method = BootstrapCIMethod(method)

        if method == BootstrapCIMethod.PERCENTILE:
            ci_lower, ci_upper = self._percentile_ci(boot_stats, alpha)
        elif method == BootstrapCIMethod.BASIC:
            ci_lower, ci_upper = self._basic_ci(boot_stats, observed, alpha)
        else:
            # Default to percentile for two-sample
            ci_lower, ci_upper = self._percentile_ci(boot_stats, alpha)

        return BootstrapResult(
            statistic_name="mean_difference",
            observed=observed,
            bootstrap_distribution=boot_stats,
            ci_method=method,
            confidence_level=self.confidence_level,
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            se=se,
            bias=bias,
            n_bootstrap=self.n_bootstrap,
            n_original=len(group1) + len(group2),
            interpretation=f"Mean difference = {observed:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}])",
            additional_info={
                "n1": len(group1),
                "n2": len(group2),
            },
        )

    def ci_cohens_d(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        method: Union[str, BootstrapCIMethod] = BootstrapCIMethod.PERCENTILE,
    ) -> BootstrapResult:
        """Bootstrap CI for Cohen's d effect size."""
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()
        n1, n2 = len(group1), len(group2)

        def cohens_d(g1, g2):
            pooled_std = np.sqrt(
                ((len(g1)-1)*np.var(g1, ddof=1) + (len(g2)-1)*np.var(g2, ddof=1)) /
                (len(g1) + len(g2) - 2)
            )
            return (np.mean(g1) - np.mean(g2)) / pooled_std if pooled_std > 0 else 0

        observed = cohens_d(group1, group2)

        boot_stats = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            s1 = self._resample(group1)
            s2 = self._resample(group2)
            boot_stats[i] = cohens_d(s1, s2)

        se = np.std(boot_stats, ddof=1)
        bias = np.mean(boot_stats) - observed

        alpha = 1 - self.confidence_level
        ci_lower, ci_upper = self._percentile_ci(boot_stats, alpha)

        if isinstance(method, str):
            method = BootstrapCIMethod(method)

        return BootstrapResult(
            statistic_name="cohens_d",
            observed=observed,
            bootstrap_distribution=boot_stats,
            ci_method=method,
            confidence_level=self.confidence_level,
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            se=se,
            bias=bias,
            n_bootstrap=self.n_bootstrap,
            n_original=n1 + n2,
            interpretation=f"Cohen's d = {observed:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}])",
        )

    def hypothesis_test(
        self,
        data: np.ndarray,
        statistic: Callable[[np.ndarray], float],
        null_value: float = 0,
        alternative: str = "two-sided",
        test_name: str = "Bootstrap test",
        alpha: float = 0.05,
    ) -> BootstrapTestResult:
        """
        Bootstrap hypothesis test.

        Args:
            data: Sample data
            statistic: Function to compute test statistic
            null_value: Value under null hypothesis
            alternative: 'two-sided', 'greater', or 'less'
            test_name: Name of the test
            alpha: Significance level

        Returns:
            BootstrapTestResult
        """
        data = np.asarray(data).flatten()

        # Observed statistic
        observed = statistic(data)

        # Center data under null
        centered_data = data - np.mean(data) + null_value

        # Bootstrap null distribution
        null_dist = self._bootstrap_distribution(centered_data, statistic)

        # Calculate p-value
        if alternative == "two-sided":
            p_value = np.mean(np.abs(null_dist) >= np.abs(observed))
        elif alternative == "greater":
            p_value = np.mean(null_dist >= observed)
        elif alternative == "less":
            p_value = np.mean(null_dist <= observed)
        else:
            raise ValueError(f"Unknown alternative: {alternative}")

        decision = "reject_null" if p_value < alpha else "fail_to_reject_null"

        interpretation = (
            f"Observed statistic = {observed:.4f}, p = {p_value:.4f}. "
            f"{'Reject' if decision == 'reject_null' else 'Fail to reject'} "
            f"null hypothesis at alpha = {alpha}."
        )

        return BootstrapTestResult(
            test_name=test_name,
            observed_statistic=float(observed),
            p_value=float(p_value),
            null_distribution=null_dist,
            alternative=alternative,
            n_bootstrap=self.n_bootstrap,
            alpha=alpha,
            decision=decision,
            interpretation=interpretation,
        )

    def two_sample_test(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        alternative: str = "two-sided",
        alpha: float = 0.05,
    ) -> BootstrapTestResult:
        """
        Two-sample bootstrap test for difference in means.

        Uses permutation approach for the null distribution.

        Args:
            group1: First group data
            group2: Second group data
            alternative: 'two-sided', 'greater', or 'less'
            alpha: Significance level

        Returns:
            BootstrapTestResult
        """
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()

        # Observed difference
        observed = np.mean(group1) - np.mean(group2)

        # Permutation null distribution
        combined = np.concatenate([group1, group2])
        n1 = len(group1)

        null_dist = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            perm = self.rng.permutation(combined)
            null_dist[i] = np.mean(perm[:n1]) - np.mean(perm[n1:])

        # P-value
        if alternative == "two-sided":
            p_value = np.mean(np.abs(null_dist) >= np.abs(observed))
        elif alternative == "greater":
            p_value = np.mean(null_dist >= observed)
        else:
            p_value = np.mean(null_dist <= observed)

        decision = "reject_null" if p_value < alpha else "fail_to_reject_null"

        interpretation = (
            f"Mean difference = {observed:.4f}, p = {p_value:.4f}. "
            f"{'Reject' if decision == 'reject_null' else 'Fail to reject'} "
            f"null hypothesis at alpha = {alpha}."
        )

        return BootstrapTestResult(
            test_name="Two-sample permutation test",
            observed_statistic=float(observed),
            p_value=float(p_value),
            null_distribution=null_dist,
            alternative=alternative,
            n_bootstrap=self.n_bootstrap,
            alpha=alpha,
            decision=decision,
            interpretation=interpretation,
        )

    def paired_test(
        self,
        before: np.ndarray,
        after: np.ndarray,
        alternative: str = "two-sided",
        alpha: float = 0.05,
    ) -> BootstrapTestResult:
        """
        Paired bootstrap test.

        Args:
            before: Pre-treatment measurements
            after: Post-treatment measurements
            alternative: 'two-sided', 'greater', or 'less'
            alpha: Significance level

        Returns:
            BootstrapTestResult
        """
        before = np.asarray(before).flatten()
        after = np.asarray(after).flatten()

        if len(before) != len(after):
            raise ValueError("Paired samples must have equal length")

        differences = after - before
        observed = np.mean(differences)

        # Permutation: randomly flip signs
        null_dist = np.zeros(self.n_bootstrap)
        for i in range(self.n_bootstrap):
            signs = self.rng.choice([-1, 1], size=len(differences))
            null_dist[i] = np.mean(differences * signs)

        if alternative == "two-sided":
            p_value = np.mean(np.abs(null_dist) >= np.abs(observed))
        elif alternative == "greater":
            p_value = np.mean(null_dist >= observed)
        else:
            p_value = np.mean(null_dist <= observed)

        decision = "reject_null" if p_value < alpha else "fail_to_reject_null"

        interpretation = (
            f"Mean difference = {observed:.4f}, p = {p_value:.4f}. "
            f"{'Reject' if decision == 'reject_null' else 'Fail to reject'} "
            f"null hypothesis at alpha = {alpha}."
        )

        return BootstrapTestResult(
            test_name="Paired permutation test",
            observed_statistic=float(observed),
            p_value=float(p_value),
            null_distribution=null_dist,
            alternative=alternative,
            n_bootstrap=self.n_bootstrap,
            alpha=alpha,
            decision=decision,
            interpretation=interpretation,
        )


class PermutationTest:
    """
    Permutation-based hypothesis tests.

    More exact than bootstrap for hypothesis testing.
    """

    def __init__(
        self,
        n_permutations: int = 10000,
        random_state: Optional[int] = None
    ):
        """
        Initialize permutation tester.

        Args:
            n_permutations: Number of permutations
            random_state: Random seed
        """
        self.n_permutations = n_permutations
        self.rng = np.random.default_rng(random_state)

    def two_sample(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        statistic: str = "mean_diff",
        alternative: str = "two-sided",
        alpha: float = 0.05,
    ) -> BootstrapTestResult:
        """
        Permutation test for two independent samples.

        Args:
            group1: First group data
            group2: Second group data
            statistic: 'mean_diff', 't_stat', or callable
            alternative: 'two-sided', 'greater', or 'less'
            alpha: Significance level

        Returns:
            BootstrapTestResult
        """
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()

        # Define statistic function
        if statistic == "mean_diff":
            stat_func = lambda g1, g2: np.mean(g1) - np.mean(g2)
        elif statistic == "t_stat":
            def stat_func(g1, g2):
                n1, n2 = len(g1), len(g2)
                s1, s2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
                se = np.sqrt(s1/n1 + s2/n2)
                return (np.mean(g1) - np.mean(g2)) / se if se > 0 else 0
        elif callable(statistic):
            stat_func = statistic
        else:
            raise ValueError(f"Unknown statistic: {statistic}")

        # Observed
        observed = stat_func(group1, group2)

        # Permutation distribution
        combined = np.concatenate([group1, group2])
        n1 = len(group1)

        perm_dist = np.zeros(self.n_permutations)
        for i in range(self.n_permutations):
            perm = self.rng.permutation(combined)
            perm_dist[i] = stat_func(perm[:n1], perm[n1:])

        # P-value
        if alternative == "two-sided":
            p_value = (np.sum(np.abs(perm_dist) >= np.abs(observed)) + 1) / (self.n_permutations + 1)
        elif alternative == "greater":
            p_value = (np.sum(perm_dist >= observed) + 1) / (self.n_permutations + 1)
        else:
            p_value = (np.sum(perm_dist <= observed) + 1) / (self.n_permutations + 1)

        decision = "reject_null" if p_value < alpha else "fail_to_reject_null"

        return BootstrapTestResult(
            test_name=f"Permutation test ({statistic})",
            observed_statistic=float(observed),
            p_value=float(p_value),
            null_distribution=perm_dist,
            alternative=alternative,
            n_bootstrap=self.n_permutations,
            alpha=alpha,
            decision=decision,
            interpretation=f"Observed = {observed:.4f}, p = {p_value:.4f}",
        )

    def correlation(
        self,
        x: np.ndarray,
        y: np.ndarray,
        alternative: str = "two-sided",
        alpha: float = 0.05,
    ) -> BootstrapTestResult:
        """
        Permutation test for correlation.

        Args:
            x: First variable
            y: Second variable
            alternative: 'two-sided', 'greater', or 'less'
            alpha: Significance level

        Returns:
            BootstrapTestResult
        """
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        if len(x) != len(y):
            raise ValueError("Arrays must have equal length")

        # Observed correlation
        observed = np.corrcoef(x, y)[0, 1]

        # Permutation distribution (permute y)
        perm_dist = np.zeros(self.n_permutations)
        for i in range(self.n_permutations):
            y_perm = self.rng.permutation(y)
            perm_dist[i] = np.corrcoef(x, y_perm)[0, 1]

        # P-value
        if alternative == "two-sided":
            p_value = (np.sum(np.abs(perm_dist) >= np.abs(observed)) + 1) / (self.n_permutations + 1)
        elif alternative == "greater":
            p_value = (np.sum(perm_dist >= observed) + 1) / (self.n_permutations + 1)
        else:
            p_value = (np.sum(perm_dist <= observed) + 1) / (self.n_permutations + 1)

        decision = "reject_null" if p_value < alpha else "fail_to_reject_null"

        return BootstrapTestResult(
            test_name="Permutation correlation test",
            observed_statistic=float(observed),
            p_value=float(p_value),
            null_distribution=perm_dist,
            alternative=alternative,
            n_bootstrap=self.n_permutations,
            alpha=alpha,
            decision=decision,
            interpretation=f"r = {observed:.4f}, p = {p_value:.4f}",
        )


def bootstrap_ci(
    data: np.ndarray,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_bootstrap: int = 10000,
    confidence_level: float = 0.95,
    method: str = "bca",
) -> Tuple[float, float]:
    """
    Convenience function for bootstrap confidence intervals.

    Args:
        data: Sample data
        statistic: Statistic function
        n_bootstrap: Number of bootstrap samples
        confidence_level: Confidence level
        method: CI method

    Returns:
        Tuple of (lower, upper) bounds
    """
    bs = Bootstrap(n_bootstrap=n_bootstrap, confidence_level=confidence_level)
    result = bs.confidence_interval(data, statistic, method=method)
    return result.ci_lower, result.ci_upper


def permutation_test(
    group1: np.ndarray,
    group2: np.ndarray,
    n_permutations: int = 10000,
    alternative: str = "two-sided",
) -> float:
    """
    Convenience function for two-sample permutation test.

    Args:
        group1: First group data
        group2: Second group data
        n_permutations: Number of permutations
        alternative: Alternative hypothesis

    Returns:
        P-value
    """
    pt = PermutationTest(n_permutations=n_permutations)
    result = pt.two_sample(group1, group2, alternative=alternative)
    return result.p_value
