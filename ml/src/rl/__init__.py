"""Reinforcement Learning module for SHAKTI-CHAIN V2G platform.

This module provides the RL environment and utilities for training
trading agents in the V2G (Vehicle-to-Grid) energy market.

Components:
- V2GTradingEnv: Main Gymnasium environment
- BatteryModel: Realistic battery simulation with degradation
- MarketSimulator: Electricity market price dynamics
- Wrappers: Observation/reward normalization, monitoring
- Visualization: Episode analysis and plotting tools
- Policy: Custom neural network architectures
- Curriculum: Progressive difficulty training
- Callbacks: Training monitoring and logging
- Backtest: Performance evaluation framework
"""

from .environment import (
    V2GTradingEnv,
    BatteryModel,
    MarketSimulator,
    BatteryConfig,
    MarketConfig,
    RewardConfig,
    EnvironmentConfig,
    DayType,
    ReputationTier,
)

from .wrappers import (
    NormalizeObservation,
    NormalizeReward,
    FrameStack,
    ActionMask,
    RewardShaping,
    EpisodeMonitor,
    TimeLimit,
    RecordEpisode,
    make_env,
    make_vec_env,
)

from .visualization import (
    EnvironmentVisualizer,
    EpisodeData,
    create_animation,
)

from .curriculum import (
    CurriculumStage,
    StageConfig,
    CurriculumScheduler,
    CurriculumEnv,
    make_curriculum_env,
    create_simple_stage_config,
    create_normal_stage_config,
    create_adversarial_stage_config,
    create_full_stage_config,
)

from .callbacks import (
    TradingMetricsCallback,
    CurriculumCallback,
    CustomEvalCallback,
    ProgressCallback,
    SaveOnBestTrainingRewardCallback,
    create_training_callbacks,
)

from .backtest import (
    Backtester,
    BacktestResult,
    BacktestReporter,
    TradeRecord,
    BenchmarkResult,
    backtest_trained_model,
)

# Policy imports are optional (require stable-baselines3)
try:
    from .policy import (
        V2GTradingPolicy,
        V2GFeaturesExtractor,
        ForecastEncoder,
        StateEncoder,
        AttentionFusion,
        SimpleMlpPolicy,
    )
    _HAS_SB3 = True
except ImportError:
    _HAS_SB3 = False

__all__ = [
    # Environment
    "V2GTradingEnv",
    "BatteryModel",
    "MarketSimulator",
    # Configurations
    "BatteryConfig",
    "MarketConfig",
    "RewardConfig",
    "EnvironmentConfig",
    # Enums
    "DayType",
    "ReputationTier",
    # Wrappers
    "NormalizeObservation",
    "NormalizeReward",
    "FrameStack",
    "ActionMask",
    "RewardShaping",
    "EpisodeMonitor",
    "TimeLimit",
    "RecordEpisode",
    # Factory functions
    "make_env",
    "make_vec_env",
    # Visualization
    "EnvironmentVisualizer",
    "EpisodeData",
    "create_animation",
    # Curriculum
    "CurriculumStage",
    "StageConfig",
    "CurriculumScheduler",
    "CurriculumEnv",
    "make_curriculum_env",
    "create_simple_stage_config",
    "create_normal_stage_config",
    "create_adversarial_stage_config",
    "create_full_stage_config",
    # Callbacks
    "TradingMetricsCallback",
    "CurriculumCallback",
    "CustomEvalCallback",
    "ProgressCallback",
    "SaveOnBestTrainingRewardCallback",
    "create_training_callbacks",
    # Backtest
    "Backtester",
    "BacktestResult",
    "BacktestReporter",
    "TradeRecord",
    "BenchmarkResult",
    "backtest_trained_model",
]

# Add policy exports if available
if _HAS_SB3:
    __all__.extend([
        "V2GTradingPolicy",
        "V2GFeaturesExtractor",
        "ForecastEncoder",
        "StateEncoder",
        "AttentionFusion",
        "SimpleMlpPolicy",
    ])
