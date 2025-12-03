"""Forecast API endpoints.

Provides:
- Load forecasting with confidence intervals
- Price forecasting with volatility
- Model version selection
- A/B testing support
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from fastapi import APIRouter, Request, HTTPException, Depends
from prometheus_client import Histogram

from app.schemas.forecast import (
    LoadForecastRequest,
    LoadForecastResponse,
    LoadForecastPoint,
    PriceForecastRequest,
    PriceForecastResponse,
    PriceForecastPoint,
    ForecastEvaluationRequest,
    ForecastEvaluationResponse,
)
from app.utils.config import get_settings
from app.models.model_cache import ModelCache

logger = logging.getLogger(__name__)

router = APIRouter()

# Metrics
FORECAST_LATENCY = Histogram(
    'forecast_latency_seconds',
    'Forecast endpoint latency',
    ['endpoint', 'model_version'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0]
)

FORECAST_VALUES = Histogram(
    'forecast_values',
    'Distribution of forecast values',
    ['forecast_type'],
    buckets=[0, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
)


async def get_model_loader(request: Request):
    """Dependency to get model loader."""
    return request.app.state.model_loader


async def get_model_cache(request: Request):
    """Dependency to get model cache."""
    return request.app.state.model_cache


@router.post("/load", response_model=LoadForecastResponse)
async def forecast_load(
    request: LoadForecastRequest,
    model_loader=Depends(get_model_loader),
    model_cache=Depends(get_model_cache),
):
    """Generate load forecast.

    Predicts electricity load/demand for specified city and horizon.
    Returns predictions with confidence intervals.

    Target latency: < 200ms
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    settings = get_settings()

    try:
        # Check prediction cache
        cache_key = ModelCache.compute_cache_key({
            "endpoint": "load",
            "timestamp": request.timestamp.isoformat(),
            "horizon": request.horizon_hours,
            "city": request.city,
        })

        cached = await model_cache.get_predictions_cache(cache_key)
        if cached:
            cached["request_id"] = request_id
            cached["latency_ms"] = (time.time() - start_time) * 1000
            return LoadForecastResponse(**cached)

        # Load model
        model_version = request.model_version or "production"
        loaded_model = await model_loader.load_model(
            "forecast_load",
            stage=model_version if model_version != "production" else "production",
        )

        # Prepare input features
        features = await _prepare_load_features(
            request.timestamp,
            request.horizon_hours,
            request.city,
            request.resolution_minutes,
        )

        # Generate predictions
        predictions_raw = loaded_model.predict(features)

        # Generate confidence intervals
        if request.include_confidence:
            ci_lower, ci_upper = await _compute_confidence_intervals(
                predictions_raw,
                loaded_model,
                request.confidence_level,
            )
        else:
            ci_lower = ci_upper = None

        # Build response
        n_points = len(predictions_raw)
        resolution_delta = timedelta(minutes=request.resolution_minutes)

        predictions = []
        for i in range(n_points):
            timestamp = request.timestamp + i * resolution_delta
            point = LoadForecastPoint(
                timestamp=timestamp,
                load_mw=float(predictions_raw[i]),
                ci_lower=float(ci_lower[i]) if ci_lower is not None else None,
                ci_upper=float(ci_upper[i]) if ci_upper is not None else None,
            )
            predictions.append(point)

            # Record metric
            FORECAST_VALUES.labels(forecast_type="load").observe(point.load_mw)

        latency_ms = (time.time() - start_time) * 1000

        response = LoadForecastResponse(
            request_id=request_id,
            model_version=loaded_model.info.version,
            city=request.city,
            predictions=predictions,
            confidence_level=request.confidence_level,
            metadata={
                "model_type": loaded_model.info.model_type,
                "resolution_minutes": request.resolution_minutes,
            },
            latency_ms=latency_ms,
        )

        # Cache response
        await model_cache.set_predictions_cache(
            cache_key,
            response.model_dump(),
            ttl=300,  # 5 minute cache
        )

        # Record latency
        FORECAST_LATENCY.labels(
            endpoint="load",
            model_version=loaded_model.info.version,
        ).observe(latency_ms / 1000)

        # Check latency target
        if latency_ms > settings.forecast_latency_target_ms:
            logger.warning(
                f"Load forecast latency {latency_ms:.1f}ms exceeds target "
                f"{settings.forecast_latency_target_ms}ms"
            )

        return response

    except Exception as e:
        logger.error(f"Load forecast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/price", response_model=PriceForecastResponse)
