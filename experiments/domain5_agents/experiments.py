"""
Agent Behavior Experiment Runner (Domain 5).

Main orchestration module for running agent behavior and strategy-proofness
experiments and generating comprehensive validation results for SHAKTI-CHAIN.

Validates hypotheses:
- H5.1: Incentive Compatibility (Exact binomial test)
- H5.2: Convergence within 50 rounds (ADF test)
- H5.3: Robustness to bounded rationality >= 85% efficiency (Two-sample t-test)
- H5.4: Manipulation gain < 5% (One-sample t-test)
- H5.5: Sybil attack resistance (Regression slope test)
- H5.6: Collusion gain < 10% (Two-sample t-test)
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

from .incentive_compatibility import (
    IncentiveCompatibilityTester,
    ICTestResult,
    simulate_ic_test,
)
from .convergence_analyzer import (
    ConvergenceAnalyzer,
    ConvergenceTestResult,
    RobustnessTestResult,
    EfficiencyResult,
    simulate_convergence_test,
    simulate_robustness_test,
)
from .manipulation_simulator import (
    ManipulationSimulator,
    ManipulationTestResult,
    ManipulationResult,
    simulate_manipulation_test,
)
from .sybil_tester import (
    SybilTester,
    SybilTestResult,
    ComprehensiveSybilResult,
    simulate_sybil_test,
    simulate_comprehensive_sybil_test,
)
from .collusion_detector import (
    CollusionSimulator,
    CollusionTestResult,
    simulate_collusion_test,
)
from .hypothesis_tests import (
    AgentHypothesisTester,
    AgentHypothesisResult,
)
from .visualization import AgentVisualization

logger = logging.getLogger(__name__)


@dataclass
class AgentExperimentConfig:
    """Configuration for agent behavior experiments."""

    # Agent configuration
    num_agents: int = 30
    num_buyers: int = 15
    num_sellers: int = 15

    # Simulation parameters
    num_rounds: int = 50
    num_simulations: int = 30

    # IC test parameters
    ic_n_rounds: int = 30
    ic_deviations: List[float] = field(default_factory=lambda: [-0.3, -0.2, -0.1, 0.1, 0.2, 0.3])

    # Convergence parameters
    convergence_max_rounds: int = 50

    # Robustness parameters
    bounded_rational_fraction: float = 0.50
    efficiency_threshold: float = 0.85

    # Manipulation parameters
    manipulation_gain_threshold: float = 0.05
    attack_duration_rounds: int = 10

    # Sybil parameters
    sybil_wealth: float = 100.0
    sybil_identity_counts: List[int] = field(default_factory=lambda: [1, 2, 5, 10, 20])

    # Collusion parameters
    coalition_size_fraction: float = 0.10
    collusion_gain_threshold: float = 0.10

    # Statistical parameters
    alpha: float = 0.05

    # Run configuration
    num_runs: int = 5
    seed: Optional[int] = None

    # Output configuration
    output_dir: str = "results/domain5_agents"
    save_raw_data: bool = True
    generate_plots: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "num_agents": self.num_agents,
            "num_buyers": self.num_buyers,
            "num_sellers": self.num_sellers,
            "num_rounds": self.num_rounds,
            "num_simulations": self.num_simulations,
            "ic_n_rounds": self.ic_n_rounds,
            "convergence_max_rounds": self.convergence_max_rounds,
            "bounded_rational_fraction": self.bounded_rational_fraction,
            "efficiency_threshold": self.efficiency_threshold,
            "manipulation_gain_threshold": self.manipulation_gain_threshold,
            "sybil_wealth": self.sybil_wealth,
            "coalition_size_fraction": self.coalition_size_fraction,
            "collusion_gain_threshold": self.collusion_gain_threshold,
            "alpha": self.alpha,
            "num_runs": self.num_runs,
            "seed": self.seed,
            "output_dir": self.output_dir,
        }


@dataclass
class SingleAgentRunResults:
    """Results from a single agent behavior simulation run."""

    # IC results
    ic_result: ICTestResult
    deviation_success_rate: float

    # Convergence results
    convergence_result: ConvergenceTestResult
    converged: bool
    convergence_round: Optional[int]

    # Robustness results
    robustness_result: RobustnessTestResult
    efficiency_with_mixed: float

    # Manipulation results
    manipulation_result: ManipulationTestResult
    max_manipulation_gain: float

    # Sybil results
    sybil_result: SybilTestResult
    sybil_slope: float

    # Collusion results
    collusion_result: CollusionTestResult
    max_collusion_gain: float

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "deviation_success_rate": float(self.deviation_success_rate),
            "converged": self.converged,
            "convergence_round": self.convergence_round,
            "efficiency_with_mixed": float(self.efficiency_with_mixed),
            "max_manipulation_gain": float(self.max_manipulation_gain),
            "sybil_slope": float(self.sybil_slope),
            "max_collusion_gain": float(self.max_collusion_gain),
        }


@dataclass
class AgentExperimentResults:
    """Complete results from agent behavior experiment."""

    config: AgentExperimentConfig
    run_results: List[SingleAgentRunResults]
    hypothesis_results: Dict[str, AgentHypothesisResult]
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
            "Agent Behavior Experiment Results",
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


class AgentBehaviorExperiment:
    """
    Main experiment runner for Domain 5 - Agent Behavior.

    Orchestrates:
    1. Incentive compatibility testing
    2. Market convergence analysis
    3. Robustness to bounded rationality
    4. Manipulation resistance testing
    5. Sybil attack resistance testing
    6. Collusion resistance testing
    7. Hypothesis testing
    8. Result aggregation and reporting
    """

    def __init__(self, config: Optional[AgentExperimentConfig] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration (uses defaults if None)
        """
        self.config = config or AgentExperimentConfig()
        self.hypothesis_tester = AgentHypothesisTester(
            alpha=self.config.alpha,
            num_agents=self.config.num_agents,
            seed=self.config.seed,
        )

        self._rng = np.random.default_rng(self.config.seed)

    def run(self, progress_callback=None) -> AgentExperimentResults:
        """
        Execute the full experiment.

        Args:
            progress_callback: Optional callback(run_number, total_runs)

        Returns:
            AgentExperimentResults with all metrics and hypothesis tests
        """
        start_time = time.time()
        logger.info(f"Starting agent behavior experiment with {self.config.num_runs} runs")

        run_results: List[SingleAgentRunResults] = []

        # Aggregated data for hypothesis testing
        all_deviation_rates = []
        all_convergence_rounds = []
        all_efficiencies = []
        all_manipulation_gains = []
        all_sybil_slopes = []
        all_collusion_gains = []

        for run_idx in range(self.config.num_runs):
            if progress_callback:
                progress_callback(run_idx + 1, self.config.num_runs)

            seed = self.config.seed + run_idx if self.config.seed else None
            run_result = self._run_single_iteration(seed)
            run_results.append(run_result)

            # Collect aggregate data
            all_deviation_rates.append(run_result.deviation_success_rate)
            if run_result.convergence_round:
                all_convergence_rounds.append(run_result.convergence_round)
            all_efficiencies.append(run_result.efficiency_with_mixed)
            all_manipulation_gains.append(run_result.max_manipulation_gain)
            all_sybil_slopes.append(run_result.sybil_slope)
            all_collusion_gains.append(run_result.max_collusion_gain)

            if (run_idx + 1) % 2 == 0:
                logger.debug(f"Completed run {run_idx + 1}/{self.config.num_runs}")

        # Run final hypothesis tests using last run's detailed results
        logger.info("Running hypothesis tests...")
        last_run = run_results[-1]

        hypothesis_results = self.hypothesis_tester.run_all_tests(
            ic_result=last_run.ic_result,
            convergence_result=last_run.convergence_result,
            robustness_result=last_run.robustness_result,
            manipulation_result=last_run.manipulation_result,
            sybil_result=ComprehensiveSybilResult(
                is_resistant=not last_run.sybil_result.sybil_profitable,
                mean_slope=last_run.sybil_result.regression_slope,
                slope_std=last_run.sybil_result.slope_std_error,
                positive_slope_fraction=1.0 if last_run.sybil_result.sybil_profitable else 0.0,
                t_statistic=0.0,
                p_value=last_run.sybil_result.slope_p_value,
                individual_tests=[last_run.sybil_result],
            ),
            collusion_result=last_run.collusion_result,
        )

        # Compute aggregate statistics
        aggregate_stats = self._compute_aggregate_stats(
            run_results,
            all_deviation_rates,
            all_convergence_rounds,
            all_efficiencies,
            all_manipulation_gains,
            all_sybil_slopes,
            all_collusion_gains,
        )

        execution_time = time.time() - start_time
        logger.info(f"Experiment completed in {execution_time:.2f}s")

        results = AgentExperimentResults(
            config=self.config,
            run_results=run_results,
            hypothesis_results=hypothesis_results,
            aggregate_stats=aggregate_stats,
            execution_time_seconds=execution_time,
        )

        return results

    def _run_single_iteration(self, seed: Optional[int] = None) -> SingleAgentRunResults:
        """
        Run a single experiment iteration.

        Args:
            seed: Random seed for this iteration

        Returns:
            SingleAgentRunResults with all metrics
        """
        # 1. IC test
        ic_result = simulate_ic_test(
            num_buyers=self.config.num_buyers,
            num_sellers=self.config.num_sellers,
            n_rounds=self.config.ic_n_rounds,
            seed=seed,
        )

        # 2. Convergence test
        convergence_result = simulate_convergence_test(
            num_agents=self.config.num_agents,
            num_rounds=self.config.convergence_max_rounds,
            seed=seed,
        )

        # 3. Robustness test
        robustness_result = simulate_robustness_test(
            bounded_rational_fraction=self.config.bounded_rational_fraction,
            efficiency_threshold=self.config.efficiency_threshold,
            n_simulations=self.config.num_simulations // 2,
            seed=seed,
        )

        # 4. Manipulation test
        manipulation_result = simulate_manipulation_test(
            num_agents=self.config.num_agents,
            n_simulations=self.config.num_simulations // 2,
            seed=seed,
        )

        # 5. Sybil test
        sybil_result = simulate_sybil_test(
            original_wealth=self.config.sybil_wealth,
            num_other_agents=self.config.num_agents,
            seed=seed,
        )

        # 6. Collusion test
        collusion_result = simulate_collusion_test(
            num_agents=self.config.num_agents,
            coalition_fraction=self.config.coalition_size_fraction,
            n_simulations=self.config.num_simulations // 2,
            seed=seed,
        )

        return SingleAgentRunResults(
            ic_result=ic_result,
            deviation_success_rate=ic_result.deviation_success_rate,
            convergence_result=convergence_result,
            converged=convergence_result.converged,
            convergence_round=convergence_result.convergence_round,
            robustness_result=robustness_result,
            efficiency_with_mixed=robustness_result.efficiency_with_mixed,
            manipulation_result=manipulation_result,
            max_manipulation_gain=manipulation_result.max_manipulation_gain,
            sybil_result=sybil_result,
            sybil_slope=sybil_result.regression_slope,
            collusion_result=collusion_result,
            max_collusion_gain=collusion_result.max_collusion_gain,
        )

    def _compute_aggregate_stats(
        self,
        run_results: List[SingleAgentRunResults],
        all_deviation_rates: List[float],
        all_convergence_rounds: List[int],
        all_efficiencies: List[float],
        all_manipulation_gains: List[float],
        all_sybil_slopes: List[float],
        all_collusion_gains: List[float],
    ) -> Dict[str, Any]:
        """Compute aggregate statistics across all runs."""
        return {
            # IC statistics
            "mean_deviation_rate": float(np.mean(all_deviation_rates)),
            "std_deviation_rate": float(np.std(all_deviation_rates)),
            "ic_pass_rate": float(np.mean([r < 0.1 for r in all_deviation_rates])),

            # Convergence statistics
            "convergence_rate": float(np.mean([r.converged for r in run_results])),
            "mean_convergence_round": float(np.mean(all_convergence_rounds)) if all_convergence_rounds else None,

            # Robustness statistics
            "mean_efficiency_mixed": float(np.mean(all_efficiencies)),
            "std_efficiency_mixed": float(np.std(all_efficiencies)),
            "robustness_pass_rate": float(np.mean([e >= 0.85 for e in all_efficiencies])),

            # Manipulation statistics
            "mean_manipulation_gain": float(np.mean(all_manipulation_gains)),
            "max_manipulation_gain": float(np.max(all_manipulation_gains)),
            "manipulation_pass_rate": float(np.mean([g < 0.05 for g in all_manipulation_gains])),

            # Sybil statistics
            "mean_sybil_slope": float(np.mean(all_sybil_slopes)),
            "std_sybil_slope": float(np.std(all_sybil_slopes)),
            "sybil_pass_rate": float(np.mean([s <= 0 for s in all_sybil_slopes])),

            # Collusion statistics
            "mean_collusion_gain": float(np.mean(all_collusion_gains)),
            "max_collusion_gain": float(np.max(all_collusion_gains)),
            "collusion_pass_rate": float(np.mean([g < 0.10 for g in all_collusion_gains])),
        }

    def save_results(self, results: AgentExperimentResults) -> Path:
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
        results_file = output_dir / f"agent_experiment_results_{timestamp}.json"

        with open(results_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2, default=str)

        logger.info(f"Results saved to {results_file}")

        # Generate plots if enabled
        if self.config.generate_plots:
            self._generate_plots(results, output_dir)

        return results_file

    def _generate_plots(self, results: AgentExperimentResults, output_dir: Path):
        """Generate visualization plots."""
        visualizer = AgentVisualization(output_dir=str(output_dir))

        if results.run_results:
            last_run = results.run_results[-1]

            if last_run.ic_result:
                visualizer.plot_ic_scatter(last_run.ic_result)

            if last_run.sybil_result:
                visualizer.plot_sybil_regression(last_run.sybil_result)

            if last_run.manipulation_result:
                visualizer.plot_manipulation_gains(last_run.manipulation_result)

            if last_run.collusion_result:
                visualizer.plot_collusion_sensitivity(last_run.collusion_result)

        if results.hypothesis_results:
            visualizer.plot_hypothesis_summary(results.hypothesis_results)

        logger.info(f"Plots generated in {output_dir}")

    @staticmethod
    def load_results(path: Path) -> dict:
        """Load experiment results from disk."""
        with open(path, "r") as f:
            return json.load(f)


