"""
Latency Profiler for SHAKTI-CHAIN System Performance Testing (Domain 3).

Analyzes latency distributions with detailed percentile analysis
and statistical characterization.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats


@dataclass
class LatencyMeasurement:
    """
    Single latency measurement.

    Attributes:
        timestamp: When measurement was taken
        latency_ms: Latency in milliseconds
        operation_type: Type of operation measured
        metadata: Additional context
    """
    timestamp: float
    latency_ms: float
    operation_type: str = "transaction"
    metadata: Dict = field(default_factory=dict)


@dataclass
class LatencyPercentiles:
    """
    Latency percentile breakdown.

    Attributes:
        p50: 50th percentile (median)
        p75: 75th percentile
        p90: 90th percentile
        p95: 95th percentile
        p99: 99th percentile
        p999: 99.9th percentile
        max: Maximum latency
        min: Minimum latency
    """
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    p999: float
    max: float
    min: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "p50": float(self.p50),
            "p75": float(self.p75),
            "p90": float(self.p90),
            "p95": float(self.p95),
            "p99": float(self.p99),
            "p999": float(self.p999),
            "max": float(self.max),
            "min": float(self.min),
        }


@dataclass
class LatencyStatistics:
    """
    Complete latency statistics.

    Attributes:
        mean: Mean latency
        std: Standard deviation
        median: Median latency
        percentiles: Percentile breakdown
        sample_size: Number of samples
        cv: Coefficient of variation
        skewness: Distribution skewness
        kurtosis: Distribution kurtosis
        is_normal: Whether distribution passes normality test
    """
    mean: float
    std: float
    median: float
    percentiles: LatencyPercentiles
    sample_size: int
    cv: float
    skewness: float
    kurtosis: float
    is_normal: bool

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean": float(self.mean),
            "std": float(self.std),
            "median": float(self.median),
            "percentiles": self.percentiles.to_dict(),
            "sample_size": self.sample_size,
            "cv": float(self.cv),
            "skewness": float(self.skewness),
            "kurtosis": float(self.kurtosis),
            "is_normal": self.is_normal,
        }


@dataclass
class LatencyDistributionFit:
    """
    Results of fitting distributions to latency data.

    Attributes:
        best_fit: Name of best-fitting distribution
        lognormal_params: Log-normal fit parameters (mu, sigma)
        exponential_params: Exponential fit parameters (lambda)
        gamma_params: Gamma fit parameters (shape, scale)
        ks_test_results: Kolmogorov-Smirnov test p-values for each fit
    """
    best_fit: str
    lognormal_params: Tuple[float, float]
    exponential_params: Tuple[float]
    gamma_params: Tuple[float, float]
    ks_test_results: Dict[str, float]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "best_fit": self.best_fit,
            "lognormal_params": list(self.lognormal_params),
            "exponential_params": list(self.exponential_params),
            "gamma_params": list(self.gamma_params),
            "ks_test_results": self.ks_test_results,
        }


class LatencyProfiler:
    """
    Profile and analyze latency distributions.

    Provides detailed statistical analysis of response times,
    including distribution fitting and percentile tracking.
    """

    def __init__(
        self,
        max_samples: int = 100000,
    ):
        """
        Initialize latency profiler.

        Args:
            max_samples: Maximum number of samples to retain
        """
        self.max_samples = max_samples
        self.measurements: List[LatencyMeasurement] = []
        self._latencies: List[float] = []
        self._by_operation: Dict[str, List[float]] = {}

    def record(
        self,
        latency_ms: float,
        operation_type: str = "transaction",
        metadata: Optional[Dict] = None,
    ):
        """
        Record a latency measurement.

        Args:
            latency_ms: Latency in milliseconds
            operation_type: Type of operation
            metadata: Additional metadata
        """
        measurement = LatencyMeasurement(
            timestamp=time.time(),
            latency_ms=latency_ms,
            operation_type=operation_type,
            metadata=metadata or {},
        )

        self.measurements.append(measurement)
        self._latencies.append(latency_ms)

        # Track by operation type
        if operation_type not in self._by_operation:
            self._by_operation[operation_type] = []
        self._by_operation[operation_type].append(latency_ms)

        # Trim if exceeding max
        if len(self.measurements) > self.max_samples:
            self.measurements = self.measurements[-self.max_samples:]
            self._latencies = self._latencies[-self.max_samples:]

    def record_batch(
        self,
        latencies: List[float],
        operation_type: str = "transaction",
    ):
        """
        Record a batch of latency measurements.

        Args:
            latencies: List of latency values in milliseconds
            operation_type: Type of operation
        """
        for lat in latencies:
            self.record(lat, operation_type)

    def get_percentiles(
        self,
        operation_type: Optional[str] = None,
    ) -> LatencyPercentiles:
        """
        Calculate latency percentiles.

        Args:
            operation_type: Optional filter by operation type

        Returns:
            LatencyPercentiles object
        """
        if operation_type:
            latencies = self._by_operation.get(operation_type, [])
        else:
            latencies = self._latencies

        if not latencies:
            return LatencyPercentiles(
                p50=0, p75=0, p90=0, p95=0, p99=0, p999=0, max=0, min=0
            )

        arr = np.array(latencies)

        return LatencyPercentiles(
            p50=float(np.percentile(arr, 50)),
            p75=float(np.percentile(arr, 75)),
            p90=float(np.percentile(arr, 90)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            p999=float(np.percentile(arr, 99.9)),
            max=float(np.max(arr)),
            min=float(np.min(arr)),
        )

    def get_statistics(
        self,
        operation_type: Optional[str] = None,
    ) -> LatencyStatistics:
        """
        Calculate comprehensive latency statistics.

        Args:
            operation_type: Optional filter by operation type

        Returns:
            LatencyStatistics object
        """
        if operation_type:
            latencies = self._by_operation.get(operation_type, [])
        else:
            latencies = self._latencies

        if not latencies:
            return LatencyStatistics(
                mean=0, std=0, median=0,
                percentiles=LatencyPercentiles(0, 0, 0, 0, 0, 0, 0, 0),
                sample_size=0, cv=0, skewness=0, kurtosis=0, is_normal=False,
            )

        arr = np.array(latencies)
        n = len(arr)

        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0
        median = float(np.median(arr))

        # Coefficient of variation
        cv = std / mean if mean > 0 else 0

        # Skewness and kurtosis
        if n > 2:
            skewness = float(scipy_stats.skew(arr))
            kurtosis = float(scipy_stats.kurtosis(arr))
        else:
            skewness = 0
            kurtosis = 0

        # Normality test
        is_normal = False
        if n >= 8:
            try:
                _, p_value = scipy_stats.shapiro(arr[:min(5000, n)])
                is_normal = p_value > 0.05
            except Exception:
                pass

        percentiles = self.get_percentiles(operation_type)

        return LatencyStatistics(
            mean=mean,
            std=std,
            median=median,
            percentiles=percentiles,
            sample_size=n,
            cv=cv,
            skewness=skewness,
            kurtosis=kurtosis,
            is_normal=is_normal,
        )

    def fit_distributions(
        self,
        operation_type: Optional[str] = None,
    ) -> LatencyDistributionFit:
        """
        Fit common distributions to latency data.

        Response times typically follow log-normal, exponential,
        or gamma distributions.

        Args:
            operation_type: Optional filter by operation type

        Returns:
            LatencyDistributionFit with fitted parameters
        """
        if operation_type:
            latencies = self._by_operation.get(operation_type, [])
        else:
            latencies = self._latencies

        if len(latencies) < 10:
            return LatencyDistributionFit(
                best_fit="insufficient_data",
                lognormal_params=(0, 1),
                exponential_params=(1,),
                gamma_params=(1, 1),
                ks_test_results={},
            )

        arr = np.array(latencies)
        arr = arr[arr > 0]  # Remove non-positive for log-normal fit

        ks_results = {}

        # Fit log-normal
        try:
            ln_shape, ln_loc, ln_scale = scipy_stats.lognorm.fit(arr, floc=0)
            ln_mu = np.log(ln_scale)
            ln_sigma = ln_shape
            _, ln_p = scipy_stats.kstest(arr, 'lognorm', args=(ln_shape, ln_loc, ln_scale))
            ks_results['lognormal'] = float(ln_p)
            lognormal_params = (ln_mu, ln_sigma)
        except Exception:
            lognormal_params = (0, 1)
            ks_results['lognormal'] = 0

        # Fit exponential
        try:
            exp_loc, exp_scale = scipy_stats.expon.fit(arr)
            exp_lambda = 1 / exp_scale
            _, exp_p = scipy_stats.kstest(arr, 'expon', args=(exp_loc, exp_scale))
            ks_results['exponential'] = float(exp_p)
            exponential_params = (exp_lambda,)
        except Exception:
            exponential_params = (1,)
            ks_results['exponential'] = 0

        # Fit gamma
        try:
            gamma_a, gamma_loc, gamma_scale = scipy_stats.gamma.fit(arr, floc=0)
            _, gamma_p = scipy_stats.kstest(arr, 'gamma', args=(gamma_a, gamma_loc, gamma_scale))
            ks_results['gamma'] = float(gamma_p)
            gamma_params = (gamma_a, gamma_scale)
        except Exception:
            gamma_params = (1, 1)
            ks_results['gamma'] = 0

        # Determine best fit
        best_fit = max(ks_results.items(), key=lambda x: x[1])[0] if ks_results else "unknown"

        return LatencyDistributionFit(
            best_fit=best_fit,
            lognormal_params=lognormal_params,
            exponential_params=exponential_params,
            gamma_params=gamma_params,
            ks_test_results=ks_results,
        )

    def get_histogram(
        self,
        n_bins: int = 50,
        operation_type: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get histogram of latency distribution.

        Args:
            n_bins: Number of histogram bins
            operation_type: Optional filter by operation type

        Returns:
            Tuple of (bin_edges, counts)
        """
        if operation_type:
            latencies = self._by_operation.get(operation_type, [])
        else:
            latencies = self._latencies

        if not latencies:
            return np.array([]), np.array([])

        arr = np.array(latencies)
        counts, bin_edges = np.histogram(arr, bins=n_bins)

        return bin_edges, counts

    def get_cdf(
        self,
        operation_type: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get cumulative distribution function.

        Args:
            operation_type: Optional filter by operation type

        Returns:
            Tuple of (latency_values, cumulative_probabilities)
        """
        if operation_type:
            latencies = self._by_operation.get(operation_type, [])
        else:
            latencies = self._latencies

        if not latencies:
            return np.array([]), np.array([])

        arr = np.sort(np.array(latencies))
        n = len(arr)
        cdf = np.arange(1, n + 1) / n

        return arr, cdf

    def get_sla_compliance(
        self,
        threshold_ms: float,
        operation_type: Optional[str] = None,
    ) -> float:
        """
        Calculate SLA compliance rate.

        Args:
            threshold_ms: SLA threshold in milliseconds
            operation_type: Optional filter by operation type

        Returns:
            Fraction of requests within SLA
        """
        if operation_type:
            latencies = self._by_operation.get(operation_type, [])
        else:
            latencies = self._latencies

        if not latencies:
            return 1.0

        arr = np.array(latencies)
        return float(np.mean(arr <= threshold_ms))

    def get_time_series(
        self,
        window_seconds: float = 1.0,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get latency as time series with windowed statistics.

        Args:
            window_seconds: Size of aggregation window

        Returns:
            Tuple of (timestamps, mean_latencies, p95_latencies)
        """
        if not self.measurements:
            return np.array([]), np.array([]), np.array([])

        # Group measurements by window
        measurements_sorted = sorted(self.measurements, key=lambda m: m.timestamp)
        if not measurements_sorted:
            return np.array([]), np.array([]), np.array([])

        start_time = measurements_sorted[0].timestamp
        windows: Dict[int, List[float]] = {}

        for m in measurements_sorted:
            window_idx = int((m.timestamp - start_time) / window_seconds)
            if window_idx not in windows:
                windows[window_idx] = []
            windows[window_idx].append(m.latency_ms)

        # Calculate per-window stats
        timestamps = []
        means = []
        p95s = []

        for idx in sorted(windows.keys()):
            latencies = windows[idx]
            if latencies:
                timestamps.append(start_time + idx * window_seconds)
                means.append(np.mean(latencies))
                p95s.append(np.percentile(latencies, 95))

        return np.array(timestamps), np.array(means), np.array(p95s)

    def clear(self):
        """Clear all recorded measurements."""
        self.measurements = []
        self._latencies = []
        self._by_operation = {}


def bootstrap_percentile_ci(
    latencies: np.ndarray,
    percentile: float,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    seed: Optional[int] = None,
) -> Tuple[float, float, float]:
    """
    Calculate bootstrap confidence interval for a latency percentile.

    Args:
        latencies: Array of latency values
        percentile: Percentile to estimate (e.g., 95 for P95)
        n_bootstrap: Number of bootstrap iterations
        confidence: Confidence level
        seed: Random seed

    Returns:
        Tuple of (point_estimate, ci_lower, ci_upper)
    """
    if len(latencies) == 0:
        return (0, 0, 0)

    rng = np.random.default_rng(seed)
    n = len(latencies)

    # Point estimate
    point_estimate = float(np.percentile(latencies, percentile))

    # Bootstrap
    bootstrap_estimates = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        resample = rng.choice(latencies, size=n, replace=True)
        bootstrap_estimates[i] = np.percentile(resample, percentile)

    # Confidence interval
    alpha = 1 - confidence
    ci_lower = float(np.percentile(bootstrap_estimates, 100 * alpha / 2))
    ci_upper = float(np.percentile(bootstrap_estimates, 100 * (1 - alpha / 2)))

    return (point_estimate, ci_lower, ci_upper)


def simulate_latency_samples(
    n_samples: int,
    base_latency_ms: float = 10.0,
    p95_target_ms: float = 50.0,
    p99_target_ms: float = 100.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Simulate realistic latency samples using log-normal distribution.

    Args:
        n_samples: Number of samples to generate
        base_latency_ms: Median (base) latency
        p95_target_ms: Target 95th percentile
        p99_target_ms: Target 99th percentile
        seed: Random seed

    Returns:
        Array of latency values in milliseconds
    """
    rng = np.random.default_rng(seed)

    # Log-normal parameters
    mu = np.log(base_latency_ms)

    # Estimate sigma from P95 target
    # P95 of lognormal = exp(mu + 1.645*sigma)
    sigma = (np.log(p95_target_ms) - mu) / 1.645
    sigma = max(sigma, 0.1)

    # Generate base latencies
    latencies = rng.lognormal(mu, sigma, n_samples)

    # Add occasional outliers (simulating tail latencies)
    outlier_mask = rng.random(n_samples) < 0.01
    outlier_factor = rng.uniform(2, 5, n_samples)
    latencies[outlier_mask] *= outlier_factor[outlier_mask]

    return latencies
