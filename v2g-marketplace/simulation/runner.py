"""
V2G Marketplace Simulation Runner.

This module provides a simulation framework for modeling V2G energy trading
scenarios, integrating realistic Indian demand patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum
import random

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from backend.core.demand import IndiaLoadProfile
from backend.core.token import SHAKTIToken


class DemandMode(Enum):
    """Demand modeling modes for simulation."""
    FLAT = "flat"              # Constant demand (baseline)
    REALISTIC = "realistic"    # Full Indian load profile
    HOURLY_ONLY = "hourly"     # Only hourly variations
    CUSTOM = "custom"          # User-provided demand function


@dataclass
class SimulationConfig:
    """Configuration for V2G marketplace simulation."""

    # Time parameters
    start_time: datetime = field(default_factory=lambda: datetime(2024, 5, 15, 0, 0))
    duration_hours: int = 24
    time_step_minutes: int = 60

    # Demand modeling
    demand_mode: DemandMode = DemandMode.REALISTIC
    base_demand_mw: float = 1000.0
    region: str = "Delhi"
    custom_demand_fn: Optional[Callable[[datetime], float]] = None

    # EV fleet parameters
    num_evs: int = 100
    ev_battery_capacity_kwh: float = 50.0
    ev_initial_soc_range: tuple = (0.3, 0.8)  # State of charge range
    v2g_efficiency: float = 0.90

    # Market parameters
    base_price_per_kwh: float = 6.0  # INR per kWh
    price_demand_sensitivity: float = 0.5  # Price increase per 0.1 demand multiplier

    # Token parameters
    enable_token: bool = True  # Whether to simulate SHAKTI token
    initial_staking_rate: float = 0.20  # Initial fraction of tokens staked
    target_staking_rate: float = 0.40  # Equilibrium staking rate

    # Random seed for reproducibility
    random_seed: Optional[int] = None


@dataclass
class HourlyStats:
    """Statistics for a single simulation hour."""
    timestamp: datetime
    demand_multiplier: float
    grid_demand_mw: float
    energy_price_inr: float
    v2g_discharge_kwh: float
    charging_kwh: float
    evs_discharging: int
    evs_charging: int
    evs_idle: int
    revenue_inr: float
    # Token metrics (optional, only populated when token enabled)
    token_price: Optional[float] = None
    token_supply: Optional[float] = None
    staking_rate: Optional[float] = None
    tokens_burned: Optional[float] = None
    tokens_minted: Optional[float] = None


@dataclass
class SimulationResult:
    """Results from a V2G marketplace simulation run."""

    # Configuration used
    config: SimulationConfig

    # Hourly data
    hourly_stats: List[HourlyStats]

    # Summary metrics
    total_v2g_discharge_kwh: float = 0.0
    total_charging_kwh: float = 0.0
    total_revenue_inr: float = 0.0
    peak_demand_mw: float = 0.0
    min_demand_mw: float = 0.0
    avg_demand_mw: float = 0.0
    peak_price_inr: float = 0.0
    min_price_inr: float = 0.0
    avg_price_inr: float = 0.0

    # Demand pattern analysis
    peak_hours: List[int] = field(default_factory=list)
    off_peak_hours: List[int] = field(default_factory=list)
    v2g_opportunity_hours: List[int] = field(default_factory=list)

    # Token metrics (lists for time series analysis)
    token_prices: List[float] = field(default_factory=list)
    token_supply: List[float] = field(default_factory=list)
    staking_rates: List[float] = field(default_factory=list)
    total_tokens_burned: float = 0.0
    total_tokens_minted: float = 0.0

    def __post_init__(self):
        """Calculate summary metrics from hourly data."""
        if not self.hourly_stats:
            return

        demands = [h.grid_demand_mw for h in self.hourly_stats]
        prices = [h.energy_price_inr for h in self.hourly_stats]

        self.total_v2g_discharge_kwh = sum(h.v2g_discharge_kwh for h in self.hourly_stats)
        self.total_charging_kwh = sum(h.charging_kwh for h in self.hourly_stats)
        self.total_revenue_inr = sum(h.revenue_inr for h in self.hourly_stats)

        self.peak_demand_mw = max(demands)
        self.min_demand_mw = min(demands)
        self.avg_demand_mw = sum(demands) / len(demands)

        self.peak_price_inr = max(prices)
        self.min_price_inr = min(prices)
        self.avg_price_inr = sum(prices) / len(prices)

        # Calculate token metrics if available
        if self.hourly_stats[0].token_price is not None:
            self.token_prices = [h.token_price for h in self.hourly_stats]
            self.token_supply = [h.token_supply for h in self.hourly_stats]
            self.staking_rates = [h.staking_rate for h in self.hourly_stats]
            self.total_tokens_burned = sum(
                h.tokens_burned for h in self.hourly_stats if h.tokens_burned
            )
            self.total_tokens_minted = sum(
                h.tokens_minted for h in self.hourly_stats if h.tokens_minted
            )


class SimulationRunner:
    """
    V2G Marketplace simulation runner with Indian demand patterns.

    This class runs simulations of V2G energy trading scenarios,
    modeling EV fleet behavior, grid demand, and market dynamics.

    Example:
        >>> config = SimulationConfig(
        ...     start_time=datetime(2024, 5, 15),
        ...     duration_hours=24,
        ...     demand_mode=DemandMode.REALISTIC,
        ...     region="Delhi"
        ... )
        >>> runner = SimulationRunner(config)
        >>> result = runner.run()
        >>> print(f"Total V2G revenue: INR {result.total_revenue_inr:.2f}")
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        """
        Initialize the simulation runner.

        Args:
            config: Simulation configuration. Uses defaults if not provided.
        """
        self.config = config or SimulationConfig()
        self.load_profile = IndiaLoadProfile(base_load_mw=self.config.base_demand_mw)

        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)

        # Initialize EV fleet
        self._init_ev_fleet()

        # Initialize SHAKTI token if enabled
        self.token: Optional[SHAKTIToken] = None
        if self.config.enable_token:
            self._init_token()

    def _init_token(self):
        """Initialize the SHAKTI token model."""
        self.token = SHAKTIToken(
            initial_staking_rate=self.config.initial_staking_rate
        )

    def _init_ev_fleet(self):
        """Initialize the simulated EV fleet."""
        min_soc, max_soc = self.config.ev_initial_soc_range
        self.ev_soc = [
            random.uniform(min_soc, max_soc)
            for _ in range(self.config.num_evs)
        ]

    def get_demand_multiplier(self, timestamp: datetime) -> float:
        """
        Get demand multiplier for given timestamp based on demand mode.

        Args:
            timestamp: Simulation timestamp

        Returns:
            Demand multiplier
        """
        mode = self.config.demand_mode

        if mode == DemandMode.FLAT:
            return 1.0

        elif mode == DemandMode.HOURLY_ONLY:
            return self.load_profile.get_hourly_multiplier(timestamp.hour)

        elif mode == DemandMode.REALISTIC:
            return self.load_profile.get_demand_multiplier(
                hour=timestamp.hour,
                day_of_week=timestamp.weekday(),
                month=timestamp.month,
                region=self.config.region
            )

        elif mode == DemandMode.CUSTOM:
            if self.config.custom_demand_fn:
                return self.config.custom_demand_fn(timestamp)
            return 1.0

        return 1.0

    def calculate_price(self, demand_multiplier: float) -> float:
        """
        Calculate energy price based on demand.

        Higher demand leads to higher prices, simulating market dynamics.

        Args:
            demand_multiplier: Current demand multiplier

        Returns:
            Energy price in INR per kWh
        """
        base = self.config.base_price_per_kwh
        sensitivity = self.config.price_demand_sensitivity

        # Price increases with demand above 1.0
        if demand_multiplier > 1.0:
            price_multiplier = 1.0 + (demand_multiplier - 1.0) * sensitivity * 10
        else:
            # Slight discount during low demand
            price_multiplier = 0.8 + demand_multiplier * 0.2

        return base * price_multiplier

    def simulate_ev_decisions(
        self,
        demand_multiplier: float,
        price: float
    ) -> Dict[str, float]:
        """
        Simulate EV charging/discharging decisions for current hour.

        EVs decide to charge during low demand/price periods and
        discharge (V2G) during high demand/price periods.

        Args:
            demand_multiplier: Current demand multiplier
            price: Current energy price

        Returns:
            Dictionary with discharge_kwh, charging_kwh, and EV counts
        """
        discharge_kwh = 0.0
        charging_kwh = 0.0
        discharging_count = 0
        charging_count = 0
        idle_count = 0

        capacity = self.config.ev_battery_capacity_kwh
        efficiency = self.config.v2g_efficiency

        for i, soc in enumerate(self.ev_soc):
            # V2G discharge decision: high demand + sufficient battery
            if demand_multiplier >= 1.4 and soc > 0.3:
                # Discharge up to 20% of battery per hour
                discharge_amount = min(soc - 0.2, 0.2) * capacity
                if discharge_amount > 0:
                    discharge_kwh += discharge_amount * efficiency
                    self.ev_soc[i] -= discharge_amount / capacity
                    discharging_count += 1
                else:
                    idle_count += 1

            # Charging decision: low demand + needs charging
            elif demand_multiplier < 0.8 and soc < 0.8:
                # Charge up to 20% of battery per hour
                charge_amount = min(0.8 - soc, 0.2) * capacity
                charging_kwh += charge_amount
                self.ev_soc[i] += charge_amount / capacity
                charging_count += 1

            else:
                idle_count += 1

        return {
            "discharge_kwh": discharge_kwh,
            "charging_kwh": charging_kwh,
            "discharging_count": discharging_count,
            "charging_count": charging_count,
            "idle_count": idle_count,
        }

    def run(self) -> SimulationResult:
        """
        Run the V2G marketplace simulation.

        Returns:
            SimulationResult with hourly data and summary metrics
        """
        hourly_stats = []
        current_time = self.config.start_time
        step_delta = timedelta(minutes=self.config.time_step_minutes)
        num_steps = (self.config.duration_hours * 60) // self.config.time_step_minutes

        for _ in range(num_steps):
            # Get demand and price for this hour
            demand_mult = self.get_demand_multiplier(current_time)
            grid_demand = self.config.base_demand_mw * demand_mult
            price = self.calculate_price(demand_mult)

            # Simulate EV fleet decisions
            ev_results = self.simulate_ev_decisions(demand_mult, price)

            # Calculate revenue (V2G discharge revenue minus charging cost)
            discharge_revenue = ev_results["discharge_kwh"] * price
            charging_cost = ev_results["charging_kwh"] * price * 0.7  # Discounted rate
            net_revenue = discharge_revenue - charging_cost

            # Token metrics (default to None if token not enabled)
            token_price = None
            token_supply = None
            staking_rate = None
            tokens_burned = None
            tokens_minted = None

            # Process token transaction if enabled
            if self.token is not None:
                # Total trading volume in INR for this period
                trading_volume_inr = discharge_revenue + charging_cost

                # Process the transaction
                tx_result = self.token.process_transaction(trading_volume_inr)

                # Update staking rate toward equilibrium
                self.token.update_staking(self.config.target_staking_rate)

                # Record token metrics
                token_price = self.token.current_price
                token_supply = self.token.current_supply
                staking_rate = self.token.staking_rate
                tokens_burned = tx_result.burned
                tokens_minted = tx_result.minted

            # Record hourly statistics
            stats = HourlyStats(
                timestamp=current_time,
                demand_multiplier=demand_mult,
                grid_demand_mw=grid_demand,
                energy_price_inr=price,
                v2g_discharge_kwh=ev_results["discharge_kwh"],
                charging_kwh=ev_results["charging_kwh"],
                evs_discharging=ev_results["discharging_count"],
                evs_charging=ev_results["charging_count"],
                evs_idle=ev_results["idle_count"],
                revenue_inr=net_revenue,
                token_price=token_price,
                token_supply=token_supply,
                staking_rate=staking_rate,
                tokens_burned=tokens_burned,
                tokens_minted=tokens_minted,
            )
            hourly_stats.append(stats)

            current_time += step_delta

        # Identify peak and opportunity hours
        peak_hours = self.load_profile.get_peak_hours()
        result = SimulationResult(
            config=self.config,
            hourly_stats=hourly_stats,
            peak_hours=peak_hours.get("morning_peak", []) + peak_hours.get("evening_peak", []),
            off_peak_hours=self.load_profile.get_off_peak_hours(),
            v2g_opportunity_hours=self.load_profile.get_v2g_opportunity_hours(),
        )

        return result

    def compare_demand_modes(
        self,
        modes: Optional[List[DemandMode]] = None
    ) -> Dict[DemandMode, SimulationResult]:
        """
        Run simulations with different demand modes for comparison.

        Args:
            modes: List of demand modes to compare. Defaults to FLAT vs REALISTIC.

        Returns:
            Dictionary mapping demand mode to simulation result
        """
        if modes is None:
            modes = [DemandMode.FLAT, DemandMode.REALISTIC]

        results = {}
        original_mode = self.config.demand_mode

        for mode in modes:
            # Reset EV fleet and token for fair comparison
            self._init_ev_fleet()
            if self.config.enable_token:
                self._init_token()

            self.config.demand_mode = mode
            results[mode] = self.run()

        # Restore original mode
        self.config.demand_mode = original_mode

        return results


