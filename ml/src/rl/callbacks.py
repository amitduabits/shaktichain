"""Custom callbacks for V2G Trading Agent training.

Implements specialized callbacks for:
- Evaluation with custom metrics (daily profit, ROI)
- TensorBoard logging with detailed metrics
- Curriculum learning progress tracking
- Checkpoint saving with performance-based selection
"""

import os
import numpy as np
from typing import Dict, Any, Optional, List, Union, Callable
from pathlib import Path
import json
import logging

from stable_baselines3.common.callbacks import (
    BaseCallback,
    EvalCallback,
    CheckpointCallback,
    CallbackList,
)
from stable_baselines3.common.vec_env import VecEnv, sync_envs_normalization

logger = logging.getLogger(__name__)


class TradingMetricsCallback(BaseCallback):
    """Callback for logging detailed trading metrics.

    Tracks and logs:
    - Episode profits and returns
    - Trade statistics
    - Battery utilization
    - Win rate and Sharpe ratio
    """

    def __init__(
        self,
        log_freq: int = 1000,
        verbose: int = 0,
    ):
        """Initialize callback.

        Args:
            log_freq: Logging frequency in timesteps
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.log_freq = log_freq

        # Metrics storage
        self.episode_profits: List[float] = []
        self.episode_rewards: List[float] = []
        self.episode_trades: List[int] = []
        self.episode_lengths: List[int] = []
        self.final_socs: List[float] = []
        self.battery_healths: List[float] = []

        self._current_episode_reward = 0.0

    def _on_step(self) -> bool:
        """Called at each step."""
        # Accumulate reward
        self._current_episode_reward += self.locals.get("rewards", [0])[0]

        # Check for episode end
        dones = self.locals.get("dones", [False])
        infos = self.locals.get("infos", [{}])

        for done, info in zip(dones, infos):
            if done:
                self.episode_profits.append(info.get("episode_profit", 0.0))
                self.episode_rewards.append(self._current_episode_reward)
                self.episode_trades.append(info.get("num_trades", 0))
                self.episode_lengths.append(info.get("episode_length", 24))
                self.final_socs.append(info.get("soc", 0.5))
                self.battery_healths.append(info.get("battery_health", 1.0))

                self._current_episode_reward = 0.0

        # Log metrics periodically
        if self.num_timesteps % self.log_freq == 0 and self.episode_profits:
            self._log_metrics()

        return True

    def _log_metrics(self):
        """Log trading metrics to TensorBoard."""
        n = min(100, len(self.episode_profits))  # Last 100 episodes
        recent_profits = self.episode_profits[-n:]
        recent_rewards = self.episode_rewards[-n:]
        recent_trades = self.episode_trades[-n:]

        # Calculate metrics
        avg_profit = np.mean(recent_profits)
        std_profit = np.std(recent_profits)
        win_rate = np.mean([p > 0 for p in recent_profits])

        # Sharpe-like ratio (profit / std)
        sharpe = avg_profit / (std_profit + 1e-8)

        # ROI approximation (profit / initial balance)
        roi = avg_profit / 1000.0 * 100  # Assuming 1000 initial balance

        # Log to TensorBoard
        self.logger.record("trading/avg_profit", avg_profit)
        self.logger.record("trading/std_profit", std_profit)
        self.logger.record("trading/win_rate", win_rate)
        self.logger.record("trading/sharpe_ratio", sharpe)
        self.logger.record("trading/roi_percent", roi)
        self.logger.record("trading/avg_trades", np.mean(recent_trades))
        self.logger.record("trading/avg_reward", np.mean(recent_rewards))
        self.logger.record("trading/total_episodes", len(self.episode_profits))

        if self.final_socs:
            self.logger.record("trading/avg_final_soc", np.mean(self.final_socs[-n:]))
        if self.battery_healths:
            self.logger.record("trading/avg_battery_health", np.mean(self.battery_healths[-n:]))

        if self.verbose > 0:
            print(f"\n[Trading Metrics @ {self.num_timesteps}]")
            print(f"  Avg Profit: ₹{avg_profit:.2f} ± {std_profit:.2f}")
            print(f"  Win Rate: {win_rate*100:.1f}%")
            print(f"  ROI: {roi:.1f}%")
            print(f"  Sharpe: {sharpe:.2f}")

    def get_metrics(self) -> Dict[str, float]:
        """Get current metrics.

        Returns:
            Dictionary of metrics
        """
        if not self.episode_profits:
            return {}

        n = min(100, len(self.episode_profits))
        recent_profits = self.episode_profits[-n:]

        return {
            "avg_profit": np.mean(recent_profits),
            "std_profit": np.std(recent_profits),
            "win_rate": np.mean([p > 0 for p in recent_profits]),
            "sharpe": np.mean(recent_profits) / (np.std(recent_profits) + 1e-8),
            "roi": np.mean(recent_profits) / 1000.0 * 100,
            "total_episodes": len(self.episode_profits),
        }


class CurriculumCallback(BaseCallback):
    """Callback for curriculum learning progress tracking.

    Monitors curriculum stage progression and logs
    stage-specific metrics.
    """

    def __init__(
        self,
        scheduler,
        log_freq: int = 5000,
        verbose: int = 0,
    ):
        """Initialize callback.

        Args:
            scheduler: CurriculumScheduler instance
            log_freq: Logging frequency
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.scheduler = scheduler
        self.log_freq = log_freq
        self.previous_stage = 0

    def _on_step(self) -> bool:
        """Called at each step."""
        # Check for stage change
        if self.scheduler.current_stage_idx != self.previous_stage:
            self._on_stage_change()
            self.previous_stage = self.scheduler.current_stage_idx

        # Log curriculum status periodically
        if self.num_timesteps % self.log_freq == 0:
            self._log_curriculum_status()

        return True

    def _on_stage_change(self):
        """Handle curriculum stage change."""
        stage = self.scheduler.current_stage

        if self.verbose > 0:
            print(f"\n{'='*50}")
            print(f"CURRICULUM STAGE ADVANCED!")
            print(f"New Stage: {self.scheduler.current_stage_idx + 1} - {stage.name}")
            print(f"Description: {stage.description}")
            print(f"{'='*50}\n")

        # Log to TensorBoard
        self.logger.record("curriculum/stage", self.scheduler.current_stage_idx)
        self.logger.record("curriculum/stage_name", stage.name)

    def _log_curriculum_status(self):
        """Log curriculum status."""
        status = self.scheduler.get_status()

        self.logger.record("curriculum/stage", status["stage_idx"])
        self.logger.record("curriculum/timesteps_in_stage", status["timesteps_in_stage"])
        self.logger.record("curriculum/avg_profit", status["avg_profit"])
        self.logger.record("curriculum/threshold", status["threshold"])
        self.logger.record("curriculum/progress", status["consecutive_above"] / status["patience"])


