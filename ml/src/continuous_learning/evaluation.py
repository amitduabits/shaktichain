"""Evaluation gates for continuous learning.

Provides:
- Model comparison gates
- Shadow testing
- Segment analysis
- Human approval workflow
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import math

logger = logging.getLogger(__name__)


class EvaluationDecision(Enum):
    """Decision from evaluation gate."""
    APPROVE = "approve"
    REJECT = "reject"
    PENDING = "pending"
    REQUIRES_HUMAN = "requires_human"


@dataclass
class MetricComparison:
    """Comparison of a single metric."""
    metric_name: str
    baseline_value: float
    candidate_value: float
    improvement_pct: float
    threshold_pct: float
    passes: bool
    is_regression: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "improvement_pct": self.improvement_pct,
            "threshold_pct": self.threshold_pct,
            "passes": self.passes,
            "is_regression": self.is_regression,
        }


@dataclass
class SegmentAnalysis:
    """Analysis of model performance on a segment."""
    segment_name: str
    segment_filter: Dict[str, Any]
    sample_count: int
    baseline_metric: float
    candidate_metric: float
    improvement_pct: float
    passes: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "segment_name": self.segment_name,
            "segment_filter": self.segment_filter,
            "sample_count": self.sample_count,
            "baseline_metric": self.baseline_metric,
            "candidate_metric": self.candidate_metric,
            "improvement_pct": self.improvement_pct,
            "passes": self.passes,
        }


@dataclass
class ModelComparison:
    """Result of comparing two models."""
    baseline_model: str
    candidate_model: str
    metric_comparisons: List[MetricComparison]
    segment_analyses: List[SegmentAnalysis]
    overall_improvement: float
    decision: EvaluationDecision
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def passes_all_metrics(self) -> bool:
        """Check if all metrics pass."""
        return all(m.passes for m in self.metric_comparisons)

    @property
    def has_regressions(self) -> bool:
        """Check if any segments regressed."""
        return any(s.improvement_pct < 0 for s in self.segment_analyses)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "baseline_model": self.baseline_model,
            "candidate_model": self.candidate_model,
            "metric_comparisons": [m.to_dict() for m in self.metric_comparisons],
            "segment_analyses": [s.to_dict() for s in self.segment_analyses],
            "overall_improvement": self.overall_improvement,
            "decision": self.decision.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ShadowTestResult:
    """Result of shadow testing."""
    test_id: str
    candidate_model: str
    baseline_model: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_requests: int = 0
    candidate_metrics: Dict[str, float] = field(default_factory=dict)
    baseline_metrics: Dict[str, float] = field(default_factory=dict)
    decision: EvaluationDecision = EvaluationDecision.PENDING
    errors: List[str] = field(default_factory=list)

    @property
    def duration_hours(self) -> float:
        """Get test duration in hours."""
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds() / 3600

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "candidate_model": self.candidate_model,
            "baseline_model": self.baseline_model,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_hours": self.duration_hours,
            "total_requests": self.total_requests,
            "candidate_metrics": self.candidate_metrics,
            "baseline_metrics": self.baseline_metrics,
            "decision": self.decision.value,
            "errors": self.errors,
        }


@dataclass
class EvaluationResult:
    """Result of evaluation gate."""
    gate_name: str
    decision: EvaluationDecision
    model_comparison: Optional[ModelComparison] = None
    shadow_test: Optional[ShadowTestResult] = None
    requires_human_approval: bool = False
    human_approval_status: Optional[str] = None
    human_approver: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gate_name": self.gate_name,
            "decision": self.decision.value,
            "model_comparison": self.model_comparison.to_dict() if self.model_comparison else None,
            "shadow_test": self.shadow_test.to_dict() if self.shadow_test else None,
            "requires_human_approval": self.requires_human_approval,
            "human_approval_status": self.human_approval_status,
            "human_approver": self.human_approver,
            "notes": self.notes,
            "timestamp": self.timestamp.isoformat(),
        }


class EvaluationGate:
    """Evaluation gate for model deployment decisions."""

    def __init__(
        self,
        min_improvement_pct: float = 2.0,
        max_regression_pct: float = 5.0,
        require_human_for_major: bool = True,
        major_change_threshold: float = 10.0,
    ):
        """Initialize evaluation gate.

        Args:
            min_improvement_pct: Minimum improvement required
            max_regression_pct: Maximum allowed regression on any segment
            require_human_for_major: Require human approval for major changes
            major_change_threshold: Threshold for major change
        """
        self.min_improvement_pct = min_improvement_pct
        self.max_regression_pct = max_regression_pct
        self.require_human_for_major = require_human_for_major
        self.major_change_threshold = major_change_threshold

        # Segments to evaluate
        self.segments = [
            {"name": "peak_hours", "filter": {"hour": range(7, 20)}},
            {"name": "off_peak", "filter": {"hour": list(range(0, 7)) + list(range(20, 24))}},
            {"name": "weekday", "filter": {"day_of_week": range(0, 5)}},
            {"name": "weekend", "filter": {"day_of_week": range(5, 7)}},
        ]

        # Human approval queue
        self._pending_approvals: Dict[str, EvaluationResult] = {}
        self._approval_callbacks: List[Callable] = []

    def on_approval_needed(self, callback: Callable):
        """Register callback for human approval needed.

        Args:
            callback: Callback function
        """
        self._approval_callbacks.append(callback)

    async def evaluate(
        self,
        baseline_model: str,
        candidate_model: str,
        baseline_predictions: List[Dict[str, Any]],
        candidate_predictions: List[Dict[str, Any]],
        actuals: List[Dict[str, Any]],
        metrics: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """Evaluate candidate model against baseline.

        Args:
            baseline_model: Baseline model name/version
            candidate_model: Candidate model name/version
            baseline_predictions: Predictions from baseline
            candidate_predictions: Predictions from candidate
            actuals: Actual values
            metrics: Metrics to evaluate

        Returns:
            EvaluationResult
        """
        metrics = metrics or ["mape", "rmse", "mae"]

        # Calculate metrics
        metric_comparisons = []
        for metric_name in metrics:
            baseline_value = self._calculate_metric(
                baseline_predictions, actuals, metric_name
            )
            candidate_value = self._calculate_metric(
                candidate_predictions, actuals, metric_name
            )

            # For error metrics, lower is better
            if baseline_value > 0:
                improvement = (baseline_value - candidate_value) / baseline_value * 100
            else:
                improvement = 0

            passes = improvement >= self.min_improvement_pct

            metric_comparisons.append(MetricComparison(
                metric_name=metric_name,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                improvement_pct=improvement,
                threshold_pct=self.min_improvement_pct,
                passes=passes,
                is_regression=improvement < -self.max_regression_pct,
            ))

        # Segment analysis
        segment_analyses = []
        for segment in self.segments:
            analysis = await self._analyze_segment(
                segment,
                baseline_predictions,
                candidate_predictions,
                actuals,
            )
            segment_analyses.append(analysis)

        # Calculate overall improvement
        overall_improvement = sum(m.improvement_pct for m in metric_comparisons) / len(metric_comparisons)

        # Make decision
        comparison = ModelComparison(
            baseline_model=baseline_model,
            candidate_model=candidate_model,
            metric_comparisons=metric_comparisons,
            segment_analyses=segment_analyses,
            overall_improvement=overall_improvement,
            decision=EvaluationDecision.PENDING,
            reason="",
        )

        # Check for regressions
        has_severe_regression = any(m.is_regression for m in metric_comparisons)
        has_segment_regression = any(
            s.improvement_pct < -self.max_regression_pct
            for s in segment_analyses
        )

        if has_severe_regression or has_segment_regression:
            comparison.decision = EvaluationDecision.REJECT
            comparison.reason = "Model shows regression on key metrics or segments"

        elif comparison.passes_all_metrics:
            # Check if major change requiring human approval
            if self.require_human_for_major and overall_improvement > self.major_change_threshold:
                comparison.decision = EvaluationDecision.REQUIRES_HUMAN
                comparison.reason = f"Major improvement ({overall_improvement:.1f}%) requires human approval"
            else:
                comparison.decision = EvaluationDecision.APPROVE
                comparison.reason = f"Model improves by {overall_improvement:.1f}%"

        else:
            comparison.decision = EvaluationDecision.REJECT
            comparison.reason = "Model does not meet minimum improvement threshold"

        # Create result
        result = EvaluationResult(
            gate_name="model_comparison",
            decision=comparison.decision,
            model_comparison=comparison,
            requires_human_approval=(comparison.decision == EvaluationDecision.REQUIRES_HUMAN),
        )

        # Queue for human approval if needed
        if result.requires_human_approval:
            self._pending_approvals[candidate_model] = result
            await self._notify_approval_needed(result)

        return result

    async def _analyze_segment(
        self,
        segment: Dict[str, Any],
        baseline_predictions: List[Dict[str, Any]],
        candidate_predictions: List[Dict[str, Any]],
        actuals: List[Dict[str, Any]],
    ) -> SegmentAnalysis:
        """Analyze model performance on a segment."""
        segment_name = segment["name"]
        filter_spec = segment["filter"]

        # Filter data to segment
        indices = []
        for i, actual in enumerate(actuals):
            matches = True
            for key, values in filter_spec.items():
                if key in actual.get("features", {}):
                    if actual["features"][key] not in values:
                        matches = False
                        break
            if matches:
                indices.append(i)

        if not indices:
            return SegmentAnalysis(
                segment_name=segment_name,
                segment_filter=filter_spec,
                sample_count=0,
                baseline_metric=0,
                candidate_metric=0,
                improvement_pct=0,
                passes=True,
            )

        # Calculate segment metrics
        baseline_segment = [baseline_predictions[i] for i in indices if i < len(baseline_predictions)]
        candidate_segment = [candidate_predictions[i] for i in indices if i < len(candidate_predictions)]
        actuals_segment = [actuals[i] for i in indices]

        baseline_mape = self._calculate_metric(baseline_segment, actuals_segment, "mape")
        candidate_mape = self._calculate_metric(candidate_segment, actuals_segment, "mape")

        if baseline_mape > 0:
            improvement = (baseline_mape - candidate_mape) / baseline_mape * 100
        else:
            improvement = 0

        return SegmentAnalysis(
            segment_name=segment_name,
            segment_filter=filter_spec,
            sample_count=len(indices),
            baseline_metric=baseline_mape,
            candidate_metric=candidate_mape,
            improvement_pct=improvement,
            passes=improvement >= -self.max_regression_pct,
        )

    def _calculate_metric(
        self,
        predictions: List[Dict[str, Any]],
        actuals: List[Dict[str, Any]],
        metric_name: str,
    ) -> float:
        """Calculate a metric value."""
        if not predictions or not actuals:
            return 0.0

        # Extract values
        pred_values = []
        actual_values = []

        for i, (pred, actual) in enumerate(zip(predictions, actuals)):
            p = pred.get("prediction") or pred.get("value")
            a = actual.get("actual_value") or actual.get("value")

            if p is not None and a is not None:
                try:
                    pred_values.append(float(p))
                    actual_values.append(float(a))
                except (TypeError, ValueError):
                    pass

        if not pred_values:
            return 0.0

        if metric_name == "mape":
            # Mean Absolute Percentage Error
            errors = []
            for p, a in zip(pred_values, actual_values):
                if a != 0:
                    errors.append(abs((p - a) / a))
            return sum(errors) / len(errors) * 100 if errors else 0

        elif metric_name == "rmse":
            # Root Mean Square Error
            sq_errors = [(p - a) ** 2 for p, a in zip(pred_values, actual_values)]
            return math.sqrt(sum(sq_errors) / len(sq_errors))

        elif metric_name == "mae":
            # Mean Absolute Error
            abs_errors = [abs(p - a) for p, a in zip(pred_values, actual_values)]
            return sum(abs_errors) / len(abs_errors)

        return 0.0

    async def _notify_approval_needed(self, result: EvaluationResult):
        """Notify that human approval is needed."""
        for callback in self._approval_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Approval callback error: {e}")

    async def submit_human_approval(
        self,
        model_name: str,
        approved: bool,
        approver: str,
        notes: str = "",
    ) -> Optional[EvaluationResult]:
        """Submit human approval decision.

        Args:
            model_name: Model awaiting approval
            approved: Whether approved
            approver: Name of approver
            notes: Approval notes

        Returns:
            Updated evaluation result
        """
        if model_name not in self._pending_approvals:
            return None

        result = self._pending_approvals.pop(model_name)
        result.human_approver = approver
        result.human_approval_status = "approved" if approved else "rejected"
        result.notes.append(notes)
        result.decision = EvaluationDecision.APPROVE if approved else EvaluationDecision.REJECT

        logger.info(f"Human approval for {model_name}: {'approved' if approved else 'rejected'} by {approver}")

        return result

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get pending human approvals."""
        return [r.to_dict() for r in self._pending_approvals.values()]


