"""Backtesting framework for V2G Trading Agent.

Provides comprehensive backtesting capabilities:
- Historical data replay
- Performance metrics calculation
- Benchmark comparisons
- Visualization and reporting
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a single trade."""
    step: int
    hour: int
    action_type: str  # "buy", "sell", "hold"
    quantity: float
    price: float
    profit: float
    soc_before: float
    soc_after: float
    market_price: float


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    # Episode results
    total_profit: float
    total_reward: float
    num_trades: int
    win_rate: float

    # Performance metrics
    roi: float  # Return on investment (%)
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float

    # Trade statistics
    avg_trade_profit: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float

    # Battery statistics
    final_soc: float
    avg_soc: float
    min_soc: float
    max_soc: float
    battery_health: float

    # Time series
    profit_history: List[float] = field(default_factory=list)
    soc_history: List[float] = field(default_factory=list)
    price_history: List[float] = field(default_factory=list)
    trades: List[TradeRecord] = field(default_factory=list)

    # Metadata
    initial_balance: float = 1000.0
    episode_length: int = 24


@dataclass
class BenchmarkResult:
    """Results from benchmark strategy."""
    name: str
    total_profit: float
    roi: float
    num_trades: int
    win_rate: float


class Backtester:
    """Backtesting engine for V2G trading strategies.

    Runs trained agents against historical or simulated data
    and computes comprehensive performance metrics.
    """

    def __init__(
        self,
        env,
        initial_balance: float = 1000.0,
    ):
        """Initialize backtester.

        Args:
            env: V2GTradingEnv instance
            initial_balance: Initial capital for ROI calculation
        """
        self.env = env
        self.initial_balance = initial_balance

    def run_episode(
        self,
        policy: Callable,
        seed: Optional[int] = None,
        deterministic: bool = True,
    ) -> BacktestResult:
        """Run a single backtest episode.

        Args:
            policy: Policy function (obs -> action)
            seed: Random seed
            deterministic: Use deterministic actions

        Returns:
            BacktestResult with all metrics
        """
        obs, info = self.env.reset(seed=seed)

        # Initialize tracking
        profit_history = [0.0]
        soc_history = [info["soc"]]
        price_history = [info["market_price"]]
        trades: List[TradeRecord] = []
        rewards = []

        total_reward = 0.0
        step = 0

        terminated = False
        truncated = False

        while not (terminated or truncated):
            # Get action
            action = policy(obs)

            # Record state before action
            soc_before = info["soc"]
            market_price = info["market_price"]

            # Step
            obs, reward, terminated, truncated, info = self.env.step(action)
            total_reward += reward
            rewards.append(reward)
            step += 1

            # Record trade if executed
            if info.get("trade_executed", False):
                # Determine trade type
                if hasattr(self.env, "use_discrete_actions") and self.env.use_discrete_actions:
                    qty_idx = action[0]
                    qty = self.env.quantity_levels[qty_idx]
                else:
                    qty = action[0]

                trade_type = "buy" if qty > 0 else "sell"

                trades.append(TradeRecord(
                    step=step,
                    hour=info["hour"],
                    action_type=trade_type,
                    quantity=abs(qty),
                    price=info.get("market_price", market_price),
                    profit=info.get("trade_profit", 0.0),
                    soc_before=soc_before,
                    soc_after=info["soc"],
                    market_price=market_price,
                ))

            # Record history
            profit_history.append(info["episode_profit"])
            soc_history.append(info["soc"])
            price_history.append(info["market_price"])

        # Calculate metrics
        return self._calculate_metrics(
            total_profit=info["episode_profit"],
            total_reward=total_reward,
            trades=trades,
            profit_history=profit_history,
            soc_history=soc_history,
            price_history=price_history,
            final_soc=info["soc"],
            battery_health=info["battery_health"],
            episode_length=step,
        )

    def run_multiple_episodes(
        self,
        policy: Callable,
        num_episodes: int = 100,
        seeds: Optional[List[int]] = None,
        deterministic: bool = True,
    ) -> List[BacktestResult]:
        """Run multiple backtest episodes.

        Args:
            policy: Policy function
            num_episodes: Number of episodes
            seeds: Optional list of seeds
            deterministic: Use deterministic actions

        Returns:
            List of BacktestResult
        """
        if seeds is None:
            seeds = list(range(num_episodes))

        results = []
        for i, seed in enumerate(seeds[:num_episodes]):
            if (i + 1) % 10 == 0:
                logger.info(f"Backtesting episode {i + 1}/{num_episodes}")

            result = self.run_episode(policy, seed=seed, deterministic=deterministic)
            results.append(result)

        return results

    def _calculate_metrics(
        self,
        total_profit: float,
        total_reward: float,
        trades: List[TradeRecord],
        profit_history: List[float],
        soc_history: List[float],
        price_history: List[float],
        final_soc: float,
        battery_health: float,
        episode_length: int,
    ) -> BacktestResult:
        """Calculate comprehensive performance metrics.

        Args:
            Various episode data

        Returns:
            BacktestResult with all metrics
        """
        # Trade statistics
        num_trades = len(trades)
        trade_profits = [t.profit for t in trades]
        wins = [p for p in trade_profits if p > 0]
        losses = [p for p in trade_profits if p < 0]

        win_rate = len(wins) / num_trades if num_trades > 0 else 0.0
        avg_trade_profit = np.mean(trade_profits) if trade_profits else 0.0
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0

        # Profit factor
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 1.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # ROI
        roi = (total_profit / self.initial_balance) * 100

        # Sharpe ratio (simplified - using profit history)
        if len(profit_history) > 1:
            returns = np.diff(profit_history)
            sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(24)  # Annualized for 24h
        else:
            sharpe = 0.0

        # Max drawdown
        cumulative = np.array(profit_history)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0

        # Battery statistics
        avg_soc = np.mean(soc_history)
        min_soc = np.min(soc_history)
        max_soc = np.max(soc_history)

        return BacktestResult(
            total_profit=total_profit,
            total_reward=total_reward,
            num_trades=num_trades,
            win_rate=win_rate,
            roi=roi,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            avg_trade_profit=avg_trade_profit,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            final_soc=final_soc,
            avg_soc=avg_soc,
            min_soc=min_soc,
            max_soc=max_soc,
            battery_health=battery_health,
            profit_history=profit_history,
            soc_history=soc_history,
            price_history=price_history,
            trades=trades,
            initial_balance=self.initial_balance,
            episode_length=episode_length,
        )

    def run_benchmark(
        self,
        strategy: str = "buy_hold",
        num_episodes: int = 100,
        seeds: Optional[List[int]] = None,
    ) -> BenchmarkResult:
        """Run benchmark strategy.

        Args:
            strategy: Benchmark strategy name
            num_episodes: Number of episodes
            seeds: Optional seeds

        Returns:
            BenchmarkResult
        """
        strategies = {
            "buy_hold": self._buy_hold_policy,
            "sell_hold": self._sell_hold_policy,
            "random": self._random_policy,
            "peak_arbitrage": self._peak_arbitrage_policy,
            "threshold": self._threshold_policy,
        }

        if strategy not in strategies:
            raise ValueError(f"Unknown strategy: {strategy}. Available: {list(strategies.keys())}")

        policy = strategies[strategy]
        results = self.run_multiple_episodes(
            policy=policy,
            num_episodes=num_episodes,
            seeds=seeds,
        )

        profits = [r.total_profit for r in results]
        trades = [r.num_trades for r in results]
        win_rates = [r.win_rate for r in results]

        return BenchmarkResult(
            name=strategy,
            total_profit=np.mean(profits),
            roi=np.mean(profits) / self.initial_balance * 100,
            num_trades=int(np.mean(trades)),
            win_rate=np.mean(win_rates),
        )

    def _buy_hold_policy(self, obs) -> np.ndarray:
        """Buy and hold strategy - charge fully then do nothing."""
        soc = obs[0]
        if soc < 0.9:
            return np.array([1.0, 0.5], dtype=np.float32)  # Buy
        return np.array([0.0, 0.5], dtype=np.float32)  # Hold

    def _sell_hold_policy(self, obs) -> np.ndarray:
        """Sell and hold strategy - discharge fully then do nothing."""
        soc = obs[0]
        if soc > 0.3:
            return np.array([-1.0, 0.5], dtype=np.float32)  # Sell
        return np.array([0.0, 0.5], dtype=np.float32)  # Hold

    def _random_policy(self, obs) -> np.ndarray:
        """Random trading strategy."""
        return np.random.uniform([-1, 0], [1, 1]).astype(np.float32)

    def _peak_arbitrage_policy(self, obs) -> np.ndarray:
        """Simple peak/off-peak arbitrage.

        Buy during off-peak (night), sell during peak (evening).
        """
        hour = int(obs[1] * 23)  # Denormalize hour

        soc = obs[0]

        # Off-peak hours (0-6): Buy if SOC low
        if 0 <= hour <= 6 and soc < 0.8:
            return np.array([0.8, 0.6], dtype=np.float32)

        # Peak hours (18-22): Sell if SOC high
        elif 18 <= hour <= 22 and soc > 0.4:
            return np.array([-0.8, 0.6], dtype=np.float32)

        return np.array([0.0, 0.5], dtype=np.float32)

    def _threshold_policy(self, obs) -> np.ndarray:
        """Price threshold strategy.

        Buy when price below average, sell when above.
        """
        # Get current price (normalized)
        current_price = obs[53]  # Index for current price

        # Get price forecast
        price_forecast = obs[29:53]
        avg_price = np.mean(price_forecast)

        soc = obs[0]

        if current_price < avg_price * 0.9 and soc < 0.8:
            return np.array([0.7, 0.5], dtype=np.float32)
        elif current_price > avg_price * 1.1 and soc > 0.3:
            return np.array([-0.7, 0.5], dtype=np.float32)

        return np.array([0.0, 0.5], dtype=np.float32)


