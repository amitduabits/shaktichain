"""
Visualization Module for Market Mechanism Efficiency (Domain 1).

Generates publication-quality plots for mechanism validation:
- Efficiency distributions (histograms, box plots)
- Supply/demand curves with equilibrium
- Hypothesis test results
- Convergence analysis
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from .walrasian_calculator import WalrasianEquilibrium
from .efficiency_metrics import EfficiencyResults
from .hypothesis_tests import HypothesisResult
from .experiments import ExperimentResults


class MechanismVisualizer:
    """
    Generate visualizations for mechanism efficiency experiments.

    Creates publication-quality figures with consistent styling.
    """

    # Color scheme
    COLORS = {
        "primary": "#2E86AB",      # Blue
        "secondary": "#A23B72",    # Magenta
        "success": "#28A745",      # Green
        "warning": "#FFC107",      # Yellow
        "danger": "#DC3545",       # Red
        "neutral": "#6C757D",      # Gray
        "demand": "#E74C3C",       # Red for demand
        "supply": "#3498DB",       # Blue for supply
        "equilibrium": "#2ECC71", # Green for equilibrium
    }

    # Plot style
    STYLE = {
        "figure.figsize": (10, 6),
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.dpi": 100,
    }

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize visualizer.

        Args:
            output_dir: Directory for saving plots (None for display only)
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("matplotlib is required for visualization")

        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Apply style
        plt.rcParams.update(self.STYLE)

    def plot_efficiency_distributions(
        self,
        results: ExperimentResults,
        save: bool = True,
    ) -> Figure:
        """
        Plot distributions of all efficiency metrics.

        Creates a 2x3 subplot figure with histograms and threshold lines.
        """
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle("Mechanism Efficiency Distributions", fontsize=16, fontweight="bold")

        # Extract data
        alloc_eff = np.array([r.allocative_efficiency for r in results.run_results])
        vol_eff = np.array([r.volume_efficiency for r in results.run_results])
        price_err = np.array([np.abs(r.price_discovery_error) for r in results.run_results])
        buyer_ir = np.array([r.buyer_ir_rate for r in results.run_results])
        seller_ir = np.array([r.seller_ir_rate for r in results.run_results])
        revenue = np.array([r.market_maker_revenue for r in results.run_results])

        # Plot 1: Allocative Efficiency
        ax = axes[0, 0]
        self._plot_histogram(
            ax, alloc_eff, "Allocative Efficiency (H1.1)",
            threshold=0.95, threshold_label="95% Target",
            color=self.COLORS["primary"]
        )

        # Plot 2: Volume Efficiency
        ax = axes[0, 1]
        self._plot_histogram(
            ax, vol_eff, "Volume Efficiency (H1.6)",
            threshold=0.90, threshold_label="90% Target",
            color=self.COLORS["secondary"]
        )

        # Plot 3: Price Discovery Error
        ax = axes[0, 2]
        self._plot_histogram(
            ax, price_err, "Price Discovery Error (H1.5)",
            threshold=0.05, threshold_label="5% Target",
            color=self.COLORS["warning"], direction="less"
        )

        # Plot 4: Buyer IR Rate
        ax = axes[1, 0]
        self._plot_histogram(
            ax, buyer_ir, "Buyer IR Rate (H1.2)",
            threshold=1.0, threshold_label="100% Target",
            color=self.COLORS["success"]
        )

        # Plot 5: Seller IR Rate
        ax = axes[1, 1]
        self._plot_histogram(
            ax, seller_ir, "Seller IR Rate (H1.3)",
            threshold=1.0, threshold_label="100% Target",
            color=self.COLORS["success"]
        )

        # Plot 6: Market Maker Revenue
        ax = axes[1, 2]
        self._plot_histogram(
            ax, revenue, "Market Maker Revenue (H1.4)",
            threshold=0.0, threshold_label="Break-even",
            color=self.COLORS["neutral"]
        )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / "efficiency_distributions.png", dpi=150, bbox_inches="tight")
            fig.savefig(self.output_dir / "efficiency_distributions.pdf", bbox_inches="tight")

        return fig

    def _plot_histogram(
        self,
        ax,
        data: np.ndarray,
        title: str,
        threshold: float,
        threshold_label: str,
        color: str,
        direction: str = "greater",
    ):
        """Helper to plot a single histogram with threshold line."""
        n_bins = min(30, len(data) // 3 + 1)

        ax.hist(data, bins=n_bins, color=color, alpha=0.7, edgecolor="black", linewidth=0.5)

        # Add threshold line
        line_color = self.COLORS["success"] if direction == "greater" else self.COLORS["danger"]
        ax.axvline(threshold, color=line_color, linestyle="--", linewidth=2, label=threshold_label)

        # Add mean line
        mean_val = np.mean(data)
        ax.axvline(mean_val, color="black", linestyle="-", linewidth=1.5, label=f"Mean: {mean_val:.3f}")

        ax.set_title(title)
        ax.set_xlabel("Value")
        ax.set_ylabel("Frequency")
        ax.legend(loc="upper left", fontsize=8)

        # Add pass/fail indicator
        if direction == "greater":
            passed = mean_val >= threshold
        else:
            passed = mean_val <= threshold

        status_color = self.COLORS["success"] if passed else self.COLORS["danger"]
        status_text = "PASS" if passed else "FAIL"
        ax.text(
            0.95, 0.95, status_text,
            transform=ax.transAxes,
            fontsize=12, fontweight="bold",
            color=status_color,
            ha="right", va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

    def plot_supply_demand_curves(
        self,
        walrasian_eq: WalrasianEquilibrium,
        title: str = "Supply and Demand Curves",
        save: bool = True,
        filename: str = "supply_demand_curves.png",
    ) -> Figure:
        """
        Plot supply and demand curves with equilibrium point.

        Args:
            walrasian_eq: Walrasian equilibrium with curve data
            title: Plot title
            save: Whether to save the figure
            filename: Filename for saved figure
        """
        fig, ax = plt.subplots(figsize=(10, 8))

        demand_curve = walrasian_eq.demand_curve
        supply_curve = walrasian_eq.supply_curve

        if demand_curve:
            # Extract step function points
            demand_q = [p[0] for p in demand_curve]
            demand_p = [p[1] for p in demand_curve]
            ax.step(demand_q, demand_p, where="post", color=self.COLORS["demand"],
                   linewidth=2.5, label="Demand Curve")

        if supply_curve:
            supply_q = [p[0] for p in supply_curve]
            supply_p = [p[1] for p in supply_curve]
            ax.step(supply_q, supply_p, where="post", color=self.COLORS["supply"],
                   linewidth=2.5, label="Supply Curve")

        # Mark equilibrium
        eq_q = walrasian_eq.equilibrium_quantity
        eq_p = walrasian_eq.equilibrium_price

        ax.plot(eq_q, eq_p, "o", color=self.COLORS["equilibrium"],
               markersize=15, markeredgecolor="black", markeredgewidth=2,
               label=f"Equilibrium (Q*={eq_q:.1f}, P*={eq_p:.2f})")

        # Add reference lines
        ax.axhline(eq_p, color=self.COLORS["equilibrium"], linestyle=":", alpha=0.5)
        ax.axvline(eq_q, color=self.COLORS["equilibrium"], linestyle=":", alpha=0.5)

        # Shade consumer and producer surplus
        if demand_curve and supply_curve:
            self._shade_surplus(ax, demand_curve, supply_curve, eq_p, eq_q)

        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel("Quantity", fontsize=12)
        ax.set_ylabel("Price (₹/kWh)", fontsize=12)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

        # Add welfare annotation
        welfare_text = (
            f"Consumer Surplus: ₹{walrasian_eq.buyer_surplus:.2f}\n"
            f"Producer Surplus: ₹{walrasian_eq.seller_surplus:.2f}\n"
            f"Total Welfare: ₹{walrasian_eq.maximum_welfare:.2f}"
        )
        ax.text(
            0.02, 0.98, welfare_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8)
        )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def _shade_surplus(
        self,
        ax,
        demand_curve: List[Tuple[float, float]],
        supply_curve: List[Tuple[float, float]],
        eq_price: float,
        eq_quantity: float,
    ):
        """Shade consumer and producer surplus regions."""
        # Consumer surplus (above price, below demand)
        cs_q = []
        cs_p_demand = []
        for q, p in demand_curve:
            if q <= eq_quantity:
                cs_q.append(q)
                cs_p_demand.append(max(p, eq_price))

        if cs_q:
            cs_q.append(eq_quantity)
            cs_p_demand.append(eq_price)
            ax.fill_between(
                cs_q, eq_price, cs_p_demand,
                color=self.COLORS["demand"], alpha=0.2,
                label="Consumer Surplus"
            )

        # Producer surplus (below price, above supply)
        ps_q = []
        ps_p_supply = []
        for q, p in supply_curve:
            if q <= eq_quantity:
                ps_q.append(q)
                ps_p_supply.append(min(p, eq_price))

        if ps_q:
            ps_q.append(eq_quantity)
            ps_p_supply.append(eq_price)
            ax.fill_between(
                ps_q, ps_p_supply, eq_price,
                color=self.COLORS["supply"], alpha=0.2,
                label="Producer Surplus"
            )

    def plot_hypothesis_summary(
        self,
        hypothesis_results: Dict[str, HypothesisResult],
        save: bool = True,
    ) -> Figure:
        """
        Create a visual summary of hypothesis test results.

        Shows pass/fail status with confidence intervals and effect sizes.
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Left panel: Pass/Fail bar chart
        ax = axes[0]
        hypotheses = sorted(hypothesis_results.keys())
        n_hyp = len(hypotheses)

        colors = []
        for h in hypotheses:
            if hypothesis_results[h].passed:
                colors.append(self.COLORS["success"])
            else:
                colors.append(self.COLORS["danger"])

        y_pos = np.arange(n_hyp)
        ax.barh(y_pos, [1] * n_hyp, color=colors, alpha=0.8)

        # Add pass/fail labels
        for i, h in enumerate(hypotheses):
            result = hypothesis_results[h]
            status = "PASS" if result.passed else "FAIL"
            ax.text(0.5, i, f"{h}: {status}", ha="center", va="center",
                   fontsize=11, fontweight="bold", color="white")

        ax.set_yticks(y_pos)
        ax.set_yticklabels([hypothesis_results[h].description[:40] + "..."
                          if len(hypothesis_results[h].description) > 40
                          else hypothesis_results[h].description
                          for h in hypotheses], fontsize=9)
        ax.set_xlim(0, 1)
        ax.set_xlabel("")
        ax.set_title("Hypothesis Test Results", fontsize=12, fontweight="bold")
        ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

        # Right panel: Effect sizes with confidence intervals
        ax = axes[1]

        effect_sizes = [hypothesis_results[h].effect_size for h in hypotheses]
        ci_lower = [hypothesis_results[h].confidence_interval[0] for h in hypotheses]
        ci_upper = [hypothesis_results[h].confidence_interval[1] for h in hypotheses]

        # Cap extreme effect sizes for visualization
        effect_sizes_capped = [min(max(e, -5), 5) for e in effect_sizes]

        ax.barh(y_pos, effect_sizes_capped, color=colors, alpha=0.6)

        # Add CI error bars (only for reasonable ranges)
        for i, h in enumerate(hypotheses):
            result = hypothesis_results[h]
            if abs(result.effect_size) < 5:
                ax.errorh(
                    i, result.effect_size,
                    xerr=[[result.effect_size - ci_lower[i]], [ci_upper[i] - result.effect_size]],
                    fmt="none", color="black", capsize=3
                )

        ax.axvline(0, color="black", linestyle="-", linewidth=1)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"{h}" for h in hypotheses])
        ax.set_xlabel("Effect Size (Cohen's d)")
        ax.set_title("Effect Sizes with 95% CI", fontsize=12, fontweight="bold")
        ax.grid(True, axis="x", alpha=0.3)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / "hypothesis_summary.png", dpi=150, bbox_inches="tight")
            fig.savefig(self.output_dir / "hypothesis_summary.pdf", bbox_inches="tight")

        return fig

    def plot_convergence_analysis(
        self,
        results: ExperimentResults,
        save: bool = True,
    ) -> Figure:
        """
        Plot convergence of efficiency metrics over runs.

        Shows how estimates stabilize with more data (running mean and CI).
        """
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle("Convergence Analysis", fontsize=14, fontweight="bold")

        alloc_eff = np.array([r.allocative_efficiency for r in results.run_results])
        vol_eff = np.array([r.volume_efficiency for r in results.run_results])
        price_err = np.array([np.abs(r.price_discovery_error) for r in results.run_results])
        revenue = np.array([r.market_maker_revenue for r in results.run_results])

        metrics = [
            (alloc_eff, "Allocative Efficiency", 0.95, axes[0, 0]),
            (vol_eff, "Volume Efficiency", 0.90, axes[0, 1]),
            (price_err, "Price Discovery Error", 0.05, axes[1, 0]),
            (revenue, "Market Maker Revenue", 0.0, axes[1, 1]),
        ]

        for data, title, threshold, ax in metrics:
            self._plot_convergence(ax, data, title, threshold)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / "convergence_analysis.png", dpi=150, bbox_inches="tight")

        return fig

    def _plot_convergence(
        self,
        ax,
        data: np.ndarray,
        title: str,
        threshold: float,
    ):
        """Helper to plot convergence of a single metric."""
        n = len(data)
        runs = np.arange(1, n + 1)

        # Running mean
        running_mean = np.cumsum(data) / runs

        # Running standard error (approximate CI)
        running_std = np.array([np.std(data[:i+1], ddof=1) if i > 0 else 0 for i in range(n)])
        running_se = running_std / np.sqrt(runs)
        ci_lower = running_mean - 1.96 * running_se
        ci_upper = running_mean + 1.96 * running_se

        ax.plot(runs, running_mean, color=self.COLORS["primary"], linewidth=2, label="Running Mean")
        ax.fill_between(runs, ci_lower, ci_upper, color=self.COLORS["primary"], alpha=0.2, label="95% CI")
        ax.axhline(threshold, color=self.COLORS["danger"], linestyle="--", linewidth=1.5, label=f"Threshold: {threshold}")

        ax.set_title(title)
        ax.set_xlabel("Number of Runs")
        ax.set_ylabel("Value")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)

    def plot_box_comparison(
        self,
        results: ExperimentResults,
        save: bool = True,
    ) -> Figure:
        """
        Create box plots comparing all efficiency metrics.

        Useful for seeing distributions and outliers at a glance.
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data
        data = [
            [r.allocative_efficiency for r in results.run_results],
            [r.volume_efficiency for r in results.run_results],
            [1 - np.abs(r.price_discovery_error) for r in results.run_results],  # Invert for consistency
            [r.buyer_ir_rate for r in results.run_results],
            [r.seller_ir_rate for r in results.run_results],
        ]

        labels = [
            "Allocative\nEfficiency",
            "Volume\nEfficiency",
            "Price Discovery\n(1 - |error|)",
            "Buyer IR\nRate",
            "Seller IR\nRate",
        ]

        thresholds = [0.95, 0.90, 0.95, 1.0, 1.0]

        bp = ax.boxplot(data, labels=labels, patch_artist=True)

        # Color boxes
        colors = [self.COLORS["primary"], self.COLORS["secondary"],
                 self.COLORS["warning"], self.COLORS["success"], self.COLORS["success"]]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        # Add threshold markers
        for i, thresh in enumerate(thresholds):
            ax.hlines(thresh, i + 0.6, i + 1.4, colors=self.COLORS["danger"],
                     linestyles="dashed", linewidth=2)

        ax.set_ylabel("Efficiency / Rate")
        ax.set_title("Efficiency Metrics Distribution", fontsize=14, fontweight="bold")
        ax.set_ylim(0, 1.1)
        ax.grid(True, axis="y", alpha=0.3)

        # Add legend for threshold
        threshold_patch = mpatches.Patch(
            facecolor="none", edgecolor=self.COLORS["danger"],
            linestyle="--", linewidth=2, label="Target Threshold"
        )
        ax.legend(handles=[threshold_patch], loc="lower right")

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / "efficiency_boxplots.png", dpi=150, bbox_inches="tight")

        return fig

    def generate_all_plots(
        self,
        results: ExperimentResults,
        show: bool = False,
    ) -> List[Figure]:
        """
        Generate all visualization plots.

        Args:
            results: Experiment results
            show: Whether to display plots (True) or just save (False)

        Returns:
            List of generated Figure objects
        """
        figures = []

        # 1. Efficiency distributions
        fig1 = self.plot_efficiency_distributions(results)
        figures.append(fig1)

        # 2. Hypothesis summary
        fig2 = self.plot_hypothesis_summary(results.hypothesis_results)
        figures.append(fig2)

        # 3. Convergence analysis
        fig3 = self.plot_convergence_analysis(results)
        figures.append(fig3)

        # 4. Box plot comparison
        fig4 = self.plot_box_comparison(results)
        figures.append(fig4)

        # 5. Supply/demand curves for first equilibrium
        if results.walrasian_equilibria:
            fig5 = self.plot_supply_demand_curves(
                results.walrasian_equilibria[0],
                title="Example Supply-Demand Equilibrium (Run 1)"
            )
            figures.append(fig5)

        if show:
            plt.show()

        return figures

    def close_all(self):
        """Close all open figures to free memory."""
        plt.close("all")
