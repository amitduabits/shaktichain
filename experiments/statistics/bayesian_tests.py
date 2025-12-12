"""
Bayesian Statistical Tests Module.

Provides Bayesian alternatives to classical hypothesis tests:
- Bayesian t-tests (one-sample, two-sample, paired)
- Bayesian ANOVA
- Bayesian correlation
- Bayesian proportion tests
- Bayes factors
- Credible intervals

Uses conjugate priors where possible for analytical solutions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats
from scipy.special import betaln, gammaln

logger = logging.getLogger(__name__)


class BayesFactorInterpretation(Enum):
    """Interpretation of Bayes factor strength."""
    EXTREME_H1 = "extreme_h1"  # BF > 100
    VERY_STRONG_H1 = "very_strong_h1"  # 30 < BF <= 100
    STRONG_H1 = "strong_h1"  # 10 < BF <= 30
    MODERATE_H1 = "moderate_h1"  # 3 < BF <= 10
    ANECDOTAL_H1 = "anecdotal_h1"  # 1 < BF <= 3
    NO_EVIDENCE = "no_evidence"  # BF = 1
    ANECDOTAL_H0 = "anecdotal_h0"  # 1/3 < BF < 1
    MODERATE_H0 = "moderate_h0"  # 1/10 < BF <= 1/3
    STRONG_H0 = "strong_h0"  # 1/30 < BF <= 1/10
    VERY_STRONG_H0 = "very_strong_h0"  # 1/100 < BF <= 1/30
    EXTREME_H0 = "extreme_h0"  # BF <= 1/100


@dataclass
class BayesianTestResult:
    """
    Result of a Bayesian hypothesis test.

    Attributes:
        test_name: Name of the test
        bayes_factor: BF10 (evidence for H1 over H0)
        bf_interpretation: Qualitative interpretation
        posterior_mean: Posterior mean of parameter
        posterior_std: Posterior standard deviation
        credible_interval: Highest density interval
        credible_level: Credible interval level
        prior_description: Description of prior used
        posterior_description: Description of posterior
        rope: Region of practical equivalence (if used)
        probability_in_rope: Probability parameter is in ROPE
        interpretation: Human-readable interpretation
        additional_info: Extra information
    """
    test_name: str
    bayes_factor: float
    bf_interpretation: BayesFactorInterpretation
    posterior_mean: float
    posterior_std: float
    credible_interval: Tuple[float, float]
    credible_level: float
    prior_description: str
    posterior_description: str
    rope: Optional[Tuple[float, float]] = None
    probability_in_rope: Optional[float] = None
    interpretation: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "bayes_factor": self.bayes_factor,
            "bf_interpretation": self.bf_interpretation.value,
            "posterior_mean": self.posterior_mean,
            "posterior_std": self.posterior_std,
            "credible_interval": self.credible_interval,
            "credible_level": self.credible_level,
            "prior_description": self.prior_description,
            "posterior_description": self.posterior_description,
            "rope": self.rope,
            "probability_in_rope": self.probability_in_rope,
            "interpretation": self.interpretation,
            "additional_info": self.additional_info,
        }

    def summary(self) -> str:
        """Generate summary string."""
        return (
            f"Test: {self.test_name}\n"
            f"BF10 = {self.bayes_factor:.4f} ({self.bf_interpretation.value})\n"
            f"Posterior: {self.posterior_mean:.4f} +/- {self.posterior_std:.4f}\n"
            f"{self.credible_level*100:.0f}% CI: [{self.credible_interval[0]:.4f}, {self.credible_interval[1]:.4f}]"
        )


def interpret_bayes_factor(bf: float) -> BayesFactorInterpretation:
    """
    Interpret Bayes factor using Jeffreys' scale.

    Args:
        bf: Bayes factor (BF10)

    Returns:
        BayesFactorInterpretation enum
    """
    if bf > 100:
        return BayesFactorInterpretation.EXTREME_H1
    elif bf > 30:
        return BayesFactorInterpretation.VERY_STRONG_H1
    elif bf > 10:
        return BayesFactorInterpretation.STRONG_H1
    elif bf > 3:
        return BayesFactorInterpretation.MODERATE_H1
    elif bf > 1:
        return BayesFactorInterpretation.ANECDOTAL_H1
    elif bf == 1:
        return BayesFactorInterpretation.NO_EVIDENCE
    elif bf > 1/3:
        return BayesFactorInterpretation.ANECDOTAL_H0
    elif bf > 1/10:
        return BayesFactorInterpretation.MODERATE_H0
    elif bf > 1/30:
        return BayesFactorInterpretation.STRONG_H0
    elif bf > 1/100:
        return BayesFactorInterpretation.VERY_STRONG_H0
    else:
        return BayesFactorInterpretation.EXTREME_H0


class BayesianTester:
    """
    Bayesian hypothesis testing suite.

    Provides Bayesian alternatives to common frequentist tests.
    """

    def __init__(
        self,
        credible_level: float = 0.95,
        default_prior_scale: float = 1.0
    ):
        """
        Initialize Bayesian tester.

        Args:
            credible_level: Level for credible intervals
            default_prior_scale: Default scale for priors (Cauchy scale)
        """
        self.credible_level = credible_level
        self.prior_scale = default_prior_scale

    def one_sample_t_test(
        self,
        data: np.ndarray,
        null_value: float = 0,
        prior_scale: Optional[float] = None,
        rope: Optional[Tuple[float, float]] = None,
    ) -> BayesianTestResult:
        """
        Bayesian one-sample t-test.

        Uses JZS (Jeffreys-Zellner-Siow) prior on effect size.

        Args:
            data: Sample data
            null_value: Value under null hypothesis
            prior_scale: Cauchy prior scale (r parameter)
            rope: Region of practical equivalence

        Returns:
            BayesianTestResult
        """
        data = np.asarray(data).flatten()
        n = len(data)
        r = prior_scale or self.prior_scale

        # Compute statistics
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        se = std / np.sqrt(n)
        t_stat = (mean - null_value) / se
        df = n - 1

        # Effect size
        d = (mean - null_value) / std

        # JZS Bayes factor (approximation)
        bf10 = self._jzs_bf(t_stat, n, r)

        # Posterior for effect size (approximately t-distribution)
        # Using scaled-shifted t as posterior approximation
        posterior_mean = d
        posterior_std = np.sqrt(1/n + d**2 / (2*n))

        # Credible interval
        alpha = 1 - self.credible_level
        ci_lower = posterior_mean - stats.t.ppf(1 - alpha/2, df) * posterior_std
        ci_upper = posterior_mean + stats.t.ppf(1 - alpha/2, df) * posterior_std

        # ROPE analysis
        prob_rope = None
        if rope is not None:
            prob_rope = stats.t.cdf((rope[1] - posterior_mean) / posterior_std, df) - \
                       stats.t.cdf((rope[0] - posterior_mean) / posterior_std, df)

        bf_interp = interpret_bayes_factor(bf10)

        interpretation = (
            f"Bayesian one-sample t-test: BF10 = {bf10:.4f} ({bf_interp.value}). "
            f"Posterior effect size d = {posterior_mean:.4f}, "
            f"{self.credible_level*100:.0f}% CI [{ci_lower:.4f}, {ci_upper:.4f}]"
        )

        return BayesianTestResult(
            test_name="Bayesian one-sample t-test",
            bayes_factor=bf10,
            bf_interpretation=bf_interp,
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval=(ci_lower, ci_upper),
            credible_level=self.credible_level,
            prior_description=f"Cauchy(0, {r}) prior on effect size",
            posterior_description=f"Scaled t({df}) posterior on effect size",
            rope=rope,
            probability_in_rope=prob_rope,
            interpretation=interpretation,
            additional_info={
                "t_statistic": float(t_stat),
                "df": df,
                "effect_size_d": float(d),
                "sample_mean": float(mean),
                "sample_std": float(std),
                "n": n,
            },
        )

    def two_sample_t_test(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        prior_scale: Optional[float] = None,
        rope: Optional[Tuple[float, float]] = None,
    ) -> BayesianTestResult:
        """
        Bayesian two-sample t-test.

        Args:
            group1: First group data
            group2: Second group data
            prior_scale: Cauchy prior scale
            rope: Region of practical equivalence

        Returns:
            BayesianTestResult
        """
        group1 = np.asarray(group1).flatten()
        group2 = np.asarray(group2).flatten()
        n1, n2 = len(group1), len(group2)
        r = prior_scale or self.prior_scale

        mean1, mean2 = np.mean(group1), np.mean(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

        # Pooled variance
        pooled_var = ((n1-1)*var1 + (n2-1)*var2) / (n1 + n2 - 2)
        pooled_std = np.sqrt(pooled_var)

        # T-statistic
        se = pooled_std * np.sqrt(1/n1 + 1/n2)
        t_stat = (mean1 - mean2) / se
        df = n1 + n2 - 2

        # Effect size
        d = (mean1 - mean2) / pooled_std

        # JZS Bayes factor
        n_eff = (n1 * n2) / (n1 + n2)
        bf10 = self._jzs_bf(t_stat, n_eff, r)

        # Posterior
        posterior_mean = d
        posterior_std = np.sqrt(1/n1 + 1/n2 + d**2 / (2*(n1 + n2 - 2)))

        # Credible interval
        alpha = 1 - self.credible_level
        ci_lower = posterior_mean - stats.t.ppf(1 - alpha/2, df) * posterior_std
        ci_upper = posterior_mean + stats.t.ppf(1 - alpha/2, df) * posterior_std

        # ROPE
        prob_rope = None
        if rope is not None:
            prob_rope = stats.t.cdf((rope[1] - posterior_mean) / posterior_std, df) - \
                       stats.t.cdf((rope[0] - posterior_mean) / posterior_std, df)

        bf_interp = interpret_bayes_factor(bf10)

        interpretation = (
            f"Bayesian two-sample t-test: BF10 = {bf10:.4f} ({bf_interp.value}). "
            f"Posterior effect size d = {posterior_mean:.4f}"
        )

        return BayesianTestResult(
            test_name="Bayesian two-sample t-test",
            bayes_factor=bf10,
            bf_interpretation=bf_interp,
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval=(ci_lower, ci_upper),
            credible_level=self.credible_level,
            prior_description=f"Cauchy(0, {r}) prior on effect size",
            posterior_description=f"Scaled t({df}) posterior on effect size",
            rope=rope,
            probability_in_rope=prob_rope,
            interpretation=interpretation,
            additional_info={
                "t_statistic": float(t_stat),
                "df": df,
                "effect_size_d": float(d),
                "mean_diff": float(mean1 - mean2),
                "n1": n1,
                "n2": n2,
            },
        )

    def paired_t_test(
        self,
        before: np.ndarray,
        after: np.ndarray,
        prior_scale: Optional[float] = None,
        rope: Optional[Tuple[float, float]] = None,
    ) -> BayesianTestResult:
        """
        Bayesian paired t-test.

        Args:
            before: Pre-treatment measurements
            after: Post-treatment measurements
            prior_scale: Cauchy prior scale
            rope: Region of practical equivalence

        Returns:
            BayesianTestResult
        """
        before = np.asarray(before).flatten()
        after = np.asarray(after).flatten()

        if len(before) != len(after):
            raise ValueError("Paired samples must have equal length")

        differences = after - before
        return self.one_sample_t_test(differences, null_value=0,
                                      prior_scale=prior_scale, rope=rope)

    def proportion_test(
        self,
        successes: int,
        n: int,
        null_proportion: float = 0.5,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
    ) -> BayesianTestResult:
        """
        Bayesian proportion test.

        Uses Beta-Binomial conjugate prior.

        Args:
            successes: Number of successes
            n: Total trials
            null_proportion: Proportion under H0
            prior_alpha: Beta prior alpha parameter
            prior_beta: Beta prior beta parameter

        Returns:
            BayesianTestResult
        """
        # Posterior parameters (Beta-Binomial conjugacy)
        post_alpha = prior_alpha + successes
        post_beta = prior_beta + n - successes

        # Posterior mean and std
        posterior_mean = post_alpha / (post_alpha + post_beta)
        posterior_var = (post_alpha * post_beta) / \
                       ((post_alpha + post_beta)**2 * (post_alpha + post_beta + 1))
        posterior_std = np.sqrt(posterior_var)

        # Credible interval
        alpha = 1 - self.credible_level
        ci_lower = stats.beta.ppf(alpha/2, post_alpha, post_beta)
        ci_upper = stats.beta.ppf(1 - alpha/2, post_alpha, post_beta)

        # Savage-Dickey density ratio for point null
        # BF10 = prior density at null / posterior density at null
        prior_density_null = stats.beta.pdf(null_proportion, prior_alpha, prior_beta)
        post_density_null = stats.beta.pdf(null_proportion, post_alpha, post_beta)

        if post_density_null > 0:
            bf10 = 1 / (post_density_null / prior_density_null)
        else:
            bf10 = float('inf')

        bf_interp = interpret_bayes_factor(bf10)

        # Probability that proportion differs from null
        prob_greater = 1 - stats.beta.cdf(null_proportion, post_alpha, post_beta)
        prob_less = stats.beta.cdf(null_proportion, post_alpha, post_beta)

        interpretation = (
            f"Bayesian proportion test: BF10 = {bf10:.4f} ({bf_interp.value}). "
            f"Posterior proportion = {posterior_mean:.4f}, "
            f"P(p > {null_proportion}) = {prob_greater:.4f}"
        )

        return BayesianTestResult(
            test_name="Bayesian proportion test",
            bayes_factor=bf10,
            bf_interpretation=bf_interp,
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval=(ci_lower, ci_upper),
            credible_level=self.credible_level,
            prior_description=f"Beta({prior_alpha}, {prior_beta}) prior",
            posterior_description=f"Beta({post_alpha}, {post_beta}) posterior",
            interpretation=interpretation,
            additional_info={
                "successes": successes,
                "n": n,
                "observed_proportion": successes / n,
                "prob_greater_null": float(prob_greater),
                "prob_less_null": float(prob_less),
            },
        )

    def correlation_test(
        self,
        x: np.ndarray,
        y: np.ndarray,
        prior_kappa: float = 1.0,
    ) -> BayesianTestResult:
        """
        Bayesian correlation test.

        Uses stretched beta prior on correlation.

        Args:
            x: First variable
            y: Second variable
            prior_kappa: Concentration parameter (1 = uniform on [-1, 1])

        Returns:
            BayesianTestResult
        """
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()

        if len(x) != len(y):
            raise ValueError("Arrays must have equal length")

        n = len(x)
        r = np.corrcoef(x, y)[0, 1]

        # Fisher's z transformation for posterior
        z = 0.5 * np.log((1 + r) / (1 - r)) if abs(r) < 1 else np.sign(r) * 10
        se_z = 1 / np.sqrt(n - 3) if n > 3 else 0.5

        # Approximate Bayes factor using Wetzels & Wagenmakers (2012) method
        # Simplified: based on sample correlation and sample size
        bf10 = self._correlation_bf(r, n, prior_kappa)

        # Posterior (approximately normal in z-space)
        posterior_mean = r
        posterior_std = (1 - r**2) / np.sqrt(n - 3) if n > 3 else 0.2

        # Credible interval (back-transformed from z)
        alpha = 1 - self.credible_level
        z_crit = stats.norm.ppf(1 - alpha/2)
        z_lower = z - z_crit * se_z
        z_upper = z + z_crit * se_z
        ci_lower = (np.exp(2*z_lower) - 1) / (np.exp(2*z_lower) + 1)
        ci_upper = (np.exp(2*z_upper) - 1) / (np.exp(2*z_upper) + 1)

        bf_interp = interpret_bayes_factor(bf10)

        interpretation = (
            f"Bayesian correlation: BF10 = {bf10:.4f} ({bf_interp.value}). "
            f"Posterior r = {posterior_mean:.4f}"
        )

        return BayesianTestResult(
            test_name="Bayesian correlation test",
            bayes_factor=bf10,
            bf_interpretation=bf_interp,
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval=(ci_lower, ci_upper),
            credible_level=self.credible_level,
            prior_description=f"Stretched beta prior (kappa={prior_kappa})",
            posterior_description="Approximate posterior on correlation",
            interpretation=interpretation,
            additional_info={
                "sample_r": float(r),
                "fisher_z": float(z),
                "n": n,
            },
        )

    def _jzs_bf(self, t: float, n: float, r: float = 1.0) -> float:
        """
        Compute JZS Bayes factor for t-statistic.

        Uses Rouder et al. (2009) approximation.

        Args:
            t: T-statistic
            n: Sample size (or effective sample size)
            r: Cauchy prior scale

        Returns:
            BF10
        """
        # Degrees of freedom
        df = n - 1 if n > 1 else 1

        # Numerical integration for exact BF is complex
        # Use Rouder's approximation based on BIC

        # Simple approximation using BIC
        # BF10 ≈ sqrt(n) * exp(-t^2/2) for large n under JZS prior
        # More accurate approximation:
        bf10 = np.sqrt((1 + n * r**2) / (1 + n)) * \
               np.exp(0.5 * t**2 * n * r**2 / (1 + n * r**2))

        # Correction for small samples
        if n < 30:
            correction = np.sqrt(df / (df - 2)) if df > 2 else 1
            bf10 *= correction

        return float(bf10)

    def _correlation_bf(self, r: float, n: int, kappa: float = 1.0) -> float:
        """
        Compute Bayes factor for correlation.

        Args:
            r: Sample correlation
            n: Sample size
            kappa: Prior concentration

        Returns:
            BF10
        """
        # Approximation based on Jeffreys (1961)
        # BF10 ≈ sqrt(n/2π) * (1-r^2)^((n-3)/2) * hypergeometric term

        if n <= 3:
            return 1.0

        # Simplified approximation
        log_bf = 0.5 * np.log(n / (2 * np.pi))
        log_bf += ((n - 3) / 2) * np.log(1 - r**2)
        log_bf += gammaln((n-1)/2) - gammaln((n-2)/2)

        bf10 = np.exp(log_bf) if log_bf < 700 else float('inf')

        return float(max(0.001, bf10))

    def anova(
        self,
        *groups: np.ndarray,
        prior_scale: Optional[float] = None,
    ) -> BayesianTestResult:
        """
        Bayesian one-way ANOVA.

        Args:
            *groups: Variable number of group arrays
            prior_scale: Prior scale for effect sizes

        Returns:
            BayesianTestResult
        """
        groups = [np.asarray(g).flatten() for g in groups]
        k = len(groups)

        if k < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        r = prior_scale or self.prior_scale

        # Classical ANOVA statistics
        f_stat, p_value = stats.f_oneway(*groups)

        all_data = np.concatenate(groups)
        grand_mean = np.mean(all_data)
        n_total = len(all_data)
        ns = [len(g) for g in groups]

        # Effect size (eta-squared)
        ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in groups)
        ss_total = sum((x - grand_mean)**2 for x in all_data)
        eta_sq = ss_between / ss_total if ss_total > 0 else 0

        # Cohen's f
        f_effect = np.sqrt(eta_sq / (1 - eta_sq)) if eta_sq < 1 else float('inf')

        # BF approximation using BIC
        # BF10 ≈ exp(-0.5 * (BIC_H0 - BIC_H1))
        df_between = k - 1
        df_within = n_total - k

        # Log BF approximation
        log_bf = 0.5 * df_between * np.log(n_total)
        log_bf += 0.5 * df_within * np.log(1 + f_stat * df_between / df_within)

        bf10 = np.exp(log_bf) if log_bf < 700 else float('inf')
        bf10 = min(bf10, 1e10)  # Cap at reasonable value

        bf_interp = interpret_bayes_factor(bf10)

        # Posterior on effect size (approximation)
        posterior_mean = f_effect
        posterior_std = f_effect / np.sqrt(2 * n_total)  # Rough approximation

        # Credible interval
        alpha = 1 - self.credible_level
        ci_lower = max(0, posterior_mean - 2 * posterior_std)
        ci_upper = posterior_mean + 2 * posterior_std

        interpretation = (
            f"Bayesian ANOVA: BF10 = {bf10:.4f} ({bf_interp.value}). "
            f"Posterior Cohen's f = {posterior_mean:.4f}"
        )

        return BayesianTestResult(
            test_name="Bayesian ANOVA",
            bayes_factor=bf10,
            bf_interpretation=bf_interp,
            posterior_mean=posterior_mean,
            posterior_std=posterior_std,
            credible_interval=(ci_lower, ci_upper),
            credible_level=self.credible_level,
            prior_description=f"JZS prior with scale {r}",
            posterior_description="Approximate posterior on Cohen's f",
            interpretation=interpretation,
            additional_info={
                "f_statistic": float(f_stat),
                "p_value_classical": float(p_value),
                "eta_squared": float(eta_sq),
                "cohens_f": float(f_effect),
                "k_groups": k,
                "group_sizes": ns,
            },
        )


class BayesFactorCalculator:
    """
    Direct Bayes factor calculations for various scenarios.
    """

    @staticmethod
    def bf_from_t(t: float, n: int, r: float = 0.707) -> float:
        """
        BF10 from t-statistic.

        Args:
            t: T-statistic
            n: Sample size
            r: Prior scale (default sqrt(2)/2)

        Returns:
            BF10
        """
        tester = BayesianTester()
        return tester._jzs_bf(t, n, r)

    @staticmethod
    def bf_from_f(f: float, df1: int, df2: int, r: float = 0.5) -> float:
        """
        BF10 from F-statistic.

        Args:
            f: F-statistic
            df1: Numerator df
            df2: Denominator df
            r: Prior scale

        Returns:
            BF10
        """
        n_total = df1 + df2 + 1

        # BIC approximation
        log_bf = 0.5 * df1 * np.log(n_total)
        log_bf += 0.5 * df2 * np.log(1 + f * df1 / df2)

        return float(np.exp(log_bf))

    @staticmethod
    def bf_from_r(r: float, n: int) -> float:
        """
        BF10 from correlation.

        Args:
            r: Sample correlation
            n: Sample size

        Returns:
            BF10
        """
        tester = BayesianTester()
        return tester._correlation_bf(r, n)

    @staticmethod
    def bf_from_proportion(
        successes: int,
        n: int,
        null_p: float = 0.5
    ) -> float:
        """
        BF10 for proportion against point null.

        Args:
            successes: Number of successes
            n: Total trials
            null_p: Null proportion

        Returns:
            BF10
        """
        # Beta(1,1) prior (uniform)
        # Savage-Dickey ratio
        prior_at_null = 1.0  # Uniform prior
        post_alpha = 1 + successes
        post_beta = 1 + n - successes
        post_at_null = stats.beta.pdf(null_p, post_alpha, post_beta)

        return prior_at_null / post_at_null if post_at_null > 0 else float('inf')


class RopeAnalysis:
    """
    Region of Practical Equivalence (ROPE) analysis.

    Determines whether effect is practically meaningful.
    """

    def __init__(self, rope_lower: float, rope_upper: float):
        """
        Initialize ROPE analysis.

        Args:
            rope_lower: Lower bound of ROPE
            rope_upper: Upper bound of ROPE
        """
        self.rope_lower = rope_lower
        self.rope_upper = rope_upper

    def analyze_posterior(
        self,
        posterior_samples: np.ndarray,
        credible_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Analyze posterior samples against ROPE.

        Args:
            posterior_samples: MCMC or bootstrap posterior samples
            credible_level: HDI level

        Returns:
            ROPE analysis results
        """
        samples = np.asarray(posterior_samples).flatten()

        # Proportion in ROPE
        in_rope = np.mean((samples >= self.rope_lower) & (samples <= self.rope_upper))

        # Proportion above/below ROPE
        above_rope = np.mean(samples > self.rope_upper)
        below_rope = np.mean(samples < self.rope_lower)

        # HDI
        hdi = self._hdi(samples, credible_level)

        # Decision based on HDI and ROPE
        if hdi[0] > self.rope_upper:
            decision = "accept_alternative_positive"
        elif hdi[1] < self.rope_lower:
            decision = "accept_alternative_negative"
        elif hdi[0] >= self.rope_lower and hdi[1] <= self.rope_upper:
            decision = "accept_null"
        else:
            decision = "undecided"

        return {
            "rope": (self.rope_lower, self.rope_upper),
            "proportion_in_rope": float(in_rope),
            "proportion_above_rope": float(above_rope),
            "proportion_below_rope": float(below_rope),
            "hdi": hdi,
            "hdi_level": credible_level,
            "decision": decision,
        }

    def _hdi(
        self,
        samples: np.ndarray,
        level: float = 0.95
    ) -> Tuple[float, float]:
        """Compute highest density interval."""
        samples = np.sort(samples)
        n = len(samples)
        interval_width = int(np.ceil(level * n))

        if interval_width >= n:
            return (float(samples[0]), float(samples[-1]))

        # Find narrowest interval
        min_width = float('inf')
        hdi = (samples[0], samples[-1])

        for i in range(n - interval_width):
            width = samples[i + interval_width] - samples[i]
            if width < min_width:
                min_width = width
                hdi = (float(samples[i]), float(samples[i + interval_width]))

        return hdi


