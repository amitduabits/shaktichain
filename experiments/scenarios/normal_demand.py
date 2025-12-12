"""
Normal Demand Scenario - Typical day-to-day market conditions.
"""

from __future__ import annotations

import numpy as np

from .base_scenario import BaseScenario, ScenarioConfig, ScenarioState


class NormalDemandScenario(BaseScenario):
    """
    Normal demand scenario with typical diurnal patterns.

    Features:
    - Standard 24-hour demand cycle
    - Moderate volatility
    - Normal supply conditions
    """

    def __init__(
        self,
        base_demand_kwh: float = 1000.0,
        peak_multiplier: float = 1.5,
        trough_multiplier: float = 0.6,
        volatility: float = 0.1,
        duration_hours: int = 24,
    ):
        """
        Initialize normal demand scenario.

        Args:
            base_demand_kwh: Base demand level
            peak_multiplier: Multiplier for peak hours
            trough_multiplier: Multiplier for off-peak hours
            volatility: Demand volatility
            duration_hours: Scenario duration
        """
        config = ScenarioConfig(
            name="normal_demand",
            description="Standard market conditions with typical demand patterns",
            duration_hours=duration_hours,
            base_demand_kwh=base_demand_kwh,
            volatility=volatility,
            warmup_periods=10,
        )
        super().__init__(config)

        self.peak_multiplier = peak_multiplier
        self.trough_multiplier = trough_multiplier

        # Peak hours: 2-6 PM (14-18)
        self.peak_hours = set(range(14, 18))
        # Off-peak: 10 PM - 6 AM
        self.off_peak_hours = set(range(22, 24)) | set(range(0, 6))

    def get_demand(self, period: int) -> float:
        """
        Get demand with diurnal pattern.

        Demand follows a sinusoidal pattern with peaks in afternoon
        and troughs at night.
        """
        hour = period % 24

        # Base pattern: sinusoidal with peak at 15:00 (3 PM)
        # Using cosine shifted to peak at 15
        phase = 2 * np.pi * (hour - 15) / 24
        pattern_factor = 0.5 * (1 - np.cos(phase))

        # Scale between trough and peak
        range_factor = self.peak_multiplier - self.trough_multiplier
        multiplier = self.trough_multiplier + range_factor * pattern_factor

        # Add Gaussian noise
        noise = 1 + self._random_state.normal(0, self.config.volatility)

        demand = self.config.base_demand_kwh * multiplier * max(0.5, noise)

        self.state.demand_level = multiplier
        return demand

    def get_supply(self, period: int) -> float:
        """
        Get supply for normal conditions.

        Supply is relatively stable with minor fluctuations.
        """
        hour = period % 24

        # Base supply matches average demand
        base_supply = self.config.base_demand_kwh

        # Slight variation based on time (e.g., solar during day)
        if 6 <= hour <= 18:
            # Daytime: slight increase from renewables
            solar_bonus = 0.15 * np.sin(np.pi * (hour - 6) / 12)
            supply_factor = 1.0 + solar_bonus
        else:
            supply_factor = 0.95

        # Small random fluctuation
        noise = 1 + self._random_state.normal(0, 0.05)

        self.state.supply_level = supply_factor
        return base_supply * supply_factor * noise

    def get_price_factors(self, period: int) -> dict:
        """Get price factors for normal conditions."""
        hour = period % 24

        # Time-of-use pricing influence
        if hour in self.peak_hours:
            tou_factor = 1.3
        elif hour in self.off_peak_hours:
            tou_factor = 0.7
        else:
            tou_factor = 1.0

        return {
            "base_multiplier": tou_factor,
            "demand_pressure": 0.0,
            "supply_pressure": 0.0,
            "volatility_premium": 0.0,
        }

    def step(self) -> ScenarioState:
        """Advance to next period."""
        super().step()

        hour = self.state.period % 24
        if hour in self.peak_hours:
            self.state.custom_data["period_type"] = "peak"
        elif hour in self.off_peak_hours:
            self.state.custom_data["period_type"] = "off_peak"
        else:
            self.state.custom_data["period_type"] = "standard"

        return self.state
