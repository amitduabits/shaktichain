"""
Walrasian Calculator - Compute theoretical competitive equilibrium.

Calculates the Walrasian (competitive) equilibrium which serves as the
benchmark for measuring market mechanism efficiency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class WalrasianEquilibrium:
    """
    Result of Walrasian equilibrium computation.

    Attributes:
        equilibrium_price: P* - the competitive equilibrium price
        equilibrium_quantity: Q* - total quantity traded at equilibrium
        maximum_welfare: W* - total surplus at equilibrium
        buyer_surplus: Total buyer surplus at equilibrium
        seller_surplus: Total seller surplus at equilibrium
        num_buyers_trading: Number of buyers who trade at equilibrium
        num_sellers_trading: Number of sellers who trade at equilibrium
        demand_curve: List of (cumulative_quantity, price) points
        supply_curve: List of (cumulative_quantity, price) points
        marginal_buyer_valuation: Valuation of the marginal buyer
        marginal_seller_cost: Cost of the marginal seller
    """
    equilibrium_price: float
    equilibrium_quantity: float
    maximum_welfare: float
    buyer_surplus: float
    seller_surplus: float
    num_buyers_trading: int
    num_sellers_trading: int
    demand_curve: List[Tuple[float, float]] = field(default_factory=list)
    supply_curve: List[Tuple[float, float]] = field(default_factory=list)
    marginal_buyer_valuation: Optional[float] = None
    marginal_seller_cost: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "equilibrium_price": self.equilibrium_price,
            "equilibrium_quantity": self.equilibrium_quantity,
            "maximum_welfare": self.maximum_welfare,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "num_buyers_trading": self.num_buyers_trading,
            "num_sellers_trading": self.num_sellers_trading,
            "marginal_buyer_valuation": self.marginal_buyer_valuation,
            "marginal_seller_cost": self.marginal_seller_cost,
        }


@dataclass
class TraderInfo:
    """Information about a trader."""
    trader_id: str
    valuation_or_cost: float
    quantity: float
    is_buyer: bool


class WalrasianCalculator:
    """
    Compute Walrasian competitive equilibrium.

    The Walrasian equilibrium is found at the intersection of the
    aggregate demand and supply curves, where:
    - Demand curve: Buyers sorted by valuation (descending)
    - Supply curve: Sellers sorted by cost (ascending)

    At equilibrium, all buyers with valuation ≥ P* trade,
    and all sellers with cost ≤ P* trade.
    """

    def __init__(self):
        """Initialize the calculator."""
        pass

    def compute_walrasian_equilibrium(
        self,
        buyer_valuations: np.ndarray,
        seller_costs: np.ndarray,
        buyer_quantities: Optional[np.ndarray] = None,
        seller_quantities: Optional[np.ndarray] = None,
    ) -> WalrasianEquilibrium:
        """
        Compute Walrasian competitive equilibrium.

        Args:
            buyer_valuations: Array of buyer valuations (willingness to pay)
            seller_costs: Array of seller costs (minimum acceptable price)
            buyer_quantities: Array of quantities each buyer wants (default: 1 each)
            seller_quantities: Array of quantities each seller offers (default: 1 each)

        Returns:
            WalrasianEquilibrium with equilibrium price, quantity, and welfare
        """
        buyer_valuations = np.asarray(buyer_valuations)
        seller_costs = np.asarray(seller_costs)

        n_buyers = len(buyer_valuations)
        n_sellers = len(seller_costs)

        # Default quantities
        if buyer_quantities is None:
            buyer_quantities = np.ones(n_buyers)
        else:
            buyer_quantities = np.asarray(buyer_quantities)

        if seller_quantities is None:
            seller_quantities = np.ones(n_sellers)
        else:
            seller_quantities = np.asarray(seller_quantities)

        # Build demand curve (sorted by valuation descending)
        demand_curve = self._build_demand_curve(buyer_valuations, buyer_quantities)

        # Build supply curve (sorted by cost ascending)
        supply_curve = self._build_supply_curve(seller_costs, seller_quantities)

        # Find equilibrium (intersection of curves)
        eq_price, eq_quantity, trading_buyers, trading_sellers = \
            self._find_equilibrium(demand_curve, supply_curve)

        # Calculate welfare components
        buyer_surplus, seller_surplus = self._calculate_welfare(
            buyer_valuations, seller_costs,
            buyer_quantities, seller_quantities,
            eq_price, trading_buyers, trading_sellers
        )

        total_welfare = buyer_surplus + seller_surplus

        # Get marginal traders
        marginal_buyer_val = None
        marginal_seller_cost = None

        if trading_buyers > 0:
            sorted_buyers = np.argsort(buyer_valuations)[::-1]
            if trading_buyers <= len(sorted_buyers):
                marginal_idx = sorted_buyers[trading_buyers - 1]
                marginal_buyer_val = buyer_valuations[marginal_idx]

        if trading_sellers > 0:
            sorted_sellers = np.argsort(seller_costs)
            if trading_sellers <= len(sorted_sellers):
                marginal_idx = sorted_sellers[trading_sellers - 1]
                marginal_seller_cost = seller_costs[marginal_idx]

        return WalrasianEquilibrium(
            equilibrium_price=eq_price,
            equilibrium_quantity=eq_quantity,
            maximum_welfare=total_welfare,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            num_buyers_trading=trading_buyers,
            num_sellers_trading=trading_sellers,
            demand_curve=demand_curve,
            supply_curve=supply_curve,
            marginal_buyer_valuation=marginal_buyer_val,
            marginal_seller_cost=marginal_seller_cost,
        )

    def _build_demand_curve(
        self,
        valuations: np.ndarray,
        quantities: np.ndarray,
    ) -> List[Tuple[float, float]]:
        """
        Build aggregate demand curve.

        Returns list of (cumulative_quantity, price) tuples,
        sorted by price descending.
        """
        # Sort by valuation descending
        sorted_indices = np.argsort(valuations)[::-1]

        curve = []
        cumulative_qty = 0.0

        for idx in sorted_indices:
            price = valuations[idx]
            qty = quantities[idx]

            # Add point at start of this segment
            curve.append((cumulative_qty, price))
            cumulative_qty += qty
            # Add point at end of this segment
            curve.append((cumulative_qty, price))

        return curve

    def _build_supply_curve(
        self,
        costs: np.ndarray,
        quantities: np.ndarray,
    ) -> List[Tuple[float, float]]:
        """
        Build aggregate supply curve.

        Returns list of (cumulative_quantity, price) tuples,
        sorted by price ascending.
        """
        # Sort by cost ascending
        sorted_indices = np.argsort(costs)

        curve = []
        cumulative_qty = 0.0

        for idx in sorted_indices:
            price = costs[idx]
            qty = quantities[idx]

            # Add point at start of this segment
            curve.append((cumulative_qty, price))
            cumulative_qty += qty
            # Add point at end of this segment
            curve.append((cumulative_qty, price))

        return curve

    def _find_equilibrium(
        self,
        demand_curve: List[Tuple[float, float]],
        supply_curve: List[Tuple[float, float]],
    ) -> Tuple[float, float, int, int]:
        """
        Find equilibrium price and quantity.

        Returns:
            (equilibrium_price, equilibrium_quantity, num_buyers, num_sellers)
        """
        if not demand_curve or not supply_curve:
            return (0.0, 0.0, 0, 0)

        # Convert to step functions for easier comparison
        # Find where demand crosses supply

        # Get unique quantity points
        all_quantities = sorted(set(
            [q for q, _ in demand_curve] + [q for q, _ in supply_curve]
        ))

        equilibrium_qty = 0.0
        equilibrium_price = 0.0

        for qty in all_quantities:
            demand_price = self._get_price_at_quantity(demand_curve, qty, is_demand=True)
            supply_price = self._get_price_at_quantity(supply_curve, qty, is_demand=False)

            if demand_price is None or supply_price is None:
                continue

            if demand_price >= supply_price:
                equilibrium_qty = qty
                # Equilibrium price is typically between demand and supply at marginal unit
                equilibrium_price = (demand_price + supply_price) / 2
            else:
                # We've passed the equilibrium
                break

        # Refine equilibrium quantity by checking each unit
        # Count number of traders
        num_buyers = 0
        num_sellers = 0

        # Each step in demand curve represents a buyer
        qty_check = 0.0
        for i in range(0, len(demand_curve) - 1, 2):
            qty_step = demand_curve[i + 1][0] - demand_curve[i][0]
            price = demand_curve[i][1]
            if price >= equilibrium_price:
                num_buyers += 1
                qty_check += qty_step

        # Each step in supply curve represents a seller
        for i in range(0, len(supply_curve) - 1, 2):
            qty_step = supply_curve[i + 1][0] - supply_curve[i][0]
            price = supply_curve[i][1]
            if price <= equilibrium_price:
                num_sellers += 1

        # Actual equilibrium quantity is min of demand and supply at equilibrium
        return (equilibrium_price, equilibrium_qty, num_buyers, num_sellers)

    def _get_price_at_quantity(
        self,
        curve: List[Tuple[float, float]],
        quantity: float,
        is_demand: bool,
    ) -> Optional[float]:
        """Get price on curve at given quantity."""
        if not curve:
            return None

        for i in range(0, len(curve) - 1, 2):
            q_start, p = curve[i]
            q_end, _ = curve[i + 1]

            if q_start <= quantity <= q_end:
                return p
            elif quantity < q_start:
                # For demand curve, before first point means infinite price
                # For supply curve, before first point means zero/undefined
                if is_demand:
                    return curve[0][1] if i == 0 else curve[i-1][1]
                else:
                    return 0.0 if i == 0 else curve[i-1][1]

        # Beyond the curve
        return curve[-1][1] if curve else None

    def _calculate_welfare(
        self,
        buyer_valuations: np.ndarray,
        seller_costs: np.ndarray,
        buyer_quantities: np.ndarray,
        seller_quantities: np.ndarray,
        eq_price: float,
        num_buyers: int,
        num_sellers: int,
    ) -> Tuple[float, float]:
        """
        Calculate buyer and seller surplus at equilibrium.

        Returns:
            (buyer_surplus, seller_surplus)
        """
        # Sort buyers by valuation descending
        buyer_order = np.argsort(buyer_valuations)[::-1]

        # Sort sellers by cost ascending
        seller_order = np.argsort(seller_costs)

        # Buyer surplus: sum of (valuation - price) for all trading buyers
        buyer_surplus = 0.0
        for i in range(min(num_buyers, len(buyer_order))):
            idx = buyer_order[i]
            if buyer_valuations[idx] >= eq_price:
                surplus = (buyer_valuations[idx] - eq_price) * buyer_quantities[idx]
                buyer_surplus += surplus

        # Seller surplus: sum of (price - cost) for all trading sellers
        seller_surplus = 0.0
        for i in range(min(num_sellers, len(seller_order))):
            idx = seller_order[i]
            if seller_costs[idx] <= eq_price:
                surplus = (eq_price - seller_costs[idx]) * seller_quantities[idx]
                seller_surplus += surplus

        return (buyer_surplus, seller_surplus)

    def compute_optimal_welfare_direct(
        self,
        buyer_valuations: np.ndarray,
        seller_costs: np.ndarray,
        buyer_quantities: Optional[np.ndarray] = None,
        seller_quantities: Optional[np.ndarray] = None,
    ) -> Tuple[float, float, List[Tuple[int, int, float]]]:
        """
        Compute maximum welfare through direct matching.

        This finds the optimal allocation by matching highest-value buyers
        with lowest-cost sellers, regardless of price.

        Returns:
            (max_welfare, optimal_quantity, list of (buyer_idx, seller_idx, quantity) matches)
        """
        buyer_valuations = np.asarray(buyer_valuations)
        seller_costs = np.asarray(seller_costs)

        if buyer_quantities is None:
            buyer_quantities = np.ones(len(buyer_valuations))
        if seller_quantities is None:
            seller_quantities = np.ones(len(seller_costs))

        # Sort buyers by valuation descending
        buyer_order = np.argsort(buyer_valuations)[::-1]

        # Sort sellers by cost ascending
        seller_order = np.argsort(seller_costs)

        matches = []
        total_welfare = 0.0
        total_quantity = 0.0

        buyer_remaining = dict(zip(range(len(buyer_valuations)), buyer_quantities))
        seller_remaining = dict(zip(range(len(seller_costs)), seller_quantities))

        buyer_idx = 0
        seller_idx = 0

        while buyer_idx < len(buyer_order) and seller_idx < len(seller_order):
            b = buyer_order[buyer_idx]
            s = seller_order[seller_idx]

            # Check if trade is profitable
            if buyer_valuations[b] < seller_costs[s]:
                break  # No more profitable trades possible

            # Match quantity
            match_qty = min(buyer_remaining[b], seller_remaining[s])

            if match_qty > 0:
                welfare = (buyer_valuations[b] - seller_costs[s]) * match_qty
                total_welfare += welfare
                total_quantity += match_qty
                matches.append((b, s, match_qty))

                buyer_remaining[b] -= match_qty
                seller_remaining[s] -= match_qty

            # Move to next trader if exhausted
            if buyer_remaining[b] <= 0:
                buyer_idx += 1
            if seller_remaining[s] <= 0:
                seller_idx += 1

        return (total_welfare, total_quantity, matches)


def compute_walrasian_equilibrium(
    buyer_valuations: np.ndarray,
    seller_costs: np.ndarray,
    buyer_quantities: np.ndarray = None,
    seller_quantities: np.ndarray = None,
) -> Tuple[float, float, float]:
    """
    Convenience function to compute Walrasian competitive equilibrium.

    Args:
        buyer_valuations: Array of buyer valuations
        seller_costs: Array of seller costs
        buyer_quantities: Array of buyer quantities (default: 1 each)
        seller_quantities: Array of seller quantities (default: 1 each)

    Returns:
        equilibrium_price: P*
        equilibrium_quantity: Q*
        maximum_welfare: W*
    """
    calculator = WalrasianCalculator()
    result = calculator.compute_walrasian_equilibrium(
        buyer_valuations,
        seller_costs,
        buyer_quantities,
        seller_quantities,
    )
    return (result.equilibrium_price, result.equilibrium_quantity, result.maximum_welfare)
