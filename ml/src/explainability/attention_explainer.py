"""TFT Attention Visualization and Interpretation.

Extracts and visualizes attention weights from Temporal Fusion Transformer
models to explain which time steps and features influence predictions.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


@dataclass
class VariableImportance:
    """Variable importance from TFT variable selection network."""

    variable_name: str
    importance_score: float  # 0-1 normalized importance
    category: str  # "static", "encoder", "decoder"
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable_name": self.variable_name,
            "importance_score": self.importance_score,
            "category": self.category,
            "rank": self.rank,
        }


@dataclass
class TemporalAttention:
    """Temporal attention pattern for a single forecast horizon."""

    horizon_idx: int
    attention_weights: np.ndarray  # (encoder_length,) attention to history
    top_attended_steps: List[Tuple[int, float]]  # [(step_idx, weight), ...]
    attention_entropy: float  # Measure of attention spread
    peak_attention_lag: int  # Lag of highest attention

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_idx": self.horizon_idx,
            "attention_weights": self.attention_weights.tolist(),
            "top_attended_steps": self.top_attended_steps,
            "attention_entropy": self.attention_entropy,
            "peak_attention_lag": self.peak_attention_lag,
        }


@dataclass
class AttentionExplanation:
    """Complete attention-based explanation from TFT model."""

    # Variable importance
    static_variable_importance: List[VariableImportance]
    encoder_variable_importance: List[VariableImportance]
    decoder_variable_importance: List[VariableImportance]

    # Temporal attention
    temporal_attention: List[TemporalAttention]
    attention_matrix: np.ndarray  # (decoder_length, encoder_length)

    # Multi-head attention details
    num_heads: int
    head_attention_patterns: Optional[np.ndarray] = None  # (num_heads, dec, enc)

    # Aggregate statistics
    overall_encoder_importance: Dict[str, float] = field(default_factory=dict)
    attention_statistics: Dict[str, float] = field(default_factory=dict)

    # Natural language summary
    text_summary: str = ""

    # Visualization data
    visualization_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "static_variable_importance": [v.to_dict() for v in self.static_variable_importance],
            "encoder_variable_importance": [v.to_dict() for v in self.encoder_variable_importance],
            "decoder_variable_importance": [v.to_dict() for v in self.decoder_variable_importance],
            "temporal_attention": [t.to_dict() for t in self.temporal_attention],
            "attention_matrix": self.attention_matrix.tolist(),
            "num_heads": self.num_heads,
            "head_attention_patterns": self.head_attention_patterns.tolist() if self.head_attention_patterns is not None else None,
            "overall_encoder_importance": self.overall_encoder_importance,
            "attention_statistics": self.attention_statistics,
            "text_summary": self.text_summary,
            "visualization_data": self.visualization_data,
        }


class TFTAttentionExplainer:
    """Extract and interpret attention patterns from TFT models.

    Provides interpretability through:
    1. Variable selection network weights (which features matter)
    2. Temporal attention patterns (which historical steps matter)
    3. Multi-head attention analysis

    Example:
        >>> explainer = TFTAttentionExplainer(tft_model, feature_names)
        >>> explanation = explainer.explain_prediction(
        ...     static_covariates, historical_observed,
        ...     historical_known, future_known
        ... )
        >>> print(explanation.text_summary)
        "Prediction relies heavily on:
         - Temperature (32% importance)
         - Historical load (28% importance)
         Most attention focuses on hours -2 to -6 (peak demand period)"
    """

    # Default feature names if not provided
    DEFAULT_STATIC_FEATURES = ["city", "prosumer_type", "capacity_tier"]
    DEFAULT_ENCODER_FEATURES = [
        "load_observed", "temperature", "hour_sin", "hour_cos",
        "day_sin", "day_cos", "is_holiday"
    ]
    DEFAULT_DECODER_FEATURES = [
        "temperature_forecast", "hour_sin", "hour_cos",
        "day_sin", "day_cos", "is_holiday"
    ]

    def __init__(
        self,
        model: nn.Module,
        static_feature_names: Optional[List[str]] = None,
        encoder_feature_names: Optional[List[str]] = None,
        decoder_feature_names: Optional[List[str]] = None,
        device: str = "cpu",
    ):
        """Initialize TFT attention explainer.

        Args:
            model: TFT model instance
            static_feature_names: Names of static covariate features
            encoder_feature_names: Names of encoder (historical) features
            decoder_feature_names: Names of decoder (future) features
            device: Device for inference
        """
        self.model = model
        self.device = device

        # Feature names
        self.static_feature_names = static_feature_names or self.DEFAULT_STATIC_FEATURES
        self.encoder_feature_names = encoder_feature_names or self.DEFAULT_ENCODER_FEATURES
        self.decoder_feature_names = decoder_feature_names or self.DEFAULT_DECODER_FEATURES

        # Extract model configuration
        self._extract_model_config()

        logger.info(
            f"TFTAttentionExplainer initialized: "
            f"{len(self.static_feature_names)} static, "
            f"{len(self.encoder_feature_names)} encoder, "
            f"{len(self.decoder_feature_names)} decoder features"
        )

    def _extract_model_config(self):
        """Extract configuration from model."""
        self.num_heads = getattr(self.model, "num_heads", 4)
        self.encoder_length = getattr(self.model, "encoder_length", 168)
        self.decoder_length = getattr(self.model, "decoder_length", 24)

    def explain_prediction(
        self,
        static_covariates: Union[np.ndarray, torch.Tensor],
        historical_observed: Union[np.ndarray, torch.Tensor],
        historical_known: Union[np.ndarray, torch.Tensor],
        future_known: Union[np.ndarray, torch.Tensor],
        timestamps: Optional[List[str]] = None,
    ) -> AttentionExplanation:
        """Generate attention-based explanation for TFT prediction.

        Args:
            static_covariates: Static features (batch, static_size)
            historical_observed: Historical observed values (batch, enc_len, obs_size)
            historical_known: Historical known features (batch, enc_len, known_size)
            future_known: Future known features (batch, dec_len, known_size)
            timestamps: Optional timestamps for historical steps

        Returns:
            AttentionExplanation with variable importance and attention patterns
        """
        # Convert to tensors
        inputs = self._prepare_inputs(
            static_covariates, historical_observed,
            historical_known, future_known
        )

        # Get prediction with interpretability
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(
                inputs["static"],
                inputs["historical_observed"],
                inputs["historical_known"],
                inputs["future_known"],
            )

        # Extract interpretability info
        if isinstance(outputs, tuple) and len(outputs) > 1:
            predictions, interpretability = outputs
        else:
            # Model doesn't return interpretability, extract manually
            interpretability = self._extract_attention_manual(inputs)

        # Process variable importance
        static_importance = self._process_variable_importance(
            interpretability.get("static_weights"),
            self.static_feature_names,
            "static"
        )

        encoder_importance = self._process_variable_importance(
            interpretability.get("encoder_variable_weights"),
            self.encoder_feature_names,
            "encoder"
        )

        decoder_importance = self._process_variable_importance(
            interpretability.get("decoder_variable_weights"),
            self.decoder_feature_names,
            "decoder"
        )

        # Process temporal attention
        attention_weights = interpretability.get("attention_weights")
        temporal_attention, attention_matrix = self._process_temporal_attention(
            attention_weights, timestamps
        )

        # Calculate attention statistics
        attention_stats = self._calculate_attention_statistics(attention_matrix)

        # Calculate overall encoder importance
        overall_encoder = self._calculate_overall_encoder_importance(
            encoder_importance
        )

        # Generate text summary
        text_summary = self._generate_text_summary(
            static_importance, encoder_importance,
            decoder_importance, temporal_attention, attention_stats
        )

        # Prepare visualization data
        viz_data = self._prepare_visualization_data(
            static_importance, encoder_importance, decoder_importance,
            attention_matrix, timestamps
        )

        return AttentionExplanation(
            static_variable_importance=static_importance,
            encoder_variable_importance=encoder_importance,
            decoder_variable_importance=decoder_importance,
            temporal_attention=temporal_attention,
            attention_matrix=attention_matrix,
            num_heads=self.num_heads,
            head_attention_patterns=interpretability.get("attention_weights"),
            overall_encoder_importance=overall_encoder,
            attention_statistics=attention_stats,
            text_summary=text_summary,
            visualization_data=viz_data,
        )

    def _prepare_inputs(
        self,
        static_covariates: Union[np.ndarray, torch.Tensor],
        historical_observed: Union[np.ndarray, torch.Tensor],
        historical_known: Union[np.ndarray, torch.Tensor],
        future_known: Union[np.ndarray, torch.Tensor],
    ) -> Dict[str, torch.Tensor]:
        """Prepare input tensors."""
        def to_tensor(x):
            if isinstance(x, np.ndarray):
                return torch.tensor(x, dtype=torch.float32).to(self.device)
            return x.to(self.device)

        # Ensure batch dimension
        static = to_tensor(static_covariates)
        if static.dim() == 1:
            static = static.unsqueeze(0)

        hist_obs = to_tensor(historical_observed)
        if hist_obs.dim() == 2:
            hist_obs = hist_obs.unsqueeze(0)

        hist_known = to_tensor(historical_known)
        if hist_known.dim() == 2:
            hist_known = hist_known.unsqueeze(0)

        fut_known = to_tensor(future_known)
        if fut_known.dim() == 2:
            fut_known = fut_known.unsqueeze(0)

        return {
            "static": static,
            "historical_observed": hist_obs,
            "historical_known": hist_known,
            "future_known": fut_known,
        }

    def _extract_attention_manual(
        self,
        inputs: Dict[str, torch.Tensor],
    ) -> Dict[str, Any]:
        """Manually extract attention weights if model doesn't return them."""
        interpretability = {}

        # Try to access internal attention weights
        if hasattr(self.model, "interpretable_multi_head_attention"):
            attn_module = self.model.interpretable_multi_head_attention
            if hasattr(attn_module, "attention_weights"):
                interpretability["attention_weights"] = attn_module.attention_weights

        # Try to access variable selection weights
        if hasattr(self.model, "static_variable_selection"):
            vsn = self.model.static_variable_selection
            if hasattr(vsn, "variable_weights"):
                interpretability["static_weights"] = vsn.variable_weights

        if hasattr(self.model, "encoder_variable_selection"):
            vsn = self.model.encoder_variable_selection
            if hasattr(vsn, "variable_weights"):
                interpretability["encoder_variable_weights"] = vsn.variable_weights

        if hasattr(self.model, "decoder_variable_selection"):
            vsn = self.model.decoder_variable_selection
            if hasattr(vsn, "variable_weights"):
                interpretability["decoder_variable_weights"] = vsn.variable_weights

        return interpretability

    def _process_variable_importance(
        self,
        weights: Optional[Union[np.ndarray, torch.Tensor]],
        feature_names: List[str],
        category: str,
    ) -> List[VariableImportance]:
        """Process variable selection weights into importance scores."""
        if weights is None:
            # Return uniform importance if weights not available
            n = len(feature_names)
            return [
                VariableImportance(
                    variable_name=name,
                    importance_score=1.0 / n,
                    category=category,
                    rank=i + 1,
                )
                for i, name in enumerate(feature_names)
            ]

        # Convert to numpy
        if isinstance(weights, torch.Tensor):
            weights = weights.cpu().numpy()

        # Average over batch and time dimensions if needed
        while weights.ndim > 1:
            weights = weights.mean(axis=0)

        # Ensure correct length
        if len(weights) != len(feature_names):
            logger.warning(
                f"Weight length ({len(weights)}) != feature names ({len(feature_names)}). "
                "Adjusting..."
            )
            weights = weights[:len(feature_names)] if len(weights) > len(feature_names) else \
                np.pad(weights, (0, len(feature_names) - len(weights)))

        # Normalize to sum to 1
        weights = np.abs(weights)
        total = weights.sum()
        if total > 0:
            weights = weights / total

        # Sort by importance
        sorted_indices = np.argsort(weights)[::-1]

        importance_list = []
        for rank, idx in enumerate(sorted_indices, 1):
            importance_list.append(VariableImportance(
                variable_name=feature_names[idx],
                importance_score=float(weights[idx]),
                category=category,
                rank=rank,
            ))

        return importance_list

    def _process_temporal_attention(
        self,
        attention_weights: Optional[Union[np.ndarray, torch.Tensor]],
        timestamps: Optional[List[str]] = None,
    ) -> Tuple[List[TemporalAttention], np.ndarray]:
        """Process attention weights into temporal patterns."""
        if attention_weights is None:
            # Return uniform attention if not available
            enc_len = self.encoder_length
            dec_len = self.decoder_length
            attention_matrix = np.ones((dec_len, enc_len)) / enc_len
        else:
            # Convert to numpy
            if isinstance(attention_weights, torch.Tensor):
                attention_weights = attention_weights.cpu().numpy()

            # Average over batch and heads if needed
            # Expected shape: (batch, num_heads, decoder_length, encoder_length)
            while attention_weights.ndim > 2:
                attention_weights = attention_weights.mean(axis=0)

            attention_matrix = attention_weights

        dec_len, enc_len = attention_matrix.shape

        temporal_attention = []
        for h in range(dec_len):
            attn = attention_matrix[h]

            # Calculate entropy (measure of attention spread)
            entropy = -np.sum(attn * np.log(attn + 1e-10))

            # Top attended steps
            top_k = min(5, enc_len)
            top_indices = np.argsort(attn)[::-1][:top_k]
            top_attended = [
                (int(idx), float(attn[idx]))
                for idx in top_indices
            ]

            # Peak attention lag (negative = past)
            peak_idx = np.argmax(attn)
            peak_lag = peak_idx - enc_len  # Negative for past steps

            temporal_attention.append(TemporalAttention(
                horizon_idx=h,
                attention_weights=attn,
                top_attended_steps=top_attended,
                attention_entropy=float(entropy),
                peak_attention_lag=int(peak_lag),
            ))

        return temporal_attention, attention_matrix

    def _calculate_attention_statistics(
        self,
        attention_matrix: np.ndarray,
    ) -> Dict[str, float]:
        """Calculate aggregate attention statistics."""
        # Average attention per encoder step
        avg_attention = attention_matrix.mean(axis=0)

        # Find most attended period
        peak_step = int(np.argmax(avg_attention))

        # Calculate attention span (weighted std)
        steps = np.arange(attention_matrix.shape[1])
        mean_step = np.sum(avg_attention * steps)
        std_step = np.sqrt(np.sum(avg_attention * (steps - mean_step) ** 2))

        # Attention concentration (max attention value)
        max_attention = float(np.max(attention_matrix))

        # Recent vs distant ratio (last 24h vs before)
        recent_cutoff = max(attention_matrix.shape[1] - 24, 0)
        recent_attention = avg_attention[recent_cutoff:].sum()
        distant_attention = avg_attention[:recent_cutoff].sum()
        recency_ratio = recent_attention / (distant_attention + 1e-10)

        return {
            "peak_attended_step": peak_step,
            "attention_span_std": float(std_step),
            "max_attention": max_attention,
            "recent_attention_ratio": float(recency_ratio),
            "mean_entropy": float(np.mean([t.attention_entropy for t in []])),
        }

    def _calculate_overall_encoder_importance(
        self,
        encoder_importance: List[VariableImportance],
    ) -> Dict[str, float]:
        """Calculate overall encoder variable importance."""
        return {
            vi.variable_name: vi.importance_score
            for vi in encoder_importance
        }

    def _generate_text_summary(
        self,
        static_importance: List[VariableImportance],
        encoder_importance: List[VariableImportance],
        decoder_importance: List[VariableImportance],
        temporal_attention: List[TemporalAttention],
        attention_stats: Dict[str, float],
    ) -> str:
        """Generate natural language summary of attention patterns."""
        lines = []

        # Top static features
        lines.append("Model Interpretation Summary")
        lines.append("=" * 40)

        if static_importance:
            lines.append("\nStatic Feature Importance:")
            for vi in static_importance[:3]:
                lines.append(
                    f"  • {vi.variable_name}: {vi.importance_score * 100:.1f}%"
                )

        # Top encoder features
        if encoder_importance:
            lines.append("\nHistorical Feature Importance:")
            for vi in encoder_importance[:3]:
                lines.append(
                    f"  • {vi.variable_name}: {vi.importance_score * 100:.1f}%"
                )

        # Top decoder features
        if decoder_importance:
            lines.append("\nForecast Feature Importance:")
            for vi in decoder_importance[:3]:
                lines.append(
                    f"  • {vi.variable_name}: {vi.importance_score * 100:.1f}%"
                )

        # Temporal attention summary
        if temporal_attention:
            peak_step = attention_stats.get("peak_attended_step", 0)
            peak_lag = peak_step - len(temporal_attention[0].attention_weights)

            lines.append(f"\nTemporal Attention Pattern:")
            lines.append(f"  • Peak attention: {abs(peak_lag)} hours ago")

            recency = attention_stats.get("recent_attention_ratio", 1.0)
            if recency > 2.0:
                lines.append("  • Strong focus on recent history (last 24h)")
            elif recency < 0.5:
                lines.append("  • Focus on distant history")
            else:
                lines.append("  • Balanced attention across history")

        return "\n".join(lines)

    def _prepare_visualization_data(
        self,
        static_importance: List[VariableImportance],
        encoder_importance: List[VariableImportance],
        decoder_importance: List[VariableImportance],
        attention_matrix: np.ndarray,
        timestamps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Prepare data for visualizations."""
        return {
            "variable_importance_bar": {
                "static": {
                    "names": [vi.variable_name for vi in static_importance],
                    "values": [vi.importance_score for vi in static_importance],
                },
                "encoder": {
                    "names": [vi.variable_name for vi in encoder_importance],
                    "values": [vi.importance_score for vi in encoder_importance],
                },
                "decoder": {
                    "names": [vi.variable_name for vi in decoder_importance],
                    "values": [vi.importance_score for vi in decoder_importance],
                },
            },
            "attention_heatmap": {
                "matrix": attention_matrix.tolist(),
                "x_labels": timestamps or [f"t-{i}" for i in range(attention_matrix.shape[1], 0, -1)],
                "y_labels": [f"h+{i}" for i in range(attention_matrix.shape[0])],
            },
            "attention_line": {
                "avg_attention": attention_matrix.mean(axis=0).tolist(),
                "max_attention": attention_matrix.max(axis=0).tolist(),
                "min_attention": attention_matrix.min(axis=0).tolist(),
            },
        }

    def get_attention_for_horizon(
        self,
        explanation: AttentionExplanation,
        horizon_idx: int,
    ) -> Dict[str, Any]:
        """Get detailed attention for a specific forecast horizon.

        Args:
            explanation: Previously computed explanation
            horizon_idx: Index of the forecast horizon to analyze

        Returns:
            Dictionary with attention details for that horizon
        """
        if horizon_idx >= len(explanation.temporal_attention):
            raise ValueError(f"horizon_idx {horizon_idx} out of range")

        temporal = explanation.temporal_attention[horizon_idx]

        return {
            "horizon_idx": horizon_idx,
            "attention_weights": temporal.attention_weights.tolist(),
            "top_attended_steps": temporal.top_attended_steps,
            "attention_entropy": temporal.attention_entropy,
            "peak_attention_lag": temporal.peak_attention_lag,
            "interpretation": self._interpret_horizon_attention(temporal),
        }

    def _interpret_horizon_attention(
        self,
        temporal: TemporalAttention,
    ) -> str:
        """Generate interpretation for a single horizon's attention."""
        peak_lag = abs(temporal.peak_attention_lag)

        if peak_lag <= 6:
            recency = "very recent"
        elif peak_lag <= 24:
            recency = "within last day"
        elif peak_lag <= 168:
            recency = "within last week"
        else:
            recency = "distant past"

        # Attention spread interpretation
        max_entropy = np.log(len(temporal.attention_weights))
        relative_entropy = temporal.attention_entropy / max_entropy

        if relative_entropy > 0.9:
            spread = "diffuse (considers entire history)"
        elif relative_entropy > 0.7:
            spread = "moderately spread"
        else:
            spread = "focused on specific time periods"

        return (
            f"For this forecast step, the model focuses primarily on data "
            f"from {recency} ({peak_lag} hours ago). Attention is {spread}."
        )

    def compare_attention_patterns(
        self,
        explanations: List[AttentionExplanation],
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compare attention patterns across multiple predictions.

        Useful for understanding how attention changes across different
        conditions (e.g., weekday vs weekend, summer vs winter).

        Args:
            explanations: List of explanations to compare
            labels: Optional labels for each explanation

        Returns:
            Comparison analysis
        """
        if not labels:
            labels = [f"Sample {i+1}" for i in range(len(explanations))]

        # Aggregate attention matrices
        attention_matrices = [exp.attention_matrix for exp in explanations]

        # Calculate mean attention pattern
        mean_attention = np.mean(attention_matrices, axis=0)

        # Calculate variance
        var_attention = np.var(attention_matrices, axis=0)

        # Find most variable time steps
        step_variance = var_attention.mean(axis=0)
        most_variable_steps = np.argsort(step_variance)[::-1][:5].tolist()

        # Compare variable importance
        encoder_comparisons = {}
        for i, exp in enumerate(explanations):
            for vi in exp.encoder_variable_importance:
                if vi.variable_name not in encoder_comparisons:
                    encoder_comparisons[vi.variable_name] = []
                encoder_comparisons[vi.variable_name].append(vi.importance_score)

        return {
            "labels": labels,
            "mean_attention": mean_attention.tolist(),
            "attention_variance": var_attention.tolist(),
            "most_variable_time_steps": most_variable_steps,
            "variable_importance_comparison": encoder_comparisons,
            "interpretation": self._interpret_comparison(
                step_variance, encoder_comparisons, labels
            ),
        }

    def _interpret_comparison(
        self,
        step_variance: np.ndarray,
        encoder_comparisons: Dict[str, List[float]],
        labels: List[str],
    ) -> str:
        """Generate interpretation for attention comparison."""
        lines = ["Attention Pattern Comparison:"]

        # Find most variable features
        feature_variance = {
            name: np.var(scores)
            for name, scores in encoder_comparisons.items()
        }
        most_variable_feature = max(feature_variance, key=feature_variance.get)

        lines.append(
            f"• Most variable feature across samples: {most_variable_feature}"
        )

        # Time step variability
        max_var_step = np.argmax(step_variance)
        lines.append(
            f"• Most variable time step: t-{len(step_variance) - max_var_step}"
        )

        return "\n".join(lines)
