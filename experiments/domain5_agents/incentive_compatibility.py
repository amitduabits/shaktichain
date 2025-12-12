"""
Incentive Compatibility Tester for SHAKTI-CHAIN Agent Behavior (Domain 5).

Tests hypothesis H5.1: Truthful bidding yields utility >= any deviation.
Uses exact binomial test on deviation success rate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class DeviationResult:
    """
    Result of testing a single deviation strategy.

    Attributes:
        agent_id: Agent tested
        true_valuation: Agent's true valuation/cost
        deviation_factor: Relative deviation tested (e.g., -0.2 = 20% below)
        strategic_bid: The bid placed with deviation
        utility_truthful: Utility when bidding truthfully
        utility_deviation: Utility with this deviation
        is_profitable: Whether deviation was profitable
        utility_difference: deviation - truthful utility
    """
    agent_id: str
    true_valuation: float
    deviation_factor: float
    strategic_bid: float
    utility_truthful: float
    utility_deviation: float
    is_profitable: bool
    utility_difference: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "true_valuation": float(self.true_valuation),
            "deviation_factor": float(self.deviation_factor),
            "strategic_bid": float(self.strategic_bid),
            "utility_truthful": float(self.utility_truthful),
            "utility_deviation": float(self.utility_deviation),
            "is_profitable": self.is_profitable,
            "utility_difference": float(self.utility_difference),
        }


@dataclass
class AgentICResult:
    """
    Incentive compatibility result for a single agent.

    Attributes:
        agent_id: Agent tested
        true_valuation: True value/cost
        utility_truthful: Utility from truthful bidding
        utility_deviate_max: Maximum utility from any deviation
        best_deviation_factor: The most profitable deviation
        profitable_deviation_exists: Whether any deviation was profitable
        all_deviations: All deviation results tested
    """
    agent_id: str
    true_valuation: float
    utility_truthful: float
    utility_deviate_max: float
    best_deviation_factor: float
    profitable_deviation_exists: bool
    all_deviations: List[DeviationResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "true_valuation": float(self.true_valuation),
            "utility_truthful": float(self.utility_truthful),
            "utility_deviate_max": float(self.utility_deviate_max),
            "best_deviation_factor": float(self.best_deviation_factor),
            "profitable_deviation_exists": self.profitable_deviation_exists,
            "num_deviations_tested": len(self.all_deviations),
        }


@dataclass
class ICTestResult:
    """
    Result of comprehensive incentive compatibility test.

    Attributes:
        is_incentive_compatible: Whether mechanism is IC
        deviation_success_count: Number of profitable deviations
        total_tests: Total deviation tests run
        deviation_success_rate: Fraction of profitable deviations
        binomial_p_value: P-value from exact binomial test
        mean_deviation_gain: Mean gain from deviating (when profitable)
        max_deviation_gain: Maximum gain observed
        agent_results: Per-agent IC results
    """
    is_incentive_compatible: bool
    deviation_success_count: int
    total_tests: int
    deviation_success_rate: float
    binomial_p_value: float
    mean_deviation_gain: float
    max_deviation_gain: float
    agent_results: List[AgentICResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_incentive_compatible": self.is_incentive_compatible,
            "deviation_success_count": self.deviation_success_count,
            "total_tests": self.total_tests,
            "deviation_success_rate": float(self.deviation_success_rate),
            "binomial_p_value": float(self.binomial_p_value),
            "mean_deviation_gain": float(self.mean_deviation_gain),
            "max_deviation_gain": float(self.max_deviation_gain),
            "num_agents_tested": len(self.agent_results),
        }


class SimpleMarketSimulator:
    """
    Simplified market simulator for IC testing.

    Implements a sealed-bid double auction with uniform price.
    """

    def __init__(
        self,
        num_buyers: int = 10,
        num_sellers: int = 10,
        buyer_valuations: Optional[np.ndarray] = None,
        seller_costs: Optional[np.ndarray] = None,
        seed: Optional[int] = None,
    ):
        """
        Initialize market simulator.

        Args:
            num_buyers: Number of buyers
            num_sellers: Number of sellers
            buyer_valuations: Pre-set buyer valuations
            seller_costs: Pre-set seller costs
            seed: Random seed
        """
        self.rng = np.random.default_rng(seed)
        self.num_buyers = num_buyers
        self.num_sellers = num_sellers

        # Generate or use provided valuations
        if buyer_valuations is not None:
            self.buyer_valuations = np.asarray(buyer_valuations)
        else:
            # Uniform distribution between 5 and 15 INR/kWh
            self.buyer_valuations = self.rng.uniform(5, 15, num_buyers)

        if seller_costs is not None:
            self.seller_costs = np.asarray(seller_costs)
        else:
            # Uniform distribution between 2 and 12 INR/kWh
            self.seller_costs = self.rng.uniform(2, 12, num_sellers)

    def run_auction(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
    ) -> Tuple[float, List[Tuple[int, int, float]]]:
        """
        Run sealed-bid double auction.

        Args:
            buyer_bids: Bids from buyers
            seller_asks: Asks from sellers

        Returns:
            clearing_price: The uniform clearing price
            matches: List of (buyer_idx, seller_idx, quantity) tuples
        """
        # Sort buyers by bid descending
        buyer_order = np.argsort(buyer_bids)[::-1]
        # Sort sellers by ask ascending
        seller_order = np.argsort(seller_asks)

        matches = []
        b_idx = 0
        s_idx = 0

        while b_idx < len(buyer_order) and s_idx < len(seller_order):
            buyer = buyer_order[b_idx]
            seller = seller_order[s_idx]

            if buyer_bids[buyer] >= seller_asks[seller]:
                # Match at midpoint price
                price = (buyer_bids[buyer] + seller_asks[seller]) / 2
                matches.append((buyer, seller, 1.0, price))
                b_idx += 1
                s_idx += 1
            else:
                break

        # Calculate uniform clearing price (average of matched prices)
        if matches:
            clearing_price = np.mean([m[3] for m in matches])
        else:
            clearing_price = 0.0

        return clearing_price, [(m[0], m[1], m[2]) for m in matches]

    def compute_utility(
        self,
        agent_idx: int,
        is_buyer: bool,
        clearing_price: float,
        matched: bool,
    ) -> float:
        """
        Compute utility for an agent.

        Args:
            agent_idx: Agent index
            is_buyer: Whether agent is buyer
            clearing_price: The clearing price
            matched: Whether agent was matched

        Returns:
            Utility (surplus) for the agent
        """
        if not matched:
            return 0.0

        if is_buyer:
            return self.buyer_valuations[agent_idx] - clearing_price
        else:
            return clearing_price - self.seller_costs[agent_idx]


class IncentiveCompatibilityTester:
    """
    Test if truthful bidding is a dominant strategy.

    For each agent, compare utility of truthful bid vs deviations.
    Uses exact binomial test on deviation success rate.
    """

    def __init__(
        self,
        num_buyers: int = 10,
        num_sellers: int = 10,
        seed: Optional[int] = None,
    ):
        """
        Initialize IC tester.

        Args:
            num_buyers: Number of buyers in market
            num_sellers: Number of sellers in market
            seed: Random seed
        """
        self.num_buyers = num_buyers
        self.num_sellers = num_sellers
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.deviation_results: List[DeviationResult] = []

    def test_single_agent(
        self,
        agent_idx: int,
        is_buyer: bool,
        true_valuation: float,
        other_buyer_bids: np.ndarray,
        other_seller_asks: np.ndarray,
        deviations: List[float] = None,
    ) -> AgentICResult:
        """
        Test truthful vs strategic bidding for one agent.

        Args:
            agent_idx: Index of agent to test
            is_buyer: Whether agent is buyer
            true_valuation: True value/cost
            other_buyer_bids: Bids from other buyers
            other_seller_asks: Asks from other sellers
            deviations: Relative deviations to test

        Returns:
            AgentICResult with utility comparisons
        """
        if deviations is None:
            deviations = [-0.3, -0.2, -0.1, -0.05, 0.05, 0.1, 0.2, 0.3]

        market = SimpleMarketSimulator(
            num_buyers=len(other_buyer_bids) + (1 if is_buyer else 0),
            num_sellers=len(other_seller_asks) + (0 if is_buyer else 1),
        )

        # Run with truthful bid
        utility_truthful = self._run_with_bid(
            agent_idx, is_buyer, true_valuation,
            other_buyer_bids, other_seller_asks, market
        )

        # Run with each deviation
        deviation_results = []
        max_utility = utility_truthful
        best_deviation = 0.0

        for d in deviations:
            strategic_bid = true_valuation * (1 + d)

            # For buyers, don't bid above true value in normal circumstances
            # For sellers, don't ask below true cost
            if is_buyer and d > 0:
                strategic_bid = min(strategic_bid, true_valuation * 1.5)
            elif not is_buyer and d < 0:
                strategic_bid = max(strategic_bid, true_valuation * 0.5)

            utility_deviation = self._run_with_bid(
                agent_idx, is_buyer, strategic_bid,
                other_buyer_bids, other_seller_asks, market
            )

            is_profitable = utility_deviation > utility_truthful

            result = DeviationResult(
                agent_id=f"{'buyer' if is_buyer else 'seller'}_{agent_idx}",
                true_valuation=true_valuation,
                deviation_factor=d,
                strategic_bid=strategic_bid,
                utility_truthful=utility_truthful,
                utility_deviation=utility_deviation,
                is_profitable=is_profitable,
                utility_difference=utility_deviation - utility_truthful,
            )
            deviation_results.append(result)
            self.deviation_results.append(result)

            if utility_deviation > max_utility:
                max_utility = utility_deviation
                best_deviation = d

        return AgentICResult(
            agent_id=f"{'buyer' if is_buyer else 'seller'}_{agent_idx}",
            true_valuation=true_valuation,
            utility_truthful=utility_truthful,
            utility_deviate_max=max_utility,
            best_deviation_factor=best_deviation,
            profitable_deviation_exists=max_utility > utility_truthful,
            all_deviations=deviation_results,
        )

    def _run_with_bid(
        self,
        agent_idx: int,
        is_buyer: bool,
        bid: float,
        other_buyer_bids: np.ndarray,
        other_seller_asks: np.ndarray,
        market: SimpleMarketSimulator,
    ) -> float:
        """Run market with agent using specified bid."""
        if is_buyer:
            buyer_bids = np.insert(other_buyer_bids, agent_idx, bid)
            seller_asks = other_seller_asks.copy()
            market.buyer_valuations = np.insert(
                market.buyer_valuations[:len(other_buyer_bids)],
                agent_idx,
                bid  # Use bid as valuation for utility calc
            )
        else:
            buyer_bids = other_buyer_bids.copy()
            seller_asks = np.insert(other_seller_asks, agent_idx, bid)
            market.seller_costs = np.insert(
                market.seller_costs[:len(other_seller_asks)],
                agent_idx,
                bid
            )

        clearing_price, matches = market.run_auction(buyer_bids, seller_asks)

        # Check if agent was matched
        matched = False
        for b, s, _ in matches:
            if is_buyer and b == agent_idx:
                matched = True
                break
            elif not is_buyer and s == agent_idx:
                matched = True
                break

        return market.compute_utility(agent_idx, is_buyer, clearing_price, matched)

    def run_comprehensive_test(
        self,
        n_agents: int = 100,
        n_rounds: int = 50,
        deviations: List[float] = None,
        alpha: float = 0.05,
    ) -> ICTestResult:
        """
        Test IC for many agents over many rounds.

        Args:
            n_agents: Number of agents to test
            n_rounds: Number of rounds per agent
            deviations: Deviation factors to test
            alpha: Significance level

        Returns:
            ICTestResult with deviation success rate and statistical test
        """
        if deviations is None:
            deviations = [-0.3, -0.2, -0.1, -0.05, 0.05, 0.1, 0.2, 0.3]

        self.deviation_results = []
        agent_results = []

        for round_idx in range(n_rounds):
            # Generate new market
            seed = self.seed + round_idx if self.seed else None
            rng = np.random.default_rng(seed)

            buyer_valuations = rng.uniform(5, 15, self.num_buyers)
            seller_costs = rng.uniform(2, 12, self.num_sellers)

            # Test subset of agents
            agents_to_test = min(n_agents // n_rounds + 1, self.num_buyers + self.num_sellers)

            for i in range(agents_to_test):
                is_buyer = i < self.num_buyers // 2

                if is_buyer:
                    agent_idx = i % self.num_buyers
                    true_val = buyer_valuations[agent_idx]
                    other_bids = np.delete(buyer_valuations, agent_idx)
                    other_asks = seller_costs.copy()
                else:
                    agent_idx = (i - self.num_buyers // 2) % self.num_sellers
                    true_val = seller_costs[agent_idx]
                    other_bids = buyer_valuations.copy()
                    other_asks = np.delete(seller_costs, agent_idx)

                result = self.test_single_agent(
                    agent_idx=agent_idx,
                    is_buyer=is_buyer,
                    true_valuation=true_val,
                    other_buyer_bids=other_bids,
                    other_seller_asks=other_asks,
                    deviations=deviations,
                )
                agent_results.append(result)

        # Aggregate results
        total_tests = len(self.deviation_results)
        profitable_deviations = [r for r in self.deviation_results if r.is_profitable]
        success_count = len(profitable_deviations)
        success_rate = success_count / total_tests if total_tests > 0 else 0

        # Calculate deviation gains
        gains = [r.utility_difference for r in profitable_deviations]
        mean_gain = float(np.mean(gains)) if gains else 0.0
        max_gain = float(np.max(gains)) if gains else 0.0

        # Exact binomial test
        # H0: deviation success rate >= 0.5 (deviating is profitable)
        # H1: deviation success rate < 0.5 (truthful is better)
        # We want to reject H0 to show IC
        if total_tests > 0:
            # One-tailed binomial test
            p_value = scipy_stats.binom.cdf(success_count, total_tests, 0.5)
        else:
            p_value = 1.0

        # IC if success rate is low and we can reject H0
        is_ic = success_rate < 0.1 and p_value < alpha

        return ICTestResult(
            is_incentive_compatible=is_ic,
            deviation_success_count=success_count,
            total_tests=total_tests,
            deviation_success_rate=success_rate,
            binomial_p_value=p_value,
            mean_deviation_gain=mean_gain,
            max_deviation_gain=max_gain,
            agent_results=agent_results,
        )


def simulate_ic_test(
    num_buyers: int = 20,
    num_sellers: int = 20,
    n_rounds: int = 30,
    seed: Optional[int] = None,
) -> ICTestResult:
    """
    Run a simulated IC test.

    Args:
        num_buyers: Number of buyers
        num_sellers: Number of sellers
        n_rounds: Number of test rounds
        seed: Random seed

    Returns:
        ICTestResult
    """
    tester = IncentiveCompatibilityTester(
        num_buyers=num_buyers,
        num_sellers=num_sellers,
        seed=seed,
    )

    return tester.run_comprehensive_test(
        n_agents=num_buyers + num_sellers,
        n_rounds=n_rounds,
    )
