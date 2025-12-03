"""Visualization tools for V2G Trading Environment.

Provides comprehensive visualization utilities for testing and analyzing
the RL environment behavior, agent policies, and trading performance.
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EpisodeData:
    """Container for episode data."""
    soc_history: List[float]
    price_history: List[float]
    action_history: List[Tuple[float, float]]
    reward_history: List[float]
    profit_history: List[float]
    trade_history: List[Dict[str, Any]]
    info_history: List[Dict[str, Any]]
    total_reward: float
    total_profit: float
    final_soc: float
    num_trades: int


class EnvironmentVisualizer:
    """Visualization tools for V2G Trading Environment.

    Provides methods for:
    - Episode trajectory visualization
    - Trading action analysis
    - Performance metrics plotting
    - Interactive dashboard generation
    """

    def __init__(self, figsize: Tuple[int, int] = (14, 10)):
        """Initialize visualizer.

        Args:
            figsize: Default figure size for plots
        """
        self.figsize = figsize
        self.episodes: List[EpisodeData] = []

    def record_episode(
        self,
        env,
        policy: Optional[callable] = None,
        seed: Optional[int] = None,
    ) -> EpisodeData:
        """Record a full episode for visualization.

        Args:
            env: V2GTradingEnv instance
            policy: Optional policy function (obs -> action)
            seed: Random seed for reproducibility

        Returns:
            EpisodeData containing full episode trajectory
        """
        obs, info = env.reset(seed=seed)

        soc_history = [info["soc"]]
        price_history = [info["market_price"]]
        action_history = []
        reward_history = []
        profit_history = [0.0]
        info_history = [info]
        trade_history = []

        terminated = False
        truncated = False
        total_reward = 0.0

        while not (terminated or truncated):
            # Get action
            if policy is not None:
                action = policy(obs)
            else:
                action = env.action_space.sample()

            # Step environment
            obs, reward, terminated, truncated, info = env.step(action)

            # Record data
            if env.use_discrete_actions:
                qty_idx, price_idx = action
                qty = env.quantity_levels[qty_idx]
                price_agg = 0.5 + env.price_levels[price_idx]
                action_history.append((qty, price_agg))
            else:
                action_history.append((float(action[0]), float(action[1])))

            soc_history.append(info["soc"])
            price_history.append(info["market_price"])
            reward_history.append(reward)
            profit_history.append(info["episode_profit"])
            info_history.append(info)
            total_reward += reward

            # Record trades
            if info.get("trade_executed", False):
                trade_history.append({
                    "step": len(action_history),
                    "hour": info["hour"],
                    "profit": info.get("trade_profit", 0),
                })

        episode_data = EpisodeData(
            soc_history=soc_history,
            price_history=price_history,
            action_history=action_history,
            reward_history=reward_history,
            profit_history=profit_history,
            trade_history=trade_history,
            info_history=info_history,
            total_reward=total_reward,
            total_profit=info["episode_profit"],
            final_soc=info["soc"],
            num_trades=info["num_trades"],
        )

        self.episodes.append(episode_data)
        return episode_data

    def plot_episode(
        self,
        episode: EpisodeData,
        save_path: Optional[str] = None,
        show: bool = True,
    ) -> Optional[Any]:
        """Plot comprehensive episode visualization.

        Args:
            episode: Episode data to visualize
            save_path: Optional path to save figure
            show: Whether to display the plot

        Returns:
            matplotlib figure if available
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.gridspec as gridspec
        except ImportError:
            logger.warning("matplotlib not available for visualization")
            return None

        fig = plt.figure(figsize=self.figsize)
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

        steps = list(range(len(episode.soc_history)))

        # 1. SOC over time
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(steps, episode.soc_history, 'b-', linewidth=2, label='SOC')
        ax1.axhline(y=0.2, color='r', linestyle='--', alpha=0.7, label='Min SOC')
        ax1.axhline(y=0.95, color='g', linestyle='--', alpha=0.7, label='Max SOC')
        ax1.fill_between(steps, 0.2, episode.soc_history, alpha=0.3)
        ax1.set_ylabel('State of Charge')
        ax1.set_xlabel('Step')
        ax1.set_title('Battery SOC')
        ax1.legend(loc='upper right', fontsize=8)
        ax1.set_ylim(0, 1)
        ax1.grid(True, alpha=0.3)

        # 2. Price over time
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.plot(steps, episode.price_history, 'g-', linewidth=2)
        ax2.fill_between(steps, 0, episode.price_history, alpha=0.3, color='green')
        ax2.set_ylabel('Price (₹/kWh)')
        ax2.set_xlabel('Step')
        ax2.set_title('Market Price')
        ax2.grid(True, alpha=0.3)

        # Mark trade points
        for trade in episode.trade_history:
            step = trade["step"]
            if step < len(episode.price_history):
                ax2.axvline(x=step, color='red' if trade["profit"] < 0 else 'blue',
                           alpha=0.5, linestyle=':')

        # 3. Cumulative profit
        ax3 = fig.add_subplot(gs[0, 2])
        ax3.plot(steps, episode.profit_history, 'orange', linewidth=2)
        ax3.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        ax3.fill_between(steps, 0, episode.profit_history,
                         where=[p >= 0 for p in episode.profit_history],
                         color='green', alpha=0.3, label='Profit')
        ax3.fill_between(steps, 0, episode.profit_history,
                         where=[p < 0 for p in episode.profit_history],
                         color='red', alpha=0.3, label='Loss')
        ax3.set_ylabel('Cumulative Profit (₹)')
        ax3.set_xlabel('Step')
        ax3.set_title('Episode Profit')
        ax3.legend(loc='upper left', fontsize=8)
        ax3.grid(True, alpha=0.3)

        # 4. Actions - Quantity
        ax4 = fig.add_subplot(gs[1, 0])
        action_steps = list(range(len(episode.action_history)))
        quantities = [a[0] for a in episode.action_history]
        colors = ['green' if q > 0 else 'red' if q < 0 else 'gray' for q in quantities]
        ax4.bar(action_steps, quantities, color=colors, alpha=0.7)
        ax4.axhline(y=0, color='k', linestyle='-', alpha=0.5)
        ax4.set_ylabel('Quantity (normalized)')
        ax4.set_xlabel('Step')
        ax4.set_title('Trade Actions (+ Buy, - Sell)')
        ax4.set_ylim(-1.1, 1.1)
        ax4.grid(True, alpha=0.3)

        # 5. Actions - Price Aggressiveness
        ax5 = fig.add_subplot(gs[1, 1])
        aggressiveness = [a[1] for a in episode.action_history]
        ax5.bar(action_steps, aggressiveness, color='purple', alpha=0.7)
        ax5.axhline(y=0.5, color='k', linestyle='--', alpha=0.5, label='Neutral')
        ax5.set_ylabel('Price Aggressiveness')
        ax5.set_xlabel('Step')
        ax5.set_title('Price Strategy (0=Passive, 1=Aggressive)')
        ax5.set_ylim(0, 1.1)
        ax5.legend(loc='upper right', fontsize=8)
        ax5.grid(True, alpha=0.3)

        # 6. Step rewards
        ax6 = fig.add_subplot(gs[1, 2])
        reward_colors = ['green' if r >= 0 else 'red' for r in episode.reward_history]
        ax6.bar(action_steps, episode.reward_history, color=reward_colors, alpha=0.7)
        ax6.axhline(y=0, color='k', linestyle='-', alpha=0.5)
        ax6.set_ylabel('Reward')
        ax6.set_xlabel('Step')
        ax6.set_title('Step Rewards')
        ax6.grid(True, alpha=0.3)

        # 7. SOC vs Price scatter (buy/sell decision analysis)
        ax7 = fig.add_subplot(gs[2, 0])
        soc_at_action = episode.soc_history[:-1]
        price_at_action = episode.price_history[:-1]
        scatter_colors = ['green' if q > 0.1 else 'red' if q < -0.1 else 'gray'
                         for q in quantities]
        ax7.scatter(price_at_action, soc_at_action, c=scatter_colors, alpha=0.6, s=50)
        ax7.set_xlabel('Market Price (₹/kWh)')
        ax7.set_ylabel('Battery SOC')
        ax7.set_title('Action vs Market State\n(Green=Buy, Red=Sell, Gray=Hold)')
        ax7.grid(True, alpha=0.3)

        # 8. Episode summary text
        ax8 = fig.add_subplot(gs[2, 1:])
        ax8.axis('off')

        summary_text = f"""
        Episode Summary
        ═══════════════════════════════════════

        Total Reward:     {episode.total_reward:>10.2f}
        Total Profit:     ₹{episode.total_profit:>9.2f}
        Final SOC:        {episode.final_soc*100:>9.1f}%
        Number of Trades: {episode.num_trades:>10d}

        Price Range:      ₹{min(episode.price_history):.2f} - ₹{max(episode.price_history):.2f}
        Avg Price:        ₹{np.mean(episode.price_history):.2f}

        SOC Range:        {min(episode.soc_history)*100:.1f}% - {max(episode.soc_history)*100:.1f}%

        Avg Reward:       {np.mean(episode.reward_history):.3f}
        Max Reward:       {max(episode.reward_history):.3f}
        Min Reward:       {min(episode.reward_history):.3f}
        """

        ax8.text(0.1, 0.9, summary_text, transform=ax8.transAxes,
                fontfamily='monospace', fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.suptitle('V2G Trading Environment - Episode Analysis', fontsize=14, fontweight='bold')

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Episode plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return fig

    def plot_multiple_episodes(
        self,
        episodes: Optional[List[EpisodeData]] = None,
        save_path: Optional[str] = None,
        show: bool = True,
    ) -> Optional[Any]:
        """Plot comparison of multiple episodes.

        Args:
            episodes: List of episodes to compare (uses recorded if None)
            save_path: Optional path to save figure
            show: Whether to display the plot

        Returns:
            matplotlib figure if available
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available for visualization")
            return None

        episodes = episodes or self.episodes
        if not episodes:
            logger.warning("No episodes to plot")
            return None

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        # 1. Profit comparison
        ax1 = axes[0, 0]
        for i, ep in enumerate(episodes):
            ax1.plot(ep.profit_history, alpha=0.7, label=f'Episode {i+1}')
        ax1.set_ylabel('Cumulative Profit (₹)')
        ax1.set_xlabel('Step')
        ax1.set_title('Profit Trajectories')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # 2. Reward comparison
        ax2 = axes[0, 1]
        for i, ep in enumerate(episodes):
            cumsum_reward = np.cumsum(ep.reward_history)
            ax2.plot(cumsum_reward, alpha=0.7, label=f'Episode {i+1}')
        ax2.set_ylabel('Cumulative Reward')
        ax2.set_xlabel('Step')
        ax2.set_title('Reward Trajectories')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        # 3. SOC distributions
        ax3 = axes[1, 0]
        all_socs = [np.mean(ep.soc_history) for ep in episodes]
        soc_stds = [np.std(ep.soc_history) for ep in episodes]
        x = range(len(episodes))
        ax3.bar(x, all_socs, yerr=soc_stds, alpha=0.7, capsize=5)
        ax3.set_ylabel('Average SOC')
        ax3.set_xlabel('Episode')
        ax3.set_title('SOC Distribution per Episode')
        ax3.set_xticks(x)
        ax3.set_xticklabels([f'Ep {i+1}' for i in x])
        ax3.grid(True, alpha=0.3)

        # 4. Performance summary
        ax4 = axes[1, 1]
        profits = [ep.total_profit for ep in episodes]
        rewards = [ep.total_reward for ep in episodes]
        trades = [ep.num_trades for ep in episodes]

        x = np.arange(len(episodes))
        width = 0.25

        ax4.bar(x - width, [p/max(abs(p) for p in profits) if profits else 0 for p in profits],
               width, label='Profit (norm)', alpha=0.7)
        ax4.bar(x, [r/max(abs(r) for r in rewards) if rewards else 0 for r in rewards],
               width, label='Reward (norm)', alpha=0.7)
        ax4.bar(x + width, [t/max(trades) if trades else 0 for t in trades],
               width, label='Trades (norm)', alpha=0.7)

        ax4.set_ylabel('Normalized Value')
        ax4.set_xlabel('Episode')
        ax4.set_title('Performance Comparison')
        ax4.set_xticks(x)
        ax4.set_xticklabels([f'Ep {i+1}' for i in x])
        ax4.legend(fontsize=8)
        ax4.grid(True, alpha=0.3)

        plt.suptitle('V2G Trading - Multi-Episode Comparison', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Multi-episode plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return fig

    def plot_action_distribution(
        self,
        episodes: Optional[List[EpisodeData]] = None,
        save_path: Optional[str] = None,
        show: bool = True,
    ) -> Optional[Any]:
        """Plot action distribution analysis.

        Args:
            episodes: List of episodes (uses recorded if None)
            save_path: Optional path to save figure
            show: Whether to display the plot

        Returns:
            matplotlib figure if available
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available for visualization")
            return None

        episodes = episodes or self.episodes
        if not episodes:
            logger.warning("No episodes to plot")
            return None

        # Aggregate all actions
        all_quantities = []
        all_aggressiveness = []
        for ep in episodes:
            all_quantities.extend([a[0] for a in ep.action_history])
            all_aggressiveness.extend([a[1] for a in ep.action_history])

        fig, axes = plt.subplots(1, 3, figsize=(14, 4))

        # 1. Quantity histogram
        ax1 = axes[0]
        ax1.hist(all_quantities, bins=20, alpha=0.7, color='blue', edgecolor='black')
        ax1.axvline(x=0, color='red', linestyle='--', label='Hold')
        ax1.set_xlabel('Quantity (normalized)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Trade Quantity Distribution')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. Aggressiveness histogram
        ax2 = axes[1]
        ax2.hist(all_aggressiveness, bins=20, alpha=0.7, color='purple', edgecolor='black')
        ax2.axvline(x=0.5, color='red', linestyle='--', label='Neutral')
        ax2.set_xlabel('Price Aggressiveness')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Price Aggressiveness Distribution')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 3. 2D action distribution
        ax3 = axes[2]
        ax3.hist2d(all_quantities, all_aggressiveness, bins=15, cmap='YlOrRd')
        ax3.set_xlabel('Quantity (normalized)')
        ax3.set_ylabel('Price Aggressiveness')
        ax3.set_title('2D Action Distribution')
        ax3.axvline(x=0, color='white', linestyle='--', alpha=0.7)
        ax3.axhline(y=0.5, color='white', linestyle='--', alpha=0.7)

        plt.suptitle('Action Distribution Analysis', fontsize=12, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Action distribution plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

        return fig

    def get_statistics(
        self,
        episodes: Optional[List[EpisodeData]] = None,
    ) -> Dict[str, Any]:
        """Calculate aggregate statistics over episodes.

        Args:
            episodes: List of episodes (uses recorded if None)

        Returns:
            Dictionary of statistics
        """
        episodes = episodes or self.episodes
        if not episodes:
            return {}

        profits = [ep.total_profit for ep in episodes]
        rewards = [ep.total_reward for ep in episodes]
        trades = [ep.num_trades for ep in episodes]
        final_socs = [ep.final_soc for ep in episodes]

        return {
            "num_episodes": len(episodes),
            "profit": {
                "mean": np.mean(profits),
                "std": np.std(profits),
                "min": np.min(profits),
                "max": np.max(profits),
                "median": np.median(profits),
            },
            "reward": {
                "mean": np.mean(rewards),
                "std": np.std(rewards),
                "min": np.min(rewards),
                "max": np.max(rewards),
                "median": np.median(rewards),
            },
            "trades": {
                "mean": np.mean(trades),
                "std": np.std(trades),
                "min": np.min(trades),
                "max": np.max(trades),
            },
            "final_soc": {
                "mean": np.mean(final_socs),
                "std": np.std(final_socs),
                "min": np.min(final_socs),
                "max": np.max(final_socs),
            },
            "profitable_episodes": sum(1 for p in profits if p > 0) / len(profits),
        }

    def print_statistics(
        self,
        episodes: Optional[List[EpisodeData]] = None,
    ):
        """Print formatted statistics.

        Args:
            episodes: List of episodes (uses recorded if None)
        """
        stats = self.get_statistics(episodes)
        if not stats:
            print("No episodes recorded")
            return

        print("\n" + "=" * 60)
        print("V2G Trading Environment - Episode Statistics")
        print("=" * 60)
        print(f"\nTotal Episodes: {stats['num_episodes']}")
        print(f"Profitable Episodes: {stats['profitable_episodes']*100:.1f}%")

        print("\nProfit Statistics:")
        print(f"  Mean:   ₹{stats['profit']['mean']:.2f}")
        print(f"  Std:    ₹{stats['profit']['std']:.2f}")
        print(f"  Min:    ₹{stats['profit']['min']:.2f}")
        print(f"  Max:    ₹{stats['profit']['max']:.2f}")
        print(f"  Median: ₹{stats['profit']['median']:.2f}")

        print("\nReward Statistics:")
        print(f"  Mean:   {stats['reward']['mean']:.3f}")
        print(f"  Std:    {stats['reward']['std']:.3f}")
        print(f"  Min:    {stats['reward']['min']:.3f}")
        print(f"  Max:    {stats['reward']['max']:.3f}")

        print("\nTrade Statistics:")
        print(f"  Mean:   {stats['trades']['mean']:.1f}")
        print(f"  Std:    {stats['trades']['std']:.1f}")
        print(f"  Min:    {stats['trades']['min']}")
        print(f"  Max:    {stats['trades']['max']}")

        print("\nFinal SOC Statistics:")
        print(f"  Mean:   {stats['final_soc']['mean']*100:.1f}%")
        print(f"  Std:    {stats['final_soc']['std']*100:.1f}%")
        print("=" * 60 + "\n")


def create_animation(
    env,
    policy: Optional[callable] = None,
    seed: Optional[int] = None,
    save_path: Optional[str] = None,
    fps: int = 2,
) -> Optional[Any]:
    """Create animation of episode execution.

    Args:
        env: V2GTradingEnv instance
        policy: Optional policy function
        seed: Random seed
        save_path: Path to save animation
        fps: Frames per second

    Returns:
        Animation object if available
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
    except ImportError:
        logger.warning("matplotlib not available for animation")
        return None

    # Record episode first
    obs, info = env.reset(seed=seed)
    frames = [env._render_rgb_array()]

    terminated = False
    truncated = False

    while not (terminated or truncated):
        if policy is not None:
            action = policy(obs)
        else:
            action = env.action_space.sample()

        obs, reward, terminated, truncated, info = env.step(action)
        frames.append(env._render_rgb_array())

    # Create animation
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis('off')

    im = ax.imshow(frames[0])

    def update(frame_idx):
        im.set_array(frames[frame_idx])
        return [im]

    anim = animation.FuncAnimation(
        fig, update, frames=len(frames),
        interval=1000//fps, blit=True,
    )

    if save_path:
        anim.save(save_path, writer='pillow', fps=fps)
        logger.info(f"Animation saved to {save_path}")

    return anim
