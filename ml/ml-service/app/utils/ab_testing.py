"""A/B testing and traffic routing for model experiments.

Provides:
- Traffic splitting between champion and challenger models
- Performance metric tracking
- Automatic promotion based on statistical significance
- Experiment management
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json
import hashlib

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment lifecycle status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class VariantType(Enum):
    """Type of experiment variant."""
    CHAMPION = "champion"  # Current production model
    CHALLENGER = "challenger"  # New model being tested


@dataclass
class ExperimentVariant:
    """Experiment variant (model version)."""
    name: str
    model_name: str
    model_version: str
    variant_type: VariantType
    traffic_weight: float  # 0-1, fraction of traffic
    is_active: bool = True


@dataclass
class ExperimentMetrics:
    """Metrics for an experiment variant."""
    variant_name: str
    request_count: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0
    prediction_sum: float = 0.0
    prediction_squared_sum: float = 0.0
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    timestamps: List[datetime] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(1, self.request_count)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(1, self.request_count)

    @property
    def avg_prediction(self) -> float:
        return self.prediction_sum / max(1, self.request_count)

    @property
    def prediction_variance(self) -> float:
        n = max(1, self.request_count)
        mean = self.prediction_sum / n
        return (self.prediction_squared_sum / n) - (mean ** 2)

    def record(
        self,
        latency_ms: float,
        prediction: Optional[float] = None,
        is_error: bool = False,
        custom: Optional[Dict[str, float]] = None,
    ):
        """Record a request outcome."""
        self.request_count += 1
        self.total_latency_ms += latency_ms
        if is_error:
            self.error_count += 1
        if prediction is not None:
            self.prediction_sum += prediction
            self.prediction_squared_sum += prediction ** 2
        if custom:
            for key, value in custom.items():
                if key not in self.custom_metrics:
                    self.custom_metrics[key] = 0.0
                self.custom_metrics[key] += value
        self.timestamps.append(datetime.now())


@dataclass
class Experiment:
    """A/B test experiment."""
    experiment_id: str
    name: str
    description: str
    endpoint: str  # Which endpoint this applies to
    variants: List[ExperimentVariant]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    min_sample_size: int = 1000
    max_duration_hours: int = 168  # 1 week default
    auto_promote: bool = True
    promotion_threshold: float = 0.05  # p-value threshold

    def get_variant_by_name(self, name: str) -> Optional[ExperimentVariant]:
        for v in self.variants:
            if v.name == name:
                return v
        return None


class ABTestRouter:
    """Routes traffic between experiment variants."""

    def __init__(self, sticky_sessions: bool = True):
        """Initialize router.

        Args:
            sticky_sessions: Whether to route same user to same variant
        """
        self.sticky_sessions = sticky_sessions
        self.experiments: Dict[str, Experiment] = {}
        self.metrics: Dict[str, Dict[str, ExperimentMetrics]] = {}
        self._session_assignments: Dict[str, str] = {}

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        endpoint: str,
        champion_model: str,
        champion_version: str,
        challenger_model: str,
        challenger_version: str,
        challenger_traffic_pct: float = 0.1,
        description: str = "",
        **kwargs,
    ) -> Experiment:
        """Create a new A/B test experiment."""
        variants = [
            ExperimentVariant(
                name="champion",
                model_name=champion_model,
                model_version=champion_version,
                variant_type=VariantType.CHAMPION,
                traffic_weight=1 - challenger_traffic_pct,
            ),
            ExperimentVariant(
                name="challenger",
                model_name=challenger_model,
                model_version=challenger_version,
                variant_type=VariantType.CHALLENGER,
                traffic_weight=challenger_traffic_pct,
            ),
        ]

        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            endpoint=endpoint,
            variants=variants,
            **kwargs,
        )

        self.experiments[experiment_id] = experiment
        self.metrics[experiment_id] = {
            v.name: ExperimentMetrics(variant_name=v.name)
            for v in variants
        }

        logger.info(f"Created experiment {experiment_id}: {name}")
        return experiment

    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment."""
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now()

        logger.info(f"Started experiment {experiment_id}")
        return True

    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause an experiment."""
        if experiment_id not in self.experiments:
            return False

        self.experiments[experiment_id].status = ExperimentStatus.PAUSED
        logger.info(f"Paused experiment {experiment_id}")
        return True

    def end_experiment(
        self,
        experiment_id: str,
        promote_challenger: bool = False,
    ) -> bool:
        """End an experiment."""
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now()

        if promote_challenger:
            logger.info(f"Promoting challenger for experiment {experiment_id}")
            # In production, would update model registry

        return True

    def route_request(
        self,
        endpoint: str,
        session_id: Optional[str] = None,
    ) -> Optional[ExperimentVariant]:
        """Route a request to an experiment variant.

        Args:
            endpoint: API endpoint
            session_id: Optional session ID for sticky routing

        Returns:
            Selected variant or None if no active experiment
        """
        # Find active experiment for this endpoint
        active_experiment = None
        for exp in self.experiments.values():
            if exp.endpoint == endpoint and exp.status == ExperimentStatus.RUNNING:
                active_experiment = exp
                break

        if not active_experiment:
            return None

        # Check sticky session
        if self.sticky_sessions and session_id:
            session_key = f"{active_experiment.experiment_id}:{session_id}"
            if session_key in self._session_assignments:
                variant_name = self._session_assignments[session_key]
                return active_experiment.get_variant_by_name(variant_name)

        # Random assignment based on weights
        active_variants = [v for v in active_experiment.variants if v.is_active]
        if not active_variants:
            return None

        weights = [v.traffic_weight for v in active_variants]
        total_weight = sum(weights)
        if total_weight == 0:
            return None

        # Normalize weights
        weights = [w / total_weight for w in weights]

        # Select variant
        rand = random.random()
        cumulative = 0
        selected = active_variants[0]

        for variant, weight in zip(active_variants, weights):
            cumulative += weight
            if rand < cumulative:
                selected = variant
                break

        # Store assignment for sticky sessions
        if self.sticky_sessions and session_id:
            session_key = f"{active_experiment.experiment_id}:{session_id}"
            self._session_assignments[session_key] = selected.name

        return selected

    def record_outcome(
        self,
        experiment_id: str,
        variant_name: str,
        latency_ms: float,
        prediction: Optional[float] = None,
        is_error: bool = False,
        custom_metrics: Optional[Dict[str, float]] = None,
    ):
        """Record outcome for a variant."""
        if experiment_id not in self.metrics:
            return

        if variant_name not in self.metrics[experiment_id]:
            return

        self.metrics[experiment_id][variant_name].record(
            latency_ms=latency_ms,
            prediction=prediction,
            is_error=is_error,
            custom=custom_metrics,
        )

        # Check for auto-promotion
        experiment = self.experiments.get(experiment_id)
        if experiment and experiment.auto_promote:
            asyncio.create_task(self._check_auto_promotion(experiment_id))

    async def _check_auto_promotion(self, experiment_id: str):
        """Check if challenger should be auto-promoted."""
        experiment = self.experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return

        metrics = self.metrics.get(experiment_id, {})
        champion_metrics = metrics.get("champion")
        challenger_metrics = metrics.get("challenger")

        if not champion_metrics or not challenger_metrics:
            return

        # Check minimum sample size
        if (champion_metrics.request_count < experiment.min_sample_size or
            challenger_metrics.request_count < experiment.min_sample_size):
            return

        # Check max duration
        if experiment.started_at:
            elapsed = datetime.now() - experiment.started_at
            if elapsed > timedelta(hours=experiment.max_duration_hours):
                logger.info(f"Experiment {experiment_id} reached max duration")
                self.end_experiment(experiment_id)
                return

        # Statistical test for promotion
        result = await self._run_significance_test(
            champion_metrics,
            challenger_metrics,
        )

        if result["is_significant"] and result["challenger_better"]:
            if result["p_value"] < experiment.promotion_threshold:
                logger.info(
                    f"Challenger wins for {experiment_id} "
                    f"(p={result['p_value']:.4f})"
                )
                self.end_experiment(experiment_id, promote_challenger=True)

    async def _run_significance_test(
        self,
        champion: ExperimentMetrics,
        challenger: ExperimentMetrics,
    ) -> Dict[str, Any]:
        """Run statistical significance test."""
        # Two-sample t-test on latency (lower is better)
        try:
            from scipy import stats

            # Compare latencies
            n1, n2 = champion.request_count, challenger.request_count
            mean1, mean2 = champion.avg_latency_ms, challenger.avg_latency_ms
            var1 = champion.prediction_variance + 1e-8
            var2 = challenger.prediction_variance + 1e-8

            # Welch's t-test
            t_stat = (mean1 - mean2) / (
                (var1/n1 + var2/n2) ** 0.5 + 1e-8
            )
            df = ((var1/n1 + var2/n2)**2) / (
                (var1/n1)**2/(n1-1) + (var2/n2)**2/(n2-1) + 1e-8
            )
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))

            return {
                "is_significant": p_value < 0.05,
                "challenger_better": mean2 < mean1,  # Lower latency is better
                "p_value": float(p_value),
                "effect_size": (mean1 - mean2) / (mean1 + 1e-8),
            }

        except ImportError:
            # Fallback without scipy
            return {
                "is_significant": False,
                "challenger_better": challenger.avg_latency_ms < champion.avg_latency_ms,
                "p_value": 1.0,
                "effect_size": 0,
            }

    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment results and statistics."""
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            return {}

        metrics = self.metrics.get(experiment_id, {})

        results = {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "status": experiment.status.value,
            "endpoint": experiment.endpoint,
            "created_at": experiment.created_at.isoformat(),
            "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
            "variants": {},
        }

        for variant in experiment.variants:
            variant_metrics = metrics.get(variant.name)
            if variant_metrics:
                results["variants"][variant.name] = {
                    "model_name": variant.model_name,
                    "model_version": variant.model_version,
                    "traffic_weight": variant.traffic_weight,
                    "request_count": variant_metrics.request_count,
                    "avg_latency_ms": variant_metrics.avg_latency_ms,
                    "error_rate": variant_metrics.error_rate,
                    "custom_metrics": {
                        k: v / max(1, variant_metrics.request_count)
                        for k, v in variant_metrics.custom_metrics.items()
                    },
                }

        return results

    def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List all experiments."""
        experiments = []

        for exp_id, exp in self.experiments.items():
            if status and exp.status != status:
                continue

            experiments.append({
                "experiment_id": exp_id,
                "name": exp.name,
                "endpoint": exp.endpoint,
                "status": exp.status.value,
                "created_at": exp.created_at.isoformat(),
            })

        return experiments


class DataDriftDetector:
    """Detect data drift in model inputs."""

    def __init__(
        self,
        reference_window: int = 1000,
        detection_threshold: float = 0.05,
    ):
        """Initialize drift detector.

        Args:
            reference_window: Number of samples for reference distribution
            detection_threshold: P-value threshold for drift detection
        """
        self.reference_window = reference_window
        self.detection_threshold = detection_threshold
        self.reference_data: Dict[str, List[float]] = defaultdict(list)
        self.current_data: Dict[str, List[float]] = defaultdict(list)

    def add_reference(self, feature_name: str, value: float):
        """Add value to reference distribution."""
        self.reference_data[feature_name].append(value)
        if len(self.reference_data[feature_name]) > self.reference_window:
            self.reference_data[feature_name] = \
                self.reference_data[feature_name][-self.reference_window:]

    def add_sample(self, feature_name: str, value: float):
        """Add value to current sample."""
        self.current_data[feature_name].append(value)
        if len(self.current_data[feature_name]) > self.reference_window:
            self.current_data[feature_name] = \
                self.current_data[feature_name][-self.reference_window:]

    def check_drift(self, feature_name: str) -> Dict[str, Any]:
        """Check for drift in a feature."""
        ref = self.reference_data.get(feature_name, [])
        curr = self.current_data.get(feature_name, [])

        if len(ref) < 100 or len(curr) < 100:
            return {
                "feature": feature_name,
                "drift_detected": False,
                "reason": "insufficient_data",
            }

        try:
            from scipy import stats

            # Kolmogorov-Smirnov test
            ks_stat, p_value = stats.ks_2samp(ref, curr)

            drift_detected = p_value < self.detection_threshold

            return {
                "feature": feature_name,
                "drift_detected": drift_detected,
                "ks_statistic": float(ks_stat),
                "p_value": float(p_value),
                "ref_mean": float(sum(ref) / len(ref)),
                "curr_mean": float(sum(curr) / len(curr)),
            }

        except ImportError:
            # Simple mean comparison fallback
            ref_mean = sum(ref) / len(ref)
            curr_mean = sum(curr) / len(curr)
            drift = abs(ref_mean - curr_mean) / (ref_mean + 1e-8) > 0.2

            return {
                "feature": feature_name,
                "drift_detected": drift,
                "ref_mean": ref_mean,
                "curr_mean": curr_mean,
            }

    def check_all_features(self) -> Dict[str, Dict[str, Any]]:
        """Check drift for all tracked features."""
        results = {}
        all_features = set(self.reference_data.keys()) | set(self.current_data.keys())

        for feature in all_features:
            results[feature] = self.check_drift(feature)

        return results


# Global instances
_ab_router: Optional[ABTestRouter] = None
_drift_detector: Optional[DataDriftDetector] = None


def get_ab_router() -> ABTestRouter:
    """Get global A/B test router."""
    global _ab_router
    if _ab_router is None:
        _ab_router = ABTestRouter()
    return _ab_router


def get_drift_detector() -> DataDriftDetector:
    """Get global drift detector."""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DataDriftDetector()
    return _drift_detector
