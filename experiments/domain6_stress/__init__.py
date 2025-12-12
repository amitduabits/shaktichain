"""
Domain 6: Stress Testing & Robustness Experiments for SHAKTI-CHAIN.

This module implements hypothesis tests for stress testing:
- H6.1: Peak Demand Performance (Efficiency >= 90% at 2.5x demand)
- H6.2: Supply Shock Recovery (Recovery within 10 rounds)
- H6.3: High Volatility Stability (No failure at 3σ variance)
- H6.4: Graceful Degradation (TPS >= 50% at 2x load)
- H6.5: Network Partition Tolerance (No inconsistency after heal)
- H6.6: Byzantine Fault Tolerance (Correct operation with 30% Byzantine)
"""

from .peak_demand_simulator import (
    PeakDemandSimulator,
    PeakDemandResult,
    PeakDemandTestResult,
    DemandScenario,
    DELHI_SUMMER_PEAK,
    MUMBAI_MONSOON,
    CHENNAI_HEATWAVE,
    BANGALORE_TECH_PEAK,
    KOLKATA_EVENING_PEAK,
    INDIA_PEAK_SCENARIOS,
    simulate_peak_demand_test,
)

from .supply_shock_simulator import (
    SupplyShockSimulator,
    SupplyShockResult,
    RecoveryTestResult,
    SupplyShockEvent,
    ShockType,
    GRID_OUTAGE,
    LOCALIZED_FAILURE,
    GRADUAL_DEGRADATION,
    CASCADING_FAILURE,
    SUPPLY_SHOCK_SCENARIOS,
    simulate_supply_shock_test,
)

from .volatility_injector import (
    VolatilityInjector,
    VolatilityTestResult,
    StabilityTestResult,
    VolatilityScenario,
    VolatilityPattern,
    HIGH_VARIANCE_GAUSSIAN,
    EXTREME_VARIANCE,
    HEAVY_TAILED_VOLATILITY,
    VOLATILITY_CLUSTERING,
    JUMP_VOLATILITY,
    VOLATILITY_SCENARIOS,
    simulate_volatility_test,
)

from .overload_tester import (
    OverloadTester,
    OverloadResult,
    DegradationTestResult,
    LoadScenario,
    LoadPattern,
    DOUBLE_LOAD,
    TRIPLE_LOAD,
    GRADUAL_OVERLOAD,
    SPIKE_LOAD,
    OVERLOAD_SCENARIOS,
    simulate_overload_test,
)

from .partition_simulator import (
    NetworkPartitionSimulator,
    PartitionResult,
    PartitionToleranceResult,
    PartitionScenario,
    PartitionType,
    SYMMETRIC_SPLIT,
    ASYMMETRIC_SPLIT,
    MINORITY_ISOLATED,
    LEADER_ISOLATED,
    PARTITION_SCENARIOS,
    simulate_partition_test,
)

from .byzantine_tester import (
    ByzantineTester,
    ByzantineTestResult,
    ByzantineToleranceResult,
    ByzantineScenario,
    ByzantineStrategy,
    LOW_BYZANTINE,
    MEDIUM_BYZANTINE,
    HIGH_BYZANTINE,
    THRESHOLD_BYZANTINE,
    OVER_THRESHOLD,
    BYZANTINE_SCENARIOS,
    simulate_byzantine_test,
)

from .recovery_analyzer import (
    RecoveryAnalyzer,
    RecoveryMetrics,
    RecoveryAnalysisResult,
    RecoveryType,
    analyze_recovery_from_series,
    calculate_resilience_score,
)

from .hypothesis_tests import (
    StressHypothesisTester,
    StressHypothesisResult,
)

from .visualization import (
    StressVisualization,
    create_visualization_report,
)

from .experiments import (
    StressExperimentConfig,
    StressExperimentResults,
    SingleStressRunResults,
    StressTestingExperiment,
    run_quick_stress_test,
    run_full_stress_experiment,
)

__all__ = [
    # Peak demand
    "PeakDemandSimulator",
    "PeakDemandResult",
    "PeakDemandTestResult",
    "DemandScenario",
    "DELHI_SUMMER_PEAK",
    "MUMBAI_MONSOON",
    "CHENNAI_HEATWAVE",
    "BANGALORE_TECH_PEAK",
    "KOLKATA_EVENING_PEAK",
    "INDIA_PEAK_SCENARIOS",
    "simulate_peak_demand_test",

    # Supply shock
    "SupplyShockSimulator",
    "SupplyShockResult",
    "RecoveryTestResult",
    "SupplyShockEvent",
    "ShockType",
    "GRID_OUTAGE",
    "LOCALIZED_FAILURE",
    "GRADUAL_DEGRADATION",
    "CASCADING_FAILURE",
    "SUPPLY_SHOCK_SCENARIOS",
    "simulate_supply_shock_test",

    # Volatility
    "VolatilityInjector",
    "VolatilityTestResult",
    "StabilityTestResult",
    "VolatilityScenario",
    "VolatilityPattern",
    "HIGH_VARIANCE_GAUSSIAN",
    "EXTREME_VARIANCE",
    "HEAVY_TAILED_VOLATILITY",
    "VOLATILITY_CLUSTERING",
    "JUMP_VOLATILITY",
    "VOLATILITY_SCENARIOS",
    "simulate_volatility_test",

    # Overload
    "OverloadTester",
    "OverloadResult",
    "DegradationTestResult",
    "LoadScenario",
    "LoadPattern",
    "DOUBLE_LOAD",
    "TRIPLE_LOAD",
    "GRADUAL_OVERLOAD",
    "SPIKE_LOAD",
    "OVERLOAD_SCENARIOS",
    "simulate_overload_test",

    # Partition
    "NetworkPartitionSimulator",
    "PartitionResult",
    "PartitionToleranceResult",
    "PartitionScenario",
    "PartitionType",
    "SYMMETRIC_SPLIT",
    "ASYMMETRIC_SPLIT",
    "MINORITY_ISOLATED",
    "LEADER_ISOLATED",
    "PARTITION_SCENARIOS",
    "simulate_partition_test",

    # Byzantine
    "ByzantineTester",
    "ByzantineTestResult",
    "ByzantineToleranceResult",
    "ByzantineScenario",
    "ByzantineStrategy",
    "LOW_BYZANTINE",
    "MEDIUM_BYZANTINE",
    "HIGH_BYZANTINE",
    "THRESHOLD_BYZANTINE",
    "OVER_THRESHOLD",
    "BYZANTINE_SCENARIOS",
    "simulate_byzantine_test",

    # Recovery
    "RecoveryAnalyzer",
    "RecoveryMetrics",
    "RecoveryAnalysisResult",
    "RecoveryType",
    "analyze_recovery_from_series",
    "calculate_resilience_score",

    # Hypothesis tests
    "StressHypothesisTester",
    "StressHypothesisResult",

    # Visualization
    "StressVisualization",
    "create_visualization_report",

    # Experiments
    "StressExperimentConfig",
    "StressExperimentResults",
    "SingleStressRunResults",
    "StressTestingExperiment",
    "run_quick_stress_test",
    "run_full_stress_experiment",
]
