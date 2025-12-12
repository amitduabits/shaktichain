"""
Sybil Attack Tester for SHAKTI-CHAIN Agent Behavior (Domain 5).

Tests hypothesis H5.5: Utility with n identities <= utility with 1 identity.
Uses regression slope test to determine if Sybil attacks are profitable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class SybilTestPoint:
    """
    Result for a single identity count test.

    Attributes:
        num_identities: Number of identities used
        wealth_per_identity: Wealth allocated to each identity
        total_utility: Total utility across all identities
        trades_per_identity: Average trades per identity
        success_rate: Fraction of identities that traded successfully
    """
    num_identities: int
    wealth_per_identity: float
    total_utility: float
    trades_per_identity: float
    success_rate: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "num_identities": self.num_identities,
            "wealth_per_identity": float(self.wealth_per_identity),
            "total_utility": float(self.total_utility),
            "trades_per_identity": float(self.trades_per_identity),
            "success_rate": float(self.success_rate),
        }


@dataclass
class SybilTestResult:
    """
    Result of Sybil attack profitability test.

    Attributes:
        sybil_profitable: Whether Sybil attack is profitable
        regression_slope: Slope of utility vs number of identities
        slope_std_error: Standard error of slope
        slope_p_value: P-value for slope significance
        r_squared: R-squared of regression
        intercept: Regression intercept
        test_points: Individual test results
        utility_single_identity: Utility with single identity
        utility_max_identities: Utility with maximum identities tested
    """
    sybil_profitable: bool
    regression_slope: float
    slope_std_error: float
    slope_p_value: float
    r_squared: float
    intercept: float
    test_points: List[SybilTestPoint]
    utility_single_identity: float
    utility_max_identities: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "sybil_profitable": self.sybil_profitable,
            "regression_slope": float(self.regression_slope),
            "slope_std_error": float(self.slope_std_error),
            "slope_p_value": float(self.slope_p_value),
            "r_squared": float(self.r_squared),
            "intercept": float(self.intercept),
            "utility_single_identity": float(self.utility_single_identity),
            "utility_max_identities": float(self.utility_max_identities),
            "num_test_points": len(self.test_points),
        }


@dataclass
class ComprehensiveSybilResult:
    """
    Comprehensive Sybil resistance test result.

    Attributes:
        is_resistant: Whether system resists Sybil attacks
        mean_slope: Mean slope across multiple tests
        slope_std: Standard deviation of slopes
        positive_slope_fraction: Fraction of tests with positive slope
        t_statistic: T-statistic for slope test
        p_value: P-value
        individual_tests: Results from individual test runs
    """
    is_resistant: bool
    mean_slope: float
    slope_std: float
    positive_slope_fraction: float
    t_statistic: float
    p_value: float
    individual_tests: List[SybilTestResult]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_resistant": self.is_resistant,
            "mean_slope": float(self.mean_slope),
            "slope_std": float(self.slope_std),
            "positive_slope_fraction": float(self.positive_slope_fraction),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "num_tests": len(self.individual_tests),
        }


class MarketSimulatorForSybil:
    """
    Simplified market simulator for Sybil testing.

    Implements a continuous double auction where agents can participate
    with varying wealth levels.
    """

    def __init__(
        self,
        num_other_agents: int = 20,
        seed: Optional[int] = None,
    ):
        """
        Initialize market simulator.

        Args:
            num_other_agents: Number of non-Sybil agents
            seed: Random seed
        """
        self.num_other_agents = num_other_agents
        self.rng = np.random.default_rng(seed)

        # Generate other agents' characteristics
        self.other_valuations = self.rng.uniform(5, 15, num_other_agents // 2)
        self.other_costs = self.rng.uniform(2, 12, num_other_agents - num_other_agents // 2)

    def run_with_sybil_identities(
        self,
        num_identities: int,
        total_wealth: float,
        num_rounds: int = 20,
    ) -> Tuple[float, int, int]:
        """
        Run market with agent split into multiple identities.

        Args:
            num_identities: Number of Sybil identities
            total_wealth: Total wealth to distribute
            num_rounds: Number of trading rounds

        Returns:
            (total_utility, total_trades, successful_identities)
        """
        wealth_per_identity = total_wealth / num_identities

        total_utility = 0.0
        total_trades = 0
        successful_identities = 0

        for round_idx in range(num_rounds):
            # Generate other agents' bids
            n_buyers = len(self.other_valuations)
            n_sellers = len(self.other_costs)

            buyer_bids = self.other_valuations * self.rng.uniform(0.9, 1.0, n_buyers)
            seller_asks = self.other_costs * self.rng.uniform(1.0, 1.1, n_sellers)

            # Sybil identities bid based on their wealth
            # Higher wealth = can afford more aggressive bids
            sybil_bids = []
            sybil_valuations = []

            for i in range(num_identities):
                # Each identity has limited wealth, which limits bid aggressiveness
                max_bid = min(wealth_per_identity, 12.0)  # Can't bid more than wealth
                valuation = self.rng.uniform(8, 12)  # True valuation
                bid = min(valuation * 0.95, max_bid)

                sybil_bids.append(bid)
                sybil_valuations.append(valuation)

            # Run auction
            all_bids = np.concatenate([buyer_bids, sybil_bids])
            all_valuations = np.concatenate([self.other_valuations, sybil_valuations])

            clearing_price, matches = self._run_auction(all_bids, seller_asks)

            # Calculate utility for Sybil identities
            identities_that_traded = set()
            for b, s in matches:
                if b >= n_buyers:  # Sybil identity
                    identity_idx = b - n_buyers
                    buyer_valuation = sybil_valuations[identity_idx]
                    utility = buyer_valuation - clearing_price
                    total_utility += utility
                    total_trades += 1
                    identities_that_traded.add(identity_idx)

            successful_identities = max(successful_identities, len(identities_that_traded))

        return total_utility, total_trades, successful_identities

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


class SybilTester:
    """
    Test if creating multiple identities is profitable.

    Agent with true wealth W can split into n identities with W/n each.
    Tests if total utility with n > utility with 1.
    """

    def __init__(
        self,
        num_other_agents: int = 20,
        seed: Optional[int] = None,
    ):
        """
        Initialize Sybil tester.

        Args:
            num_other_agents: Number of non-Sybil agents
            seed: Random seed
        """
        self.num_other_agents = num_other_agents
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def test_sybil_profitability(
        self,
        original_wealth: float = 100.0,
        identity_counts: List[int] = None,
        num_rounds: int = 20,
        n_simulations: int = 10,
    ) -> SybilTestResult:
        """
        Test utility as function of number of identities.

        Args:
            original_wealth: Total wealth to distribute
            identity_counts: List of identity counts to test
            num_rounds: Rounds per simulation
            n_simulations: Simulations per identity count

        Returns:
            SybilTestResult with regression analysis
        """
        if identity_counts is None:
            identity_counts = [1, 2, 5, 10, 20]

        test_points = []
        utilities_by_n = {}

        for n in identity_counts:
            wealth_per_identity = original_wealth / n
            utilities = []
            trades = []
            successes = []

            for sim in range(n_simulations):
                sim_seed = self.seed + sim * 1000 + n if self.seed else None
                market = MarketSimulatorForSybil(
                    num_other_agents=self.num_other_agents,
                    seed=sim_seed,
                )

                utility, num_trades, successful = market.run_with_sybil_identities(
                    num_identities=n,
                    total_wealth=original_wealth,
                    num_rounds=num_rounds,
                )

                utilities.append(utility)
                trades.append(num_trades / max(1, n))
                successes.append(successful / n)

            mean_utility = float(np.mean(utilities))
            mean_trades = float(np.mean(trades))
            mean_success = float(np.mean(successes))

            utilities_by_n[n] = utilities

            test_points.append(SybilTestPoint(
                num_identities=n,
                wealth_per_identity=wealth_per_identity,
                total_utility=mean_utility,
                trades_per_identity=mean_trades,
                success_rate=mean_success,
            ))

        # Regression analysis: utility vs n
        n_values = np.array([p.num_identities for p in test_points])
        utility_values = np.array([p.total_utility for p in test_points])

        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(
            n_values, utility_values
        )

        r_squared = r_value ** 2

        # Sybil is profitable if slope > 0 significantly
        sybil_profitable = slope > 0 and p_value < 0.05

        return SybilTestResult(
            sybil_profitable=sybil_profitable,
            regression_slope=float(slope),
            slope_std_error=float(std_err),
            slope_p_value=float(p_value),
            r_squared=float(r_squared),
            intercept=float(intercept),
            test_points=test_points,
            utility_single_identity=test_points[0].total_utility if test_points else 0.0,
            utility_max_identities=test_points[-1].total_utility if test_points else 0.0,
        )

    def run_comprehensive_test(
        self,
        wealth_levels: List[float] = None,
        n_tests: int = 20,
        alpha: float = 0.05,
    ) -> ComprehensiveSybilResult:
        """
        Run comprehensive Sybil resistance test.

        Tests H5.5 across multiple wealth levels.

        Args:
            wealth_levels: Wealth levels to test
            n_tests: Number of test runs
            alpha: Significance level

        Returns:
            ComprehensiveSybilResult
        """
        if wealth_levels is None:
            wealth_levels = [50.0, 100.0, 200.0]

        individual_tests = []
        all_slopes = []

        for test_idx in range(n_tests):
            for wealth in wealth_levels:
                test_seed = self.seed + test_idx * 100 if self.seed else None

                tester = SybilTester(
                    num_other_agents=self.num_other_agents,
                    seed=test_seed,
                )

                result = tester.test_sybil_profitability(
                    original_wealth=wealth,
                    n_simulations=5,
                )

                individual_tests.append(result)
                all_slopes.append(result.regression_slope)

        # Aggregate analysis
        slopes_arr = np.array(all_slopes)
        mean_slope = float(np.mean(slopes_arr))
        slope_std = float(np.std(slopes_arr))
        positive_fraction = float(np.mean(slopes_arr > 0))

        # T-test: is mean slope > 0?
        if len(slopes_arr) > 1 and np.std(slopes_arr) > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(slopes_arr, 0)
            # One-tailed test for positive slope
            p_value = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        else:
            t_stat = 0.0
            p_value = 0.5

        # Resistant if slope is not significantly positive
        is_resistant = mean_slope <= 0 or p_value > alpha

        return ComprehensiveSybilResult(
            is_resistant=is_resistant,
            mean_slope=mean_slope,
            slope_std=slope_std,
            positive_slope_fraction=positive_fraction,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            individual_tests=individual_tests,
        )


def simulate_sybil_test(
    original_wealth: float = 100.0,
    num_other_agents: int = 20,
    seed: Optional[int] = None,
) -> SybilTestResult:
    """
    Run a simulated Sybil attack test.

    Args:
        original_wealth: Total wealth
        num_other_agents: Number of other agents
        seed: Random seed

    Returns:
        SybilTestResult
    """
    tester = SybilTester(
        num_other_agents=num_other_agents,
        seed=seed,
    )

    return tester.test_sybil_profitability(
        original_wealth=original_wealth,
    )


def simulate_comprehensive_sybil_test(
    n_tests: int = 10,
    seed: Optional[int] = None,
) -> ComprehensiveSybilResult:
    """
    Run comprehensive Sybil resistance test.

    Args:
        n_tests: Number of tests
        seed: Random seed

    Returns:
        ComprehensiveSybilResult
    """
    tester = SybilTester(seed=seed)

    return tester.run_comprehensive_test(n_tests=n_tests)
