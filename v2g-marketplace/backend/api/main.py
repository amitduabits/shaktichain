"""FastAPI application for V2G Marketplace."""

import logging
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Application version
VERSION = "0.1.0"

# In-memory storage for simulation jobs and results
simulation_jobs: dict[str, dict] = {}
latest_clearing_price: Optional[float] = None

app = FastAPI(
    title="V2G Marketplace API",
    description="API for Vehicle-to-Grid energy marketplace simulation",
    version=VERSION,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = time.time()

    logger.info(f"Request started: {request.method} {request.url.path}")

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        f"Request completed: {request.method} {request.url.path} "
        f"- Status: {response.status_code} - Duration: {duration:.3f}s"
    )

    return response


# Pydantic models
class SimulationRequest(BaseModel):
    """Request model for running a simulation."""

    n_agents: int = Field(default=100, ge=1, le=10000, description="Number of agents")
    n_days: int = Field(default=7, ge=1, le=365, description="Number of days to simulate")


class SimulationStartResponse(BaseModel):
    """Response model for simulation start."""

    job_id: str
    status: str


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    version: str


class MarketPriceResponse(BaseModel):
    """Response model for market price."""

    price: Optional[float]
    currency: str = "USD/kWh"


# Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": VERSION}


@app.post("/simulation/run", response_model=SimulationStartResponse)
async def run_simulation(request: SimulationRequest):
    """
    Start a new simulation in the background.

    Returns a job_id that can be used to check status and retrieve results.
    """
    global latest_clearing_price

    job_id = str(uuid.uuid4())

    logger.info(
        f"Starting simulation job {job_id} with "
        f"n_agents={request.n_agents}, n_days={request.n_days}"
    )

    # Store job information
    simulation_jobs[job_id] = {
        "status": "running",
        "n_agents": request.n_agents,
        "n_days": request.n_days,
        "results": None,
    }

    # TODO: Run actual simulation in background task
    # For now, simulate completion with mock results
    simulation_jobs[job_id]["status"] = "completed"
    simulation_jobs[job_id]["results"] = {
        "total_energy_traded": request.n_agents * request.n_days * 10.5,
        "average_price": 0.12,
        "clearing_price": 0.115,
        "n_transactions": request.n_agents * request.n_days * 2,
    }

    # Update latest clearing price
    latest_clearing_price = simulation_jobs[job_id]["results"]["clearing_price"]

    return {"job_id": job_id, "status": "started"}


@app.get("/simulation/results/{job_id}")
async def get_simulation_results(job_id: str):
    """
    Get results for a simulation job.

    Returns the results if completed, or status if still running.
    """
    if job_id not in simulation_jobs:
        return {"status": "not_found", "message": f"Job {job_id} not found"}

    job = simulation_jobs[job_id]

    if job["status"] == "running":
        return {"status": "running"}

    return {
        "status": job["status"],
        "n_agents": job["n_agents"],
        "n_days": job["n_days"],
        "results": job["results"],
    }


@app.get("/market/current-price", response_model=MarketPriceResponse)
async def get_current_price():
    """
    Get the latest clearing price from the most recent simulation.

    Returns None if no simulation has been run yet.
    """
    return {"price": latest_clearing_price, "currency": "USD/kWh"}
