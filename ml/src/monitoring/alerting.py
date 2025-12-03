"""Alerting system for SHAKTI-CHAIN ML production.

Provides:
- Alert rule definitions
- Alert evaluation
- Notification dispatching (PagerDuty, Slack, Email)
- Alert state management
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"  # PagerDuty page
    WARNING = "warning"    # Slack notification
    INFO = "info"          # Email/logging


class AlertState(Enum):
    """Alert state."""
    OK = "ok"
    PENDING = "pending"  # Condition met but waiting for duration
    FIRING = "firing"
    RESOLVED = "resolved"


@dataclass
class AlertRule:
    """Definition of an alert rule."""

    name: str
    description: str
    severity: AlertSeverity
    condition: Callable[[], bool]  # Function that returns True if alert should fire
    duration: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    runbook_url: Optional[str] = None

    def __hash__(self):
        return hash(self.name)


@dataclass
class Alert:
    """An active alert instance."""

    rule: AlertRule
    state: AlertState
    started_at: datetime
    last_evaluated: datetime
    value: Optional[float] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        """Compute unique fingerprint for this alert."""
        data = f"{self.rule.name}:{sorted(self.labels.items())}"
        return hashlib.md5(data.encode()).hexdigest()[:16]


class AlertManager:
    """Manages alert evaluation and notification.

    Example:
        >>> manager = AlertManager()
        >>> manager.add_rule(AlertRule(
        ...     name="high_latency",
        ...     description="p99 latency above threshold",
        ...     severity=AlertSeverity.WARNING,
        ...     condition=lambda: get_p99_latency() > 500,
        ...     duration=timedelta(minutes=5)
        ... ))
        >>> await manager.evaluate()
    """

    def __init__(
        self,
        pagerduty_key: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        email_config: Optional[Dict[str, str]] = None,
    ):
        """Initialize alert manager.

        Args:
            pagerduty_key: PagerDuty integration key
            slack_webhook: Slack webhook URL
            email_config: Email configuration dict
        """
        self.pagerduty_key = pagerduty_key
        self.slack_webhook = slack_webhook
        self.email_config = email_config

        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._pending: Dict[str, datetime] = {}  # When condition first became true
        self._silenced: Set[str] = set()

        # Notification history to prevent spam
        self._notification_history: Dict[str, datetime] = {}
        self._min_notification_interval = timedelta(minutes=5)

    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self._rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name} ({rule.severity.value})")

    def remove_rule(self, name: str):
        """Remove an alert rule."""
        self._rules.pop(name, None)
        self._alerts.pop(name, None)
        self._pending.pop(name, None)

    def silence(self, rule_name: str, duration: timedelta = timedelta(hours=1)):
        """Silence an alert rule temporarily."""
        self._silenced.add(rule_name)
        logger.info(f"Silenced alert: {rule_name} for {duration}")

        # Schedule unsilence
        asyncio.create_task(self._unsilence_after(rule_name, duration))

    async def _unsilence_after(self, rule_name: str, duration: timedelta):
        """Unsilence after duration."""
        await asyncio.sleep(duration.total_seconds())
        self._silenced.discard(rule_name)
        logger.info(f"Unsilenced alert: {rule_name}")

    async def evaluate(self) -> List[Alert]:
        """Evaluate all rules and return firing alerts.

        Returns:
            List of currently firing alerts
        """
        firing_alerts = []
        now = datetime.now()

        for rule in self._rules.values():
            try:
                condition_met = rule.condition()
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")
                continue

            alert = self._alerts.get(rule.name)

            if condition_met:
                if rule.name not in self._pending:
                    # First time condition is met
                    self._pending[rule.name] = now

                pending_since = self._pending[rule.name]
                pending_duration = now - pending_since

                if pending_duration >= rule.duration:
                    # Alert should fire
                    if alert is None or alert.state != AlertState.FIRING:
                        # New or re-firing alert
                        alert = Alert(
                            rule=rule,
                            state=AlertState.FIRING,
                            started_at=pending_since,
                            last_evaluated=now,
                            labels=rule.labels.copy(),
                            annotations=rule.annotations.copy(),
                        )
                        self._alerts[rule.name] = alert

                        # Send notification
                        if rule.name not in self._silenced:
                            await self._notify(alert, "firing")
                    else:
                        alert.last_evaluated = now

                    firing_alerts.append(alert)
                else:
                    # Still pending
                    if alert is None:
                        alert = Alert(
                            rule=rule,
                            state=AlertState.PENDING,
                            started_at=pending_since,
                            last_evaluated=now,
                        )
                        self._alerts[rule.name] = alert

            else:
                # Condition not met
                self._pending.pop(rule.name, None)

                if alert is not None and alert.state == AlertState.FIRING:
                    # Alert resolved
                    alert.state = AlertState.RESOLVED
                    alert.last_evaluated = now

                    if rule.name not in self._silenced:
                        await self._notify(alert, "resolved")

        return firing_alerts

    async def _notify(self, alert: Alert, action: str):
        """Send notification for an alert.

        Args:
            alert: The alert
            action: "firing" or "resolved"
        """
        # Check notification rate limit
        history_key = f"{alert.fingerprint}:{action}"
        last_notified = self._notification_history.get(history_key)

        if last_notified and datetime.now() - last_notified < self._min_notification_interval:
            logger.debug(f"Skipping notification for {alert.rule.name} (rate limited)")
            return

        self._notification_history[history_key] = datetime.now()

        # Route based on severity
        if alert.rule.severity == AlertSeverity.CRITICAL:
            await self._notify_pagerduty(alert, action)
            await self._notify_slack(alert, action)

        elif alert.rule.severity == AlertSeverity.WARNING:
            await self._notify_slack(alert, action)

        else:  # INFO
            await self._notify_email(alert, action)

        logger.info(f"Alert {action}: {alert.rule.name} ({alert.rule.severity.value})")

    async def _notify_pagerduty(self, alert: Alert, action: str):
        """Send PagerDuty notification."""
        if not self.pagerduty_key:
            logger.warning("PagerDuty key not configured")
            return

        try:
            import aiohttp

            event_action = "trigger" if action == "firing" else "resolve"

            payload = {
                "routing_key": self.pagerduty_key,
                "event_action": event_action,
                "dedup_key": alert.fingerprint,
                "payload": {
                    "summary": f"[{alert.rule.severity.value.upper()}] {alert.rule.name}: {alert.rule.description}",
                    "severity": "critical" if alert.rule.severity == AlertSeverity.CRITICAL else "warning",
                    "source": "shakti-ml-service",
                    "custom_details": {
                        "started_at": alert.started_at.isoformat(),
                        "labels": alert.labels,
                        "runbook": alert.rule.runbook_url,
                    },
                },
            }

            if alert.rule.runbook_url:
                payload["links"] = [{"href": alert.rule.runbook_url, "text": "Runbook"}]

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    timeout=10,
                ) as response:
                    if response.status != 202:
                        logger.error(f"PagerDuty error: {await response.text()}")

        except Exception as e:
            logger.error(f"PagerDuty notification failed: {e}")

    async def _notify_slack(self, alert: Alert, action: str):
        """Send Slack notification."""
        if not self.slack_webhook:
            logger.warning("Slack webhook not configured")
            return

        try:
            import aiohttp

            color = "#dc3545" if action == "firing" else "#28a745"
            emoji = "🚨" if alert.rule.severity == AlertSeverity.CRITICAL else "⚠️"

            if action == "resolved":
                emoji = "✅"
                color = "#28a745"

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Alert {action.upper()}: {alert.rule.name}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severity:* {alert.rule.severity.value}"},
                        {"type": "mrkdwn", "text": f"*Started:* {alert.started_at.strftime('%Y-%m-%d %H:%M:%S')}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Description:* {alert.rule.description}"},
                },
            ]

            if alert.rule.runbook_url:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"📖 <{alert.rule.runbook_url}|View Runbook>"},
                })

            payload = {
                "attachments": [{
                    "color": color,
                    "blocks": blocks,
                }],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook,
                    json=payload,
                    timeout=10,
                ) as response:
                    if response.status != 200:
                        logger.error(f"Slack error: {await response.text()}")

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    async def _notify_email(self, alert: Alert, action: str):
        """Send email notification."""
        if not self.email_config:
            logger.debug("Email not configured")
            return

        # Email implementation would go here
        logger.info(f"Email notification: {alert.rule.name} {action}")

    def get_firing_alerts(self) -> List[Alert]:
        """Get currently firing alerts."""
        return [
            alert for alert in self._alerts.values()
            if alert.state == AlertState.FIRING
        ]

    def get_alert_status(self) -> Dict[str, Any]:
        """Get overall alert status."""
        firing = self.get_firing_alerts()

        return {
            "total_rules": len(self._rules),
            "firing_count": len(firing),
            "critical_count": sum(1 for a in firing if a.rule.severity == AlertSeverity.CRITICAL),
            "warning_count": sum(1 for a in firing if a.rule.severity == AlertSeverity.WARNING),
            "silenced_count": len(self._silenced),
            "alerts": [
                {
                    "name": a.rule.name,
                    "severity": a.rule.severity.value,
                    "state": a.state.value,
                    "started_at": a.started_at.isoformat(),
                    "description": a.rule.description,
                }
                for a in firing
            ],
        }


def check_alerts(
    metrics_getter: Callable[[str], float],
    rules: List[AlertRule],
) -> List[Alert]:
    """Simple synchronous alert check.

    Args:
        metrics_getter: Function to get metric values
        rules: List of alert rules to check

    Returns:
        List of firing alerts
    """
    firing = []

    for rule in rules:
        try:
            if rule.condition():
                alert = Alert(
                    rule=rule,
                    state=AlertState.FIRING,
                    started_at=datetime.now(),
                    last_evaluated=datetime.now(),
                )
                firing.append(alert)
        except Exception as e:
            logger.error(f"Error checking rule {rule.name}: {e}")

    return firing


# Pre-defined alert rules for SHAKTI-CHAIN ML

def create_default_alert_rules(
    performance_collector: Any,
    prediction_collector: Any,
    feature_collector: Any,
) -> List[AlertRule]:
    """Create default alert rules for ML service.

    Args:
        performance_collector: PerformanceCollector instance
        prediction_collector: PredictionCollector instance
        feature_collector: FeatureCollector instance

    Returns:
        List of AlertRule objects
    """
    rules = []

    # Critical alerts (PagerDuty)

    rules.append(AlertRule(
        name="ml_high_error_rate",
        description="ML service error rate above 5%",
        severity=AlertSeverity.CRITICAL,
        condition=lambda: (
            (stats := performance_collector.get_stats("/trading/action", 5)) and
            stats.get("error_rate", 0) > 0.05
        ),
        duration=timedelta(minutes=5),
        runbook_url="https://wiki.shaktichain.io/runbooks/ML-001",
        labels={"service": "ml-service", "type": "availability"},
    ))

    rules.append(AlertRule(
        name="ml_high_latency_critical",
        description="p99 latency above 2x target for trading endpoint",
        severity=AlertSeverity.CRITICAL,
        condition=lambda: (
            (stats := performance_collector.get_stats("/trading/action", 10)) and
            stats.get("latency_p99_ms", 0) > 200  # 2x target of 100ms
        ),
        duration=timedelta(minutes=10),
        runbook_url="https://wiki.shaktichain.io/runbooks/ML-001",
        labels={"service": "ml-service", "type": "latency"},
    ))

    rules.append(AlertRule(
        name="ml_model_serving_failed",
        description="Model serving health check failed",
        severity=AlertSeverity.CRITICAL,
        condition=lambda: False,  # Implement actual health check
        duration=timedelta(minutes=2),
        runbook_url="https://wiki.shaktichain.io/runbooks/ML-003",
        labels={"service": "ml-service", "type": "model"},
    ))

    # Warning alerts (Slack)

    rules.append(AlertRule(
        name="ml_forecast_accuracy_degraded",
        description="Forecast MAPE above threshold",
        severity=AlertSeverity.WARNING,
        condition=lambda: (
            (mape := prediction_collector.get_accuracy("load_forecast", "mape", 1)) and
            mape > 0.15
        ),
        duration=timedelta(hours=1),
        runbook_url="https://wiki.shaktichain.io/runbooks/ML-002",
        labels={"service": "ml-service", "type": "accuracy"},
    ))

    rules.append(AlertRule(
        name="ml_feature_stale",
        description="Feature data staleness above 10 minutes",
        severity=AlertSeverity.WARNING,
        condition=lambda: (
            feature_collector.get_staleness("temperature") > 600 or
            feature_collector.get_staleness("grid_load") > 600
        ),
        duration=timedelta(minutes=5),
        runbook_url="https://wiki.shaktichain.io/runbooks/ML-004",
        labels={"service": "ml-service", "type": "data"},
    ))

    rules.append(AlertRule(
        name="ml_feature_drift_detected",
        description="Feature drift score above 0.5",
        severity=AlertSeverity.WARNING,
        condition=lambda: False,  # Implement with DriftCollector
        duration=timedelta(hours=1),
        runbook_url="https://wiki.shaktichain.io/runbooks/ML-002",
        labels={"service": "ml-service", "type": "drift"},
    ))

    rules.append(AlertRule(
        name="ml_anomaly_rate_spike",
        description="Anomaly alert rate unusually high",
        severity=AlertSeverity.WARNING,
        condition=lambda: False,  # Implement with anomaly rate check
        duration=timedelta(minutes=15),
        labels={"service": "ml-service", "type": "anomaly"},
    ))

    # Info alerts (Email)

    rules.append(AlertRule(
        name="ml_model_retrained",
        description="Model has been retrained",
        severity=AlertSeverity.INFO,
        condition=lambda: False,  # Triggered by retraining pipeline
        duration=timedelta(seconds=0),
        labels={"service": "ml-service", "type": "model"},
    ))

    return rules
