"""Trading API endpoints.

Provides:
- Trading action recommendations
- Batch trading requests
- Portfolio optimization
- Performance tracking
"""

import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, Request, HTTPException, Depends
from prometheus_client import Histogram, Counter

from app.schemas.trading import (
    TradingAction,
    TradingActionRequest,
    TradingActionResponse,
    BatchTradingRequest,
    BatchTradingResponse,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResponse,
    TradingPerformanceRequest,
    TradingPerformanceResponse,
)
from app.utils.config import get_settings
from app.models.model_cache import ModelCache

logger = logging.getLogger(__name__)

router = APIRouter()

# Metrics
TRADING_LATENCY = Histogram(
    'trading_latency_seconds',
    'Trading endpoint latency',
    ['endpoint', 'model_version'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.2]
)

TRADING_ACTIONS = Counter(
    'trading_actions_total',
    'Count of trading actions',
    ['action', 'model_version']
)

TRADING_QUANTITIES = Histogram(
    'trading_quantities_kwh',
    'Distribution of trading quantities',
    ['action'],
    buckets=[0, 1, 5, 10, 20, 50, 100]
)


async def get_model_loader(request: Request):
    """Dependency to get model loader."""
    return request.app.state.model_loader


async def get_model_cache(request: Request):
    """Dependency to get model cache."""
    return request.app.state.model_cache


