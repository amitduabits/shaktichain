"""Transaction monitoring for SHAKTI-CHAIN trading.

Provides:
- Transaction tracking and recording
- Failure alerting
- Gas usage monitoring
- Execution metrics
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from pathlib import Path
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class TransactionRecord:
    """Record of a transaction."""
    tx_hash: Optional[str]
    action_type: str
    quantity: float
    price: float
    status: str
    timestamp: datetime
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    gas_price: Optional[int] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0

    @property
    def gas_cost_eth(self) -> Optional[float]:
        """Calculate gas cost in ETH."""
        if self.gas_used and self.gas_price:
            return (self.gas_used * self.gas_price) / 1e18
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tx_hash": self.tx_hash,
            "action_type": self.action_type,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "block_number": self.block_number,
            "gas_used": self.gas_used,
            "gas_price": self.gas_price,
            "gas_cost_eth": self.gas_cost_eth,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionRecord":
        """Create from dictionary."""
        return cls(
            tx_hash=data.get("tx_hash"),
            action_type=data["action_type"],
            quantity=data["quantity"],
            price=data["price"],
            status=data["status"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            block_number=data.get("block_number"),
            gas_used=data.get("gas_used"),
            gas_price=data.get("gas_price"),
            error_message=data.get("error_message"),
            execution_time_ms=data.get("execution_time_ms", 0),
        )


@dataclass
class MonitorConfig:
    """Transaction monitor configuration."""
    # Storage
    storage_path: Optional[str] = None
    max_records: int = 10000

    # Alerting
    alert_on_failure: bool = True
    alert_on_high_gas: bool = True
    high_gas_threshold_gwei: float = 50.0
    alert_on_slow_execution: bool = True
    slow_execution_threshold_ms: float = 30000.0

    # Webhooks
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None


class TransactionMonitor:
    """Monitor and track trading transactions."""

    def __init__(self, config: Optional[MonitorConfig] = None):
        """Initialize transaction monitor.

        Args:
            config: Monitor configuration
        """
        self.config = config or MonitorConfig()

        # Transaction history
        self._records: deque = deque(maxlen=self.config.max_records)
        self._pending_transactions: Dict[str, TransactionRecord] = {}

        # Alert handlers
        self._alert_handlers: List[Callable[[str, Dict], None]] = []

        # Statistics
        self._stats = {
            "total_transactions": 0,
            "successful": 0,
            "failed": 0,
            "total_gas_used": 0,
            "total_gas_cost_eth": 0.0,
            "avg_execution_time_ms": 0.0,
            "failures_last_hour": 0,
        }

        # Load from storage
        if self.config.storage_path:
            self._load()

    def _load(self):
        """Load records from storage."""
        path = Path(self.config.storage_path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                    for record_data in data.get("records", []):
                        self._records.append(TransactionRecord.from_dict(record_data))
                    self._stats = data.get("stats", self._stats)
                logger.info(f"Loaded {len(self._records)} transaction records")
            except Exception as e:
                logger.error(f"Failed to load transaction records: {e}")

    def _save(self):
        """Save records to storage."""
        if not self.config.storage_path:
            return

        path = Path(self.config.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w") as f:
                data = {
                    "records": [r.to_dict() for r in self._records],
                    "stats": self._stats,
                    "saved_at": datetime.now().isoformat(),
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save transaction records: {e}")

    def add_alert_handler(self, handler: Callable[[str, Dict], None]):
        """Add alert handler.

        Args:
            handler: Function that receives (alert_type, details)
        """
        self._alert_handlers.append(handler)

    async def record(self, action, result) -> TransactionRecord:
        """Record a transaction.

        Args:
            action: TradingAction
            result: TransactionResult

        Returns:
            TransactionRecord
        """
        record = TransactionRecord(
            tx_hash=result.tx_hash,
            action_type=action.action_type.value,
            quantity=action.quantity,
            price=action.price,
            status=result.status.value,
            timestamp=result.timestamp,
            block_number=result.block_number,
            gas_used=result.gas_used,
            gas_price=result.gas_price,
            error_message=result.error_message,
            execution_time_ms=result.execution_time_ms,
        )

        self._records.append(record)
        self._update_stats(record)

        # Check for alerts
        await self._check_alerts(record)

        # Save periodically
        if len(self._records) % 10 == 0:
            self._save()

        return record

    def _update_stats(self, record: TransactionRecord):
        """Update statistics with new record."""
        self._stats["total_transactions"] += 1

        if record.status == "success":
            self._stats["successful"] += 1
        else:
            self._stats["failed"] += 1

        if record.gas_used:
            self._stats["total_gas_used"] += record.gas_used

        if record.gas_cost_eth:
            self._stats["total_gas_cost_eth"] += record.gas_cost_eth

        # Update average execution time
        n = self._stats["total_transactions"]
        avg = self._stats["avg_execution_time_ms"]
        self._stats["avg_execution_time_ms"] = (
            (avg * (n - 1) + record.execution_time_ms) / n
        )

        # Update failures last hour
        hour_ago = datetime.now() - timedelta(hours=1)
        self._stats["failures_last_hour"] = sum(
            1 for r in self._records
            if r.timestamp > hour_ago and r.status != "success"
        )

    async def _check_alerts(self, record: TransactionRecord):
        """Check if record triggers any alerts."""
        alerts = []

        # Failure alert
        if self.config.alert_on_failure and record.status not in ("success", "dry_run"):
            alerts.append(("transaction_failed", {
                "tx_hash": record.tx_hash,
                "action": record.action_type,
                "status": record.status,
                "error": record.error_message,
            }))

        # High gas alert
        if self.config.alert_on_high_gas and record.gas_price:
            gas_gwei = record.gas_price / 1e9
            if gas_gwei > self.config.high_gas_threshold_gwei:
                alerts.append(("high_gas", {
                    "tx_hash": record.tx_hash,
                    "gas_price_gwei": gas_gwei,
                    "threshold": self.config.high_gas_threshold_gwei,
                }))

        # Slow execution alert
        if self.config.alert_on_slow_execution:
            if record.execution_time_ms > self.config.slow_execution_threshold_ms:
                alerts.append(("slow_execution", {
                    "tx_hash": record.tx_hash,
                    "execution_time_ms": record.execution_time_ms,
                    "threshold": self.config.slow_execution_threshold_ms,
                }))

        # Dispatch alerts
        for alert_type, details in alerts:
            await self._dispatch_alert(alert_type, details)

    async def _dispatch_alert(self, alert_type: str, details: Dict[str, Any]):
        """Dispatch alert to handlers."""
        logger.warning(f"ALERT [{alert_type}]: {details}")

        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert_type, details)
                else:
                    handler(alert_type, details)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        # Send to webhooks
        await self._send_webhook_alert(alert_type, details)

    async def _send_webhook_alert(self, alert_type: str, details: Dict[str, Any]):
        """Send alert to configured webhooks."""
        message = {
            "alert_type": alert_type,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            import aiohttp

            if self.config.slack_webhook_url:
                slack_message = {
                    "text": f"🚨 Trading Alert: {alert_type}",
                    "attachments": [{
                        "color": "#F44336",
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in details.items()
                        ],
                    }],
                }
                async with aiohttp.ClientSession() as session:
                    await session.post(self.config.slack_webhook_url, json=slack_message)

            if self.config.discord_webhook_url:
                discord_message = {
                    "content": f"🚨 **Trading Alert: {alert_type}**\n```json\n{json.dumps(details, indent=2)}\n```",
                }
                async with aiohttp.ClientSession() as session:
                    await session.post(self.config.discord_webhook_url, json=discord_message)

        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Webhook error: {e}")

    def get_recent_transactions(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent transactions.

        Args:
            limit: Maximum records to return
            status: Filter by status
            action_type: Filter by action type

        Returns:
            List of transaction records
        """
        records = list(self._records)

        if status:
            records = [r for r in records if r.status == status]

        if action_type:
            records = [r for r in records if r.action_type == action_type]

        # Sort by timestamp descending
        records.sort(key=lambda r: r.timestamp, reverse=True)

        return [r.to_dict() for r in records[:limit]]

    def get_pending_transactions(self) -> List[Dict[str, Any]]:
        """Get pending transactions."""
        return [r.to_dict() for r in self._pending_transactions.values()]

    def get_failure_rate(self, window_hours: int = 24) -> float:
        """Calculate failure rate over time window.

        Args:
            window_hours: Time window in hours

        Returns:
            Failure rate as percentage
        """
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent = [r for r in self._records if r.timestamp > cutoff]

        if not recent:
            return 0.0

        failures = sum(1 for r in recent if r.status != "success")
        return (failures / len(recent)) * 100

    def get_gas_summary(self, window_hours: int = 24) -> Dict[str, Any]:
        """Get gas usage summary.

        Args:
            window_hours: Time window in hours

        Returns:
            Gas usage summary
        """
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent = [r for r in self._records if r.timestamp > cutoff and r.gas_used]

        if not recent:
            return {
                "total_gas": 0,
                "total_cost_eth": 0.0,
                "avg_gas_per_tx": 0,
                "avg_gas_price_gwei": 0.0,
            }

        total_gas = sum(r.gas_used for r in recent)
        total_cost = sum(r.gas_cost_eth or 0 for r in recent)
        avg_gas = total_gas / len(recent)
        avg_price = sum(r.gas_price or 0 for r in recent) / len(recent) / 1e9

        return {
            "total_gas": total_gas,
            "total_cost_eth": total_cost,
            "avg_gas_per_tx": avg_gas,
            "avg_gas_price_gwei": avg_price,
            "transaction_count": len(recent),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        return {
            **self._stats,
            "record_count": len(self._records),
            "pending_count": len(self._pending_transactions),
            "failure_rate_24h": self.get_failure_rate(24),
            "gas_summary_24h": self.get_gas_summary(24),
        }


class ExecutionMetrics:
    """Track execution metrics for performance monitoring."""

    def __init__(self):
        """Initialize metrics tracker."""
        self._latencies: deque = deque(maxlen=1000)
        self._success_count = 0
        self._failure_count = 0

    def record_execution(self, latency_ms: float, success: bool):
        """Record an execution.

        Args:
            latency_ms: Execution latency in milliseconds
            success: Whether execution was successful
        """
        self._latencies.append(latency_ms)

        if success:
            self._success_count += 1
        else:
            self._failure_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics."""
        if not self._latencies:
            return {
                "count": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
            }

        latencies = sorted(self._latencies)
        total = self._success_count + self._failure_count

        def percentile(p):
            idx = int(len(latencies) * p / 100)
            return latencies[min(idx, len(latencies) - 1)]

        return {
            "count": total,
            "success_rate": self._success_count / total * 100 if total > 0 else 0.0,
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": percentile(50),
            "p95_latency_ms": percentile(95),
            "p99_latency_ms": percentile(99),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
        }
