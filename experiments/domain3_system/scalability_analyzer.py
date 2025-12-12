"""
Scalability Analyzer for SHAKTI-CHAIN System Performance Testing (Domain 3).

Analyzes system scaling behavior by fitting complexity models
and determining asymptotic complexity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats
from scipy.optimize import curve_fit, OptimizeWarning
import warnings


@dataclass
class ModelFitResult:
    """
    Result of fitting a scaling model.

    Attributes:
        model_name: Name of the model (e.g., "O(n)", "O(n log n)")
        parameters: Fitted parameters
        r_squared: R-squared (coefficient of determination)
        aic: Akaike Information Criterion
        bic: Bayesian Information Criterion
        residual_std: Standard deviation of residuals
        prediction_function: Function for predictions
    """
    model_name: str
    parameters: Dict[str, float]
    r_squared: float
    aic: float
    bic: float
    residual_std: float
    prediction_function: Optional[Callable] = None

    def to_dict(self) -> dict:
        """Convert to dictionary (without prediction function)."""
        return {
            "model_name": self.model_name,
            "parameters": self.parameters,
            "r_squared": float(self.r_squared),
            "aic": float(self.aic),
            "bic": float(self.bic),
            "residual_std": float(self.residual_std),
        }

    def predict(self, n: np.ndarray) -> np.ndarray:
        """Make predictions using fitted model."""
        if self.prediction_function is None:
            raise ValueError("Prediction function not available")
        return self.prediction_function(n)


@dataclass
class ScalabilityAnalysisResult:
    """
    Complete scalability analysis result.

    Attributes:
        measurements: Original (n, time) measurements
        model_fits: Fit results for each model
        best_model: Name of best-fitting model
        complexity_class: Determined complexity class
        is_acceptable: Whether complexity is O(n log n) or better
        f_test_results: F-test results for model comparisons
    """
    measurements: List[Tuple[int, float]]
    model_fits: Dict[str, ModelFitResult]
    best_model: str
    complexity_class: str
    is_acceptable: bool
    f_test_results: Dict[str, Dict]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "measurements": self.measurements,
            "model_fits": {k: v.to_dict() for k, v in self.model_fits.items()},
            "best_model": self.best_model,
            "complexity_class": self.complexity_class,
            "is_acceptable": self.is_acceptable,
            "f_test_results": self.f_test_results,
        }


# Model functions
def linear_model(n: np.ndarray, a: float, b: float) -> np.ndarray:
    """O(n) linear model: T(n) = a*n + b"""
    return a * n + b


def nlogn_model(n: np.ndarray, a: float, b: float) -> np.ndarray:
    """O(n log n) model: T(n) = a*n*log(n) + b"""
    return a * n * np.log(np.maximum(n, 1)) + b


def quadratic_model(n: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    """O(n^2) quadratic model: T(n) = a*n^2 + b*n + c"""
    return a * n**2 + b * n + c


def logarithmic_model(n: np.ndarray, a: float, b: float) -> np.ndarray:
    """O(log n) model: T(n) = a*log(n) + b"""
    return a * np.log(np.maximum(n, 1)) + b


def constant_model(n: np.ndarray, a: float) -> np.ndarray:
    """O(1) constant model: T(n) = a"""
    return np.full_like(n, a, dtype=float)


def sqrt_model(n: np.ndarray, a: float, b: float) -> np.ndarray:
    """O(sqrt(n)) model: T(n) = a*sqrt(n) + b"""
    return a * np.sqrt(n) + b


class ScalabilityAnalyzer:
    """
    Analyze system scaling behavior.

    Fits multiple complexity models to performance measurements
    and determines the best-fitting asymptotic complexity.
    """

    # Available models with their properties
    MODELS = {
        "O(1)": {
            "function": constant_model,
            "n_params": 1,
            "complexity_order": 0,
        },
        "O(log n)": {
            "function": logarithmic_model,
            "n_params": 2,
            "complexity_order": 1,
        },
        "O(sqrt(n))": {
            "function": sqrt_model,
            "n_params": 2,
            "complexity_order": 2,
        },
        "O(n)": {
            "function": linear_model,
            "n_params": 2,
            "complexity_order": 3,
        },
        "O(n log n)": {
            "function": nlogn_model,
            "n_params": 2,
            "complexity_order": 4,
        },
        "O(n^2)": {
            "function": quadratic_model,
            "n_params": 3,
            "complexity_order": 5,
        },
    }

    def __init__(self):
        """Initialize scalability analyzer."""
        self.measurements: List[Tuple[int, float]] = []

    def add_measurement(self, n_agents: int, time_ms: float):
        """
        Add a scaling measurement.

        Args:
            n_agents: Number of agents/items processed
            time_ms: Time taken in milliseconds
        """
        self.measurements.append((n_agents, time_ms))

    def add_measurements(self, measurements: List[Tuple[int, float]]):
        """
        Add multiple measurements.

        Args:
            measurements: List of (n_agents, time_ms) tuples
        """
        self.measurements.extend(measurements)

    def clear(self):
        """Clear all measurements."""
        self.measurements = []

    def fit_models(self) -> Dict[str, ModelFitResult]:
        """
        Fit all scaling models to the measurements.

        Returns:
            Dictionary mapping model name to ModelFitResult
        """
        if len(self.measurements) < 3:
            raise ValueError("Need at least 3 measurements for model fitting")

        # Convert to arrays
        n_values = np.array([m[0] for m in self.measurements], dtype=float)
        time_values = np.array([m[1] for m in self.measurements], dtype=float)
        n_samples = len(n_values)

        results = {}

        for model_name, model_info in self.MODELS.items():
            model_func = model_info["function"]
            n_params = model_info["n_params"]

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", OptimizeWarning)

                    # Initial guess
                    if model_name == "O(1)":
                        p0 = [np.mean(time_values)]
                        bounds = ([0], [np.inf])
                    elif n_params == 2:
                        p0 = [1.0, np.min(time_values)]
                        bounds = ([-np.inf, -np.inf], [np.inf, np.inf])
                    else:  # 3 params
                        p0 = [0.001, 1.0, np.min(time_values)]
                        bounds = ([-np.inf, -np.inf, -np.inf], [np.inf, np.inf, np.inf])

                    # Fit model
                    popt, pcov = curve_fit(
                        model_func,
                        n_values,
                        time_values,
                        p0=p0,
                        bounds=bounds,
                        maxfev=10000,
                    )

                    # Calculate predictions and residuals
                    predictions = model_func(n_values, *popt)
                    residuals = time_values - predictions

                    # R-squared
                    ss_res = np.sum(residuals**2)
                    ss_tot = np.sum((time_values - np.mean(time_values))**2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                    # Residual standard deviation
                    residual_std = np.std(residuals, ddof=n_params)

                    # AIC and BIC
                    # AIC = n*ln(RSS/n) + 2k
                    # BIC = n*ln(RSS/n) + k*ln(n)
                    rss_per_n = ss_res / n_samples if ss_res > 0 else 1e-10
                    aic = n_samples * np.log(rss_per_n) + 2 * n_params
                    bic = n_samples * np.log(rss_per_n) + n_params * np.log(n_samples)

                    # Create parameter dictionary
                    param_names = ['a', 'b', 'c'][:n_params]
                    parameters = dict(zip(param_names, popt))

                    # Create prediction function
                    def make_predictor(func, params):
                        return lambda x: func(np.array(x), *params)

                    results[model_name] = ModelFitResult(
                        model_name=model_name,
                        parameters=parameters,
                        r_squared=float(r_squared),
                        aic=float(aic),
                        bic=float(bic),
                        residual_std=float(residual_std),
                        prediction_function=make_predictor(model_func, popt),
                    )

            except Exception as e:
                # Failed to fit this model
                results[model_name] = ModelFitResult(
                    model_name=model_name,
                    parameters={},
                    r_squared=-np.inf,
                    aic=np.inf,
                    bic=np.inf,
                    residual_std=np.inf,
                    prediction_function=None,
                )

        return results

    def test_complexity(self) -> ScalabilityAnalysisResult:
        """
        Determine the scaling complexity.

        Uses model comparison with AIC/BIC and F-tests for nested models.

        Returns:
            ScalabilityAnalysisResult with complete analysis
        """
        model_fits = self.fit_models()

        # Filter out failed fits
        valid_fits = {
            k: v for k, v in model_fits.items()
            if not np.isinf(v.aic) and not np.isnan(v.r_squared)
        }

        if not valid_fits:
            return ScalabilityAnalysisResult(
                measurements=self.measurements,
                model_fits=model_fits,
                best_model="unknown",
                complexity_class="unknown",
                is_acceptable=False,
                f_test_results={},
            )

        # Find best model by BIC (prefers simpler models)
        best_model_name = min(valid_fits.keys(), key=lambda k: valid_fits[k].bic)
        best_model = valid_fits[best_model_name]

        # F-tests for nested model comparisons
        f_test_results = self._run_f_tests(model_fits)

        # Determine complexity class
        complexity_class = self._determine_complexity_class(
            model_fits, f_test_results
        )

        # Check if acceptable (O(n log n) or better)
        acceptable_complexities = ["O(1)", "O(log n)", "O(sqrt(n))", "O(n)", "O(n log n)"]
        is_acceptable = complexity_class in acceptable_complexities

        return ScalabilityAnalysisResult(
            measurements=self.measurements,
            model_fits=model_fits,
            best_model=best_model_name,
            complexity_class=complexity_class,
            is_acceptable=is_acceptable,
            f_test_results=f_test_results,
        )

    def _run_f_tests(
        self,
        model_fits: Dict[str, ModelFitResult],
    ) -> Dict[str, Dict]:
        """
        Run F-tests for nested model comparisons.

        Tests whether more complex models provide significant improvement.
        """
        n_values = np.array([m[0] for m in self.measurements], dtype=float)
        time_values = np.array([m[1] for m in self.measurements], dtype=float)
        n = len(n_values)

        f_test_results = {}

        # Compare nested models
        comparisons = [
            ("O(n)", "O(n log n)"),
            ("O(n)", "O(n^2)"),
            ("O(n log n)", "O(n^2)"),
        ]

        for simple, complex_ in comparisons:
            if simple not in model_fits or complex_ not in model_fits:
                continue

            simple_fit = model_fits[simple]
            complex_fit = model_fits[complex_]

            if simple_fit.residual_std == np.inf or complex_fit.residual_std == np.inf:
                continue

            # Get predictions
            try:
                simple_pred = simple_fit.predict(n_values)
                complex_pred = complex_fit.predict(n_values)
            except Exception:
                continue

            # Calculate RSS
            rss_simple = np.sum((time_values - simple_pred)**2)
            rss_complex = np.sum((time_values - complex_pred)**2)

            # Degrees of freedom
            df_simple = self.MODELS[simple]["n_params"]
            df_complex = self.MODELS[complex_]["n_params"]
            df_diff = df_complex - df_simple
            df_residual = n - df_complex

            if df_diff <= 0 or df_residual <= 0:
                continue

            # F-statistic
            if rss_complex > 0:
                f_stat = ((rss_simple - rss_complex) / df_diff) / (rss_complex / df_residual)
            else:
                f_stat = 0

            # P-value
            p_value = 1 - scipy_stats.f.cdf(f_stat, df_diff, df_residual)

            f_test_results[f"{simple} vs {complex_}"] = {
                "f_statistic": float(f_stat),
                "p_value": float(p_value),
                "df_numerator": df_diff,
                "df_denominator": df_residual,
                "significant": p_value < 0.05,
                "prefer_complex": p_value < 0.05 and f_stat > 0,
            }

        return f_test_results

    def _determine_complexity_class(
        self,
        model_fits: Dict[str, ModelFitResult],
        f_test_results: Dict[str, Dict],
    ) -> str:
        """
        Determine the most likely complexity class.

        Uses a combination of BIC comparison and F-tests.
        """
        # Get valid fits sorted by BIC
        valid_fits = [
            (name, fit) for name, fit in model_fits.items()
            if not np.isinf(fit.bic) and fit.r_squared > 0.5
        ]

        if not valid_fits:
            return "unknown"

        valid_fits.sort(key=lambda x: x[1].bic)

        # Start with simplest adequate model
        best_name = valid_fits[0][0]

        # Check if more complex model is significantly better
        for comparison, result in f_test_results.items():
            simple, complex_ = comparison.split(" vs ")
            if result.get("prefer_complex", False):
                # Complex model is significantly better
                if (simple == best_name and
                    complex_ in model_fits and
                    model_fits[complex_].r_squared > 0.9):
                    best_name = complex_

        return best_name

    def get_efficiency_factor(
        self,
        baseline_n: int = 100,
    ) -> Dict[str, float]:
        """
        Calculate efficiency factors for each load level.

        Efficiency = (ideal_time / actual_time) where ideal assumes O(n).

        Args:
            baseline_n: Baseline N for normalization

        Returns:
            Dictionary mapping n_agents to efficiency factor
        """
        if len(self.measurements) < 2:
            return {}

        # Find baseline measurement
        baseline_time = None
        for n, t in self.measurements:
            if n == baseline_n:
                baseline_time = t
                break

        if baseline_time is None:
            # Use smallest n as baseline
            sorted_measurements = sorted(self.measurements, key=lambda x: x[0])
            baseline_n, baseline_time = sorted_measurements[0]

        # Calculate efficiency for each measurement
        # Ideal time assuming O(n): ideal_t = baseline_t * (n / baseline_n)
        efficiency = {}
        for n, actual_time in self.measurements:
            ideal_time = baseline_time * (n / baseline_n)
            efficiency[n] = ideal_time / actual_time if actual_time > 0 else 0

        return efficiency


def simulate_scaling_data(
    n_values: List[int],
    complexity: str = "nlogn",
    base_time_ms: float = 0.1,
    noise_factor: float = 0.1,
    seed: Optional[int] = None,
) -> List[Tuple[int, float]]:
    """
    Generate simulated scaling data.

    Args:
        n_values: List of n values to simulate
        complexity: One of "constant", "log", "linear", "nlogn", "quadratic"
        base_time_ms: Base time per unit operation
        noise_factor: Noise level (relative)
        seed: Random seed

    Returns:
        List of (n, time_ms) tuples
    """
    rng = np.random.default_rng(seed)

    measurements = []

    for n in n_values:
        # Calculate ideal time based on complexity
        if complexity == "constant":
            ideal_time = base_time_ms
        elif complexity == "log":
            ideal_time = base_time_ms * np.log(max(n, 2))
        elif complexity == "linear":
            ideal_time = base_time_ms * n
        elif complexity == "nlogn":
            ideal_time = base_time_ms * n * np.log(max(n, 2))
        elif complexity == "quadratic":
            ideal_time = base_time_ms * n * n / 100  # Scale down
        else:
            raise ValueError(f"Unknown complexity: {complexity}")

        # Add noise
        noise = rng.normal(1, noise_factor)
        actual_time = ideal_time * max(noise, 0.5)

        measurements.append((n, actual_time))

    return measurements
