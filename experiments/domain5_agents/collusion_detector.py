"""
Collusion Detector/Simulator for SHAKTI-CHAIN Agent Behavior (Domain 5).

Tests hypothesis H5.6: Collusion gain < 10%.
Simulates coordinated trading by coalitions and measures profitability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class CollusionStrategy(Enum):
    """Types of collusion strategies."""
    PRICE_FIXING = "price_fixing"
    MARKET_DIVISION = "market_division"
    QUANTITY_RESTRICTION = "quantity_restriction"
    BID_ROTATION = "bid_rotation"
    INFORMATION_SHARING = "information_sharing"


@dataclass
class CollusionSimResult:
    """
    Result of a single collusion simulation.

    Attributes:
        strategy: Collusion strategy used
        coalition_size: Number of agents in coalition
        profit_honest: Coalition profit if trading independently
        profit_collude: Coalition profit with coordination
        collusion_gain: Relative improvement from collusion
        welfare_impact: Change in total market welfare
        non_coalition_welfare: Welfare of non-coalition members
        success_rate: Fraction of rounds where collusion was profitable
    """
    strategy: CollusionStrategy
    coalition_size: int
    profit_honest: float
    profit_collude: float
    collusion_gain: float
    welfare_impact: float
    non_coalition_welfare: float
    success_rate: float
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy.value,
            "coalition_size": self.coalition_size,
            "profit_honest": float(self.profit_honest),
            "profit_collude": float(self.profit_collude),
            "collusion_gain": float(self.collusion_gain),
            "welfare_impact": float(self.welfare_impact),
            "non_coalition_welfare": float(self.non_coalition_welfare),
            "success_rate": float(self.success_rate),
            "additional_info": self.additional_info,
        }


@dataclass
class CollusionTestResult:
    """
    Result of collusion resistance test.

    Attributes:
        is_resistant: Whether market resists collusion (max gain < threshold)
        max_collusion_gain: Maximum gain observed
        mean_collusion_gain: Mean gain across strategies
        gain_threshold: Threshold used
        t_statistic: Two-sample t-test statistic
        p_value: P-value
        results_by_strategy: Results for each strategy
        coalition_size_effect: How gain varies with coalition size
    """
    is_resistant: bool
    max_collusion_gain: float
    mean_collusion_gain: float
    gain_threshold: float
    t_statistic: float
    p_value: float
    results_by_strategy: Dict[str, CollusionSimResult]
    coalition_size_effect: Dict[int, float]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_resistant": self.is_resistant,
            "max_collusion_gain": float(self.max_collusion_gain),
            "mean_collusion_gain": float(self.mean_collusion_gain),
            "gain_threshold": float(self.gain_threshold),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "strategies_tested": list(self.results_by_strategy.keys()),
            "coalition_size_effect": {
                str(k): float(v) for k, v in self.coalition_size_effect.items()
            },
        }


class CollusionSimulator:
    """
    Simulate coordinated trading by coalitions and test profitability.

    Tests H5.6: Collusion gain < 10%.
    """

    def __init__(
        self,
        num_agents: int = 30,
        seed: Optional[int] = None,
    ):
        """
        Initialize collusion simulator.

        Args:
            num_agents: Total number of market agents
            seed: Random seed
        """
        self.num_agents = num_agents
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Generate agent characteristics
        n_buyers = num_agents // 2
        n_sellers = num_agents - n_buyers

        self.buyer_valuations = self.rng.uniform(5, 15, n_buyers)
        self.seller_costs = self.rng.uniform(2, 12, n_sellers)

    def simulate_collusion(
        self,
        coalition_size_fraction: float = 0.1,
        strategy: CollusionStrategy = CollusionStrategy.PRICE_FIXING,
        num_rounds: int = 50,
        n_simulations: int = 30,
    ) -> CollusionSimResult:
        """
        Run market with colluding subset.

        Args:
            coalition_size_fraction: Fraction of agents in coalition
            strategy: Coordination strategy
            num_rounds: Trading rounds per simulation
            n_simulations: Number of simulations

        Returns:
            CollusionSimResult
        """
        coalition_size = max(2, int(self.num_agents * coalition_size_fraction))

        honest_profits = []
        collude_profits = []
        welfare_impacts = []
        non_coalition_welfares = []
        success_counts = []

        for sim in range(n_simulations):
            sim_seed = self.seed + sim if self.seed else None
            rng = np.random.default_rng(sim_seed)

            # Run honest baseline
            honest_profit, baseline_welfare, baseline_nc_welfare = \
                self._run_honest_market(coalition_size, num_rounds, rng)
            honest_profits.append(honest_profit)

            # Run with collusion
            collude_profit, collude_welfare, nc_welfare, successes = \
                self._run_collusion_market(
                    coalition_size, strategy, num_rounds, rng
                )
            collude_profits.append(collude_profit)
            welfare_impacts.append(baseline_welfare - collude_welfare)
            non_coalition_welfares.append(nc_welfare)
            success_counts.append(successes / num_rounds)

        # Calculate statistics
        mean_honest = float(np.mean(honest_profits))
        mean_collude = float(np.mean(collude_profits))

        if mean_honest > 0:
            collusion_gain = (mean_collude - mean_honest) / mean_honest
        elif mean_collude > 0:
            collusion_gain = 1.0  # 100% gain from zero
        else:
            collusion_gain = 0.0

        return CollusionSimResult(
            strategy=strategy,
            coalition_size=coalition_size,
            profit_honest=mean_honest,
            profit_collude=mean_collude,
            collusion_gain=float(collusion_gain),
            welfare_impact=float(np.mean(welfare_impacts)),
            non_coalition_welfare=float(np.mean(non_coalition_welfares)),
            success_rate=float(np.mean(success_counts)),
            additional_info={
                "n_simulations": n_simulations,
                "num_rounds": num_rounds,
                "coalition_fraction": coalition_size_fraction,
                "profit_std_honest": float(np.std(honest_profits)),
                "profit_std_collude": float(np.std(collude_profits)),
            },
        )

    def _run_honest_market(
        self,
        coalition_size: int,
        num_rounds: int,
        rng: np.random.Generator,
    ) -> Tuple[float, float, float]:
        """
        Run market with honest (non-colluding) participation.

        Returns:
            (coalition_profit, total_welfare, non_coalition_welfare)
        """
        n_buyers = len(self.buyer_valuations)
        n_sellers = len(self.seller_costs)

        # Select coalition members (mix of buyers and sellers)
        coalition_buyers = set(rng.choice(n_buyers, size=coalition_size // 2, replace=False))
        coalition_sellers = set(rng.choice(n_sellers, size=coalition_size - coalition_size // 2, replace=False))

        coalition_profit = 0.0
        total_welfare = 0.0
        non_coalition_welfare = 0.0

        for round_idx in range(num_rounds):
            # Generate bids (honest behavior)
            buyer_bids = self.buyer_valuations * rng.uniform(0.9, 1.0, n_buyers)
            seller_asks = self.seller_costs * rng.uniform(1.0, 1.1, n_sellers)

            # Run auction
            clearing_price, matches = self._run_auction(buyer_bids, seller_asks)

            # Calculate profits
            for b, s in matches:
                buyer_surplus = self.buyer_valuations[b] - clearing_price
                seller_surplus = clearing_price - self.seller_costs[s]
                trade_welfare = buyer_surplus + seller_surplus

                total_welfare += trade_welfare

                if b in coalition_buyers:
                    coalition_profit += buyer_surplus
                else:
                    non_coalition_welfare += buyer_surplus

                if s in coalition_sellers:
                    coalition_profit += seller_surplus
                else:
                    non_coalition_welfare += seller_surplus

        return coalition_profit, total_welfare, non_coalition_welfare

    def _run_collusion_market(
        self,
        coalition_size: int,
        strategy: CollusionStrategy,
        num_rounds: int,
        rng: np.random.Generator,
    ) -> Tuple[float, float, float, int]:
        """
        Run market with colluding coalition.

        Returns:
            (coalition_profit, total_welfare, non_coalition_welfare, success_rounds)
        """
        n_buyers = len(self.buyer_valuations)
        n_sellers = len(self.seller_costs)

        # Select coalition members
        coalition_buyers = list(rng.choice(n_buyers, size=coalition_size // 2, replace=False))
        coalition_sellers = list(rng.choice(n_sellers, size=coalition_size - coalition_size // 2, replace=False))

        coalition_profit = 0.0
        total_welfare = 0.0
        non_coalition_welfare = 0.0
        success_rounds = 0

        for round_idx in range(num_rounds):
            # Generate base bids
            buyer_bids = self.buyer_valuations * rng.uniform(0.9, 1.0, n_buyers)
            seller_asks = self.seller_costs * rng.uniform(1.0, 1.1, n_sellers)

            # Apply collusion strategy
            if strategy == CollusionStrategy.PRICE_FIXING:
                buyer_bids, seller_asks = self._apply_price_fixing(
                    buyer_bids, seller_asks,
                    coalition_buyers, coalition_sellers,
                    rng
                )
            elif strategy == CollusionStrategy.QUANTITY_RESTRICTION:
                buyer_bids, seller_asks = self._apply_quantity_restriction(
                    buyer_bids, seller_asks,
                    coalition_buyers, coalition_sellers,
                    rng
                )
            elif strategy == CollusionStrategy.MARKET_DIVISION:
                buyer_bids, seller_asks = self._apply_market_division(
                    buyer_bids, seller_asks,
                    coalition_buyers, coalition_sellers,
                    round_idx, rng
                )
            elif strategy == CollusionStrategy.BID_ROTATION:
                buyer_bids, seller_asks = self._apply_bid_rotation(
                    buyer_bids, seller_asks,
                    coalition_buyers, coalition_sellers,
                    round_idx, rng
                )

            # Run auction
            clearing_price, matches = self._run_auction(buyer_bids, seller_asks)

            # Track round success
            round_coalition_profit = 0.0

            # Calculate profits
            for b, s in matches:
                buyer_surplus = self.buyer_valuations[b] - clearing_price
                seller_surplus = clearing_price - self.seller_costs[s]
                trade_welfare = buyer_surplus + seller_surplus

                total_welfare += trade_welfare

                if b in coalition_buyers:
                    coalition_profit += buyer_surplus
                    round_coalition_profit += buyer_surplus
                else:
                    non_coalition_welfare += buyer_surplus

                if s in coalition_sellers:
                    coalition_profit += seller_surplus
                    round_coalition_profit += seller_surplus
                else:
                    non_coalition_welfare += seller_surplus

            if round_coalition_profit > 0:
                success_rounds += 1

        return coalition_profit, total_welfare, non_coalition_welfare, success_rounds

    def _apply_price_fixing(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
        coalition_buyers: List[int],
        coalition_sellers: List[int],
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply price fixing strategy.

        Coalition agrees on a common price.
        """
        # Coalition sellers ask high price
        target_price = np.percentile(self.buyer_valuations, 75)  # Aim high

        for s in coalition_sellers:
            seller_asks[s] = target_price * 1.05  # Slightly above target

        # Coalition buyers bid at target (to ensure trades happen within coalition)
        for b in coalition_buyers:
            buyer_bids[b] = target_price

        return buyer_bids, seller_asks

    def _apply_quantity_restriction(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
        coalition_buyers: List[int],
        coalition_sellers: List[int],
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply quantity restriction strategy.

        Coalition limits supply to raise prices.
        """
        # Half of coalition sellers withdraw from market
        withdraw_sellers = coalition_sellers[::2]

        for s in withdraw_sellers:
            seller_asks[s] = 1000.0  # Effectively withdraw

        return buyer_bids, seller_asks

    def _apply_market_division(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
        coalition_buyers: List[int],
        coalition_sellers: List[int],
        round_idx: int,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply market division strategy.

        Coalition members take turns dominating different market segments.
        """
        # Alternate which coalition members are active
        active_idx = round_idx % max(1, len(coalition_sellers))

        for i, s in enumerate(coalition_sellers):
            if i != active_idx:
                seller_asks[s] = 1000.0  # Withdraw

        return buyer_bids, seller_asks

    def _apply_bid_rotation(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
        coalition_buyers: List[int],
        coalition_sellers: List[int],
        round_idx: int,
        rng: np.random.Generator,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply bid rotation strategy.

        Coalition members take turns winning, others bid low/high.
        """
        winner_idx = round_idx % max(1, len(coalition_buyers))

        for i, b in enumerate(coalition_buyers):
            if i == winner_idx:
                buyer_bids[b] = self.buyer_valuations[b]  # Full valuation
            else:
                buyer_bids[b] = 0.0  # Drop out

        return buyer_bids, seller_asks

    def _run_auction(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
    ) -> Tuple[float, List[Tuple[int, int]]]:
        """Run double auction."""
        buyer_order = np.argsort(buyer_bids)[::-1]
        seller_order = np.argsort(seller_asks)

        matches = []
        b_idx = 0
        s_idx = 0

        while b_idx < len(buyer_order) and s_idx < len(seller_order):
            buyer = buyer_order[b_idx]
            seller = seller_order[s_idx]

            if buyer_bids[buyer] >= seller_asks[seller]:
                matches.append((buyer, seller))
                b_idx += 1
                s_idx += 1
            else:
                break

        if matches:
            last_buyer = matches[-1][0]
            last_seller = matches[-1][1]
            clearing_price = (buyer_bids[last_buyer] + seller_asks[last_seller]) / 2
        else:
            clearing_price = np.mean(seller_asks)

        return clearing_price, matches

    def test_all_strategies(
        self,
        coalition_size_fraction: float = 0.1,
        n_simulations: int = 30,
    ) -> Dict[str, CollusionSimResult]:
        """
        Test all collusion strategies.

        Args:
            coalition_size_fraction: Fraction of agents in coalition
            n_simulations: Number of simulations per strategy

        Returns:
            Dictionary mapping strategy name to result
        """
        results = {}

        for strategy in CollusionStrategy:
            result = self.simulate_collusion(
                coalition_size_fraction=coalition_size_fraction,
                strategy=strategy,
                n_simulations=n_simulations,
            )
            results[strategy.value] = result

        return results

    def test_coalition_size_effect(
        self,
        coalition_fractions: List[float] = None,
        strategy: CollusionStrategy = CollusionStrategy.PRICE_FIXING,
        n_simulations: int = 20,
    ) -> Dict[int, float]:
        """
        Test how collusion gain varies with coalition size.

        Args:
            coalition_fractions: Fractions to test
            strategy: Strategy to use
            n_simulations: Simulations per size

        Returns:
            Dictionary mapping coalition size to collusion gain
        """
        if coalition_fractions is None:
            coalition_fractions = [0.05, 0.10, 0.20, 0.30, 0.50]

        results = {}

        for fraction in coalition_fractions:
            result = self.simulate_collusion(
                coalition_size_fraction=fraction,
                strategy=strategy,
                n_simulations=n_simulations,
            )
            results[result.coalition_size] = result.collusion_gain

        return results

    def test_collusion_resistance(
        self,
        gain_threshold: float = 0.10,
        coalition_size_fraction: float = 0.10,
        n_simulations: int = 30,
        alpha: float = 0.05,
    ) -> CollusionTestResult:
        """
        Test if market is resistant to collusion.

        Tests H5.6: Collusion gain < 10%.

        Args:
            gain_threshold: Maximum acceptable collusion gain
            coalition_size_fraction: Coalition size to test
            n_simulations: Number of simulations
            alpha: Significance level

        Returns:
            CollusionTestResult
        """
        # Test all strategies
        results = self.test_all_strategies(
            coalition_size_fraction=coalition_size_fraction,
            n_simulations=n_simulations,
        )

        # Test coalition size effect
        size_effect = self.test_coalition_size_effect(n_simulations=n_simulations // 2)

        # Aggregate results
        gains = [r.collusion_gain for r in results.values()]
        honest_profits = [r.profit_honest for r in results.values()]
        collude_profits = [r.profit_collude for r in results.values()]

        mean_gain = float(np.mean(gains))
        max_gain = float(np.max(gains))

        # Two-sample t-test: collude vs honest profits
        if len(honest_profits) > 1 and len(collude_profits) > 1:
            t_stat, p_value = scipy_stats.ttest_ind(collude_profits, honest_profits)
        else:
            t_stat = 0.0
            p_value = 0.5

        # Resistant if max gain < threshold
        is_resistant = max_gain < gain_threshold

        return CollusionTestResult(
            is_resistant=is_resistant,
            max_collusion_gain=max_gain,
            mean_collusion_gain=mean_gain,
            gain_threshold=gain_threshold,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            results_by_strategy=results,
            coalition_size_effect=size_effect,
        )


def simulate_collusion_test(
    num_agents: int = 30,
    coalition_fraction: float = 0.10,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> CollusionTestResult:
    """
    Run a simulated collusion resistance test.

    Args:
        num_agents: Number of market agents
        coalition_fraction: Fraction forming coalition
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        CollusionTestResult
    """
    simulator = CollusionSimulator(
        num_agents=num_agents,
        seed=seed,
    )

    return simulator.test_collusion_resistance(
        coalition_size_fraction=coalition_fraction,
        n_simulations=n_simulations,
    )
