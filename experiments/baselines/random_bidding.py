"""
Random Bidding Baseline - Zero Intelligence Market.

Market with all zero-intelligence agents for baseline comparison.
Based on Gode & Sunder (1993) findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..agents.zero_intelligence_agent import ZeroIntelligenceAgent
from ..agents.base_agent import AgentState, MarketState


@dataclass
class ZIMarketConfig:
    """Configuration for ZI market simulation."""
    num_agents: int = 100
    zi_variant: str = "ZI-C"  # "ZI-C" or "ZI-U"
    min_price: float = 0.5
    max_price: float = 20.0
    min_quantity: float = 0.1
    max_quantity: float = 10.0
    clearing_mechanism: str = "mcafee"  # "mcafee" or "uniform"
    periods: int = 100


@dataclass
class ZIMarketResult:
    """Result of a ZI market simulation."""
    period: int
    clearing_price: float
    clearing_quantity: float
    num_trades: int
    buyer_surplus: float
    seller_surplus: float
    total_surplus: float
    efficiency: float
    theoretical_maximum: float

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "clearing_price": self.clearing_price,
            "clearing_quantity": self.clearing_quantity,
            "num_trades": self.num_trades,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "total_surplus": self.total_surplus,
            "efficiency": self.efficiency,
            "theoretical_maximum": self.theoretical_maximum,
        }


class RandomBiddingMarket:
    """
    Market simulation with zero-intelligence agents.

    Used to establish baseline for how much efficiency comes from
    market mechanism vs. agent intelligence.
    """

    def __init__(
        self,
        config: Optional[ZIMarketConfig] = None,
        random_seed: int = 42,
    ):
        """
        Initialize the random bidding market.

        Args:
            config: Market configuration
            random_seed: Random seed for reproducibility
        """
        self.config = config or ZIMarketConfig()
        self.random_seed = random_seed
        np.random.seed(random_seed)

        # Create ZI agents
        self.agents = self._create_agents()

        # Results
        self.results: list[ZIMarketResult] = []
        self.all_bids: list[dict] = []
        self.all_trades: list[dict] = []

    def _create_agents(self) -> list[ZeroIntelligenceAgent]:
        """Create zero-intelligence agents."""
        agents = []

        for i in range(self.config.num_agents):
            # Random agent parameters
            battery_capacity = np.random.choice([30, 40, 50, 60, 75])
            soc = np.random.uniform(0.3, 0.8)

            # Value and cost drawn from distributions
            value = np.random.uniform(4.0, 10.0)
            cost = np.random.uniform(2.0, 6.0)

            # Ensure value > cost for reasonable agents
            if value < cost:
                value, cost = cost, value

            state = AgentState(
                id=f"zi_agent_{i}",
                type="zero_intelligence",
                battery_capacity_kwh=battery_capacity,
                current_soc=soc,
                min_soc=0.2,
                max_soc=0.9,
                cost_per_kwh=cost,
                value_per_kwh=value,
                risk_aversion=0.0,
            )

            agent = ZeroIntelligenceAgent(
                state=state,
                variant=self.config.zi_variant,
                bid_probability=0.8,
            )
            agents.append(agent)

        return agents

    def simulate_period(self, period: int) -> ZIMarketResult:
        """
        Simulate a single clearing period.

        Args:
            period: Period number

        Returns:
            Result of the period
        """
        # Collect bids from all agents
        bids = []
        asks = []

        market_state = MarketState(
            period=period,
            current_time=float(period),
            clearing_price=self.results[-1].clearing_price if self.results else 5.0,
            clearing_quantity=self.results[-1].clearing_quantity if self.results else 0,
        )

        for agent in self.agents:
            bid_result = agent.generate_bid(market_state)

            if bid_result is not None:
                price, quantity, side = bid_result

                bid_data = {
                    "agent_id": agent.state.id,
                    "agent_type": agent.state.type,
                    "price": price,
                    "quantity": quantity,
                    "side": side,
                    "value": agent.state.value_per_kwh,
                    "cost": agent.state.cost_per_kwh,
                }

                self.all_bids.append(bid_data)

                if side == "buy":
                    bids.append(bid_data)
                else:
                    asks.append(bid_data)

        # Clear the market
        if self.config.clearing_mechanism == "mcafee":
            result = self._mcafee_clearing(bids, asks, period)
        else:
            result = self._uniform_clearing(bids, asks, period)

        self.results.append(result)
        return result

    def _mcafee_clearing(
        self,
        bids: list[dict],
        asks: list[dict],
        period: int,
    ) -> ZIMarketResult:
        """
        McAfee double auction clearing.

        Satisfies individual rationality, budget balance, and
        incentive compatibility.
        """
        if not bids or not asks:
            return ZIMarketResult(
                period=period,
                clearing_price=0.0,
                clearing_quantity=0.0,
                num_trades=0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
                total_surplus=0.0,
                efficiency=0.0,
                theoretical_maximum=0.0,
            )

        # Sort bids descending, asks ascending
        sorted_bids = sorted(bids, key=lambda x: -x["price"])
        sorted_asks = sorted(asks, key=lambda x: x["price"])

        # Find market clearing
        trades = []
        buyer_surplus = 0.0
        seller_surplus = 0.0

        k = 0  # Number of potential trades
        while k < len(sorted_bids) and k < len(sorted_asks):
            if sorted_bids[k]["price"] >= sorted_asks[k]["price"]:
                k += 1
            else:
                break

        if k == 0:
            return ZIMarketResult(
                period=period,
                clearing_price=0.0,
                clearing_quantity=0.0,
                num_trades=0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
                total_surplus=0.0,
                efficiency=0.0,
                theoretical_maximum=self._calculate_max_surplus(sorted_bids, sorted_asks),
            )

        # McAfee mechanism
        if k < len(sorted_bids) and k < len(sorted_asks):
            # Use (b_{k+1} + a_{k+1}) / 2 as clearing price if it works
            p_m = (sorted_bids[k]["price"] + sorted_asks[k]["price"]) / 2

            if sorted_asks[k - 1]["price"] <= p_m <= sorted_bids[k - 1]["price"]:
                # Use this price for all k trades
                clearing_price = p_m
                num_trades = k
            else:
                # Remove one trade, use average of k-th pair
                clearing_price = (sorted_bids[k - 1]["price"] + sorted_asks[k - 1]["price"]) / 2
                num_trades = k - 1
        else:
            # All trades clear
            clearing_price = (sorted_bids[k - 1]["price"] + sorted_asks[k - 1]["price"]) / 2
            num_trades = k

        # Execute trades
        total_quantity = 0.0
        for i in range(num_trades):
            bid = sorted_bids[i]
            ask = sorted_asks[i]
            quantity = min(bid["quantity"], ask["quantity"])

            trade = {
                "buyer_id": bid["agent_id"],
                "seller_id": ask["agent_id"],
                "price": clearing_price,
                "quantity": quantity,
                "buyer_surplus": (bid["value"] - clearing_price) * quantity,
                "seller_surplus": (clearing_price - ask["cost"]) * quantity,
            }

            trades.append(trade)
            self.all_trades.append(trade)

            buyer_surplus += trade["buyer_surplus"]
            seller_surplus += trade["seller_surplus"]
            total_quantity += quantity

        theoretical_max = self._calculate_max_surplus(sorted_bids, sorted_asks)
        total_surplus = buyer_surplus + seller_surplus
        efficiency = total_surplus / theoretical_max if theoretical_max > 0 else 0

        return ZIMarketResult(
            period=period,
            clearing_price=clearing_price,
            clearing_quantity=total_quantity,
            num_trades=num_trades,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            total_surplus=total_surplus,
            efficiency=efficiency,
            theoretical_maximum=theoretical_max,
        )

    def _uniform_clearing(
        self,
        bids: list[dict],
        asks: list[dict],
        period: int,
    ) -> ZIMarketResult:
        """Uniform price clearing (for comparison)."""
        if not bids or not asks:
            return ZIMarketResult(
                period=period,
                clearing_price=0.0,
                clearing_quantity=0.0,
                num_trades=0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
                total_surplus=0.0,
                efficiency=0.0,
                theoretical_maximum=0.0,
            )

        sorted_bids = sorted(bids, key=lambda x: -x["price"])
        sorted_asks = sorted(asks, key=lambda x: x["price"])

        # Find crossing point
        k = 0
        while k < len(sorted_bids) and k < len(sorted_asks):
            if sorted_bids[k]["price"] >= sorted_asks[k]["price"]:
                k += 1
            else:
                break

        if k == 0:
            return ZIMarketResult(
                period=period,
                clearing_price=0.0,
                clearing_quantity=0.0,
                num_trades=0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
                total_surplus=0.0,
                efficiency=0.0,
                theoretical_maximum=self._calculate_max_surplus(sorted_bids, sorted_asks),
            )

        # Uniform price = midpoint of marginal pair
        clearing_price = (sorted_bids[k - 1]["price"] + sorted_asks[k - 1]["price"]) / 2

        # Execute trades
        buyer_surplus = 0.0
        seller_surplus = 0.0
        total_quantity = 0.0

        for i in range(k):
            bid = sorted_bids[i]
            ask = sorted_asks[i]
            quantity = min(bid["quantity"], ask["quantity"])

            buyer_surplus += (bid["value"] - clearing_price) * quantity
            seller_surplus += (clearing_price - ask["cost"]) * quantity
            total_quantity += quantity

        theoretical_max = self._calculate_max_surplus(sorted_bids, sorted_asks)
        total_surplus = buyer_surplus + seller_surplus
        efficiency = total_surplus / theoretical_max if theoretical_max > 0 else 0

        return ZIMarketResult(
            period=period,
            clearing_price=clearing_price,
            clearing_quantity=total_quantity,
            num_trades=k,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            total_surplus=total_surplus,
            efficiency=efficiency,
            theoretical_maximum=theoretical_max,
        )

    def _calculate_max_surplus(
        self,
        bids: list[dict],
        asks: list[dict],
    ) -> float:
        """Calculate theoretical maximum surplus."""
        if not bids or not asks:
            return 0.0

        total = 0.0
        sorted_bids = sorted(bids, key=lambda x: -x["value"])
        sorted_asks = sorted(asks, key=lambda x: x["cost"])

        for i in range(min(len(sorted_bids), len(sorted_asks))):
            if sorted_bids[i]["value"] >= sorted_asks[i]["cost"]:
                quantity = min(sorted_bids[i]["quantity"], sorted_asks[i]["quantity"])
                total += (sorted_bids[i]["value"] - sorted_asks[i]["cost"]) * quantity

        return total

    def run_simulation(
        self,
        periods: Optional[int] = None,
    ) -> list[ZIMarketResult]:
        """
        Run full simulation.

        Args:
            periods: Number of periods (uses config if not specified)

        Returns:
            List of period results
        """
        periods = periods or self.config.periods
        self.results = []

        for period in range(periods):
            result = self.simulate_period(period)

        return self.results

    def get_summary_statistics(self) -> dict:
        """Get summary statistics from simulation."""
        if not self.results:
            return {}

        prices = [r.clearing_price for r in self.results if r.clearing_price > 0]
        quantities = [r.clearing_quantity for r in self.results]
        efficiencies = [r.efficiency for r in self.results]
        surpluses = [r.total_surplus for r in self.results]

        return {
            "num_periods": len(self.results),
            "avg_price": float(np.mean(prices)) if prices else 0,
            "price_std": float(np.std(prices)) if prices else 0,
            "avg_quantity": float(np.mean(quantities)),
            "total_trades": sum(r.num_trades for r in self.results),
            "avg_efficiency": float(np.mean(efficiencies)),
            "efficiency_std": float(np.std(efficiencies)),
            "total_surplus": sum(surpluses),
            "avg_buyer_surplus": float(np.mean([r.buyer_surplus for r in self.results])),
            "avg_seller_surplus": float(np.mean([r.seller_surplus for r in self.results])),
        }

    def compare_with_intelligent_market(
        self,
        intelligent_results: list[dict],
    ) -> dict:
        """
        Compare ZI market with intelligent agents.

        Args:
            intelligent_results: Results from market with intelligent agents

        Returns:
            Comparison metrics
        """
        zi_stats = self.get_summary_statistics()

        int_prices = [r.get("clearing_price", 0) for r in intelligent_results]
        int_efficiencies = [r.get("efficiency", 0) for r in intelligent_results]
        int_surpluses = [r.get("total_surplus", 0) for r in intelligent_results]

        return {
            "zi_avg_efficiency": zi_stats["avg_efficiency"],
            "intelligent_avg_efficiency": float(np.mean(int_efficiencies)),
            "efficiency_difference": float(np.mean(int_efficiencies)) - zi_stats["avg_efficiency"],
            "zi_avg_price": zi_stats["avg_price"],
            "intelligent_avg_price": float(np.mean(int_prices)) if int_prices else 0,
            "zi_total_surplus": zi_stats["total_surplus"],
            "intelligent_total_surplus": sum(int_surpluses),
            "surplus_ratio": sum(int_surpluses) / zi_stats["total_surplus"] if zi_stats["total_surplus"] > 0 else 0,
            "comment": (
                "Efficiency close to ZI suggests market mechanism is key; "
                "large difference suggests agent intelligence matters."
            ),
        }
