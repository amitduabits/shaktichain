"""
Synthetic Data Generator - Generate test data for SHAKTI-CHAIN experiments.

Generates demand curves, EV profiles, and agent valuations
following India-specific patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np


@dataclass
class EVProfile:
    """Profile of an electric vehicle."""
    ev_id: str
    battery_capacity_kwh: float
    current_soc: float
    arrival_time: float  # Hour of day
    departure_time: float  # Hour of day
    charging_rate_kw: float
    discharging_rate_kw: float
    min_soc: float = 0.2
    target_soc: float = 0.8


@dataclass
class DemandPoint:
    """A single demand data point."""
    timestamp: datetime
    hour: int
    demand_kwh: float
    temperature_c: float
    is_holiday: bool
    is_weekend: bool


@dataclass
class AgentValuation:
    """Valuation parameters for an agent."""
    agent_id: str
    value_per_kwh: float
    cost_per_kwh: float
    risk_aversion: float
    time_preference: float  # Discount rate


class SyntheticDataGenerator:
    """
    Generator for synthetic test data.

    Produces realistic patterns for:
    - Demand curves (India-specific diurnal and seasonal patterns)
    - EV arrival/departure distributions
    - Battery SoC distributions
    - Agent valuations
    """

    def __init__(
        self,
        random_seed: int = 42,
        base_demand_kwh: float = 1000.0,
    ):
        """
        Initialize the generator.

        Args:
            random_seed: Random seed for reproducibility
            base_demand_kwh: Base demand level
        """
        self.random_seed = random_seed
        self.base_demand_kwh = base_demand_kwh
        self._rng = np.random.RandomState(random_seed)

        # India-specific parameters
        self._peak_hours = [14, 15, 16, 17]  # 2-5 PM
        self._morning_peak = [8, 9, 10]
        self._evening_peak = [18, 19, 20, 21]
        self._off_peak = list(range(0, 6)) + [22, 23]

    def generate_demand_curve(
        self,
        start_date: datetime,
        num_days: int = 7,
        city: str = "Delhi",
        include_weather: bool = True,
    ) -> list[DemandPoint]:
        """
        Generate a demand curve for multiple days.

        Args:
            start_date: Starting date
            num_days: Number of days to generate
            city: City for weather correlation
            include_weather: Whether to include weather effects

        Returns:
            List of DemandPoint objects
        """
        demand_points = []

        for day in range(num_days):
            current_date = start_date + timedelta(days=day)
            is_weekend = current_date.weekday() >= 5
            is_holiday = self._check_holiday(current_date)

            # Temperature pattern (India-specific)
            base_temp = self._get_base_temperature(city, current_date)

            for hour in range(24):
                timestamp = current_date.replace(hour=hour, minute=0, second=0)

                # Temperature for this hour
                temp = self._get_hourly_temperature(base_temp, hour)

                # Demand calculation
                demand = self._calculate_hourly_demand(
                    hour=hour,
                    temperature=temp if include_weather else 30.0,
                    is_weekend=is_weekend,
                    is_holiday=is_holiday,
                )

                demand_points.append(DemandPoint(
                    timestamp=timestamp,
                    hour=hour,
                    demand_kwh=demand,
                    temperature_c=temp,
                    is_holiday=is_holiday,
                    is_weekend=is_weekend,
                ))

        return demand_points

    def _calculate_hourly_demand(
        self,
        hour: int,
        temperature: float,
        is_weekend: bool,
        is_holiday: bool,
    ) -> float:
        """Calculate demand for a specific hour."""
        # Base diurnal pattern
        phase = 2 * np.pi * (hour - 15) / 24
        diurnal = 0.5 * (1 - np.cos(phase))

        # Scale between 0.5 and 1.5 of base
        multiplier = 0.6 + 0.9 * diurnal

        # Weekend effect
        if is_weekend or is_holiday:
            if hour in self._morning_peak:
                multiplier *= 0.85  # Less morning demand
            elif hour in self._evening_peak:
                multiplier *= 1.1  # More evening demand
            else:
                multiplier *= 0.9

        # Temperature effect (AC load)
        if temperature > 30:
            temp_factor = 1 + 0.03 * (temperature - 30)
            multiplier *= temp_factor

        # Add noise
        noise = 1 + self._rng.normal(0, 0.08)

        return self.base_demand_kwh * multiplier * max(0.5, noise)

    def _get_base_temperature(self, city: str, date: datetime) -> float:
        """Get base temperature for a city on a given date."""
        # Simplified seasonal pattern
        month = date.month

        # City-specific base temperatures (approximate averages)
        city_temps = {
            "Delhi": [14, 17, 23, 30, 35, 38, 35, 33, 32, 28, 21, 15],
            "Mumbai": [24, 25, 27, 30, 32, 30, 28, 28, 28, 29, 27, 25],
            "Bangalore": [21, 23, 26, 28, 27, 24, 23, 23, 24, 24, 22, 20],
            "Chennai": [25, 26, 28, 31, 34, 34, 32, 31, 30, 29, 27, 25],
            "Kolkata": [19, 23, 28, 32, 33, 32, 31, 31, 31, 29, 25, 20],
        }

        temps = city_temps.get(city, city_temps["Delhi"])
        return temps[month - 1]

    def _get_hourly_temperature(self, base_temp: float, hour: int) -> float:
        """Get temperature for a specific hour."""
        # Temperature varies through the day
        # Min around 5 AM, max around 2 PM
        phase = 2 * np.pi * (hour - 14) / 24
        variation = 5 * np.cos(phase)

        return base_temp + variation + self._rng.normal(0, 1)

    def _check_holiday(self, date: datetime) -> bool:
        """Check if date is a holiday (simplified)."""
        # Major Indian holidays (approximate)
        holidays = [
            (1, 26),   # Republic Day
            (8, 15),   # Independence Day
            (10, 2),   # Gandhi Jayanti
        ]

        return (date.month, date.day) in holidays

    def generate_ev_fleet(
        self,
        num_vehicles: int,
        fleet_type: str = "mixed",
    ) -> list[EVProfile]:
        """
        Generate a fleet of EV profiles.

        Args:
            num_vehicles: Number of vehicles
            fleet_type: "residential", "commercial", or "mixed"

        Returns:
            List of EVProfile objects
        """
        profiles = []

        # Battery capacity distribution
        capacity_options = [30, 40, 50, 60, 75, 100]
        capacity_probs = [0.1, 0.2, 0.3, 0.25, 0.1, 0.05]

        for i in range(num_vehicles):
            # Battery capacity
            capacity = self._rng.choice(capacity_options, p=capacity_probs)

            # SoC distribution (beta distribution)
            soc = self._rng.beta(2, 3)  # Skewed towards lower SoC

            # Arrival/departure based on fleet type
            if fleet_type == "residential":
                arrival, departure = self._residential_schedule()
            elif fleet_type == "commercial":
                arrival, departure = self._commercial_schedule()
            else:
                if self._rng.random() < 0.6:
                    arrival, departure = self._residential_schedule()
                else:
                    arrival, departure = self._commercial_schedule()

            # Charging/discharging rates
            charging_rate = self._rng.choice([3.3, 7.4, 11.0, 22.0], p=[0.2, 0.4, 0.3, 0.1])
            discharging_rate = min(charging_rate, 11.0)

            profiles.append(EVProfile(
                ev_id=f"ev_{i:04d}",
                battery_capacity_kwh=capacity,
                current_soc=soc,
                arrival_time=arrival,
                departure_time=departure,
                charging_rate_kw=charging_rate,
                discharging_rate_kw=discharging_rate,
                min_soc=0.2,
                target_soc=0.8 + self._rng.uniform(-0.1, 0.1),
            ))

        return profiles

    def _residential_schedule(self) -> tuple[float, float]:
        """Generate residential EV schedule."""
        # Arrive home: 5-8 PM
        arrival = 17 + self._rng.exponential(1.5)
        arrival = min(22, max(16, arrival))

        # Leave: 7-9 AM next day
        departure = 7 + self._rng.exponential(1.0)
        departure = min(10, max(6, departure))

        return arrival, departure

    def _commercial_schedule(self) -> tuple[float, float]:
        """Generate commercial EV schedule."""
        # Arrive at work: 8-10 AM
        arrival = 8 + self._rng.exponential(1.0)
        arrival = min(11, max(7, arrival))

        # Leave: 5-7 PM
        departure = 17 + self._rng.exponential(1.0)
        departure = min(20, max(16, departure))

        return arrival, departure

    def generate_agent_valuations(
        self,
        num_agents: int,
        distribution: str = "heterogeneous",
    ) -> list[AgentValuation]:
        """
        Generate agent valuations.

        Args:
            num_agents: Number of agents
            distribution: "homogeneous", "heterogeneous", or "bimodal"

        Returns:
            List of AgentValuation objects
        """
        valuations = []

        for i in range(num_agents):
            if distribution == "homogeneous":
                value = 7.0 + self._rng.normal(0, 0.5)
                cost = 4.0 + self._rng.normal(0, 0.5)
            elif distribution == "bimodal":
                if self._rng.random() < 0.5:
                    value = 5.0 + self._rng.normal(0, 0.5)
                    cost = 3.0 + self._rng.normal(0, 0.3)
                else:
                    value = 9.0 + self._rng.normal(0, 0.5)
                    cost = 5.0 + self._rng.normal(0, 0.3)
            else:  # heterogeneous
                value = self._rng.uniform(4.0, 12.0)
                cost = self._rng.uniform(2.0, 6.0)

            # Ensure value > cost
            if value <= cost:
                value, cost = cost + 1.0, value - 1.0

            valuations.append(AgentValuation(
                agent_id=f"agent_{i:04d}",
                value_per_kwh=max(2.0, value),
                cost_per_kwh=max(1.0, cost),
                risk_aversion=self._rng.uniform(0.0, 2.0),
                time_preference=self._rng.uniform(0.9, 0.99),
            ))

        return valuations

    def generate_order_book(
        self,
        num_orders: int,
        mid_price: float = 6.0,
        spread_pct: float = 0.1,
    ) -> tuple[list[dict], list[dict]]:
        """
        Generate a synthetic order book.

        Args:
            num_orders: Total number of orders
            mid_price: Mid-market price
            spread_pct: Spread as percentage of mid price

        Returns:
            Tuple of (bids, asks)
        """
        bids = []
        asks = []

        half_spread = mid_price * spread_pct / 2

        for i in range(num_orders // 2):
            # Bid side
            bid_price = mid_price - half_spread - self._rng.exponential(0.5)
            bid_qty = self._rng.exponential(5.0)

            bids.append({
                "price": max(0.5, bid_price),
                "quantity": max(0.1, bid_qty),
                "agent_id": f"buyer_{i}",
            })

            # Ask side
            ask_price = mid_price + half_spread + self._rng.exponential(0.5)
            ask_qty = self._rng.exponential(5.0)

            asks.append({
                "price": ask_price,
                "quantity": max(0.1, ask_qty),
                "agent_id": f"seller_{i}",
            })

        return bids, asks

    def generate_price_series(
        self,
        num_periods: int,
        initial_price: float = 6.0,
        volatility: float = 0.1,
        mean_reversion: float = 0.1,
    ) -> list[float]:
        """
        Generate a synthetic price series.

        Uses Ornstein-Uhlenbeck process for mean reversion.

        Args:
            num_periods: Number of periods
            initial_price: Starting price
            volatility: Price volatility
            mean_reversion: Mean reversion speed

        Returns:
            List of prices
        """
        prices = [initial_price]
        long_term_mean = initial_price

        for _ in range(num_periods - 1):
            current = prices[-1]

            # OU process: dP = θ(μ - P)dt + σdW
            drift = mean_reversion * (long_term_mean - current)
            diffusion = volatility * self._rng.normal()

            new_price = current + drift + diffusion
            prices.append(max(0.5, new_price))

        return prices
