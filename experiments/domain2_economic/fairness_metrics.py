"""
Fairness Metrics for SHAKTI-CHAIN Economic Performance (Domain 2).

Implements welfare distribution fairness measures:
- Gini coefficient
- Theil index (entropy-based inequality)
- Hoover index
- Lorenz curve computation
- Bootstrap confidence intervals
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np


@dataclass
class FairnessMetrics:
    """Collection of fairness metrics."""
    gini_coefficient: float
    theil_index: float
    hoover_index: float
    atkinson_index: float
    palma_ratio: float
    p90_p10_ratio: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "gini_coefficient": float(self.gini_coefficient),
            "theil_index": float(self.theil_index),
            "hoover_index": float(self.hoover_index),
            "atkinson_index": float(self.atkinson_index),
            "palma_ratio": float(self.palma_ratio),
            "p90_p10_ratio": float(self.p90_p10_ratio),
        }


def calculate_gini_coefficient(welfare_distribution: np.ndarray) -> float:
    """
    Calculate Gini coefficient for welfare distribution.

    Gini = (SUM_i SUM_j |w_i - w_j|) / (2 * n^2 * mu_w)

    Alternative formula using sorted values:
    Gini = (2 * SUM_i (i * w_i)) / (n * SUM_i w_i) - (n + 1) / n

    Args:
        welfare_distribution: Array of welfare values for each participant

    Returns:
        Gini coefficient in [0, 1] where 0 = perfect equality, 1 = perfect inequality
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    # Handle edge cases
    if len(welfare) == 0:
        return 0.0

    if len(welfare) == 1:
        return 0.0

    # Remove negative values (can't have negative welfare in standard Gini)
    # Option: shift distribution or use absolute values
    # Here we handle negative by shifting to non-negative
    min_welfare = np.min(welfare)
    if min_welfare < 0:
        welfare = welfare - min_welfare  # Shift to make all non-negative

    # Handle all-zero case
    total = np.sum(welfare)
    if total == 0:
        return 0.0

    n = len(welfare)

    # Sort values
    sorted_welfare = np.sort(welfare)

    # Calculate using the formula:
    # G = (2 * SUM_i (i * x_i)) / (n * SUM x_i) - (n + 1) / n
    # where i is 1-indexed rank
    index = np.arange(1, n + 1)
    gini = (2.0 * np.sum(index * sorted_welfare)) / (n * total) - (n + 1) / n

    return float(np.clip(gini, 0.0, 1.0))


def calculate_gini_fast(welfare_distribution: np.ndarray) -> float:
    """
    Fast Gini coefficient calculation using mean absolute difference.

    Gini = (SUM_i SUM_j |w_i - w_j|) / (2 * n^2 * mean)

    This is O(n log n) instead of O(n^2).

    Args:
        welfare_distribution: Array of welfare values

    Returns:
        Gini coefficient in [0, 1]
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) <= 1:
        return 0.0

    # Shift if necessary
    min_val = np.min(welfare)
    if min_val < 0:
        welfare = welfare - min_val

    if np.sum(welfare) == 0:
        return 0.0

    n = len(welfare)
    sorted_welfare = np.sort(welfare)
    cumulative = np.cumsum(sorted_welfare)

    # Gini = 1 - (2 / n) * SUM_i ((n - i + 0.5) * x_i / SUM x_i)
    # Alternative: Using area under Lorenz curve
    # G = 1 - 2 * B where B is area under Lorenz curve
    total = cumulative[-1]
    B = np.sum(cumulative) / (n * total) - 0.5 / n
    gini = 1 - 2 * B

    return float(np.clip(gini, 0.0, 1.0))


def calculate_theil_index(welfare_distribution: np.ndarray) -> float:
    """
    Calculate Theil index (generalized entropy measure).

    Theil T = (1/n) * SUM_i (w_i / mu) * ln(w_i / mu)

    Where mu is the mean welfare.

    The Theil index is more sensitive to changes at the top of the distribution.

    Args:
        welfare_distribution: Array of welfare values (must be positive)

    Returns:
        Theil index (0 = perfect equality, higher = more inequality)
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) == 0:
        return 0.0

    if len(welfare) == 1:
        return 0.0

    # Theil index requires strictly positive values
    # Filter out zeros and negatives, or shift
    welfare = welfare[welfare > 0]

    if len(welfare) <= 1:
        return 0.0

    n = len(welfare)
    mu = np.mean(welfare)

    if mu <= 0:
        return 0.0

    # Normalized values
    normalized = welfare / mu

    # Theil T index
    theil_t = np.mean(normalized * np.log(normalized))

    return float(max(0.0, theil_t))


