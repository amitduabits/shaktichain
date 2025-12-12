"""
Visualization for Load Forecasting (Domain 7).

Provides plotting functions for forecasting analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Check for matplotlib
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    logger.warning("matplotlib not available, visualization disabled")


@dataclass
class ForecastVisualization:
    """
    Visualization class for forecasting results.
    """

    def __init__(self, figsize: Tuple[int, int] = (12, 6)):
        """
        Initialize visualization.

        Args:
            figsize: Default figure size
        """
        self.figsize = figsize
        self.style = "seaborn-v0_8-whitegrid" if MATPLOTLIB_AVAILABLE else None

    def plot_actual_vs_predicted(
        self,
        actual: np.ndarray,
        predicted: np.ndarray,
        lower: Optional[np.ndarray] = None,
        upper: Optional[np.ndarray] = None,
        timestamps: Optional[np.ndarray] = None,
        title: str = "Actual vs Predicted Load",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot actual vs predicted values with optional confidence interval.

        Args:
            actual: Actual values
            predicted: Predicted values
            lower: Lower bound of prediction interval
            upper: Upper bound of prediction interval
            timestamps: Optional timestamps for x-axis
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available")
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        x = timestamps if timestamps is not None else np.arange(len(actual))

        # Plot actual
        ax.plot(x, actual, 'b-', label='Actual', linewidth=1.5)

        # Plot predicted
        ax.plot(x, predicted, 'r--', label='Predicted', linewidth=1.5)

        # Plot confidence interval
        if lower is not None and upper is not None:
            ax.fill_between(
                x, lower, upper,
                alpha=0.3, color='red',
                label='95% PI'
            )

        ax.set_xlabel('Time')
        ax.set_ylabel('Load (MW)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        if timestamps is not None and len(timestamps) > 0:
            if hasattr(timestamps[0], 'strftime'):
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.xticks(rotation=45)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_mape_by_horizon(
        self,
        mape_by_horizon: Dict[int, float],
        title: str = "MAPE by Forecast Horizon",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot MAPE as a function of forecast horizon.

        Args:
            mape_by_horizon: Dict mapping horizon to MAPE
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        horizons = sorted(mape_by_horizon.keys())
        mapes = [mape_by_horizon[h] for h in horizons]

        ax.bar(horizons, mapes, color='steelblue', alpha=0.7)
        ax.axhline(y=5, color='green', linestyle='--', label='H7.1 threshold (5%)')
        ax.axhline(y=10, color='orange', linestyle='--', label='H7.2 threshold (10%)')

        ax.set_xlabel('Forecast Horizon (hours)')
        ax.set_ylabel('MAPE (%)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_mape_by_city(
        self,
        city_mape: Dict[str, float],
        threshold: float = 5.0,
        title: str = "MAPE by City",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot MAPE by city as horizontal bar chart.

        Args:
            city_mape: Dict mapping city to MAPE
            threshold: MAPE threshold line
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        cities = list(city_mape.keys())
        mapes = list(city_mape.values())

        # Color based on threshold
        colors = ['green' if m < threshold else 'red' for m in mapes]

        y_pos = np.arange(len(cities))
        ax.barh(y_pos, mapes, color=colors, alpha=0.7)
        ax.axvline(x=threshold, color='orange', linestyle='--',
                   label=f'Threshold ({threshold}%)')

        ax.set_yticks(y_pos)
        ax.set_yticklabels(cities)
        ax.set_xlabel('MAPE (%)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_model_comparison(
        self,
        model_metrics: Dict[str, Dict[str, float]],
        metric: str = "mape",
        title: str = "Model Comparison",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot comparison of multiple models.

        Args:
            model_metrics: Dict mapping model name to metrics dict
            metric: Metric to compare
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        models = list(model_metrics.keys())
        values = [model_metrics[m].get(metric, 0) for m in models]

        # Sort by value
        sorted_idx = np.argsort(values)
        models = [models[i] for i in sorted_idx]
        values = [values[i] for i in sorted_idx]

        colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(models)))

        ax.barh(models, values, color=colors)
        ax.set_xlabel(metric.upper())
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='x')

        # Add value labels
        for i, v in enumerate(values):
            ax.text(v + 0.1, i, f'{v:.2f}', va='center')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_coverage_calibration(
        self,
        nominal_coverage: List[float],
        empirical_coverage: List[float],
        title: str = "Coverage Calibration",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot coverage calibration diagram.

        Args:
            nominal_coverage: List of nominal coverage levels
            empirical_coverage: List of empirical coverage values
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=(8, 8))

        # Perfect calibration line
        ax.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')

        # Actual calibration
        ax.plot(nominal_coverage, empirical_coverage, 'bo-',
                markersize=8, label='Empirical')

        # Highlight 95% nominal
        if 0.95 in nominal_coverage:
            idx = nominal_coverage.index(0.95)
            ax.axhline(y=0.90, color='red', linestyle=':',
                       label='90% target for 95% nominal')
            ax.plot(0.95, empirical_coverage[idx], 'ro', markersize=12)

        ax.set_xlabel('Nominal Coverage')
        ax.set_ylabel('Empirical Coverage')
        ax.set_title(title)
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_residual_distribution(
        self,
        residuals: np.ndarray,
        title: str = "Residual Distribution",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot distribution of forecast residuals.

        Args:
            residuals: Forecast residuals (actual - predicted)
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Histogram with KDE
        ax1 = axes[0]
        ax1.hist(residuals, bins=50, density=True, alpha=0.7,
                 color='steelblue', edgecolor='black')

        # Fit normal distribution
        mu, std = np.mean(residuals), np.std(residuals)
        x = np.linspace(residuals.min(), residuals.max(), 100)
        from scipy import stats
        ax1.plot(x, stats.norm.pdf(x, mu, std), 'r-', linewidth=2,
                 label=f'Normal fit (μ={mu:.2f}, σ={std:.2f})')

        ax1.axvline(x=0, color='green', linestyle='--', label='Zero')
        ax1.set_xlabel('Residual (MW)')
        ax1.set_ylabel('Density')
        ax1.set_title('Residual Histogram')
        ax1.legend()

        # Q-Q plot
        ax2 = axes[1]
        stats.probplot(residuals, dist="norm", plot=ax2)
        ax2.set_title('Q-Q Plot')

        plt.suptitle(title)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_hypothesis_summary(
        self,
        hypothesis_results: Dict[str, Dict[str, Any]],
        title: str = "Hypothesis Test Summary",
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

        fig, ax = plt.subplots(figsize=(10, 6))

        hypotheses = list(hypothesis_results.keys())
        passed = [hypothesis_results[h].get('passed', False) for h in hypotheses]
        p_values = [hypothesis_results[h].get('p_value', 1.0) for h in hypotheses]

        y_pos = np.arange(len(hypotheses))
        colors = ['green' if p else 'red' for p in passed]

        # Main bars
        bars = ax.barh(y_pos, p_values, color=colors, alpha=0.7)

        # Significance line
        ax.axvline(x=0.05, color='orange', linestyle='--',
                   label='α = 0.05')

        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"{h}: {'✓' if p else '✗'}" for h, p in zip(hypotheses, passed)])
        ax.set_xlabel('P-value')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')
        ax.set_xlim(0, 1)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig

    def plot_training_history(
        self,
        train_loss: List[float],
        val_loss: Optional[List[float]] = None,
        title: str = "Training History",
        save_path: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Plot training loss history.

        Args:
            train_loss: Training loss per epoch
            val_loss: Validation loss per epoch
            title: Plot title
            save_path: Path to save figure

        Returns:
            Figure object or None
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        fig, ax = plt.subplots(figsize=self.figsize)

        epochs = range(1, len(train_loss) + 1)
        ax.plot(epochs, train_loss, 'b-', label='Training Loss', linewidth=1.5)

        if val_loss:
            ax.plot(epochs, val_loss, 'r-', label='Validation Loss', linewidth=1.5)

        ax.set_xlabel('Epoch')
        ax.set_ylabel('Loss')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')

        return fig


def create_visualization_report(
    actual: np.ndarray,
    predicted: np.ndarray,
    lower: Optional[np.ndarray],
    upper: Optional[np.ndarray],
    mape_by_horizon: Dict[int, float],
    city_mape: Dict[str, float],
    model_metrics: Dict[str, Dict[str, float]],
    hypothesis_results: Dict[str, Dict[str, Any]],
    output_dir: str,
) -> Dict[str, str]:
    """
    Create full visualization report.

    Args:
        actual: Actual values
        predicted: Predicted values
        lower: Lower bounds
        upper: Upper bounds
        mape_by_horizon: MAPE by forecast horizon
        city_mape: MAPE by city
        model_metrics: Metrics by model
        hypothesis_results: Hypothesis test results
        output_dir: Output directory for plots

    Returns:
        Dict mapping plot name to file path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    viz = ForecastVisualization()
    saved_files = {}

    # Actual vs Predicted
    path = str(output_path / "actual_vs_predicted.png")
    viz.plot_actual_vs_predicted(actual, predicted, lower, upper, save_path=path)
    saved_files["actual_vs_predicted"] = path

    # MAPE by horizon
    path = str(output_path / "mape_by_horizon.png")
    viz.plot_mape_by_horizon(mape_by_horizon, save_path=path)
    saved_files["mape_by_horizon"] = path

    # MAPE by city
    path = str(output_path / "mape_by_city.png")
    viz.plot_mape_by_city(city_mape, save_path=path)
    saved_files["mape_by_city"] = path

    # Model comparison
    path = str(output_path / "model_comparison.png")
    viz.plot_model_comparison(model_metrics, save_path=path)
    saved_files["model_comparison"] = path

    # Residual distribution
    residuals = actual - predicted
    path = str(output_path / "residual_distribution.png")
    viz.plot_residual_distribution(residuals, save_path=path)
    saved_files["residual_distribution"] = path

    # Hypothesis summary
    path = str(output_path / "hypothesis_summary.png")
    viz.plot_hypothesis_summary(hypothesis_results, save_path=path)
    saved_files["hypothesis_summary"] = path

    return saved_files