class CustomEvalCallback(EvalCallback):
    """Extended evaluation callback with custom metrics.

    Evaluates on daily profit instead of just episode reward,
    and saves detailed evaluation results.
    """

    def __init__(
        self,
        eval_env: VecEnv,
        n_eval_episodes: int = 10,
        eval_freq: int = 50000,
        log_path: Optional[str] = None,
        best_model_save_path: Optional[str] = None,
        deterministic: bool = True,
        metric: str = "profit",  # "profit", "reward", or "roi"
        verbose: int = 1,
        **kwargs,
    ):
        """Initialize callback.

        Args:
            eval_env: Evaluation environment
            n_eval_episodes: Number of evaluation episodes
            eval_freq: Evaluation frequency in timesteps
            log_path: Path to save evaluation logs
            best_model_save_path: Path to save best model
            deterministic: Use deterministic actions
            metric: Metric for best model selection
            verbose: Verbosity level
            **kwargs: Additional arguments
        """
        super().__init__(
            eval_env=eval_env,
            n_eval_episodes=n_eval_episodes,
            eval_freq=eval_freq,
            log_path=log_path,
            best_model_save_path=best_model_save_path,
            deterministic=deterministic,
            verbose=verbose,
            **kwargs,
        )
        self.metric = metric
        self.best_metric_value = -np.inf
        self.eval_history: List[Dict[str, Any]] = []

    def _on_step(self) -> bool:
        """Called at each step."""
        if self.eval_freq > 0 and self.n_calls % self.eval_freq == 0:
            # Sync normalization if needed
            if self.model.get_vec_normalize_env() is not None:
                try:
                    sync_envs_normalization(self.training_env, self.eval_env)
                except AttributeError:
                    pass

            # Run evaluation
            eval_results = self._evaluate()

            # Log results
            self._log_eval_results(eval_results)

            # Check for best model
            metric_value = eval_results.get(f"avg_{self.metric}", eval_results.get("avg_profit", 0))

            if metric_value > self.best_metric_value:
                self.best_metric_value = metric_value

                if self.best_model_save_path is not None:
                    self.model.save(os.path.join(self.best_model_save_path, "best_model"))

                    if self.verbose > 0:
                        print(f"New best model! {self.metric}: {metric_value:.2f}")

            # Save evaluation history
            self.eval_history.append(eval_results)

        return True

    def _evaluate(self) -> Dict[str, Any]:
        """Run evaluation episodes.

        Returns:
            Dictionary of evaluation results
        """
        episode_rewards = []
        episode_profits = []
        episode_trades = []
        episode_lengths = []

        for _ in range(self.n_eval_episodes):
            obs = self.eval_env.reset()
            done = False
            episode_reward = 0.0

            while not done:
                action, _ = self.model.predict(obs, deterministic=self.deterministic)
                obs, reward, done, info = self.eval_env.step(action)
                episode_reward += reward[0]

                if done[0]:
                    episode_profits.append(info[0].get("episode_profit", 0.0))
                    episode_trades.append(info[0].get("num_trades", 0))
                    episode_lengths.append(info[0].get("episode_length", 24))

            episode_rewards.append(episode_reward)

        # Calculate ROI
        avg_profit = np.mean(episode_profits) if episode_profits else 0
        roi = avg_profit / 1000.0 * 100  # Assuming 1000 initial balance

        return {
            "timestep": self.num_timesteps,
            "avg_reward": np.mean(episode_rewards),
            "std_reward": np.std(episode_rewards),
            "avg_profit": avg_profit,
            "std_profit": np.std(episode_profits) if episode_profits else 0,
            "roi": roi,
            "avg_trades": np.mean(episode_trades) if episode_trades else 0,
            "win_rate": np.mean([p > 0 for p in episode_profits]) if episode_profits else 0,
        }

    def _log_eval_results(self, results: Dict[str, Any]):
        """Log evaluation results."""
        self.logger.record("eval/avg_reward", results["avg_reward"])
        self.logger.record("eval/std_reward", results["std_reward"])
        self.logger.record("eval/avg_profit", results["avg_profit"])
        self.logger.record("eval/std_profit", results["std_profit"])
        self.logger.record("eval/roi", results["roi"])
        self.logger.record("eval/avg_trades", results["avg_trades"])
        self.logger.record("eval/win_rate", results["win_rate"])

        if self.verbose > 0:
            print(f"\n[Evaluation @ {self.num_timesteps}]")
            print(f"  Avg Reward: {results['avg_reward']:.2f} ± {results['std_reward']:.2f}")
            print(f"  Avg Profit: ₹{results['avg_profit']:.2f} ± {results['std_profit']:.2f}")
            print(f"  ROI: {results['roi']:.1f}%")
            print(f"  Win Rate: {results['win_rate']*100:.1f}%")


