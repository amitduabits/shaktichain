"""
Peak Demand Simulator for SHAKTI-CHAIN Stress Testing (Domain 6).

Tests hypothesis H6.1: Efficiency >= 90% at 2.5x demand.
Simulates India-specific peak demand scenarios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class DemandScenario:
    """
    Configuration for a peak demand scenario.

    Attributes:
        name: Human-readable scenario name
        multiplier: Demand multiplier (e.g., 2.5 = 250% of base)
        duration_hours: Duration of peak period
        ramp_time_minutes: Time to ramp up to peak
        city: Indian city for the scenario
        time_of_day: Time period (e.g., "14:00-17:00")
        base_demand_mw: Base demand in MW
    """
    name: str
    multiplier: float
    duration_hours: float
    ramp_time_minutes: float
    city: str
    time_of_day: str
    base_demand_mw: float = 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "multiplier": float(self.multiplier),
            "duration_hours": float(self.duration_hours),
            "ramp_time_minutes": float(self.ramp_time_minutes),
            "city": self.city,
            "time_of_day": self.time_of_day,
            "base_demand_mw": float(self.base_demand_mw),
        }


# India-specific peak demand scenarios
DELHI_SUMMER_PEAK = DemandScenario(
    name="Delhi Summer Peak",
    multiplier=2.5,
    duration_hours=3,
    ramp_time_minutes=30,
    city="Delhi",
    time_of_day="14:00-17:00",
    base_demand_mw=150.0,
)

MUMBAI_MONSOON = DemandScenario(
    name="Mumbai Monsoon",
    multiplier=1.8,
    duration_hours=6,
    ramp_time_minutes=60,
    city="Mumbai",
    time_of_day="18:00-00:00",
    base_demand_mw=200.0,
)

CHENNAI_HEATWAVE = DemandScenario(
    name="Chennai Heatwave",
    multiplier=2.2,
    duration_hours=4,
    ramp_time_minutes=45,
    city="Chennai",
    time_of_day="12:00-16:00",
    base_demand_mw=120.0,
)

BANGALORE_TECH_PEAK = DemandScenario(
    name="Bangalore Tech District Peak",
    multiplier=2.0,
    duration_hours=2,
    ramp_time_minutes=15,
    city="Bangalore",
    time_of_day="10:00-12:00",
    base_demand_mw=180.0,
)

KOLKATA_EVENING_PEAK = DemandScenario(
    name="Kolkata Evening Peak",
    multiplier=1.9,
    duration_hours=4,
    ramp_time_minutes=45,
    city="Kolkata",
    time_of_day="18:00-22:00",
    base_demand_mw=130.0,
)

# List of all predefined scenarios
INDIA_PEAK_SCENARIOS = [
    DELHI_SUMMER_PEAK,
    MUMBAI_MONSOON,
    CHENNAI_HEATWAVE,
    BANGALORE_TECH_PEAK,
    KOLKATA_EVENING_PEAK,
]


@dataclass
class PeakDemandResult:
    """
    Result of a peak demand simulation.

    Attributes:
        scenario: The scenario tested
        efficiency_baseline: Efficiency before peak
        efficiency_during_peak: Mean efficiency during peak
        efficiency_min: Minimum efficiency during peak
        price_baseline: Baseline price
        price_peak: Maximum price during peak
        price_spike_ratio: Peak price / baseline price
        unmet_demand_volume: Total unmet demand (kWh)
        unmet_demand_fraction: Fraction of demand unmet
        recovery_rounds: Rounds to return to 95% efficiency
        demand_curve: Array of demand values
        efficiency_curve: Array of efficiency values
        price_curve: Array of price values
    """
    scenario: DemandScenario
    efficiency_baseline: float
    efficiency_during_peak: float
    efficiency_min: float
    price_baseline: float
    price_peak: float
    price_spike_ratio: float
    unmet_demand_volume: float
    unmet_demand_fraction: float
    recovery_rounds: int
    demand_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    efficiency_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    price_curve: np.ndarray = field(default_factory=lambda: np.array([]))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario.to_dict(),
            "efficiency_baseline": float(self.efficiency_baseline),
            "efficiency_during_peak": float(self.efficiency_during_peak),
            "efficiency_min": float(self.efficiency_min),
            "price_baseline": float(self.price_baseline),
            "price_peak": float(self.price_peak),
            "price_spike_ratio": float(self.price_spike_ratio),
            "unmet_demand_volume": float(self.unmet_demand_volume),
            "unmet_demand_fraction": float(self.unmet_demand_fraction),
            "recovery_rounds": self.recovery_rounds,
        }


@dataclass
class PeakDemandTestResult:
    """
    Result of peak demand hypothesis test (H6.1).

    Attributes:
        passed: Whether efficiency >= threshold at target multiplier
        mean_efficiency: Mean efficiency across simulations
        std_efficiency: Standard deviation
        efficiency_threshold: Required efficiency (default 90%)
        demand_multiplier: Demand multiplier tested
        t_statistic: T-test statistic
        p_value: P-value
        individual_results: Results from each simulation
    """
    passed: bool
    mean_efficiency: float
    std_efficiency: float
    efficiency_threshold: float
    demand_multiplier: float
    t_statistic: float
    p_value: float
    individual_results: List[PeakDemandResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "mean_efficiency": float(self.mean_efficiency),
            "std_efficiency": float(self.std_efficiency),
            "efficiency_threshold": float(self.efficiency_threshold),
            "demand_multiplier": float(self.demand_multiplier),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "num_simulations": len(self.individual_results),
        }


class SimpleMarketSimulator:
    """
    Simplified market simulator for stress testing.

    Simulates a double auction market with variable demand.
    """

    def __init__(
        self,
        n_buyers: int = 50,
        n_sellers: int = 50,
        base_supply_capacity: float = 100.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize market simulator.

        Args:
            n_buyers: Number of buyers
            n_sellers: Number of sellers
            base_supply_capacity: Total supply capacity
            seed: Random seed
        """
        self.n_buyers = n_buyers
        self.n_sellers = n_sellers
        self.base_supply_capacity = base_supply_capacity
        self.rng = np.random.default_rng(seed)

        # Generate seller characteristics
        self.seller_capacities = self.rng.uniform(1, 5, n_sellers)
        self.seller_capacities = self.seller_capacities / self.seller_capacities.sum() * base_supply_capacity
        self.seller_costs = self.rng.uniform(2, 10, n_sellers)

    def run_round(
        self,
        demand_multiplier: float = 1.0,
        supply_fraction: float = 1.0,
    ) -> Tuple[float, float, float, float]:
        """
        Run a single market round.

        Args:
            demand_multiplier: Scale demand by this factor
            supply_fraction: Available supply fraction (for shocks)

        Returns:
            (clearing_price, efficiency, traded_volume, unmet_demand)
        """
        # Generate demand
        base_demand = self.base_supply_capacity * 0.8  # 80% of capacity normally
        actual_demand = base_demand * demand_multiplier

        # Generate buyer valuations
        buyer_demands = self.rng.uniform(1, 4, self.n_buyers)
        buyer_demands = buyer_demands / buyer_demands.sum() * actual_demand
        buyer_valuations = self.rng.uniform(8, 15, self.n_buyers)

        # Apply supply constraint
        available_supply = self.seller_capacities * supply_fraction

        # Sort buyers by valuation (descending) and sellers by cost (ascending)
        buyer_order = np.argsort(buyer_valuations)[::-1]
        seller_order = np.argsort(self.seller_costs)

        # Match buyers and sellers
        total_traded = 0.0
        total_surplus = 0.0
        max_possible_surplus = 0.0
        prices = []

        cum_demand = 0.0
        cum_supply = 0.0

        for i, buyer_idx in enumerate(buyer_order):
            cum_demand += buyer_demands[buyer_idx]

            # Find matching sellers
            while cum_supply < cum_demand and len(seller_order) > 0:
                seller_idx = seller_order[0]
                if self.seller_costs[seller_idx] <= buyer_valuations[buyer_idx]:
                    trade_qty = min(
                        buyer_demands[buyer_idx] - total_traded + cum_supply,
                        available_supply[seller_idx]
                    )
                    if trade_qty > 0:
                        price = (buyer_valuations[buyer_idx] + self.seller_costs[seller_idx]) / 2
                        surplus = (buyer_valuations[buyer_idx] - self.seller_costs[seller_idx]) * trade_qty
                        total_traded += trade_qty
                        total_surplus += surplus
                        prices.append(price)
                        cum_supply += trade_qty
                        available_supply[seller_idx] -= trade_qty

                        if available_supply[seller_idx] <= 0:
                            seller_order = seller_order[1:]
                    else:
                        break
                else:
                    break

        # Calculate maximum possible surplus (Walrasian)
        sorted_valuations = np.sort(buyer_valuations)[::-1]
        sorted_costs = np.sort(self.seller_costs)
        cum_buyer = 0
        cum_seller = 0

        for v, d in zip(sorted_valuations, buyer_demands[np.argsort(buyer_valuations)[::-1]]):
            for c, s in zip(sorted_costs, self.seller_capacities[np.argsort(self.seller_costs)]):
                if v >= c and cum_seller < actual_demand:
                    trade = min(d, s, actual_demand - cum_seller)
                    max_possible_surplus += (v - c) * trade
                    cum_seller += trade

        if max_possible_surplus <= 0:
            max_possible_surplus = 1.0  # Avoid division by zero

        efficiency = total_surplus / max_possible_surplus if max_possible_surplus > 0 else 0
        efficiency = min(1.0, max(0.0, efficiency))

        clearing_price = np.mean(prices) if prices else 10.0
        unmet_demand = max(0, actual_demand - total_traded)

        return clearing_price, efficiency, total_traded, unmet_demand


