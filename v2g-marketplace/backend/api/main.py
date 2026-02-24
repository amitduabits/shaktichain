"""
V2G Marketplace API endpoints.

Provides REST API for simulation management and price history.
"""

import sys
import time
import math
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException, Query, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add backend directory to path for imports (works on both Windows and Unix)
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from core.database import get_database, Database
from core.auction import Bid, McAfeeAuction
from core.logging import (
    setup_logging,
    get_logger,
    LoggerFactory,
    LogMessages,
    set_request_id,
    set_user_context,
    clear_context,
    generate_request_id,
)
from core.metrics import (
    get_metrics,
    record_request,
    record_error,
    record_simulation_created,
    record_user_registration,
    record_user_login,
    health_status,
    REQUEST_IN_PROGRESS,
    normalize_endpoint,
)
from api.schemas import (
    SimulationCreate,
    SimulationUpdate,
    SimulationResponse,
    PeriodCreate,
    PeriodResponse,
    PriceCreate,
    PriceResponse,
)
from api.auth import router as auth_router, get_current_user
from api.simulation_service import get_simulation_service
from api.routes.blockchain import router as blockchain_router

# Database instance
db: Optional[Database] = None

# Logger instance
logger = get_logger("v2g.api")


class AuctionCommitRequest(BaseModel):
    """Commit phase payload for sealed-bid auction order."""

    round_id: Optional[str] = None
    prosumer_id: str = Field(..., min_length=1, max_length=128)
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    commit_hash: str = Field(..., min_length=32, max_length=128)
    reveal_window_minutes: int = Field(10, ge=1, le=240)


class AuctionRevealRequest(BaseModel):
    """Reveal phase payload for previously committed order."""

    round_id: str = Field(..., min_length=1)
    order_id: str = Field(..., min_length=1)
    prosumer_id: str = Field(..., min_length=1, max_length=128)
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    nonce: str = Field(..., min_length=1, max_length=256)


class AuctionSettleBatchRequest(BaseModel):
    """Settlement request for revealed orders in a round."""

    round_id: str = Field(..., min_length=1)
    max_matches: int = Field(200, ge=1, le=2000)


def _get_db() -> Database:
    """Get DB instance safely for runtime and tests."""
    global db
    resolved = get_database()
    if db is not resolved:
        db = resolved
    return db


def _compute_commit_hash(
    round_id: str,
    prosumer_id: str,
    side: str,
    quantity: float,
    price: float,
    nonce: str,
) -> str:
    payload = f"{round_id}|{prosumer_id}|{side}|{quantity:.6f}|{price:.6f}|{nonce}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LoggingMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging and metrics collection."""

    async def dispatch(self, request: Request, call_next):
        # Generate and set request ID
        request_id = generate_request_id()
        set_request_id(request_id)

        # Add request ID to response headers
        start_time = time.perf_counter()
        method = request.method
        path = str(request.url.path)
        normalized_path = normalize_endpoint(path)

        # Track in-progress requests
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=normalized_path).inc()

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            duration_ms = duration * 1000

            # Record metrics
            record_request(method, path, response.status_code, duration)

            # Log request
            LogMessages.api_request(
                logger,
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.perf_counter() - start_time
            duration_ms = duration * 1000

            # Record error metrics
            record_error(type(e).__name__, path)
            record_request(method, path, 500, duration)

            # Log error
            LogMessages.request_failed(
                logger,
                method=method,
                path=path,
                error=str(e),
                status_code=500,
            )

            raise

        finally:
            # Decrement in-progress counter
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=normalized_path).dec()
            # Clear request context
            clear_context()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global db

    # Initialize logging
    setup_logging()
    logger.info("application_startup", message="V2G Marketplace API starting up")

    # Startup: Initialize database
    db = get_database()

    # Verify database connection for health check
    try:
        db.list_simulations(limit=1)
        health_status.set_db_health(True)
        logger.info("database_connected", message="Database connection established")
    except Exception as e:
        health_status.set_db_health(False)
        logger.error("database_connection_failed", error=str(e))

    yield

    # Shutdown: Close database connection
    logger.info("application_shutdown", message="V2G Marketplace API shutting down")
    if db:
        db.close()


app = FastAPI(
    title="V2G Marketplace API",
    description="API for Vehicle-to-Grid energy marketplace simulations",
    version="0.1.0",
    lifespan=lifespan,
)

