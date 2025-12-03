"""Explainability API endpoints for SHAKTI-CHAIN ML models.

Provides endpoints for:
- Forecast explanations (SHAP-based)
- TFT attention visualization
- Trading decision explanations
- Model summaries
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/explain", tags=["Explainability"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ForecastExplainRequest(BaseModel):
    """Request for forecast explanation."""

    timestamp: datetime = Field(..., description="Timestamp for the prediction")
    features: Dict[str, float] = Field(..., description="Input features for the forecast")
    model_type: str = Field("load", description="Model type: 'load' or 'price'")
    model_version: str = Field("production", description="Model version to use")
    top_k: int = Field(5, ge=1, le=20, description="Number of top features to explain")
    include_visualization: bool = Field(True, description="Include visualization data")
    visualization_format: str = Field("data", description="Visualization format: 'data', 'base64', or 'svg'")


class FeatureContributionResponse(BaseModel):
    """Feature contribution in explanation."""

    feature_name: str
    feature_value: float
    shap_value: float
    contribution_pct: float
    direction: str


class ForecastExplainResponse(BaseModel):
    """Response for forecast explanation."""

    request_id: str
    timestamp: datetime
    model_type: str
    model_version: str

    # Prediction
    prediction: float
    baseline: float
    deviation_pct: float

    # Explanation
    top_features: List[FeatureContributionResponse]
    text_explanation: str

    # Visualization
    visualization_data: Optional[Dict[str, Any]] = None

    # Metadata
    latency_ms: float


class TFTAttentionRequest(BaseModel):
    """Request for TFT attention visualization."""

    static_covariates: List[float] = Field(..., description="Static covariate features")
    historical_observed: List[List[float]] = Field(..., description="Historical observed values")
    historical_known: List[List[float]] = Field(..., description="Historical known features")
    future_known: List[List[float]] = Field(..., description="Future known features")
    timestamps: Optional[List[str]] = Field(None, description="Historical timestamps")
    model_version: str = Field("production", description="Model version")


class VariableImportanceResponse(BaseModel):
    """Variable importance in attention explanation."""

    variable_name: str
    importance_score: float
    category: str
    rank: int


class TFTAttentionResponse(BaseModel):
    """Response for TFT attention explanation."""

    request_id: str
    model_version: str

    # Variable importance
    static_importance: List[VariableImportanceResponse]
    encoder_importance: List[VariableImportanceResponse]
    decoder_importance: List[VariableImportanceResponse]

    # Attention summary
    attention_summary: Dict[str, Any]
    text_summary: str

    # Visualization
    visualization_data: Optional[Dict[str, Any]] = None

    latency_ms: float


class TradingExplainRequest(BaseModel):
    """Request for trading decision explanation."""

    state: Dict[str, float] = Field(..., description="Current trading state")
    action: Optional[str] = Field(None, description="Action taken (if known)")
    quantity: Optional[float] = Field(None, description="Trade quantity in kWh")
    price: Optional[float] = Field(None, description="Trade price")
    model_version: str = Field("production", description="Model version")
    include_counterfactual: bool = Field(True, description="Include counterfactual analysis")


class ActionReasonResponse(BaseModel):
    """Reason for trading action."""

    reason: str
    factor: str
    value: Any
    threshold: Optional[float]
    contribution: float
    direction: str


class AlternativeActionResponse(BaseModel):
    """Alternative action in explanation."""

    action: str
    expected_value: float
    probability: float
    reasons: List[str]


class TradingExplainResponse(BaseModel):
    """Response for trading explanation."""

    request_id: str
    model_version: str

    # Decision
    action: str
    quantity: float
    target_price: float
    confidence: float

    # Reasoning
    reasons: List[ActionReasonResponse]
    text_explanation: str
    alternative_actions: List[AlternativeActionResponse]

    # Analysis
    feature_contributions: Dict[str, float]
    action_probabilities: Dict[str, float]
    risk_factors: List[str]
    expected_profit: float
    expected_risk: float

    # Counterfactual
    counterfactual_analysis: Optional[Dict[str, Any]] = None

    # Visualization
    visualization_data: Optional[Dict[str, Any]] = None

    latency_ms: float


class ModelSummaryResponse(BaseModel):
    """Model summary with global interpretability."""

    model_name: str
    model_version: str
    model_type: str

    # Feature importance
    feature_importance: Dict[str, float]
    top_features: List[str]

    # Model statistics
    num_features: int
    baseline_prediction: float

    # Performance metrics (if available)
    recent_accuracy: Optional[float] = None
    recent_mae: Optional[float] = None

    # Metadata
    last_updated: Optional[datetime] = None


class WhatIfRequest(BaseModel):
    """Request for what-if analysis."""

    features: Dict[str, float] = Field(..., description="Current feature values")
    changes: Dict[str, float] = Field(..., description="Feature changes to apply")
    model_type: str = Field("load", description="Model type")
    model_version: str = Field("production", description="Model version")


class WhatIfResponse(BaseModel):
    """Response for what-if analysis."""

    request_id: str
    original_prediction: float
    modified_prediction: float
    absolute_change: float
    percentage_change: float
    feature_changes: Dict[str, Dict[str, float]]  # {feature: {from, to}}
    interpretation: str
    latency_ms: float


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/forecast", response_model=ForecastExplainResponse)
async def explain_forecast(request: ForecastExplainRequest):
    """Generate explanation for a forecast prediction.

    Uses SHAP values to explain which features contributed most to the
    prediction and by how much.

    Returns:
        - Top contributing features with SHAP values
        - Natural language explanation
        - Visualization data (optional)
    """
    start_time = time.time()
    request_id = str(uuid4())

    try:
        # Import explainer
        from src.explainability import ForecastExplainer

        # Get model and background data (mock for now)
        # In production, load from model registry
        model, background_data, feature_names = await _load_forecast_model(
            request.model_type, request.model_version
        )

        # Create explainer
        explainer = ForecastExplainer(
            model=model,
            background_data=background_data,
            feature_names=feature_names,
        )

        # Prepare input features
        import numpy as np
        feature_array = np.array([request.features.get(name, 0.0) for name in feature_names])

        # Generate explanation
        explanation = explainer.explain_prediction(
            input_features=feature_array,
            timestamp=request.timestamp.isoformat(),
            top_k=request.top_k,
            include_visualization=request.include_visualization,
        )

        # Calculate deviation percentage
        deviation_pct = 0.0
        if explanation.baseline != 0:
            deviation_pct = (explanation.prediction - explanation.baseline) / abs(explanation.baseline) * 100

        latency_ms = (time.time() - start_time) * 1000

        return ForecastExplainResponse(
            request_id=request_id,
            timestamp=request.timestamp,
            model_type=request.model_type,
            model_version=request.model_version,
            prediction=explanation.prediction,
            baseline=explanation.baseline,
            deviation_pct=deviation_pct,
            top_features=[
                FeatureContributionResponse(
                    feature_name=f.feature_name,
                    feature_value=f.feature_value,
                    shap_value=f.shap_value,
                    contribution_pct=f.contribution_pct,
                    direction=f.direction,
                )
                for f in explanation.top_features
            ],
            text_explanation=explanation.text_explanation,
            visualization_data=explanation.visualization_data if request.include_visualization else None,
            latency_ms=latency_ms,
        )

    except ImportError as e:
        logger.warning(f"Explainability module not available: {e}")
        # Return mock response for testing
        return _mock_forecast_explanation(request, request_id, start_time)

    except Exception as e:
        logger.error(f"Error generating forecast explanation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attention", response_model=TFTAttentionResponse)
async def explain_tft_attention(request: TFTAttentionRequest):
    """Generate TFT attention visualization.

    Extracts attention weights from the Temporal Fusion Transformer to show:
    - Which input variables are most important (variable selection)
    - Which historical time steps are attended to (temporal attention)

    Returns:
        - Variable importance scores by category
        - Attention pattern summary
        - Heatmap visualization data
    """
    start_time = time.time()
    request_id = str(uuid4())

    try:
        from src.explainability import TFTAttentionExplainer
        import numpy as np

        # Load TFT model
        model, feature_config = await _load_tft_model(request.model_version)

        # Create explainer
        explainer = TFTAttentionExplainer(
            model=model,
            static_feature_names=feature_config.get("static", []),
            encoder_feature_names=feature_config.get("encoder", []),
            decoder_feature_names=feature_config.get("decoder", []),
        )

        # Generate explanation
        explanation = explainer.explain_prediction(
            static_covariates=np.array(request.static_covariates),
            historical_observed=np.array(request.historical_observed),
            historical_known=np.array(request.historical_known),
            future_known=np.array(request.future_known),
            timestamps=request.timestamps,
        )

        latency_ms = (time.time() - start_time) * 1000

        return TFTAttentionResponse(
            request_id=request_id,
            model_version=request.model_version,
            static_importance=[
                VariableImportanceResponse(**vi.to_dict())
                for vi in explanation.static_variable_importance
            ],
            encoder_importance=[
                VariableImportanceResponse(**vi.to_dict())
                for vi in explanation.encoder_variable_importance
            ],
            decoder_importance=[
                VariableImportanceResponse(**vi.to_dict())
                for vi in explanation.decoder_variable_importance
            ],
            attention_summary=explanation.attention_statistics,
            text_summary=explanation.text_summary,
            visualization_data=explanation.visualization_data,
            latency_ms=latency_ms,
        )

    except ImportError as e:
        logger.warning(f"Attention explainer not available: {e}")
        return _mock_attention_explanation(request, request_id, start_time)

    except Exception as e:
        logger.error(f"Error generating attention explanation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading", response_model=TradingExplainResponse)
async def explain_trading(request: TradingExplainRequest):
    """Generate explanation for a trading decision.

    Analyzes the RL agent's decision-making process to explain:
    - Why a particular action was chosen
    - What factors contributed most
    - What alternative actions were considered
    - Risk assessment

    Returns:
        - Action taken with confidence
        - Key reasoning factors
        - Alternative actions considered
        - Counterfactual analysis
    """
    start_time = time.time()
    request_id = str(uuid4())

    try:
        from src.explainability import TradingExplainer
        from src.explainability.trading_explainer import ActionType

        # Load trading agent
        agent, feature_names = await _load_trading_agent(request.model_version)

        # Create explainer
        explainer = TradingExplainer(
            agent=agent,
            feature_names=feature_names,
        )

        # Parse action if provided
        action = None
        if request.action:
            action = ActionType[request.action.upper()]

        # Generate explanation
        explanation = explainer.explain_action(
            state=request.state,
            action=action,
            quantity=request.quantity,
            price=request.price,
        )

        latency_ms = (time.time() - start_time) * 1000

        return TradingExplainResponse(
            request_id=request_id,
            model_version=request.model_version,
            action=explanation.action.name,
            quantity=explanation.quantity,
            target_price=explanation.target_price,
            confidence=explanation.confidence,
            reasons=[
                ActionReasonResponse(
                    reason=r.reason,
                    factor=r.factor,
                    value=r.value,
                    threshold=r.threshold,
                    contribution=r.contribution,
                    direction=r.direction,
                )
                for r in explanation.reasons
            ],
            text_explanation=explanation.text_explanation,
            alternative_actions=[
                AlternativeActionResponse(
                    action=a.action.name,
                    expected_value=a.expected_value,
                    probability=a.probability,
                    reasons=a.reasons,
                )
                for a in explanation.alternative_actions
            ],
            feature_contributions=explanation.feature_contributions,
            action_probabilities=explanation.action_probabilities,
            risk_factors=explanation.risk_factors,
            expected_profit=explanation.expected_profit,
            expected_risk=explanation.expected_risk,
            counterfactual_analysis=explanation.counterfactual_analysis if request.include_counterfactual else None,
            visualization_data=explanation.visualization_data,
            latency_ms=latency_ms,
        )

    except ImportError as e:
        logger.warning(f"Trading explainer not available: {e}")
        return _mock_trading_explanation(request, request_id, start_time)

    except Exception as e:
        logger.error(f"Error generating trading explanation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-summary/{model_type}", response_model=ModelSummaryResponse)
async def get_model_summary(
    model_type: str,
    model_version: str = Query("production", description="Model version"),
):
    """Get global interpretability summary for a model.

    Provides:
    - Global feature importance
    - Baseline predictions
    - Recent performance metrics

    Args:
        model_type: Type of model ('load', 'price', 'trading')
        model_version: Model version to summarize
    """
    try:
        from src.explainability import ForecastExplainer

        if model_type in ["load", "price"]:
            model, background_data, feature_names = await _load_forecast_model(
                model_type, model_version
            )

            explainer = ForecastExplainer(
                model=model,
                background_data=background_data,
                feature_names=feature_names,
            )

            feature_importance = explainer.get_feature_importance()

            # Sort by importance
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )

            return ModelSummaryResponse(
                model_name=f"{model_type}_forecast",
                model_version=model_version,
                model_type=model_type,
                feature_importance=feature_importance,
                top_features=[f[0] for f in sorted_features[:10]],
                num_features=len(feature_names),
                baseline_prediction=explainer.baseline,
                last_updated=datetime.now(),
            )

        else:
            # Return mock for trading model
            return _mock_model_summary(model_type, model_version)

    except Exception as e:
        logger.error(f"Error getting model summary: {e}")
        return _mock_model_summary(model_type, model_version)


@router.post("/what-if", response_model=WhatIfResponse)
async def what_if_analysis(request: WhatIfRequest):
    """Perform what-if analysis on a forecast.

    Shows how changing specific features would affect the prediction.

    Args:
        features: Current feature values
        changes: Dictionary of {feature_name: new_value}

    Returns:
        - Original and modified predictions
        - Percentage change
        - Interpretation
    """
    start_time = time.time()
    request_id = str(uuid4())

    try:
        from src.explainability import ForecastExplainer
        import numpy as np

        model, background_data, feature_names = await _load_forecast_model(
            request.model_type, request.model_version
        )

        explainer = ForecastExplainer(
            model=model,
            background_data=background_data,
            feature_names=feature_names,
        )

        feature_array = np.array([request.features.get(name, 0.0) for name in feature_names])

        result = explainer.what_if_analysis(
            input_features=feature_array,
            feature_changes=request.changes,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Format feature changes
        feature_changes_formatted = {
            name: {
                "from": request.features.get(name, 0.0),
                "to": value,
            }
            for name, value in request.changes.items()
        }

        return WhatIfResponse(
            request_id=request_id,
            original_prediction=result["original_prediction"],
            modified_prediction=result["modified_prediction"],
            absolute_change=result["absolute_change"],
            percentage_change=result["percentage_change"],
            feature_changes=feature_changes_formatted,
            interpretation=result["interpretation"],
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Error in what-if analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visualization/{viz_type}")
async def get_visualization(
    viz_type: str,
    request_id: Optional[str] = Query(None, description="Request ID from previous explain call"),
    output_format: str = Query("base64", description="Output format: base64 or svg"),
):
    """Get visualization for a previous explanation.

    Args:
        viz_type: Type of visualization ('waterfall', 'attention', 'decision')
        request_id: Request ID from a previous explanation call
        output_format: 'base64' for PNG image or 'svg' for vector graphic

    Returns:
        Visualization image in requested format
    """
    # In production, this would retrieve cached explanation data
    # For now, return appropriate error or mock
    raise HTTPException(
        status_code=501,
        detail="Visualization caching not implemented. Use include_visualization=true in explain requests."
    )


# ============================================================================
# Helper Functions
# ============================================================================


async def _load_forecast_model(model_type: str, model_version: str):
    """Load forecast model with background data."""
    import numpy as np

    # In production, load from MLflow or model registry
    # For now, create mock model and data

    feature_names = [
        "temperature", "humidity", "hour_sin", "hour_cos",
        "day_sin", "day_cos", "month_sin", "month_cos",
        "is_weekend", "is_holiday", "load_lag_1h", "load_lag_24h",
        "price_lag_1h", "grid_load", "solar_irradiance",
    ]

    # Mock background data
    np.random.seed(42)
    background_data = np.random.randn(100, len(feature_names))

    # Mock model (simple linear)
    class MockModel:
        def __init__(self):
            self.weights = np.random.randn(len(feature_names))
            self.bias = 100.0

        def __call__(self, x):
            import torch
            if isinstance(x, torch.Tensor):
                x = x.numpy()
            return np.dot(x, self.weights) + self.bias

        def predict(self, x):
            return self(x)

    return MockModel(), background_data, feature_names


async def _load_tft_model(model_version: str):
    """Load TFT model with feature configuration."""
    # In production, load from model registry
    feature_config = {
        "static": ["city", "prosumer_type", "capacity_tier"],
        "encoder": ["load_observed", "temperature", "hour_sin", "hour_cos", "is_holiday"],
        "decoder": ["temperature_forecast", "hour_sin", "hour_cos", "is_holiday"],
    }

    # Mock model
    class MockTFTModel:
        def __init__(self):
            self.num_heads = 4
            self.encoder_length = 168
            self.decoder_length = 24

        def __call__(self, static, hist_obs, hist_known, future_known):
            import numpy as np
            batch_size = static.shape[0] if hasattr(static, "shape") else 1

            predictions = np.random.randn(batch_size, self.decoder_length, 1)

            interpretability = {
                "static_weights": np.random.rand(batch_size, len(feature_config["static"])),
                "encoder_variable_weights": np.random.rand(batch_size, self.encoder_length, len(feature_config["encoder"])),
                "decoder_variable_weights": np.random.rand(batch_size, self.decoder_length, len(feature_config["decoder"])),
                "attention_weights": np.random.rand(batch_size, self.num_heads, self.decoder_length, self.encoder_length),
            }

            return predictions, interpretability

        def eval(self):
            pass

    return MockTFTModel(), feature_config


async def _load_trading_agent(model_version: str):
    """Load trading agent with feature names."""
    feature_names = [
        "spot_price", "price_velocity_1m", "volatility_1h",
        "order_imbalance", "grid_load", "grid_frequency", "soc",
    ]

    # Mock agent
    class MockAgent:
        def predict(self, obs, deterministic=True):
            import numpy as np
            return np.random.randint(0, 3), None

        def predict_proba(self, obs):
            import numpy as np
            probs = np.random.rand(3)
            return probs / probs.sum()

    return MockAgent(), feature_names


def _mock_forecast_explanation(request, request_id, start_time):
    """Generate mock forecast explanation."""
    latency_ms = (time.time() - start_time) * 1000

    # Generate mock top features
    top_features = [
        FeatureContributionResponse(
            feature_name="temperature",
            feature_value=request.features.get("temperature", 32.0),
            shap_value=0.15,
            contribution_pct=30.0,
            direction="positive",
        ),
        FeatureContributionResponse(
            feature_name="hour_sin",
            feature_value=request.features.get("hour_sin", 0.5),
            shap_value=0.08,
            contribution_pct=16.0,
            direction="positive",
        ),
        FeatureContributionResponse(
            feature_name="load_lag_1h",
            feature_value=request.features.get("load_lag_1h", 95.0),
            shap_value=0.07,
            contribution_pct=14.0,
            direction="positive",
        ),
    ]

    return ForecastExplainResponse(
        request_id=request_id,
        timestamp=request.timestamp,
        model_type=request.model_type,
        model_version=request.model_version,
        prediction=105.5,
        baseline=100.0,
        deviation_pct=5.5,
        top_features=top_features,
        text_explanation="Forecast is 5.5% higher than average.\n\nKey contributing factors:\n  1. Temperature (32.0°C): ↑ +30.0% impact\n  2. Time of day (cyclical): ↑ +16.0% impact\n  3. Load 1 hour ago (95.0 MW): ↑ +14.0% impact",
        visualization_data=None,
        latency_ms=latency_ms,
    )


def _mock_attention_explanation(request, request_id, start_time):
    """Generate mock attention explanation."""
    latency_ms = (time.time() - start_time) * 1000

    return TFTAttentionResponse(
        request_id=request_id,
        model_version=request.model_version,
        static_importance=[
            VariableImportanceResponse(variable_name="city", importance_score=0.4, category="static", rank=1),
            VariableImportanceResponse(variable_name="prosumer_type", importance_score=0.35, category="static", rank=2),
        ],
        encoder_importance=[
            VariableImportanceResponse(variable_name="load_observed", importance_score=0.3, category="encoder", rank=1),
            VariableImportanceResponse(variable_name="temperature", importance_score=0.25, category="encoder", rank=2),
        ],
        decoder_importance=[
            VariableImportanceResponse(variable_name="temperature_forecast", importance_score=0.4, category="decoder", rank=1),
            VariableImportanceResponse(variable_name="hour_sin", importance_score=0.3, category="decoder", rank=2),
        ],
        attention_summary={"peak_attended_step": 162, "attention_span_std": 12.5},
        text_summary="Model focuses primarily on recent history (last 6 hours) with high importance on load and temperature.",
        visualization_data=None,
        latency_ms=latency_ms,
    )


def _mock_trading_explanation(request, request_id, start_time):
    """Generate mock trading explanation."""
    latency_ms = (time.time() - start_time) * 1000

    return TradingExplainResponse(
        request_id=request_id,
        model_version=request.model_version,
        action=request.action or "SELL",
        quantity=request.quantity or 50.0,
        target_price=request.price or request.state.get("spot_price", 4.5),
        confidence=0.75,
        reasons=[
            ActionReasonResponse(
                reason="Current price (₹4.50/kWh) is favorable for selling",
                factor="spot_price",
                value=4.5,
                threshold=4.0,
                contribution=0.35,
                direction="positive",
            ),
            ActionReasonResponse(
                reason="Battery SOC (80%) is above selling threshold",
                factor="soc",
                value=0.8,
                threshold=0.7,
                contribution=0.25,
                direction="positive",
            ),
        ],
        text_explanation="Decision: SELL 50 kWh @ ₹4.50/kWh\nConfidence: 75%\n\nKey Factors:\n  1. ✓ Current price favorable for selling\n  2. ✓ Battery SOC above threshold",
        alternative_actions=[
            AlternativeActionResponse(
                action="HOLD",
                expected_value=-2.5,
                probability=0.2,
                reasons=["Lower expected value than SELL"],
            ),
        ],
        feature_contributions={"spot_price": 0.35, "soc": 0.25, "volatility_1h": 0.15},
        action_probabilities={"HOLD": 0.2, "BUY": 0.05, "SELL": 0.75},
        risk_factors=["Moderate volatility (15%)"],
        expected_profit=12.5,
        expected_risk=3.0,
        counterfactual_analysis={"current_action": "SELL", "counterfactuals": {}},
        visualization_data=None,
        latency_ms=latency_ms,
    )


def _mock_model_summary(model_type: str, model_version: str):
    """Generate mock model summary."""
    return ModelSummaryResponse(
        model_name=f"{model_type}_model",
        model_version=model_version,
        model_type=model_type,
        feature_importance={
            "temperature": 0.20,
            "load_lag_1h": 0.18,
            "hour_sin": 0.15,
            "day_sin": 0.12,
            "is_weekend": 0.10,
            "humidity": 0.08,
            "grid_load": 0.07,
            "solar_irradiance": 0.05,
            "is_holiday": 0.03,
            "month_sin": 0.02,
        },
        top_features=["temperature", "load_lag_1h", "hour_sin", "day_sin", "is_weekend"],
        num_features=15,
        baseline_prediction=100.0,
        recent_accuracy=0.92,
        recent_mae=5.5,
        last_updated=datetime.now(),
    )
