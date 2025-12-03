"""Event ingestion for the feature pipeline.

Handles:
- Blockchain event subscription (The Graph, web3)
- Grid API polling
- Weather API integration
- Redis Streams for event queue
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, AsyncIterator
from dataclasses import dataclass
from abc import ABC, abstractmethod
import threading
from queue import Queue, Empty

from .events import Event, EventType, EventParser, TradeEvent, PriceEvent, GridEvent

logger = logging.getLogger(__name__)

# Optional imports
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class EventQueue(ABC):
    """Abstract event queue interface."""

    @abstractmethod
    async def publish(self, event: Event) -> bool:
        """Publish event to queue."""
        pass

    @abstractmethod
    async def consume(self, timeout: float = 1.0) -> Optional[Event]:
        """Consume next event from queue."""
        pass

    @abstractmethod
    async def acknowledge(self, event_id: str) -> bool:
        """Acknowledge event processing."""
        pass


class InMemoryEventQueue(EventQueue):
    """Simple in-memory event queue for testing."""

    def __init__(self, max_size: int = 10000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._pending: Dict[str, Event] = {}

    async def publish(self, event: Event) -> bool:
        try:
            await asyncio.wait_for(
                self._queue.put(event),
                timeout=1.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Event queue full, dropping event")
            return False

    async def consume(self, timeout: float = 1.0) -> Optional[Event]:
        try:
            event = await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout
            )
            self._pending[event.event_id] = event
            return event
        except asyncio.TimeoutError:
            return None

    async def acknowledge(self, event_id: str) -> bool:
        if event_id in self._pending:
            del self._pending[event_id]
            return True
        return False

    @property
    def size(self) -> int:
        return self._queue.qsize()


class RedisEventQueue(EventQueue):
    """Redis Streams-based event queue."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        stream_name: str = "shakti:events",
        consumer_group: str = "feature_pipeline",
        consumer_name: Optional[str] = None,
        max_len: int = 100000,
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"consumer-{uuid.uuid4().hex[:8]}"
        self.max_len = max_len

        self._redis: Optional[Any] = None
        self._initialized = False

    async def _ensure_connection(self) -> bool:
        """Ensure Redis connection and consumer group exist."""
        if not HAS_REDIS:
            logger.error("Redis not available")
            return False

        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis.ping()
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                return False

        if not self._initialized:
            try:
                # Create consumer group if not exists
                await self._redis.xgroup_create(
                    self.stream_name,
                    self.consumer_group,
                    id='0',
                    mkstream=True,
                )
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
            self._initialized = True

        return True

    async def publish(self, event: Event) -> bool:
        """Publish event to Redis stream."""
        if not await self._ensure_connection():
            return False

        try:
            message = {
                'event_id': event.event_id,
                'event_type': event.event_type.value,
                'timestamp': event.timestamp.isoformat(),
                'data': event.to_json(),
            }

            await self._redis.xadd(
                self.stream_name,
                message,
                maxlen=self.max_len,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    async def consume(self, timeout: float = 1.0) -> Optional[Event]:
        """Consume event from Redis stream."""
        if not await self._ensure_connection():
            return None

        try:
            # Read from consumer group
            messages = await self._redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_name: '>'},
                count=1,
                block=int(timeout * 1000),
            )

            if not messages:
                return None

            # Parse first message
            stream_name, stream_messages = messages[0]
            if not stream_messages:
                return None

            message_id, fields = stream_messages[0]
            event_data = json.loads(fields.get('data', '{}'))
            event = EventParser.parse(event_data)

            if event:
                event.event_id = message_id  # Use Redis message ID

            return event

        except Exception as e:
            logger.error(f"Failed to consume event: {e}")
            return None

    async def acknowledge(self, event_id: str) -> bool:
        """Acknowledge event processing."""
        if not await self._ensure_connection():
            return False

        try:
            await self._redis.xack(
                self.stream_name,
                self.consumer_group,
                event_id,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge event: {e}")
            return False

    async def get_pending(self) -> List[Dict[str, Any]]:
        """Get pending (unacknowledged) events."""
        if not await self._ensure_connection():
            return []

        try:
            pending = await self._redis.xpending(
                self.stream_name,
                self.consumer_group,
            )
            return pending
        except Exception as e:
            logger.error(f"Failed to get pending events: {e}")
            return []

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


class BlockchainIngester:
    """Ingest events from blockchain via The Graph or direct web3."""

    def __init__(
        self,
        graphql_endpoint: str,
        event_queue: EventQueue,
        poll_interval: float = 2.0,
        subscriptions: Optional[List[str]] = None,
    ):
        """Initialize blockchain ingester.

        Args:
            graphql_endpoint: The Graph GraphQL endpoint
            event_queue: Queue to publish events to
            poll_interval: Polling interval in seconds
            subscriptions: Event types to subscribe to
        """
        self.graphql_endpoint = graphql_endpoint
        self.event_queue = event_queue
        self.poll_interval = poll_interval
        self.subscriptions = subscriptions or [
            'TradeExecuted',
            'AuctionClosed',
            'PriceUpdated',
        ]

        self._running = False
        self._last_block = 0
        self._session: Optional[Any] = None
        self._stats = {
            'events_ingested': 0,
            'errors': 0,
            'last_poll': None,
        }

    async def start(self):
        """Start the ingester."""
        if not HAS_AIOHTTP:
            logger.error("aiohttp not available, using mock ingester")
            return await self._start_mock()

        self._running = True
        self._session = aiohttp.ClientSession()

        logger.info(f"Starting blockchain ingester, polling {self.graphql_endpoint}")

        while self._running:
            try:
                await self._poll_events()
                self._stats['last_poll'] = datetime.now()
            except Exception as e:
                logger.error(f"Poll error: {e}")
                self._stats['errors'] += 1

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the ingester."""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None

    async def _poll_events(self):
        """Poll for new events from The Graph."""
        query = self._build_query()

        async with self._session.post(
            self.graphql_endpoint,
            json={'query': query},
            headers={'Content-Type': 'application/json'},
        ) as response:
            if response.status != 200:
                raise Exception(f"GraphQL query failed: {response.status}")

            result = await response.json()

            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")

            events = self._parse_response(result)

            for event in events:
                await self.event_queue.publish(event)
                self._stats['events_ingested'] += 1

    def _build_query(self) -> str:
        """Build GraphQL query for events."""
        # Query for trades
        query = """
        {
            trades(
                first: 100,
                orderBy: blockTimestamp,
                orderDirection: desc,
                where: { blockNumber_gt: %d }
            ) {
                id
                buyer
                seller
                price
                quantity
                energyKwh
                blockNumber
                blockTimestamp
                transactionHash
            }
            priceUpdates(
                first: 50,
                orderBy: blockTimestamp,
                orderDirection: desc,
                where: { blockNumber_gt: %d }
            ) {
                id
                price
                market
                blockNumber
                blockTimestamp
            }
        }
        """ % (self._last_block, self._last_block)

        return query

    def _parse_response(self, result: Dict[str, Any]) -> List[Event]:
        """Parse GraphQL response into events."""
        events = []
        data = result.get('data', {})

        # Parse trades
        for trade in data.get('trades', []):
            event = EventParser.parse_blockchain_log({
                'event': 'TradeExecuted',
                'args': trade,
                'blockNumber': trade.get('blockNumber'),
                'blockTimestamp': trade.get('blockTimestamp'),
                'transactionHash': trade.get('transactionHash'),
            })
            if event:
                events.append(event)
                self._last_block = max(
                    self._last_block,
                    int(trade.get('blockNumber', 0))
                )

        # Parse price updates
        for price in data.get('priceUpdates', []):
            event = EventParser.parse_blockchain_log({
                'event': 'PriceUpdated',
                'args': price,
                'blockNumber': price.get('blockNumber'),
                'blockTimestamp': price.get('blockTimestamp'),
            })
            if event:
                events.append(event)

        return events

    async def _start_mock(self):
        """Start mock event generation for testing."""
        import random

        self._running = True
        logger.info("Starting mock blockchain ingester")

        while self._running:
            # Generate mock trade event
            if random.random() < 0.3:
                event = TradeEvent(
                    event_id=f"mock-{uuid.uuid4().hex[:8]}",
                    event_type=EventType.TRADE_EXECUTED,
                    timestamp=datetime.now(),
                    source="mock_blockchain",
                    trade_id=f"TRADE-{random.randint(1000, 9999)}",
                    buyer_id=f"0x{random.randbytes(20).hex()}",
                    seller_id=f"0x{random.randbytes(20).hex()}",
                    price=random.uniform(0.05, 0.15),
                    quantity=random.uniform(10, 100),
                    energy_kwh=random.uniform(50, 500),
                )
                await self.event_queue.publish(event)
                self._stats['events_ingested'] += 1

            # Generate mock price event
            if random.random() < 0.2:
                event = PriceEvent(
                    event_id=f"mock-price-{uuid.uuid4().hex[:8]}",
                    event_type=EventType.PRICE_UPDATED,
                    timestamp=datetime.now(),
                    source="mock_blockchain",
                    price=random.uniform(0.05, 0.15),
                    market="spot",
                )
                await self.event_queue.publish(event)
                self._stats['events_ingested'] += 1

            await asyncio.sleep(self.poll_interval)

    def get_stats(self) -> Dict[str, Any]:
        """Get ingester statistics."""
        return {
            **self._stats,
            'running': self._running,
            'last_block': self._last_block,
        }


class GridAPIIngester:
    """Ingest data from grid utility APIs."""

    def __init__(
        self,
        api_endpoints: Dict[str, str],
        event_queue: EventQueue,
        poll_interval: float = 60.0,
        api_key: Optional[str] = None,
    ):
        """Initialize grid API ingester.

        Args:
            api_endpoints: Dict mapping metric type to API URL
            event_queue: Queue to publish events to
            poll_interval: Polling interval in seconds
            api_key: API key for authentication
        """
        self.api_endpoints = api_endpoints
        self.event_queue = event_queue
        self.poll_interval = poll_interval
        self.api_key = api_key

        self._running = False
        self._session: Optional[Any] = None
        self._stats = {
            'events_ingested': 0,
            'errors': 0,
            'last_poll': None,
        }

    async def start(self):
        """Start the ingester."""
        if not HAS_AIOHTTP:
            logger.error("aiohttp not available, using mock ingester")
            return await self._start_mock()

        self._running = True
        self._session = aiohttp.ClientSession()

        logger.info("Starting grid API ingester")

        while self._running:
            try:
                await self._poll_all_endpoints()
                self._stats['last_poll'] = datetime.now()
            except Exception as e:
                logger.error(f"Grid API poll error: {e}")
                self._stats['errors'] += 1

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the ingester."""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None

    async def _poll_all_endpoints(self):
        """Poll all configured endpoints."""
        for metric_type, url in self.api_endpoints.items():
            try:
                await self._poll_endpoint(metric_type, url)
            except Exception as e:
                logger.error(f"Failed to poll {metric_type}: {e}")

    async def _poll_endpoint(self, metric_type: str, url: str):
        """Poll a single endpoint."""
        headers = {}
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"

        async with self._session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"API request failed: {response.status}")

            data = await response.json()
            event = EventParser.parse_grid_api(data, metric_type)

            if event:
                await self.event_queue.publish(event)
                self._stats['events_ingested'] += 1

    async def _start_mock(self):
        """Start mock event generation for testing."""
        import random

        self._running = True
        logger.info("Starting mock grid API ingester")

        while self._running:
            # Generate mock grid load event
            event = GridEvent(
                event_id=f"grid-load-{uuid.uuid4().hex[:8]}",
                event_type=EventType.GRID_LOAD,
                timestamp=datetime.now(),
                source="mock_grid_api",
                metric_type="load",
                value=random.uniform(5000, 8000),
                unit="MW",
                region="delhi",
                total_load_mw=random.uniform(5000, 8000),
            )
            await self.event_queue.publish(event)

            # Generate mock frequency event
            event = GridEvent(
                event_id=f"grid-freq-{uuid.uuid4().hex[:8]}",
                event_type=EventType.GRID_FREQUENCY,
                timestamp=datetime.now(),
                source="mock_grid_api",
                metric_type="frequency",
                value=50.0 + random.uniform(-0.1, 0.1),
                unit="Hz",
                frequency_hz=50.0 + random.uniform(-0.1, 0.1),
            )
            await self.event_queue.publish(event)

            self._stats['events_ingested'] += 2
            self._stats['last_poll'] = datetime.now()

            await asyncio.sleep(self.poll_interval)

    def get_stats(self) -> Dict[str, Any]:
        """Get ingester statistics."""
        return {
            **self._stats,
            'running': self._running,
        }


class EventIngestionManager:
    """Manage multiple event ingesters."""

    def __init__(self, event_queue: EventQueue):
        """Initialize manager.

        Args:
            event_queue: Shared event queue
        """
        self.event_queue = event_queue
        self.ingesters: Dict[str, Any] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    def add_ingester(self, name: str, ingester):
        """Add an ingester."""
        self.ingesters[name] = ingester

    async def start_all(self):
        """Start all ingesters."""
        for name, ingester in self.ingesters.items():
            task = asyncio.create_task(ingester.start())
            self._tasks[name] = task
            logger.info(f"Started ingester: {name}")

    async def stop_all(self):
        """Stop all ingesters."""
        for name, ingester in self.ingesters.items():
            await ingester.stop()

        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("All ingesters stopped")

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats from all ingesters."""
        return {
            name: ingester.get_stats()
            for name, ingester in self.ingesters.items()
        }