class ProgressCallback(BaseCallback):
    """Callback for tracking and displaying training progress.

    Shows real-time progress with key metrics.
    """

    def __init__(
        self,
        total_timesteps: int,
        log_freq: int = 10000,
        verbose: int = 1,
    ):
        """Initialize callback.

        Args:
            total_timesteps: Total training timesteps
            log_freq: Logging frequency
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.total_timesteps = total_timesteps
        self.log_freq = log_freq

    def _on_step(self) -> bool:
        """Called at each step."""
        if self.num_timesteps % self.log_freq == 0:
            progress = self.num_timesteps / self.total_timesteps * 100
            fps = int(self.num_timesteps / (self.locals.get("time_elapsed", 1) + 1e-8))

            if self.verbose > 0:
                print(f"Progress: {progress:.1f}% | Timesteps: {self.num_timesteps:,} | FPS: {fps}")

        return True


class SaveOnBestTrainingRewardCallback(BaseCallback):
    """Callback to save model when training reward improves.

    Alternative to evaluation-based saving when evaluation
    is expensive.
    """

    def __init__(
        self,
        check_freq: int = 10000,
        log_dir: str = "./logs/",
        verbose: int = 1,
    ):
        """Initialize callback.

        Args:
            check_freq: Check frequency
            log_dir: Directory to save model
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.check_freq = check_freq
        self.log_dir = log_dir
        self.save_path = os.path.join(log_dir, "best_training_model")
        self.best_mean_reward = -np.inf

    def _on_step(self) -> bool:
        """Called at each step."""
        if self.n_calls % self.check_freq == 0:
            # Get recent rewards from logger
            if len(self.model.ep_info_buffer) > 0:
                mean_reward = np.mean([ep_info["r"] for ep_info in self.model.ep_info_buffer])

                if mean_reward > self.best_mean_reward:
                    self.best_mean_reward = mean_reward

                    if self.verbose > 0:
                        print(f"New best training reward: {mean_reward:.2f}")
                        print(f"Saving model to {self.save_path}")

                    self.model.save(self.save_path)

        return True