# Add logging/metrics middleware
app.add_middleware(LoggingMetricsMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router)

# Include blockchain router
app.include_router(blockchain_router)


# === Health Check Endpoints ===


@app.get("/health")
async def health_check():
    """
    Basic liveness health check.

    Returns healthy if the service is running.
    """
    return {"status": "healthy", "service": "v2g-marketplace"}


@app.get("/health/ready")
async def readiness_check():
    """
    Full readiness health check.

    Checks database connectivity and other dependencies.
    """
    checks = {
        "database": False,
    }

    # Check database connection
    try:
        database = _get_db()
        database.list_simulations(limit=1)
        checks["database"] = True
        health_status.set_db_health(True)
    except Exception as e:
        health_status.set_db_health(False)
        logger.warning("readiness_check_failed", component="database", error=str(e))

    # Determine overall status
    is_ready = all(checks.values())

    if not is_ready:
        return Response(
            content='{"status": "not_ready", "checks": ' + str(checks).replace("'", '"').replace("True", "true").replace("False", "false") + '}',
            status_code=503,
            media_type="application/json",
        )

    return {
        "status": "ready",
        "checks": checks,
    }


# === Metrics Endpoint ===


@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.
    """
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


# === Simulation Endpoints ===


@app.post("/simulations", response_model=SimulationResponse)
async def create_simulation(
    sim: SimulationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new simulation. Requires authentication."""
    # Set user context for logging
    set_user_context(current_user.get("id"), current_user.get("email"))

    database = _get_db()
    sim_id = database.save_simulation({
        "n_agents": sim.n_agents,
        "n_days": sim.n_days,
    })

    # Record metrics
    record_simulation_created(sim.n_agents)

    # Log simulation creation
    LogMessages.simulation_started(
        LoggerFactory.get_simulation_logger(),
        simulation_id=sim_id,
        n_agents=sim.n_agents,
        n_days=sim.n_days,
    )

    result = database.get_simulation(sim_id)
    return result


