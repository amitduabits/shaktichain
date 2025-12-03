#!/usr/bin/env python3
"""Run the SHAKTI-CHAIN real-time feature pipeline.

Usage:
    python run_pipeline.py [--demo]

Options:
    --demo    Run in demo mode with simulated events
"""

import argparse
import asyncio
import logging
import random
import signal
import sys
from datetime import datetime
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_demo_mode():
    """Run pipeline with simulated events for demonstration."""
    from .events import TradeEvent, PriceEvent, GridEvent, EventType
    from .processor import StreamingFeatureProcessor
    from .store import InMemoryFeatureStore, FeatureStoreWriter, FeatureCategory
    from .refresher import FeatureRefresher
    from .serving import FeatureServer

    logger.info("Starting demo mode with simulated events...")

    # Initialize components with in-memory store
    store = InMemoryFeatureStore()
    processor = StreamingFeatureProcessor()
    store_writer = FeatureStoreWriter(store)
    refresher = FeatureRefresher(processor, store, store_writer)
    server = FeatureServer(store)

    # Start refresher
    await refresher.start()

    # Simulate events
    markets = ["spot", "forward", "balancing"]
    base_prices = {"spot": 50.0, "forward": 48.0, "balancing": 55.0}

    event_count = 0

    try:
        while True:
            # Generate random events
            event_type = random.choice(["trade", "price", "grid"])

            if event_type == "trade":
                market = random.choice(markets)
                price = base_prices[market] + random.gauss(0, 2)
                quantity = random.uniform(10, 1000)

                event = TradeEvent(
                    event_type=EventType.TRADE_EXECUTED,
                    timestamp=datetime.now(),
                    source="demo",
                    trade_id=f"demo-{event_count}",
                    buyer_id=f"buyer-{random.randint(1, 100)}",
                    seller_id=f"seller-{random.randint(1, 100)}",
                    price=price,
                    quantity=quantity,
                    energy_kwh=quantity * 10,
                    trade_type=market,
                )
                await refresher.on_trade_event(event)

                # Update base price with slight drift
                base_prices[market] = price

            elif event_type == "price":
                market = random.choice(markets)
                price = base_prices[market] + random.gauss(0, 1)

                event = PriceEvent(
                    event_type=EventType.PRICE_UPDATED,
                    timestamp=datetime.now(),
                    source="demo",
                    market=market,
                    price=price,
                    bid_price=price - random.uniform(0.1, 0.5),
                    ask_price=price + random.uniform(0.1, 0.5),
                    volume_24h=random.uniform(10000, 100000),
                )
                await refresher.on_price_update(event)

                base_prices[market] = price

            else:  # grid
                event = GridEvent(
                    event_type=EventType.GRID_LOAD,
                    timestamp=datetime.now(),
                    source="demo",
                    region="default",
                    load_mw=random.uniform(20000, 40000),
                    frequency_hz=50.0 + random.gauss(0, 0.02),
                    frequency_deviation=random.gauss(0, 0.02),
                )
                await refresher.on_grid_event(event)

            event_count += 1

            # Log progress every 100 events
            if event_count % 100 == 0:
                stats = refresher.get_stats()
                logger.info(
                    f"Processed {event_count} events | "
                    f"Features updated: {stats['features_updated']} | "
                    f"Errors: {stats['errors']}"
                )

                # Sample feature retrieval
                vector = await server.get_features("trading", "spot")
                logger.info(f"Trading features: {vector.features}")

            # Random delay between events (10-100ms)
            await asyncio.sleep(random.uniform(0.01, 0.1))

    except asyncio.CancelledError:
        logger.info("Demo mode cancelled")
    finally:
        await refresher.stop()
        logger.info(f"Demo completed. Total events: {event_count}")


async def run_production_mode(config_path: Optional[str] = None):
    """Run pipeline in production mode."""
    from .orchestrator import FeaturePipelineOrchestrator, PipelineConfig

    # Load config
    if config_path:
        import yaml
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)
        config = PipelineConfig(**config_dict)
    else:
        config = PipelineConfig()

    logger.info(f"Starting production pipeline...")
    logger.info(f"  Redis: {config.redis_url}")
    logger.info(f"  Graph URL: {config.graph_url}")
    logger.info(f"  Serving port: {config.serving_port}")

    # Create orchestrator
    orchestrator = FeaturePipelineOrchestrator(config)

    # Setup shutdown handler
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        # Windows fallback
        pass

    try:
        # Start pipeline
        await orchestrator.start()

        # Wait for shutdown
        await shutdown_event.wait()

    finally:
        await orchestrator.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SHAKTI-CHAIN Real-time Feature Pipeline"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode with simulated events",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (YAML)",
    )
    parser.add_argument(
        "--redis-url",
        type=str,
        default="redis://localhost:6379",
        help="Redis URL",
    )
    parser.add_argument(
        "--serving-port",
        type=int,
        default=8001,
        help="Feature serving port",
    )
    args = parser.parse_args()

    if args.demo:
        asyncio.run(run_demo_mode())
    else:
        asyncio.run(run_production_mode(args.config))


if __name__ == "__main__":
    main()
