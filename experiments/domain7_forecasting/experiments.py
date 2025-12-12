"""
Load Forecasting Experiments (Domain 7).

Main experiment runner for testing H7.1-H7.5 hypotheses:
- H7.1: MAPE < 5% on out-of-sample data
- H7.2: MAPE < 10% up to 24h horizon
- H7.3: MAPE < 5% for all major Indian cities
- H7.4: TFT beats Naive, ARIMA, Prophet
- H7.5: 95% PI contains actual 95±3% of time
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .synthetic_load_generator import (
    SyntheticLoadGenerator,
    CITY_PROFILES,
    INDIA_CITIES,
)
from .evaluation_metrics import (
    ForecastEvaluation,
    evaluate_forecast,
    mape,
    rmse,
    coverage_probability,
)
from .baseline_models import (
    NaiveForecaster,
    SeasonalNaiveForecaster,
    MovingAverageForecaster,
    ARIMAForecaster,
    ProphetForecaster,
)
from .tft_trainer import TFTTrainer, TFTConfig, train_tft_model
from .cross_validator import (
    ForecastCrossValidator,
    MultiModelCrossValidator,
    CVResult,
)
from .hypothesis_tests import (
    ForecastingHypothesisTester,
    ForecastingHypothesisResults,
    run_hypothesis_tests,
)
from .visualization import ForecastVisualization, create_visualization_report

logger = logging.getLogger(__name__)


@dataclass
class ForecastingExperimentConfig:
    """
    Configuration for forecasting experiments.

    Attributes:
        n_runs: Number of experiment runs
        cities: List of cities to include
        data_days: Days of synthetic data to generate
        train_ratio: Training data ratio
        short_horizon: Short-term forecast horizon (hours)
        long_horizon: Long-term forecast horizon (hours)
        cv_splits: Number of cross-validation splits
        random_seed: Random seed for reproducibility
    """
    n_runs: int = 10
    cities: List[str] = field(default_factory=lambda: INDIA_CITIES)
    data_days: int = 365
    train_ratio: float = 0.8
    short_horizon: int = 24
    long_horizon: int = 168
    cv_splits: int = 5
    random_seed: int = 42

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "n_runs": self.n_runs,
            "cities": self.cities,
            "data_days": self.data_days,
            "train_ratio": self.train_ratio,
            "short_horizon": self.short_horizon,
            "long_horizon": self.long_horizon,
            "cv_splits": self.cv_splits,
            "random_seed": self.random_seed,
        }


@dataclass
class SingleRunResults:
    """
    Results from a single experiment run.

    Attributes:
        run_idx: Run index
        city: City name
        mape_by_horizon: MAPE at each forecast horizon
        tft_mape: TFT model MAPE
        baseline_mapes: MAPE for each baseline model
        coverage: Empirical coverage
        in_interval: Boolean array of whether predictions were in interval
        model_metrics: Metrics for all models
        training_time: Total training time
    """
    run_idx: int
    city: str
    mape_by_horizon: Dict[int, float] = field(default_factory=dict)
    tft_mape: float = 0.0
    baseline_mapes: Dict[str, float] = field(default_factory=dict)
    coverage: float = 0.0
    in_interval: Optional[np.ndarray] = None
    model_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    training_time: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "run_idx": self.run_idx,
            "city": self.city,
            "mape_by_horizon": self.mape_by_horizon,
            "tft_mape": self.tft_mape,
            "baseline_mapes": self.baseline_mapes,
            "coverage": self.coverage,
            "model_metrics": self.model_metrics,
            "training_time": self.training_time,
        }


@dataclass
class ForecastingExperimentResults:
    """
    Results from full forecasting experiment.

    Attributes:
        config: Experiment configuration
        run_results: Results from each run
        hypothesis_results: Hypothesis test results
        aggregate_metrics: Aggregate metrics across runs
        total_time: Total experiment time
    """
    config: ForecastingExperimentConfig
    run_results: List[SingleRunResults] = field(default_factory=list)
    hypothesis_results: Optional[ForecastingHypothesisResults] = None
    aggregate_metrics: Dict[str, float] = field(default_factory=dict)
    total_time: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "config": self.config.to_dict(),
            "run_results": [r.to_dict() for r in self.run_results],
            "hypothesis_results": self.hypothesis_results.to_dict() if self.hypothesis_results else None,
            "aggregate_metrics": self.aggregate_metrics,
            "total_time": self.total_time,
        }

    def save(self, path: str) -> None:
        """Save results to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


