"""
Evaluation Metrics for SHAKTI-CHAIN Load Forecasting (Domain 7).

Provides comprehensive evaluation metrics for time series forecasting:
- MAPE (Mean Absolute Percentage Error)
- RMSE (Root Mean Square Error)
- MAE (Mean Absolute Error)
- Prediction Interval Coverage
- Sharpness
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class ForecastEvaluation:
    """
    Comprehensive forecast evaluation results.

    Attributes:
        mape: Mean Absolute Percentage Error (%)
        rmse: Root Mean Square Error
        mae: Mean Absolute Error
        smape: Symmetric MAPE
        mase: Mean Absolute Scaled Error
        r_squared: R-squared (coefficient of determination)
        coverage: Prediction interval coverage
        sharpness: Average prediction interval width
        bias: Mean error (positive = over-prediction)
        n_samples: Number of samples evaluated
    """
    mape: float
    rmse: float
    mae: float
    smape: float
    mase: float
    r_squared: float
    coverage: Optional[float] = None
    sharpness: Optional[float] = None
    bias: float = 0.0
    n_samples: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mape": float(self.mape),
            "rmse": float(self.rmse),
            "mae": float(self.mae),
            "smape": float(self.smape),
            "mase": float(self.mase),
            "r_squared": float(self.r_squared),
            "coverage": float(self.coverage) if self.coverage is not None else None,
            "sharpness": float(self.sharpness) if self.sharpness is not None else None,
            "bias": float(self.bias),
            "n_samples": self.n_samples,
        }


def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Mean Absolute Percentage Error.

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        MAPE in percentage (0-100)
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    # Avoid division by zero
    mask = actual != 0
    if not mask.any():
        return np.inf

    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Root Mean Square Error.

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        RMSE in same units as input
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Mean Absolute Error.

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        MAE in same units as input
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    return float(np.mean(np.abs(actual - predicted)))


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Symmetric Mean Absolute Percentage Error.

    More robust to outliers than MAPE.

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        sMAPE in percentage (0-200)
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    denominator = (np.abs(actual) + np.abs(predicted)) / 2
    mask = denominator != 0

    if not mask.any():
        return np.inf

    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denominator[mask]) * 100)


def mase(
    actual: np.ndarray,
    predicted: np.ndarray,
    seasonal_period: int = 24,
) -> float:
    """
    Mean Absolute Scaled Error.

    Compares forecast error to naive seasonal forecast error.

    Args:
        actual: Actual values
        predicted: Predicted values
        seasonal_period: Period for seasonal naive (e.g., 24 for hourly)

    Returns:
        MASE (values < 1 beat naive seasonal)
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    # Forecast error
    forecast_error = np.abs(actual - predicted)

    # Naive seasonal error (in-sample)
    if len(actual) <= seasonal_period:
        return float(np.mean(forecast_error))

    naive_error = np.abs(actual[seasonal_period:] - actual[:-seasonal_period])

    if np.mean(naive_error) == 0:
        return np.inf

    return float(np.mean(forecast_error) / np.mean(naive_error))


def r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Coefficient of Determination (R²).

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        R² value (1 = perfect, 0 = no better than mean)
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)

    if ss_tot == 0:
        return 0.0

    return float(1 - (ss_res / ss_tot))


