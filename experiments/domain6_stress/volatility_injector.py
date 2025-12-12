"""
Volatility Injector for SHAKTI-CHAIN Stress Testing (Domain 6).

Tests hypothesis H6.3: No market failure at 3σ variance.
Injects high variance into demand/supply patterns and monitors for failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class VolatilityPattern(Enum):
    """Types of volatility patterns."""
    GAUSSIAN = "gaussian"           # Normal distribution noise
    HEAVY_TAILED = "heavy_tailed"   # Fat-tailed distribution
    CLUSTERED = "clustered"         # Volatility clustering (GARCH-like)
    JUMP = "jump"                   # Random jumps/spikes
    MEAN_REVERTING = "mean_reverting"  # Ornstein-Uhlenbeck


@dataclass
class VolatilityScenario:
    """
    Configuration for a volatility scenario.

    Attributes:
        name: Scenario name
        variance_multiplier: Multiple of base variance (3.0 = 3σ)
        pattern: Type of volatility pattern
        duration_rounds: Duration of high volatility
        base_variance: Base variance level
    """
    name: str
    variance_multiplier: float
    pattern: VolatilityPattern
    duration_rounds: int
    base_variance: float = 0.1

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "variance_multiplier": float(self.variance_multiplier),
            "pattern": self.pattern.value,
            "duration_rounds": self.duration_rounds,
            "base_variance": float(self.base_variance),
        }


# Predefined volatility scenarios
HIGH_VARIANCE_GAUSSIAN = VolatilityScenario(
    name="High Variance Gaussian",
    variance_multiplier=3.0,
    pattern=VolatilityPattern.GAUSSIAN,
    duration_rounds=50,
    base_variance=0.1,
)

EXTREME_VARIANCE = VolatilityScenario(
    name="Extreme Variance (5σ)",
    variance_multiplier=5.0,
    pattern=VolatilityPattern.GAUSSIAN,
    duration_rounds=30,
    base_variance=0.1,
)

HEAVY_TAILED_VOLATILITY = VolatilityScenario(
    name="Heavy-Tailed Volatility",
    variance_multiplier=3.0,
    pattern=VolatilityPattern.HEAVY_TAILED,
    duration_rounds=50,
    base_variance=0.1,
)

VOLATILITY_CLUSTERING = VolatilityScenario(
    name="Volatility Clustering",
    variance_multiplier=3.0,
    pattern=VolatilityPattern.CLUSTERED,
    duration_rounds=50,
    base_variance=0.1,
)

JUMP_VOLATILITY = VolatilityScenario(
    name="Jump Volatility",
    variance_multiplier=4.0,
    pattern=VolatilityPattern.JUMP,
    duration_rounds=50,
    base_variance=0.1,
)

VOLATILITY_SCENARIOS = [
    HIGH_VARIANCE_GAUSSIAN,
    EXTREME_VARIANCE,
    HEAVY_TAILED_VOLATILITY,
    VOLATILITY_CLUSTERING,
    JUMP_VOLATILITY,
]


@dataclass
class VolatilityTestResult:
    """
    Result of a volatility stress test.

    Attributes:
        scenario: The volatility scenario tested
        market_failed: Whether market failure occurred
        failure_round: Round when failure occurred (if any)
        consecutive_zero_trade_rounds: Max consecutive rounds with no trades
        min_efficiency: Minimum efficiency observed
        mean_efficiency: Mean efficiency during volatility
        efficiency_variance: Variance of efficiency
        trade_count_series: Number of trades per round
        efficiency_series: Efficiency per round
        price_volatility: Price standard deviation
    """
    scenario: VolatilityScenario
    market_failed: bool
    failure_round: Optional[int]
    consecutive_zero_trade_rounds: int
    min_efficiency: float
    mean_efficiency: float
    efficiency_variance: float
    trade_count_series: np.ndarray = field(default_factory=lambda: np.array([]))
    efficiency_series: np.ndarray = field(default_factory=lambda: np.array([]))
    price_volatility: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario.to_dict(),
            "market_failed": self.market_failed,
            "failure_round": self.failure_round,
            "consecutive_zero_trade_rounds": self.consecutive_zero_trade_rounds,
            "min_efficiency": float(self.min_efficiency),
            "mean_efficiency": float(self.mean_efficiency),
            "efficiency_variance": float(self.efficiency_variance),
            "price_volatility": float(self.price_volatility),
        }


@dataclass
class StabilityTestResult:
    """
    Result of market stability hypothesis test (H6.3).

    Attributes:
        passed: Whether no market failure at target variance
        failure_count: Number of simulations with failure
        total_simulations: Total simulations run
        failure_rate: Fraction of simulations with failure
        variance_multiplier_tested: Variance multiplier tested
        mean_consecutive_zeros: Mean max consecutive zero-trade rounds
        individual_results: Results from each simulation
    """
    passed: bool
    failure_count: int
    total_simulations: int
    failure_rate: float
    variance_multiplier_tested: float
    mean_consecutive_zeros: float
    individual_results: List[VolatilityTestResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "failure_count": self.failure_count,
            "total_simulations": self.total_simulations,
            "failure_rate": float(self.failure_rate),
            "variance_multiplier_tested": float(self.variance_multiplier_tested),
            "mean_consecutive_zeros": float(self.mean_consecutive_zeros),
        }


class SimpleMarketSimulator:
    """Simplified market simulator for volatility testing."""

    def __init__(
        self,
        n_buyers: int = 50,
        n_sellers: int = 50,
        base_demand: float = 100.0,
        seed: Optional[int] = None,
    ):
        self.n_buyers = n_buyers
        self.n_sellers = n_sellers
        self.base_demand = base_demand
        self.rng = np.random.default_rng(seed)

        # Generate base characteristics
        self.base_buyer_valuations = self.rng.uniform(8, 15, n_buyers)
        self.base_seller_costs = self.rng.uniform(2, 10, n_sellers)
        self.seller_capacities = self.rng.uniform(1, 5, n_sellers)
        self.seller_capacities = self.seller_capacities / self.seller_capacities.sum() * base_demand

    def run_round(
        self,
        demand_noise: float = 0.0,
        supply_noise: float = 0.0,
        valuation_noise: np.ndarray = None,
        cost_noise: np.ndarray = None,
    ) -> Tuple[float, float, int]:
        """
        Run a single market round with noise.

        Args:
            demand_noise: Additive demand noise
            supply_noise: Multiplicative supply noise
            valuation_noise: Per-buyer valuation noise
            cost_noise: Per-seller cost noise

        Returns:
            (clearing_price, efficiency, trade_count)
        """
        # Apply noise to valuations
        if valuation_noise is not None:
            buyer_valuations = self.base_buyer_valuations + valuation_noise
        else:
            buyer_valuations = self.base_buyer_valuations.copy()

        # Apply noise to costs
        if cost_noise is not None:
            seller_costs = self.base_seller_costs + cost_noise
        else:
            seller_costs = self.base_seller_costs.copy()

        # Apply supply noise
        supply_multiplier = 1.0 + supply_noise
        available_supply = self.seller_capacities * max(0.1, supply_multiplier)

        # Clamp values to reasonable ranges
        buyer_valuations = np.clip(buyer_valuations, 1, 30)
        seller_costs = np.clip(seller_costs, 0.5, 20)

        # Generate demands
        demand_multiplier = 1.0 + demand_noise / self.base_demand
        demand_multiplier = max(0.1, demand_multiplier)
        buyer_demands = self.rng.uniform(1, 4, self.n_buyers) * demand_multiplier

        # Match using merit order
        buyer_order = np.argsort(buyer_valuations)[::-1]
        seller_order = np.argsort(seller_costs)

        trade_count = 0
        total_surplus = 0.0
        prices = []
        remaining_supply = available_supply.copy()

        for buyer_idx in buyer_order:
            buyer_val = buyer_valuations[buyer_idx]
            buyer_demand = buyer_demands[buyer_idx]
            bought = 0.0

            for seller_idx in seller_order:
                if remaining_supply[seller_idx] <= 0:
                    continue
                if seller_costs[seller_idx] > buyer_val:
                    break

                trade_qty = min(buyer_demand - bought, remaining_supply[seller_idx])
                if trade_qty > 0:
                    price = (buyer_val + seller_costs[seller_idx]) / 2
                    surplus = (buyer_val - seller_costs[seller_idx]) * trade_qty

                    total_surplus += surplus
                    prices.append(price)
                    trade_count += 1
                    bought += trade_qty
                    remaining_supply[seller_idx] -= trade_qty

                if bought >= buyer_demand:
                    break

        # Calculate max possible surplus
        max_surplus = 0.0
        sorted_vals = np.sort(buyer_valuations)[::-1]
        sorted_costs = np.sort(seller_costs)

        for val, cost in zip(sorted_vals, sorted_costs):
            if val >= cost:
                max_surplus += val - cost

        efficiency = total_surplus / max_surplus if max_surplus > 0 else 0
        efficiency = min(1.0, max(0.0, efficiency))

        clearing_price = np.mean(prices) if prices else 10.0

        return clearing_price, efficiency, trade_count


class VolatilityInjector:
    """
    Inject high variance into market signals.

    Tests H6.3: No market failure at 3σ variance.
    """

    def __init__(
        self,
        base_variance: float = 0.1,
        seed: Optional[int] = None,
    ):
        """
        Initialize volatility injector.

        Args:
            base_variance: Base variance level
            seed: Random seed
        """
        self.base_variance = base_variance
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def inject_volatility(
        self,
        signal: np.ndarray,
        variance_multiplier: float = 3.0,
        pattern: VolatilityPattern = VolatilityPattern.GAUSSIAN,
    ) -> np.ndarray:
        """
        Add noise with increased variance to a signal.

        Args:
            signal: Base signal
            variance_multiplier: Multiple of base variance
            pattern: Type of volatility pattern

        Returns:
            Signal with added volatility
        """
        n = len(signal)
        actual_variance = self.base_variance * variance_multiplier

        if pattern == VolatilityPattern.GAUSSIAN:
            noise = self.rng.normal(0, actual_variance, n)

        elif pattern == VolatilityPattern.HEAVY_TAILED:
            # Student's t distribution with low degrees of freedom
            noise = self.rng.standard_t(df=3, size=n) * actual_variance

        elif pattern == VolatilityPattern.CLUSTERED:
            # GARCH-like volatility clustering
            noise = np.zeros(n)
            volatility = actual_variance
            for i in range(n):
                noise[i] = self.rng.normal(0, volatility)
                # Update volatility based on previous shock
                volatility = 0.9 * volatility + 0.1 * actual_variance * (1 + abs(noise[i]))

        elif pattern == VolatilityPattern.JUMP:
            # Normal noise with occasional jumps
            noise = self.rng.normal(0, actual_variance * 0.5, n)
            # Add jumps with 10% probability
            jump_mask = self.rng.random(n) < 0.1
            jumps = self.rng.normal(0, actual_variance * 3, n)
            noise[jump_mask] += jumps[jump_mask]

        elif pattern == VolatilityPattern.MEAN_REVERTING:
            # Ornstein-Uhlenbeck process
            noise = np.zeros(n)
            theta = 0.5  # Mean reversion speed
            for i in range(1, n):
                noise[i] = noise[i-1] - theta * noise[i-1] + self.rng.normal(0, actual_variance)

        else:
            noise = self.rng.normal(0, actual_variance, n)

        return signal + noise

    def detect_market_failure(
        self,
        trade_counts: np.ndarray,
        failure_threshold: int = 3,
    ) -> Tuple[bool, Optional[int], int]:
        """
        Check if market failed (no trades for consecutive rounds).

        Args:
            trade_counts: Number of trades per round
            failure_threshold: Consecutive zero-trade rounds for failure

        Returns:
            (failed, failure_round, max_consecutive_zeros)
        """
        consecutive_zeros = 0
        max_consecutive = 0
        failure_round = None

        for i, count in enumerate(trade_counts):
            if count == 0:
                consecutive_zeros += 1
                max_consecutive = max(max_consecutive, consecutive_zeros)
                if consecutive_zeros >= failure_threshold and failure_round is None:
                    failure_round = i - failure_threshold + 1
            else:
                consecutive_zeros = 0

        failed = max_consecutive >= failure_threshold

        return failed, failure_round, max_consecutive

    def run_volatility_test(
        self,
        scenario: VolatilityScenario,
        n_rounds: int = 100,
        failure_threshold: int = 3,
    ) -> VolatilityTestResult:
        """
        Run a single volatility stress test.

        Args:
            scenario: Volatility scenario configuration
            n_rounds: Number of rounds to simulate
            failure_threshold: Consecutive zero rounds for failure

        Returns:
            VolatilityTestResult
        """
        # Create market simulator
        market = SimpleMarketSimulator(seed=self.seed)

        # Generate volatility for demand and supply
        base_demand = np.ones(n_rounds) * market.base_demand
        demand_signal = self.inject_volatility(
            base_demand,
            variance_multiplier=scenario.variance_multiplier,
            pattern=scenario.pattern,
        )

        # Run simulation
        trade_counts = []
        efficiency_series = []
        price_series = []

        for round_idx in range(n_rounds):
            # Calculate noise for this round
            demand_noise = demand_signal[round_idx] - market.base_demand
            supply_noise = self.rng.normal(0, scenario.base_variance * scenario.variance_multiplier)

            # Generate per-agent noise
            valuation_noise = self.rng.normal(
                0, scenario.base_variance * scenario.variance_multiplier * 2,
                market.n_buyers
            )
            cost_noise = self.rng.normal(
                0, scenario.base_variance * scenario.variance_multiplier * 2,
                market.n_sellers
            )

            price, efficiency, trades = market.run_round(
                demand_noise=demand_noise,
                supply_noise=supply_noise,
                valuation_noise=valuation_noise,
                cost_noise=cost_noise,
            )

            trade_counts.append(trades)
            efficiency_series.append(efficiency)
            price_series.append(price)

        trade_counts = np.array(trade_counts)
        efficiency_series = np.array(efficiency_series)
        price_series = np.array(price_series)

        # Detect failure
        failed, failure_round, max_consecutive = self.detect_market_failure(
            trade_counts, failure_threshold
        )

        return VolatilityTestResult(
            scenario=scenario,
            market_failed=failed,
            failure_round=failure_round,
            consecutive_zero_trade_rounds=max_consecutive,
            min_efficiency=float(np.min(efficiency_series)),
            mean_efficiency=float(np.mean(efficiency_series)),
            efficiency_variance=float(np.var(efficiency_series)),
            trade_count_series=trade_counts,
            efficiency_series=efficiency_series,
            price_volatility=float(np.std(price_series)),
        )

    def test_stability_threshold(
        self,
        variance_multiplier: float = 3.0,
        n_simulations: int = 30,
        failure_threshold: int = 3,
    ) -> StabilityTestResult:
        """
        Test H6.3: No market failure at given variance multiplier.

        Args:
            variance_multiplier: Target variance multiplier (e.g., 3.0 for 3σ)
            n_simulations: Number of simulations
            failure_threshold: Consecutive zero rounds for failure

        Returns:
            StabilityTestResult
        """
        scenario = VolatilityScenario(
            name=f"Stability Test ({variance_multiplier}σ)",
            variance_multiplier=variance_multiplier,
            pattern=VolatilityPattern.GAUSSIAN,
            duration_rounds=50,
            base_variance=self.base_variance,
        )

        results = []
        failure_count = 0
        consecutive_zeros_list = []

        for sim_idx in range(n_simulations):
            sim_seed = self.seed + sim_idx if self.seed else None
            self.rng = np.random.default_rng(sim_seed)

            result = self.run_volatility_test(
                scenario=scenario,
                n_rounds=100,
                failure_threshold=failure_threshold,
            )
            results.append(result)

            if result.market_failed:
                failure_count += 1
            consecutive_zeros_list.append(result.consecutive_zero_trade_rounds)

        failure_rate = failure_count / n_simulations
        mean_consecutive_zeros = float(np.mean(consecutive_zeros_list))

        # Passed if no failures (or very low failure rate)
        passed = failure_count == 0

        return StabilityTestResult(
            passed=passed,
            failure_count=failure_count,
            total_simulations=n_simulations,
            failure_rate=failure_rate,
            variance_multiplier_tested=variance_multiplier,
            mean_consecutive_zeros=mean_consecutive_zeros,
            individual_results=results,
        )

    def run_all_scenarios(
        self,
        n_rounds: int = 100,
    ) -> Dict[str, VolatilityTestResult]:
        """
        Run all predefined volatility scenarios.

        Args:
            n_rounds: Number of rounds per scenario

        Returns:
            Dictionary mapping scenario name to result
        """
        results = {}

        for scenario in VOLATILITY_SCENARIOS:
            logger.info(f"Running scenario: {scenario.name}")
            result = self.run_volatility_test(scenario, n_rounds)
            results[scenario.name] = result

        return results


def simulate_volatility_test(
    variance_multiplier: float = 3.0,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> StabilityTestResult:
    """
    Run a volatility stability test.

    Args:
        variance_multiplier: Target variance multiplier
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        StabilityTestResult
    """
    injector = VolatilityInjector(seed=seed)

    return injector.test_stability_threshold(
        variance_multiplier=variance_multiplier,
        n_simulations=n_simulations,
    )
