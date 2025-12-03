"""Oracle data subscriptions for SHAKTI-CHAIN.

Provides:
- PriceOracle: Real-time energy price feeds
- GridStatus: Grid load, frequency, generation data
- Integration with trading decisions
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OracleType(Enum):
    """Types of oracles."""
    PRICE = "price"
    GRID_LOAD = "grid_load"
    GRID_FREQUENCY = "grid_frequency"
    GRID_GENERATION = "grid_generation"
    WEATHER = "weather"
    SOLAR = "solar"


@dataclass
class OracleUpdate:
    """Update from an oracle."""
    oracle_type: OracleType
    value: float
    timestamp: datetime
    source: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PriceOracleClient:
    """Client for price oracle data."""

    def __init__(
        self,
        subgraph_client=None,
        contract_address: Optional[str] = None,
        poll_interval: float = 5.0,
    ):
        """Initialize price oracle client.

        Args:
            subgraph_client: SubgraphClient for subscriptions
            contract_address: Oracle contract address
            poll_interval: Polling interval in seconds
        """
        self.subgraph = subgraph_client
        self.contract_address = contract_address
        self.poll_interval = poll_interval

        # Callbacks
        self._callbacks: List[Callable[[OracleUpdate], None]] = []

        # State
        self._running = False
        self._last_price: Optional[float] = None
        self._last_update: Optional[datetime] = None

        # Statistics
        self._stats = {
            "updates_received": 0,
            "price_changes": 0,
            "errors": 0,
        }

    def on_update(self, callback: Callable[[OracleUpdate], None]):
        """Register callback for price updates.

        Args:
            callback: Callback function
        """
        self._callbacks.append(callback)

    async def start(self):
        """Start price oracle subscription."""
        self._running = True
        logger.info("Starting price oracle client")

        if self.subgraph:
            # Use subgraph subscription
            await self.subgraph.subscribe_price_updates(self._handle_subscription)
        else:
            # Fall back to polling
            await self._poll_loop()

    async def stop(self):
        """Stop price oracle client."""
        self._running = False
        logger.info("Price oracle client stopped")

    async def _poll_loop(self):
        """Poll for price updates (fallback mode)."""
        while self._running:
            try:
                # Mock price update for demo
                import random
                price = 50.0 + random.gauss(0, 2)

                update = OracleUpdate(
                    oracle_type=OracleType.PRICE,
                    value=price,
                    timestamp=datetime.now(),
                    source="mock",
                    confidence=0.95,
                )

                await self._dispatch_update(update)
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Price poll error: {e}")
                self._stats["errors"] += 1
                await asyncio.sleep(self.poll_interval)

    async def _handle_subscription(self, data: Dict[str, Any]):
        """Handle subscription event."""
        price_updates = data.get("priceUpdates", [])

        for update_data in price_updates:
            try:
                price = float(update_data.get("price", 0))
                timestamp = update_data.get("timestamp")

                if isinstance(timestamp, (int, float)):
                    update_time = datetime.fromtimestamp(timestamp)
                else:
                    update_time = datetime.now()

                update = OracleUpdate(
                    oracle_type=OracleType.PRICE,
                    value=price,
                    timestamp=update_time,
                    source=update_data.get("source", "subgraph"),
                    confidence=float(update_data.get("confidence", 1.0)),
                    metadata={
                        "oracle": update_data.get("oracle"),
                        "block_number": update_data.get("blockNumber"),
                    },
                )

                await self._dispatch_update(update)

            except Exception as e:
                logger.error(f"Price update processing error: {e}")
                self._stats["errors"] += 1

    async def _dispatch_update(self, update: OracleUpdate):
        """Dispatch update to callbacks."""
        self._stats["updates_received"] += 1

        # Check for price change
        if self._last_price is not None and update.value != self._last_price:
            self._stats["price_changes"] += 1

        self._last_price = update.value
        self._last_update = update.timestamp

        # Dispatch to callbacks
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(f"Price callback error: {e}")

    def get_last_price(self) -> Optional[float]:
        """Get last known price."""
        return self._last_price

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            **self._stats,
            "last_price": self._last_price,
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }


class GridStatusClient:
    """Client for grid status data."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        subgraph_client=None,
        poll_interval: float = 10.0,
    ):
        """Initialize grid status client.

        Args:
            api_url: Grid API URL
            subgraph_client: SubgraphClient for subscriptions
            poll_interval: Polling interval in seconds
        """
        self.api_url = api_url
        self.subgraph = subgraph_client
        self.poll_interval = poll_interval

        # Callbacks by oracle type
        self._callbacks: Dict[OracleType, List[Callable]] = {
            OracleType.GRID_LOAD: [],
            OracleType.GRID_FREQUENCY: [],
            OracleType.GRID_GENERATION: [],
        }

        # State
        self._running = False
        self._last_values: Dict[OracleType, float] = {}
        self._last_updates: Dict[OracleType, datetime] = {}

        # Statistics
        self._stats = {
            "updates_received": 0,
            "api_calls": 0,
            "errors": 0,
        }

    def on_load_update(self, callback: Callable[[OracleUpdate], None]):
        """Register callback for load updates."""
        self._callbacks[OracleType.GRID_LOAD].append(callback)

    def on_frequency_update(self, callback: Callable[[OracleUpdate], None]):
        """Register callback for frequency updates."""
        self._callbacks[OracleType.GRID_FREQUENCY].append(callback)

    def on_generation_update(self, callback: Callable[[OracleUpdate], None]):
        """Register callback for generation updates."""
        self._callbacks[OracleType.GRID_GENERATION].append(callback)

    async def start(self):
        """Start grid status monitoring."""
        self._running = True
        logger.info("Starting grid status client")

        await self._poll_loop()

    async def stop(self):
        """Stop grid status client."""
        self._running = False
        logger.info("Grid status client stopped")

    async def _poll_loop(self):
        """Poll for grid status updates."""
        while self._running:
            try:
                await self._fetch_grid_status()
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Grid poll error: {e}")
                self._stats["errors"] += 1
                await asyncio.sleep(self.poll_interval)

    async def _fetch_grid_status(self):
        """Fetch current grid status."""
        self._stats["api_calls"] += 1

        try:
            if self.api_url:
                # Real API call
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.api_url}/status") as resp:
                        data = await resp.json()
                        await self._process_grid_data(data)
            else:
                # Mock data for demo
                await self._generate_mock_data()

        except ImportError:
            # aiohttp not available, use mock
            await self._generate_mock_data()

    async def _generate_mock_data(self):
        """Generate mock grid data."""
        import random

        now = datetime.now()

        # Grid load (MW)
        load_update = OracleUpdate(
            oracle_type=OracleType.GRID_LOAD,
            value=30000 + random.gauss(0, 2000),  # ~30 GW typical load
            timestamp=now,
            source="mock",
            confidence=0.99,
        )
        await self._dispatch_update(load_update)

        # Grid frequency (Hz)
        freq_update = OracleUpdate(
            oracle_type=OracleType.GRID_FREQUENCY,
            value=50.0 + random.gauss(0, 0.02),  # ~50 Hz with small deviation
            timestamp=now,
            source="mock",
            confidence=0.999,
        )
        await self._dispatch_update(freq_update)

        # Generation mix (MW of renewable)
        gen_update = OracleUpdate(
            oracle_type=OracleType.GRID_GENERATION,
            value=15000 + random.gauss(0, 3000),  # Renewable generation
            timestamp=now,
            source="mock",
            confidence=0.95,
            metadata={"type": "renewable"},
        )
        await self._dispatch_update(gen_update)

    async def _process_grid_data(self, data: Dict[str, Any]):
        """Process grid API response."""
        now = datetime.now()

        if "load" in data:
            update = OracleUpdate(
                oracle_type=OracleType.GRID_LOAD,
                value=float(data["load"]),
                timestamp=now,
                source="api",
                confidence=data.get("confidence", 0.99),
            )
            await self._dispatch_update(update)

        if "frequency" in data:
            update = OracleUpdate(
                oracle_type=OracleType.GRID_FREQUENCY,
                value=float(data["frequency"]),
                timestamp=now,
                source="api",
                confidence=0.999,
            )
            await self._dispatch_update(update)

        if "generation" in data:
            update = OracleUpdate(
                oracle_type=OracleType.GRID_GENERATION,
                value=float(data["generation"]),
                timestamp=now,
                source="api",
                confidence=data.get("confidence", 0.95),
                metadata=data.get("generation_metadata", {}),
            )
            await self._dispatch_update(update)

    async def _dispatch_update(self, update: OracleUpdate):
        """Dispatch update to callbacks."""
        self._stats["updates_received"] += 1
        self._last_values[update.oracle_type] = update.value
        self._last_updates[update.oracle_type] = update.timestamp

        callbacks = self._callbacks.get(update.oracle_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(f"Grid callback error: {e}")

    def get_last_values(self) -> Dict[str, float]:
        """Get last known values."""
        return {k.value: v for k, v in self._last_values.items()}

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            **self._stats,
            "last_values": self.get_last_values(),
        }


