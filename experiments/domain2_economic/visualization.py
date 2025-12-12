"""
Visualization Module for Economic Performance (Domain 2).

Generates publication-quality plots for economic performance validation:
- ROI distribution by agent type (violin plot)
- Lorenz curve with Gini annotation
- Price volatility over time
- Spread time series
- Liquidity depth chart
- Hypothesis test summary
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure
    from matplotlib.gridspec import GridSpec
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from .roi_calculator import RoiDistribution, RoiResult
from .fairness_metrics import calculate_lorenz_curve, calculate_gini_coefficient
from .liquidity_metrics import (
    SpreadMetrics,
    DepthMetrics,
    VolatilityMetrics,
    OrderBookSnapshot,
)
from .hypothesis_tests import EconomicHypothesisResult


class EconomicVisualizer:
    """
    Generate visualizations for economic performance experiments.

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
        "equality": "#2ECC71",     # Green for equality line
        "lorenz": "#E74C3C",       # Red for Lorenz curve
    }

    # Agent type colors
    AGENT_COLORS = {
        "RAT": "#3498DB",   # Blue - Rational
        "BND": "#E74C3C",   # Red - Bounded Rational
        "ZI": "#2ECC71",    # Green - Zero Intelligence
        "BEH": "#9B59B6",   # Purple - Behavioral
        "ADV": "#F39C12",   # Orange - Adversarial
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

        plt.rcParams.update(self.STYLE)

    def plot_roi_distribution_violin(
        self,
        roi_distribution: RoiDistribution,
        save: bool = True,
        filename: str = "roi_violin.png",
    ) -> Figure:
        """
        Plot ROI distribution by agent type as violin plot.

        Shows distribution shape, median, quartiles for each agent type.

        Args:
            roi_distribution: RoiDistribution object
            save: Whether to save the figure
            filename: Filename for saved figure

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        # Prepare data
        agent_types = sorted(roi_distribution.roi_by_type.keys())
        data = [roi_distribution.roi_by_type[t] * 100 for t in agent_types]  # Convert to percentage

        # Create violin plot
        parts = ax.violinplot(
            data,
            positions=range(len(agent_types)),
            showmeans=True,
            showmedians=True,
            showextrema=True,
        )

        # Customize colors
        for i, (pc, agent_type) in enumerate(zip(parts['bodies'], agent_types)):
            color = self.AGENT_COLORS.get(agent_type, self.COLORS["neutral"])
            pc.set_facecolor(color)
            pc.set_alpha(0.7)
            pc.set_edgecolor('black')

        # Customize other parts
        for partname in ['cmeans', 'cmedians', 'cbars', 'cmins', 'cmaxes']:
            if partname in parts:
                parts[partname].set_color('black')
                parts[partname].set_linewidth(1.5)

        # Add box plot overlay for quartiles
        bp = ax.boxplot(
            data,
            positions=range(len(agent_types)),
            widths=0.1,
            patch_artist=True,
            showfliers=False,
        )

        for patch in bp['boxes']:
            patch.set_facecolor('white')
            patch.set_alpha(0.8)

        # Add threshold line
        ax.axhline(15, color=self.COLORS["success"], linestyle="--", linewidth=2, label="15% Target ROI")
        ax.axhline(0, color=self.COLORS["neutral"], linestyle="-", linewidth=1, alpha=0.5)

        # Labels
        ax.set_xticks(range(len(agent_types)))
        ax.set_xticklabels([self._agent_type_label(t) for t in agent_types])
        ax.set_xlabel("Agent Type")
        ax.set_ylabel("ROI (%)")
        ax.set_title("ROI Distribution by Agent Type", fontsize=14, fontweight="bold")

        # Add statistics annotation
        stats_text = []
        for i, agent_type in enumerate(agent_types):
            rois = roi_distribution.roi_by_type[agent_type] * 100
            stats_text.append(f"{agent_type}: μ={np.mean(rois):.1f}%, n={len(rois)}")

        ax.text(
            0.02, 0.98, "\n".join(stats_text),
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

        ax.legend(loc="upper right")
        ax.grid(True, axis="y", alpha=0.3)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")
            fig.savefig(self.output_dir / filename.replace(".png", ".pdf"), bbox_inches="tight")

        return fig

    def _agent_type_label(self, agent_type: str) -> str:
        """Convert agent type code to readable label."""
        labels = {
            "RAT": "Rational",
            "BND": "Bounded\nRational",
            "ZI": "Zero\nIntelligence",
            "BEH": "Behavioral",
            "ADV": "Adversarial",
        }
        return labels.get(agent_type, agent_type)

    def plot_lorenz_curve(
        self,
        welfare_distribution: np.ndarray,
        save: bool = True,
        filename: str = "lorenz_curve.png",
    ) -> Figure:
        """
        Plot Lorenz curve with Gini coefficient annotation.

        Shows welfare inequality with area between equality line and curve.

        Args:
            welfare_distribution: Array of welfare values
            save: Whether to save the figure
            filename: Filename for saved figure

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(10, 10))

        # Calculate Lorenz curve
        pop_share, welfare_share = calculate_lorenz_curve(welfare_distribution)

        # Calculate Gini
        gini = calculate_gini_coefficient(welfare_distribution)

        # Plot equality line (45-degree line)
        ax.plot([0, 1], [0, 1], color=self.COLORS["equality"], linestyle="--",
               linewidth=2, label="Perfect Equality")

        # Plot Lorenz curve
        ax.plot(pop_share, welfare_share, color=self.COLORS["lorenz"],
               linewidth=2.5, label=f"Lorenz Curve (Gini = {gini:.3f})")

        # Fill area between curves (represents inequality)
        ax.fill_between(
            pop_share, pop_share, welfare_share,
            color=self.COLORS["lorenz"], alpha=0.2,
            label=f"Inequality Area (A = {gini/2:.3f})"
        )

        # Add Gini coefficient annotation
        ax.annotate(
            f"Gini = {gini:.3f}",
            xy=(0.5, 0.5), xytext=(0.7, 0.3),
            fontsize=16, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="black"),
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.9)
        )

        # Threshold annotation
        if gini < 0.4:
            status = "FAIR"
            status_color = self.COLORS["success"]
        else:
            status = "UNFAIR"
            status_color = self.COLORS["danger"]

        ax.text(
            0.95, 0.05,
            f"Status: {status}\n(threshold: 0.4)",
            transform=ax.transAxes,
            fontsize=12, fontweight="bold",
            color=status_color,
            ha="right", va="bottom",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.9)
        )

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Cumulative Share of Population (Poorest to Richest)")
        ax.set_ylabel("Cumulative Share of Welfare")
        ax.set_title("Lorenz Curve: Welfare Distribution", fontsize=14, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        ax.set_aspect("equal")

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")
            fig.savefig(self.output_dir / filename.replace(".png", ".pdf"), bbox_inches="tight")

        return fig

    def plot_price_volatility_time_series(
        self,
        prices: List[float],
        timestamps: Optional[List[float]] = None,
        window_size: int = 10,
        cv_threshold: float = 0.15,
        save: bool = True,
        filename: str = "price_volatility.png",
    ) -> Figure:
        """
        Plot price volatility over time with rolling CV.

        Shows price time series and rolling coefficient of variation.

        Args:
            prices: List of prices
            timestamps: Optional list of timestamps
            window_size: Rolling window size for CV calculation
            cv_threshold: CV threshold for highlighting
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

        if timestamps is None:
            timestamps = list(range(len(prices)))

        prices_arr = np.array(prices)

        # Top panel: Price time series
        ax1 = axes[0]
        ax1.plot(timestamps, prices_arr, color=self.COLORS["primary"], linewidth=1.5)
        ax1.fill_between(timestamps, prices_arr, alpha=0.3, color=self.COLORS["primary"])

        ax1.set_ylabel("Price (INR/kWh)")
        ax1.set_title("Price Time Series", fontsize=12, fontweight="bold")
        ax1.grid(True, alpha=0.3)

        # Add mean line
        mean_price = np.mean(prices_arr)
        ax1.axhline(mean_price, color=self.COLORS["neutral"], linestyle="--",
                   linewidth=1.5, label=f"Mean: {mean_price:.2f}")
        ax1.legend(loc="upper right")

        # Bottom panel: Rolling CV
        ax2 = axes[1]

        # Calculate rolling CV
        rolling_cv = []
        rolling_ts = []
        for i in range(window_size, len(prices)):
            window = prices_arr[i-window_size:i]
            cv = np.std(window) / np.mean(window) if np.mean(window) > 0 else 0
            rolling_cv.append(cv)
            rolling_ts.append(timestamps[i])

        rolling_cv_arr = np.array(rolling_cv)

        # Plot CV
        ax2.plot(rolling_ts, rolling_cv_arr, color=self.COLORS["secondary"], linewidth=1.5)

        # Fill above threshold in red
        ax2.fill_between(
            rolling_ts,
            rolling_cv_arr,
            cv_threshold,
            where=(rolling_cv_arr > cv_threshold),
            color=self.COLORS["danger"],
            alpha=0.3,
            label="High Volatility"
        )

        # Fill below threshold in green
        ax2.fill_between(
            rolling_ts,
            rolling_cv_arr,
            0,
            where=(rolling_cv_arr <= cv_threshold),
            color=self.COLORS["success"],
            alpha=0.2,
            label="Normal Volatility"
        )

        # Threshold line
        ax2.axhline(cv_threshold, color=self.COLORS["danger"], linestyle="--",
                   linewidth=2, label=f"Threshold: {cv_threshold}")

        ax2.set_xlabel("Time Period")
        ax2.set_ylabel("Coefficient of Variation")
        ax2.set_title(f"Rolling Volatility (Window = {window_size})", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, max(cv_threshold * 2, np.max(rolling_cv_arr) * 1.1))

        # Add statistics
        mean_cv = np.mean(rolling_cv_arr)
        pct_high = np.mean(rolling_cv_arr > cv_threshold) * 100
        stats_text = f"Mean CV: {mean_cv:.4f}\nHigh volatility: {pct_high:.1f}%"
        ax2.text(
            0.02, 0.98, stats_text,
            transform=ax2.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_spread_time_series(
        self,
        order_book_snapshots: List[OrderBookSnapshot],
        spread_threshold: float = 0.10,
        save: bool = True,
        filename: str = "spread_time_series.png",
    ) -> Figure:
        """
        Plot bid-ask spread over time.

        Args:
            order_book_snapshots: List of OrderBookSnapshot objects
            spread_threshold: Spread threshold for highlighting
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

        timestamps = [s.timestamp for s in order_book_snapshots]
        spreads_pct = [s.spread_pct * 100 if s.spread_pct else 0 for s in order_book_snapshots]
        mid_prices = [s.mid_price if s.mid_price else 0 for s in order_book_snapshots]

        # Top panel: Mid price with bid-ask range
        ax1 = axes[0]
        ax1.plot(timestamps, mid_prices, color=self.COLORS["primary"], linewidth=1.5, label="Mid Price")

        # Show bid-ask as shaded area
        best_bids = [s.best_bid if s.best_bid else mid_prices[i] for i, s in enumerate(order_book_snapshots)]
        best_asks = [s.best_ask if s.best_ask else mid_prices[i] for i, s in enumerate(order_book_snapshots)]

        ax1.fill_between(timestamps, best_bids, best_asks, alpha=0.3, color=self.COLORS["secondary"],
                        label="Bid-Ask Range")

        ax1.set_ylabel("Price (INR/kWh)")
        ax1.set_title("Mid Price with Bid-Ask Range", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)

        # Bottom panel: Spread percentage
        ax2 = axes[1]
        spreads_arr = np.array(spreads_pct)

        ax2.plot(timestamps, spreads_arr, color=self.COLORS["secondary"], linewidth=1.5)

        # Threshold
        threshold_pct = spread_threshold * 100
        ax2.axhline(threshold_pct, color=self.COLORS["danger"], linestyle="--",
                   linewidth=2, label=f"Threshold: {threshold_pct:.0f}%")

        # Color by threshold
        ax2.fill_between(
            timestamps, spreads_arr, threshold_pct,
            where=(spreads_arr > threshold_pct),
            color=self.COLORS["danger"], alpha=0.3
        )
        ax2.fill_between(
            timestamps, spreads_arr, 0,
            where=(spreads_arr <= threshold_pct),
            color=self.COLORS["success"], alpha=0.2
        )

        ax2.set_xlabel("Time")
        ax2.set_ylabel("Spread (%)")
        ax2.set_title("Bid-Ask Spread Over Time", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, max(threshold_pct * 2, np.max(spreads_arr) * 1.1))

        # Statistics
        mean_spread = np.mean(spreads_arr)
        pct_above = np.mean(spreads_arr > threshold_pct) * 100
        stats_text = f"Mean spread: {mean_spread:.2f}%\nAbove threshold: {pct_above:.1f}%"
        ax2.text(
            0.02, 0.98, stats_text,
            transform=ax2.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
        )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_liquidity_depth_chart(
        self,
        order_book: OrderBookSnapshot,
        n_levels: int = 10,
        save: bool = True,
        filename: str = "liquidity_depth.png",
    ) -> Figure:
        """
        Plot market depth chart showing order book.

        Args:
            order_book: OrderBookSnapshot with bids and asks
            n_levels: Number of price levels to show
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(12, 8))

        # Get bids and asks (limited to n_levels)
        bids = sorted(order_book.bids, key=lambda x: -x[0])[:n_levels]
        asks = sorted(order_book.asks, key=lambda x: x[0])[:n_levels]

        if not bids and not asks:
            ax.text(0.5, 0.5, "No order book data available",
                   ha="center", va="center", fontsize=14)
            return fig

        # Calculate cumulative depth
        bid_prices = [p for p, _ in bids]
        bid_volumes = np.cumsum([v for _, v in bids])
        ask_prices = [p for p, _ in asks]
        ask_volumes = np.cumsum([v for _, v in asks])

        # Plot bid depth (green, left side)
        if bids:
            ax.fill_between(bid_prices, 0, bid_volumes, step="post",
                           color=self.COLORS["success"], alpha=0.5, label="Bid Depth")
            ax.step(bid_prices, bid_volumes, where="post",
                   color=self.COLORS["success"], linewidth=2)

        # Plot ask depth (red, right side)
        if asks:
            ax.fill_between(ask_prices, 0, ask_volumes, step="post",
                           color=self.COLORS["danger"], alpha=0.5, label="Ask Depth")
            ax.step(ask_prices, ask_volumes, where="post",
                   color=self.COLORS["danger"], linewidth=2)

        # Mark mid price
        if order_book.mid_price:
            ax.axvline(order_book.mid_price, color=self.COLORS["neutral"],
                      linestyle="--", linewidth=2, label=f"Mid: {order_book.mid_price:.2f}")

        # Mark spread
        if order_book.best_bid and order_book.best_ask:
            ax.axvspan(order_book.best_bid, order_book.best_ask,
                      color=self.COLORS["warning"], alpha=0.2, label="Spread")

        ax.set_xlabel("Price (INR/kWh)")
        ax.set_ylabel("Cumulative Volume (kWh)")
        ax.set_title("Market Depth Chart", fontsize=14, fontweight="bold")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

        # Add info box
        if order_book.spread_pct:
            info_text = (
                f"Best Bid: {order_book.best_bid:.2f}\n"
                f"Best Ask: {order_book.best_ask:.2f}\n"
                f"Spread: {order_book.spread:.2f} ({order_book.spread_pct*100:.2f}%)"
            )
            ax.text(
                0.02, 0.98, info_text,
                transform=ax.transAxes,
                fontsize=10,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
            )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_hypothesis_summary(
        self,
        hypothesis_results: Dict[str, EconomicHypothesisResult],
        save: bool = True,
        filename: str = "hypothesis_summary.png",
    ) -> Figure:
        """
        Create visual summary of economic hypothesis test results.

        Args:
            hypothesis_results: Dictionary of hypothesis results
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 8))

        # Left panel: Pass/Fail chart
        ax1 = axes[0]
        hypotheses = sorted(hypothesis_results.keys())
        n_hyp = len(hypotheses)

        colors = []
        for h in hypotheses:
            if hypothesis_results[h].passed:
                colors.append(self.COLORS["success"])
            else:
                colors.append(self.COLORS["danger"])

        y_pos = np.arange(n_hyp)
        ax1.barh(y_pos, [1] * n_hyp, color=colors, alpha=0.8)

        # Add pass/fail labels
        for i, h in enumerate(hypotheses):
            result = hypothesis_results[h]
            status = "PASS" if result.passed else "FAIL"
            ax1.text(0.5, i, f"{h}: {status}", ha="center", va="center",
                    fontsize=11, fontweight="bold", color="white")

        ax1.set_yticks(y_pos)
        ax1.set_yticklabels([
            hypothesis_results[h].description[:35] + "..."
            if len(hypothesis_results[h].description) > 35
            else hypothesis_results[h].description
            for h in hypotheses
        ], fontsize=9)
        ax1.set_xlim(0, 1)
        ax1.set_title("Hypothesis Test Results", fontsize=12, fontweight="bold")
        ax1.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

        # Right panel: Effect sizes
        ax2 = axes[1]

        effect_sizes = []
        ci_lower = []
        ci_upper = []

        for h in hypotheses:
            result = hypothesis_results[h]
            es = result.effect_size
            if np.isnan(es) or np.isinf(es):
                es = 0
            effect_sizes.append(np.clip(es, -3, 3))
            ci_lower.append(result.confidence_interval[0])
            ci_upper.append(result.confidence_interval[1])

        ax2.barh(y_pos, effect_sizes, color=colors, alpha=0.6)

        # Add zero line
        ax2.axvline(0, color="black", linestyle="-", linewidth=1)

        ax2.set_yticks(y_pos)
        ax2.set_yticklabels([f"{h}" for h in hypotheses])
        ax2.set_xlabel("Effect Size")
        ax2.set_title("Effect Sizes", fontsize=12, fontweight="bold")
        ax2.grid(True, axis="x", alpha=0.3)

        # Summary
        passed = sum(1 for h in hypotheses if hypothesis_results[h].passed)
        total = len(hypotheses)
        fig.suptitle(
            f"Economic Performance Validation: {passed}/{total} Hypotheses Supported",
            fontsize=14, fontweight="bold", y=1.02
        )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")
            fig.savefig(self.output_dir / filename.replace(".png", ".pdf"), bbox_inches="tight")

        return fig

    def plot_roi_by_battery_size(
        self,
        roi_by_size: Dict[str, Dict[str, float]],
        save: bool = True,
        filename: str = "roi_by_battery_size.png",
    ) -> Figure:
        """
        Plot ROI comparison by battery size category.

        Args:
            roi_by_size: Dictionary with size categories and statistics
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        categories = ["small", "medium", "large"]
        labels = ["Small\n(<10 kWh)", "Medium\n(10-50 kWh)", "Large\n(>50 kWh)"]
        colors = [self.COLORS["warning"], self.COLORS["primary"], self.COLORS["secondary"]]

        x = np.arange(len(categories))
        width = 0.6

        means = []
        stds = []
        ns = []

        for cat in categories:
            if cat in roi_by_size and not np.isnan(roi_by_size[cat].get("mean", np.nan)):
                means.append(roi_by_size[cat]["mean"] * 100)
                stds.append(roi_by_size[cat].get("std", 0) * 100)
                ns.append(roi_by_size[cat].get("n", 0))
            else:
                means.append(0)
                stds.append(0)
                ns.append(0)

        bars = ax.bar(x, means, width, color=colors, alpha=0.7, yerr=stds, capsize=5)

        # Add value labels
        for i, (bar, n) in enumerate(zip(bars, ns)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + stds[i] + 1,
                   f'{height:.1f}%\n(n={n})',
                   ha='center', va='bottom', fontsize=10)

        # Threshold line
        ax.axhline(15, color=self.COLORS["success"], linestyle="--",
                  linewidth=2, label="15% Target ROI")

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("ROI (%)")
        ax.set_title("ROI by Battery Size Category", fontsize=14, fontweight="bold")
        ax.legend(loc="upper right")
        ax.grid(True, axis="y", alpha=0.3)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def generate_all_plots(
        self,
        roi_distribution: RoiDistribution,
        welfare_distribution: np.ndarray,
        prices: List[float],
        order_book_snapshots: List[OrderBookSnapshot],
        hypothesis_results: Dict[str, EconomicHypothesisResult],
        roi_by_size: Optional[Dict] = None,
        show: bool = False,
    ) -> List[Figure]:
        """
        Generate all economic visualization plots.

        Args:
            roi_distribution: ROI distribution data
            welfare_distribution: Welfare values
            prices: Price time series
            order_book_snapshots: Order book snapshots
            hypothesis_results: Hypothesis test results
            roi_by_size: Optional ROI by battery size
            show: Whether to display plots

        Returns:
            List of generated Figure objects
        """
        figures = []

        # 1. ROI violin plot
        fig1 = self.plot_roi_distribution_violin(roi_distribution)
        figures.append(fig1)

        # 2. Lorenz curve
        fig2 = self.plot_lorenz_curve(welfare_distribution)
        figures.append(fig2)

        # 3. Price volatility
        if prices:
            fig3 = self.plot_price_volatility_time_series(prices)
            figures.append(fig3)

        # 4. Spread time series
        if order_book_snapshots:
            fig4 = self.plot_spread_time_series(order_book_snapshots)
            figures.append(fig4)

        # 5. Liquidity depth chart (using last snapshot)
        if order_book_snapshots:
            fig5 = self.plot_liquidity_depth_chart(order_book_snapshots[-1])
            figures.append(fig5)

        # 6. Hypothesis summary
        fig6 = self.plot_hypothesis_summary(hypothesis_results)
        figures.append(fig6)

        # 7. ROI by battery size (if available)
        if roi_by_size:
            fig7 = self.plot_roi_by_battery_size(roi_by_size)
            figures.append(fig7)

        if show:
            plt.show()

        return figures

    def close_all(self):
        """Close all open figures to free memory."""
        plt.close("all")