def run_comparison_demo():
    """Run a demo comparison of flat vs realistic demand patterns."""
    print("=" * 60)
    print("V2G Marketplace Simulation: Demand Pattern Comparison")
    print("=" * 60)

    config = SimulationConfig(
        start_time=datetime(2024, 5, 15),  # Summer day
        duration_hours=24,
        region="Delhi",
        num_evs=100,
        random_seed=42,
        enable_token=True,
        initial_staking_rate=0.20,
        target_staking_rate=0.40,
    )

    runner = SimulationRunner(config)
    results = runner.compare_demand_modes()

    for mode, result in results.items():
        print(f"\n{mode.value.upper()} Demand Mode:")
        print("-" * 40)
        print(f"  Peak Demand:        {result.peak_demand_mw:,.0f} MW")
        print(f"  Min Demand:         {result.min_demand_mw:,.0f} MW")
        print(f"  Avg Demand:         {result.avg_demand_mw:,.0f} MW")
        print(f"  Peak Price:         INR {result.peak_price_inr:.2f}/kWh")
        print(f"  Min Price:          INR {result.min_price_inr:.2f}/kWh")
        print(f"  Avg Price:          INR {result.avg_price_inr:.2f}/kWh")
        print(f"  Total V2G Discharge: {result.total_v2g_discharge_kwh:,.0f} kWh")
        print(f"  Total Charging:     {result.total_charging_kwh:,.0f} kWh")
        print(f"  Net Revenue:        INR {result.total_revenue_inr:,.0f}")

        # Show token metrics if available
        if result.token_prices:
            print(f"\n  SHAKTI Token Metrics:")
            print(f"    Start Price:      INR {result.token_prices[0]:.4f}")
            print(f"    End Price:        INR {result.token_prices[-1]:.4f}")
            print(f"    Price Change:     {((result.token_prices[-1] / result.token_prices[0]) - 1) * 100:+.2f}%")
            print(f"    Start Supply:     {result.token_supply[0]:,.0f}")
            print(f"    End Supply:       {result.token_supply[-1]:,.0f}")
            print(f"    Tokens Burned:    {result.total_tokens_burned:,.2f}")
            print(f"    Tokens Minted:    {result.total_tokens_minted:,.2f}")
            print(f"    Net Deflation:    {result.total_tokens_burned - result.total_tokens_minted:,.2f}")
            print(f"    End Staking Rate: {result.staking_rates[-1] * 100:.1f}%")

    # Show demand pattern analysis for realistic mode
    realistic = results[DemandMode.REALISTIC]
    print(f"\nRealistic Demand Pattern Analysis:")
    print("-" * 40)
    print(f"  Peak Hours:          {realistic.peak_hours}")
    print(f"  Off-Peak Hours:      {realistic.off_peak_hours}")
    print(f"  V2G Opportunity:     {realistic.v2g_opportunity_hours}")

    return results


if __name__ == "__main__":
    run_comparison_demo()
