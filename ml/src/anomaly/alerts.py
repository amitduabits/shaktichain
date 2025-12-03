"""Alert system for anomaly detection.

Provides:
- Alert generation with severity levels
- Alert routing and handling
- Alert persistence and trending
- Notification dispatch
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
from collections import defaultdict
from pathlib import Path
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class AlertSeverity(IntEnum):
    """Alert severity levels."""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlertStatus(Enum):
    """Alert lifecycle status."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    ESCALATED = "escalated"


class AlertCategory(Enum):
    """Alert category types."""
    TRADING = "trading"
    DELIVERY = "delivery"
    ACCOUNT = "account"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass
class Alert:
    """Individual alert with full context."""
    alert_id: str
    severity: AlertSeverity
    category: AlertCategory
    anomaly_type: str
    score: float
    entity_id: str
    entity_type: str
    timestamp: datetime
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    status: AlertStatus = AlertStatus.NEW
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    related_alerts: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'severity': self.severity.name,
            'category': self.category.value,
            'anomaly_type': self.anomaly_type,
            'score': self.score,
            'entity_id': self.entity_id,
            'entity_type': self.entity_type,
            'timestamp': self.timestamp.isoformat(),
            'description': self.description,
            'details': self.details,
            'status': self.status.value,
            'assigned_to': self.assigned_to,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'related_alerts': self.related_alerts,
            'tags': self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        """Create from dictionary."""
        return cls(
            alert_id=data['alert_id'],
            severity=AlertSeverity[data['severity']],
            category=AlertCategory(data['category']),
            anomaly_type=data['anomaly_type'],
            score=data['score'],
            entity_id=data['entity_id'],
            entity_type=data['entity_type'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            description=data['description'],
            details=data.get('details', {}),
            status=AlertStatus(data.get('status', 'new')),
            assigned_to=data.get('assigned_to'),
            resolution_notes=data.get('resolution_notes'),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
            related_alerts=data.get('related_alerts', []),
            tags=data.get('tags', []),
        )


@dataclass
class AlertRule:
    """Rule for generating alerts from anomaly scores."""
    rule_id: str
    name: str
    anomaly_types: List[str]
    min_score: float
    severity: AlertSeverity
    category: AlertCategory
    description_template: str
    enabled: bool = True
    cooldown_minutes: int = 60  # Prevent duplicate alerts
    max_alerts_per_hour: int = 10
    tags: List[str] = field(default_factory=list)


class AlertHandler:
    """Base class for alert handlers."""

    def __init__(self, name: str):
        """Initialize handler.

        Args:
            name: Handler name
        """
        self.name = name

    def handle(self, alert: Alert) -> bool:
        """Handle an alert.

        Args:
            alert: Alert to handle

        Returns:
            True if handled successfully
        """
        raise NotImplementedError

    def can_handle(self, alert: Alert) -> bool:
        """Check if handler can process this alert.

        Args:
            alert: Alert to check

        Returns:
            True if handler can process
        """
        return True


class LoggingHandler(AlertHandler):
    """Handler that logs alerts."""

    def __init__(
        self,
        name: str = "logging",
        log_level: int = logging.WARNING,
    ):
        super().__init__(name)
        self.log_level = log_level
        self.logger = logging.getLogger(f"alerts.{name}")

    def handle(self, alert: Alert) -> bool:
        """Log the alert."""
        level_map = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }
        level = level_map.get(alert.severity, logging.WARNING)

        self.logger.log(
            level,
            f"[{alert.severity.name}] {alert.category.value}: {alert.description} "
            f"(score={alert.score:.3f}, entity={alert.entity_id})"
        )
        return True


class FileHandler(AlertHandler):
    """Handler that writes alerts to files."""

    def __init__(
        self,
        name: str = "file",
        output_dir: str = "alerts",
        rotate_daily: bool = True,
    ):
        super().__init__(name)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rotate_daily = rotate_daily

    def handle(self, alert: Alert) -> bool:
        """Write alert to file."""
        try:
            if self.rotate_daily:
                filename = f"alerts_{datetime.now().strftime('%Y%m%d')}.jsonl"
            else:
                filename = "alerts.jsonl"

            filepath = self.output_dir / filename

            with open(filepath, 'a') as f:
                f.write(json.dumps(alert.to_dict()) + '\n')

            return True
        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")
            return False


