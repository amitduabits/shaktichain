"""
Effect Size Calculator Module.

Provides comprehensive effect size calculations:
- Cohen's d (standardized mean difference)
- Cohen's f (ANOVA effect size)
- Eta-squared and partial eta-squared
- Omega-squared
- Cohen's h (proportion difference)
- Correlation-based measures (r, r-squared)
- Odds ratio and risk ratio
- Common language effect size
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class EffectSizeType(Enum):
    """Types of effect sizes."""
    COHENS_D = "cohens_d"
    COHENS_F = "cohens_f"
    ETA_SQUARED = "eta_squared"
    PARTIAL_ETA_SQUARED = "partial_eta_squared"
    OMEGA_SQUARED = "omega_squared"
    COHENS_H = "cohens_h"
    CORRELATION_R = "correlation_r"
    R_SQUARED = "r_squared"
    ODDS_RATIO = "odds_ratio"
    RISK_RATIO = "risk_ratio"
    CLIFFS_DELTA = "cliffs_delta"
    COMMON_LANGUAGE = "common_language"
    GLASS_DELTA = "glass_delta"
    HEDGES_G = "hedges_g"


class EffectMagnitude(Enum):
    """Effect size magnitude classification."""
    NEGLIGIBLE = "negligible"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    VERY_LARGE = "very_large"


@dataclass
class EffectSizeResult:
    """
    Result of effect size calculation.

    Attributes:
        effect_type: Type of effect size
        value: Calculated effect size
        magnitude: Qualitative magnitude
        confidence_interval: CI for effect size
        interpretation: Human-readable interpretation
        additional_info: Extra information
    """
    effect_type: EffectSizeType
    value: float
    magnitude: EffectMagnitude
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    interpretation: str = ""
    additional_info: Dict[str, Any] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "effect_type": self.effect_type.value,
            "value": self.value,
            "magnitude": self.magnitude.value,
            "confidence_interval": self.confidence_interval,
            "interpretation": self.interpretation,
            "additional_info": self.additional_info,
        }


class EffectSizeCalculator:
    """
    Comprehensive effect size calculator.

    Provides methods for calculating various effect sizes with
    confidence intervals and interpretations.
    """

    # Thresholds for Cohen's d
    COHENS_D_THRESHOLDS = {
        EffectMagnitude.NEGLIGIBLE: 0.0,
        EffectMagnitude.SMALL: 0.2,
        EffectMagnitude.MEDIUM: 0.5,
        EffectMagnitude.LARGE: 0.8,
        EffectMagnitude.VERY_LARGE: 1.2,
    }

    # Thresholds for eta-squared
    ETA_SQUARED_THRESHOLDS = {
        EffectMagnitude.NEGLIGIBLE: 0.0,
        EffectMagnitude.SMALL: 0.01,
        EffectMagnitude.MEDIUM: 0.06,
        EffectMagnitude.LARGE: 0.14,
        EffectMagnitude.VERY_LARGE: 0.20,
    }

    # Thresholds for correlation r
    CORRELATION_THRESHOLDS = {
        EffectMagnitude.NEGLIGIBLE: 0.0,
        EffectMagnitude.SMALL: 0.1,
        EffectMagnitude.MEDIUM: 0.3,
        EffectMagnitude.LARGE: 0.5,
        EffectMagnitude.VERY_LARGE: 0.7,
    }

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize calculator.

        Args:
            confidence_level: Confidence level for intervals
        """
        self.confidence_level = confidence_level

    def _classify_cohens_d(self, d: float) -> EffectMagnitude:
        """Classify Cohen's d magnitude."""
        d = abs(d)
        if d >= self.COHENS_D_THRESHOLDS[EffectMagnitude.VERY_LARGE]:
            return EffectMagnitude.VERY_LARGE
        elif d >= self.COHENS_D_THRESHOLDS[EffectMagnitude.LARGE]:
            return EffectMagnitude.LARGE
        elif d >= self.COHENS_D_THRESHOLDS[EffectMagnitude.MEDIUM]:
            return EffectMagnitude.MEDIUM
        elif d >= self.COHENS_D_THRESHOLDS[EffectMagnitude.SMALL]:
            return EffectMagnitude.SMALL
        else:
            return EffectMagnitude.NEGLIGIBLE

    def _classify_eta_squared(self, eta: float) -> EffectMagnitude:
        """Classify eta-squared magnitude."""
        if eta >= self.ETA_SQUARED_THRESHOLDS[EffectMagnitude.VERY_LARGE]:
            return EffectMagnitude.VERY_LARGE
        elif eta >= self.ETA_SQUARED_THRESHOLDS[EffectMagnitude.LARGE]:
            return EffectMagnitude.LARGE
        elif eta >= self.ETA_SQUARED_THRESHOLDS[EffectMagnitude.MEDIUM]:
            return EffectMagnitude.MEDIUM
        elif eta >= self.ETA_SQUARED_THRESHOLDS[EffectMagnitude.SMALL]:
            return EffectMagnitude.SMALL
        else:
            return EffectMagnitude.NEGLIGIBLE

    def _classify_correlation(self, r: float) -> EffectMagnitude:
        """Classify correlation magnitude."""
        r = abs(r)
        if r >= self.CORRELATION_THRESHOLDS[EffectMagnitude.VERY_LARGE]:
            return EffectMagnitude.VERY_LARGE
        elif r >= self.CORRELATION_THRESHOLDS[EffectMagnitude.LARGE]:
            return EffectMagnitude.LARGE
        elif r >= self.CORRELATION_THRESHOLDS[EffectMagnitude.MEDIUM]:
            return EffectMagnitude.MEDIUM
        elif r >= self.CORRELATION_THRESHOLDS[EffectMagnitude.SMALL]:
            return EffectMagnitude.SMALL
        else:
            return EffectMagnitude.NEGLIGIBLE

    def cohens_d(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
        pooled: bool = True,
    ) -> EffectSizeResult:
        """
        Calculate Cohen's d (standardized mean difference).

        Args:
            group1: First group data
            group2: Second group data
            pooled: Use pooled standard deviation

        Returns:
            EffectSizeResult
        """
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        mean1, mean2 = np.mean(group1), np.mean(group2)
        std1, std2 = np.std(group1, ddof=1), np.std(group2, ddof=1)

        if pooled:
            # Pooled standard deviation
            s_pooled = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
            d = (mean1 - mean2) / s_pooled if s_pooled > 0 else 0
        else:
            # Using group 2's std (Glass's delta)
            d = (mean1 - mean2) / std2 if std2 > 0 else 0

        # Confidence interval using non-central t
        se_d = np.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))
        df = n1 + n2 - 2
        t_crit = stats.t.ppf((1 + self.confidence_level) / 2, df)
        ci = (d - t_crit * se_d, d + t_crit * se_d)

        magnitude = self._classify_cohens_d(d)

        interpretation = (
            f"Cohen's d = {d:.3f} ({magnitude.value} effect). "
            f"Group 1 mean differs from Group 2 by {abs(d):.2f} standard deviations."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.COHENS_D,
            value=float(d),
            magnitude=magnitude,
            confidence_interval=ci,
            interpretation=interpretation,
            additional_info={
                "mean1": float(mean1),
                "mean2": float(mean2),
                "std_pooled": float(s_pooled) if pooled else None,
                "n1": n1,
                "n2": n2,
            },
        )

    def hedges_g(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Hedges' g (bias-corrected Cohen's d).

        Better for small samples.

        Args:
            group1: First group data
            group2: Second group data

        Returns:
            EffectSizeResult
        """
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        # First calculate Cohen's d
        mean1, mean2 = np.mean(group1), np.mean(group2)
        std1, std2 = np.std(group1, ddof=1), np.std(group2, ddof=1)
        s_pooled = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        d = (mean1 - mean2) / s_pooled if s_pooled > 0 else 0

        # Apply correction factor (Hedges' correction)
        df = n1 + n2 - 2
        correction = 1 - (3 / (4 * df - 1))
        g = d * correction

        # Confidence interval
        se_g = np.sqrt((n1 + n2) / (n1 * n2) + g**2 / (2 * (n1 + n2)))
        t_crit = stats.t.ppf((1 + self.confidence_level) / 2, df)
        ci = (g - t_crit * se_g, g + t_crit * se_g)

        magnitude = self._classify_cohens_d(g)

        interpretation = (
            f"Hedges' g = {g:.3f} ({magnitude.value} effect). "
            f"Bias-corrected standardized mean difference."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.HEDGES_G,
            value=float(g),
            magnitude=magnitude,
            confidence_interval=ci,
            interpretation=interpretation,
            additional_info={
                "cohens_d": float(d),
                "correction_factor": float(correction),
                "n1": n1,
                "n2": n2,
            },
        )

    def glass_delta(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Glass's delta (uses control group SD).

        Useful when group variances differ.

        Args:
            group1: Treatment group data
            group2: Control group data

        Returns:
            EffectSizeResult
        """
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        mean1, mean2 = np.mean(group1), np.mean(group2)
        std2 = np.std(group2, ddof=1)

        delta = (mean1 - mean2) / std2 if std2 > 0 else 0

        # Approximate CI
        se = np.sqrt((n1 + n2) / (n1 * n2) + delta**2 / (2 * n2))
        df = n2 - 1
        t_crit = stats.t.ppf((1 + self.confidence_level) / 2, df)
        ci = (delta - t_crit * se, delta + t_crit * se)

        magnitude = self._classify_cohens_d(delta)

        interpretation = (
            f"Glass's delta = {delta:.3f} ({magnitude.value} effect). "
            f"Standardized using control group SD."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.GLASS_DELTA,
            value=float(delta),
            magnitude=magnitude,
            confidence_interval=ci,
            interpretation=interpretation,
            additional_info={
                "control_std": float(std2),
                "n_treatment": n1,
                "n_control": n2,
            },
        )

    def cohens_d_paired(
        self,
        before: np.ndarray,
        after: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Cohen's d for paired samples.

        Args:
            before: Pre-treatment measurements
            after: Post-treatment measurements

        Returns:
            EffectSizeResult
        """
        before = np.asarray(before)
        after = np.asarray(after)

        if len(before) != len(after):
            raise ValueError("Paired samples must have equal length")

        n = len(before)
        diff = after - before
        mean_diff = np.mean(diff)
        std_diff = np.std(diff, ddof=1)

        d = mean_diff / std_diff if std_diff > 0 else 0

        # Confidence interval
        se = std_diff / np.sqrt(n)
        se_d = se / std_diff if std_diff > 0 else 0
        t_crit = stats.t.ppf((1 + self.confidence_level) / 2, n - 1)
        ci = (d - t_crit * np.sqrt(1/n + d**2/(2*n)),
              d + t_crit * np.sqrt(1/n + d**2/(2*n)))

        magnitude = self._classify_cohens_d(d)

        interpretation = (
            f"Cohen's d (paired) = {d:.3f} ({magnitude.value} effect). "
            f"Mean change of {abs(mean_diff):.3f} relative to within-subject SD."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.COHENS_D,
            value=float(d),
            magnitude=magnitude,
            confidence_interval=ci,
            interpretation=interpretation,
            additional_info={
                "mean_diff": float(mean_diff),
                "std_diff": float(std_diff),
                "n_pairs": n,
            },
        )

    def eta_squared(
        self,
        *groups: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate eta-squared for ANOVA.

        Proportion of variance explained by group membership.

        Args:
            *groups: Variable number of group arrays

        Returns:
            EffectSizeResult
        """
        groups = [np.asarray(g) for g in groups]

        if len(groups) < 2:
            raise ValueError("Eta-squared requires at least 2 groups")

        # Calculate ANOVA components
        all_data = np.concatenate(groups)
        grand_mean = np.mean(all_data)
        n_total = len(all_data)

        # Sum of squares
        ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in groups)
        ss_total = np.sum((all_data - grand_mean)**2)

        eta_sq = ss_between / ss_total if ss_total > 0 else 0

        magnitude = self._classify_eta_squared(eta_sq)

        interpretation = (
            f"Eta-squared = {eta_sq:.3f} ({magnitude.value} effect). "
            f"{eta_sq*100:.1f}% of variance explained by group membership."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.ETA_SQUARED,
            value=float(eta_sq),
            magnitude=magnitude,
            confidence_interval=(0.0, 1.0),  # Bounded
            interpretation=interpretation,
            additional_info={
                "ss_between": float(ss_between),
                "ss_total": float(ss_total),
                "n_groups": len(groups),
                "n_total": n_total,
            },
        )

    def partial_eta_squared(
        self,
        ss_effect: float,
        ss_error: float,
    ) -> EffectSizeResult:
        """
        Calculate partial eta-squared.

        Used in factorial designs.

        Args:
            ss_effect: Sum of squares for the effect
            ss_error: Sum of squares for error

        Returns:
            EffectSizeResult
        """
        partial_eta = ss_effect / (ss_effect + ss_error) if (ss_effect + ss_error) > 0 else 0

        magnitude = self._classify_eta_squared(partial_eta)

        interpretation = (
            f"Partial eta-squared = {partial_eta:.3f} ({magnitude.value} effect). "
            f"{partial_eta*100:.1f}% of variance explained controlling for other factors."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.PARTIAL_ETA_SQUARED,
            value=float(partial_eta),
            magnitude=magnitude,
            confidence_interval=(0.0, 1.0),
            interpretation=interpretation,
            additional_info={
                "ss_effect": ss_effect,
                "ss_error": ss_error,
            },
        )

    def omega_squared(
        self,
        *groups: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate omega-squared for ANOVA.

        Less biased estimate than eta-squared.

        Args:
            *groups: Variable number of group arrays

        Returns:
            EffectSizeResult
        """
        groups = [np.asarray(g) for g in groups]
        k = len(groups)

        all_data = np.concatenate(groups)
        grand_mean = np.mean(all_data)
        n_total = len(all_data)

        # Sum of squares
        ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in groups)
        ss_within = sum(np.sum((g - np.mean(g))**2) for g in groups)
        ss_total = ss_between + ss_within

        # Mean squares
        df_between = k - 1
        df_within = n_total - k
        ms_within = ss_within / df_within if df_within > 0 else 0

        # Omega-squared (adjusted)
        omega_sq = (ss_between - df_between * ms_within) / (ss_total + ms_within)
        omega_sq = max(0, omega_sq)  # Can't be negative

        magnitude = self._classify_eta_squared(omega_sq)

        interpretation = (
            f"Omega-squared = {omega_sq:.3f} ({magnitude.value} effect). "
            f"Population estimate: {omega_sq*100:.1f}% variance explained."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.OMEGA_SQUARED,
            value=float(omega_sq),
            magnitude=magnitude,
            confidence_interval=(0.0, 1.0),
            interpretation=interpretation,
            additional_info={
                "ss_between": float(ss_between),
                "ss_within": float(ss_within),
                "ms_within": float(ms_within),
                "k_groups": k,
            },
        )

    def cohens_f(
        self,
        *groups: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Cohen's f for ANOVA.

        Standard effect size for power analysis.

        Args:
            *groups: Variable number of group arrays

        Returns:
            EffectSizeResult
        """
        # First calculate eta-squared
        eta_result = self.eta_squared(*groups)
        eta_sq = eta_result.value

        # Convert to Cohen's f
        f = np.sqrt(eta_sq / (1 - eta_sq)) if eta_sq < 1 else float('inf')

        # Cohen's f thresholds: small=0.10, medium=0.25, large=0.40
        if f >= 0.40:
            magnitude = EffectMagnitude.LARGE
        elif f >= 0.25:
            magnitude = EffectMagnitude.MEDIUM
        elif f >= 0.10:
            magnitude = EffectMagnitude.SMALL
        else:
            magnitude = EffectMagnitude.NEGLIGIBLE

        interpretation = (
            f"Cohen's f = {f:.3f} ({magnitude.value} effect). "
            f"Standard ANOVA effect size."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.COHENS_F,
            value=float(f),
            magnitude=magnitude,
            confidence_interval=(0.0, float('inf')),
            interpretation=interpretation,
            additional_info={
                "eta_squared": eta_sq,
            },
        )

    def cohens_h(
        self,
        p1: float,
        p2: float,
    ) -> EffectSizeResult:
        """
        Calculate Cohen's h for proportion difference.

        Uses arcsine transformation.

        Args:
            p1: First proportion
            p2: Second proportion

        Returns:
            EffectSizeResult
        """
        if not (0 <= p1 <= 1 and 0 <= p2 <= 1):
            raise ValueError("Proportions must be between 0 and 1")

        # Arcsine transformation
        phi1 = 2 * np.arcsin(np.sqrt(p1))
        phi2 = 2 * np.arcsin(np.sqrt(p2))
        h = phi1 - phi2

        # Cohen's h uses same thresholds as d
        magnitude = self._classify_cohens_d(h)

        interpretation = (
            f"Cohen's h = {h:.3f} ({magnitude.value} effect). "
            f"Difference between proportions {p1:.3f} and {p2:.3f}."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.COHENS_H,
            value=float(h),
            magnitude=magnitude,
            confidence_interval=(-np.pi, np.pi),  # Theoretical bounds
            interpretation=interpretation,
            additional_info={
                "p1": p1,
                "p2": p2,
                "phi1": float(phi1),
                "phi2": float(phi2),
            },
        )

    def correlation_r(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Pearson correlation as effect size.

        Args:
            x: First variable
            y: Second variable

        Returns:
            EffectSizeResult
        """
        x = np.asarray(x)
        y = np.asarray(y)

        if len(x) != len(y):
            raise ValueError("Arrays must have equal length")

        n = len(x)
        r, p_value = stats.pearsonr(x, y)

        # Fisher's z confidence interval
        z = 0.5 * np.log((1 + r) / (1 - r)) if abs(r) < 1 else np.sign(r) * 10
        se_z = 1 / np.sqrt(n - 3) if n > 3 else 0
        z_crit = stats.norm.ppf((1 + self.confidence_level) / 2)
        z_low, z_high = z - z_crit * se_z, z + z_crit * se_z

        # Back-transform
        r_low = (np.exp(2 * z_low) - 1) / (np.exp(2 * z_low) + 1)
        r_high = (np.exp(2 * z_high) - 1) / (np.exp(2 * z_high) + 1)

        magnitude = self._classify_correlation(r)

        interpretation = (
            f"r = {r:.3f} ({magnitude.value} correlation). "
            f"{'Positive' if r > 0 else 'Negative'} linear relationship."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.CORRELATION_R,
            value=float(r),
            magnitude=magnitude,
            confidence_interval=(r_low, r_high),
            interpretation=interpretation,
            additional_info={
                "p_value": float(p_value),
                "n": n,
                "r_squared": float(r**2),
            },
        )

    def cliffs_delta(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Cliff's delta (non-parametric effect size).

        Robust to outliers and non-normality.

        Args:
            group1: First group data
            group2: Second group data

        Returns:
            EffectSizeResult
        """
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)
        n1, n2 = len(group1), len(group2)

        # Count dominance
        more = 0
        less = 0
        for x in group1:
            for y in group2:
                if x > y:
                    more += 1
                elif x < y:
                    less += 1

        delta = (more - less) / (n1 * n2)

        # Thresholds for Cliff's delta: |d| < 0.147 negligible, < 0.33 small, < 0.474 medium, else large
        d_abs = abs(delta)
        if d_abs < 0.147:
            magnitude = EffectMagnitude.NEGLIGIBLE
        elif d_abs < 0.33:
            magnitude = EffectMagnitude.SMALL
        elif d_abs < 0.474:
            magnitude = EffectMagnitude.MEDIUM
        else:
            magnitude = EffectMagnitude.LARGE

        interpretation = (
            f"Cliff's delta = {delta:.3f} ({magnitude.value} effect). "
            f"Probability of Group 1 > Group 2: {(delta + 1) / 2:.1%}."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.CLIFFS_DELTA,
            value=float(delta),
            magnitude=magnitude,
            confidence_interval=(-1.0, 1.0),
            interpretation=interpretation,
            additional_info={
                "n_more": more,
                "n_less": less,
                "n1": n1,
                "n2": n2,
            },
        )

    def common_language_effect_size(
        self,
        group1: np.ndarray,
        group2: np.ndarray,
    ) -> EffectSizeResult:
        """
        Calculate Common Language Effect Size (CLES).

        Probability that random draw from Group 1 > Group 2.

        Args:
            group1: First group data
            group2: Second group data

        Returns:
            EffectSizeResult
        """
        group1 = np.asarray(group1)
        group2 = np.asarray(group2)

        # Calculate Cohen's d first
        mean1, mean2 = np.mean(group1), np.mean(group2)
        std1, std2 = np.std(group1, ddof=1), np.std(group2, ddof=1)
        s_pooled = np.sqrt((std1**2 + std2**2) / 2)
        d = (mean1 - mean2) / s_pooled if s_pooled > 0 else 0

        # CLES = Phi(d / sqrt(2))
        cles = stats.norm.cdf(d / np.sqrt(2))

        # Classify based on how far from 50%
        deviation = abs(cles - 0.5)
        if deviation < 0.06:
            magnitude = EffectMagnitude.NEGLIGIBLE
        elif deviation < 0.14:
            magnitude = EffectMagnitude.SMALL
        elif deviation < 0.24:
            magnitude = EffectMagnitude.MEDIUM
        else:
            magnitude = EffectMagnitude.LARGE

        interpretation = (
            f"CLES = {cles:.1%}. "
            f"Probability that random member of Group 1 exceeds Group 2."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.COMMON_LANGUAGE,
            value=float(cles),
            magnitude=magnitude,
            confidence_interval=(0.0, 1.0),
            interpretation=interpretation,
            additional_info={
                "cohens_d": float(d),
            },
        )

    def odds_ratio(
        self,
        a: int,
        b: int,
        c: int,
        d: int,
    ) -> EffectSizeResult:
        """
        Calculate odds ratio from 2x2 contingency table.

        Table format:
                    Outcome+  Outcome-
        Exposed       a          b
        Not Exposed   c          d

        Args:
            a, b, c, d: Cell counts

        Returns:
            EffectSizeResult
        """
        if a == 0 or b == 0 or c == 0 or d == 0:
            # Add 0.5 correction for zero cells
            a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5

        odds_ratio = (a * d) / (b * c)

        # Log odds ratio CI
        se_log_or = np.sqrt(1/a + 1/b + 1/c + 1/d)
        log_or = np.log(odds_ratio)
        z_crit = stats.norm.ppf((1 + self.confidence_level) / 2)
        ci = (np.exp(log_or - z_crit * se_log_or),
              np.exp(log_or + z_crit * se_log_or))

        # Classify OR
        if odds_ratio >= 4 or odds_ratio <= 0.25:
            magnitude = EffectMagnitude.LARGE
        elif odds_ratio >= 2 or odds_ratio <= 0.5:
            magnitude = EffectMagnitude.MEDIUM
        elif odds_ratio >= 1.5 or odds_ratio <= 0.67:
            magnitude = EffectMagnitude.SMALL
        else:
            magnitude = EffectMagnitude.NEGLIGIBLE

        interpretation = (
            f"OR = {odds_ratio:.2f} ({magnitude.value} effect). "
            f"Exposed {'more' if odds_ratio > 1 else 'less'} likely to have outcome."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.ODDS_RATIO,
            value=float(odds_ratio),
            magnitude=magnitude,
            confidence_interval=ci,
            interpretation=interpretation,
            additional_info={
                "log_or": float(log_or),
                "se_log_or": float(se_log_or),
                "cell_counts": {"a": a, "b": b, "c": c, "d": d},
            },
        )

    def risk_ratio(
        self,
        a: int,
        b: int,
        c: int,
        d: int,
    ) -> EffectSizeResult:
        """
        Calculate risk ratio (relative risk) from 2x2 table.

        Args:
            a, b, c, d: Cell counts (same format as odds_ratio)

        Returns:
            EffectSizeResult
        """
        # Risk in exposed = a / (a + b)
        # Risk in unexposed = c / (c + d)
        risk_exposed = a / (a + b) if (a + b) > 0 else 0
        risk_unexposed = c / (c + d) if (c + d) > 0 else 0

        rr = risk_exposed / risk_unexposed if risk_unexposed > 0 else float('inf')

        # Log RR CI
        if a > 0 and (a + b) > 0 and c > 0 and (c + d) > 0:
            se_log_rr = np.sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))
            log_rr = np.log(rr)
            z_crit = stats.norm.ppf((1 + self.confidence_level) / 2)
            ci = (np.exp(log_rr - z_crit * se_log_rr),
                  np.exp(log_rr + z_crit * se_log_rr))
        else:
            ci = (0.0, float('inf'))

        # Similar classification as OR
        if rr >= 4 or rr <= 0.25:
            magnitude = EffectMagnitude.LARGE
        elif rr >= 2 or rr <= 0.5:
            magnitude = EffectMagnitude.MEDIUM
        elif rr >= 1.5 or rr <= 0.67:
            magnitude = EffectMagnitude.SMALL
        else:
            magnitude = EffectMagnitude.NEGLIGIBLE

        interpretation = (
            f"RR = {rr:.2f} ({magnitude.value} effect). "
            f"Exposed have {rr:.1f}x the risk of unexposed."
        )

        return EffectSizeResult(
            effect_type=EffectSizeType.RISK_RATIO,
            value=float(rr),
            magnitude=magnitude,
            confidence_interval=ci,
            interpretation=interpretation,
            additional_info={
                "risk_exposed": float(risk_exposed),
                "risk_unexposed": float(risk_unexposed),
            },
        )

    def r_to_d(self, r: float) -> float:
        """
        Convert correlation r to Cohen's d.

        Args:
            r: Correlation coefficient

        Returns:
            Cohen's d equivalent
        """
        if abs(r) >= 1:
            return np.sign(r) * float('inf')
        return (2 * r) / np.sqrt(1 - r**2)

    def d_to_r(self, d: float) -> float:
        """
        Convert Cohen's d to correlation r.

        Args:
            d: Cohen's d

        Returns:
            Correlation equivalent
        """
        return d / np.sqrt(d**2 + 4)

    def d_to_odds_ratio(self, d: float) -> float:
        """
        Convert Cohen's d to odds ratio.

        Uses Cox's formula.

        Args:
            d: Cohen's d

        Returns:
            Odds ratio equivalent
        """
        return np.exp(d * np.pi / np.sqrt(3))


def calculate_effect_size(
    effect_type: str,
    **kwargs,
) -> EffectSizeResult:
    """
    Calculate effect size by type.

    Args:
        effect_type: Type of effect size
        **kwargs: Parameters for calculation

    Returns:
        EffectSizeResult
    """
    calculator = EffectSizeCalculator()

    methods = {
        "cohens_d": calculator.cohens_d,
        "hedges_g": calculator.hedges_g,
        "glass_delta": calculator.glass_delta,
        "cohens_d_paired": calculator.cohens_d_paired,
        "eta_squared": calculator.eta_squared,
        "omega_squared": calculator.omega_squared,
        "cohens_f": calculator.cohens_f,
        "cohens_h": calculator.cohens_h,
        "correlation_r": calculator.correlation_r,
        "cliffs_delta": calculator.cliffs_delta,
        "common_language": calculator.common_language_effect_size,
        "odds_ratio": calculator.odds_ratio,
        "risk_ratio": calculator.risk_ratio,
    }

    if effect_type not in methods:
        raise ValueError(f"Unknown effect type: {effect_type}")

    return methods[effect_type](**kwargs)
