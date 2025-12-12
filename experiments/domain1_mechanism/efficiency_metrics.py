"""
Efficiency Metrics - Calculate all mechanism efficiency measures.

Provides comprehensive metrics for evaluating market mechanism performance
including allocative efficiency, individual rationality, and budget balance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .walrasian_calculator import WalrasianCalculator, WalrasianEquilibrium


@dataclass
class Trade:
    """A single trade record."""
    trade_id: str
    buyer_id: str
    seller_id: str
    price: float
    quantity: float
    buyer_valuation: float
    seller_cost: float
    timestamp: float = 0.0

    @property
    def buyer_surplus(self) -> float:
        """Buyer surplus from this trade."""
        return (self.buyer_valuation - self.price) * self.quantity

    @property
    def seller_surplus(self) -> float:
        """Seller surplus from this trade."""
        return (self.price - self.seller_cost) * self.quantity

    @property
    def total_surplus(self) -> float:
        """Total surplus from this trade."""
        return self.buyer_surplus + self.seller_surplus

    @property
    def is_buyer_ir(self) -> bool:
        """Check if buyer individual rationality is satisfied."""
        return self.price <= self.buyer_valuation

    @property
    def is_seller_ir(self) -> bool:
        """Check if seller individual rationality is satisfied."""
        return self.price >= self.seller_cost

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "price": self.price,
            "quantity": self.quantity,
            "buyer_valuation": self.buyer_valuation,
            "seller_cost": self.seller_cost,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "is_buyer_ir": self.is_buyer_ir,
            "is_seller_ir": self.is_seller_ir,
        }


@dataclass
class IRViolation:
    """Record of an individual rationality violation."""
    trade_id: str
    agent_id: str
    agent_type: str  # "buyer" or "seller"
    price: float
    valuation_or_cost: float
    violation_amount: float  # How much the violation is


@dataclass
class EfficiencyResults:
    """
    Complete efficiency metrics for a market run.

    Attributes:
        allocative_efficiency: η = Realized_Welfare / Optimal_Welfare
        realized_welfare: Total surplus from actual trades
        optimal_welfare: Maximum possible welfare (Walrasian)
        buyer_surplus_total: Total buyer surplus
        seller_surplus_total: Total seller surplus

        realized_volume: Total quantity traded
        optimal_volume: Walrasian equilibrium quantity
        volume_efficiency: Realized / Optimal volume ratio

        realized_price: Average clearing price
        equilibrium_price: Walrasian equilibrium price
        price_deviation: |Realized - Equilibrium| / Equilibrium
        price_deviation_pct: Price deviation as percentage

        market_maker_revenue: Revenue collected by auctioneer
        is_budget_balanced: Whether R >= 0

        num_trades: Number of trades executed
        num_buyer_ir_violations: Number of buyer IR violations
        num_seller_ir_violations: Number of seller IR violations
        buyer_ir_violations: List of buyer IR violations
        seller_ir_violations: List of seller IR violations

        all_trades: List of all trade records
    """
    # Allocative efficiency
    allocative_efficiency: float
    realized_welfare: float
    optimal_welfare: float
    buyer_surplus_total: float
    seller_surplus_total: float

    # Volume efficiency
    realized_volume: float
    optimal_volume: float
    volume_efficiency: float

    # Price discovery
    realized_price: float
    equilibrium_price: float
    price_deviation: float
    price_deviation_pct: float

    # Budget balance
    market_maker_revenue: float
    is_budget_balanced: bool

    # Trade counts
    num_trades: int
    num_buyer_ir_violations: int
    num_seller_ir_violations: int

    # Detailed records
    buyer_ir_violations: List[IRViolation] = field(default_factory=list)
    seller_ir_violations: List[IRViolation] = field(default_factory=list)
    all_trades: List[Trade] = field(default_factory=list)

    # Additional metrics
    price_variance: float = 0.0
    clearing_prices: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "allocative_efficiency": self.allocative_efficiency,
            "realized_welfare": self.realized_welfare,
            "optimal_welfare": self.optimal_welfare,
            "buyer_surplus_total": self.buyer_surplus_total,
            "seller_surplus_total": self.seller_surplus_total,
            "realized_volume": self.realized_volume,
            "optimal_volume": self.optimal_volume,
            "volume_efficiency": self.volume_efficiency,
            "realized_price": self.realized_price,
            "equilibrium_price": self.equilibrium_price,
            "price_deviation": self.price_deviation,
            "price_deviation_pct": self.price_deviation_pct,
            "market_maker_revenue": self.market_maker_revenue,
            "is_budget_balanced": self.is_budget_balanced,
            "num_trades": self.num_trades,
            "num_buyer_ir_violations": self.num_buyer_ir_violations,
            "num_seller_ir_violations": self.num_seller_ir_violations,
            "price_variance": self.price_variance,
        }


class EfficiencyMetrics:
    """
    Calculator for market mechanism efficiency metrics.

    Computes all metrics needed for hypotheses H1.1-H1.6.
    """

    def __init__(self):
        """Initialize the metrics calculator."""
        self.walrasian_calc = WalrasianCalculator()

    def compute_efficiency_metrics(
        self,
        trades: List[Trade],
        buyer_valuations: np.ndarray,
        seller_costs: np.ndarray,
        buyer_quantities: Optional[np.ndarray] = None,
        seller_quantities: Optional[np.ndarray] = None,
        market_maker_revenues: Optional[List[float]] = None,
    ) -> EfficiencyResults:
        """
        Compute all efficiency metrics from trade data.

        Args:
            trades: List of executed trades
            buyer_valuations: Array of all buyer valuations
            seller_costs: Array of all seller costs
            buyer_quantities: Array of buyer quantities
            seller_quantities: Array of seller quantities
            market_maker_revenues: List of market maker revenues per clearing

        Returns:
            EfficiencyResults with all metrics
        """
        # Compute Walrasian equilibrium
        walrasian = self.walrasian_calc.compute_walrasian_equilibrium(
            buyer_valuations,
            seller_costs,
            buyer_quantities,
            seller_quantities,
        )

        # Also compute optimal welfare directly (may differ slightly)
        optimal_welfare, optimal_volume, _ = self.walrasian_calc.compute_optimal_welfare_direct(
            buyer_valuations,
            seller_costs,
            buyer_quantities,
            seller_quantities,
        )

        # Calculate realized metrics from trades
        realized_welfare = sum(t.total_surplus for t in trades)
        buyer_surplus_total = sum(t.buyer_surplus for t in trades)
        seller_surplus_total = sum(t.seller_surplus for t in trades)
        realized_volume = sum(t.quantity for t in trades)

        # Calculate average realized price
        if trades:
            total_value = sum(t.price * t.quantity for t in trades)
            realized_price = total_value / realized_volume if realized_volume > 0 else 0
            prices = [t.price for t in trades]
            price_variance = float(np.var(prices)) if len(prices) > 1 else 0
        else:
            realized_price = 0
            prices = []
            price_variance = 0

        # Use maximum of the two optimal welfare calculations
        optimal_welfare = max(optimal_welfare, walrasian.maximum_welfare)
        optimal_volume = max(optimal_volume, walrasian.equilibrium_quantity)

        # Allocative efficiency
        allocative_efficiency = (
            realized_welfare / optimal_welfare
            if optimal_welfare > 0 else 0.0
        )

        # Volume efficiency
        volume_efficiency = (
            realized_volume / optimal_volume
            if optimal_volume > 0 else 0.0
        )

        # Price deviation
        eq_price = walrasian.equilibrium_price
        if eq_price > 0:
            price_deviation = abs(realized_price - eq_price) / eq_price
        else:
            price_deviation = 0.0

        # Market maker revenue
        if market_maker_revenues is not None:
            total_mm_revenue = sum(market_maker_revenues)
        else:
            # In McAfee, auctioneer keeps the spread between clearing prices
            # For now, assume budget balanced (no explicit auctioneer profit)
            total_mm_revenue = 0.0

        # Check individual rationality
        buyer_violations = []
        seller_violations = []

        for trade in trades:
            if not trade.is_buyer_ir:
                violation = IRViolation(
                    trade_id=trade.trade_id,
                    agent_id=trade.buyer_id,
                    agent_type="buyer",
                    price=trade.price,
                    valuation_or_cost=trade.buyer_valuation,
                    violation_amount=trade.price - trade.buyer_valuation,
                )
                buyer_violations.append(violation)

            if not trade.is_seller_ir:
                violation = IRViolation(
                    trade_id=trade.trade_id,
                    agent_id=trade.seller_id,
                    agent_type="seller",
                    price=trade.price,
                    valuation_or_cost=trade.seller_cost,
                    violation_amount=trade.seller_cost - trade.price,
                )
                seller_violations.append(violation)

        return EfficiencyResults(
            allocative_efficiency=float(allocative_efficiency),
            realized_welfare=float(realized_welfare),
            optimal_welfare=float(optimal_welfare),
            buyer_surplus_total=float(buyer_surplus_total),
            seller_surplus_total=float(seller_surplus_total),
            realized_volume=float(realized_volume),
            optimal_volume=float(optimal_volume),
            volume_efficiency=float(volume_efficiency),
            realized_price=float(realized_price),
            equilibrium_price=float(eq_price),
            price_deviation=float(price_deviation),
            price_deviation_pct=float(price_deviation * 100),
            market_maker_revenue=float(total_mm_revenue),
            is_budget_balanced=total_mm_revenue >= 0,
            num_trades=len(trades),
            num_buyer_ir_violations=len(buyer_violations),
            num_seller_ir_violations=len(seller_violations),
            buyer_ir_violations=buyer_violations,
            seller_ir_violations=seller_violations,
            all_trades=trades,
            price_variance=float(price_variance),
            clearing_prices=prices,
        )

    def compute_mcafee_efficiency(
        self,
        bids: List[Dict],
        asks: List[Dict],
    ) -> Tuple[EfficiencyResults, List[Trade]]:
        """
        Run McAfee auction and compute efficiency.

        Args:
            bids: List of bid dictionaries with keys:
                  {agent_id, price, quantity, valuation}
            asks: List of ask dictionaries with keys:
                  {agent_id, price, quantity, cost}

        Returns:
            Tuple of (EfficiencyResults, list of trades)
        """
        if not bids or not asks:
            # Empty market
            return self._empty_results(), []

        # Extract valuations and costs
        buyer_valuations = np.array([b["valuation"] for b in bids])
        seller_costs = np.array([a["cost"] for a in asks])
        buyer_quantities = np.array([b["quantity"] for b in bids])
        seller_quantities = np.array([a["quantity"] for a in asks])

        # Run McAfee auction
        trades, mm_revenue = self._run_mcafee_auction(bids, asks)

        # Compute efficiency metrics
        results = self.compute_efficiency_metrics(
            trades=trades,
            buyer_valuations=buyer_valuations,
            seller_costs=seller_costs,
            buyer_quantities=buyer_quantities,
            seller_quantities=seller_quantities,
            market_maker_revenues=[mm_revenue],
        )

        return results, trades

    def _run_mcafee_auction(
        self,
        bids: List[Dict],
        asks: List[Dict],
    ) -> Tuple[List[Trade], float]:
        """
        Execute McAfee double auction.

        Returns:
            Tuple of (list of trades, market maker revenue)
        """
        # Sort bids descending by price
        sorted_bids = sorted(bids, key=lambda x: -x["price"])

        # Sort asks ascending by price
        sorted_asks = sorted(asks, key=lambda x: x["price"])

        # Find number of potential trades (k)
        k = 0
        while k < len(sorted_bids) and k < len(sorted_asks):
            if sorted_bids[k]["price"] >= sorted_asks[k]["price"]:
                k += 1
            else:
                break

        if k == 0:
            return [], 0.0

        trades = []
        mm_revenue = 0.0

        # McAfee mechanism
        if k < len(sorted_bids) and k < len(sorted_asks):
            # Check the (k+1)th pair
            b_k1 = sorted_bids[k]["price"]
            a_k1 = sorted_asks[k]["price"]
            p_m = (b_k1 + a_k1) / 2

            # Check if p_m works for the k-th pair
            b_k = sorted_bids[k - 1]["price"]
            a_k = sorted_asks[k - 1]["price"]

            if a_k <= p_m <= b_k:
                # Use p_m for all k trades
                clearing_price = p_m
                num_trades = k
            else:
                # Remove one trade, use average of k-th pair
                clearing_price = (b_k + a_k) / 2
                num_trades = k - 1
                # Market maker keeps the spread on k-th trade
                mm_revenue = (b_k - a_k) * min(
                    sorted_bids[k - 1]["quantity"],
                    sorted_asks[k - 1]["quantity"]
                )
        else:
            # All trades clear at average of last matched pair
            clearing_price = (sorted_bids[k - 1]["price"] + sorted_asks[k - 1]["price"]) / 2
            num_trades = k

        # Execute trades
        for i in range(num_trades):
            bid = sorted_bids[i]
            ask = sorted_asks[i]
            quantity = min(bid["quantity"], ask["quantity"])

            trade = Trade(
                trade_id=f"trade_{i}",
                buyer_id=bid["agent_id"],
                seller_id=ask["agent_id"],
                price=clearing_price,
                quantity=quantity,
                buyer_valuation=bid["valuation"],
                seller_cost=ask["cost"],
            )
            trades.append(trade)

        return trades, mm_revenue

    def _empty_results(self) -> EfficiencyResults:
        """Return empty results for empty market."""
        return EfficiencyResults(
            allocative_efficiency=0.0,
            realized_welfare=0.0,
            optimal_welfare=0.0,
            buyer_surplus_total=0.0,
            seller_surplus_total=0.0,
            realized_volume=0.0,
            optimal_volume=0.0,
            volume_efficiency=0.0,
            realized_price=0.0,
            equilibrium_price=0.0,
            price_deviation=0.0,
            price_deviation_pct=0.0,
            market_maker_revenue=0.0,
            is_budget_balanced=True,
            num_trades=0,
            num_buyer_ir_violations=0,
            num_seller_ir_violations=0,
        )

    def aggregate_results(
        self,
        results_list: List[EfficiencyResults],
    ) -> Dict:
        """
        Aggregate results across multiple runs.

        Args:
            results_list: List of EfficiencyResults from multiple runs

        Returns:
            Dictionary with aggregated statistics
        """
        if not results_list:
            return {}

        # Extract arrays of each metric
        efficiencies = np.array([r.allocative_efficiency for r in results_list])
        volume_effs = np.array([r.volume_efficiency for r in results_list])
        price_devs = np.array([r.price_deviation_pct for r in results_list])
        mm_revenues = np.array([r.market_maker_revenue for r in results_list])

        buyer_violations = sum(r.num_buyer_ir_violations for r in results_list)
        seller_violations = sum(r.num_seller_ir_violations for r in results_list)
        total_trades = sum(r.num_trades for r in results_list)

        return {
            "n_runs": len(results_list),
            "allocative_efficiency": {
                "mean": float(np.mean(efficiencies)),
                "std": float(np.std(efficiencies)),
                "min": float(np.min(efficiencies)),
                "max": float(np.max(efficiencies)),
                "median": float(np.median(efficiencies)),
            },
            "volume_efficiency": {
                "mean": float(np.mean(volume_effs)),
                "std": float(np.std(volume_effs)),
                "min": float(np.min(volume_effs)),
                "max": float(np.max(volume_effs)),
            },
            "price_deviation_pct": {
                "mean": float(np.mean(price_devs)),
                "std": float(np.std(price_devs)),
                "min": float(np.min(price_devs)),
                "max": float(np.max(price_devs)),
            },
            "market_maker_revenue": {
                "mean": float(np.mean(mm_revenues)),
                "std": float(np.std(mm_revenues)),
                "min": float(np.min(mm_revenues)),
                "any_negative": bool(np.any(mm_revenues < 0)),
            },
            "ir_violations": {
                "total_buyer_violations": buyer_violations,
                "total_seller_violations": seller_violations,
                "total_violations": buyer_violations + seller_violations,
                "total_trades": total_trades,
                "buyer_violation_rate": buyer_violations / total_trades if total_trades > 0 else 0,
                "seller_violation_rate": seller_violations / total_trades if total_trades > 0 else 0,
            },
            "raw_data": {
                "efficiencies": efficiencies.tolist(),
                "volume_efficiencies": volume_effs.tolist(),
                "price_deviations": price_devs.tolist(),
                "mm_revenues": mm_revenues.tolist(),
            },
        }
