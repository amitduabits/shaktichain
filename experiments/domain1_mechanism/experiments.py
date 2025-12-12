"""
Market Mechanism Efficiency Experiment Runner (Domain 1).

Main orchestration module for running mechanism efficiency experiments
and generating comprehensive validation results.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .walrasian_calculator import WalrasianCalculator, WalrasianEquilibrium
from .efficiency_metrics import EfficiencyMetrics, EfficiencyResults
from .hypothesis_tests import MechanismHypothesisTester, HypothesisResult

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for mechanism efficiency experiments."""

    # Market configuration
    num_buyers: int = 50
    num_sellers: int = 50
    min_valuation: float = 5.0
    max_valuation: float = 15.0
    min_cost: float = 3.0
    max_cost: float = 12.0

    # Valuation/cost distribution
    valuation_distribution: str = "uniform"  # uniform, normal, beta
    cost_distribution: str = "uniform"

    # Experiment parameters
    num_runs: int = 100
    seed: Optional[int] = None

    # Statistical parameters
    alpha: float = 0.05
    bootstrap_iterations: int = 10000
    correction_method: str = "holm"

    # Output configuration
    output_dir: str = "results/domain1"
    save_raw_data: bool = True
    generate_plots: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "num_buyers": self.num_buyers,
            "num_sellers": self.num_sellers,
            "min_valuation": self.min_valuation,
            "max_valuation": self.max_valuation,
            "min_cost": self.min_cost,
            "max_cost": self.max_cost,
            "valuation_distribution": self.valuation_distribution,
            "cost_distribution": self.cost_distribution,
            "num_runs": self.num_runs,
            "seed": self.seed,
            "alpha": self.alpha,
            "bootstrap_iterations": self.bootstrap_iterations,
            "correction_method": self.correction_method,
            "output_dir": self.output_dir,
            "save_raw_data": self.save_raw_data,
            "generate_plots": self.generate_plots,
        }


