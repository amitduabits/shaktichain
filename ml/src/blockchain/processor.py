"""BlockchainEventProcessor for processing trade and auction events.

Provides:
- Feature extraction from blockchain events
- Anomaly detection scoring
- Feature store updates
- Trading agent triggers
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class ProcessedEvent:
    """Result of processing a blockchain event."""
    event_id: str
    event_type: str
    timestamp: datetime
    features: Dict[str, Any]
    anomaly_score: Optional[float] = None
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_anomalous(self) -> bool:
        """Check if event is anomalous."""
        return self.anomaly_score is not None and self.anomaly_score > 0.8


class EventProcessor(ABC):
    """Abstract base class for event processors."""

    @abstractmethod
    async def process(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process an event and extract features."""
        pass


class TradeProcessor(EventProcessor):
    """Process trade events from blockchain."""

    def __init__(
        self,
        feature_store: Optional[Any] = None,
        anomaly_detector: Optional[Any] = None,
        alert_service: Optional[Any] = None,
    ):
        """Initialize trade processor.

        Args:
            feature_store: Feature store for updates
            anomaly_detector: Anomaly detection model
            alert_service: Alert service for notifications
        """
        self.feature_store = feature_store
        self.anomaly_detector = anomaly_detector
        self.alert_service = alert_service

        # Maintain rolling statistics
        self._trade_count = 0
        self._volume_sum = 0.0
        self._price_history: List[float] = []
        self._max_price_history = 1000

        # Statistics
        self._stats = {
            "trades_processed": 0,
            "anomalies_detected": 0,
            "alerts_sent": 0,
        }

    async def process(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process a trade event.

        Args:
            event: Raw trade event from subgraph

        Returns:
            ProcessedEvent with extracted features
        """
        self._stats["trades_processed"] += 1

        # Extract raw values
        trade_id = event.get("id", "unknown")
        quantity = float(event.get("quantity", 0))
        price = float(event.get("price", 0))
        timestamp = event.get("timestamp")
        energy_kwh = float(event.get("energyKwh", quantity * 10))

        # Parse timestamp
        if isinstance(timestamp, (int, float)):
            event_time = datetime.fromtimestamp(timestamp)
        else:
            event_time = datetime.now()

        # Extract participant info
        buyer = event.get("buyer", {})
        seller = event.get("seller", {})

        buyer_reputation = float(buyer.get("reputation", 50)) / 100
        seller_reputation = float(seller.get("reputation", 50)) / 100
        buyer_trades = int(buyer.get("totalTrades", 0))
        seller_trades = int(seller.get("totalTrades", 0))

        # Update internal state
        self._trade_count += 1
        self._volume_sum += quantity
        self._price_history.append(price)
        if len(self._price_history) > self._max_price_history:
            self._price_history.pop(0)

        # Calculate derived features
        features = {
            # Basic trade features
            "trade_volume": quantity,
            "trade_price": price,
            "energy_kwh": energy_kwh,
            "price_per_kwh": price / max(energy_kwh, 0.001),

            # Participant features
            "buyer_reputation": buyer_reputation,
            "seller_reputation": seller_reputation,
            "buyer_trades": buyer_trades,
            "seller_trades": seller_trades,
            "reputation_diff": buyer_reputation - seller_reputation,
            "experience_ratio": buyer_trades / max(seller_trades, 1),

            # Time features
            "hour": event_time.hour,
            "day_of_week": event_time.weekday(),
            "is_weekend": event_time.weekday() >= 5,
            "is_peak_hour": 7 <= event_time.hour <= 19,

            # Price context
            "price_vs_mean": self._price_vs_mean(price),
            "price_vs_recent": self._price_vs_recent(price),
            "price_percentile": self._price_percentile(price),

            # Volume context
            "volume_vs_mean": self._volume_vs_mean(quantity),
            "cumulative_volume": self._volume_sum,
            "trade_count": self._trade_count,
        }

        # Update feature store
        if self.feature_store:
            await self._update_feature_store(features, event_time)

        # Score for anomaly
        anomaly_score = None
        if self.anomaly_detector:
            anomaly_score = await self._score_anomaly(features)

        # Generate alerts
        alerts = []
        if anomaly_score and anomaly_score > 0.8:
            self._stats["anomalies_detected"] += 1
            alert = await self._create_alert(event, features, anomaly_score)
            alerts.append(alert)

            if self.alert_service:
                await self.alert_service.send(alert)
                self._stats["alerts_sent"] += 1

        return ProcessedEvent(
            event_id=trade_id,
            event_type="trade",
            timestamp=event_time,
            features=features,
            anomaly_score=anomaly_score,
            alerts=alerts,
            metadata={
                "buyer_id": buyer.get("id"),
                "seller_id": seller.get("id"),
                "status": event.get("status"),
                "trade_type": event.get("tradeType"),
                "block_number": event.get("blockNumber"),
                "tx_hash": event.get("transactionHash"),
            },
        )

    def _price_vs_mean(self, price: float) -> float:
        """Calculate price deviation from mean."""
        if not self._price_history:
            return 0.0
        mean_price = sum(self._price_history) / len(self._price_history)
        if mean_price == 0:
            return 0.0
        return (price - mean_price) / mean_price

    def _price_vs_recent(self, price: float, window: int = 10) -> float:
        """Calculate price deviation from recent average."""
        recent = self._price_history[-window:] if self._price_history else []
        if not recent:
            return 0.0
        recent_mean = sum(recent) / len(recent)
        if recent_mean == 0:
            return 0.0
        return (price - recent_mean) / recent_mean

    def _price_percentile(self, price: float) -> float:
        """Calculate price percentile in history."""
        if not self._price_history:
            return 0.5
        below = sum(1 for p in self._price_history if p < price)
        return below / len(self._price_history)

    def _volume_vs_mean(self, volume: float) -> float:
        """Calculate volume deviation from mean."""
        if self._trade_count == 0:
            return 0.0
        mean_volume = self._volume_sum / self._trade_count
        if mean_volume == 0:
            return 0.0
        return (volume - mean_volume) / mean_volume

    async def _update_feature_store(
        self,
        features: Dict[str, Any],
        timestamp: datetime,
    ):
        """Update feature store with trade features."""
        try:
            # Import feature store types
            from ..features.pipeline.store import FeatureKey, FeatureValue, FeatureCategory

            for name, value in features.items():
                key = FeatureKey(
                    name=f"trade_{name}",
                    entity_type="market",
                    entity_id="spot",
                )
                feat_value = FeatureValue(
                    value=value,
                    timestamp=timestamp,
                    category=FeatureCategory.TRADING,
                    ttl_seconds=300,  # 5 minutes TTL
                )
                await self.feature_store.set(key, feat_value)

        except Exception as e:
            logger.error(f"Failed to update feature store: {e}")

    async def _score_anomaly(self, features: Dict[str, Any]) -> float:
        """Score event for anomaly."""
        try:
            # Prepare feature vector
            feature_vector = [
                features.get("trade_volume", 0),
                features.get("trade_price", 0),
                features.get("buyer_reputation", 0.5),
                features.get("seller_reputation", 0.5),
                features.get("price_vs_mean", 0),
                features.get("volume_vs_mean", 0),
            ]

            # Score with anomaly detector
            if hasattr(self.anomaly_detector, "score"):
                return await self.anomaly_detector.score(feature_vector)
            elif hasattr(self.anomaly_detector, "predict"):
                import numpy as np
                score = self.anomaly_detector.predict([feature_vector])[0]
                return float(score)

            return 0.0

        except Exception as e:
            logger.error(f"Anomaly scoring failed: {e}")
            return 0.0

    async def _create_alert(
        self,
        event: Dict[str, Any],
        features: Dict[str, Any],
        anomaly_score: float,
    ) -> Dict[str, Any]:
        """Create alert for anomalous trade."""
        return {
            "type": "trade_anomaly",
            "severity": "high" if anomaly_score > 0.95 else "medium",
            "trade_id": event.get("id"),
            "anomaly_score": anomaly_score,
            "features": {
                "price": features.get("trade_price"),
                "volume": features.get("trade_volume"),
                "price_deviation": features.get("price_vs_mean"),
                "volume_deviation": features.get("volume_vs_mean"),
            },
            "timestamp": datetime.now().isoformat(),
            "buyer_id": event.get("buyer", {}).get("id"),
            "seller_id": event.get("seller", {}).get("id"),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            **self._stats,
            "trade_count": self._trade_count,
            "volume_sum": self._volume_sum,
            "price_history_size": len(self._price_history),
        }


class AuctionProcessor(EventProcessor):
    """Process auction events from blockchain."""

    def __init__(
        self,
        feature_store: Optional[Any] = None,
        trading_agent: Optional[Any] = None,
    ):
        """Initialize auction processor.

        Args:
            feature_store: Feature store for updates
            trading_agent: Trading agent for re-evaluation triggers
        """
        self.feature_store = feature_store
        self.trading_agent = trading_agent

        # Historical data
        self._clearing_prices: List[float] = []
        self._volumes: List[float] = []

        # Statistics
        self._stats = {
            "auctions_processed": 0,
            "agent_triggers": 0,
        }

    async def process(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process an auction event.

        Args:
            event: Raw auction event from subgraph

        Returns:
            ProcessedEvent with extracted features
        """
        self._stats["auctions_processed"] += 1

        # Extract raw values
        auction_id = event.get("id", "unknown")
        clearing_price = float(event.get("clearingPrice", 0))
        total_volume = float(event.get("totalVolume", 0))
        participant_count = int(event.get("participantCount", 0))
        min_price = float(event.get("minPrice", 0))
        max_price = float(event.get("maxPrice", 0))

        # Parse timestamps
        end_time = event.get("endTime")
        if isinstance(end_time, (int, float)):
            event_time = datetime.fromtimestamp(end_time)
        else:
            event_time = datetime.now()

        # Update history
        self._clearing_prices.append(clearing_price)
        self._volumes.append(total_volume)
        if len(self._clearing_prices) > 100:
            self._clearing_prices.pop(0)
            self._volumes.pop(0)

        # Calculate features
        features = {
            # Auction results
            "clearing_price": clearing_price,
            "total_volume": total_volume,
            "participant_count": participant_count,

            # Price range
            "min_price": min_price,
            "max_price": max_price,
            "price_spread": max_price - min_price,
            "clearing_vs_mid": clearing_price - (min_price + max_price) / 2,

            # Volume per participant
            "volume_per_participant": total_volume / max(participant_count, 1),

            # Historical context
            "clearing_vs_avg": self._vs_average(clearing_price, self._clearing_prices),
            "volume_vs_avg": self._vs_average(total_volume, self._volumes),

            # Time features
            "hour": event_time.hour,
            "is_peak_hour": 7 <= event_time.hour <= 19,
        }

        # Update feature store for price forecasting
        if self.feature_store:
            await self._update_feature_store(features, event_time)

        # Trigger trading agent re-evaluation
        if self.trading_agent:
            await self._trigger_trading_agent(features, event)
            self._stats["agent_triggers"] += 1

        return ProcessedEvent(
            event_id=auction_id,
            event_type="auction",
            timestamp=event_time,
            features=features,
            metadata={
                "auction_type": event.get("auctionType"),
                "status": event.get("status"),
                "block_number": event.get("blockNumber"),
            },
        )

    def _vs_average(self, value: float, history: List[float]) -> float:
        """Calculate deviation from historical average."""
        if not history:
            return 0.0
        avg = sum(history) / len(history)
        if avg == 0:
            return 0.0
        return (value - avg) / avg

    async def _update_feature_store(
        self,
        features: Dict[str, Any],
        timestamp: datetime,
    ):
        """Update feature store with auction data."""
        try:
            from ..features.pipeline.store import FeatureKey, FeatureValue, FeatureCategory

            for name, value in features.items():
                key = FeatureKey(
                    name=f"auction_{name}",
                    entity_type="market",
                    entity_id="clearing",
                )
                feat_value = FeatureValue(
                    value=value,
                    timestamp=timestamp,
                    category=FeatureCategory.TRADING,
                    ttl_seconds=3600,  # 1 hour TTL
                )
                await self.feature_store.set(key, feat_value)

        except Exception as e:
            logger.error(f"Failed to update feature store: {e}")

    async def _trigger_trading_agent(
        self,
        features: Dict[str, Any],
        event: Dict[str, Any],
    ):
        """Trigger trading agent re-evaluation."""
        try:
            if hasattr(self.trading_agent, "on_auction_close"):
                await self.trading_agent.on_auction_close(features, event)
            elif hasattr(self.trading_agent, "reevaluate"):
                await self.trading_agent.reevaluate()
        except Exception as e:
            logger.error(f"Trading agent trigger failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            **self._stats,
            "clearing_prices_history": len(self._clearing_prices),
        }


class OracleProcessor(EventProcessor):
    """Process oracle update events."""

    def __init__(
        self,
        feature_store: Optional[Any] = None,
        trading_agent: Optional[Any] = None,
    ):
        """Initialize oracle processor."""
        self.feature_store = feature_store
        self.trading_agent = trading_agent

        self._last_price: Optional[float] = None
        self._price_updates = 0

    async def process(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process oracle price update."""
        self._price_updates += 1

        price = float(event.get("price", 0))
        confidence = float(event.get("confidence", 1.0))
        source = event.get("source", "unknown")

        timestamp = event.get("timestamp")
        if isinstance(timestamp, (int, float)):
            event_time = datetime.fromtimestamp(timestamp)
        else:
            event_time = datetime.now()

        # Calculate price change
        price_change = 0.0
        if self._last_price:
            price_change = (price - self._last_price) / self._last_price
        self._last_price = price

        features = {
            "oracle_price": price,
            "price_confidence": confidence,
            "price_change": price_change,
            "price_change_abs": abs(price_change),
        }

        # Update feature store
        if self.feature_store:
            await self._update_feature_store(features, event_time, source)

        # Trigger trading agent on significant price change
        if abs(price_change) > 0.02 and self.trading_agent:  # > 2% change
            if hasattr(self.trading_agent, "on_price_update"):
                await self.trading_agent.on_price_update(price, price_change)

        return ProcessedEvent(
            event_id=event.get("id", str(self._price_updates)),
            event_type="oracle_price",
            timestamp=event_time,
            features=features,
            metadata={
                "oracle": event.get("oracle"),
                "source": source,
                "block_number": event.get("blockNumber"),
            },
        )

    async def _update_feature_store(
        self,
        features: Dict[str, Any],
        timestamp: datetime,
        source: str,
    ):
        """Update feature store with oracle data."""
        try:
            from ..features.pipeline.store import FeatureKey, FeatureValue, FeatureCategory

            for name, value in features.items():
                key = FeatureKey(
                    name=name,
                    entity_type="oracle",
                    entity_id=source,
                )
                feat_value = FeatureValue(
                    value=value,
                    timestamp=timestamp,
                    category=FeatureCategory.PRICE,
                    ttl_seconds=60,  # Short TTL for oracle data
                )
                await self.feature_store.set(key, feat_value)

        except Exception as e:
            logger.error(f"Failed to update feature store: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            "price_updates": self._price_updates,
            "last_price": self._last_price,
        }


class BlockchainEventProcessor:
    """Main processor coordinating all event types."""

    def __init__(
        self,
        feature_store: Optional[Any] = None,
        anomaly_detector: Optional[Any] = None,
        alert_service: Optional[Any] = None,
        trading_agent: Optional[Any] = None,
    ):
        """Initialize blockchain event processor.

        Args:
            feature_store: Feature store for updates
            anomaly_detector: Anomaly detection model
            alert_service: Alert service for notifications
            trading_agent: Trading agent for triggers
        """
        self.trade_processor = TradeProcessor(
            feature_store=feature_store,
            anomaly_detector=anomaly_detector,
            alert_service=alert_service,
        )
        self.auction_processor = AuctionProcessor(
            feature_store=feature_store,
            trading_agent=trading_agent,
        )
        self.oracle_processor = OracleProcessor(
            feature_store=feature_store,
            trading_agent=trading_agent,
        )

        # Event handlers
        self._handlers: Dict[str, List[Callable]] = {
            "trade": [],
            "auction": [],
            "oracle": [],
        }

        self._stats = {
            "events_processed": 0,
            "errors": 0,
        }

    def add_handler(
        self,
        event_type: str,
        handler: Callable[[ProcessedEvent], None],
    ):
        """Add handler for processed events.

        Args:
            event_type: Type of event (trade, auction, oracle)
            handler: Handler function
        """
        if event_type in self._handlers:
            self._handlers[event_type].append(handler)

    async def process_trade(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process a trade event."""
        self._stats["events_processed"] += 1

        try:
            result = await self.trade_processor.process(event)

            # Dispatch to handlers
            for handler in self._handlers["trade"]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(result)
                    else:
                        handler(result)
                except Exception as e:
                    logger.error(f"Trade handler error: {e}")

            return result

        except Exception as e:
            logger.error(f"Trade processing error: {e}")
            self._stats["errors"] += 1
            raise

    async def process_auction_close(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process an auction close event."""
        self._stats["events_processed"] += 1

        try:
            result = await self.auction_processor.process(event)

            for handler in self._handlers["auction"]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(result)
                    else:
                        handler(result)
                except Exception as e:
                    logger.error(f"Auction handler error: {e}")

            return result

        except Exception as e:
            logger.error(f"Auction processing error: {e}")
            self._stats["errors"] += 1
            raise

    async def process_oracle_update(self, event: Dict[str, Any]) -> ProcessedEvent:
        """Process an oracle update event."""
        self._stats["events_processed"] += 1

        try:
            result = await self.oracle_processor.process(event)

            for handler in self._handlers["oracle"]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(result)
                    else:
                        handler(result)
                except Exception as e:
                    logger.error(f"Oracle handler error: {e}")

            return result

        except Exception as e:
            logger.error(f"Oracle processing error: {e}")
            self._stats["errors"] += 1
            raise

    async def process_subscription_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ):
        """Process event from subscription.

        Args:
            event_type: Type of subscription event
            data: Event data from subscription
        """
        if event_type == "trades":
            trades = data.get("trades", [])
            for trade in trades:
                await self.process_trade(trade)

        elif event_type == "auctions":
            auctions = data.get("auctions", [])
            for auction in auctions:
                await self.process_auction_close(auction)

        elif event_type == "priceUpdates":
            updates = data.get("priceUpdates", [])
            for update in updates:
                await self.process_oracle_update(update)

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            **self._stats,
            "trade_processor": self.trade_processor.get_stats(),
            "auction_processor": self.auction_processor.get_stats(),
            "oracle_processor": self.oracle_processor.get_stats(),
        }
