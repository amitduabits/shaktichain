"""Pydantic schemas for forecast endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class LoadForecastRequest(BaseModel):
    """Request schema for load forecasting."""

    timestamp: datetime = Field(
        ...,
        description="Forecast start timestamp (ISO 8601 format)"
    )
    horizon_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Forecast horizon in hours (1-168)"
    )
    city: str = Field(
        default="delhi",
        description="City for load forecast"
    )
    resolution_minutes: int = Field(
        default=60,
        description="Forecast resolution in minutes"
    )
    include_confidence: bool = Field(
        default=True,
        description="Include confidence intervals"
    )
    confidence_level: float = Field(
        default=0.95,
        ge=0.5,
        le=0.99,
        description="Confidence level for intervals"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Specific model version to use"
    )

    @field_validator('city')
    @classmethod
    def validate_city(cls, v: str) -> str:
        valid_cities = ['delhi', 'mumbai', 'bangalore', 'chennai', 'kolkata', 'hyderabad']
        v = v.lower()
        if v not in valid_cities:
            raise ValueError(f"City must be one of: {valid_cities}")
        return v


class LoadForecastPoint(BaseModel):
    """Single forecast point."""

    timestamp: datetime
    load_mw: float = Field(..., description="Predicted load in MW")
    ci_lower: Optional[float] = Field(None, description="Lower confidence bound")
    ci_upper: Optional[float] = Field(None, description="Upper confidence bound")


class LoadForecastResponse(BaseModel):
    """Response schema for load forecasting."""

    request_id: str = Field(..., description="Unique request identifier")
    model_version: str = Field(..., description="Model version used")
    city: str = Field(..., description="City")
    predictions: List[LoadForecastPoint] = Field(..., description="Forecast points")
    confidence_level: float = Field(..., description="Confidence level")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    latency_ms: float = Field(..., description="Processing latency in ms")


class PriceForecastRequest(BaseModel):
    """Request schema for price forecasting."""

    timestamp: datetime = Field(
        ...,
        description="Forecast start timestamp"
    )
    horizon_hours: int = Field(
        default=24,
        ge=1,
        le=72,
        description="Forecast horizon in hours (1-72)"
    )
    load_forecast: Optional[List[float]] = Field(
        default=None,
        description="Optional load forecast to condition on"
    )
    market: str = Field(
        default="day_ahead",
        description="Market type (day_ahead, real_time, ancillary)"
    )
    include_volatility: bool = Field(
        default=True,
        description="Include volatility forecast"
    )
    include_quantiles: bool = Field(
        default=False,
        description="Include quantile forecasts"
    )
    quantiles: List[float] = Field(
        default=[0.1, 0.25, 0.5, 0.75, 0.9],
        description="Quantiles to forecast"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Specific model version"
    )

    @field_validator('market')
    @classmethod
    def validate_market(cls, v: str) -> str:
        valid_markets = ['day_ahead', 'real_time', 'ancillary']
        v = v.lower()
        if v not in valid_markets:
            raise ValueError(f"Market must be one of: {valid_markets}")
        return v


class PriceForecastPoint(BaseModel):
    """Single price forecast point."""

    timestamp: datetime
    price: float = Field(..., description="Predicted price (INR/kWh)")
    volatility: Optional[float] = Field(None, description="Predicted volatility")
    ci_lower: Optional[float] = Field(None, description="Lower confidence bound")
    ci_upper: Optional[float] = Field(None, description="Upper confidence bound")
    quantiles: Optional[Dict[str, float]] = Field(
        None,
        description="Quantile forecasts"
    )


class PriceForecastResponse(BaseModel):
    """Response schema for price forecasting."""

    request_id: str = Field(..., description="Unique request identifier")
    model_version: str = Field(..., description="Model version used")
    market: str = Field(..., description="Market type")
    predictions: List[PriceForecastPoint] = Field(..., description="Forecast points")
    aggregate_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Aggregate forecast metrics"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    latency_ms: float = Field(..., description="Processing latency in ms")


class ForecastEvaluationRequest(BaseModel):
    """Request to evaluate forecast accuracy."""

    forecast_id: str = Field(..., description="Original forecast request ID")
    actuals: List[float] = Field(..., description="Actual observed values")


class ForecastEvaluationResponse(BaseModel):
    """Forecast evaluation results."""

    forecast_id: str
    metrics: Dict[str, float] = Field(
        ...,
        description="Evaluation metrics (MAE, RMSE, MAPE, etc.)"
    )
    skill_score: float = Field(
        ...,
        description="Skill score vs naive baseline"
    )
