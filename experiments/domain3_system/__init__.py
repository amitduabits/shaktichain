"""
Domain 3 - System Performance Experiments for SHAKTI-CHAIN.

This module implements hypothesis tests for validating the system
performance of the V2G marketplace:

Hypotheses:
- H3.1: TPS >= 10,000 transactions per second
- H3.2: P95 latency < 100ms
- H3.3: 99.9% settlement finality within 30 seconds
- H3.4: O(n log n) or better scaling
- H3.5: Mean gas cost < 1 INR per transaction
- H3.6: System availability >= 99.9%
"""

from .load_generator import (
    Transaction,
    LoadProfile,
    LoadGenerator,
    SyntheticLoadGenerator,
)

from .throughput_measurer import (
    ThroughputMeasurement,
    ThroughputStatistics,
    ThroughputMeasurer,
    ThroughputBenchmarker,
)

from .latency_profiler import (
    LatencyStatistics,
    LatencyDistributionFit,
    LatencyProfiler,
    bootstrap_percentile_ci,
)

from .scalability_analyzer import (
    ModelFitResult,
    ScalabilityAnalysisResult,
    ScalabilityAnalyzer,
)

from .gas_cost_tracker import (
    GasEstimate,
    GasCostStatistics,
    GasCostTracker,
    simulate_gas_costs,
    GAS_ESTIMATES,
)

from .availability_monitor import (
    DowntimeEvent,
    AvailabilityMetrics,
    AvailabilityMonitor,
    SettlementFinalityTracker,
    simulate_availability_data,
    simulate_settlement_finality,
)

from .hypothesis_tests import (
    SystemHypothesisResult,
    SystemHypothesisTester,
)

from .visualization import SystemVisualizer

from .experiments import (
    SystemExperimentConfig,
    SingleRunResults,
    SystemExperimentResults,
    SystemPerformanceExperiment,
    run_quick_system_test,
    run_full_system_experiment,
)

__all__ = [
    # Load Generator
    "Transaction",
    "LoadProfile",
    "LoadGenerator",
    "SyntheticLoadGenerator",
    # Throughput
    "ThroughputMeasurement",
    "ThroughputStatistics",
    "ThroughputMeasurer",
    "ThroughputBenchmarker",
    # Latency
    "LatencyStatistics",
    "LatencyDistributionFit",
    "LatencyProfiler",
    "bootstrap_percentile_ci",
    # Scalability
    "ModelFitResult",
    "ScalabilityAnalysisResult",
    "ScalabilityAnalyzer",
    # Gas Cost
    "GasEstimate",
    "GasCostStatistics",
    "GasCostTracker",
    "simulate_gas_costs",
    "GAS_ESTIMATES",
    # Availability
    "DowntimeEvent",
    "AvailabilityMetrics",
    "AvailabilityMonitor",
    "SettlementFinalityTracker",
    "simulate_availability_data",
    "simulate_settlement_finality",
    # Hypothesis Tests
    "SystemHypothesisResult",
    "SystemHypothesisTester",
    # Visualization
    "SystemVisualizer",
    # Experiments
    "SystemExperimentConfig",
    "SingleRunResults",
    "SystemExperimentResults",
    "SystemPerformanceExperiment",
    "run_quick_system_test",
    "run_full_system_experiment",
]
