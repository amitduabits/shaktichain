#!/usr/bin/env python
"""Comprehensive backtesting script for SHAKTI-CHAIN V2G trading agent.

This script:
1. Loads a trained agent or uses baselines
2. Generates synthetic or loads historical data
3. Runs backtests with multiple strategies
4. Computes comprehensive metrics
5. Performs statistical tests
6. Generates visualizations
7. Creates backtest_report.md

Usage:
    python run_backtest.py --model-path ./models/best_model.zip
    python run_backtest.py --generate-data --days 365
    python run_backtest.py --baselines-only
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json

import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run V2G trading backtest")

    # Model options
    parser.add_argument("--model-path", type=str, default=None,
                       help="Path to trained model (.zip)")
    parser.add_argument("--baselines-only", action="store_true",
                       help="Only run baseline strategies")

    # Data options
    parser.add_argument("--data-path", type=str, default=None,
                       help="Path to historical data CSV")
    parser.add_argument("--generate-data", action="store_true",
                       help="Generate synthetic data")
    parser.add_argument("--days", type=int, default=365,
                       help="Number of days for synthetic data")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")

    # Backtest options
    parser.add_argument("--initial-balance", type=float, default=1000.0,
                       help="Initial portfolio balance")
    parser.add_argument("--volatility", type=float, default=0.3,
                       help="Price volatility for synthetic data")

    # Output options
    parser.add_argument("--output-dir", type=str, default="./backtest_output",
                       help="Output directory")
    parser.add_argument("--report-name", type=str, default="backtest_report.md",
                       help="Report filename")

    parser.add_argument("--verbose", type=int, default=1,
                       help="Verbosity level")

    return parser.parse_args()


def generate_synthetic_data(
    n_days: int = 365,
    seed: int = 42,
    base_price: float = 5.0,
    volatility: float = 0.3,
) -> pd.DataFrame:
    """Generate synthetic price and load data.

    Args:
        n_days: Number of days
        seed: Random seed
        base_price: Base price per kWh
        volatility: Price volatility

    Returns:
        DataFrame with hourly data
    """
    np.random.seed(seed)

    start_date = datetime(2024, 1, 1)
    timestamps = []
    prices = []
    loads = []

    for day in range(n_days):
        date = start_date + timedelta(days=day)
        is_weekend = date.weekday() >= 5

        for hour in range(24):
            timestamp = date + timedelta(hours=hour)
            timestamps.append(timestamp)

            # Price pattern
            # Morning peak (6-10), Evening peak (18-22)
            if 6 <= hour <= 10:
                hour_factor = 1.2 + 0.1 * (hour - 6)
            elif 18 <= hour <= 22:
                hour_factor = 1.3 + 0.15 * (hour - 18)
            elif 0 <= hour <= 5:
                hour_factor = 0.7
            else:
                hour_factor = 1.0

            # Weekend adjustment
            day_factor = 0.85 if is_weekend else 1.0

            # Random noise
            noise = np.random.normal(0, volatility * base_price)

            price = base_price * hour_factor * day_factor + noise
            price = max(base_price * 0.3, min(base_price * 5, price))
            prices.append(price)

            # Load pattern (similar to price)
            base_load = 0.5
            if 6 <= hour <= 10:
                load_factor = 1.2
            elif 18 <= hour <= 22:
                load_factor = 1.4
            elif 0 <= hour <= 5:
                load_factor = 0.6
            else:
                load_factor = 1.0

            load = base_load * load_factor * day_factor + np.random.normal(0, 0.05)
            load = max(0.2, min(1.0, load))
            loads.append(load)

    df = pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'load': loads,
    })
    df.set_index('timestamp', inplace=True)

    logger.info(f"Generated {len(df)} hours of synthetic data")
    return df


def load_historical_data(data_path: str) -> pd.DataFrame:
    """Load historical data from CSV.

    Args:
        data_path: Path to CSV file

    Returns:
        DataFrame with historical data
    """
    df = pd.read_csv(data_path)

    # Ensure timestamp column
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    else:
        df.index = pd.to_datetime(df.index)

    logger.info(f"Loaded {len(df)} rows from {data_path}")
    return df


def create_agent_policy(model_path: str):
    """Create policy function from trained model.

    Args:
        model_path: Path to model

    Returns:
        Policy function
    """
    from stable_baselines3 import PPO

    logger.info(f"Loading model from {model_path}")
    model = PPO.load(model_path)

    def policy(state):
        # Convert state dict to observation
        obs = np.array([
            state.get('soc', 0.5),
            state.get('hour', 12) / 23.0,
            # Simplified - would need full observation
        ], dtype=np.float32)

        # Pad to match expected observation space
        # This is a simplified version - actual implementation
        # would need to match the environment's observation space
        full_obs = np.zeros(58, dtype=np.float32)
        full_obs[0] = state.get('soc', 0.5)
        full_obs[1] = state.get('hour', 12) / 23.0
        full_obs[53] = state.get('price', 5.0) / 25.0  # Normalized

        action, _ = model.predict(full_obs, deterministic=True)
        return action

    return policy


def run_backtest(args):
    """Run complete backtest pipeline.

    Args:
        args: Command line arguments
    """
    from rl.backtesting import (
        V2GBacktester,
        BacktestConfig,
        PerformanceMetrics,
        AllBaselines,
        StatisticalTests,
        BootstrapCI,
        MonteCarloSimulation,
        BacktestVisualizer,
        ReportGenerator,
    )

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    plot_dir = os.path.join(args.output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    # Load or generate data
    if args.data_path:
        data = load_historical_data(args.data_path)
    else:
        data = generate_synthetic_data(
            n_days=args.days,
            seed=args.seed,
            volatility=args.volatility,
        )

    # Save generated data
    data_path = os.path.join(args.output_dir, "backtest_data.csv")
    data.to_csv(data_path)
    logger.info(f"Data saved to {data_path}")

    # Create config
    config = BacktestConfig(
        initial_balance=args.initial_balance,
        initial_soc=0.5,
    )

    # Initialize baselines
    price_list = data['price'].tolist()
    baselines = AllBaselines(price_forecast=price_list, seed=args.seed)

    # Run baseline backtests
    baseline_runs = {}
    baseline_names = ['rule_based', 'threshold', 'random', 'momentum', 'mean_reversion']

    if 'oracle' in baselines.strategies:
        baseline_names.append('oracle')

    for name in baseline_names:
        logger.info(f"Running baseline: {name}")
        strategy = baselines.get_strategy(name)
        strategy.reset()

        backtester = V2GBacktester(strategy, data, config)
        run = backtester.run(verbose=False)
        baseline_runs[strategy.name] = run

        logger.info(f"  {strategy.name}: ROI={run.total_return:.2f}%, "
                   f"Trades={run.total_trades}")

    # Run main strategy
    strategy_run = None
    strategy_name = "PPO Trading Agent"

    if args.model_path and not args.baselines_only:
        logger.info("Running trained agent backtest")
        try:
            policy = create_agent_policy(args.model_path)
            backtester = V2GBacktester(policy, data, config)
            strategy_run = backtester.run(verbose=True)
            logger.info(f"Agent: ROI={strategy_run.total_return:.2f}%, "
                       f"Trades={strategy_run.total_trades}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.info("Falling back to rule-based strategy")
            args.baselines_only = True

    if args.baselines_only or strategy_run is None:
        # Use best baseline as "strategy" for reporting
        strategy_name = "Rule-Based (Peak Arbitrage)"
        strategy = baselines.get_strategy('rule_based')
        strategy.reset()
        backtester = V2GBacktester(strategy, data, config)
        strategy_run = backtester.run(verbose=True)

    # Calculate metrics
    logger.info("Calculating performance metrics...")
    metrics = PerformanceMetrics(strategy_run)
    all_metrics = metrics.calculate_all()

    # Print summary
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"\nStrategy: {strategy_name}")
    print(f"Period: {strategy_run.start_date.date()} to {strategy_run.end_date.date()}")
    print(f"Days: {strategy_run.total_days}")
    print(f"\nTotal Return: {all_metrics['returns'].total_return:.2f}%")
    print(f"Total Profit: ₹{all_metrics['returns'].total_profit:.2f}")
    print(f"Sharpe Ratio: {all_metrics['returns'].sharpe_ratio:.2f}")
    print(f"Max Drawdown: {all_metrics['returns'].max_drawdown:.2f}%")
    print(f"Win Rate: {all_metrics['trading'].win_rate*100:.1f}%")
    print(f"Total Trades: {all_metrics['trading'].total_trades}")
    print("=" * 60)

    # Run statistical tests
    logger.info("Running statistical tests...")
    tests = StatisticalTests(alpha=0.05)
    strategy_returns = np.array(strategy_run.daily_returns)

    print("\nStatistical Tests vs Baselines:")
    print("-" * 40)
    for name, baseline_run in baseline_runs.items():
        baseline_returns = np.array(baseline_run.daily_returns)
        result = tests.t_test_vs_baseline(strategy_returns, baseline_returns)
        sig = "✓" if result.is_significant else "✗"
        print(f"{name[:25]:<25} p={result.p_value:.4f} {sig}")

    # Bootstrap confidence intervals
    logger.info("Calculating bootstrap confidence intervals...")
    bootstrap = BootstrapCI(n_bootstrap=10000, random_state=args.seed)
    ci_return = bootstrap.calculate(strategy_returns, np.mean, confidence_level=0.95)

    print(f"\n95% CI for Daily Return: [{ci_return.ci_lower*100:.3f}%, {ci_return.ci_upper*100:.3f}%]")

    # Monte Carlo simulation
    logger.info("Running Monte Carlo simulation...")
    mc = MonteCarloSimulation(n_simulations=10000, random_state=args.seed)
    mc_result = mc.simulate_returns(strategy_returns, n_days=365, target_return=0.15)

    print(f"\nMonte Carlo (365 days, n=10000):")
    print(f"  Expected Return: {mc_result.mean*100:.1f}%")
    print(f"  P(Return > 15%): {mc_result.probability_above_target*100:.1f}%")

    # Generate visualizations
    logger.info("Generating visualizations...")
    visualizer = BacktestVisualizer()
    visualizer.create_all_plots(
        strategy_run,
        baseline_runs,
        output_dir=plot_dir,
        show=False,
    )

    # Generate Monte Carlo plot
    visualizer.plot_monte_carlo(
        mc_result,
        save_path=os.path.join(plot_dir, "monte_carlo.png"),
        show=False,
    )

    # Generate report
    logger.info("Generating backtest report...")
    reporter = ReportGenerator(
        strategy_run=strategy_run,
        baseline_runs=baseline_runs,
        strategy_name=strategy_name,
    )

    report_path = os.path.join(args.output_dir, args.report_name)
    reporter.generate_report(
        output_path=report_path,
        include_plots=True,
        plot_dir="plots",
    )

    # Export JSON
    json_path = os.path.join(args.output_dir, "backtest_results.json")
    reporter.export_json(json_path)

    print(f"\n✓ Report saved to: {report_path}")
    print(f"✓ JSON results saved to: {json_path}")
    print(f"✓ Plots saved to: {plot_dir}/")

    # Final assessment
    target_roi = 15.0
    achieved_roi = all_metrics['returns'].total_return

    print("\n" + "=" * 60)
    if achieved_roi >= target_roi:
        print(f"✓ TARGET ACHIEVED: {achieved_roi:.2f}% >= {target_roi}% target")
    else:
        print(f"✗ TARGET NOT MET: {achieved_roi:.2f}% < {target_roi}% target")
        print(f"  Gap: {target_roi - achieved_roi:.2f}%")
    print("=" * 60)

    return strategy_run, baseline_runs, all_metrics


def main():
    """Main function."""
    args = parse_args()

    try:
        strategy_run, baseline_runs, metrics = run_backtest(args)
        logger.info("Backtest completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
