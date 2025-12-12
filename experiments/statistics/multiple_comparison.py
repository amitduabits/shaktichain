"""
Multiple Comparison Correction Module.

Provides methods to control family-wise error rate (FWER) and
false discovery rate (FDR) when performing multiple hypothesis tests.

Methods included:
- Bonferroni correction
- Sidak correction
- Holm step-down procedure
- Holm-Sidak procedure
- Hochberg step-up procedure
- Benjamini-Hochberg FDR
- Benjamini-Yekutieli FDR
- Hommel procedure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class CorrectionMethod(Enum):
    """Available correction methods."""
    BONFERRONI = "bonferroni"
    SIDAK = "sidak"
    HOLM = "holm"
    HOLM_SIDAK = "holm_sidak"
    HOCHBERG = "hochberg"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    BENJAMINI_YEKUTIELI = "benjamini_yekutieli"
    HOMMEL = "hommel"
    NONE = "none"


@dataclass
class CorrectionResult:
    """
    Result of multiple comparison correction.

    Attributes:
        method: Correction method used
        original_p_values: Original p-values
        adjusted_p_values: Adjusted p-values (if applicable)
        significant: Boolean array of significant results
        adjusted_alpha: Adjusted significance threshold (if applicable)
        n_significant: Number of significant tests
        n_tests: Total number of tests
        fwer: Family-wise error rate controlled
        fdr: False discovery rate (for FDR methods)
        interpretation: Human-readable interpretation
        additional_info: Extra information
    """
    method: CorrectionMethod
    original_p_values: np.ndarray
    adjusted_p_values: Optional[np.ndarray]
    significant: np.ndarray
    adjusted_alpha: Optional[float]
    n_significant: int
    n_tests: int
    fwer: Optional[float] = None
    fdr: Optional[float] = None
    interpretation: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "method": self.method.value,
            "original_p_values": self.original_p_values.tolist(),
            "adjusted_p_values": self.adjusted_p_values.tolist() if self.adjusted_p_values is not None else None,
            "significant": self.significant.tolist(),
            "adjusted_alpha": self.adjusted_alpha,
            "n_significant": self.n_significant,
            "n_tests": self.n_tests,
            "fwer": self.fwer,
            "fdr": self.fdr,
            "interpretation": self.interpretation,
            "additional_info": self.additional_info,
        }

    def summary(self) -> str:
        """Generate summary string."""
        return (
            f"Method: {self.method.value}\n"
            f"Tests: {self.n_tests}\n"
            f"Significant: {self.n_significant} ({self.n_significant/self.n_tests*100:.1f}%)\n"
            f"Controlled rate: FWER={self.fwer:.3f}" if self.fwer else f"FDR={self.fdr:.3f}"
        )


class MultipleComparisonCorrector:
    """
    Multiple comparison correction handler.

    Provides methods to adjust p-values or significance thresholds
    to account for multiple testing.
    """

    def __init__(self, p_values: Union[List[float], np.ndarray], alpha: float = 0.05):
        """
        Initialize corrector.

        Args:
            p_values: List or array of p-values
            alpha: Family-wise or false discovery rate to control
        """
        self.p_values = np.asarray(p_values).flatten()
        self.alpha = alpha
        self.n = len(self.p_values)

        if self.n == 0:
            raise ValueError("At least one p-value required")

        if np.any(self.p_values < 0) or np.any(self.p_values > 1):
            raise ValueError("P-values must be between 0 and 1")

    def bonferroni(self) -> CorrectionResult:
        """
        Bonferroni correction.

        Most conservative. Divides alpha by number of tests.
        Controls FWER at level alpha.

        Formula: alpha_adj = alpha / m
        Reject H0 if p_i < alpha/m

        Returns:
            CorrectionResult
        """
        adjusted_alpha = self.alpha / self.n
        significant = self.p_values < adjusted_alpha
        adjusted_p = np.minimum(self.p_values * self.n, 1.0)

        n_sig = np.sum(significant)

        interpretation = (
            f"Bonferroni correction: {n_sig}/{self.n} tests significant "
            f"at adjusted alpha = {adjusted_alpha:.6f}"
        )

        return CorrectionResult(
            method=CorrectionMethod.BONFERRONI,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=adjusted_alpha,
            n_significant=n_sig,
            n_tests=self.n,
            fwer=self.alpha,
            interpretation=interpretation,
            additional_info={
                "correction_factor": self.n,
                "note": "Most conservative FWER method",
            },
        )

    def sidak(self) -> CorrectionResult:
        """
        Sidak correction.

        Slightly less conservative than Bonferroni.
        Assumes independent tests.

        Formula: alpha_adj = 1 - (1 - alpha)^(1/m)

        Returns:
            CorrectionResult
        """
        adjusted_alpha = 1 - (1 - self.alpha) ** (1 / self.n)
        significant = self.p_values < adjusted_alpha
        adjusted_p = 1 - (1 - self.p_values) ** self.n
        adjusted_p = np.minimum(adjusted_p, 1.0)

        n_sig = np.sum(significant)

        interpretation = (
            f"Sidak correction: {n_sig}/{self.n} tests significant "
            f"at adjusted alpha = {adjusted_alpha:.6f}"
        )

        return CorrectionResult(
            method=CorrectionMethod.SIDAK,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=adjusted_alpha,
            n_significant=n_sig,
            n_tests=self.n,
            fwer=self.alpha,
            interpretation=interpretation,
            additional_info={
                "assumption": "Independent tests",
                "note": "Less conservative than Bonferroni for independent tests",
            },
        )

    def holm(self) -> CorrectionResult:
        """
        Holm step-down procedure.

        Uniformly more powerful than Bonferroni.
        Also called Holm-Bonferroni method.

        Procedure:
        1. Sort p-values: p(1) <= p(2) <= ... <= p(m)
        2. Find smallest k where p(k) > alpha/(m-k+1)
        3. Reject H0 for tests with p <= p(k-1)

        Returns:
            CorrectionResult
        """
        sorted_indices = np.argsort(self.p_values)
        sorted_p = self.p_values[sorted_indices]

        # Calculate thresholds
        thresholds = self.alpha / (self.n - np.arange(self.n))

        # Find rejection boundary
        significant = np.zeros(self.n, dtype=bool)
        adjusted_p = np.ones(self.n)

        # Step-down: reject until we fail
        for i in range(self.n):
            adjusted_p[sorted_indices[i]] = np.min([
                sorted_p[i] * (self.n - i),
                1.0
            ])
            if sorted_p[i] <= thresholds[i]:
                significant[sorted_indices[i]] = True
            else:
                break

        # Ensure monotonicity of adjusted p-values
        adjusted_p = self._enforce_monotonicity_down(adjusted_p, sorted_indices)

        n_sig = np.sum(significant)

        interpretation = (
            f"Holm step-down: {n_sig}/{self.n} tests significant "
            f"(more powerful than Bonferroni)"
        )

        return CorrectionResult(
            method=CorrectionMethod.HOLM,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=None,  # Varies per test
            n_significant=n_sig,
            n_tests=self.n,
            fwer=self.alpha,
            interpretation=interpretation,
            additional_info={
                "procedure": "step-down",
                "note": "Uniformly more powerful than Bonferroni",
            },
        )

    def holm_sidak(self) -> CorrectionResult:
        """
        Holm-Sidak step-down procedure.

        Uses Sidak correction in step-down manner.
        Assumes independent tests.

        Returns:
            CorrectionResult
        """
        sorted_indices = np.argsort(self.p_values)
        sorted_p = self.p_values[sorted_indices]

        # Calculate thresholds using Sidak
        thresholds = 1 - (1 - self.alpha) ** (1 / (self.n - np.arange(self.n)))

        significant = np.zeros(self.n, dtype=bool)
        adjusted_p = np.ones(self.n)

        for i in range(self.n):
            adjusted_p[sorted_indices[i]] = 1 - (1 - sorted_p[i]) ** (self.n - i)
            if sorted_p[i] <= thresholds[i]:
                significant[sorted_indices[i]] = True
            else:
                break

        adjusted_p = self._enforce_monotonicity_down(adjusted_p, sorted_indices)
        n_sig = np.sum(significant)

        interpretation = (
            f"Holm-Sidak: {n_sig}/{self.n} tests significant "
            f"(assumes independence)"
        )

        return CorrectionResult(
            method=CorrectionMethod.HOLM_SIDAK,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=None,
            n_significant=n_sig,
            n_tests=self.n,
            fwer=self.alpha,
            interpretation=interpretation,
            additional_info={
                "procedure": "step-down",
                "assumption": "Independent tests",
            },
        )

    def hochberg(self) -> CorrectionResult:
        """
        Hochberg step-up procedure.

        More powerful than Holm but requires independence or
        positive dependence (PRDS).

        Procedure:
        1. Sort p-values: p(1) <= p(2) <= ... <= p(m)
        2. Find largest k where p(k) <= alpha/(m-k+1)
        3. Reject H0 for tests with p <= p(k)

        Returns:
            CorrectionResult
        """
        sorted_indices = np.argsort(self.p_values)
        sorted_p = self.p_values[sorted_indices]

        # Step-up: start from largest
        thresholds = self.alpha / (self.n - np.arange(self.n))

        significant = np.zeros(self.n, dtype=bool)
        adjusted_p = np.ones(self.n)

        # Find the largest k where p(k) <= threshold(k)
        reject_all = False
        for i in range(self.n - 1, -1, -1):
            adjusted_p[sorted_indices[i]] = np.min([
                sorted_p[i] * (self.n - i),
                1.0
            ])
            if sorted_p[i] <= thresholds[i]:
                reject_all = True

            if reject_all:
                significant[sorted_indices[i]] = True

        adjusted_p = self._enforce_monotonicity_up(adjusted_p, sorted_indices)
        n_sig = np.sum(significant)

        interpretation = (
            f"Hochberg step-up: {n_sig}/{self.n} tests significant "
            f"(more powerful than Holm if PRDS holds)"
        )

        return CorrectionResult(
            method=CorrectionMethod.HOCHBERG,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=None,
            n_significant=n_sig,
            n_tests=self.n,
            fwer=self.alpha,
            interpretation=interpretation,
            additional_info={
                "procedure": "step-up",
                "assumption": "Independence or PRDS (positive regression dependence)",
            },
        )

    def benjamini_hochberg(self) -> CorrectionResult:
        """
        Benjamini-Hochberg FDR control.

        Controls false discovery rate (FDR) instead of FWER.
        Less conservative, more powerful for multiple tests.

        Procedure:
        1. Sort p-values: p(1) <= p(2) <= ... <= p(m)
        2. Find largest k where p(k) <= k*alpha/m
        3. Reject H0 for tests with p <= p(k)

        Returns:
            CorrectionResult
        """
        sorted_indices = np.argsort(self.p_values)
        sorted_p = self.p_values[sorted_indices]

        # BH critical values: (i/m) * alpha
        critical_values = (np.arange(1, self.n + 1) / self.n) * self.alpha

        # Find largest k where p(k) <= critical_value(k)
        below_threshold = sorted_p <= critical_values

        if below_threshold.any():
            k = np.max(np.where(below_threshold)[0]) + 1
        else:
            k = 0

        # All tests up to k are significant
        significant = np.zeros(self.n, dtype=bool)
        significant[sorted_indices[:k]] = True

        # Adjusted p-values
        adjusted_p = np.ones(self.n)
        for i in range(self.n):
            adjusted_p[sorted_indices[i]] = sorted_p[i] * self.n / (i + 1)

        # Enforce monotonicity (cumulative minimum from right)
        adjusted_p = self._enforce_monotonicity_up(adjusted_p, sorted_indices)
        adjusted_p = np.minimum(adjusted_p, 1.0)

        n_sig = np.sum(significant)

        interpretation = (
            f"Benjamini-Hochberg FDR: {n_sig}/{self.n} tests significant "
            f"at FDR = {self.alpha}"
        )

        return CorrectionResult(
            method=CorrectionMethod.BENJAMINI_HOCHBERG,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=None,
            n_significant=n_sig,
            n_tests=self.n,
            fdr=self.alpha,
            interpretation=interpretation,
            additional_info={
                "procedure": "FDR control (step-up)",
                "k_rejected": k,
                "note": "Controls expected proportion of false discoveries",
            },
        )

    def benjamini_yekutieli(self) -> CorrectionResult:
        """
        Benjamini-Yekutieli FDR control.

        Controls FDR under arbitrary dependence.
        More conservative than BH.

        Uses correction factor: c(m) = sum(1/i) for i=1 to m

        Returns:
            CorrectionResult
        """
        sorted_indices = np.argsort(self.p_values)
        sorted_p = self.p_values[sorted_indices]

        # Correction factor for arbitrary dependence
        c_m = np.sum(1 / np.arange(1, self.n + 1))

        # BY critical values
        critical_values = (np.arange(1, self.n + 1) / self.n) * self.alpha / c_m

        below_threshold = sorted_p <= critical_values

        if below_threshold.any():
            k = np.max(np.where(below_threshold)[0]) + 1
        else:
            k = 0

        significant = np.zeros(self.n, dtype=bool)
        significant[sorted_indices[:k]] = True

        # Adjusted p-values
        adjusted_p = np.ones(self.n)
        for i in range(self.n):
            adjusted_p[sorted_indices[i]] = sorted_p[i] * self.n * c_m / (i + 1)

        adjusted_p = self._enforce_monotonicity_up(adjusted_p, sorted_indices)
        adjusted_p = np.minimum(adjusted_p, 1.0)

        n_sig = np.sum(significant)

        interpretation = (
            f"Benjamini-Yekutieli FDR: {n_sig}/{self.n} tests significant "
            f"(valid under any dependence)"
        )

        return CorrectionResult(
            method=CorrectionMethod.BENJAMINI_YEKUTIELI,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=None,
            n_significant=n_sig,
            n_tests=self.n,
            fdr=self.alpha,
            interpretation=interpretation,
            additional_info={
                "procedure": "FDR control with dependence correction",
                "correction_factor_cm": float(c_m),
                "note": "Controls FDR under arbitrary dependence structure",
            },
        )

    def hommel(self) -> CorrectionResult:
        """
        Hommel procedure.

        More powerful than Hochberg but computationally intensive.
        Requires independence or PRDS.

        Returns:
            CorrectionResult
        """
        sorted_indices = np.argsort(self.p_values)
        sorted_p = self.p_values[sorted_indices]

        # Hommel's procedure
        significant = np.zeros(self.n, dtype=bool)
        adjusted_p = np.ones(self.n)

        # Start with all rejected
        reject = np.ones(self.n, dtype=bool)

        for j in range(self.n, 0, -1):
            # Check if we can claim j hypotheses are true
            q = self.alpha / j

            # Check condition for all subsets
            valid = True
            for i in range(self.n - j + 1):
                if sorted_p[i + j - 1] > (i + j) * q / j:
                    valid = False
                    break

            if valid:
                # Reject hypotheses with p <= alpha/j
                threshold = self.alpha / j
                reject = self.p_values <= threshold
                break

        significant = reject

        # Simple adjusted p-values (approximation)
        for i in range(self.n):
            adjusted_p[i] = min(1.0, self.p_values[i] * self.n)

        n_sig = np.sum(significant)

        interpretation = (
            f"Hommel procedure: {n_sig}/{self.n} tests significant "
            f"(most powerful FWER method under PRDS)"
        )

        return CorrectionResult(
            method=CorrectionMethod.HOMMEL,
            original_p_values=self.p_values,
            adjusted_p_values=adjusted_p,
            significant=significant,
            adjusted_alpha=None,
            n_significant=n_sig,
            n_tests=self.n,
            fwer=self.alpha,
            interpretation=interpretation,
            additional_info={
                "procedure": "Hommel closed testing",
                "assumption": "Independence or PRDS",
                "note": "Most powerful FWER method under positive dependence",
            },
        )

    def no_correction(self) -> CorrectionResult:
        """
        No correction (for comparison).

        Simply applies nominal alpha to each test.

        Returns:
            CorrectionResult
        """
        significant = self.p_values < self.alpha
        n_sig = np.sum(significant)

        # Expected false positives under H0
        expected_false = self.n * self.alpha

        interpretation = (
            f"No correction: {n_sig}/{self.n} tests significant at alpha={self.alpha}. "
            f"Warning: Expected {expected_false:.1f} false positives if all nulls true."
        )

        return CorrectionResult(
            method=CorrectionMethod.NONE,
            original_p_values=self.p_values,
            adjusted_p_values=self.p_values,
            significant=significant,
            adjusted_alpha=self.alpha,
            n_significant=n_sig,
            n_tests=self.n,
            fwer=1 - (1 - self.alpha) ** self.n,  # True FWER if all H0 true
            interpretation=interpretation,
            additional_info={
                "warning": "No correction for multiple comparisons",
                "inflated_fwer": 1 - (1 - self.alpha) ** self.n,
            },
        )

    def apply(self, method: Union[str, CorrectionMethod]) -> CorrectionResult:
        """
        Apply specified correction method.

        Args:
            method: Correction method name or enum

        Returns:
            CorrectionResult
        """
        if isinstance(method, str):
            method = CorrectionMethod(method)

        method_map = {
            CorrectionMethod.BONFERRONI: self.bonferroni,
            CorrectionMethod.SIDAK: self.sidak,
            CorrectionMethod.HOLM: self.holm,
            CorrectionMethod.HOLM_SIDAK: self.holm_sidak,
            CorrectionMethod.HOCHBERG: self.hochberg,
            CorrectionMethod.BENJAMINI_HOCHBERG: self.benjamini_hochberg,
            CorrectionMethod.BENJAMINI_YEKUTIELI: self.benjamini_yekutieli,
            CorrectionMethod.HOMMEL: self.hommel,
            CorrectionMethod.NONE: self.no_correction,
        }

        return method_map[method]()

    def compare_methods(self) -> Dict[str, CorrectionResult]:
        """
        Apply all methods and compare results.

        Returns:
            Dictionary of method -> CorrectionResult
        """
        results = {}
        for method in CorrectionMethod:
            try:
                results[method.value] = self.apply(method)
            except Exception as e:
                logger.warning(f"Failed to apply {method.value}: {e}")

        return results

    def _enforce_monotonicity_down(
        self,
        adjusted_p: np.ndarray,
        sorted_indices: np.ndarray
    ) -> np.ndarray:
        """Ensure adjusted p-values are monotonically increasing (step-down)."""
        adj = adjusted_p.copy()
        cummax = adj[sorted_indices[0]]
        for i in range(self.n):
            idx = sorted_indices[i]
            cummax = max(cummax, adj[idx])
            adj[idx] = cummax
        return adj

    def _enforce_monotonicity_up(
        self,
        adjusted_p: np.ndarray,
        sorted_indices: np.ndarray
    ) -> np.ndarray:
        """Ensure adjusted p-values are monotonically increasing (step-up)."""
        adj = adjusted_p.copy()
        # Process from largest to smallest, take cumulative minimum
        cummin = adj[sorted_indices[-1]]
        for i in range(self.n - 1, -1, -1):
            idx = sorted_indices[i]
            cummin = min(cummin, adj[idx])
            adj[idx] = cummin
        return adj


def correct_p_values(
    p_values: Union[List[float], np.ndarray],
    method: str = "benjamini_hochberg",
    alpha: float = 0.05,
) -> CorrectionResult:
    """
    Convenience function to correct p-values.

    Args:
        p_values: List or array of p-values
        method: Correction method name
        alpha: Significance level or FDR to control

    Returns:
        CorrectionResult
    """
    corrector = MultipleComparisonCorrector(p_values, alpha)
    return corrector.apply(method)


def get_significant_tests(
    p_values: Union[List[float], np.ndarray],
    method: str = "benjamini_hochberg",
    alpha: float = 0.05,
) -> np.ndarray:
    """
    Get indices of significant tests after correction.

    Args:
        p_values: List or array of p-values
        method: Correction method name
        alpha: Significance level or FDR to control

    Returns:
        Array of indices of significant tests
    """
    result = correct_p_values(p_values, method, alpha)
    return np.where(result.significant)[0]


class PostHocTests:
    """
    Post-hoc pairwise comparison tests.

    For use after ANOVA to determine which groups differ.
    """

    def __init__(self, alpha: float = 0.05):
        """
        Initialize post-hoc tester.

        Args:
            alpha: Family-wise error rate
        """
        self.alpha = alpha

    def tukey_hsd(
        self,
        *groups: np.ndarray,
        group_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Tukey's Honestly Significant Difference test.

        Compares all pairs of groups while controlling FWER.

        Args:
            *groups: Group data arrays
            group_names: Optional names for groups

        Returns:
            Dictionary with pairwise comparisons
        """
        groups = [np.asarray(g).flatten() for g in groups]
        k = len(groups)

        if k < 2:
            raise ValueError("Need at least 2 groups")

        if group_names is None:
            group_names = [f"Group_{i+1}" for i in range(k)]

        # Try using statsmodels
        try:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd

            all_data = np.concatenate(groups)
            group_labels = np.concatenate([[group_names[i]] * len(g)
                                          for i, g in enumerate(groups)])

            result = pairwise_tukeyhsd(all_data, group_labels, alpha=self.alpha)

            comparisons = []
            for row in result.summary().data[1:]:
                comparisons.append({
                    "group1": row[0],
                    "group2": row[1],
                    "mean_diff": float(row[2]),
                    "p_adj": float(row[3]),
                    "lower_ci": float(row[4]),
                    "upper_ci": float(row[5]),
                    "reject": bool(row[6]),
                })

            return {
                "method": "Tukey HSD",
                "alpha": self.alpha,
                "comparisons": comparisons,
                "summary": str(result),
                "n_comparisons": len(comparisons),
                "n_significant": sum(1 for c in comparisons if c["reject"]),
            }

        except ImportError:
            # Fallback: manual calculation
            return self._tukey_manual(*groups, group_names=group_names)

    def _tukey_manual(
        self,
        *groups: np.ndarray,
        group_names: List[str]
    ) -> Dict[str, Any]:
        """Manual Tukey HSD calculation."""
        k = len(groups)
        ns = [len(g) for g in groups]
        n_total = sum(ns)
        means = [np.mean(g) for g in groups]

        # Pooled variance (MSE)
        ss_within = sum(np.sum((g - np.mean(g))**2) for g in groups)
        df_within = n_total - k
        mse = ss_within / df_within

        # Studentized range critical value (approximation)
        # Using q-distribution: q(alpha, k, df)
        q_crit = stats.studentized_range.ppf(1 - self.alpha, k, df_within)

        comparisons = []
        for i in range(k):
            for j in range(i + 1, k):
                mean_diff = means[i] - means[j]
                se = np.sqrt(mse * (1/ns[i] + 1/ns[j]) / 2)

                # HSD threshold
                hsd = q_crit * se

                # p-value approximation
                q_stat = abs(mean_diff) / se
                p_adj = 1 - stats.studentized_range.cdf(q_stat, k, df_within)

                reject = abs(mean_diff) > hsd

                comparisons.append({
                    "group1": group_names[i],
                    "group2": group_names[j],
                    "mean_diff": float(mean_diff),
                    "p_adj": float(p_adj),
                    "lower_ci": float(mean_diff - hsd),
                    "upper_ci": float(mean_diff + hsd),
                    "reject": reject,
                })

        return {
            "method": "Tukey HSD (manual)",
            "alpha": self.alpha,
            "comparisons": comparisons,
            "n_comparisons": len(comparisons),
            "n_significant": sum(1 for c in comparisons if c["reject"]),
            "mse": float(mse),
            "q_critical": float(q_crit),
        }

    def games_howell(
        self,
        *groups: np.ndarray,
        group_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Games-Howell test.

        Does not assume equal variances.

        Args:
            *groups: Group data arrays
            group_names: Optional names for groups

        Returns:
            Dictionary with pairwise comparisons
        """
        groups = [np.asarray(g).flatten() for g in groups]
        k = len(groups)

        if group_names is None:
            group_names = [f"Group_{i+1}" for i in range(k)]

        ns = [len(g) for g in groups]
        means = [np.mean(g) for g in groups]
        variances = [np.var(g, ddof=1) for g in groups]

        comparisons = []
        for i in range(k):
            for j in range(i + 1, k):
                mean_diff = means[i] - means[j]

                # Welch-type SE
                se = np.sqrt(variances[i]/ns[i] + variances[j]/ns[j])

                # Welch-Satterthwaite df
                num = (variances[i]/ns[i] + variances[j]/ns[j])**2
                denom = (variances[i]/ns[i])**2/(ns[i]-1) + (variances[j]/ns[j])**2/(ns[j]-1)
                df = num / denom

                # t-statistic
                t_stat = mean_diff / se

                # Use studentized range for p-value
                try:
                    q_stat = abs(t_stat) * np.sqrt(2)
                    p_adj = 1 - stats.studentized_range.cdf(q_stat, k, df)
                except:
                    # Fallback to t-distribution with Bonferroni
                    p_adj = 2 * (1 - stats.t.cdf(abs(t_stat), df))
                    n_comparisons = k * (k - 1) / 2
                    p_adj = min(p_adj * n_comparisons, 1.0)

                reject = p_adj < self.alpha

                comparisons.append({
                    "group1": group_names[i],
                    "group2": group_names[j],
                    "mean_diff": float(mean_diff),
                    "se": float(se),
                    "df": float(df),
                    "p_adj": float(p_adj),
                    "reject": reject,
                })

        return {
            "method": "Games-Howell",
            "alpha": self.alpha,
            "comparisons": comparisons,
            "n_comparisons": len(comparisons),
            "n_significant": sum(1 for c in comparisons if c["reject"]),
            "note": "Does not assume equal variances",
        }

    def dunnett(
        self,
        control: np.ndarray,
        *treatments: np.ndarray,
        treatment_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Dunnett's test.

        Compares each treatment to a control group.

        Args:
            control: Control group data
            *treatments: Treatment group data arrays
            treatment_names: Optional names for treatments

        Returns:
            Dictionary with comparisons to control
        """
        control = np.asarray(control).flatten()
        treatments = [np.asarray(t).flatten() for t in treatments]
        k = len(treatments)  # Number of treatments

        if treatment_names is None:
            treatment_names = [f"Treatment_{i+1}" for i in range(k)]

        # Pool for MSE
        all_groups = [control] + treatments
        n_total = sum(len(g) for g in all_groups)
        ss_within = sum(np.sum((g - np.mean(g))**2) for g in all_groups)
        df_within = n_total - (k + 1)
        mse = ss_within / df_within

        mean_control = np.mean(control)
        n_control = len(control)

        comparisons = []
        for i, treatment in enumerate(treatments):
            mean_treat = np.mean(treatment)
            n_treat = len(treatment)

            mean_diff = mean_treat - mean_control
            se = np.sqrt(mse * (1/n_control + 1/n_treat))

            t_stat = mean_diff / se

            # Dunnett critical value (approximation using t-distribution)
            # For proper Dunnett, need multivariate t tables
            # Using Bonferroni approximation
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df_within))
            p_adj = min(p_value * k, 1.0)

            reject = p_adj < self.alpha

            comparisons.append({
                "treatment": treatment_names[i],
                "control_mean": float(mean_control),
                "treatment_mean": float(mean_treat),
                "mean_diff": float(mean_diff),
                "se": float(se),
                "t_stat": float(t_stat),
                "p_adj": float(p_adj),
                "reject": reject,
            })

        return {
            "method": "Dunnett (Bonferroni approximation)",
            "alpha": self.alpha,
            "comparisons": comparisons,
            "n_comparisons": len(comparisons),
            "n_significant": sum(1 for c in comparisons if c["reject"]),
            "mse": float(mse),
            "note": "Compares treatments to control",
        }

    def pairwise_t_tests(
        self,
        *groups: np.ndarray,
        correction: str = "benjamini_hochberg",
        group_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Pairwise t-tests with p-value correction.

        Args:
            *groups: Group data arrays
            correction: Multiple comparison correction method
            group_names: Optional names for groups

        Returns:
            Dictionary with pairwise comparisons
        """
        groups = [np.asarray(g).flatten() for g in groups]
        k = len(groups)

        if group_names is None:
            group_names = [f"Group_{i+1}" for i in range(k)]

        # Perform all pairwise t-tests
        p_values = []
        comparisons = []

        for i in range(k):
            for j in range(i + 1, k):
                t_stat, p_value = stats.ttest_ind(groups[i], groups[j])

                p_values.append(p_value)
                comparisons.append({
                    "group1": group_names[i],
                    "group2": group_names[j],
                    "mean_diff": float(np.mean(groups[i]) - np.mean(groups[j])),
                    "t_stat": float(t_stat),
                    "p_value": float(p_value),
                })

        # Apply correction
        corrector = MultipleComparisonCorrector(p_values, self.alpha)
        correction_result = corrector.apply(correction)

        # Add adjusted p-values and significance
        for idx, comp in enumerate(comparisons):
            comp["p_adj"] = float(correction_result.adjusted_p_values[idx])
            comp["reject"] = bool(correction_result.significant[idx])

        return {
            "method": f"Pairwise t-tests ({correction})",
            "alpha": self.alpha,
            "correction": correction,
            "comparisons": comparisons,
            "n_comparisons": len(comparisons),
            "n_significant": int(correction_result.n_significant),
        }
