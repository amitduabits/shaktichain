"""Comprehensive backtesting framework for SHAKTI-CHAIN V2G trading.

This module provides:
- V2GBacktester: Main backtesting engine
- PerformanceMetrics: Comprehensive metric calculations
- BaselineStrategies: Benchmark trading strategies
- StatisticalTests: Significance testing and confidence intervals
- BacktestVisualizer: Visualization suite
- ReportGenerator: Markdown report generation
"""

from .backtester import (
    V2GBacktester,
    BacktestConfig,
    BacktestRun,
    DailyResult,
)

from .metrics import (
    PerformanceMetrics,
    ReturnMetrics,
    TradingMetrics,
    RiskMetrics,
    OperationalMetrics,
)

from .baselines import (
    BaseStrategy,
    RuleBasedStrategy,
    ThresholdStrategy,
    RandomStrategy,
    OracleStrategy,
    MomentumStrategy,
    MeanReversionStrategy,
)

from .statistics import (
    StatisticalTests,
    BootstrapCI,
    MonteCarloSimulation,
)

from .visualizer import (
    BacktestVisualizer,
)

from .report import (
    ReportGenerator,
)

__all__ = [
    # Backtester
    "V2GBacktester",
    "BacktestConfig",
    "BacktestRun",
    "DailyResult",
    # Metrics
    "PerformanceMetrics",
    "ReturnMetrics",
    "TradingMetrics",
    "RiskMetrics",
    "OperationalMetrics",
    # Baselines
    "BaseStrategy",
    "RuleBasedStrategy",
    "ThresholdStrategy",
    "RandomStrategy",
    "OracleStrategy",
    "MomentumStrategy",
    "MeanReversionStrategy",
    # Statistics
    "StatisticalTests",
    "BootstrapCI",
    "MonteCarloSimulation",
    # Visualization
    "BacktestVisualizer",
    # Report
    "ReportGenerator",
]