class ShadowTest:
    """Shadow testing for candidate models."""

    def __init__(
        self,
        duration_hours: int = 24,
        min_requests: int = 1000,
        max_latency_increase_pct: float = 20.0,
    ):
        """Initialize shadow test.

        Args:
            duration_hours: Test duration
            min_requests: Minimum requests before conclusion
            max_latency_increase_pct: Max allowed latency increase
        """
        self.duration_hours = duration_hours
        self.min_requests = min_requests
        self.max_latency_increase_pct = max_latency_increase_pct

        # Active tests
        self._active_tests: Dict[str, ShadowTestResult] = {}

    async def start_test(
        self,
        candidate_model: str,
        baseline_model: str,
    ) -> ShadowTestResult:
        """Start a shadow test.

        Args:
            candidate_model: Candidate model version
            baseline_model: Baseline model version

        Returns:
            ShadowTestResult
        """
        import uuid

        test_id = f"shadow-{uuid.uuid4().hex[:8]}"

        result = ShadowTestResult(
            test_id=test_id,
            candidate_model=candidate_model,
            baseline_model=baseline_model,
            started_at=datetime.now(),
        )

        self._active_tests[test_id] = result

        logger.info(f"Started shadow test {test_id}: {candidate_model} vs {baseline_model}")

        return result

    async def record_prediction(
        self,
        test_id: str,
        candidate_prediction: float,
        baseline_prediction: float,
        actual_value: Optional[float] = None,
        candidate_latency_ms: float = 0,
        baseline_latency_ms: float = 0,
    ):
        """Record a prediction pair from shadow testing.

        Args:
            test_id: Shadow test ID
            candidate_prediction: Candidate model prediction
            baseline_prediction: Baseline model prediction
            actual_value: Actual value (if available)
            candidate_latency_ms: Candidate latency
            baseline_latency_ms: Baseline latency
        """
        if test_id not in self._active_tests:
            return

        result = self._active_tests[test_id]
        result.total_requests += 1

        # Update metrics (running averages)
        n = result.total_requests

        # Error metrics
        if actual_value is not None:
            cand_error = abs(candidate_prediction - actual_value)
            base_error = abs(baseline_prediction - actual_value)

            result.candidate_metrics["mae"] = (
                (result.candidate_metrics.get("mae", 0) * (n - 1) + cand_error) / n
            )
            result.baseline_metrics["mae"] = (
                (result.baseline_metrics.get("mae", 0) * (n - 1) + base_error) / n
            )

        # Latency metrics
        result.candidate_metrics["avg_latency_ms"] = (
            (result.candidate_metrics.get("avg_latency_ms", 0) * (n - 1) + candidate_latency_ms) / n
        )
        result.baseline_metrics["avg_latency_ms"] = (
            (result.baseline_metrics.get("avg_latency_ms", 0) * (n - 1) + baseline_latency_ms) / n
        )

    async def check_test(self, test_id: str) -> ShadowTestResult:
        """Check shadow test status and potentially conclude.

        Args:
            test_id: Shadow test ID

        Returns:
            Updated test result
        """
        if test_id not in self._active_tests:
            raise ValueError(f"No active test with ID: {test_id}")

        result = self._active_tests[test_id]

        # Check if test should conclude
        duration_hours = result.duration_hours
        has_min_requests = result.total_requests >= self.min_requests

        if duration_hours >= self.duration_hours and has_min_requests:
            # Conclude test
            result.completed_at = datetime.now()

            # Make decision
            cand_mae = result.candidate_metrics.get("mae", 0)
            base_mae = result.baseline_metrics.get("mae", 0)
            cand_latency = result.candidate_metrics.get("avg_latency_ms", 0)
            base_latency = result.baseline_metrics.get("avg_latency_ms", 0)

            # Check accuracy improvement
            if base_mae > 0:
                accuracy_improvement = (base_mae - cand_mae) / base_mae * 100
            else:
                accuracy_improvement = 0

            # Check latency regression
            if base_latency > 0:
                latency_increase = (cand_latency - base_latency) / base_latency * 100
            else:
                latency_increase = 0

            if latency_increase > self.max_latency_increase_pct:
                result.decision = EvaluationDecision.REJECT
                result.errors.append(f"Latency increased by {latency_increase:.1f}%")
            elif accuracy_improvement >= 0:
                result.decision = EvaluationDecision.APPROVE
            else:
                result.decision = EvaluationDecision.REJECT
                result.errors.append("No accuracy improvement in shadow testing")

            # Remove from active tests
            del self._active_tests[test_id]

            logger.info(f"Shadow test {test_id} completed: {result.decision.value}")

        return result

    async def stop_test(self, test_id: str) -> Optional[ShadowTestResult]:
        """Stop a shadow test early.

        Args:
            test_id: Shadow test ID

        Returns:
            Final test result
        """
        if test_id not in self._active_tests:
            return None

        result = self._active_tests.pop(test_id)
        result.completed_at = datetime.now()
        result.decision = EvaluationDecision.REJECT
        result.errors.append("Test stopped early")

        return result

    def get_active_tests(self) -> List[Dict[str, Any]]:
        """Get active shadow tests."""
        return [t.to_dict() for t in self._active_tests.values()]
