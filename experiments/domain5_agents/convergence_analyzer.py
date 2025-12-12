"""
Convergence Analyzer for SHAKTI-CHAIN Agent Behavior (Domain 5).

Tests hypothesis H5.2: Prices converge within 50 rounds.
Tests hypothesis H5.3: Efficiency >= 85% with 50% bounded rational agents.
Uses Augmented Dickey-Fuller test for stationarity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

# Try to import statsmodels for ADF test
try:
    from statsmodels.tsa.stattools import adfuller
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    logger.warning("statsmodels not available; using simplified convergence test")


@dataclass
class ConvergenceTestResult:
    """
    Result of price convergence test.

    Attributes:
        converged: Whether price series converged
        convergence_round: First round where stationarity detected
        adf_statistic: Augmented Dickey-Fuller test statistic
        adf_p_value: P-value for stationarity
        critical_values: Critical values at different significance levels
        final_price: Price at end of series
        equilibrium_price: Theoretical equilibrium price
        price_deviation: Final deviation from equilibrium
    """
    converged: bool
    convergence_round: Optional[int]
    adf_statistic: float
    adf_p_value: float
    critical_values: Dict[str, float]
    final_price: float
    equilibrium_price: float
    price_deviation: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "converged": self.converged,
            "convergence_round": self.convergence_round,
            "adf_statistic": float(self.adf_statistic),
            "adf_p_value": float(self.adf_p_value),
            "critical_values": self.critical_values,
            "final_price": float(self.final_price),
            "equilibrium_price": float(self.equilibrium_price),
            "price_deviation": float(self.price_deviation),
        }


@dataclass
class EfficiencyResult:
    """
    Result of efficiency analysis under different agent compositions.

    Attributes:
        rational_fraction: Fraction of rational agents
        bounded_rational_fraction: Fraction of bounded rational agents
        zero_intelligence_fraction: Fraction of ZI agents
        achieved_efficiency: Actual market efficiency
        total_welfare: Actual total welfare
        maximum_welfare: Walrasian maximum welfare
        num_trades: Number of trades executed
        converged: Whether prices converged
        convergence_round: Round at which convergence occurred
    """
    rational_fraction: float
    bounded_rational_fraction: float
    zero_intelligence_fraction: float
    achieved_efficiency: float
    total_welfare: float
    maximum_welfare: float
    num_trades: int
    converged: bool
    convergence_round: Optional[int]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "rational_fraction": float(self.rational_fraction),
            "bounded_rational_fraction": float(self.bounded_rational_fraction),
            "zero_intelligence_fraction": float(self.zero_intelligence_fraction),
            "achieved_efficiency": float(self.achieved_efficiency),
            "total_welfare": float(self.total_welfare),
            "maximum_welfare": float(self.maximum_welfare),
            "num_trades": self.num_trades,
            "converged": self.converged,
            "convergence_round": self.convergence_round,
        }


@dataclass
class RobustnessTestResult:
    """
    Result of robustness to bounded rationality test.

    Attributes:
        is_robust: Whether efficiency >= threshold with mixed agents
        efficiency_with_rational: Efficiency with all rational agents
        efficiency_with_mixed: Efficiency with mixed agents
        efficiency_threshold: Threshold used
        t_statistic: Two-sample t-test statistic
        p_value: P-value
        effect_size: Cohen's d effect size
        efficiency_by_composition: Efficiencies at different compositions
    """
    is_robust: bool
    efficiency_with_rational: float
    efficiency_with_mixed: float
    efficiency_threshold: float
    t_statistic: float
    p_value: float
    effect_size: float
    efficiency_by_composition: List[EfficiencyResult]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_robust": self.is_robust,
            "efficiency_with_rational": float(self.efficiency_with_rational),
            "efficiency_with_mixed": float(self.efficiency_with_mixed),
            "efficiency_threshold": float(self.efficiency_threshold),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "effect_size": float(self.effect_size),
            "num_compositions_tested": len(self.efficiency_by_composition),
        }


class ConvergenceAnalyzer:
    """
    Analyze market price convergence and efficiency.

    Tests H5.2 (convergence within 50 rounds) using ADF test.
    Tests H5.3 (robustness to bounded rationality) using two-sample t-test.
    """

    def __init__(self, equilibrium_price: Optional[float] = None):
        """
        Initialize convergence analyzer.

        Args:
            equilibrium_price: Theoretical equilibrium price (if known)
        """
        self.equilibrium_price = equilibrium_price
        self.price_series: List[float] = []
        self.efficiency_series: List[float] = []
        self.round_data: List[Dict[str, Any]] = []

    def add_observation(
        self,
        price: float,
        efficiency: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add a price observation.

        Args:
            price: Observed clearing price
            efficiency: Market efficiency for this round
            metadata: Additional round data
        """
        self.price_series.append(price)
        if efficiency is not None:
            self.efficiency_series.append(efficiency)
        if metadata is not None:
            self.round_data.append(metadata)

    def test_convergence(
        self,
        max_rounds: int = 50,
        significance: float = 0.05,
        min_observations: int = 10,
    ) -> ConvergenceTestResult:
        """
        Test if price series has converged using ADF test.

        Convergence = rejection of unit root = stationarity.

        Args:
            max_rounds: Maximum rounds to check
            significance: Significance level for ADF test
            min_observations: Minimum observations for test

        Returns:
            ConvergenceTestResult
        """
        if len(self.price_series) < min_observations:
            return ConvergenceTestResult(
                converged=False,
                convergence_round=None,
                adf_statistic=0.0,
                adf_p_value=1.0,
                critical_values={},
                final_price=self.price_series[-1] if self.price_series else 0.0,
                equilibrium_price=self.equilibrium_price or 0.0,
                price_deviation=0.0,
            )

        prices = np.array(self.price_series)
        convergence_round = None
        final_adf_result = None

        # Check for convergence at each window
        check_points = range(min_observations, min(len(prices) + 1, max_rounds + 1), 5)

        for round_num in check_points:
            window = prices[:round_num]

            if HAS_STATSMODELS:
                try:
                    result = adfuller(window, autolag='AIC')
                    adf_stat = result[0]
                    p_value = result[1]
                    critical_values = result[4]
                    final_adf_result = result
                except Exception as e:
                    logger.warning(f"ADF test failed: {e}")
                    continue
            else:
                # Simplified test: check if variance is decreasing
                adf_stat, p_value = self._simplified_stationarity_test(window)
                critical_values = {"5%": -2.86}
                final_adf_result = (adf_stat, p_value, None, None, critical_values)

            if p_value < significance:
                convergence_round = round_num
                break

        # Final result
        if final_adf_result is not None:
            adf_statistic = final_adf_result[0]
            adf_p_value = final_adf_result[1]
            crit_vals = final_adf_result[4] if len(final_adf_result) > 4 else {}
        else:
            adf_statistic = 0.0
            adf_p_value = 1.0
            crit_vals = {}

        final_price = prices[-1] if len(prices) > 0 else 0.0
        eq_price = self.equilibrium_price or np.mean(prices[-10:])
        deviation = abs(final_price - eq_price) / eq_price if eq_price > 0 else 0.0

        return ConvergenceTestResult(
            converged=convergence_round is not None,
            convergence_round=convergence_round,
            adf_statistic=float(adf_statistic),
            adf_p_value=float(adf_p_value),
            critical_values={k: float(v) for k, v in crit_vals.items()} if crit_vals else {},
            final_price=float(final_price),
            equilibrium_price=float(eq_price),
            price_deviation=float(deviation),
        )

    def _simplified_stationarity_test(
        self,
        series: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Simplified stationarity test when statsmodels unavailable.

        Uses variance ratio and trend tests.
        """
        n = len(series)
        if n < 10:
            return 0.0, 1.0

        # Split series into halves
        half = n // 2
        first_half = series[:half]
        second_half = series[half:]

        # Variance ratio test
        var1 = np.var(first_half)
        var2 = np.var(second_half)

        if var1 > 0:
            var_ratio = var2 / var1
        else:
            var_ratio = 1.0

        # Trend test (regression slope)
        x = np.arange(n)
        slope, _, r_value, p_trend, _ = scipy_stats.linregress(x, series)

        # Combined statistic
        # Lower var_ratio and lower abs(slope) suggests stationarity
        statistic = -np.log(var_ratio + 0.001) - abs(slope) * 10

        # Approximate p-value based on statistic magnitude
        if statistic > 2:
            p_value = 0.01
        elif statistic > 1:
            p_value = 0.05
        elif statistic > 0:
            p_value = 0.10
        else:
            p_value = 0.50

        return statistic, p_value

    def test_robustness(
        self,
        efficiency_threshold: float = 0.85,
        bounded_rational_fraction: float = 0.50,
        n_simulations: int = 30,
        alpha: float = 0.05,
    ) -> RobustnessTestResult:
        """
        Test robustness to bounded rationality.

        Tests H5.3: Efficiency >= 85% with 50% bounded rational agents.

        Args:
            efficiency_threshold: Required minimum efficiency
            bounded_rational_fraction: Fraction of bounded rational agents
            n_simulations: Number of simulations to run
            alpha: Significance level

        Returns:
            RobustnessTestResult
        """
        # Simulate markets with different agent compositions
        efficiencies_rational = []
        efficiencies_mixed = []
        all_results = []

        rng = np.random.default_rng(42)

        for sim in range(n_simulations):
            # All rational agents
            eff_rational = self._simulate_market_efficiency(
                rational_fraction=1.0,
                bounded_rational_fraction=0.0,
                rng=rng,
            )
            efficiencies_rational.append(eff_rational.achieved_efficiency)

            # Mixed agents (50% bounded rational)
            eff_mixed = self._simulate_market_efficiency(
                rational_fraction=1.0 - bounded_rational_fraction,
                bounded_rational_fraction=bounded_rational_fraction,
                rng=rng,
            )
            efficiencies_mixed.append(eff_mixed.achieved_efficiency)
            all_results.append(eff_mixed)

        # Two-sample t-test
        eff_rational_arr = np.array(efficiencies_rational)
        eff_mixed_arr = np.array(efficiencies_mixed)

        t_stat, p_value = scipy_stats.ttest_ind(eff_rational_arr, eff_mixed_arr)

        # Effect size (Cohen's d)
        pooled_std = np.sqrt(
            (np.std(eff_rational_arr, ddof=1) ** 2 + np.std(eff_mixed_arr, ddof=1) ** 2) / 2
        )
        effect_size = (np.mean(eff_rational_arr) - np.mean(eff_mixed_arr)) / pooled_std if pooled_std > 0 else 0

        mean_mixed_efficiency = float(np.mean(eff_mixed_arr))
        is_robust = mean_mixed_efficiency >= efficiency_threshold

        return RobustnessTestResult(
            is_robust=is_robust,
            efficiency_with_rational=float(np.mean(eff_rational_arr)),
            efficiency_with_mixed=mean_mixed_efficiency,
            efficiency_threshold=efficiency_threshold,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            effect_size=float(effect_size),
            efficiency_by_composition=all_results,
        )

    def _simulate_market_efficiency(
        self,
        rational_fraction: float,
        bounded_rational_fraction: float,
        num_agents: int = 20,
        num_rounds: int = 50,
        rng: Optional[np.random.Generator] = None,
    ) -> EfficiencyResult:
        """
        Simulate market and calculate efficiency.

        Args:
            rational_fraction: Fraction of rational agents
            bounded_rational_fraction: Fraction of bounded rational agents
            num_agents: Total number of agents
            num_rounds: Number of trading rounds
            rng: Random number generator

        Returns:
            EfficiencyResult
        """
        if rng is None:
            rng = np.random.default_rng()

        # Generate agent valuations
        n_buyers = num_agents // 2
        n_sellers = num_agents - n_buyers

        buyer_valuations = rng.uniform(5, 15, n_buyers)
        seller_costs = rng.uniform(2, 12, n_sellers)

        # Calculate maximum welfare (Walrasian)
        sorted_buyers = np.sort(buyer_valuations)[::-1]
        sorted_sellers = np.sort(seller_costs)

        max_welfare = 0.0
        optimal_trades = 0
        for i in range(min(n_buyers, n_sellers)):
            if sorted_buyers[i] >= sorted_sellers[i]:
                max_welfare += sorted_buyers[i] - sorted_sellers[i]
                optimal_trades += 1
            else:
                break

        # Simulate trading with mixed agent types
        # Rational agents bid truthfully, bounded rational add noise
        noise_level = 0.2  # 20% noise for bounded rational

        prices = []
        total_welfare = 0.0
        num_trades = 0

        for round_idx in range(num_rounds):
            # Generate bids
            buyer_bids = []
            for i, val in enumerate(buyer_valuations):
                agent_type = self._get_agent_type(i, n_buyers, rational_fraction, bounded_rational_fraction, rng)
                if agent_type == "rational":
                    bid = val * 0.95  # Slight shading
                elif agent_type == "bounded_rational":
                    bid = val * (1 + rng.uniform(-noise_level, noise_level))
                else:  # zero intelligence
                    bid = rng.uniform(0, val * 1.5)
                buyer_bids.append(bid)

            seller_asks = []
            for i, cost in enumerate(seller_costs):
                agent_type = self._get_agent_type(i, n_sellers, rational_fraction, bounded_rational_fraction, rng)
                if agent_type == "rational":
                    ask = cost * 1.05  # Slight markup
                elif agent_type == "bounded_rational":
                    ask = cost * (1 + rng.uniform(-noise_level, noise_level))
                else:  # zero intelligence
                    ask = rng.uniform(cost * 0.5, 20)
                seller_asks.append(ask)

            # Run auction
            buyer_bids = np.array(buyer_bids)
            seller_asks = np.array(seller_asks)

            # Match orders
            buyer_order = np.argsort(buyer_bids)[::-1]
            seller_order = np.argsort(seller_asks)

            round_trades = 0
            round_welfare = 0.0

            b_idx = 0
            s_idx = 0
            while b_idx < len(buyer_order) and s_idx < len(seller_order):
                buyer = buyer_order[b_idx]
                seller = seller_order[s_idx]

                if buyer_bids[buyer] >= seller_asks[seller]:
                    price = (buyer_bids[buyer] + seller_asks[seller]) / 2
                    welfare = buyer_valuations[buyer] - seller_costs[seller]
                    round_welfare += welfare
                    round_trades += 1
                    prices.append(price)
                    b_idx += 1
                    s_idx += 1
                else:
                    break

            total_welfare += round_welfare
            num_trades += round_trades

        # Average efficiency
        if max_welfare > 0 and num_rounds > 0:
            avg_efficiency = (total_welfare / num_rounds) / max_welfare
        else:
            avg_efficiency = 0.0

        # Check convergence
        self.price_series = prices
        conv_result = self.test_convergence()

        return EfficiencyResult(
            rational_fraction=rational_fraction,
            bounded_rational_fraction=bounded_rational_fraction,
            zero_intelligence_fraction=1.0 - rational_fraction - bounded_rational_fraction,
            achieved_efficiency=float(avg_efficiency),
            total_welfare=float(total_welfare),
            maximum_welfare=float(max_welfare * num_rounds),
            num_trades=num_trades,
            converged=conv_result.converged,
            convergence_round=conv_result.convergence_round,
        )

    def _get_agent_type(
        self,
        agent_idx: int,
        num_agents: int,
        rational_fraction: float,
        bounded_rational_fraction: float,
        rng: np.random.Generator,
    ) -> str:
        """Determine agent type based on fractions."""
        r = rng.random()
        if r < rational_fraction:
            return "rational"
        elif r < rational_fraction + bounded_rational_fraction:
            return "bounded_rational"
        else:
            return "zero_intelligence"

    def get_price_series(self) -> np.ndarray:
        """Get price series as numpy array."""
        return np.array(self.price_series)

    def get_statistics(self) -> Dict[str, float]:
        """Get price series statistics."""
        if not self.price_series:
            return {}

        prices = np.array(self.price_series)
        return {
            "mean_price": float(np.mean(prices)),
            "std_price": float(np.std(prices)),
            "min_price": float(np.min(prices)),
            "max_price": float(np.max(prices)),
            "final_price": float(prices[-1]),
            "price_range": float(np.max(prices) - np.min(prices)),
            "num_observations": len(prices),
        }

    def clear(self):
        """Clear all data."""
        self.price_series = []
        self.efficiency_series = []
        self.round_data = []


def simulate_convergence_test(
    num_agents: int = 20,
    num_rounds: int = 50,
    seed: Optional[int] = None,
) -> ConvergenceTestResult:
    """
    Run a simulated convergence test.

    Args:
        num_agents: Number of agents
        num_rounds: Number of rounds
        seed: Random seed

    Returns:
        ConvergenceTestResult
    """
    rng = np.random.default_rng(seed)

    # Generate equilibrium price
    equilibrium_price = 8.0

    # Simulate price series converging to equilibrium
    analyzer = ConvergenceAnalyzer(equilibrium_price=equilibrium_price)

    initial_price = rng.uniform(5, 12)
    current_price = initial_price

    for round_idx in range(num_rounds):
        # Price converges toward equilibrium with noise
        convergence_rate = 0.1
        noise = rng.normal(0, 0.5)
        current_price = current_price + convergence_rate * (equilibrium_price - current_price) + noise
        current_price = max(1, current_price)  # Price floor

        analyzer.add_observation(current_price)

    return analyzer.test_convergence(max_rounds=num_rounds)


def simulate_robustness_test(
    bounded_rational_fraction: float = 0.5,
    efficiency_threshold: float = 0.85,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> RobustnessTestResult:
    """
    Run a simulated robustness test.

    Args:
        bounded_rational_fraction: Fraction of bounded rational agents
        efficiency_threshold: Required efficiency threshold
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        RobustnessTestResult
    """
    analyzer = ConvergenceAnalyzer()

    return analyzer.test_robustness(
        efficiency_threshold=efficiency_threshold,
        bounded_rational_fraction=bounded_rational_fraction,
        n_simulations=n_simulations,
    )
