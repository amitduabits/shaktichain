"""Environment wrappers and utilities for V2G Trading.

Provides standard wrappers for:
- Observation normalization
- Action normalization
- Frame stacking
- Reward shaping
- Episode monitoring
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Dict, Any, Optional, Tuple, List, Union
from collections import deque
import logging

logger = logging.getLogger(__name__)


class NormalizeObservation(gym.ObservationWrapper):
    """Normalize observations using running statistics.

    Tracks mean and variance of observations and normalizes
    them to have approximately zero mean and unit variance.
    """

    def __init__(
        self,
        env: gym.Env,
        epsilon: float = 1e-8,
        clip_obs: float = 10.0,
    ):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
            epsilon: Small constant for numerical stability
            clip_obs: Clip normalized observations to this range
        """
        super().__init__(env)
        self.epsilon = epsilon
        self.clip_obs = clip_obs

        obs_shape = env.observation_space.shape
        self.obs_mean = np.zeros(obs_shape, dtype=np.float64)
        self.obs_var = np.ones(obs_shape, dtype=np.float64)
        self.count = 1e-4

    def observation(self, obs: np.ndarray) -> np.ndarray:
        """Normalize observation.

        Args:
            obs: Raw observation

        Returns:
            Normalized observation
        """
        self._update_stats(obs)
        normalized = (obs - self.obs_mean) / np.sqrt(self.obs_var + self.epsilon)
        return np.clip(normalized, -self.clip_obs, self.clip_obs).astype(np.float32)

    def _update_stats(self, obs: np.ndarray):
        """Update running mean and variance.

        Uses Welford's online algorithm.
        """
        self.count += 1
        delta = obs - self.obs_mean
        self.obs_mean += delta / self.count
        delta2 = obs - self.obs_mean
        self.obs_var += (delta * delta2 - self.obs_var) / self.count

    def reset_stats(self):
        """Reset running statistics."""
        obs_shape = self.env.observation_space.shape
        self.obs_mean = np.zeros(obs_shape, dtype=np.float64)
        self.obs_var = np.ones(obs_shape, dtype=np.float64)
        self.count = 1e-4


class NormalizeReward(gym.RewardWrapper):
    """Normalize rewards using running statistics.

    Scales rewards to have approximately unit variance while
    preserving the sign and relative magnitudes.
    """

    def __init__(
        self,
        env: gym.Env,
        gamma: float = 0.99,
        epsilon: float = 1e-8,
        clip_reward: float = 10.0,
    ):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
            gamma: Discount factor for return estimation
            epsilon: Small constant for numerical stability
            clip_reward: Clip normalized rewards to this range
        """
        super().__init__(env)
        self.gamma = gamma
        self.epsilon = epsilon
        self.clip_reward = clip_reward

        self.return_var = 1.0
        self.returns = 0.0
        self.count = 1e-4

    def reward(self, reward: float) -> float:
        """Normalize reward.

        Args:
            reward: Raw reward

        Returns:
            Normalized reward
        """
        self._update_stats(reward)
        normalized = reward / np.sqrt(self.return_var + self.epsilon)
        return np.clip(normalized, -self.clip_reward, self.clip_reward)

    def _update_stats(self, reward: float):
        """Update running return variance."""
        self.returns = self.returns * self.gamma + reward
        self.count += 1
        delta = self.returns**2 - self.return_var
        self.return_var += delta / self.count

    def reset(self, **kwargs):
        """Reset environment and return tracking."""
        self.returns = 0.0
        return self.env.reset(**kwargs)


class FrameStack(gym.ObservationWrapper):
    """Stack multiple observations for temporal context.

    Useful for giving the agent information about recent history
    without requiring recurrent networks.
    """

    def __init__(
        self,
        env: gym.Env,
        num_stack: int = 4,
    ):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
            num_stack: Number of frames to stack
        """
        super().__init__(env)
        self.num_stack = num_stack

        old_space = env.observation_space
        low = np.repeat(old_space.low[np.newaxis, ...], num_stack, axis=0)
        high = np.repeat(old_space.high[np.newaxis, ...], num_stack, axis=0)

        self.observation_space = spaces.Box(
            low=low.flatten(),
            high=high.flatten(),
            dtype=old_space.dtype,
        )

        self.frames: deque = deque(maxlen=num_stack)

    def reset(self, **kwargs):
        """Reset environment and frame buffer."""
        obs, info = self.env.reset(**kwargs)
        for _ in range(self.num_stack):
            self.frames.append(obs)
        return self.observation(None), info

    def observation(self, obs: Optional[np.ndarray]) -> np.ndarray:
        """Stack frames into single observation.

        Args:
            obs: New observation (added to buffer)

        Returns:
            Stacked observations
        """
        if obs is not None:
            self.frames.append(obs)
        return np.concatenate(list(self.frames), axis=0)