def calculate_theil_l(welfare_distribution: np.ndarray) -> float:
    """
    Calculate Theil L index (mean log deviation).

    Theil L = (1/n) * SUM_i ln(mu / w_i)

    Theil L is more sensitive to changes at the bottom of the distribution.

    Args:
        welfare_distribution: Array of positive welfare values

    Returns:
        Theil L index (0 = perfect equality)
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) <= 1:
        return 0.0

    # Filter positive values
    welfare = welfare[welfare > 0]

    if len(welfare) <= 1:
        return 0.0

    mu = np.mean(welfare)
    if mu <= 0:
        return 0.0

    theil_l = np.mean(np.log(mu / welfare))

    return float(max(0.0, theil_l))


def bootstrap_gini_ci(
    welfare_distribution: np.ndarray,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    random_state: Optional[int] = None,
) -> Tuple[float, float]:
    """
    Calculate bootstrap confidence interval for Gini coefficient.

    Uses percentile method for confidence interval estimation.

    Args:
        welfare_distribution: Array of welfare values
        n_bootstrap: Number of bootstrap iterations (default 10000)
        confidence: Confidence level (default 0.95 for 95% CI)
        random_state: Random seed for reproducibility

    Returns:
        Tuple of (lower_bound, upper_bound) for confidence interval
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)
    n = len(welfare)

    if n == 0:
        return (0.0, 0.0)

    if n == 1:
        return (0.0, 0.0)

    if random_state is not None:
        np.random.seed(random_state)

    bootstrap_ginis = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        # Resample with replacement
        resample = np.random.choice(welfare, size=n, replace=True)
        bootstrap_ginis[i] = calculate_gini_coefficient(resample)

    # Percentile method
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_ginis, 100 * alpha / 2)
    upper = np.percentile(bootstrap_ginis, 100 * (1 - alpha / 2))

    return (float(lower), float(upper))


