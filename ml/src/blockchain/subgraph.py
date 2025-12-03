"""SubgraphClient for The Graph WebSocket subscriptions.

Provides:
- WebSocket-based subscriptions to trades, auctions, oracles
- GraphQL query execution with pagination
- Connection management with auto-reconnect
- Event parsing and normalization
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from gql import gql, Client
    from gql.transport.websockets import WebsocketsTransport
    from gql.transport.aiohttp import AIOHTTPTransport
    HAS_GQL = True
except ImportError:
    HAS_GQL = False
    logger.warning("gql not installed. Install with: pip install gql[websockets,aiohttp]")


class SubscriptionType(Enum):
    """Types of subgraph subscriptions."""
    TRADES = "trades"
    AUCTIONS = "auctions"
    PRICE_UPDATES = "priceUpdates"
    GRID_STATUS = "gridStatusUpdates"
    PARTICIPANTS = "participants"


@dataclass
class SubgraphConfig:
    """Configuration for subgraph connection."""
    # Subgraph endpoints
    http_url: str = "https://api.thegraph.com/subgraphs/name/shakti/v2g-market"
    ws_url: str = "wss://api.thegraph.com/subgraphs/name/shakti/v2g-market"

    # Connection settings
    reconnect_interval: float = 5.0
    max_reconnect_attempts: int = 10
    request_timeout: float = 30.0

    # Pagination
    page_size: int = 1000
    max_pages: int = 100

    # Rate limiting
    requests_per_second: float = 10.0


@dataclass
class GraphQLQuery:
    """Represents a GraphQL query or subscription."""
    name: str
    query: str
    variables: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def trades_subscription(cls) -> "GraphQLQuery":
        """Create trades subscription query."""
        return cls(
            name="trades_subscription",
            query="""
                subscription TradesSubscription {
                    trades(orderBy: timestamp, orderDirection: desc, first: 10) {
                        id
                        buyer {
                            id
                            reputation
                            totalTrades
                            totalVolume
                        }
                        seller {
                            id
                            reputation
                            totalTrades
                            totalVolume
                        }
                        quantity
                        price
                        energyKwh
                        timestamp
                        status
                        tradeType
                        blockNumber
                        transactionHash
                    }
                }
            """,
        )

    @classmethod
    def auctions_subscription(cls) -> "GraphQLQuery":
        """Create auctions subscription query."""
        return cls(
            name="auctions_subscription",
            query="""
                subscription AuctionsSubscription {
                    auctions(orderBy: endTime, orderDirection: desc, first: 10) {
                        id
                        auctionType
                        startTime
                        endTime
                        minPrice
                        maxPrice
                        clearingPrice
                        totalVolume
                        participantCount
                        status
                        bids {
                            id
                            bidder { id }
                            price
                            quantity
                            accepted
                        }
                        blockNumber
                    }
                }
            """,
        )

    @classmethod
    def price_oracle_subscription(cls) -> "GraphQLQuery":
        """Create price oracle subscription."""
        return cls(
            name="price_oracle_subscription",
            query="""
                subscription PriceOracleSubscription {
                    priceUpdates(orderBy: timestamp, orderDirection: desc, first: 5) {
                        id
                        oracle
                        price
                        timestamp
                        source
                        confidence
                        blockNumber
                    }
                }
            """,
        )

    @classmethod
    def historical_trades(
        cls,
        from_timestamp: int,
        to_timestamp: int,
        skip: int = 0,
        first: int = 1000,
    ) -> "GraphQLQuery":
        """Create historical trades query with pagination."""
        return cls(
            name="historical_trades",
            query="""
                query HistoricalTrades($fromTs: BigInt!, $toTs: BigInt!, $skip: Int!, $first: Int!) {
                    trades(
                        where: { timestamp_gte: $fromTs, timestamp_lte: $toTs }
                        orderBy: timestamp
                        orderDirection: asc
                        skip: $skip
                        first: $first
                    ) {
                        id
                        buyer {
                            id
                            reputation
                            totalTrades
                            totalVolume
                        }
                        seller {
                            id
                            reputation
                            totalTrades
                            totalVolume
                        }
                        quantity
                        price
                        energyKwh
                        timestamp
                        status
                        tradeType
                        blockNumber
                        transactionHash
                    }
                }
            """,
            variables={
                "fromTs": str(from_timestamp),
                "toTs": str(to_timestamp),
                "skip": skip,
                "first": first,
            },
        )

    @classmethod
    def historical_auctions(
        cls,
        from_timestamp: int,
        to_timestamp: int,
        skip: int = 0,
        first: int = 1000,
    ) -> "GraphQLQuery":
        """Create historical auctions query."""
        return cls(
            name="historical_auctions",
            query="""
                query HistoricalAuctions($fromTs: BigInt!, $toTs: BigInt!, $skip: Int!, $first: Int!) {
                    auctions(
                        where: { endTime_gte: $fromTs, endTime_lte: $toTs }
                        orderBy: endTime
                        orderDirection: asc
                        skip: $skip
                        first: $first
                    ) {
                        id
                        auctionType
                        startTime
                        endTime
                        minPrice
                        maxPrice
                        clearingPrice
                        totalVolume
                        participantCount
                        status
                        blockNumber
                    }
                }
            """,
            variables={
                "fromTs": str(from_timestamp),
                "toTs": str(to_timestamp),
                "skip": skip,
                "first": first,
            },
        )


class SubgraphClient:
    """Client for The Graph subgraph with WebSocket subscriptions."""

    def __init__(self, config: Optional[SubgraphConfig] = None):
        """Initialize subgraph client.

        Args:
            config: Subgraph configuration
        """
        self.config = config or SubgraphConfig()
        self._ws_client: Optional[Client] = None
        self._http_client: Optional[Client] = None
        self._subscriptions: Dict[str, asyncio.Task] = {}
        self._connected = False
        self._reconnect_count = 0
        self._last_request_time = 0.0

        # Callbacks for subscription events
        self._callbacks: Dict[SubscriptionType, List[Callable]] = {
            sub_type: [] for sub_type in SubscriptionType
        }

        # Statistics
        self._stats = {
            "queries_executed": 0,
            "subscriptions_active": 0,
            "events_received": 0,
            "errors": 0,
            "reconnections": 0,
        }

    async def connect(self):
        """Establish connections to subgraph."""
        if not HAS_GQL:
            logger.warning("gql not available, using mock client")
            self._connected = True
            return

        try:
            # HTTP client for queries
            http_transport = AIOHTTPTransport(
                url=self.config.http_url,
                timeout=self.config.request_timeout,
            )
            self._http_client = Client(
                transport=http_transport,
                fetch_schema_from_transport=False,
            )

            # WebSocket client for subscriptions
            ws_transport = WebsocketsTransport(
                url=self.config.ws_url,
                close_timeout=10,
            )
            self._ws_client = Client(
                transport=ws_transport,
                fetch_schema_from_transport=False,
            )

            self._connected = True
            logger.info(f"Connected to subgraph at {self.config.http_url}")

        except Exception as e:
            logger.error(f"Failed to connect to subgraph: {e}")
            self._stats["errors"] += 1
            raise

    async def disconnect(self):
        """Disconnect from subgraph."""
        # Cancel all subscriptions
        for name, task in self._subscriptions.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._subscriptions.clear()

        # Close clients
        if self._ws_client:
            await self._ws_client.close_async()
        if self._http_client:
            await self._http_client.close_async()

        self._connected = False
        logger.info("Disconnected from subgraph")

    def register_callback(
        self,
        subscription_type: SubscriptionType,
        callback: Callable[[Dict[str, Any]], None],
    ):
        """Register callback for subscription events.

        Args:
            subscription_type: Type of subscription
            callback: Async callback function
        """
        self._callbacks[subscription_type].append(callback)

    async def subscribe_trades(self, callback: Optional[Callable] = None):
        """Subscribe to trade events.

        Args:
            callback: Optional callback for trade events
        """
        if callback:
            self.register_callback(SubscriptionType.TRADES, callback)

        query = GraphQLQuery.trades_subscription()
        await self._start_subscription(SubscriptionType.TRADES, query)

    async def subscribe_auctions(self, callback: Optional[Callable] = None):
        """Subscribe to auction events."""
        if callback:
            self.register_callback(SubscriptionType.AUCTIONS, callback)

        query = GraphQLQuery.auctions_subscription()
        await self._start_subscription(SubscriptionType.AUCTIONS, query)

    async def subscribe_price_updates(self, callback: Optional[Callable] = None):
        """Subscribe to price oracle updates."""
        if callback:
            self.register_callback(SubscriptionType.PRICE_UPDATES, callback)

        query = GraphQLQuery.price_oracle_subscription()
        await self._start_subscription(SubscriptionType.PRICE_UPDATES, query)

    async def _start_subscription(
        self,
        sub_type: SubscriptionType,
        query: GraphQLQuery,
    ):
        """Start a subscription task.

        Args:
            sub_type: Subscription type
            query: GraphQL query
        """
        # Cancel existing subscription
        if sub_type.value in self._subscriptions:
            self._subscriptions[sub_type.value].cancel()

        # Start new subscription task
        task = asyncio.create_task(
            self._subscription_loop(sub_type, query)
        )
        self._subscriptions[sub_type.value] = task
        self._stats["subscriptions_active"] = len(self._subscriptions)

    async def _subscription_loop(
        self,
        sub_type: SubscriptionType,
        query: GraphQLQuery,
    ):
        """Subscription loop with auto-reconnect.

        Args:
            sub_type: Subscription type
            query: GraphQL query
        """
        while True:
            try:
                if not HAS_GQL:
                    # Mock subscription for testing
                    await self._mock_subscription_loop(sub_type)
                    return

                async with self._ws_client as session:
                    gql_query = gql(query.query)
                    async for result in session.subscribe(gql_query):
                        self._stats["events_received"] += 1

                        # Parse and dispatch events
                        await self._dispatch_event(sub_type, result)

            except asyncio.CancelledError:
                logger.info(f"Subscription {sub_type.value} cancelled")
                break

            except Exception as e:
                logger.error(f"Subscription error for {sub_type.value}: {e}")
                self._stats["errors"] += 1
                self._reconnect_count += 1
                self._stats["reconnections"] += 1

                if self._reconnect_count > self.config.max_reconnect_attempts:
                    logger.error(f"Max reconnect attempts reached for {sub_type.value}")
                    break

                # Exponential backoff
                wait_time = min(
                    self.config.reconnect_interval * (2 ** self._reconnect_count),
                    300,  # Max 5 minutes
                )
                logger.info(f"Reconnecting in {wait_time}s...")
                await asyncio.sleep(wait_time)

    async def _mock_subscription_loop(self, sub_type: SubscriptionType):
        """Mock subscription for testing without gql."""
        import random

        while True:
            await asyncio.sleep(random.uniform(1, 5))

            if sub_type == SubscriptionType.TRADES:
                mock_event = {
                    "trades": [{
                        "id": f"0x{random.randbytes(32).hex()}",
                        "buyer": {"id": f"0x{random.randbytes(20).hex()}", "reputation": random.randint(50, 100)},
                        "seller": {"id": f"0x{random.randbytes(20).hex()}", "reputation": random.randint(50, 100)},
                        "quantity": random.uniform(10, 1000),
                        "price": random.uniform(40, 60),
                        "timestamp": int(datetime.now().timestamp()),
                        "status": "COMPLETED",
                    }]
                }
            elif sub_type == SubscriptionType.AUCTIONS:
                mock_event = {
                    "auctions": [{
                        "id": f"auction-{random.randint(1, 1000)}",
                        "clearingPrice": random.uniform(40, 60),
                        "totalVolume": random.uniform(1000, 10000),
                        "endTime": int(datetime.now().timestamp()),
                        "status": "CLOSED",
                    }]
                }
            else:
                mock_event = {
                    "priceUpdates": [{
                        "price": random.uniform(40, 60),
                        "timestamp": int(datetime.now().timestamp()),
                    }]
                }

            self._stats["events_received"] += 1
            await self._dispatch_event(sub_type, mock_event)

    async def _dispatch_event(
        self,
        sub_type: SubscriptionType,
        result: Dict[str, Any],
    ):
        """Dispatch event to registered callbacks.

        Args:
            sub_type: Subscription type
            result: GraphQL result
        """
        callbacks = self._callbacks.get(sub_type, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Callback error for {sub_type.value}: {e}")

    async def execute_query(self, query: GraphQLQuery) -> Dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query to execute

        Returns:
            Query result
        """
        # Rate limiting
        await self._rate_limit()

        self._stats["queries_executed"] += 1

        if not HAS_GQL:
            # Return mock data
            return self._mock_query_result(query)

        try:
            async with self._http_client as session:
                gql_query = gql(query.query)
                result = await session.execute(gql_query, variable_values=query.variables)
                return result

        except Exception as e:
            logger.error(f"Query error: {e}")
            self._stats["errors"] += 1
            raise

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        import time

        min_interval = 1.0 / self.config.requests_per_second
        elapsed = time.time() - self._last_request_time

        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

        self._last_request_time = time.time()

    def _mock_query_result(self, query: GraphQLQuery) -> Dict[str, Any]:
        """Generate mock query result for testing."""
        import random

        if "trades" in query.name:
            return {
                "trades": [
                    {
                        "id": f"0x{random.randbytes(32).hex()}",
                        "buyer": {"id": f"0x{random.randbytes(20).hex()}", "reputation": random.randint(50, 100)},
                        "seller": {"id": f"0x{random.randbytes(20).hex()}", "reputation": random.randint(50, 100)},
                        "quantity": random.uniform(10, 1000),
                        "price": random.uniform(40, 60),
                        "timestamp": int(datetime.now().timestamp()) - random.randint(0, 86400 * 30),
                        "status": "COMPLETED",
                    }
                    for _ in range(min(100, query.variables.get("first", 100)))
                ]
            }
        elif "auctions" in query.name:
            return {
                "auctions": [
                    {
                        "id": f"auction-{random.randint(1, 1000)}",
                        "clearingPrice": random.uniform(40, 60),
                        "totalVolume": random.uniform(1000, 10000),
                        "endTime": int(datetime.now().timestamp()) - random.randint(0, 86400 * 30),
                        "status": "CLOSED",
                    }
                    for _ in range(min(50, query.variables.get("first", 50)))
                ]
            }
        return {}

    async def get_historical_trades(
        self,
        from_timestamp: int,
        to_timestamp: int,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Get historical trades with pagination.

        Args:
            from_timestamp: Start timestamp (unix)
            to_timestamp: End timestamp (unix)

        Yields:
            Trade records
        """
        skip = 0
        page = 0

        while page < self.config.max_pages:
            query = GraphQLQuery.historical_trades(
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                skip=skip,
                first=self.config.page_size,
            )

            result = await self.execute_query(query)
            trades = result.get("trades", [])

            if not trades:
                break

            for trade in trades:
                yield trade

            if len(trades) < self.config.page_size:
                break

            skip += self.config.page_size
            page += 1

            logger.debug(f"Fetched page {page}, {skip} trades total")

    async def get_historical_auctions(
        self,
        from_timestamp: int,
        to_timestamp: int,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Get historical auctions with pagination.

        Args:
            from_timestamp: Start timestamp (unix)
            to_timestamp: End timestamp (unix)

        Yields:
            Auction records
        """
        skip = 0
        page = 0

        while page < self.config.max_pages:
            query = GraphQLQuery.historical_auctions(
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                skip=skip,
                first=self.config.page_size,
            )

            result = await self.execute_query(query)
            auctions = result.get("auctions", [])

            if not auctions:
                break

            for auction in auctions:
                yield auction

            if len(auctions) < self.config.page_size:
                break

            skip += self.config.page_size
            page += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            **self._stats,
            "connected": self._connected,
            "active_subscriptions": list(self._subscriptions.keys()),
        }