class PeakDemandSimulator:
    """
    Simulate peak demand scenarios for stress testing.

    Tests H6.1: Efficiency >= 90% at 2.5x demand.
    """

    def __init__(
        self,
        base_demand: float = 100.0,
        n_buyers: int = 50,
        n_sellers: int = 50,
        seed: Optional[int] = None,
    ):
        """
        Initialize peak demand simulator.

        Args:
            base_demand: Base demand level (MW)
            n_buyers: Number of buyers
            n_sellers: Number of sellers
            seed: Random seed
        """
        self.base_demand = base_demand
        self.n_buyers = n_buyers
        self.n_sellers = n_sellers
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def generate_demand_curve(
        self,
        scenario: DemandScenario,
        resolution_minutes: int = 5,
    ) -> np.ndarray:
        """
        Generate demand curve with ramp up, sustained peak, and ramp down.

        Args:
            scenario: Demand scenario configuration
            resolution_minutes: Time resolution in minutes

        Returns:
            Array of demand values over time
        """
        # Calculate time points
        ramp_steps = int(scenario.ramp_time_minutes / resolution_minutes)
        peak_steps = int(scenario.duration_hours * 60 / resolution_minutes)
        total_steps = ramp_steps + peak_steps + ramp_steps

        demand_curve = np.zeros(total_steps)

        # Ramp up phase
        for i in range(ramp_steps):
            progress = (i + 1) / ramp_steps
            # Smooth ramp using cosine
            multiplier = 1 + (scenario.multiplier - 1) * (1 - np.cos(np.pi * progress)) / 2
            demand_curve[i] = scenario.base_demand_mw * multiplier

        # Sustained peak phase (with some variation)
        for i in range(peak_steps):
            noise = self.rng.normal(0, 0.05)  # 5% variation
            demand_curve[ramp_steps + i] = scenario.base_demand_mw * scenario.multiplier * (1 + noise)

        # Ramp down phase
        for i in range(ramp_steps):
            progress = (i + 1) / ramp_steps
            multiplier = scenario.multiplier - (scenario.multiplier - 1) * (1 - np.cos(np.pi * progress)) / 2
            demand_curve[ramp_steps + peak_steps + i] = scenario.base_demand_mw * multiplier

        return demand_curve

    def inject_peak_demand(
        self,
        scenario: DemandScenario,
        n_rounds: int = 100,
    ) -> PeakDemandResult:
        """
        Run market under peak demand conditions.

        Args:
            scenario: Demand scenario to simulate
            n_rounds: Number of market rounds

        Returns:
            PeakDemandResult with efficiency and price metrics
        """
        # Generate demand curve
        demand_curve = self.generate_demand_curve(scenario)

        # Extend demand curve to match n_rounds
        if len(demand_curve) < n_rounds:
            # Pad with base demand
            padding = np.full(n_rounds - len(demand_curve), scenario.base_demand_mw)
            demand_curve = np.concatenate([demand_curve, padding])
        elif len(demand_curve) > n_rounds:
            demand_curve = demand_curve[:n_rounds]

        # Create market simulator
        market = SimpleMarketSimulator(
            n_buyers=self.n_buyers,
            n_sellers=self.n_sellers,
            base_supply_capacity=scenario.base_demand_mw * 1.2,  # 20% surplus capacity
            seed=self.seed,
        )

        # Run baseline (first 10 rounds at base demand)
        baseline_rounds = 10
        baseline_efficiencies = []
        baseline_prices = []

        for i in range(baseline_rounds):
            price, eff, _, _ = market.run_round(demand_multiplier=1.0)
            baseline_efficiencies.append(eff)
            baseline_prices.append(price)

        efficiency_baseline = np.mean(baseline_efficiencies)
        price_baseline = np.mean(baseline_prices)

        # Run peak demand scenario
        efficiency_curve = []
        price_curve = []
        unmet_demand_total = 0.0
        total_demand = 0.0

        # Identify peak period (where demand > 1.5x base)
        peak_threshold = scenario.base_demand_mw * 1.5
        peak_indices = np.where(demand_curve > peak_threshold)[0]

        for i in range(n_rounds):
            demand_multiplier = demand_curve[i] / scenario.base_demand_mw
            price, eff, traded, unmet = market.run_round(demand_multiplier=demand_multiplier)

            efficiency_curve.append(eff)
            price_curve.append(price)
            unmet_demand_total += unmet
            total_demand += demand_curve[i]

        efficiency_curve = np.array(efficiency_curve)
        price_curve = np.array(price_curve)

        # Calculate peak period efficiency
        if len(peak_indices) > 0:
            efficiency_during_peak = np.mean(efficiency_curve[peak_indices])
            efficiency_min = np.min(efficiency_curve[peak_indices])
            price_peak = np.max(price_curve[peak_indices])
        else:
            efficiency_during_peak = np.mean(efficiency_curve)
            efficiency_min = np.min(efficiency_curve)
            price_peak = np.max(price_curve)

        # Calculate recovery time
        recovery_threshold = 0.95 * efficiency_baseline
        recovery_rounds = 0

        if len(peak_indices) > 0:
            end_of_peak = peak_indices[-1]
            for i in range(end_of_peak, n_rounds):
                if efficiency_curve[i] >= recovery_threshold:
                    recovery_rounds = i - end_of_peak
                    break
            else:
                recovery_rounds = n_rounds - end_of_peak

        return PeakDemandResult(
            scenario=scenario,
            efficiency_baseline=float(efficiency_baseline),
            efficiency_during_peak=float(efficiency_during_peak),
            efficiency_min=float(efficiency_min),
            price_baseline=float(price_baseline),
            price_peak=float(price_peak),
            price_spike_ratio=float(price_peak / price_baseline) if price_baseline > 0 else 1.0,
            unmet_demand_volume=float(unmet_demand_total),
            unmet_demand_fraction=float(unmet_demand_total / total_demand) if total_demand > 0 else 0.0,
            recovery_rounds=recovery_rounds,
            demand_curve=demand_curve,
            efficiency_curve=efficiency_curve,
            price_curve=price_curve,
        )

    def test_efficiency_threshold(
        self,
        demand_multiplier: float = 2.5,
        efficiency_threshold: float = 0.90,
        n_simulations: int = 30,
        alpha: float = 0.05,
    ) -> PeakDemandTestResult:
        """
        Test H6.1: Efficiency >= threshold at given demand multiplier.

        Args:
            demand_multiplier: Target demand multiplier
            efficiency_threshold: Required efficiency (default 90%)
            n_simulations: Number of simulations
            alpha: Significance level

        Returns:
            PeakDemandTestResult
        """
        # Create custom scenario with target multiplier
        scenario = DemandScenario(
            name=f"Custom {demand_multiplier}x Peak",
            multiplier=demand_multiplier,
            duration_hours=2,
            ramp_time_minutes=15,
            city="Test",
            time_of_day="12:00-14:00",
            base_demand_mw=self.base_demand,
        )

        results = []
        efficiencies = []

        for sim_idx in range(n_simulations):
            sim_seed = self.seed + sim_idx if self.seed else None
            self.rng = np.random.default_rng(sim_seed)

            result = self.inject_peak_demand(scenario)
            results.append(result)
            efficiencies.append(result.efficiency_during_peak)

        efficiencies = np.array(efficiencies)
        mean_eff = float(np.mean(efficiencies))
        std_eff = float(np.std(efficiencies, ddof=1))

        # One-sample t-test: H0: mean < threshold, H1: mean >= threshold
        if std_eff > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(efficiencies, efficiency_threshold)
            # One-tailed test (we want mean >= threshold)
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        else:
            t_stat = float('inf') if mean_eff >= efficiency_threshold else float('-inf')
            p_value = 0.0 if mean_eff >= efficiency_threshold else 1.0

        passed = mean_eff >= efficiency_threshold and p_value < alpha

        return PeakDemandTestResult(
            passed=passed,
            mean_efficiency=mean_eff,
            std_efficiency=std_eff,
            efficiency_threshold=efficiency_threshold,
            demand_multiplier=demand_multiplier,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            individual_results=results,
        )

    def run_all_scenarios(
        self,
        n_rounds: int = 100,
    ) -> Dict[str, PeakDemandResult]:
        """
        Run all India-specific peak demand scenarios.

        Args:
            n_rounds: Number of rounds per scenario

        Returns:
            Dictionary mapping scenario name to result
        """
        results = {}

        for scenario in INDIA_PEAK_SCENARIOS:
            logger.info(f"Running scenario: {scenario.name}")
            result = self.inject_peak_demand(scenario, n_rounds)
            results[scenario.name] = result

        return results


def simulate_peak_demand_test(
    demand_multiplier: float = 2.5,
    efficiency_threshold: float = 0.90,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> PeakDemandTestResult:
    """
    Run a peak demand hypothesis test.

    Args:
        demand_multiplier: Target demand multiplier
        efficiency_threshold: Required efficiency
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        PeakDemandTestResult
    """
    simulator = PeakDemandSimulator(seed=seed)

    return simulator.test_efficiency_threshold(
        demand_multiplier=demand_multiplier,
        efficiency_threshold=efficiency_threshold,
        n_simulations=n_simulations,
    )