class ActionMask(gym.ActionWrapper):
    """Mask invalid actions based on current state.

    Prevents agent from taking actions that would violate
    physical constraints (e.g., discharging empty battery).
    """

    def __init__(self, env: gym.Env):
        """Initialize wrapper.

        Args:
            env: Environment to wrap (must be V2GTradingEnv)
        """
        super().__init__(env)
        self._action_mask = np.ones(env.action_space.shape, dtype=np.float32)

    def action(self, action: np.ndarray) -> np.ndarray:
        """Apply action mask.

        Args:
            action: Agent's action

        Returns:
            Masked action
        """
        return action * self._action_mask

    def step(self, action):
        """Take step and update action mask."""
        result = self.env.step(self.action(action))
        self._update_mask()
        return result

    def reset(self, **kwargs):
        """Reset environment and action mask."""
        result = self.env.reset(**kwargs)
        self._update_mask()
        return result

    def _update_mask(self):
        """Update action mask based on current state."""
        env = self.env

        # Check available capacity for actions
        can_charge = env.battery.get_available_charge_capacity() > env.config.market.min_trade_kwh
        can_discharge = env.battery.get_available_discharge_capacity() > env.config.market.min_trade_kwh

        # For continuous action space: [quantity, aggressiveness]
        if not env.use_discrete_actions:
            self._action_mask = np.ones(2, dtype=np.float32)

            # Limit quantity based on capacity
            if not can_charge:
                # Can't buy (positive quantity)
                self._action_mask[0] = -1.0  # Only allow negative (sell) or zero
            if not can_discharge:
                # Can't sell (negative quantity)
                self._action_mask[0] = 1.0  # Only allow positive (buy) or zero

    def get_action_mask(self) -> np.ndarray:
        """Get current action mask."""
        return self._action_mask.copy()


