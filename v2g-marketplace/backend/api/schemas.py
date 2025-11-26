"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SimulationCreate(BaseModel):
    """Schema for creating a new simulation."""
    n_agents: int = Field(..., gt=0, description="Number of agents")
    n_days: int = Field(..., gt=0, description="Number of days to simulate")


class SimulationUpdate(BaseModel):
    """Schema for updating a simulation."""
    status: Optional[str] = Field(None, pattern="^(pending|running|completed|failed)$")
    avg_price: Optional[float] = None
    total_volume: Optional[float] = None


class SimulationResponse(BaseModel):
    """Schema for simulation response."""
    id: str
    created_at: str
    n_agents: int
    n_days: int
    status: str
    avg_price: Optional[float] = None
    total_volume: Optional[float] = None


class PeriodCreate(BaseModel):
    """Schema for creating a market period."""
    simulation_id: str
    period: int = Field(..., ge=0)
    hour: int = Field(..., ge=0, lt=24)
    clearing_price: Optional[float] = None
    volume: Optional[float] = None
    n_buyers: Optional[int] = None
    n_sellers: Optional[int] = None


class PeriodResponse(BaseModel):
    """Schema for market period response."""
    id: int
    simulation_id: str
    period: int
    hour: int
    clearing_price: Optional[float] = None
    volume: Optional[float] = None
    n_buyers: Optional[int] = None
    n_sellers: Optional[int] = None


class PriceCreate(BaseModel):
    """Schema for creating a price history entry."""
    price: float
    source: str = Field("simulation", pattern="^(simulation|live)$")


class PriceResponse(BaseModel):
    """Schema for price history response."""
    id: int
    timestamp: str
    price: float
    source: str
