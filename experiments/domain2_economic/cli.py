#!/usr/bin/env python3
"""
Command Line Interface for Domain 2 - Economic Performance Experiments.

Usage:
    python -m experiments.domain2_economic.cli run --num-runs 100 --output results/
    python -m experiments.domain2_economic.cli quick-test
    python -m experiments.domain2_economic.cli analyze results/domain2/run_20241201_120000/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

from .experiments import (
    EconomicExperimentConfig,
    EconomicExperimentResults,
    EconomicPerformanceExperiment,
    run_quick_economic_test,
    run_full_economic_experiment,
)
from .hypothesis_tests import EconomicHypothesisTester


def setup_logging(verbose: bool = False, log_file: str = None):
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=level, format=format_str, handlers=handlers)


def cmd_run(args):
    """Execute experiment run command."""
    print("=" * 60)
    print("SHAKTI-CHAIN Economic Performance Experiment")
    print("Domain 2: ROI, Fairness, and Market Quality Validation")
    print("=" * 60)
    print()

    # Parse agent types
    agent_types = args.agent_types.split(",") if args.agent_types else ["RAT", "BND", "ZI", "BEH"]

    config = EconomicExperimentConfig(
        num_agents_per_type=args.agents_per_type,
        agent_types=agent_types,
        min_battery_capacity_kwh=args.min_battery,
        max_battery_capacity_kwh=args.max_battery,
        battery_cost_per_kwh=args.battery_cost,
        registration_cost=args.registration_cost,
        min_trades_per_agent=args.min_trades,
        max_trades_per_agent=args.max_trades,
        min_price=args.min_price,
        max_price=args.max_price,
        fee_rate=args.fee_rate,
        order_book_snapshots_per_run=args.snapshots,
        simulation_duration_days=args.duration,
        degradation_rate_per_cycle=args.degradation_rate,
        annual_discount_rate=args.discount_rate,
        num_runs=args.num_runs,
        seed=args.seed,
        alpha=args.alpha,
        bootstrap_iterations=args.bootstrap_iterations,
        correction_method=args.correction,
        output_dir=args.output,
        save_raw_data=not args.no_raw_data,
        generate_plots=not args.no_plots,
    )

    print(f"Configuration:")
    print(f"  Agent Types: {config.agent_types}")
    print(f"  Agents per Type: {config.num_agents_per_type}")
    print(f"  Total Agents: {len(config.agent_types) * config.num_agents_per_type}")
    print(f"  Battery Range: [{config.min_battery_capacity_kwh}, {config.max_battery_capacity_kwh}] kWh")
    print(f"  Price Range: [{config.min_price}, {config.max_price}] INR/kWh")
    print(f"  Simulation Duration: {config.simulation_duration_days} days")
    print(f"  Runs: {config.num_runs}")
    print(f"  Seed: {config.seed or 'random'}")
    print(f"  Alpha: {config.alpha}, Correction: {config.correction_method}")
    print()

    experiment = EconomicPerformanceExperiment(config)

    def progress_callback(current, total):
        pct = current / total * 100
        bar_len = 40
        filled = int(bar_len * current / total)
        bar = "=" * filled + "-" * (bar_len - filled)
        print(f"\rProgress: |{bar}| {pct:5.1f}% ({current}/{total})", end="", flush=True)

    print("Running experiment...")
    results = experiment.run(progress_callback=progress_callback)
    print("\n")

    # Print summary
    print(results.summary())
    print()

    # Print hypothesis results
    tester = EconomicHypothesisTester(
        alpha=config.alpha,
        correction_method=config.correction_method,
    )
    print(tester.generate_summary_report(results.hypothesis_results))

    # Print ROI by battery size
    print("\nROI by Battery Size:")
    print("-" * 40)
    for size, stats in results.roi_by_battery_size.items():
        if not np.isnan(stats.get("mean", np.nan)):
            print(f"  {size.capitalize()}: mean={stats['mean']*100:.2f}%, n={stats['n']}")

    # Save results
    if args.output:
        output_dir = experiment.save_results(results)
        print(f"\nResults saved to: {output_dir}")

    return 0 if all(r.passed for r in results.hypothesis_results.values()) else 1


def cmd_quick_test(args):
    """Run quick test."""
    print("Running quick economic test...")
    print("-" * 40)

    results = run_quick_economic_test()

    passed = sum(1 for r in results.hypothesis_results.values() if r.passed)
    total = len(results.hypothesis_results)

    print(f"\nQuick test complete: {passed}/{total} hypotheses passed")

    return 0 if passed == total else 1


def cmd_analyze(args):
    """Analyze existing results."""
    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        return 1

    print(f"Analyzing results from: {results_dir}")
    print("-" * 60)

    # Load results
    loaded = EconomicPerformanceExperiment.load_results(str(results_dir))

    if "summary" in loaded:
        summary = loaded["summary"]
        print("\nExperiment Summary:")
        print(f"  Timestamp: {summary.get('timestamp', 'N/A')}")
        print(f"  Runs: {summary.get('num_runs', 'N/A')}")
        print(f"  Execution Time: {summary.get('execution_time_seconds', 0):.2f}s")

        print("\nAggregate Statistics:")
        for key, value in summary.get("aggregate_stats", {}).items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

        print("\nHypothesis Results:")
        for h_id, result in sorted(summary.get("hypothesis_results", {}).items()):
            status = "PASS" if result["decision"] == "reject_null" else "FAIL"
            print(f"  {h_id}: {status} (p={result['p_value']:.4f})")

        print("\nROI by Battery Size:")
        for size, stats in summary.get("roi_by_battery_size", {}).items():
            if stats.get("mean") is not None and not np.isnan(stats.get("mean", np.nan)):
                print(f"  {size.capitalize()}: mean={stats['mean']*100:.2f}%, n={stats.get('n', 0)}")

    if "arrays" in loaded and args.detailed:
        print("\nDetailed Statistics from Arrays:")
        arrays = loaded["arrays"]
        for name, arr in arrays.items():
            print(f"\n  {name}:")
            print(f"    Mean: {np.mean(arr):.4f}")
            print(f"    Std: {np.std(arr):.4f}")
            print(f"    Min: {np.min(arr):.4f}")
            print(f"    Max: {np.max(arr):.4f}")
            print(f"    Median: {np.median(arr):.4f}")

    # Regenerate plots if requested
    if args.regenerate_plots:
        try:
            from .visualization import EconomicVisualizer

            if "arrays" in loaded:
                visualizer = EconomicVisualizer(str(results_dir / "plots_regenerated"))
                # Would need full data reconstruction for complete plotting
                print("\nNote: Full plot regeneration requires complete result objects.")
            else:
                print("\nCannot regenerate plots: array data not found")
        except ImportError:
            print("\nCannot regenerate plots: matplotlib not available")

    return 0


def cmd_compare(args):
    """Compare multiple experiment runs."""
    dirs = [Path(d) for d in args.dirs]

    for d in dirs:
        if not d.exists():
            print(f"Error: Directory not found: {d}")
            return 1

    print("Comparing economic experiments:")
    print("-" * 60)

    comparison_data = []
    for d in dirs:
        loaded = EconomicPerformanceExperiment.load_results(str(d))
        if "summary" in loaded:
            comparison_data.append({
                "dir": str(d),
                "data": loaded["summary"],
            })

    if not comparison_data:
        print("No valid results found to compare")
        return 1

    # Print comparison table
    metrics = [
        ("roi_mean", "Mean ROI"),
        ("roi_above_15pct_rate", "ROI > 15% Rate"),
        ("gini_mean", "Mean Gini"),
        ("gini_below_0.4_rate", "Gini < 0.4 Rate"),
        ("spread_mean", "Mean Spread"),
        ("cv_mean", "Mean CV"),
        ("fill_rate_mean", "Mean Fill Rate"),
    ]

    # Print header
    print(f"\n{'Metric':<25}", end="")
    for d in comparison_data:
        name = str(d["dir"]).split("/")[-1][:15]
        print(f"{name:>18}", end="")
    print()
    print("-" * (25 + 18 * len(comparison_data)))

    # Print rows
    for metric_key, metric_name in metrics:
        print(f"{metric_name:<25}", end="")
        for d in comparison_data:
            value = d["data"].get("aggregate_stats", {}).get(metric_key, "N/A")
            if isinstance(value, float):
                print(f"{value:>18.4f}", end="")
            else:
                print(f"{str(value):>18}", end="")
        print()

    return 0


def cmd_hypotheses(args):
    """Print hypothesis descriptions."""
    print("Domain 2: Economic Performance Hypotheses")
    print("=" * 60)
    print()

    hypotheses = [
        ("H2.1", "Participant ROI > 15%",
         "H0: Mean ROI <= 15%",
         "H1: Mean ROI > 15%",
         "One-sample t-test (one-tailed)"),

        ("H2.2", "ROI varies by agent type",
         "H0: mu_RAT = mu_BND = mu_ZI = mu_BEH",
         "H1: At least one mean differs",
         "One-way ANOVA + Tukey HSD"),

        ("H2.3", "Welfare distribution fairness",
         "H0: Gini >= 0.4 (unfair)",
         "H1: Gini < 0.4 (fair)",
         "Bootstrap CI for Gini coefficient"),

        ("H2.4", "Price volatility",
         "H0: CV >= 0.15 (high volatility)",
         "H1: CV < 0.15 (acceptable)",
         "Bootstrap CI for coefficient of variation"),

        ("H2.5", "Bid-ask spread",
         "H0: Spread >= 10% of mid-price",
         "H1: Spread < 10%",
         "One-sample t-test (one-tailed)"),

        ("H2.6", "Market liquidity",
         "H0: Fill rate <= 80%",
         "H1: Fill rate > 80%",
         "One-sample proportion z-test"),
    ]

    for h_id, desc, h0, h1, test in hypotheses:
        print(f"{h_id}: {desc}")
        print(f"  {h0}")
        print(f"  {h1}")
        print(f"  Test: {test}")
        print()

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SHAKTI-CHAIN Economic Performance Experiments (Domain 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Run full experiment:
    python -m experiments.domain2_economic.cli run --num-runs 100

  Quick test:
    python -m experiments.domain2_economic.cli quick-test

  List hypotheses:
    python -m experiments.domain2_economic.cli hypotheses

  Analyze results:
    python -m experiments.domain2_economic.cli analyze results/domain2/run_20241201_120000/

  Compare experiments:
    python -m experiments.domain2_economic.cli compare results/run1/ results/run2/
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--log-file", type=str, help="Log to file")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run economic performance experiment")
    run_parser.add_argument("--num-runs", type=int, default=100, help="Number of experiment runs")
    run_parser.add_argument("--agents-per-type", type=int, default=25, help="Agents per agent type")
    run_parser.add_argument("--agent-types", type=str, default="RAT,BND,ZI,BEH",
                           help="Comma-separated list of agent types")
    run_parser.add_argument("--min-battery", type=float, default=5.0, help="Minimum battery capacity (kWh)")
    run_parser.add_argument("--max-battery", type=float, default=100.0, help="Maximum battery capacity (kWh)")
    run_parser.add_argument("--battery-cost", type=float, default=10000.0, help="Battery cost per kWh (INR)")
    run_parser.add_argument("--registration-cost", type=float, default=500.0, help="Registration cost (INR)")
    run_parser.add_argument("--min-trades", type=int, default=5, help="Minimum trades per agent")
    run_parser.add_argument("--max-trades", type=int, default=50, help="Maximum trades per agent")
    run_parser.add_argument("--min-price", type=float, default=5.0, help="Minimum price (INR/kWh)")
    run_parser.add_argument("--max-price", type=float, default=15.0, help="Maximum price (INR/kWh)")
    run_parser.add_argument("--fee-rate", type=float, default=0.01, help="Transaction fee rate")
    run_parser.add_argument("--snapshots", type=int, default=100, help="Order book snapshots per run")
    run_parser.add_argument("--duration", type=float, default=30.0, help="Simulation duration (days)")
    run_parser.add_argument("--degradation-rate", type=float, default=0.001,
                           help="Battery degradation rate per cycle")
    run_parser.add_argument("--discount-rate", type=float, default=0.08, help="Annual discount rate")
    run_parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    run_parser.add_argument("--alpha", type=float, default=0.05, help="Significance level")
    run_parser.add_argument("--bootstrap-iterations", type=int, default=10000,
                           help="Bootstrap iterations for CI")
    run_parser.add_argument("--correction", type=str, default="holm",
                           choices=["none", "bonferroni", "holm"],
                           help="Multiple comparison correction method")
    run_parser.add_argument("--output", "-o", type=str, default="results/domain2",
                           help="Output directory")
    run_parser.add_argument("--no-raw-data", action="store_true", help="Don't save raw data")
    run_parser.add_argument("--no-plots", action="store_true", help="Don't generate plots")
    run_parser.set_defaults(func=cmd_run)

    # Quick test command
    quick_parser = subparsers.add_parser("quick-test", help="Run quick validation test")
    quick_parser.set_defaults(func=cmd_quick_test)

    # Hypotheses command
    hyp_parser = subparsers.add_parser("hypotheses", help="List all hypotheses")
    hyp_parser.set_defaults(func=cmd_hypotheses)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze existing results")
    analyze_parser.add_argument("results_dir", type=str, help="Path to results directory")
    analyze_parser.add_argument("--detailed", action="store_true", help="Show detailed statistics")
    analyze_parser.add_argument("--regenerate-plots", action="store_true", help="Regenerate plots")
    analyze_parser.set_defaults(func=cmd_analyze)

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare multiple experiment runs")
    compare_parser.add_argument("dirs", nargs="+", help="Directories to compare")
    compare_parser.set_defaults(func=cmd_compare)

    args = parser.parse_args()

    setup_logging(args.verbose, args.log_file)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