class ForecastingExperiment:
    """
    Main experiment runner for load forecasting.

    Runs experiments to test H7.1-H7.5 hypotheses.
    """

    def __init__(self, config: Optional[ForecastingExperimentConfig] = None):
        """
        Initialize experiment.

        Args:
            config: Experiment configuration
        """
        self.config = config or ForecastingExperimentConfig()
        self.generator = SyntheticLoadGenerator(seed=self.config.random_seed)
        self.hypothesis_tester = ForecastingHypothesisTester()

    def generate_data(self, city: str) -> pd.DataFrame:
        """
        Generate synthetic load data for a city.

        Args:
            city: City name

        Returns:
            DataFrame with load data
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.config.data_days)

        return self.generator.generate(
            city=city,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            resolution_minutes=60,
            include_events=True,
        )

    def run_single_city(
        self,
        city: str,
        run_idx: int,
    ) -> SingleRunResults:
        """
        Run experiment for a single city.

        Args:
            city: City name
            run_idx: Run index

        Returns:
            SingleRunResults
        """
        logger.info(f"Running experiment for {city} (run {run_idx + 1})...")

        start_time = time.time()

        # Generate data
        data = self.generate_data(city)

        # Split data
        n = len(data)
        train_end = int(n * self.config.train_ratio)
        train_df = data.iloc[:train_end].copy()
        test_df = data.iloc[train_end:].copy()

        # Train TFT model
        tft_config = TFTConfig(
            max_prediction_length=self.config.short_horizon,
            epochs=20,
        )
        tft_trainer = TFTTrainer(tft_config)
        tft_trainer.train(train_df, target_col="load_mw")

        # Get TFT predictions
        tft_pred, tft_lower, tft_upper = tft_trainer.predict(
            train_df,
            horizon=self.config.short_horizon,
        )

        # Get actual values
        actual_short = test_df["load_mw"].values[:self.config.short_horizon]

        # Ensure same length
        min_len = min(len(actual_short), len(tft_pred))
        actual_short = actual_short[:min_len]
        tft_pred = tft_pred[:min_len]
        tft_lower = tft_lower[:min_len]
        tft_upper = tft_upper[:min_len]

        # Calculate TFT MAPE
        tft_mape_val = mape(actual_short, tft_pred)

        # Calculate MAPE by horizon
        mape_by_horizon = {}
        for h in range(1, min_len + 1):
            mape_by_horizon[h] = mape(actual_short[:h], tft_pred[:h])

        # Train baseline models and get their MAPEs
        baseline_mapes = {}
        model_metrics = {
            "TFT": {"mape": tft_mape_val, "rmse": rmse(actual_short, tft_pred)},
        }

        # Naive baseline
        try:
            naive = NaiveForecaster()
            naive.fit(train_df, target_col="load_mw")
            naive_pred = naive.forecast(self.config.short_horizon)[:min_len]
            naive_mape = mape(actual_short, naive_pred)
            baseline_mapes["Naive"] = naive_mape
            model_metrics["Naive"] = {
                "mape": naive_mape,
                "rmse": rmse(actual_short, naive_pred),
            }
        except Exception as e:
            logger.warning(f"Naive baseline failed: {e}")
            baseline_mapes["Naive"] = 100.0  # Penalty for failure

        # ARIMA baseline
        try:
            arima = ARIMAForecaster(order=(2, 1, 2))
            arima.fit(train_df["load_mw"].values)
            arima_pred = arima.predict(self.config.short_horizon)[:min_len]
            arima_mape = mape(actual_short, arima_pred)
            baseline_mapes["ARIMA"] = arima_mape
            model_metrics["ARIMA"] = {
                "mape": arima_mape,
                "rmse": rmse(actual_short, arima_pred),
            }
        except Exception as e:
            logger.warning(f"ARIMA baseline failed: {e}")
            baseline_mapes["ARIMA"] = 100.0  # Penalty for failure

        # Prophet baseline
        try:
            prophet = ProphetForecaster()
            prophet.fit(train_df["load_mw"].values)
            prophet_pred = prophet.predict(self.config.short_horizon)[:min_len]
            prophet_mape = mape(actual_short, prophet_pred)
            baseline_mapes["Prophet"] = prophet_mape
            model_metrics["Prophet"] = {
                "mape": prophet_mape,
                "rmse": rmse(actual_short, prophet_pred),
            }
        except Exception as e:
            logger.warning(f"Prophet baseline failed: {e}")
            baseline_mapes["Prophet"] = 100.0  # Penalty for failure

        # Coverage calculation
        in_interval = (actual_short >= tft_lower) & (actual_short <= tft_upper)
        coverage = np.mean(in_interval)

        training_time = time.time() - start_time

        return SingleRunResults(
            run_idx=run_idx,
            city=city,
            mape_by_horizon=mape_by_horizon,
            tft_mape=tft_mape_val,
            baseline_mapes=baseline_mapes,
            coverage=coverage,
            in_interval=in_interval,
            model_metrics=model_metrics,
            training_time=training_time,
        )

    def run(self) -> ForecastingExperimentResults:
        """
        Run full experiment.

        Returns:
            ForecastingExperimentResults
        """
        logger.info(f"Starting forecasting experiment with {self.config.n_runs} runs...")
        logger.info(f"Cities: {self.config.cities}")

        start_time = time.time()
        results = ForecastingExperimentResults(config=self.config)

        # Run experiments for each city
        for run_idx in range(self.config.n_runs):
            for city in self.config.cities:
                try:
                    run_result = self.run_single_city(city, run_idx)
                    results.run_results.append(run_result)
                except Exception as e:
                    logger.error(f"Error in run {run_idx} for {city}: {e}")

        # Aggregate metrics and run hypothesis tests
        if results.run_results:
            # H7.1: Collect all MAPE values (from TFT model)
            mape_values = [r.tft_mape for r in results.run_results]

            # H7.2: Collect MAPE by horizon across all runs
            mape_by_horizon = {}
            for h in range(1, self.config.short_horizon + 1):
                horizon_mapes = []
                for r in results.run_results:
                    if h in r.mape_by_horizon:
                        horizon_mapes.append(r.mape_by_horizon[h])
                if horizon_mapes:
                    mape_by_horizon[h] = horizon_mapes

            # H7.3: Per-city MAPE
            city_mape = {}
            for city in self.config.cities:
                city_runs = [r for r in results.run_results if r.city == city]
                if city_runs:
                    city_mape[city] = [r.tft_mape for r in city_runs]

            # H7.4: TFT vs baselines
            tft_mapes = [r.tft_mape for r in results.run_results]
            baseline_mapes_dict = {"Naive": [], "ARIMA": [], "Prophet": []}
            for r in results.run_results:
                for baseline_name in baseline_mapes_dict:
                    if baseline_name in r.baseline_mapes:
                        baseline_mapes_dict[baseline_name].append(r.baseline_mapes[baseline_name])

            # H7.5: Coverage - collect all in_interval arrays
            all_in_interval = []
            for r in results.run_results:
                if r.in_interval is not None:
                    all_in_interval.extend(r.in_interval.tolist())
            in_interval_array = np.array(all_in_interval) if all_in_interval else np.array([True])

            # Aggregate metrics for reporting
            coverages = [r.coverage for r in results.run_results]
            results.aggregate_metrics = {
                "mean_mape": np.mean(mape_values),
                "std_mape": np.std(mape_values),
                "mean_coverage": np.mean(coverages),
                "std_coverage": np.std(coverages),
                "mean_tft_mape": np.mean(tft_mapes),
            }

            # Add per-baseline mean MAPE
            for baseline_name, mapes in baseline_mapes_dict.items():
                if mapes:
                    results.aggregate_metrics[f"mean_{baseline_name.lower()}_mape"] = np.mean(mapes)

            # Run hypothesis tests
            try:
                results.hypothesis_results = run_hypothesis_tests(
                    mape_values=mape_values,
                    mape_by_horizon=mape_by_horizon,
                    city_mape=city_mape,
                    tft_mape=tft_mapes,
                    baseline_mapes=baseline_mapes_dict,
                    in_interval=in_interval_array,
                )
            except Exception as e:
                logger.error(f"Error running hypothesis tests: {e}")

        results.total_time = time.time() - start_time
        logger.info(f"Experiment complete in {results.total_time:.1f}s")

        return results


def run_quick_forecasting_test(
    n_runs: int = 3,
    cities: Optional[List[str]] = None,
    data_days: int = 60,
) -> ForecastingExperimentResults:
    """
    Run a quick forecasting test.

    Args:
        n_runs: Number of runs
        cities: Cities to test (default: 3 major cities)
        data_days: Days of data

    Returns:
        ForecastingExperimentResults
    """
    if cities is None:
        cities = ["Delhi", "Mumbai", "Bangalore"]

    config = ForecastingExperimentConfig(
        n_runs=n_runs,
        cities=cities,
        data_days=data_days,
        cv_splits=3,
    )

    experiment = ForecastingExperiment(config)
    return experiment.run()


def run_full_forecasting_experiment(
    output_dir: Optional[str] = None,
) -> ForecastingExperimentResults:
    """
    Run full forecasting experiment.

    Args:
        output_dir: Optional output directory

    Returns:
        ForecastingExperimentResults
    """
    config = ForecastingExperimentConfig(
        n_runs=10,
        cities=INDIA_CITIES,
        data_days=365,
        cv_splits=5,
    )

    experiment = ForecastingExperiment(config)
    results = experiment.run()

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        results.save(str(output_path / "forecasting_results.json"))

    return results


def print_hypothesis_summary(results: ForecastingExperimentResults) -> None:
    """
    Print summary of hypothesis test results.

    Args:
        results: Experiment results
    """
    if not results.hypothesis_results:
        print("No hypothesis results available")
        return

    print("\n" + "=" * 60)
    print("LOAD FORECASTING HYPOTHESIS TEST RESULTS (Domain 7)")
    print("=" * 60)

    hr = results.hypothesis_results
    for h_id in ["H7.1", "H7.2", "H7.3", "H7.4", "H7.5"]:
        if h_id in hr.results:
            r = hr.results[h_id]
            status = "[PASS]" if r.passed else "[FAIL]"
            # Use ASCII-safe description
            desc = r.description.replace('\u00b1', '+/-')
            print(f"\n{h_id}: {desc}")
            print(f"  Status: {status}")
            print(f"  p-value: {r.p_value:.4f}")
            print(f"  Effect size: {r.effect_size:.3f}")
            print(f"  95% CI: ({r.confidence_interval[0]:.3f}, {r.confidence_interval[1]:.3f})")

    print("\n" + "-" * 60)
    print(f"Overall: {hr.summary['n_passed']}/{hr.summary['n_hypotheses']} hypotheses passed")
    print("=" * 60)
