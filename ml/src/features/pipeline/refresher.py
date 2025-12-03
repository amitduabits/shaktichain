"""Feature refresher for scheduled and event-triggered updates.

Handles:
- Event-triggered feature updates
- Scheduled periodic refreshes
- Feature staleness monitoring
- Triggered model re-runs
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from .events import Event, EventType, TradeEvent, PriceEvent, GridEvent
from .processor import StreamingFeatureProcessor
from .store import (
    FeatureStore,
    FeatureStoreWriter,
    FeatureKey,
    FeatureValue,
    FeatureCategory,
)

logger = logging.getLogger(__name__)


class RefreshTrigger(Enum):
    """Types of refresh triggers."""
    EVENT = "event"           # Triggered by specific event
    SCHEDULE = "schedule"     # Scheduled interval
    THRESHOLD = "threshold"   # Value threshold crossed
    STALENESS = "staleness"   # Feature became stale
    MANUAL = "manual"         # Manual trigger


@dataclass
class RefreshSchedule:
    """Schedule configuration for feature refresh."""
    name: str
    interval_seconds: int
    feature_names: List[str] = field(default_factory=list)
    refresh_func: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True

    def is_due(self) -> bool:
        """Check if refresh is due."""
        if not self.enabled:
            return False
        if self.next_run is None:
            return True
        return datetime.now() >= self.next_run

    def update_next_run(self):
        """Update next run time."""
        self.last_run = datetime.now()
        self.next_run = datetime.now() + timedelta(seconds=self.interval_seconds)


@dataclass
class RefreshThreshold:
    """Threshold-based refresh trigger."""
    feature_name: str
    threshold_value: float
    comparison: str = "gt"  # gt, lt, eq, change_pct
    cooldown_seconds: int = 60
    last_triggered: Optional[datetime] = None
    callback: Optional[Callable[[str, float], Awaitable[None]]] = None

    def check(self, value: float) -> bool:
        """Check if threshold is crossed."""
        # Check cooldown
        if self.last_triggered:
            if (datetime.now() - self.last_triggered).total_seconds() < self.cooldown_seconds:
                return False

        if self.comparison == "gt":
            return value > self.threshold_value
        elif self.comparison == "lt":
            return value < self.threshold_value
        elif self.comparison == "eq":
            return abs(value - self.threshold_value) < 1e-6
        elif self.comparison == "change_pct":
            # Need historical value for this
            return False

        return False


class FeatureRefresher:
    """Manage feature refreshes from events and schedules."""

    def __init__(
        self,
        processor: StreamingFeatureProcessor,
        store: FeatureStore,
        store_writer: Optional[FeatureStoreWriter] = None,
    ):
        """Initialize refresher.

        Args:
            processor: Streaming feature processor
            store: Feature store
            store_writer: Feature store writer
        """
        self.processor = processor
        self.store = store
        self.store_writer = store_writer or FeatureStoreWriter(store)

        # Schedules
        self.schedules: Dict[str, RefreshSchedule] = {}

        # Thresholds
        self.thresholds: List[RefreshThreshold] = []

        # Event handlers
        self._event_handlers: Dict[EventType, List[Callable]] = {}

        # Callbacks for model triggers
        self._model_triggers: List[Callable[[str, Dict[str, Any]], Awaitable[None]]] = []

        # Running state
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats = {
            'events_processed': 0,
            'scheduled_refreshes': 0,
            'threshold_triggers': 0,
            'features_updated': 0,
            'errors': 0,
        }

        # Setup default schedules
        self._setup_default_schedules()

    def _setup_default_schedules(self):
        """Setup default refresh schedules."""
        # Weather refresh every 5 minutes
        self.add_schedule(RefreshSchedule(
            name="weather",
            interval_seconds=300,
            feature_names=["temperature", "humidity", "solar_irradiance"],
        ))

        # Grid status refresh every minute
        self.add_schedule(RefreshSchedule(
            name="grid_status",
            interval_seconds=60,
            feature_names=["grid_load", "grid_frequency", "grid_price"],
        ))

        # Forecast model refresh every hour
        self.add_schedule(RefreshSchedule(
            name="forecasts",
            interval_seconds=3600,
            feature_names=["load_forecast", "price_forecast"],
        ))

        # Feature aggregations every 5 minutes
        self.add_schedule(RefreshSchedule(
            name="aggregations",
            interval_seconds=300,
            feature_names=["hourly_stats", "daily_stats"],
        ))

    def add_schedule(self, schedule: RefreshSchedule):
        """Add a refresh schedule."""
        self.schedules[schedule.name] = schedule
        schedule.update_next_run()

    def remove_schedule(self, name: str) -> bool:
        """Remove a refresh schedule."""
        if name in self.schedules:
            del self.schedules[name]
            return True
        return False

    def add_threshold(self, threshold: RefreshThreshold):
        """Add a threshold trigger."""
        self.thresholds.append(threshold)

    def add_model_trigger(
        self,
        callback: Callable[[str, Dict[str, Any]], Awaitable[None]],
    ):
        """Add a callback for model triggering."""
        self._model_triggers.append(callback)

    def register_event_handler(
        self,
        event_type: EventType,
        handler: Callable[[Event, Dict[str, Any]], Awaitable[None]],
    ):
        """Register handler for specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def on_trade_event(self, event: TradeEvent):
        """Handle trade event and update features.

        Args:
            event: Trade event
        """
        self._stats['events_processed'] += 1

        try:
            # Process through streaming processor
            features = await self.processor.process_event(event)

            # Write to feature store
            market = getattr(event, 'trade_type', 'spot')
            count = await self.store_writer.write_features(
                features,
                category=FeatureCategory.REAL_TIME,
                entity_type="market",
                entity_id=market,
            )
            self._stats['features_updated'] += count

            # Check thresholds
            await self._check_thresholds(features)

            # Call registered handlers
            await self._call_event_handlers(event, features)

            # Check if should trigger model
            await self._check_model_triggers("trade", features)

        except Exception as e:
            logger.error(f"Trade event processing error: {e}")
            self._stats['errors'] += 1

    async def on_price_update(self, event: PriceEvent):
        """Handle price update event.

        Args:
            event: Price update event
        """
        self._stats['events_processed'] += 1

        try:
            # Process through streaming processor
            features = await self.processor.process_event(event)

            # Write to feature store
            market = event.market
            count = await self.store_writer.write_features(
                features,
                category=FeatureCategory.REAL_TIME,
                entity_type="market",
                entity_id=market,
            )
            self._stats['features_updated'] += count

            # Check price thresholds
            await self._check_thresholds(features)

            # Price updates often trigger trading agent
            await self._check_model_triggers("price", features)

        except Exception as e:
            logger.error(f"Price event processing error: {e}")
            self._stats['errors'] += 1

    async def on_grid_event(self, event: GridEvent):
        """Handle grid status event.

        Args:
            event: Grid event
        """
        self._stats['events_processed'] += 1

        try:
            # Process through streaming processor
            features = await self.processor.process_event(event)

            # Write to feature store
            count = await self.store_writer.write_features(
                features,
                category=FeatureCategory.REAL_TIME,
                entity_type="grid",
                entity_id=event.region,
            )
            self._stats['features_updated'] += count

            # Check for frequency deviations
            if event.frequency_deviation and abs(event.frequency_deviation) > 0.05:
                logger.warning(f"Grid frequency deviation: {event.frequency_deviation} Hz")
                await self._check_model_triggers("grid_alert", features)

        except Exception as e:
            logger.error(f"Grid event processing error: {e}")
            self._stats['errors'] += 1

    async def scheduled_refresh(self):
        """Run scheduled feature refresh tasks."""
        self._stats['scheduled_refreshes'] += 1

        for name, schedule in self.schedules.items():
            if not schedule.is_due():
                continue

            try:
                logger.debug(f"Running scheduled refresh: {name}")

                if schedule.refresh_func:
                    features = await schedule.refresh_func()
                else:
                    features = await self._default_refresh(schedule)

                if features:
                    count = await self.store_writer.write_features(
                        features,
                        category=FeatureCategory.SCHEDULED,
                        entity_type="scheduled",
                        entity_id=name,
                    )
                    self._stats['features_updated'] += count

                schedule.update_next_run()

            except Exception as e:
                logger.error(f"Scheduled refresh '{name}' failed: {e}")
                self._stats['errors'] += 1

    async def _default_refresh(
        self,
        schedule: RefreshSchedule,
    ) -> Dict[str, Any]:
        """Default refresh logic."""
        # Get current feature values and aggregate
        features = {}

        for feature_name in schedule.feature_names:
            key = FeatureKey(
                name=feature_name,
                entity_type="market",
                entity_id="default",
            )
            value = await self.store.get(key)
            if value:
                features[feature_name] = value.value

        return features

    async def _check_thresholds(self, features: Dict[str, Any]):
        """Check if any threshold triggers are met."""
        for threshold in self.thresholds:
            if threshold.feature_name not in features:
                continue

            value = features[threshold.feature_name]
            if not isinstance(value, (int, float)):
                continue

            if threshold.check(value):
                threshold.last_triggered = datetime.now()
                self._stats['threshold_triggers'] += 1

                logger.info(
                    f"Threshold triggered: {threshold.feature_name} "
                    f"{threshold.comparison} {threshold.threshold_value} "
                    f"(actual: {value})"
                )

                if threshold.callback:
                    try:
                        await threshold.callback(threshold.feature_name, value)
                    except Exception as e:
                        logger.error(f"Threshold callback error: {e}")

    async def _check_model_triggers(
        self,
        trigger_type: str,
        features: Dict[str, Any],
    ):
        """Check if model should be triggered."""
        for callback in self._model_triggers:
            try:
                await callback(trigger_type, features)
            except Exception as e:
                logger.error(f"Model trigger callback error: {e}")

    async def _call_event_handlers(
        self,
        event: Event,
        features: Dict[str, Any],
    ):
        """Call registered event handlers."""
        handlers = self._event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event, features)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def start(self):
        """Start the refresher with scheduled tasks."""
        self._running = True

        # Start scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Feature refresher started")

    async def stop(self):
        """Stop the refresher."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Feature refresher stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await self.scheduled_refresh()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Check every 10 seconds
            await asyncio.sleep(10)

    async def check_staleness(self) -> Dict[str, Any]:
        """Check feature staleness and generate alerts."""
        if hasattr(self.store, 'get_freshness_report'):
            return await self.store.get_freshness_report()

        # Basic staleness check
        return {
            'checked_at': datetime.now().isoformat(),
            'stats': self._stats,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get refresher statistics."""
        return {
            **self._stats,
            'schedules': {
                name: {
                    'interval_seconds': s.interval_seconds,
                    'last_run': s.last_run.isoformat() if s.last_run else None,
                    'next_run': s.next_run.isoformat() if s.next_run else None,
                    'enabled': s.enabled,
                }
                for name, s in self.schedules.items()
            },
            'thresholds': len(self.thresholds),
            'running': self._running,
        }


