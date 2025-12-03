#!/usr/bin/env python3
"""Run the SHAKTI-CHAIN trading agent.

Usage:
    python run_agent.py [--mode paper|live] [--config config.yaml]

Examples:
    # Paper trading (dry run)
    python run_agent.py --mode paper

    # Live trading with config
    python run_agent.py --mode live --config agent_config.yaml
"""

import argparse
import asyncio
import logging
import signal
import os
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_trading_agent(
    mode: str = "paper",
    config_path: str = None,
    rpc_url: str = None,
    private_key: str = None,
):
    """Run the trading agent.

    Args:
        mode: Trading mode (paper/live)
        config_path: Path to configuration file
        rpc_url: Blockchain RPC URL
        private_key: Trading account private key
    """
    from .executor import BlockchainTradingExecutor, ExecutorConfig
    from .agent import TradingAgent, AgentConfig, AgentMode
    from .risk import RiskManager, RiskConfig, RiskLimits
    from .monitor import TransactionMonitor, MonitorConfig
    from .pnl import PnLTracker

    # Determine mode
    agent_mode = AgentMode.PAPER if mode == "paper" else AgentMode.LIVE

    # Create storage directory
    storage_dir = Path("./data/trading")
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Initialize executor
    executor_config = ExecutorConfig(
        rpc_url=rpc_url or os.getenv("RPC_URL", "http://localhost:8545"),
        dry_run=(mode == "paper"),
        max_slippage_pct=1.0,
    )

    # Only pass private key for live mode
    pk = private_key or os.getenv("TRADING_PRIVATE_KEY") if mode == "live" else None

    executor = BlockchainTradingExecutor(
        config=executor_config,
        private_key=pk,
    )

    # Initialize risk manager
    risk_config = RiskConfig(
        limits=RiskLimits(
            max_trade_size=500.0,
            max_daily_loss=1000.0,
            max_daily_trades=50,
            max_slippage_pct=2.0,
        ),
        enabled=True,
    )
    risk_manager = RiskManager(config=risk_config)

    # Initialize transaction monitor
    monitor_config = MonitorConfig(
        storage_path=str(storage_dir / "transactions.json"),
        alert_on_failure=True,
    )
    monitor = TransactionMonitor(config=monitor_config)

    # Initialize P&L tracker
    pnl_tracker = PnLTracker(
        storage_path=str(storage_dir / "pnl.json"),
        initial_capital=100000.0,
    )

    # Initialize agent
    agent_config = AgentConfig(
        mode=agent_mode,
        min_confidence=0.6,
        base_position_size=100.0,
        position_sizing="volatility",
    )

    agent = TradingAgent(
        config=agent_config,
        executor=executor,
        risk_manager=risk_manager,
        pnl_tracker=pnl_tracker,
    )

    # Set executor's monitor and risk manager
    executor.risk_manager = risk_manager
    executor.transaction_monitor = monitor

    # Register callbacks
    def on_decision(decision):
        logger.info(f"Decision: {decision.action.value} {decision.quantity} @ {decision.price} "
                   f"(confidence: {decision.confidence:.2f})")

    def on_execution(decision, result):
        logger.info(f"Executed: {result.status.value} - tx: {result.tx_hash}")

    agent.on_decision(on_decision)
    agent.on_execution(on_execution)

    # Setup shutdown handler
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

    # Start agent
    await agent.start()

    logger.info(f"Trading agent running in {mode} mode")
    logger.info("Press Ctrl+C to stop")

    try:
        # Main loop
        while not shutdown_event.is_set():
            try:
                # Observe and act
                result = await agent.observe_and_act()

                if result:
                    logger.info(f"Trade result: {result.status.value}")

                # Wait before next iteration
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=10.0,  # Check every 10 seconds
                )

            except asyncio.TimeoutError:
                continue

    finally:
        await agent.stop()

        # Print summary
        summary = pnl_tracker.get_summary()
        logger.info("\n" + "=" * 50)
        logger.info("Trading Session Summary")
        logger.info("=" * 50)
        logger.info(f"Total P&L: {summary['net_pnl']:.2f}")
        logger.info(f"Return: {summary['return_pct']:.2f}%")
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info("=" * 50)


async def run_demo():
    """Run a demo of the trading agent."""
    from .executor import BlockchainTradingExecutor, ExecutorConfig, TradingAction, ActionType
    from .agent import TradingAgent, AgentConfig, AgentMode
    from .risk import RiskManager, RiskConfig, RiskLimits
    from .pnl import PnLTracker

    logger.info("Running trading agent demo...")

    # Create executor in dry-run mode
    executor = BlockchainTradingExecutor(
        config=ExecutorConfig(dry_run=True),
    )

    # Create risk manager
    risk_manager = RiskManager(
        config=RiskConfig(
            limits=RiskLimits(max_trade_size=1000.0),
        ),
    )

    # Create P&L tracker
    pnl_tracker = PnLTracker(initial_capital=100000.0)

    # Create agent
    agent = TradingAgent(
        config=AgentConfig(
            mode=AgentMode.PAPER,
            min_confidence=0.5,
        ),
        executor=executor,
        risk_manager=risk_manager,
        pnl_tracker=pnl_tracker,
    )

    await agent.start()

    # Simulate some trading cycles
    for i in range(5):
        logger.info(f"\n--- Trading Cycle {i + 1} ---")

        result = await agent.observe_and_act()

        if result:
            logger.info(f"Result: {result.status.value}")
            if result.tx_hash:
                logger.info(f"TX Hash: {result.tx_hash}")

        # Print current state
        state = agent.get_state()
        logger.info(f"Position: {state['position']} kWh")
        logger.info(f"Trades today: {state['trades_today']}")

        await asyncio.sleep(1)

    await agent.stop()

    # Print final summary
    summary = pnl_tracker.get_summary()
    report = pnl_tracker.generate_report("all")

    logger.info("\n" + "=" * 50)
    logger.info("Demo Summary")
    logger.info("=" * 50)
    logger.info(f"Total Trades: {summary['total_trades']}")
    logger.info(f"Net P&L: {summary['net_pnl']:.2f}")
    logger.info(f"Win Rate: {report.win_rate:.1f}%")
    logger.info("=" * 50)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SHAKTI-CHAIN Trading Agent"
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--rpc-url",
        type=str,
        help="Blockchain RPC URL",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo mode",
    )
    args = parser.parse_args()

    if args.demo:
        asyncio.run(run_demo())
    else:
        asyncio.run(run_trading_agent(
            mode=args.mode,
            config_path=args.config,
            rpc_url=args.rpc_url,
        ))


if __name__ == "__main__":
    main()
