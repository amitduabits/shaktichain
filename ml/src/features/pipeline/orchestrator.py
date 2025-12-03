"""Pipeline orchestrator for real-time feature pipeline.

Coordinates:
- Event ingestion from multiple sources
- Streaming feature processing
- Feature store writes
- Feature serving
- Health monitoring
"""

import asyncio
import logging
import signal
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .events import Event, EventType
from .ingestion import (
    EventQueue,
    RedisEventQueue,
    BlockchainIngester,
    GridAPIIngester,
)
from .processor import StreamingFeatureProcessor
from .store import FeatureStore, RedisFeatureStore, FeatureStoreWriter
from .refresher import FeatureRefresher, ModelTriggerHandler
from .serving import FeatureServer

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the feature pipeline."""
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream_key: str = "shakti:events"

    # Blockchain
    graph_url: str = "https://api.thegraph.com/subgraphs/name/shakti/v2g-market"
    blockchain_poll_interval: float = 2.0

    # Grid API
    grid_api_url: str = "http://localhost:8080/api/grid"
    grid_poll_interval: float = 5.0

    # Processing
    enable_blockchain: bool = True
    enable_grid_api: bool = True
    enable_feature_serving: bool = True
    serving_port: int = 8001

    # Model triggers
    model_service_url: str = "http://localhost:8000"
    enable_model_triggers: bool = True

    # Monitoring
    health_check_interval: float = 30.0
    metrics_port: int = 9091


class FeaturePipelineOrchestrator:
    """Orchestrate the entire feature pipeline."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        """Initialize orchestrator.

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()

        # Components (initialized in start())
        self.event_queue: Optional[EventQueue] = None
        self.blockchain_ingester: Optional[BlockchainIngester] = None
        self.grid_ingester: Optional[GridAPIIngester] = None
        self.processor: Optional[StreamingFeatureProcessor] = None
        self.store: Optional[FeatureStore] = None
        self.store_writer: Optional[FeatureStoreWriter] = None
        self.refresher: Optional[FeatureRefresher] = None
        self.feature_server: Optional[FeatureServer] = None

        # State
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Statistics
        self._stats = {
            "started_at": None,
            "events_processed": 0,
            "features_computed": 0,
            "errors": 0,
        }

    async def start(self):
        """Start the feature pipeline."""
        logger.info("Starting feature pipeline...")
        self._running = True
        self._stats["started_at"] = datetime.now().isoformat()

        # Initialize components
        await self._initialize_components()

        # Start background tasks
        self._tasks = []

        # Event consumer
        self._tasks.append(
            asyncio.create_task(self._event_consumer_loop())
        )

        # Blockchain ingester
        if self.config.enable_blockchain and self.blockchain_ingester:
            self._tasks.append(
                asyncio.create_task(self.blockchain_ingester.start())
            )

        # Grid API ingester
        if self.config.enable_grid_api and self.grid_ingester:
            self._tasks.append(
                asyncio.create_task(self.grid_ingester.start())
            )

        # Feature refresher
        if self.refresher:
            self._tasks.append(
                asyncio.create_task(self.refresher.start())
            )

        # Health monitor
        self._tasks.append(
            asyncio.create_task(self._health_monitor_loop())
        )

        # Feature serving API
        if self.config.enable_feature_serving:
            self._tasks.append(
                asyncio.create_task(self._start_serving_api())
            )

        logger.info(f"Feature pipeline started with {len(self._tasks)} tasks")

    async def stop(self):
        """Stop the feature pipeline."""
        logger.info("Stopping feature pipeline...")
        self._running = False

        # Stop ingesters
        if self.blockchain_ingester:
            await self.blockchain_ingester.stop()
        if self.grid_ingester:
            await self.grid_ingester.stop()
        if self.refresher:
            await self.refresher.stop()

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Close connections
        if hasattr(self.store, 'close'):
            await self.store.close()
        if hasattr(self.event_queue, 'close'):
            await self.event_queue.close()

        logger.info("Feature pipeline stopped")

    async def _initialize_components(self):
        """Initialize pipeline components."""
        # Feature store
        try:
            self.store = RedisFeatureStore(redis_url=self.config.redis_url)
            await self.store.connect()
            logger.info("Connected to Redis feature store")
        except Exception as e:
            logger.warning(f"Redis not available, using in-memory store: {e}")
            from .store import InMemoryFeatureStore
            self.store = InMemoryFeatureStore()

        self.store_writer = FeatureStoreWriter(self.store)

        # Event queue
        try:
            self.event_queue = RedisEventQueue(
                redis_url=self.config.redis_url,
                stream_key=self.config.redis_stream_key,
            )
            await self.event_queue.connect()
            logger.info("Connected to Redis event queue")
        except Exception as e:
            logger.warning(f"Redis queue not available: {e}")
            self.event_queue = None

        # Streaming processor
        self.processor = StreamingFeatureProcessor()

        # Blockchain ingester
        if self.config.enable_blockchain and self.event_queue:
            self.blockchain_ingester = BlockchainIngester(
                graph_url=self.config.graph_url,
                event_queue=self.event_queue,
                poll_interval=self.config.blockchain_poll_interval,
            )

        # Grid API ingester
        if self.config.enable_grid_api and self.event_queue:
            self.grid_ingester = GridAPIIngester(
                api_base_url=self.config.grid_api_url,
                event_queue=self.event_queue,
                poll_interval=self.config.grid_poll_interval,
            )

        # Feature refresher
        self.refresher = FeatureRefresher(
            processor=self.processor,
            store=self.store,
            store_writer=self.store_writer,
        )

        # Model trigger handler
        if self.config.enable_model_triggers:
            trigger_handler = ModelTriggerHandler(
                model_service_url=self.config.model_service_url,
            )
            self.refresher.add_model_trigger(trigger_handler)

        # Feature server
        self.feature_server = FeatureServer(
            store=self.store,
            timeout_seconds=1.0,
            enable_fallback=True,
        )

    async def _event_consumer_loop(self):
        """Consume events from queue and process."""
        logger.info("Starting event consumer loop")

        while self._running:
            try:
                if not self.event_queue:
                    await asyncio.sleep(1)
                    continue

                # Consume event
                event = await self.event_queue.consume(timeout=1.0)
                if event is None:
                    continue

                # Process event
                await self._process_event(event)

                # Acknowledge
                if hasattr(event, 'event_id'):
                    await self.event_queue.acknowledge(event.event_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event consumer error: {e}")
                self._stats["errors"] += 1
                await asyncio.sleep(0.1)

    async def _process_event(self, event: Event):
        """Process a single event."""
        self._stats["events_processed"] += 1

        try:
            # Route to appropriate handler
            if event.event_type == EventType.TRADE_EXECUTED:
                await self.refresher.on_trade_event(event)
            elif event.event_type == EventType.PRICE_UPDATED:
                await self.refresher.on_price_update(event)
            elif event.event_type in (
                EventType.GRID_LOAD,
                EventType.GRID_FREQUENCY,
                EventType.GRID_GENERATION,
            ):
                await self.refresher.on_grid_event(event)
            else:
                # Generic processing
                features = await self.processor.process_event(event)
                if features:
                    self._stats["features_computed"] += len(features)

        except Exception as e:
            logger.error(f"Event processing error: {e}")
            self._stats["errors"] += 1

    async def _health_monitor_loop(self):
        """Monitor pipeline health."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                # Check staleness
                if self.refresher:
                    report = await self.refresher.check_staleness()
                    logger.debug(f"Staleness report: {report}")

                # Log stats
                stats = self.get_stats()
                logger.info(f"Pipeline stats: {stats}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _start_serving_api(self):
        """Start the feature serving API."""
        try:
            import uvicorn
            from fastapi import FastAPI
            from .serving import create_feature_router

            app = FastAPI(
                title="SHAKTI-CHAIN Feature Service",
                version="1.0.0",
            )

            # Add feature routes
            router = create_feature_router(self.feature_server)
            app.include_router(router)

            # Health endpoint at root
            @app.get("/health")
            async def health():
                return {
                    "status": "healthy",
                    "pipeline": self.get_stats(),
                }

            # Run server
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=self.config.serving_port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()

        except ImportError:
            logger.warning("FastAPI/uvicorn not available, serving API disabled")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Feature serving API error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        stats = {
            **self._stats,
            "running": self._running,
        }

        if self.processor:
            stats["processor"] = {
                "features": len(self.processor.get_all_features()),
            }

        if self.refresher:
            stats["refresher"] = self.refresher.get_stats()

        if self.feature_server:
            stats["serving"] = self.feature_server.get_stats()

        return stats


async def run_pipeline(config: Optional[PipelineConfig] = None):
    """Run the feature pipeline with graceful shutdown."""
    orchestrator = FeaturePipelineOrchestrator(config)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    # Register signal handlers (Unix only)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    try:
        # Start pipeline
        await orchestrator.start()

        # Wait for shutdown signal
        await shutdown_event.wait()

    finally:
        # Stop pipeline
        await orchestrator.stop()


# Entry point
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = PipelineConfig()
    asyncio.run(run_pipeline(config))
