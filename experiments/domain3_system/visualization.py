"""
Visualization Module for System Performance (Domain 3).

Generates publication-quality plots for system performance validation:
- TPS vs concurrent users
- Latency distribution (histogram + CDF)
- P50, P90, P95, P99 latency vs load
- Scalability curve (measured vs fitted models)
- Gas cost distribution
- Availability timeline
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
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from .throughput_measurer import ThroughputStatistics, ThroughputMeasurement
from .latency_profiler import LatencyStatistics, LatencyPercentiles
from .scalability_analyzer import ScalabilityAnalysisResult, ModelFitResult
from .gas_cost_tracker import GasCostStatistics
from .availability_monitor import AvailabilityMetrics
from .hypothesis_tests import SystemHypothesisResult


class SystemVisualizer:
    """
    Generate visualizations for system performance experiments.

    Creates publication-quality figures with consistent styling.
    """

    # Color scheme
    COLORS = {
        "primary": "#2E86AB",
        "secondary": "#A23B72",
        "success": "#28A745",
        "warning": "#FFC107",
        "danger": "#DC3545",
        "neutral": "#6C757D",
        "tps": "#3498DB",
        "latency": "#E74C3C",
        "cost": "#2ECC71",
        "availability": "#9B59B6",
    }

    # Model colors for scalability
    MODEL_COLORS = {
        "O(1)": "#27AE60",
        "O(log n)": "#2ECC71",
        "O(sqrt(n))": "#3498DB",
        "O(n)": "#F39C12",
        "O(n log n)": "#E67E22",
        "O(n^2)": "#E74C3C",
        "measured": "#2C3E50",
    }

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
            output_dir: Directory for saving plots
        """
        if not HAS_MATPLOTLIB:
            raise ImportError("matplotlib is required for visualization")

        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        plt.rcParams.update(self.STYLE)

    def plot_tps_vs_load(
        self,
        load_levels: List[int],
        mean_tps: List[float],
        std_tps: Optional[List[float]] = None,
        target_tps: float = 10000,
        save: bool = True,
        filename: str = "tps_vs_load.png",
    ) -> Figure:
        """
        Plot TPS vs concurrent users.

        Args:
            load_levels: List of concurrent user counts
            mean_tps: Mean TPS at each load level
            std_tps: Optional standard deviation at each level
            target_tps: Target TPS threshold
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        x = np.array(load_levels)
        y = np.array(mean_tps)

        # Plot line with markers
        ax.plot(x, y, 'o-', color=self.COLORS["tps"], linewidth=2,
                markersize=8, label="Measured TPS")

        # Add error bars if provided
        if std_tps is not None:
            yerr = np.array(std_tps)
            ax.fill_between(x, y - yerr, y + yerr, alpha=0.2, color=self.COLORS["tps"])

        # Target line
        ax.axhline(target_tps, color=self.COLORS["success"], linestyle="--",
                   linewidth=2, label=f"Target: {target_tps:,.0f} TPS")

        # Identify if/where target is met
        meets_target = y >= target_tps
        if np.any(meets_target):
            first_meet = load_levels[np.argmax(meets_target)]
            ax.axvline(first_meet, color=self.COLORS["warning"], linestyle=":",
                       linewidth=1.5, alpha=0.7)

        ax.set_xlabel("Concurrent Users")
        ax.set_ylabel("Transactions Per Second (TPS)")
        ax.set_title("Throughput vs Load", fontsize=14, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)

        # Format y-axis with thousands separator
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_latency_distribution(
        self,
        latencies: np.ndarray,
        p95_threshold: float = 100.0,
        save: bool = True,
        filename: str = "latency_distribution.png",
    ) -> Figure:
        """
        Plot latency distribution histogram and CDF.

        Args:
            latencies: Array of latency values in ms
            p95_threshold: P95 threshold line
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Left: Histogram
        ax1 = axes[0]
        n_bins = min(100, max(20, len(latencies) // 50))
        ax1.hist(latencies, bins=n_bins, density=True, alpha=0.7,
                 color=self.COLORS["latency"], edgecolor='black', linewidth=0.5)

        # Add percentile lines
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)

        ax1.axvline(p50, color=self.COLORS["success"], linestyle="-",
                    linewidth=2, label=f"P50: {p50:.1f}ms")
        ax1.axvline(p95, color=self.COLORS["warning"], linestyle="--",
                    linewidth=2, label=f"P95: {p95:.1f}ms")
        ax1.axvline(p99, color=self.COLORS["danger"], linestyle=":",
                    linewidth=2, label=f"P99: {p99:.1f}ms")
        ax1.axvline(p95_threshold, color="black", linestyle="--",
                    linewidth=1.5, alpha=0.5, label=f"Threshold: {p95_threshold}ms")

        ax1.set_xlabel("Latency (ms)")
        ax1.set_ylabel("Density")
        ax1.set_title("Latency Distribution", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3)

        # Right: CDF
        ax2 = axes[1]
        sorted_lat = np.sort(latencies)
        cdf = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat)

        ax2.plot(sorted_lat, cdf * 100, color=self.COLORS["latency"], linewidth=2)

        # Add percentile markers
        for pct, color, style in [(50, self.COLORS["success"], "-"),
                                   (95, self.COLORS["warning"], "--"),
                                   (99, self.COLORS["danger"], ":")]:
            p_val = np.percentile(latencies, pct)
            ax2.axhline(pct, color=color, linestyle=style, alpha=0.5, linewidth=1)
            ax2.axvline(p_val, color=color, linestyle=style, alpha=0.5, linewidth=1)
            ax2.plot(p_val, pct, 'o', color=color, markersize=8)

        ax2.axvline(p95_threshold, color="black", linestyle="--",
                    linewidth=1.5, alpha=0.5)

        ax2.set_xlabel("Latency (ms)")
        ax2.set_ylabel("Cumulative Percentage")
        ax2.set_title("Latency CDF", fontsize=12, fontweight="bold")
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_latency_percentiles_vs_load(
        self,
        load_levels: List[int],
        percentiles_by_load: Dict[int, Dict[str, float]],
        p95_threshold: float = 100.0,
        save: bool = True,
        filename: str = "latency_percentiles.png",
    ) -> Figure:
        """
        Plot latency percentiles (P50, P90, P95, P99) vs load.

        Args:
            load_levels: List of load levels
            percentiles_by_load: Dict mapping load to percentile dict
            p95_threshold: P95 threshold
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        x = np.array(load_levels)

        percentile_colors = {
            "p50": self.COLORS["success"],
            "p90": self.COLORS["warning"],
            "p95": self.COLORS["danger"],
            "p99": self.COLORS["secondary"],
        }

        for pct_name, color in percentile_colors.items():
            y = [percentiles_by_load.get(load, {}).get(pct_name, 0) for load in load_levels]
            ax.plot(x, y, 'o-', color=color, linewidth=2, markersize=6,
                    label=pct_name.upper())

        # P95 threshold
        ax.axhline(p95_threshold, color="black", linestyle="--",
                   linewidth=2, alpha=0.7, label=f"P95 Threshold: {p95_threshold}ms")

        ax.set_xlabel("Concurrent Users")
        ax.set_ylabel("Latency (ms)")
        ax.set_title("Latency Percentiles vs Load", fontsize=14, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_scalability_curve(
        self,
        scalability_result: ScalabilityAnalysisResult,
        save: bool = True,
        filename: str = "scalability_curve.png",
    ) -> Figure:
        """
        Plot scalability curve with fitted models.

        Args:
            scalability_result: ScalabilityAnalysisResult
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(12, 8))

        # Extract measurements
        measurements = scalability_result.measurements
        n_values = np.array([m[0] for m in measurements])
        time_values = np.array([m[1] for m in measurements])

        # Plot measured points
        ax.scatter(n_values, time_values, s=100, color=self.MODEL_COLORS["measured"],
                   marker='o', label="Measured", zorder=5)

        # Generate smooth x for model curves
        x_smooth = np.linspace(min(n_values), max(n_values), 200)

        # Plot fitted models
        for model_name, fit in scalability_result.model_fits.items():
            if fit.prediction_function is not None and fit.r_squared > 0:
                try:
                    y_smooth = fit.predict(x_smooth)
                    color = self.MODEL_COLORS.get(model_name, self.COLORS["neutral"])
                    linestyle = "-" if model_name == scalability_result.best_model else "--"
                    linewidth = 2.5 if model_name == scalability_result.best_model else 1.5
                    alpha = 1.0 if model_name == scalability_result.best_model else 0.6

                    ax.plot(x_smooth, y_smooth, linestyle=linestyle, color=color,
                            linewidth=linewidth, alpha=alpha,
                            label=f"{model_name} (R^2={fit.r_squared:.3f})")
                except Exception:
                    pass

        ax.set_xlabel("Number of Agents (n)")
        ax.set_ylabel("Processing Time (ms)")
        ax.set_title(f"Scalability Analysis - Best Fit: {scalability_result.best_model}",
                     fontsize=14, fontweight="bold")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.3)

        # Add complexity class annotation
        status = "ACCEPTABLE" if scalability_result.is_acceptable else "NOT ACCEPTABLE"
        status_color = self.COLORS["success"] if scalability_result.is_acceptable else self.COLORS["danger"]

        ax.text(0.98, 0.02,
                f"Complexity: {scalability_result.complexity_class}\nStatus: {status}",
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=status_color, ha="right", va="bottom",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_gas_cost_distribution(
        self,
        gas_costs: np.ndarray,
        threshold: float = 1.0,
        save: bool = True,
        filename: str = "gas_cost_distribution.png",
    ) -> Figure:
        """
        Plot gas cost distribution histogram.

        Args:
            gas_costs: Array of costs in INR
            threshold: Cost threshold
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        n_bins = min(50, max(20, len(gas_costs) // 20))
        ax.hist(gas_costs, bins=n_bins, density=False, alpha=0.7,
                color=self.COLORS["cost"], edgecolor='black', linewidth=0.5)

        # Add statistics
        mean_cost = np.mean(gas_costs)
        median_cost = np.median(gas_costs)

        ax.axvline(mean_cost, color=self.COLORS["primary"], linestyle="-",
                   linewidth=2, label=f"Mean: {mean_cost:.4f} INR")
        ax.axvline(median_cost, color=self.COLORS["secondary"], linestyle="--",
                   linewidth=2, label=f"Median: {median_cost:.4f} INR")
        ax.axvline(threshold, color=self.COLORS["danger"], linestyle=":",
                   linewidth=2, label=f"Threshold: {threshold:.2f} INR")

        # Status annotation
        pct_below = np.mean(gas_costs < threshold) * 100
        status = "PASS" if mean_cost < threshold else "FAIL"
        status_color = self.COLORS["success"] if mean_cost < threshold else self.COLORS["danger"]

        ax.text(0.98, 0.98,
                f"Mean: {mean_cost:.4f} INR\n{pct_below:.1f}% below threshold\nStatus: {status}",
                transform=ax.transAxes, fontsize=10, fontweight="bold",
                color=status_color, ha="right", va="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

        ax.set_xlabel("Transaction Cost (INR)")
        ax.set_ylabel("Count")
        ax.set_title("Gas Cost Distribution", fontsize=14, fontweight="bold")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_availability_timeline(
        self,
        timestamps: np.ndarray,
        availability_pct: np.ndarray,
        threshold: float = 99.9,
        save: bool = True,
        filename: str = "availability_timeline.png",
    ) -> Figure:
        """
        Plot availability over time.

        Args:
            timestamps: Array of timestamps
            availability_pct: Array of availability percentages
            threshold: SLA threshold
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=(14, 6))

        ax.plot(timestamps, availability_pct, color=self.COLORS["availability"],
                linewidth=1.5)
        ax.fill_between(timestamps, 0, availability_pct, alpha=0.3,
                        color=self.COLORS["availability"])

        # SLA threshold
        ax.axhline(threshold, color=self.COLORS["danger"], linestyle="--",
                   linewidth=2, label=f"SLA: {threshold}%")

        # Highlight below-SLA periods
        below_sla = availability_pct < threshold
        if np.any(below_sla):
            ax.fill_between(timestamps, 0, 100,
                            where=below_sla, alpha=0.2,
                            color=self.COLORS["danger"])

        ax.set_xlabel("Time")
        ax.set_ylabel("Availability (%)")
        ax.set_title("System Availability Over Time", fontsize=14, fontweight="bold")
        ax.set_ylim(min(95, np.min(availability_pct) - 1), 100.5)
        ax.legend(loc="lower left")
        ax.grid(True, alpha=0.3)

        # Overall stats
        mean_avail = np.mean(availability_pct)
        ax.text(0.98, 0.02,
                f"Mean: {mean_avail:.3f}%",
                transform=ax.transAxes, fontsize=10, fontweight="bold",
                ha="right", va="bottom",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def plot_hypothesis_summary(
        self,
        hypothesis_results: Dict[str, SystemHypothesisResult],
        save: bool = True,
        filename: str = "hypothesis_summary.png",
    ) -> Figure:
        """
        Create visual summary of system hypothesis test results.

        Args:
            hypothesis_results: Dictionary of hypothesis results
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 8))

        hypotheses = sorted(hypothesis_results.keys())
        n_hyp = len(hypotheses)

        # Left: Pass/Fail bars
        ax1 = axes[0]

        colors = []
        for h in hypotheses:
            if hypothesis_results[h].passed:
                colors.append(self.COLORS["success"])
            else:
                colors.append(self.COLORS["danger"])

        y_pos = np.arange(n_hyp)
        ax1.barh(y_pos, [1] * n_hyp, color=colors, alpha=0.8)

        for i, h in enumerate(hypotheses):
            result = hypothesis_results[h]
            status = "PASS" if result.passed else "FAIL"
            ax1.text(0.5, i, f"{h}: {status}", ha="center", va="center",
                     fontsize=11, fontweight="bold", color="white")

        ax1.set_yticks(y_pos)
        ax1.set_yticklabels([
            hypothesis_results[h].description[:30] + "..."
            if len(hypothesis_results[h].description) > 30
            else hypothesis_results[h].description
            for h in hypotheses
        ], fontsize=9)
        ax1.set_xlim(0, 1)
        ax1.set_title("Hypothesis Test Results", fontsize=12, fontweight="bold")
        ax1.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

        # Right: Observed vs Threshold
        ax2 = axes[1]

        # Normalize observed/threshold for comparison
        observed = []
        thresholds = []

        for h in hypotheses:
            result = hypothesis_results[h]
            obs = result.observed_value
            thresh = result.threshold

            # Normalize
            if thresh != 0:
                ratio = obs / thresh
            else:
                ratio = 1

            observed.append(ratio)
            thresholds.append(1.0)  # Normalized threshold = 1

        ax2.barh(y_pos - 0.2, observed, height=0.4, color=colors, alpha=0.6,
                 label="Observed / Threshold")
        ax2.axvline(1.0, color="black", linestyle="--", linewidth=2,
                    label="Threshold")

        ax2.set_yticks(y_pos)
        ax2.set_yticklabels([f"{h}" for h in hypotheses])
        ax2.set_xlabel("Ratio (Observed / Threshold)")
        ax2.set_title("Performance vs Threshold", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper right")
        ax2.grid(True, axis="x", alpha=0.3)

        # Summary
        passed = sum(1 for h in hypotheses if hypothesis_results[h].passed)
        total = len(hypotheses)
        fig.suptitle(
            f"System Performance Validation: {passed}/{total} Hypotheses Supported",
            fontsize=14, fontweight="bold", y=1.02
        )

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")
            fig.savefig(self.output_dir / filename.replace(".png", ".pdf"), bbox_inches="tight")

        return fig

    def plot_settlement_finality(
        self,
        finality_times: np.ndarray,
        target_seconds: float = 30.0,
        save: bool = True,
        filename: str = "settlement_finality.png",
    ) -> Figure:
        """
        Plot settlement finality time distribution.

        Args:
            finality_times: Array of finality times in seconds
            target_seconds: Target finality time
            save: Whether to save
            filename: Filename

        Returns:
            matplotlib Figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Left: Histogram
        ax1 = axes[0]
        n_bins = min(50, max(20, len(finality_times) // 20))
        ax1.hist(finality_times, bins=n_bins, density=False, alpha=0.7,
                 color=self.COLORS["primary"], edgecolor='black', linewidth=0.5)

        ax1.axvline(target_seconds, color=self.COLORS["danger"], linestyle="--",
                    linewidth=2, label=f"Target: {target_seconds}s")

        within_target = np.sum(finality_times <= target_seconds)
        total = len(finality_times)
        rate = within_target / total * 100

        ax1.text(0.98, 0.98,
                 f"{within_target}/{total} ({rate:.2f}%)\nwithin {target_seconds}s",
                 transform=ax1.transAxes, fontsize=10,
                 ha="right", va="top",
                 bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

        ax1.set_xlabel("Finality Time (seconds)")
        ax1.set_ylabel("Count")
        ax1.set_title("Settlement Finality Distribution", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right")
        ax1.grid(True, alpha=0.3, axis='y')

        # Right: CDF
        ax2 = axes[1]
        sorted_times = np.sort(finality_times)
        cdf = np.arange(1, len(sorted_times) + 1) / len(sorted_times) * 100

        ax2.plot(sorted_times, cdf, color=self.COLORS["primary"], linewidth=2)
        ax2.axvline(target_seconds, color=self.COLORS["danger"], linestyle="--",
                    linewidth=2)
        ax2.axhline(99.9, color=self.COLORS["warning"], linestyle=":",
                    linewidth=1.5, label="99.9% SLA")

        ax2.set_xlabel("Finality Time (seconds)")
        ax2.set_ylabel("Cumulative Percentage")
        ax2.set_title("Settlement Finality CDF", fontsize=12, fontweight="bold")
        ax2.legend(loc="lower right")
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100.5)

        plt.tight_layout()

        if save and self.output_dir:
            fig.savefig(self.output_dir / filename, dpi=150, bbox_inches="tight")

        return fig

    def generate_all_plots(
        self,
        tps_samples: np.ndarray,
        latency_samples: np.ndarray,
        finality_times: np.ndarray,
        scalability_result: ScalabilityAnalysisResult,
        gas_costs: np.ndarray,
        availability_timestamps: np.ndarray,
        availability_pct: np.ndarray,
        hypothesis_results: Dict[str, SystemHypothesisResult],
        load_levels: Optional[List[int]] = None,
        show: bool = False,
    ) -> List[Figure]:
        """
        Generate all system performance plots.

        Returns:
            List of generated Figure objects
        """
        figures = []

        # 1. TPS time series / distribution
        if len(tps_samples) > 0:
            fig1, ax = plt.subplots(figsize=(12, 6))
            ax.plot(tps_samples, color=self.COLORS["tps"], linewidth=1)
            ax.axhline(10000, color=self.COLORS["success"], linestyle="--",
                       label="Target: 10,000 TPS")
            ax.set_xlabel("Sample")
            ax.set_ylabel("TPS")
            ax.set_title("TPS Over Time")
            ax.legend()
            ax.grid(True, alpha=0.3)
            if self.output_dir:
                fig1.savefig(self.output_dir / "tps_timeseries.png", dpi=150)
            figures.append(fig1)

        # 2. Latency distribution
        if len(latency_samples) > 0:
            fig2 = self.plot_latency_distribution(latency_samples)
            figures.append(fig2)

        # 3. Settlement finality
        if len(finality_times) > 0:
            fig3 = self.plot_settlement_finality(finality_times)
            figures.append(fig3)

        # 4. Scalability
        if scalability_result.measurements:
            fig4 = self.plot_scalability_curve(scalability_result)
            figures.append(fig4)

        # 5. Gas costs
        if len(gas_costs) > 0:
            fig5 = self.plot_gas_cost_distribution(gas_costs)
            figures.append(fig5)

        # 6. Availability
        if len(availability_timestamps) > 0 and len(availability_pct) > 0:
            fig6 = self.plot_availability_timeline(availability_timestamps, availability_pct)
            figures.append(fig6)

        # 7. Hypothesis summary
        if hypothesis_results:
            fig7 = self.plot_hypothesis_summary(hypothesis_results)
            figures.append(fig7)

        if show:
            plt.show()

        return figures

    def close_all(self):
        """Close all open figures."""
        plt.close("all")
