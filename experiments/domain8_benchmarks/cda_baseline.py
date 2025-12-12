"""
Continuous Double Auction (CDA) Baseline for SHAKTI-CHAIN Benchmarking (Domain 8).

Implements a Continuous Double Auction mechanism as per IEEE Trans. Smart Grid 2023.
Orders matched continuously as they arrive.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import heapq

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """
    CDA order.

    Attributes:
        agent_id: Agent identifier
        side: 'buy' or 'sell'
        quantity: Energy quantity (kWh)
        price: Limit price (INR/kWh)
        timestamp: Order submission time
        order_id: Unique order identifier
    """
    agent_id: str
    side: str
    quantity: float
    price: float
    timestamp: float = 0.0
    order_id: int = 0

    def __lt__(self, other):
        """For heap ordering."""
        if self.side == 'buy':
            # Higher price = higher priority for bids
            return (-self.price, self.timestamp) < (-other.price, other.timestamp)
        else:
            # Lower price = higher priority for asks
            return (self.price, self.timestamp) < (other.price, other.timestamp)


@dataclass
class Trade:
    """Executed trade."""
    buyer_id: str
    seller_id: str
    quantity: float
    price: float
    timestamp: float
    bid_price: float = 0.0
    ask_price: float = 0.0

    def to_dict(self) -> dict:
        return {
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp,
        }


class OrderBook:
    """
    Order book for CDA.

    Maintains sorted bids (descending by price) and asks (ascending by price).
    """

    def __init__(self):
        """Initialize order book."""
        self.bids: List[Order] = []  # Max-heap (negated prices)
        self.asks: List[Order] = []  # Min-heap
        self._order_counter = 0

    def add_bid(self, order: Order) -> None:
        """Add a bid to the book."""
        order.order_id = self._order_counter
        self._order_counter += 1
        heapq.heappush(self.bids, order)

    def add_ask(self, order: Order) -> None:
        """Add an ask to the book."""
        order.order_id = self._order_counter
        self._order_counter += 1
        heapq.heappush(self.asks, order)

    def best_bid(self) -> Optional[Order]:
        """Get best (highest) bid."""
        while self.bids:
            if self.bids[0].quantity > 0:
                return self.bids[0]
            heapq.heappop(self.bids)
        return None

    def best_ask(self) -> Optional[Order]:
        """Get best (lowest) ask."""
        while self.asks:
            if self.asks[0].quantity > 0:
                return self.asks[0]
            heapq.heappop(self.asks)
        return None

    def remove_best_bid(self) -> Optional[Order]:
        """Remove and return best bid."""
        while self.bids:
            order = heapq.heappop(self.bids)
            if order.quantity > 0:
                return order
        return None

    def remove_best_ask(self) -> Optional[Order]:
        """Remove and return best ask."""
        while self.asks:
            order = heapq.heappop(self.asks)
            if order.quantity > 0:
                return order
        return None

    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None

    def midpoint(self) -> Optional[float]:
        """Get midpoint price."""
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / 2
        return None

    def depth(self, levels: int = 5) -> Dict[str, List[Tuple[float, float]]]:
        """Get order book depth."""
        bid_depth = []
        ask_depth = []

        # Get bid depth
        temp_bids = sorted(self.bids, key=lambda x: -x.price)
        for order in temp_bids[:levels]:
            if order.quantity > 0:
                bid_depth.append((order.price, order.quantity))

        # Get ask depth
        temp_asks = sorted(self.asks, key=lambda x: x.price)
        for order in temp_asks[:levels]:
            if order.quantity > 0:
                ask_depth.append((order.price, order.quantity))

        return {"bids": bid_depth, "asks": ask_depth}


@dataclass
class CDAResult:
    """
    Result from CDA simulation.

    Attributes:
        trades: List of executed trades
        total_welfare: Total welfare (buyer + seller surplus)
        buyer_surplus: Total buyer surplus
        seller_surplus: Total seller surplus
        efficiency: Allocative efficiency
        avg_spread: Average bid-ask spread
        price_volatility: Price volatility (std of trade prices)
    """
    trades: List[Trade] = field(default_factory=list)
    total_welfare: float = 0.0
    buyer_surplus: float = 0.0
    seller_surplus: float = 0.0
    efficiency: float = 0.0
    avg_spread: float = 0.0
    price_volatility: float = 0.0
    total_quantity: float = 0.0
    avg_price: float = 0.0

    def to_dict(self) -> dict:
        return {
            "n_trades": len(self.trades),
            "total_welfare": self.total_welfare,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "efficiency": self.efficiency,
            "avg_spread": self.avg_spread,
            "price_volatility": self.price_volatility,
            "total_quantity": self.total_quantity,
            "avg_price": self.avg_price,
        }


class ContinuousDoubleAuction:
    """
    Continuous Double Auction mechanism.

    Reference: IEEE Trans. Smart Grid 2023

    Orders matched continuously as they arrive.
    Price = midpoint of matched bid-ask.
    """

    def __init__(self, price_priority: str = "midpoint"):
        """
        Initialize CDA.

        Args:
            price_priority: 'midpoint', 'buyer', or 'seller' for price determination
        """
        self.order_book = OrderBook()
        self.trades: List[Trade] = []
        self.price_priority = price_priority
        self.spreads: List[float] = []

    def submit_order(self, order: Order) -> Optional[Trade]:
        """
        Submit order and attempt immediate match.

        CDA matches aggressively (any overlap clears).

        Args:
            order: Order to submit

        Returns:
            Trade if matched, None otherwise
        """
        if order.side == 'buy':
            return self._process_bid(order)
        else:
            return self._process_ask(order)

    def _process_bid(self, bid: Order) -> Optional[Trade]:
        """Process a buy order."""
        best_ask = self.order_book.best_ask()

        # Record spread
        best_bid_price = self.order_book.best_bid()
        if best_bid_price and best_ask:
            self.spreads.append(best_ask.price - best_bid_price.price)

        if best_ask and bid.price >= best_ask.price:
            # Match found
            trade_price = self._determine_price(bid.price, best_ask.price)
            trade_qty = min(bid.quantity, best_ask.quantity)

            trade = Trade(
                buyer_id=bid.agent_id,
                seller_id=best_ask.agent_id,
                quantity=trade_qty,
                price=trade_price,
                timestamp=bid.timestamp,
                bid_price=bid.price,
                ask_price=best_ask.price,
            )
            self.trades.append(trade)

            # Update order quantities
            best_ask.quantity -= trade_qty
            bid.quantity -= trade_qty

            # Remove filled ask
            if best_ask.quantity <= 0:
                self.order_book.remove_best_ask()

            # If bid not fully filled, add remainder to book
            if bid.quantity > 0:
                self.order_book.add_bid(bid)

            return trade

        # No match - add to book
        self.order_book.add_bid(bid)
        return None

    def _process_ask(self, ask: Order) -> Optional[Trade]:
        """Process a sell order."""
        best_bid = self.order_book.best_bid()

        # Record spread
        best_ask_price = self.order_book.best_ask()
        if best_bid and best_ask_price:
            self.spreads.append(best_ask_price.price - best_bid.price)

        if best_bid and best_bid.price >= ask.price:
            # Match found
            trade_price = self._determine_price(best_bid.price, ask.price)
            trade_qty = min(best_bid.quantity, ask.quantity)

            trade = Trade(
                buyer_id=best_bid.agent_id,
                seller_id=ask.agent_id,
                quantity=trade_qty,
                price=trade_price,
                timestamp=ask.timestamp,
                bid_price=best_bid.price,
                ask_price=ask.price,
            )
            self.trades.append(trade)

            # Update order quantities
            best_bid.quantity -= trade_qty
            ask.quantity -= trade_qty

            # Remove filled bid
            if best_bid.quantity <= 0:
                self.order_book.remove_best_bid()

            # If ask not fully filled, add remainder to book
            if ask.quantity > 0:
                self.order_book.add_ask(ask)

            return trade

        # No match - add to book
        self.order_book.add_ask(ask)
        return None

    def _determine_price(self, bid_price: float, ask_price: float) -> float:
        """Determine trade price based on priority rule."""
        if self.price_priority == "midpoint":
            return (bid_price + ask_price) / 2
        elif self.price_priority == "buyer":
            return ask_price  # Buyer gets better price
        elif self.price_priority == "seller":
            return bid_price  # Seller gets better price
        else:
            return (bid_price + ask_price) / 2

    def calculate_welfare(self) -> Tuple[float, float, float]:
        """
        Calculate total welfare.

        Returns:
            (total_welfare, buyer_surplus, seller_surplus)
        """
        buyer_surplus = 0.0
        seller_surplus = 0.0

        for trade in self.trades:
            buyer_surplus += (trade.bid_price - trade.price) * trade.quantity
            seller_surplus += (trade.price - trade.ask_price) * trade.quantity

        return buyer_surplus + seller_surplus, buyer_surplus, seller_surplus

    def get_results(self, max_welfare: float = None) -> CDAResult:
        """
        Get CDA results.

        Args:
            max_welfare: Maximum possible welfare (for efficiency calc)

        Returns:
            CDAResult
        """
        total_welfare, buyer_surplus, seller_surplus = self.calculate_welfare()

        # Calculate efficiency
        efficiency = total_welfare / max_welfare if max_welfare and max_welfare > 0 else 0

        # Calculate price statistics
        prices = [t.price for t in self.trades]
        avg_price = np.mean(prices) if prices else 0
        price_volatility = np.std(prices) if len(prices) > 1 else 0

        # Average spread
        avg_spread = np.mean(self.spreads) if self.spreads else 0

        # Total quantity
        total_quantity = sum(t.quantity for t in self.trades)

        return CDAResult(
            trades=self.trades,
            total_welfare=total_welfare,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            efficiency=efficiency,
            avg_spread=avg_spread,
            price_volatility=price_volatility,
            total_quantity=total_quantity,
            avg_price=avg_price,
        )

    def reset(self) -> None:
        """Reset CDA state."""
        self.order_book = OrderBook()
        self.trades.clear()
        self.spreads.clear()


class CDASimulator:
    """
    Simulator for Continuous Double Auction.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize simulator.

        Args:
            seed: Random seed
        """
        self.rng = np.random.default_rng(seed)

    def simulate(
        self,
        n_buyers: int,
        n_sellers: int,
        n_orders_per_agent: int = 10,
        mean_valuation: float = 8.0,
        mean_cost: float = 4.0,
        valuation_std: float = 2.0,
        cost_std: float = 1.5,
    ) -> CDAResult:
        """
        Simulate CDA trading session.

        Args:
            n_buyers: Number of buyers
            n_sellers: Number of sellers
            n_orders_per_agent: Orders per agent
            mean_valuation: Mean buyer valuation
            mean_cost: Mean seller cost
            valuation_std: Valuation standard deviation
            cost_std: Cost standard deviation

        Returns:
            CDAResult
        """
        cda = ContinuousDoubleAuction()

        # Generate all orders with random arrival times
        all_orders = []

        for i in range(n_buyers):
            valuation = self.rng.normal(mean_valuation, valuation_std)
            valuation = max(1.0, valuation)

            for j in range(n_orders_per_agent):
                # Buyers shade bids below valuation
                bid_price = valuation * self.rng.uniform(0.8, 1.0)
                quantity = self.rng.uniform(1, 5)
                timestamp = self.rng.uniform(0, 1000)

                all_orders.append(Order(
                    agent_id=f"buyer_{i}",
                    side="buy",
                    quantity=quantity,
                    price=bid_price,
                    timestamp=timestamp,
                ))

        for i in range(n_sellers):
            cost = self.rng.normal(mean_cost, cost_std)
            cost = max(0.5, cost)

            for j in range(n_orders_per_agent):
                # Sellers mark up above cost
                ask_price = cost * self.rng.uniform(1.0, 1.2)
                quantity = self.rng.uniform(1, 5)
                timestamp = self.rng.uniform(0, 1000)

                all_orders.append(Order(
                    agent_id=f"seller_{i}",
                    side="sell",
                    quantity=quantity,
                    price=ask_price,
                    timestamp=timestamp,
                ))

        # Sort by timestamp and process
        all_orders.sort(key=lambda x: x.timestamp)

        for order in all_orders:
            cda.submit_order(order)

        # Calculate max welfare for efficiency
        max_welfare = self._calculate_max_welfare(all_orders)

        return cda.get_results(max_welfare)

    def _calculate_max_welfare(self, orders: List[Order]) -> float:
        """Calculate maximum possible welfare."""
        bids = [o for o in orders if o.side == 'buy']
        asks = [o for o in orders if o.side == 'sell']

        bid_values = sorted([(b.price, b.quantity) for b in bids], key=lambda x: -x[0])
        ask_costs = sorted([(a.price, a.quantity) for a in asks], key=lambda x: x[0])

        max_welfare = 0.0
        bid_idx = 0
        ask_idx = 0

        while bid_idx < len(bid_values) and ask_idx < len(ask_costs):
            bid_price, bid_qty = bid_values[bid_idx]
            ask_price, ask_qty = ask_costs[ask_idx]

            if bid_price >= ask_price:
                trade_qty = min(bid_qty, ask_qty)
                max_welfare += (bid_price - ask_price) * trade_qty
                bid_idx += 1
                ask_idx += 1
            else:
                break

        return max_welfare


def simulate_cda(
    n_buyers: int = 50,
    n_sellers: int = 50,
    n_orders_per_agent: int = 10,
    seed: Optional[int] = None,
) -> CDAResult:
    """
    Run CDA simulation.

    Args:
        n_buyers: Number of buyers
        n_sellers: Number of sellers
        n_orders_per_agent: Orders per agent
        seed: Random seed

    Returns:
        CDAResult
    """
    simulator = CDASimulator(seed=seed)
    return simulator.simulate(n_buyers, n_sellers, n_orders_per_agent)
