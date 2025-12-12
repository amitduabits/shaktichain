"""
Domain 1: Market Mechanism Efficiency Experiments

This module implements hypothesis tests for validating the allocative efficiency,
individual rationality, budget balance, and price discovery of the McAfee
double auction mechanism in SHAKTI-CHAIN.

Hypotheses:
- H1.1: Allocative Efficiency ≥ 95% of Walrasian optimal
- H1.2: Buyer Individual Rationality (100% compliance)
- H1.3: Seller Individual Rationality (100% compliance)
- H1.4: Budget Balance (market maker revenue ≥ 0)
- H1.5: Price Discovery Accuracy (< 5% deviation from equilibrium)
- H1.6: Trade Volume Efficiency ≥ 90% of Walrasian optimal
"""

from .walrasian_calculator import WalrasianCalculator, WalrasianEquilibrium
from .efficiency_metrics import EfficiencyMetrics, EfficiencyResults, Trade
from .hypothesis_tests import MechanismHypothesisTester, HypothesisResult
from .experiments import (
    MechanismEfficiencyExperiment,
    ExperimentResults,
    ExperimentConfig,
    run_quick_test,
    run_full_experiment,
)
from .visualization import MechanismVisualizer

__all__ = [
    # Walrasian equilibrium
    "WalrasianCalculator",
    "WalrasianEquilibrium",
    # Efficiency metrics
    "EfficiencyMetrics",
    "EfficiencyResults",
    "Trade",
    # Hypothesis testing
    "MechanismHypothesisTester",
    "HypothesisResult",
    # Experiments
    "MechanismEfficiencyExperiment",
    "ExperimentResults",
    "ExperimentConfig",
    "run_quick_test",
    "run_full_experiment",
    # Visualization
    "MechanismVisualizer",
]
