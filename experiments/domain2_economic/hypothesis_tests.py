"""
Hypothesis Tests for Economic Performance (Domain 2).

Implements statistical tests for validating SHAKTI-CHAIN economic performance:
- H2.1: Participant ROI > 15%
- H2.2: Significant difference in ROI across agent types (ANOVA)
- H2.3: Welfare Distribution Fairness (Gini < 0.4)
- H2.4: Price Volatility (CV < 0.15)
- H2.5: Bid-Ask Spread < 10% of mid-price
- H2.6: Market Liquidity (Fill Rate > 80%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from .roi_calculator import RoiDistribution
from .fairness_metrics import calculate_gini_coefficient, bootstrap_gini_ci
from .liquidity_metrics import SpreadMetrics, VolatilityMetrics, bootstrap_cv_ci


@dataclass
class EconomicHypothesisResult:
    """
    Result of an economic hypothesis test.

    Attributes:
        hypothesis_id: Unique identifier (e.g., 'H2.1')
        description: Human-readable description
        null_hypothesis: H0 statement
        alternative_hypothesis: H1 statement
        test_name: Statistical test used
        test_statistic: Value of test statistic
        p_value: Probability under null hypothesis
        effect_size: Standardized effect size (Cohen's d, eta^2, etc.)
        confidence_interval: CI for the parameter of interest
        sample_size: Number of observations
        decision: 'reject_null' or 'fail_to_reject_null'
        conclusion: Human-readable conclusion
        raw_data: The data used for the test
        assumptions_met: Dictionary of assumption checks
        additional_info: Extra information specific to the test
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
    additional_info: Dict = field(default_factory=dict)

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
            "additional_info": self.additional_info,
        }

    @property
    def passed(self) -> bool:
        """Check if hypothesis test supports the economic performance claim."""
        return self.decision == "reject_null"


