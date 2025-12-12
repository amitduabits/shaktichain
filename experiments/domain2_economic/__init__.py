"""
Domain 2 - Economic Performance Experiments for SHAKTI-CHAIN.

This module implements hypothesis tests for validating the economic
performance of the V2G marketplace:

Hypotheses:
- H2.1: Participant ROI > 15%
- H2.2: ROI varies significantly by agent type
- H2.3: Welfare distribution fairness (Gini < 0.4)
- H2.4: Price volatility (CV < 0.15 under normal conditions)
- H2.5: Bid-ask spread < 10% of mid-price
- H2.6: Market liquidity (fill rate > 80%)
"""

from .roi_calculator import (
    RoiResult,
    RoiDistribution,
    calculate_agent_roi,
    calculate_roi_distribution,
    calculate_roi_by_battery_size,
)

from .fairness_metrics import (
    calculate_gini_coefficient,
    calculate_theil_index,
    bootstrap_gini_ci,
    calculate_lorenz_curve,
    calculate_hoover_index,
)

from .liquidity_metrics import (
    SpreadMetrics,
    DepthMetrics,
    OrderBookSnapshot,
    calculate_bid_ask_spread,
    calculate_fill_rate,
    calculate_market_depth,
    calculate_price_volatility,
)

from .hypothesis_tests import (
    EconomicHypothesisResult,
    EconomicHypothesisTester,
)

from .experiments import (
    EconomicExperimentConfig,
    EconomicExperimentResults,
    EconomicPerformanceExperiment,
    run_quick_economic_test,
    run_full_economic_experiment,
)

from .visualization import EconomicVisualizer

__all__ = [
    # ROI
    "RoiResult",
    "RoiDistribution",
    "calculate_agent_roi",
    "calculate_roi_distribution",
    "calculate_roi_by_battery_size",
    # Fairness
    "calculate_gini_coefficient",
    "calculate_theil_index",
    "bootstrap_gini_ci",
    "calculate_lorenz_curve",
    "calculate_hoover_index",
    # Liquidity
    "SpreadMetrics",
    "DepthMetrics",
    "OrderBookSnapshot",
    "calculate_bid_ask_spread",
    "calculate_fill_rate",
    "calculate_market_depth",
    "calculate_price_volatility",
    # Hypothesis tests
    "EconomicHypothesisResult",
    "EconomicHypothesisTester",
    # Experiments
    "EconomicExperimentConfig",
    "EconomicExperimentResults",
    "EconomicPerformanceExperiment",
    "run_quick_economic_test",
    "run_full_economic_experiment",
    # Visualization
    "EconomicVisualizer",
]
