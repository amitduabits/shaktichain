"""Pydantic schemas for anomaly detection endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    """Types of anomalies."""
    WASH_TRADING = "wash_trading"
    PRICE_MANIPULATION = "price_manipulation"
    SPOOFING = "spoofing"
    VOLUME_SPIKE = "volume_spike"
    COORDINATED_TRADING = "coordinated_trading"
    FALSE_DELIVERY = "false_delivery"
    NON_DELIVERY = "non_delivery"
    ENERGY_DISCREPANCY = "energy_discrepancy"
    REPUTATION_MANIPULATION = "reputation_manipulation"
    UNUSUAL_REGISTRATION = "unusual_registration"
    SYBIL_CLUSTER = "sybil_cluster"
    UNKNOWN = "unknown"


class AlertLevel(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TradeData(BaseModel):
    """Trade data for anomaly scoring."""

    trade_id: str = Field(..., description="Unique trade identifier")
    buyer_id: str = Field(..., description="Buyer account ID")
    seller_id: str = Field(..., description="Seller account ID")
    price: float = Field(..., gt=0, description="Trade price")
    quantity: float = Field(..., gt=0, description="Trade quantity")
    energy_kwh: float = Field(..., ge=0, description="Energy in kWh")
    timestamp: datetime = Field(..., description="Trade timestamp")
    trade_type: str = Field(default="spot", description="Trade type")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional trade metadata"
    )


class DeliveryData(BaseModel):
    """Delivery data for anomaly scoring."""

    delivery_id: str = Field(..., description="Unique delivery ID")
    provider_id: str = Field(..., description="Energy provider ID")
    consumer_id: str = Field(..., description="Energy consumer ID")
    claimed_kwh: float = Field(..., ge=0, description="Claimed energy")
    actual_kwh: Optional[float] = Field(None, ge=0, description="Actual energy")
    scheduled_time: datetime = Field(..., description="Scheduled delivery time")
    actual_time: Optional[datetime] = Field(None, description="Actual delivery time")
    meter_reading: Optional[str] = Field(None, description="Meter reading reference")


class AccountData(BaseModel):
    """Account data for anomaly scoring."""

    account_id: str = Field(..., description="Account ID")
    account_type: str = Field(default="prosumer", description="Account type")
    created_at: datetime = Field(..., description="Account creation time")
    reputation: float = Field(default=0.5, ge=0, le=1, description="Reputation score")
    total_trades: int = Field(default=0, ge=0, description="Total trade count")
    total_volume: float = Field(default=0, ge=0, description="Total traded volume")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional account metadata"
    )


class AnomalyScoreRequest(BaseModel):
    """Request schema for anomaly scoring."""

    trade: Optional[TradeData] = Field(
        default=None,
        description="Trade to score"
    )
    delivery: Optional[DeliveryData] = Field(
        default=None,
        description="Delivery to score"
    )
    account: Optional[AccountData] = Field(
        default=None,
        description="Account to score"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context (history, network, etc.)"
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Specific model version"
    )


class AnomalyScoreDetail(BaseModel):
    """Detailed anomaly score breakdown."""

    anomaly_type: AnomalyType
    score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    contributing_factors: List[str] = Field(default_factory=list)


class AnomalyScoreResponse(BaseModel):
    """Response schema for anomaly scoring."""

    request_id: str = Field(..., description="Unique request identifier")
    model_version: str = Field(..., description="Model version used")
    anomaly_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Overall anomaly score (0=normal, 1=anomalous)"
    )
    alert_level: AlertLevel = Field(
        ...,
        description="Recommended alert level"
    )
    primary_anomaly_type: AnomalyType = Field(
        ...,
        description="Most likely anomaly type"
    )
    score_details: List[AnomalyScoreDetail] = Field(
        default_factory=list,
        description="Detailed score breakdown by type"
    )
    explanation: str = Field(
        ...,
        description="Human-readable explanation"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended actions"
    )
    latency_ms: float = Field(..., description="Processing latency in ms")


class BatchAnomalyRequest(BaseModel):
    """Batch anomaly scoring request."""

    trades: List[TradeData] = Field(
        default_factory=list,
        max_length=1000,
        description="Trades to score"
    )
    deliveries: List[DeliveryData] = Field(
        default_factory=list,
        max_length=1000,
        description="Deliveries to score"
    )
    accounts: List[AccountData] = Field(
        default_factory=list,
        max_length=1000,
        description="Accounts to score"
    )


class BatchAnomalyResponse(BaseModel):
    """Batch anomaly scoring response."""

    trade_scores: List[AnomalyScoreResponse] = Field(default_factory=list)
    delivery_scores: List[AnomalyScoreResponse] = Field(default_factory=list)
    account_scores: List[AnomalyScoreResponse] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics"
    )
    total_latency_ms: float


class NetworkAnalysisRequest(BaseModel):
    """Request for network/graph analysis."""

    account_ids: List[str] = Field(
        ...,
        max_length=100,
        description="Accounts to analyze"
    )
    include_neighbors: bool = Field(
        default=True,
        description="Include neighbor analysis"
    )
    depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Graph traversal depth"
    )


class NetworkAnalysisResponse(BaseModel):
    """Network analysis response."""

    request_id: str
    clusters: List[Dict[str, Any]] = Field(
        ...,
        description="Detected account clusters"
    )
    sybil_candidates: List[str] = Field(
        default_factory=list,
        description="Potential Sybil accounts"
    )
    coordination_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Overall coordination score"
    )
    graph_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Graph-level metrics"
    )
    latency_ms: float


class AlertConfigRequest(BaseModel):
    """Request to configure alert thresholds."""

    critical_threshold: float = Field(default=0.9, ge=0, le=1)
    high_threshold: float = Field(default=0.8, ge=0, le=1)
    medium_threshold: float = Field(default=0.6, ge=0, le=1)
    low_threshold: float = Field(default=0.4, ge=0, le=1)
    enabled_anomaly_types: List[AnomalyType] = Field(
        default_factory=lambda: list(AnomalyType)
    )


class AlertConfigResponse(BaseModel):
    """Alert configuration response."""

    config: AlertConfigRequest
    updated_at: datetime
