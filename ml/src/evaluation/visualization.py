"""Visualization utilities for SHAKTI-CHAIN forecast evaluation."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try to import plotting libraries
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not installed. Visualization functions will not work.")

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


def set_plot_style():
    """Set consistent plot style."""
    if not HAS_MATPLOTLIB:
        return

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "legend.fontsize": 9,
        "figure.figsize": (12, 6),
        "figure.dpi": 100,
    })


def plot_predictions_vs_actuals(
    predictions: np.ndarray,
    targets: np.ndarray,
    timestamps: Optional[pd.DatetimeIndex] = None,
    quantiles: Optional[List[float]] = None,
    title: str = "Predictions vs Actuals",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot predictions against actual values with uncertainty bands.

    Args:
        predictions: Predicted values (horizon,) or (horizon, num_quantiles)
        targets: Actual values (horizon,)
        timestamps: Optional timestamps for x-axis
        quantiles: List of quantiles if predictions has multiple columns
        title: Plot title
        save_path: Optional path to save the figure

    Returns:
        Matplotlib Figure or None if matplotlib not available
    """
    if not HAS_MATPLOTLIB:
        logger.warning("matplotlib not installed, skipping plot")
        return None

    set_plot_style()
    fig, ax = plt.subplots(figsize=(14, 6))

    # Create x-axis
    if timestamps is not None:
        x = timestamps
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    else:
        x = np.arange(len(targets))

    # Plot actuals
    ax.plot(x, targets, "b-", label="Actual", linewidth=1.5)

    # Plot predictions
    if len(predictions.shape) == 1 or (quantiles is None):
        # Point predictions
        ax.plot(x, predictions, "r--", label="Predicted", linewidth=1.5)
    else:
        # Quantile predictions
        median_idx = quantiles.index(0.5) if 0.5 in quantiles else len(quantiles) // 2
        ax.plot(x, predictions[:, median_idx], "r-", label="Predicted (median)", linewidth=1.5)

        # Plot prediction intervals
        if 0.1 in quantiles and 0.9 in quantiles:
            q10_idx = quantiles.index(0.1)
            q90_idx = quantiles.index(0.9)
            ax.fill_between(
                x,
                predictions[:, q10_idx],
                predictions[:, q90_idx],
                alpha=0.3,
                color="red",
                label="80% PI"
            )

    ax.set_xlabel("Time")
    ax.set_ylabel("Load (MW)")
    ax.set_title(title)
    ax.legend()

    if timestamps is not None:
        plt.xticks(rotation=45)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {save_path}")

    return fig


