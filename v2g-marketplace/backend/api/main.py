"""
V2G Marketplace API endpoints.

Provides REST API for simulation management and price history.
"""

import sys
import time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Add backend directory to path for imports (works on both Windows and Unix)
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from core.database import get_database, Database
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

# Database instance
db: Optional[Database] = None

# Logger instance
logger = get_logger("v2g.api")


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
        db.list_simulations(limit=1)
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

    sim_id = db.save_simulation({
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

    result = db.get_simulation(sim_id)
    return result


@app.get("/simulations", response_model=list[SimulationResponse])
async def list_simulations(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List recent simulations. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    return db.list_simulations(limit=limit)


@app.get("/simulations/{sim_id}", response_model=SimulationResponse)
async def get_simulation(
    sim_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a simulation by ID. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))
    result = db.get_simulation(sim_id)
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
    existing = db.get_simulation(sim_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Apply updates
    update_data = updates.model_dump(exclude_none=True)
    if update_data:
        db.update_simulation(sim_id, update_data)

    return db.get_simulation(sim_id)


# === Market Period Endpoints ===


@app.post("/periods", response_model=PeriodResponse)
async def create_period(
    period: PeriodCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a market period record. Requires authentication."""
    set_user_context(current_user.get("id"), current_user.get("email"))

    # Verify simulation exists
    sim = db.get_simulation(period.simulation_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    period_id = db.save_period(period.model_dump())
    periods = db.get_periods(period.simulation_id)
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
    sim = db.get_simulation(sim_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return db.get_periods(sim_id)


# === Price History Endpoints ===


@app.post("/prices", response_model=PriceResponse)
async def create_price(price_data: PriceCreate):
    """Add a price history entry."""
    price_id = db.save_price(price_data.price, price_data.source)
    history = db.get_price_history(limit=1)
    if history and history[0]["id"] == price_id:
        return history[0]
    raise HTTPException(status_code=500, detail="Failed to retrieve created price")


@app.get("/prices", response_model=list[PriceResponse])
async def get_price_history(limit: int = Query(100, ge=1, le=1000)):
    """Get recent price history."""
    return db.get_price_history(limit=limit)


# === Market Endpoints (for frontend compatibility) ===


@app.get("/market/price")
async def get_current_market_price():
    """Get current energy price."""
    history = db.get_price_history(limit=1)
    if history:
        return {
            "price": history[0]["price"],
            "timestamp": history[0]["timestamp"],
            "source": history[0]["source"],
        }
    # Return default price if no history
    return {
        "price": 6.0,  # Base price in INR/kWh
        "timestamp": "N/A",
        "source": "default",
    }


@app.get("/market/price/history")
async def get_market_price_history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """Get price history for a time range."""
    # For now, just return recent history
    # TODO: Add date filtering when needed
    history = db.get_price_history(limit=limit)
    return [
        {
            "time": h["timestamp"],
            "price": h["price"],
            "source": h["source"],
        }
        for h in history
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
    sim_service = get_simulation_service(db)

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
    sim_service = get_simulation_service(db)
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

    sim_service = get_simulation_service(db)
    csv_data = sim_service.get_results_csv(job_id)

    if csv_data is None:
        raise HTTPException(status_code=404, detail="Simulation results not available")

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=simulation_{job_id}.csv"}
    )


# === Prosumer Endpoints (placeholder for future implementation) ===


@app.get("/prosumers")
async def get_prosumers(current_user: dict = Depends(get_current_user)):
    """Get list of active prosumers (placeholder)."""
    # TODO: Implement actual prosumer tracking
    return []


@app.get("/prosumers/{prosumer_id}")
async def get_prosumer_details(
    prosumer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get prosumer details by ID (placeholder)."""
    # TODO: Implement actual prosumer tracking
    raise HTTPException(status_code=404, detail="Prosumer not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