def run_quick_agent_test(seed: Optional[int] = None) -> AgentExperimentResults:
    """
    Run a quick agent behavior test with minimal configuration.

    Args:
        seed: Random seed

    Returns:
        AgentExperimentResults
    """
    config = AgentExperimentConfig(
        num_agents=20,
        num_rounds=30,
        num_simulations=15,
        ic_n_rounds=15,
        num_runs=2,
        generate_plots=False,
        seed=seed,
    )

    experiment = AgentBehaviorExperiment(config)
    return experiment.run()


def run_full_agent_experiment(
    seed: Optional[int] = None,
    output_dir: str = "results/domain5_agents",
) -> AgentExperimentResults:
    """
    Run a full agent behavior experiment.

    Args:
        seed: Random seed
        output_dir: Output directory for results

    Returns:
        AgentExperimentResults
    """
    config = AgentExperimentConfig(
        num_agents=30,
        num_rounds=50,
        num_simulations=30,
        num_runs=5,
        generate_plots=True,
        output_dir=output_dir,
        seed=seed,
    )

    experiment = AgentBehaviorExperiment(config)
    results = experiment.run()

    # Save results
    experiment.save_results(results)

    return results


if __name__ == "__main__":
    # Run quick test when executed directly
    logging.basicConfig(level=logging.INFO)
    results = run_quick_agent_test(seed=42)
    print(results.summary())
