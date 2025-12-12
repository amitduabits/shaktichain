#!/usr/bin/env python3
"""
Command Line Interface for Domain 1 - Market Mechanism Efficiency Experiments.

Usage:
    python -m experiments.domain1_mechanism.cli run --num-runs 100 --output results/
    python -m experiments.domain1_mechanism.cli quick-test
    python -m experiments.domain1_mechanism.cli analyze results/domain1/run_20241201_120000/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

from .experiments import (
    ExperimentConfig,
    ExperimentResults,
    MechanismEfficiencyExperiment,
    run_quick_test,
    run_full_experiment,
)
from .hypothesis_tests import MechanismHypothesisTester


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
    print("SHAKTI-CHAIN Market Mechanism Efficiency Experiment")
    print("Domain 1: McAfee Double Auction Validation")
    print("=" * 60)
    print()

    config = ExperimentConfig(
        num_buyers=args.num_buyers,
        num_sellers=args.num_sellers,
        min_valuation=args.min_valuation,
        max_valuation=args.max_valuation,
        min_cost=args.min_cost,
        max_cost=args.max_cost,
        valuation_distribution=args.valuation_dist,
        cost_distribution=args.cost_dist,
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
    print(f"  Buyers: {config.num_buyers}, Sellers: {config.num_sellers}")
    print(f"  Valuations: [{config.min_valuation}, {config.max_valuation}] ({config.valuation_distribution})")
    print(f"  Costs: [{config.min_cost}, {config.max_cost}] ({config.cost_distribution})")
    print(f"  Runs: {config.num_runs}")
    print(f"  Seed: {config.seed or 'random'}")
    print(f"  Alpha: {config.alpha}, Correction: {config.correction_method}")
    print()

    experiment = MechanismEfficiencyExperiment(config)

    def progress_callback(current, total):
        pct = current / total * 100
        bar_len = 40
        filled = int(bar_len * current / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\rProgress: |{bar}| {pct:5.1f}% ({current}/{total})", end="", flush=True)

    print("Running experiment...")
    results = experiment.run(progress_callback=progress_callback)
    print("\n")

    # Print summary
    print(results.summary())
    print()

    # Print hypothesis results
    tester = MechanismHypothesisTester(
        alpha=config.alpha,
        correction_method=config.correction_method,
    )
    print(tester.generate_summary_report(results.hypothesis_results))

    # Save results
    if args.output:
        output_dir = experiment.save_results(results)
        print(f"\nResults saved to: {output_dir}")

        # Generate plots
        if not args.no_plots:
            try:
                from .visualization import MechanismVisualizer
                visualizer = MechanismVisualizer(output_dir=str(output_dir))
                visualizer.generate_all_plots(results, show=False)
                visualizer.close_all()
                print(f"Plots saved to: {output_dir}")
            except ImportError as e:
                print(f"Warning: Could not generate plots ({e})")

    return 0 if all(r.passed for r in results.hypothesis_results.values()) else 1


def cmd_quick_test(args):
    """Run quick test."""
    print("Running quick test...")
    print("-" * 40)

    results = run_quick_test()

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
    loaded = MechanismEfficiencyExperiment.load_results(str(results_dir))

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
            from .visualization import MechanismVisualizer
            from .efficiency_metrics import EfficiencyResults

            if "raw_data" in loaded:
                # Reconstruct results for plotting
                run_results = [
                    EfficiencyResults(**{k: v for k, v in r.items() if k != 'trades'})
                    for r in loaded["raw_data"]
                ]
                # Would need full reconstruction for complete plotting
                print("\nNote: Full plot regeneration requires complete result objects.")
            else:
                print("\nCannot regenerate plots: raw data not found")
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

    print("Comparing experiments:")
    print("-" * 60)

    comparison_data = []
    for d in dirs:
        loaded = MechanismEfficiencyExperiment.load_results(str(d))
        if "summary" in loaded:
            comparison_data.append({
                "dir": str(d),
                "data": loaded["summary"],
            })

    if not comparison_data:
        print("No valid results found to compare")
        return 1

    # Print comparison table
    headers = ["Metric"] + [str(d["dir"]).split("/")[-1][:20] for d in comparison_data]

    metrics = [
        ("allocative_efficiency_mean", "Alloc. Efficiency"),
        ("volume_efficiency_mean", "Volume Efficiency"),
        ("price_discovery_error_mean", "Price Error"),
        ("buyer_ir_rate_mean", "Buyer IR Rate"),
        ("seller_ir_rate_mean", "Seller IR Rate"),
        ("market_maker_revenue_mean", "MM Revenue"),
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


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SHAKTI-CHAIN Market Mechanism Efficiency Experiments (Domain 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Run full experiment:
    python -m experiments.domain1_mechanism.cli run --num-runs 100

  Quick test:
    python -m experiments.domain1_mechanism.cli quick-test

  Analyze results:
    python -m experiments.domain1_mechanism.cli analyze results/domain1/run_20241201_120000/

  Compare experiments:
    python -m experiments.domain1_mechanism.cli compare results/run1/ results/run2/
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--log-file", type=str, help="Log to file")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run mechanism efficiency experiment")
    run_parser.add_argument("--num-runs", type=int, default=100, help="Number of experiment runs")
    run_parser.add_argument("--num-buyers", type=int, default=50, help="Number of buyers")
    run_parser.add_argument("--num-sellers", type=int, default=50, help="Number of sellers")
    run_parser.add_argument("--min-valuation", type=float, default=5.0, help="Minimum buyer valuation")
    run_parser.add_argument("--max-valuation", type=float, default=15.0, help="Maximum buyer valuation")
    run_parser.add_argument("--min-cost", type=float, default=3.0, help="Minimum seller cost")
    run_parser.add_argument("--max-cost", type=float, default=12.0, help="Maximum seller cost")
    run_parser.add_argument("--valuation-dist", type=str, default="uniform",
                           choices=["uniform", "normal", "beta"], help="Buyer valuation distribution")
    run_parser.add_argument("--cost-dist", type=str, default="uniform",
                           choices=["uniform", "normal", "beta"], help="Seller cost distribution")
    run_parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    run_parser.add_argument("--alpha", type=float, default=0.05, help="Significance level")
    run_parser.add_argument("--bootstrap-iterations", type=int, default=10000,
                           help="Bootstrap iterations for CI")
    run_parser.add_argument("--correction", type=str, default="holm",
                           choices=["none", "bonferroni", "holm"],
                           help="Multiple comparison correction method")
    run_parser.add_argument("--output", "-o", type=str, default="results/domain1",
                           help="Output directory")
    run_parser.add_argument("--no-raw-data", action="store_true", help="Don't save raw data")
    run_parser.add_argument("--no-plots", action="store_true", help="Don't generate plots")
    run_parser.set_defaults(func=cmd_run)

    # Quick test command
    quick_parser = subparsers.add_parser("quick-test", help="Run quick validation test")
    quick_parser.set_defaults(func=cmd_quick_test)

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
