"""SHAP-based explainability for forecast models.

Provides interpretable explanations for load and price forecasting
using SHAP (SHapley Additive exPlanations) values.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# Optional SHAP import with fallback
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not available. Install with: pip install shap")


@dataclass
class FeatureContribution:
    """Individual feature contribution to prediction."""

    feature_name: str
    feature_value: float
    shap_value: float
    contribution_pct: float  # Percentage contribution to deviation from baseline
    direction: str  # "positive" or "negative"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_value": self.feature_value,
            "shap_value": self.shap_value,
            "contribution_pct": self.contribution_pct,
            "direction": self.direction,
        }


@dataclass
class ForecastExplanation:
    """Complete explanation for a forecast prediction."""

    prediction: float
    baseline: float  # Expected/average prediction
    shap_values: np.ndarray
    feature_names: List[str]
    feature_values: np.ndarray
    top_features: List[FeatureContribution]
    text_explanation: str
    timestamp: Optional[str] = None
    horizon_idx: Optional[int] = None
    model_type: str = "forecast"
    confidence_interval: Optional[Tuple[float, float]] = None
    visualization_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": float(self.prediction),
            "baseline": float(self.baseline),
            "shap_values": self.shap_values.tolist() if isinstance(self.shap_values, np.ndarray) else self.shap_values,
            "feature_names": self.feature_names,
            "feature_values": self.feature_values.tolist() if isinstance(self.feature_values, np.ndarray) else self.feature_values,
            "top_features": [f.to_dict() for f in self.top_features],
            "text_explanation": self.text_explanation,
            "timestamp": self.timestamp,
            "horizon_idx": self.horizon_idx,
            "model_type": self.model_type,
            "confidence_interval": self.confidence_interval,
            "visualization_data": self.visualization_data,
        }


class ForecastExplainer:
    """SHAP-based explainer for load and price forecast models.

    Supports both PyTorch models (via DeepExplainer) and sklearn-style
    models (via TreeExplainer or KernelExplainer).

    Example:
        >>> explainer = ForecastExplainer(model, background_data, feature_names)
        >>> explanation = explainer.explain_prediction(input_features)
        >>> print(explanation.text_explanation)
        "Load forecast is 15% higher than baseline due to:
         1. High temperature (35°C): +8.2% impact
         2. Festival period (Diwali): +4.5% impact
         3. Peak hours (18:00): +2.3% impact"
    """

    # Feature display names for natural language explanations
    FEATURE_DISPLAY_NAMES = {
        "temperature": "Temperature",
        "temp": "Temperature",
        "humidity": "Humidity",
        "hour": "Hour of day",
        "hour_sin": "Time of day (cyclical)",
        "hour_cos": "Time of day (cyclical)",
        "day_of_week": "Day of week",
        "dow_sin": "Day of week (cyclical)",
        "dow_cos": "Day of week (cyclical)",
        "month": "Month",
        "month_sin": "Season (cyclical)",
        "month_cos": "Season (cyclical)",
        "is_weekend": "Weekend",
        "is_holiday": "Holiday",
        "is_festival": "Festival period",
        "load_lag_1h": "Load 1 hour ago",
        "load_lag_24h": "Load 24 hours ago",
        "load_lag_168h": "Load 1 week ago",
        "price_lag_1h": "Price 1 hour ago",
        "price_lag_24h": "Price 24 hours ago",
        "grid_load": "Grid load",
        "grid_frequency": "Grid frequency",
        "solar_irradiance": "Solar irradiance",
        "wind_speed": "Wind speed",
        "cloud_cover": "Cloud cover",
        "spot_price": "Spot price",
        "volatility": "Price volatility",
    }

    def __init__(
        self,
        model: Union[nn.Module, Any],
        background_data: Union[np.ndarray, torch.Tensor],
        feature_names: List[str],
        model_type: str = "auto",
        device: str = "cpu",
    ):
        """Initialize the forecast explainer.

        Args:
            model: The forecast model (PyTorch or sklearn-style)
            background_data: Background dataset for SHAP (typically training samples)
            feature_names: Names of input features
            model_type: One of "deep", "tree", "kernel", or "auto"
            device: Device for PyTorch models
        """
        if not SHAP_AVAILABLE:
            raise ImportError("SHAP is required. Install with: pip install shap")

        self.model = model
        self.feature_names = feature_names
        self.device = device
        self.model_type = model_type

        # Prepare background data
        if isinstance(background_data, torch.Tensor):
            background_data = background_data.cpu().numpy()
        self.background_data = background_data

        # Calculate baseline (expected prediction)
        self.baseline = self._compute_baseline()

        # Initialize appropriate SHAP explainer
        self.explainer = self._create_explainer(model_type)

        logger.info(
            f"ForecastExplainer initialized with {len(feature_names)} features, "
            f"baseline={self.baseline:.4f}"
        )

    def _compute_baseline(self) -> float:
        """Compute baseline prediction (mean over background data)."""
        try:
            if isinstance(self.model, nn.Module):
                self.model.eval()
                with torch.no_grad():
                    bg_tensor = torch.tensor(
                        self.background_data, dtype=torch.float32
                    ).to(self.device)
                    preds = self.model(bg_tensor)
                    if isinstance(preds, tuple):
                        preds = preds[0]  # Handle models returning (pred, aux)
                    return float(preds.mean().cpu().numpy())
            else:
                preds = self.model.predict(self.background_data)
                return float(np.mean(preds))
        except Exception as e:
            logger.warning(f"Could not compute baseline: {e}. Using 0.0")
            return 0.0

    def _create_explainer(self, model_type: str) -> Any:
        """Create the appropriate SHAP explainer based on model type."""
        if model_type == "auto":
            model_type = self._detect_model_type()

        if model_type == "deep":
            return self._create_deep_explainer()
        elif model_type == "tree":
            return shap.TreeExplainer(self.model)
        elif model_type == "kernel":
            return self._create_kernel_explainer()
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def _detect_model_type(self) -> str:
        """Auto-detect the appropriate explainer type."""
        if isinstance(self.model, nn.Module):
            return "deep"

        model_class = type(self.model).__name__.lower()
        if any(tree in model_class for tree in ["tree", "forest", "xgb", "lgb", "catboost"]):
            return "tree"

        return "kernel"

    def _create_deep_explainer(self) -> Any:
        """Create DeepExplainer for PyTorch models."""
        self.model.eval()

        # Create wrapper for consistent output
        class ModelWrapper(nn.Module):
            def __init__(wrapper_self, model):
                super().__init__()
                wrapper_self.model = model

            def forward(wrapper_self, x):
                out = wrapper_self.model(x)
                if isinstance(out, tuple):
                    out = out[0]
                if out.dim() > 1:
                    out = out.mean(dim=tuple(range(1, out.dim())))
                return out

        wrapped_model = ModelWrapper(self.model).to(self.device)
        bg_tensor = torch.tensor(
            self.background_data[:100],  # Limit background size
            dtype=torch.float32
        ).to(self.device)

        return shap.DeepExplainer(wrapped_model, bg_tensor)

    def _create_kernel_explainer(self) -> Any:
        """Create KernelExplainer for general models."""
        def model_predict(x):
            if isinstance(self.model, nn.Module):
                self.model.eval()
                with torch.no_grad():
                    x_tensor = torch.tensor(x, dtype=torch.float32).to(self.device)
                    preds = self.model(x_tensor)
                    if isinstance(preds, tuple):
                        preds = preds[0]
                    return preds.cpu().numpy()
            return self.model.predict(x)

        # Use k-means summarization for efficiency
        background_summary = shap.kmeans(self.background_data, 50)
        return shap.KernelExplainer(model_predict, background_summary)

    def explain_prediction(
        self,
        input_features: Union[np.ndarray, torch.Tensor],
        timestamp: Optional[str] = None,
        horizon_idx: Optional[int] = None,
        top_k: int = 5,
        include_visualization: bool = True,
    ) -> ForecastExplanation:
        """Generate explanation for a single prediction.

        Args:
            input_features: Input feature vector (1D or 2D with batch=1)
            timestamp: Optional timestamp for the prediction
            horizon_idx: Optional horizon index (for multi-step forecasts)
            top_k: Number of top contributing features to highlight
            include_visualization: Whether to include visualization data

        Returns:
            ForecastExplanation with SHAP values and natural language explanation
        """
        # Prepare input
        if isinstance(input_features, torch.Tensor):
            input_features = input_features.cpu().numpy()

        if input_features.ndim == 1:
            input_features = input_features.reshape(1, -1)

        # Get prediction
        prediction = self._get_prediction(input_features)

        # Calculate SHAP values
        shap_values = self._compute_shap_values(input_features)

        # Get top contributing features
        top_features = self._get_top_features(
            shap_values[0], input_features[0], top_k
        )

        # Generate natural language explanation
        text_explanation = self._generate_text_explanation(
            prediction, top_features, timestamp
        )

        # Prepare visualization data
        visualization_data = {}
        if include_visualization:
            visualization_data = self._prepare_visualization_data(
                shap_values[0], input_features[0], prediction
            )

        return ForecastExplanation(
            prediction=prediction,
            baseline=self.baseline,
            shap_values=shap_values[0],
            feature_names=self.feature_names,
            feature_values=input_features[0],
            top_features=top_features,
            text_explanation=text_explanation,
            timestamp=timestamp,
            horizon_idx=horizon_idx,
            visualization_data=visualization_data,
        )

    def explain_batch(
        self,
        input_features: Union[np.ndarray, torch.Tensor],
        timestamps: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[ForecastExplanation]:
        """Generate explanations for a batch of predictions.

        Args:
            input_features: Batch of input features (batch_size, num_features)
            timestamps: Optional list of timestamps
            top_k: Number of top features per explanation

        Returns:
            List of ForecastExplanation objects
        """
        if isinstance(input_features, torch.Tensor):
            input_features = input_features.cpu().numpy()

        if input_features.ndim == 1:
            input_features = input_features.reshape(1, -1)

        batch_size = input_features.shape[0]
        timestamps = timestamps or [None] * batch_size

        # Compute SHAP values for entire batch
        shap_values = self._compute_shap_values(input_features)

        # Get predictions
        predictions = self._get_predictions_batch(input_features)

        explanations = []
        for i in range(batch_size):
            top_features = self._get_top_features(
                shap_values[i], input_features[i], top_k
            )
            text_explanation = self._generate_text_explanation(
                predictions[i], top_features, timestamps[i]
            )

            explanations.append(ForecastExplanation(
                prediction=predictions[i],
                baseline=self.baseline,
                shap_values=shap_values[i],
                feature_names=self.feature_names,
                feature_values=input_features[i],
                top_features=top_features,
                text_explanation=text_explanation,
                timestamp=timestamps[i],
                horizon_idx=i,
            ))

        return explanations

    def _get_prediction(self, input_features: np.ndarray) -> float:
        """Get model prediction for input."""
        if isinstance(self.model, nn.Module):
            self.model.eval()
            with torch.no_grad():
                x = torch.tensor(input_features, dtype=torch.float32).to(self.device)
                pred = self.model(x)
                if isinstance(pred, tuple):
                    pred = pred[0]
                return float(pred.mean().cpu().numpy())
        return float(self.model.predict(input_features)[0])

    def _get_predictions_batch(self, input_features: np.ndarray) -> np.ndarray:
        """Get model predictions for batch."""
        if isinstance(self.model, nn.Module):
            self.model.eval()
            with torch.no_grad():
                x = torch.tensor(input_features, dtype=torch.float32).to(self.device)
                preds = self.model(x)
                if isinstance(preds, tuple):
                    preds = preds[0]
                if preds.dim() > 1:
                    preds = preds.mean(dim=tuple(range(1, preds.dim())))
                return preds.cpu().numpy()
        return self.model.predict(input_features)

    def _compute_shap_values(self, input_features: np.ndarray) -> np.ndarray:
        """Compute SHAP values for input features."""
        if self.model_type == "deep" or isinstance(self.explainer, shap.DeepExplainer):
            x = torch.tensor(input_features, dtype=torch.float32).to(self.device)
            shap_values = self.explainer.shap_values(x)
            if isinstance(shap_values, list):
                shap_values = shap_values[0]
            if isinstance(shap_values, torch.Tensor):
                shap_values = shap_values.cpu().numpy()
        else:
            shap_values = self.explainer.shap_values(input_features)
            if isinstance(shap_values, list):
                shap_values = shap_values[0]

        return np.array(shap_values)

    def _get_top_features(
        self,
        shap_values: np.ndarray,
        feature_values: np.ndarray,
        top_k: int,
    ) -> List[FeatureContribution]:
        """Extract top k contributing features."""
        # Calculate absolute contributions
        abs_shap = np.abs(shap_values)
        total_contribution = abs_shap.sum()

        # Sort by absolute SHAP value
        sorted_indices = np.argsort(abs_shap)[::-1][:top_k]

        contributions = []
        for idx in sorted_indices:
            shap_val = float(shap_values[idx])
            feature_val = float(feature_values[idx])

            # Calculate percentage contribution
            contrib_pct = (abs_shap[idx] / total_contribution * 100) if total_contribution > 0 else 0

            contributions.append(FeatureContribution(
                feature_name=self.feature_names[idx],
                feature_value=feature_val,
                shap_value=shap_val,
                contribution_pct=float(contrib_pct),
                direction="positive" if shap_val > 0 else "negative",
            ))

        return contributions

    def _generate_text_explanation(
        self,
        prediction: float,
        top_features: List[FeatureContribution],
        timestamp: Optional[str] = None,
    ) -> str:
        """Generate natural language explanation."""
        # Calculate deviation from baseline
        deviation = prediction - self.baseline
        deviation_pct = (deviation / abs(self.baseline) * 100) if self.baseline != 0 else 0

        # Direction text
        if abs(deviation_pct) < 1:
            direction_text = "close to average"
        elif deviation_pct > 0:
            direction_text = f"{abs(deviation_pct):.1f}% higher than average"
        else:
            direction_text = f"{abs(deviation_pct):.1f}% lower than average"

        # Build explanation
        lines = []

        # Header
        if timestamp:
            lines.append(f"Forecast for {timestamp} is {direction_text}.")
        else:
            lines.append(f"Forecast is {direction_text}.")

        # Top contributing factors
        if top_features:
            lines.append("\nKey contributing factors:")
            for i, feat in enumerate(top_features, 1):
                display_name = self.FEATURE_DISPLAY_NAMES.get(
                    feat.feature_name, feat.feature_name.replace("_", " ").title()
                )

                # Format feature value
                value_str = self._format_feature_value(feat.feature_name, feat.feature_value)

                # Impact direction
                impact = "↑" if feat.direction == "positive" else "↓"
                impact_sign = "+" if feat.direction == "positive" else "-"

                lines.append(
                    f"  {i}. {display_name} ({value_str}): "
                    f"{impact} {impact_sign}{feat.contribution_pct:.1f}% impact"
                )

        return "\n".join(lines)

    def _format_feature_value(self, feature_name: str, value: float) -> str:
        """Format feature value for display."""
        name_lower = feature_name.lower()

        if "temp" in name_lower:
            return f"{value:.1f}°C"
        elif "humidity" in name_lower:
            return f"{value:.0f}%"
        elif "hour" in name_lower and "lag" not in name_lower:
            return f"{int(value):02d}:00"
        elif "price" in name_lower:
            return f"₹{value:.2f}/kWh"
        elif "load" in name_lower:
            return f"{value:.1f} MW"
        elif "frequency" in name_lower:
            return f"{value:.2f} Hz"
        elif name_lower in ("is_weekend", "is_holiday", "is_festival"):
            return "Yes" if value > 0.5 else "No"
        elif "sin" in name_lower or "cos" in name_lower:
            return f"{value:.3f}"
        else:
            return f"{value:.2f}"

    def _prepare_visualization_data(
        self,
        shap_values: np.ndarray,
        feature_values: np.ndarray,
        prediction: float,
    ) -> Dict[str, Any]:
        """Prepare data for visualizations."""
        # Sort by absolute SHAP value
        sorted_indices = np.argsort(np.abs(shap_values))[::-1]

        return {
            "waterfall": {
                "base_value": float(self.baseline),
                "output_value": float(prediction),
                "features": [self.feature_names[i] for i in sorted_indices],
                "feature_values": [float(feature_values[i]) for i in sorted_indices],
                "shap_values": [float(shap_values[i]) for i in sorted_indices],
            },
            "bar": {
                "features": self.feature_names,
                "importance": np.abs(shap_values).tolist(),
            },
            "force": {
                "base_value": float(self.baseline),
                "output_value": float(prediction),
                "features": {
                    self.feature_names[i]: {
                        "value": float(feature_values[i]),
                        "effect": float(shap_values[i]),
                    }
                    for i in range(len(self.feature_names))
                },
            },
        }

    def get_feature_importance(self) -> Dict[str, float]:
        """Calculate global feature importance from background data.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        # Compute SHAP values for background data
        shap_values = self._compute_shap_values(self.background_data[:100])

        # Mean absolute SHAP value per feature
        importance = np.abs(shap_values).mean(axis=0)

        # Normalize to percentages
        total = importance.sum()
        if total > 0:
            importance = importance / total * 100

        return {
            name: float(imp)
            for name, imp in zip(self.feature_names, importance)
        }

    def what_if_analysis(
        self,
        input_features: Union[np.ndarray, torch.Tensor],
        feature_changes: Dict[str, float],
    ) -> Dict[str, Any]:
        """Analyze how changes in features would affect the prediction.

        Args:
            input_features: Original input features
            feature_changes: Dictionary of {feature_name: new_value}

        Returns:
            Analysis results with original and modified predictions
        """
        if isinstance(input_features, torch.Tensor):
            input_features = input_features.cpu().numpy()

        if input_features.ndim == 1:
            input_features = input_features.reshape(1, -1)

        # Get original prediction
        original_pred = self._get_prediction(input_features)

        # Apply changes
        modified_features = input_features.copy()
        for feature_name, new_value in feature_changes.items():
            if feature_name in self.feature_names:
                idx = self.feature_names.index(feature_name)
                modified_features[0, idx] = new_value

        # Get modified prediction
        modified_pred = self._get_prediction(modified_features)

        # Calculate change
        change = modified_pred - original_pred
        change_pct = (change / abs(original_pred) * 100) if original_pred != 0 else 0

        return {
            "original_prediction": float(original_pred),
            "modified_prediction": float(modified_pred),
            "absolute_change": float(change),
            "percentage_change": float(change_pct),
            "feature_changes": feature_changes,
            "interpretation": self._interpret_what_if(change, change_pct, feature_changes),
        }

    def _interpret_what_if(
        self,
        change: float,
        change_pct: float,
        feature_changes: Dict[str, float],
    ) -> str:
        """Generate interpretation for what-if analysis."""
        changes_text = ", ".join(
            f"{self.FEATURE_DISPLAY_NAMES.get(k, k)} → {self._format_feature_value(k, v)}"
            for k, v in feature_changes.items()
        )

        if abs(change_pct) < 1:
            impact = "minimal impact"
        elif change_pct > 0:
            impact = f"increase of {abs(change_pct):.1f}%"
        else:
            impact = f"decrease of {abs(change_pct):.1f}%"

        return f"Changing {changes_text} would result in {impact} on the forecast."
