"""
Base Agent - Abstract base class for all SHAKTI-CHAIN trading agents.

Provides common functionality and interfaces for agent implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple
import uuid


class TradeSide(Enum):
    """Side of a trade."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    trade_id: str
    period: int
    side: TradeSide
    price: float
    quantity: float
    counterparty_id: str
    profit: float
    timestamp: float


@dataclass
class AgentState:
    """
    State of a trading agent.

    Attributes:
        id: Unique agent identifier
        type: Agent type (rational, bounded_rational, etc.)
        battery_capacity_kwh: Total battery capacity
        current_soc: Current state of charge [0, 1]
        min_soc: Minimum acceptable SoC
        max_soc: Maximum acceptable SoC
        cost_per_kwh: Cost of energy for the agent (marginal cost for sellers)
        value_per_kwh: Value of energy for the agent (willingness to pay for buyers)
        risk_aversion: Risk aversion coefficient (higher = more risk averse)
        historical_trades: List of past trades
        cumulative_profit: Total profit across all trades
    """
    id: str
    type: str
    battery_capacity_kwh: float
    current_soc: float
    min_soc: float = 0.2
    max_soc: float = 0.9
    cost_per_kwh: float = 4.0  # INR
    value_per_kwh: float = 8.0  # INR
    risk_aversion: float = 1.0
    historical_trades: list[TradeRecord] = field(default_factory=list)
    cumulative_profit: float = 0.0

    # Additional state
    token_balance: float = 0.0
    pending_orders: list = field(default_factory=list)
    is_active: bool = True

    @property
    def available_capacity_kwh(self) -> float:
        """Capacity available for charging (buying)."""
        return self.battery_capacity_kwh * (self.max_soc - self.current_soc)

    @property
    def available_energy_kwh(self) -> float:
        """Energy available for discharging (selling)."""
        return self.battery_capacity_kwh * (self.current_soc - self.min_soc)

    def can_buy(self, quantity: float) -> bool:
        """Check if agent can buy the specified quantity."""
        return quantity <= self.available_capacity_kwh

    def can_sell(self, quantity: float) -> bool:
        """Check if agent can sell the specified quantity."""
        return quantity <= self.available_energy_kwh

    def update_soc(self, quantity: float, side: TradeSide) -> None:
        """Update SoC after a trade."""
        if side == TradeSide.BUY:
            self.current_soc += quantity / self.battery_capacity_kwh
        else:
            self.current_soc -= quantity / self.battery_capacity_kwh

        # Clamp to valid range
        self.current_soc = max(0.0, min(1.0, self.current_soc))

    def to_dict(self) -> dict:
        """Convert state to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "battery_capacity_kwh": self.battery_capacity_kwh,
            "current_soc": self.current_soc,
            "min_soc": self.min_soc,
            "max_soc": self.max_soc,
            "cost_per_kwh": self.cost_per_kwh,
            "value_per_kwh": self.value_per_kwh,
            "risk_aversion": self.risk_aversion,
            "cumulative_profit": self.cumulative_profit,
            "token_balance": self.token_balance,
            "num_trades": len(self.historical_trades),
            "is_active": self.is_active,
        }


@dataclass
class MarketState:
    """
    Current state of the market.

    Provides information agents can use for decision-making.
    """
    period: int
    current_time: float
    clearing_price: Optional[float]  # Last clearing price
    clearing_quantity: Optional[float]  # Last clearing quantity

    # Order book summary
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    bid_depth: float = 0.0
    ask_depth: float = 0.0

    # Price history
    price_history: list[float] = field(default_factory=list)
    volume_history: list[float] = field(default_factory=list)

    # Market statistics
    volatility: float = 0.0
    spread: float = 0.0
    num_participants: int = 0

    # Time-of-use context
    hour_of_day: int = 0
    is_peak_hour: bool = False
    demand_level: str = "normal"  # "low", "normal", "high"

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price if both bid and ask exist."""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return self.clearing_price

    def get_price_trend(self, periods: int = 10) -> float:
        """
        Calculate price trend over recent periods.

        Returns:
            Positive for upward trend, negative for downward
        """
        if len(self.price_history) < 2:
            return 0.0

        recent = self.price_history[-periods:]
        if len(recent) < 2:
            return 0.0

        return (recent[-1] - recent[0]) / recent[0] if recent[0] != 0 else 0.0


@dataclass
class Bid:
    """A bid/offer in the market."""
    bid_id: str
    agent_id: str
    price: float
    quantity: float
    side: TradeSide
    timestamp: float = 0.0

    def to_tuple(self) -> Tuple[float, float, str]:
        """Convert to (price, quantity, side) tuple."""
        return (self.price, self.quantity, self.side.value)