def bootstrap_gini_ci_bca(
    welfare_distribution: np.ndarray,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    random_state: Optional[int] = None,
) -> Tuple[float, float]:
    """
    Calculate bias-corrected and accelerated (BCa) bootstrap CI for Gini.

    BCa corrects for bias and skewness in the bootstrap distribution.

    Args:
        welfare_distribution: Array of welfare values
        n_bootstrap: Number of bootstrap iterations
        confidence: Confidence level
        random_state: Random seed

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    from scipy import stats

    welfare = np.array(welfare_distribution, dtype=np.float64)
    n = len(welfare)

    if n <= 1:
        return (0.0, 0.0)

    if random_state is not None:
        np.random.seed(random_state)

    # Original statistic
    theta_hat = calculate_gini_coefficient(welfare)

    # Bootstrap distribution
    bootstrap_ginis = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        resample = np.random.choice(welfare, size=n, replace=True)
        bootstrap_ginis[i] = calculate_gini_coefficient(resample)

    # Bias correction factor (z0)
    prop_less = np.mean(bootstrap_ginis < theta_hat)
    if prop_less == 0:
        prop_less = 1 / (2 * n_bootstrap)
    elif prop_less == 1:
        prop_less = 1 - 1 / (2 * n_bootstrap)
    z0 = stats.norm.ppf(prop_less)

    # Acceleration factor (a) using jackknife
    jackknife_values = np.empty(n)
    for i in range(n):
        jackknife_sample = np.delete(welfare, i)
        jackknife_values[i] = calculate_gini_coefficient(jackknife_sample)

    jack_mean = np.mean(jackknife_values)
    numerator = np.sum((jack_mean - jackknife_values) ** 3)
    denominator = 6 * (np.sum((jack_mean - jackknife_values) ** 2) ** 1.5)

    if abs(denominator) > 1e-10:
        a = numerator / denominator
    else:
        a = 0.0

    # BCa percentiles
    alpha = 1 - confidence
    z_alpha = stats.norm.ppf(alpha / 2)
    z_1_alpha = stats.norm.ppf(1 - alpha / 2)

    # Adjusted percentiles
    def adjust_alpha(z):
        numerator = z0 + z
        denominator = 1 - a * (z0 + z)
        if abs(denominator) < 1e-10:
            return stats.norm.cdf(z0 + z)
        return stats.norm.cdf(z0 + numerator / denominator)

    alpha_lower = adjust_alpha(z_alpha)
    alpha_upper = adjust_alpha(z_1_alpha)

    # Clip to valid percentile range
    alpha_lower = np.clip(alpha_lower, 0.001, 0.999)
    alpha_upper = np.clip(alpha_upper, 0.001, 0.999)

    lower = np.percentile(bootstrap_ginis, 100 * alpha_lower)
    upper = np.percentile(bootstrap_ginis, 100 * alpha_upper)

    return (float(lower), float(upper))


def calculate_lorenz_curve(
    welfare_distribution: np.ndarray,
    n_points: int = 100,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate Lorenz curve for welfare distribution.

    The Lorenz curve shows the cumulative share of welfare held by
    the bottom x% of the population.

    Args:
        welfare_distribution: Array of welfare values
        n_points: Number of points on the curve

    Returns:
        Tuple of (population_share, welfare_share) arrays
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) == 0:
        return (np.array([0.0, 1.0]), np.array([0.0, 1.0]))

    # Shift if negative
    min_val = np.min(welfare)
    if min_val < 0:
        welfare = welfare - min_val

    # Sort
    sorted_welfare = np.sort(welfare)
    n = len(sorted_welfare)
    total = np.sum(sorted_welfare)

    if total == 0:
        return (np.linspace(0, 1, n_points), np.linspace(0, 1, n_points))

    # Cumulative sums
    cumulative = np.cumsum(sorted_welfare)

    # Population share (x-axis)
    pop_share = np.arange(1, n + 1) / n

    # Welfare share (y-axis)
    welfare_share = cumulative / total

    # Add origin point
    pop_share = np.concatenate([[0], pop_share])
    welfare_share = np.concatenate([[0], welfare_share])

    # Interpolate to n_points if needed
    if n_points != len(pop_share):
        from numpy import interp
        x_interp = np.linspace(0, 1, n_points)
        y_interp = interp(x_interp, pop_share, welfare_share)
        return (x_interp, y_interp)

    return (pop_share, welfare_share)


def calculate_hoover_index(welfare_distribution: np.ndarray) -> float:
    """
    Calculate Hoover index (Robin Hood index).

    Represents the maximum proportion of total welfare that would need
    to be redistributed to achieve perfect equality.

    Hoover = (1/2) * SUM_i |w_i / total - 1/n|

    Args:
        welfare_distribution: Array of welfare values

    Returns:
        Hoover index in [0, 1]
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) == 0:
        return 0.0

    if len(welfare) == 1:
        return 0.0

    # Shift if negative
    min_val = np.min(welfare)
    if min_val < 0:
        welfare = welfare - min_val

    total = np.sum(welfare)
    if total == 0:
        return 0.0

    n = len(welfare)

    # Share each person has vs. equal share
    actual_share = welfare / total
    equal_share = 1.0 / n

    hoover = 0.5 * np.sum(np.abs(actual_share - equal_share))

    return float(np.clip(hoover, 0.0, 1.0))


