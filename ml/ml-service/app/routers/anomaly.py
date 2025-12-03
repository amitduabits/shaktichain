"""Anomaly detection API endpoints.

Provides:
- Trade anomaly scoring
- Delivery verification
- Account risk assessment
- Network analysis
"""

import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
from fastapi import APIRouter, Request, HTTPException, Depends
from prometheus_client import Histogram, Counter

from app.schemas.anomaly import (
    AnomalyType,
    AlertLevel,
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
from app.utils.config import get_settings
from app.models.model_cache import ModelCache

logger = logging.getLogger(__name__)

router = APIRouter()

# Alert thresholds (configurable)
ALERT_THRESHOLDS = {
    "critical": 0.9,
    "high": 0.8,
    "medium": 0.6,
    "low": 0.4,
}

# Metrics
ANOMALY_LATENCY = Histogram(
    'anomaly_latency_seconds',
    'Anomaly detection latency',
    ['endpoint', 'model_version'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.2, 0.5]
)

ANOMALY_SCORES = Histogram(
    'anomaly_scores',
    'Distribution of anomaly scores',
    ['anomaly_type'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

ALERTS_GENERATED = Counter(
    'anomaly_alerts_total',
    'Count of alerts generated',
    ['alert_level', 'anomaly_type']
)


async def get_model_loader(request: Request):
    """Dependency to get model loader."""
    return request.app.state.model_loader


async def get_model_cache(request: Request):
    """Dependency to get model cache."""
    return request.app.state.model_cache


@router.post("/score", response_model=AnomalyScoreResponse)
async def score_anomaly(
    request: AnomalyScoreRequest,
    model_loader=Depends(get_model_loader),
    model_cache=Depends(get_model_cache),
):
    """Score entity for anomalies.

    Analyzes trades, deliveries, or accounts for suspicious patterns.
    Returns anomaly score and explanation.

    Target latency: < 100ms
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    settings = get_settings()

    try:
        # Determine entity type and extract data
        if request.trade:
            entity_type = "trade"
            entity_data = request.trade.model_dump()
            model_name = "anomaly_trade"
        elif request.delivery:
            entity_type = "delivery"
            entity_data = request.delivery.model_dump()
            model_name = "anomaly_delivery"
        elif request.account:
            entity_type = "account"
            entity_data = request.account.model_dump()
            model_name = "anomaly_account"
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide trade, delivery, or account data"
            )

        # Load appropriate model
        model_version = request.model_version or "production"
        loaded_model = await model_loader.load_model(
            model_name,
            stage=model_version if model_version != "production" else "production",
        )

        # Prepare features
        features = await _prepare_anomaly_features(
            entity_type,
            entity_data,
            request.context,
        )

        # Score with model
        if hasattr(loaded_model.model, 'score'):
            anomaly_score = float(loaded_model.model.score(features))
        elif hasattr(loaded_model.model, 'predict_proba'):
            proba = loaded_model.model.predict_proba(features.reshape(1, -1))
            anomaly_score = float(proba[0, 1]) if proba.shape[1] > 1 else float(proba[0, 0])
        elif hasattr(loaded_model.model, 'decision_function'):
            # Isolation Forest style
            score_raw = loaded_model.model.decision_function(features.reshape(1, -1))
            # Convert to 0-1 (more negative = more anomalous)
            anomaly_score = float(1 / (1 + np.exp(score_raw[0])))
        else:
            # Mock scoring
            anomaly_score = await _heuristic_anomaly_score(entity_type, entity_data)

        # Determine primary anomaly type
        primary_type, score_details = await _analyze_anomaly_type(
            entity_type,
            entity_data,
            anomaly_score,
            request.context,
        )

        # Determine alert level
        alert_level = _score_to_alert_level(anomaly_score)

        # Generate explanation
        explanation = await _generate_anomaly_explanation(
            entity_type,
            entity_data,
            primary_type,
            anomaly_score,
            score_details,
        )

        # Generate recommendations
        recommendations = await _generate_recommendations(
            primary_type,
            alert_level,
            entity_type,
        )

        latency_ms = (time.time() - start_time) * 1000

        response = AnomalyScoreResponse(
            request_id=request_id,
            model_version=loaded_model.info.version,
            anomaly_score=anomaly_score,
            alert_level=alert_level,
            primary_anomaly_type=primary_type,
            score_details=score_details,
            explanation=explanation,
            recommendations=recommendations,
            latency_ms=latency_ms,
        )

        # Record metrics
        ANOMALY_LATENCY.labels(
            endpoint="score",
            model_version=loaded_model.info.version,
        ).observe(latency_ms / 1000)

        ANOMALY_SCORES.labels(anomaly_type=primary_type.value).observe(anomaly_score)

        if alert_level != AlertLevel.INFO:
            ALERTS_GENERATED.labels(
                alert_level=alert_level.value,
                anomaly_type=primary_type.value,
            ).inc()

        # Check latency target
        if latency_ms > settings.anomaly_latency_target_ms:
            logger.warning(
                f"Anomaly scoring latency {latency_ms:.1f}ms exceeds target "
                f"{settings.anomaly_latency_target_ms}ms"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anomaly scoring failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchAnomalyResponse)
async def batch_score_anomalies(
    request: BatchAnomalyRequest,
    model_loader=Depends(get_model_loader),
):
    """Score multiple entities for anomalies."""
    start_time = time.time()

    trade_scores = []
    delivery_scores = []
    account_scores = []

    # Score trades
    for trade in request.trades:
        try:
            score_request = AnomalyScoreRequest(trade=trade)
            response = await score_anomaly(score_request, model_loader, None)
            trade_scores.append(response)
        except Exception as e:
            logger.error(f"Trade scoring failed: {e}")

    # Score deliveries
    for delivery in request.deliveries:
        try:
            score_request = AnomalyScoreRequest(delivery=delivery)
            response = await score_anomaly(score_request, model_loader, None)
            delivery_scores.append(response)
        except Exception as e:
            logger.error(f"Delivery scoring failed: {e}")

    # Score accounts
    for account in request.accounts:
        try:
            score_request = AnomalyScoreRequest(account=account)
            response = await score_anomaly(score_request, model_loader, None)
            account_scores.append(response)
        except Exception as e:
            logger.error(f"Account scoring failed: {e}")

    # Compute summary
    all_scores = (
        [s.anomaly_score for s in trade_scores] +
        [s.anomaly_score for s in delivery_scores] +
        [s.anomaly_score for s in account_scores]
    )

    summary = {
        "total_scored": len(all_scores),
        "high_risk_count": sum(1 for s in all_scores if s > ALERT_THRESHOLDS["high"]),
        "medium_risk_count": sum(
            1 for s in all_scores
            if ALERT_THRESHOLDS["medium"] < s <= ALERT_THRESHOLDS["high"]
        ),
        "avg_score": float(np.mean(all_scores)) if all_scores else 0,
        "max_score": float(np.max(all_scores)) if all_scores else 0,
    }

    total_latency = (time.time() - start_time) * 1000

    return BatchAnomalyResponse(
        trade_scores=trade_scores,
        delivery_scores=delivery_scores,
        account_scores=account_scores,
        summary=summary,
        total_latency_ms=total_latency,
    )


@router.post("/network/analyze", response_model=NetworkAnalysisResponse)
async def analyze_network(
    request: NetworkAnalysisRequest,
    model_loader=Depends(get_model_loader),
):
    """Analyze trading network for coordinated behavior."""
    start_time = time.time()
    request_id = str(uuid.uuid4())

    try:
        # Load graph anomaly model
        loaded_model = await model_loader.load_model(
            "anomaly_graph",
            stage="production",
        )

        # In production, would fetch network data from database
        # For now, generate mock analysis
        clusters = await _detect_clusters(
            request.account_ids,
            request.depth,
        )

        sybil_candidates = await _detect_sybil_candidates(
            request.account_ids,
            clusters,
        )

        coordination_score = await _compute_coordination_score(
            request.account_ids,
            clusters,
        )

        graph_metrics = {
            "density": 0.15,
            "avg_clustering": 0.35,
            "modularity": 0.45,
            "num_components": len(clusters),
        }

        latency_ms = (time.time() - start_time) * 1000

        return NetworkAnalysisResponse(
            request_id=request_id,
            clusters=clusters,
            sybil_candidates=sybil_candidates,
            coordination_score=coordination_score,
            graph_metrics=graph_metrics,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Network analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=AlertConfigResponse)
async def get_alert_config():
    """Get current alert configuration."""
    return AlertConfigResponse(
        config=AlertConfigRequest(
            critical_threshold=ALERT_THRESHOLDS["critical"],
            high_threshold=ALERT_THRESHOLDS["high"],
            medium_threshold=ALERT_THRESHOLDS["medium"],
            low_threshold=ALERT_THRESHOLDS["low"],
        ),
        updated_at=datetime.now(),
    )


@router.post("/config", response_model=AlertConfigResponse)
async def update_alert_config(config: AlertConfigRequest):
    """Update alert configuration."""
    global ALERT_THRESHOLDS

    ALERT_THRESHOLDS["critical"] = config.critical_threshold
    ALERT_THRESHOLDS["high"] = config.high_threshold
    ALERT_THRESHOLDS["medium"] = config.medium_threshold
    ALERT_THRESHOLDS["low"] = config.low_threshold

    return AlertConfigResponse(
        config=config,
        updated_at=datetime.now(),
    )


@router.get("/models")
async def list_anomaly_models(model_loader=Depends(get_model_loader)):
    """List available anomaly detection models."""
    models = await model_loader.list_models()

    anomaly_models = {
        "registered_models": [
            m for m in models.get("registered_models", [])
            if "anomaly" in m.get("name", "").lower()
        ],
        "loaded_models": [
            m for m in models.get("loaded_models", [])
            if "anomaly" in m.get("name", "").lower()
        ],
    }

    return anomaly_models


# Helper functions

async def _prepare_anomaly_features(
    entity_type: str,
    entity_data: dict,
    context: Optional[dict],
) -> np.ndarray:
    """Prepare features for anomaly detection."""
    features = []

    if entity_type == "trade":
        # Trade features
        features.extend([
            entity_data.get("price", 0) / 10,  # Normalize
            entity_data.get("quantity", 0) / 100,
            entity_data.get("energy_kwh", 0) / 1000,
        ])

        # Time features
        timestamp = entity_data.get("timestamp")
        if isinstance(timestamp, datetime):
            features.extend([
                np.sin(2 * np.pi * timestamp.hour / 24),
                np.cos(2 * np.pi * timestamp.hour / 24),
                float(timestamp.weekday() >= 5),  # Weekend
            ])
        else:
            features.extend([0, 0, 0])

        # Context features
        if context:
            features.extend([
                context.get("account_age_days", 30) / 365,
                context.get("total_trades", 10) / 100,
                context.get("avg_trade_size", 50) / 100,
            ])
        else:
            features.extend([0.5, 0.5, 0.5])

    elif entity_type == "delivery":
        claimed = entity_data.get("claimed_kwh", 0)
        actual = entity_data.get("actual_kwh", claimed)
        discrepancy = abs(claimed - actual) / (claimed + 1e-8)

        features.extend([
            claimed / 100,
            actual / 100 if actual else claimed / 100,
            discrepancy,
        ])

    elif entity_type == "account":
        features.extend([
            entity_data.get("reputation", 0.5),
            entity_data.get("total_trades", 0) / 100,
            entity_data.get("total_volume", 0) / 10000,
        ])

        # Account age
        created_at = entity_data.get("created_at")
        if isinstance(created_at, datetime):
            age_days = (datetime.now() - created_at).days
            features.append(age_days / 365)
        else:
            features.append(0.5)

    # Pad to fixed size
    while len(features) < 20:
        features.append(0)

    return np.array(features[:20], dtype=np.float32)


async def _heuristic_anomaly_score(entity_type: str, entity_data: dict) -> float:
    """Compute heuristic anomaly score when model unavailable."""
    score = 0.0

    if entity_type == "trade":
        price = entity_data.get("price", 0)
        quantity = entity_data.get("quantity", 0)

        # High price anomaly
        if price > 0.5:  # Extremely high
            score += 0.3

        # Volume anomaly
        if quantity > 500:
            score += 0.3

        # Time anomaly (late night)
        timestamp = entity_data.get("timestamp")
        if isinstance(timestamp, datetime):
            if 2 <= timestamp.hour <= 5:
                score += 0.1

    elif entity_type == "delivery":
        claimed = entity_data.get("claimed_kwh", 0)
        actual = entity_data.get("actual_kwh", claimed)

        if claimed > 0:
            discrepancy_pct = abs(claimed - actual) / claimed
            if discrepancy_pct > 0.2:
                score += min(0.5, discrepancy_pct)

    elif entity_type == "account":
        reputation = entity_data.get("reputation", 0.5)
        trades = entity_data.get("total_trades", 0)

        # Low reputation
        if reputation < 0.3:
            score += 0.2

        # Very new account with high activity
        created_at = entity_data.get("created_at")
        if isinstance(created_at, datetime):
            age_days = (datetime.now() - created_at).days
            if age_days < 7 and trades > 50:
                score += 0.3

    return min(1.0, score)


async def _analyze_anomaly_type(
    entity_type: str,
    entity_data: dict,
    overall_score: float,
    context: Optional[dict],
) -> tuple:
    """Analyze specific anomaly types."""
    score_details = []

    if entity_type == "trade":
        # Wash trading check
        wash_score = 0.0
        if context and context.get("same_counterparty_trades", 0) > 5:
            wash_score = min(1.0, context.get("same_counterparty_trades", 0) / 10)
        score_details.append(AnomalyScoreDetail(
            anomaly_type=AnomalyType.WASH_TRADING,
            score=wash_score,
            confidence=0.7,
            contributing_factors=["repeated counterparty"] if wash_score > 0.3 else [],
        ))

        # Price manipulation check
        price = entity_data.get("price", 0)
        price_score = min(1.0, max(0, (price - 0.2) / 0.3)) if price > 0.2 else 0
        score_details.append(AnomalyScoreDetail(
            anomaly_type=AnomalyType.PRICE_MANIPULATION,
            score=price_score,
            confidence=0.6,
            contributing_factors=["extreme price"] if price_score > 0.3 else [],
        ))

        # Volume spike check
        quantity = entity_data.get("quantity", 0)
        volume_score = min(1.0, quantity / 500) if quantity > 100 else 0
        score_details.append(AnomalyScoreDetail(
            anomaly_type=AnomalyType.VOLUME_SPIKE,
            score=volume_score,
            confidence=0.8,
            contributing_factors=["high volume"] if volume_score > 0.3 else [],
        ))

    elif entity_type == "delivery":
        claimed = entity_data.get("claimed_kwh", 0)
        actual = entity_data.get("actual_kwh", claimed)
        discrepancy = abs(claimed - actual) / (claimed + 1e-8)

        score_details.append(AnomalyScoreDetail(
            anomaly_type=AnomalyType.ENERGY_DISCREPANCY,
            score=min(1.0, discrepancy * 2),
            confidence=0.9,
            contributing_factors=[f"{discrepancy*100:.1f}% discrepancy"] if discrepancy > 0.1 else [],
        ))

        if actual < claimed * 0.5:
            score_details.append(AnomalyScoreDetail(
                anomaly_type=AnomalyType.FALSE_DELIVERY,
                score=min(1.0, (claimed - actual) / claimed),
                confidence=0.8,
                contributing_factors=["significant underdelivery"],
            ))

    elif entity_type == "account":
        # Reputation manipulation
        rep = entity_data.get("reputation", 0.5)
        rep_score = 0.0
        if context and context.get("reputation_change_30d", 0) > 0.3:
            rep_score = min(1.0, context.get("reputation_change_30d", 0))
        score_details.append(AnomalyScoreDetail(
            anomaly_type=AnomalyType.REPUTATION_MANIPULATION,
            score=rep_score,
            confidence=0.7,
            contributing_factors=["rapid reputation change"] if rep_score > 0.3 else [],
        ))

        # Sybil check
        sybil_score = 0.0
        if context and context.get("similar_accounts", 0) > 3:
            sybil_score = min(1.0, context.get("similar_accounts", 0) / 5)
        score_details.append(AnomalyScoreDetail(
            anomaly_type=AnomalyType.SYBIL_CLUSTER,
            score=sybil_score,
            confidence=0.6,
            contributing_factors=["similar account patterns"] if sybil_score > 0.3 else [],
        ))

    # Determine primary type
    if score_details:
        primary = max(score_details, key=lambda x: x.score)
        primary_type = primary.anomaly_type
    else:
        primary_type = AnomalyType.UNKNOWN

    return primary_type, score_details


def _score_to_alert_level(score: float) -> AlertLevel:
    """Convert anomaly score to alert level."""
    if score >= ALERT_THRESHOLDS["critical"]:
        return AlertLevel.CRITICAL
    elif score >= ALERT_THRESHOLDS["high"]:
        return AlertLevel.HIGH
    elif score >= ALERT_THRESHOLDS["medium"]:
        return AlertLevel.MEDIUM
    elif score >= ALERT_THRESHOLDS["low"]:
        return AlertLevel.LOW
    else:
        return AlertLevel.INFO


async def _generate_anomaly_explanation(
    entity_type: str,
    entity_data: dict,
    primary_type: AnomalyType,
    score: float,
    details: List[AnomalyScoreDetail],
) -> str:
    """Generate human-readable explanation."""
    if score < 0.3:
        return f"No significant anomalies detected. Overall risk score: {score:.2f}"

    explanation = f"Anomaly detected with score {score:.2f}. "

    if primary_type == AnomalyType.WASH_TRADING:
        explanation += "Pattern consistent with wash trading (trades between related parties)."
    elif primary_type == AnomalyType.PRICE_MANIPULATION:
        explanation += f"Price of ₹{entity_data.get('price', 0):.2f} is significantly above normal range."
    elif primary_type == AnomalyType.VOLUME_SPIKE:
        explanation += f"Volume of {entity_data.get('quantity', 0):.1f} units is unusually high."
    elif primary_type == AnomalyType.ENERGY_DISCREPANCY:
        claimed = entity_data.get('claimed_kwh', 0)
        actual = entity_data.get('actual_kwh', claimed)
        explanation += f"Energy discrepancy: claimed {claimed:.1f} kWh vs actual {actual:.1f} kWh."
    elif primary_type == AnomalyType.FALSE_DELIVERY:
        explanation += "Delivery appears to be significantly under-fulfilled or false."
    elif primary_type == AnomalyType.REPUTATION_MANIPULATION:
        explanation += "Account shows signs of artificial reputation inflation."
    elif primary_type == AnomalyType.SYBIL_CLUSTER:
        explanation += "Account may be part of a coordinated Sybil cluster."
    else:
        explanation += f"Anomaly type: {primary_type.value}"

    # Add contributing factors
    factors = []
    for detail in details:
        if detail.score > 0.3:
            factors.extend(detail.contributing_factors)

    if factors:
        explanation += f" Contributing factors: {', '.join(factors)}."

    return explanation


async def _generate_recommendations(
    anomaly_type: AnomalyType,
    alert_level: AlertLevel,
    entity_type: str,
) -> List[str]:
    """Generate recommended actions."""
    recommendations = []

    if alert_level == AlertLevel.CRITICAL:
        recommendations.append("Immediately flag for manual review")
        recommendations.append("Consider temporary suspension pending investigation")

    if alert_level in [AlertLevel.CRITICAL, AlertLevel.HIGH]:
        recommendations.append("Notify compliance team")

    if anomaly_type == AnomalyType.WASH_TRADING:
        recommendations.append("Analyze counterparty relationships")
        recommendations.append("Check for common ownership indicators")

    elif anomaly_type == AnomalyType.PRICE_MANIPULATION:
        recommendations.append("Compare with market reference prices")
        recommendations.append("Review recent price history")

    elif anomaly_type in [AnomalyType.ENERGY_DISCREPANCY, AnomalyType.FALSE_DELIVERY]:
        recommendations.append("Request meter verification")
        recommendations.append("Cross-check with grid operator data")

    elif anomaly_type == AnomalyType.SYBIL_CLUSTER:
        recommendations.append("Analyze network connections")
        recommendations.append("Check registration metadata for patterns")

    if alert_level in [AlertLevel.MEDIUM, AlertLevel.LOW]:
        recommendations.append("Add to monitoring watchlist")
        recommendations.append("Track for pattern development")

    return recommendations


async def _detect_clusters(
    account_ids: List[str],
    depth: int,
) -> List[Dict[str, Any]]:
    """Detect clusters in trading network."""
    # Mock cluster detection
    # In production, would use graph algorithms on actual trading data
    clusters = []

    if len(account_ids) >= 3:
        # Create mock cluster
        clusters.append({
            "cluster_id": "cluster_001",
            "members": account_ids[:3],
            "density": 0.8,
            "risk_score": 0.45,
        })

    if len(account_ids) >= 5:
        clusters.append({
            "cluster_id": "cluster_002",
            "members": account_ids[3:5] if len(account_ids) > 3 else [],
            "density": 0.6,
            "risk_score": 0.3,
        })

    return clusters


async def _detect_sybil_candidates(
    account_ids: List[str],
    clusters: List[Dict],
) -> List[str]:
    """Detect potential Sybil accounts."""
    sybil_candidates = []

    for cluster in clusters:
        if cluster.get("density", 0) > 0.7 and len(cluster.get("members", [])) >= 3:
            # High density small cluster - potential Sybil
            sybil_candidates.extend(cluster.get("members", []))

    return list(set(sybil_candidates))


async def _compute_coordination_score(
    account_ids: List[str],
    clusters: List[Dict],
) -> float:
    """Compute overall coordination score."""
    if not clusters:
        return 0.0

    # Weighted average of cluster risk scores
    total_weight = 0
    weighted_score = 0

    for cluster in clusters:
        members = len(cluster.get("members", []))
        risk = cluster.get("risk_score", 0)
        weighted_score += members * risk
        total_weight += members

    return weighted_score / (total_weight + 1e-8)
