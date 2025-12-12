"""
Supply Shock Simulator for SHAKTI-CHAIN Stress Testing (Domain 6).

Tests hypothesis H6.2: Recovery within 10 rounds after supply shock.
Simulates sudden supply reductions and measures recovery dynamics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class ShockType(Enum):
    """Types of supply shock events."""
    INSTANT = "instant"           # Immediate drop
    GRADUAL = "gradual"           # Progressive degradation
    INTERMITTENT = "intermittent" # Fluctuating outage
    CASCADING = "cascading"       # Failures spread over time


@dataclass
class SupplyShockEvent:
    """
    Configuration for a supply shock event.

    Attributes:
        name: Human-readable name
        trigger_round: Round when shock occurs
        supply_drop_fraction: Fraction of supply lost (0.4 = 40% drop)
        recovery_rate: Fraction recovered per round
        affected_seller_fraction: Fraction of sellers affected
        shock_type: Type of shock event
        duration_rounds: Duration for gradual/intermittent shocks
    """
    name: str
    trigger_round: int
    supply_drop_fraction: float
    recovery_rate: float
    affected_seller_fraction: float = 1.0
    shock_type: ShockType = ShockType.INSTANT
    duration_rounds: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trigger_round": self.trigger_round,
            "supply_drop_fraction": float(self.supply_drop_fraction),
            "recovery_rate": float(self.recovery_rate),
            "affected_seller_fraction": float(self.affected_seller_fraction),
            "shock_type": self.shock_type.value,
            "duration_rounds": self.duration_rounds,
        }


# Predefined shock scenarios
GRID_OUTAGE = SupplyShockEvent(
    name="Complete Grid Outage",
    trigger_round=20,
    supply_drop_fraction=0.8,
    recovery_rate=0.10,
    affected_seller_fraction=1.0,
    shock_type=ShockType.INSTANT,
)

LOCALIZED_FAILURE = SupplyShockEvent(
    name="Localized Substation Failure",
    trigger_round=20,
    supply_drop_fraction=0.4,
    recovery_rate=0.15,
    affected_seller_fraction=0.3,
    shock_type=ShockType.INSTANT,
)

GRADUAL_DEGRADATION = SupplyShockEvent(
    name="Gradual System Degradation",
    trigger_round=20,
    supply_drop_fraction=0.5,
    recovery_rate=0.08,
    affected_seller_fraction=0.6,
    shock_type=ShockType.GRADUAL,
    duration_rounds=10,
)

CASCADING_FAILURE = SupplyShockEvent(
    name="Cascading Grid Failure",
    trigger_round=20,
    supply_drop_fraction=0.7,
    recovery_rate=0.05,
    affected_seller_fraction=0.8,
    shock_type=ShockType.CASCADING,
    duration_rounds=5,
)

SUPPLY_SHOCK_SCENARIOS = [
    GRID_OUTAGE,
    LOCALIZED_FAILURE,
    GRADUAL_DEGRADATION,
    CASCADING_FAILURE,
]


@dataclass
class SupplyShockResult:
    """
    Result of a supply shock simulation.

    Attributes:
        shock_event: The shock configuration
        efficiency_pre_shock: Baseline efficiency before shock
        efficiency_at_shock: Efficiency immediately after shock
        efficiency_min: Minimum efficiency during shock
        recovery_rounds: Rounds until 90% of pre-shock efficiency
        recovered: Whether system recovered within observation period
        price_pre_shock: Baseline price
        price_at_shock: Price immediately after shock
        price_spike_ratio: Max price / baseline price
        welfare_loss: Total welfare lost during shock period
        efficiency_series: Efficiency over time
        price_series: Prices over time
        supply_fraction_series: Available supply over time
    """
    shock_event: SupplyShockEvent
    efficiency_pre_shock: float
    efficiency_at_shock: float
    efficiency_min: float
    recovery_rounds: int
    recovered: bool
    price_pre_shock: float
    price_at_shock: float
    price_spike_ratio: float
    welfare_loss: float
    efficiency_series: np.ndarray = field(default_factory=lambda: np.array([]))
    price_series: np.ndarray = field(default_factory=lambda: np.array([]))
    supply_fraction_series: np.ndarray = field(default_factory=lambda: np.array([]))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "shock_event": self.shock_event.to_dict(),
            "efficiency_pre_shock": float(self.efficiency_pre_shock),
            "efficiency_at_shock": float(self.efficiency_at_shock),
            "efficiency_min": float(self.efficiency_min),
            "recovery_rounds": self.recovery_rounds,
            "recovered": self.recovered,
            "price_pre_shock": float(self.price_pre_shock),
            "price_at_shock": float(self.price_at_shock),
            "price_spike_ratio": float(self.price_spike_ratio),
            "welfare_loss": float(self.welfare_loss),
        }


@dataclass
class RecoveryTestResult:
    """
    Result of recovery time hypothesis test (H6.2).

    Attributes:
        passed: Whether recovery <= threshold rounds
        mean_recovery_time: Mean recovery time across simulations
        std_recovery_time: Standard deviation
        recovery_threshold: Required recovery time (default 10 rounds)
        recovery_rate: Fraction of simulations that recovered
        t_statistic: T-test statistic
        p_value: P-value
        individual_results: Results from each simulation
    """
    passed: bool
    mean_recovery_time: float
    std_recovery_time: float
    recovery_threshold: int
    recovery_rate: float
    t_statistic: float
    p_value: float
    individual_results: List[SupplyShockResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "mean_recovery_time": float(self.mean_recovery_time),
            "std_recovery_time": float(self.std_recovery_time),
            "recovery_threshold": self.recovery_threshold,
            "recovery_rate": float(self.recovery_rate),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "num_simulations": len(self.individual_results),
        }


class SimpleMarketSimulator:
    """Simplified market simulator for supply shock testing."""

    def __init__(
        self,
        n_buyers: int = 50,
        n_sellers: int = 50,
        base_supply: float = 100.0,
        seed: Optional[int] = None,
    ):
        self.n_buyers = n_buyers
        self.n_sellers = n_sellers
        self.base_supply = base_supply
        self.rng = np.random.default_rng(seed)

        # Generate agent characteristics
        self.seller_capacities = self.rng.uniform(1, 5, n_sellers)
        self.seller_capacities = self.seller_capacities / self.seller_capacities.sum() * base_supply
        self.seller_costs = self.rng.uniform(2, 10, n_sellers)
        self.buyer_valuations = self.rng.uniform(8, 15, n_buyers)

    def run_round(
        self,
        supply_fraction: float = 1.0,
        demand_multiplier: float = 1.0,
    ) -> Tuple[float, float, float]:
        """
        Run a single market round.

        Args:
            supply_fraction: Available supply fraction (for shocks)
            demand_multiplier: Demand scaling factor

        Returns:
            (clearing_price, efficiency, welfare)
        """
        # Generate demand
        buyer_demands = self.rng.uniform(1, 4, self.n_buyers)
        buyer_demands = buyer_demands / buyer_demands.sum() * self.base_supply * 0.8 * demand_multiplier

        # Apply supply constraint
        available_supply = self.seller_capacities * supply_fraction

        # Match using simple merit order
        buyer_order = np.argsort(self.buyer_valuations)[::-1]
        seller_order = np.argsort(self.seller_costs)

        total_traded = 0.0
        total_surplus = 0.0
        prices = []

        remaining_supply = available_supply.copy()

        for buyer_idx in buyer_order:
            buyer_demand = buyer_demands[buyer_idx]
            buyer_val = self.buyer_valuations[buyer_idx]
            bought = 0.0

            for seller_idx in seller_order:
                if remaining_supply[seller_idx] <= 0:
                    continue
                if self.seller_costs[seller_idx] > buyer_val:
                    break

                trade_qty = min(buyer_demand - bought, remaining_supply[seller_idx])
                if trade_qty > 0:
                    price = (buyer_val + self.seller_costs[seller_idx]) / 2
                    surplus = (buyer_val - self.seller_costs[seller_idx]) * trade_qty

                    total_traded += trade_qty
                    total_surplus += surplus
                    prices.append(price)
                    bought += trade_qty
                    remaining_supply[seller_idx] -= trade_qty

                if bought >= buyer_demand:
                    break

        # Calculate max possible surplus
        max_surplus = 0.0
        sorted_vals = np.sort(self.buyer_valuations)[::-1]
        sorted_costs = np.sort(self.seller_costs)
        total_supply = np.sum(available_supply)

        for val, cost in zip(sorted_vals, sorted_costs):
            if val >= cost:
                max_surplus += val - cost

        efficiency = total_surplus / max_surplus if max_surplus > 0 else 0
        efficiency = min(1.0, max(0.0, efficiency))

        clearing_price = np.mean(prices) if prices else 10.0

        return clearing_price, efficiency, total_surplus


class SupplyShockSimulator:
    """
    Simulate supply shock events and measure recovery dynamics.

    Tests H6.2: Recovery within 10 rounds.
    """

    def __init__(
        self,
        n_buyers: int = 50,
        n_sellers: int = 50,
        base_supply: float = 100.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize supply shock simulator.

        Args:
            n_buyers: Number of buyers
            n_sellers: Number of sellers
            base_supply: Base supply capacity
            seed: Random seed
        """
        self.n_buyers = n_buyers
        self.n_sellers = n_sellers
        self.base_supply = base_supply
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.shocks: List[SupplyShockEvent] = []

    def generate_supply_curve(
        self,
        shock: SupplyShockEvent,
        n_rounds: int = 100,
    ) -> np.ndarray:
        """
        Generate supply fraction curve for a shock event.

        Args:
            shock: Shock event configuration
            n_rounds: Total number of rounds

        Returns:
            Array of supply fractions over time
        """
        supply_curve = np.ones(n_rounds)

        trigger = shock.trigger_round
        drop = shock.supply_drop_fraction

        if shock.shock_type == ShockType.INSTANT:
            # Instant drop, gradual recovery
            supply_curve[trigger:] = 1 - drop
            for i in range(trigger + 1, n_rounds):
                recovery = min(drop, shock.recovery_rate * (i - trigger))
                supply_curve[i] = 1 - drop + recovery

        elif shock.shock_type == ShockType.GRADUAL:
            # Progressive degradation
            for i in range(shock.duration_rounds):
                if trigger + i < n_rounds:
                    progress = (i + 1) / shock.duration_rounds
                    supply_curve[trigger + i] = 1 - drop * progress

            # Recovery after degradation
            end_degradation = trigger + shock.duration_rounds
            for i in range(end_degradation, n_rounds):
                recovery = min(drop, shock.recovery_rate * (i - end_degradation))
                supply_curve[i] = 1 - drop + recovery

        elif shock.shock_type == ShockType.INTERMITTENT:
            # Fluctuating outage
            for i in range(trigger, n_rounds):
                if self.rng.random() < 0.5:
                    supply_curve[i] = 1 - drop * self.rng.uniform(0.5, 1.0)
                else:
                    supply_curve[i] = 1 - drop * self.rng.uniform(0, 0.5)

        elif shock.shock_type == ShockType.CASCADING:
            # Failures spread over time
            current_drop = 0
            for i in range(shock.duration_rounds):
                if trigger + i < n_rounds:
                    current_drop = min(drop, current_drop + drop / shock.duration_rounds)
                    supply_curve[trigger + i] = 1 - current_drop

            # Recovery after cascade
            end_cascade = trigger + shock.duration_rounds
            for i in range(end_cascade, n_rounds):
                recovery = min(drop, shock.recovery_rate * (i - end_cascade))
                supply_curve[i] = 1 - drop + recovery

        # Clamp values
        supply_curve = np.clip(supply_curve, 0.1, 1.0)

        return supply_curve

    def inject_shock(
        self,
        shock: SupplyShockEvent,
        n_rounds: int = 100,
    ) -> SupplyShockResult:
        """
        Simulate supply shock event.

        Args:
            shock: Shock event configuration
            n_rounds: Number of rounds to simulate

        Returns:
            SupplyShockResult with recovery metrics
        """
        # Generate supply curve
        supply_curve = self.generate_supply_curve(shock, n_rounds)

        # Create market simulator
        market = SimpleMarketSimulator(
            n_buyers=self.n_buyers,
            n_sellers=self.n_sellers,
            base_supply=self.base_supply,
            seed=self.seed,
        )

        # Run simulation
        efficiency_series = []
        price_series = []
        welfare_series = []

        for round_idx in range(n_rounds):
            supply_fraction = supply_curve[round_idx]
            price, efficiency, welfare = market.run_round(supply_fraction=supply_fraction)

            efficiency_series.append(efficiency)
            price_series.append(price)
            welfare_series.append(welfare)

        efficiency_series = np.array(efficiency_series)
        price_series = np.array(price_series)
        welfare_series = np.array(welfare_series)

        # Calculate pre-shock metrics
        pre_shock_end = shock.trigger_round
        efficiency_pre_shock = np.mean(efficiency_series[:pre_shock_end])
        price_pre_shock = np.mean(price_series[:pre_shock_end])
        welfare_pre_shock = np.mean(welfare_series[:pre_shock_end])

        # Calculate shock metrics
        shock_start = shock.trigger_round
        shock_end = min(shock_start + 5, n_rounds)  # First 5 rounds of shock

        efficiency_at_shock = np.mean(efficiency_series[shock_start:shock_end])
        efficiency_min = np.min(efficiency_series[shock_start:])
        price_at_shock = np.mean(price_series[shock_start:shock_end])
        price_max = np.max(price_series[shock_start:])

        # Measure recovery time
        recovery_rounds, recovered = self.measure_recovery(
            efficiency_series=efficiency_series[shock_start:],
            pre_shock_efficiency=efficiency_pre_shock,
            threshold=0.9,
        )

        # Calculate welfare loss
        welfare_loss = sum(
            max(0, welfare_pre_shock - w)
            for w in welfare_series[shock_start:]
        )

        return SupplyShockResult(
            shock_event=shock,
            efficiency_pre_shock=float(efficiency_pre_shock),
            efficiency_at_shock=float(efficiency_at_shock),
            efficiency_min=float(efficiency_min),
            recovery_rounds=recovery_rounds,
            recovered=recovered,
            price_pre_shock=float(price_pre_shock),
            price_at_shock=float(price_at_shock),
            price_spike_ratio=float(price_max / price_pre_shock) if price_pre_shock > 0 else 1.0,
            welfare_loss=float(welfare_loss),
            efficiency_series=efficiency_series,
            price_series=price_series,
            supply_fraction_series=supply_curve,
        )

    def measure_recovery(
        self,
        efficiency_series: np.ndarray,
        pre_shock_efficiency: float,
        threshold: float = 0.9,
    ) -> Tuple[int, bool]:
        """
        Count rounds until efficiency >= threshold * pre_shock.

        Args:
            efficiency_series: Efficiency values after shock
            pre_shock_efficiency: Baseline efficiency
            threshold: Recovery threshold (e.g., 0.9 = 90% of baseline)

        Returns:
            (recovery_rounds, recovered)
        """
        target_efficiency = threshold * pre_shock_efficiency

        for i, eff in enumerate(efficiency_series):
            if eff >= target_efficiency:
                return i, True

        return len(efficiency_series), False

    def test_recovery_time(
        self,
        shock: Optional[SupplyShockEvent] = None,
        recovery_threshold: int = 10,
        n_simulations: int = 30,
        alpha: float = 0.05,
    ) -> RecoveryTestResult:
        """
        Test H6.2: Recovery within threshold rounds.

        Args:
            shock: Shock event to test (uses default if None)
            recovery_threshold: Maximum acceptable recovery time
            n_simulations: Number of simulations
            alpha: Significance level

        Returns:
            RecoveryTestResult
        """
        if shock is None:
            shock = SupplyShockEvent(
                name="Default Shock",
                trigger_round=20,
                supply_drop_fraction=0.4,
                recovery_rate=0.15,
                shock_type=ShockType.INSTANT,
            )

        results = []
        recovery_times = []

        for sim_idx in range(n_simulations):
            sim_seed = self.seed + sim_idx if self.seed else None
            self.rng = np.random.default_rng(sim_seed)

            result = self.inject_shock(shock, n_rounds=100)
            results.append(result)
            recovery_times.append(result.recovery_rounds)

        recovery_times = np.array(recovery_times)
        mean_recovery = float(np.mean(recovery_times))
        std_recovery = float(np.std(recovery_times, ddof=1)) if len(recovery_times) > 1 else 0.0

        # Count recoveries
        recovered_count = sum(1 for r in results if r.recovered)
        recovery_rate = recovered_count / n_simulations

        # One-sample t-test: H0: mean > threshold, H1: mean <= threshold
        if std_recovery > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(recovery_times, recovery_threshold)
            # One-tailed test (we want mean <= threshold)
            p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2
        else:
            t_stat = float('-inf') if mean_recovery <= recovery_threshold else float('inf')
            p_value = 0.0 if mean_recovery <= recovery_threshold else 1.0

        passed = mean_recovery <= recovery_threshold and recovery_rate >= 0.9

        return RecoveryTestResult(
            passed=passed,
            mean_recovery_time=mean_recovery,
            std_recovery_time=std_recovery,
            recovery_threshold=recovery_threshold,
            recovery_rate=recovery_rate,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            individual_results=results,
        )

    def run_all_scenarios(
        self,
        n_rounds: int = 100,
    ) -> Dict[str, SupplyShockResult]:
        """
        Run all predefined shock scenarios.

        Args:
            n_rounds: Number of rounds per scenario

        Returns:
            Dictionary mapping scenario name to result
        """
        results = {}

        for shock in SUPPLY_SHOCK_SCENARIOS:
            logger.info(f"Running scenario: {shock.name}")
            result = self.inject_shock(shock, n_rounds)
            results[shock.name] = result

        return results


def simulate_supply_shock_test(
    supply_drop_fraction: float = 0.4,
    recovery_threshold: int = 10,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> RecoveryTestResult:
    """
    Run a supply shock recovery test.

    Args:
        supply_drop_fraction: Fraction of supply lost
        recovery_threshold: Maximum acceptable recovery rounds
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        RecoveryTestResult
    """
    simulator = SupplyShockSimulator(seed=seed)

    shock = SupplyShockEvent(
        name=f"Test Shock ({supply_drop_fraction*100:.0f}% drop)",
        trigger_round=20,
        supply_drop_fraction=supply_drop_fraction,
        recovery_rate=0.15,
        shock_type=ShockType.INSTANT,
    )

    return simulator.test_recovery_time(
        shock=shock,
        recovery_threshold=recovery_threshold,
        n_simulations=n_simulations,
    )
