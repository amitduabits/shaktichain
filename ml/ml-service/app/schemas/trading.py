"""Pydantic schemas for trading endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class TradingAction(str, Enum):
    """Trading action types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CHARGE = "charge"
    DISCHARGE = "discharge"


class BatteryState(BaseModel):
    """Battery state information."""

    soc: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="State of charge (0-1)"
    )
    capacity_kwh: float = Field(
        default=50.0,
        gt=0,
        description="Battery capacity in kWh"
    )
    max_charge_rate_kw: float = Field(
        default=11.0,
        gt=0,
        description="Maximum charge rate in kW"
    )
    max_discharge_rate_kw: float = Field(
        default=11.0,
        gt=0,
        description="Maximum discharge rate in kW"
    )
    efficiency: float = Field(
        default=0.95,
        gt=0,
        le=1.0,
        description="Round-trip efficiency"
    )
    degradation_cost: float = Field(
        default=0.02,
        ge=0,
        description="Degradation cost per kWh cycled"
    )


class MarketState(BaseModel):
    """Current market state."""

    current_price: float = Field(
        ...,
        description="Current energy price (INR/kWh)"
    )
    price_forecast: List[float] = Field(
        default_factory=list,
        description="Price forecast for next hours"
    )
    load_forecast: Optional[List[float]] = Field(
        default=None,
        description="Load forecast for next hours"
    )
    volatility: float = Field(
        default=0.1,
        ge=0,
        description="Current price volatility"
    )
    spread: float = Field(
        default=0.02,
        ge=0,
        description="Bid-ask spread"
    )


class TradingActionRequest(BaseModel):
    """Request schema for trading action recommendation."""

    timestamp: datetime = Field(
        ...,
        description="Current timestamp"
    )
    battery_state: BatteryState = Field(
        ...,
        description="Current battery state"
    )
    market_state: MarketState = Field(
        ...,
        description="Current market state"
    )
    vehicle_schedule: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Vehicle usage schedule"
    )
    min_soc_reserve: float = Field(
        default=0.2,
        ge=0,
        le=1,
        description="Minimum SOC to reserve for driving"
    )
    risk_tolerance: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Risk tolerance (0=conservative, 1=aggressive)"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Specific model version"
    )


class TradingActionResponse(BaseModel):
    """Response schema for trading action."""

    request_id: str = Field(..., description="Unique request identifier")
    model_version: str = Field(..., description="Model version used")
    action: TradingAction = Field(..., description="Recommended action")
    quantity_kwh: float = Field(
        ...,
        ge=0,
        description="Recommended quantity in kWh"
    )
    target_price: Optional[float] = Field(
        None,
        description="Recommended target price"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in recommendation"
    )
    expected_profit: float = Field(
        ...,
        description="Expected profit from action"
    )
    risk_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Risk metrics (VaR, etc.)"
    )
    alternative_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alternative actions considered"
    )
    explanation: str = Field(
        ...,
        description="Human-readable explanation"
    )
    latency_ms: float = Field(..., description="Processing latency in ms")


class BatchTradingRequest(BaseModel):
    """Batch trading action request."""

    requests: List[TradingActionRequest] = Field(
        ...,
        max_length=100,
        description="List of trading requests"
    )


class BatchTradingResponse(BaseModel):
    """Batch trading action response."""

    responses: List[TradingActionResponse]
    total_latency_ms: float


class PortfolioState(BaseModel):
    """Portfolio state for multi-vehicle optimization."""

    vehicles: List[Dict[str, Any]] = Field(
        ...,
        description="List of vehicles with battery states"
    )
    total_capacity_kwh: float = Field(
        ...,
        description="Total portfolio capacity"
    )
    aggregated_soc: float = Field(
        ...,
        description="Weighted average SOC"
    )


class PortfolioOptimizationRequest(BaseModel):
    """Request for portfolio optimization."""

    timestamp: datetime
    portfolio: PortfolioState
    market_state: MarketState
    optimization_horizon_hours: int = Field(default=24, ge=1, le=72)
    objective: str = Field(
        default="maximize_profit",
        description="Optimization objective"
    )


class PortfolioOptimizationResponse(BaseModel):
    """Portfolio optimization response."""

    request_id: str
    vehicle_actions: Dict[str, TradingActionResponse] = Field(
        ...,
        description="Actions for each vehicle"
    )
    aggregate_metrics: Dict[str, float]
    expected_total_profit: float
    latency_ms: float


class TradingPerformanceRequest(BaseModel):
    """Request for trading performance metrics."""

    start_date: datetime
    end_date: datetime
    vehicle_id: Optional[str] = None


class TradingPerformanceResponse(BaseModel):
    """Trading performance metrics."""

    period_start: datetime
    period_end: datetime
    total_trades: int
    total_profit: float
    roi_pct: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    metrics_by_action: Dict[str, Dict[str, float]]
