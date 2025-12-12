"""
Command-line interface for Domain 6: Stress Testing experiments.

Usage:
    python -m experiments.domain6_stress run [options]
    python -m experiments.domain6_stress quick-test
    python -m experiments.domain6_stress analyze <path>
    python -m experiments.domain6_stress hypotheses
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .experiments import (
    StressExperimentConfig,
    StressTestingExperiment,
    run_quick_stress_test,
    run_full_stress_experiment,
)


def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers,
    )


def print_header():
    """Print experiment header."""
    print("\n" + "=" * 70)
    print("SHAKTI-CHAIN Domain 6: Stress Testing & Robustness Experiment")
    print("=" * 70 + "\n")


def cmd_run(args):
    """Run the main experiment."""
    setup_logging(args.verbose, args.log_file)
    print_header()

    # Build configuration from arguments
    config = StressExperimentConfig(
        demand_multiplier=args.demand_multiplier,
        efficiency_threshold=args.efficiency_threshold,
        supply_drop_fraction=args.supply_drop,
        recovery_threshold=args.recovery_threshold,
        variance_multiplier=args.variance_multiplier,
        load_multiplier=args.load_multiplier,
        tps_threshold=args.tps_threshold,
        partition_ratio=args.partition_ratio,
        byzantine_fraction=args.byzantine_fraction,
        n_simulations=args.num_simulations,
        num_runs=args.num_runs,
        seed=args.seed,
        alpha=args.alpha,
        output_dir=args.output,
        generate_plots=not args.no_plots,
    )

    # Print configuration
    print("Configuration:")
    print("-" * 40)
    print(f"  Demand Multiplier: {config.demand_multiplier}x")
    print(f"  Supply Drop: {config.supply_drop_fraction * 100:.0f}%")
    print(f"  Variance Multiplier: {config.variance_multiplier}σ")
    print(f"  Load Multiplier: {config.load_multiplier}x")
    print(f"  Byzantine Fraction: {config.byzantine_fraction * 100:.0f}%")
    print(f"  Simulations: {config.n_simulations}")
    print(f"  Runs: {config.num_runs}")
    print(f"  Seed: {config.seed}")
    print()

    # Run experiment
    experiment = StressTestingExperiment(config)

    def progress_callback(current: int, total: int):
        pct = current / total * 100
        print(f"\rProgress: [{current}/{total}] {pct:.0f}%", end="", flush=True)

    print("Running experiment...")
    results = experiment.run(progress_callback=progress_callback)
    print("\n")

    # Print hypothesis results
    print("Hypothesis Test Results:")
    print("-" * 40)
    for h_id in sorted(results.hypothesis_results.keys()):
        result = results.hypothesis_results[h_id]
        status = "PASS" if result.passed else "FAIL"
        status_color = "\033[92m" if result.passed else "\033[91m"
        reset_color = "\033[0m"
        print(f"  {h_id} ({result.description}): {status_color}{status}{reset_color}")
        print(f"      Observed: {result.observed_value:.4f}, Threshold: {result.threshold:.4f}")
        print(f"      p-value: {result.p_value:.6f}, Decision: {result.decision}")
    print()

    # Print aggregate statistics
    print("Aggregate Statistics:")
    print("-" * 40)
    for key, value in results.aggregate_stats.items():
        if value is None:
            print(f"  {key}: N/A")
        elif isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    print()

    # Save results
    results_path = experiment.save_results(results)
    print(f"Results saved to: {results_path}")

    # Print summary
    passed = sum(1 for r in results.hypothesis_results.values() if r.passed)
    total = len(results.hypothesis_results)
    print()
    print("=" * 40)
    print(f"SUMMARY: {passed}/{total} hypotheses passed")
    print(f"Execution time: {results.execution_time_seconds:.2f}s")
    print("=" * 40)

    return 0 if passed == total else 1


def cmd_quick_test(args):
    """Run a quick validation test."""
    setup_logging(args.verbose)
    print_header()

    print("Running quick validation test...")
    print("(This is a minimal test with reduced parameters)\n")

    results = run_quick_stress_test(seed=args.seed)

    # Print results
    print("Quick Test Results:")
    print("-" * 40)

    passed_count = 0
    for h_id in sorted(results.hypothesis_results.keys()):
        result = results.hypothesis_results[h_id]
        status = "PASS" if result.passed else "FAIL"
        status_color = "\033[92m" if result.passed else "\033[91m"
        reset_color = "\033[0m"
        print(f"  {h_id}: {status_color}{status}{reset_color} (p={result.p_value:.4f})")
        if result.passed:
            passed_count += 1

    print()
    print(f"Passed: {passed_count}/{len(results.hypothesis_results)}")
    print(f"Execution time: {results.execution_time_seconds:.2f}s")

    return 0 if passed_count == len(results.hypothesis_results) else 1


def cmd_analyze(args):
    """Analyze saved experiment results."""
    setup_logging(args.verbose)
    print_header()

    path = Path(args.path)
    if not path.exists():
        print(f"Error: File not found: {path}")
        return 1

    print(f"Loading results from: {path}\n")

    results_dict = StressTestingExperiment.load_results(path)

    # Print configuration
    if "config" in results_dict:
        print("Configuration:")
        print("-" * 40)
        config = results_dict["config"]
        for key in ["demand_multiplier", "variance_multiplier", "byzantine_fraction", "num_runs", "seed"]:
            if key in config:
                print(f"  {key}: {config[key]}")
        print()

    # Print hypothesis results
    if "hypothesis_results" in results_dict:
        print("Hypothesis Results:")
        print("-" * 40)
        for h_id, result in sorted(results_dict["hypothesis_results"].items()):
            status = "PASS" if result["passed"] else "FAIL"
            print(f"  {h_id}: {status}")
            print(f"      Description: {result.get('description', 'N/A')}")
            print(f"      Observed: {result.get('observed_value', 'N/A')}")
            print(f"      Threshold: {result.get('threshold', 'N/A')}")
            print(f"      p-value: {result.get('p_value', 'N/A')}")
        print()

    # Print aggregate statistics
    if "aggregate_stats" in results_dict:
        print("Aggregate Statistics:")
        print("-" * 40)
        for key, value in results_dict["aggregate_stats"].items():
            if value is None:
                print(f"  {key}: N/A")
            elif isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
        print()

    # Summary
    if "hypothesis_results" in results_dict:
        passed = sum(1 for r in results_dict["hypothesis_results"].values() if r["passed"])
        total = len(results_dict["hypothesis_results"])
        print(f"Summary: {passed}/{total} hypotheses passed")

    if "execution_time_seconds" in results_dict:
        print(f"Execution time: {results_dict['execution_time_seconds']:.2f}s")

    return 0


def cmd_hypotheses(args):
    """Display hypothesis definitions."""
    print_header()

    hypotheses = [
        {
            "id": "H6.1",
            "name": "Peak Demand Performance",
            "description": "Efficiency >= 90% at 2.5x demand",
            "null": "Efficiency < 90%",
            "alternative": "Efficiency >= 90%",
            "test": "One-Sample t-Test",
            "threshold": "90% efficiency at 2.5x demand",
        },
        {
            "id": "H6.2",
            "name": "Supply Shock Recovery",
            "description": "Recovery within 10 rounds",
            "null": "Recovery > 10 rounds",
            "alternative": "Recovery <= 10 rounds",
            "test": "One-Sample t-Test",
            "threshold": "10 rounds max recovery time",
        },
        {
            "id": "H6.3",
            "name": "High Volatility Stability",
            "description": "No market failure at 3σ variance",
            "null": "Failure occurs",
            "alternative": "No failure",
            "test": "Exact Count",
            "threshold": "Zero failures",
        },
        {
            "id": "H6.4",
            "name": "Graceful Degradation",
            "description": "TPS >= 50% at 2x load",
            "null": "TPS < 50%",
            "alternative": "TPS >= 50%",
            "test": "One-Sample t-Test",
            "threshold": "50% TPS retention",
        },
        {
            "id": "H6.5",
            "name": "Network Partition Tolerance",
            "description": "No inconsistency after partition heal",
            "null": "Inconsistency occurs",
            "alternative": "No inconsistency",
            "test": "Binary Outcome",
            "threshold": "Zero inconsistencies",
        },
        {
            "id": "H6.6",
            "name": "Byzantine Fault Tolerance",
            "description": "Correct operation with 30% Byzantine",
            "null": "Failure with < 30% Byzantine",
            "alternative": "Correct operation with 30% Byzantine",
            "test": "Exact Binomial",
            "threshold": "95% consensus success rate",
        },
    ]

    print("Domain 6: Stress Testing & Robustness Hypotheses")
    print("=" * 60)
    print()

    for h in hypotheses:
        print(f"{h['id']}: {h['name']}")
        print(f"  Description: {h['description']}")
        print(f"  H0 (Null): {h['null']}")
        print(f"  H1 (Alternative): {h['alternative']}")
        print(f"  Test: {h['test']}")
        print(f"  Threshold: {h['threshold']}")
        print()

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SHAKTI-CHAIN Domain 6: Stress Testing Experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m experiments.domain6_stress run                    Run full experiment
  python -m experiments.domain6_stress run --num-runs 5       Run with 5 iterations
  python -m experiments.domain6_stress quick-test             Run quick validation
  python -m experiments.domain6_stress analyze results.json   Analyze saved results
  python -m experiments.domain6_stress hypotheses             Show hypothesis definitions
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run stress testing experiment")
    run_parser.add_argument(
        "--demand-multiplier", type=float, default=2.5,
        help="Peak demand multiplier (default: 2.5)"
    )
    run_parser.add_argument(
        "--efficiency-threshold", type=float, default=0.90,
        help="Efficiency threshold for H6.1 (default: 0.90)"
    )
    run_parser.add_argument(
        "--supply-drop", type=float, default=0.4,
        help="Supply drop fraction (default: 0.4)"
    )
    run_parser.add_argument(
        "--recovery-threshold", type=int, default=10,
        help="Recovery threshold in rounds (default: 10)"
    )
    run_parser.add_argument(
        "--variance-multiplier", type=float, default=3.0,
        help="Variance multiplier (default: 3.0)"
    )
    run_parser.add_argument(
        "--load-multiplier", type=float, default=2.0,
        help="Load multiplier for degradation test (default: 2.0)"
    )
    run_parser.add_argument(
        "--tps-threshold", type=float, default=0.50,
        help="TPS threshold for degradation (default: 0.50)"
    )
    run_parser.add_argument(
        "--partition-ratio", type=float, default=0.5,
        help="Network partition ratio (default: 0.5)"
    )
    run_parser.add_argument(
        "--byzantine-fraction", type=float, default=0.30,
        help="Byzantine node fraction (default: 0.30)"
    )
    run_parser.add_argument(
        "--num-simulations", type=int, default=30,
        help="Simulations per test (default: 30)"
    )
    run_parser.add_argument(
        "--num-runs", type=int, default=5,
        help="Number of experiment runs (default: 5)"
    )
    run_parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility"
    )
    run_parser.add_argument(
        "--alpha", type=float, default=0.05,
        help="Significance level (default: 0.05)"
    )
    run_parser.add_argument(
        "--no-plots", action="store_true",
        help="Disable plot generation"
    )
    run_parser.add_argument(
        "-o", "--output", type=str, default="results/domain6_stress",
        help="Output directory (default: results/domain6_stress)"
    )
    run_parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging"
    )
    run_parser.add_argument(
        "--log-file", type=str, default=None,
        help="Write logs to file"
    )
    run_parser.set_defaults(func=cmd_run)

    # Quick test command
    quick_parser = subparsers.add_parser("quick-test", help="Run quick validation test")
    quick_parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)"
    )
    quick_parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging"
    )
    quick_parser.set_defaults(func=cmd_quick_test)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze saved results")
    analyze_parser.add_argument(
        "path", type=str,
        help="Path to results JSON file"
    )
    analyze_parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging"
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # Hypotheses command
    hypo_parser = subparsers.add_parser("hypotheses", help="Show hypothesis definitions")
    hypo_parser.set_defaults(func=cmd_hypotheses)

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
