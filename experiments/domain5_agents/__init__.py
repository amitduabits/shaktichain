"""
Domain 5: Agent Behavior & Strategy-Proofness Experiments for SHAKTI-CHAIN Validation.

This module provides comprehensive testing and validation of agent behavior
hypotheses for the SHAKTI-CHAIN decentralized energy trading system.

Hypotheses Tested:
- H5.1: Incentive Compatibility (Truthful bidding is optimal)
- H5.2: Convergence Under Rational Agents (within 50 rounds)
- H5.3: Robustness to Bounded Rationality (>= 85% efficiency)
- H5.4: Manipulation Resistance (< 5% gain)
- H5.5: Sybil Attack Resistance (no profit from splitting)
- H5.6: Collusion Resistance (< 10% gain)

Usage:
    # Quick test
    from experiments.domain5_agents import run_quick_agent_test
    results = run_quick_agent_test(seed=42)
    print(results.summary())

    # Full experiment
    from experiments.domain5_agents import AgentExperimentConfig, AgentBehaviorExperiment
    config = AgentExperimentConfig(num_runs=10, seed=42)
    experiment = AgentBehaviorExperiment(config)
    results = experiment.run()

    # Command line
    python -m experiments.domain5_agents run --num-runs 5
    python -m experiments.domain5_agents quick-test
    python -m experiments.domain5_agents hypotheses
"""

from .incentive_compatibility import (
    IncentiveCompatibilityTester,
    ICTestResult,
    AgentICResult,
    DeviationResult,
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
    ManipulationStrategy,
    ManipulationResult,
    ManipulationTestResult,
    ManipulationAttack,
    SpoofingAttack,
    WashTradingAttack,
    PriceManipulationAttack,
    simulate_manipulation_test,
)

from .sybil_tester import (
    SybilTester,
    SybilTestResult,
    SybilTestPoint,
    ComprehensiveSybilResult,
    simulate_sybil_test,
    simulate_comprehensive_sybil_test,
)

from .collusion_detector import (
    CollusionSimulator,
    CollusionStrategy,
    CollusionSimResult,
    CollusionTestResult,
    simulate_collusion_test,
)

from .hypothesis_tests import (
    AgentHypothesisTester,
    AgentHypothesisResult,
)

from .visualization import (
    AgentVisualization,
    create_visualization_report,
)

from .experiments import (
    AgentExperimentConfig,
    SingleAgentRunResults,
    AgentExperimentResults,
    AgentBehaviorExperiment,
    run_quick_agent_test,
    run_full_agent_experiment,
)

__all__ = [
    # Incentive Compatibility
    "IncentiveCompatibilityTester",
    "ICTestResult",
    "AgentICResult",
    "DeviationResult",
    "simulate_ic_test",
    # Convergence Analyzer
    "ConvergenceAnalyzer",
    "ConvergenceTestResult",
    "RobustnessTestResult",
    "EfficiencyResult",
    "simulate_convergence_test",
    "simulate_robustness_test",
    # Manipulation Simulator
    "ManipulationSimulator",
    "ManipulationStrategy",
    "ManipulationResult",
    "ManipulationTestResult",
    "ManipulationAttack",
    "SpoofingAttack",
    "WashTradingAttack",
    "PriceManipulationAttack",
    "simulate_manipulation_test",
    # Sybil Tester
    "SybilTester",
    "SybilTestResult",
    "SybilTestPoint",
    "ComprehensiveSybilResult",
    "simulate_sybil_test",
    "simulate_comprehensive_sybil_test",
    # Collusion Detector
    "CollusionSimulator",
    "CollusionStrategy",
    "CollusionSimResult",
    "CollusionTestResult",
    "simulate_collusion_test",
    # Hypothesis Tests
    "AgentHypothesisTester",
    "AgentHypothesisResult",
    # Visualization
    "AgentVisualization",
    "create_visualization_report",
    # Experiments
    "AgentExperimentConfig",
    "SingleAgentRunResults",
    "AgentExperimentResults",
    "AgentBehaviorExperiment",
    "run_quick_agent_test",
    "run_full_agent_experiment",
]
