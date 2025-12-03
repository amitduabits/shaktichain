"""Explainability module for SHAKTI-CHAIN ML models.

Provides interpretable explanations for:
- Load and price forecasting models (SHAP-based)
- TFT attention visualization
- Trading agent decisions (RL explainability)
"""

from .forecast_explainer import ForecastExplainer, ForecastExplanation
from .attention_explainer import TFTAttentionExplainer, AttentionExplanation
from .trading_explainer import TradingExplainer, TradingExplanation
from .visualizations import (
    plot_shap_waterfall,
    plot_shap_summary,
    plot_attention_heatmap,
    plot_temporal_attention,
    plot_decision_factors,
    plot_feature_importance,
)

__all__ = [
    # Forecast explainability
    "ForecastExplainer",
    "ForecastExplanation",
    # TFT attention
    "TFTAttentionExplainer",
    "AttentionExplanation",
    # Trading explainability
    "TradingExplainer",
    "TradingExplanation",
    # Visualization utilities
    "plot_shap_waterfall",
    "plot_shap_summary",
    "plot_attention_heatmap",
    "plot_temporal_attention",
    "plot_decision_factors",
    "plot_feature_importance",
]
