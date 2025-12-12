"""
CLI for Comparative Benchmarking Experiments (Domain 8).

Provides command-line interface for running benchmark experiments.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .experiments import (
    BenchmarkExperimentConfig,
    BenchmarkExperiment,
    run_quick_benchmark_test,
    run_full_benchmark_experiment,
    print_hypothesis_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_run(args: argparse.Namespace) -> int:
    """Run benchmark experiment."""
    logger.info("Starting comparative benchmark experiment...")

    config = BenchmarkExperimentConfig(
        n_runs=args.runs,
        n_agents=args.agents,
        duration_hours=args.hours,
        random_seed=args.seed,
    )

    experiment = BenchmarkExperiment(config)
    results = experiment.run()

    # Print summary
    print_hypothesis_summary(results)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results.save(str(output_path))
        logger.info(f"Results saved to {args.output}")

    return 0 if results.hypothesis_results and results.hypothesis_results.all_passed else 1


def cmd_quick_test(args: argparse.Namespace) -> int:
    """Run quick benchmark test."""
    logger.info("Running quick benchmark test...")

    results = run_quick_benchmark_test(n_runs=args.runs)
    print_hypothesis_summary(results)

    if args.output:
        results.save(args.output)

    return 0 if results.hypothesis_results and results.hypothesis_results.all_passed else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze existing results file."""
    results_path = Path(args.results)

    if not results_path.exists():
        logger.error(f"Results file not found: {args.results}")
        return 1

    with open(results_path) as f:
        data = json.load(f)

    print("\n" + "=" * 60)
    print("BENCHMARK EXPERIMENT ANALYSIS")
    print("=" * 60)

    # Configuration
    config = data.get("config", {})
    print(f"\nConfiguration:")
    print(f"  Runs: {config.get('n_runs', 'N/A')}")
    print(f"  Agents: {config.get('n_agents', 'N/A')}")
    print(f"  Duration: {config.get('duration_hours', 'N/A')} hours")

    # Aggregate metrics
    metrics = data.get("aggregate_metrics", {})
    if metrics:
        print(f"\nAggregate Metrics:")
        print(f"  SHAKTI ROI: {metrics.get('mean_shakti_roi', 0):.2f}%")
        print(f"  Fixed Tariff ROI: {metrics.get('mean_fixed_roi', 0):.2f}%")
        print(f"  McAfee Efficiency: {metrics.get('mean_mcafee_efficiency', 0):.2%}")
        print(f"  Uniform Efficiency: {metrics.get('mean_uniform_efficiency', 0):.2%}")

    # Hypothesis results
    hr = data.get("hypothesis_results", {})
    if hr:
        print(f"\nHypothesis Test Results:")
        results_dict = hr.get("results", {})
        for h_id in ["H8.1", "H8.2", "H8.3", "H8.4", "H8.5", "H8.6"]:
            if h_id in results_dict:
                r = results_dict[h_id]
                status = "PASS" if r.get("passed") else "FAIL"
                print(f"  {h_id}: {status} (p={r.get('p_value', 1):.4f})")

        summary = hr.get("summary", {})
        print(f"\nOverall: {summary.get('n_passed', 0)}/{summary.get('n_hypotheses', 0)} passed")

    print("=" * 60)
    return 0


def cmd_hypotheses(args: argparse.Namespace) -> int:
    """Show hypothesis definitions."""
    print("\n" + "=" * 60)
    print("COMPARATIVE BENCHMARKING HYPOTHESES (Domain 8)")
    print("=" * 60)

    hypotheses = [
        ("H8.1", "ROI(SHAKTI) > ROI(Fixed Tariff)",
         "H1: SHAKTI > Fixed | Test: Independent t-test"),
        ("H8.2", "McAfee efficiency > Uniform efficiency",
         "H1: McAfee > Uniform | Test: Two-sample t-test"),
        ("H8.3", "SHAKTI welfare >= 95% of CDA",
         "H1: SHAKTI/CDA >= 0.95 | Test: TOST equivalence"),
        ("H8.4", "SHAKTI cost < Brooklyn cost",
         "H1: SHAKTI < Brooklyn | Test: Two-sample t-test"),
        ("H8.5", "SAC reward >= 95% of SOTA RL",
         "H1: SAC/SOTA >= 0.95 | Test: TOST equivalence"),
        ("H8.6", "SHAKTI is Pareto optimal",
         "H1: Not dominated | Test: Hypervolume indicator"),
    ]

    for h_id, title, description in hypotheses:
        print(f"\n{h_id}: {title}")
        print(f"  {description}")

    print("\n" + "=" * 60)
    return 0


def cmd_baselines(args: argparse.Namespace) -> int:
    """Show baseline descriptions."""
    print("\n" + "=" * 60)
    print("BENCHMARK BASELINES")
    print("=" * 60)

    baselines = [
        ("Fixed Tariff (DISCOM)", "Indian distribution company rates with time-of-use pricing and slabs"),
        ("Uniform Price Auction", "Single clearing price where all trades occur at market equilibrium"),
        ("Continuous Double Auction", "IEEE SOTA - orders matched continuously with midpoint pricing"),
        ("Brooklyn Microgrid", "P2P trading with local preference and Ethereum settlement"),
        ("SOTA RL Bidding", "IEEE Trans. Industrial Informatics 2024 - DQN-based bidding"),
    ]

    for name, description in baselines:
        print(f"\n{name}:")
        print(f"  {description}")

    print("\n" + "=" * 60)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="domain8_benchmarks",
        description="Comparative Benchmarking Experiments (Domain 8)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run full experiment")
    run_parser.add_argument("--runs", type=int, default=10,
                            help="Number of experiment runs")
    run_parser.add_argument("--agents", type=int, default=100,
                            help="Number of agents")
    run_parser.add_argument("--hours", type=int, default=720,
                            help="Simulation duration (hours)")
    run_parser.add_argument("--seed", type=int, default=42,
                            help="Random seed")
    run_parser.add_argument("--output", "-o",
                            help="Output file for results")
    run_parser.set_defaults(func=cmd_run)

    # Quick test command
    quick_parser = subparsers.add_parser("quick-test", help="Run quick test")
    quick_parser.add_argument("--runs", type=int, default=3,
                              help="Number of runs")
    quick_parser.add_argument("--output", "-o",
                              help="Output file")
    quick_parser.set_defaults(func=cmd_quick_test)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze results")
    analyze_parser.add_argument("results", help="Results JSON file")
    analyze_parser.set_defaults(func=cmd_analyze)

    # Hypotheses command
    hyp_parser = subparsers.add_parser("hypotheses", help="Show hypotheses")
    hyp_parser.set_defaults(func=cmd_hypotheses)

    # Baselines command
    base_parser = subparsers.add_parser("baselines", help="Show baselines")
    base_parser.set_defaults(func=cmd_baselines)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
