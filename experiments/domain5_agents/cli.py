"""
Command-line interface for Domain 5: Agent Behavior experiments.

Usage:
    python -m experiments.domain5_agents run [options]
    python -m experiments.domain5_agents quick-test
    python -m experiments.domain5_agents analyze <path>
    python -m experiments.domain5_agents hypotheses
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .experiments import (
    AgentExperimentConfig,
    AgentBehaviorExperiment,
    AgentExperimentResults,
    run_quick_agent_test,
    run_full_agent_experiment,
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
    print("SHAKTI-CHAIN Domain 5: Agent Behavior & Strategy-Proofness Experiment")
    print("=" * 70 + "\n")


def cmd_run(args):
    """Run the main experiment."""
    setup_logging(args.verbose, args.log_file)
    print_header()

    # Build configuration from arguments
    config = AgentExperimentConfig(
        num_agents=args.num_agents,
        num_rounds=args.num_rounds,
        num_simulations=args.num_simulations,
        bounded_rational_fraction=args.br_fraction,
        efficiency_threshold=args.efficiency_threshold,
        manipulation_gain_threshold=args.manipulation_threshold,
        coalition_size_fraction=args.coalition_fraction,
        collusion_gain_threshold=args.collusion_threshold,
        num_runs=args.num_runs,
        seed=args.seed,
        alpha=args.alpha,
        output_dir=args.output,
        generate_plots=not args.no_plots,
    )

    # Print configuration
    print("Configuration:")
    print("-" * 40)
    print(f"  Agents: {config.num_agents}")
    print(f"  Rounds: {config.num_rounds}")
    print(f"  Simulations: {config.num_simulations}")
    print(f"  Number of Runs: {config.num_runs}")
    print(f"  Bounded Rational Fraction: {config.bounded_rational_fraction:.0%}")
    print(f"  Seed: {config.seed}")
    print()

    # Run experiment
    experiment = AgentBehaviorExperiment(config)

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

    results = run_quick_agent_test(seed=args.seed)

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

    results_dict = AgentBehaviorExperiment.load_results(path)

    # Print configuration
    if "config" in results_dict:
        print("Configuration:")
        print("-" * 40)
        config = results_dict["config"]
        for key in ["num_agents", "num_rounds", "num_runs", "seed"]:
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
            "id": "H5.1",
            "name": "Incentive Compatibility",
            "description": "Truthful bidding yields utility >= any deviation",
            "null": "Profitable deviation exists",
            "alternative": "Truthful bidding is optimal",
            "test": "Exact Binomial Test",
            "threshold": "< 10% deviation success rate",
        },
        {
            "id": "H5.2",
            "name": "Convergence Under Rational Agents",
            "description": "Prices converge within 50 rounds",
            "null": "No convergence within 50 rounds",
            "alternative": "Prices converge (stationary)",
            "test": "Augmented Dickey-Fuller Test",
            "threshold": "Converge by round 50",
        },
        {
            "id": "H5.3",
            "name": "Robustness to Bounded Rationality",
            "description": "Efficiency >= 85% with 50% bounded rational agents",
            "null": "Efficiency < 85%",
            "alternative": "Efficiency >= 85%",
            "test": "Two-Sample t-Test",
            "threshold": "85% efficiency",
        },
        {
            "id": "H5.4",
            "name": "Manipulation Resistance",
            "description": "Manipulation gain < 5%",
            "null": "Gain >= 5%",
            "alternative": "Gain < 5%",
            "test": "One-Sample t-Test",
            "threshold": "5% maximum gain",
        },
        {
            "id": "H5.5",
            "name": "Sybil Attack Resistance",
            "description": "Utility with n identities <= utility with 1 identity",
            "null": "Sybil attack profitable (positive slope)",
            "alternative": "Sybil attack not profitable",
            "test": "Regression Slope Test",
            "threshold": "Slope <= 0",
        },
        {
            "id": "H5.6",
            "name": "Collusion Resistance",
            "description": "Collusion gain < 10%",
            "null": "Gain >= 10%",
            "alternative": "Gain < 10%",
            "test": "Two-Sample t-Test",
            "threshold": "10% maximum gain",
        },
    ]

    print("Domain 5: Agent Behavior & Strategy-Proofness Hypotheses")
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
        description="SHAKTI-CHAIN Domain 5: Agent Behavior Experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m experiments.domain5_agents run                    Run full experiment
  python -m experiments.domain5_agents run --num-runs 5       Run with 5 iterations
  python -m experiments.domain5_agents quick-test             Run quick validation
  python -m experiments.domain5_agents analyze results.json   Analyze saved results
  python -m experiments.domain5_agents hypotheses             Show hypothesis definitions
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run agent behavior experiment")
    run_parser.add_argument(
        "--num-agents", type=int, default=30,
        help="Number of agents (default: 30)"
    )
    run_parser.add_argument(
        "--num-rounds", type=int, default=50,
        help="Number of trading rounds (default: 50)"
    )
    run_parser.add_argument(
        "--num-simulations", type=int, default=30,
        help="Number of simulations per test (default: 30)"
    )
    run_parser.add_argument(
        "--br-fraction", type=float, default=0.50,
        help="Bounded rational agent fraction (default: 0.50)"
    )
    run_parser.add_argument(
        "--efficiency-threshold", type=float, default=0.85,
        help="Efficiency threshold for H5.3 (default: 0.85)"
    )
    run_parser.add_argument(
        "--manipulation-threshold", type=float, default=0.05,
        help="Manipulation gain threshold (default: 0.05)"
    )
    run_parser.add_argument(
        "--coalition-fraction", type=float, default=0.10,
        help="Coalition size fraction (default: 0.10)"
    )
    run_parser.add_argument(
        "--collusion-threshold", type=float, default=0.10,
        help="Collusion gain threshold (default: 0.10)"
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
        "-o", "--output", type=str, default="results/domain5_agents",
        help="Output directory (default: results/domain5_agents)"
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
