"""
High Volatility Scenario - Unstable market with rapid price changes.
"""

from __future__ import annotations

import numpy as np

from .base_scenario import BaseScenario, ScenarioConfig, ScenarioState


class HighVolatilityScenario(BaseScenario):
    """
    High volatility scenario with rapid price swings.

    Features:
    - Jump-diffusion process for demand/supply
    - High renewable intermittency
    - GARCH-like volatility clustering
    - Weather-driven fluctuations
    """

    def __init__(
        self,
        base_demand_kwh: float = 1000.0,
        volatility: float = 0.35,
        jump_intensity: float = 0.1,
        jump_mean: float = 0.0,
        jump_std: float = 0.3,
        renewable_fraction: float = 0.5,
        garch_persistence: float = 0.85,
        duration_hours: int = 24,
    ):
        """
        Initialize high volatility scenario.

        Args:
            base_demand_kwh: Base demand level
            volatility: Base volatility level
            jump_intensity: Probability of jump per period
            jump_mean: Mean of jump size
            jump_std: Std of jump size
            renewable_fraction: Fraction of supply from renewables
            garch_persistence: GARCH volatility persistence
            duration_hours: Scenario duration
        """
        config = ScenarioConfig(
            name="high_volatility",
            description="Highly volatile market conditions with rapid price swings",
            duration_hours=duration_hours,
            base_demand_kwh=base_demand_kwh,
            volatility=volatility,
            warmup_periods=20,
        )
        super().__init__(config)

        self.jump_intensity = jump_intensity
        self.jump_mean = jump_mean
        self.jump_std = jump_std
        self.renewable_fraction = renewable_fraction
        self.garch_persistence = garch_persistence

        # State variables
        self._current_volatility = volatility
        self._last_return = 0.0
        self._cloud_cover = 0.0
        self._wind_speed = 1.0

    def get_demand(self, period: int) -> float:
        """
        Get demand with jump-diffusion process.

        Demand follows a volatile pattern with occasional jumps.
        """
        hour = period % 24

        # Base diurnal pattern
        phase = 2 * np.pi * (hour - 15) / 24
        base_pattern = 0.4 + 0.8 * (0.5 * (1 - np.cos(phase)))

        # Jump-diffusion component
        # Continuous diffusion
        diffusion = self._random_state.normal(0, self._current_volatility)

        # Jump component (Poisson process)
        if self._random_state.random() < self.jump_intensity:
            jump = self._random_state.normal(self.jump_mean, self.jump_std)
        else:
            jump = 0.0

        # Combined return
        total_return = diffusion + jump
        self._last_return = total_return

        # Update GARCH volatility
        self._update_volatility()

        # Apply to demand
        demand_factor = base_pattern * (1 + total_return)
        demand_factor = max(0.3, min(2.5, demand_factor))

        demand = self.config.base_demand_kwh * demand_factor

        self.state.demand_level = demand_factor
        self.state.volatility = self._current_volatility

        return demand

    def get_supply(self, period: int) -> float:
        """
        Get supply with high renewable intermittency.

        Solar and wind vary significantly based on weather.
        """
        hour = period % 24

        # Update weather conditions
        self._update_weather()

        # Conventional supply (stable)
        conventional_fraction = 1.0 - self.renewable_fraction
        conventional_supply = (
            self.config.base_demand_kwh * conventional_fraction *
            (1 + self._random_state.normal(0, 0.05))
        )

        # Solar component
        if 6 <= hour <= 18:
            solar_potential = np.sin(np.pi * (hour - 6) / 12)
            solar_actual = solar_potential * (1 - self._cloud_cover)
        else:
            solar_actual = 0.0

        # Wind component (more variable)
        wind_actual = self._wind_speed * (0.5 + 0.5 * self._random_state.random())

        # Combined renewable (50% solar, 50% wind)
        renewable_factor = 0.5 * solar_actual + 0.5 * wind_actual
        renewable_supply = (
            self.config.base_demand_kwh * self.renewable_fraction * renewable_factor
        )

        total_supply = conventional_supply + renewable_supply

        self.state.supply_level = total_supply / self.config.base_demand_kwh

        return total_supply

    def _update_volatility(self) -> None:
        """Update volatility using GARCH-like process."""
        # GARCH(1,1): σ²_t = ω + α*ε²_{t-1} + β*σ²_{t-1}
        omega = self.config.volatility * (1 - self.garch_persistence)
        alpha = 0.1
        beta = self.garch_persistence - alpha

        variance = (
            omega +
            alpha * self._last_return ** 2 +
            beta * self._current_volatility ** 2
        )

        self._current_volatility = np.sqrt(max(0.05, min(1.0, variance)))

    def _update_weather(self) -> None:
        """Update weather conditions (cloud cover, wind)."""
        # Cloud cover: Markov process
        cloud_change = self._random_state.normal(0, 0.1)
        self._cloud_cover = max(0, min(1, self._cloud_cover + cloud_change))

        # Occasional rapid cloud transitions
        if self._random_state.random() < 0.05:
            if self._cloud_cover < 0.5:
                self._cloud_cover = min(1.0, self._cloud_cover + 0.4)
            else:
                self._cloud_cover = max(0.0, self._cloud_cover - 0.4)

        # Wind speed: Mean-reverting
        wind_mean = 1.0
        wind_reversion = 0.3
        wind_change = (
            wind_reversion * (wind_mean - self._wind_speed) +
            self._random_state.normal(0, 0.2)
        )
        self._wind_speed = max(0.1, min(2.0, self._wind_speed + wind_change))

    def get_price_factors(self, period: int) -> dict:
        """Get price factors during high volatility."""
        # Volatility premium
        vol_premium = (self._current_volatility - self.config.volatility) / self.config.volatility
        vol_premium = max(-0.2, min(0.5, vol_premium))

        # Supply-demand imbalance
        imbalance = self.state.demand_level - self.state.supply_level
        imbalance_factor = imbalance * 0.3

        return {
            "base_multiplier": 1.0,
            "demand_pressure": max(0, imbalance_factor),
            "supply_pressure": max(0, -imbalance_factor),
            "volatility_premium": vol_premium,
        }

    def get_agent_adjustments(self, agent_type: str) -> dict:
        """Adjust agent behavior for high volatility."""
        if agent_type == "rational":
            return {
                "risk_aversion_modifier": 1.5,  # More risk averse
                "bid_shading_modifier": 0.9,  # More conservative
            }
        elif agent_type == "behavioral":
            return {
                "recency_bias_modifier": 1.3,
                "overconfidence_modifier": 0.7,  # Less overconfident
            }
        elif agent_type == "bounded_rational":
            return {
                "aspiration_volatility": 0.2,  # Aspirations fluctuate more
            }

        return {}

    def step(self) -> ScenarioState:
        """Advance to next period."""
        super().step()

        self.state.custom_data["current_volatility"] = self._current_volatility
        self.state.custom_data["cloud_cover"] = self._cloud_cover
        self.state.custom_data["wind_speed"] = self._wind_speed
        self.state.custom_data["last_return"] = self._last_return

        return self.state