class BacktestReporter:
    """Generate backtest reports and visualizations."""

    def __init__(self, results: List[BacktestResult]):
        """Initialize reporter.

        Args:
            results: List of backtest results
        """
        self.results = results

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics across all episodes.

        Returns:
            Dictionary of statistics
        """
        profits = [r.total_profit for r in self.results]
        rois = [r.roi for r in self.results]
        sharpes = [r.sharpe_ratio for r in self.results]
        win_rates = [r.win_rate for r in self.results]
        trades = [r.num_trades for r in self.results]
        drawdowns = [r.max_drawdown for r in self.results]

        return {
            "num_episodes": len(self.results),
            "profit": {
                "mean": np.mean(profits),
                "std": np.std(profits),
                "min": np.min(profits),
                "max": np.max(profits),
                "median": np.median(profits),
            },
            "roi": {
                "mean": np.mean(rois),
                "std": np.std(rois),
                "min": np.min(rois),
                "max": np.max(rois),
            },
            "sharpe_ratio": {
                "mean": np.mean(sharpes),
                "std": np.std(sharpes),
            },
            "win_rate": {
                "mean": np.mean(win_rates),
                "std": np.std(win_rates),
            },
            "trades_per_episode": {
                "mean": np.mean(trades),
                "std": np.std(trades),
            },
            "max_drawdown": {
                "mean": np.mean(drawdowns),
                "max": np.max(drawdowns),
            },
            "profitable_episodes": sum(1 for p in profits if p > 0) / len(profits),
        }

    def print_report(self):
        """Print formatted backtest report."""
        stats = self.get_summary_stats()

        print("\n" + "=" * 70)
        print("BACKTEST REPORT")
        print("=" * 70)

        print(f"\nEpisodes: {stats['num_episodes']}")
        print(f"Profitable Episodes: {stats['profitable_episodes']*100:.1f}%")

        print("\n--- Profit Statistics ---")
        print(f"Mean:   ₹{stats['profit']['mean']:>10.2f}")
        print(f"Std:    ₹{stats['profit']['std']:>10.2f}")
        print(f"Min:    ₹{stats['profit']['min']:>10.2f}")
        print(f"Max:    ₹{stats['profit']['max']:>10.2f}")
        print(f"Median: ₹{stats['profit']['median']:>10.2f}")

        print("\n--- Return on Investment ---")
        print(f"Mean ROI:  {stats['roi']['mean']:>8.2f}%")
        print(f"Std ROI:   {stats['roi']['std']:>8.2f}%")
        print(f"Min ROI:   {stats['roi']['min']:>8.2f}%")
        print(f"Max ROI:   {stats['roi']['max']:>8.2f}%")

        print("\n--- Risk Metrics ---")
        print(f"Sharpe Ratio:  {stats['sharpe_ratio']['mean']:>8.2f} ± {stats['sharpe_ratio']['std']:.2f}")
        print(f"Win Rate:      {stats['win_rate']['mean']*100:>8.1f}% ± {stats['win_rate']['std']*100:.1f}%")
        print(f"Max Drawdown:  ₹{stats['max_drawdown']['max']:>8.2f} (worst)")
        print(f"Avg Drawdown:  ₹{stats['max_drawdown']['mean']:>8.2f}")

        print("\n--- Trading Activity ---")
        print(f"Trades/Episode: {stats['trades_per_episode']['mean']:.1f} ± {stats['trades_per_episode']['std']:.1f}")

        # Target check
        print("\n--- Target Performance Check ---")
        roi_target = 15.0
        roi_achieved = stats['roi']['mean']
        status = "✓ PASS" if roi_achieved >= roi_target else "✗ FAIL"
        print(f"ROI Target: {roi_target}% | Achieved: {roi_achieved:.1f}% | {status}")

        print("=" * 70 + "\n")

    def plot_results(
        self,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot backtest results.

        Args:
            save_path: Optional path to save figure
            show: Whether to display plot
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available for plotting")
            return

        fig, axes = plt.subplots(2, 3, figsize=(15, 8))

        # 1. Profit distribution
        profits = [r.total_profit for r in self.results]
        axes[0, 0].hist(profits, bins=30, alpha=0.7, color='blue', edgecolor='black')
        axes[0, 0].axvline(np.mean(profits), color='red', linestyle='--', label=f'Mean: ₹{np.mean(profits):.2f}')
        axes[0, 0].axvline(0, color='black', linestyle='-', alpha=0.5)
        axes[0, 0].set_xlabel('Profit (₹)')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('Profit Distribution')
        axes[0, 0].legend()

        # 2. ROI distribution
        rois = [r.roi for r in self.results]
        axes[0, 1].hist(rois, bins=30, alpha=0.7, color='green', edgecolor='black')
        axes[0, 1].axvline(15, color='red', linestyle='--', label='Target: 15%')
        axes[0, 1].axvline(np.mean(rois), color='orange', linestyle='--', label=f'Mean: {np.mean(rois):.1f}%')
        axes[0, 1].set_xlabel('ROI (%)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title('ROI Distribution')
        axes[0, 1].legend()

        # 3. Win rate vs Trades
        win_rates = [r.win_rate for r in self.results]
        trades = [r.num_trades for r in self.results]
        axes[0, 2].scatter(trades, [w*100 for w in win_rates], alpha=0.5)
        axes[0, 2].set_xlabel('Number of Trades')
        axes[0, 2].set_ylabel('Win Rate (%)')
        axes[0, 2].set_title('Win Rate vs Trading Activity')
        axes[0, 2].axhline(50, color='red', linestyle='--', alpha=0.5)

        # 4. Sharpe ratio distribution
        sharpes = [r.sharpe_ratio for r in self.results]
        axes[1, 0].hist(sharpes, bins=30, alpha=0.7, color='purple', edgecolor='black')
        axes[1, 0].axvline(1.0, color='red', linestyle='--', label='Target: 1.0')
        axes[1, 0].set_xlabel('Sharpe Ratio')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].set_title('Sharpe Ratio Distribution')
        axes[1, 0].legend()

        # 5. Example profit trajectory
        best_idx = np.argmax(profits)
        worst_idx = np.argmin(profits)
        axes[1, 1].plot(self.results[best_idx].profit_history, 'g-', label='Best Episode', linewidth=2)
        axes[1, 1].plot(self.results[worst_idx].profit_history, 'r-', label='Worst Episode', linewidth=2)
        axes[1, 1].axhline(0, color='black', linestyle='-', alpha=0.3)
        axes[1, 1].set_xlabel('Step')
        axes[1, 1].set_ylabel('Cumulative Profit (₹)')
        axes[1, 1].set_title('Profit Trajectories')
        axes[1, 1].legend()

        # 6. Max drawdown vs Profit
        drawdowns = [r.max_drawdown for r in self.results]
        axes[1, 2].scatter(drawdowns, profits, alpha=0.5)
        axes[1, 2].set_xlabel('Max Drawdown (₹)')
        axes[1, 2].set_ylabel('Total Profit (₹)')
        axes[1, 2].set_title('Drawdown vs Profit')

        plt.suptitle('V2G Trading Agent Backtest Results', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Backtest plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def save_results(self, path: str):
        """Save results to JSON file.

        Args:
            path: Output file path
        """
        stats = self.get_summary_stats()

        # Convert to serializable format
        output = {
            "summary": stats,
            "episodes": [
                {
                    "profit": r.total_profit,
                    "roi": r.roi,
                    "sharpe": r.sharpe_ratio,
                    "win_rate": r.win_rate,
                    "num_trades": r.num_trades,
                    "max_drawdown": r.max_drawdown,
                    "final_soc": r.final_soc,
                    "battery_health": r.battery_health,
                }
                for r in self.results
            ],
        }

        with open(path, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Results saved to {path}")


def backtest_trained_model(
    model_path: str,
    num_episodes: int = 100,
    seed: int = 42,
    compare_benchmarks: bool = True,
) -> BacktestReporter:
    """Convenience function to backtest a trained model.

    Args:
        model_path: Path to saved model
        num_episodes: Number of backtest episodes
        seed: Random seed
        compare_benchmarks: Whether to run benchmark comparisons

    Returns:
        BacktestReporter with results
    """
    from stable_baselines3 import PPO
    from .environment import V2GTradingEnv

    # Load model
    logger.info(f"Loading model from {model_path}")
    model = PPO.load(model_path)

    # Create environment
    env = V2GTradingEnv()

    # Create backtester
    backtester = Backtester(env)

    # Define policy function
    def policy(obs):
        action, _ = model.predict(obs, deterministic=True)
        return action

    # Run backtest
    logger.info(f"Running {num_episodes} backtest episodes...")
    results = backtester.run_multiple_episodes(
        policy=policy,
        num_episodes=num_episodes,
        seeds=list(range(seed, seed + num_episodes)),
    )

    # Create reporter
    reporter = BacktestReporter(results)
    reporter.print_report()

    # Compare with benchmarks
    if compare_benchmarks:
        print("\n--- Benchmark Comparisons ---")
        for strategy in ["random", "peak_arbitrage", "threshold"]:
            benchmark = backtester.run_benchmark(strategy, num_episodes=num_episodes)
            print(f"{strategy:20s}: ROI = {benchmark.roi:>6.1f}%, "
                  f"Win Rate = {benchmark.win_rate*100:.1f}%")

    return reporter
