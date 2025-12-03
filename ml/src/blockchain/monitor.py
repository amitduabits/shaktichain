"""Sync monitoring and alerting for blockchain integration.

Provides:
- Sync lag monitoring
- Alert generation on lag > threshold
- Health metrics for observability
- Integration with external alerting systems
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of sync alerts."""
    SYNC_LAG = "sync_lag"
    SYNC_STALLED = "sync_stalled"
    HIGH_ERROR_RATE = "high_error_rate"
    DLQ_THRESHOLD = "dlq_threshold"
    CIRCUIT_OPEN = "circuit_open"
    ORACLE_STALE = "oracle_stale"


@dataclass
class SyncAlert:
    """Alert for sync issues."""
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class SyncMetrics:
    """Metrics for sync monitoring."""
    # Sync progress
    last_synced_block: int = 0
    current_chain_block: int = 0
    sync_lag_blocks: int = 0
    sync_lag_seconds: float = 0.0

    # Throughput
    events_per_second: float = 0.0
    blocks_per_second: float = 0.0

    # Errors
    error_rate: float = 0.0
    dlq_size: int = 0

    # Latency
    avg_processing_latency_ms: float = 0.0
    p99_processing_latency_ms: float = 0.0

    # Oracle freshness
    oracle_last_update: Optional[datetime] = None
    oracle_staleness_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sync": {
                "last_synced_block": self.last_synced_block,
                "current_chain_block": self.current_chain_block,
                "lag_blocks": self.sync_lag_blocks,
                "lag_seconds": self.sync_lag_seconds,
            },
            "throughput": {
                "events_per_second": self.events_per_second,
                "blocks_per_second": self.blocks_per_second,
            },
            "errors": {
                "error_rate": self.error_rate,
                "dlq_size": self.dlq_size,
            },
            "latency": {
                "avg_ms": self.avg_processing_latency_ms,
                "p99_ms": self.p99_processing_latency_ms,
            },
            "oracle": {
                "last_update": self.oracle_last_update.isoformat() if self.oracle_last_update else None,
                "staleness_seconds": self.oracle_staleness_seconds,
            },
        }


class AlertHandler:
    """Base class for alert handlers."""

    async def send(self, alert: SyncAlert):
        """Send alert. Override in subclasses."""
        raise NotImplementedError


class LogAlertHandler(AlertHandler):
    """Alert handler that logs alerts."""

    async def send(self, alert: SyncAlert):
        """Log alert."""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.ERROR,
        }.get(alert.severity, logging.WARNING)

        logger.log(log_level, f"ALERT [{alert.alert_type.value}]: {alert.message}")


