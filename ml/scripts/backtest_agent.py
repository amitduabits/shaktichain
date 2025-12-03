#!/usr/bin/env python
"""Backtest trained V2G trading agent.

This script evaluates a trained PPO agent by:
1. Running multiple backtest episodes
2. Computing performance metrics (ROI, Sharpe, etc.)
3. Comparing against benchmark strategies
4. Generating visualizations and reports

Usage:
    python backtest_agent.py --model-path ./logs/ppo_v2g/best_model/best_model.zip
    python backtest_agent.py --model-path ./models/final_model.zip --num-episodes 200
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import logging
import json

import numpy as np

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
    parser = argparse.ArgumentParser(description="Backtest V2G trading agent")

    parser.add_argument("--model-path", type=str, required=True,
                       help="Path to trained model (.zip)")
    parser.add_argument("--num-episodes", type=int, default=100,
                       help="Number of backtest episodes")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")
    parser.add_argument("--deterministic", action="store_true", default=True,
                       help="Use deterministic actions")

    # Environment options
    parser.add_argument("--use-discrete", action="store_true",
                       help="Use discrete action space")
    parser.add_argument("--volatility", type=float, default=0.3,
                       help="Market volatility for backtest")

    # Benchmark comparisons
    parser.add_argument("--compare-benchmarks", action="store_true", default=True,
                       help="Compare against benchmark strategies")
    parser.add_argument("--benchmarks", nargs="+",
                       default=["random", "peak_arbitrage", "threshold"],
                       help="Benchmark strategies to compare")

    # Output options
    parser.add_argument("--output-dir", type=str, default="./backtest_results",
                       help="Output directory for results")
    parser.add_argument("--save-plots", action="store_true", default=True,
                       help="Save visualization plots")
    parser.add_argument("--save-json", action="store_true", default=True,
                       help="Save results as JSON")

    parser.add_argument("--verbose", type=int, default=1,
                       help="Verbosity level")

    return parser.parse_args()


def load_model(model_path: str):
    """Load trained model.

    Args:
        model_path: Path to model file

    Returns:
        Loaded PPO model
    """
    from stable_baselines3 import PPO

    logger.info(f"Loading model from {model_path}")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    model = PPO.load(model_path)
    logger.info("Model loaded successfully")

    return model


def create_backtest_env(args):
    """Create environment for backtesting.

    Args:
        args: Command line arguments

    Returns:
        V2GTradingEnv instance
    """
    from rl.environment import V2GTradingEnv, EnvironmentConfig, MarketConfig

    # Create market config with specified volatility
    market_config = MarketConfig(
        price_volatility=args.volatility,
    )

    config = EnvironmentConfig(
        market=market_config,
        seed=args.seed,
    )

    env = V2GTradingEnv(
        config=config,
        use_discrete_actions=args.use_discrete,
    )

    return env


def run_backtest(model, env, args):
    """Run backtest episodes.

    Args:
        model: Trained PPO model
        env: Backtest environment
        args: Command line arguments

    Returns:
        BacktestReporter with results
    """
    from rl.backtest import Backtester, BacktestReporter

    # Create backtester
    backtester = Backtester(env)

    # Define policy function
    def policy(obs):
        action, _ = model.predict(obs, deterministic=args.deterministic)
        return action

    # Run backtest
    logger.info(f"Running {args.num_episodes} backtest episodes...")
    results = backtester.run_multiple_episodes(
        policy=policy,
        num_episodes=args.num_episodes,
        seeds=list(range(args.seed, args.seed + args.num_episodes)),
    )

    return BacktestReporter(results), backtester


def run_benchmarks(backtester, args):
    """Run benchmark strategy comparisons.

    Args:
        backtester: Backtester instance
        args: Command line arguments

    Returns:
        Dictionary of benchmark results
    """
    benchmark_results = {}

    for strategy in args.benchmarks:
        logger.info(f"Running benchmark: {strategy}")
        try:
            result = backtester.run_benchmark(
                strategy=strategy,
                num_episodes=args.num_episodes,
                seeds=list(range(args.seed, args.seed + args.num_episodes)),
            )
            benchmark_results[strategy] = result
        except Exception as e:
            logger.warning(f"Benchmark {strategy} failed: {e}")

    return benchmark_results


def print_comparison(reporter, benchmark_results):
    """Print comparison table.

    Args:
        reporter: BacktestReporter with agent results
        benchmark_results: Dictionary of benchmark results
    """
    stats = reporter.get_summary_stats()

    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"{'Strategy':<20} {'ROI':>10} {'Win Rate':>12} {'Trades':>10} {'Profit':>12}")
    print("-" * 80)

    # Agent results
    print(f"{'PPO Agent':<20} {stats['roi']['mean']:>9.1f}% "
          f"{stats['win_rate']['mean']*100:>11.1f}% "
          f"{stats['trades_per_episode']['mean']:>10.1f} "
          f"₹{stats['profit']['mean']:>11.2f}")

    # Benchmark results
    for name, result in benchmark_results.items():
        print(f"{name:<20} {result.roi:>9.1f}% "
              f"{result.win_rate*100:>11.1f}% "
              f"{result.num_trades:>10} "
              f"₹{result.total_profit:>11.2f}")

    print("=" * 80)

    # Calculate improvement over best benchmark
    best_benchmark_roi = max(r.roi for r in benchmark_results.values()) if benchmark_results else 0
    agent_roi = stats['roi']['mean']
    improvement = agent_roi - best_benchmark_roi

    print(f"\nAgent vs Best Benchmark: {'+' if improvement >= 0 else ''}{improvement:.1f}% ROI")

    # Target check
    target_roi = 15.0
    if agent_roi >= target_roi:
        print(f"\n✓ TARGET ACHIEVED: {agent_roi:.1f}% ROI >= {target_roi}% target")
    else:
        print(f"\n✗ TARGET NOT MET: {agent_roi:.1f}% ROI < {target_roi}% target")
        print(f"  Gap: {target_roi - agent_roi:.1f}%")


def save_results(reporter, benchmark_results, output_dir, args):
    """Save backtest results.

    Args:
        reporter: BacktestReporter
        benchmark_results: Benchmark results
        output_dir: Output directory
        args: Command line arguments
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON results
    if args.save_json:
        json_path = os.path.join(output_dir, f"backtest_results_{timestamp}.json")

        stats = reporter.get_summary_stats()
        output = {
            "agent": stats,
            "benchmarks": {
                name: {
                    "roi": result.roi,
                    "win_rate": result.win_rate,
                    "num_trades": result.num_trades,
                    "total_profit": result.total_profit,
                }
                for name, result in benchmark_results.items()
            },
            "config": {
                "model_path": args.model_path,
                "num_episodes": args.num_episodes,
                "seed": args.seed,
                "volatility": args.volatility,
            },
        }

        with open(json_path, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Results saved to {json_path}")

    # Save plots
    if args.save_plots:
        plot_path = os.path.join(output_dir, f"backtest_plots_{timestamp}.png")
        reporter.plot_results(save_path=plot_path, show=False)
        logger.info(f"Plots saved to {plot_path}")


def main():
    """Main backtest function."""
    args = parse_args()

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(args.output_dir, timestamp)

    try:
        # Load model
        model = load_model(args.model_path)

        # Create environment
        env = create_backtest_env(args)

        # Run backtest
        reporter, backtester = run_backtest(model, env, args)

        # Print report
        reporter.print_report()

        # Run benchmarks
        benchmark_results = {}
        if args.compare_benchmarks:
            benchmark_results = run_benchmarks(backtester, args)
            print_comparison(reporter, benchmark_results)

        # Save results
        if args.save_json or args.save_plots:
            save_results(reporter, benchmark_results, output_dir, args)

        # Return success based on target
        stats = reporter.get_summary_stats()
        if stats['roi']['mean'] >= 15.0:
            logger.info("Backtest PASSED - Target ROI achieved!")
            return 0
        else:
            logger.warning("Backtest WARNING - Target ROI not achieved")
            return 1

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())
