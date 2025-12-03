"""Evaluation module for SHAKTI-CHAIN forecasting."""

from .metrics import (
    ForecastEvaluator,
    EvaluationResults,
    MetricResult,
    TimePeriod,
    Season,
    DayType,
)
from .baselines import (
    BaselineModel,
    NaiveModel,
    SeasonalNaiveModel,
    ARIMAModel,
    XGBoostModel,
    ProphetModel,
    PersistenceModel,
    MovingAverageModel,
    get_all_baselines,
    get_simple_baselines,
)
from .cross_validation import (
    TimeSeriesSplit,
    BlockingTimeSeriesSplit,
    CrossValidator,
    CVResults,
    TimeSeriesFold,
    cross_validate_baselines,
    format_cv_comparison,
)
from .visualization import (
    plot_predictions_vs_actuals,
    plot_error_distribution,
    plot_metrics_by_horizon,
    plot_metrics_by_dimension,
    plot_model_comparison,
    plot_cv_results,
    plot_attention_weights,
    plot_feature_importance,
    create_evaluation_report_plots,
)

__all__ = [
    # Metrics
    "ForecastEvaluator",
    "EvaluationResults",
    "MetricResult",
    "TimePeriod",
    "Season",
    "DayType",
    # Baselines
    "BaselineModel",
    "NaiveModel",
    "SeasonalNaiveModel",
    "ARIMAModel",
    "XGBoostModel",
    "ProphetModel",
    "PersistenceModel",
    "MovingAverageModel",
    "get_all_baselines",
    "get_simple_baselines",
    # Cross-validation
    "TimeSeriesSplit",
    "BlockingTimeSeriesSplit",
    "CrossValidator",
    "CVResults",
    "TimeSeriesFold",
    "cross_validate_baselines",
    "format_cv_comparison",
    # Visualization
    "plot_predictions_vs_actuals",
    "plot_error_distribution",
    "plot_metrics_by_horizon",
    "plot_metrics_by_dimension",
    "plot_model_comparison",
    "plot_cv_results",
    "plot_attention_weights",
    "plot_feature_importance",
    "create_evaluation_report_plots",
]
