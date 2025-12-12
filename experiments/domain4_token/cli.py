"""
Command-line interface for Domain 4: Token Economics experiments.

Usage:
    python -m experiments.domain4_token run [options]
    python -m experiments.domain4_token quick-test
    python -m experiments.domain4_token analyze <path>
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .experiments import (
    TokenExperimentConfig,
    TokenEconomicsExperiment,
    TokenExperimentResults,
    run_quick_token_test,
    run_full_token_experiment,
)
from .hypothesis_tests import TokenHypothesisTester


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
    print("SHAKTI-CHAIN Domain 4: Token Economics Experiment")
    print("=" * 70 + "\n")


def cmd_run(args):
    """Run the main experiment."""
    setup_logging(args.verbose, args.log_file)
    print_header()

    # Build configuration from arguments
    config = TokenExperimentConfig(
        initial_supply=args.initial_supply,
        simulation_duration_days=args.duration_days,
        snapshot_interval_hours=args.snapshot_interval,
        daily_mint_mean=args.daily_mint,
        daily_burn_mean=args.daily_burn,
        num_redemptions=args.num_redemptions,
        velocity_periods=args.velocity_periods,
        num_agents=args.num_agents,
        num_runs=args.num_runs,
        seed=args.seed,
        alpha=args.alpha,
        bootstrap_iterations=args.bootstrap_iterations,
        supply_cv_threshold=args.supply_cv_threshold,
        mint_burn_tolerance=args.mint_burn_tolerance,
        velocity_tolerance=args.velocity_tolerance,
        peg_tolerance=args.peg_tolerance,
        inflation_threshold=args.inflation_threshold,
        run_stress_tests=not args.no_stress_tests,
        output_dir=args.output,
        save_raw_data=True,
        generate_plots=not args.no_plots,
    )

    # Print configuration
    print("Configuration:")
    print("-" * 40)
    print(f"  Initial Supply: {config.initial_supply:,.0f} SHAKTI")
    print(f"  Simulation Duration: {config.simulation_duration_days} days")
    print(f"  Number of Runs: {config.num_runs}")
    print(f"  Agents: {config.num_agents}")
    print(f"  Stress Tests: {'Enabled' if config.run_stress_tests else 'Disabled'}")
    print(f"  Seed: {config.seed}")
    print()

    # Run experiment
    experiment = TokenEconomicsExperiment(config)

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
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    print()

    # Print stress test results if available
    if results.stress_test_results:
        print("Stress Test Results:")
        print("-" * 40)
        for test_name, test_result in results.stress_test_results.items():
            print(f"  {test_name}:")
            for key, value in test_result.items():
                if isinstance(value, float):
                    print(f"    {key}: {value:.4f}")
                else:
                    print(f"    {key}: {value}")
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

    results = run_quick_token_test(seed=args.seed)

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

    results_dict = TokenEconomicsExperiment.load_results(path)

    # Print configuration
    if "config" in results_dict:
        print("Configuration:")
        print("-" * 40)
        config = results_dict["config"]
        for key in ["initial_supply", "simulation_duration_days", "num_runs", "seed"]:
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
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
        print()

    # Print stress test results if available
    if "stress_test_results" in results_dict and results_dict["stress_test_results"]:
        print("Stress Test Results:")
        print("-" * 40)
        for test_name, test_result in results_dict["stress_test_results"].items():
            print(f"  {test_name}:")
            for key, value in test_result.items():
                if isinstance(value, float):
                    print(f"    {key}: {value:.4f}")
                else:
                    print(f"    {key}: {value}")
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
            "id": "H4.1",
            "name": "Token Supply Stability",
            "description": "Supply coefficient of variation < 5% over 30-day periods",
            "null": "CV >= 5%",
            "alternative": "CV < 5%",
            "test": "Bootstrap CI",
            "threshold": "5%",
        },
        {
            "id": "H4.2",
            "name": "Mint-Burn Equilibrium",
            "description": "|Mint_rate - Burn_rate| / Avg_rate < 10%",
            "null": "Deviation >= 10%",
            "alternative": "Deviation < 10%",
            "test": "Paired t-test",
            "threshold": "10%",
        },
        {
            "id": "H4.3",
            "name": "Token Velocity Prediction",
            "description": "Fisher equation: |V_actual - V_predicted| / V_predicted < 20%",
            "null": "Deviation >= 20%",
            "alternative": "Deviation < 20%",
            "test": "Paired t-test",
            "threshold": "20%",
        },
        {
            "id": "H4.4",
            "name": "Token-kWh Peg Stability",
            "description": "Redemption rate = 1.0 +/- 1%",
            "null": "Deviation > 1%",
            "alternative": "Deviation <= 1%",
            "test": "One-sample t-test",
            "threshold": "1%",
        },
        {
            "id": "H4.5",
            "name": "No Hyperinflation",
            "description": "Annual inflation < 10%",
            "null": "Inflation >= 10%",
            "alternative": "Inflation < 10%",
            "test": "One-sample t-test",
            "threshold": "10%",
        },
    ]

    print("Domain 4: Token Economics Hypotheses")
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
        description="SHAKTI-CHAIN Domain 4: Token Economics Experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m experiments.domain4_token run                    Run full experiment
  python -m experiments.domain4_token run --num-runs 5       Run with 5 iterations
  python -m experiments.domain4_token quick-test             Run quick validation
  python -m experiments.domain4_token analyze results.json   Analyze saved results
  python -m experiments.domain4_token hypotheses             Show hypothesis definitions
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run token economics experiment")
    run_parser.add_argument(
        "--initial-supply", type=float, default=1_000_000.0,
        help="Initial token supply (default: 1,000,000)"
    )
    run_parser.add_argument(
        "--duration-days", type=int, default=90,
        help="Simulation duration in days (default: 90)"
    )
    run_parser.add_argument(
        "--snapshot-interval", type=float, default=1.0,
        help="Hours between supply snapshots (default: 1.0)"
    )
    run_parser.add_argument(
        "--daily-mint", type=float, default=1000.0,
        help="Mean daily mint volume (default: 1000)"
    )
    run_parser.add_argument(
        "--daily-burn", type=float, default=1000.0,
        help="Mean daily burn volume (default: 1000)"
    )
    run_parser.add_argument(
        "--num-redemptions", type=int, default=1000,
        help="Number of redemption events (default: 1000)"
    )
    run_parser.add_argument(
        "--velocity-periods", type=int, default=30,
        help="Number of velocity measurement periods (default: 30)"
    )
    run_parser.add_argument(
        "--num-agents", type=int, default=50,
        help="Number of agents in simulation (default: 50)"
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
        "--bootstrap-iterations", type=int, default=10000,
        help="Bootstrap iterations (default: 10000)"
    )
    run_parser.add_argument(
        "--supply-cv-threshold", type=float, default=0.05,
        help="Supply CV threshold (default: 0.05)"
    )
    run_parser.add_argument(
        "--mint-burn-tolerance", type=float, default=0.10,
        help="Mint-burn equilibrium tolerance (default: 0.10)"
    )
    run_parser.add_argument(
        "--velocity-tolerance", type=float, default=0.20,
        help="Velocity prediction tolerance (default: 0.20)"
    )
    run_parser.add_argument(
        "--peg-tolerance", type=float, default=0.01,
        help="Peg stability tolerance (default: 0.01)"
    )
    run_parser.add_argument(
        "--inflation-threshold", type=float, default=0.10,
        help="Inflation threshold (default: 0.10)"
    )
    run_parser.add_argument(
        "--no-stress-tests", action="store_true",
        help="Disable stress tests"
    )
    run_parser.add_argument(
        "--no-plots", action="store_true",
        help="Disable plot generation"
    )
    run_parser.add_argument(
        "-o", "--output", type=str, default="results/domain4_token",
        help="Output directory (default: results/domain4_token)"
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
