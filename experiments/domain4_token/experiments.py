"""
Token Economics Experiment Runner (Domain 4).

Main orchestration module for running token economics experiments
and generating comprehensive validation results for SHAKTI-CHAIN.

Validates hypotheses:
- H4.1: Supply CV < 5% over 30-day periods (Bootstrap CI)
- H4.2: |Mint_rate - Burn_rate| / Avg_rate < 10% (Paired t-test)
- H4.3: |V_actual - V_predicted| / V_predicted < 20% (Paired t-test)
- H4.4: Redemption rate = 1.0 +/- 1% (One-sample t-test)
- H4.5: Annual inflation < 10% (One-sample t-test)
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

from .token_supply_tracker import (
    TokenSupplyTracker,
    TokenSupplySnapshot,
    simulate_token_supply,
    simulate_supply_scenarios,
)
from .mint_burn_analyzer import (
    MintBurnAnalyzer,
    MintBurnEvent,
    DailyMintBurnStats,
    simulate_mint_burn_events,
    simulate_equilibrium_scenarios,
)
from .velocity_calculator import (
    VelocityCalculator,
    VelocityMeasurement,
    simulate_velocity_data,
    simulate_velocity_scenarios,
)
from .peg_stability_tester import (
    PegStabilityTester,
    RedemptionEvent,
    simulate_redemptions,
    simulate_peg_scenarios,
    simulate_stress_redemptions,
)
from .inflation_monitor import (
    InflationMonitor,
    InflationMeasurement,
    simulate_inflation_data,
    simulate_inflation_scenarios,
    simulate_mint_attack,
)
from .hypothesis_tests import (
    TokenHypothesisTester,
    TokenHypothesisResult,
)
from .visualization import TokenVisualization

logger = logging.getLogger(__name__)


@dataclass
class TokenExperimentConfig:
    """Configuration for token economics experiments."""

    # Initial token supply
    initial_supply: float = 1_000_000.0

    # Simulation duration
    simulation_duration_days: int = 90
    snapshot_interval_hours: float = 1.0

    # Mint/burn rates (daily mean)
    daily_mint_mean: float = 1000.0
    daily_burn_mean: float = 1000.0
    mint_burn_volatility: float = 0.1

    # Velocity parameters
    velocity_periods: int = 30
    velocity_period_days: int = 1
    base_transaction_volume: float = 100_000.0
    base_price_per_kwh: float = 1.0

    # Redemption parameters
    num_redemptions: int = 1000
    redemption_rate_std: float = 0.005
    mean_redemption_size: float = 100.0

    # Inflation parameters
    daily_mint_rate: float = 0.0002  # ~7.5% annual
    daily_burn_rate: float = 0.00015

    # Agent configuration
    num_agents: int = 50

    # Scenario configuration
    run_stress_tests: bool = True
    stress_redemption_fraction: float = 0.20
    stress_duration_hours: float = 1.0
    mint_attack_multiplier: float = 10.0

    # Run configuration
    num_runs: int = 5
    seed: Optional[int] = None

    # Statistical parameters
    alpha: float = 0.05
    bootstrap_iterations: int = 10000
    correction_method: str = "holm"

    # Thresholds from requirements
    supply_cv_threshold: float = 0.05
    mint_burn_tolerance: float = 0.10
    velocity_tolerance: float = 0.20
    peg_tolerance: float = 0.01
    inflation_threshold: float = 0.10

    # Output configuration
    output_dir: str = "results/domain4_token"
    save_raw_data: bool = True
    generate_plots: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "initial_supply": self.initial_supply,
            "simulation_duration_days": self.simulation_duration_days,
            "snapshot_interval_hours": self.snapshot_interval_hours,
            "daily_mint_mean": self.daily_mint_mean,
            "daily_burn_mean": self.daily_burn_mean,
            "mint_burn_volatility": self.mint_burn_volatility,
            "velocity_periods": self.velocity_periods,
            "velocity_period_days": self.velocity_period_days,
            "base_transaction_volume": self.base_transaction_volume,
            "base_price_per_kwh": self.base_price_per_kwh,
            "num_redemptions": self.num_redemptions,
            "redemption_rate_std": self.redemption_rate_std,
            "mean_redemption_size": self.mean_redemption_size,
            "daily_mint_rate": self.daily_mint_rate,
            "daily_burn_rate": self.daily_burn_rate,
            "num_agents": self.num_agents,
            "run_stress_tests": self.run_stress_tests,
            "stress_redemption_fraction": self.stress_redemption_fraction,
            "stress_duration_hours": self.stress_duration_hours,
            "mint_attack_multiplier": self.mint_attack_multiplier,
            "num_runs": self.num_runs,
            "seed": self.seed,
            "alpha": self.alpha,
            "bootstrap_iterations": self.bootstrap_iterations,
            "correction_method": self.correction_method,
            "supply_cv_threshold": self.supply_cv_threshold,
            "mint_burn_tolerance": self.mint_burn_tolerance,
            "velocity_tolerance": self.velocity_tolerance,
            "peg_tolerance": self.peg_tolerance,
            "inflation_threshold": self.inflation_threshold,
            "output_dir": self.output_dir,
            "save_raw_data": self.save_raw_data,
            "generate_plots": self.generate_plots,
        }


@dataclass
class SingleTokenRunResults:
    """Results from a single token economics simulation run."""

    # Supply data
    supply_snapshots: List[TokenSupplySnapshot]
    supply_cv: float
    supply_cv_max: float

    # Mint/burn data
    mint_burn_events: List[MintBurnEvent]
    daily_mint_burn_stats: List[DailyMintBurnStats]
    mint_burn_equilibrium: bool
    rate_difference: float

    # Velocity data
    velocity_measurements: List[VelocityMeasurement]
    velocity_error: float
    velocity_correlation: float

    # Peg data
    redemption_events: List[RedemptionEvent]
    peg_mean_rate: float
    peg_deviation: float

    # Inflation data
    inflation_measurements: List[InflationMeasurement]
    mean_annual_inflation: float
    max_inflation: float

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "supply_cv": float(self.supply_cv),
            "supply_cv_max": float(self.supply_cv_max),
            "num_supply_snapshots": len(self.supply_snapshots),
            "mint_burn_events_count": len(self.mint_burn_events),
            "mint_burn_equilibrium": self.mint_burn_equilibrium,
            "rate_difference": float(self.rate_difference),
            "velocity_error": float(self.velocity_error),
            "velocity_correlation": float(self.velocity_correlation),
            "num_redemptions": len(self.redemption_events),
            "peg_mean_rate": float(self.peg_mean_rate),
            "peg_deviation": float(self.peg_deviation),
            "mean_annual_inflation": float(self.mean_annual_inflation),
            "max_inflation": float(self.max_inflation),
        }


@dataclass
class TokenExperimentResults:
    """
    Complete results from token economics experiment.

    Contains all run results, hypothesis tests, and aggregate statistics.
    """

    config: TokenExperimentConfig
    run_results: List[SingleTokenRunResults]
    hypothesis_results: Dict[str, TokenHypothesisResult]
    aggregate_stats: Dict[str, Any]
    scenario_results: Dict[str, Dict[str, Any]]
    stress_test_results: Optional[Dict[str, Any]]
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
            "scenario_results": self.scenario_results,
            "stress_test_results": self.stress_test_results,
            "execution_time_seconds": self.execution_time_seconds,
            "timestamp": self.timestamp,
            "num_runs": len(self.run_results),
        }

    def summary(self) -> str:
        """Generate summary string."""
        passed = sum(1 for r in self.hypothesis_results.values() if r.passed)
        total = len(self.hypothesis_results)

        lines = [
            "Token Economics Experiment Results",
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


class TokenEconomicsExperiment:
    """
    Main experiment runner for Domain 4 - Token Economics.

    Orchestrates:
    1. Token supply tracking and stability analysis
    2. Mint/burn dynamics and equilibrium testing
    3. Velocity calculation and Fisher equation validation
    4. Peg stability testing for 1:1 kWh redemption
    5. Inflation monitoring
    6. Stress testing (coordinated redemptions, mint attacks)
    7. Hypothesis testing
    8. Result aggregation and reporting
    """

    def __init__(self, config: Optional[TokenExperimentConfig] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration (uses defaults if None)
        """
        self.config = config or TokenExperimentConfig()
        self.hypothesis_tester = TokenHypothesisTester(
            alpha=self.config.alpha,
            bootstrap_iterations=self.config.bootstrap_iterations,
        )

        self._rng = np.random.default_rng(self.config.seed)

    def run(self, progress_callback=None) -> TokenExperimentResults:
        """
        Execute the full experiment.

        Args:
            progress_callback: Optional callback(run_number, total_runs)

        Returns:
            TokenExperimentResults with all metrics and hypothesis tests
        """
        start_time = time.time()
        logger.info(f"Starting token economics experiment with {self.config.num_runs} runs")

        run_results: List[SingleTokenRunResults] = []

        # Aggregated data for hypothesis testing
        all_cv_values = []
        all_rate_differences = []
        all_velocity_errors = []
        all_peg_deviations = []
        all_inflation_rates = []

        # Components for final hypothesis testing
        combined_supply_tracker = TokenSupplyTracker(
            initial_supply=self.config.initial_supply,
            snapshot_interval_hours=self.config.snapshot_interval_hours,
        )
        combined_mint_burn_analyzer = MintBurnAnalyzer()
        combined_velocity_calculator = VelocityCalculator()
        combined_peg_tester = PegStabilityTester(target_rate=1.0)
        combined_inflation_monitor = InflationMonitor(
            initial_supply=self.config.initial_supply,
            inflation_threshold=self.config.inflation_threshold,
        )

        for run_idx in range(self.config.num_runs):
            if progress_callback:
                progress_callback(run_idx + 1, self.config.num_runs)

            seed = self.config.seed + run_idx if self.config.seed else None
            run_result = self._run_single_iteration(seed)
            run_results.append(run_result)

            # Collect aggregate data
            all_cv_values.append(run_result.supply_cv)
            all_rate_differences.append(run_result.rate_difference)
            all_velocity_errors.append(run_result.velocity_error)
            all_peg_deviations.append(run_result.peg_deviation)
            all_inflation_rates.append(run_result.mean_annual_inflation)

            # Add to combined components
            for snapshot in run_result.supply_snapshots:
                combined_supply_tracker.record_snapshot(snapshot)

            for event in run_result.mint_burn_events:
                combined_mint_burn_analyzer.add_event(event)

            for measurement in run_result.velocity_measurements:
                combined_velocity_calculator.measurements.append(measurement)

            for event in run_result.redemption_events:
                combined_peg_tester.add_redemption(event)

            for measurement in run_result.inflation_measurements:
                combined_inflation_monitor.measurements.append(measurement)

            if (run_idx + 1) % 5 == 0:
                logger.debug(f"Completed run {run_idx + 1}/{self.config.num_runs}")

        # Run scenario analysis
        logger.info("Running scenario analysis...")
        scenario_results = self._run_scenario_analysis()

        # Run stress tests if enabled
        stress_test_results = None
        if self.config.run_stress_tests:
            logger.info("Running stress tests...")
            stress_test_results = self._run_stress_tests()

        # Run hypothesis tests using combined components
        logger.info("Running hypothesis tests...")
        hypothesis_results = self.hypothesis_tester.run_all_tests(
            supply_tracker=combined_supply_tracker,
            mint_burn_analyzer=combined_mint_burn_analyzer,
            velocity_calculator=combined_velocity_calculator,
            peg_tester=combined_peg_tester,
            inflation_monitor=combined_inflation_monitor,
        )

        # Compute aggregate statistics
        aggregate_stats = self._compute_aggregate_stats(
            run_results,
            all_cv_values,
            all_rate_differences,
            all_velocity_errors,
            all_peg_deviations,
            all_inflation_rates,
        )

        execution_time = time.time() - start_time
        logger.info(f"Experiment completed in {execution_time:.2f}s")

        results = TokenExperimentResults(
            config=self.config,
            run_results=run_results,
            hypothesis_results=hypothesis_results,
            aggregate_stats=aggregate_stats,
            scenario_results=scenario_results,
            stress_test_results=stress_test_results,
            execution_time_seconds=execution_time,
        )

        return results

    def _run_single_iteration(self, seed: Optional[int] = None) -> SingleTokenRunResults:
        """
        Run a single experiment iteration.

        Args:
            seed: Random seed for this iteration

        Returns:
            SingleTokenRunResults with all metrics
        """
        # 1. Simulate token supply
        supply_tracker = simulate_token_supply(
            initial_supply=self.config.initial_supply,
            duration_days=self.config.simulation_duration_days,
            snapshot_interval_hours=self.config.snapshot_interval_hours,
            daily_mint_mean=self.config.daily_mint_mean,
            daily_burn_mean=self.config.daily_burn_mean,
            volatility=self.config.mint_burn_volatility,
            seed=seed,
        )

        stability_result = supply_tracker.calculate_rolling_stability(
            window_days=30,
            cv_threshold=self.config.supply_cv_threshold,
        )

        # 2. Simulate mint/burn events
        mint_burn_analyzer = simulate_mint_burn_events(
            duration_days=self.config.simulation_duration_days,
            daily_events_mean=100,
            mint_burn_ratio=self.config.daily_mint_mean / max(self.config.daily_burn_mean, 1),
            event_size_mean=10.0,
            event_size_std=5.0,
            num_agents=self.config.num_agents,
            seed=seed,
        )

        equilibrium_result = mint_burn_analyzer.test_equilibrium(
            tolerance=self.config.mint_burn_tolerance,
            alpha=self.config.alpha,
        )

        # 3. Simulate velocity data
        velocity_calculator = simulate_velocity_data(
            num_periods=self.config.velocity_periods,
            period_days=self.config.velocity_period_days,
            base_supply=self.config.initial_supply,
            base_volume=self.config.base_transaction_volume,
            base_price=self.config.base_price_per_kwh,
            volume_volatility=0.2,
            price_volatility=0.1,
            fisher_noise=0.1,
            seed=seed,
        )

        velocity_result = velocity_calculator.test_fisher_equation(
            tolerance=self.config.velocity_tolerance,
            alpha=self.config.alpha,
        )

        # 4. Simulate redemptions
        peg_tester = simulate_redemptions(
            num_redemptions=self.config.num_redemptions,
            duration_days=self.config.simulation_duration_days,
            target_rate=1.0,
            rate_std=self.config.redemption_rate_std,
            mean_redemption_size=self.config.mean_redemption_size,
            num_agents=self.config.num_agents,
            seed=seed,
        )

        peg_result = peg_tester.test_peg_accuracy(
            tolerance=self.config.peg_tolerance,
            alpha=self.config.alpha,
        )

        # 5. Simulate inflation data
        inflation_monitor = simulate_inflation_data(
            initial_supply=self.config.initial_supply,
            duration_days=self.config.simulation_duration_days,
            daily_mint_rate=self.config.daily_mint_rate,
            daily_burn_rate=self.config.daily_burn_rate,
            volatility=0.5,
            snapshot_interval_hours=24.0,
            seed=seed,
        )

        inflation_result = inflation_monitor.test_inflation(
            threshold=self.config.inflation_threshold,
            alpha=self.config.alpha,
        )

        return SingleTokenRunResults(
            supply_snapshots=supply_tracker.snapshots,
            supply_cv=stability_result.mean_cv,
            supply_cv_max=stability_result.max_cv,
            mint_burn_events=mint_burn_analyzer.events,
            daily_mint_burn_stats=mint_burn_analyzer.calculate_daily_rates(),
            mint_burn_equilibrium=equilibrium_result.is_equilibrium,
            rate_difference=equilibrium_result.rate_difference,
            velocity_measurements=velocity_calculator.measurements,
            velocity_error=velocity_result.mean_absolute_error,
            velocity_correlation=velocity_result.correlation,
            redemption_events=peg_tester.redemptions,
            peg_mean_rate=peg_result.mean_rate,
            peg_deviation=peg_result.deviation_from_target,
            inflation_measurements=inflation_monitor.measurements,
            mean_annual_inflation=inflation_result.mean_annual_inflation,
            max_inflation=inflation_result.max_inflation,
        )

    def _run_scenario_analysis(self) -> Dict[str, Dict[str, Any]]:
        """
        Run analysis across different economic scenarios.

        Returns:
            Dictionary mapping scenario name to results
        """
        results = {}
        seed = self.config.seed

        # Supply scenarios
        supply_scenarios = simulate_supply_scenarios(
            initial_supply=self.config.initial_supply,
            duration_days=30,
            seed=seed,
        )

        for name, tracker in supply_scenarios.items():
            stability = tracker.calculate_rolling_stability(window_days=30)
            results[f"supply_{name}"] = {
                "mean_cv": stability.mean_cv,
                "max_cv": stability.max_cv,
                "passes_threshold": stability.mean_cv < self.config.supply_cv_threshold,
            }

        # Mint/burn equilibrium scenarios
        equilibrium_scenarios = simulate_equilibrium_scenarios(
            duration_days=30,
            seed=seed,
        )

        for name, analyzer in equilibrium_scenarios.items():
            eq_result = analyzer.test_equilibrium(tolerance=self.config.mint_burn_tolerance)
            results[f"equilibrium_{name}"] = {
                "is_equilibrium": eq_result.is_equilibrium,
                "rate_difference": eq_result.rate_difference,
                "mean_mint_rate": eq_result.mean_mint_rate,
                "mean_burn_rate": eq_result.mean_burn_rate,
            }

        # Velocity scenarios
        velocity_scenarios = simulate_velocity_scenarios(
            num_periods=30,
            seed=seed,
        )

        for name, calculator in velocity_scenarios.items():
            v_result = calculator.test_fisher_equation(tolerance=self.config.velocity_tolerance)
            results[f"velocity_{name}"] = {
                "is_valid": v_result.is_valid,
                "mean_absolute_error": v_result.mean_absolute_error,
                "correlation": v_result.correlation,
                "r_squared": v_result.r_squared,
            }

        # Peg stability scenarios
        peg_scenarios = simulate_peg_scenarios(
            num_redemptions=500,
            duration_days=30,
            seed=seed,
        )

        for name, tester in peg_scenarios.items():
            peg_result = tester.test_peg_accuracy(tolerance=self.config.peg_tolerance)
            results[f"peg_{name}"] = {
                "is_stable": peg_result.is_stable,
                "mean_rate": peg_result.mean_rate,
                "deviation_from_target": peg_result.deviation_from_target,
                "std_rate": peg_result.std_rate,
            }

        # Inflation scenarios
        inflation_scenarios = simulate_inflation_scenarios(
            duration_days=365,
            seed=seed,
        )

        for name, monitor in inflation_scenarios.items():
            inf_result = monitor.test_inflation(threshold=self.config.inflation_threshold)
            results[f"inflation_{name}"] = {
                "is_acceptable": inf_result.is_acceptable,
                "mean_annual_inflation": inf_result.mean_annual_inflation,
                "max_inflation": inf_result.max_inflation,
            }

        return results

    def _run_stress_tests(self) -> Dict[str, Any]:
        """
        Run stress tests for extreme scenarios.

        Returns:
            Dictionary of stress test results
        """
        results = {}
        seed = self.config.seed

        # 1. Coordinated redemption stress test
        logger.info("Running coordinated redemption stress test...")
        stress_peg = simulate_stress_redemptions(
            total_supply=self.config.initial_supply,
            redemption_fraction=self.config.stress_redemption_fraction,
            duration_hours=self.config.stress_duration_hours,
            target_rate=1.0,
            stress_rate_deviation=0.02,
            seed=seed,
        )

        peg_result = stress_peg.test_peg_accuracy(tolerance=self.config.peg_tolerance)
        peg_breaks = stress_peg.detect_peg_breaks(deviation_threshold=0.05)

        results["coordinated_redemption"] = {
            "description": f"20% supply redeemed in {self.config.stress_duration_hours} hour(s)",
            "peg_maintained": peg_result.is_stable,
            "mean_rate": peg_result.mean_rate,
            "deviation_from_target": peg_result.deviation_from_target,
            "peg_breaks_count": len(peg_breaks),
            "total_redemptions": len(stress_peg.redemptions),
        }

        # 2. Mint attack simulation
        logger.info("Running mint attack simulation...")
        attack_monitor = simulate_mint_attack(
            initial_supply=self.config.initial_supply,
            attack_multiplier=self.config.mint_attack_multiplier,
            attack_duration_days=7,
            total_duration_days=30,
            seed=seed,
        )

        attack_inflation = attack_monitor.test_inflation(threshold=self.config.inflation_threshold)
        hyperinflation_periods = attack_monitor.detect_hyperinflation_periods()

        results["mint_attack"] = {
            "description": f"{self.config.mint_attack_multiplier}x normal minting for 7 days",
            "inflation_contained": attack_inflation.is_acceptable,
            "mean_annual_inflation": attack_inflation.mean_annual_inflation,
            "max_inflation": attack_inflation.max_inflation,
            "hyperinflation_periods": len(hyperinflation_periods),
        }

        # 3. High volume stress test (10x normal)
        logger.info("Running high volume stress test...")
        high_volume_mb = simulate_mint_burn_events(
            duration_days=30,
            daily_events_mean=1000,  # 10x normal
            mint_burn_ratio=1.0,
            event_size_mean=10.0,
            event_size_std=5.0,
            num_agents=self.config.num_agents,
            seed=seed,
        )

        hv_equilibrium = high_volume_mb.test_equilibrium(tolerance=self.config.mint_burn_tolerance)

        results["high_volume"] = {
            "description": "10x normal transaction volume",
            "equilibrium_maintained": hv_equilibrium.is_equilibrium,
            "rate_difference": hv_equilibrium.rate_difference,
            "total_events": len(high_volume_mb.events),
        }

        return results

    def _compute_aggregate_stats(
        self,
        run_results: List[SingleTokenRunResults],
        all_cv_values: List[float],
        all_rate_differences: List[float],
        all_velocity_errors: List[float],
        all_peg_deviations: List[float],
        all_inflation_rates: List[float],
    ) -> Dict[str, Any]:
        """
        Compute aggregate statistics across all runs.

        Returns:
            Dictionary of aggregate statistics
        """
        return {
            # Supply stability
            "mean_supply_cv": float(np.mean(all_cv_values)),
            "std_supply_cv": float(np.std(all_cv_values)),
            "max_supply_cv": float(np.max(all_cv_values)),
            "cv_below_threshold_rate": float(np.mean([cv < self.config.supply_cv_threshold for cv in all_cv_values])),

            # Mint/burn equilibrium
            "mean_rate_difference": float(np.mean(all_rate_differences)),
            "std_rate_difference": float(np.std(all_rate_differences)),
            "equilibrium_rate": float(np.mean([r.mint_burn_equilibrium for r in run_results])),

            # Velocity prediction
            "mean_velocity_error": float(np.mean(all_velocity_errors)),
            "std_velocity_error": float(np.std(all_velocity_errors)),
            "velocity_below_threshold_rate": float(np.mean([e < self.config.velocity_tolerance for e in all_velocity_errors])),

            # Peg stability
            "mean_peg_deviation": float(np.mean(all_peg_deviations)),
            "std_peg_deviation": float(np.std(all_peg_deviations)),
            "peg_within_tolerance_rate": float(np.mean([d < self.config.peg_tolerance for d in all_peg_deviations])),

            # Inflation
            "mean_annual_inflation": float(np.mean(all_inflation_rates)),
            "std_annual_inflation": float(np.std(all_inflation_rates)),
            "max_annual_inflation": float(np.max(all_inflation_rates)),
            "inflation_below_threshold_rate": float(np.mean([r < self.config.inflation_threshold for r in all_inflation_rates])),
        }

    def save_results(self, results: TokenExperimentResults) -> Path:
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
        results_file = output_dir / f"token_experiment_results_{timestamp}.json"

        with open(results_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2, default=str)

        logger.info(f"Results saved to {results_file}")

        # Generate plots if enabled
        if self.config.generate_plots:
            self._generate_plots(results, output_dir)

        return results_file

    def _generate_plots(self, results: TokenExperimentResults, output_dir: Path):
        """Generate visualization plots."""
        visualizer = TokenVisualization(output_dir=str(output_dir))

        # Use data from first run for visualizations
        if results.run_results:
            first_run = results.run_results[0]

            if first_run.supply_snapshots:
                visualizer.plot_supply_over_time(first_run.supply_snapshots)

            if first_run.daily_mint_burn_stats:
                visualizer.plot_mint_burn_volumes(first_run.daily_mint_burn_stats)

            if first_run.velocity_measurements:
                visualizer.plot_velocity_comparison(first_run.velocity_measurements)

            if first_run.redemption_events:
                visualizer.plot_redemption_distribution(first_run.redemption_events)

            if first_run.inflation_measurements:
                visualizer.plot_inflation_over_time(first_run.inflation_measurements)

        # Plot hypothesis summary
        if results.hypothesis_results:
            visualizer.plot_hypothesis_summary(results.hypothesis_results)

        logger.info(f"Plots generated in {output_dir}")

    @staticmethod
    def load_results(path: Path) -> dict:
        """
        Load experiment results from disk.

        Args:
            path: Path to results file

        Returns:
            Dictionary of results
        """
        with open(path, "r") as f:
            return json.load(f)


