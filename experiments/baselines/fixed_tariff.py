"""
Fixed Tariff Baseline - Indian DISCOM time-of-use rates.

Implements the traditional utility pricing model for comparison
with P2P trading mechanisms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np


class TimeOfUse(Enum):
    """Time-of-use periods."""
    OFF_PEAK = "off_peak"
    STANDARD = "standard"
    PEAK = "peak"


@dataclass
class DISCOMRates:
    """
    Indian DISCOM tariff rates.

    Default values based on Delhi BSES Yamuna rates (2024).
    """
    # Time-of-use rates (INR/kWh)
    off_peak_rate: float = 3.0
    standard_rate: float = 5.5
    peak_rate: float = 8.0

    # Time definitions (hours 0-23)
    peak_hours: tuple = (14, 15, 16, 17)
    off_peak_hours: tuple = (22, 23, 0, 1, 2, 3, 4, 5)
    # Standard is everything else

    # Feed-in tariff for V2G
    feed_in_rate: float = 3.0
    feed_in_cap_kwh_per_day: float = 50.0
    feed_in_allowed_hours: tuple = (14, 15, 16, 17, 18, 19)

    # Fixed charges
    monthly_fixed_charge: float = 150.0  # INR
    demand_charge_per_kw: float = 100.0  # INR/kW

    # Slab-based pricing (optional)
    slab_enabled: bool = False
    slabs: dict = field(default_factory=lambda: {
        (0, 200): 3.0,
        (201, 400): 4.5,
        (401, 800): 6.5,
        (801, float('inf')): 7.5,
    })

    def get_time_of_use(self, hour: int) -> TimeOfUse:
        """Get time-of-use period for an hour."""
        if hour in self.peak_hours:
            return TimeOfUse.PEAK
        elif hour in self.off_peak_hours:
            return TimeOfUse.OFF_PEAK
        else:
            return TimeOfUse.STANDARD

    def get_purchase_rate(self, hour: int) -> float:
        """Get the rate for purchasing electricity at given hour."""
        tou = self.get_time_of_use(hour)
        if tou == TimeOfUse.PEAK:
            return self.peak_rate
        elif tou == TimeOfUse.OFF_PEAK:
            return self.off_peak_rate
        else:
            return self.standard_rate

    def get_sell_rate(self, hour: int) -> float:
        """Get the rate for selling electricity (V2G) at given hour."""
        if hour in self.feed_in_allowed_hours:
            return self.feed_in_rate
        return 0.0  # Cannot sell outside allowed hours


# Pre-defined rates for different DISCOMs
BSES_DELHI = DISCOMRates(
    off_peak_rate=3.0,
    standard_rate=5.5,
    peak_rate=8.0,
    peak_hours=(14, 15, 16, 17),
    off_peak_hours=(22, 23, 0, 1, 2, 3, 4, 5),
)

TATA_MUMBAI = DISCOMRates(
    off_peak_rate=3.4,
    standard_rate=4.5,
    peak_rate=5.85,
    peak_hours=(18, 19, 20, 21),
    off_peak_hours=(0, 1, 2, 3, 4, 5, 6),
)

BESCOM_BANGALORE = DISCOMRates(
    off_peak_rate=4.15,
    standard_rate=5.55,
    peak_rate=7.40,
    peak_hours=(18, 19, 20, 21, 22),
    off_peak_hours=(0, 1, 2, 3, 4, 5),
)

TANGEDCO_CHENNAI = DISCOMRates(
    off_peak_rate=3.5,
    standard_rate=4.6,
    peak_rate=6.35,
    peak_hours=(18, 19, 20, 21),
    off_peak_hours=(22, 23, 0, 1, 2, 3, 4, 5),
)

WBSEDCL_KOLKATA = DISCOMRates(
    off_peak_rate=4.39,
    standard_rate=5.48,
    peak_rate=7.18,
    peak_hours=(17, 18, 19, 20, 21),
    off_peak_hours=(23, 0, 1, 2, 3, 4, 5),
)


@dataclass
class FixedTariffResult:
    """Result of a fixed tariff transaction."""
    buyer_id: str
    quantity_kwh: float
    price_per_kwh: float
    total_cost: float
    time_of_use: TimeOfUse
    hour: int
    is_feed_in: bool = False

    def to_dict(self) -> dict:
        return {
            "buyer_id": self.buyer_id,
            "quantity_kwh": self.quantity_kwh,
            "price_per_kwh": self.price_per_kwh,
            "total_cost": self.total_cost,
            "time_of_use": self.time_of_use.value,
            "hour": self.hour,
            "is_feed_in": self.is_feed_in,
        }


class FixedTariffMarket:
    """
    Fixed tariff market simulation.

    In this baseline, all energy is bought from/sold to the utility
    at fixed time-of-use rates. No P2P trading occurs.
    """

    def __init__(
        self,
        rates: Optional[DISCOMRates] = None,
        city: str = "Delhi",
    ):
        """
        Initialize the fixed tariff market.

        Args:
            rates: DISCOM rates to use
            city: City for default rates
        """
        if rates is None:
            rates = self._get_city_rates(city)
        self.rates = rates

        # Tracking
        self.total_energy_purchased = 0.0
        self.total_energy_sold = 0.0
        self.total_cost = 0.0
        self.total_revenue = 0.0
        self.transactions: list[FixedTariffResult] = []

        # Daily limits
        self._daily_feed_in: dict[str, float] = {}

    def _get_city_rates(self, city: str) -> DISCOMRates:
        """Get rates for a city."""
        city_rates = {
            "Delhi": BSES_DELHI,
            "Mumbai": TATA_MUMBAI,
            "Bangalore": BESCOM_BANGALORE,
            "Chennai": TANGEDCO_CHENNAI,
            "Kolkata": WBSEDCL_KOLKATA,
        }
        return city_rates.get(city, BSES_DELHI)

    def buy_energy(
        self,
        buyer_id: str,
        quantity_kwh: float,
        hour: int,
    ) -> FixedTariffResult:
        """
        Buy energy from the grid.

        Args:
            buyer_id: ID of the buyer
            quantity_kwh: Amount to purchase
            hour: Hour of the day (0-23)

        Returns:
            Transaction result
        """
        rate = self.rates.get_purchase_rate(hour)
        total_cost = quantity_kwh * rate

        result = FixedTariffResult(
            buyer_id=buyer_id,
            quantity_kwh=quantity_kwh,
            price_per_kwh=rate,
            total_cost=total_cost,
            time_of_use=self.rates.get_time_of_use(hour),
            hour=hour,
        )

        self.total_energy_purchased += quantity_kwh
        self.total_cost += total_cost
        self.transactions.append(result)

        return result

    def sell_energy(
        self,
        seller_id: str,
        quantity_kwh: float,
        hour: int,
    ) -> Optional[FixedTariffResult]:
        """
        Sell energy to the grid (V2G feed-in).

        Args:
            seller_id: ID of the seller
            quantity_kwh: Amount to sell
            hour: Hour of the day (0-23)

        Returns:
            Transaction result or None if not allowed
        """
        # Check if feed-in is allowed at this hour
        if hour not in self.rates.feed_in_allowed_hours:
            return None

        # Check daily cap
        daily_total = self._daily_feed_in.get(seller_id, 0.0)
        remaining = self.rates.feed_in_cap_kwh_per_day - daily_total

        if remaining <= 0:
            return None

        quantity_kwh = min(quantity_kwh, remaining)
        rate = self.rates.feed_in_rate
        total_revenue = quantity_kwh * rate

        result = FixedTariffResult(
            buyer_id=seller_id,  # The grid is buying from the seller
            quantity_kwh=quantity_kwh,
            price_per_kwh=rate,
            total_cost=-total_revenue,  # Negative cost = revenue
            time_of_use=self.rates.get_time_of_use(hour),
            hour=hour,
            is_feed_in=True,
        )

        self.total_energy_sold += quantity_kwh
        self.total_revenue += total_revenue
        self._daily_feed_in[seller_id] = daily_total + quantity_kwh
        self.transactions.append(result)

        return result

    def reset_daily_limits(self) -> None:
        """Reset daily feed-in limits."""
        self._daily_feed_in = {}

    def get_metrics(self) -> dict:
        """Get market metrics."""
        return {
            "total_energy_purchased_kwh": self.total_energy_purchased,
            "total_energy_sold_kwh": self.total_energy_sold,
            "total_cost_inr": self.total_cost,
            "total_revenue_inr": self.total_revenue,
            "net_cost_inr": self.total_cost - self.total_revenue,
            "num_transactions": len(self.transactions),
            "avg_purchase_rate": (
                self.total_cost / self.total_energy_purchased
                if self.total_energy_purchased > 0 else 0
            ),
            "avg_sell_rate": (
                self.total_revenue / self.total_energy_sold
                if self.total_energy_sold > 0 else 0
            ),
        }

    def compute_welfare_comparison(
        self,
        p2p_welfare: float,
    ) -> dict:
        """
        Compare welfare with P2P market.

        Args:
            p2p_welfare: Total welfare from P2P market

        Returns:
            Comparison metrics
        """
        # In fixed tariff, consumer surplus is value - price paid
        # Producer surplus is price received - cost
        # But since it's centralized, we use net cost as welfare proxy

        fixed_welfare = -(self.total_cost - self.total_revenue)

        return {
            "p2p_welfare": p2p_welfare,
            "fixed_tariff_welfare": fixed_welfare,
            "welfare_improvement": p2p_welfare - fixed_welfare,
            "welfare_improvement_percent": (
                (p2p_welfare - fixed_welfare) / abs(fixed_welfare) * 100
                if fixed_welfare != 0 else 0
            ),
        }

    def simulate_day(
        self,
        agents: list,
        demand_profile: list[float],
    ) -> dict:
        """
        Simulate a full day of fixed tariff trading.

        Args:
            agents: List of agents with energy needs
            demand_profile: Hourly demand (24 values)

        Returns:
            Daily simulation results
        """
        self.reset_daily_limits()
        hourly_results = []

        for hour in range(24):
            hour_demand = demand_profile[hour]
            hour_purchases = 0.0
            hour_sales = 0.0
            hour_cost = 0.0
            hour_revenue = 0.0

            for agent in agents:
                # Determine if agent buys or sells based on SoC
                if hasattr(agent, 'state'):
                    soc = agent.state.current_soc
                    capacity = agent.state.battery_capacity_kwh

                    if soc < 0.4:
                        # Need to charge
                        qty = min(capacity * 0.2, hour_demand / len(agents))
                        result = self.buy_energy(agent.state.id, qty, hour)
                        hour_purchases += qty
                        hour_cost += result.total_cost

                    elif soc > 0.7 and hour in self.rates.feed_in_allowed_hours:
                        # Can discharge
                        qty = min(capacity * 0.1, 10.0)
                        result = self.sell_energy(agent.state.id, qty, hour)
                        if result:
                            hour_sales += qty
                            hour_revenue += abs(result.total_cost)

            hourly_results.append({
                "hour": hour,
                "purchases_kwh": hour_purchases,
                "sales_kwh": hour_sales,
                "cost_inr": hour_cost,
                "revenue_inr": hour_revenue,
                "rate": self.rates.get_purchase_rate(hour),
                "tou": self.rates.get_time_of_use(hour).value,
            })

        return {
            "hourly_results": hourly_results,
            "summary": self.get_metrics(),
        }
