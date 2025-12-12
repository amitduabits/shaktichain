"""
Manipulation Simulator for SHAKTI-CHAIN Agent Behavior (Domain 5).

Tests hypothesis H5.4: Manipulation gain < 5%.
Simulates various market manipulation strategies and measures their effectiveness.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class ManipulationStrategy(Enum):
    """Types of market manipulation strategies."""
    SPOOFING = "spoofing"
    WASH_TRADING = "wash_trading"
    QUOTE_STUFFING = "quote_stuffing"
    PRICE_MANIPULATION = "price_manipulation"
    FRONT_RUNNING = "front_running"
    LAYERING = "layering"


@dataclass
class Order:
    """A market order."""
    order_id: str
    agent_id: str
    price: float
    quantity: float
    side: str  # 'buy' or 'sell'
    timestamp: float
    is_fake: bool = False  # For spoofing/layering detection

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "agent_id": self.agent_id,
            "price": float(self.price),
            "quantity": float(self.quantity),
            "side": self.side,
            "timestamp": float(self.timestamp),
            "is_fake": self.is_fake,
        }


@dataclass
class ManipulationResult:
    """
    Result of a manipulation attack simulation.

    Attributes:
        strategy: The manipulation strategy used
        profit_honest: Profit if trading honestly
        profit_attack: Profit using manipulation
        manipulation_gain: Relative gain from manipulation
        market_impact: Change in welfare for other participants
        detection_risk: Estimated probability of detection
        orders_placed: Number of orders placed
        orders_cancelled: Number of orders cancelled
        success_rate: Rate of successful manipulations
    """
    strategy: ManipulationStrategy
    profit_honest: float
    profit_attack: float
    manipulation_gain: float
    market_impact: float
    detection_risk: float
    orders_placed: int
    orders_cancelled: int
    success_rate: float
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy.value,
            "profit_honest": float(self.profit_honest),
            "profit_attack": float(self.profit_attack),
            "manipulation_gain": float(self.manipulation_gain),
            "market_impact": float(self.market_impact),
            "detection_risk": float(self.detection_risk),
            "orders_placed": self.orders_placed,
            "orders_cancelled": self.orders_cancelled,
            "success_rate": float(self.success_rate),
            "additional_info": self.additional_info,
        }


@dataclass
class ManipulationTestResult:
    """
    Result of manipulation resistance test.

    Attributes:
        is_resistant: Whether market is resistant (max gain < threshold)
        max_manipulation_gain: Maximum gain observed
        mean_manipulation_gain: Mean gain across strategies
        gain_threshold: Threshold used
        t_statistic: One-sample t-test statistic
        p_value: P-value
        results_by_strategy: Results for each strategy tested
    """
    is_resistant: bool
    max_manipulation_gain: float
    mean_manipulation_gain: float
    gain_threshold: float
    t_statistic: float
    p_value: float
    results_by_strategy: Dict[str, ManipulationResult]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_resistant": self.is_resistant,
            "max_manipulation_gain": float(self.max_manipulation_gain),
            "mean_manipulation_gain": float(self.mean_manipulation_gain),
            "gain_threshold": float(self.gain_threshold),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "strategies_tested": list(self.results_by_strategy.keys()),
        }


class ManipulationAttack(ABC):
    """Abstract base class for manipulation attacks."""

    def __init__(self, attacker_id: str = "manipulator"):
        """Initialize attack."""
        self.attacker_id = attacker_id
        self.orders_placed = 0
        self.orders_cancelled = 0

    @abstractmethod
    def execute(
        self,
        market_state: Dict[str, Any],
        rng: np.random.Generator,
    ) -> List[Order]:
        """
        Execute the manipulation attack.

        Args:
            market_state: Current market state
            rng: Random number generator

        Returns:
            List of orders to submit
        """
        pass

    @abstractmethod
    def get_strategy(self) -> ManipulationStrategy:
        """Get the strategy type."""
        pass


class SpoofingAttack(ManipulationAttack):
    """
    Spoofing attack: Place large fake orders to move price, then cancel.

    Strategy:
    1. Place large buy orders above market to push price up
    2. Wait for price to move
    3. Cancel orders
    4. Sell at inflated price
    """

    def __init__(
        self,
        attacker_id: str = "spoofer",
        order_size_multiplier: float = 5.0,
        cancel_delay_rounds: int = 1,
    ):
        """
        Initialize spoofing attack.

        Args:
            attacker_id: Attacker ID
            order_size_multiplier: How much larger than normal orders
            cancel_delay_rounds: Rounds before cancellation
        """
        super().__init__(attacker_id)
        self.order_size_multiplier = order_size_multiplier
        self.cancel_delay_rounds = cancel_delay_rounds
        self.fake_orders: List[Order] = []

    def execute(
        self,
        market_state: Dict[str, Any],
        rng: np.random.Generator,
    ) -> List[Order]:
        """Execute spoofing attack."""
        current_price = market_state.get("clearing_price", 10.0)
        avg_order_size = market_state.get("avg_order_size", 5.0)

        orders = []

        # Phase 1: Place large fake buy orders to push price up
        fake_buy_price = current_price * 1.1  # 10% above market
        fake_buy_size = avg_order_size * self.order_size_multiplier

        fake_order = Order(
            order_id=f"spoof_{rng.integers(10000)}",
            agent_id=self.attacker_id,
            price=fake_buy_price,
            quantity=fake_buy_size,
            side="buy",
            timestamp=market_state.get("timestamp", 0.0),
            is_fake=True,
        )
        orders.append(fake_order)
        self.fake_orders.append(fake_order)
        self.orders_placed += 1

        # Phase 2: Place real sell order at slightly higher price
        real_sell_price = current_price * 1.05
        real_sell_size = avg_order_size

        real_order = Order(
            order_id=f"real_{rng.integers(10000)}",
            agent_id=self.attacker_id,
            price=real_sell_price,
            quantity=real_sell_size,
            side="sell",
            timestamp=market_state.get("timestamp", 0.0) + 0.001,
            is_fake=False,
        )
        orders.append(real_order)
        self.orders_placed += 1

        return orders

    def cancel_fake_orders(self) -> int:
        """Cancel all fake orders."""
        cancelled = len(self.fake_orders)
        self.orders_cancelled += cancelled
        self.fake_orders = []
        return cancelled

    def get_strategy(self) -> ManipulationStrategy:
        return ManipulationStrategy.SPOOFING


class WashTradingAttack(ManipulationAttack):
    """
    Wash trading: Trade with self to create false volume signals.

    Strategy:
    1. Submit matching buy and sell orders
    2. Trade with self
    3. Create impression of high activity
    """

    def __init__(
        self,
        attacker_id: str = "wash_trader",
        trade_size: float = 10.0,
    ):
        """
        Initialize wash trading attack.

        Args:
            attacker_id: Attacker ID
            trade_size: Size of wash trades
        """
        super().__init__(attacker_id)
        self.trade_size = trade_size

    def execute(
        self,
        market_state: Dict[str, Any],
        rng: np.random.Generator,
    ) -> List[Order]:
        """Execute wash trading attack."""
        current_price = market_state.get("clearing_price", 10.0)
        timestamp = market_state.get("timestamp", 0.0)

        orders = []

        # Submit matching buy and sell at same price
        order_id = rng.integers(10000)

        buy_order = Order(
            order_id=f"wash_buy_{order_id}",
            agent_id=self.attacker_id,
            price=current_price,
            quantity=self.trade_size,
            side="buy",
            timestamp=timestamp,
            is_fake=False,  # These are real orders, just self-dealing
        )
        orders.append(buy_order)
        self.orders_placed += 1

        sell_order = Order(
            order_id=f"wash_sell_{order_id}",
            agent_id=self.attacker_id,
            price=current_price,
            quantity=self.trade_size,
            side="sell",
            timestamp=timestamp + 0.001,
            is_fake=False,
        )
        orders.append(sell_order)
        self.orders_placed += 1

        return orders

    def get_strategy(self) -> ManipulationStrategy:
        return ManipulationStrategy.WASH_TRADING


class PriceManipulationAttack(ManipulationAttack):
    """
    Price manipulation: Use market power to move prices.

    Strategy:
    1. Accumulate large position in one direction
    2. Use position to influence clearing price
    3. Profit from price movement
    """

    def __init__(
        self,
        attacker_id: str = "price_manipulator",
        position_size: float = 50.0,
        target_price_change: float = 0.10,  # 10% price change
    ):
        """
        Initialize price manipulation attack.

        Args:
            attacker_id: Attacker ID
            position_size: Size of manipulative position
            target_price_change: Target price movement
        """
        super().__init__(attacker_id)
        self.position_size = position_size
        self.target_price_change = target_price_change

    def execute(
        self,
        market_state: Dict[str, Any],
        rng: np.random.Generator,
    ) -> List[Order]:
        """Execute price manipulation attack."""
        current_price = market_state.get("clearing_price", 10.0)
        timestamp = market_state.get("timestamp", 0.0)

        orders = []

        # Large aggressive buy to push price up
        aggressive_price = current_price * (1 + self.target_price_change)

        order = Order(
            order_id=f"manip_{rng.integers(10000)}",
            agent_id=self.attacker_id,
            price=aggressive_price,
            quantity=self.position_size,
            side="buy",
            timestamp=timestamp,
            is_fake=False,
        )
        orders.append(order)
        self.orders_placed += 1

        return orders

    def get_strategy(self) -> ManipulationStrategy:
        return ManipulationStrategy.PRICE_MANIPULATION


class ManipulationSimulator:
    """
    Simulate market manipulation attacks and measure their effectiveness.

    Tests H5.4: Manipulation gain < 5%.
    """

    def __init__(
        self,
        num_honest_agents: int = 20,
        attack_budget: float = 100.0,
        seed: Optional[int] = None,
    ):
        """
        Initialize manipulation simulator.

        Args:
            num_honest_agents: Number of honest market participants
            attack_budget: Budget available for attacks
            seed: Random seed
        """
        self.num_honest_agents = num_honest_agents
        self.attack_budget = attack_budget
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def simulate_attack(
        self,
        strategy: ManipulationStrategy,
        attack_duration_rounds: int = 10,
        n_simulations: int = 50,
    ) -> ManipulationResult:
        """
        Run market with adversarial agent using given strategy.

        Args:
            strategy: Manipulation strategy to test
            attack_duration_rounds: Duration of attack
            n_simulations: Number of simulations

        Returns:
            ManipulationResult with profit comparisons
        """
        attack_class = self._get_attack_class(strategy)
        if attack_class is None:
            logger.warning(f"Unknown strategy: {strategy}")
            return self._empty_result(strategy)

        honest_profits = []
        attack_profits = []
        market_impacts = []
        success_count = 0
        total_orders_placed = 0
        total_orders_cancelled = 0

        for sim in range(n_simulations):
            sim_seed = self.seed + sim if self.seed else None
            rng = np.random.default_rng(sim_seed)

            # Run honest baseline
            honest_profit, baseline_welfare = self._run_honest_market(
                attack_duration_rounds, rng
            )
            honest_profits.append(honest_profit)

            # Run with manipulation
            attack = attack_class()
            attack_profit, attack_welfare, orders_placed, orders_cancelled = \
                self._run_attack_market(attack, attack_duration_rounds, rng)

            attack_profits.append(attack_profit)
            market_impacts.append(baseline_welfare - attack_welfare)
            total_orders_placed += orders_placed
            total_orders_cancelled += orders_cancelled

            if attack_profit > honest_profit:
                success_count += 1

        # Calculate statistics
        mean_honest = float(np.mean(honest_profits))
        mean_attack = float(np.mean(attack_profits))

        if mean_honest > 0:
            manipulation_gain = (mean_attack - mean_honest) / mean_honest
        else:
            manipulation_gain = 0.0 if mean_attack <= 0 else float('inf')

        # Detection risk (simplified model)
        detection_risk = self._estimate_detection_risk(strategy, total_orders_cancelled / max(1, total_orders_placed))

        return ManipulationResult(
            strategy=strategy,
            profit_honest=mean_honest,
            profit_attack=mean_attack,
            manipulation_gain=float(manipulation_gain),
            market_impact=float(np.mean(market_impacts)),
            detection_risk=detection_risk,
            orders_placed=total_orders_placed,
            orders_cancelled=total_orders_cancelled,
            success_rate=success_count / n_simulations,
            additional_info={
                "n_simulations": n_simulations,
                "attack_duration": attack_duration_rounds,
                "profit_std_honest": float(np.std(honest_profits)),
                "profit_std_attack": float(np.std(attack_profits)),
            },
        )

    def _get_attack_class(self, strategy: ManipulationStrategy):
        """Get attack class for strategy."""
        mapping = {
            ManipulationStrategy.SPOOFING: SpoofingAttack,
            ManipulationStrategy.WASH_TRADING: WashTradingAttack,
            ManipulationStrategy.PRICE_MANIPULATION: PriceManipulationAttack,
        }
        return mapping.get(strategy)

    def _run_honest_market(
        self,
        num_rounds: int,
        rng: np.random.Generator,
    ) -> Tuple[float, float]:
        """
        Run market with honest participation.

        Returns:
            (attacker_profit_if_honest, total_welfare)
        """
        n_buyers = self.num_honest_agents // 2
        n_sellers = self.num_honest_agents - n_buyers

        buyer_valuations = rng.uniform(5, 15, n_buyers)
        seller_costs = rng.uniform(2, 12, n_sellers)

        total_profit = 0.0
        total_welfare = 0.0

        # Attacker acts as honest buyer
        attacker_valuation = 10.0

        for round_idx in range(num_rounds):
            # Generate bids
            buyer_bids = buyer_valuations * rng.uniform(0.9, 1.0, n_buyers)
            seller_asks = seller_costs * rng.uniform(1.0, 1.1, n_sellers)

            attacker_bid = attacker_valuation * 0.95

            # Run auction
            all_bids = np.append(buyer_bids, attacker_bid)
            all_asks = seller_asks

            clearing_price, matches = self._run_auction(all_bids, all_asks)

            # Calculate welfare
            for b, s in matches:
                if b < n_buyers:
                    buyer_val = buyer_valuations[b]
                else:
                    buyer_val = attacker_valuation
                seller_cost = seller_costs[s]
                welfare = buyer_val - seller_cost
                total_welfare += welfare

                # Check if attacker matched
                if b == n_buyers:  # Attacker is last buyer
                    profit = attacker_valuation - clearing_price
                    total_profit += profit

        return total_profit, total_welfare

    def _run_attack_market(
        self,
        attack: ManipulationAttack,
        num_rounds: int,
        rng: np.random.Generator,
    ) -> Tuple[float, float, int, int]:
        """
        Run market with manipulation attack.

        Returns:
            (attacker_profit, total_welfare, orders_placed, orders_cancelled)
        """
        n_buyers = self.num_honest_agents // 2
        n_sellers = self.num_honest_agents - n_buyers

        buyer_valuations = rng.uniform(5, 15, n_buyers)
        seller_costs = rng.uniform(2, 12, n_sellers)

        total_profit = 0.0
        total_welfare = 0.0
        orders_placed = 0
        orders_cancelled = 0

        for round_idx in range(num_rounds):
            # Generate honest bids
            buyer_bids = buyer_valuations * rng.uniform(0.9, 1.0, n_buyers)
            seller_asks = seller_costs * rng.uniform(1.0, 1.1, n_sellers)

            # Get market state
            clearing_price_est = np.median(np.concatenate([buyer_bids, seller_asks]))
            market_state = {
                "clearing_price": clearing_price_est,
                "avg_order_size": 5.0,
                "timestamp": float(round_idx),
            }

            # Execute attack
            attack_orders = attack.execute(market_state, rng)
            orders_placed += len(attack_orders)

            # Add attack orders to market
            for order in attack_orders:
                if order.side == "buy" and not order.is_fake:
                    buyer_bids = np.append(buyer_bids, order.price)
                elif order.side == "sell" and not order.is_fake:
                    seller_asks = np.append(seller_asks, order.price)

            # Run auction
            clearing_price, matches = self._run_auction(buyer_bids, seller_asks)

            # Cancel fake orders (for spoofing)
            if hasattr(attack, 'cancel_fake_orders'):
                cancelled = attack.cancel_fake_orders()
                orders_cancelled += cancelled

            # Calculate attacker profit (simplified)
            # Attacker profits from any price movement they cause
            expected_price = np.median(np.concatenate([
                buyer_valuations * 0.95,
                seller_costs * 1.05
            ]))

            for order in attack_orders:
                if not order.is_fake:
                    if order.side == "sell":
                        profit = clearing_price - expected_price
                    else:
                        profit = expected_price - clearing_price
                    total_profit += profit * order.quantity * 0.1  # Scaled

            # Calculate welfare
            n_honest_buyers = n_buyers
            for i, (b, s) in enumerate(matches):
                if b < n_honest_buyers and s < n_sellers:
                    buyer_val = buyer_valuations[b]
                    seller_cost = seller_costs[s]
                    welfare = buyer_val - seller_cost
                    total_welfare += welfare

        return total_profit, total_welfare, orders_placed, orders_cancelled

    def _run_auction(
        self,
        buyer_bids: np.ndarray,
        seller_asks: np.ndarray,
    ) -> Tuple[float, List[Tuple[int, int]]]:
        """Run simple double auction."""
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
            # Uniform price at midpoint of marginal match
            last_buyer = matches[-1][0]
            last_seller = matches[-1][1]
            clearing_price = (buyer_bids[last_buyer] + seller_asks[last_seller]) / 2
        else:
            clearing_price = np.mean(np.concatenate([buyer_bids, seller_asks]))

        return clearing_price, matches

    def _estimate_detection_risk(
        self,
        strategy: ManipulationStrategy,
        cancel_rate: float,
    ) -> float:
        """Estimate detection risk for strategy."""
        base_risk = {
            ManipulationStrategy.SPOOFING: 0.7,
            ManipulationStrategy.WASH_TRADING: 0.8,
            ManipulationStrategy.QUOTE_STUFFING: 0.6,
            ManipulationStrategy.PRICE_MANIPULATION: 0.5,
            ManipulationStrategy.FRONT_RUNNING: 0.4,
            ManipulationStrategy.LAYERING: 0.7,
        }.get(strategy, 0.5)

        # High cancel rate increases detection risk
        if cancel_rate > 0.5:
            base_risk = min(1.0, base_risk + 0.2)

        return base_risk

    def _empty_result(self, strategy: ManipulationStrategy) -> ManipulationResult:
        """Return empty result for unknown strategy."""
        return ManipulationResult(
            strategy=strategy,
            profit_honest=0.0,
            profit_attack=0.0,
            manipulation_gain=0.0,
            market_impact=0.0,
            detection_risk=0.0,
            orders_placed=0,
            orders_cancelled=0,
            success_rate=0.0,
        )

    def test_all_strategies(
        self,
        attack_duration_rounds: int = 10,
        n_simulations: int = 30,
    ) -> Dict[str, ManipulationResult]:
        """
        Test all manipulation strategies.

        Args:
            attack_duration_rounds: Duration of each attack
            n_simulations: Number of simulations per strategy

        Returns:
            Dictionary mapping strategy name to result
        """
        results = {}

        for strategy in [
            ManipulationStrategy.SPOOFING,
            ManipulationStrategy.WASH_TRADING,
            ManipulationStrategy.PRICE_MANIPULATION,
        ]:
            result = self.simulate_attack(
                strategy=strategy,
                attack_duration_rounds=attack_duration_rounds,
                n_simulations=n_simulations,
            )
            results[strategy.value] = result

        return results

    def test_manipulation_resistance(
        self,
        gain_threshold: float = 0.05,
        n_simulations: int = 50,
        alpha: float = 0.05,
    ) -> ManipulationTestResult:
        """
        Test if market is resistant to manipulation.

        Tests H5.4: Manipulation gain < 5%.

        Args:
            gain_threshold: Maximum acceptable manipulation gain
            n_simulations: Number of simulations
            alpha: Significance level

        Returns:
            ManipulationTestResult
        """
        results = self.test_all_strategies(n_simulations=n_simulations)

        gains = [r.manipulation_gain for r in results.values()]
        mean_gain = float(np.mean(gains))
        max_gain = float(np.max(gains))

        # One-sample t-test: H0: mean gain >= threshold
        gains_arr = np.array(gains)
        if len(gains_arr) > 1 and np.std(gains_arr) > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(gains_arr, gain_threshold)
            # One-tailed test
            p_value = p_value / 2 if t_stat < 0 else 1 - p_value / 2
        else:
            t_stat = 0.0
            p_value = 0.5

        is_resistant = max_gain < gain_threshold

        return ManipulationTestResult(
            is_resistant=is_resistant,
            max_manipulation_gain=max_gain,
            mean_manipulation_gain=mean_gain,
            gain_threshold=gain_threshold,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            results_by_strategy=results,
        )


def simulate_manipulation_test(
    num_agents: int = 20,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> ManipulationTestResult:
    """
    Run a simulated manipulation resistance test.

    Args:
        num_agents: Number of honest agents
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        ManipulationTestResult
    """
    simulator = ManipulationSimulator(
        num_honest_agents=num_agents,
        attack_budget=100.0,
        seed=seed,
    )

    return simulator.test_manipulation_resistance(
        gain_threshold=0.05,
        n_simulations=n_simulations,
    )
