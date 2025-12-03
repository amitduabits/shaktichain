"""Retraining triggers for continuous learning.

Provides:
- Scheduled triggers (weekly, daily)
- Performance-based triggers (MAPE degradation)
- Drift-based triggers (input distribution shift)
- Manual triggers
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Types of retraining triggers."""
    SCHEDULED = "scheduled"
    PERFORMANCE = "performance"
    DRIFT = "drift"
    MANUAL = "manual"
    STALENESS = "staleness"


@dataclass
class TriggerEvent:
    """A retraining trigger event."""
    trigger_type: TriggerType
    model_name: str
    triggered_at: datetime
    reason: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1=low, 5=critical
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trigger_type": self.trigger_type.value,
            "model_name": self.model_name,
            "triggered_at": self.triggered_at.isoformat(),
            "reason": self.reason,
            "metrics": self.metrics,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class TriggerConfig:
    """Configuration for triggers."""
    # Scheduled
    schedule_interval: str = "weekly"  # daily, weekly, monthly
    schedule_day: int = 0  # Day of week (0=Monday) or month

    # Performance
    performance_metric: str = "mape"
    performance_threshold: float = 0.1  # 10% degradation
    performance_window_hours: int = 24

    # Drift
    drift_threshold: float = 0.1
    drift_check_interval_hours: int = 6

    # Staleness
    max_model_age_days: int = 30

    # General
    cooldown_hours: float = 24.0  # Min time between triggers
    enabled: bool = True


class BaseTrigger(ABC):
    """Base class for retraining triggers."""

    def __init__(self, config: TriggerConfig, model_name: str):
        """Initialize trigger.

        Args:
            config: Trigger configuration
            model_name: Name of model to monitor
        """
        self.config = config
        self.model_name = model_name
        self._last_trigger: Optional[datetime] = None

    @abstractmethod
    async def check(self) -> Optional[TriggerEvent]:
        """Check if trigger condition is met.

        Returns:
            TriggerEvent if triggered, None otherwise
        """
        pass

    def _check_cooldown(self) -> bool:
        """Check if cooldown period has passed."""
        if not self._last_trigger:
            return True

        elapsed = (datetime.now() - self._last_trigger).total_seconds() / 3600
        return elapsed >= self.config.cooldown_hours

    def _record_trigger(self):
        """Record that trigger fired."""
        self._last_trigger = datetime.now()


class ScheduledTrigger(BaseTrigger):
    """Scheduled retraining trigger."""

    def __init__(self, config: TriggerConfig, model_name: str):
        """Initialize scheduled trigger."""
        super().__init__(config, model_name)
        self._last_check_date: Optional[datetime] = None

    async def check(self) -> Optional[TriggerEvent]:
        """Check if scheduled trigger time has arrived."""
        if not self.config.enabled:
            return None

        now = datetime.now()

        # Check if we've already triggered today
        if self._last_check_date and self._last_check_date.date() == now.date():
            return None

        should_trigger = False
        reason = ""

        if self.config.schedule_interval == "daily":
            # Trigger once per day
            if not self._last_trigger or self._last_trigger.date() < now.date():
                should_trigger = True
                reason = "Daily scheduled retraining"

        elif self.config.schedule_interval == "weekly":
            # Trigger on specified day of week
            if now.weekday() == self.config.schedule_day:
                if not self._last_trigger or (now - self._last_trigger).days >= 7:
                    should_trigger = True
                    reason = f"Weekly scheduled retraining (day {self.config.schedule_day})"

        elif self.config.schedule_interval == "monthly":
            # Trigger on specified day of month
            if now.day == self.config.schedule_day:
                if not self._last_trigger or self._last_trigger.month != now.month:
                    should_trigger = True
                    reason = f"Monthly scheduled retraining (day {self.config.schedule_day})"

        self._last_check_date = now

        if should_trigger and self._check_cooldown():
            self._record_trigger()
            return TriggerEvent(
                trigger_type=TriggerType.SCHEDULED,
                model_name=self.model_name,
                triggered_at=now,
                reason=reason,
                priority=2,
            )

        return None


