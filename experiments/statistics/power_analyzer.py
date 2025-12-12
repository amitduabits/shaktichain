"""
Statistical Power Analysis Module.

Provides power analysis for various statistical tests:
- Sample size determination
- Power calculation
- Effect size estimation
- Sensitivity analysis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class PowerAnalysisType(Enum):
    """Types of power analysis."""
    T_TEST_ONE_SAMPLE = "t_test_one_sample"
    T_TEST_TWO_SAMPLE = "t_test_two_sample"
    T_TEST_PAIRED = "t_test_paired"
    ANOVA = "anova"
    PROPORTION = "proportion"
    CORRELATION = "correlation"
    CHI_SQUARE = "chi_square"


@dataclass
class PowerAnalysisResult:
    """
    Result of power analysis.

    Attributes:
        analysis_type: Type of power analysis
        sample_size: Calculated or given sample size
        effect_size: Effect size used
        alpha: Significance level
        power: Statistical power
        n_groups: Number of groups (for ANOVA)
        direction: One-tailed or two-tailed
        interpretation: Human-readable interpretation
        additional_info: Extra information
    """
    analysis_type: PowerAnalysisType
    sample_size: int
    effect_size: float
    alpha: float
    power: float
    n_groups: int = 2
    direction: str = "two-tailed"
    interpretation: str = ""
    additional_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "analysis_type": self.analysis_type.value,
            "sample_size": self.sample_size,
            "effect_size": self.effect_size,
            "alpha": self.alpha,
            "power": self.power,
            "n_groups": self.n_groups,
            "direction": self.direction,
            "interpretation": self.interpretation,
            "additional_info": self.additional_info,
        }


class PowerAnalyzer:
    """
    Statistical power analyzer.

    Provides methods for:
    - Calculating required sample size
    - Computing achieved power
    - Estimating minimum detectable effect size
    """

    def __init__(self, alpha: float = 0.05, power: float = 0.80):
        """
        Initialize power analyzer.

        Args:
            alpha: Default significance level
            power: Default desired power
        """
        self.alpha = alpha
        self.power = power

    def _t_test_sample_size(
        self,
        effect_size: float,
        alpha: float,
        power: float,
        two_tailed: bool = True,
        ratio: float = 1.0,
    ) -> int:
        """
        Calculate sample size for t-test using iterative method.

        Args:
            effect_size: Cohen's d
            alpha: Significance level
            power: Desired power
            two_tailed: Two-tailed test
            ratio: Ratio of n2/n1 for two-sample

        Returns:
            Required sample size per group
        """
        if effect_size == 0:
            return float('inf')

        # Use normal approximation for initial estimate
        if two_tailed:
            z_alpha = stats.norm.ppf(1 - alpha / 2)
        else:
            z_alpha = stats.norm.ppf(1 - alpha)
        z_power = stats.norm.ppf(power)

        # Initial estimate
        n = 2 * ((z_alpha + z_power) / effect_size) ** 2

        # Iterative refinement using t-distribution
        for _ in range(100):
            df = 2 * n - 2
            if two_tailed:
                t_crit = stats.t.ppf(1 - alpha / 2, df)
            else:
                t_crit = stats.t.ppf(1 - alpha, df)

            # Non-central t parameter
            ncp = effect_size * np.sqrt(n / 2)

            # Achieved power
            achieved_power = 1 - stats.nct.cdf(t_crit, df, ncp)
            if two_tailed:
                achieved_power += stats.nct.cdf(-t_crit, df, ncp)

            if abs(achieved_power - power) < 0.001:
                break

            # Adjust n
            if achieved_power < power:
                n *= 1.1
            else:
                n *= 0.95

        return int(np.ceil(n))

    def sample_size_t_test_one_sample(
        self,
        effect_size: float,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate sample size for one-sample t-test.

        Args:
            effect_size: Cohen's d
            alpha: Significance level
            power: Desired power
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha
        power = power or self.power

        # One-sample uses different formula
        if two_tailed:
            z_alpha = stats.norm.ppf(1 - alpha / 2)
        else:
            z_alpha = stats.norm.ppf(1 - alpha)
        z_power = stats.norm.ppf(power)

        n = ((z_alpha + z_power) / effect_size) ** 2
        n = int(np.ceil(n))

        # Refine with t-distribution
        for _ in range(50):
            df = n - 1
            if two_tailed:
                t_crit = stats.t.ppf(1 - alpha / 2, df)
            else:
                t_crit = stats.t.ppf(1 - alpha, df)

            ncp = effect_size * np.sqrt(n)
            achieved = 1 - stats.nct.cdf(t_crit, df, ncp)
            if two_tailed:
                achieved += stats.nct.cdf(-t_crit, df, ncp)

            if achieved >= power:
                break
            n += 1

        interpretation = (
            f"Need n={n} for {power*100:.0f}% power to detect d={effect_size:.2f} "
            f"at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.T_TEST_ONE_SAMPLE,
            sample_size=n,
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            n_groups=1,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
        )

    def sample_size_t_test_two_sample(
        self,
        effect_size: float,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        ratio: float = 1.0,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate sample size for two-sample t-test.

        Args:
            effect_size: Cohen's d
            alpha: Significance level
            power: Desired power
            ratio: Ratio of n2/n1
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult with sample size per group
        """
        alpha = alpha or self.alpha
        power = power or self.power

        n = self._t_test_sample_size(effect_size, alpha, power, two_tailed, ratio)

        interpretation = (
            f"Need n={n} per group for {power*100:.0f}% power to detect d={effect_size:.2f} "
            f"at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.T_TEST_TWO_SAMPLE,
            sample_size=n,
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            n_groups=2,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
            additional_info={"ratio": ratio, "total_n": int(n * (1 + ratio))},
        )

    def sample_size_paired_t_test(
        self,
        effect_size: float,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate sample size for paired t-test.

        Args:
            effect_size: Cohen's d for paired differences
            alpha: Significance level
            power: Desired power
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        # Paired t-test has same formula as one-sample
        return self.sample_size_t_test_one_sample(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            two_tailed=two_tailed,
        )

    def sample_size_anova(
        self,
        effect_size: float,
        n_groups: int,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
    ) -> PowerAnalysisResult:
        """
        Calculate sample size for one-way ANOVA.

        Args:
            effect_size: Cohen's f
            n_groups: Number of groups
            alpha: Significance level
            power: Desired power

        Returns:
            PowerAnalysisResult with sample size per group
        """
        alpha = alpha or self.alpha
        power = power or self.power

        if n_groups < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        # Convert Cohen's f to lambda
        # f = sqrt(sum(nj*(muj-mu)^2) / (k*sigma^2)) / sqrt(k)

        df1 = n_groups - 1

        # Iterative search for n
        n = 5  # Start with minimum reasonable sample size

        for _ in range(1000):
            df2 = n_groups * (n - 1)
            # Non-centrality parameter
            ncp = n * n_groups * effect_size ** 2

            # Critical F
            f_crit = stats.f.ppf(1 - alpha, df1, df2)

            # Power = P(F > f_crit | ncp)
            achieved_power = 1 - stats.ncf.cdf(f_crit, df1, df2, ncp)

            if achieved_power >= power:
                break
            n += 1

        interpretation = (
            f"Need n={n} per group ({n_groups} groups) for {power*100:.0f}% power "
            f"to detect f={effect_size:.2f} at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.ANOVA,
            sample_size=n,
            effect_size=effect_size,
            alpha=alpha,
            power=achieved_power,
            n_groups=n_groups,
            direction="two-tailed",
            interpretation=interpretation,
            additional_info={"total_n": n * n_groups, "df1": df1, "df2": df2},
        )

    def sample_size_proportion(
        self,
        p1: float,
        p2: float,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        ratio: float = 1.0,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate sample size for proportion comparison.

        Args:
            p1: Proportion in group 1
            p2: Proportion in group 2
            alpha: Significance level
            power: Desired power
            ratio: Ratio of n2/n1
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha
        power = power or self.power

        # Effect size (Cohen's h)
        h = 2 * (np.arcsin(np.sqrt(p1)) - np.arcsin(np.sqrt(p2)))

        if two_tailed:
            z_alpha = stats.norm.ppf(1 - alpha / 2)
        else:
            z_alpha = stats.norm.ppf(1 - alpha)
        z_power = stats.norm.ppf(power)

        # Sample size using arcsine transformation
        p_bar = (p1 + ratio * p2) / (1 + ratio)

        n1 = (z_alpha * np.sqrt((1 + 1/ratio) * p_bar * (1 - p_bar)) +
              z_power * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / ratio)) ** 2 / (p1 - p2) ** 2

        n1 = int(np.ceil(n1))
        n2 = int(np.ceil(n1 * ratio))

        interpretation = (
            f"Need n1={n1}, n2={n2} for {power*100:.0f}% power to detect "
            f"p1={p1:.3f} vs p2={p2:.3f} at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.PROPORTION,
            sample_size=n1,
            effect_size=abs(h),
            alpha=alpha,
            power=power,
            n_groups=2,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
            additional_info={
                "n1": n1,
                "n2": n2,
                "p1": p1,
                "p2": p2,
                "cohens_h": float(h),
            },
        )

    def sample_size_correlation(
        self,
        r: float,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate sample size for correlation test.

        Args:
            r: Expected correlation
            alpha: Significance level
            power: Desired power
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha
        power = power or self.power

        if abs(r) >= 1:
            raise ValueError("Correlation must be between -1 and 1")

        if two_tailed:
            z_alpha = stats.norm.ppf(1 - alpha / 2)
        else:
            z_alpha = stats.norm.ppf(1 - alpha)
        z_power = stats.norm.ppf(power)

        # Fisher's z transformation
        z_r = 0.5 * np.log((1 + r) / (1 - r))

        # Sample size
        n = ((z_alpha + z_power) / z_r) ** 2 + 3

        n = int(np.ceil(n))

        interpretation = (
            f"Need n={n} for {power*100:.0f}% power to detect r={r:.3f} "
            f"at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.CORRELATION,
            sample_size=n,
            effect_size=abs(r),
            alpha=alpha,
            power=power,
            n_groups=1,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
            additional_info={"fisher_z": float(z_r)},
        )

    def power_t_test_one_sample(
        self,
        n: int,
        effect_size: float,
        alpha: Optional[float] = None,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate power for one-sample t-test.

        Args:
            n: Sample size
            effect_size: Cohen's d
            alpha: Significance level
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha
        df = n - 1

        if two_tailed:
            t_crit = stats.t.ppf(1 - alpha / 2, df)
        else:
            t_crit = stats.t.ppf(1 - alpha, df)

        ncp = effect_size * np.sqrt(n)

        power = 1 - stats.nct.cdf(t_crit, df, ncp)
        if two_tailed:
            power += stats.nct.cdf(-t_crit, df, ncp)

        interpretation = (
            f"Power = {power*100:.1f}% with n={n} to detect d={effect_size:.2f} "
            f"at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.T_TEST_ONE_SAMPLE,
            sample_size=n,
            effect_size=effect_size,
            alpha=alpha,
            power=float(power),
            n_groups=1,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
        )

    def power_t_test_two_sample(
        self,
        n: int,
        effect_size: float,
        alpha: Optional[float] = None,
        ratio: float = 1.0,
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate power for two-sample t-test.

        Args:
            n: Sample size per group (or n1 if ratio != 1)
            effect_size: Cohen's d
            alpha: Significance level
            ratio: Ratio of n2/n1
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha

        n1 = n
        n2 = int(n * ratio)
        df = n1 + n2 - 2

        if two_tailed:
            t_crit = stats.t.ppf(1 - alpha / 2, df)
        else:
            t_crit = stats.t.ppf(1 - alpha, df)

        # Non-centrality parameter for unequal n
        ncp = effect_size / np.sqrt(1/n1 + 1/n2)

        power = 1 - stats.nct.cdf(t_crit, df, ncp)
        if two_tailed:
            power += stats.nct.cdf(-t_crit, df, ncp)

        interpretation = (
            f"Power = {power*100:.1f}% with n={n} per group to detect d={effect_size:.2f} "
            f"at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.T_TEST_TWO_SAMPLE,
            sample_size=n,
            effect_size=effect_size,
            alpha=alpha,
            power=float(power),
            n_groups=2,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
            additional_info={"n1": n1, "n2": n2, "total_n": n1 + n2},
        )

    def power_anova(
        self,
        n: int,
        effect_size: float,
        n_groups: int,
        alpha: Optional[float] = None,
    ) -> PowerAnalysisResult:
        """
        Calculate power for one-way ANOVA.

        Args:
            n: Sample size per group
            effect_size: Cohen's f
            n_groups: Number of groups
            alpha: Significance level

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha

        df1 = n_groups - 1
        df2 = n_groups * (n - 1)

        # Non-centrality parameter
        ncp = n * n_groups * effect_size ** 2

        # Critical F
        f_crit = stats.f.ppf(1 - alpha, df1, df2)

        # Power
        power = 1 - stats.ncf.cdf(f_crit, df1, df2, ncp)

        interpretation = (
            f"Power = {power*100:.1f}% with n={n} per group ({n_groups} groups) "
            f"to detect f={effect_size:.2f} at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.ANOVA,
            sample_size=n,
            effect_size=effect_size,
            alpha=alpha,
            power=float(power),
            n_groups=n_groups,
            direction="two-tailed",
            interpretation=interpretation,
            additional_info={"total_n": n * n_groups, "df1": df1, "df2": df2},
        )

    def minimum_detectable_effect(
        self,
        n: int,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        test_type: str = "t_test_two_sample",
        two_tailed: bool = True,
    ) -> PowerAnalysisResult:
        """
        Calculate minimum detectable effect size.

        Args:
            n: Sample size (per group for two-sample)
            alpha: Significance level
            power: Desired power
            test_type: Type of test
            two_tailed: Two-tailed test

        Returns:
            PowerAnalysisResult
        """
        alpha = alpha or self.alpha
        power = power or self.power

        # Binary search for effect size
        low, high = 0.01, 3.0

        for _ in range(100):
            mid = (low + high) / 2

            if test_type == "t_test_one_sample":
                result = self.power_t_test_one_sample(n, mid, alpha, two_tailed)
            elif test_type == "t_test_two_sample":
                result = self.power_t_test_two_sample(n, mid, alpha, 1.0, two_tailed)
            else:
                raise ValueError(f"Unknown test type: {test_type}")

            if abs(result.power - power) < 0.001:
                break

            if result.power < power:
                low = mid
            else:
                high = mid

        interpretation = (
            f"Minimum detectable effect size d={mid:.3f} with n={n} "
            f"for {power*100:.0f}% power at alpha={alpha}"
        )

        return PowerAnalysisResult(
            analysis_type=PowerAnalysisType.T_TEST_TWO_SAMPLE
                if test_type == "t_test_two_sample"
                else PowerAnalysisType.T_TEST_ONE_SAMPLE,
            sample_size=n,
            effect_size=mid,
            alpha=alpha,
            power=power,
            direction="two-tailed" if two_tailed else "one-tailed",
            interpretation=interpretation,
        )

    def sensitivity_analysis(
        self,
        effect_sizes: List[float],
        sample_sizes: List[int],
        alpha: Optional[float] = None,
        test_type: str = "t_test_two_sample",
    ) -> Dict[str, Any]:
        """
        Perform sensitivity analysis across effect sizes and sample sizes.

        Args:
            effect_sizes: List of effect sizes to test
            sample_sizes: List of sample sizes to test
            alpha: Significance level
            test_type: Type of test

        Returns:
            Dict with power matrix and analysis
        """
        alpha = alpha or self.alpha

        power_matrix = np.zeros((len(effect_sizes), len(sample_sizes)))

        for i, d in enumerate(effect_sizes):
            for j, n in enumerate(sample_sizes):
                if test_type == "t_test_two_sample":
                    result = self.power_t_test_two_sample(n, d, alpha)
                elif test_type == "t_test_one_sample":
                    result = self.power_t_test_one_sample(n, d, alpha)
                else:
                    raise ValueError(f"Unknown test type: {test_type}")

                power_matrix[i, j] = result.power

        return {
            "effect_sizes": effect_sizes,
            "sample_sizes": sample_sizes,
            "power_matrix": power_matrix.tolist(),
            "alpha": alpha,
            "test_type": test_type,
            "adequate_power_threshold": 0.80,
            "adequate_combinations": [
                {"effect_size": effect_sizes[i], "sample_size": sample_sizes[j], "power": power_matrix[i, j]}
                for i in range(len(effect_sizes))
                for j in range(len(sample_sizes))
                if power_matrix[i, j] >= 0.80
            ],
        }


def calculate_sample_size(
    effect_size: float,
    test_type: str = "t_test_two_sample",
    alpha: float = 0.05,
    power: float = 0.80,
    **kwargs,
) -> int:
    """
    Calculate required sample size for given parameters.

    Args:
        effect_size: Expected effect size
        test_type: Type of test
        alpha: Significance level
        power: Desired power
        **kwargs: Additional parameters

    Returns:
        Required sample size
    """
    analyzer = PowerAnalyzer(alpha=alpha, power=power)

    if test_type == "t_test_one_sample":
        result = analyzer.sample_size_t_test_one_sample(effect_size)
    elif test_type == "t_test_two_sample":
        result = analyzer.sample_size_t_test_two_sample(effect_size)
    elif test_type == "paired_t_test":
        result = analyzer.sample_size_paired_t_test(effect_size)
    elif test_type == "anova":
        n_groups = kwargs.get("n_groups", 3)
        result = analyzer.sample_size_anova(effect_size, n_groups)
    elif test_type == "correlation":
        result = analyzer.sample_size_correlation(effect_size)
    else:
        raise ValueError(f"Unknown test type: {test_type}")

    return result.sample_size


def calculate_power(
    n: int,
    effect_size: float,
    test_type: str = "t_test_two_sample",
    alpha: float = 0.05,
    **kwargs,
) -> float:
    """
    Calculate statistical power for given parameters.

    Args:
        n: Sample size
        effect_size: Expected effect size
        test_type: Type of test
        alpha: Significance level
        **kwargs: Additional parameters

    Returns:
        Statistical power
    """
    analyzer = PowerAnalyzer(alpha=alpha)

    if test_type == "t_test_one_sample":
        result = analyzer.power_t_test_one_sample(n, effect_size)
    elif test_type == "t_test_two_sample":
        result = analyzer.power_t_test_two_sample(n, effect_size)
    elif test_type == "anova":
        n_groups = kwargs.get("n_groups", 3)
        result = analyzer.power_anova(n, effect_size, n_groups)
    else:
        raise ValueError(f"Unknown test type: {test_type}")

    return result.power
