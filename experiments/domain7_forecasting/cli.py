"""
CLI for Load Forecasting Experiments (Domain 7).

Provides command-line interface for running forecasting experiments.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .experiments import (
    ForecastingExperimentConfig,
    ForecastingExperiment,
    run_quick_forecasting_test,
    run_full_forecasting_experiment,
    print_hypothesis_summary,
)
from .synthetic_load_generator import INDIA_CITIES

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_run(args: argparse.Namespace) -> int:
    """Run forecasting experiment."""
    logger.info("Starting load forecasting experiment...")

    config = ForecastingExperimentConfig(
        n_runs=args.runs,
        cities=args.cities if args.cities else INDIA_CITIES,
        data_days=args.days,
        cv_splits=args.cv_splits,
        random_seed=args.seed,
    )

    experiment = ForecastingExperiment(config)
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
    """Run quick forecasting test."""
    logger.info("Running quick forecasting test...")

    cities = args.cities if args.cities else ["Delhi", "Mumbai", "Bangalore"]
    results = run_quick_forecasting_test(
        n_runs=args.runs,
        cities=cities,
        data_days=args.days,
    )

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
    print("LOAD FORECASTING EXPERIMENT ANALYSIS")
    print("=" * 60)

    # Configuration
    config = data.get("config", {})
    print(f"\nConfiguration:")
    print(f"  Runs: {config.get('n_runs', 'N/A')}")
    print(f"  Cities: {config.get('cities', [])}")
    print(f"  Data days: {config.get('data_days', 'N/A')}")

    # Aggregate metrics
    metrics = data.get("aggregate_metrics", {})
    if metrics:
        print(f"\nAggregate Metrics:")
        print(f"  Mean short-term MAPE: {metrics.get('mean_short_term_mape', 0):.2f}%")
        print(f"  Mean long-term MAPE: {metrics.get('mean_long_term_mape', 0):.2f}%")
        print(f"  Mean coverage: {metrics.get('mean_coverage', 0):.2%}")

    # Hypothesis results
    hr = data.get("hypothesis_results", {})
    if hr:
        print(f"\nHypothesis Test Results:")
        results_dict = hr.get("results", {})
        for h_id in ["H7.1", "H7.2", "H7.3", "H7.4", "H7.5"]:
            if h_id in results_dict:
                r = results_dict[h_id]
                status = "✓ PASS" if r.get("passed") else "✗ FAIL"
                print(f"  {h_id}: {status} (p={r.get('p_value', 1):.4f})")

        summary = hr.get("summary", {})
        print(f"\nOverall: {summary.get('n_passed', 0)}/{summary.get('n_hypotheses', 0)} passed")

    print("=" * 60)
    return 0


def cmd_hypotheses(args: argparse.Namespace) -> int:
    """Show hypothesis definitions."""
    print("\n" + "=" * 60)
    print("LOAD FORECASTING HYPOTHESES (Domain 7)")
    print("=" * 60)

    hypotheses = [
        ("H7.1", "MAPE < 5% on out-of-sample data",
         "H1: MAPE < 5% | Test: One-sample t-test across k-folds"),
        ("H7.2", "MAPE < 10% up to 24h horizon",
         "H1: MAPE < 10% for all h <= 24h | Test: One-sample t-tests at each horizon"),
        ("H7.3", "MAPE < 5% for all major Indian cities",
         "H1: MAPE < 5% for all cities | Test: Multiple one-sample t-tests with Bonferroni"),
        ("H7.4", "TFT beats Naive, ARIMA, Prophet",
         "H1: TFT beats all baselines | Test: Paired t-tests"),
        ("H7.5", "95% PI contains actual 95+/-3% of time",
         "H1: Coverage within 92-98% | Test: Exact binomial"),
    ]

    for h_id, title, description in hypotheses:
        print(f"\n{h_id}: {title}")
        print(f"  {description}")

    print("\n" + "=" * 60)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="domain7_forecasting",
        description="Load Forecasting Experiments (Domain 7)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run full experiment")
    run_parser.add_argument("--runs", type=int, default=10,
                            help="Number of experiment runs")
    run_parser.add_argument("--cities", nargs="+",
                            help="Cities to include")
    run_parser.add_argument("--days", type=int, default=365,
                            help="Days of data to generate")
    run_parser.add_argument("--cv-splits", type=int, default=5,
                            help="CV splits")
    run_parser.add_argument("--seed", type=int, default=42,
                            help="Random seed")
    run_parser.add_argument("--output", "-o",
                            help="Output file for results")
    run_parser.set_defaults(func=cmd_run)

    # Quick test command
    quick_parser = subparsers.add_parser("quick-test", help="Run quick test")
    quick_parser.add_argument("--runs", type=int, default=3,
                              help="Number of runs")
    quick_parser.add_argument("--cities", nargs="+",
                              help="Cities to test")
    quick_parser.add_argument("--days", type=int, default=60,
                              help="Days of data")
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

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