class WebhookAlertHandler(AlertHandler):
    """Alert handler that sends to webhook."""

    def __init__(self, webhook_url: str):
        """Initialize webhook handler.

        Args:
            webhook_url: Webhook URL
        """
        self.webhook_url = webhook_url

    async def send(self, alert: SyncAlert):
        """Send alert to webhook."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.webhook_url,
                    json=alert.to_dict(),
                )
        except ImportError:
            logger.warning("aiohttp not installed, webhook alert not sent")
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")


class SlackAlertHandler(AlertHandler):
    """Alert handler for Slack notifications."""

    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        """Initialize Slack handler.

        Args:
            webhook_url: Slack webhook URL
            channel: Optional channel override
        """
        self.webhook_url = webhook_url
        self.channel = channel

    async def send(self, alert: SyncAlert):
        """Send alert to Slack."""
        emoji = {
            AlertSeverity.INFO: ":information_source:",
            AlertSeverity.WARNING: ":warning:",
            AlertSeverity.CRITICAL: ":rotating_light:",
        }.get(alert.severity, ":bell:")

        color = {
            AlertSeverity.INFO: "#2196F3",
            AlertSeverity.WARNING: "#FF9800",
            AlertSeverity.CRITICAL: "#F44336",
        }.get(alert.severity, "#9E9E9E")

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} SHAKTI-CHAIN ML Alert: {alert.alert_type.value}",
                    "text": alert.message,
                    "fields": [
                        {"title": k, "value": str(v), "short": True}
                        for k, v in alert.details.items()
                    ],
                    "ts": int(alert.timestamp.timestamp()),
                }
            ]
        }

        if self.channel:
            payload["channel"] = self.channel

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(self.webhook_url, json=payload)
        except ImportError:
            logger.warning("aiohttp not installed, Slack alert not sent")
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")


class SyncMonitor:
    """Monitor blockchain sync status and generate alerts."""

    def __init__(
        self,
        sync_lag_threshold_seconds: float = 300.0,  # 5 minutes
        error_rate_threshold: float = 0.1,  # 10%
        dlq_threshold: int = 100,
        oracle_staleness_threshold_seconds: float = 60.0,
        check_interval_seconds: float = 30.0,
    ):
        """Initialize sync monitor.

        Args:
            sync_lag_threshold_seconds: Threshold for sync lag alerts
            error_rate_threshold: Threshold for error rate alerts
            dlq_threshold: Threshold for DLQ size alerts
            oracle_staleness_threshold_seconds: Threshold for oracle staleness
            check_interval_seconds: Interval between health checks
        """
        self.sync_lag_threshold = sync_lag_threshold_seconds
        self.error_rate_threshold = error_rate_threshold
        self.dlq_threshold = dlq_threshold
        self.oracle_staleness_threshold = oracle_staleness_threshold_seconds
        self.check_interval = check_interval_seconds

        # Components to monitor
        self._subgraph_client = None
        self._sync_manager = None
        self._reliability_layer = None
        self._oracle_subscriber = None

        # Alert handlers
        self._alert_handlers: List[AlertHandler] = [LogAlertHandler()]

        # State
        self._running = False
        self._active_alerts: Dict[str, SyncAlert] = {}
        self._metrics = SyncMetrics()
        self._alert_counter = 0

        # Metrics history for rate calculation
        self._events_history: List[tuple[datetime, int]] = []
        self._errors_history: List[tuple[datetime, int]] = []

    def set_subgraph_client(self, client):
        """Set subgraph client to monitor."""
        self._subgraph_client = client

    def set_sync_manager(self, sync):
        """Set sync manager to monitor."""
        self._sync_manager = sync

    def set_reliability_layer(self, reliability):
        """Set reliability layer to monitor."""
        self._reliability_layer = reliability

    def set_oracle_subscriber(self, oracles):
        """Set oracle subscriber to monitor."""
        self._oracle_subscriber = oracles

    def add_alert_handler(self, handler: AlertHandler):
        """Add alert handler."""
        self._alert_handlers.append(handler)

    async def start(self):
        """Start monitoring."""
        self._running = True
        logger.info("Starting sync monitor")

        while self._running:
            try:
                await self._check_health()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Stop monitoring."""
        self._running = False
        logger.info("Sync monitor stopped")

    async def _check_health(self):
        """Perform health check and generate alerts."""
        await self._update_metrics()

        # Check sync lag
        if self._metrics.sync_lag_seconds > self.sync_lag_threshold:
            await self._create_alert(
                alert_type=AlertType.SYNC_LAG,
                severity=AlertSeverity.WARNING if self._metrics.sync_lag_seconds < self.sync_lag_threshold * 2 else AlertSeverity.CRITICAL,
                message=f"Sync lag is {self._metrics.sync_lag_seconds:.0f}s (threshold: {self.sync_lag_threshold}s)",
                details={
                    "lag_seconds": self._metrics.sync_lag_seconds,
                    "lag_blocks": self._metrics.sync_lag_blocks,
                    "last_synced_block": self._metrics.last_synced_block,
                },
            )
        else:
            await self._resolve_alert(AlertType.SYNC_LAG)

        # Check error rate
        if self._metrics.error_rate > self.error_rate_threshold:
            await self._create_alert(
                alert_type=AlertType.HIGH_ERROR_RATE,
                severity=AlertSeverity.WARNING,
                message=f"Error rate is {self._metrics.error_rate:.1%} (threshold: {self.error_rate_threshold:.1%})",
                details={
                    "error_rate": self._metrics.error_rate,
                },
            )
        else:
            await self._resolve_alert(AlertType.HIGH_ERROR_RATE)

        # Check DLQ size
        if self._metrics.dlq_size > self.dlq_threshold:
            await self._create_alert(
                alert_type=AlertType.DLQ_THRESHOLD,
                severity=AlertSeverity.WARNING,
                message=f"DLQ size is {self._metrics.dlq_size} (threshold: {self.dlq_threshold})",
                details={
                    "dlq_size": self._metrics.dlq_size,
                },
            )
        else:
            await self._resolve_alert(AlertType.DLQ_THRESHOLD)

        # Check oracle staleness
        if self._metrics.oracle_staleness_seconds > self.oracle_staleness_threshold:
            await self._create_alert(
                alert_type=AlertType.ORACLE_STALE,
                severity=AlertSeverity.WARNING,
                message=f"Oracle data is {self._metrics.oracle_staleness_seconds:.0f}s stale (threshold: {self.oracle_staleness_threshold}s)",
                details={
                    "staleness_seconds": self._metrics.oracle_staleness_seconds,
                    "last_update": self._metrics.oracle_last_update.isoformat() if self._metrics.oracle_last_update else None,
                },
            )
        else:
            await self._resolve_alert(AlertType.ORACLE_STALE)

        # Check circuit breakers
        if self._reliability_layer:
            stats = self._reliability_layer.get_stats()
            for service, cb_status in stats.get("circuit_breakers", {}).items():
                if cb_status.get("state") == "open":
                    await self._create_alert(
                        alert_type=AlertType.CIRCUIT_OPEN,
                        severity=AlertSeverity.CRITICAL,
                        message=f"Circuit breaker open for {service}",
                        details={
                            "service": service,
                            "failure_count": cb_status.get("failure_count"),
                        },
                    )

    async def _update_metrics(self):
        """Update metrics from monitored components."""
        now = datetime.now()

        # Subgraph metrics
        if self._subgraph_client:
            stats = self._subgraph_client.get_stats()
            events_received = stats.get("events_received", 0)

            # Update events history
            self._events_history.append((now, events_received))
            self._events_history = [
                (t, c) for t, c in self._events_history
                if now - t < timedelta(minutes=5)
            ]

            # Calculate events/second
            if len(self._events_history) >= 2:
                first = self._events_history[0]
                elapsed = (now - first[0]).total_seconds()
                if elapsed > 0:
                    self._metrics.events_per_second = (events_received - first[1]) / elapsed

        # Sync metrics
        if self._sync_manager:
            sync_stats = self._sync_manager.get_stats()
            progress = sync_stats.get("progress", {})

            for entity_type, prog in progress.items():
                if prog.get("status") == "syncing":
                    end_ts = prog.get("end_timestamp", 0)
                    current_ts = prog.get("current_timestamp", 0)
                    self._metrics.sync_lag_seconds = end_ts - current_ts

        # Reliability metrics
        if self._reliability_layer:
            rel_stats = self._reliability_layer.get_stats()
            self._metrics.dlq_size = rel_stats.get("dlq", {}).get("current_size", 0)

            # Calculate error rate
            total_ops = rel_stats.get("operations_executed", 0)
            failures = rel_stats.get("failures", 0)
            if total_ops > 0:
                self._metrics.error_rate = failures / total_ops

        # Oracle metrics
        if self._oracle_subscriber:
            oracle_stats = self._oracle_subscriber.get_stats()
            price_stats = oracle_stats.get("price_oracle", {})
            last_update_str = price_stats.get("last_update")

            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str)
                    self._metrics.oracle_last_update = last_update
                    self._metrics.oracle_staleness_seconds = (now - last_update).total_seconds()
                except (ValueError, TypeError):
                    pass

    async def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        details: Dict[str, Any],
    ):
        """Create and dispatch alert."""
        alert_key = alert_type.value

        # Check if alert already exists
        if alert_key in self._active_alerts:
            return

        self._alert_counter += 1
        alert = SyncAlert(
            id=f"alert-{self._alert_counter}",
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            details=details,
        )

        self._active_alerts[alert_key] = alert

        # Dispatch to handlers
        for handler in self._alert_handlers:
            try:
                await handler.send(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    async def _resolve_alert(self, alert_type: AlertType):
        """Resolve an active alert."""
        alert_key = alert_type.value

        if alert_key in self._active_alerts:
            alert = self._active_alerts[alert_key]
            alert.resolved = True
            alert.resolved_at = datetime.now()

            # Log resolution
            logger.info(f"Alert resolved: {alert_type.value}")

            del self._active_alerts[alert_key]

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return self._metrics.to_dict()

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts."""
        return [alert.to_dict() for alert in self._active_alerts.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        return {
            "running": self._running,
            "metrics": self.get_metrics(),
            "active_alerts": len(self._active_alerts),
            "total_alerts": self._alert_counter,
        }