class BaseAgent(ABC):
    """
    Abstract base class for all trading agents.

    All agent implementations must inherit from this class and implement
    the abstract methods.
    """

    def __init__(self, state: AgentState):
        """
        Initialize the agent with the given state.

        Args:
            state: Initial agent state
        """
        self.state = state
        self._last_bid: Optional[Bid] = None

    @property
    def agent_id(self) -> str:
        """Get agent ID."""
        return self.state.id

    @property
    def agent_type(self) -> str:
        """Get agent type."""
        return self.state.type

    @abstractmethod
    def generate_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Generate a bid based on current market state.

        Args:
            market_state: Current market information

        Returns:
            Tuple of (price, quantity, side) where side is 'buy' or 'sell',
            or None if not bidding this period.
        """
        pass

    @abstractmethod
    def update_after_trade(self, trade_result: dict) -> None:
        """
        Update agent state after a trade is executed.

        Args:
            trade_result: Dictionary containing trade details:
                - price: Execution price
                - quantity: Traded quantity
                - side: 'buy' or 'sell'
                - counterparty_id: ID of the counterparty
                - profit: Profit from the trade
        """
        pass

    def compute_utility(
        self,
        price: float,
        quantity: float,
        side: str,
    ) -> float:
        """
        Compute utility from a potential trade.

        Args:
            price: Trade price
            quantity: Trade quantity
            side: 'buy' or 'sell'

        Returns:
            Utility value (profit/surplus)
        """
        if side == "buy":
            # Buyer surplus: value - price
            return (self.state.value_per_kwh - price) * quantity
        else:
            # Seller surplus: price - cost
            return (price - self.state.cost_per_kwh) * quantity

    def compute_risk_adjusted_utility(
        self,
        price: float,
        quantity: float,
        side: str,
        probability: float = 1.0,
    ) -> float:
        """
        Compute risk-adjusted expected utility.

        Uses CARA (Constant Absolute Risk Aversion) utility function.

        Args:
            price: Trade price
            quantity: Trade quantity
            side: 'buy' or 'sell'
            probability: Probability of trade execution

        Returns:
            Risk-adjusted utility
        """
        import numpy as np

        raw_utility = self.compute_utility(price, quantity, side)

        if self.state.risk_aversion == 0:
            return probability * raw_utility

        # CARA utility: U(x) = (1 - exp(-ρx)) / ρ
        rho = self.state.risk_aversion
        if raw_utility >= 0:
            utility = (1 - np.exp(-rho * raw_utility)) / rho
        else:
            utility = -(1 - np.exp(rho * raw_utility)) / rho

        return probability * utility

    def decide_side(self, market_state: MarketState) -> Optional[TradeSide]:
        """
        Decide whether to buy, sell, or not participate.

        Default implementation based on SoC and price expectations.

        Args:
            market_state: Current market state

        Returns:
            TradeSide.BUY, TradeSide.SELL, or None
        """
        # Check if we can trade
        can_buy = self.state.available_capacity_kwh > 0.1
        can_sell = self.state.available_energy_kwh > 0.1

        if not can_buy and not can_sell:
            return None

        # Default logic based on SoC
        soc = self.state.current_soc
        mid_soc = (self.state.min_soc + self.state.max_soc) / 2

        if soc < mid_soc - 0.1 and can_buy:
            return TradeSide.BUY
        elif soc > mid_soc + 0.1 and can_sell:
            return TradeSide.SELL
        elif can_buy and can_sell:
            # Use price as tiebreaker
            if market_state.clearing_price is not None:
                if market_state.clearing_price < self.state.value_per_kwh:
                    return TradeSide.BUY
                elif market_state.clearing_price > self.state.cost_per_kwh:
                    return TradeSide.SELL
            return None
        elif can_buy:
            return TradeSide.BUY
        else:
            return TradeSide.SELL

    def determine_quantity(
        self,
        side: TradeSide,
        market_state: MarketState,
        max_quantity: Optional[float] = None,
    ) -> float:
        """
        Determine the quantity to bid.

        Args:
            side: Buy or sell
            market_state: Current market state
            max_quantity: Maximum allowed quantity

        Returns:
            Quantity to bid
        """
        if side == TradeSide.BUY:
            available = self.state.available_capacity_kwh
        else:
            available = self.state.available_energy_kwh

        if max_quantity is not None:
            available = min(available, max_quantity)

        # Don't bid tiny amounts
        if available < 0.1:
            return 0.0

        return available

    def record_trade(
        self,
        trade_result: dict,
    ) -> None:
        """
        Record a trade in history and update state.

        Args:
            trade_result: Trade details
        """
        side = TradeSide(trade_result["side"])
        quantity = trade_result["quantity"]
        price = trade_result["price"]
        profit = trade_result.get("profit", self.compute_utility(price, quantity, side.value))

        # Create trade record
        record = TradeRecord(
            trade_id=trade_result.get("trade_id", str(uuid.uuid4())),
            period=trade_result.get("period", 0),
            side=side,
            price=price,
            quantity=quantity,
            counterparty_id=trade_result.get("counterparty_id", "unknown"),
            profit=profit,
            timestamp=trade_result.get("timestamp", 0.0),
        )

        self.state.historical_trades.append(record)
        self.state.cumulative_profit += profit
        self.state.update_soc(quantity, side)

    def get_statistics(self) -> dict:
        """
        Get trading statistics for this agent.

        Returns:
            Dictionary of statistics
        """
        trades = self.state.historical_trades
        if not trades:
            return {
                "num_trades": 0,
                "total_profit": 0.0,
                "avg_profit_per_trade": 0.0,
            }

        profits = [t.profit for t in trades]
        buy_trades = [t for t in trades if t.side == TradeSide.BUY]
        sell_trades = [t for t in trades if t.side == TradeSide.SELL]

        return {
            "num_trades": len(trades),
            "num_buys": len(buy_trades),
            "num_sells": len(sell_trades),
            "total_profit": sum(profits),
            "avg_profit_per_trade": sum(profits) / len(profits) if profits else 0,
            "total_volume_bought": sum(t.quantity for t in buy_trades),
            "total_volume_sold": sum(t.quantity for t in sell_trades),
            "avg_buy_price": (
                sum(t.price * t.quantity for t in buy_trades) /
                sum(t.quantity for t in buy_trades)
                if buy_trades else 0
            ),
            "avg_sell_price": (
                sum(t.price * t.quantity for t in sell_trades) /
                sum(t.quantity for t in sell_trades)
                if sell_trades else 0
            ),
        }

    def reset(self) -> None:
        """Reset agent state for a new run."""
        self.state.historical_trades = []
        self.state.cumulative_profit = 0.0
        self.state.pending_orders = []
        self._last_bid = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.state.id}, type={self.state.type})"
