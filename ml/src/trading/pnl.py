"""P&L tracking and reporting for SHAKTI-CHAIN trading.

Provides:
- Trade-by-trade P&L calculation
- Daily, weekly, monthly reports
- Performance metrics (Sharpe, drawdown)
- Gas cost tracking
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    trade_id: str
    timestamp: datetime
    action_type: str  # buy, sell
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    fees: float = 0.0
    gas_cost: float = 0.0
    is_closed: bool = False
    close_timestamp: Optional[datetime] = None

    @property
    def net_pnl(self) -> float:
        """Calculate net P&L after fees and gas."""
        return self.realized_pnl - self.fees - self.gas_cost

    @property
    def holding_period_hours(self) -> Optional[float]:
        """Calculate holding period in hours."""
        if self.close_timestamp:
            return (self.close_timestamp - self.timestamp).total_seconds() / 3600
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "net_pnl": self.net_pnl,
            "fees": self.fees,
            "gas_cost": self.gas_cost,
            "is_closed": self.is_closed,
            "close_timestamp": self.close_timestamp.isoformat() if self.close_timestamp else None,
            "holding_period_hours": self.holding_period_hours,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeRecord":
        """Create from dictionary."""
        return cls(
            trade_id=data["trade_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action_type=data["action_type"],
            quantity=data["quantity"],
            entry_price=data["entry_price"],
            exit_price=data.get("exit_price"),
            realized_pnl=data.get("realized_pnl", 0),
            unrealized_pnl=data.get("unrealized_pnl", 0),
            fees=data.get("fees", 0),
            gas_cost=data.get("gas_cost", 0),
            is_closed=data.get("is_closed", False),
            close_timestamp=datetime.fromisoformat(data["close_timestamp"]) if data.get("close_timestamp") else None,
        )


@dataclass
class PnLReport:
    """P&L report for a time period."""
    period_start: datetime
    period_end: datetime
    period_name: str  # daily, weekly, monthly

    # P&L summary
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    fees_paid: float = 0.0
    gas_cost: float = 0.0
    net_pnl: float = 0.0

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # Volume
    total_volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0

    # Performance metrics
    sharpe_ratio: Optional[float] = None
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_trade_pnl: float = 0.0
    profit_factor: float = 0.0

    # Best/worst
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    largest_position: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_name": self.period_name,
            "pnl": {
                "total": self.total_pnl,
                "realized": self.realized_pnl,
                "unrealized": self.unrealized_pnl,
                "fees": self.fees_paid,
                "gas": self.gas_cost,
                "net": self.net_pnl,
            },
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "win_rate": self.win_rate,
            },
            "volume": {
                "total": self.total_volume,
                "buy": self.buy_volume,
                "sell": self.sell_volume,
            },
            "performance": {
                "sharpe_ratio": self.sharpe_ratio,
                "max_drawdown": self.max_drawdown,
                "max_drawdown_pct": self.max_drawdown_pct,
                "avg_trade_pnl": self.avg_trade_pnl,
                "profit_factor": self.profit_factor,
            },
            "extremes": {
                "best_trade": self.best_trade_pnl,
                "worst_trade": self.worst_trade_pnl,
                "largest_position": self.largest_position,
            },
        }


class PnLTracker:
    """Track P&L for trading operations."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        initial_capital: float = 100000.0,
    ):
        """Initialize P&L tracker.

        Args:
            storage_path: Path for persistent storage
            initial_capital: Starting capital
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.initial_capital = initial_capital

        # Trade records
        self._trades: List[TradeRecord] = []
        self._open_positions: Dict[str, TradeRecord] = {}

        # Running totals
        self._total_pnl: float = 0.0
        self._total_fees: float = 0.0
        self._total_gas: float = 0.0
        self._current_capital: float = initial_capital

        # Equity curve for drawdown calculation
        self._equity_curve: List[tuple] = [(datetime.now(), initial_capital)]

        # Trade counter
        self._trade_counter = 0

        # Load from storage
        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self):
        """Load from storage."""
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                self._trades = [TradeRecord.from_dict(t) for t in data.get("trades", [])]
                self._total_pnl = data.get("total_pnl", 0)
                self._total_fees = data.get("total_fees", 0)
                self._total_gas = data.get("total_gas", 0)
                self._current_capital = data.get("current_capital", self.initial_capital)
                self._trade_counter = data.get("trade_counter", 0)
            logger.info(f"Loaded {len(self._trades)} trades from storage")
        except Exception as e:
            logger.error(f"Failed to load P&L data: {e}")

    def _save(self):
        """Save to storage."""
        if not self.storage_path:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.storage_path, "w") as f:
                data = {
                    "trades": [t.to_dict() for t in self._trades],
                    "total_pnl": self._total_pnl,
                    "total_fees": self._total_fees,
                    "total_gas": self._total_gas,
                    "current_capital": self._current_capital,
                    "trade_counter": self._trade_counter,
                    "saved_at": datetime.now().isoformat(),
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save P&L data: {e}")

    def record_trade(
        self,
        action_type: str,
        quantity: float,
        price: float,
        fees: float = 0.0,
        gas_cost: float = 0.0,
        trade_id: Optional[str] = None,
    ) -> TradeRecord:
        """Record a new trade.

        Args:
            action_type: Type of action (buy/sell)
            quantity: Trade quantity
            price: Trade price
            fees: Trading fees
            gas_cost: Gas cost in tokens
            trade_id: Optional trade ID

        Returns:
            TradeRecord
        """
        self._trade_counter += 1
        trade_id = trade_id or f"trade-{self._trade_counter}"

        trade = TradeRecord(
            trade_id=trade_id,
            timestamp=datetime.now(),
            action_type=action_type,
            quantity=quantity,
            entry_price=price,
            fees=fees,
            gas_cost=gas_cost,
        )

        self._trades.append(trade)
        self._total_fees += fees
        self._total_gas += gas_cost

        # Update equity curve
        self._update_equity()

        # Save periodically
        if len(self._trades) % 10 == 0:
            self._save()

        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        fees: float = 0.0,
        gas_cost: float = 0.0,
    ) -> Optional[TradeRecord]:
        """Close an open trade.

        Args:
            trade_id: Trade to close
            exit_price: Exit price
            fees: Closing fees
            gas_cost: Gas cost

        Returns:
            Updated trade record or None
        """
        # Find trade
        trade = next((t for t in self._trades if t.trade_id == trade_id and not t.is_closed), None)

        if not trade:
            logger.warning(f"Trade {trade_id} not found or already closed")
            return None

        # Calculate P&L
        if trade.action_type == "buy":
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:  # sell (short)
            pnl = (trade.entry_price - exit_price) * trade.quantity

        trade.exit_price = exit_price
        trade.realized_pnl = pnl
        trade.fees += fees
        trade.gas_cost += gas_cost
        trade.is_closed = True
        trade.close_timestamp = datetime.now()

        # Update totals
        self._total_pnl += pnl
        self._total_fees += fees
        self._total_gas += gas_cost
        self._current_capital += trade.net_pnl

        # Update equity curve
        self._update_equity()

        self._save()

        return trade

    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized P&L for open positions.

        Args:
            current_price: Current market price
        """
        for trade in self._trades:
            if not trade.is_closed:
                if trade.action_type == "buy":
                    trade.unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
                else:
                    trade.unrealized_pnl = (trade.entry_price - current_price) * trade.quantity

        self._update_equity()

    def _update_equity(self):
        """Update equity curve."""
        unrealized = sum(t.unrealized_pnl for t in self._trades if not t.is_closed)
        equity = self._current_capital + unrealized
        self._equity_curve.append((datetime.now(), equity))

        # Keep last 10000 points
        if len(self._equity_curve) > 10000:
            self._equity_curve = self._equity_curve[-10000:]

    def generate_report(
        self,
        period: str = "daily",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> PnLReport:
        """Generate P&L report for a period.

        Args:
            period: Report period (daily, weekly, monthly, all)
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            PnLReport
        """
        now = datetime.now()

        # Determine period
        if period == "daily":
            start = start_date or now.replace(hour=0, minute=0, second=0)
            end = end_date or now
        elif period == "weekly":
            start = start_date or (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
            end = end_date or now
        elif period == "monthly":
            start = start_date or now.replace(day=1, hour=0, minute=0, second=0)
            end = end_date or now
        else:  # all
            start = start_date or datetime.min
            end = end_date or now

        # Filter trades
        trades = [
            t for t in self._trades
            if start <= t.timestamp <= end
        ]

        # Calculate metrics
        report = PnLReport(
            period_start=start,
            period_end=end,
            period_name=period,
        )

        if not trades:
            return report

        # P&L
        report.realized_pnl = sum(t.realized_pnl for t in trades if t.is_closed)
        report.unrealized_pnl = sum(t.unrealized_pnl for t in trades if not t.is_closed)
        report.total_pnl = report.realized_pnl + report.unrealized_pnl
        report.fees_paid = sum(t.fees for t in trades)
        report.gas_cost = sum(t.gas_cost for t in trades)
        report.net_pnl = report.total_pnl - report.fees_paid - report.gas_cost

        # Trade counts
        report.total_trades = len(trades)
        closed_trades = [t for t in trades if t.is_closed]
        report.winning_trades = sum(1 for t in closed_trades if t.net_pnl > 0)
        report.losing_trades = sum(1 for t in closed_trades if t.net_pnl < 0)
        report.win_rate = report.winning_trades / len(closed_trades) * 100 if closed_trades else 0

        # Volume
        report.total_volume = sum(t.quantity for t in trades)
        report.buy_volume = sum(t.quantity for t in trades if t.action_type == "buy")
        report.sell_volume = sum(t.quantity for t in trades if t.action_type == "sell")

        # Performance metrics
        if closed_trades:
            pnls = [t.net_pnl for t in closed_trades]
            report.avg_trade_pnl = sum(pnls) / len(pnls)
            report.best_trade_pnl = max(pnls)
            report.worst_trade_pnl = min(pnls)

            # Profit factor
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            report.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

            # Sharpe ratio (assuming daily)
            if len(pnls) > 1:
                avg_return = sum(pnls) / len(pnls)
                std_dev = math.sqrt(sum((p - avg_return) ** 2 for p in pnls) / len(pnls))
                if std_dev > 0:
                    report.sharpe_ratio = (avg_return / std_dev) * math.sqrt(252)  # Annualized

        # Drawdown
        report.max_drawdown, report.max_drawdown_pct = self._calculate_drawdown(start, end)

        # Largest position
        report.largest_position = max((t.quantity for t in trades), default=0)

        return report

    def _calculate_drawdown(
        self,
        start: datetime,
        end: datetime,
    ) -> tuple[float, float]:
        """Calculate maximum drawdown.

        Returns:
            Tuple of (max_drawdown_value, max_drawdown_pct)
        """
        # Filter equity curve to period
        curve = [(t, v) for t, v in self._equity_curve if start <= t <= end]

        if not curve:
            return 0.0, 0.0

        peak = curve[0][1]
        max_dd = 0.0
        max_dd_pct = 0.0

        for _, value in curve:
            if value > peak:
                peak = value
            dd = peak - value
            dd_pct = (dd / peak * 100) if peak > 0 else 0

            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def get_daily_pnl(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily P&L for recent days.

        Args:
            days: Number of days

        Returns:
            List of daily P&L records
        """
        results = []
        end = datetime.now()

        for i in range(days):
            date = end - timedelta(days=i)
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            report = self.generate_report("daily", start_of_day, end_of_day)

            results.append({
                "date": start_of_day.strftime("%Y-%m-%d"),
                "pnl": report.net_pnl,
                "trades": report.total_trades,
                "volume": report.total_volume,
                "win_rate": report.win_rate,
            })

        return list(reversed(results))

    def get_summary(self) -> Dict[str, Any]:
        """Get overall P&L summary."""
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self._current_capital,
            "total_pnl": self._total_pnl,
            "total_fees": self._total_fees,
            "total_gas": self._total_gas,
            "net_pnl": self._total_pnl - self._total_fees - self._total_gas,
            "return_pct": ((self._current_capital - self.initial_capital) / self.initial_capital) * 100,
            "total_trades": len(self._trades),
            "open_trades": sum(1 for t in self._trades if not t.is_closed),
            "closed_trades": sum(1 for t in self._trades if t.is_closed),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        return {
            "summary": self.get_summary(),
            "daily_report": self.generate_report("daily").to_dict(),
            "weekly_report": self.generate_report("weekly").to_dict(),
        }
