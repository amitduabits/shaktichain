"""Visualization utilities for ML model explainability.

Provides functions to create various visualizations:
- SHAP waterfall and summary plots
- Attention heatmaps
- Decision factor charts
- Feature importance plots
"""

import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports with fallbacks
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available. Visualizations will return data only.")

try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    SEABORN_AVAILABLE = False


def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{img_str}"


def _fig_to_svg(fig) -> str:
    """Convert matplotlib figure to SVG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    buf.seek(0)
    svg_str = buf.read().decode("utf-8")
    plt.close(fig)
    return svg_str


def plot_shap_waterfall(
    base_value: float,
    shap_values: Union[np.ndarray, List[float]],
    feature_names: List[str],
    feature_values: Optional[Union[np.ndarray, List[float]]] = None,
    max_display: int = 10,
    title: str = "SHAP Waterfall Plot",
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Create a SHAP waterfall plot showing feature contributions.

    Args:
        base_value: Baseline/expected value
        shap_values: SHAP values for each feature
        feature_names: Names of features
        feature_values: Optional feature values to display
        max_display: Maximum features to display
        title: Plot title
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    shap_values = np.asarray(shap_values)

    # Sort by absolute SHAP value
    sorted_indices = np.argsort(np.abs(shap_values))[::-1][:max_display]

    sorted_shap = shap_values[sorted_indices]
    sorted_names = [feature_names[i] for i in sorted_indices]
    sorted_values = None
    if feature_values is not None:
        feature_values = np.asarray(feature_values)
        sorted_values = feature_values[sorted_indices]

    # Return data only if matplotlib not available or requested
    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "base_value": float(base_value),
            "final_value": float(base_value + shap_values.sum()),
            "features": [
                {
                    "name": name,
                    "shap_value": float(sv),
                    "feature_value": float(fv) if sorted_values is not None else None,
                }
                for name, sv, fv in zip(
                    sorted_names, sorted_shap,
                    sorted_values if sorted_values is not None else [None] * len(sorted_names)
                )
            ],
        }

    # Create waterfall plot
    fig, ax = plt.subplots(figsize=(10, max(6, max_display * 0.4)))

    # Calculate cumulative values
    cumulative = base_value
    y_positions = list(range(len(sorted_shap), 0, -1))

    colors = ["#ff0051" if v < 0 else "#008bfb" for v in sorted_shap]

    # Plot bars
    for i, (y, shap_val, color) in enumerate(zip(y_positions, sorted_shap, colors)):
        left = cumulative if shap_val >= 0 else cumulative + shap_val
        ax.barh(y, abs(shap_val), left=left, color=color, height=0.7, alpha=0.8)

        # Add value annotation
        text_x = cumulative + shap_val / 2
        sign = "+" if shap_val >= 0 else ""
        ax.text(text_x, y, f"{sign}{shap_val:.3f}", ha="center", va="center", fontsize=9)

        cumulative += shap_val

    # Add feature names with values
    labels = []
    for i, name in enumerate(sorted_names):
        if sorted_values is not None:
            val = sorted_values[i]
            if isinstance(val, float):
                labels.append(f"{name} = {val:.2f}")
            else:
                labels.append(f"{name} = {val}")
        else:
            labels.append(name)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels)

    # Add baseline and final value lines
    ax.axvline(x=base_value, color="gray", linestyle="--", linewidth=1, label=f"Baseline: {base_value:.2f}")
    ax.axvline(x=cumulative, color="black", linestyle="-", linewidth=2, label=f"Output: {cumulative:.2f}")

    ax.set_xlabel("Impact on model output")
    ax.set_title(title)
    ax.legend(loc="best")

    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_shap_summary(
    shap_values: np.ndarray,
    feature_names: List[str],
    feature_values: Optional[np.ndarray] = None,
    max_display: int = 15,
    title: str = "Feature Importance",
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Create a SHAP summary/importance bar plot.

    Args:
        shap_values: SHAP values matrix (samples, features)
        feature_names: Names of features
        feature_values: Optional feature values matrix
        max_display: Maximum features to display
        title: Plot title
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    shap_values = np.asarray(shap_values)
    if shap_values.ndim == 1:
        shap_values = shap_values.reshape(1, -1)

    # Mean absolute SHAP value per feature
    importance = np.abs(shap_values).mean(axis=0)

    # Sort by importance
    sorted_indices = np.argsort(importance)[::-1][:max_display]
    sorted_importance = importance[sorted_indices]
    sorted_names = [feature_names[i] for i in sorted_indices]

    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "features": sorted_names,
            "importance": sorted_importance.tolist(),
        }

    fig, ax = plt.subplots(figsize=(10, max(6, max_display * 0.35)))

    y_pos = np.arange(len(sorted_names))[::-1]

    # Color gradient based on importance
    colors = plt.cm.Blues(np.linspace(0.3, 0.9, len(sorted_names)))[::-1]

    ax.barh(y_pos, sorted_importance, color=colors, height=0.7)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_names)
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(title)

    # Add value labels
    for i, (y, v) in enumerate(zip(y_pos, sorted_importance)):
        ax.text(v + 0.001, y, f"{v:.4f}", va="center", fontsize=9)

    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_attention_heatmap(
    attention_matrix: np.ndarray,
    x_labels: Optional[List[str]] = None,
    y_labels: Optional[List[str]] = None,
    title: str = "Attention Weights",
    colormap: str = "viridis",
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Create an attention heatmap visualization.

    Args:
        attention_matrix: 2D attention weights (decoder, encoder)
        x_labels: Labels for x-axis (encoder steps)
        y_labels: Labels for y-axis (decoder steps)
        title: Plot title
        colormap: Matplotlib colormap name
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    attention_matrix = np.asarray(attention_matrix)

    dec_len, enc_len = attention_matrix.shape

    if x_labels is None:
        x_labels = [f"t-{i}" for i in range(enc_len, 0, -1)]
    if y_labels is None:
        y_labels = [f"h+{i}" for i in range(dec_len)]

    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "matrix": attention_matrix.tolist(),
            "x_labels": x_labels,
            "y_labels": y_labels,
        }

    fig, ax = plt.subplots(figsize=(min(20, enc_len * 0.3), min(10, dec_len * 0.4)))

    if SEABORN_AVAILABLE:
        sns.heatmap(
            attention_matrix,
            xticklabels=x_labels if enc_len <= 50 else False,
            yticklabels=y_labels,
            cmap=colormap,
            ax=ax,
            cbar_kws={"label": "Attention Weight"},
        )
    else:
        im = ax.imshow(attention_matrix, cmap=colormap, aspect="auto")
        plt.colorbar(im, ax=ax, label="Attention Weight")

        if enc_len <= 50:
            ax.set_xticks(range(enc_len))
            ax.set_xticklabels(x_labels, rotation=45, ha="right")
        ax.set_yticks(range(dec_len))
        ax.set_yticklabels(y_labels)

    ax.set_xlabel("Historical Time Steps")
    ax.set_ylabel("Forecast Horizon")
    ax.set_title(title)

    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_temporal_attention(
    attention_weights: np.ndarray,
    timestamps: Optional[List[str]] = None,
    title: str = "Temporal Attention Pattern",
    highlight_top_k: int = 5,
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Plot temporal attention as a line chart.

    Args:
        attention_weights: 1D array of attention weights
        timestamps: Optional timestamp labels
        title: Plot title
        highlight_top_k: Number of top attended steps to highlight
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    attention_weights = np.asarray(attention_weights)
    n_steps = len(attention_weights)

    if timestamps is None:
        timestamps = [f"t-{i}" for i in range(n_steps, 0, -1)]

    # Find top attended steps
    top_indices = np.argsort(attention_weights)[::-1][:highlight_top_k]

    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "attention": attention_weights.tolist(),
            "timestamps": timestamps,
            "top_indices": top_indices.tolist(),
        }

    fig, ax = plt.subplots(figsize=(12, 5))

    # Plot attention line
    x = np.arange(n_steps)
    ax.fill_between(x, attention_weights, alpha=0.3, color="steelblue")
    ax.plot(x, attention_weights, color="steelblue", linewidth=2)

    # Highlight top attended
    ax.scatter(
        top_indices,
        attention_weights[top_indices],
        color="red",
        s=100,
        zorder=5,
        label=f"Top {highlight_top_k} attended",
    )

    # Set labels
    if n_steps <= 50:
        ax.set_xticks(x)
        ax.set_xticklabels(timestamps, rotation=45, ha="right")
    else:
        # Show subset of labels
        step = n_steps // 20
        ax.set_xticks(x[::step])
        ax.set_xticklabels([timestamps[i] for i in range(0, n_steps, step)], rotation=45, ha="right")

    ax.set_xlabel("Historical Time")
    ax.set_ylabel("Attention Weight")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_decision_factors(
    action: str,
    factors: List[Dict[str, Any]],
    confidence: float,
    title: str = "Trading Decision Factors",
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Plot factors contributing to a trading decision.

    Args:
        action: The action taken (BUY, SELL, HOLD)
        factors: List of factor dicts with 'name', 'contribution', 'direction'
        confidence: Overall confidence score
        title: Plot title
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "action": action,
            "confidence": confidence,
            "factors": factors,
        }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [2, 1]})

    # Factor contributions bar chart
    names = [f["name"] if isinstance(f, dict) else f.feature_name for f in factors]
    contributions = [f["contribution"] if isinstance(f, dict) else f.contribution for f in factors]
    directions = [f.get("direction", "neutral") if isinstance(f, dict) else f.direction for f in factors]

    colors = ["#2ecc71" if d == "positive" else "#e74c3c" if d == "negative" else "#95a5a6"
              for d in directions]

    y_pos = np.arange(len(names))[::-1]
    ax1.barh(y_pos, contributions, color=colors, height=0.6)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(names)
    ax1.set_xlabel("Contribution")
    ax1.axvline(x=0, color="black", linewidth=0.5)
    ax1.set_title("Factor Contributions")

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#2ecc71", label="Supporting"),
        Patch(facecolor="#e74c3c", label="Opposing"),
        Patch(facecolor="#95a5a6", label="Neutral"),
    ]
    ax1.legend(handles=legend_elements, loc="lower right")

    # Confidence gauge
    ax2.set_xlim(-1.5, 1.5)
    ax2.set_ylim(-1.5, 1.5)
    ax2.set_aspect("equal")
    ax2.axis("off")

    # Draw confidence arc
    theta = np.linspace(0, np.pi, 100)
    r = 1.0
    x_arc = r * np.cos(theta)
    y_arc = r * np.sin(theta)
    ax2.plot(x_arc, y_arc, "gray", linewidth=10, solid_capstyle="round")

    # Colored arc based on confidence
    conf_theta = np.linspace(0, np.pi * confidence, 100)
    x_conf = r * np.cos(conf_theta)
    y_conf = r * np.sin(conf_theta)
    color = "#2ecc71" if confidence > 0.7 else "#f39c12" if confidence > 0.4 else "#e74c3c"
    ax2.plot(x_conf, y_conf, color, linewidth=10, solid_capstyle="round")

    # Add labels
    ax2.text(0, 0.3, f"{confidence*100:.0f}%", ha="center", va="center", fontsize=24, fontweight="bold")
    ax2.text(0, -0.1, "Confidence", ha="center", va="center", fontsize=12)
    ax2.text(0, -0.5, f"Action: {action}", ha="center", va="center", fontsize=16, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_feature_importance(
    importance_dict: Dict[str, float],
    title: str = "Feature Importance",
    max_display: int = 15,
    horizontal: bool = True,
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Plot feature importance as a bar chart.

    Args:
        importance_dict: Dictionary mapping feature names to importance scores
        title: Plot title
        max_display: Maximum features to display
        horizontal: If True, plot horizontal bars
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    # Sort by importance
    sorted_items = sorted(importance_dict.items(), key=lambda x: abs(x[1]), reverse=True)[:max_display]
    names = [item[0] for item in sorted_items]
    values = [item[1] for item in sorted_items]

    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "features": names,
            "importance": values,
        }

    fig, ax = plt.subplots(figsize=(10, max(6, len(names) * 0.4)) if horizontal else (max(8, len(names) * 0.3), 6))

    # Color based on sign
    colors = ["#3498db" if v >= 0 else "#e74c3c" for v in values]

    if horizontal:
        y_pos = np.arange(len(names))[::-1]
        ax.barh(y_pos, values, color=colors, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlabel("Importance Score")
        ax.axvline(x=0, color="black", linewidth=0.5)
    else:
        x_pos = np.arange(len(names))
        ax.bar(x_pos, values, color=colors, width=0.6)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_ylabel("Importance Score")
        ax.axhline(y=0, color="black", linewidth=0.5)

    ax.set_title(title)
    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_prediction_explanation(
    prediction: float,
    baseline: float,
    contributions: Dict[str, float],
    confidence_interval: Optional[Tuple[float, float]] = None,
    title: str = "Prediction Explanation",
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Create a comprehensive prediction explanation plot.

    Args:
        prediction: Model prediction
        baseline: Baseline/expected value
        contributions: Feature contributions to prediction
        confidence_interval: Optional (lower, upper) confidence bounds
        title: Plot title
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "prediction": prediction,
            "baseline": baseline,
            "deviation": prediction - baseline,
            "contributions": contributions,
            "confidence_interval": confidence_interval,
        }

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Left: Contribution waterfall
    ax1 = axes[0]
    sorted_contribs = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    names = [item[0] for item in sorted_contribs]
    values = [item[1] for item in sorted_contribs]

    y_pos = np.arange(len(names))[::-1]
    colors = ["#3498db" if v >= 0 else "#e74c3c" for v in values]

    ax1.barh(y_pos, values, color=colors, height=0.6)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(names)
    ax1.set_xlabel("Contribution")
    ax1.set_title("Top Contributing Factors")
    ax1.axvline(x=0, color="black", linewidth=0.5)

    # Right: Prediction gauge
    ax2 = axes[1]
    ax2.set_xlim(-0.5, 1.5)
    ax2.set_ylim(-0.5, 1.5)
    ax2.set_aspect("equal")
    ax2.axis("off")

    # Draw prediction indicator
    deviation = prediction - baseline
    deviation_pct = deviation / (abs(baseline) + 1e-6) * 100

    # Prediction box
    ax2.add_patch(plt.Rectangle((0.2, 0.6), 0.6, 0.3, fill=True, facecolor="lightblue", edgecolor="navy", linewidth=2))
    ax2.text(0.5, 0.75, f"{prediction:.2f}", ha="center", va="center", fontsize=20, fontweight="bold")
    ax2.text(0.5, 0.65, "Prediction", ha="center", va="center", fontsize=10)

    # Baseline box
    ax2.add_patch(plt.Rectangle((0.2, 0.2), 0.6, 0.25, fill=True, facecolor="lightgray", edgecolor="gray", linewidth=1))
    ax2.text(0.5, 0.35, f"{baseline:.2f}", ha="center", va="center", fontsize=14)
    ax2.text(0.5, 0.25, "Baseline", ha="center", va="center", fontsize=10)

    # Deviation indicator
    color = "#2ecc71" if deviation_pct >= 0 else "#e74c3c"
    sign = "+" if deviation_pct >= 0 else ""
    ax2.text(0.5, 0.5, f"({sign}{deviation_pct:.1f}%)", ha="center", va="center", fontsize=12, color=color, fontweight="bold")

    # Confidence interval if provided
    if confidence_interval:
        ax2.text(0.5, 0.05, f"95% CI: [{confidence_interval[0]:.2f}, {confidence_interval[1]:.2f}]",
                ha="center", va="center", fontsize=10, style="italic")

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def plot_action_probabilities(
    actions: List[str],
    probabilities: List[float],
    q_values: Optional[List[float]] = None,
    selected_action: Optional[str] = None,
    title: str = "Action Probabilities",
    output_format: str = "base64",
) -> Union[str, Dict[str, Any]]:
    """Plot action probabilities and Q-values for RL decisions.

    Args:
        actions: List of action names
        probabilities: Action probabilities
        q_values: Optional Q-values for each action
        selected_action: The action that was selected
        title: Plot title
        output_format: "base64", "svg", or "data"

    Returns:
        Base64 encoded image, SVG string, or raw data dict
    """
    if output_format == "data" or not MATPLOTLIB_AVAILABLE:
        return {
            "actions": actions,
            "probabilities": probabilities,
            "q_values": q_values,
            "selected": selected_action,
        }

    n_actions = len(actions)
    has_q = q_values is not None

    fig, ax = plt.subplots(figsize=(10, 5))

    x = np.arange(n_actions)
    width = 0.35 if has_q else 0.6

    # Probability bars
    colors = ["#27ae60" if a == selected_action else "#3498db" for a in actions]
    bars1 = ax.bar(x - width/2 if has_q else x, probabilities, width, label="Probability", color=colors, alpha=0.8)

    # Q-value bars
    if has_q:
        bars2 = ax.bar(x + width/2, q_values, width, label="Q-Value", color="#e74c3c", alpha=0.6)

    # Labels
    ax.set_xticks(x)
    ax.set_xticklabels(actions)
    ax.set_ylabel("Value")
    ax.set_title(title)
    ax.legend()

    # Add value labels on bars
    for bar, prob in zip(bars1, probabilities):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height, f"{prob:.2f}", ha="center", va="bottom", fontsize=10)

    if has_q:
        for bar, qv in zip(bars2, q_values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, height, f"{qv:.2f}", ha="center", va="bottom", fontsize=10)

    plt.tight_layout()

    if output_format == "svg":
        return _fig_to_svg(fig)
    return _fig_to_base64(fig)


def create_html_report(
    title: str,
    sections: List[Dict[str, Any]],
) -> str:
    """Create an HTML report with multiple visualizations.

    Args:
        title: Report title
        sections: List of section dicts with 'title', 'content', 'image' (base64)

    Returns:
        HTML string
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<title>{title}</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; max-width: 1200px; margin: auto; padding: 20px; }",
        "h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }",
        "h2 { color: #34495e; margin-top: 30px; }",
        ".section { background: #f9f9f9; padding: 20px; margin: 20px 0; border-radius: 8px; }",
        ".image-container { text-align: center; margin: 20px 0; }",
        "img { max-width: 100%; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        ".metric { display: inline-block; padding: 10px 20px; margin: 5px; background: #3498db; color: white; border-radius: 4px; }",
        "table { width: 100%; border-collapse: collapse; margin: 10px 0; }",
        "th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }",
        "th { background: #3498db; color: white; }",
        "tr:nth-child(even) { background: #f2f2f2; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{title}</h1>",
    ]

    for section in sections:
        html_parts.append('<div class="section">')
        html_parts.append(f'<h2>{section.get("title", "Section")}</h2>')

        if "content" in section:
            html_parts.append(f'<p>{section["content"]}</p>')

        if "metrics" in section:
            for name, value in section["metrics"].items():
                html_parts.append(f'<span class="metric">{name}: {value}</span>')

        if "image" in section:
            html_parts.append('<div class="image-container">')
            html_parts.append(f'<img src="{section["image"]}" alt="{section.get("title", "")}">')
            html_parts.append('</div>')

        if "table" in section:
            html_parts.append('<table>')
            headers = section["table"].get("headers", [])
            if headers:
                html_parts.append('<tr>')
                for h in headers:
                    html_parts.append(f'<th>{h}</th>')
                html_parts.append('</tr>')
            for row in section["table"].get("rows", []):
                html_parts.append('<tr>')
                for cell in row:
                    html_parts.append(f'<td>{cell}</td>')
                html_parts.append('</tr>')
            html_parts.append('</table>')

        html_parts.append('</div>')

    html_parts.extend([
        "</body>",
        "</html>",
    ])

    return "\n".join(html_parts)