class RewardShaping(gym.RewardWrapper):
    """Shape rewards with additional components.

    Adds auxiliary reward signals to encourage good behavior:
    - Trading at optimal times
    - Maintaining healthy SOC levels
    - Consistent participation
    """

    def __init__(
        self,
        env: gym.Env,
        soc_target: float = 0.6,
        soc_bonus_weight: float = 0.1,
        activity_bonus: float = 0.01,
        peak_trading_bonus: float = 0.5,
    ):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
            soc_target: Target SOC for bonus
            soc_bonus_weight: Weight for SOC bonus
            activity_bonus: Small bonus for taking action
            peak_trading_bonus: Bonus for trading during peak hours
        """
        super().__init__(env)
        self.soc_target = soc_target
        self.soc_bonus_weight = soc_bonus_weight
        self.activity_bonus = activity_bonus
        self.peak_trading_bonus = peak_trading_bonus

        self._last_info = {}

    def step(self, action):
        """Take step and shape reward."""
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._last_info = info
        shaped_reward = self._shape_reward(reward, action, info)
        return obs, shaped_reward, terminated, truncated, info

    def reward(self, reward: float) -> float:
        """Shape reward (called by wrapper).

        Args:
            reward: Original reward

        Returns:
            Shaped reward
        """
        return reward

    def _shape_reward(
        self,
        reward: float,
        action: np.ndarray,
        info: Dict[str, Any],
    ) -> float:
        """Apply reward shaping.

        Args:
            reward: Original reward
            action: Action taken
            info: Step information

        Returns:
            Shaped reward
        """
        shaped = reward

        # SOC target bonus
        soc = info.get("soc", 0.5)
        soc_distance = abs(soc - self.soc_target)
        shaped += self.soc_bonus_weight * (1.0 - soc_distance)

        # Activity bonus (encourage participation)
        if not self.env.use_discrete_actions:
            if abs(action[0]) > 0.1:
                shaped += self.activity_bonus

        # Peak trading bonus
        hour = info.get("hour", 12)
        if info.get("trade_executed", False) and hour in [18, 19, 20, 21]:
            shaped += self.peak_trading_bonus

        return shaped


class EpisodeMonitor(gym.Wrapper):
    """Monitor and log episode statistics.

    Tracks episode rewards, lengths, and other metrics
    for logging and analysis.
    """

    def __init__(
        self,
        env: gym.Env,
        max_history: int = 100,
    ):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
            max_history: Maximum number of episodes to keep in history
        """
        super().__init__(env)
        self.max_history = max_history

        # Current episode
        self.episode_reward = 0.0
        self.episode_length = 0
        self.episode_profit = 0.0
        self.episode_trades = 0

        # History
        self.episode_rewards: deque = deque(maxlen=max_history)
        self.episode_lengths: deque = deque(maxlen=max_history)
        self.episode_profits: deque = deque(maxlen=max_history)
        self.episode_trades_history: deque = deque(maxlen=max_history)
        self.total_episodes = 0

    def step(self, action):
        """Take step and update statistics."""
        obs, reward, terminated, truncated, info = self.env.step(action)

        self.episode_reward += reward
        self.episode_length += 1
        self.episode_profit = info.get("episode_profit", 0.0)
        self.episode_trades = info.get("num_trades", 0)

        if terminated or truncated:
            self._on_episode_end()

        return obs, reward, terminated, truncated, info

    def reset(self, **kwargs):
        """Reset environment and episode statistics."""
        self.episode_reward = 0.0
        self.episode_length = 0
        self.episode_profit = 0.0
        self.episode_trades = 0
        return self.env.reset(**kwargs)

    def _on_episode_end(self):
        """Handle episode completion."""
        self.episode_rewards.append(self.episode_reward)
        self.episode_lengths.append(self.episode_length)
        self.episode_profits.append(self.episode_profit)
        self.episode_trades_history.append(self.episode_trades)
        self.total_episodes += 1

        logger.info(
            f"Episode {self.total_episodes}: "
            f"reward={self.episode_reward:.2f}, "
            f"length={self.episode_length}, "
            f"profit=₹{self.episode_profit:.2f}, "
            f"trades={self.episode_trades}"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get episode statistics.

        Returns:
            Dictionary of statistics
        """
        if not self.episode_rewards:
            return {}

        return {
            "total_episodes": self.total_episodes,
            "mean_reward": np.mean(self.episode_rewards),
            "std_reward": np.std(self.episode_rewards),
            "min_reward": np.min(self.episode_rewards),
            "max_reward": np.max(self.episode_rewards),
            "mean_length": np.mean(self.episode_lengths),
            "mean_profit": np.mean(self.episode_profits),
            "std_profit": np.std(self.episode_profits),
            "mean_trades": np.mean(self.episode_trades_history),
            "profitable_ratio": np.mean([p > 0 for p in self.episode_profits]),
        }


class TimeLimit(gym.Wrapper):
    """Limit episode length.

    Truncates episodes after a maximum number of steps.
    """

    def __init__(
        self,
        env: gym.Env,
        max_episode_steps: int = 24,
    ):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
            max_episode_steps: Maximum steps per episode
        """
        super().__init__(env)
        self.max_episode_steps = max_episode_steps
        self._elapsed_steps = 0

    def step(self, action):
        """Take step and check time limit."""
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._elapsed_steps += 1

        if self._elapsed_steps >= self.max_episode_steps:
            truncated = True

        return obs, reward, terminated, truncated, info

    def reset(self, **kwargs):
        """Reset environment and step counter."""
        self._elapsed_steps = 0
        return self.env.reset(**kwargs)


class RecordEpisode(gym.Wrapper):
    """Record episode data for replay and analysis."""

    def __init__(self, env: gym.Env):
        """Initialize wrapper.

        Args:
            env: Environment to wrap
        """
        super().__init__(env)
        self.observations: List[np.ndarray] = []
        self.actions: List[Any] = []
        self.rewards: List[float] = []
        self.infos: List[Dict[str, Any]] = []
        self.terminated = False
        self.truncated = False

    def step(self, action):
        """Record step data."""
        obs, reward, terminated, truncated, info = self.env.step(action)

        self.observations.append(obs.copy())
        self.actions.append(action)
        self.rewards.append(reward)
        self.infos.append(info.copy())
        self.terminated = terminated
        self.truncated = truncated

        return obs, reward, terminated, truncated, info

    def reset(self, **kwargs):
        """Reset recording."""
        self.observations = []
        self.actions = []
        self.rewards = []
        self.infos = []
        self.terminated = False
        self.truncated = False

        obs, info = self.env.reset(**kwargs)
        self.observations.append(obs.copy())
        self.infos.append(info.copy())
        return obs, info

    def get_episode_data(self) -> Dict[str, Any]:
        """Get recorded episode data.

        Returns:
            Dictionary containing episode data
        """
        return {
            "observations": np.array(self.observations),
            "actions": self.actions,
            "rewards": np.array(self.rewards),
            "infos": self.infos,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "total_reward": sum(self.rewards),
            "length": len(self.rewards),
        }


def make_env(
    config=None,
    normalize_obs: bool = True,
    normalize_reward: bool = True,
    frame_stack: int = 0,
    reward_shaping: bool = False,
    monitor: bool = True,
    seed: Optional[int] = None,
) -> gym.Env:
    """Create wrapped V2G trading environment.

    Args:
        config: Environment configuration
        normalize_obs: Whether to normalize observations
        normalize_reward: Whether to normalize rewards
        frame_stack: Number of frames to stack (0 = no stacking)
        reward_shaping: Whether to apply reward shaping
        monitor: Whether to add episode monitor
        seed: Random seed

    Returns:
        Wrapped environment
    """
    from .environment import V2GTradingEnv, EnvironmentConfig

    config = config or EnvironmentConfig(seed=seed)
    env = V2GTradingEnv(config)

    # Apply wrappers in order
    if monitor:
        env = EpisodeMonitor(env)

    if normalize_obs:
        env = NormalizeObservation(env)

    if normalize_reward:
        env = NormalizeReward(env)

    if reward_shaping:
        env = RewardShaping(env)

    if frame_stack > 0:
        env = FrameStack(env, num_stack=frame_stack)

    return env


def make_vec_env(
    num_envs: int = 4,
    config=None,
    normalize_obs: bool = True,
    normalize_reward: bool = True,
    seed: Optional[int] = None,
) -> List[gym.Env]:
    """Create multiple wrapped environments.

    Args:
        num_envs: Number of environments
        config: Environment configuration
        normalize_obs: Whether to normalize observations
        normalize_reward: Whether to normalize rewards
        seed: Base random seed

    Returns:
        List of wrapped environments
    """
    envs = []
    for i in range(num_envs):
        env_seed = seed + i if seed is not None else None
        env = make_env(
            config=config,
            normalize_obs=normalize_obs,
            normalize_reward=normalize_reward,
            seed=env_seed,
        )
        envs.append(env)
    return envs