class OracleSubscriber:
    """Unified subscriber for all oracle data."""

    def __init__(
        self,
        subgraph_client=None,
        grid_api_url: Optional[str] = None,
        feature_store=None,
        trading_agent=None,
    ):
        """Initialize oracle subscriber.

        Args:
            subgraph_client: SubgraphClient for blockchain subscriptions
            grid_api_url: Grid API URL
            feature_store: Feature store for updates
            trading_agent: Trading agent for decision triggers
        """
        self.price_oracle = PriceOracleClient(
            subgraph_client=subgraph_client,
        )
        self.grid_status = GridStatusClient(
            api_url=grid_api_url,
            subgraph_client=subgraph_client,
        )
        self.feature_store = feature_store
        self.trading_agent = trading_agent

        # Register internal handlers
        self.price_oracle.on_update(self._on_price_update)
        self.grid_status.on_load_update(self._on_grid_update)
        self.grid_status.on_frequency_update(self._on_grid_update)

        # External callbacks
        self._callbacks: List[Callable[[OracleUpdate], None]] = []

        self._running = False

    def on_update(self, callback: Callable[[OracleUpdate], None]):
        """Register callback for all oracle updates."""
        self._callbacks.append(callback)

    async def start(self):
        """Start all oracle subscriptions."""
        self._running = True
        logger.info("Starting oracle subscriber")

        await asyncio.gather(
            self.price_oracle.start(),
            self.grid_status.start(),
        )

    async def stop(self):
        """Stop all oracle subscriptions."""
        self._running = False
        await self.price_oracle.stop()
        await self.grid_status.stop()
        logger.info("Oracle subscriber stopped")

    async def _on_price_update(self, update: OracleUpdate):
        """Handle price oracle update."""
        # Update feature store
        if self.feature_store:
            await self._update_feature_store(update)

        # Check for trading triggers
        if self.trading_agent:
            await self._check_trading_trigger(update)

        # Dispatch to external callbacks
        await self._dispatch(update)

    async def _on_grid_update(self, update: OracleUpdate):
        """Handle grid status update."""
        if self.feature_store:
            await self._update_feature_store(update)

        # Check for grid anomalies
        if update.oracle_type == OracleType.GRID_FREQUENCY:
            # Frequency deviation > 0.1 Hz is significant
            if abs(update.value - 50.0) > 0.1:
                logger.warning(f"Grid frequency deviation: {update.value} Hz")
                if self.trading_agent and hasattr(self.trading_agent, "on_grid_alert"):
                    await self.trading_agent.on_grid_alert(update)

        await self._dispatch(update)

    async def _update_feature_store(self, update: OracleUpdate):
        """Update feature store with oracle data."""
        try:
            from ..features.pipeline.store import FeatureKey, FeatureValue, FeatureCategory

            # Determine feature name and category
            feature_name = update.oracle_type.value
            if update.oracle_type == OracleType.PRICE:
                category = FeatureCategory.PRICE
                ttl = 60
            else:
                category = FeatureCategory.GRID
                ttl = 120

            key = FeatureKey(
                name=feature_name,
                entity_type="oracle",
                entity_id=update.source,
            )
            value = FeatureValue(
                value=update.value,
                timestamp=update.timestamp,
                category=category,
                ttl_seconds=ttl,
            )

            await self.feature_store.set(key, value)

        except Exception as e:
            logger.error(f"Feature store update failed: {e}")

    async def _check_trading_trigger(self, update: OracleUpdate):
        """Check if trading agent should be triggered."""
        if not self.trading_agent:
            return

        try:
            # Trigger on significant price changes
            last_price = self.price_oracle._last_price
            if last_price and update.value:
                change_pct = abs(update.value - last_price) / last_price

                if change_pct > 0.02:  # > 2% change
                    if hasattr(self.trading_agent, "on_price_signal"):
                        await self.trading_agent.on_price_signal(
                            price=update.value,
                            change_pct=change_pct,
                            confidence=update.confidence,
                        )

        except Exception as e:
            logger.error(f"Trading trigger check failed: {e}")

    async def _dispatch(self, update: OracleUpdate):
        """Dispatch update to external callbacks."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(f"Oracle callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        return {
            "price_oracle": self.price_oracle.get_stats(),
            "grid_status": self.grid_status.get_stats(),
        }