def bayesian_t_test(
    group1: np.ndarray,
    group2: Optional[np.ndarray] = None,
    null_value: float = 0,
    paired: bool = False,
    prior_scale: float = 0.707,
) -> BayesianTestResult:
    """
    Convenience function for Bayesian t-test.

    Args:
        group1: First group data (or differences if paired)
        group2: Second group data (optional)
        null_value: Value under H0
        paired: Whether test is paired
        prior_scale: Cauchy prior scale

    Returns:
        BayesianTestResult
    """
    tester = BayesianTester()

    if group2 is None:
        return tester.one_sample_t_test(group1, null_value, prior_scale)
    elif paired:
        return tester.paired_t_test(group1, group2, prior_scale)
    else:
        return tester.two_sample_t_test(group1, group2, prior_scale)


def bayes_factor(
    test_type: str,
    **kwargs
) -> float:
    """
    Convenience function to compute Bayes factor.

    Args:
        test_type: 't', 'f', 'r', or 'proportion'
        **kwargs: Test-specific parameters

    Returns:
        BF10
    """
    calc = BayesFactorCalculator()

    if test_type == 't':
        return calc.bf_from_t(kwargs['t'], kwargs['n'], kwargs.get('r', 0.707))
    elif test_type == 'f':
        return calc.bf_from_f(kwargs['f'], kwargs['df1'], kwargs['df2'])
    elif test_type == 'r':
        return calc.bf_from_r(kwargs['r'], kwargs['n'])
    elif test_type == 'proportion':
        return calc.bf_from_proportion(kwargs['successes'], kwargs['n'],
                                       kwargs.get('null_p', 0.5))
    else:
        raise ValueError(f"Unknown test type: {test_type}")
