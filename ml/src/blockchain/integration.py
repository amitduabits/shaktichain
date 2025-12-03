"""Main blockchain integration for SHAKTI-CHAIN ML.

Provides unified interface for:
- Subgraph subscriptions
- Event processing
- Historical sync
- Oracle data
- Reliability and monitoring
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

from .subgraph import SubgraphClient, SubgraphConfig, SubscriptionType
from .processor import BlockchainEventProcessor
from .sync import HistoricalSync, CursorStorage
from .oracles import OracleSubscriber
from .reliability import ReliabilityLayer, RetryPolicy
from .monitor import SyncMonitor, SlackAlertHandler

logger = logging.getLogger(__name__)


@dataclass
class BlockchainIntegrationConfig:
    """Configuration for blockchain integration."""
    # Subgraph
    subgraph_http_url: str = "https://api.thegraph.com/subgraphs/name/shakti/v2g-market"
    subgraph_ws_url: str = "wss://api.thegraph.com/subgraphs/name/shakti/v2g-market"

    # Grid API
    grid_api_url: Optional[str] = None

    # Sync
    sync_days: int = 30
    sync_on_startup: bool = True

    # Storage
    storage_dir: str = "./data/blockchain"

    # Alerting
    slack_webhook_url: Optional[str] = None
    sync_lag_threshold_seconds: float = 300.0

    # Feature store
    feature_store: Optional[Any] = None

    # Anomaly detector
    anomaly_detector: Optional[Any] = None

    # Trading agent
    trading_agent: Optional[Any] = None


class BlockchainIntegration:
    """Main class for blockchain integration with ML pipeline."""

    def __init__(self, config: Optional[BlockchainIntegrationConfig] = None):
        """Initialize blockchain integration.

        Args:
            config: Configuration for integration
        """
        self.config = config or BlockchainIntegrationConfig()

        # Create storage directory
        self.storage_dir = Path(self.config.storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize subgraph client
        subgraph_config = SubgraphConfig(
            http_url=self.config.subgraph_http_url,
            ws_url=self.config.subgraph_ws_url,
        )
        self.subgraph = SubgraphClient(subgraph_config)

        # Initialize event processor
        self.processor = BlockchainEventProcessor(
            feature_store=self.config.feature_store,
            anomaly_detector=self.config.anomaly_detector,
            trading_agent=self.config.trading_agent,
        )

        # Initialize reliability layer
        self.reliability = ReliabilityLayer(
            storage_dir=str(self.storage_dir / "reliability"),
        )

        # Initialize cursor storage for sync
        cursor_storage = CursorStorage(
            storage_path=str(self.storage_dir / "cursors.json"),
        )

        # Initialize historical sync
        self.sync = HistoricalSync(
            subgraph_client=self.subgraph,
            event_processor=self.processor,
            feature_store=self.config.feature_store,
            cursor_storage=cursor_storage,
            sync_days=self.config.sync_days,
        )

        # Initialize oracle subscriber
        self.oracles = OracleSubscriber(
            subgraph_client=self.subgraph,
            grid_api_url=self.config.grid_api_url,
            feature_store=self.config.feature_store,
            trading_agent=self.config.trading_agent,
        )

        # Initialize monitor
        self.monitor = SyncMonitor(
            sync_lag_threshold_seconds=self.config.sync_lag_threshold_seconds,
        )
        self.monitor.set_subgraph_client(self.subgraph)
        self.monitor.set_sync_manager(self.sync)
        self.monitor.set_reliability_layer(self.reliability)
        self.monitor.set_oracle_subscriber(self.oracles)

        # Add Slack alerting if configured
        if self.config.slack_webhook_url:
            self.monitor.add_alert_handler(
                SlackAlertHandler(self.config.slack_webhook_url)
            )

        # Running state
        self._running = False
        self._tasks = []

        # Event callbacks
        self._on_trade_callbacks: list[Callable] = []
        self._on_auction_callbacks: list[Callable] = []
        self._on_price_callbacks: list[Callable] = []

    def on_trade(self, callback: Callable):
        """Register callback for trade events."""
        self._on_trade_callbacks.append(callback)

    def on_auction(self, callback: Callable):
        """Register callback for auction events."""
        self._on_auction_callbacks.append(callback)

    def on_price(self, callback: Callable):
        """Register callback for price updates."""
        self._on_price_callbacks.append(callback)

    async def start(self):
        """Start blockchain integration."""
        if self._running:
            logger.warning("Integration already running")
            return

        self._running = True
        logger.info("Starting blockchain integration...")

        # Connect to subgraph
        await self.subgraph.connect()

        # Start tasks
        self._tasks = []

        # Historical sync (if enabled)
        if self.config.sync_on_startup:
            self._tasks.append(
                asyncio.create_task(self._run_initial_sync())
            )

        # Real-time subscriptions
        self._tasks.append(
            asyncio.create_task(self._start_subscriptions())
        )

        # Oracle subscriber
        self._tasks.append(
            asyncio.create_task(self.oracles.start())
        )

        # Monitoring
        self._tasks.append(
            asyncio.create_task(self.monitor.start())
        )

        logger.info(f"Blockchain integration started with {len(self._tasks)} tasks")

    async def stop(self):
        """Stop blockchain integration."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping blockchain integration...")

        # Stop sync
        await self.sync.stop()

        # Stop oracles
        await self.oracles.stop()

        # Stop monitor
        await self.monitor.stop()

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Disconnect subgraph
        await self.subgraph.disconnect()

        logger.info("Blockchain integration stopped")

    async def _run_initial_sync(self):
        """Run initial historical sync."""
        try:
            logger.info("Starting initial historical sync...")
            await self.sync.start()
            await self.sync.populate_feature_store()
            logger.info("Initial sync completed")
        except Exception as e:
            logger.error(f"Initial sync failed: {e}")

    async def _start_subscriptions(self):
        """Start real-time subscriptions."""
        try:
            # Register handlers
            self.subgraph.register_callback(
                SubscriptionType.TRADES,
                self._handle_trade_subscription,
            )
            self.subgraph.register_callback(
                SubscriptionType.AUCTIONS,
                self._handle_auction_subscription,
            )
            self.subgraph.register_callback(
                SubscriptionType.PRICE_UPDATES,
                self._handle_price_subscription,
            )

            # Start subscriptions
            await asyncio.gather(
                self.subgraph.subscribe_trades(),
                self.subgraph.subscribe_auctions(),
                self.subgraph.subscribe_price_updates(),
            )

        except Exception as e:
            logger.error(f"Subscriptions failed: {e}")

    async def _handle_trade_subscription(self, data: Dict[str, Any]):
        """Handle trade subscription events."""
        trades = data.get("trades", [])

        for trade in trades:
            try:
                # Process with reliability
                success = await self.reliability.process_event_safely(
                    event_id=trade.get("id", "unknown"),
                    event_type="trade",
                    payload=trade,
                    processor=self.processor.process_trade,
                )

                if success:
                    # Dispatch to callbacks
                    for callback in self._on_trade_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(trade)
                            else:
                                callback(trade)
                        except Exception as e:
                            logger.error(f"Trade callback error: {e}")

            except Exception as e:
                logger.error(f"Trade handling error: {e}")

    async def _handle_auction_subscription(self, data: Dict[str, Any]):
        """Handle auction subscription events."""
        auctions = data.get("auctions", [])

        for auction in auctions:
            try:
                success = await self.reliability.process_event_safely(
                    event_id=auction.get("id", "unknown"),
                    event_type="auction",
                    payload=auction,
                    processor=self.processor.process_auction_close,
                )

                if success:
                    for callback in self._on_auction_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(auction)
                            else:
                                callback(auction)
                        except Exception as e:
                            logger.error(f"Auction callback error: {e}")

            except Exception as e:
                logger.error(f"Auction handling error: {e}")

    async def _handle_price_subscription(self, data: Dict[str, Any]):
        """Handle price subscription events."""
        updates = data.get("priceUpdates", [])

        for update in updates:
            try:
                success = await self.reliability.process_event_safely(
                    event_id=update.get("id", "unknown"),
                    event_type="oracle",
                    payload=update,
                    processor=self.processor.process_oracle_update,
                )

                if success:
                    for callback in self._on_price_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(update)
                            else:
                                callback(update)
                        except Exception as e:
                            logger.error(f"Price callback error: {e}")

            except Exception as e:
                logger.error(f"Price handling error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        return {
            "running": self._running,
            "subgraph": self.subgraph.get_stats(),
            "processor": self.processor.get_stats(),
            "sync": self.sync.get_stats(),
            "oracles": self.oracles.get_stats(),
            "reliability": self.reliability.get_stats(),
            "monitor": self.monitor.get_stats(),
        }

    def get_health(self) -> Dict[str, Any]:
        """Get health status."""
        metrics = self.monitor.get_metrics()
        alerts = self.monitor.get_active_alerts()

        is_healthy = (
            self._running and
            len(alerts) == 0 and
            metrics.get("sync", {}).get("lag_seconds", 0) < self.config.sync_lag_threshold_seconds
        )

        return {
            "healthy": is_healthy,
            "running": self._running,
            "active_alerts": len(alerts),
            "sync_lag_seconds": metrics.get("sync", {}).get("lag_seconds", 0),
            "oracle_staleness_seconds": metrics.get("oracle", {}).get("staleness_seconds", 0),
        }


async def run_integration(config: Optional[BlockchainIntegrationConfig] = None):
    """Run blockchain integration with graceful shutdown.

    Args:
        config: Integration configuration
    """
    import signal

    integration = BlockchainIntegration(config)
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        pass

    try:
        await integration.start()
        await shutdown_event.wait()
    finally:
        await integration.stop()


# Entry point
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = BlockchainIntegrationConfig()
    asyncio.run(run_integration(config))