class PerformanceTrigger(BaseTrigger):
    """Performance degradation trigger."""

    def __init__(
        self,
        config: TriggerConfig,
        model_name: str,
        metrics_store=None,
    ):
        """Initialize performance trigger.

        Args:
            config: Trigger configuration
            model_name: Name of model
            metrics_store: Store for retrieving metrics
        """
        super().__init__(config, model_name)
        self.metrics_store = metrics_store

        # Baseline metrics
        self._baseline_metric: Optional[float] = None
        self._metric_history: List[tuple] = []  # (timestamp, value)

    def set_baseline(self, metric_value: float):
        """Set baseline metric value.

        Args:
            metric_value: Baseline value
        """
        self._baseline_metric = metric_value
        logger.info(f"Performance baseline set: {self.config.performance_metric}={metric_value}")

    def record_metric(self, value: float, timestamp: Optional[datetime] = None):
        """Record a metric value.

        Args:
            value: Metric value
            timestamp: When the metric was recorded
        """
        timestamp = timestamp or datetime.now()
        self._metric_history.append((timestamp, value))

        # Keep only recent history
        cutoff = datetime.now() - timedelta(hours=self.config.performance_window_hours * 2)
        self._metric_history = [(t, v) for t, v in self._metric_history if t > cutoff]

    async def check(self) -> Optional[TriggerEvent]:
        """Check if performance has degraded."""
        if not self.config.enabled:
            return None

        if not self._check_cooldown():
            return None

        if self._baseline_metric is None:
            return None

        # Get recent metrics
        cutoff = datetime.now() - timedelta(hours=self.config.performance_window_hours)
        recent_metrics = [v for t, v in self._metric_history if t > cutoff]

        if not recent_metrics:
            return None

        # Calculate current metric
        current_metric = sum(recent_metrics) / len(recent_metrics)

        # Check degradation
        if self._baseline_metric > 0:
            degradation = (current_metric - self._baseline_metric) / self._baseline_metric
        else:
            degradation = current_metric - self._baseline_metric

        # For metrics like MAPE, higher is worse
        if degradation > self.config.performance_threshold:
            self._record_trigger()
            return TriggerEvent(
                trigger_type=TriggerType.PERFORMANCE,
                model_name=self.model_name,
                triggered_at=datetime.now(),
                reason=f"Performance degradation: {self.config.performance_metric} "
                       f"increased by {degradation:.1%}",
                metrics={
                    "baseline": self._baseline_metric,
                    "current": current_metric,
                    "degradation": degradation,
                    "threshold": self.config.performance_threshold,
                },
                priority=4,  # High priority
            )

        return None


class DriftTrigger(BaseTrigger):
    """Data drift trigger."""

    def __init__(
        self,
        config: TriggerConfig,
        model_name: str,
        drift_detector=None,
    ):
        """Initialize drift trigger.

        Args:
            config: Trigger configuration
            model_name: Name of model
            drift_detector: DriftDetector instance
        """
        super().__init__(config, model_name)
        self.drift_detector = drift_detector
        self._last_drift_check: Optional[datetime] = None

    async def check(self) -> Optional[TriggerEvent]:
        """Check for data drift."""
        if not self.config.enabled:
            return None

        if not self._check_cooldown():
            return None

        # Check if enough time has passed since last drift check
        now = datetime.now()
        if self._last_drift_check:
            elapsed_hours = (now - self._last_drift_check).total_seconds() / 3600
            if elapsed_hours < self.config.drift_check_interval_hours:
                return None

        self._last_drift_check = now

        if not self.drift_detector:
            return None

        # Get drift report from detector
        # The drift detector should be updated with recent data externally
        try:
            drift_report = self.drift_detector.detect_drift([])  # Would need current data

            if drift_report.has_drift and drift_report.drift_score > self.config.drift_threshold:
                self._record_trigger()
                return TriggerEvent(
                    trigger_type=TriggerType.DRIFT,
                    model_name=self.model_name,
                    triggered_at=now,
                    reason=f"Data drift detected: score={drift_report.drift_score:.3f}",
                    metrics={
                        "drift_score": drift_report.drift_score,
                        "threshold": self.config.drift_threshold,
                        "feature_drifts": drift_report.feature_drifts,
                    },
                    priority=3,
                )
        except Exception as e:
            logger.error(f"Drift check failed: {e}")

        return None


class StalenessTrigger(BaseTrigger):
    """Model staleness trigger."""

    def __init__(
        self,
        config: TriggerConfig,
        model_name: str,
        model_registry=None,
    ):
        """Initialize staleness trigger.

        Args:
            config: Trigger configuration
            model_name: Name of model
            model_registry: Model registry for getting model info
        """
        super().__init__(config, model_name)
        self.model_registry = model_registry
        self._model_trained_at: Optional[datetime] = None

    def set_model_trained_at(self, trained_at: datetime):
        """Set when the current model was trained.

        Args:
            trained_at: Training timestamp
        """
        self._model_trained_at = trained_at

    async def check(self) -> Optional[TriggerEvent]:
        """Check if model is stale."""
        if not self.config.enabled:
            return None

        if not self._check_cooldown():
            return None

        trained_at = self._model_trained_at

        # Try to get from registry
        if not trained_at and self.model_registry:
            try:
                model_info = await self.model_registry.get_model_info(self.model_name)
                trained_at = model_info.get("trained_at")
            except Exception:
                pass

        if not trained_at:
            return None

        # Check age
        age_days = (datetime.now() - trained_at).days

        if age_days > self.config.max_model_age_days:
            self._record_trigger()
            return TriggerEvent(
                trigger_type=TriggerType.STALENESS,
                model_name=self.model_name,
                triggered_at=datetime.now(),
                reason=f"Model is {age_days} days old (max: {self.config.max_model_age_days})",
                metrics={
                    "age_days": age_days,
                    "max_age_days": self.config.max_model_age_days,
                    "trained_at": trained_at.isoformat(),
                },
                priority=2,
            )

        return None


