"""Visualization suite for backtesting results.

Provides comprehensive plotting functions for:
- Equity curves
- Trade distributions
- SOC over time
- Profit analysis by hour/day
- Performance comparisons
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

from .backtester import BacktestRun, Trade, TradeType, DailyResult
from .metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class BacktestVisualizer:
    """Comprehensive visualization for backtest results."""

    def __init__(
        self,
        figsize: Tuple[int, int] = (14, 10),
        style: str = 'seaborn-v0_8-whitegrid',
    ):
        """Initialize visualizer.

        Args:
            figsize: Default figure size
            style: Matplotlib style
        """
        self.figsize = figsize
        self.style = style

    def _setup_plot(self):
        """Setup matplotlib with style."""
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            try:
                plt.style.use(self.style)
            except:
                pass
            return plt
        except ImportError:
            logger.warning("matplotlib not available")
            return None

    def plot_equity_curve(
        self,
        backtest_run: BacktestRun,
        benchmark_runs: Optional[Dict[str, BacktestRun]] = None,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot equity curve with optional benchmarks.

        Args:
            backtest_run: Main strategy backtest run
            benchmark_runs: Dictionary of benchmark runs
            save_path: Path to save figure
            show: Whether to display
        """
        plt = self._setup_plot()
        if plt is None:
            return

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        # 1. Equity Curve
        ax1 = axes[0, 0]
        equity = np.array(backtest_run.equity_curve)
        ax1.plot(equity, 'b-', linewidth=2, label='Strategy')

        if benchmark_runs:
            colors = ['orange', 'green', 'red', 'purple', 'brown']
            for (name, run), color in zip(benchmark_runs.items(), colors):
                ax1.plot(run.equity_curve, color=color, alpha=0.7, label=name)

        ax1.axhline(y=backtest_run.config.initial_balance, color='gray',
                   linestyle='--', alpha=0.5, label='Initial')
        ax1.set_xlabel('Days')
        ax1.set_ylabel('Portfolio Value (₹)')
        ax1.set_title('Equity Curve')
        ax1.legend(loc='upper left', fontsize=8)
        ax1.grid(True, alpha=0.3)

        # 2. Drawdown
        ax2 = axes[0, 1]
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max * 100
        ax2.fill_between(range(len(drawdown)), drawdown, 0, alpha=0.5, color='red')
        ax2.plot(drawdown, 'r-', linewidth=1)
        ax2.set_xlabel('Days')
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_title('Portfolio Drawdown')
        ax2.grid(True, alpha=0.3)

        # 3. Daily Returns Distribution
        ax3 = axes[1, 0]
        returns = np.array(backtest_run.daily_returns) * 100
        ax3.hist(returns, bins=50, alpha=0.7, color='blue', edgecolor='black')
        ax3.axvline(x=0, color='black', linestyle='-', alpha=0.5)
        ax3.axvline(x=np.mean(returns), color='red', linestyle='--',
                   label=f'Mean: {np.mean(returns):.2f}%')
        ax3.set_xlabel('Daily Return (%)')
        ax3.set_ylabel('Frequency')
        ax3.set_title('Daily Returns Distribution')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. Cumulative Returns
        ax4 = axes[1, 1]
        cum_returns = np.cumprod(1 + np.array(backtest_run.daily_returns)) - 1
        ax4.plot(cum_returns * 100, 'g-', linewidth=2)
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax4.fill_between(range(len(cum_returns)), cum_returns * 100, 0,
                        where=cum_returns >= 0, alpha=0.3, color='green')
        ax4.fill_between(range(len(cum_returns)), cum_returns * 100, 0,
                        where=cum_returns < 0, alpha=0.3, color='red')
        ax4.set_xlabel('Days')
        ax4.set_ylabel('Cumulative Return (%)')
        ax4.set_title('Cumulative Returns')
        ax4.grid(True, alpha=0.3)

        plt.suptitle('V2G Trading Backtest - Equity Analysis', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Equity curve saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_trade_analysis(
        self,
        backtest_run: BacktestRun,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot trade distribution and analysis.

        Args:
            backtest_run: Backtest run results
            save_path: Path to save figure
            show: Whether to display
        """
        plt = self._setup_plot()
        if plt is None:
            return

        trades = backtest_run.all_trades
        if not trades:
            logger.warning("No trades to visualize")
            return

        fig, axes = plt.subplots(2, 3, figsize=(16, 10))

        # 1. Profit per trade
        ax1 = axes[0, 0]
        profits = [t.profit for t in trades]
        colors = ['green' if p > 0 else 'red' for p in profits]
        ax1.bar(range(len(profits)), profits, color=colors, alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax1.set_xlabel('Trade #')
        ax1.set_ylabel('Profit (₹)')
        ax1.set_title('Profit per Trade')
        ax1.grid(True, alpha=0.3)

        # 2. Trade profit distribution
        ax2 = axes[0, 1]
        ax2.hist(profits, bins=30, alpha=0.7, color='blue', edgecolor='black')
        ax2.axvline(x=0, color='red', linestyle='--', alpha=0.7)
        ax2.axvline(x=np.mean(profits), color='green', linestyle='--',
                   label=f'Mean: ₹{np.mean(profits):.2f}')
        ax2.set_xlabel('Profit (₹)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Trade Profit Distribution')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 3. Trades by hour
        ax3 = axes[0, 2]
        buy_hours = [t.hour for t in trades if t.trade_type == TradeType.BUY]
        sell_hours = [t.hour for t in trades if t.trade_type == TradeType.SELL]

        hours = range(24)
        buy_counts = [buy_hours.count(h) for h in hours]
        sell_counts = [sell_hours.count(h) for h in hours]

        width = 0.35
        ax3.bar([h - width/2 for h in hours], buy_counts, width, label='Buy', color='green', alpha=0.7)
        ax3.bar([h + width/2 for h in hours], sell_counts, width, label='Sell', color='red', alpha=0.7)
        ax3.set_xlabel('Hour')
        ax3.set_ylabel('Number of Trades')
        ax3.set_title('Trade Distribution by Hour')
        ax3.legend()
        ax3.set_xticks(range(0, 24, 2))
        ax3.grid(True, alpha=0.3)

        # 4. Profit by hour
        ax4 = axes[1, 0]
        hourly_profits = {h: [] for h in range(24)}
        for t in trades:
            hourly_profits[t.hour].append(t.profit)

        avg_profits = [np.mean(hourly_profits[h]) if hourly_profits[h] else 0 for h in range(24)]
        colors = ['green' if p > 0 else 'red' for p in avg_profits]
        ax4.bar(range(24), avg_profits, color=colors, alpha=0.7)
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax4.set_xlabel('Hour')
        ax4.set_ylabel('Average Profit (₹)')
        ax4.set_title('Average Profit by Hour')
        ax4.set_xticks(range(0, 24, 2))
        ax4.grid(True, alpha=0.3)

        # 5. Trade size distribution
        ax5 = axes[1, 1]
        quantities = [t.quantity_kwh for t in trades]
        ax5.hist(quantities, bins=30, alpha=0.7, color='purple', edgecolor='black')
        ax5.set_xlabel('Trade Size (kWh)')
        ax5.set_ylabel('Frequency')
        ax5.set_title('Trade Size Distribution')
        ax5.grid(True, alpha=0.3)

        # 6. Win/Loss streak
        ax6 = axes[1, 2]
        streak = []
        current_streak = 0
        for p in profits:
            if p > 0:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    streak.append(current_streak)
                    current_streak = 1
            else:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    streak.append(current_streak)
                    current_streak = -1
        streak.append(current_streak)

        colors = ['green' if s > 0 else 'red' for s in streak]
        ax6.bar(range(len(streak)), streak, color=colors, alpha=0.7)
        ax6.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax6.set_xlabel('Streak #')
        ax6.set_ylabel('Streak Length')
        ax6.set_title('Win/Loss Streaks')
        ax6.grid(True, alpha=0.3)

        plt.suptitle('V2G Trading Backtest - Trade Analysis', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Trade analysis saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_soc_analysis(
        self,
        backtest_run: BacktestRun,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot SOC (State of Charge) analysis.

        Args:
            backtest_run: Backtest run results
            save_path: Path to save figure
            show: Whether to display
        """
        plt = self._setup_plot()
        if plt is None:
            return

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        soc_history = backtest_run.soc_history
        price_history = backtest_run.price_history

        # 1. SOC over time
        ax1 = axes[0, 0]
        ax1.plot(soc_history, 'b-', linewidth=1, alpha=0.8)
        ax1.axhline(y=backtest_run.config.min_soc, color='red', linestyle='--',
                   alpha=0.7, label=f'Min: {backtest_run.config.min_soc:.0%}')
        ax1.axhline(y=backtest_run.config.max_soc, color='green', linestyle='--',
                   alpha=0.7, label=f'Max: {backtest_run.config.max_soc:.0%}')
        ax1.fill_between(range(len(soc_history)), backtest_run.config.min_soc,
                        soc_history, alpha=0.3, color='blue')
        ax1.set_xlabel('Hour')
        ax1.set_ylabel('State of Charge')
        ax1.set_title('Battery SOC Over Time')
        ax1.set_ylim(0, 1)
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

        # 2. SOC distribution
        ax2 = axes[0, 1]
        ax2.hist(soc_history, bins=50, alpha=0.7, color='blue', edgecolor='black')
        ax2.axvline(x=np.mean(soc_history), color='red', linestyle='--',
                   label=f'Mean: {np.mean(soc_history):.2%}')
        ax2.axvline(x=backtest_run.config.min_soc, color='orange', linestyle=':',
                   label='Min Limit')
        ax2.axvline(x=backtest_run.config.max_soc, color='green', linestyle=':',
                   label='Max Limit')
        ax2.set_xlabel('State of Charge')
        ax2.set_ylabel('Frequency')
        ax2.set_title('SOC Distribution')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 3. SOC vs Price scatter
        ax3 = axes[1, 0]
        if len(soc_history) == len(price_history):
            scatter = ax3.scatter(price_history, soc_history, c=range(len(soc_history)),
                                cmap='viridis', alpha=0.5, s=10)
            plt.colorbar(scatter, ax=ax3, label='Hour')
        ax3.set_xlabel('Price (₹/kWh)')
        ax3.set_ylabel('State of Charge')
        ax3.set_title('SOC vs Market Price')
        ax3.grid(True, alpha=0.3)

        # 4. Average SOC by hour
        ax4 = axes[1, 1]
        hourly_soc = {h: [] for h in range(24)}
        for i, soc in enumerate(soc_history):
            hour = i % 24
            hourly_soc[hour].append(soc)

        avg_soc = [np.mean(hourly_soc[h]) if hourly_soc[h] else 0.5 for h in range(24)]
        std_soc = [np.std(hourly_soc[h]) if hourly_soc[h] else 0 for h in range(24)]

        ax4.bar(range(24), avg_soc, yerr=std_soc, alpha=0.7, color='blue',
               capsize=3, error_kw={'alpha': 0.5})
        ax4.axhline(y=backtest_run.config.min_soc, color='red', linestyle='--', alpha=0.5)
        ax4.axhline(y=backtest_run.config.max_soc, color='green', linestyle='--', alpha=0.5)
        ax4.set_xlabel('Hour')
        ax4.set_ylabel('Average SOC')
        ax4.set_title('Average SOC by Hour of Day')
        ax4.set_xticks(range(0, 24, 2))
        ax4.set_ylim(0, 1)
        ax4.grid(True, alpha=0.3)

        plt.suptitle('V2G Trading Backtest - Battery Analysis', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"SOC analysis saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_daily_analysis(
        self,
        backtest_run: BacktestRun,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot daily performance analysis.

        Args:
            backtest_run: Backtest run results
            save_path: Path to save figure
            show: Whether to display
        """
        plt = self._setup_plot()
        if plt is None:
            return

        daily_results = backtest_run.daily_results

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        # 1. Daily profits
        ax1 = axes[0, 0]
        daily_profits = [d.total_profit for d in daily_results]
        colors = ['green' if p > 0 else 'red' for p in daily_profits]
        ax1.bar(range(len(daily_profits)), daily_profits, color=colors, alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax1.axhline(y=np.mean(daily_profits), color='blue', linestyle='--',
                   label=f'Mean: ₹{np.mean(daily_profits):.2f}')
        ax1.set_xlabel('Day')
        ax1.set_ylabel('Daily Profit (₹)')
        ax1.set_title('Daily Profits')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. Daily trades
        ax2 = axes[0, 1]
        daily_trades = [d.total_trades for d in daily_results]
        ax2.bar(range(len(daily_trades)), daily_trades, alpha=0.7, color='purple')
        ax2.axhline(y=np.mean(daily_trades), color='red', linestyle='--',
                   label=f'Mean: {np.mean(daily_trades):.1f}')
        ax2.set_xlabel('Day')
        ax2.set_ylabel('Number of Trades')
        ax2.set_title('Daily Trading Activity')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 3. Win rate rolling
        ax3 = axes[1, 0]
        window = 7
        win_rates = [d.win_trades / d.total_trades if d.total_trades > 0 else 0
                    for d in daily_results]
        if len(win_rates) >= window:
            rolling_wr = np.convolve(win_rates, np.ones(window)/window, mode='valid')
            ax3.plot(range(window-1, len(win_rates)), rolling_wr, 'b-', linewidth=2)
        ax3.scatter(range(len(win_rates)), win_rates, alpha=0.3, s=20)
        ax3.axhline(y=0.5, color='red', linestyle='--', alpha=0.5, label='50%')
        ax3.set_xlabel('Day')
        ax3.set_ylabel('Win Rate')
        ax3.set_title(f'Daily Win Rate ({window}-day rolling average)')
        ax3.set_ylim(0, 1)
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # 4. Battery cycles per day
        ax4 = axes[1, 1]
        cycles = [d.battery_cycles for d in daily_results]
        ax4.bar(range(len(cycles)), cycles, alpha=0.7, color='orange')
        ax4.axhline(y=np.mean(cycles), color='red', linestyle='--',
                   label=f'Mean: {np.mean(cycles):.2f}')
        ax4.set_xlabel('Day')
        ax4.set_ylabel('Battery Cycles')
        ax4.set_title('Daily Battery Cycling')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.suptitle('V2G Trading Backtest - Daily Analysis', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Daily analysis saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_comparison(
        self,
        strategy_run: BacktestRun,
        baseline_runs: Dict[str, BacktestRun],
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot comparison between strategy and baselines.

        Args:
            strategy_run: Main strategy results
            baseline_runs: Dictionary of baseline results
            save_path: Path to save figure
            show: Whether to display
        """
        plt = self._setup_plot()
        if plt is None:
            return

        fig, axes = plt.subplots(2, 2, figsize=self.figsize)

        all_runs = {'Strategy': strategy_run, **baseline_runs}
        names = list(all_runs.keys())
        n = len(names)

        # 1. Total Return comparison
        ax1 = axes[0, 0]
        returns = [all_runs[name].total_return for name in names]
        colors = ['blue'] + ['gray'] * (n - 1)
        bars = ax1.bar(names, returns, color=colors, alpha=0.7)
        bars[0].set_color('blue')
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax1.axhline(y=15, color='green', linestyle='--', alpha=0.5, label='Target: 15%')
        ax1.set_ylabel('Total Return (%)')
        ax1.set_title('Return Comparison')
        ax1.legend()
        plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
        ax1.grid(True, alpha=0.3)

        # 2. Equity curves
        ax2 = axes[0, 1]
        colors_list = ['blue', 'orange', 'green', 'red', 'purple', 'brown', 'pink']
        for i, name in enumerate(names):
            equity = all_runs[name].equity_curve
            # Normalize to percentage
            normalized = [(e / equity[0] - 1) * 100 for e in equity]
            ax2.plot(normalized, label=name, color=colors_list[i % len(colors_list)],
                    linewidth=2 if name == 'Strategy' else 1,
                    alpha=1.0 if name == 'Strategy' else 0.6)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax2.set_xlabel('Days')
        ax2.set_ylabel('Return (%)')
        ax2.set_title('Normalized Equity Curves')
        ax2.legend(loc='upper left', fontsize=8)
        ax2.grid(True, alpha=0.3)

        # 3. Risk-Return scatter
        ax3 = axes[1, 0]
        for i, name in enumerate(names):
            run = all_runs[name]
            ret = run.total_return
            vol = np.std(run.daily_returns) * np.sqrt(365) * 100 if run.daily_returns else 0
            color = 'blue' if name == 'Strategy' else 'gray'
            size = 200 if name == 'Strategy' else 100
            ax3.scatter(vol, ret, s=size, c=color, alpha=0.7, label=name)
            ax3.annotate(name, (vol, ret), textcoords="offset points",
                        xytext=(5, 5), fontsize=8)
        ax3.set_xlabel('Annualized Volatility (%)')
        ax3.set_ylabel('Total Return (%)')
        ax3.set_title('Risk-Return Profile')
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax3.axvline(x=0, color='black', linestyle='-', alpha=0.3)
        ax3.grid(True, alpha=0.3)

        # 4. Metrics comparison table (as bar chart)
        ax4 = axes[1, 1]
        metrics = ['Win Rate', 'Sharpe', 'Max DD']
        x = np.arange(len(metrics))
        width = 0.8 / n

        for i, name in enumerate(names):
            run = all_runs[name]
            perf = PerformanceMetrics(run)
            trading = perf.calculate_trading_metrics()
            returns_m = perf.calculate_return_metrics()

            values = [
                trading.win_rate * 100,
                returns_m.sharpe_ratio,
                abs(returns_m.max_drawdown),
            ]
            offset = (i - n/2 + 0.5) * width
            color = 'blue' if name == 'Strategy' else f'C{i}'
            ax4.bar(x + offset, values, width, label=name, alpha=0.7, color=color)

        ax4.set_ylabel('Value')
        ax4.set_title('Key Metrics Comparison')
        ax4.set_xticks(x)
        ax4.set_xticklabels(metrics)
        ax4.legend(loc='upper right', fontsize=8)
        ax4.grid(True, alpha=0.3)

        plt.suptitle('V2G Trading - Strategy vs Baselines', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Comparison saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_monte_carlo(
        self,
        mc_result,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Plot Monte Carlo simulation results.

        Args:
            mc_result: MonteCarloResult object
            save_path: Path to save figure
            show: Whether to display
        """
        plt = self._setup_plot()
        if plt is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # 1. Distribution
        ax1 = axes[0]
        dist = np.array(mc_result.distribution) * 100
        ax1.hist(dist, bins=50, alpha=0.7, color='blue', edgecolor='black')
        ax1.axvline(x=mc_result.mean * 100, color='red', linestyle='--',
                   label=f'Mean: {mc_result.mean*100:.1f}%')
        ax1.axvline(x=mc_result.percentile_5 * 100, color='orange', linestyle=':',
                   label=f'5th: {mc_result.percentile_5*100:.1f}%')
        ax1.axvline(x=mc_result.percentile_95 * 100, color='green', linestyle=':',
                   label=f'95th: {mc_result.percentile_95*100:.1f}%')
        ax1.axvline(x=mc_result.target * 100, color='purple', linestyle='-',
                   linewidth=2, label=f'Target: {mc_result.target*100:.0f}%')
        ax1.set_xlabel(f'{mc_result.metric_name} (%)')
        ax1.set_ylabel('Frequency')
        ax1.set_title(f'Monte Carlo Distribution (n={mc_result.n_simulations})')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # 2. Probability summary
        ax2 = axes[1]
        probs = [
            mc_result.probability_positive * 100,
            mc_result.probability_above_target * 100,
        ]
        labels = ['P(Profit > 0)', f'P(Return > {mc_result.target*100:.0f}%)']
        colors = ['green' if p > 50 else 'red' for p in probs]

        bars = ax2.barh(labels, probs, color=colors, alpha=0.7)
        ax2.axvline(x=50, color='black', linestyle='--', alpha=0.5)
        ax2.set_xlabel('Probability (%)')
        ax2.set_xlim(0, 100)
        ax2.set_title('Probability Summary')

        for bar, prob in zip(bars, probs):
            ax2.text(prob + 2, bar.get_y() + bar.get_height()/2,
                    f'{prob:.1f}%', va='center', fontsize=10)

        ax2.grid(True, alpha=0.3)

        plt.suptitle('Monte Carlo Simulation Results', fontsize=14, fontweight='bold')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Monte Carlo plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def create_all_plots(
        self,
        backtest_run: BacktestRun,
        baseline_runs: Optional[Dict[str, BacktestRun]] = None,
        output_dir: str = './plots',
        show: bool = False,
    ) -> List[str]:
        """Generate all visualization plots.

        Args:
            backtest_run: Main backtest results
            baseline_runs: Optional baseline results
            output_dir: Output directory
            show: Whether to display plots

        Returns:
            List of saved file paths
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        saved_paths = []

        # Equity curve
        path = os.path.join(output_dir, 'equity_curve.png')
        self.plot_equity_curve(backtest_run, baseline_runs, save_path=path, show=show)
        saved_paths.append(path)

        # Trade analysis
        path = os.path.join(output_dir, 'trade_analysis.png')
        self.plot_trade_analysis(backtest_run, save_path=path, show=show)
        saved_paths.append(path)

        # SOC analysis
        path = os.path.join(output_dir, 'soc_analysis.png')
        self.plot_soc_analysis(backtest_run, save_path=path, show=show)
        saved_paths.append(path)

        # Daily analysis
        path = os.path.join(output_dir, 'daily_analysis.png')
        self.plot_daily_analysis(backtest_run, save_path=path, show=show)
        saved_paths.append(path)

        # Comparison (if baselines provided)
        if baseline_runs:
            path = os.path.join(output_dir, 'comparison.png')
            self.plot_comparison(backtest_run, baseline_runs, save_path=path, show=show)
            saved_paths.append(path)

        logger.info(f"Generated {len(saved_paths)} plots in {output_dir}")
        return saved_paths