class WebhookHandler(AlertHandler):
    """Handler that sends alerts to webhooks."""

    def __init__(
        self,
        name: str = "webhook",
        url: str = "",
        headers: Optional[Dict[str, str]] = None,
        min_severity: AlertSeverity = AlertSeverity.MEDIUM,
    ):
        super().__init__(name)
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.min_severity = min_severity

    def can_handle(self, alert: Alert) -> bool:
        """Only handle alerts above min severity."""
        return alert.severity >= self.min_severity

    def handle(self, alert: Alert) -> bool:
        """Send alert to webhook."""
        if not self.url:
            return False

        try:
            import urllib.request

            data = json.dumps(alert.to_dict()).encode('utf-8')
            req = urllib.request.Request(
                self.url,
                data=data,
                headers=self.headers,
                method='POST',
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False


class QueueHandler(AlertHandler):
    """Handler that adds alerts to a queue for async processing."""

    def __init__(
        self,
        name: str = "queue",
        queue: Optional[Queue] = None,
    ):
        super().__init__(name)
        self.queue = queue or Queue()

    def handle(self, alert: Alert) -> bool:
        """Add alert to queue."""
        try:
            self.queue.put_nowait(alert)
            return True
        except Exception as e:
            logger.error(f"Failed to queue alert: {e}")
            return False


class AlertStore:
    """Persistent storage for alerts with trending capabilities."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize alert store.

        Args:
            storage_path: Path to store alerts (None for in-memory)
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.alerts: Dict[str, Alert] = {}
        self.alerts_by_entity: Dict[str, List[str]] = defaultdict(list)
        self.alerts_by_type: Dict[str, List[str]] = defaultdict(list)
        self.score_history: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        self._lock = threading.Lock()

        if self.storage_path and self.storage_path.exists():
            self._load()

    def add(self, alert: Alert) -> None:
        """Add an alert to the store."""
        with self._lock:
            self.alerts[alert.alert_id] = alert
            self.alerts_by_entity[alert.entity_id].append(alert.alert_id)
            self.alerts_by_type[alert.anomaly_type].append(alert.alert_id)
            self.score_history[alert.entity_id].append((alert.timestamp, alert.score))

        if self.storage_path:
            self._save()

    def get(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        return self.alerts.get(alert_id)

    def update(self, alert_id: str, **kwargs) -> bool:
        """Update alert fields."""
        with self._lock:
            if alert_id not in self.alerts:
                return False

            alert = self.alerts[alert_id]
            for key, value in kwargs.items():
                if hasattr(alert, key):
                    setattr(alert, key, value)
            alert.updated_at = datetime.now()

        if self.storage_path:
            self._save()

        return True

    def get_by_entity(
        self,
        entity_id: str,
        since: Optional[datetime] = None,
    ) -> List[Alert]:
        """Get alerts for an entity."""
        alert_ids = self.alerts_by_entity.get(entity_id, [])
        alerts = [self.alerts[aid] for aid in alert_ids if aid in self.alerts]

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_by_type(
        self,
        anomaly_type: str,
        since: Optional[datetime] = None,
    ) -> List[Alert]:
        """Get alerts by anomaly type."""
        alert_ids = self.alerts_by_type.get(anomaly_type, [])
        alerts = [self.alerts[aid] for aid in alert_ids if aid in self.alerts]

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_score_trend(
        self,
        entity_id: str,
        window_hours: int = 24,
    ) -> Dict[str, Any]:
        """Get score trend for an entity.

        Args:
            entity_id: Entity to analyze
            window_hours: Hours to look back

        Returns:
            Trend statistics
        """
        history = self.score_history.get(entity_id, [])
        cutoff = datetime.now() - timedelta(hours=window_hours)

        recent = [(ts, score) for ts, score in history if ts >= cutoff]

        if not recent:
            return {
                'entity_id': entity_id,
                'count': 0,
                'trend': 'no_data',
                'avg_score': 0,
                'max_score': 0,
                'score_increase': 0,
            }

        scores = [s for _, s in recent]
        timestamps = [ts for ts, _ in recent]

        avg_score = sum(scores) / len(scores)
        max_score = max(scores)

        # Calculate trend
        if len(scores) >= 2:
            first_half = scores[:len(scores)//2]
            second_half = scores[len(scores)//2:]
            score_increase = sum(second_half)/len(second_half) - sum(first_half)/len(first_half)

            if score_increase > 0.1:
                trend = 'increasing'
            elif score_increase < -0.1:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
            score_increase = 0

        return {
            'entity_id': entity_id,
            'count': len(recent),
            'trend': trend,
            'avg_score': avg_score,
            'max_score': max_score,
            'score_increase': score_increase,
            'first_alert': min(timestamps).isoformat(),
            'last_alert': max(timestamps).isoformat(),
        }

    def get_statistics(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get overall alert statistics."""
        alerts = list(self.alerts.values())

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        if not alerts:
            return {'total': 0}

        by_severity = defaultdict(int)
        by_category = defaultdict(int)
        by_type = defaultdict(int)
        by_status = defaultdict(int)

        for alert in alerts:
            by_severity[alert.severity.name] += 1
            by_category[alert.category.value] += 1
            by_type[alert.anomaly_type] += 1
            by_status[alert.status.value] += 1

        return {
            'total': len(alerts),
            'by_severity': dict(by_severity),
            'by_category': dict(by_category),
            'by_type': dict(by_type),
            'by_status': dict(by_status),
            'avg_score': sum(a.score for a in alerts) / len(alerts),
            'unique_entities': len(set(a.entity_id for a in alerts)),
        }

    def cleanup(self, older_than_days: int = 90) -> int:
        """Remove old alerts.

        Args:
            older_than_days: Remove alerts older than this

        Returns:
            Number of alerts removed
        """
        cutoff = datetime.now() - timedelta(days=older_than_days)
        to_remove = []

        with self._lock:
            for alert_id, alert in self.alerts.items():
                if alert.timestamp < cutoff:
                    to_remove.append(alert_id)

            for alert_id in to_remove:
                alert = self.alerts.pop(alert_id)

                # Remove from indices
                if alert.entity_id in self.alerts_by_entity:
                    self.alerts_by_entity[alert.entity_id] = [
                        aid for aid in self.alerts_by_entity[alert.entity_id]
                        if aid != alert_id
                    ]
                if alert.anomaly_type in self.alerts_by_type:
                    self.alerts_by_type[alert.anomaly_type] = [
                        aid for aid in self.alerts_by_type[alert.anomaly_type]
                        if aid != alert_id
                    ]

        if self.storage_path:
            self._save()

        return len(to_remove)

    def _save(self) -> None:
        """Save alerts to disk."""
        if not self.storage_path:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'alerts': {aid: a.to_dict() for aid, a in self.alerts.items()},
                'score_history': {
                    eid: [(ts.isoformat(), s) for ts, s in history]
                    for eid, history in self.score_history.items()
                },
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alerts: {e}")

    def _load(self) -> None:
        """Load alerts from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)

            for aid, alert_data in data.get('alerts', {}).items():
                alert = Alert.from_dict(alert_data)
                self.alerts[aid] = alert
                self.alerts_by_entity[alert.entity_id].append(aid)
                self.alerts_by_type[alert.anomaly_type].append(aid)

            for eid, history in data.get('score_history', {}).items():
                self.score_history[eid] = [
                    (datetime.fromisoformat(ts), s) for ts, s in history
                ]

        except Exception as e:
            logger.error(f"Failed to load alerts: {e}")


class AlertSystem:
    """Main alert system coordinating detection, routing, and storage."""

    def __init__(
        self,
        store: Optional[AlertStore] = None,
        handlers: Optional[List[AlertHandler]] = None,
    ):
        """Initialize alert system.

        Args:
            store: Alert storage backend
            handlers: List of alert handlers
        """
        self.store = store or AlertStore()
        self.handlers = handlers or [LoggingHandler()]

        # Alert rules
        self.rules: Dict[str, AlertRule] = {}
        self._setup_default_rules()

        # Rate limiting
        self.alert_counts: Dict[str, List[datetime]] = defaultdict(list)
        self.last_alert_time: Dict[str, datetime] = {}

        # Alert counter
        self._alert_counter = 0
        self._counter_lock = threading.Lock()

    def _setup_default_rules(self) -> None:
        """Set up default alert rules."""
        default_rules = [
            # Critical alerts (score > 0.9)
            AlertRule(
                rule_id="critical_wash_trading",
                name="Critical Wash Trading",
                anomaly_types=["WASH_TRADING"],
                min_score=0.9,
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.TRADING,
                description_template="Critical wash trading detected for {entity_id}",
                cooldown_minutes=30,
            ),
            AlertRule(
                rule_id="critical_sybil",
                name="Critical Sybil Attack",
                anomaly_types=["SYBIL_CLUSTER"],
                min_score=0.9,
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.NETWORK,
                description_template="Critical Sybil cluster detected: {entity_id}",
                cooldown_minutes=60,
            ),
            # High alerts (score > 0.8)
            AlertRule(
                rule_id="high_price_manipulation",
                name="High Price Manipulation",
                anomaly_types=["PRICE_MANIPULATION"],
                min_score=0.8,
                severity=AlertSeverity.HIGH,
                category=AlertCategory.TRADING,
                description_template="Price manipulation suspected for {entity_id}",
            ),
            AlertRule(
                rule_id="high_false_delivery",
                name="High False Delivery",
                anomaly_types=["FALSE_DELIVERY_CLAIM"],
                min_score=0.8,
                severity=AlertSeverity.HIGH,
                category=AlertCategory.DELIVERY,
                description_template="False delivery claim suspected: {entity_id}",
            ),
            AlertRule(
                rule_id="high_coordinated",
                name="High Coordinated Trading",
                anomaly_types=["COORDINATED_TRADING"],
                min_score=0.8,
                severity=AlertSeverity.HIGH,
                category=AlertCategory.NETWORK,
                description_template="Coordinated trading pattern: {entity_id}",
            ),
            # Medium alerts (score > 0.6)
            AlertRule(
                rule_id="medium_spoofing",
                name="Medium Spoofing",
                anomaly_types=["SPOOFING"],
                min_score=0.6,
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.TRADING,
                description_template="Potential spoofing by {entity_id}",
            ),
            AlertRule(
                rule_id="medium_volume_spike",
                name="Medium Volume Spike",
                anomaly_types=["VOLUME_SPIKE"],
                min_score=0.6,
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.TRADING,
                description_template="Unusual volume spike: {entity_id}",
            ),
            AlertRule(
                rule_id="medium_non_delivery",
                name="Medium Non-Delivery",
                anomaly_types=["SYSTEMATIC_NON_DELIVERY"],
                min_score=0.6,
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.DELIVERY,
                description_template="Systematic non-delivery pattern: {entity_id}",
            ),
            AlertRule(
                rule_id="medium_accounting",
                name="Medium Accounting Discrepancy",
                anomaly_types=["ENERGY_ACCOUNTING_DISCREPANCY"],
                min_score=0.6,
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.DELIVERY,
                description_template="Energy accounting discrepancy: {entity_id}",
            ),
            AlertRule(
                rule_id="medium_reputation",
                name="Medium Reputation Manipulation",
                anomaly_types=["REPUTATION_MANIPULATION"],
                min_score=0.6,
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.ACCOUNT,
                description_template="Reputation manipulation suspected: {entity_id}",
            ),
            # Low alerts (score > 0.4)
            AlertRule(
                rule_id="low_unusual_registration",
                name="Low Unusual Registration",
                anomaly_types=["UNUSUAL_REGISTRATION"],
                min_score=0.4,
                severity=AlertSeverity.LOW,
                category=AlertCategory.ACCOUNT,
                description_template="Unusual registration pattern: {entity_id}",
                cooldown_minutes=120,
            ),
        ]

        for rule in default_rules:
            self.rules[rule.rule_id] = rule

    def add_rule(self, rule: AlertRule) -> None:
        """Add a custom alert rule."""
        self.rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False

    def add_handler(self, handler: AlertHandler) -> None:
        """Add an alert handler."""
        self.handlers.append(handler)

    def process_anomaly(
        self,
        anomaly_type: str,
        score: float,
        entity_id: str,
        entity_type: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Alert]:
        """Process an anomaly score and generate alert if needed.

        Args:
            anomaly_type: Type of anomaly detected
            score: Anomaly score (0-1)
            entity_id: ID of the entity (trade, account, etc.)
            entity_type: Type of entity
            details: Additional details
            timestamp: Event timestamp

        Returns:
            Generated alert if applicable, None otherwise
        """
        timestamp = timestamp or datetime.now()
        details = details or {}

        # Find matching rule
        matching_rule = None
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            if anomaly_type not in rule.anomaly_types:
                continue
            if score < rule.min_score:
                continue
            if matching_rule is None or rule.severity > matching_rule.severity:
                matching_rule = rule

        if not matching_rule:
            # Log for pattern analysis even if no alert
            self._log_for_trending(entity_id, score, timestamp)
            return None

        # Check rate limiting
        if not self._check_rate_limit(matching_rule, entity_id):
            return None

        # Generate alert
        alert = self._create_alert(
            matching_rule, anomaly_type, score, entity_id,
            entity_type, details, timestamp
        )

        # Store and dispatch
        self.store.add(alert)
        self._dispatch_alert(alert)

        return alert

    def _check_rate_limit(self, rule: AlertRule, entity_id: str) -> bool:
        """Check if alert should be rate limited."""
        key = f"{rule.rule_id}:{entity_id}"
        now = datetime.now()

        # Check cooldown
        if key in self.last_alert_time:
            cooldown_end = self.last_alert_time[key] + timedelta(minutes=rule.cooldown_minutes)
            if now < cooldown_end:
                return False

        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        self.alert_counts[key] = [
            ts for ts in self.alert_counts[key] if ts >= hour_ago
        ]

        if len(self.alert_counts[key]) >= rule.max_alerts_per_hour:
            return False

        # Update rate limit tracking
        self.last_alert_time[key] = now
        self.alert_counts[key].append(now)

        return True

    def _create_alert(
        self,
        rule: AlertRule,
        anomaly_type: str,
        score: float,
        entity_id: str,
        entity_type: str,
        details: Dict[str, Any],
        timestamp: datetime,
    ) -> Alert:
        """Create an alert from a rule match."""
        with self._counter_lock:
            self._alert_counter += 1
            alert_id = f"ALERT-{timestamp.strftime('%Y%m%d')}-{self._alert_counter:06d}"

        description = rule.description_template.format(
            entity_id=entity_id,
            score=score,
            **details,
        )

        return Alert(
            alert_id=alert_id,
            severity=rule.severity,
            category=rule.category,
            anomaly_type=anomaly_type,
            score=score,
            entity_id=entity_id,
            entity_type=entity_type,
            timestamp=timestamp,
            description=description,
            details=details,
            tags=rule.tags.copy(),
        )

    def _dispatch_alert(self, alert: Alert) -> None:
        """Send alert to all applicable handlers."""
        for handler in self.handlers:
            try:
                if handler.can_handle(alert):
                    handler.handle(alert)
            except Exception as e:
                logger.error(f"Handler {handler.name} failed: {e}")

    def _log_for_trending(
        self,
        entity_id: str,
        score: float,
        timestamp: datetime,
    ) -> None:
        """Log score for trending even without alert."""
        self.store.score_history[entity_id].append((timestamp, score))

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        return self.store.get(alert_id)

    def update_alert(
        self,
        alert_id: str,
        status: Optional[AlertStatus] = None,
        assigned_to: Optional[str] = None,
        resolution_notes: Optional[str] = None,
    ) -> bool:
        """Update an alert."""
        updates = {}
        if status:
            updates['status'] = status
        if assigned_to:
            updates['assigned_to'] = assigned_to
        if resolution_notes:
            updates['resolution_notes'] = resolution_notes

        return self.store.update(alert_id, **updates)

    def get_alerts(
        self,
        entity_id: Optional[str] = None,
        anomaly_type: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        status: Optional[AlertStatus] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """Query alerts with filters.

        Args:
            entity_id: Filter by entity
            anomaly_type: Filter by anomaly type
            severity: Filter by minimum severity
            status: Filter by status
            since: Filter by time
            limit: Maximum results

        Returns:
            List of matching alerts
        """
        if entity_id:
            alerts = self.store.get_by_entity(entity_id, since)
        elif anomaly_type:
            alerts = self.store.get_by_type(anomaly_type, since)
        else:
            alerts = list(self.store.alerts.values())
            if since:
                alerts = [a for a in alerts if a.timestamp >= since]
            alerts = sorted(alerts, key=lambda a: a.timestamp, reverse=True)

        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.severity >= severity]
        if status:
            alerts = [a for a in alerts if a.status == status]

        return alerts[:limit]

    def get_trending_entities(
        self,
        window_hours: int = 24,
        min_alerts: int = 2,
        increasing_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get entities with increasing anomaly scores.

        Args:
            window_hours: Time window to analyze
            min_alerts: Minimum alerts required
            increasing_only: Only return increasing trends

        Returns:
            List of trending entity info
        """
        trending = []

        for entity_id in self.store.score_history.keys():
            trend_info = self.store.get_score_trend(entity_id, window_hours)

            if trend_info['count'] < min_alerts:
                continue

            if increasing_only and trend_info['trend'] != 'increasing':
                continue

            trending.append(trend_info)

        return sorted(trending, key=lambda x: x['score_increase'], reverse=True)

    def get_statistics(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get alert statistics."""
        return self.store.get_statistics(since)

    def cleanup(self, older_than_days: int = 90) -> int:
        """Clean up old alerts."""
        return self.store.cleanup(older_than_days)
