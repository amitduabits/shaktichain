"""
Metrics Calculator - Compute efficiency, welfare, and system metrics.

Provides comprehensive metrics for evaluating market performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class EfficiencyMetrics:
    """Efficiency-related metrics."""
    allocative_efficiency: float
    price_efficiency: float
    volume_efficiency: float
    convergence_rate: float
    deadweight_loss: float

    def to_dict(self) -> dict:
        return {
            "allocative_efficiency": self.allocative_efficiency,
            "price_efficiency": self.price_efficiency,
            "volume_efficiency": self.volume_efficiency,
            "convergence_rate": self.convergence_rate,
            "deadweight_loss": self.deadweight_loss,
        }


@dataclass
class WelfareMetrics:
    """Welfare-related metrics."""
    total_surplus: float
    buyer_surplus: float
    seller_surplus: float
    theoretical_maximum: float
    surplus_distribution_gini: float
    fairness_index: float

    def to_dict(self) -> dict:
        return {
            "total_surplus": self.total_surplus,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "theoretical_maximum": self.theoretical_maximum,
            "surplus_distribution_gini": self.surplus_distribution_gini,
            "fairness_index": self.fairness_index,
        }


@dataclass
class SystemMetrics:
    """System performance metrics."""
    avg_latency_ms: float
    p95_latency_ms: float
    throughput_tps: float
    gas_cost_total: float
    gas_cost_per_trade: float
    failed_transactions: int
    success_rate: float

    def to_dict(self) -> dict:
        return {
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "throughput_tps": self.throughput_tps,
            "gas_cost_total": self.gas_cost_total,
            "gas_cost_per_trade": self.gas_cost_per_trade,
            "failed_transactions": self.failed_transactions,
            "success_rate": self.success_rate,
        }


@dataclass
class TokenMetrics:
    """SHAKTI token metrics."""
    total_supply: float
    circulating_supply: float
    velocity: float
    tokens_minted: float
    tokens_burned: float
    price_stability: float
    kwh_backing_ratio: float

    def to_dict(self) -> dict:
        return {
            "total_supply": self.total_supply,
            "circulating_supply": self.circulating_supply,
            "velocity": self.velocity,
            "tokens_minted": self.tokens_minted,
            "tokens_burned": self.tokens_burned,
            "price_stability": self.price_stability,
            "kwh_backing_ratio": self.kwh_backing_ratio,
        }


class MetricsCalculator:
    """
    Calculator for market performance metrics.

    Computes efficiency, welfare, system, and token metrics.
    """

    def __init__(self):
        """Initialize the calculator."""
        pass

    def calculate_efficiency_metrics(
        self,
        trades: list[dict],
        bids: list[dict],
        asks: list[dict],
        theoretical_equilibrium_price: Optional[float] = None,
    ) -> EfficiencyMetrics:
        """
        Calculate efficiency metrics.

        Args:
            trades: List of executed trades
            bids: List of buy orders
            asks: List of sell orders
            theoretical_equilibrium_price: Known equilibrium price if available

        Returns:
            EfficiencyMetrics object
        """
        if not trades:
            return EfficiencyMetrics(
                allocative_efficiency=0.0,
                price_efficiency=0.0,
                volume_efficiency=0.0,
                convergence_rate=0.0,
                deadweight_loss=0.0,
            )

        # Allocative efficiency
        actual_surplus = sum(
            t.get("buyer_surplus", 0) + t.get("seller_surplus", 0)
            for t in trades
        )
        theoretical_max = self._calculate_theoretical_maximum(bids, asks)
        allocative_efficiency = (
            actual_surplus / theoretical_max if theoretical_max > 0 else 0
        )
        allocative_efficiency = max(0.0, min(float(allocative_efficiency), 1.0))

        # Price efficiency
        if theoretical_equilibrium_price:
            trade_prices = [t["price"] for t in trades]
            price_deviations = [
                abs(p - theoretical_equilibrium_price) / theoretical_equilibrium_price
                for p in trade_prices
            ]
            price_efficiency = 1 - np.mean(price_deviations) if price_deviations else 0
        else:
            price_efficiency = np.nan

        # Volume efficiency
        bid_volume = sum(b["quantity"] for b in bids)
        ask_volume = sum(a["quantity"] for a in asks)
        traded_volume = sum(t["quantity"] for t in trades)
        potential_volume = min(bid_volume, ask_volume)
        volume_efficiency = traded_volume / potential_volume if potential_volume > 0 else 0
        volume_efficiency = max(0.0, min(float(volume_efficiency), 1.0))

        # Convergence rate (how fast prices converge)
        if len(trades) > 10:
            early_prices = [t["price"] for t in trades[:len(trades)//3]]
            late_prices = [t["price"] for t in trades[-len(trades)//3:]]
            early_std = np.std(early_prices) if early_prices else 0
            late_std = np.std(late_prices) if late_prices else 0
            convergence_rate = 1 - (late_std / early_std) if early_std > 0 else 0
        else:
            convergence_rate = np.nan

        # Deadweight loss
        deadweight_loss = max(0.0, theoretical_max - actual_surplus)

        return EfficiencyMetrics(
            allocative_efficiency=float(allocative_efficiency),
            price_efficiency=float(price_efficiency),
            volume_efficiency=float(volume_efficiency),
            convergence_rate=float(convergence_rate),
            deadweight_loss=float(deadweight_loss),
        )

    def _calculate_theoretical_maximum(
        self,
        bids: list[dict],
        asks: list[dict],
    ) -> float:
        """Calculate theoretical maximum surplus."""
        if not bids or not asks:
            return 0.0

        # Sort by value/cost
        sorted_bids = sorted(bids, key=lambda x: -x.get("value", x["price"]))
        sorted_asks = sorted(asks, key=lambda x: x.get("cost", x["price"]))

        total = 0.0
        for i in range(min(len(sorted_bids), len(sorted_asks))):
            bid_value = sorted_bids[i].get("value", sorted_bids[i]["price"])
            ask_cost = sorted_asks[i].get("cost", sorted_asks[i]["price"])

            if bid_value >= ask_cost:
                quantity = min(sorted_bids[i]["quantity"], sorted_asks[i]["quantity"])
                total += (bid_value - ask_cost) * quantity
            else:
                break

        return total

    def calculate_welfare_metrics(
        self,
        trades: list[dict],
        agent_surpluses: Optional[dict] = None,
    ) -> WelfareMetrics:
        """
        Calculate welfare metrics.

        Args:
            trades: List of executed trades
            agent_surpluses: Optional dictionary of agent ID to total surplus

        Returns:
            WelfareMetrics object
        """
        if not trades:
            return WelfareMetrics(
                total_surplus=0.0,
                buyer_surplus=0.0,
                seller_surplus=0.0,
                theoretical_maximum=0.0,
                surplus_distribution_gini=0.0,
                fairness_index=1.0,
            )

        buyer_surplus = sum(t.get("buyer_surplus", 0) for t in trades)
        seller_surplus = sum(t.get("seller_surplus", 0) for t in trades)
        total_surplus = buyer_surplus + seller_surplus

        # Calculate Gini coefficient for surplus distribution
        if agent_surpluses:
            surpluses = list(agent_surpluses.values())
            gini = self._calculate_gini(surpluses)
        else:
            # Use per-trade surpluses
            all_surpluses = (
                [t.get("buyer_surplus", 0) for t in trades] +
                [t.get("seller_surplus", 0) for t in trades]
            )
            gini = self._calculate_gini(all_surpluses)

        # Fairness index (Jain's fairness)
        fairness = self._calculate_jains_fairness(
            [buyer_surplus, seller_surplus]
        )

        return WelfareMetrics(
            total_surplus=float(total_surplus),
            buyer_surplus=float(buyer_surplus),
            seller_surplus=float(seller_surplus),
            theoretical_maximum=0.0,  # Needs external calculation
            surplus_distribution_gini=float(gini),
            fairness_index=float(fairness),
        )

    def _calculate_gini(self, values: list[float]) -> float:
        """Calculate Gini coefficient."""
        if not values or all(v == 0 for v in values):
            return 0.0

        arr = np.array(values, dtype=float)
        min_val = float(np.min(arr))
        if min_val < 0:
            arr = arr - min_val

        if np.allclose(arr.sum(), 0.0):
            return 0.0

        sorted_values = np.sort(arr)
        n = len(sorted_values)
        index = np.arange(1, n + 1)

        gini = (np.sum((2 * index - n - 1) * sorted_values)) / (n * np.sum(sorted_values))
        return float(max(0.0, min(gini, 1.0)))

    def _calculate_jains_fairness(self, values: list[float]) -> float:
        """Calculate Jain's fairness index."""
        if not values or all(v == 0 for v in values):
            return 1.0

        n = len(values)
        sum_x = sum(values)
        sum_x2 = sum(x ** 2 for x in values)

        if sum_x2 == 0:
            return 1.0

        return (sum_x ** 2) / (n * sum_x2)

    def calculate_system_metrics(
        self,
        latencies: list[float],
        gas_costs: list[float],
        num_transactions: int,
        num_failed: int,
        duration_seconds: float,
    ) -> SystemMetrics:
        """
        Calculate system performance metrics.

        Args:
            latencies: List of transaction latencies in ms
            gas_costs: List of gas costs
            num_transactions: Total number of transactions
            num_failed: Number of failed transactions
            duration_seconds: Total duration

        Returns:
            SystemMetrics object
        """
        if not latencies:
            latencies = [0]

        avg_latency = float(np.mean(latencies))
        p95_latency = float(np.percentile(latencies, 95))

        throughput = num_transactions / duration_seconds if duration_seconds > 0 else 0

        total_gas = sum(gas_costs)
        gas_per_trade = total_gas / num_transactions if num_transactions > 0 else 0

        success_rate = (
            (num_transactions - num_failed) / num_transactions
            if num_transactions > 0 else 0
        )

        return SystemMetrics(
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            throughput_tps=float(throughput),
            gas_cost_total=float(total_gas),
            gas_cost_per_trade=float(gas_per_trade),
            failed_transactions=num_failed,
            success_rate=float(success_rate),
        )

    def calculate_token_metrics(
        self,
        initial_supply: float,
        current_supply: float,
        minted: float,
        burned: float,
        num_transactions: int,
        price_history: list[float],
        energy_traded_kwh: float,
    ) -> TokenMetrics:
        """
        Calculate SHAKTI token metrics.

        Args:
            initial_supply: Initial token supply
            current_supply: Current token supply
            minted: Tokens minted
            burned: Tokens burned
            num_transactions: Number of transactions
            price_history: Price history (INR per token)
            energy_traded_kwh: Total energy traded

        Returns:
            TokenMetrics object
        """
        # Velocity = transactions / supply
        velocity = num_transactions / current_supply if current_supply > 0 else 0

        # Price stability (1 - coefficient of variation)
        if price_history and len(price_history) > 1:
            price_std = np.std(price_history)
            price_mean = np.mean(price_history)
            cv = price_std / price_mean if price_mean > 0 else 0
            price_stability = max(0, 1 - cv)
        else:
            price_stability = 1.0

        # kWh backing ratio (should be close to 1.0)
        kwh_backing = energy_traded_kwh / current_supply if current_supply > 0 else 0

        return TokenMetrics(
            total_supply=float(initial_supply),
            circulating_supply=float(current_supply),
            velocity=float(velocity),
            tokens_minted=float(minted),
            tokens_burned=float(burned),
            price_stability=float(price_stability),
            kwh_backing_ratio=float(kwh_backing),
        )

    def calculate_market_quality(
        self,
        trades: list[dict],
        order_book_snapshots: list[dict],
    ) -> dict:
        """
        Calculate market quality metrics.

        Args:
            trades: List of trades
            order_book_snapshots: Snapshots of order book state

        Returns:
            Dictionary of market quality metrics
        """
        if not trades:
            return {
                "avg_spread": np.nan,
                "avg_depth": 0,
                "price_impact": np.nan,
                "volatility": np.nan,
            }

        prices = [t["price"] for t in trades]

        # Average spread from order book
        spreads = []
        depths = []
        for snapshot in order_book_snapshots:
            best_bid = snapshot.get("best_bid")
            best_ask = snapshot.get("best_ask")
            if best_bid and best_ask:
                spreads.append(best_ask - best_bid)
            depths.append(
                snapshot.get("bid_depth", 0) + snapshot.get("ask_depth", 0)
            )

        avg_spread = float(np.mean(spreads)) if spreads else np.nan
        avg_depth = float(np.mean(depths)) if depths else 0

        # Volatility
        if len(prices) > 1:
            returns = np.diff(np.log(prices))
            volatility = float(np.std(returns))
        else:
            volatility = np.nan

        # Price impact (average price change per unit volume)
        if len(trades) > 1:
            price_changes = np.abs(np.diff(prices))
            volumes = [t["quantity"] for t in trades[1:]]
            price_impact = float(np.mean(price_changes / np.array(volumes)))
        else:
            price_impact = np.nan

        return {
            "avg_spread": avg_spread,
            "avg_depth": avg_depth,
            "price_impact": price_impact,
            "volatility": volatility,
        }

    def aggregate_metrics(
        self,
        efficiency: EfficiencyMetrics,
        welfare: WelfareMetrics,
        system: SystemMetrics,
        token: TokenMetrics,
    ) -> dict:
        """
        Aggregate all metrics into a single dictionary.

        Args:
            efficiency: Efficiency metrics
            welfare: Welfare metrics
            system: System metrics
            token: Token metrics

        Returns:
            Combined dictionary
        """
        return {
            "efficiency": efficiency.to_dict(),
            "welfare": welfare.to_dict(),
            "system": system.to_dict(),
            "token": token.to_dict(),
        }