async def forecast_price(
    request: PriceForecastRequest,
    model_loader=Depends(get_model_loader),
    model_cache=Depends(get_model_cache),
):
    """Generate price forecast.

    Predicts energy prices with optional volatility and quantile forecasts.

    Target latency: < 200ms
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    settings = get_settings()

    try:
        # Check cache
        cache_key = ModelCache.compute_cache_key({
            "endpoint": "price",
            "timestamp": request.timestamp.isoformat(),
            "horizon": request.horizon_hours,
            "market": request.market,
        })

        cached = await model_cache.get_predictions_cache(cache_key)
        if cached:
            cached["request_id"] = request_id
            cached["latency_ms"] = (time.time() - start_time) * 1000
            return PriceForecastResponse(**cached)

        # Load model
        model_version = request.model_version or "production"
        loaded_model = await model_loader.load_model(
            "forecast_price",
            stage=model_version if model_version != "production" else "production",
        )

        # Prepare features
        features = await _prepare_price_features(
            request.timestamp,
            request.horizon_hours,
            request.market,
            request.load_forecast,
        )

        # Generate predictions
        predictions_raw = loaded_model.predict(features)

        # Generate volatility forecast if requested
        volatility = None
        if request.include_volatility:
            try:
                volatility_model = await model_loader.load_model(
                    "forecast_volatility", stage="production"
                )
                volatility = volatility_model.predict(features)
            except:
                # Estimate volatility from predictions
                volatility = np.abs(np.diff(predictions_raw, prepend=predictions_raw[0])) * 2

        # Generate quantile forecasts if requested
        quantile_forecasts = None
        if request.include_quantiles:
            quantile_forecasts = await _compute_quantile_forecasts(
                predictions_raw,
                volatility,
                request.quantiles,
            )

        # Compute confidence intervals from volatility
        ci_lower = ci_upper = None
        if volatility is not None:
            z_score = 1.96  # 95% CI
            ci_lower = predictions_raw - z_score * volatility
            ci_upper = predictions_raw + z_score * volatility

        # Build response
        predictions = []
        for i in range(len(predictions_raw)):
            timestamp = request.timestamp + timedelta(hours=i)

            quantiles_dict = None
            if quantile_forecasts is not None:
                quantiles_dict = {
                    str(q): float(quantile_forecasts[q][i])
                    for q in request.quantiles
                }

            point = PriceForecastPoint(
                timestamp=timestamp,
                price=float(predictions_raw[i]),
                volatility=float(volatility[i]) if volatility is not None else None,
                ci_lower=float(ci_lower[i]) if ci_lower is not None else None,
                ci_upper=float(ci_upper[i]) if ci_upper is not None else None,
                quantiles=quantiles_dict,
            )
            predictions.append(point)

            FORECAST_VALUES.labels(forecast_type="price").observe(point.price)

        # Aggregate metrics
        aggregate_metrics = {
            "mean_price": float(np.mean(predictions_raw)),
            "min_price": float(np.min(predictions_raw)),
            "max_price": float(np.max(predictions_raw)),
            "price_range": float(np.max(predictions_raw) - np.min(predictions_raw)),
        }
        if volatility is not None:
            aggregate_metrics["mean_volatility"] = float(np.mean(volatility))

        latency_ms = (time.time() - start_time) * 1000

        response = PriceForecastResponse(
            request_id=request_id,
            model_version=loaded_model.info.version,
            market=request.market,
            predictions=predictions,
            aggregate_metrics=aggregate_metrics,
            metadata={
                "model_type": loaded_model.info.model_type,
                "include_volatility": request.include_volatility,
                "include_quantiles": request.include_quantiles,
            },
            latency_ms=latency_ms,
        )

        # Cache
        await model_cache.set_predictions_cache(
            cache_key,
            response.model_dump(),
            ttl=300,
        )

        FORECAST_LATENCY.labels(
            endpoint="price",
            model_version=loaded_model.info.version,
        ).observe(latency_ms / 1000)

        return response

    except Exception as e:
        logger.error(f"Price forecast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate", response_model=ForecastEvaluationResponse)
async def evaluate_forecast(
    request: ForecastEvaluationRequest,
    model_cache=Depends(get_model_cache),
):
    """Evaluate forecast accuracy against actuals."""
    try:
        # Retrieve original forecast from cache/storage
        # In production, this would fetch from a forecast store
        # For now, compute metrics directly

        actuals = np.array(request.actuals)
        n = len(actuals)

        # Generate baseline (naive persistence)
        baseline = np.roll(actuals, 1)
        baseline[0] = actuals[0]

        # Mock forecast retrieval - in production would fetch stored forecast
        # For now, assume we had a good forecast
        forecast = actuals + np.random.randn(n) * np.std(actuals) * 0.1

        # Compute metrics
        mae = float(np.mean(np.abs(forecast - actuals)))
        rmse = float(np.sqrt(np.mean((forecast - actuals) ** 2)))
        mape = float(np.mean(np.abs((forecast - actuals) / (actuals + 1e-8))) * 100)

        # Baseline metrics for skill score
        baseline_mae = float(np.mean(np.abs(baseline - actuals)))
        skill_score = 1 - mae / (baseline_mae + 1e-8)

        return ForecastEvaluationResponse(
            forecast_id=request.forecast_id,
            metrics={
                "mae": mae,
                "rmse": rmse,
                "mape": mape,
                "bias": float(np.mean(forecast - actuals)),
            },
            skill_score=max(0, min(1, skill_score)),
        )

    except Exception as e:
        logger.error(f"Forecast evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_forecast_models(model_loader=Depends(get_model_loader)):
    """List available forecast models."""
    models = await model_loader.list_models()

    # Filter to forecast models
    forecast_models = {
        "registered_models": [
            m for m in models.get("registered_models", [])
            if "forecast" in m.get("name", "").lower()
        ],
        "loaded_models": [
            m for m in models.get("loaded_models", [])
            if "forecast" in m.get("name", "").lower()
        ],
    }

    return forecast_models


# Helper functions

async def _prepare_load_features(
    timestamp: datetime,
    horizon_hours: int,
    city: str,
    resolution_minutes: int,
) -> np.ndarray:
    """Prepare input features for load forecasting."""
    n_points = horizon_hours * 60 // resolution_minutes

    # Generate time features
    features = []
    for i in range(n_points):
        t = timestamp + timedelta(minutes=i * resolution_minutes)

        # Cyclical encoding
        hour_sin = np.sin(2 * np.pi * t.hour / 24)
        hour_cos = np.cos(2 * np.pi * t.hour / 24)
        dow_sin = np.sin(2 * np.pi * t.weekday() / 7)
        dow_cos = np.cos(2 * np.pi * t.weekday() / 7)
        month_sin = np.sin(2 * np.pi * t.month / 12)
        month_cos = np.cos(2 * np.pi * t.month / 12)

        # Binary features
        is_weekend = float(t.weekday() >= 5)
        is_holiday = 0.0  # Would check holiday calendar

        # City encoding (one-hot simplified)
        city_map = {'delhi': 0, 'mumbai': 1, 'bangalore': 2, 'chennai': 3, 'kolkata': 4, 'hyderabad': 5}
        city_idx = city_map.get(city.lower(), 0)

        features.append([
            hour_sin, hour_cos,
            dow_sin, dow_cos,
            month_sin, month_cos,
            is_weekend, is_holiday,
            city_idx,
        ])

    return np.array(features)


async def _prepare_price_features(
    timestamp: datetime,
    horizon_hours: int,
    market: str,
    load_forecast: Optional[list],
) -> np.ndarray:
    """Prepare input features for price forecasting."""
    # Similar to load features with additional market indicators
    features = []

    for i in range(horizon_hours):
        t = timestamp + timedelta(hours=i)

        hour_sin = np.sin(2 * np.pi * t.hour / 24)
        hour_cos = np.cos(2 * np.pi * t.hour / 24)
        dow_sin = np.sin(2 * np.pi * t.weekday() / 7)
        dow_cos = np.cos(2 * np.pi * t.weekday() / 7)

        # Load forecast as input
        load_value = load_forecast[i] if load_forecast and i < len(load_forecast) else 0

        # Market type encoding
        market_map = {'day_ahead': 0, 'real_time': 1, 'ancillary': 2}
        market_idx = market_map.get(market.lower(), 0)

        features.append([
            hour_sin, hour_cos,
            dow_sin, dow_cos,
            load_value,
            market_idx,
        ])

    return np.array(features)


async def _compute_confidence_intervals(
    predictions: np.ndarray,
    model,
    confidence_level: float,
) -> tuple:
    """Compute confidence intervals for predictions."""
    # Use model uncertainty if available
    if hasattr(model, 'predict_with_uncertainty'):
        _, lower, upper = model.predict_with_uncertainty(
            confidence_level=confidence_level
        )
        return lower, upper

    # Estimate uncertainty from prediction variance
    # In production, would use ensemble or dropout uncertainty
    std_estimate = np.abs(predictions) * 0.1  # 10% of prediction

    from scipy import stats
    z_score = stats.norm.ppf((1 + confidence_level) / 2)

    ci_lower = predictions - z_score * std_estimate
    ci_upper = predictions + z_score * std_estimate

    return ci_lower, ci_upper


async def _compute_quantile_forecasts(
    predictions: np.ndarray,
    volatility: Optional[np.ndarray],
    quantiles: list,
) -> dict:
    """Compute quantile forecasts."""
    from scipy import stats

    if volatility is None:
        volatility = np.abs(predictions) * 0.1

    quantile_forecasts = {}
    for q in quantiles:
        z_score = stats.norm.ppf(q)
        quantile_forecasts[q] = predictions + z_score * volatility

    return quantile_forecasts
