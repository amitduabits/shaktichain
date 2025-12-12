"""
Uniform Price Auction Baseline for SHAKTI-CHAIN Benchmarking (Domain 8).

Implements a uniform price auction mechanism where all trades clear
at a single market clearing price.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """
    Auction order.

    Attributes:
        agent_id: Agent identifier
        side: 'buy' or 'sell'
        quantity: Energy quantity (kWh)
        price: Limit price (INR/kWh)
        timestamp: Order timestamp
    """
    agent_id: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp,
        }


@dataclass
class Trade:
    """
    Executed trade.

    Attributes:
        buyer_id: Buyer agent ID
        seller_id: Seller agent ID
        quantity: Traded quantity (kWh)
        price: Trade price (INR/kWh)
        timestamp: Trade timestamp
    """
    buyer_id: str
    seller_id: str
    quantity: float
    price: float
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp,
        }


@dataclass
class AuctionResult:
    """
    Result from uniform price auction.

    Attributes:
        clearing_price: Market clearing price
        total_quantity: Total quantity traded
        trades: List of executed trades
        efficiency: Allocative efficiency
        surplus: Total surplus (buyer + seller)
        buyer_surplus: Buyer surplus
        seller_surplus: Seller surplus
    """
    clearing_price: float
    total_quantity: float
    trades: List[Trade]
    efficiency: float
    surplus: float
    buyer_surplus: float
    seller_surplus: float
    unmatched_demand: float = 0.0
    unmatched_supply: float = 0.0

    def to_dict(self) -> dict:
        return {
            "clearing_price": self.clearing_price,
            "total_quantity": self.total_quantity,
            "n_trades": len(self.trades),
            "efficiency": self.efficiency,
            "surplus": self.surplus,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "unmatched_demand": self.unmatched_demand,
            "unmatched_supply": self.unmatched_supply,
        }


class UniformPriceAuction:
    """
    Uniform Price Auction mechanism.

    All trades clear at a single market clearing price where
    aggregate supply equals aggregate demand.

    This is the baseline for comparison with McAfee mechanism.
    """

    def __init__(self, price_cap: float = 15.0, price_floor: float = 1.0):
        """
        Initialize auction.

        Args:
            price_cap: Maximum allowed price
            price_floor: Minimum allowed price
        """
        self.price_cap = price_cap
        self.price_floor = price_floor
        self.bids: List[Order] = []
        self.asks: List[Order] = []

    def submit_bid(self, order: Order) -> None:
        """Submit a buy order (bid)."""
        if order.side != 'buy':
            raise ValueError("Bid must have side='buy'")
        self.bids.append(order)

    def submit_ask(self, order: Order) -> None:
        """Submit a sell order (ask)."""
        if order.side != 'sell':
            raise ValueError("Ask must have side='sell'")
        self.asks.append(order)

    def clear_market(self) -> AuctionResult:
        """
        Clear the market at uniform price.

        1. Sort bids descending by price
        2. Sort asks ascending by price
        3. Find intersection (clearing price and quantity)
        4. Execute trades at clearing price

        Returns:
            AuctionResult with trades and metrics
        """
        if not self.bids or not self.asks:
            return AuctionResult(
                clearing_price=0.0,
                total_quantity=0.0,
                trades=[],
                efficiency=0.0,
                surplus=0.0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
            )

        # Sort orders
        sorted_bids = sorted(self.bids, key=lambda x: -x.price)
        sorted_asks = sorted(self.asks, key=lambda x: x.price)

        # Build aggregate demand and supply curves
        demand_curve = self._build_curve(sorted_bids)
        supply_curve = self._build_curve(sorted_asks)

        # Find clearing price and quantity
        clearing_price, clearing_qty = self._find_clearing_point(
            sorted_bids, sorted_asks
        )

        if clearing_qty <= 0:
            return AuctionResult(
                clearing_price=0.0,
                total_quantity=0.0,
                trades=[],
                efficiency=0.0,
                surplus=0.0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
                unmatched_demand=sum(b.quantity for b in self.bids),
                unmatched_supply=sum(a.quantity for a in self.asks),
            )

        # Execute trades at uniform clearing price
        trades, buyer_surplus, seller_surplus = self._execute_trades(
            sorted_bids, sorted_asks, clearing_price, clearing_qty
        )

        # Calculate efficiency
        max_welfare = self._calculate_max_welfare(sorted_bids, sorted_asks)
        actual_welfare = buyer_surplus + seller_surplus
        efficiency = actual_welfare / max_welfare if max_welfare > 0 else 0

        # Calculate unmatched
        total_demand = sum(b.quantity for b in self.bids)
        total_supply = sum(a.quantity for a in self.asks)

        return AuctionResult(
            clearing_price=clearing_price,
            total_quantity=clearing_qty,
            trades=trades,
            efficiency=efficiency,
            surplus=actual_welfare,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            unmatched_demand=max(0, total_demand - clearing_qty),
            unmatched_supply=max(0, total_supply - clearing_qty),
        )

    def _build_curve(self, orders: List[Order]) -> List[Tuple[float, float]]:
        """Build aggregate curve from orders."""
        curve = []
        cumulative_qty = 0

        for order in orders:
            curve.append((order.price, cumulative_qty))
            cumulative_qty += order.quantity
            curve.append((order.price, cumulative_qty))

        return curve

    def _find_clearing_point(
        self,
        bids: List[Order],
        asks: List[Order],
    ) -> Tuple[float, float]:
        """Find market clearing price and quantity."""
        bid_idx = 0
        ask_idx = 0
        bid_qty = 0.0
        ask_qty = 0.0

        clearing_price = 0.0
        clearing_qty = 0.0

        while bid_idx < len(bids) and ask_idx < len(asks):
            bid = bids[bid_idx]
            ask = asks[ask_idx]

            # Check if bid >= ask (can trade)
            if bid.price >= ask.price:
                # Determine quantity at this price level
                remaining_bid = bid.quantity - (bid_qty if bid_idx == 0 else 0)
                remaining_ask = ask.quantity - (ask_qty if ask_idx == 0 else 0)

                trade_qty = min(bid.quantity, ask.quantity)
                clearing_qty += trade_qty

                # Price is midpoint or can be any value in [ask, bid]
                clearing_price = (bid.price + ask.price) / 2

                # Move to next orders
                bid_idx += 1
                ask_idx += 1
            else:
                # No more trades possible
                break

        return clearing_price, clearing_qty

    def _execute_trades(
        self,
        bids: List[Order],
        asks: List[Order],
        clearing_price: float,
        clearing_qty: float,
    ) -> Tuple[List[Trade], float, float]:
        """Execute trades at clearing price."""
        trades = []
        buyer_surplus = 0.0
        seller_surplus = 0.0
        remaining_qty = clearing_qty

        bid_idx = 0
        ask_idx = 0

        while remaining_qty > 0 and bid_idx < len(bids) and ask_idx < len(asks):
            bid = bids[bid_idx]
            ask = asks[ask_idx]

            if bid.price < clearing_price or ask.price > clearing_price:
                break

            trade_qty = min(bid.quantity, ask.quantity, remaining_qty)

            if trade_qty > 0:
                trade = Trade(
                    buyer_id=bid.agent_id,
                    seller_id=ask.agent_id,
                    quantity=trade_qty,
                    price=clearing_price,
                )
                trades.append(trade)

                buyer_surplus += (bid.price - clearing_price) * trade_qty
                seller_surplus += (clearing_price - ask.price) * trade_qty
                remaining_qty -= trade_qty

            bid_idx += 1
            ask_idx += 1

        return trades, buyer_surplus, seller_surplus

    def _calculate_max_welfare(
        self,
        bids: List[Order],
        asks: List[Order],
    ) -> float:
        """Calculate maximum possible welfare (perfect matching)."""
        # Sort by surplus potential
        bid_values = [(b.price, b.quantity) for b in bids]
        ask_costs = [(a.price, a.quantity) for a in asks]

        bid_values.sort(key=lambda x: -x[0])
        ask_costs.sort(key=lambda x: x[0])

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

    def reset(self) -> None:
        """Reset auction state."""
        self.bids.clear()
        self.asks.clear()


class UniformAuctionSimulator:
    """
    Simulator for uniform price auctions.
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
        n_rounds: int = 100,
        mean_valuation: float = 8.0,
        mean_cost: float = 4.0,
        valuation_std: float = 2.0,
        cost_std: float = 1.5,
    ) -> Dict[str, Any]:
        """
        Simulate multiple auction rounds.

        Args:
            n_buyers: Number of buyers
            n_sellers: Number of sellers
            n_rounds: Number of auction rounds
            mean_valuation: Mean buyer valuation
            mean_cost: Mean seller cost
            valuation_std: Valuation standard deviation
            cost_std: Cost standard deviation

        Returns:
            Simulation results
        """
        efficiencies = []
        clearing_prices = []
        quantities = []
        surpluses = []

        for _ in range(n_rounds):
            auction = UniformPriceAuction()

            # Generate buyer orders
            for i in range(n_buyers):
                valuation = self.rng.normal(mean_valuation, valuation_std)
                valuation = max(1.0, valuation)
                quantity = self.rng.uniform(1, 10)

                auction.submit_bid(Order(
                    agent_id=f"buyer_{i}",
                    side="buy",
                    quantity=quantity,
                    price=valuation,
                ))

            # Generate seller orders
            for i in range(n_sellers):
                cost = self.rng.normal(mean_cost, cost_std)
                cost = max(0.5, cost)
                quantity = self.rng.uniform(1, 10)

                auction.submit_ask(Order(
                    agent_id=f"seller_{i}",
                    side="sell",
                    quantity=quantity,
                    price=cost,
                ))

            # Clear market
            result = auction.clear_market()

            efficiencies.append(result.efficiency)
            clearing_prices.append(result.clearing_price)
            quantities.append(result.total_quantity)
            surpluses.append(result.surplus)

        return {
            "mean_efficiency": float(np.mean(efficiencies)),
            "std_efficiency": float(np.std(efficiencies)),
            "mean_clearing_price": float(np.mean(clearing_prices)),
            "mean_quantity": float(np.mean(quantities)),
            "mean_surplus": float(np.mean(surpluses)),
            "efficiencies": efficiencies,
            "n_rounds": n_rounds,
        }


def simulate_uniform_auction(
    n_buyers: int = 50,
    n_sellers: int = 50,
    n_rounds: int = 100,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run uniform auction simulation.

    Args:
        n_buyers: Number of buyers
        n_sellers: Number of sellers
        n_rounds: Number of rounds
        seed: Random seed

    Returns:
        Simulation results
    """
    simulator = UniformAuctionSimulator(seed=seed)
    return simulator.simulate(n_buyers, n_sellers, n_rounds)
