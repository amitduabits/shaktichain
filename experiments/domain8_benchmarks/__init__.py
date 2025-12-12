"""
Domain 8: Comparative Benchmarking Experiments for SHAKTI-CHAIN.

This module implements hypothesis tests for benchmarking against alternatives:

H8.1: vs Fixed Tariff (DISCOM)
    - H1: ROI(SHAKTI) > ROI(Fixed Tariff)
    - H0: ROI(SHAKTI) <= ROI(Fixed Tariff)
    - Test: Independent t-test

H8.2: vs Uniform Price Auction
    - H1: McAfee efficiency > Uniform efficiency
    - H0: McAfee <= Uniform
    - Test: Two-sample t-test

H8.3: vs Continuous Double Auction (IEEE SOTA)
    - H1: SHAKTI welfare >= 95% of CDA
    - H0: SHAKTI < 95% of CDA
    - Test: TOST equivalence test

H8.4: vs Brooklyn Microgrid Model
    - H1: SHAKTI cost < Brooklyn cost
    - H0: SHAKTI >= Brooklyn
    - Test: Two-sample t-test

H8.5: vs RL-based Bidding (IEEE SOTA)
    - H1: SAC reward >= 95% of SOTA RL
    - H0: SAC < 95%
    - Test: TOST equivalence test

H8.6: Multi-Criteria Dominance
    - H1: SHAKTI is Pareto optimal
    - H0: SHAKTI is dominated
    - Test: Hypervolume indicator

Components:
    - fixed_tariff_baseline: Indian DISCOM rates
    - uniform_auction_baseline: Single clearing price auction
    - cda_baseline: Continuous double auction
    - brooklyn_baseline: Brooklyn Microgrid model
    - sota_rl_baseline: IEEE SOTA RL agent
    - pareto_analyzer: Multi-objective analysis
    - hypothesis_tests: Statistical testing
    - visualization: Benchmark plots
"""

from .fixed_tariff_baseline import (
    DISCOMTariff,
    FixedTariffResult,
    FixedTariffSimulator,
    BSES_DELHI,
    TATA_MUMBAI,
    BESCOM_BANGALORE,
    TNEB_CHENNAI,
    CESC_KOLKATA,
    HPSEBL_HYDERABAD,
    INDIA_DISCOM_TARIFFS,
    get_tariff_for_city,
    simulate_fixed_tariff,
)

from .uniform_auction_baseline import (
    Order,
    Trade,
    AuctionResult,
    UniformPriceAuction,
    UniformAuctionSimulator,
    simulate_uniform_auction,
)

from .cda_baseline import (
    OrderBook,
    CDAResult,
    ContinuousDoubleAuction,
    CDASimulator,
    simulate_cda,
)

from .brooklyn_baseline import (
    BrooklynMicrogridModel,
    BrooklynResult,
    BrooklynSimulator,
    simulate_brooklyn,
)

from .sota_rl_baseline import (
    RLState,
    ReplayBuffer,
    DQNetwork,
    SOTARLAgent,
    RLResult,
    RLSimulator,
    simulate_sota_rl,
)

from .pareto_analyzer import (
    SystemMetrics,
    ParetoResult,
    ParetoAnalyzer,
    create_benchmark_systems,
    analyze_pareto_optimality,
    test_shakti_pareto_optimal,
)

from .hypothesis_tests import (
    HypothesisResult,
    BenchmarkHypothesisResults,
    BenchmarkHypothesisTester,
    tost_test,
    run_benchmark_hypothesis_tests,
)

from .visualization import (
    BenchmarkVisualization,
    create_benchmark_report,
)

from .experiments import (
    BenchmarkExperimentConfig,
    SingleRunResults,
    BenchmarkExperimentResults,
    BenchmarkExperiment,
    run_quick_benchmark_test,
    run_full_benchmark_experiment,
    print_hypothesis_summary,
)

__all__ = [
    # Fixed tariff
    "DISCOMTariff",
    "FixedTariffResult",
    "FixedTariffSimulator",
    "BSES_DELHI",
    "TATA_MUMBAI",
    "BESCOM_BANGALORE",
    "TNEB_CHENNAI",
    "CESC_KOLKATA",
    "HPSEBL_HYDERABAD",
    "INDIA_DISCOM_TARIFFS",
    "get_tariff_for_city",
    "simulate_fixed_tariff",

    # Uniform auction
    "Order",
    "Trade",
    "AuctionResult",
    "UniformPriceAuction",
    "UniformAuctionSimulator",
    "simulate_uniform_auction",

    # CDA
    "OrderBook",
    "CDAResult",
    "ContinuousDoubleAuction",
    "CDASimulator",
    "simulate_cda",

    # Brooklyn
    "BrooklynMicrogridModel",
    "BrooklynResult",
    "BrooklynSimulator",
    "simulate_brooklyn",

    # SOTA RL
    "RLState",
    "ReplayBuffer",
    "DQNetwork",
    "SOTARLAgent",
    "RLResult",
    "RLSimulator",
    "simulate_sota_rl",

    # Pareto analyzer
    "SystemMetrics",
    "ParetoResult",
    "ParetoAnalyzer",
    "create_benchmark_systems",
    "analyze_pareto_optimality",
    "test_shakti_pareto_optimal",

    # Hypothesis tests
    "HypothesisResult",
    "BenchmarkHypothesisResults",
    "BenchmarkHypothesisTester",
    "tost_test",
    "run_benchmark_hypothesis_tests",

    # Visualization
    "BenchmarkVisualization",
    "create_benchmark_report",

    # Experiments
    "BenchmarkExperimentConfig",
    "SingleRunResults",
    "BenchmarkExperimentResults",
    "BenchmarkExperiment",
    "run_quick_benchmark_test",
    "run_full_benchmark_experiment",
    "print_hypothesis_summary",
]
