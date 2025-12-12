"""
Visualization for Benchmarking Experiments (Domain 8).

Provides plotting functions for benchmark comparisons.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Check for matplotlib
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    logger.warning("matplotlib not available, visualization disabled")


@dataclass
class BenchmarkVisualization:
    """
    Visualization class for benchmark results.
    """

    def __init__(self, figsize: Tuple[int, int] = (12, 6)):
        """
        Initialize visualization.

        Args:
            figsize: Default figure size
        """
        self.figsize = figsize
        self.colors = {
            'SHAKTI-CHAIN': '#2ecc71',
            'Fixed Tariff': '#e74c3c',
            'Uniform Auction': '#3498db',
            'CDA': '#9b59b6',
            'Brooklyn': '#f39c12',
            'SOTA RL': '#1abc9c',
        }

    def plot_roi_comparison(
        self,
        roi_data: Dict[str, List[float]],
        title: str = "ROI Comparison: SHAKTI vs Baselines",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot ROI comparison boxplots.

        Args:
            roi_data: Dict mapping system name to ROI values
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        systems = list(roi_data.keys())
        data = [roi_data[s] for s in systems]
        colors = [self.colors.get(s, '#95a5a6') for s in systems]

        bp = ax.boxplot(data, labels=systems, patch_artist=True)

        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.set_ylabel('ROI (%)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='y')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_efficiency_comparison(
        self,
        efficiency_data: Dict[str, float],
        title: str = "Efficiency Comparison",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot efficiency comparison bar chart.

        Args:
            efficiency_data: Dict mapping system name to efficiency
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        systems = list(efficiency_data.keys())
        values = list(efficiency_data.values())
        colors = [self.colors.get(s, '#95a5a6') for s in systems]

        bars = ax.bar(systems, values, color=colors, alpha=0.7, edgecolor='black')

        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                   f'{val:.1%}', ha='center', va='bottom', fontsize=10)

        ax.set_ylabel('Allocative Efficiency')
        ax.set_title(title)
        ax.set_ylim(0, 1.1)
        ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='Perfect')
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_cost_comparison(
        self,
        cost_data: Dict[str, List[float]],
        title: str = "Transaction Cost Comparison",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot cost comparison (SHAKTI vs Brooklyn).

        Args:
            cost_data: Dict mapping system name to cost values
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        systems = list(cost_data.keys())
        data = [cost_data[s] for s in systems]
        colors = [self.colors.get(s, '#95a5a6') for s in systems]

        bp = ax.boxplot(data, labels=systems, patch_artist=True)

        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Transaction Cost (INR/kWh)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_pareto_front(
        self,
        systems: List[Dict[str, Any]],
        objectives: Tuple[str, str] = ('efficiency', 'roi'),
        title: str = "Pareto Front",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot 2D Pareto front projection.

        Args:
            systems: List of system metrics dicts
            objectives: Two objectives to plot
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=(10, 8))

        obj1, obj2 = objectives

        for system in systems:
            name = system['name']
            x = system.get(obj1, 0)
            y = system.get(obj2, 0)
            color = self.colors.get(name, '#95a5a6')

            ax.scatter(x, y, s=200, c=color, label=name, edgecolors='black', linewidth=2)
            ax.annotate(name, (x, y), xytext=(10, 10), textcoords='offset points',
                       fontsize=10, fontweight='bold')

        # Draw Pareto front
        # Sort by first objective and connect non-dominated points
        sorted_systems = sorted(systems, key=lambda s: -s.get(obj1, 0))
        pareto_x = []
        pareto_y = []
        max_y = float('-inf')

        for s in sorted_systems:
            if s.get(obj2, 0) > max_y:
                pareto_x.append(s.get(obj1, 0))
                pareto_y.append(s.get(obj2, 0))
                max_y = s.get(obj2, 0)

        if len(pareto_x) > 1:
            ax.plot(pareto_x, pareto_y, 'k--', alpha=0.5, linewidth=2, label='Pareto Front')

        ax.set_xlabel(obj1.capitalize())
        ax.set_ylabel(obj2.capitalize())
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='lower right')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_radar_chart(
        self,
        systems: List[Dict[str, Any]],
        metrics: List[str] = None,
        title: str = "System Comparison Radar",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot radar chart comparing all systems.

        Args:
            systems: List of system metrics dicts
            metrics: Metrics to include
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        if metrics is None:
            metrics = ['efficiency', 'roi', 'fairness', 'throughput']

        n_metrics = len(metrics)
        angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
        angles += angles[:1]  # Close the polygon

        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

        for system in systems:
            name = system['name']
            values = [system.get(m, 0) for m in metrics]

            # Normalize values to 0-1 range for radar
            max_vals = {
                'efficiency': 1.0,
                'roi': 50.0,
                'fairness': 1.0,
                'throughput': 200.0,
                'cost': 5.0,
                'latency': 500.0,
            }
            normalized = [min(1, v / max_vals.get(m, 1)) for v, m in zip(values, metrics)]
            normalized += normalized[:1]

            color = self.colors.get(name, '#95a5a6')
            ax.plot(angles, normalized, 'o-', linewidth=2, label=name, color=color)
            ax.fill(angles, normalized, alpha=0.25, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([m.capitalize() for m in metrics])
        ax.set_title(title, size=14, y=1.1)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_hypothesis_summary(
        self,
        hypothesis_results: Dict[str, Dict[str, Any]],
        title: str = "Benchmark Hypothesis Test Results",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot summary of hypothesis test results.

        Args:
            hypothesis_results: Dict of hypothesis results
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=(12, 6))

        hypotheses = list(hypothesis_results.keys())
        passed = [hypothesis_results[h].get('passed', False) for h in hypotheses]
        p_values = [hypothesis_results[h].get('p_value', 1.0) for h in hypotheses]
        effect_sizes = [hypothesis_results[h].get('effect_size', 0) for h in hypotheses]

        x = np.arange(len(hypotheses))
        width = 0.35

        # P-value bars
        colors = ['green' if p else 'red' for p in passed]
        bars1 = ax.bar(x - width/2, p_values, width, label='p-value', color=colors, alpha=0.7)

        # Effect size bars
        bars2 = ax.bar(x + width/2, np.abs(effect_sizes), width, label='|Effect Size|',
                      color='steelblue', alpha=0.7)

        # Significance line
        ax.axhline(y=0.05, color='orange', linestyle='--', label='alpha = 0.05')

        ax.set_ylabel('Value')
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{h}\n({'PASS' if p else 'FAIL'})" for h, p in zip(hypotheses, passed)])
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_welfare_comparison(
        self,
        welfare_data: Dict[str, List[float]],
        title: str = "Welfare Comparison",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot welfare comparison (SHAKTI vs CDA).

        Args:
            welfare_data: Dict mapping system name to welfare values
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        systems = list(welfare_data.keys())
        data = [welfare_data[s] for s in systems]
        colors = [self.colors.get(s, '#95a5a6') for s in systems]

        bp = ax.boxplot(data, labels=systems, patch_artist=True)

        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Total Welfare (INR)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig


def create_benchmark_report(
    roi_data: Dict[str, List[float]],
    efficiency_data: Dict[str, float],
    cost_data: Dict[str, List[float]],
    systems: List[Dict[str, Any]],
    hypothesis_results: Dict[str, Dict[str, Any]],
    output_dir: str,
) -> Dict[str, str]:
    """
    Create full benchmark visualization report.

    Args:
        roi_data: ROI values by system
        efficiency_data: Efficiency by system
        cost_data: Cost values by system
        systems: System metrics
        hypothesis_results: Hypothesis test results
        output_dir: Output directory

    Returns:
        Dict mapping plot name to file path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    viz = BenchmarkVisualization()
    saved_files = {}

    # ROI comparison
    path = str(output_path / "roi_comparison.png")
    viz.plot_roi_comparison(roi_data, save_path=path)
    saved_files["roi_comparison"] = path

    # Efficiency comparison
    path = str(output_path / "efficiency_comparison.png")
    viz.plot_efficiency_comparison(efficiency_data, save_path=path)
    saved_files["efficiency_comparison"] = path

    # Cost comparison
    path = str(output_path / "cost_comparison.png")
    viz.plot_cost_comparison(cost_data, save_path=path)
    saved_files["cost_comparison"] = path

    # Pareto front
    path = str(output_path / "pareto_front.png")
    viz.plot_pareto_front(systems, save_path=path)
    saved_files["pareto_front"] = path

    # Radar chart
    path = str(output_path / "radar_comparison.png")
    viz.plot_radar_chart(systems, save_path=path)
    saved_files["radar_comparison"] = path

    # Hypothesis summary
    path = str(output_path / "hypothesis_summary.png")
    viz.plot_hypothesis_summary(hypothesis_results, save_path=path)
    saved_files["hypothesis_summary"] = path

    return saved_files