def plot_error_distribution(
    predictions: np.ndarray,
    targets: np.ndarray,
    title: str = "Error Distribution",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot distribution of forecast errors.

    Args:
        predictions: Predicted values
        targets: Actual values
        title: Plot title
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB:
        return None

    set_plot_style()
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    errors = predictions.flatten() - targets.flatten()

    # Histogram
    axes[0].hist(errors, bins=50, edgecolor="black", alpha=0.7)
    axes[0].axvline(0, color="red", linestyle="--", linewidth=2)
    axes[0].set_xlabel("Error (MW)")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title("Error Distribution")

    # Q-Q plot
    from scipy import stats
    stats.probplot(errors, dist="norm", plot=axes[1])
    axes[1].set_title("Q-Q Plot (Normal)")

    # Error vs Actual scatter
    axes[2].scatter(targets.flatten(), errors, alpha=0.3, s=10)
    axes[2].axhline(0, color="red", linestyle="--")
    axes[2].set_xlabel("Actual Load (MW)")
    axes[2].set_ylabel("Error (MW)")
    axes[2].set_title("Error vs Actual")

    plt.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_metrics_by_horizon(
    results: "EvaluationResults",
    metrics: List[str] = ["mape", "mae", "rmse"],
    title: str = "Metrics by Forecast Horizon",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot evaluation metrics across different forecast horizons.

    Args:
        results: EvaluationResults object
        metrics: List of metrics to plot
        title: Plot title
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB:
        return None

    set_plot_style()
    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(5 * n_metrics, 5))

    if n_metrics == 1:
        axes = [axes]

    horizons = sorted(results.by_horizon.keys())

    for i, metric in enumerate(metrics):
        values = [results.by_horizon[h].get(metric, {}).mean for h in horizons]
        axes[i].bar(horizons, values, color=f"C{i}", edgecolor="black")
        axes[i].set_xlabel("Forecast Horizon (hours)")
        axes[i].set_ylabel(metric.upper())
        axes[i].set_title(f"{metric.upper()} by Horizon")

    plt.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_metrics_by_dimension(
    results: "EvaluationResults",
    metric: str = "mape",
    title: str = "MAPE by Evaluation Dimension",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot a metric across all evaluation dimensions.

    Args:
        results: EvaluationResults object
        metric: Metric to plot
        title: Plot title
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB:
        return None

    set_plot_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # By Time Period
    if results.by_time_period:
        periods = list(results.by_time_period.keys())
        values = [results.by_time_period[p].get(metric, {}).mean for p in periods]
        axes[0, 0].bar(periods, values, color="steelblue", edgecolor="black")
        axes[0, 0].set_title(f"{metric.upper()} by Time Period")
        axes[0, 0].set_ylabel(metric.upper())

    # By Season
    if results.by_season:
        seasons = list(results.by_season.keys())
        values = [results.by_season[s].get(metric, {}).mean for s in seasons]
        axes[0, 1].bar(seasons, values, color="orange", edgecolor="black")
        axes[0, 1].set_title(f"{metric.upper()} by Season")

    # By Day Type
    if results.by_day_type:
        day_types = list(results.by_day_type.keys())
        values = [results.by_day_type[d].get(metric, {}).mean for d in day_types]
        axes[1, 0].bar(day_types, values, color="green", edgecolor="black")
        axes[1, 0].set_title(f"{metric.upper()} by Day Type")
        axes[1, 0].set_ylabel(metric.upper())

    # By Horizon
    if results.by_horizon:
        horizons = sorted(results.by_horizon.keys())
        values = [results.by_horizon[h].get(metric, {}).mean for h in horizons]
        axes[1, 1].bar([str(h) + "h" for h in horizons], values, color="purple", edgecolor="black")
        axes[1, 1].set_title(f"{metric.upper()} by Horizon")

    plt.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_model_comparison(
    model_results: Dict[str, "EvaluationResults"],
    metrics: List[str] = ["mape", "mae", "rmse", "coverage_90"],
    title: str = "Model Comparison",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot comparison of multiple models.

    Args:
        model_results: Dictionary mapping model names to results
        metrics: List of metrics to compare
        title: Plot title
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB:
        return None

    set_plot_style()
    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(4 * n_metrics, 6))

    if n_metrics == 1:
        axes = [axes]

    models = list(model_results.keys())
    x = np.arange(len(models))
    width = 0.6

    for i, metric in enumerate(metrics):
        values = [model_results[m].overall.get(metric, {}).mean for m in models]

        bars = axes[i].bar(x, values, width, color=[f"C{j}" for j in range(len(models))], edgecolor="black")
        axes[i].set_xticks(x)
        axes[i].set_xticklabels(models, rotation=45, ha="right")
        axes[i].set_ylabel(metric.upper())
        axes[i].set_title(metric.upper())

        # Add value labels on bars
        for bar, val in zip(bars, values):
            if not np.isnan(val):
                axes[i].annotate(
                    f"{val:.2f}",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

    plt.suptitle(title, fontsize=14, y=1.02)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_cv_results(
    cv_results: Dict[str, "CVResults"],
    metric: str = "mape",
    title: str = "Cross-Validation Results",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot cross-validation results with error bars.

    Args:
        cv_results: Dictionary mapping model names to CVResults
        metric: Metric to plot
        title: Plot title
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB:
        return None

    set_plot_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    models = list(cv_results.keys())
    means = [cv_results[m].mean_metrics.get(metric, np.nan) for m in models]
    stds = [cv_results[m].std_metrics.get(metric, np.nan) for m in models]

    x = np.arange(len(models))
    bars = ax.bar(x, means, yerr=stds, capsize=5, color="steelblue", edgecolor="black", alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=45, ha="right")
    ax.set_ylabel(f"{metric.upper()}")
    ax.set_title(title)

    # Add value labels
    for bar, mean, std in zip(bars, means, stds):
        if not np.isnan(mean):
            ax.annotate(
                f"{mean:.2f}±{std:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height() + std),
                ha="center",
                va="bottom",
                fontsize=9,
            )

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_attention_weights(
    attention_weights: np.ndarray,
    encoder_timestamps: Optional[pd.DatetimeIndex] = None,
    decoder_timestamps: Optional[pd.DatetimeIndex] = None,
    title: str = "TFT Attention Weights",
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot TFT attention weights as heatmap.

    Args:
        attention_weights: Attention weights (decoder_length, encoder_length)
        encoder_timestamps: Timestamps for encoder (historical)
        decoder_timestamps: Timestamps for decoder (future)
        title: Plot title
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB or not HAS_SEABORN:
        return None

    set_plot_style()
    fig, ax = plt.subplots(figsize=(14, 8))

    # Create labels
    if encoder_timestamps is not None:
        x_labels = [ts.strftime("%d %H:%M") for ts in encoder_timestamps[::24]]
        x_ticks = np.arange(0, len(encoder_timestamps), 24)
    else:
        x_labels = [f"-{i}h" for i in range(attention_weights.shape[1], 0, -24)]
        x_ticks = np.arange(0, attention_weights.shape[1], 24)

    if decoder_timestamps is not None:
        y_labels = [ts.strftime("%d %H:%M") for ts in decoder_timestamps[::6]]
        y_ticks = np.arange(0, len(decoder_timestamps), 6)
    else:
        y_labels = [f"+{i}h" for i in range(0, attention_weights.shape[0], 6)]
        y_ticks = np.arange(0, attention_weights.shape[0], 6)

    # Plot heatmap
    sns.heatmap(attention_weights, ax=ax, cmap="YlOrRd", cbar_kws={"label": "Attention Weight"})

    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)

    ax.set_xlabel("Historical Time")
    ax.set_ylabel("Forecast Time")
    ax.set_title(title)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_feature_importance(
    importance_scores: Dict[str, float],
    title: str = "Feature Importance",
    top_n: int = 20,
    save_path: Optional[str] = None,
) -> Optional[Figure]:
    """Plot feature importance scores.

    Args:
        importance_scores: Dictionary mapping feature names to importance
        title: Plot title
        top_n: Number of top features to show
        save_path: Optional path to save

    Returns:
        Matplotlib Figure or None
    """
    if not HAS_MATPLOTLIB:
        return None

    set_plot_style()
    fig, ax = plt.subplots(figsize=(10, max(6, top_n * 0.3)))

    # Sort and take top N
    sorted_items = sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    features, scores = zip(*sorted_items)

    y_pos = np.arange(len(features))
    ax.barh(y_pos, scores, color="steelblue", edgecolor="black")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features)
    ax.invert_yaxis()
    ax.set_xlabel("Importance Score")
    ax.set_title(title)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def create_evaluation_report_plots(
    results: "EvaluationResults",
    model_name: str,
    output_dir: str = "evaluation_plots",
) -> Dict[str, str]:
    """Create all evaluation plots and save to directory.

    Args:
        results: EvaluationResults object
        model_name: Name of the model
        output_dir: Directory to save plots

    Returns:
        Dictionary mapping plot names to file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    saved_plots = {}

    # Metrics by horizon
    fig = plot_metrics_by_horizon(
        results,
        title=f"{model_name}: Metrics by Forecast Horizon",
        save_path=str(output_path / "metrics_by_horizon.png"),
    )
    if fig:
        saved_plots["metrics_by_horizon"] = str(output_path / "metrics_by_horizon.png")
        plt.close(fig)

    # Metrics by dimension
    fig = plot_metrics_by_dimension(
        results,
        title=f"{model_name}: MAPE by Evaluation Dimension",
        save_path=str(output_path / "metrics_by_dimension.png"),
    )
    if fig:
        saved_plots["metrics_by_dimension"] = str(output_path / "metrics_by_dimension.png")
        plt.close(fig)

    return saved_plots