def bias(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Forecast Bias (Mean Error).

    Positive = over-prediction, Negative = under-prediction.

    Args:
        actual: Actual values
        predicted: Predicted values

    Returns:
        Mean error
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    return float(np.mean(predicted - actual))


def prediction_interval_coverage(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """
    Fraction of actuals within prediction interval.

    Args:
        actual: Actual values
        lower: Lower bound of prediction interval
        upper: Upper bound of prediction interval

    Returns:
        Coverage fraction (0-1)
    """
    actual = np.asarray(actual)
    lower = np.asarray(lower)
    upper = np.asarray(upper)

    in_interval = (actual >= lower) & (actual <= upper)
    return float(np.mean(in_interval))


def sharpness(lower: np.ndarray, upper: np.ndarray) -> float:
    """
    Average width of prediction interval (narrower is better).

    Args:
        lower: Lower bound of prediction interval
        upper: Upper bound of prediction interval

    Returns:
        Average interval width
    """
    lower = np.asarray(lower)
    upper = np.asarray(upper)

    return float(np.mean(upper - lower))


def winkler_score(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    alpha: float = 0.05,
) -> float:
    """
    Winkler Score for prediction intervals.

    Combines coverage and sharpness into a single score.
    Lower is better.

    Args:
        actual: Actual values
        lower: Lower bound
        upper: Upper bound
        alpha: Significance level (e.g., 0.05 for 95% PI)

    Returns:
        Winkler score
    """
    actual = np.asarray(actual)
    lower = np.asarray(lower)
    upper = np.asarray(upper)

    width = upper - lower
    below_lower = actual < lower
    above_upper = actual > upper

    score = width.copy()
    score[below_lower] += (2 / alpha) * (lower[below_lower] - actual[below_lower])
    score[above_upper] += (2 / alpha) * (actual[above_upper] - upper[above_upper])

    return float(np.mean(score))


def evaluate_forecast(
    actual: np.ndarray,
    predicted: np.ndarray,
    lower: Optional[np.ndarray] = None,
    upper: Optional[np.ndarray] = None,
    seasonal_period: int = 24,
) -> ForecastEvaluation:
    """
    Comprehensive forecast evaluation.

    Args:
        actual: Actual values
        predicted: Point forecasts
        lower: Optional lower bound of prediction interval
        upper: Optional upper bound of prediction interval
        seasonal_period: Period for MASE calculation

    Returns:
        ForecastEvaluation with all metrics
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    # Calculate base metrics
    eval_mape = mape(actual, predicted)
    eval_rmse = rmse(actual, predicted)
    eval_mae = mae(actual, predicted)
    eval_smape = smape(actual, predicted)
    eval_mase = mase(actual, predicted, seasonal_period)
    eval_r2 = r_squared(actual, predicted)
    eval_bias = bias(actual, predicted)

    # Calculate PI metrics if available
    eval_coverage = None
    eval_sharpness = None

    if lower is not None and upper is not None:
        lower = np.asarray(lower)
        upper = np.asarray(upper)
        eval_coverage = prediction_interval_coverage(actual, lower, upper)
        eval_sharpness = sharpness(lower, upper)

    return ForecastEvaluation(
        mape=eval_mape,
        rmse=eval_rmse,
        mae=eval_mae,
        smape=eval_smape,
        mase=eval_mase,
        r_squared=eval_r2,
        coverage=eval_coverage,
        sharpness=eval_sharpness,
        bias=eval_bias,
        n_samples=len(actual),
    )


def evaluate_by_horizon(
    actual: np.ndarray,
    predicted: np.ndarray,
    horizons: Optional[List[int]] = None,
) -> Dict[int, ForecastEvaluation]:
    """
    Evaluate forecast at different horizons.

    Args:
        actual: Actual values (shape: [n_forecasts, max_horizon])
        predicted: Predicted values (same shape)
        horizons: Specific horizons to evaluate

    Returns:
        Dictionary mapping horizon to evaluation
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    if actual.ndim == 1:
        actual = actual.reshape(1, -1)
        predicted = predicted.reshape(1, -1)

    max_horizon = actual.shape[1]

    if horizons is None:
        horizons = list(range(1, max_horizon + 1))

    results = {}

    for h in horizons:
        if h > max_horizon:
            continue

        h_actual = actual[:, h - 1]
        h_predicted = predicted[:, h - 1]

        results[h] = evaluate_forecast(h_actual, h_predicted)

    return results


def evaluate_by_group(
    actual: np.ndarray,
    predicted: np.ndarray,
    groups: np.ndarray,
) -> Dict[Any, ForecastEvaluation]:
    """
    Evaluate forecast by groups (e.g., cities).

    Args:
        actual: Actual values
        predicted: Predicted values
        groups: Group labels for each sample

    Returns:
        Dictionary mapping group to evaluation
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)
    groups = np.asarray(groups)

    unique_groups = np.unique(groups)
    results = {}

    for group in unique_groups:
        mask = groups == group
        results[group] = evaluate_forecast(actual[mask], predicted[mask])

    return results


@dataclass
class MAPETestResult:
    """
    Result of MAPE hypothesis test.

    Attributes:
        passed: Whether MAPE < threshold
        mean_mape: Mean MAPE across folds/samples
        std_mape: Standard deviation
        threshold: MAPE threshold tested
        t_statistic: T-test statistic
        p_value: P-value
        individual_mapes: MAPE values per fold
    """
    passed: bool
    mean_mape: float
    std_mape: float
    threshold: float
    t_statistic: float
    p_value: float
    individual_mapes: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "mean_mape": float(self.mean_mape),
            "std_mape": float(self.std_mape),
            "threshold": float(self.threshold),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
        }


def test_mape_threshold(
    mape_values: List[float],
    threshold: float = 5.0,
    alpha: float = 0.05,
) -> MAPETestResult:
    """
    Test if MAPE is significantly below threshold.

    Uses one-sample t-test.
    H0: mean MAPE >= threshold
    H1: mean MAPE < threshold

    Args:
        mape_values: MAPE values from cross-validation folds
        threshold: Target MAPE threshold
        alpha: Significance level

    Returns:
        MAPETestResult
    """
    mape_arr = np.array(mape_values)
    mean_mape = float(np.mean(mape_arr))
    std_mape = float(np.std(mape_arr, ddof=1)) if len(mape_arr) > 1 else 0.0

    if std_mape > 0:
        t_stat, p_value = scipy_stats.ttest_1samp(mape_arr, threshold)
        # One-tailed test (we want mean < threshold)
        p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2
    else:
        t_stat = float('-inf') if mean_mape < threshold else float('inf')
        p_value = 0.0 if mean_mape < threshold else 1.0

    passed = mean_mape < threshold and p_value < alpha

    return MAPETestResult(
        passed=passed,
        mean_mape=mean_mape,
        std_mape=std_mape,
        threshold=threshold,
        t_statistic=float(t_stat),
        p_value=float(p_value),
        individual_mapes=list(mape_values),
    )


@dataclass
class CoverageTestResult:
    """
    Result of prediction interval coverage test.

    Attributes:
        passed: Whether coverage is within acceptable range
        observed_coverage: Observed coverage rate
        expected_coverage: Expected coverage rate (e.g., 0.95)
        tolerance: Acceptable deviation from expected
        p_value: Binomial test p-value
        n_samples: Total samples
        n_covered: Samples within interval
    """
    passed: bool
    observed_coverage: float
    expected_coverage: float
    tolerance: float
    p_value: float
    n_samples: int
    n_covered: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "observed_coverage": float(self.observed_coverage),
            "expected_coverage": float(self.expected_coverage),
            "tolerance": float(self.tolerance),
            "p_value": float(self.p_value),
            "n_samples": self.n_samples,
            "n_covered": self.n_covered,
        }


def test_coverage(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    expected_coverage: float = 0.95,
    tolerance: float = 0.03,
) -> CoverageTestResult:
    """
    Test if prediction interval coverage is within expected range.

    Uses exact binomial test.
    H0: Coverage significantly different from expected
    H1: Coverage within expected ± tolerance

    Args:
        actual: Actual values
        lower: Lower bounds
        upper: Upper bounds
        expected_coverage: Expected coverage (e.g., 0.95 for 95% PI)
        tolerance: Acceptable deviation (e.g., 0.03 for ±3%)

    Returns:
        CoverageTestResult
    """
    actual = np.asarray(actual)
    lower = np.asarray(lower)
    upper = np.asarray(upper)

    n_samples = len(actual)
    in_interval = (actual >= lower) & (actual <= upper)
    n_covered = int(np.sum(in_interval))

    observed_coverage = n_covered / n_samples

    # Two-tailed binomial test
    p_value = scipy_stats.binom_test(
        n_covered, n_samples, expected_coverage, alternative='two-sided'
    )

    # Check if within tolerance
    passed = abs(observed_coverage - expected_coverage) <= tolerance

    return CoverageTestResult(
        passed=passed,
        observed_coverage=float(observed_coverage),
        expected_coverage=expected_coverage,
        tolerance=tolerance,
        p_value=float(p_value),
        n_samples=n_samples,
        n_covered=n_covered,
    )


# Aliases for compatibility with cross_validator
def coverage_probability(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """Alias for prediction_interval_coverage."""
    return prediction_interval_coverage(actual, lower, upper)


def interval_sharpness(lower: np.ndarray, upper: np.ndarray) -> float:
    """Alias for sharpness."""
    return sharpness(lower, upper)


def test_coverage_target(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    expected_coverage: float = 0.95,
    tolerance: float = 0.03,
) -> CoverageTestResult:
    """Alias for test_coverage."""
    return test_coverage(actual, lower, upper, expected_coverage, tolerance)
