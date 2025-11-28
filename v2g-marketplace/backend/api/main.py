"""
V2G Marketplace API endpoints.

Provides REST API for simulation management and price history.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_database, Database
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

# Database instance
db: Optional[Database] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global db
    # Startup: Initialize database
    db = get_database()
    yield
    # Shutdown: Close database connection
    if db:
        db.close()


app = FastAPI(
    title="V2G Marketplace API",
    description="API for Vehicle-to-Grid energy marketplace simulations",
    version="0.1.0",
    lifespan=lifespan,
)

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# === Simulation Endpoints ===


@app.post("/simulations", response_model=SimulationResponse)
async def create_simulation(
    sim: SimulationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new simulation. Requires authentication."""
    sim_id = db.save_simulation({
        "n_agents": sim.n_agents,
        "n_days": sim.n_days,
    })
    result = db.get_simulation(sim_id)
    return result


@app.get("/simulations", response_model=list[SimulationResponse])
async def list_simulations(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List recent simulations. Requires authentication."""
    return db.list_simulations(limit=limit)


@app.get("/simulations/{sim_id}", response_model=SimulationResponse)
async def get_simulation(
    sim_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a simulation by ID. Requires authentication."""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