@dataclass
class ExperimentResults:
    """
    Complete results from mechanism efficiency experiment.

    Contains all run results, hypothesis tests, and aggregate statistics.
    """

    config: ExperimentConfig
    run_results: List[EfficiencyResults]
    walrasian_equilibria: List[WalrasianEquilibrium]
    hypothesis_results: Dict[str, HypothesisResult]
    aggregate_stats: Dict[str, Any]
    execution_time_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "config": self.config.to_dict(),
            "hypothesis_results": {
                h_id: result.to_dict()
                for h_id, result in self.hypothesis_results.items()
            },
            "aggregate_stats": self.aggregate_stats,
            "execution_time_seconds": self.execution_time_seconds,
            "timestamp": self.timestamp,
            "num_runs": len(self.run_results),
        }

    def summary(self) -> str:
        """Generate summary string."""
        passed = sum(1 for r in self.hypothesis_results.values() if r.passed)
        total = len(self.hypothesis_results)

        lines = [
            f"Mechanism Efficiency Experiment Results",
            f"=" * 40,
            f"Runs: {len(self.run_results)}",
            f"Hypotheses Passed: {passed}/{total}",
            f"Execution Time: {self.execution_time_seconds:.2f}s",
            f"",
            f"Aggregate Statistics:",
        ]

        for key, value in self.aggregate_stats.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class MechanismEfficiencyExperiment:
    """
    Main experiment runner for Domain 1 - Market Mechanism Efficiency.

    Orchestrates:
    1. Market generation with configurable distributions
    2. Walrasian equilibrium computation
    3. McAfee auction simulation
    4. Efficiency metrics calculation
    5. Hypothesis testing
    6. Result aggregation and reporting
    """

    def __init__(self, config: Optional[ExperimentConfig] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration (uses defaults if None)
        """
        self.config = config or ExperimentConfig()
        self.walrasian_calculator = WalrasianCalculator()
        self.efficiency_metrics = EfficiencyMetrics()
        self.hypothesis_tester = MechanismHypothesisTester(
            alpha=self.config.alpha,
            bootstrap_iterations=self.config.bootstrap_iterations,
            correction_method=self.config.correction_method,
        )

        if self.config.seed is not None:
            np.random.seed(self.config.seed)

    def run(self, progress_callback=None) -> ExperimentResults:
        """
        Execute the full experiment.

        Args:
            progress_callback: Optional callback(run_number, total_runs)

        Returns:
            ExperimentResults with all metrics and hypothesis tests
        """
        start_time = time.time()
        logger.info(f"Starting mechanism efficiency experiment with {self.config.num_runs} runs")

        run_results: List[EfficiencyResults] = []
        walrasian_equilibria: List[WalrasianEquilibrium] = []

        for run_idx in range(self.config.num_runs):
            if progress_callback:
                progress_callback(run_idx + 1, self.config.num_runs)

            # Generate market
            buyer_valuations, seller_costs = self._generate_market()

            # Compute Walrasian equilibrium
            walrasian_eq = self.walrasian_calculator.compute_walrasian_equilibrium(
                buyer_valuations, seller_costs
            )
            walrasian_equilibria.append(walrasian_eq)

            # Compute efficiency metrics (runs McAfee auction internally)
            efficiency_result = self.efficiency_metrics.compute_efficiency_metrics(
                buyer_valuations, seller_costs, walrasian_eq
            )
            run_results.append(efficiency_result)

            if (run_idx + 1) % 10 == 0:
                logger.debug(f"Completed run {run_idx + 1}/{self.config.num_runs}")

        # Run hypothesis tests
        logger.info("Running hypothesis tests...")
        hypothesis_results = self.hypothesis_tester.run_all_tests(run_results)

        # Compute aggregate statistics
        aggregate_stats = self._compute_aggregate_stats(run_results, walrasian_equilibria)

        execution_time = time.time() - start_time
        logger.info(f"Experiment completed in {execution_time:.2f}s")

        results = ExperimentResults(
            config=self.config,
            run_results=run_results,
            walrasian_equilibria=walrasian_equilibria,
            hypothesis_results=hypothesis_results,
            aggregate_stats=aggregate_stats,
            execution_time_seconds=execution_time,
        )

        return results

    def _generate_market(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate buyer valuations and seller costs.

        Returns:
            (buyer_valuations, seller_costs) arrays
        """
        # Generate buyer valuations
        if self.config.valuation_distribution == "uniform":
            buyer_valuations = np.random.uniform(
                self.config.min_valuation,
                self.config.max_valuation,
                self.config.num_buyers,
            )
        elif self.config.valuation_distribution == "normal":
            mean = (self.config.min_valuation + self.config.max_valuation) / 2
            std = (self.config.max_valuation - self.config.min_valuation) / 4
            buyer_valuations = np.random.normal(mean, std, self.config.num_buyers)
            buyer_valuations = np.clip(
                buyer_valuations,
                self.config.min_valuation,
                self.config.max_valuation,
            )
        elif self.config.valuation_distribution == "beta":
            # Beta distribution skewed towards higher valuations
            raw = np.random.beta(2, 5, self.config.num_buyers)
            buyer_valuations = self.config.min_valuation + raw * (
                self.config.max_valuation - self.config.min_valuation
            )
        else:
            raise ValueError(f"Unknown distribution: {self.config.valuation_distribution}")

        # Generate seller costs
        if self.config.cost_distribution == "uniform":
            seller_costs = np.random.uniform(
                self.config.min_cost,
                self.config.max_cost,
                self.config.num_sellers,
            )
        elif self.config.cost_distribution == "normal":
            mean = (self.config.min_cost + self.config.max_cost) / 2
            std = (self.config.max_cost - self.config.min_cost) / 4
            seller_costs = np.random.normal(mean, std, self.config.num_sellers)
            seller_costs = np.clip(
                seller_costs,
                self.config.min_cost,
                self.config.max_cost,
            )
        elif self.config.cost_distribution == "beta":
            # Beta distribution skewed towards lower costs
            raw = np.random.beta(5, 2, self.config.num_sellers)
            seller_costs = self.config.min_cost + raw * (
                self.config.max_cost - self.config.min_cost
            )
        else:
            raise ValueError(f"Unknown distribution: {self.config.cost_distribution}")

        return buyer_valuations, seller_costs

    def _compute_aggregate_stats(
        self,
        run_results: List[EfficiencyResults],
        walrasian_equilibria: List[WalrasianEquilibrium],
    ) -> Dict[str, Any]:
        """
        Compute aggregate statistics across all runs.

        Args:
            run_results: List of efficiency results
            walrasian_equilibria: List of Walrasian equilibria

        Returns:
            Dictionary of aggregate statistics
        """
        # Extract arrays
        allocative_effs = np.array([r.allocative_efficiency for r in run_results])
        volume_effs = np.array([r.volume_efficiency for r in run_results])
        price_errors = np.array([r.price_discovery_error for r in run_results])
        buyer_ir = np.array([r.buyer_ir_rate for r in run_results])
        seller_ir = np.array([r.seller_ir_rate for r in run_results])
        revenues = np.array([r.market_maker_revenue for r in run_results])
        realized_welfares = np.array([r.realized_welfare for r in run_results])
        optimal_welfares = np.array([r.optimal_welfare for r in run_results])

        eq_prices = np.array([eq.equilibrium_price for eq in walrasian_equilibria])
        eq_quantities = np.array([eq.equilibrium_quantity for eq in walrasian_equilibria])

        return {
            # Allocative efficiency
            "allocative_efficiency_mean": float(np.mean(allocative_effs)),
            "allocative_efficiency_std": float(np.std(allocative_effs)),
            "allocative_efficiency_min": float(np.min(allocative_effs)),
            "allocative_efficiency_max": float(np.max(allocative_effs)),
            "allocative_efficiency_median": float(np.median(allocative_effs)),

            # Volume efficiency
            "volume_efficiency_mean": float(np.mean(volume_effs)),
            "volume_efficiency_std": float(np.std(volume_effs)),
            "volume_efficiency_min": float(np.min(volume_effs)),
            "volume_efficiency_max": float(np.max(volume_effs)),

            # Price discovery
            "price_discovery_error_mean": float(np.mean(np.abs(price_errors))),
            "price_discovery_error_std": float(np.std(np.abs(price_errors))),
            "price_discovery_error_max": float(np.max(np.abs(price_errors))),

            # Individual rationality
            "buyer_ir_rate_mean": float(np.mean(buyer_ir)),
            "seller_ir_rate_mean": float(np.mean(seller_ir)),
            "perfect_buyer_ir_runs": int(np.sum(buyer_ir == 1.0)),
            "perfect_seller_ir_runs": int(np.sum(seller_ir == 1.0)),

            # Budget balance
            "market_maker_revenue_mean": float(np.mean(revenues)),
            "market_maker_revenue_std": float(np.std(revenues)),
            "budget_balanced_runs": int(np.sum(revenues >= 0)),

            # Welfare
            "realized_welfare_mean": float(np.mean(realized_welfares)),
            "optimal_welfare_mean": float(np.mean(optimal_welfares)),
            "welfare_loss_mean": float(np.mean(optimal_welfares - realized_welfares)),

            # Equilibrium statistics
            "equilibrium_price_mean": float(np.mean(eq_prices)),
            "equilibrium_price_std": float(np.std(eq_prices)),
            "equilibrium_quantity_mean": float(np.mean(eq_quantities)),

            # Run counts
            "total_runs": len(run_results),
        }

    def save_results(
        self,
        results: ExperimentResults,
        output_dir: Optional[str] = None,
    ) -> Path:
        """
        Save experiment results to disk.

        Args:
            results: Experiment results to save
            output_dir: Output directory (uses config default if None)

        Returns:
            Path to saved results directory
        """
        output_path = Path(output_dir or self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = output_path / f"run_{timestamp}"
        run_dir.mkdir(exist_ok=True)

        # Save summary JSON
        summary_file = run_dir / "results_summary.json"
        with open(summary_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2)

        # Save hypothesis test report
        report_file = run_dir / "hypothesis_report.txt"
        report = self.hypothesis_tester.generate_summary_report(results.hypothesis_results)
        with open(report_file, "w") as f:
            f.write(report)

        # Save raw data if configured
        if self.config.save_raw_data:
            raw_data_file = run_dir / "raw_efficiency_data.json"
            raw_data = [r.to_dict() for r in results.run_results]
            with open(raw_data_file, "w") as f:
                json.dump(raw_data, f, indent=2)

            # Save as numpy arrays for analysis
            np.savez(
                run_dir / "efficiency_arrays.npz",
                allocative_efficiency=np.array([r.allocative_efficiency for r in results.run_results]),
                volume_efficiency=np.array([r.volume_efficiency for r in results.run_results]),
                price_discovery_error=np.array([r.price_discovery_error for r in results.run_results]),
                buyer_ir_rate=np.array([r.buyer_ir_rate for r in results.run_results]),
                seller_ir_rate=np.array([r.seller_ir_rate for r in results.run_results]),
                market_maker_revenue=np.array([r.market_maker_revenue for r in results.run_results]),
            )

        logger.info(f"Results saved to {run_dir}")
        return run_dir

    @staticmethod
    def load_results(results_dir: str) -> Dict[str, Any]:
        """
        Load saved experiment results.

        Args:
            results_dir: Path to results directory

        Returns:
            Dictionary with loaded results
        """
        results_path = Path(results_dir)

        loaded = {}

        summary_file = results_path / "results_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                loaded["summary"] = json.load(f)

        raw_file = results_path / "raw_efficiency_data.json"
        if raw_file.exists():
            with open(raw_file) as f:
                loaded["raw_data"] = json.load(f)

        arrays_file = results_path / "efficiency_arrays.npz"
        if arrays_file.exists():
            loaded["arrays"] = dict(np.load(arrays_file))

        return loaded


def run_quick_test() -> ExperimentResults:
    """
    Run a quick test with minimal configuration.

    Useful for verifying the implementation works.
    """
    config = ExperimentConfig(
        num_buyers=20,
        num_sellers=20,
        num_runs=10,
        seed=42,
        bootstrap_iterations=1000,
    )

    experiment = MechanismEfficiencyExperiment(config)
    results = experiment.run()

    print(results.summary())
    print("\n")
    print(experiment.hypothesis_tester.generate_summary_report(results.hypothesis_results))

    return results


def run_full_experiment(
    num_runs: int = 100,
    seed: Optional[int] = None,
    output_dir: str = "results/domain1",
) -> ExperimentResults:
    """
    Run full experiment with default configuration.

    Args:
        num_runs: Number of experiment runs
        seed: Random seed for reproducibility
        output_dir: Directory for saving results

    Returns:
        Complete experiment results
    """
    config = ExperimentConfig(
        num_runs=num_runs,
        seed=seed,
        output_dir=output_dir,
    )

    experiment = MechanismEfficiencyExperiment(config)

    def progress(current, total):
        if current % 10 == 0 or current == total:
            print(f"Progress: {current}/{total} runs completed")

    results = experiment.run(progress_callback=progress)
    experiment.save_results(results)

    return results


if __name__ == "__main__":
    # Run quick test when executed directly
    logging.basicConfig(level=logging.INFO)
    run_quick_test()
