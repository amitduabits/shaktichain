"""
Gas Cost Tracker for SHAKTI-CHAIN System Performance Testing (Domain 3).

Tracks and analyzes blockchain transaction costs with live exchange rate
integration from Yahoo Finance.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# Default rates for fallback
DEFAULT_MATIC_INR_RATE = 80.0  # INR per MATIC
DEFAULT_GAS_PRICE_GWEI = 30.0  # Gwei


@dataclass
class GasEstimate:
    """
    Gas estimate for a transaction type.

    Attributes:
        tx_type: Type of transaction
        gas_used: Estimated gas units
        gas_price_gwei: Gas price in Gwei
        cost_matic: Cost in MATIC
        cost_inr: Cost in INR
    """
    tx_type: str
    gas_used: int
    gas_price_gwei: float
    cost_matic: float
    cost_inr: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tx_type": self.tx_type,
            "gas_used": self.gas_used,
            "gas_price_gwei": float(self.gas_price_gwei),
            "cost_matic": float(self.cost_matic),
            "cost_inr": float(self.cost_inr),
        }


@dataclass
class GasCostStatistics:
    """
    Aggregate gas cost statistics.

    Attributes:
        mean_cost_inr: Mean cost in INR
        std_cost_inr: Standard deviation
        min_cost_inr: Minimum cost
        max_cost_inr: Maximum cost
        median_cost_inr: Median cost
        total_cost_inr: Total cost
        num_transactions: Number of transactions
        by_tx_type: Statistics broken down by transaction type
    """
    mean_cost_inr: float
    std_cost_inr: float
    min_cost_inr: float
    max_cost_inr: float
    median_cost_inr: float
    total_cost_inr: float
    num_transactions: int
    by_tx_type: Dict[str, Dict[str, float]]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_cost_inr": float(self.mean_cost_inr),
            "std_cost_inr": float(self.std_cost_inr),
            "min_cost_inr": float(self.min_cost_inr),
            "max_cost_inr": float(self.max_cost_inr),
            "median_cost_inr": float(self.median_cost_inr),
            "total_cost_inr": float(self.total_cost_inr),
            "num_transactions": self.num_transactions,
            "by_tx_type": self.by_tx_type,
        }


# Typical gas usage for different transaction types
GAS_ESTIMATES = {
    "erc20_transfer": 65000,
    "erc20_approve": 46000,
    "bid_submit": 100000,
    "ask_submit": 100000,
    "order_cancel": 50000,
    "trade_settlement": 150000,
    "batch_settlement": 300000,
    "market_clear": 200000,
    "register_participant": 120000,
    "update_balance": 80000,
}


class GasCostTracker:
    """
    Track and analyze blockchain gas costs.

    Integrates with Yahoo Finance for live MATIC/INR rates.
    """

    def __init__(
        self,
        fetch_live_rate: bool = True,
        fallback_rate: float = DEFAULT_MATIC_INR_RATE,
        default_gas_price_gwei: float = DEFAULT_GAS_PRICE_GWEI,
    ):
        """
        Initialize gas cost tracker.

        Args:
            fetch_live_rate: Whether to fetch live exchange rate
            fallback_rate: Fallback MATIC/INR rate if fetch fails
            default_gas_price_gwei: Default gas price in Gwei
        """
        self.fallback_rate = fallback_rate
        self.default_gas_price_gwei = default_gas_price_gwei
        self._rate_cache: Optional[Tuple[float, float]] = None  # (rate, timestamp)
        self._cache_duration = 300  # 5 minutes

        self.transactions: List[GasEstimate] = []
        self._costs_by_type: Dict[str, List[float]] = {}

        if fetch_live_rate:
            self.matic_inr_rate = self._fetch_matic_rate()
        else:
            self.matic_inr_rate = fallback_rate

    def _fetch_matic_rate(self) -> float:
        """
        Fetch current MATIC/INR rate from Yahoo Finance.

        Returns:
            MATIC/INR exchange rate
        """
        # Check cache
        current_time = time.time()
        if self._rate_cache is not None:
            cached_rate, cache_time = self._rate_cache
            if current_time - cache_time < self._cache_duration:
                return cached_rate

        try:
            import yfinance as yf

            # Try MATIC-INR directly
            ticker = yf.Ticker("MATIC-INR")
            info = ticker.info

            rate = info.get('regularMarketPrice')
            if rate is None:
                rate = info.get('previousClose')

            if rate is not None and rate > 0:
                self._rate_cache = (float(rate), current_time)
                logger.info(f"Fetched MATIC/INR rate: {rate}")
                return float(rate)

            # Try via USD
            matic_usd = yf.Ticker("MATIC-USD")
            usd_inr = yf.Ticker("USDINR=X")

            matic_price = matic_usd.info.get('regularMarketPrice', 0.8)
            inr_rate = usd_inr.info.get('regularMarketPrice', 83.0)

            if matic_price and inr_rate:
                rate = matic_price * inr_rate
                self._rate_cache = (float(rate), current_time)
                logger.info(f"Calculated MATIC/INR rate via USD: {rate}")
                return float(rate)

        except ImportError:
            logger.warning("yfinance not installed, using fallback rate")
        except Exception as e:
            logger.warning(f"Failed to fetch MATIC rate: {e}, using fallback")

        return self.fallback_rate

    def refresh_rate(self) -> float:
        """
        Force refresh of exchange rate.

        Returns:
            Updated MATIC/INR rate
        """
        self._rate_cache = None
        self.matic_inr_rate = self._fetch_matic_rate()
        return self.matic_inr_rate

    def calculate_transaction_cost(
        self,
        gas_used: int,
        gas_price_gwei: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Calculate transaction cost in MATIC and INR.

        Cost = gas_used * gas_price * MATIC_INR / 1e9

        Args:
            gas_used: Gas units consumed
            gas_price_gwei: Gas price in Gwei (uses default if None)

        Returns:
            Tuple of (cost_matic, cost_inr)
        """
        if gas_price_gwei is None:
            gas_price_gwei = self.default_gas_price_gwei

        # Cost in MATIC: gas_used * gas_price_gwei / 1e9 (Gwei to MATIC)
        cost_matic = gas_used * gas_price_gwei / 1e9

        # Cost in INR
        cost_inr = cost_matic * self.matic_inr_rate

        return (cost_matic, cost_inr)

    def estimate_transaction_cost(
        self,
        tx_type: str,
        gas_price_gwei: Optional[float] = None,
    ) -> GasEstimate:
        """
        Estimate cost for a transaction type.

        Args:
            tx_type: Type of transaction
            gas_price_gwei: Gas price in Gwei

        Returns:
            GasEstimate with cost details
        """
        if tx_type not in GAS_ESTIMATES:
            logger.warning(f"Unknown tx type: {tx_type}, using default")
            gas_used = 100000
        else:
            gas_used = GAS_ESTIMATES[tx_type]

        if gas_price_gwei is None:
            gas_price_gwei = self.default_gas_price_gwei

        cost_matic, cost_inr = self.calculate_transaction_cost(gas_used, gas_price_gwei)

        return GasEstimate(
            tx_type=tx_type,
            gas_used=gas_used,
            gas_price_gwei=gas_price_gwei,
            cost_matic=cost_matic,
            cost_inr=cost_inr,
        )

    def estimate_settlement_cost(
        self,
        trade_value_inr: float,
        gas_price_gwei: Optional[float] = None,
    ) -> GasEstimate:
        """
        Estimate gas cost for settling a trade.

        Args:
            trade_value_inr: Value of the trade in INR
            gas_price_gwei: Gas price in Gwei

        Returns:
            GasEstimate for settlement
        """
        # Base settlement gas
        base_gas = GAS_ESTIMATES["trade_settlement"]

        # Additional gas for larger trades (more storage updates)
        if trade_value_inr > 10000:
            additional_gas = int((trade_value_inr / 10000) * 5000)
            gas_used = base_gas + min(additional_gas, 50000)
        else:
            gas_used = base_gas

        if gas_price_gwei is None:
            gas_price_gwei = self.default_gas_price_gwei

        cost_matic, cost_inr = self.calculate_transaction_cost(gas_used, gas_price_gwei)

        return GasEstimate(
            tx_type="trade_settlement",
            gas_used=gas_used,
            gas_price_gwei=gas_price_gwei,
            cost_matic=cost_matic,
            cost_inr=cost_inr,
        )

    def record_transaction(
        self,
        tx_type: str,
        gas_used: int,
        gas_price_gwei: Optional[float] = None,
    ) -> GasEstimate:
        """
        Record an actual transaction cost.

        Args:
            tx_type: Type of transaction
            gas_used: Actual gas used
            gas_price_gwei: Actual gas price

        Returns:
            GasEstimate for the recorded transaction
        """
        if gas_price_gwei is None:
            gas_price_gwei = self.default_gas_price_gwei

        cost_matic, cost_inr = self.calculate_transaction_cost(gas_used, gas_price_gwei)

        estimate = GasEstimate(
            tx_type=tx_type,
            gas_used=gas_used,
            gas_price_gwei=gas_price_gwei,
            cost_matic=cost_matic,
            cost_inr=cost_inr,
        )

        self.transactions.append(estimate)

        # Track by type
        if tx_type not in self._costs_by_type:
            self._costs_by_type[tx_type] = []
        self._costs_by_type[tx_type].append(cost_inr)

        return estimate

    def get_statistics(self) -> GasCostStatistics:
        """
        Calculate aggregate gas cost statistics.

        Returns:
            GasCostStatistics with aggregated metrics
        """
        if not self.transactions:
            return GasCostStatistics(
                mean_cost_inr=0, std_cost_inr=0, min_cost_inr=0,
                max_cost_inr=0, median_cost_inr=0, total_cost_inr=0,
                num_transactions=0, by_tx_type={},
            )

        costs = np.array([t.cost_inr for t in self.transactions])

        # Per-type statistics
        by_type = {}
        for tx_type, type_costs in self._costs_by_type.items():
            if type_costs:
                arr = np.array(type_costs)
                by_type[tx_type] = {
                    "mean": float(np.mean(arr)),
                    "std": float(np.std(arr)),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                    "count": len(arr),
                    "total": float(np.sum(arr)),
                }

        return GasCostStatistics(
            mean_cost_inr=float(np.mean(costs)),
            std_cost_inr=float(np.std(costs)),
            min_cost_inr=float(np.min(costs)),
            max_cost_inr=float(np.max(costs)),
            median_cost_inr=float(np.median(costs)),
            total_cost_inr=float(np.sum(costs)),
            num_transactions=len(costs),
            by_tx_type=by_type,
        )

    def check_cost_threshold(
        self,
        threshold_inr: float = 1.0,
    ) -> Tuple[bool, float]:
        """
        Check if mean cost is below threshold.

        Args:
            threshold_inr: Cost threshold in INR

        Returns:
            Tuple of (is_below_threshold, mean_cost)
        """
        if not self.transactions:
            return (True, 0.0)

        costs = [t.cost_inr for t in self.transactions]
        mean_cost = np.mean(costs)

        return (mean_cost < threshold_inr, float(mean_cost))

    def estimate_daily_costs(
        self,
        daily_transactions: int,
        tx_type_distribution: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Estimate daily operational costs.

        Args:
            daily_transactions: Expected daily transaction count
            tx_type_distribution: Distribution of transaction types

        Returns:
            Estimated daily cost in INR
        """
        if tx_type_distribution is None:
            tx_type_distribution = {
                "bid_submit": 0.30,
                "ask_submit": 0.30,
                "order_cancel": 0.10,
                "trade_settlement": 0.20,
                "update_balance": 0.10,
            }

        total_cost = 0.0

        for tx_type, fraction in tx_type_distribution.items():
            n_txs = int(daily_transactions * fraction)
            estimate = self.estimate_transaction_cost(tx_type)
            total_cost += n_txs * estimate.cost_inr

        return total_cost

    def clear(self):
        """Clear all recorded transactions."""
        self.transactions = []
        self._costs_by_type = {}


def simulate_gas_costs(
    n_transactions: int,
    tx_type_distribution: Optional[Dict[str, float]] = None,
    gas_price_mean_gwei: float = 30.0,
    gas_price_std_gwei: float = 10.0,
    matic_inr_rate: float = 80.0,
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, GasCostStatistics]:
    """
    Simulate gas cost samples.

    Args:
        n_transactions: Number of transactions to simulate
        tx_type_distribution: Distribution of transaction types
        gas_price_mean_gwei: Mean gas price
        gas_price_std_gwei: Gas price standard deviation
        matic_inr_rate: MATIC/INR exchange rate
        seed: Random seed

    Returns:
        Tuple of (cost array in INR, statistics)
    """
    rng = np.random.default_rng(seed)

    if tx_type_distribution is None:
        tx_type_distribution = {
            "bid_submit": 0.30,
            "ask_submit": 0.30,
            "order_cancel": 0.10,
            "trade_settlement": 0.20,
            "update_balance": 0.10,
        }

    tx_types = list(tx_type_distribution.keys())
    tx_probs = list(tx_type_distribution.values())

    costs = []
    costs_by_type: Dict[str, List[float]] = {t: [] for t in tx_types}

    for _ in range(n_transactions):
        # Select transaction type
        tx_type = rng.choice(tx_types, p=tx_probs)

        # Get base gas with variation
        base_gas = GAS_ESTIMATES.get(tx_type, 100000)
        gas_used = int(rng.normal(base_gas, base_gas * 0.1))
        gas_used = max(gas_used, 21000)  # Minimum gas

        # Gas price variation
        gas_price = rng.normal(gas_price_mean_gwei, gas_price_std_gwei)
        gas_price = max(gas_price, 1.0)

        # Calculate cost
        cost_matic = gas_used * gas_price / 1e9
        cost_inr = cost_matic * matic_inr_rate

        costs.append(cost_inr)
        costs_by_type[tx_type].append(cost_inr)

    costs_arr = np.array(costs)

    # Calculate statistics
    by_type = {}
    for tx_type, type_costs in costs_by_type.items():
        if type_costs:
            arr = np.array(type_costs)
            by_type[tx_type] = {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "count": len(arr),
                "total": float(np.sum(arr)),
            }

    stats = GasCostStatistics(
        mean_cost_inr=float(np.mean(costs_arr)),
        std_cost_inr=float(np.std(costs_arr)),
        min_cost_inr=float(np.min(costs_arr)),
        max_cost_inr=float(np.max(costs_arr)),
        median_cost_inr=float(np.median(costs_arr)),
        total_cost_inr=float(np.sum(costs_arr)),
        num_transactions=n_transactions,
        by_tx_type=by_type,
    )

    return costs_arr, stats
