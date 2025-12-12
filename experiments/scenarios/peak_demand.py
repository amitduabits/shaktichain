"""
Peak Demand Scenario - Extreme demand conditions (summer afternoon in Delhi).
"""

from __future__ import annotations

import numpy as np

from .base_scenario import BaseScenario, ScenarioConfig, ScenarioState


class PeakDemandScenario(BaseScenario):
    """
    Peak demand scenario simulating extreme conditions.

    Features:
    - Sustained high demand
    - Temperature-driven AC load
    - Grid stress conditions
    - Higher price volatility
    """

    def __init__(
        self,
        base_demand_kwh: float = 1000.0,
        peak_multiplier: float = 2.5,
        temperature_c: float = 45.0,
        duration_hours: int = 6,
        grid_stress_probability: float = 0.1,
    ):
        """
        Initialize peak demand scenario.

        Args:
            base_demand_kwh: Base demand level
            peak_multiplier: Peak demand multiplier
            temperature_c: Ambient temperature
            duration_hours: Duration of peak period
            grid_stress_probability: Probability of grid stress events
        """
        config = ScenarioConfig(
            name="peak_demand",
            description="Extreme peak demand during summer afternoon",
            duration_hours=duration_hours,
            base_demand_kwh=base_demand_kwh,
            volatility=0.2,
            warmup_periods=5,
            custom_params={
                "temperature_c": temperature_c,
                "grid_stress_prob": grid_stress_probability,
            },
        )
        super().__init__(config)

        self.peak_multiplier = peak_multiplier
        self.temperature_c = temperature_c
        self.grid_stress_probability = grid_stress_probability

        # Track grid stress events
        self._grid_stressed = False
        self._stress_duration = 0

    def get_demand(self, period: int) -> float:
        """
        Get demand during peak conditions.

        Demand is driven by temperature-sensitive AC load.
        """
        hour = period % 24

        # Temperature effect on demand
        # Demand increases ~3% per degree above 25°C
        temp_effect = 1.0 + 0.03 * max(0, self.temperature_c - 25)

        # Intraday pattern during peak hours (assuming 2-8 PM)
        base_hour = 14  # Start of peak
        if 0 <= period < self.config.duration_hours:
            # Ramp up, plateau, ramp down
            relative_hour = period
            if relative_hour < 2:
                # Ramp up
                pattern = 0.8 + 0.2 * (relative_hour / 2)
            elif relative_hour < self.config.duration_hours - 1:
                # Plateau
                pattern = 1.0
            else:
                # Ramp down
                pattern = 0.9
        else:
            pattern = 0.8

        # High volatility noise
        noise = 1 + self._random_state.normal(0, self.config.volatility)

        # Combined multiplier
        multiplier = self.peak_multiplier * temp_effect * pattern

        demand = self.config.base_demand_kwh * multiplier * max(0.7, noise)

        self.state.demand_level = multiplier
        return demand

    def get_supply(self, period: int) -> float:
        """
        Get supply during peak conditions.

        Supply may be constrained due to grid stress.
        """
        # Base supply
        base_supply = self.config.base_demand_kwh

        # Solar contribution (high during afternoon)
        hour = 14 + (period % self.config.duration_hours)
        if 10 <= hour <= 18:
            solar_factor = 0.4 * np.sin(np.pi * (hour - 6) / 12)
        else:
            solar_factor = 0.0

        supply_factor = 1.0 + solar_factor

        # Grid stress events
        if self._grid_stressed:
            self._stress_duration -= 1
            if self._stress_duration <= 0:
                self._grid_stressed = False
            supply_factor *= 0.8  # 20% reduction during stress
        else:
            if self._random_state.random() < self.grid_stress_probability:
                self._grid_stressed = True
                self._stress_duration = self._random_state.randint(1, 4)
                supply_factor *= 0.8

        self.state.supply_level = supply_factor
        self.state.is_shock_active = self._grid_stressed

        return base_supply * supply_factor

    def get_price_factors(self, period: int) -> dict:
        """Get price factors for peak conditions."""
        # Scarcity premium during peak
        demand_supply_ratio = self.state.demand_level / max(0.1, self.state.supply_level)

        demand_pressure = max(0, (demand_supply_ratio - 1) * 0.5)

        # Grid stress premium
        stress_premium = 0.3 if self._grid_stressed else 0.0

        return {
            "base_multiplier": 1.5,  # Peak TOU rate
            "demand_pressure": demand_pressure,
            "supply_pressure": stress_premium,
            "volatility_premium": 0.1,
        }

    def get_agent_adjustments(self, agent_type: str) -> dict:
        """
        Adjust agent behavior for peak conditions.

        During peak demand, rational agents should be more willing
        to pay higher prices; sellers should hold out for better prices.
        """
        if agent_type == "rational":
            return {
                "value_multiplier": 1.2,  # Higher willingness to pay
                "bid_aggressiveness": 1.1,
            }
        elif agent_type == "behavioral":
            return {
                "loss_aversion_modifier": 1.3,  # More loss averse
                "herding_strength": 1.2,  # More herding
            }
        return {}

    def step(self) -> ScenarioState:
        """Advance to next period."""
        super().step()

        self.state.custom_data["temperature_c"] = self.temperature_c
        self.state.custom_data["grid_stressed"] = self._grid_stressed

        return self.state
