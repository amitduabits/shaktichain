"""Curriculum learning for V2G Trading Agent.

Implements progressive difficulty stages for training:
1. Simple market (fixed prices, easy profits)
2. Normal market (realistic dynamics)
3. Adversarial market (spikes and volatility)
4. Full complexity (all features enabled)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import IntEnum
import logging

from .environment import (
    V2GTradingEnv,
    EnvironmentConfig,
    BatteryConfig,
    MarketConfig,
    RewardConfig,
    DayType,
)

logger = logging.getLogger(__name__)


class CurriculumStage(IntEnum):
    """Curriculum learning stages."""
    SIMPLE = 0      # Fixed prices, no volatility
    NORMAL = 1      # Realistic price movements
    ADVERSARIAL = 2 # Price spikes and crashes
    FULL = 3        # Full complexity


@dataclass
class StageConfig:
    """Configuration for a curriculum stage."""
    name: str
    description: str
    min_timesteps: int  # Minimum timesteps before advancing
    advance_threshold: float  # Performance threshold to advance
    env_config: EnvironmentConfig = field(default_factory=EnvironmentConfig)


def create_simple_stage_config() -> StageConfig:
    """Create Stage 1: Simple market configuration.

    Features:
    - Fixed/predictable prices
    - No volatility
    - No degradation
    - No transaction fees
    - Easy to learn buy-low-sell-high
    """
    battery = BatteryConfig(
        capacity_kwh=60.0,
        max_charge_rate_kw=11.0,
        max_discharge_rate_kw=11.0,
        charge_efficiency=1.0,  # Perfect efficiency
        discharge_efficiency=1.0,
        min_soc=0.1,
        max_soc=0.95,
        initial_soc=0.5,
        degradation_per_cycle=0.0,  # No degradation
        cycle_cost_per_kwh=0.0,
    )

    market = MarketConfig(
        base_price=5.0,
        price_volatility=0.0,  # No volatility
        bid_ask_spread=0.0,    # No spread
        transaction_fee=0.0,   # No fees
        min_trade_kwh=1.0,
        max_trade_kwh=50.0,
        price_impact=0.0,      # No price impact
    )

    reward = RewardConfig(
        profit_weight=1.0,
        battery_health_weight=0.0,  # No health penalty
        grid_service_weight=0.0,
        reputation_weight=0.0,
        failed_delivery_penalty=0.0,
        low_soc_penalty=0.0,
        high_soc_penalty=0.0,
        frequency_regulation_bonus=0.0,
    )

    env_config = EnvironmentConfig(
        battery=battery,
        market=market,
        reward=reward,
        episode_length=24,
        forecast_horizon=24,
    )

    return StageConfig(
        name="Simple Market",
        description="Fixed prices, no volatility, learn basic buy-low-sell-high",
        min_timesteps=100_000,
        advance_threshold=5.0,  # Average profit > 5
        env_config=env_config,
    )


def create_normal_stage_config() -> StageConfig:
    """Create Stage 2: Normal market configuration.

    Features:
    - Realistic price movements
    - Normal volatility
    - Small bid-ask spread
    - Light degradation
    - Learn timing and sizing
    """
    battery = BatteryConfig(
        capacity_kwh=60.0,
        max_charge_rate_kw=11.0,
        max_discharge_rate_kw=11.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc=0.2,
        max_soc=0.95,
        initial_soc=0.5,
        degradation_per_cycle=0.00005,  # Light degradation
        cycle_cost_per_kwh=0.02,
    )

    market = MarketConfig(
        base_price=5.0,
        price_volatility=0.15,  # Moderate volatility
        bid_ask_spread=0.03,    # Small spread
        transaction_fee=0.005,  # Small fees
        min_trade_kwh=1.0,
        max_trade_kwh=50.0,
        price_impact=0.0005,
    )

    reward = RewardConfig(
        profit_weight=1.0,
        battery_health_weight=0.2,
        grid_service_weight=0.1,
        reputation_weight=0.1,
        failed_delivery_penalty=-20.0,
        low_soc_penalty=-2.0,
        high_soc_penalty=-1.0,
        frequency_regulation_bonus=2.0,
    )

    env_config = EnvironmentConfig(
        battery=battery,
        market=market,
        reward=reward,
        episode_length=24,
        forecast_horizon=24,
    )

    return StageConfig(
        name="Normal Market",
        description="Realistic price movements, learn timing and sizing",
        min_timesteps=500_000,
        advance_threshold=10.0,  # Average profit > 10
        env_config=env_config,
    )


def create_adversarial_stage_config() -> StageConfig:
    """Create Stage 3: Adversarial market configuration.

    Features:
    - Price spikes and crashes
    - High volatility
    - Larger spreads
    - Learn risk management
    """
    battery = BatteryConfig(
        capacity_kwh=60.0,
        max_charge_rate_kw=11.0,
        max_discharge_rate_kw=11.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc=0.2,
        max_soc=0.95,
        initial_soc=0.5,
        degradation_per_cycle=0.0001,
        cycle_cost_per_kwh=0.05,
    )

    market = MarketConfig(
        base_price=5.0,
        price_volatility=0.4,   # High volatility
        bid_ask_spread=0.08,    # Larger spread
        transaction_fee=0.01,
        min_trade_kwh=1.0,
        max_trade_kwh=50.0,
        price_impact=0.002,
    )

    reward = RewardConfig(
        profit_weight=1.0,
        battery_health_weight=0.4,
        grid_service_weight=0.2,
        reputation_weight=0.2,
        failed_delivery_penalty=-50.0,
        low_soc_penalty=-5.0,
        high_soc_penalty=-3.0,
        frequency_regulation_bonus=5.0,
    )

    env_config = EnvironmentConfig(
        battery=battery,
        market=market,
        reward=reward,
        episode_length=24,
        forecast_horizon=24,
    )

    return StageConfig(
        name="Adversarial Market",
        description="Price spikes and crashes, learn risk management",
        min_timesteps=1_000_000,
        advance_threshold=8.0,  # Average profit > 8 (harder to achieve)
        env_config=env_config,
    )


def create_full_stage_config() -> StageConfig:
    """Create Stage 4: Full complexity configuration.

    Features:
    - All realistic constraints
    - Full degradation model
    - Reputation system active
    - Transaction fees
    - Complete reward structure
    """
    battery = BatteryConfig(
        capacity_kwh=60.0,
        max_charge_rate_kw=11.0,
        max_discharge_rate_kw=11.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc=0.2,
        max_soc=0.95,
        initial_soc=0.5,
        degradation_per_cycle=0.0001,
        cycle_cost_per_kwh=0.05,
    )

    market = MarketConfig(
        base_price=5.0,
        price_volatility=0.3,
        bid_ask_spread=0.05,
        transaction_fee=0.01,
        min_trade_kwh=1.0,
        max_trade_kwh=50.0,
        price_impact=0.001,
    )

    reward = RewardConfig(
        profit_weight=1.0,
        battery_health_weight=0.5,
        grid_service_weight=0.3,
        reputation_weight=0.2,
        failed_delivery_penalty=-100.0,
        low_soc_penalty=-10.0,
        high_soc_penalty=-5.0,
        frequency_regulation_bonus=5.0,
    )

    env_config = EnvironmentConfig(
        battery=battery,
        market=market,
        reward=reward,
        episode_length=24,
        forecast_horizon=24,
    )

    return StageConfig(
        name="Full Complexity",
        description="All features enabled, production-ready training",
        min_timesteps=5_000_000,
        advance_threshold=15.0,  # Target: >15% ROI
        env_config=env_config,
    )


class CurriculumScheduler:
    """Manages curriculum learning progression.

    Tracks training progress and decides when to advance
    to the next difficulty stage.
    """

    def __init__(
        self,
        stages: Optional[List[StageConfig]] = None,
        evaluation_window: int = 100,
        advance_patience: int = 5,
    ):
        """Initialize curriculum scheduler.

        Args:
            stages: List of stage configurations (default: all 4 stages)
            evaluation_window: Number of episodes for rolling average
            advance_patience: Consecutive windows above threshold to advance
        """
        if stages is None:
            stages = [
                create_simple_stage_config(),
                create_normal_stage_config(),
                create_adversarial_stage_config(),
                create_full_stage_config(),
            ]

        self.stages = stages
        self.evaluation_window = evaluation_window
        self.advance_patience = advance_patience

        self.current_stage_idx = 0
        self.timesteps_in_stage = 0
        self.episode_profits: List[float] = []
        self.consecutive_above_threshold = 0
        self.stage_history: List[Dict[str, Any]] = []

    @property
    def current_stage(self) -> StageConfig:
        """Get current stage configuration."""
        return self.stages[self.current_stage_idx]

    @property
    def current_env_config(self) -> EnvironmentConfig:
        """Get current environment configuration."""
        return self.current_stage.env_config

    @property
    def is_final_stage(self) -> bool:
        """Check if at final stage."""
        return self.current_stage_idx >= len(self.stages) - 1

    def record_episode(self, profit: float, timesteps: int):
        """Record episode result.

        Args:
            profit: Episode profit
            timesteps: Timesteps taken in episode
        """
        self.episode_profits.append(profit)
        self.timesteps_in_stage += timesteps

        # Keep only recent episodes
        if len(self.episode_profits) > self.evaluation_window * 2:
            self.episode_profits = self.episode_profits[-self.evaluation_window:]

    def should_advance(self) -> bool:
        """Check if should advance to next stage.

        Returns:
            True if should advance
        """
        if self.is_final_stage:
            return False

        # Check minimum timesteps
        if self.timesteps_in_stage < self.current_stage.min_timesteps:
            return False

        # Check performance threshold
        if len(self.episode_profits) < self.evaluation_window:
            return False

        recent_profits = self.episode_profits[-self.evaluation_window:]
        avg_profit = np.mean(recent_profits)

        if avg_profit >= self.current_stage.advance_threshold:
            self.consecutive_above_threshold += 1
        else:
            self.consecutive_above_threshold = 0

        return self.consecutive_above_threshold >= self.advance_patience

    def advance_stage(self):
        """Advance to next curriculum stage."""
        if self.is_final_stage:
            logger.warning("Already at final stage, cannot advance")
            return

        # Record stage history
        self.stage_history.append({
            "stage": self.current_stage.name,
            "timesteps": self.timesteps_in_stage,
            "final_avg_profit": np.mean(self.episode_profits[-self.evaluation_window:])
            if len(self.episode_profits) >= self.evaluation_window else np.mean(self.episode_profits),
        })

        # Advance
        self.current_stage_idx += 1
        self.timesteps_in_stage = 0
        self.episode_profits = []
        self.consecutive_above_threshold = 0

        logger.info(f"Advanced to stage {self.current_stage_idx}: {self.current_stage.name}")
        logger.info(f"  {self.current_stage.description}")

    def get_status(self) -> Dict[str, Any]:
        """Get current curriculum status.

        Returns:
            Status dictionary
        """
        recent_profits = (
            self.episode_profits[-self.evaluation_window:]
            if len(self.episode_profits) >= self.evaluation_window
            else self.episode_profits
        )

        return {
            "stage_idx": self.current_stage_idx,
            "stage_name": self.current_stage.name,
            "timesteps_in_stage": self.timesteps_in_stage,
            "min_timesteps": self.current_stage.min_timesteps,
            "episodes_recorded": len(self.episode_profits),
            "avg_profit": np.mean(recent_profits) if recent_profits else 0.0,
            "threshold": self.current_stage.advance_threshold,
            "consecutive_above": self.consecutive_above_threshold,
            "patience": self.advance_patience,
            "is_final": self.is_final_stage,
        }

    def print_status(self):
        """Print current curriculum status."""
        status = self.get_status()

        print("\n" + "=" * 50)
        print("Curriculum Learning Status")
        print("=" * 50)
        print(f"Stage: {status['stage_idx'] + 1}/{len(self.stages)} - {status['stage_name']}")
        print(f"Timesteps: {status['timesteps_in_stage']:,} / {status['min_timesteps']:,}")
        print(f"Episodes: {status['episodes_recorded']}")
        print(f"Avg Profit: ₹{status['avg_profit']:.2f} (threshold: ₹{status['threshold']:.2f})")
        print(f"Progress: {status['consecutive_above']}/{status['patience']} windows above threshold")
        print("=" * 50)


class CurriculumEnv(V2GTradingEnv):
    """Environment wrapper that supports curriculum learning.

    Automatically adjusts difficulty based on curriculum scheduler.
    """

    def __init__(
        self,
        scheduler: CurriculumScheduler,
        **kwargs,
    ):
        """Initialize curriculum environment.

        Args:
            scheduler: Curriculum scheduler
            **kwargs: Additional arguments for V2GTradingEnv
        """
        self.scheduler = scheduler

        # Initialize with current stage config
        super().__init__(
            config=scheduler.current_env_config,
            **kwargs,
        )

    def step(self, action):
        """Take step and track for curriculum."""
        obs, reward, terminated, truncated, info = super().step(action)

        # Record episode completion
        if terminated or truncated:
            self.scheduler.record_episode(
                profit=info.get("episode_profit", 0.0),
                timesteps=self.current_step,
            )

            # Check if should advance
            if self.scheduler.should_advance():
                self.scheduler.advance_stage()
                self._update_config()

        return obs, reward, terminated, truncated, info

    def _update_config(self):
        """Update environment configuration for new stage."""
        new_config = self.scheduler.current_env_config

        # Update battery config
        self.battery.config = new_config.battery
        self.battery.reset()

        # Update market config
        self.market.config = new_config.market
        self.market.reset()

        # Update reward config
        self.config = new_config

        logger.info(f"Environment updated for stage: {self.scheduler.current_stage.name}")


def make_curriculum_env(
    scheduler: Optional[CurriculumScheduler] = None,
    **env_kwargs,
) -> CurriculumEnv:
    """Create curriculum learning environment.

    Args:
        scheduler: Curriculum scheduler (created if None)
        **env_kwargs: Additional environment arguments

    Returns:
        CurriculumEnv instance
    """
    if scheduler is None:
        scheduler = CurriculumScheduler()

    return CurriculumEnv(scheduler=scheduler, **env_kwargs)
