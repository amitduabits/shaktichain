"""
Visualization - Plotting and visualization utilities for experiments.

Generates plots for price series, welfare distribution, efficiency,
and comparative analysis.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

# Note: matplotlib imports are conditional to handle environments without display


class ExperimentVisualizer:
    """
    Visualizer for experiment results.

    Generates various plots for analyzing experiment outcomes.
    """

    def __init__(
        self,
        output_dir: Path | str = "experiments/results",
        dpi: int = 150,
        figsize: tuple = (10, 6),
        style: str = "seaborn-v0_8-whitegrid",
    ):
        """
        Initialize the visualizer.

        Args:
            output_dir: Directory for saving plots
            dpi: Resolution for saved figures
            figsize: Default figure size
            style: Matplotlib style
        """
        self.output_dir = Path(output_dir)
        self.dpi = dpi
        self.figsize = figsize
        self.style = style

        self._plt = None
        self._sns = None

    def _import_matplotlib(self):
        """Lazily import matplotlib."""
        if self._plt is None:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            self._plt = plt
            try:
                plt.style.use(self.style)
            except OSError:
                plt.style.use('seaborn-v0_8')
        return self._plt

    def _import_seaborn(self):
        """Lazily import seaborn."""
        if self._sns is None:
            try:
                import seaborn as sns
                self._sns = sns
            except ImportError:
                self._sns = None
        return self._sns

    def plot_price_series(
        self,
        prices: list[float],
        title: str = "Market Clearing Prices",
        save_path: Optional[Path] = None,
        show_trend: bool = True,
        show_volatility_bands: bool = True,
    ) -> Optional[Path]:
        """
        Plot price series over time.

        Args:
            prices: List of prices
            title: Plot title
            save_path: Path to save the plot
            show_trend: Show moving average trend
            show_volatility_bands: Show volatility bands

        Returns:
            Path to saved plot
        """
        plt = self._import_matplotlib()

        fig, ax = plt.subplots(figsize=self.figsize)

        periods = range(len(prices))
        ax.plot(periods, prices, 'b-', alpha=0.7, label='Price')

        if show_trend and len(prices) > 10:
            window = min(20, len(prices) // 5)
            ma = np.convolve(prices, np.ones(window)/window, mode='valid')
            ax.plot(range(window-1, len(prices)), ma, 'r-',
                   linewidth=2, label=f'{window}-period MA')

        if show_volatility_bands and len(prices) > 20:
            window = 20
            rolling_mean = np.convolve(prices, np.ones(window)/window, mode='valid')
            rolling_std = np.array([
                np.std(prices[max(0, i-window+1):i+1])
                for i in range(window-1, len(prices))
            ])

            x = range(window-1, len(prices))
            ax.fill_between(
                x,
                rolling_mean - 2*rolling_std,
                rolling_mean + 2*rolling_std,
                alpha=0.2,
                label='±2σ band'
            )

        ax.set_xlabel('Period')
        ax.set_ylabel('Price (INR/kWh)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            return save_path

        plt.close(fig)
        return None

    def plot_welfare_distribution(
        self,
        buyer_surpluses: list[float],
        seller_surpluses: list[float],
        title: str = "Welfare Distribution",
        save_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Plot distribution of welfare/surplus.

        Args:
            buyer_surpluses: List of buyer surpluses
            seller_surpluses: List of seller surpluses
            title: Plot title
            save_path: Path to save

        Returns:
            Path to saved plot
        """
        plt = self._import_matplotlib()

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Histogram
        ax1 = axes[0]
        ax1.hist(buyer_surpluses, bins=30, alpha=0.6, label='Buyers', color='blue')
        ax1.hist(seller_surpluses, bins=30, alpha=0.6, label='Sellers', color='green')
        ax1.set_xlabel('Surplus (INR)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Surplus Distribution')
        ax1.legend()

        # Box plot
        ax2 = axes[1]
        data = [buyer_surpluses, seller_surpluses]
        bp = ax2.boxplot(data, labels=['Buyers', 'Sellers'], patch_artist=True)
        bp['boxes'][0].set_facecolor('lightblue')
        bp['boxes'][1].set_facecolor('lightgreen')
        ax2.set_ylabel('Surplus (INR)')
        ax2.set_title('Surplus Comparison')

        plt.suptitle(title)
        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            return save_path

        plt.close(fig)
        return None

    def plot_efficiency_over_time(
        self,
        efficiencies: list[float],
        title: str = "Market Efficiency Over Time",
        save_path: Optional[Path] = None,
        baseline: float = 0.9,
    ) -> Optional[Path]:
        """
        Plot efficiency metrics over time.

        Args:
            efficiencies: List of efficiency values
            title: Plot title
            save_path: Path to save
            baseline: Baseline efficiency to compare against

        Returns:
            Path to saved plot
        """
        plt = self._import_matplotlib()

        fig, ax = plt.subplots(figsize=self.figsize)

        periods = range(len(efficiencies))
        ax.plot(periods, efficiencies, 'b-', alpha=0.7, label='Efficiency')

        # Baseline
        ax.axhline(y=baseline, color='r', linestyle='--',
                  label=f'Target ({baseline:.0%})')

        # Moving average
        if len(efficiencies) > 10:
            window = min(20, len(efficiencies) // 5)
            ma = np.convolve(efficiencies, np.ones(window)/window, mode='valid')
            ax.plot(range(window-1, len(efficiencies)), ma, 'g-',
                   linewidth=2, label=f'{window}-period MA')

        ax.set_xlabel('Period')
        ax.set_ylabel('Allocative Efficiency')
        ax.set_title(title)
        ax.set_ylim(0, 1.05)
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            return save_path

        plt.close(fig)
        return None

    def plot_agent_performance(
        self,
        agent_profits: dict[str, list[float]],
        title: str = "Agent Performance by Type",
        save_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Plot performance metrics by agent type.

        Args:
            agent_profits: Dictionary mapping agent type to list of profits
            title: Plot title
            save_path: Path to save

        Returns:
            Path to saved plot
        """
        plt = self._import_matplotlib()
        sns = self._import_seaborn()

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Violin plot
        ax1 = axes[0]
        types = list(agent_profits.keys())
        data = list(agent_profits.values())

        if sns:
            positions = range(len(types))
            parts = ax1.violinplot(data, positions=positions, showmeans=True)
            ax1.set_xticks(positions)
            ax1.set_xticklabels(types, rotation=45, ha='right')
        else:
            ax1.boxplot(data, labels=types)

        ax1.set_ylabel('Profit (INR)')
        ax1.set_title('Profit Distribution by Agent Type')
        ax1.axhline(y=0, color='r', linestyle='--', alpha=0.5)

        # Cumulative performance
        ax2 = axes[1]
        for agent_type, profits in agent_profits.items():
            cumulative = np.cumsum(profits)
            ax2.plot(cumulative, label=agent_type)

        ax2.set_xlabel('Period')
        ax2.set_ylabel('Cumulative Profit (INR)')
        ax2.set_title('Cumulative Performance')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.suptitle(title)
        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            return save_path

        plt.close(fig)
        return None

    def plot_scenario_comparison(
        self,
        scenarios: dict[str, dict],
        metric: str = "efficiency",
        title: str = "Scenario Comparison",
        save_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Compare metrics across scenarios.

        Args:
            scenarios: Dictionary mapping scenario name to metrics
            metric: Metric to compare
            title: Plot title
            save_path: Path to save

        Returns:
            Path to saved plot
        """
        plt = self._import_matplotlib()

        fig, ax = plt.subplots(figsize=self.figsize)

        names = list(scenarios.keys())
        values = [s.get(metric, 0) for s in scenarios.values()]
        errors = [s.get(f"{metric}_std", 0) for s in scenarios.values()]

        x = range(len(names))
        bars = ax.bar(x, values, yerr=errors, capsize=5, alpha=0.7)

        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:.3f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom')

        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.set_ylabel(metric.replace('_', ' ').title())
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            return save_path

        plt.close(fig)
        return None

    def plot_demand_supply(
        self,
        demand_curve: list[tuple[float, float]],
        supply_curve: list[tuple[float, float]],
        clearing_price: Optional[float] = None,
        clearing_quantity: Optional[float] = None,
        title: str = "Supply and Demand",
        save_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Plot supply and demand curves.

        Args:
            demand_curve: List of (quantity, price) tuples for demand
            supply_curve: List of (quantity, price) tuples for supply
            clearing_price: Market clearing price
            clearing_quantity: Market clearing quantity
            title: Plot title
            save_path: Path to save

        Returns:
            Path to saved plot
        """
        plt = self._import_matplotlib()

        fig, ax = plt.subplots(figsize=self.figsize)

        # Sort and plot curves
        if demand_curve:
            demand_sorted = sorted(demand_curve, key=lambda x: x[0])
            d_qty, d_price = zip(*demand_sorted)
            ax.step(d_qty, d_price, 'b-', where='post', label='Demand', linewidth=2)

        if supply_curve:
            supply_sorted = sorted(supply_curve, key=lambda x: x[0])
            s_qty, s_price = zip(*supply_sorted)
            ax.step(s_qty, s_price, 'r-', where='post', label='Supply', linewidth=2)

        # Clearing point
        if clearing_price and clearing_quantity:
            ax.plot(clearing_quantity, clearing_price, 'go', markersize=10,
                   label=f'Equilibrium ({clearing_quantity:.1f}, {clearing_price:.2f})')
            ax.axhline(y=clearing_price, color='g', linestyle='--', alpha=0.5)
            ax.axvline(x=clearing_quantity, color='g', linestyle='--', alpha=0.5)

        ax.set_xlabel('Quantity (kWh)')
        ax.set_ylabel('Price (INR/kWh)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            return save_path

        plt.close(fig)
        return None

    def generate_experiment_report(
        self,
        experiment_id: str,
        metrics: dict,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """
        Generate a complete visual report for an experiment.

        Args:
            experiment_id: Experiment identifier
            metrics: Dictionary of all metrics
            output_dir: Output directory

        Returns:
            Path to output directory
        """
        output_dir = Path(output_dir or self.output_dir) / experiment_id / "visualizations"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Price series
        if "price_history" in metrics:
            self.plot_price_series(
                metrics["price_history"],
                title=f"Price Series - {experiment_id}",
                save_path=output_dir / "price_series.png",
            )

        # Efficiency
        if "efficiency_history" in metrics:
            self.plot_efficiency_over_time(
                metrics["efficiency_history"],
                title=f"Efficiency - {experiment_id}",
                save_path=output_dir / "efficiency_over_time.png",
            )

        # Welfare
        if "buyer_surpluses" in metrics and "seller_surpluses" in metrics:
            self.plot_welfare_distribution(
                metrics["buyer_surpluses"],
                metrics["seller_surpluses"],
                title=f"Welfare Distribution - {experiment_id}",
                save_path=output_dir / "welfare_distribution.png",
            )

        # Save metrics summary
        summary_path = output_dir / "metrics_summary.json"
        with open(summary_path, "w") as f:
            # Filter out non-serializable items
            serializable = {
                k: v for k, v in metrics.items()
                if isinstance(v, (int, float, str, bool, list, dict))
            }
            json.dump(serializable, f, indent=2, default=str)

        return output_dir
