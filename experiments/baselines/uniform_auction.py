"""
Uniform Price Auction Baseline.

Single clearing price auction where all trades execute at the same price.
Commonly used in wholesale electricity markets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

import numpy as np


class TieBreaking(Enum):
    """Tie-breaking rules for order matching."""
    PRO_RATA = "pro_rata"
    TIME_PRIORITY = "time_priority"
    RANDOM = "random"


@dataclass
class Order:
    """An order in the auction."""
    order_id: str
    agent_id: str
    agent_type: str
    price: float
    quantity: float
    side: str  # "buy" or "sell"
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side,
            "timestamp": self.timestamp,
        }


@dataclass
class Trade:
    """A matched trade."""
    trade_id: str
    buyer_id: str
    seller_id: str
    buyer_type: str
    seller_type: str
    price: float
    quantity: float
    buyer_surplus: float = 0.0
    seller_surplus: float = 0.0

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "buyer_type": self.buyer_type,
            "seller_type": self.seller_type,
            "price": self.price,
            "quantity": self.quantity,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
        }


@dataclass
class ClearingResult:
    """Result of an auction clearing."""
    clearing_price: float
    clearing_quantity: float
    trades: list[Trade]
    unmatched_bids: list[Order]
    unmatched_asks: list[Order]
    buyer_surplus: float = 0.0
    seller_surplus: float = 0.0
    efficiency: float = 0.0


class UniformPriceAuction:
    """
    Uniform price auction mechanism.

    All matched trades execute at a single clearing price.
    The clearing price is typically the midpoint of the highest
    matched bid and lowest matched ask.
    """

    def __init__(
        self,
        clearing_rule: Literal["midpoint", "buyer_price", "seller_price"] = "midpoint",
        tie_breaking: TieBreaking = TieBreaking.PRO_RATA,
    ):
        """
        Initialize the auction.

        Args:
            clearing_rule: How to determine clearing price
            tie_breaking: How to break ties at same price
        """
        self.clearing_rule = clearing_rule
        self.tie_breaking = tie_breaking

        # Order books
        self.bids: list[Order] = []
        self.asks: list[Order] = []

        # Counters
        self._order_counter = 0
        self._trade_counter = 0

    def submit_order(
        self,
        agent_id: str,
        agent_type: str,
        price: float,
        quantity: float,
        side: str,
        timestamp: float = 0.0,
    ) -> str:
        """
        Submit an order to the auction.

        Args:
            agent_id: ID of the agent
            agent_type: Type of agent
            price: Limit price
            quantity: Order quantity
            side: "buy" or "sell"
            timestamp: Order timestamp

        Returns:
            Order ID
        """
        self._order_counter += 1
        order_id = f"order_{self._order_counter}"

        order = Order(
            order_id=order_id,
            agent_id=agent_id,
            agent_type=agent_type,
            price=price,
            quantity=quantity,
            side=side,
            timestamp=timestamp,
        )

        if side == "buy":
            self.bids.append(order)
        else:
            self.asks.append(order)

        return order_id

    def clear(self) -> ClearingResult:
        """
        Clear the auction and execute matches.

        Returns:
            ClearingResult with all trades and unmatched orders
        """
        if not self.bids or not self.asks:
            return ClearingResult(
                clearing_price=0.0,
                clearing_quantity=0.0,
                trades=[],
                unmatched_bids=self.bids.copy(),
                unmatched_asks=self.asks.copy(),
            )

        # Sort bids descending by price (highest first)
        sorted_bids = sorted(self.bids, key=lambda x: (-x.price, x.timestamp))

        # Sort asks ascending by price (lowest first)
        sorted_asks = sorted(self.asks, key=lambda x: (x.price, x.timestamp))

        # Find clearing price and quantity
        clearing_price, clearing_quantity, matched_bids, matched_asks = (
            self._find_clearing_point(sorted_bids, sorted_asks)
        )

        if clearing_quantity == 0:
            return ClearingResult(
                clearing_price=0.0,
                clearing_quantity=0.0,
                trades=[],
                unmatched_bids=sorted_bids,
                unmatched_asks=sorted_asks,
            )

        # Execute trades at uniform price
        trades = self._execute_trades(
            matched_bids, matched_asks, clearing_price, clearing_quantity
        )

        # Calculate welfare
        buyer_surplus = sum(t.buyer_surplus for t in trades)
        seller_surplus = sum(t.seller_surplus for t in trades)

        # Calculate efficiency
        theoretical_max = self._calculate_theoretical_maximum(sorted_bids, sorted_asks)
        efficiency = (
            (buyer_surplus + seller_surplus) / theoretical_max
            if theoretical_max > 0 else 0
        )

        # Clear order books
        unmatched_bids = [b for b in sorted_bids if b not in matched_bids]
        unmatched_asks = [a for a in sorted_asks if a not in matched_asks]

        self.bids = []
        self.asks = []

        return ClearingResult(
            clearing_price=clearing_price,
            clearing_quantity=clearing_quantity,
            trades=trades,
            unmatched_bids=unmatched_bids,
            unmatched_asks=unmatched_asks,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            efficiency=efficiency,
        )

    def _find_clearing_point(
        self,
        bids: list[Order],
        asks: list[Order],
    ) -> tuple[float, float, list[Order], list[Order]]:
        """Find clearing price and quantity."""
        matched_bids = []
        matched_asks = []
        total_quantity = 0.0

        bid_idx = 0
        ask_idx = 0

        highest_matched_bid = None
        lowest_matched_ask = None

        while bid_idx < len(bids) and ask_idx < len(asks):
            bid = bids[bid_idx]
            ask = asks[ask_idx]

            if bid.price >= ask.price:
                # Match found
                match_quantity = min(
                    bid.quantity - sum(
                        m.quantity for m in matched_bids if m.order_id == bid.order_id
                    ),
                    ask.quantity - sum(
                        m.quantity for m in matched_asks if m.order_id == ask.order_id
                    ),
                )

                if match_quantity > 0:
                    if bid not in matched_bids:
                        matched_bids.append(bid)
                    if ask not in matched_asks:
                        matched_asks.append(ask)

                    total_quantity += match_quantity

                    highest_matched_bid = bid.price
                    lowest_matched_ask = ask.price

                # Move to next order if fully matched
                bid_filled = sum(
                    m.quantity for m in matched_bids if m.order_id == bid.order_id
                ) >= bid.quantity
                ask_filled = sum(
                    m.quantity for m in matched_asks if m.order_id == ask.order_id
                ) >= ask.quantity

                if bid_filled:
                    bid_idx += 1
                if ask_filled:
                    ask_idx += 1

                if not bid_filled and not ask_filled:
                    break
            else:
                # No more matches possible
                break

        # Determine clearing price
        if highest_matched_bid is not None and lowest_matched_ask is not None:
            if self.clearing_rule == "midpoint":
                clearing_price = (highest_matched_bid + lowest_matched_ask) / 2
            elif self.clearing_rule == "buyer_price":
                clearing_price = highest_matched_bid
            else:  # seller_price
                clearing_price = lowest_matched_ask
        else:
            clearing_price = 0.0

        return clearing_price, total_quantity, matched_bids, matched_asks

    def _execute_trades(
        self,
        bids: list[Order],
        asks: list[Order],
        clearing_price: float,
        total_quantity: float,
    ) -> list[Trade]:
        """Execute trades at uniform clearing price."""
        trades = []

        bid_remaining = {b.order_id: b.quantity for b in bids}
        ask_remaining = {a.order_id: a.quantity for a in asks}

        bid_idx = 0
        ask_idx = 0

        while bid_idx < len(bids) and ask_idx < len(asks):
            bid = bids[bid_idx]
            ask = asks[ask_idx]

            match_quantity = min(
                bid_remaining[bid.order_id],
                ask_remaining[ask.order_id],
            )

            if match_quantity > 0:
                self._trade_counter += 1
                trade = Trade(
                    trade_id=f"trade_{self._trade_counter}",
                    buyer_id=bid.agent_id,
                    seller_id=ask.agent_id,
                    buyer_type=bid.agent_type,
                    seller_type=ask.agent_type,
                    price=clearing_price,
                    quantity=match_quantity,
                    buyer_surplus=(bid.price - clearing_price) * match_quantity,
                    seller_surplus=(clearing_price - ask.price) * match_quantity,
                )
                trades.append(trade)

                bid_remaining[bid.order_id] -= match_quantity
                ask_remaining[ask.order_id] -= match_quantity

            if bid_remaining[bid.order_id] <= 0:
                bid_idx += 1
            if ask_remaining[ask.order_id] <= 0:
                ask_idx += 1

        return trades

    def _calculate_theoretical_maximum(
        self,
        bids: list[Order],
        asks: list[Order],
    ) -> float:
        """Calculate theoretical maximum welfare."""
        # Maximum welfare is achieved when all positive surplus trades occur
        all_possible_surplus = 0.0

        for bid in bids:
            for ask in asks:
                if bid.price >= ask.price:
                    surplus = (bid.price - ask.price) * min(bid.quantity, ask.quantity)
                    all_possible_surplus += surplus

        return all_possible_surplus

    def get_order_book_stats(self) -> dict:
        """Get order book statistics."""
        if not self.bids or not self.asks:
            return {
                "num_bids": len(self.bids),
                "num_asks": len(self.asks),
                "best_bid": None,
                "best_ask": None,
                "spread": None,
            }

        best_bid = max(b.price for b in self.bids)
        best_ask = min(a.price for a in self.asks)

        return {
            "num_bids": len(self.bids),
            "num_asks": len(self.asks),
            "bid_volume": sum(b.quantity for b in self.bids),
            "ask_volume": sum(a.quantity for a in self.asks),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": best_ask - best_bid if best_ask > best_bid else 0,
            "bid_price_mean": np.mean([b.price for b in self.bids]),
            "ask_price_mean": np.mean([a.price for a in self.asks]),
        }

    @property
    def is_budget_balanced(self) -> bool:
        """Uniform price auction is always budget balanced."""
        return True

    @property
    def is_individually_rational(self) -> bool:
        """Uniform price auction is IR: no one trades at loss."""
        return True

    @property
    def is_incentive_compatible(self) -> bool:
        """Uniform price auction is NOT incentive compatible."""
        return False
