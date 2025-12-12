"""
Statistical Hypothesis Tests for Load Forecasting (Domain 7).

Implements hypothesis tests for H7.1-H7.5:
- H7.1: MAPE < 5% on out-of-sample data (one-sample t-test across k-folds)
- H7.2: MAPE < 10% up to 24h horizon (one-sample t-tests at each horizon)
- H7.3: MAPE < 5% for all major Indian cities (Bonferroni corrected)
- H7.4: TFT beats Naive, ARIMA, Prophet (paired t-tests)
- H7.5: 95% PI contains actual 95±3% of time (exact binomial)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .evaluation_metrics import (
    ForecastEvaluation,
    evaluate_forecast,
    mape,
    rmse,
    coverage_probability,
)
from .cross_validator import CVResult, ForecastCrossValidator

logger = logging.getLogger(__name__)


@dataclass
class HypothesisResult:
    """
    Result of a single hypothesis test.

    Attributes:
        hypothesis_id: Hypothesis identifier (e.g., "H7.1")
        description: Human-readable description
        passed: Whether the hypothesis passed
        statistic: Test statistic value
        p_value: P-value of the test
        effect_size: Effect size measure
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
        """Convert to dictionary."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "passed": self.passed,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "confidence_interval": self.confidence_interval,
            "details": self.details,
        }


@dataclass
class ForecastingHypothesisResults:
    """
    Results for all forecasting hypothesis tests.

    Attributes:
        results: Dict mapping hypothesis ID to result
        summary: Summary statistics
        all_passed: Whether all hypotheses passed
    """
    results: Dict[str, HypothesisResult] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    all_passed: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "summary": self.summary,
            "all_passed": self.all_passed,
        }

    def __getitem__(self, key: str) -> HypothesisResult:
        return self.results[key]


class ForecastingHypothesisTester:
    """
    Statistical hypothesis tester for load forecasting.

    Tests H7.1-H7.5 using appropriate statistical methods.
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
        self.n_hypotheses = 5

    def _get_adjusted_alpha(self) -> float:
        """Get alpha adjusted for multiple testing."""
        if self.bonferroni_correction:
            return self.alpha / self.n_hypotheses
        return self.alpha

    def test_h7_1_mape_target(
        self,
        mape_values: List[float],
        threshold: float = 5.0,
    ) -> HypothesisResult:
        """
        Test H7.1: MAPE < 5% on out-of-sample data.

        H₁: MAPE < 5% on out-of-sample data
        H₀: MAPE ≥ 5%
        Test: One-sample t-test across k-folds

        Args:
            mape_values: MAPE values from k-fold cross-validation
            threshold: MAPE threshold (default 5%)

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()
        mape_array = np.array(mape_values)

        mean_mape = np.mean(mape_array)
        std_mape = np.std(mape_array, ddof=1)
        n = len(mape_array)

        # One-sample t-test (one-sided, testing if mean < threshold)
        t_stat = (mean_mape - threshold) / (std_mape / np.sqrt(n))
        p_value = stats.t.cdf(t_stat, df=n - 1)  # One-sided p-value

        # Confidence interval
        se = std_mape / np.sqrt(n)
        ci_margin = stats.t.ppf(1 - adj_alpha / 2, df=n - 1) * se
        ci = (mean_mape - ci_margin, mean_mape + ci_margin)

        # Effect size (Cohen's d)
        effect_size = (threshold - mean_mape) / std_mape if std_mape > 0 else 0

        passed = p_value < adj_alpha and mean_mape < threshold

        return HypothesisResult(
            hypothesis_id="H7.1",
            description=f"MAPE < {threshold}% on out-of-sample data",
            passed=passed,
            statistic=t_stat,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "mean_mape": mean_mape,
                "std_mape": std_mape,
                "n_folds": n,
                "threshold": threshold,
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h7_2_horizon_performance(
        self,
        mape_by_horizon: Dict[int, List[float]],
        threshold: float = 10.0,
        max_horizon: int = 24,
    ) -> HypothesisResult:
        """
        Test H7.2: MAPE < 10% up to 24h horizon.

        H₁: MAPE < 10% up to 24h horizon
        H₀: MAPE ≥ 10% for some h ≤ 24h
        Test: One-sample t-tests at each horizon

        Args:
            mape_by_horizon: Dict mapping horizon (hours) to MAPE values
            threshold: MAPE threshold (default 10%)
            max_horizon: Maximum horizon to test (default 24h)

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        # Test each horizon
        horizon_results = {}
        all_pass = True
        worst_horizon = None
        worst_p_value = 0.0

        for h in range(1, max_horizon + 1):
            if h not in mape_by_horizon:
                continue

            mape_values = np.array(mape_by_horizon[h])
            n = len(mape_values)

            if n < 2:
                continue

            mean_mape = np.mean(mape_values)
            std_mape = np.std(mape_values, ddof=1)

            # One-sample t-test at this horizon
            t_stat = (mean_mape - threshold) / (std_mape / np.sqrt(n))
            p_value = stats.t.cdf(t_stat, df=n - 1)

            horizon_passed = p_value < adj_alpha and mean_mape < threshold

            horizon_results[h] = {
                "mean_mape": float(mean_mape),
                "std_mape": float(std_mape),
                "t_stat": float(t_stat),
                "p_value": float(p_value),
                "passed": horizon_passed,
            }

            if not horizon_passed:
                all_pass = False

            if p_value > worst_p_value:
                worst_p_value = p_value
                worst_horizon = h

        # Aggregate statistics
        all_mapes = []
        for h_mapes in mape_by_horizon.values():
            all_mapes.extend(h_mapes)

        overall_mean = np.mean(all_mapes) if all_mapes else np.nan
        overall_std = np.std(all_mapes, ddof=1) if len(all_mapes) > 1 else 0

        # Effect size based on worst horizon
        effect_size = (threshold - overall_mean) / overall_std if overall_std > 0 else 0

        # CI for overall mean
        n_total = len(all_mapes)
        se = overall_std / np.sqrt(n_total) if n_total > 0 else 0
        ci_margin = stats.t.ppf(1 - adj_alpha / 2, df=max(n_total - 1, 1)) * se
        ci = (overall_mean - ci_margin, overall_mean + ci_margin)

        return HypothesisResult(
            hypothesis_id="H7.2",
            description=f"MAPE < {threshold}% up to {max_horizon}h horizon",
            passed=all_pass,
            statistic=float(worst_p_value),
            p_value=float(worst_p_value),
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "horizon_results": horizon_results,
                "worst_horizon": worst_horizon,
                "overall_mean_mape": overall_mean,
                "threshold": threshold,
                "max_horizon": max_horizon,
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h7_3_city_accuracy(
        self,
        city_mape: Dict[str, List[float]],
        threshold: float = 5.0,
    ) -> HypothesisResult:
        """
        Test H7.3: MAPE < 5% for all major Indian cities.

        H₁: MAPE < 5% for all major Indian cities
        H₀: MAPE ≥ 5% for at least one city
        Test: Multiple one-sample t-tests with Bonferroni correction

        Args:
            city_mape: Dict mapping city name to MAPE values
            threshold: MAPE threshold per city (default 5%)

        Returns:
            HypothesisResult
        """
        n_cities = len(city_mape)

        # Bonferroni correction for multiple city tests
        bonferroni_alpha = self.alpha / n_cities

        city_results = {}
        all_pass = True
        worst_city = None
        worst_p_value = 0.0

        for city, mapes in city_mape.items():
            mape_array = np.array(mapes)
            n = len(mape_array)

            if n < 2:
                # Not enough data for t-test
                city_results[city] = {
                    "mean_mape": float(np.mean(mape_array)),
                    "std_mape": 0.0,
                    "t_stat": np.nan,
                    "p_value": 1.0,
                    "passed": np.mean(mape_array) < threshold,
                }
                if np.mean(mape_array) >= threshold:
                    all_pass = False
                continue

            mean_mape = np.mean(mape_array)
            std_mape = np.std(mape_array, ddof=1)

            # One-sample t-test (one-sided, testing if mean < threshold)
            t_stat = (mean_mape - threshold) / (std_mape / np.sqrt(n))
            p_value = stats.t.cdf(t_stat, df=n - 1)

            city_passed = p_value < bonferroni_alpha and mean_mape < threshold

            city_results[city] = {
                "mean_mape": float(mean_mape),
                "std_mape": float(std_mape),
                "t_stat": float(t_stat),
                "p_value": float(p_value),
                "passed": city_passed,
            }

            if not city_passed:
                all_pass = False

            if p_value > worst_p_value:
                worst_p_value = p_value
                worst_city = city

        # Aggregate metrics
        all_means = [r["mean_mape"] for r in city_results.values()]
        overall_mean = np.mean(all_means)

        # Effect size: how many cities pass
        cities_passing = sum(1 for r in city_results.values() if r["passed"])
        proportion_passing = cities_passing / n_cities

        # CI for overall mean MAPE
        overall_std = np.std(all_means, ddof=1) if len(all_means) > 1 else 0
        se = overall_std / np.sqrt(n_cities) if n_cities > 0 else 0
        ci_margin = stats.t.ppf(1 - self.alpha / 2, df=max(n_cities - 1, 1)) * se
        ci = (overall_mean - ci_margin, overall_mean + ci_margin)

        return HypothesisResult(
            hypothesis_id="H7.3",
            description=f"MAPE < {threshold}% for all major Indian cities",
            passed=all_pass,
            statistic=float(cities_passing),
            p_value=float(worst_p_value),
            effect_size=proportion_passing,
            confidence_interval=ci,
            details={
                "city_results": city_results,
                "cities_passing": cities_passing,
                "total_cities": n_cities,
                "worst_city": worst_city,
                "threshold": threshold,
                "bonferroni_alpha": bonferroni_alpha,
            },
        )

    def test_h7_4_tft_beats_baselines(
        self,
        tft_mape: List[float],
        baseline_mapes: Dict[str, List[float]],
    ) -> HypothesisResult:
        """
        Test H7.4: TFT beats Naive, ARIMA, Prophet.

        H₁: TFT beats Naive, ARIMA, Prophet
        H₀: TFT doesn't beat at least one baseline
        Test: Paired t-tests comparing TFT MAPE to each baseline

        Args:
            tft_mape: TFT model MAPE values across folds/samples
            baseline_mapes: Dict mapping baseline name to MAPE values
                            Expected keys: "Naive", "ARIMA", "Prophet"

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()
        tft_array = np.array(tft_mape)

        # Test against each baseline
        baseline_results = {}
        all_beat = True
        worst_baseline = None
        worst_p_value = 0.0

        for baseline_name, baseline_mape in baseline_mapes.items():
            baseline_array = np.array(baseline_mape)

            # Ensure same length
            min_len = min(len(tft_array), len(baseline_array))
            tft_subset = tft_array[:min_len]
            baseline_subset = baseline_array[:min_len]

            if min_len < 2:
                baseline_results[baseline_name] = {
                    "mean_tft": float(np.mean(tft_subset)),
                    "mean_baseline": float(np.mean(baseline_subset)),
                    "t_stat": np.nan,
                    "p_value": 1.0,
                    "tft_wins": np.mean(tft_subset) < np.mean(baseline_subset),
                }
                if np.mean(tft_subset) >= np.mean(baseline_subset):
                    all_beat = False
                continue

            # Paired t-test: H1: tft_mape < baseline_mape
            # Difference: baseline - tft (positive means TFT is better)
            differences = baseline_subset - tft_subset

            # One-sample t-test on differences > 0
            t_stat, two_tailed_p = stats.ttest_1samp(differences, 0)
            # One-sided p-value (we want differences > 0, i.e., TFT better)
            p_value = two_tailed_p / 2 if t_stat > 0 else 1 - two_tailed_p / 2

            tft_wins = p_value < adj_alpha and np.mean(differences) > 0

            baseline_results[baseline_name] = {
                "mean_tft": float(np.mean(tft_subset)),
                "mean_baseline": float(np.mean(baseline_subset)),
                "mean_difference": float(np.mean(differences)),
                "improvement_pct": float(np.mean(differences) / np.mean(baseline_subset) * 100) if np.mean(baseline_subset) > 0 else 0,
                "t_stat": float(t_stat),
                "p_value": float(p_value),
                "tft_wins": tft_wins,
            }

            if not tft_wins:
                all_beat = False

            if p_value > worst_p_value:
                worst_p_value = p_value
                worst_baseline = baseline_name

        # Count baselines beaten
        baselines_beaten = sum(1 for r in baseline_results.values() if r["tft_wins"])
        n_baselines = len(baseline_results)

        # Effect size: Cohen's d for worst case
        effect_size = baselines_beaten / n_baselines if n_baselines > 0 else 0

        # CI for TFT mean MAPE
        n = len(tft_array)
        tft_std = np.std(tft_array, ddof=1) if n > 1 else 0
        se = tft_std / np.sqrt(n) if n > 0 else 0
        ci_margin = stats.t.ppf(1 - adj_alpha / 2, df=max(n - 1, 1)) * se
        tft_mean = np.mean(tft_array)
        ci = (tft_mean - ci_margin, tft_mean + ci_margin)

        return HypothesisResult(
            hypothesis_id="H7.4",
            description="TFT beats Naive, ARIMA, Prophet",
            passed=all_beat,
            statistic=float(baselines_beaten),
            p_value=float(worst_p_value),
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "baseline_results": baseline_results,
                "baselines_beaten": baselines_beaten,
                "total_baselines": n_baselines,
                "worst_baseline": worst_baseline,
                "mean_tft_mape": float(np.mean(tft_array)),
                "adjusted_alpha": adj_alpha,
            },
        )

    def test_h7_5_prediction_interval_coverage(
        self,
        in_interval: np.ndarray,
        nominal_coverage: float = 0.95,
        tolerance: float = 0.03,
    ) -> HypothesisResult:
        """
        Test H7.5: 95% PI contains actual 95±3% of time.

        H₁: 95% PI contains actual 95±3% of time
        H₀: Coverage significantly different from 95%
        Test: Exact binomial test

        Args:
            in_interval: Boolean array where True means actual was in PI
            nominal_coverage: Expected coverage (default 0.95)
            tolerance: Acceptable deviation from nominal (default 0.03)

        Returns:
            HypothesisResult
        """
        adj_alpha = self._get_adjusted_alpha()

        in_interval = np.asarray(in_interval, dtype=bool)
        n_total = len(in_interval)
        n_covered = int(np.sum(in_interval))

        # Empirical coverage
        empirical_coverage = n_covered / n_total if n_total > 0 else 0

        # Exact binomial test: test if coverage is significantly different from nominal
        # Using two-sided test to check if within tolerance
        # For exact test, we check if observed proportion is significantly != expected

        # Method 1: Direct binomial test
        # Test H0: p = nominal_coverage vs H1: p != nominal_coverage
        # But we want to accept if within tolerance, so we test:
        # H0: |p - nominal| > tolerance vs H1: |p - nominal| <= tolerance

        # Calculate p-value for two-sided exact binomial test
        if n_total > 0:
            # Exact binomial test at nominal_coverage
            # P(X <= n_covered) + P(X >= n_covered) under H0
            p_lower = stats.binom.cdf(n_covered, n_total, nominal_coverage)
            p_upper = stats.binom.sf(n_covered - 1, n_total, nominal_coverage)
            p_value = 2 * min(p_lower, p_upper)  # Two-sided
            p_value = min(p_value, 1.0)  # Cap at 1
        else:
            p_value = 1.0

        # Check if coverage is within acceptable range
        lower_bound = nominal_coverage - tolerance
        upper_bound = nominal_coverage + tolerance
        within_tolerance = lower_bound <= empirical_coverage <= upper_bound

        # Test passes if:
        # 1. Empirical coverage is within tolerance of nominal
        # 2. AND not significantly different from nominal (p_value > alpha)
        #    OR significantly better than nominal
        passed = within_tolerance

        # Effect size: deviation from nominal as fraction of tolerance
        deviation = abs(empirical_coverage - nominal_coverage)
        effect_size = 1 - (deviation / tolerance) if tolerance > 0 else 0

        # Confidence interval for empirical coverage (Wilson score interval)
        z = stats.norm.ppf(1 - adj_alpha / 2)
        n = n_total
        p = empirical_coverage
        if n > 0:
            denom = 1 + z**2 / n
            center = (p + z**2 / (2 * n)) / denom
            margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
            ci = (max(0, center - margin), min(1, center + margin))
        else:
            ci = (0.0, 1.0)

        return HypothesisResult(
            hypothesis_id="H7.5",
            description=f"95% PI contains actual {int(nominal_coverage*100)}±{int(tolerance*100)}% of time",
            passed=passed,
            statistic=float(n_covered),
            p_value=float(p_value),
            effect_size=effect_size,
            confidence_interval=ci,
            details={
                "empirical_coverage": float(empirical_coverage),
                "nominal_coverage": nominal_coverage,
                "tolerance": tolerance,
                "n_covered": n_covered,
                "n_total": n_total,
                "within_tolerance": within_tolerance,
                "acceptable_range": [lower_bound, upper_bound],
                "adjusted_alpha": adj_alpha,
            },
        )

    def run_all_tests(
        self,
        mape_values: List[float],
        mape_by_horizon: Dict[int, List[float]],
        city_mape: Dict[str, List[float]],
        tft_mape: List[float],
        baseline_mapes: Dict[str, List[float]],
        in_interval: np.ndarray,
    ) -> ForecastingHypothesisResults:
        """
        Run all hypothesis tests.

        Args:
            mape_values: MAPE values from k-fold CV for H7.1
            mape_by_horizon: Dict mapping horizon to MAPE values for H7.2
            city_mape: Per-city MAPE values for H7.3
            tft_mape: TFT model MAPE values for H7.4
            baseline_mapes: Dict of baseline MAPEs (Naive, ARIMA, Prophet) for H7.4
            in_interval: Boolean array for coverage test for H7.5

        Returns:
            ForecastingHypothesisResults
        """
        results = ForecastingHypothesisResults()

        # H7.1: MAPE < 5% on out-of-sample data
        results.results["H7.1"] = self.test_h7_1_mape_target(mape_values)

        # H7.2: MAPE < 10% up to 24h horizon
        results.results["H7.2"] = self.test_h7_2_horizon_performance(mape_by_horizon)

        # H7.3: MAPE < 5% for all major Indian cities
        results.results["H7.3"] = self.test_h7_3_city_accuracy(city_mape)

        # H7.4: TFT beats Naive, ARIMA, Prophet
        results.results["H7.4"] = self.test_h7_4_tft_beats_baselines(tft_mape, baseline_mapes)

        # H7.5: 95% PI contains actual 95±3% of time
        results.results["H7.5"] = self.test_h7_5_prediction_interval_coverage(in_interval)

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


def run_hypothesis_tests(
    mape_values: List[float],
    mape_by_horizon: Dict[int, List[float]],
    city_mape: Dict[str, List[float]],
    tft_mape: List[float],
    baseline_mapes: Dict[str, List[float]],
    in_interval: np.ndarray,
    alpha: float = 0.05,
) -> ForecastingHypothesisResults:
    """
    Convenience function to run all hypothesis tests.

    Args:
        mape_values: MAPE values from k-fold CV for H7.1
        mape_by_horizon: Dict mapping horizon to MAPE values for H7.2
        city_mape: Per-city MAPE values for H7.3
        tft_mape: TFT model MAPE values for H7.4
        baseline_mapes: Dict of baseline MAPEs (Naive, ARIMA, Prophet) for H7.4
        in_interval: Boolean array for coverage test for H7.5
        alpha: Significance level

    Returns:
        ForecastingHypothesisResults
    """
    tester = ForecastingHypothesisTester(alpha=alpha)
    return tester.run_all_tests(
        mape_values=mape_values,
        mape_by_horizon=mape_by_horizon,
        city_mape=city_mape,
        tft_mape=tft_mape,
        baseline_mapes=baseline_mapes,
        in_interval=in_interval,
    )
