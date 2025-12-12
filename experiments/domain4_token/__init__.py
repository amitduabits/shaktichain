"""
Domain 4: Token Economics Experiments for SHAKTI-CHAIN Validation.

This module provides comprehensive testing and validation of token economics
hypotheses for the SHAKTI-CHAIN decentralized energy trading system.

Hypotheses Tested:
- H4.1: Token Supply Stability (CV < 5% over 30-day periods)
- H4.2: Mint-Burn Equilibrium (< 10% rate difference)
- H4.3: Token Velocity Prediction (Fisher equation, < 20% error)
- H4.4: Token-kWh Peg Stability (rate = 1.0 +/- 1%)
- H4.5: No Hyperinflation (annual < 10%)

Usage:
    # Quick test
    from experiments.domain4_token import run_quick_token_test
    results = run_quick_token_test(seed=42)
    print(results.summary())

    # Full experiment
    from experiments.domain4_token import TokenExperimentConfig, TokenEconomicsExperiment
    config = TokenExperimentConfig(num_runs=10, seed=42)
    experiment = TokenEconomicsExperiment(config)
    results = experiment.run()

    # Command line
    python -m experiments.domain4_token run --num-runs 5
    python -m experiments.domain4_token quick-test
    python -m experiments.domain4_token hypotheses
"""

from .token_supply_tracker import (
    TokenSupplySnapshot,
    SupplyStabilityMetrics,
    RollingStabilityResult,
    TokenSupplyTracker,
    simulate_token_supply,
    simulate_supply_scenarios,
)

from .mint_burn_analyzer import (
    MintBurnEvent,
    DailyMintBurnStats,
    EquilibriumTestResult,
    MintBurnSummary,
    MintBurnAnalyzer,
    simulate_mint_burn_events,
    simulate_equilibrium_scenarios,
)

from .velocity_calculator import (
    VelocityMeasurement,
    VelocityTestResult,
    VelocityStatistics,
    VelocityCalculator,
    simulate_velocity_data,
    simulate_velocity_scenarios,
)

from .peg_stability_tester import (
    RedemptionEvent,
    PegTestResult,
    PegStatistics,
    PegStabilityTester,
    simulate_redemptions,
    simulate_peg_scenarios,
    simulate_stress_redemptions,
)

from .inflation_monitor import (
    InflationMeasurement,
    InflationTestResult,
    InflationStatistics,
    InflationMonitor,
    simulate_inflation_data,
    simulate_inflation_scenarios,
    simulate_mint_attack,
)

from .hypothesis_tests import (
    TokenHypothesisResult,
    TokenHypothesisTester,
)

from .visualization import (
    TokenVisualization,
    create_visualization_report,
)

from .experiments import (
    TokenExperimentConfig,
    SingleTokenRunResults,
    TokenExperimentResults,
    TokenEconomicsExperiment,
    run_quick_token_test,
    run_full_token_experiment,
)

__all__ = [
    # Token Supply Tracker
    "TokenSupplySnapshot",
    "SupplyStabilityMetrics",
    "RollingStabilityResult",
    "TokenSupplyTracker",
    "simulate_token_supply",
    "simulate_supply_scenarios",
    # Mint/Burn Analyzer
    "MintBurnEvent",
    "DailyMintBurnStats",
    "EquilibriumTestResult",
    "MintBurnSummary",
    "MintBurnAnalyzer",
    "simulate_mint_burn_events",
    "simulate_equilibrium_scenarios",
    # Velocity Calculator
    "VelocityMeasurement",
    "VelocityTestResult",
    "VelocityStatistics",
    "VelocityCalculator",
    "simulate_velocity_data",
    "simulate_velocity_scenarios",
    # Peg Stability Tester
    "RedemptionEvent",
    "PegTestResult",
    "PegStatistics",
    "PegStabilityTester",
    "simulate_redemptions",
    "simulate_peg_scenarios",
    "simulate_stress_redemptions",
    # Inflation Monitor
    "InflationMeasurement",
    "InflationTestResult",
    "InflationStatistics",
    "InflationMonitor",
    "simulate_inflation_data",
    "simulate_inflation_scenarios",
    "simulate_mint_attack",
    # Hypothesis Tests
    "TokenHypothesisResult",
    "TokenHypothesisTester",
    # Visualization
    "TokenVisualization",
    "create_visualization_report",
    # Experiments
    "TokenExperimentConfig",
    "SingleTokenRunResults",
    "TokenExperimentResults",
    "TokenEconomicsExperiment",
    "run_quick_token_test",
    "run_full_token_experiment",
]