def create_training_callbacks(
    eval_env: VecEnv,
    log_dir: str = "./logs/",
    eval_freq: int = 50000,
    checkpoint_freq: int = 100000,
    n_eval_episodes: int = 10,
    total_timesteps: int = 10000000,
    curriculum_scheduler=None,
    verbose: int = 1,
) -> CallbackList:
    """Create standard set of training callbacks.

    Args:
        eval_env: Evaluation environment
        log_dir: Logging directory
        eval_freq: Evaluation frequency
        checkpoint_freq: Checkpoint save frequency
        n_eval_episodes: Number of evaluation episodes
        total_timesteps: Total training timesteps
        curriculum_scheduler: Optional curriculum scheduler
        verbose: Verbosity level

    Returns:
        CallbackList with all callbacks
    """
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(os.path.join(log_dir, "checkpoints"), exist_ok=True)
    os.makedirs(os.path.join(log_dir, "best_model"), exist_ok=True)

    callbacks = []

    # Trading metrics
    callbacks.append(TradingMetricsCallback(
        log_freq=5000,
        verbose=verbose,
    ))

    # Evaluation
    callbacks.append(CustomEvalCallback(
        eval_env=eval_env,
        n_eval_episodes=n_eval_episodes,
        eval_freq=eval_freq,
        log_path=os.path.join(log_dir, "eval"),
        best_model_save_path=os.path.join(log_dir, "best_model"),
        deterministic=True,
        metric="profit",
        verbose=verbose,
    ))

    # Checkpoints
    callbacks.append(CheckpointCallback(
        save_freq=checkpoint_freq,
        save_path=os.path.join(log_dir, "checkpoints"),
        name_prefix="ppo_v2g",
        verbose=verbose,
    ))

    # Progress
    callbacks.append(ProgressCallback(
        total_timesteps=total_timesteps,
        log_freq=10000,
        verbose=verbose,
    ))

    # Curriculum (if provided)
    if curriculum_scheduler is not None:
        callbacks.append(CurriculumCallback(
            scheduler=curriculum_scheduler,
            log_freq=5000,
            verbose=verbose,
        ))

    return CallbackList(callbacks)
