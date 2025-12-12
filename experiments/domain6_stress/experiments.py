"""
Stress Testing Experiment Runner (Domain 6).

Main orchestration module for running stress testing experiments and
generating comprehensive validation results for SHAKTI-CHAIN.

Validates hypotheses:
- H6.1: Peak Demand Performance (One-sample t-test)
- H6.2: Supply Shock Recovery (One-sample t-test)
- H6.3: High Volatility Stability (Exact count)
- H6.4: Graceful Degradation (One-sample t-test)
- H6.5: Network Partition Tolerance (Binary outcome)
- H6.6: Byzantine Fault Tolerance (Exact binomial)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .peak_demand_simulator import (
    PeakDemandSimulator,
    PeakDemandResult,
    PeakDemandTestResult,
    INDIA_PEAK_SCENARIOS,
    simulate_peak_demand_test,
)
from .supply_shock_simulator import (
    SupplyShockSimulator,
    SupplyShockResult,
    RecoveryTestResult,
    SUPPLY_SHOCK_SCENARIOS,
    simulate_supply_shock_test,
)
from .volatility_injector import (
    VolatilityInjector,
    VolatilityTestResult,
    StabilityTestResult,
    VOLATILITY_SCENARIOS,
    simulate_volatility_test,
)
from .overload_tester import (
    OverloadTester,
    OverloadResult,
    DegradationTestResult,
    simulate_overload_test,
)
from .partition_simulator import (
    NetworkPartitionSimulator,
    PartitionResult,
    PartitionToleranceResult,
    simulate_partition_test,
)
from .byzantine_tester import (
    ByzantineTester,
    ByzantineTestResult,
    ByzantineToleranceResult,
    ByzantineStrategy,
    BYZANTINE_SCENARIOS,
    simulate_byzantine_test,
)
from .hypothesis_tests import (
    StressHypothesisTester,
    StressHypothesisResult,
)
from .visualization import StressVisualization

logger = logging.getLogger(__name__)


@dataclass
class StressExperimentConfig:
    """Configuration for stress testing experiments."""

    # Peak demand parameters
    demand_multiplier: float = 2.5
    efficiency_threshold: float = 0.90

    # Supply shock parameters
    supply_drop_fraction: float = 0.4
    recovery_threshold: int = 10

    # Volatility parameters
    variance_multiplier: float = 3.0
    failure_threshold: int = 3

    # Overload parameters
    load_multiplier: float = 2.0
    tps_threshold: float = 0.50

    # Partition parameters
    partition_ratio: float = 0.5
    partition_duration: float = 30.0

    # Byzantine parameters
    byzantine_fraction: float = 0.30
    byzantine_strategy: str = "equivocate"

    # Statistical parameters
    alpha: float = 0.05
    n_simulations: int = 30

    # Run configuration
    num_runs: int = 5
    seed: Optional[int] = None

    # Output configuration
    output_dir: str = "results/domain6_stress"
    save_raw_data: bool = True
    generate_plots: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "demand_multiplier": float(self.demand_multiplier),
            "efficiency_threshold": float(self.efficiency_threshold),
            "supply_drop_fraction": float(self.supply_drop_fraction),
            "recovery_threshold": self.recovery_threshold,
            "variance_multiplier": float(self.variance_multiplier),
            "load_multiplier": float(self.load_multiplier),
            "tps_threshold": float(self.tps_threshold),
            "partition_ratio": float(self.partition_ratio),
            "byzantine_fraction": float(self.byzantine_fraction),
            "alpha": float(self.alpha),
            "n_simulations": self.n_simulations,
            "num_runs": self.num_runs,
            "seed": self.seed,
            "output_dir": self.output_dir,
        }


@dataclass
class SingleStressRunResults:
    """Results from a single stress test run."""

    # Peak demand
    peak_demand_result: PeakDemandTestResult
    efficiency_at_peak: float

    # Supply shock
    recovery_result: RecoveryTestResult
    mean_recovery_time: float

    # Volatility
    stability_result: StabilityTestResult
    failure_count: int

    # Overload
    degradation_result: DegradationTestResult
    tps_ratio: float

    # Partition
    partition_result: PartitionToleranceResult
    consistency_maintained: bool

    # Byzantine
    byzantine_result: ByzantineToleranceResult
    consensus_rate: float

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "efficiency_at_peak": float(self.efficiency_at_peak),
            "mean_recovery_time": float(self.mean_recovery_time),
            "failure_count": self.failure_count,
            "tps_ratio": float(self.tps_ratio),
            "consistency_maintained": self.consistency_maintained,
            "consensus_rate": float(self.consensus_rate),
        }


@dataclass
class StressExperimentResults:
    """Complete results from stress testing experiment."""

    config: StressExperimentConfig
    run_results: List[SingleStressRunResults]
    hypothesis_results: Dict[str, StressHypothesisResult]
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
            "Stress Testing Experiment Results",
            "=" * 45,
            f"Runs: {len(self.run_results)}",
            f"Hypotheses Passed: {passed}/{total}",
            f"Execution Time: {self.execution_time_seconds:.2f}s",
            "",
            "Aggregate Statistics:",
        ]

        for key, value in self.aggregate_stats.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "Hypothesis Results:",
        ])

        for h_id in sorted(self.hypothesis_results.keys()):
            result = self.hypothesis_results[h_id]
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  {h_id}: {status} (p={result.p_value:.4f})")

        return "\n".join(lines)


class StressTestingExperiment:
    """
    Main experiment runner for Domain 6 - Stress Testing.

    Orchestrates:
    1. Peak demand simulation
    2. Supply shock recovery
    3. Volatility stability testing
    4. Overload/degradation testing
    5. Network partition simulation
    6. Byzantine fault tolerance testing
    7. Hypothesis testing
    8. Result aggregation and reporting
    """

    def __init__(self, config: Optional[StressExperimentConfig] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration (uses defaults if None)
        """
        self.config = config or StressExperimentConfig()
        self.hypothesis_tester = StressHypothesisTester(
            alpha=self.config.alpha,
            seed=self.config.seed,
        )

        self._rng = np.random.default_rng(self.config.seed)

    def run(self, progress_callback=None) -> StressExperimentResults:
        """
        Execute the full experiment.

        Args:
            progress_callback: Optional callback(run_number, total_runs)

        Returns:
            StressExperimentResults with all metrics and hypothesis tests
        """
        start_time = time.time()
        logger.info(f"Starting stress testing experiment with {self.config.num_runs} runs")

        run_results: List[SingleStressRunResults] = []

        # Aggregated data
        all_peak_efficiencies = []
        all_recovery_times = []
        all_failure_counts = []
        all_tps_ratios = []
        all_consistencies = []
        all_consensus_rates = []

        for run_idx in range(self.config.num_runs):
            if progress_callback:
                progress_callback(run_idx + 1, self.config.num_runs)

            seed = self.config.seed + run_idx if self.config.seed else None
            run_result = self._run_single_iteration(seed)
            run_results.append(run_result)

            # Collect aggregate data
            all_peak_efficiencies.append(run_result.efficiency_at_peak)
            all_recovery_times.append(run_result.mean_recovery_time)
            all_failure_counts.append(run_result.failure_count)
            all_tps_ratios.append(run_result.tps_ratio)
            all_consistencies.append(1 if run_result.consistency_maintained else 0)
            all_consensus_rates.append(run_result.consensus_rate)

            logger.debug(f"Completed run {run_idx + 1}/{self.config.num_runs}")

        # Run final hypothesis tests
        logger.info("Running hypothesis tests...")
        last_run = run_results[-1]

        hypothesis_results = self.hypothesis_tester.run_all_tests(
            peak_result=last_run.peak_demand_result,
            recovery_result=last_run.recovery_result,
            stability_result=last_run.stability_result,
            degradation_result=last_run.degradation_result,
            partition_result=last_run.partition_result,
            byzantine_result=last_run.byzantine_result,
        )

        # Compute aggregate statistics
        aggregate_stats = self._compute_aggregate_stats(
            all_peak_efficiencies,
            all_recovery_times,
            all_failure_counts,
            all_tps_ratios,
            all_consistencies,
            all_consensus_rates,
        )

        execution_time = time.time() - start_time
        logger.info(f"Experiment completed in {execution_time:.2f}s")

        results = StressExperimentResults(
            config=self.config,
            run_results=run_results,
            hypothesis_results=hypothesis_results,
            aggregate_stats=aggregate_stats,
            execution_time_seconds=execution_time,
        )

        return results

    def _run_single_iteration(self, seed: Optional[int] = None) -> SingleStressRunResults:
        """
        Run a single experiment iteration.

        Args:
            seed: Random seed for this iteration

        Returns:
            SingleStressRunResults with all metrics
        """
        # 1. Peak demand test
        peak_result = simulate_peak_demand_test(
            demand_multiplier=self.config.demand_multiplier,
            efficiency_threshold=self.config.efficiency_threshold,
            n_simulations=self.config.n_simulations // 2,
            seed=seed,
        )

        # 2. Supply shock recovery test
        recovery_result = simulate_supply_shock_test(
            supply_drop_fraction=self.config.supply_drop_fraction,
            recovery_threshold=self.config.recovery_threshold,
            n_simulations=self.config.n_simulations // 2,
            seed=seed,
        )

        # 3. Volatility stability test
        stability_result = simulate_volatility_test(
            variance_multiplier=self.config.variance_multiplier,
            n_simulations=self.config.n_simulations // 2,
            seed=seed,
        )

        # 4. Overload degradation test
        degradation_result = simulate_overload_test(
            load_multiplier=self.config.load_multiplier,
            tps_threshold=self.config.tps_threshold,
            n_simulations=self.config.n_simulations // 2,
            seed=seed,
        )

        # 5. Partition tolerance test
        partition_result = simulate_partition_test(
            partition_ratio=self.config.partition_ratio,
            duration_seconds=self.config.partition_duration,
            n_simulations=self.config.n_simulations // 2,
            seed=seed,
        )

        # 6. Byzantine tolerance test
        strategy = ByzantineStrategy(self.config.byzantine_strategy)
        byzantine_result = simulate_byzantine_test(
            byzantine_fraction=self.config.byzantine_fraction,
            strategy=strategy,
            n_simulations=self.config.n_simulations // 2,
            seed=seed,
        )

        return SingleStressRunResults(
            peak_demand_result=peak_result,
            efficiency_at_peak=peak_result.mean_efficiency,
            recovery_result=recovery_result,
            mean_recovery_time=recovery_result.mean_recovery_time,
            stability_result=stability_result,
            failure_count=stability_result.failure_count,
            degradation_result=degradation_result,
            tps_ratio=degradation_result.mean_tps_ratio,
            partition_result=partition_result,
            consistency_maintained=partition_result.passed,
            byzantine_result=byzantine_result,
            consensus_rate=byzantine_result.success_rate,
        )

    def _compute_aggregate_stats(
        self,
        all_peak_efficiencies: List[float],
        all_recovery_times: List[float],
        all_failure_counts: List[int],
        all_tps_ratios: List[float],
        all_consistencies: List[int],
        all_consensus_rates: List[float],
    ) -> Dict[str, Any]:
        """Compute aggregate statistics across all runs."""
        return {
            # Peak demand
            "mean_peak_efficiency": float(np.mean(all_peak_efficiencies)),
            "std_peak_efficiency": float(np.std(all_peak_efficiencies)),
            "peak_pass_rate": float(np.mean([e >= 0.9 for e in all_peak_efficiencies])),

            # Recovery
            "mean_recovery_time": float(np.mean(all_recovery_times)),
            "std_recovery_time": float(np.std(all_recovery_times)),
            "recovery_pass_rate": float(np.mean([t <= 10 for t in all_recovery_times])),

            # Stability
            "total_failures": int(np.sum(all_failure_counts)),
            "stability_pass_rate": float(np.mean([f == 0 for f in all_failure_counts])),

            # Degradation
            "mean_tps_ratio": float(np.mean(all_tps_ratios)),
            "std_tps_ratio": float(np.std(all_tps_ratios)),
            "degradation_pass_rate": float(np.mean([r >= 0.5 for r in all_tps_ratios])),

            # Partition
            "consistency_rate": float(np.mean(all_consistencies)),

            # Byzantine
            "mean_consensus_rate": float(np.mean(all_consensus_rates)),
            "std_consensus_rate": float(np.std(all_consensus_rates)),
        }

    def save_results(self, results: StressExperimentResults) -> Path:
        """
        Save experiment results to disk.

        Args:
            results: Experiment results to save

        Returns:
            Path to saved results file
        """
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = output_dir / f"stress_experiment_results_{timestamp}.json"

        with open(results_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2, default=str)

        logger.info(f"Results saved to {results_file}")

        # Generate plots if enabled
        if self.config.generate_plots:
            self._generate_plots(results, output_dir)

        return results_file

    def _generate_plots(self, results: StressExperimentResults, output_dir: Path):
        """Generate visualization plots."""
        visualizer = StressVisualization(output_dir=str(output_dir))

        if results.run_results:
            last_run = results.run_results[-1]

            # Collect results for plotting
            if last_run.peak_demand_result.individual_results:
                visualizer.plot_efficiency_vs_demand(last_run.peak_demand_result.individual_results)

            if last_run.recovery_result.individual_results:
                visualizer.plot_recovery_distribution(last_run.recovery_result.individual_results)
                if last_run.recovery_result.individual_results:
                    visualizer.plot_shock_recovery(last_run.recovery_result.individual_results[0])

            if last_run.stability_result.individual_results:
                visualizer.plot_volatility_heatmap(last_run.stability_result.individual_results)

            if last_run.byzantine_result.individual_results:
                visualizer.plot_byzantine_tolerance(last_run.byzantine_result.individual_results)

        if results.hypothesis_results:
            visualizer.plot_hypothesis_summary(results.hypothesis_results)

        logger.info(f"Plots generated in {output_dir}")

    @staticmethod
    def load_results(path: Path) -> dict:
        """Load experiment results from disk."""
        with open(path, "r") as f:
            return json.load(f)


def run_quick_stress_test(seed: Optional[int] = None) -> StressExperimentResults:
    """
    Run a quick stress test with minimal configuration.

    Args:
        seed: Random seed

    Returns:
        StressExperimentResults
    """
    config = StressExperimentConfig(
        n_simulations=10,
        num_runs=2,
        generate_plots=False,
        seed=seed,
    )

    experiment = StressTestingExperiment(config)
    return experiment.run()


def run_full_stress_experiment(
    seed: Optional[int] = None,
    output_dir: str = "results/domain6_stress",
) -> StressExperimentResults:
    """
    Run a full stress testing experiment.

    Args:
        seed: Random seed
        output_dir: Output directory for results

    Returns:
        StressExperimentResults
    """
    config = StressExperimentConfig(
        n_simulations=30,
        num_runs=5,
        generate_plots=True,
        output_dir=output_dir,
        seed=seed,
    )

    experiment = StressTestingExperiment(config)
    results = experiment.run()

    # Save results
    experiment.save_results(results)

    return results


if __name__ == "__main__":
    # Run quick test when executed directly
    logging.basicConfig(level=logging.INFO)
    results = run_quick_stress_test(seed=42)
    print(results.summary())
