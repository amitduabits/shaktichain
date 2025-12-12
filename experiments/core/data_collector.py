"""
Data Collector - Comprehensive metrics collection for SHAKTI-CHAIN experiments.

Collects bids, trades, welfare metrics, token metrics, and latency measurements
at each clearing round.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""
    BID = "bid"
    TRADE = "trade"
    CLEARING = "clearing"
    WELFARE = "welfare"
    TOKEN = "token"
    LATENCY = "latency"
    AGENT_STATE = "agent_state"
    MARKET_STATE = "market_state"


@dataclass
class Bid:
    """Represents a single bid in the market."""
    bid_id: str
    agent_id: str
    agent_type: str
    price: float
    quantity: float
    side: str  # "buy" or "sell"
    timestamp: float
    period: int
    run_index: int

    # Optional metadata
    is_aggressive: bool = False
    latency_ms: float = 0.0
    was_filled: bool = False
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "bid_id": self.bid_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side,
            "timestamp": self.timestamp,
            "period": self.period,
            "run_index": self.run_index,
            "is_aggressive": self.is_aggressive,
            "latency_ms": self.latency_ms,
            "was_filled": self.was_filled,
            "fill_price": self.fill_price,
            "fill_quantity": self.fill_quantity,
        }


@dataclass
class Trade:
    """Represents a single executed trade."""
    trade_id: str
    buyer_id: str
    seller_id: str
    buyer_type: str
    seller_type: str
    price: float
    quantity: float
    timestamp: float
    period: int
    run_index: int

    # Transaction details
    tx_hash: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price_gwei: Optional[float] = None

    # Welfare
    buyer_surplus: float = 0.0
    seller_surplus: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "buyer_type": self.buyer_type,
            "seller_type": self.seller_type,
            "price": self.price,
            "quantity": self.quantity,
            "timestamp": self.timestamp,
            "period": self.period,
            "run_index": self.run_index,
            "tx_hash": self.tx_hash,
            "gas_used": self.gas_used,
            "gas_price_gwei": self.gas_price_gwei,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
        }


@dataclass
class ClearingResult:
    """Result of a market clearing round."""
    period: int
    run_index: int
    timestamp: float
    clearing_price: float
    clearing_quantity: float
    num_bids: int
    num_asks: int
    num_trades: int
    matched_volume: float
    unmatched_buy_volume: float
    unmatched_sell_volume: float

    # Price statistics
    bid_price_mean: float = 0.0
    bid_price_std: float = 0.0
    ask_price_mean: float = 0.0
    ask_price_std: float = 0.0
    spread: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "run_index": self.run_index,
            "timestamp": self.timestamp,
            "clearing_price": self.clearing_price,
            "clearing_quantity": self.clearing_quantity,
            "num_bids": self.num_bids,
            "num_asks": self.num_asks,
            "num_trades": self.num_trades,
            "matched_volume": self.matched_volume,
            "unmatched_buy_volume": self.unmatched_buy_volume,
            "unmatched_sell_volume": self.unmatched_sell_volume,
            "bid_price_mean": self.bid_price_mean,
            "bid_price_std": self.bid_price_std,
            "ask_price_mean": self.ask_price_mean,
            "ask_price_std": self.ask_price_std,
            "spread": self.spread,
        }


@dataclass
class WelfareMetrics:
    """Welfare metrics for a clearing period."""
    period: int
    run_index: int
    buyer_surplus: float
    seller_surplus: float
    total_surplus: float
    theoretical_maximum: float
    allocative_efficiency: float

    # By agent type
    surplus_by_type: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "run_index": self.run_index,
            "buyer_surplus": self.buyer_surplus,
            "seller_surplus": self.seller_surplus,
            "total_surplus": self.total_surplus,
            "theoretical_maximum": self.theoretical_maximum,
            "allocative_efficiency": self.allocative_efficiency,
            "surplus_by_type": self.surplus_by_type,
        }


@dataclass
class TokenMetrics:
    """SHAKTI token metrics for a period."""
    period: int
    run_index: int
    total_supply: float
    circulating_supply: float
    tokens_minted: float
    tokens_burned: float
    velocity: float  # Transactions / supply
    price_inr: float
    market_cap_inr: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "run_index": self.run_index,
            "total_supply": self.total_supply,
            "circulating_supply": self.circulating_supply,
            "tokens_minted": self.tokens_minted,
            "tokens_burned": self.tokens_burned,
            "velocity": self.velocity,
            "price_inr": self.price_inr,
            "market_cap_inr": self.market_cap_inr,
        }


@dataclass
class LatencyMetrics:
    """Latency measurements for a period."""
    period: int
    run_index: int
    bid_submission_ms: list[float] = field(default_factory=list)
    order_matching_ms: float = 0.0
    trade_execution_ms: float = 0.0
    settlement_ms: float = 0.0
    total_clearing_ms: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "run_index": self.run_index,
            "bid_submission_ms": {
                "mean": float(np.mean(self.bid_submission_ms)) if self.bid_submission_ms else 0,
                "std": float(np.std(self.bid_submission_ms)) if self.bid_submission_ms else 0,
                "p50": float(np.percentile(self.bid_submission_ms, 50)) if self.bid_submission_ms else 0,
                "p95": float(np.percentile(self.bid_submission_ms, 95)) if self.bid_submission_ms else 0,
                "p99": float(np.percentile(self.bid_submission_ms, 99)) if self.bid_submission_ms else 0,
            },
            "order_matching_ms": self.order_matching_ms,
            "trade_execution_ms": self.trade_execution_ms,
            "settlement_ms": self.settlement_ms,
            "total_clearing_ms": self.total_clearing_ms,
        }


class MetricsBuffer:
    """
    In-memory buffer for metrics with periodic flushing to disk.

    Efficiently accumulates metrics in memory and periodically
    writes them to parquet files for persistence.
    """

    def __init__(
        self,
        output_dir: Path,
        flush_interval: int = 100,  # Flush every N periods
        buffer_size: int = 10000,   # Max items before forced flush
    ):
        self.output_dir = Path(output_dir)
        self.flush_interval = flush_interval
        self.buffer_size = buffer_size

        # Buffers for each metric type
        self.bids: list[Bid] = []
        self.trades: list[Trade] = []
        self.clearing_results: list[ClearingResult] = []
        self.welfare_metrics: list[WelfareMetrics] = []
        self.token_metrics: list[TokenMetrics] = []
        self.latency_metrics: list[LatencyMetrics] = []
        self.agent_states: list[dict] = []
        self.market_states: list[dict] = []

        # Tracking
        self.periods_since_flush = 0
        self.total_flushed = defaultdict(int)

    def add_bid(self, bid: Bid) -> None:
        """Add a bid to the buffer."""
        self.bids.append(bid)
        self._check_buffer_size()

    def add_bids(self, bids: list[Bid]) -> None:
        """Add multiple bids to the buffer."""
        self.bids.extend(bids)
        self._check_buffer_size()

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the buffer."""
        self.trades.append(trade)
        self._check_buffer_size()

    def add_trades(self, trades: list[Trade]) -> None:
        """Add multiple trades to the buffer."""
        self.trades.extend(trades)
        self._check_buffer_size()

    def add_clearing_result(self, result: ClearingResult) -> None:
        """Add a clearing result to the buffer."""
        self.clearing_results.append(result)
        self.periods_since_flush += 1

        if self.periods_since_flush >= self.flush_interval:
            self.flush()

    def add_welfare_metrics(self, metrics: WelfareMetrics) -> None:
        """Add welfare metrics to the buffer."""
        self.welfare_metrics.append(metrics)

    def add_token_metrics(self, metrics: TokenMetrics) -> None:
        """Add token metrics to the buffer."""
        self.token_metrics.append(metrics)

    def add_latency_metrics(self, metrics: LatencyMetrics) -> None:
        """Add latency metrics to the buffer."""
        self.latency_metrics.append(metrics)

    def add_agent_state(self, state: dict) -> None:
        """Add an agent state snapshot."""
        self.agent_states.append(state)
        self._check_buffer_size()

    def add_market_state(self, state: dict) -> None:
        """Add a market state snapshot."""
        self.market_states.append(state)

    def _check_buffer_size(self) -> None:
        """Check if any buffer exceeds the limit."""
        if (
            len(self.bids) > self.buffer_size or
            len(self.trades) > self.buffer_size or
            len(self.agent_states) > self.buffer_size
        ):
            self.flush()

    def flush(self) -> None:
        """Flush all buffers to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Flush bids
        if self.bids:
            self._flush_to_parquet(
                [b.to_dict() for b in self.bids],
                self.output_dir / "raw_data" / f"bids_{timestamp}.parquet",
            )
            self.total_flushed["bids"] += len(self.bids)
            self.bids = []

        # Flush trades
        if self.trades:
            self._flush_to_parquet(
                [t.to_dict() for t in self.trades],
                self.output_dir / "raw_data" / f"trades_{timestamp}.parquet",
            )
            self.total_flushed["trades"] += len(self.trades)
            self.trades = []

        # Flush clearing results
        if self.clearing_results:
            self._flush_to_parquet(
                [c.to_dict() for c in self.clearing_results],
                self.output_dir / "raw_data" / f"market_state_{timestamp}.parquet",
            )
            self.total_flushed["clearing"] += len(self.clearing_results)
            self.clearing_results = []

        # Flush welfare metrics
        if self.welfare_metrics:
            self._flush_to_json(
                [w.to_dict() for w in self.welfare_metrics],
                self.output_dir / "metrics" / f"welfare_{timestamp}.json",
            )
            self.total_flushed["welfare"] += len(self.welfare_metrics)
            self.welfare_metrics = []

        # Flush token metrics
        if self.token_metrics:
            self._flush_to_json(
                [t.to_dict() for t in self.token_metrics],
                self.output_dir / "metrics" / f"token_{timestamp}.json",
            )
            self.total_flushed["token"] += len(self.token_metrics)
            self.token_metrics = []

        # Flush latency metrics
        if self.latency_metrics:
            self._flush_to_json(
                [l.to_dict() for l in self.latency_metrics],
                self.output_dir / "metrics" / f"latency_{timestamp}.json",
            )
            self.total_flushed["latency"] += len(self.latency_metrics)
            self.latency_metrics = []

        # Flush agent states
        if self.agent_states:
            self._flush_to_parquet(
                self.agent_states,
                self.output_dir / "raw_data" / f"agent_states_{timestamp}.parquet",
            )
            self.total_flushed["agent_states"] += len(self.agent_states)
            self.agent_states = []

        # Flush market states
        if self.market_states:
            self._flush_to_json(
                self.market_states,
                self.output_dir / "raw_data" / f"market_states_{timestamp}.json",
            )
            self.total_flushed["market_states"] += len(self.market_states)
            self.market_states = []

        self.periods_since_flush = 0
        logger.debug(f"Flushed metrics to disk: {dict(self.total_flushed)}")

    def _flush_to_parquet(self, data: list[dict], path: Path) -> None:
        """Write data to parquet file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(data)
        df.to_parquet(path, compression="snappy", index=False)

    def _flush_to_json(self, data: list[dict], path: Path) -> None:
        """Write data to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_stats(self) -> dict:
        """Get buffer statistics."""
        return {
            "buffered": {
                "bids": len(self.bids),
                "trades": len(self.trades),
                "clearing_results": len(self.clearing_results),
                "welfare_metrics": len(self.welfare_metrics),
                "token_metrics": len(self.token_metrics),
                "latency_metrics": len(self.latency_metrics),
                "agent_states": len(self.agent_states),
                "market_states": len(self.market_states),
            },
            "total_flushed": dict(self.total_flushed),
        }


class DataCollector:
    """
    Main data collection interface for experiments.

    Provides high-level methods for collecting all metrics
    during experiment execution.
    """

    def __init__(
        self,
        experiment_id: str,
        output_dir: Path,
        config: Optional[dict] = None,
    ):
        self.experiment_id = experiment_id
        self.output_dir = Path(output_dir)
        self.config = config or {}

        # Initialize buffer
        self.buffer = MetricsBuffer(
            output_dir=self.output_dir,
            flush_interval=self.config.get("flush_interval", 100),
            buffer_size=self.config.get("buffer_size", 10000),
        )

        # Timing
        self._period_start_time: Optional[float] = None
        self._clearing_start_time: Optional[float] = None

        # Counters
        self._bid_counter = 0
        self._trade_counter = 0

    def start_period(self, period: int, run_index: int) -> None:
        """Mark the start of a new period."""
        self._period_start_time = time.time()
        self._current_period = period
        self._current_run = run_index

    def collect_bid(
        self,
        agent_id: str,
        agent_type: str,
        price: float,
        quantity: float,
        side: str,
        latency_ms: float = 0.0,
    ) -> str:
        """
        Collect a bid submission.

        Returns the bid_id for later reference.
        """
        self._bid_counter += 1
        bid_id = f"bid_{self._current_run}_{self._current_period}_{self._bid_counter}"

        bid = Bid(
            bid_id=bid_id,
            agent_id=agent_id,
            agent_type=agent_type,
            price=price,
            quantity=quantity,
            side=side,
            timestamp=time.time(),
            period=self._current_period,
            run_index=self._current_run,
            latency_ms=latency_ms,
        )

        self.buffer.add_bid(bid)
        return bid_id

    def collect_bids_batch(self, bids_data: list[dict]) -> list[str]:
        """
        Collect multiple bids efficiently.

        Args:
            bids_data: List of dicts with bid information

        Returns:
            List of bid_ids
        """
        bid_ids = []
        bids = []

        for data in bids_data:
            self._bid_counter += 1
            bid_id = f"bid_{self._current_run}_{self._current_period}_{self._bid_counter}"
            bid_ids.append(bid_id)

            bid = Bid(
                bid_id=bid_id,
                agent_id=data["agent_id"],
                agent_type=data["agent_type"],
                price=data["price"],
                quantity=data["quantity"],
                side=data["side"],
                timestamp=time.time(),
                period=self._current_period,
                run_index=self._current_run,
                latency_ms=data.get("latency_ms", 0.0),
            )
            bids.append(bid)

        self.buffer.add_bids(bids)
        return bid_ids

    def start_clearing(self) -> None:
        """Mark the start of the clearing process."""
        self._clearing_start_time = time.time()

    def collect_clearing_result(
        self,
        clearing_price: float,
        clearing_quantity: float,
        num_bids: int,
        num_asks: int,
        trades: list[dict],
        order_book_stats: Optional[dict] = None,
    ) -> None:
        """Collect the result of a clearing round."""
        clearing_time = time.time()

        # Calculate volumes
        matched_volume = sum(t.get("quantity", 0) for t in trades)

        order_book_stats = order_book_stats or {}

        result = ClearingResult(
            period=self._current_period,
            run_index=self._current_run,
            timestamp=clearing_time,
            clearing_price=clearing_price,
            clearing_quantity=clearing_quantity,
            num_bids=num_bids,
            num_asks=num_asks,
            num_trades=len(trades),
            matched_volume=matched_volume,
            unmatched_buy_volume=order_book_stats.get("unmatched_buy_volume", 0),
            unmatched_sell_volume=order_book_stats.get("unmatched_sell_volume", 0),
            bid_price_mean=order_book_stats.get("bid_price_mean", 0),
            bid_price_std=order_book_stats.get("bid_price_std", 0),
            ask_price_mean=order_book_stats.get("ask_price_mean", 0),
            ask_price_std=order_book_stats.get("ask_price_std", 0),
            spread=order_book_stats.get("spread", 0),
        )

        self.buffer.add_clearing_result(result)

        # Collect individual trades
        for trade_data in trades:
            self._trade_counter += 1
            trade_id = f"trade_{self._current_run}_{self._current_period}_{self._trade_counter}"

            trade = Trade(
                trade_id=trade_id,
                buyer_id=trade_data["buyer_id"],
                seller_id=trade_data["seller_id"],
                buyer_type=trade_data.get("buyer_type", "unknown"),
                seller_type=trade_data.get("seller_type", "unknown"),
                price=trade_data["price"],
                quantity=trade_data["quantity"],
                timestamp=clearing_time,
                period=self._current_period,
                run_index=self._current_run,
                tx_hash=trade_data.get("tx_hash"),
                gas_used=trade_data.get("gas_used"),
                gas_price_gwei=trade_data.get("gas_price_gwei"),
                buyer_surplus=trade_data.get("buyer_surplus", 0),
                seller_surplus=trade_data.get("seller_surplus", 0),
            )

            self.buffer.add_trade(trade)

    def collect_welfare_metrics(
        self,
        buyer_surplus: float,
        seller_surplus: float,
        theoretical_maximum: float,
        surplus_by_type: Optional[dict] = None,
    ) -> None:
        """Collect welfare metrics for the current period."""
        total_surplus = buyer_surplus + seller_surplus
        efficiency = total_surplus / theoretical_maximum if theoretical_maximum > 0 else 0

        metrics = WelfareMetrics(
            period=self._current_period,
            run_index=self._current_run,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            total_surplus=total_surplus,
            theoretical_maximum=theoretical_maximum,
            allocative_efficiency=efficiency,
            surplus_by_type=surplus_by_type or {},
        )

        self.buffer.add_welfare_metrics(metrics)

    def collect_token_metrics(
        self,
        total_supply: float,
        circulating_supply: float,
        tokens_minted: float,
        tokens_burned: float,
        num_transactions: int,
        price_inr: float,
    ) -> None:
        """Collect SHAKTI token metrics."""
        velocity = num_transactions / circulating_supply if circulating_supply > 0 else 0

        metrics = TokenMetrics(
            period=self._current_period,
            run_index=self._current_run,
            total_supply=total_supply,
            circulating_supply=circulating_supply,
            tokens_minted=tokens_minted,
            tokens_burned=tokens_burned,
            velocity=velocity,
            price_inr=price_inr,
            market_cap_inr=circulating_supply * price_inr,
        )

        self.buffer.add_token_metrics(metrics)

    def collect_latency_metrics(
        self,
        bid_submission_times: list[float],
        order_matching_ms: float,
        trade_execution_ms: float,
        settlement_ms: float,
    ) -> None:
        """Collect latency metrics for the period."""
        total_clearing_ms = order_matching_ms + trade_execution_ms + settlement_ms

        metrics = LatencyMetrics(
            period=self._current_period,
            run_index=self._current_run,
            bid_submission_ms=bid_submission_times,
            order_matching_ms=order_matching_ms,
            trade_execution_ms=trade_execution_ms,
            settlement_ms=settlement_ms,
            total_clearing_ms=total_clearing_ms,
        )

        self.buffer.add_latency_metrics(metrics)

    def collect_agent_states(self, agents: list[Any]) -> None:
        """
        Collect state snapshots from all agents.

        Args:
            agents: List of agent objects with state attribute
        """
        for agent in agents:
            state = {
                "period": self._current_period,
                "run_index": self._current_run,
                "timestamp": time.time(),
                "agent_id": agent.state.id,
                "agent_type": agent.state.type,
                "battery_capacity_kwh": agent.state.battery_capacity_kwh,
                "current_soc": agent.state.current_soc,
                "cumulative_profit": agent.state.cumulative_profit,
                "num_trades": len(agent.state.historical_trades),
            }
            self.buffer.add_agent_state(state)

    def collect_market_state(
        self,
        order_book: dict,
        price_history: list[float],
        volume_history: list[float],
    ) -> None:
        """Collect market state snapshot."""
        state = {
            "period": self._current_period,
            "run_index": self._current_run,
            "timestamp": time.time(),
            "order_book": order_book,
            "price_history": price_history[-100:],  # Last 100 prices
            "volume_history": volume_history[-100:],
        }
        self.buffer.add_market_state(state)

    def end_period(self) -> dict:
        """
        Mark the end of a period and return timing info.

        Returns:
            Dictionary with period duration and other timing info
        """
        end_time = time.time()
        period_duration = end_time - self._period_start_time if self._period_start_time else 0

        return {
            "period": self._current_period,
            "run_index": self._current_run,
            "duration_seconds": period_duration,
            "bids_collected": self._bid_counter,
            "trades_collected": self._trade_counter,
        }

    def finalize(self) -> dict:
        """
        Finalize data collection and flush all remaining data.

        Returns:
            Final statistics
        """
        self.buffer.flush()
        return self.buffer.get_stats()

    def get_summary(self) -> dict:
        """Get summary of collected data."""
        stats = self.buffer.get_stats()
        return {
            "experiment_id": self.experiment_id,
            "current_period": getattr(self, "_current_period", 0),
            "current_run": getattr(self, "_current_run", 0),
            "total_bids": self._bid_counter,
            "total_trades": self._trade_counter,
            "buffer_stats": stats,
        }
