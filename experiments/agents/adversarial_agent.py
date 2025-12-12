"""
Adversarial Agent - Strategic manipulator implementing attack strategies.

Implements various market manipulation strategies for testing
market resilience and detection mechanisms.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

import numpy as np

from .base_agent import AgentState, BaseAgent, Bid, MarketState, TradeSide


class AttackStrategy(Enum):
    """Types of market manipulation attacks."""
    SPOOFING = "spoofing"
    WASH_TRADING = "wash_trading"
    QUOTE_STUFFING = "quote_stuffing"
    PRICE_MANIPULATION = "price_manipulation"
    LAYERING = "layering"


@dataclass
class ManipulationState:
    """State tracking for manipulation attacks."""
    phase: str = "passive"
    accumulated_position: float = 0.0
    target_price: Optional[float] = None
    fake_orders: list = field(default_factory=list)
    wash_trades: list = field(default_factory=list)


class AdversarialAgent(BaseAgent):
    """
    Adversarial agent implementing market manipulation strategies.

    Strategies:
    - Spoofing: Place and cancel large orders to move price
    - Wash trading: Self-trading to create false volume
    - Quote stuffing: High-frequency order submission
    - Price manipulation: Strategic position building and dumping
    - Layering: Multiple orders at different prices
    """

    def __init__(
        self,
        state: AgentState,
        strategy: str = "spoofing",
        detection_evasion: bool = True,
        manipulation_budget: float = 1000.0,
        target_price_deviation: float = 0.1,
    ):
        """
        Initialize the adversarial agent.

        Args:
            state: Agent state
            strategy: Primary attack strategy
            detection_evasion: Whether to vary behavior to avoid detection
            manipulation_budget: Token budget for manipulation
            target_price_deviation: Target price change (fraction)
        """
        super().__init__(state)
        self.state.type = "adversarial"

        self.strategy = AttackStrategy(strategy) if isinstance(strategy, str) else strategy
        self.detection_evasion = detection_evasion
        self.manipulation_budget = manipulation_budget
        self.target_price_deviation = target_price_deviation

        # Attack state
        self.attack_state = ManipulationState()
        self.orders_placed = 0
        self.orders_cancelled = 0
        self.profit_from_manipulation = 0.0

        # Strategy-specific parameters
        self._init_strategy_params()

    def _init_strategy_params(self) -> None:
        """Initialize strategy-specific parameters."""
        if self.strategy == AttackStrategy.SPOOFING:
            self.fake_order_multiplier = 5.0
            self.cancel_probability = 0.95
            self.cancel_delay = 0

        elif self.strategy == AttackStrategy.WASH_TRADING:
            self.wash_frequency = 0.3
            self.volume_inflation = 2.0
            self.max_price_deviation = 0.005

        elif self.strategy == AttackStrategy.QUOTE_STUFFING:
            self.orders_per_round = 10
            self.order_lifetime = 1

        elif self.strategy == AttackStrategy.PRICE_MANIPULATION:
            self.accumulation_periods = 10
            self.manipulation_periods = 5
            self.periods_in_phase = 0

        elif self.strategy == AttackStrategy.LAYERING:
            self.num_layers = 5
            self.layer_decay = 0.7
            self.price_increment = 0.005

    def generate_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Generate bid based on current attack strategy.

        Returns:
            (price, quantity, side) tuple or None
        """
        if self.strategy == AttackStrategy.SPOOFING:
            return self._spoofing_bid(market_state)
        elif self.strategy == AttackStrategy.WASH_TRADING:
            return self._wash_trading_bid(market_state)
        elif self.strategy == AttackStrategy.QUOTE_STUFFING:
            return self._quote_stuffing_bid(market_state)
        elif self.strategy == AttackStrategy.PRICE_MANIPULATION:
            return self._price_manipulation_bid(market_state)
        elif self.strategy == AttackStrategy.LAYERING:
            return self._layering_bid(market_state)
        else:
            return None

    def _spoofing_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Spoofing: Place large fake orders to move price, then trade.

        Phase 1: Place large fake order on one side
        Phase 2: Trade on the opposite side
        Phase 3: Cancel fake order
        """
        if market_state.clearing_price is None:
            return None

        current_price = market_state.clearing_price

        if self.attack_state.phase == "passive":
            # Start spoofing - decide direction
            if np.random.random() < 0.5:
                # Want to buy cheap - place fake sell orders
                self.attack_state.phase = "fake_sell"
                self.attack_state.target_price = current_price * (1 - self.target_price_deviation)
            else:
                # Want to sell high - place fake buy orders
                self.attack_state.phase = "fake_buy"
                self.attack_state.target_price = current_price * (1 + self.target_price_deviation)

        if self.attack_state.phase == "fake_sell":
            # Place large fake sell order to push price down
            fake_quantity = min(
                self.state.available_energy_kwh * self.fake_order_multiplier,
                50.0,
            )
            fake_price = current_price * 0.95

            # Mark as fake for tracking
            self.attack_state.fake_orders.append({
                "side": "sell",
                "price": fake_price,
                "quantity": fake_quantity,
            })

            # Move to real trade phase after placing fake
            self.attack_state.phase = "real_buy"
            return (round(fake_price, 2), round(fake_quantity, 2), "sell")

        elif self.attack_state.phase == "fake_buy":
            # Place large fake buy order to push price up
            fake_quantity = min(
                self.state.available_capacity_kwh * self.fake_order_multiplier,
                50.0,
            )
            fake_price = current_price * 1.05

            self.attack_state.fake_orders.append({
                "side": "buy",
                "price": fake_price,
                "quantity": fake_quantity,
            })

            self.attack_state.phase = "real_sell"
            return (round(fake_price, 2), round(fake_quantity, 2), "buy")

        elif self.attack_state.phase == "real_buy":
            # Place real buy order at depressed price
            quantity = min(self.state.available_capacity_kwh, 10.0)
            if quantity < 0.1:
                self.attack_state.phase = "passive"
                return None

            price = current_price * 0.98
            self.attack_state.phase = "passive"
            return (round(price, 2), round(quantity, 2), "buy")

        elif self.attack_state.phase == "real_sell":
            # Place real sell order at inflated price
            quantity = min(self.state.available_energy_kwh, 10.0)
            if quantity < 0.1:
                self.attack_state.phase = "passive"
                return None

            price = current_price * 1.02
            self.attack_state.phase = "passive"
            return (round(price, 2), round(quantity, 2), "sell")

        return None

    def _wash_trading_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Wash trading: Self-trade to inflate volume.

        Creates matching buy and sell orders.
        """
        if market_state.clearing_price is None:
            return None

        if np.random.random() > self.wash_frequency:
            # Normal trading when not wash trading
            return self._normal_trade(market_state)

        current_price = market_state.clearing_price

        # Generate matched orders
        quantity = np.random.uniform(1.0, 10.0)

        # Slight price variation to look natural
        noise = np.random.uniform(-self.max_price_deviation, self.max_price_deviation)
        price = current_price * (1 + noise)

        # Alternate buy/sell
        if len(self.attack_state.wash_trades) % 2 == 0:
            side = "buy"
        else:
            side = "sell"

        self.attack_state.wash_trades.append({
            "price": price,
            "quantity": quantity,
            "side": side,
        })

        return (round(price, 2), round(quantity, 2), side)

    def _quote_stuffing_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Quote stuffing: Submit many orders to slow down other participants.
        """
        if market_state.clearing_price is None:
            return None

        current_price = market_state.clearing_price

        # Generate aggressive orders across price range
        spread = market_state.spread if market_state.spread > 0 else current_price * 0.1
        price_offset = np.random.uniform(-spread / 2, spread / 2)
        price = current_price + price_offset

        # Small quantity
        quantity = np.random.uniform(0.1, 1.0)

        # Random side
        side = "buy" if np.random.random() < 0.5 else "sell"

        self.orders_placed += 1

        return (round(price, 2), round(quantity, 2), side)

    def _price_manipulation_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Price manipulation: Accumulate, pump, dump.

        Phase 1 (Accumulation): Gradually build position
        Phase 2 (Manipulation): Aggressive trading to move price
        Phase 3 (Exit): Liquidate position at profit
        """
        if market_state.clearing_price is None:
            return None

        current_price = market_state.clearing_price
        self.periods_in_phase = getattr(self, "periods_in_phase", 0) + 1

        if self.attack_state.phase == "passive":
            self.attack_state.phase = "accumulation"
            self.attack_state.target_price = current_price * (1 + self.target_price_deviation)
            self.periods_in_phase = 0

        if self.attack_state.phase == "accumulation":
            if self.periods_in_phase > self.accumulation_periods:
                self.attack_state.phase = "manipulation"
                self.periods_in_phase = 0
                return None

            # Accumulate slowly
            quantity = min(self.state.available_capacity_kwh * 0.2, 5.0)
            if quantity < 0.1:
                return None

            # Bid slightly below market to avoid detection
            price = current_price * 0.99
            self.attack_state.accumulated_position += quantity

            return (round(price, 2), round(quantity, 2), "buy")

        elif self.attack_state.phase == "manipulation":
            if self.periods_in_phase > self.manipulation_periods:
                self.attack_state.phase = "exit"
                self.periods_in_phase = 0
                return None

            # Aggressive buying to push price up
            quantity = min(self.manipulation_budget * 0.1, 20.0)
            price = current_price * 1.05  # Aggressive bid

            return (round(price, 2), round(quantity, 2), "buy")

        elif self.attack_state.phase == "exit":
            # Sell accumulated position
            quantity = min(self.attack_state.accumulated_position * 0.3, 10.0)
            if quantity < 0.1:
                self.attack_state.phase = "passive"
                self.attack_state.accumulated_position = 0
                return None

            price = current_price * 1.02
            self.attack_state.accumulated_position -= quantity

            return (round(price, 2), round(quantity, 2), "sell")

        return None

    def _layering_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Layering: Multiple orders at different price levels.

        Creates false impression of market depth.
        """
        if market_state.clearing_price is None:
            return None

        current_price = market_state.clearing_price

        # Choose side for layering
        side = "buy" if np.random.random() < 0.5 else "sell"

        # Choose layer
        layer = np.random.randint(0, self.num_layers)
        price_offset = (layer + 1) * self.price_increment

        if side == "buy":
            price = current_price * (1 - price_offset)
            quantity = 10.0 * (self.layer_decay ** layer)
        else:
            price = current_price * (1 + price_offset)
            quantity = 10.0 * (self.layer_decay ** layer)

        # Add jitter for detection evasion
        if self.detection_evasion:
            price *= (1 + np.random.uniform(-0.002, 0.002))
            quantity *= np.random.uniform(0.9, 1.1)

        return (round(price, 2), round(max(0.1, quantity), 2), side)

    def _normal_trade(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """Execute a normal trade to blend in."""
        side = self.decide_side(market_state)
        if side is None:
            return None

        quantity = self.determine_quantity(side, market_state)
        if quantity < 0.1:
            return None

        price = market_state.clearing_price
        if price is None:
            return None

        if side == TradeSide.BUY:
            price = price * 0.99
        else:
            price = price * 1.01

        return (round(price, 2), round(quantity, 2), side.value)

    def should_cancel_order(self, order: dict) -> bool:
        """Determine if a fake order should be cancelled."""
        if self.strategy == AttackStrategy.SPOOFING:
            return np.random.random() < self.cancel_probability
        return False

    def update_after_trade(self, trade_result: dict) -> None:
        """Update state after trade."""
        self.record_trade(trade_result)

        # Track manipulation profits
        if trade_result.get("is_manipulation_trade", False):
            self.profit_from_manipulation += trade_result.get("profit", 0)

    def get_manipulation_stats(self) -> dict:
        """Get statistics about manipulation activity."""
        return {
            "strategy": self.strategy.value,
            "phase": self.attack_state.phase,
            "accumulated_position": self.attack_state.accumulated_position,
            "fake_orders_placed": len(self.attack_state.fake_orders),
            "wash_trades": len(self.attack_state.wash_trades),
            "orders_placed": self.orders_placed,
            "orders_cancelled": self.orders_cancelled,
            "manipulation_profit": self.profit_from_manipulation,
        }
