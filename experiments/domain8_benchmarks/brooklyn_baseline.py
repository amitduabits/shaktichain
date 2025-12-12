"""
Brooklyn Microgrid Baseline for SHAKTI-CHAIN Benchmarking (Domain 8).

Implements the Brooklyn Microgrid P2P energy trading model.
Reference: Mengelkamp et al., Applied Energy, 2018

Features:
- Bilateral negotiation
- Local preference pricing
- Ethereum-based settlement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    """
    Brooklyn Microgrid agent.

    Attributes:
        agent_id: Agent identifier
        location: Grid location (for local preference)
        is_prosumer: Whether agent has generation capacity
        generation_kwh: Current generation (if prosumer)
        consumption_kwh: Current consumption
        local_preference: Preference for local energy (0-1)
        max_price: Maximum buying price
        min_price: Minimum selling price
    """
    agent_id: str
    location: Tuple[float, float] = (0.0, 0.0)
    is_prosumer: bool = False
    generation_kwh: float = 0.0
    consumption_kwh: float = 0.0
    local_preference: float = 0.5
    max_price: float = 10.0
    min_price: float = 2.0

    def net_energy(self) -> float:
        """Net energy (positive = surplus, negative = deficit)."""
        return self.generation_kwh - self.consumption_kwh

    def distance_to(self, other: 'Agent') -> float:
        """Calculate distance to another agent."""
        dx = self.location[0] - other.location[0]
        dy = self.location[1] - other.location[1]
        return np.sqrt(dx * dx + dy * dy)


@dataclass
class Trade:
    """Bilateral trade."""
    buyer_id: str
    seller_id: str
    quantity: float
    price: float
    distance: float
    local_premium: float
    settlement_cost: float
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "quantity": self.quantity,
            "price": self.price,
            "distance": self.distance,
            "local_premium": self.local_premium,
            "settlement_cost": self.settlement_cost,
        }


@dataclass
class BrooklynResult:
    """
    Result from Brooklyn Microgrid simulation.

    Attributes:
        trades: List of executed trades
        total_traded_kwh: Total energy traded
        total_settlement_cost: Total Ethereum gas costs
        avg_trade_price: Average trade price
        local_trade_fraction: Fraction of local trades
        total_buyer_cost: Total cost to buyers
        total_seller_revenue: Total revenue to sellers
    """
    trades: List[Trade] = field(default_factory=list)
    total_traded_kwh: float = 0.0
    total_settlement_cost: float = 0.0
    avg_trade_price: float = 0.0
    local_trade_fraction: float = 0.0
    total_buyer_cost: float = 0.0
    total_seller_revenue: float = 0.0
    efficiency: float = 0.0

    def to_dict(self) -> dict:
        return {
            "n_trades": len(self.trades),
            "total_traded_kwh": self.total_traded_kwh,
            "total_settlement_cost": self.total_settlement_cost,
            "avg_trade_price": self.avg_trade_price,
            "local_trade_fraction": self.local_trade_fraction,
            "total_buyer_cost": self.total_buyer_cost,
            "total_seller_revenue": self.total_seller_revenue,
            "efficiency": self.efficiency,
        }


class BrooklynMicrogridModel:
    """
    Brooklyn Microgrid P2P energy trading model.

    Reference: Mengelkamp et al., Applied Energy, 2018

    Features:
    - Bilateral negotiation
    - Local preference pricing
    - Ethereum-based settlement
    """

    def __init__(
        self,
        local_premium: float = 0.02,
        local_distance_threshold: float = 100.0,
        settlement_cost_eth: float = 0.001,
        eth_inr_rate: float = 200000.0,
    ):
        """
        Initialize Brooklyn Microgrid model.

        Args:
            local_premium: Premium for local energy (fraction)
            local_distance_threshold: Distance threshold for "local" (meters)
            settlement_cost_eth: Ethereum gas cost per trade (ETH)
            eth_inr_rate: ETH to INR exchange rate
        """
        self.local_premium = local_premium
        self.local_distance_threshold = local_distance_threshold
        self.settlement_cost_eth = settlement_cost_eth
        self.eth_inr_rate = eth_inr_rate
        self.trades: List[Trade] = []

    def match_bilateral(
        self,
        buyer: Agent,
        sellers: List[Agent],
    ) -> Optional[Trade]:
        """
        Bilateral matching with local preference.

        Buyer prefers local sellers (higher willingness to pay).

        Args:
            buyer: Buying agent
            sellers: Available sellers

        Returns:
            Trade if matched, None otherwise
        """
        if buyer.net_energy() >= 0:
            return None  # Buyer has no deficit

        demand = abs(buyer.net_energy())
        best_trade = None
        best_utility = float('-inf')

        for seller in sellers:
            if seller.net_energy() <= 0:
                continue  # Seller has no surplus

            supply = seller.net_energy()
            quantity = min(demand, supply)

            # Calculate distance
            distance = buyer.distance_to(seller)
            is_local = distance <= self.local_distance_threshold

            # Calculate price
            base_price = (buyer.max_price + seller.min_price) / 2
            local_adj = self.local_premium * base_price if is_local else 0
            trade_price = base_price + local_adj

            # Check if trade is acceptable
            if trade_price > buyer.max_price or trade_price < seller.min_price:
                continue

            # Calculate buyer utility (higher is better)
            # Includes local preference bonus
            local_bonus = buyer.local_preference * 2.0 if is_local else 0
            utility = (buyer.max_price - trade_price) * quantity + local_bonus

            if utility > best_utility:
                best_utility = utility
                settlement_cost = self.calculate_settlement_cost(
                    quantity * trade_price
                )

                best_trade = Trade(
                    buyer_id=buyer.agent_id,
                    seller_id=seller.agent_id,
                    quantity=quantity,
                    price=trade_price,
                    distance=distance,
                    local_premium=local_adj,
                    settlement_cost=settlement_cost,
                )

        if best_trade:
            self.trades.append(best_trade)

        return best_trade

    def calculate_settlement_cost(
        self,
        trade_value: float,
    ) -> float:
        """
        Calculate Ethereum gas cost in INR.

        Brooklyn uses main Ethereum (more expensive than Polygon).

        Args:
            trade_value: Trade value in INR

        Returns:
            Settlement cost in INR
        """
        # Gas cost in ETH, convert to INR
        gas_cost_inr = self.settlement_cost_eth * self.eth_inr_rate

        # Add variable component based on trade size
        variable_cost = trade_value * 0.001  # 0.1% of trade value

        return gas_cost_inr + variable_cost

    def run_trading_round(
        self,
        agents: List[Agent],
    ) -> List[Trade]:
        """
        Run a single trading round.

        Args:
            agents: All agents in the system

        Returns:
            List of trades executed
        """
        round_trades = []

        # Identify buyers and sellers
        buyers = [a for a in agents if a.net_energy() < 0]
        sellers = [a for a in agents if a.net_energy() > 0]

        # Random order for fairness
        np.random.shuffle(buyers)

        for buyer in buyers:
            trade = self.match_bilateral(buyer, sellers)
            if trade:
                round_trades.append(trade)

                # Update agent energy levels
                for s in sellers:
                    if s.agent_id == trade.seller_id:
                        s.generation_kwh -= trade.quantity
                        break

                buyer.consumption_kwh -= trade.quantity

        return round_trades

    def get_results(self) -> BrooklynResult:
        """Get simulation results."""
        if not self.trades:
            return BrooklynResult()

        total_traded = sum(t.quantity for t in self.trades)
        total_settlement = sum(t.settlement_cost for t in self.trades)
        avg_price = np.mean([t.price for t in self.trades])

        local_trades = sum(1 for t in self.trades
                         if t.distance <= self.local_distance_threshold)
        local_fraction = local_trades / len(self.trades)

        total_buyer_cost = sum(t.quantity * t.price + t.settlement_cost
                              for t in self.trades)
        total_seller_revenue = sum(t.quantity * t.price for t in self.trades)

        return BrooklynResult(
            trades=self.trades,
            total_traded_kwh=total_traded,
            total_settlement_cost=total_settlement,
            avg_trade_price=avg_price,
            local_trade_fraction=local_fraction,
            total_buyer_cost=total_buyer_cost,
            total_seller_revenue=total_seller_revenue,
        )

    def reset(self) -> None:
        """Reset trading state."""
        self.trades.clear()


class BrooklynSimulator:
    """
    Simulator for Brooklyn Microgrid model.
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
        n_prosumers: int = 30,
        n_consumers: int = 70,
        n_rounds: int = 24,
        grid_size: float = 500.0,
        avg_generation: float = 5.0,
        avg_consumption: float = 3.0,
    ) -> BrooklynResult:
        """
        Simulate Brooklyn Microgrid trading.

        Args:
            n_prosumers: Number of prosumers
            n_consumers: Number of pure consumers
            n_rounds: Number of trading rounds (hours)
            grid_size: Grid size in meters
            avg_generation: Average prosumer generation (kWh/hour)
            avg_consumption: Average consumption (kWh/hour)

        Returns:
            BrooklynResult
        """
        # Create agents
        agents = []

        for i in range(n_prosumers):
            agent = Agent(
                agent_id=f"prosumer_{i}",
                location=(
                    self.rng.uniform(0, grid_size),
                    self.rng.uniform(0, grid_size),
                ),
                is_prosumer=True,
                local_preference=self.rng.uniform(0.3, 0.8),
                max_price=self.rng.uniform(8, 12),
                min_price=self.rng.uniform(2, 4),
            )
            agents.append(agent)

        for i in range(n_consumers):
            agent = Agent(
                agent_id=f"consumer_{i}",
                location=(
                    self.rng.uniform(0, grid_size),
                    self.rng.uniform(0, grid_size),
                ),
                is_prosumer=False,
                local_preference=self.rng.uniform(0.2, 0.6),
                max_price=self.rng.uniform(6, 10),
                min_price=0,
            )
            agents.append(agent)

        # Create Brooklyn model
        brooklyn = BrooklynMicrogridModel(
            local_premium=0.02,
            local_distance_threshold=100.0,
            settlement_cost_eth=0.001,
            eth_inr_rate=200000.0,
        )

        # Run trading rounds
        for round_idx in range(n_rounds):
            # Update energy levels for this hour
            for agent in agents:
                if agent.is_prosumer:
                    # Solar generation (higher during day)
                    hour = round_idx % 24
                    if 6 <= hour < 18:
                        solar_factor = 1.0 - abs(hour - 12) / 6.0
                        agent.generation_kwh = self.rng.normal(
                            avg_generation * solar_factor,
                            avg_generation * 0.2
                        )
                        agent.generation_kwh = max(0, agent.generation_kwh)
                    else:
                        agent.generation_kwh = 0

                # Consumption varies by hour
                consumption_factor = 1.0
                if 7 <= round_idx % 24 < 9 or 18 <= round_idx % 24 < 22:
                    consumption_factor = 1.5  # Peak hours

                agent.consumption_kwh = self.rng.normal(
                    avg_consumption * consumption_factor,
                    avg_consumption * 0.3
                )
                agent.consumption_kwh = max(0, agent.consumption_kwh)

            # Run trading
            brooklyn.run_trading_round(agents)

        return brooklyn.get_results()


def simulate_brooklyn(
    n_prosumers: int = 30,
    n_consumers: int = 70,
    n_rounds: int = 24,
    seed: Optional[int] = None,
) -> BrooklynResult:
    """
    Run Brooklyn Microgrid simulation.

    Args:
        n_prosumers: Number of prosumers
        n_consumers: Number of consumers
        n_rounds: Number of trading rounds
        seed: Random seed

    Returns:
        BrooklynResult
    """
    simulator = BrooklynSimulator(seed=seed)
    return simulator.simulate(n_prosumers, n_consumers, n_rounds)
