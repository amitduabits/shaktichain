"""
Continuous Double Auction (CDA) Baseline.

Standard CDA as used in stock exchanges with immediate order matching.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

import numpy as np


class OrderType(Enum):
    """Types of orders."""
    LIMIT = "limit"
    MARKET = "market"
    IOC = "immediate_or_cancel"
    FOK = "fill_or_kill"


@dataclass
class CDAOrder:
    """An order in the CDA."""
    order_id: str
    agent_id: str
    agent_type: str
    price: float
    quantity: float
    remaining_quantity: float
    side: str  # "buy" or "sell"
    order_type: OrderType
    timestamp: float = 0.0
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "price": self.price,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "side": self.side,
            "order_type": self.order_type.value,
            "timestamp": self.timestamp,
            "is_active": self.is_active,
        }


@dataclass
class CDATrade:
    """A trade executed in the CDA."""
    trade_id: str
    buyer_order_id: str
    seller_order_id: str
    buyer_id: str
    seller_id: str
    buyer_type: str
    seller_type: str
    price: float
    quantity: float
    aggressor_side: str  # The incoming order that caused the trade
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "buyer_order_id": self.buyer_order_id,
            "seller_order_id": self.seller_order_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "buyer_type": self.buyer_type,
            "seller_type": self.seller_type,
            "price": self.price,
            "quantity": self.quantity,
            "aggressor_side": self.aggressor_side,
            "timestamp": self.timestamp,
        }


class OrderBook:
    """Order book with price-time priority."""

    def __init__(self, side: str):
        """
        Initialize order book.

        Args:
            side: "bid" or "ask"
        """
        self.side = side
        self.orders: dict[float, deque[CDAOrder]] = {}
        self._order_lookup: dict[str, CDAOrder] = {}

    def add_order(self, order: CDAOrder) -> None:
        """Add an order to the book."""
        price = order.price

        if price not in self.orders:
            self.orders[price] = deque()

        self.orders[price].append(order)
        self._order_lookup[order.order_id] = order

    def remove_order(self, order_id: str) -> Optional[CDAOrder]:
        """Remove an order from the book."""
        if order_id not in self._order_lookup:
            return None

        order = self._order_lookup[order_id]
        order.is_active = False

        if order.price in self.orders:
            try:
                self.orders[order.price].remove(order)
                if not self.orders[order.price]:
                    del self.orders[order.price]
            except ValueError:
                pass

        del self._order_lookup[order_id]
        return order

    def get_best_price(self) -> Optional[float]:
        """Get the best price in the book."""
        if not self.orders:
            return None

        if self.side == "bid":
            return max(self.orders.keys())
        else:
            return min(self.orders.keys())

    def get_orders_at_price(self, price: float) -> list[CDAOrder]:
        """Get all orders at a specific price level."""
        if price not in self.orders:
            return []
        return list(self.orders[price])

    def get_depth(self, levels: int = 10) -> list[tuple[float, float]]:
        """
        Get order book depth.

        Returns:
            List of (price, total_quantity) tuples
        """
        if not self.orders:
            return []

        prices = sorted(
            self.orders.keys(),
            reverse=(self.side == "bid"),
        )[:levels]

        return [
            (price, sum(o.remaining_quantity for o in self.orders[price]))
            for price in prices
        ]

    def get_total_volume(self) -> float:
        """Get total volume in the book."""
        return sum(
            sum(o.remaining_quantity for o in orders)
            for orders in self.orders.values()
        )

    def __len__(self) -> int:
        return len(self._order_lookup)


class ContinuousDoubleAuction:
    """
    Continuous Double Auction mechanism.

    Matches orders immediately upon arrival using price-time priority.
    """

    def __init__(
        self,
        tick_size: float = 0.01,
        execution_price_rule: Literal["aggressor", "passive", "midpoint"] = "passive",
    ):
        """
        Initialize the CDA.

        Args:
            tick_size: Minimum price increment
            execution_price_rule: How to determine trade price
                - "aggressor": Use incoming order's price
                - "passive": Use resting order's price (standard)
                - "midpoint": Average of both
        """
        self.tick_size = tick_size
        self.execution_price_rule = execution_price_rule

        # Order books
        self.bids = OrderBook("bid")
        self.asks = OrderBook("ask")

        # Trade history
        self.trades: list[CDATrade] = []
        self.trade_prices: list[float] = []

        # Counters
        self._order_counter = 0
        self._trade_counter = 0

        # Statistics
        self._total_buy_volume = 0.0
        self._total_sell_volume = 0.0

    def submit_order(
        self,
        agent_id: str,
        agent_type: str,
        price: float,
        quantity: float,
        side: str,
        order_type: str = "limit",
        timestamp: float = 0.0,
    ) -> tuple[str, list[CDATrade]]:
        """
        Submit an order and execute any matches.

        Args:
            agent_id: ID of the agent
            agent_type: Type of agent
            price: Limit price (ignored for market orders)
            quantity: Order quantity
            side: "buy" or "sell"
            order_type: Order type
            timestamp: Order timestamp

        Returns:
            Tuple of (order_id, list of executed trades)
        """
        self._order_counter += 1
        order_id = f"order_{self._order_counter}"

        order_type_enum = OrderType(order_type)

        # Round price to tick
        price = round(price / self.tick_size) * self.tick_size

        order = CDAOrder(
            order_id=order_id,
            agent_id=agent_id,
            agent_type=agent_type,
            price=price,
            quantity=quantity,
            remaining_quantity=quantity,
            side=side,
            order_type=order_type_enum,
            timestamp=timestamp,
        )

        # Try to match
        trades = self._match_order(order)

        # Handle remaining quantity based on order type
        if order.remaining_quantity > 0 and order.is_active:
            if order_type_enum == OrderType.LIMIT:
                # Add to order book
                if side == "buy":
                    self.bids.add_order(order)
                else:
                    self.asks.add_order(order)
            elif order_type_enum in (OrderType.IOC, OrderType.MARKET):
                # Cancel remaining
                order.is_active = False
            elif order_type_enum == OrderType.FOK:
                # If not fully filled, cancel all trades
                if order.remaining_quantity > 0:
                    order.is_active = False
                    trades = []

        return order_id, trades

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: ID of the order to cancel

        Returns:
            True if cancelled, False if not found
        """
        order = self.bids.remove_order(order_id)
        if order is not None:
            return True

        order = self.asks.remove_order(order_id)
        return order is not None

    def _match_order(self, incoming: CDAOrder) -> list[CDATrade]:
        """Match an incoming order against the order book."""
        trades = []

        if incoming.side == "buy":
            opposite_book = self.asks
        else:
            opposite_book = self.bids

        while incoming.remaining_quantity > 0 and incoming.is_active:
            best_price = opposite_book.get_best_price()

            if best_price is None:
                break

            # Check if prices cross
            if incoming.side == "buy":
                if incoming.price < best_price and incoming.order_type != OrderType.MARKET:
                    break  # No match possible
            else:
                if incoming.price > best_price and incoming.order_type != OrderType.MARKET:
                    break  # No match possible

            # Match with orders at best price
            resting_orders = opposite_book.get_orders_at_price(best_price)

            for resting in resting_orders:
                if incoming.remaining_quantity <= 0:
                    break

                if not resting.is_active:
                    continue

                # Determine match quantity
                match_qty = min(incoming.remaining_quantity, resting.remaining_quantity)

                # Determine execution price
                exec_price = self._determine_execution_price(incoming, resting)

                # Create trade
                self._trade_counter += 1

                if incoming.side == "buy":
                    trade = CDATrade(
                        trade_id=f"trade_{self._trade_counter}",
                        buyer_order_id=incoming.order_id,
                        seller_order_id=resting.order_id,
                        buyer_id=incoming.agent_id,
                        seller_id=resting.agent_id,
                        buyer_type=incoming.agent_type,
                        seller_type=resting.agent_type,
                        price=exec_price,
                        quantity=match_qty,
                        aggressor_side="buy",
                        timestamp=incoming.timestamp,
                    )
                    self._total_buy_volume += match_qty
                else:
                    trade = CDATrade(
                        trade_id=f"trade_{self._trade_counter}",
                        buyer_order_id=resting.order_id,
                        seller_order_id=incoming.order_id,
                        buyer_id=resting.agent_id,
                        seller_id=incoming.agent_id,
                        buyer_type=resting.agent_type,
                        seller_type=incoming.agent_type,
                        price=exec_price,
                        quantity=match_qty,
                        aggressor_side="sell",
                        timestamp=incoming.timestamp,
                    )
                    self._total_sell_volume += match_qty

                trades.append(trade)
                self.trades.append(trade)
                self.trade_prices.append(exec_price)

                # Update quantities
                incoming.remaining_quantity -= match_qty
                resting.remaining_quantity -= match_qty

                # Remove fully filled resting order
                if resting.remaining_quantity <= 0:
                    resting.is_active = False
                    opposite_book.remove_order(resting.order_id)

        return trades

    def _determine_execution_price(
        self,
        incoming: CDAOrder,
        resting: CDAOrder,
    ) -> float:
        """Determine execution price for a match."""
        if self.execution_price_rule == "passive":
            return resting.price
        elif self.execution_price_rule == "aggressor":
            return incoming.price
        else:  # midpoint
            return (incoming.price + resting.price) / 2

    def get_market_stats(self) -> dict:
        """Get current market statistics."""
        best_bid = self.bids.get_best_price()
        best_ask = self.asks.get_best_price()

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": best_ask - best_bid if best_bid and best_ask else None,
            "mid_price": (best_bid + best_ask) / 2 if best_bid and best_ask else None,
            "bid_depth": self.bids.get_total_volume(),
            "ask_depth": self.asks.get_total_volume(),
            "num_bids": len(self.bids),
            "num_asks": len(self.asks),
            "total_trades": len(self.trades),
            "last_price": self.trade_prices[-1] if self.trade_prices else None,
            "avg_price": np.mean(self.trade_prices) if self.trade_prices else None,
        }

    def get_order_book_snapshot(self, levels: int = 10) -> dict:
        """Get order book snapshot."""
        return {
            "bids": self.bids.get_depth(levels),
            "asks": self.asks.get_depth(levels),
            "timestamp": len(self.trades),
        }

    def get_trades_since(self, trade_id: int) -> list[CDATrade]:
        """Get trades since a specific trade ID."""
        return [t for t in self.trades if int(t.trade_id.split("_")[1]) > trade_id]

    def calculate_vwap(self, window: Optional[int] = None) -> float:
        """Calculate volume-weighted average price."""
        trades = self.trades[-window:] if window else self.trades

        if not trades:
            return 0.0

        total_value = sum(t.price * t.quantity for t in trades)
        total_volume = sum(t.quantity for t in trades)

        return total_value / total_volume if total_volume > 0 else 0.0

    def reset(self) -> None:
        """Reset the auction state."""
        self.bids = OrderBook("bid")
        self.asks = OrderBook("ask")
        self.trades = []
        self.trade_prices = []
        self._order_counter = 0
        self._trade_counter = 0
        self._total_buy_volume = 0.0
        self._total_sell_volume = 0.0

    @property
    def is_budget_balanced(self) -> bool:
        """CDA is budget balanced: buyer pays what seller receives."""
        return True

    @property
    def is_individually_rational(self) -> bool:
        """CDA is IR with limit orders."""
        return True

    @property
    def is_incentive_compatible(self) -> bool:
        """CDA is NOT incentive compatible."""
        return False