@router.post("/action", response_model=TradingActionResponse)
async def get_trading_action(
    request: TradingActionRequest,
    model_loader=Depends(get_model_loader),
    model_cache=Depends(get_model_cache),
):
    """Get trading action recommendation.

    Uses RL agent to recommend optimal trading action based on
    current battery state, market conditions, and vehicle schedule.

    Target latency: < 50ms
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    settings = get_settings()

    try:
        # Load trading agent model
        model_version = request.model_version or "production"
        loaded_model = await model_loader.load_model(
            "trading_agent",
            stage=model_version if model_version != "production" else "production",
        )

        # Prepare observation for RL agent
        observation = await _prepare_trading_observation(request)

        # Get action from model
        if hasattr(loaded_model.model, 'predict'):
            action_raw, _ = loaded_model.model.predict(observation, deterministic=True)
        else:
            # Mock prediction
            action_raw = np.random.randint(0, 3)

        # Decode action
        action, quantity, target_price, confidence = await _decode_action(
            action_raw,
            request.battery_state,
            request.market_state,
            request.risk_tolerance,
        )

        # Calculate expected profit
        expected_profit = await _calculate_expected_profit(
            action,
            quantity,
            request.battery_state,
            request.market_state,
        )

        # Calculate risk metrics
        risk_metrics = await _calculate_risk_metrics(
            action,
            quantity,
            request.market_state,
        )

        # Generate alternative actions
        alternatives = await _generate_alternatives(
            observation,
            loaded_model,
            action,
            request.battery_state,
            request.market_state,
        )

        # Generate explanation
        explanation = await _generate_explanation(
            action,
            quantity,
            request.battery_state,
            request.market_state,
            expected_profit,
        )

        latency_ms = (time.time() - start_time) * 1000

        response = TradingActionResponse(
            request_id=request_id,
            model_version=loaded_model.info.version,
            action=action,
            quantity_kwh=quantity,
            target_price=target_price,
            confidence=confidence,
            expected_profit=expected_profit,
            risk_metrics=risk_metrics,
            alternative_actions=alternatives,
            explanation=explanation,
            latency_ms=latency_ms,
        )

        # Record metrics
        TRADING_LATENCY.labels(
            endpoint="action",
            model_version=loaded_model.info.version,
        ).observe(latency_ms / 1000)

        TRADING_ACTIONS.labels(
            action=action.value,
            model_version=loaded_model.info.version,
        ).inc()

        TRADING_QUANTITIES.labels(action=action.value).observe(quantity)

        # Check latency target
        if latency_ms > settings.trading_latency_target_ms:
            logger.warning(
                f"Trading action latency {latency_ms:.1f}ms exceeds target "
                f"{settings.trading_latency_target_ms}ms"
            )

        return response

    except Exception as e:
        logger.error(f"Trading action failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchTradingResponse)
async def batch_trading_actions(
    request: BatchTradingRequest,
    model_loader=Depends(get_model_loader),
):
    """Get trading actions for multiple vehicles."""
    start_time = time.time()

    try:
        # Process each request
        responses = []
        for single_request in request.requests:
            try:
                response = await get_trading_action(
                    single_request,
                    model_loader=model_loader,
                    model_cache=None,  # Skip caching for batch
                )
                responses.append(response)
            except Exception as e:
                logger.error(f"Batch item failed: {e}")
                # Add error response
                responses.append(TradingActionResponse(
                    request_id=str(uuid.uuid4()),
                    model_version="error",
                    action=TradingAction.HOLD,
                    quantity_kwh=0,
                    confidence=0,
                    expected_profit=0,
                    explanation=f"Error: {str(e)}",
                    latency_ms=0,
                ))

        total_latency = (time.time() - start_time) * 1000

        return BatchTradingResponse(
            responses=responses,
            total_latency_ms=total_latency,
        )

    except Exception as e:
        logger.error(f"Batch trading failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/optimize", response_model=PortfolioOptimizationResponse)
async def optimize_portfolio(
    request: PortfolioOptimizationRequest,
    model_loader=Depends(get_model_loader),
):
    """Optimize actions across vehicle portfolio."""
    start_time = time.time()
    request_id = str(uuid.uuid4())

    try:
        # Load portfolio optimization model
        loaded_model = await model_loader.load_model(
            "portfolio_optimizer",
            stage="production",
        )

        # Prepare portfolio state
        portfolio_obs = await _prepare_portfolio_observation(request)

        # Optimize
        if hasattr(loaded_model.model, 'optimize'):
            vehicle_actions_raw = loaded_model.model.optimize(portfolio_obs)
        else:
            # Simple allocation strategy
            vehicle_actions_raw = await _simple_portfolio_allocation(
                request.portfolio,
                request.market_state,
            )

        # Build per-vehicle responses
        vehicle_actions = {}
        total_profit = 0

        for vehicle_data in request.portfolio.vehicles:
            vehicle_id = vehicle_data.get("vehicle_id", str(uuid.uuid4())[:8])
            action_data = vehicle_actions_raw.get(vehicle_id, {})

            action_response = TradingActionResponse(
                request_id=f"{request_id}-{vehicle_id}",
                model_version=loaded_model.info.version,
                action=TradingAction(action_data.get("action", "hold")),
                quantity_kwh=action_data.get("quantity", 0),
                target_price=action_data.get("target_price"),
                confidence=action_data.get("confidence", 0.5),
                expected_profit=action_data.get("expected_profit", 0),
                explanation=action_data.get("explanation", ""),
                latency_ms=0,
            )
            vehicle_actions[vehicle_id] = action_response
            total_profit += action_response.expected_profit

        latency_ms = (time.time() - start_time) * 1000

        return PortfolioOptimizationResponse(
            request_id=request_id,
            vehicle_actions=vehicle_actions,
            aggregate_metrics={
                "total_capacity": request.portfolio.total_capacity_kwh,
                "avg_soc": request.portfolio.aggregated_soc,
                "vehicles_buying": sum(
                    1 for v in vehicle_actions.values()
                    if v.action in [TradingAction.BUY, TradingAction.CHARGE]
                ),
                "vehicles_selling": sum(
                    1 for v in vehicle_actions.values()
                    if v.action in [TradingAction.SELL, TradingAction.DISCHARGE]
                ),
            },
            expected_total_profit=total_profit,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(f"Portfolio optimization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance", response_model=TradingPerformanceResponse)
async def get_trading_performance(
    request: TradingPerformanceRequest,
):
    """Get trading performance metrics for a time period."""
    try:
        # In production, would query from database
        # For now, return mock metrics
        days = (request.end_date - request.start_date).days

        return TradingPerformanceResponse(
            period_start=request.start_date,
            period_end=request.end_date,
            total_trades=int(days * 5),  # ~5 trades per day
            total_profit=float(days * 2.5),  # ~2.5 INR per day
            roi_pct=15.0,
            sharpe_ratio=1.5,
            max_drawdown=0.08,
            win_rate=0.65,
            metrics_by_action={
                "buy": {"count": int(days * 2), "avg_profit": 1.2},
                "sell": {"count": int(days * 2), "avg_profit": 1.5},
                "hold": {"count": int(days * 1), "avg_profit": 0},
            },
        )

    except Exception as e:
        logger.error(f"Performance query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_trading_models(model_loader=Depends(get_model_loader)):
    """List available trading models."""
    models = await model_loader.list_models()

    trading_models = {
        "registered_models": [
            m for m in models.get("registered_models", [])
            if "trading" in m.get("name", "").lower() or "agent" in m.get("name", "").lower()
        ],
        "loaded_models": [
            m for m in models.get("loaded_models", [])
            if "trading" in m.get("name", "").lower() or "agent" in m.get("name", "").lower()
        ],
    }

    return trading_models


# Helper functions

async def _prepare_trading_observation(request: TradingActionRequest) -> np.ndarray:
    """Prepare observation vector for RL agent."""
    bs = request.battery_state
    ms = request.market_state

    # Time features
    hour_sin = np.sin(2 * np.pi * request.timestamp.hour / 24)
    hour_cos = np.cos(2 * np.pi * request.timestamp.hour / 24)
    dow_sin = np.sin(2 * np.pi * request.timestamp.weekday() / 7)
    dow_cos = np.cos(2 * np.pi * request.timestamp.weekday() / 7)

    # Battery features
    soc = bs.soc
    available_charge = (1 - soc) * bs.capacity_kwh
    available_discharge = (soc - request.min_soc_reserve) * bs.capacity_kwh
    max_charge = min(available_charge, bs.max_charge_rate_kw)
    max_discharge = min(max(0, available_discharge), bs.max_discharge_rate_kw)

    # Market features
    current_price = ms.current_price
    price_forecast = ms.price_forecast[:24] if ms.price_forecast else [current_price] * 24
    price_forecast = price_forecast + [price_forecast[-1]] * (24 - len(price_forecast))

    avg_future_price = np.mean(price_forecast)
    max_future_price = np.max(price_forecast)
    min_future_price = np.min(price_forecast)

    # Normalized features
    obs = np.array([
        hour_sin, hour_cos,
        dow_sin, dow_cos,
        soc,
        max_charge / bs.capacity_kwh,
        max_discharge / bs.capacity_kwh,
        current_price / 10,  # Normalize to ~1
        avg_future_price / 10,
        (current_price - min_future_price) / (max_future_price - min_future_price + 1e-8),
        ms.volatility,
        ms.spread,
        request.risk_tolerance,
    ] + [p / 10 for p in price_forecast[:12]])  # First 12 hours of forecast

    return obs.astype(np.float32)


async def _decode_action(
    action_raw,
    battery_state,
    market_state,
    risk_tolerance: float,
) -> tuple:
    """Decode raw action into trading action and parameters."""
    # Discrete action space: 0=hold, 1=buy/charge, 2=sell/discharge
    if isinstance(action_raw, np.ndarray):
        action_idx = int(action_raw[0]) if len(action_raw.shape) > 0 else int(action_raw)
    else:
        action_idx = int(action_raw)

    # Map to action type
    if action_idx == 0:
        action = TradingAction.HOLD
        quantity = 0
        target_price = None
        confidence = 0.8
    elif action_idx == 1:
        action = TradingAction.CHARGE
        # Calculate optimal charge amount
        available = (1 - battery_state.soc) * battery_state.capacity_kwh
        quantity = min(available, battery_state.max_charge_rate_kw * risk_tolerance)
        target_price = market_state.current_price * 0.98  # Bid below current
        confidence = 0.7
    else:
        action = TradingAction.DISCHARGE
        # Calculate optimal discharge amount
        available = battery_state.soc * battery_state.capacity_kwh * 0.8  # Keep 20% reserve
        quantity = min(available, battery_state.max_discharge_rate_kw * risk_tolerance)
        target_price = market_state.current_price * 1.02  # Ask above current
        confidence = 0.7

    return action, quantity, target_price, confidence


async def _calculate_expected_profit(
    action: TradingAction,
    quantity: float,
    battery_state,
    market_state,
) -> float:
    """Calculate expected profit from action."""
    if action == TradingAction.HOLD or quantity == 0:
        return 0.0

    current_price = market_state.current_price
    future_prices = market_state.price_forecast[:6] if market_state.price_forecast else [current_price]
    avg_future = np.mean(future_prices)

    if action in [TradingAction.CHARGE, TradingAction.BUY]:
        # Profit from buying low and potentially selling higher
        cost = quantity * current_price * (1 + market_state.spread)
        potential_revenue = quantity * avg_future * battery_state.efficiency
        profit = potential_revenue - cost - quantity * battery_state.degradation_cost
    else:
        # Profit from selling now
        revenue = quantity * current_price * (1 - market_state.spread)
        # Opportunity cost of not having energy later
        opportunity = quantity * avg_future * 0.5  # 50% chance we'd want it
        profit = revenue - opportunity - quantity * battery_state.degradation_cost

    return float(profit)


async def _calculate_risk_metrics(
    action: TradingAction,
    quantity: float,
    market_state,
) -> dict:
    """Calculate risk metrics for the action."""
    if action == TradingAction.HOLD or quantity == 0:
        return {"var_95": 0, "expected_shortfall": 0, "max_loss": 0}

    volatility = market_state.volatility
    price = market_state.current_price

    # Value at Risk (95%)
    var_95 = quantity * price * volatility * 1.645

    # Expected Shortfall
    es = var_95 * 1.2  # Approximation

    # Maximum potential loss
    max_loss = quantity * price * 0.2  # Assume max 20% price move

    return {
        "var_95": float(var_95),
        "expected_shortfall": float(es),
        "max_loss": float(max_loss),
    }


async def _generate_alternatives(
    observation,
    model,
    chosen_action: TradingAction,
    battery_state,
    market_state,
) -> list:
    """Generate alternative actions with expected values."""
    alternatives = []

    for action in TradingAction:
        if action == chosen_action:
            continue

        if action == TradingAction.HOLD:
            quantity = 0
            expected_profit = 0
        elif action in [TradingAction.CHARGE, TradingAction.BUY]:
            quantity = min(
                (1 - battery_state.soc) * battery_state.capacity_kwh,
                battery_state.max_charge_rate_kw
            )
            expected_profit = await _calculate_expected_profit(
                action, quantity, battery_state, market_state
            )
        else:
            quantity = min(
                battery_state.soc * battery_state.capacity_kwh * 0.8,
                battery_state.max_discharge_rate_kw
            )
            expected_profit = await _calculate_expected_profit(
                action, quantity, battery_state, market_state
            )

        alternatives.append({
            "action": action.value,
            "quantity_kwh": quantity,
            "expected_profit": expected_profit,
        })

    return sorted(alternatives, key=lambda x: x["expected_profit"], reverse=True)[:3]


async def _generate_explanation(
    action: TradingAction,
    quantity: float,
    battery_state,
    market_state,
    expected_profit: float,
) -> str:
    """Generate human-readable explanation for action."""
    price = market_state.current_price
    soc_pct = battery_state.soc * 100

    if action == TradingAction.HOLD:
        return (
            f"Holding position. Current SOC is {soc_pct:.0f}%. "
            f"Market price of ₹{price:.2f}/kWh doesn't present clear opportunity."
        )

    elif action in [TradingAction.CHARGE, TradingAction.BUY]:
        future_prices = market_state.price_forecast[:6] if market_state.price_forecast else []
        if future_prices and np.mean(future_prices) > price * 1.1:
            reason = f"prices expected to rise to ₹{np.mean(future_prices):.2f}"
        else:
            reason = "current price is favorable"

        return (
            f"Recommending {action.value} of {quantity:.1f} kWh at ₹{price:.2f}/kWh. "
            f"SOC will increase from {soc_pct:.0f}% to "
            f"{min(100, soc_pct + quantity/battery_state.capacity_kwh*100):.0f}%. "
            f"Reason: {reason}. Expected profit: ₹{expected_profit:.2f}."
        )

    else:  # SELL/DISCHARGE
        return (
            f"Recommending {action.value} of {quantity:.1f} kWh at ₹{price:.2f}/kWh. "
            f"SOC will decrease from {soc_pct:.0f}% to "
            f"{max(0, soc_pct - quantity/battery_state.capacity_kwh*100):.0f}%. "
            f"Current price is above average. Expected profit: ₹{expected_profit:.2f}."
        )


async def _prepare_portfolio_observation(request: PortfolioOptimizationRequest) -> dict:
    """Prepare observation for portfolio optimization."""
    return {
        "timestamp": request.timestamp.isoformat(),
        "vehicles": request.portfolio.vehicles,
        "total_capacity": request.portfolio.total_capacity_kwh,
        "aggregated_soc": request.portfolio.aggregated_soc,
        "market": {
            "price": request.market_state.current_price,
            "forecast": request.market_state.price_forecast,
            "volatility": request.market_state.volatility,
        },
        "horizon": request.optimization_horizon_hours,
        "objective": request.objective,
    }


async def _simple_portfolio_allocation(portfolio, market_state) -> dict:
    """Simple portfolio allocation strategy."""
    result = {}
    price = market_state.current_price
    avg_future = np.mean(market_state.price_forecast[:6]) if market_state.price_forecast else price

    for vehicle in portfolio.vehicles:
        vehicle_id = vehicle.get("vehicle_id", str(uuid.uuid4())[:8])
        soc = vehicle.get("soc", 0.5)
        capacity = vehicle.get("capacity_kwh", 50)

        # Simple rule: charge when price is low relative to future, sell when high
        if price < avg_future * 0.95 and soc < 0.8:
            action = "charge"
            quantity = min((0.8 - soc) * capacity, 10)
            expected_profit = quantity * (avg_future - price) * 0.9
        elif price > avg_future * 1.05 and soc > 0.3:
            action = "discharge"
            quantity = min((soc - 0.3) * capacity, 10)
            expected_profit = quantity * (price - avg_future) * 0.9
        else:
            action = "hold"
            quantity = 0
            expected_profit = 0

        result[vehicle_id] = {
            "action": action,
            "quantity": quantity,
            "target_price": price,
            "confidence": 0.6,
            "expected_profit": expected_profit,
            "explanation": f"SOC: {soc*100:.0f}%, Price: ₹{price:.2f}",
        }

    return result