@app.get("/simulations", response_model=list[SimulationResponse])
async def list_simulations(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List recent simulations. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    return _get_db().list_simulations(limit=limit)


@app.get("/simulations/{sim_id}", response_model=SimulationResponse)
async def get_simulation(
    sim_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a simulation by ID. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    result = _get_db().get_simulation(sim_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return result


@app.patch("/simulations/{sim_id}", response_model=SimulationResponse)
async def update_simulation(
    sim_id: str,
    updates: SimulationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a simulation. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))

    # Check if simulation exists
    database = _get_db()
    existing = database.get_simulation(sim_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Apply updates
    update_data = updates.model_dump(exclude_none=True)
    if update_data:
        database.update_simulation(sim_id, update_data)

    return database.get_simulation(sim_id)


# === Market Period Endpoints ===


@app.post("/periods", response_model=PeriodResponse)
async def create_period(
    period: PeriodCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a market period record. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))

    # Verify simulation exists
    database = _get_db()
    sim = database.get_simulation(period.simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    period_id = database.save_period(period.model_dump())
    periods = database.get_periods(period.simulation_id)
    # Return the newly created period
    for p in periods:
        if p["id"] == period_id:
            return p
    raise HTTPException(status_code=500, detail="Failed to retrieve created period")


@app.get("/simulations/{sim_id}/periods", response_model=list[PeriodResponse])
async def get_simulation_periods(
    sim_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all periods for a simulation. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))

    # Verify simulation exists
    database = _get_db()
    sim = database.get_simulation(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return database.get_periods(sim_id)


# === Price History Endpoints ===


@app.post("/prices", response_model=PriceResponse)
async def create_price(price_data: PriceCreate):
    """Add a price history entry."""
    database = _get_db()
    price_id = database.save_price(price_data.price, price_data.source)
    history = database.get_price_history(limit=1)
    if history and history[0]["id"] == price_id:
        return history[0]
    raise HTTPException(status_code=500, detail="Failed to retrieve created price")


@app.get("/prices", response_model=list[PriceResponse])
async def get_price_history(limit: int = Query(100, ge=1, le=1000)):
    """Get recent price history."""
    return _get_db().get_price_history(limit=limit)


# === Market Endpoints (for frontend compatibility) ===


@app.get("/market/price")
async def get_current_market_price():
    """Get current energy price."""
    database = _get_db()
    history = database.get_price_history(limit=1)
    if history:
        return {
            "price": history[0]["price"],
            "timestamp": history[0]["timestamp"],
            "source": history[0]["source"],
        }

    # Compute diurnal baseline when no historical records exist.
    now = datetime.now(timezone.utc)
    hour_angle = (2 * math.pi * now.hour) / 24
    demand_factor = 1.0 + 0.32 * math.sin(hour_angle - 1.2) + 0.11 * math.cos(hour_angle * 2)
    computed_price = max(2.5, round(5.4 * demand_factor, 4))

    return {
        "price": computed_price,
        "timestamp": now.isoformat(),
        "source": "computed_diurnal_baseline",
    }


@app.get("/market/price/history")
async def get_market_price_history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get price history for a time range."""
    history = _get_db().get_price_history(limit=limit)
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    filtered = []
    for row in history:
        ts = datetime.fromisoformat(row["timestamp"])
        if start_dt and ts < start_dt:
            continue
        if end_dt and ts > end_dt:
            continue
        filtered.append(row)

    return [
        {
            "time": h["timestamp"],
            "price": h["price"],
            "source": h["source"],
        }
        for h in filtered
    ]


# === Simulation Runner Endpoints (for frontend SimulationPanel) ===


@app.post("/simulation/start")
async def start_simulation_job(
    params: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new simulation with enhanced parameters.

    Expected params:
    - num_agents: int
    - duration_days: int
    - agent_mix: dict with residential, commercial, fleet percentages
    - region: str
    """
    sim_service = get_simulation_service(_get_db())

    job_id = sim_service.start_simulation(
        num_agents=params.get("num_agents", 100),
        duration_days=params.get("duration_days", 1),
        agent_mix=params.get("agent_mix", {"residential": 50, "commercial": 30, "fleet": 20}),
        region=params.get("region", "delhi"),
    )

    return {"job_id": job_id}


@app.get("/simulation/status/{job_id}")
async def get_simulation_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get simulation status and progress."""
    sim_service = get_simulation_service(_get_db())
    status = sim_service.get_status(job_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Simulation job not found")

    return status


@app.get("/simulation/download/{job_id}")
async def download_simulation_results(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download simulation results as CSV."""
    from fastapi.responses import Response

    sim_service = get_simulation_service(_get_db())
    csv_data = sim_service.get_results_csv(job_id)

    if csv_data is None:
        raise HTTPException(status_code=404, detail="Simulation results not available")

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=simulation_{job_id}.csv"}
    )


# === Prosumer Endpoints ===


def _build_prosumer_snapshot(database: Database, limit: int = 100) -> list[dict]:
    """Build dynamic prosumer list from latest simulation and period records."""
    latest = database.list_simulations(limit=1)
    if not latest:
        return []

    simulation = latest[0]
    sim_id = simulation["id"]
    periods = database.get_periods(sim_id)
    if not periods:
        return []

    n_agents = max(1, int(simulation["n_agents"]))
    count = min(limit, n_agents)

    avg_price = sum((p["clearing_price"] or 0.0) for p in periods) / max(1, len(periods))
    avg_volume = sum((p["volume"] or 0.0) for p in periods) / max(1, len(periods))
    buyers = sum((p["n_buyers"] or 0) for p in periods)
    sellers = sum((p["n_sellers"] or 0) for p in periods)
    flow_skew = (buyers - sellers) / max(1, buyers + sellers)

    prosumers = []
    for idx in range(count):
        role = "buyer" if (idx + buyers) % 2 else "seller"
        relative_weight = 0.92 + ((idx % 9) * 0.02)
        expected_volume = round((avg_volume / n_agents) * relative_weight, 4)
        reliability = round(max(0.15, min(0.99, 0.55 + (avg_price / 20) + flow_skew * 0.1 - (idx % 5) * 0.03)), 3)
        prosumers.append(
            {
                "id": f"prosumer_{idx + 1}",
                "simulation_id": sim_id,
                "role": role,
                "expected_volume_kwh": expected_volume,
                "reliability_score": reliability,
                "latest_market_price": round(avg_price, 4),
            }
        )

    return prosumers


@app.get("/prosumers")
async def get_prosumers(
    limit: int = Query(100, ge=1, le=2000),
    current_user: dict = Depends(get_current_user),
):
    """Get computed list of active prosumers from current simulation data."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    return _build_prosumer_snapshot(_get_db(), limit=limit)


@app.get("/prosumers/{prosumer_id}")
async def get_prosumer_details(
    prosumer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get computed details for one prosumer ID."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    candidates = _build_prosumer_snapshot(_get_db(), limit=2000)
    for item in candidates:
        if item["id"] == prosumer_id:
            return item
    raise HTTPException(status_code=404, detail="Prosumer not found")


# === Auction Commit/Reveal Endpoints ===


@app.post("/auction/commit")
async def auction_commit(
    request: AuctionCommitRequest,
    current_user: dict = Depends(get_current_user),
):
    """Commit sealed auction order hash for a round."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    database = _get_db()

    if request.round_id:
        round_id = request.round_id
        round_data = database.get_auction_round(round_id)
        if round_data is None:
            reveal_deadline = (datetime.now(timezone.utc) + timedelta(minutes=request.reveal_window_minutes)).isoformat()
            database.create_auction_round(reveal_deadline=reveal_deadline, round_id=round_id)
            round_data = database.get_auction_round(round_id)
    else:
        reveal_deadline = (datetime.now(timezone.utc) + timedelta(minutes=request.reveal_window_minutes)).isoformat()
        round_id = database.create_auction_round(reveal_deadline=reveal_deadline)
        round_data = database.get_auction_round(round_id)

    if round_data["status"] != "open":
        raise HTTPException(status_code=409, detail="Auction round is not open")

    if datetime.fromisoformat(round_data["reveal_deadline"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Reveal window has already closed")

    order_id = database.save_auction_commit(
        {
            "round_id": round_id,
            "prosumer_id": request.prosumer_id,
            "side": request.side,
            "quantity": request.quantity,
            "commit_hash": request.commit_hash,
        }
    )

    return {
        "round_id": round_id,
        "order_id": order_id,
        "prosumer_id": request.prosumer_id,
        "status": "committed",
        "reveal_deadline": round_data["reveal_deadline"],
    }


@app.post("/auction/reveal")
async def auction_reveal(
    request: AuctionRevealRequest,
    current_user: dict = Depends(get_current_user),
):
    """Reveal committed order values and validate commit hash."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    database = _get_db()

    round_data = database.get_auction_round(request.round_id)
    if round_data is None:
        raise HTTPException(status_code=404, detail="Auction round not found")
    if round_data["status"] != "open":
        raise HTTPException(status_code=409, detail="Auction round is not open")

    order = database.get_auction_order(request.round_id, request.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Committed order not found")
    if order["prosumer_id"] != request.prosumer_id:
        raise HTTPException(status_code=403, detail="Order ownership mismatch")
    if order["status"] != "committed":
        raise HTTPException(status_code=409, detail="Order is not in committed state")
    if order["side"] != request.side:
        raise HTTPException(status_code=400, detail="Revealed side does not match committed side")
    if abs(order["quantity"] - request.quantity) > 1e-9:
        raise HTTPException(status_code=400, detail="Revealed quantity does not match committed quantity")

    computed_hash = _compute_commit_hash(
        request.round_id,
        request.prosumer_id,
        request.side,
        request.quantity,
        request.price,
        request.nonce,
    )
    if computed_hash != order["commit_hash"]:
        raise HTTPException(status_code=400, detail="Commit hash validation failed")

    if datetime.fromisoformat(round_data["reveal_deadline"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Reveal window has closed")

    updated = database.reveal_auction_order(
        request.round_id,
        request.order_id,
        request.price,
        request.nonce,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update revealed order")

    return {
        "round_id": request.round_id,
        "order_id": request.order_id,
        "status": "revealed",
        "price": request.price,
    }


@app.post("/auction/settle-batch")
async def auction_settle_batch(
    request: AuctionSettleBatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Settle revealed orders in a round using McAfee matching."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    database = _get_db()

    round_data = database.get_auction_round(request.round_id)
    if round_data is None:
        raise HTTPException(status_code=404, detail="Auction round not found")
    if round_data["status"] != "open":
        raise HTTPException(status_code=409, detail="Auction round already settled")
    if datetime.fromisoformat(round_data["reveal_deadline"]) > datetime.now(timezone.utc):
        pending_commits = database.list_auction_orders(request.round_id, status="committed")
        if pending_commits:
            raise HTTPException(status_code=409, detail="Reveal window is still open")

    revealed = database.list_auction_orders(request.round_id, status="revealed")
    bids = [o for o in revealed if o["side"] == "buy"]
    asks = [o for o in revealed if o["side"] == "sell"]

    if not bids or not asks:
        database.update_auction_round(
            request.round_id,
            status="settled",
            clearing_price=0.0,
            matched_orders=0,
            settled_volume=0.0,
        )
        return {
            "round_id": request.round_id,
            "status": "settled",
            "clearing_price": 0.0,
            "matched_orders": 0,
            "settled_volume": 0.0,
            "matches": [],
        }

    auction = McAfeeAuction()
    order_lookup = {}

    for row in bids[: request.max_matches]:
        bid = Bid(
            agent_id=row["id"],
            quantity=float(row["quantity"]),
            price=float(row["price"]),
            is_buy=True,
        )
        auction.add_bid(bid)
        order_lookup[row["id"]] = row

    for row in asks[: request.max_matches]:
        bid = Bid(
            agent_id=row["id"],
            quantity=float(row["quantity"]),
            price=float(row["price"]),
            is_buy=False,
        )
        auction.add_bid(bid)
        order_lookup[row["id"]] = row

    result = auction.clear_market()

    matches = []
    if result.clearing_price is not None:
        for buy_bid, sell_bid in zip(result.matched_buyers, result.matched_sellers):
            quantity = min(buy_bid.quantity, sell_bid.quantity)
            database.save_auction_match(
                request.round_id,
                buy_bid.agent_id,
                sell_bid.agent_id,
                quantity,
                float(result.clearing_price),
            )
            database.mark_auction_order_status(request.round_id, buy_bid.agent_id, "settled")
            database.mark_auction_order_status(request.round_id, sell_bid.agent_id, "settled")
            matches.append(
                {
                    "buy_order_id": buy_bid.agent_id,
                    "sell_order_id": sell_bid.agent_id,
                    "quantity": quantity,
                    "price": float(result.clearing_price),
                }
            )

    settled_volume = float(sum(m["quantity"] for m in matches))
    matched_orders = len(matches) * 2
    clearing_price = float(result.clearing_price or 0.0)

    database.update_auction_round(
        request.round_id,
        status="settled",
        clearing_price=clearing_price,
        matched_orders=matched_orders,
        settled_volume=settled_volume,
    )

    return {
        "round_id": request.round_id,
        "status": "settled",
        "clearing_price": clearing_price,
        "matched_orders": matched_orders,
        "settled_volume": settled_volume,
        "matches": matches,
    }


@app.get("/auction/round/{round_id}")
async def get_auction_round(round_id: str, current_user: dict = Depends(get_current_user)):
    """Get details for one auction round."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    database = _get_db()
    round_data = database.get_auction_round(round_id)
    if round_data is None:
        raise HTTPException(status_code=404, detail="Auction round not found")

    orders = database.list_auction_orders(round_id)
    matches = database.list_auction_matches(round_id)

    return {
        **round_data,
        "orders_total": len(orders),
        "orders_revealed": len([o for o in orders if o["status"] in {"revealed", "settled", "matched"}]),
        "matches_total": len(matches),
    }


@app.get("/auction/orderbook/{round_id}")
async def get_auction_orderbook(round_id: str, current_user: dict = Depends(get_current_user)):
    """Get round orderbook with revealed bids and asks."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    database = _get_db()
    round_data = database.get_auction_round(round_id)
    if round_data is None:
        raise HTTPException(status_code=404, detail="Auction round not found")

    orders = database.list_auction_orders(round_id)
    bids = [o for o in orders if o["side"] == "buy"]
    asks = [o for o in orders if o["side"] == "sell"]

    # Price visibility is gated by reveal status.
    def _public_order(row: dict) -> dict:
        visible = row["status"] in {"revealed", "matched", "settled"}
        return {
            "id": row["id"],
            "prosumer_id": row["prosumer_id"],
            "side": row["side"],
            "quantity": row["quantity"],
            "status": row["status"],
            "price": row["price"] if visible else None,
            "created_at": row["created_at"],
        }

    return {
        "round_id": round_id,
        "status": round_data["status"],
        "bids": [_public_order(o) for o in bids],
        "asks": [_public_order(o) for o in asks],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
