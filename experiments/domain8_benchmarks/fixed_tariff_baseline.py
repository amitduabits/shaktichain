"""
Fixed Tariff Baseline for SHAKTI-CHAIN Benchmarking (Domain 8).

Implements Indian DISCOM (Distribution Company) fixed tariff rates
for comparison with SHAKTI-CHAIN P2P energy trading.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DISCOMTariff:
    """
    DISCOM (Distribution Company) tariff structure.

    Attributes:
        name: Tariff name
        utility: Utility company name
        rates: Time-of-day rates (period -> rate in INR/kWh)
        slabs: Usage slabs [(usage_limit, rate), ...]
        fixed_charge: Monthly fixed charge in INR
        demand_charge: Per kVA demand charge (if applicable)
    """
    name: str
    utility: str
    rates: Dict[str, float]  # Time period -> rate (INR/kWh)
    slabs: List[Tuple[float, float]]  # (usage_limit_kWh, rate)
    fixed_charge: float = 0.0
    demand_charge: float = 0.0

    def get_rate_for_time(self, hour: int) -> float:
        """Get rate for given hour of day."""
        for period, rate in self.rates.items():
            start, end = period.split('-')
            start_hour = int(start.split(':')[0])
            end_hour = int(end.split(':')[0])

            if start_hour <= hour < end_hour:
                return rate
            # Handle overnight periods (e.g., 22:00-06:00)
            if start_hour > end_hour:
                if hour >= start_hour or hour < end_hour:
                    return rate

        # Default to first rate if no match
        return list(self.rates.values())[0]

    def get_slab_rate(self, monthly_usage_kwh: float) -> float:
        """Get rate based on usage slab."""
        for limit, rate in self.slabs:
            if monthly_usage_kwh <= limit:
                return rate
        return self.slabs[-1][1]  # Highest slab

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "utility": self.utility,
            "rates": self.rates,
            "slabs": self.slabs,
            "fixed_charge": self.fixed_charge,
            "demand_charge": self.demand_charge,
        }


# Real Indian DISCOM tariffs (2024 rates)
BSES_DELHI = DISCOMTariff(
    name="BSES Delhi Domestic",
    utility="BSES Rajdhani/Yamuna",
    rates={
        '00:00-06:00': 3.0,   # Off-peak
        '06:00-14:00': 5.5,   # Standard
        '14:00-18:00': 8.0,   # Peak
        '18:00-22:00': 5.5,   # Standard
        '22:00-24:00': 3.0,   # Off-peak
    },
    slabs=[
        (200, 3.0),
        (400, 4.5),
        (800, 6.5),
        (1200, 7.0),
        (float('inf'), 8.0)
    ],
    fixed_charge=125.0,  # Monthly
)

TATA_MUMBAI = DISCOMTariff(
    name="Tata Power Mumbai",
    utility="Tata Power",
    rates={
        '00:00-07:00': 4.0,   # Off-peak
        '07:00-11:00': 6.0,   # Standard
        '11:00-17:00': 7.5,   # Peak
        '17:00-23:00': 6.0,   # Standard
        '23:00-24:00': 4.0,   # Off-peak
    },
    slabs=[
        (100, 3.79),
        (300, 5.96),
        (500, 8.29),
        (float('inf'), 10.65)
    ],
    fixed_charge=100.0,
)

BESCOM_BANGALORE = DISCOMTariff(
    name="BESCOM Bangalore Domestic",
    utility="BESCOM",
    rates={
        '00:00-06:00': 4.15,   # Off-peak
        '06:00-10:00': 5.80,   # Morning peak
        '10:00-18:00': 6.40,   # Daytime
        '18:00-22:00': 7.60,   # Evening peak
        '22:00-24:00': 4.15,   # Off-peak
    },
    slabs=[
        (30, 4.15),
        (100, 5.45),
        (200, 6.80),
        (float('inf'), 7.85)
    ],
    fixed_charge=40.0,
)

TNEB_CHENNAI = DISCOMTariff(
    name="TANGEDCO Chennai Domestic",
    utility="TANGEDCO",
    rates={
        '00:00-06:00': 3.50,
        '06:00-18:00': 5.50,
        '18:00-22:00': 7.00,
        '22:00-24:00': 3.50,
    },
    slabs=[
        (100, 0.0),  # Free up to 100 units
        (200, 2.0),
        (500, 3.0),
        (float('inf'), 6.0)
    ],
    fixed_charge=30.0,
)

CESC_KOLKATA = DISCOMTariff(
    name="CESC Kolkata Domestic",
    utility="CESC",
    rates={
        '00:00-06:00': 4.84,
        '06:00-17:00': 6.44,
        '17:00-21:00': 7.50,
        '21:00-24:00': 4.84,
    },
    slabs=[
        (25, 4.84),
        (60, 5.38),
        (100, 5.92),
        (200, 6.44),
        (300, 6.98),
        (float('inf'), 7.52)
    ],
    fixed_charge=50.0,
)

HPSEBL_HYDERABAD = DISCOMTariff(
    name="TSSPDCL Hyderabad Domestic",
    utility="TSSPDCL",
    rates={
        '00:00-06:00': 3.80,
        '06:00-10:00': 5.60,
        '10:00-18:00': 6.20,
        '18:00-22:00': 7.40,
        '22:00-24:00': 3.80,
    },
    slabs=[
        (50, 1.45),
        (100, 2.60),
        (200, 3.60),
        (300, 5.20),
        (float('inf'), 7.80)
    ],
    fixed_charge=45.0,
)

# All DISCOM tariffs
INDIA_DISCOM_TARIFFS = {
    "Delhi": BSES_DELHI,
    "Mumbai": TATA_MUMBAI,
    "Bangalore": BESCOM_BANGALORE,
    "Chennai": TNEB_CHENNAI,
    "Kolkata": CESC_KOLKATA,
    "Hyderabad": HPSEBL_HYDERABAD,
}


@dataclass
class FixedTariffResult:
    """
    Result from fixed tariff simulation.

    Attributes:
        total_revenue: Total revenue for sellers (INR)
        total_cost: Total cost for buyers (INR)
        net_profit: Net profit (revenue - cost)
        roi_pct: Return on investment percentage
        average_rate: Average rate paid (INR/kWh)
        energy_traded_kwh: Total energy traded
        agent_rois: Per-agent ROI values
    """
    total_revenue: float
    total_cost: float
    net_profit: float
    roi_pct: float
    average_rate: float
    energy_traded_kwh: float
    agent_rois: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_revenue": self.total_revenue,
            "total_cost": self.total_cost,
            "net_profit": self.net_profit,
            "roi_pct": self.roi_pct,
            "average_rate": self.average_rate,
            "energy_traded_kwh": self.energy_traded_kwh,
            "mean_agent_roi": float(np.mean(self.agent_rois)) if self.agent_rois else 0.0,
        }


class FixedTariffSimulator:
    """
    Simulator for fixed DISCOM tariff trading.

    Used as baseline for comparison with SHAKTI-CHAIN P2P trading.
    """

    def __init__(self, tariff: DISCOMTariff):
        """
        Initialize simulator.

        Args:
            tariff: DISCOM tariff structure
        """
        self.tariff = tariff

    def calculate_revenue(
        self,
        energy_sold_kwh: List[Tuple[datetime, float]],
        feed_in_tariff_discount: float = 0.7,
    ) -> float:
        """
        Calculate revenue from selling energy to grid.

        In fixed tariff model, prosumers sell at feed-in tariff,
        typically lower than retail rate.

        Args:
            energy_sold_kwh: List of (timestamp, kwh) tuples
            feed_in_tariff_discount: FIT as fraction of retail rate

        Returns:
            Total revenue in INR
        """
        total_revenue = 0.0

        for timestamp, kwh in energy_sold_kwh:
            hour = timestamp.hour if isinstance(timestamp, datetime) else int(timestamp)
            rate = self.tariff.get_rate_for_time(hour)
            fit_rate = rate * feed_in_tariff_discount
            total_revenue += kwh * fit_rate

        return total_revenue

    def calculate_cost(
        self,
        energy_bought_kwh: List[Tuple[datetime, float]],
        monthly_usage_kwh: float = 300.0,
    ) -> float:
        """
        Calculate cost of buying from grid.

        Args:
            energy_bought_kwh: List of (timestamp, kwh) tuples
            monthly_usage_kwh: Monthly usage for slab calculation

        Returns:
            Total cost in INR
        """
        total_cost = 0.0

        for timestamp, kwh in energy_bought_kwh:
            hour = timestamp.hour if isinstance(timestamp, datetime) else int(timestamp)

            # Get time-of-use rate
            tou_rate = self.tariff.get_rate_for_time(hour)

            # Get slab rate
            slab_rate = self.tariff.get_slab_rate(monthly_usage_kwh)

            # Use maximum of ToU and slab rate
            effective_rate = max(tou_rate, slab_rate)
            total_cost += kwh * effective_rate

        return total_cost

    def simulate_agents(
        self,
        n_agents: int,
        duration_hours: int,
        prosumer_fraction: float = 0.3,
        avg_consumption_kwh: float = 10.0,
        avg_generation_kwh: float = 5.0,
        seed: Optional[int] = None,
    ) -> FixedTariffResult:
        """
        Simulate agents trading at DISCOM rates.

        Args:
            n_agents: Number of agents
            duration_hours: Simulation duration
            prosumer_fraction: Fraction of agents that are prosumers
            avg_consumption_kwh: Average consumption per agent per hour
            avg_generation_kwh: Average generation for prosumers
            seed: Random seed

        Returns:
            FixedTariffResult with agent ROIs
        """
        rng = np.random.default_rng(seed)

        n_prosumers = int(n_agents * prosumer_fraction)
        n_consumers = n_agents - n_prosumers

        agent_rois = []
        total_revenue = 0.0
        total_cost = 0.0
        total_energy = 0.0

        # Simulate prosumers
        for _ in range(n_prosumers):
            agent_cost = 0.0
            agent_revenue = 0.0
            agent_investment = rng.uniform(50000, 200000)  # Solar panel investment

            for hour in range(duration_hours):
                # Generate energy during day (6 AM - 6 PM)
                if 6 <= (hour % 24) < 18:
                    generation = rng.normal(avg_generation_kwh, avg_generation_kwh * 0.2)
                    generation = max(0, generation)
                else:
                    generation = 0

                # Consume energy
                consumption = rng.normal(avg_consumption_kwh, avg_consumption_kwh * 0.3)
                consumption = max(0, consumption)

                # Net energy
                net = generation - consumption

                timestamp = datetime(2024, 1, 1) + timedelta(hours=hour)

                if net > 0:
                    # Sell excess to grid
                    revenue = self.calculate_revenue([(timestamp, net)])
                    agent_revenue += revenue
                else:
                    # Buy from grid
                    cost = self.calculate_cost([(timestamp, abs(net))])
                    agent_cost += cost

                total_energy += max(generation, consumption)

            # Calculate ROI
            net_profit = agent_revenue - agent_cost
            roi = (net_profit / agent_investment) * 100 if agent_investment > 0 else 0
            agent_rois.append(roi)

            total_revenue += agent_revenue
            total_cost += agent_cost

        # Simulate pure consumers
        for _ in range(n_consumers):
            agent_cost = 0.0

            for hour in range(duration_hours):
                consumption = rng.normal(avg_consumption_kwh, avg_consumption_kwh * 0.3)
                consumption = max(0, consumption)

                timestamp = datetime(2024, 1, 1) + timedelta(hours=hour)
                cost = self.calculate_cost([(timestamp, consumption)])
                agent_cost += cost
                total_energy += consumption

            # Consumer ROI is negative (no investment, just cost)
            # For fair comparison, use cost savings as "ROI" base
            baseline_cost = avg_consumption_kwh * duration_hours * 6.0  # Avg rate
            roi = ((baseline_cost - agent_cost) / baseline_cost) * 100
            agent_rois.append(roi)

            total_cost += agent_cost

        net_profit = total_revenue - total_cost
        avg_rate = total_cost / total_energy if total_energy > 0 else 0

        return FixedTariffResult(
            total_revenue=total_revenue,
            total_cost=total_cost,
            net_profit=net_profit,
            roi_pct=float(np.mean(agent_rois)),
            average_rate=avg_rate,
            energy_traded_kwh=total_energy,
            agent_rois=agent_rois,
        )

    def compare_with_p2p(
        self,
        p2p_revenue: float,
        p2p_cost: float,
        energy_kwh: float,
    ) -> Dict[str, float]:
        """
        Compare fixed tariff with P2P trading outcomes.

        Args:
            p2p_revenue: Revenue from P2P trading
            p2p_cost: Cost from P2P trading
            energy_kwh: Total energy traded

        Returns:
            Comparison metrics
        """
        # Calculate what fixed tariff would have been
        avg_hours = 720  # Assume monthly

        # Approximate fixed tariff results
        fixed_revenue = energy_kwh * 0.5 * np.mean(list(self.tariff.rates.values())) * 0.7
        fixed_cost = energy_kwh * 0.5 * np.mean(list(self.tariff.rates.values()))

        p2p_profit = p2p_revenue - p2p_cost
        fixed_profit = fixed_revenue - fixed_cost

        return {
            "p2p_profit": p2p_profit,
            "fixed_profit": fixed_profit,
            "profit_improvement": p2p_profit - fixed_profit,
            "profit_improvement_pct": ((p2p_profit - fixed_profit) / abs(fixed_profit)) * 100 if fixed_profit != 0 else 0,
            "p2p_avg_rate": (p2p_revenue + p2p_cost) / (2 * energy_kwh) if energy_kwh > 0 else 0,
            "fixed_avg_rate": (fixed_revenue + fixed_cost) / (2 * energy_kwh) if energy_kwh > 0 else 0,
        }


def get_tariff_for_city(city: str) -> DISCOMTariff:
    """Get DISCOM tariff for a city."""
    return INDIA_DISCOM_TARIFFS.get(city, BSES_DELHI)


def simulate_fixed_tariff(
    city: str,
    n_agents: int = 100,
    duration_hours: int = 720,
    seed: Optional[int] = None,
) -> FixedTariffResult:
    """
    Run fixed tariff simulation for a city.

    Args:
        city: City name
        n_agents: Number of agents
        duration_hours: Simulation duration
        seed: Random seed

    Returns:
        FixedTariffResult
    """
    tariff = get_tariff_for_city(city)
    simulator = FixedTariffSimulator(tariff)
    return simulator.simulate_agents(n_agents, duration_hours, seed=seed)