class ModelTriggerHandler:
    """Handle model triggering based on feature updates."""

    def __init__(
        self,
        model_service_url: str = "http://localhost:8000",
    ):
        """Initialize trigger handler.

        Args:
            model_service_url: URL of the model service
        """
        self.model_service_url = model_service_url
        self._last_trigger: Dict[str, datetime] = {}
        self._cooldown_seconds = 30  # Minimum time between triggers

        # Trigger conditions
        self.trigger_conditions = {
            'trading_agent': self._should_trigger_trading,
            'forecast_model': self._should_trigger_forecast,
            'anomaly_detector': self._should_trigger_anomaly,
        }

    async def __call__(
        self,
        trigger_type: str,
        features: Dict[str, Any],
    ):
        """Handle a potential model trigger.

        Args:
            trigger_type: Type of trigger (trade, price, grid, etc.)
            features: Current feature values
        """
        for model_name, condition in self.trigger_conditions.items():
            if await condition(trigger_type, features):
                await self._trigger_model(model_name, features)

    def _check_cooldown(self, model_name: str) -> bool:
        """Check if model is in cooldown period."""
        last = self._last_trigger.get(model_name)
        if last is None:
            return True

        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self._cooldown_seconds

    async def _should_trigger_trading(
        self,
        trigger_type: str,
        features: Dict[str, Any],
    ) -> bool:
        """Determine if trading agent should be triggered."""
        if not self._check_cooldown('trading_agent'):
            return False

        # Trigger on price updates with significant change
        if trigger_type == 'price':
            velocity = features.get('price_velocity_1m', 0)
            if abs(velocity) > 0.02:  # 2% change in 1 minute
                return True

        # Trigger on order imbalance shift
        imbalance = features.get('order_imbalance', 0)
        if abs(imbalance) > 0.3:  # Strong imbalance
            return True

        return False

    async def _should_trigger_forecast(
        self,
        trigger_type: str,
        features: Dict[str, Any],
    ) -> bool:
        """Determine if forecast model should be re-run."""
        if not self._check_cooldown('forecast_model'):
            return False

        # Trigger on significant grid load change
        if trigger_type == 'grid':
            load_change = features.get('load_1h_std', 0)
            if load_change > 100:  # High variability
                return True

        return False

    async def _should_trigger_anomaly(
        self,
        trigger_type: str,
        features: Dict[str, Any],
    ) -> bool:
        """Determine if anomaly detector should run."""
        if not self._check_cooldown('anomaly_detector'):
            return False

        # Always run on trades
        if trigger_type == 'trade':
            return True

        return False

    async def _trigger_model(
        self,
        model_name: str,
        features: Dict[str, Any],
    ):
        """Trigger a model with current features."""
        self._last_trigger[model_name] = datetime.now()

        logger.info(f"Triggering model: {model_name}")

        # In production, would call model service API
        # For now, just log
        try:
            # Example API call structure
            # async with aiohttp.ClientSession() as session:
            #     async with session.post(
            #         f"{self.model_service_url}/{model_name}/predict",
            #         json=features,
            #     ) as response:
            #         result = await response.json()
            pass
        except Exception as e:
            logger.error(f"Failed to trigger {model_name}: {e}")
