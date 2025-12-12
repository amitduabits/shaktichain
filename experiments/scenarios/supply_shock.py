"""
Supply Shock Scenario - Sudden reduction in available supply.
"""

from __future__ import annotations

from enum import Enum

import numpy as np

from .base_scenario import BaseScenario, ScenarioConfig, ScenarioState


class ShockType(Enum):
    """Types of supply shocks."""
    STEP_REDUCTION = "step_reduction"
    GRADUAL_REDUCTION = "gradual_reduction"
    OSCILLATING = "oscillating"
    CASCADING = "cascading"


class SupplyShockScenario(BaseScenario):
    """
    Supply shock scenario simulating sudden supply reduction.

    Features:
    - Shock event with configurable onset and duration
    - Recovery dynamics
    - Price pressure from scarcity
    - Panic behavior triggers
    """

    def __init__(
        self,
        base_demand_kwh: float = 1000.0,
        shock_magnitude: float = 0.4,
        shock_onset_hours: float = 4.0,
        shock_duration_hours: float = 2.0,
        recovery_hours: float = 1.0,
        shock_type: str = "step_reduction",
        duration_hours: int = 12,
    ):
        """
        Initialize supply shock scenario.

        Args:
            base_demand_kwh: Base demand level
            shock_magnitude: Fraction of supply reduction (0.4 = 40% reduction)
            shock_onset_hours: When shock begins
            shock_duration_hours: How long shock lasts
            recovery_hours: Recovery period
            shock_type: Type of shock pattern
            duration_hours: Total scenario duration
        """
        config = ScenarioConfig(
            name="supply_shock",
            description="Sudden supply reduction simulating grid failure or generation outage",
            duration_hours=duration_hours,
            base_demand_kwh=base_demand_kwh,
            volatility=0.15,
            warmup_periods=10,
            custom_params={
                "shock_magnitude": shock_magnitude,
                "shock_onset": shock_onset_hours,
                "shock_duration": shock_duration_hours,
                "recovery_hours": recovery_hours,
            },
        )
        super().__init__(config)

        self.shock_magnitude = shock_magnitude
        self.shock_onset = shock_onset_hours
        self.shock_duration = shock_duration_hours
        self.recovery_hours = recovery_hours
        self.shock_type = ShockType(shock_type)

        # Shock state
        self._shock_active = False
        self._recovery_active = False
        self._supply_factor = 1.0

    def get_demand(self, period: int) -> float:
        """
        Get demand during supply shock.

        Demand may spike initially (panic buying) then moderate.
        """
        hour = period % 24

        # Base diurnal pattern
        phase = 2 * np.pi * (hour - 15) / 24
        base_pattern = 0.5 * (1 - np.cos(phase))
        multiplier = 0.6 + 0.9 * base_pattern

        # Panic demand during shock onset
        period_hours = period / 60 if period < 60 else period  # Assume 1 period = 1 minute
        if self._shock_active and period_hours - self.shock_onset < 0.5:
            # Initial panic spike
            panic_factor = 1.3
        elif self._shock_active:
            # Demand destruction during prolonged shortage
            panic_factor = 0.9
        else:
            panic_factor = 1.0

        # Add noise
        noise = 1 + self._random_state.normal(0, self.config.volatility)

        demand = self.config.base_demand_kwh * multiplier * panic_factor * max(0.5, noise)

        self.state.demand_level = multiplier * panic_factor
        return demand

    def get_supply(self, period: int) -> float:
        """
        Get supply during shock scenario.

        Supply reduces during shock and recovers gradually.
        """
        period_hours = period / 60 if period > 60 else period / 10  # Approximate hours

        # Check if entering shock
        if not self._shock_active and period_hours >= self.shock_onset:
            if period_hours < self.shock_onset + self.shock_duration:
                self._shock_active = True
                self._recovery_active = False
                self.state.is_shock_active = True

        # Check if entering recovery
        if self._shock_active and period_hours >= self.shock_onset + self.shock_duration:
            self._shock_active = False
            self._recovery_active = True

        # Check if recovery complete
        if self._recovery_active:
            recovery_progress = (
                period_hours - (self.shock_onset + self.shock_duration)
            ) / self.recovery_hours
            if recovery_progress >= 1.0:
                self._recovery_active = False
                self.state.is_shock_active = False

        # Calculate supply factor
        if self._shock_active:
            self._supply_factor = self._calculate_shock_supply(period_hours)
        elif self._recovery_active:
            self._supply_factor = self._calculate_recovery_supply(period_hours)
        else:
            self._supply_factor = 1.0

        # Base supply
        base_supply = self.config.base_demand_kwh

        # Add some renewable variability
        noise = 1 + self._random_state.normal(0, 0.1)

        self.state.supply_level = self._supply_factor
        return base_supply * self._supply_factor * max(0.3, noise)

    def _calculate_shock_supply(self, period_hours: float) -> float:
        """Calculate supply factor during shock."""
        shock_progress = (period_hours - self.shock_onset) / self.shock_duration

        if self.shock_type == ShockType.STEP_REDUCTION:
            return 1.0 - self.shock_magnitude

        elif self.shock_type == ShockType.GRADUAL_REDUCTION:
            # Ramp down over shock duration
            return 1.0 - self.shock_magnitude * min(1.0, shock_progress * 2)

        elif self.shock_type == ShockType.OSCILLATING:
            # Fluctuating supply
            oscillation = 0.2 * np.sin(shock_progress * 4 * np.pi)
            return (1.0 - self.shock_magnitude) + oscillation

        elif self.shock_type == ShockType.CASCADING:
            # Gets worse over time
            cascade_factor = min(1.5, 1.0 + shock_progress * 0.5)
            return max(0.3, 1.0 - self.shock_magnitude * cascade_factor)

        return 1.0 - self.shock_magnitude

    def _calculate_recovery_supply(self, period_hours: float) -> float:
        """Calculate supply factor during recovery."""
        recovery_start = self.shock_onset + self.shock_duration
        recovery_progress = (period_hours - recovery_start) / self.recovery_hours
        recovery_progress = min(1.0, recovery_progress)

        # Supply recovers from shock level back to normal
        shock_level = 1.0 - self.shock_magnitude
        return shock_level + (1.0 - shock_level) * recovery_progress

    def get_price_factors(self, period: int) -> dict:
        """Get price factors during supply shock."""
        # Scarcity creates price pressure
        supply_constraint = 1.0 - self._supply_factor

        # Price spikes during shock
        if self._shock_active:
            base_multiplier = 1.5 + supply_constraint
            volatility_premium = 0.2
        elif self._recovery_active:
            base_multiplier = 1.2
            volatility_premium = 0.1
        else:
            base_multiplier = 1.0
            volatility_premium = 0.0

        return {
            "base_multiplier": base_multiplier,
            "demand_pressure": 0.0,
            "supply_pressure": supply_constraint * 0.5,
            "volatility_premium": volatility_premium,
        }

    def get_agent_adjustments(self, agent_type: str) -> dict:
        """Adjust agent behavior during supply shock."""
        if not self._shock_active:
            return {}

        if agent_type == "rational":
            return {
                "value_multiplier": 1.5,  # Higher urgency
                "risk_tolerance": 0.8,  # Less picky about price
            }
        elif agent_type == "behavioral":
            return {
                "loss_aversion_modifier": 2.0,  # Much more loss averse
                "panic_factor": 1.5,
            }
        elif agent_type == "bounded_rational":
            return {
                "aspiration_modifier": 0.7,  # Lower expectations
            }

        return {}

    def step(self) -> ScenarioState:
        """Advance to next period."""
        super().step()

        self.state.custom_data["shock_active"] = self._shock_active
        self.state.custom_data["recovery_active"] = self._recovery_active
        self.state.custom_data["supply_factor"] = self._supply_factor

        return self.state
