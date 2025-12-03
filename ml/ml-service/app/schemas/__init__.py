"""Pydantic schemas for ML Service API."""

from .forecast import (
    LoadForecastRequest,
    LoadForecastResponse,
    LoadForecastPoint,
    PriceForecastRequest,
    PriceForecastResponse,
    PriceForecastPoint,
    ForecastEvaluationRequest,
    ForecastEvaluationResponse,
)

from .trading import (
    TradingAction,
    BatteryState,
    MarketState,
    TradingActionRequest,
    TradingActionResponse,
    BatchTradingRequest,
    BatchTradingResponse,
    PortfolioState,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResponse,
    TradingPerformanceRequest,
    TradingPerformanceResponse,
)

from .anomaly import (
    AnomalyType,
    AlertLevel,
    TradeData,
    DeliveryData,
    AccountData,
    AnomalyScoreRequest,
    AnomalyScoreResponse,
    AnomalyScoreDetail,
    BatchAnomalyRequest,
    BatchAnomalyResponse,
    NetworkAnalysisRequest,
    NetworkAnalysisResponse,
    AlertConfigRequest,
    AlertConfigResponse,
)

__all__ = [
    # Forecast
    "LoadForecastRequest",
    "LoadForecastResponse",
    "LoadForecastPoint",
    "PriceForecastRequest",
    "PriceForecastResponse",
    "PriceForecastPoint",
    "ForecastEvaluationRequest",
    "ForecastEvaluationResponse",
    # Trading
    "TradingAction",
    "BatteryState",
    "MarketState",
    "TradingActionRequest",
    "TradingActionResponse",
    "BatchTradingRequest",
    "BatchTradingResponse",
    "PortfolioState",
    "PortfolioOptimizationRequest",
    "PortfolioOptimizationResponse",
    "TradingPerformanceRequest",
    "TradingPerformanceResponse",
    # Anomaly
    "AnomalyType",
    "AlertLevel",
    "TradeData",
    "DeliveryData",
    "AccountData",
    "AnomalyScoreRequest",
    "AnomalyScoreResponse",
    "AnomalyScoreDetail",
    "BatchAnomalyRequest",
    "BatchAnomalyResponse",
    "NetworkAnalysisRequest",
    "NetworkAnalysisResponse",
    "AlertConfigRequest",
    "AlertConfigResponse",
]