def run_quick_token_test(seed: Optional[int] = None) -> TokenExperimentResults:
    """
    Run a quick token economics test with minimal configuration.

    Args:
        seed: Random seed

    Returns:
        TokenExperimentResults
    """
    config = TokenExperimentConfig(
        simulation_duration_days=30,
        num_runs=3,
        num_redemptions=500,
        velocity_periods=15,
        bootstrap_iterations=1000,
        run_stress_tests=False,
        generate_plots=False,
        seed=seed,
    )

    experiment = TokenEconomicsExperiment(config)
    return experiment.run()


def run_full_token_experiment(
    seed: Optional[int] = None,
    output_dir: str = "results/domain4_token",
) -> TokenExperimentResults:
    """
    Run a full token economics experiment with comprehensive configuration.

    Args:
        seed: Random seed
        output_dir: Output directory for results

    Returns:
        TokenExperimentResults
    """
    config = TokenExperimentConfig(
        simulation_duration_days=90,
        num_runs=10,
        num_redemptions=2000,
        velocity_periods=30,
        bootstrap_iterations=10000,
        run_stress_tests=True,
        generate_plots=True,
        output_dir=output_dir,
        seed=seed,
    )

    experiment = TokenEconomicsExperiment(config)
    results = experiment.run()

    # Save results
    experiment.save_results(results)

    return results


if __name__ == "__main__":
    # Run quick test when executed directly
    logging.basicConfig(level=logging.INFO)
    results = run_quick_token_test(seed=42)
    print(results.summary())
