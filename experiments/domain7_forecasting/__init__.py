"""
Domain 7: Load Forecasting Accuracy Experiments for SHAKTI-CHAIN.

This module implements hypothesis tests for load forecasting:

H7.1: MAPE Target
    - H₁: MAPE < 5% on out-of-sample data
    - H₀: MAPE ≥ 5%
    - Test: One-sample t-test across k-folds

H7.2: Forecast Horizon Performance
    - H₁: MAPE < 10% up to 24h horizon
    - H₀: MAPE ≥ 10% for some h ≤ 24h
    - Test: One-sample t-tests at each horizon

H7.3: City-Specific Accuracy
    - H₁: MAPE < 5% for all major Indian cities
    - H₀: MAPE ≥ 5% for at least one city
    - Test: Multiple one-sample t-tests with Bonferroni correction

H7.4: Forecast vs Baselines
    - H₁: TFT beats Naive, ARIMA, Prophet
    - H₀: TFT doesn't beat at least one
    - Test: Paired t-tests

H7.5: Prediction Interval Coverage
    - H₁: 95% PI contains actual 95±3% of time
    - H₀: Coverage significantly different
    - Test: Exact binomial

Components:
    - synthetic_load_generator: Generate realistic load data for Indian cities
    - tft_trainer: Train Temporal Fusion Transformer model
    - baseline_models: Naive, ARIMA, Prophet baselines
    - evaluation_metrics: MAPE, RMSE, coverage metrics
    - cross_validator: K-fold walk-forward cross-validation
    - hypothesis_tests: Statistical hypothesis testing
    - visualization: Result visualization
"""

from .synthetic_load_generator import (
    SyntheticLoadGenerator,
    CityLoadProfile,
    SpecialEvent,
    DELHI_PROFILE,
    MUMBAI_PROFILE,
    BANGALORE_PROFILE,
    CHENNAI_PROFILE,
    KOLKATA_PROFILE,
    HYDERABAD_PROFILE,
    CITY_PROFILES,
    INDIA_CITIES,
    INDIA_SPECIAL_EVENTS,
    generate_india_load_data,
)

from .evaluation_metrics import (
    ForecastEvaluation,
    MAPETestResult,
    CoverageTestResult,
    mape,
    rmse,
    mae,
    smape,
    mase,
    r_squared,
    coverage_probability,
    interval_sharpness,
    winkler_score,
    evaluate_forecast,
    test_mape_threshold,
    test_coverage_target,
)

from .baseline_models import (
    NaiveForecaster,
    SeasonalNaiveForecaster,
    MovingAverageForecaster,
    ExponentialSmoothingForecaster,
    ARIMAForecaster,
    ProphetForecaster,
    BASELINE_MODELS,
)

from .tft_trainer import (
    TFTConfig,
    TrainingHistory,
    SimpleTFTModel,
    TFTTrainer,
    train_tft_model,
)

from .cross_validator import (
    CVFold,
    CVResult,
    ModelCVResult,
    ForecastCrossValidator,
    MultiModelCrossValidator,
    cross_validate_forecaster,
)

from .hypothesis_tests import (
    HypothesisResult,
    ForecastingHypothesisResults,
    ForecastingHypothesisTester,
    run_hypothesis_tests,
)

from .visualization import (
    ForecastVisualization,
    create_visualization_report,
)

from .experiments import (
    ForecastingExperimentConfig,
    SingleRunResults,
    ForecastingExperimentResults,
    ForecastingExperiment,
    run_quick_forecasting_test,
    run_full_forecasting_experiment,
    print_hypothesis_summary,
)

__all__ = [
    # Synthetic data generation
    "SyntheticLoadGenerator",
    "CityLoadProfile",
    "SpecialEvent",
    "DELHI_PROFILE",
    "MUMBAI_PROFILE",
    "BANGALORE_PROFILE",
    "CHENNAI_PROFILE",
    "KOLKATA_PROFILE",
    "HYDERABAD_PROFILE",
    "CITY_PROFILES",
    "INDIA_CITIES",
    "INDIA_SPECIAL_EVENTS",
    "generate_india_load_data",

    # Evaluation metrics
    "ForecastEvaluation",
    "MAPETestResult",
    "CoverageTestResult",
    "mape",
    "rmse",
    "mae",
    "smape",
    "mase",
    "r_squared",
    "coverage_probability",
    "interval_sharpness",
    "winkler_score",
    "evaluate_forecast",
    "test_mape_threshold",
    "test_coverage_target",

    # Baseline models
    "NaiveForecaster",
    "SeasonalNaiveForecaster",
    "MovingAverageForecaster",
    "ExponentialSmoothingForecaster",
    "ARIMAForecaster",
    "ProphetForecaster",
    "BASELINE_MODELS",

    # TFT trainer
    "TFTConfig",
    "TrainingHistory",
    "SimpleTFTModel",
    "TFTTrainer",
    "train_tft_model",

    # Cross-validation
    "CVFold",
    "CVResult",
    "ModelCVResult",
    "ForecastCrossValidator",
    "MultiModelCrossValidator",
    "cross_validate_forecaster",

    # Hypothesis tests
    "HypothesisResult",
    "ForecastingHypothesisResults",
    "ForecastingHypothesisTester",
    "run_hypothesis_tests",

    # Visualization
    "ForecastVisualization",
    "create_visualization_report",

    # Experiments
    "ForecastingExperimentConfig",
    "SingleRunResults",
    "ForecastingExperimentResults",
    "ForecastingExperiment",
    "run_quick_forecasting_test",
    "run_full_forecasting_experiment",
    "print_hypothesis_summary",
]
