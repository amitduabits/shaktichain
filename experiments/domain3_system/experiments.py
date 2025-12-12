"""
System Performance Experiment Runner (Domain 3).

Main orchestration module for running system performance experiments
and generating comprehensive validation results for SHAKTI-CHAIN.

Validates hypotheses:
- H3.1: TPS >= 10,000 transactions per second
- H3.2: P95 latency < 100ms
- H3.3: 99.9% settlement finality within 30 seconds
- H3.4: O(n log n) or better scaling
- H3.5: Mean gas cost < 1 INR per transaction
- H3.6: System availability >= 99.9%
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

from .load_generator import (
    LoadGenerator,
    SyntheticLoadGenerator,
    LoadProfile,
    Transaction,
)
from .throughput_measurer import (
    ThroughputMeasurer,
    ThroughputBenchmarker,
    ThroughputStatistics,
    ThroughputMeasurement,
)
from .latency_profiler import (
    LatencyProfiler,
    LatencyStatistics,
    bootstrap_percentile_ci,
)
from .scalability_analyzer import (
    ScalabilityAnalyzer,
    ScalabilityAnalysisResult,
    ModelFitResult,
)
from .gas_cost_tracker import (
    GasCostTracker,
    GasCostStatistics,
    GasEstimate,
    simulate_gas_costs,
)
from .availability_monitor import (
    AvailabilityMonitor,
    AvailabilityMetrics,
    SettlementFinalityTracker,
    simulate_availability_data,
    simulate_settlement_finality,
)
from .hypothesis_tests import (
    SystemHypothesisTester,
    SystemHypothesisResult,
)
from .visualization import SystemVisualizer

logger = logging.getLogger(__name__)


@dataclass
class SystemExperimentConfig:
    """Configuration for system performance experiments."""

    # Load test configuration
    load_levels: List[int] = field(
        default_factory=lambda: [100, 500, 1000, 5000, 10000]
    )
    duration_per_level_seconds: float = 60.0
    warmup_seconds: float = 10.0
    cooldown_seconds: float = 5.0

    # Transaction configuration
    tx_type_distribution: Dict[str, float] = field(
        default_factory=lambda: {
            "bid_submit": 0.30,
            "ask_submit": 0.30,
            "order_cancel": 0.10,
            "trade_settlement": 0.20,
            "update_balance": 0.10,
        }
    )

    # Latency configuration
    base_latency_ms: float = 10.0
    latency_scale_factor: float = 0.5  # How much latency increases with load

    # Gas cost configuration
    gas_price_mean_gwei: float = 30.0
    gas_price_std_gwei: float = 10.0
    fetch_live_rate: bool = False  # Use fallback rate by default for testing
    matic_inr_fallback: float = 80.0

    # Availability configuration
    target_availability: float = 0.999
    mtbf_hours: float = 720.0  # Mean time between failures (30 days)
    mttr_hours: float = 0.5  # Mean time to repair (30 minutes)

    # Settlement finality
    target_finality_rate: float = 0.999
    finality_timeout_seconds: float = 30.0

    # Simulation parameters
    num_runs: int = 10
    transactions_per_run: int = 10000
    seed: Optional[int] = None

    # Statistical parameters
    alpha: float = 0.05
    bootstrap_iterations: int = 10000
    correction_method: str = "holm"

    # Thresholds from requirements
    tps_threshold: float = 10000.0
    latency_p95_threshold_ms: float = 100.0
    finality_rate_threshold: float = 0.999
    gas_cost_threshold_inr: float = 1.0
    availability_threshold: float = 0.999

    # Output configuration
    output_dir: str = "results/domain3"
    save_raw_data: bool = True
    generate_plots: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "load_levels": self.load_levels,
            "duration_per_level_seconds": self.duration_per_level_seconds,
            "warmup_seconds": self.warmup_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "tx_type_distribution": self.tx_type_distribution,
            "base_latency_ms": self.base_latency_ms,
            "latency_scale_factor": self.latency_scale_factor,
            "gas_price_mean_gwei": self.gas_price_mean_gwei,
            "gas_price_std_gwei": self.gas_price_std_gwei,
            "fetch_live_rate": self.fetch_live_rate,
            "matic_inr_fallback": self.matic_inr_fallback,
            "target_availability": self.target_availability,
            "mtbf_hours": self.mtbf_hours,
            "mttr_hours": self.mttr_hours,
            "target_finality_rate": self.target_finality_rate,
            "finality_timeout_seconds": self.finality_timeout_seconds,
            "num_runs": self.num_runs,
            "transactions_per_run": self.transactions_per_run,
            "seed": self.seed,
            "alpha": self.alpha,
            "bootstrap_iterations": self.bootstrap_iterations,
            "correction_method": self.correction_method,
            "tps_threshold": self.tps_threshold,
            "latency_p95_threshold_ms": self.latency_p95_threshold_ms,
            "finality_rate_threshold": self.finality_rate_threshold,
            "gas_cost_threshold_inr": self.gas_cost_threshold_inr,
            "availability_threshold": self.availability_threshold,
            "output_dir": self.output_dir,
            "save_raw_data": self.save_raw_data,
            "generate_plots": self.generate_plots,
        }


@dataclass
class SingleRunResults:
    """Results from a single simulation run."""

    # Throughput data
    throughput_stats: ThroughputStatistics
    tps_samples: np.ndarray

    # Latency data
    latency_stats: LatencyStatistics
    latency_samples: np.ndarray

    # Scalability data (load level -> TPS)
    scalability_data: List[Tuple[int, float]]

    # Gas cost data
    gas_cost_stats: GasCostStatistics
    gas_cost_samples: np.ndarray

    # Availability data
    availability_stats: AvailabilityMetrics
    uptime_rate: float

    # Settlement finality
    finality_rate: float
    finality_times: np.ndarray

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "throughput_stats": self.throughput_stats.to_dict(),
            "tps_mean": float(np.mean(self.tps_samples)),
            "tps_max": float(np.max(self.tps_samples)),
            "latency_stats": self.latency_stats.to_dict(),
            "latency_p95": float(np.percentile(self.latency_samples, 95)),
            "latency_p99": float(np.percentile(self.latency_samples, 99)),
            "scalability_points": len(self.scalability_data),
            "gas_cost_stats": self.gas_cost_stats.to_dict(),
            "availability_stats": self.availability_stats.to_dict(),
            "uptime_rate": self.uptime_rate,
            "finality_rate": self.finality_rate,
            "mean_finality_time": float(np.mean(self.finality_times)),
        }


@dataclass
class SystemExperimentResults:
    """
    Complete results from system performance experiment.

    Contains all run results, hypothesis tests, and aggregate statistics.
    """

    config: SystemExperimentConfig
    run_results: List[SingleRunResults]
    hypothesis_results: Dict[str, SystemHypothesisResult]
    aggregate_stats: Dict[str, Any]
    scalability_result: ScalabilityAnalysisResult
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
            "scalability_result": self.scalability_result.to_dict(),
            "execution_time_seconds": self.execution_time_seconds,
            "timestamp": self.timestamp,
            "num_runs": len(self.run_results),
        }

    def summary(self) -> str:
        """Generate summary string."""
        passed = sum(1 for r in self.hypothesis_results.values() if r.passed)
        total = len(self.hypothesis_results)

        lines = [
            "System Performance Experiment Results",
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
            f"Scalability: Best model = {self.scalability_result.best_model}",
            f"             R^2 = {self.scalability_result.model_fits[self.scalability_result.best_model].r_squared:.4f}",
            "",
            "Hypothesis Results:",
        ])

        for h_id in sorted(self.hypothesis_results.keys()):
            result = self.hypothesis_results[h_id]
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  {h_id}: {status} (p={result.p_value:.4f})")

        return "\n".join(lines)


class SystemPerformanceExperiment:
    """
    Main experiment runner for Domain 3 - System Performance.

    Orchestrates:
    1. Load generation with configurable patterns
    2. Throughput measurement and benchmarking
    3. Latency profiling with percentile analysis
    4. Scalability testing with model fitting
    5. Gas cost tracking with live exchange rates
    6. Availability monitoring
    7. Settlement finality tracking
    8. Hypothesis testing
    9. Result aggregation and reporting
    """

    def __init__(self, config: Optional[SystemExperimentConfig] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration (uses defaults if None)
        """
        self.config = config or SystemExperimentConfig()
        self.hypothesis_tester = SystemHypothesisTester(
            alpha=self.config.alpha,
            bootstrap_iterations=self.config.bootstrap_iterations,
        )

        if self.config.seed is not None:
            np.random.seed(self.config.seed)

        # Initialize components
        self.gas_tracker = GasCostTracker(
            fetch_live_rate=self.config.fetch_live_rate,
            fallback_rate=self.config.matic_inr_fallback,
            default_gas_price_gwei=self.config.gas_price_mean_gwei,
        )

    def run(self, progress_callback=None) -> SystemExperimentResults:
        """
        Execute the full experiment.

        Args:
            progress_callback: Optional callback(run_number, total_runs)

        Returns:
            SystemExperimentResults with all metrics and hypothesis tests
        """
        start_time = time.time()
        logger.info(f"Starting system performance experiment with {self.config.num_runs} runs")

        run_results: List[SingleRunResults] = []

        # Collect aggregate data for hypothesis tests
        all_tps_samples = []
        all_latency_samples = []
        all_gas_costs = []
        all_finality_times = []
        all_uptime_rates = []
        all_finality_rates = []
        all_scalability_data = []

        for run_idx in range(self.config.num_runs):
            if progress_callback:
                progress_callback(run_idx + 1, self.config.num_runs)

            # Run single iteration
            run_result = self._run_single_iteration()
            run_results.append(run_result)

            # Collect for aggregate analysis
            all_tps_samples.extend(run_result.tps_samples.tolist())
            all_latency_samples.extend(run_result.latency_samples.tolist())
            all_gas_costs.extend(run_result.gas_cost_samples.tolist())
            all_finality_times.extend(run_result.finality_times.tolist())
            all_uptime_rates.append(run_result.uptime_rate)
            all_finality_rates.append(run_result.finality_rate)
            all_scalability_data.extend(run_result.scalability_data)

            if (run_idx + 1) % 5 == 0:
                logger.debug(f"Completed run {run_idx + 1}/{self.config.num_runs}")

        # Perform scalability analysis on combined data
        logger.info("Running scalability analysis...")
        scalability_analyzer = ScalabilityAnalyzer()

        # Extract load levels and corresponding TPS
        load_tps_pairs = {}
        for load, tps in all_scalability_data:
            if load not in load_tps_pairs:
                load_tps_pairs[load] = []
            load_tps_pairs[load].append(tps)

        # Use mean TPS per load level (convert to time in ms for scaling analysis)
        load_levels = sorted(load_tps_pairs.keys())
        for load in load_levels:
            mean_tps = np.mean(load_tps_pairs[load])
            # Convert TPS to response time in ms for scaling analysis
            response_time_ms = 1000.0 / max(mean_tps, 1.0) if mean_tps > 0 else 1000.0
            scalability_analyzer.add_measurement(load, response_time_ms)

        scalability_result = scalability_analyzer.test_complexity()

        # Run hypothesis tests
        logger.info("Running hypothesis tests...")
        hypothesis_results = self._run_hypothesis_tests(
            tps_samples=np.array(all_tps_samples),
            latency_samples=np.array(all_latency_samples),
            gas_cost_samples=np.array(all_gas_costs),
            finality_times=np.array(all_finality_times),
            uptime_rates=all_uptime_rates,
            finality_rates=all_finality_rates,
            scalability_result=scalability_result,
        )

        # Compute aggregate statistics
        aggregate_stats = self._compute_aggregate_stats(
            run_results,
            all_tps_samples,
            all_latency_samples,
            all_gas_costs,
            all_finality_times,
            all_uptime_rates,
            all_finality_rates,
        )

        execution_time = time.time() - start_time
        logger.info(f"Experiment completed in {execution_time:.2f}s")

        results = SystemExperimentResults(
            config=self.config,
            run_results=run_results,
            hypothesis_results=hypothesis_results,
            aggregate_stats=aggregate_stats,
            scalability_result=scalability_result,
            execution_time_seconds=execution_time,
        )

        return results

    def _run_single_iteration(self) -> SingleRunResults:
        """
        Run a single experiment iteration.

        Returns:
            SingleRunResults with all metrics
        """
        # Initialize profilers for this run
        throughput_measurer = ThroughputMeasurer()
        latency_profiler = LatencyProfiler()
        availability_monitor = AvailabilityMonitor()
        finality_tracker = SettlementFinalityTracker()

        # Clear gas tracker for this run
        self.gas_tracker.clear()

        # Generate synthetic load
        load_generator = SyntheticLoadGenerator(seed=self.config.seed)

        # Scalability data for this run
        scalability_data = []

        # Generate TPS samples using the synthetic generator
        tps_samples_all = []
        for load_level in self.config.load_levels:
            tps_samples = load_generator.generate_tps_samples(
                target_tps=load_level,
                duration_seconds=int(self.config.duration_per_level_seconds),
            )
            tps_samples_all.extend(tps_samples.tolist())

            # Mean TPS at this load level
            mean_tps = float(np.mean(tps_samples))
            scalability_data.append((load_level, mean_tps))

            # Record throughput samples
            for tps in tps_samples[:10]:  # Sample 10 measurements
                throughput_measurer.record_transaction(tps)

        # Generate latency samples
        n_latency_samples = min(1000, self.config.transactions_per_run)
        latency_samples = load_generator.generate_latency_samples(
            n_samples=n_latency_samples,
            base_latency_ms=self.config.base_latency_ms,
            p99_target_ms=self.config.latency_p95_threshold_ms * 1.5,  # P99 slightly higher
        )
        latency_profiler.record_batch(latency_samples.tolist())

        # Generate gas costs
        gas_costs = load_generator.generate_gas_costs(
            n_transactions=self.config.transactions_per_run // 10,
            gas_price_gwei=self.config.gas_price_mean_gwei,
            matic_inr_rate=self.gas_tracker.matic_inr_rate,
        )
        # Record in gas tracker
        for cost in gas_costs:
            gas_used = int(cost * 1e9 / (self.config.gas_price_mean_gwei * self.gas_tracker.matic_inr_rate))
            tx_type = np.random.choice(list(self.config.tx_type_distribution.keys()))
            self.gas_tracker.record_transaction(tx_type, gas_used, self.config.gas_price_mean_gwei)

        # Simulate availability data
        availability_monitor_sim, downtime_events = simulate_availability_data(
            duration_hours=24,
            target_availability=self.config.target_availability,
            mtbf_hours=self.config.mtbf_hours,
            mttr_minutes=self.config.mttr_hours * 60,  # Convert hours to minutes
        )
        avail_metrics = availability_monitor_sim.calculate_metrics()
        uptime_rate = avail_metrics.availability_pct / 100.0  # Convert from percentage to rate

        # Simulate settlement finality
        finality_times_arr, finality_metrics = simulate_settlement_finality(
            n_settlements=1000,
            target_seconds=self.config.finality_timeout_seconds,
            success_rate=self.config.target_finality_rate,
        )
        finality_rate = finality_metrics.finality_rate

        # Get statistics
        throughput_stats = throughput_measurer.get_statistics()
        latency_stats = latency_profiler.get_statistics()
        gas_cost_stats = self.gas_tracker.get_statistics()
        availability_stats = avail_metrics

        return SingleRunResults(
            throughput_stats=throughput_stats,
            tps_samples=np.array(throughput_measurer.measurements) if throughput_measurer.measurements else np.array([0]),
            latency_stats=latency_stats,
            latency_samples=np.array(latency_profiler._latencies),
            scalability_data=scalability_data,
            gas_cost_stats=gas_cost_stats,
            gas_cost_samples=np.array([t.cost_inr for t in self.gas_tracker.transactions]),
            availability_stats=availability_stats,
            uptime_rate=uptime_rate,
            finality_rate=finality_rate,
            finality_times=finality_times_arr,
        )

    def _run_hypothesis_tests(
        self,
        tps_samples: np.ndarray,
        latency_samples: np.ndarray,
        gas_cost_samples: np.ndarray,
        finality_times: np.ndarray,
        uptime_rates: List[float],
        finality_rates: List[float],
        scalability_result: ScalabilityAnalysisResult,
    ) -> Dict[str, SystemHypothesisResult]:
        """
        Run all system hypothesis tests.

        Returns:
            Dictionary of hypothesis results
        """
        # Create an availability metrics object for hypothesis testing
        mean_uptime = np.mean(uptime_rates) if uptime_rates else 0.999
        total_seconds = 24 * 3600 * len(uptime_rates)  # Approximate monitoring time
        availability_metrics = AvailabilityMetrics(
            availability_pct=mean_uptime * 100,
            uptime_seconds=total_seconds * mean_uptime,
            downtime_seconds=total_seconds * (1 - mean_uptime),
            monitoring_period_seconds=total_seconds,
            num_downtime_events=int((1 - mean_uptime) * len(uptime_rates) * 10),
            mtbf_seconds=self.config.mtbf_hours * 3600,
            mttr_seconds=self.config.mttr_hours * 3600,
            longest_downtime_seconds=self.config.mttr_hours * 3600,
            availability_by_day={},
        )

        return self.hypothesis_tester.run_all_tests(
            tps_samples=tps_samples,
            latency_samples=latency_samples,
            finality_times=finality_times,
            scalability_result=scalability_result,
            gas_costs=gas_cost_samples,
            availability_metrics=availability_metrics,
        )

    def _compute_aggregate_stats(
        self,
        run_results: List[SingleRunResults],
        all_tps_samples: List[float],
        all_latency_samples: List[float],
        all_gas_costs: List[float],
        all_finality_times: List[float],
        all_uptime_rates: List[float],
        all_finality_rates: List[float],
    ) -> Dict[str, Any]:
        """
        Compute aggregate statistics across all runs.

        Returns:
            Dictionary of aggregate statistics
        """
        tps_arr = np.array(all_tps_samples)
        latency_arr = np.array(all_latency_samples)
        gas_arr = np.array(all_gas_costs)
        finality_arr = np.array(all_finality_times)

        return {
            # Throughput
            "tps_mean": float(np.mean(tps_arr)),
            "tps_std": float(np.std(tps_arr)),
            "tps_max": float(np.max(tps_arr)),
            "tps_min": float(np.min(tps_arr)),
            "tps_above_threshold_rate": float(np.mean(tps_arr >= self.config.tps_threshold)),

            # Latency
            "latency_mean_ms": float(np.mean(latency_arr)),
            "latency_std_ms": float(np.std(latency_arr)),
            "latency_p50_ms": float(np.percentile(latency_arr, 50)),
            "latency_p95_ms": float(np.percentile(latency_arr, 95)),
            "latency_p99_ms": float(np.percentile(latency_arr, 99)),
            "latency_p95_below_threshold_rate": float(
                np.percentile(latency_arr, 95) < self.config.latency_p95_threshold_ms
            ),

            # Gas costs
            "gas_cost_mean_inr": float(np.mean(gas_arr)),
            "gas_cost_std_inr": float(np.std(gas_arr)),
            "gas_cost_median_inr": float(np.median(gas_arr)),
            "gas_cost_max_inr": float(np.max(gas_arr)),
            "gas_cost_below_threshold_rate": float(np.mean(gas_arr < self.config.gas_cost_threshold_inr)),

            # Settlement finality
            "finality_mean_seconds": float(np.mean(finality_arr)),
            "finality_std_seconds": float(np.std(finality_arr)),
            "finality_rate_mean": float(np.mean(all_finality_rates)),
            "finality_rate_std": float(np.std(all_finality_rates)),
            "finality_above_threshold_rate": float(
                np.mean(np.array(all_finality_rates) >= self.config.finality_rate_threshold)
            ),

            # Availability
            "uptime_rate_mean": float(np.mean(all_uptime_rates)),
            "uptime_rate_std": float(np.std(all_uptime_rates)),
            "availability_above_threshold_rate": float(
                np.mean(np.array(all_uptime_rates) >= self.config.availability_threshold)
            ),

            # Run counts
            "total_runs": len(run_results),
            "total_tps_samples": len(all_tps_samples),
            "total_latency_samples": len(all_latency_samples),
            "total_gas_transactions": len(all_gas_costs),
        }

    def save_results(
        self,
        results: SystemExperimentResults,
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
            raw_data_file = run_dir / "raw_run_data.json"
            raw_data = [r.to_dict() for r in results.run_results]
            with open(raw_data_file, "w") as f:
                json.dump(raw_data, f, indent=2)

            # Save key arrays for analysis
            all_tps = np.concatenate([r.tps_samples for r in results.run_results])
            all_latency = np.concatenate([r.latency_samples for r in results.run_results])
            all_gas = np.concatenate([r.gas_cost_samples for r in results.run_results])
            all_finality = np.concatenate([r.finality_times for r in results.run_results])

            np.savez(
                run_dir / "system_arrays.npz",
                tps_samples=all_tps,
                latency_samples=all_latency,
                gas_cost_samples=all_gas,
                finality_times=all_finality,
                uptime_rates=np.array([r.uptime_rate for r in results.run_results]),
                finality_rates=np.array([r.finality_rate for r in results.run_results]),
            )

        # Generate plots if configured
        if self.config.generate_plots:
            self._generate_and_save_plots(results, run_dir)

        logger.info(f"Results saved to {run_dir}")
        return run_dir

    def _generate_and_save_plots(
        self,
        results: SystemExperimentResults,
        output_dir: Path,
    ) -> None:
        """Generate and save visualization plots."""
        try:
            visualizer = SystemVisualizer(str(output_dir / "plots"))

            # Aggregate data from all runs
            all_tps = np.concatenate([r.tps_samples for r in results.run_results])
            all_latency = np.concatenate([r.latency_samples for r in results.run_results])
            all_gas = np.concatenate([r.gas_cost_samples for r in results.run_results])
            uptime_rates = [r.uptime_rate for r in results.run_results]

            # Aggregate scalability data
            all_scalability = []
            for r in results.run_results:
                all_scalability.extend(r.scalability_data)

            load_tps_pairs = {}
            for load, tps in all_scalability:
                if load not in load_tps_pairs:
                    load_tps_pairs[load] = []
                load_tps_pairs[load].append(tps)

            load_levels = sorted(load_tps_pairs.keys())
            mean_tps_values = [np.mean(load_tps_pairs[l]) for l in load_levels]

            # Generate all plots
            visualizer.generate_all_plots(
                tps_samples=all_tps,
                latency_samples=all_latency,
                gas_cost_samples=all_gas,
                load_levels=np.array(load_levels),
                tps_by_load=np.array(mean_tps_values),
                uptime_samples=np.array(uptime_rates),
                scalability_result=results.scalability_result,
                hypothesis_results=results.hypothesis_results,
                show=False,
            )

            visualizer.close_all()

        except ImportError:
            logger.warning("matplotlib not available, skipping plot generation")
        except Exception as e:
            logger.error(f"Error generating plots: {e}")

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

        raw_file = results_path / "raw_run_data.json"
        if raw_file.exists():
            with open(raw_file) as f:
                loaded["raw_data"] = json.load(f)

        arrays_file = results_path / "system_arrays.npz"
        if arrays_file.exists():
            loaded["arrays"] = dict(np.load(arrays_file))

        return loaded


def run_quick_system_test() -> SystemExperimentResults:
    """
    Run a quick test with minimal configuration.

    Useful for verifying the implementation works.
    """
    config = SystemExperimentConfig(
        load_levels=[100, 500, 1000],
        num_runs=3,
        transactions_per_run=1000,
        seed=42,
        bootstrap_iterations=1000,
        generate_plots=False,
    )

    experiment = SystemPerformanceExperiment(config)
    results = experiment.run()

    print(results.summary())
    print("\n")
    print(experiment.hypothesis_tester.generate_summary_report(results.hypothesis_results))

    return results


def run_full_system_experiment(
    num_runs: int = 10,
    load_levels: Optional[List[int]] = None,
    seed: Optional[int] = None,
    output_dir: str = "results/domain3",
) -> SystemExperimentResults:
    """
    Run full experiment with default configuration.

    Args:
        num_runs: Number of experiment runs
        load_levels: List of load levels to test
        seed: Random seed for reproducibility
        output_dir: Directory for saving results

    Returns:
        Complete experiment results
    """
    if load_levels is None:
        load_levels = [100, 500, 1000, 5000, 10000]

    config = SystemExperimentConfig(
        num_runs=num_runs,
        load_levels=load_levels,
        seed=seed,
        output_dir=output_dir,
    )

    experiment = SystemPerformanceExperiment(config)

    def progress(current, total):
        if current % 2 == 0 or current == total:
            print(f"Progress: {current}/{total} runs completed")

    results = experiment.run(progress_callback=progress)
    experiment.save_results(results)

    return results


if __name__ == "__main__":
    # Run quick test when executed directly
    logging.basicConfig(level=logging.INFO)
    run_quick_system_test()
