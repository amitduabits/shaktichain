"""
Base Scenario - Abstract base class for market scenarios.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ScenarioState:
    """Current state of a scenario."""
    period: int = 0
    hour_of_day: int = 0
    demand_level: float = 1.0
    supply_level: float = 1.0
    volatility: float = 0.1
    is_shock_active: bool = False
    is_attack_active: bool = False
    price_multiplier: float = 1.0
    custom_data: dict = field(default_factory=dict)


@dataclass
class ScenarioConfig:
    """Configuration for a scenario."""
    name: str
    description: str
    duration_hours: int = 24
    base_demand_kwh: float = 1000.0
    base_supply_kwh: float = 1000.0
    volatility: float = 0.1
    warmup_periods: int = 10
    custom_params: dict = field(default_factory=dict)


class BaseScenario(ABC):
    """
    Abstract base class for market scenarios.

    Scenarios define the market conditions and external factors
    that affect supply, demand, and price dynamics.
    """

    def __init__(self, config: ScenarioConfig):
        """
        Initialize the scenario.

        Args:
            config: Scenario configuration
        """
        self.config = config
        self.state = ScenarioState()
        self._random_state = np.random.RandomState(42)

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset scenario to initial state."""
        if seed is not None:
            self._random_state = np.random.RandomState(seed)
        self.state = ScenarioState()

    @abstractmethod
    def get_demand(self, period: int) -> float:
        """
        Get demand for the given period.

        Args:
            period: Period number

        Returns:
            Demand in kWh
        """
        pass

    @abstractmethod
    def get_supply(self, period: int) -> float:
        """
        Get available supply for the given period.

        Args:
            period: Period number

        Returns:
            Supply in kWh
        """
        pass

    def get_price_factors(self, period: int) -> dict:
        """
        Get price-affecting factors for the period.

        Returns:
            Dictionary with price multipliers and factors
        """
        return {
            "base_multiplier": 1.0,
            "demand_pressure": 0.0,
            "supply_pressure": 0.0,
            "volatility_premium": 0.0,
        }

    def step(self) -> ScenarioState:
        """
        Advance scenario by one period.

        Returns:
            Updated scenario state
        """
        self.state.period += 1
        self.state.hour_of_day = self.state.period % 24
        return self.state

    def get_agent_adjustments(self, agent_type: str) -> dict:
        """
        Get adjustments for agent behavior under this scenario.

        Args:
            agent_type: Type of agent

        Returns:
            Dictionary of adjustments
        """
        return {}

    def is_warmup(self) -> bool:
        """Check if still in warmup phase."""
        return self.state.period < self.config.warmup_periods

    def get_metadata(self) -> dict:
        """Get scenario metadata."""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "duration_hours": self.config.duration_hours,
            "current_period": self.state.period,
            "is_warmup": self.is_warmup(),
        }