def calculate_atkinson_index(
    welfare_distribution: np.ndarray,
    epsilon: float = 0.5,
) -> float:
    """
    Calculate Atkinson index with inequality aversion parameter.

    The Atkinson index represents the proportion of total welfare that
    could be sacrificed while maintaining the same level of social welfare,
    if welfare were equally distributed.

    Args:
        welfare_distribution: Array of positive welfare values
        epsilon: Inequality aversion parameter (0 = not averse, higher = more averse)

    Returns:
        Atkinson index in [0, 1]
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) <= 1:
        return 0.0

    # Filter positive values
    welfare = welfare[welfare > 0]

    if len(welfare) <= 1:
        return 0.0

    n = len(welfare)
    mu = np.mean(welfare)

    if epsilon == 1.0:
        # Special case: use geometric mean
        geom_mean = np.exp(np.mean(np.log(welfare)))
        atkinson = 1 - geom_mean / mu
    else:
        # General case
        power_mean = np.mean(welfare ** (1 - epsilon)) ** (1 / (1 - epsilon))
        atkinson = 1 - power_mean / mu

    return float(np.clip(atkinson, 0.0, 1.0))


def calculate_palma_ratio(welfare_distribution: np.ndarray) -> float:
    """
    Calculate Palma ratio (top 10% share / bottom 40% share).

    A measure of inequality focused on the tails of the distribution.

    Args:
        welfare_distribution: Array of welfare values

    Returns:
        Palma ratio (1.0 = equal share, higher = more inequality)
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) < 10:
        return np.nan  # Need enough data for percentiles

    # Shift if negative
    min_val = np.min(welfare)
    if min_val < 0:
        welfare = welfare - min_val

    sorted_welfare = np.sort(welfare)
    n = len(sorted_welfare)

    # Bottom 40%
    bottom_40_idx = int(0.4 * n)
    bottom_40_sum = np.sum(sorted_welfare[:bottom_40_idx])

    # Top 10%
    top_10_idx = int(0.9 * n)
    top_10_sum = np.sum(sorted_welfare[top_10_idx:])

    if bottom_40_sum == 0:
        return np.inf

    return float(top_10_sum / bottom_40_sum)


def calculate_p90_p10_ratio(welfare_distribution: np.ndarray) -> float:
    """
    Calculate P90/P10 ratio.

    Ratio of the 90th percentile to the 10th percentile.

    Args:
        welfare_distribution: Array of welfare values

    Returns:
        P90/P10 ratio
    """
    welfare = np.array(welfare_distribution, dtype=np.float64)

    if len(welfare) < 10:
        return np.nan

    p10 = np.percentile(welfare, 10)
    p90 = np.percentile(welfare, 90)

    if p10 <= 0:
        return np.inf

    return float(p90 / p10)


def calculate_all_fairness_metrics(
    welfare_distribution: np.ndarray,
    atkinson_epsilon: float = 0.5,
) -> FairnessMetrics:
    """
    Calculate all fairness metrics for a welfare distribution.

    Args:
        welfare_distribution: Array of welfare values
        atkinson_epsilon: Inequality aversion for Atkinson index

    Returns:
        FairnessMetrics object with all measures
    """
    return FairnessMetrics(
        gini_coefficient=calculate_gini_coefficient(welfare_distribution),
        theil_index=calculate_theil_index(welfare_distribution),
        hoover_index=calculate_hoover_index(welfare_distribution),
        atkinson_index=calculate_atkinson_index(welfare_distribution, atkinson_epsilon),
        palma_ratio=calculate_palma_ratio(welfare_distribution),
        p90_p10_ratio=calculate_p90_p10_ratio(welfare_distribution),
    )


def is_fair(
    welfare_distribution: np.ndarray,
    gini_threshold: float = 0.4,
    theil_threshold: float = 0.5,
) -> bool:
    """
    Check if welfare distribution meets fairness criteria.

    Args:
        welfare_distribution: Array of welfare values
        gini_threshold: Maximum acceptable Gini coefficient
        theil_threshold: Maximum acceptable Theil index

    Returns:
        True if distribution is considered fair
    """
    gini = calculate_gini_coefficient(welfare_distribution)
    theil = calculate_theil_index(welfare_distribution)

    return gini < gini_threshold and theil < theil_threshold