class RetrainingTrigger:
    """Unified retraining trigger manager."""

    def __init__(
        self,
        model_name: str,
        config: Optional[TriggerConfig] = None,
        drift_detector=None,
        model_registry=None,
    ):
        """Initialize retraining trigger.

        Args:
            model_name: Name of model to monitor
            config: Trigger configuration
            drift_detector: Drift detector instance
            model_registry: Model registry instance
        """
        self.model_name = model_name
        self.config = config or TriggerConfig()

        # Initialize individual triggers
        self.triggers: Dict[TriggerType, BaseTrigger] = {
            TriggerType.SCHEDULED: ScheduledTrigger(self.config, model_name),
            TriggerType.PERFORMANCE: PerformanceTrigger(self.config, model_name),
            TriggerType.DRIFT: DriftTrigger(self.config, model_name, drift_detector),
            TriggerType.STALENESS: StalenessTrigger(self.config, model_name, model_registry),
        }

        # Callbacks for trigger events
        self._callbacks: List[Callable[[TriggerEvent], None]] = []

        # Event history
        self._event_history: List[TriggerEvent] = []

        # Running state
        self._running = False
        self._check_task: Optional[asyncio.Task] = None

    def on_trigger(self, callback: Callable[[TriggerEvent], None]):
        """Register callback for trigger events.

        Args:
            callback: Callback function
        """
        self._callbacks.append(callback)

    def set_performance_baseline(self, metric_value: float):
        """Set baseline for performance monitoring.

        Args:
            metric_value: Baseline metric value
        """
        perf_trigger = self.triggers.get(TriggerType.PERFORMANCE)
        if isinstance(perf_trigger, PerformanceTrigger):
            perf_trigger.set_baseline(metric_value)

    def record_performance(self, value: float):
        """Record performance metric.

        Args:
            value: Metric value
        """
        perf_trigger = self.triggers.get(TriggerType.PERFORMANCE)
        if isinstance(perf_trigger, PerformanceTrigger):
            perf_trigger.record_metric(value)

    def set_model_trained_at(self, trained_at: datetime):
        """Set when model was trained.

        Args:
            trained_at: Training timestamp
        """
        staleness_trigger = self.triggers.get(TriggerType.STALENESS)
        if isinstance(staleness_trigger, StalenessTrigger):
            staleness_trigger.set_model_trained_at(trained_at)

    async def trigger_manual(self, reason: str = "Manual trigger") -> TriggerEvent:
        """Trigger retraining manually.

        Args:
            reason: Reason for manual trigger

        Returns:
            TriggerEvent
        """
        event = TriggerEvent(
            trigger_type=TriggerType.MANUAL,
            model_name=self.model_name,
            triggered_at=datetime.now(),
            reason=reason,
            priority=5,  # Highest priority
        )

        await self._dispatch_event(event)
        return event

    async def start(self, check_interval_seconds: float = 300.0):
        """Start monitoring triggers.

        Args:
            check_interval_seconds: Interval between checks
        """
        self._running = True
        self._check_task = asyncio.create_task(
            self._check_loop(check_interval_seconds)
        )
        logger.info(f"Retraining triggers started for {self.model_name}")

    async def stop(self):
        """Stop monitoring triggers."""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Retraining triggers stopped for {self.model_name}")

    async def _check_loop(self, interval: float):
        """Background loop to check triggers."""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Trigger check error: {e}")
                await asyncio.sleep(interval)

    async def check_all(self) -> List[TriggerEvent]:
        """Check all triggers.

        Returns:
            List of triggered events
        """
        events = []

        for trigger_type, trigger in self.triggers.items():
            try:
                event = await trigger.check()
                if event:
                    events.append(event)
                    await self._dispatch_event(event)
            except Exception as e:
                logger.error(f"Error checking {trigger_type.value} trigger: {e}")

        return events

    async def _dispatch_event(self, event: TriggerEvent):
        """Dispatch trigger event to callbacks."""
        self._event_history.append(event)

        # Keep last 100 events
        if len(self._event_history) > 100:
            self._event_history = self._event_history[-100:]

        logger.info(f"Trigger fired: {event.trigger_type.value} - {event.reason}")

        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Trigger callback error: {e}")

    def get_event_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trigger events.

        Args:
            limit: Maximum events to return

        Returns:
            List of event dictionaries
        """
        return [e.to_dict() for e in self._event_history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get trigger statistics."""
        event_counts = {}
        for event in self._event_history:
            key = event.trigger_type.value
            event_counts[key] = event_counts.get(key, 0) + 1

        return {
            "model_name": self.model_name,
            "running": self._running,
            "total_events": len(self._event_history),
            "events_by_type": event_counts,
            "config": {
                "schedule_interval": self.config.schedule_interval,
                "performance_threshold": self.config.performance_threshold,
                "drift_threshold": self.config.drift_threshold,
                "max_model_age_days": self.config.max_model_age_days,
            },
        }