class EconomicHypothesisTester:
    """
    Statistical hypothesis tester for SHAKTI-CHAIN economic performance.

    Performs rigorous statistical tests with:
    - Assumption checking (normality, homoscedasticity)
    - Effect size calculations
    - Bootstrap confidence intervals
    - Multiple comparison corrections
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
        roi_distributions: List[RoiDistribution],
        welfare_distributions: List[np.ndarray],
        spread_metrics_list: List[SpreadMetrics],
        volatility_metrics_list: List[VolatilityMetrics],
        fill_rates: List[float],
    ) -> Dict[str, EconomicHypothesisResult]:
        """
        Run all economic hypothesis tests.

        Args:
            roi_distributions: ROI data from multiple simulation runs
            welfare_distributions: Welfare data from multiple runs
            spread_metrics_list: Spread metrics from multiple runs
            volatility_metrics_list: Volatility metrics from multiple runs
            fill_rates: Fill rates from multiple runs

        Returns:
            Dictionary mapping hypothesis ID to EconomicHypothesisResult
        """
        results = {}

        # Extract ROI data
        all_rois = np.concatenate([rd.all_rois for rd in roi_distributions])
        roi_by_type = self._merge_roi_by_type(roi_distributions)

        # Extract welfare data
        combined_welfare = np.concatenate(welfare_distributions) if welfare_distributions else np.array([])

        # Extract spread data
        all_spreads = np.array([sm.mean_spread_pct for sm in spread_metrics_list])

        # Extract volatility data
        all_cvs = np.array([vm.cv for vm in volatility_metrics_list])

        # H2.1: ROI > 15%
        results["H2.1"] = self.test_participant_roi(all_rois)

        # H2.2: ROI by agent type
        results["H2.2"] = self.test_roi_by_agent_type(roi_by_type)

        # H2.3: Welfare fairness (Gini < 0.4)
        results["H2.3"] = self.test_welfare_fairness(combined_welfare)

        # H2.4: Price volatility (CV < 0.15)
        results["H2.4"] = self.test_price_volatility(all_cvs)

        # H2.5: Bid-ask spread < 10%
        results["H2.5"] = self.test_bid_ask_spread(all_spreads)

        # H2.6: Fill rate > 80%
        results["H2.6"] = self.test_market_liquidity(np.array(fill_rates))

        # Apply multiple comparison correction
        if self.correction_method != "none":
            results = self._apply_correction(results)

        return results

    def _merge_roi_by_type(
        self,
        roi_distributions: List[RoiDistribution],
    ) -> Dict[str, np.ndarray]:
        """Merge ROI by type across multiple distributions."""
        merged = {}
        for rd in roi_distributions:
            for agent_type, rois in rd.roi_by_type.items():
                if agent_type not in merged:
                    merged[agent_type] = []
                merged[agent_type].extend(rois.tolist())

        return {k: np.array(v) for k, v in merged.items()}

    def test_participant_roi(
        self,
        roi_values: np.ndarray,
        threshold: float = 0.15,
    ) -> EconomicHypothesisResult:
        """
        Test H2.1: Mean participant ROI > 15%.

        H0: mu(ROI) <= 0.15
        H1: mu(ROI) > 0.15

        Uses one-sample t-test (one-tailed, greater).

        Args:
            roi_values: Array of ROI values (as decimals, e.g., 0.15 = 15%)
            threshold: ROI threshold (default 0.15 = 15%)

        Returns:
            EconomicHypothesisResult
        """
        n = len(roi_values)
        if n == 0:
            return self._empty_result("H2.1", "Participant ROI > 15%")

        mean_roi = np.mean(roi_values)
        std_roi = np.std(roi_values, ddof=1) if n > 1 else 0

        # Check normality
        normality_met = self._check_normality(roi_values)

        if normality_met and n >= self.min_samples:
            # One-sample t-test (one-tailed, greater)
            t_stat, two_tail_p = stats.ttest_1samp(roi_values, threshold)
            # One-tailed p-value for greater alternative
            p_value = two_tail_p / 2 if t_stat > 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test (one-tailed)"
            test_stat = t_stat
        else:
            # Wilcoxon signed-rank test
            shifted = roi_values - threshold
            try:
                stat, p_value = stats.wilcoxon(shifted, alternative='greater')
                test_stat = stat
            except ValueError:
                # All zeros
                test_stat = 0
                p_value = 0.0 if mean_roi > threshold else 1.0
            test_name = "Wilcoxon signed-rank test (one-tailed)"

        # Effect size (Cohen's d)
        effect_size = (mean_roi - threshold) / std_roi if std_roi > 0 else float('inf')

        # Bootstrap CI
        ci = self._bootstrap_ci(roi_values, np.mean)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        conclusion = (
            f"Mean ROI = {mean_roi*100:.2f}% (95% CI: [{ci[0]*100:.2f}%, {ci[1]*100:.2f}%]). "
            f"{'Exceeds' if decision == 'reject_null' else 'Does not exceed'} 15% threshold "
            f"(p={p_value:.4f}, d={effect_size:.3f})"
        )

        return EconomicHypothesisResult(
            hypothesis_id="H2.1",
            description="Participant ROI > 15%",
            null_hypothesis="mu(ROI) <= 0.15",
            alternative_hypothesis="mu(ROI) > 0.15",
            test_name=test_name,
            test_statistic=test_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=roi_values,
            assumptions_met={"normality": normality_met},
            additional_info={
                "mean_roi": float(mean_roi),
                "median_roi": float(np.median(roi_values)),
                "positive_roi_rate": float(np.mean(roi_values > 0)),
            },
        )

    def test_roi_by_agent_type(
        self,
        roi_by_type: Dict[str, np.ndarray],
    ) -> EconomicHypothesisResult:
        """
        Test H2.2: Significant difference in ROI across agent types.

        H0: mu_RAT = mu_BND = mu_ZI = mu_BEH (no difference)
        H1: At least one mean differs (significant difference)

        Uses one-way ANOVA with Tukey HSD post-hoc.

        Args:
            roi_by_type: Dictionary mapping agent type to ROI array

        Returns:
            EconomicHypothesisResult
        """
        # Filter out empty groups
        groups = {k: v for k, v in roi_by_type.items() if len(v) > 0}

        if len(groups) < 2:
            return self._empty_result("H2.2", "ROI varies by agent type")

        group_names = list(groups.keys())
        group_data = list(groups.values())
        all_data = np.concatenate(group_data)
        n = len(all_data)

        # Check assumptions
        normality_met = all(self._check_normality(g) for g in group_data if len(g) >= 3)
        homoscedasticity_met = self._check_homoscedasticity(*group_data)

        if normality_met and homoscedasticity_met:
            # One-way ANOVA
            f_stat, p_value = stats.f_oneway(*group_data)
            test_name = "One-way ANOVA"
            test_stat = f_stat

            # Effect size: eta-squared
            grand_mean = np.mean(all_data)
            ss_between = sum(len(g) * (np.mean(g) - grand_mean)**2 for g in group_data)
            ss_total = np.sum((all_data - grand_mean)**2)
            eta_squared = ss_between / ss_total if ss_total > 0 else 0
            effect_size = eta_squared
        else:
            # Kruskal-Wallis test (non-parametric)
            h_stat, p_value = stats.kruskal(*group_data)
            test_name = "Kruskal-Wallis H-test"
            test_stat = h_stat

            # Effect size: eta-squared approximation
            # η² = (H - k + 1) / (n - k)
            k = len(groups)
            eta_squared = (h_stat - k + 1) / (n - k) if n > k else 0
            eta_squared = max(0, eta_squared)
            effect_size = eta_squared

        # Post-hoc: Tukey HSD (if significant and parametric)
        tukey_results = None
        if p_value < self.alpha and normality_met:
            tukey_results = self._tukey_hsd(group_data, group_names)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        # Summary statistics by type
        type_stats = {
            name: {
                "mean": float(np.mean(data)),
                "std": float(np.std(data)),
                "n": len(data),
            }
            for name, data in groups.items()
        }

        conclusion = (
            f"ROI {'varies significantly' if decision == 'reject_null' else 'does not vary significantly'} "
            f"across {len(groups)} agent types (F={test_stat:.2f}, p={p_value:.4f}, eta^2={effect_size:.3f})"
        )

        return EconomicHypothesisResult(
            hypothesis_id="H2.2",
            description="ROI varies significantly by agent type",
            null_hypothesis="mu_RAT = mu_BND = mu_ZI = mu_BEH",
            alternative_hypothesis="At least one mean ROI differs",
            test_name=test_name,
            test_statistic=test_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=(0.0, 0.0),  # Not applicable for ANOVA
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=all_data,
            assumptions_met={
                "normality": normality_met,
                "homoscedasticity": homoscedasticity_met,
            },
            additional_info={
                "type_statistics": type_stats,
                "tukey_hsd": tukey_results,
                "eta_squared": float(effect_size),
            },
        )

    def test_welfare_fairness(
        self,
        welfare_distribution: np.ndarray,
        threshold: float = 0.4,
    ) -> EconomicHypothesisResult:
        """
        Test H2.3: Welfare distribution fairness (Gini < 0.4).

        H0: Gini >= 0.4 (unfair distribution)
        H1: Gini < 0.4 (fair distribution)

        Uses bootstrap CI for Gini coefficient.

        Args:
            welfare_distribution: Array of welfare values
            threshold: Gini threshold (default 0.4)

        Returns:
            EconomicHypothesisResult
        """
        n = len(welfare_distribution)
        if n == 0:
            return self._empty_result("H2.3", "Welfare Gini < 0.4")

        # Calculate Gini coefficient
        gini = calculate_gini_coefficient(welfare_distribution)

        # Bootstrap confidence interval
        ci = bootstrap_gini_ci(
            welfare_distribution,
            n_bootstrap=self.bootstrap_iterations,
            confidence=0.95,
        )

        # Decision based on upper CI bound
        # If upper bound < threshold, we can reject null
        decision = "reject_null" if ci[1] < threshold else "fail_to_reject_null"

        # "Effect size": how far below threshold
        effect_size = (threshold - gini) / threshold if threshold > 0 else 0

        # Approximate p-value using bootstrap
        bootstrap_ginis = self._bootstrap_statistic(
            welfare_distribution,
            calculate_gini_coefficient,
            self.bootstrap_iterations,
        )
        p_value = np.mean(bootstrap_ginis >= threshold)

        conclusion = (
            f"Gini coefficient = {gini:.4f} (95% CI: [{ci[0]:.4f}, {ci[1]:.4f}]). "
            f"Distribution {'is fair' if decision == 'reject_null' else 'is NOT fair'} "
            f"(threshold: {threshold}, p={p_value:.4f})"
        )

        return EconomicHypothesisResult(
            hypothesis_id="H2.3",
            description="Welfare distribution Gini < 0.4",
            null_hypothesis="Gini >= 0.4",
            alternative_hypothesis="Gini < 0.4",
            test_name="Bootstrap CI for Gini coefficient",
            test_statistic=gini,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=welfare_distribution,
            assumptions_met={},
            additional_info={
                "gini": float(gini),
                "threshold": threshold,
            },
        )

    def test_price_volatility(
        self,
        cv_values: np.ndarray,
        threshold: float = 0.15,
    ) -> EconomicHypothesisResult:
        """
        Test H2.4: Price volatility (CV < 0.15) under normal conditions.

        H0: CV >= 0.15 (high volatility)
        H1: CV < 0.15 (acceptable volatility)

        Uses bootstrap CI for coefficient of variation.

        Args:
            cv_values: Array of CV values from multiple periods
            threshold: CV threshold (default 0.15)

        Returns:
            EconomicHypothesisResult
        """
        n = len(cv_values)
        if n == 0:
            return self._empty_result("H2.4", "Price CV < 0.15")

        mean_cv = np.mean(cv_values)
        std_cv = np.std(cv_values, ddof=1) if n > 1 else 0

        # Bootstrap CI
        ci = self._bootstrap_ci(cv_values, np.mean)

        # Decision: if upper CI bound < threshold, reject null
        decision = "reject_null" if ci[1] < threshold else "fail_to_reject_null"

        # One-sample t-test (one-tailed, less)
        if n >= self.min_samples and std_cv > 0:
            t_stat, two_tail_p = stats.ttest_1samp(cv_values, threshold)
            p_value = two_tail_p / 2 if t_stat < 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test (one-tailed, less)"
        else:
            # Use proportion below threshold as p-value proxy
            p_value = np.mean(cv_values < threshold)
            t_stat = (mean_cv - threshold) / (std_cv / np.sqrt(n)) if std_cv > 0 else 0
            test_name = "Bootstrap proportion test"

        effect_size = (threshold - mean_cv) / std_cv if std_cv > 0 else float('inf')

        conclusion = (
            f"Mean CV = {mean_cv:.4f} (95% CI: [{ci[0]:.4f}, {ci[1]:.4f}]). "
            f"Volatility {'is acceptable' if decision == 'reject_null' else 'is NOT acceptable'} "
            f"(threshold: {threshold}, p={p_value:.4f})"
        )

        return EconomicHypothesisResult(
            hypothesis_id="H2.4",
            description="Price CV < 0.15 under normal conditions",
            null_hypothesis="CV >= 0.15",
            alternative_hypothesis="CV < 0.15",
            test_name=test_name,
            test_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=cv_values,
            assumptions_met={},
            additional_info={
                "mean_cv": float(mean_cv),
                "median_cv": float(np.median(cv_values)),
                "max_cv": float(np.max(cv_values)),
                "pct_below_threshold": float(np.mean(cv_values < threshold)),
            },
        )

    def test_bid_ask_spread(
        self,
        spread_values: np.ndarray,
        threshold: float = 0.10,
    ) -> EconomicHypothesisResult:
        """
        Test H2.5: Mean bid-ask spread < 10% of mid-price.

        H0: Spread >= 0.10 (high spread)
        H1: Spread < 0.10 (acceptable spread)

        Uses one-sample t-test (one-tailed, less).

        Args:
            spread_values: Array of spread percentages (as decimals)
            threshold: Spread threshold (default 0.10 = 10%)

        Returns:
            EconomicHypothesisResult
        """
        n = len(spread_values)
        if n == 0:
            return self._empty_result("H2.5", "Spread < 10%")

        mean_spread = np.mean(spread_values)
        std_spread = np.std(spread_values, ddof=1) if n > 1 else 0

        # Check normality
        normality_met = self._check_normality(spread_values)

        if normality_met and n >= self.min_samples:
            # One-sample t-test (one-tailed, less)
            t_stat, two_tail_p = stats.ttest_1samp(spread_values, threshold)
            p_value = two_tail_p / 2 if t_stat < 0 else 1 - two_tail_p / 2
            test_name = "One-sample t-test (one-tailed, less)"
        else:
            # Wilcoxon test
            shifted = spread_values - threshold
            try:
                stat, p_value = stats.wilcoxon(shifted, alternative='less')
                t_stat = stat
            except ValueError:
                t_stat = 0
                p_value = 1.0 if mean_spread >= threshold else 0.0
            test_name = "Wilcoxon signed-rank test (one-tailed, less)"

        # Effect size
        effect_size = (threshold - mean_spread) / std_spread if std_spread > 0 else float('inf')

        # Bootstrap CI
        ci = self._bootstrap_ci(spread_values, np.mean)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        conclusion = (
            f"Mean spread = {mean_spread*100:.2f}% (95% CI: [{ci[0]*100:.2f}%, {ci[1]*100:.2f}%]). "
            f"Spread {'is acceptable' if decision == 'reject_null' else 'is NOT acceptable'} "
            f"(threshold: {threshold*100:.0f}%, p={p_value:.4f})"
        )

        return EconomicHypothesisResult(
            hypothesis_id="H2.5",
            description="Bid-ask spread < 10% of mid-price",
            null_hypothesis="Spread >= 0.10",
            alternative_hypothesis="Spread < 0.10",
            test_name=test_name,
            test_statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=spread_values,
            assumptions_met={"normality": normality_met},
            additional_info={
                "mean_spread_pct": float(mean_spread * 100),
                "median_spread_pct": float(np.median(spread_values) * 100),
            },
        )

    def test_market_liquidity(
        self,
        fill_rates: np.ndarray,
        threshold: float = 0.80,
    ) -> EconomicHypothesisResult:
        """
        Test H2.6: Market liquidity (fill rate > 80%).

        H0: Fill rate <= 0.80 (insufficient liquidity)
        H1: Fill rate > 0.80 (adequate liquidity)

        Uses one-sample proportion z-test.

        Args:
            fill_rates: Array of fill rates (proportions)
            threshold: Fill rate threshold (default 0.80 = 80%)

        Returns:
            EconomicHypothesisResult
        """
        n = len(fill_rates)
        if n == 0:
            return self._empty_result("H2.6", "Fill rate > 80%")

        mean_fill = np.mean(fill_rates)
        std_fill = np.std(fill_rates, ddof=1) if n > 1 else 0

        # For proportions, use z-test
        # Standard error under null hypothesis
        se_null = np.sqrt(threshold * (1 - threshold) / n)

        # Z statistic
        z_stat = (mean_fill - threshold) / se_null if se_null > 0 else 0

        # One-tailed p-value (greater)
        p_value = 1 - stats.norm.cdf(z_stat)

        test_name = "One-sample proportion z-test (one-tailed)"

        # Effect size (Cohen's h for proportions)
        h = 2 * np.arcsin(np.sqrt(mean_fill)) - 2 * np.arcsin(np.sqrt(threshold))
        effect_size = h

        # Bootstrap CI
        ci = self._bootstrap_ci(fill_rates, np.mean)

        decision = "reject_null" if p_value < self.alpha else "fail_to_reject_null"

        conclusion = (
            f"Mean fill rate = {mean_fill*100:.2f}% (95% CI: [{ci[0]*100:.2f}%, {ci[1]*100:.2f}%]). "
            f"Liquidity {'is adequate' if decision == 'reject_null' else 'is NOT adequate'} "
            f"(threshold: {threshold*100:.0f}%, p={p_value:.4f})"
        )

        return EconomicHypothesisResult(
            hypothesis_id="H2.6",
            description="Market fill rate > 80%",
            null_hypothesis="Fill rate <= 0.80",
            alternative_hypothesis="Fill rate > 0.80",
            test_name=test_name,
            test_statistic=z_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            sample_size=n,
            decision=decision,
            conclusion=conclusion,
            raw_data=fill_rates,
            assumptions_met={},
            additional_info={
                "mean_fill_rate": float(mean_fill),
                "min_fill_rate": float(np.min(fill_rates)),
                "pct_above_threshold": float(np.mean(fill_rates > threshold)),
            },
        )

    def _check_normality(
        self,
        data: np.ndarray,
        alpha: float = 0.05,
    ) -> bool:
        """Check normality assumption using Shapiro-Wilk test."""
        if len(data) < 3:
            return False
        if len(data) > 5000:
            data = np.random.choice(data, 5000, replace=False)

        try:
            _, p_value = stats.shapiro(data)
            return p_value > alpha
        except Exception:
            return False

    def _check_homoscedasticity(
        self,
        *groups: np.ndarray,
        alpha: float = 0.05,
    ) -> bool:
        """Check homoscedasticity using Levene's test."""
        if len(groups) < 2:
            return True
        if any(len(g) < 3 for g in groups):
            return False

        try:
            _, p_value = stats.levene(*groups)
            return p_value > alpha
        except Exception:
            return False

    def _bootstrap_ci(
        self,
        data: np.ndarray,
        statistic_func,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Compute bootstrap confidence interval."""
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

        return (float(lower), float(upper))

    def _bootstrap_statistic(
        self,
        data: np.ndarray,
        statistic_func,
        n_iterations: int,
    ) -> np.ndarray:
        """Generate bootstrap distribution of a statistic."""
        n = len(data)
        bootstrap_stats = np.empty(n_iterations)

        for i in range(n_iterations):
            resample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats[i] = statistic_func(resample)

        return bootstrap_stats

    def _tukey_hsd(
        self,
        groups: List[np.ndarray],
        group_names: List[str],
    ) -> List[dict]:
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
                    p_value = np.nan

                results.append({
                    "group1": group_names[i],
                    "group2": group_names[j],
                    "mean_difference": float(mean_diff),
                    "std_error": float(se),
                    "q_statistic": float(q),
                    "p_value": float(p_value),
                    "significant": p_value < self.alpha if not np.isnan(p_value) else False,
                })

        return results

    def _apply_correction(
        self,
        results: Dict[str, EconomicHypothesisResult],
    ) -> Dict[str, EconomicHypothesisResult]:
        """Apply multiple comparison correction."""
        hypothesis_ids = list(results.keys())
        p_values = np.array([results[h].p_value for h in hypothesis_ids])
        n_tests = len(p_values)

        if self.correction_method == "bonferroni":
            adjusted_alpha = self.alpha / n_tests
            for h_id in hypothesis_ids:
                result = results[h_id]
                new_decision = "reject_null" if result.p_value < adjusted_alpha else "fail_to_reject_null"
                if new_decision != result.decision:
                    results[h_id] = EconomicHypothesisResult(
                        hypothesis_id=result.hypothesis_id,
                        description=result.description,
                        null_hypothesis=result.null_hypothesis,
                        alternative_hypothesis=result.alternative_hypothesis,
                        test_name=result.test_name + " (Bonferroni)",
                        test_statistic=result.test_statistic,
                        p_value=result.p_value,
                        effect_size=result.effect_size,
                        confidence_interval=result.confidence_interval,
                        sample_size=result.sample_size,
                        decision=new_decision,
                        conclusion=result.conclusion,
                        raw_data=result.raw_data,
                        assumptions_met=result.assumptions_met,
                        additional_info=result.additional_info,
                    )

        elif self.correction_method == "holm":
            sorted_indices = np.argsort(p_values)
            adjusted_decisions = {}

            for rank, idx in enumerate(sorted_indices):
                h_id = hypothesis_ids[idx]
                adjusted_alpha = self.alpha / (n_tests - rank)
                result = results[h_id]

                if result.p_value >= adjusted_alpha:
                    for remaining_idx in sorted_indices[rank:]:
                        remaining_h_id = hypothesis_ids[remaining_idx]
                        adjusted_decisions[remaining_h_id] = "fail_to_reject_null"
                    break
                else:
                    adjusted_decisions[h_id] = "reject_null"

            for h_id in hypothesis_ids:
                if h_id not in adjusted_decisions:
                    adjusted_decisions[h_id] = "reject_null"

            for h_id, new_decision in adjusted_decisions.items():
                result = results[h_id]
                if new_decision != result.decision:
                    results[h_id] = EconomicHypothesisResult(
                        hypothesis_id=result.hypothesis_id,
                        description=result.description,
                        null_hypothesis=result.null_hypothesis,
                        alternative_hypothesis=result.alternative_hypothesis,
                        test_name=result.test_name + " (Holm)",
                        test_statistic=result.test_statistic,
                        p_value=result.p_value,
                        effect_size=result.effect_size,
                        confidence_interval=result.confidence_interval,
                        sample_size=result.sample_size,
                        decision=new_decision,
                        conclusion=result.conclusion,
                        raw_data=result.raw_data,
                        assumptions_met=result.assumptions_met,
                        additional_info=result.additional_info,
                    )

        return results

    def _empty_result(
        self,
        hypothesis_id: str,
        description: str,
    ) -> EconomicHypothesisResult:
        """Create an empty result for when there's no data."""
        return EconomicHypothesisResult(
            hypothesis_id=hypothesis_id,
            description=description,
            null_hypothesis="",
            alternative_hypothesis="",
            test_name="No test (insufficient data)",
            test_statistic=np.nan,
            p_value=np.nan,
            effect_size=np.nan,
            confidence_interval=(np.nan, np.nan),
            sample_size=0,
            decision="fail_to_reject_null",
            conclusion="Insufficient data for hypothesis test",
            raw_data=np.array([]),
            assumptions_met={},
        )

    def generate_summary_report(
        self,
        results: Dict[str, EconomicHypothesisResult],
    ) -> str:
        """Generate a human-readable summary report."""
        lines = [
            "=" * 80,
            "ECONOMIC PERFORMANCE HYPOTHESIS TESTS - SUMMARY REPORT",
            "=" * 80,
            "",
            f"Significance Level: alpha = {self.alpha}",
            f"Multiple Comparison Correction: {self.correction_method}",
            "",
            "-" * 80,
        ]

        passed = 0
        total = len(results)

        for h_id in sorted(results.keys()):
            result = results[h_id]
            status = "PASS" if result.passed else "FAIL"
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
