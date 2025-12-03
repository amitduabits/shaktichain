"""Data validation for continuous learning.

Provides:
- Schema validation
- Distribution drift detection
- Data quality checks
- Alerting on threshold violations
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

logger = logging.getLogger(__name__)

# Optional imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class ValidationSeverity(Enum):
    """Severity of validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DriftType(Enum):
    """Types of data drift."""
    FEATURE_DRIFT = "feature_drift"
    LABEL_DRIFT = "label_drift"
    CONCEPT_DRIFT = "concept_drift"
    PREDICTION_DRIFT = "prediction_drift"


@dataclass
class ValidationIssue:
    """A validation issue."""
    severity: ValidationSeverity
    category: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
                  for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in self.issues],
            "stats": self.stats,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DriftReport:
    """Report of data drift detection."""
    has_drift: bool
    drift_type: Optional[DriftType] = None
    drift_score: float = 0.0
    threshold: float = 0.0
    feature_drifts: Dict[str, float] = field(default_factory=dict)
    reference_period: Optional[str] = None
    current_period: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "has_drift": self.has_drift,
            "drift_type": self.drift_type.value if self.drift_type else None,
            "drift_score": self.drift_score,
            "threshold": self.threshold,
            "feature_drifts": self.feature_drifts,
            "reference_period": self.reference_period,
            "current_period": self.current_period,
            "details": self.details,
        }


class SchemaValidator:
    """Validate data against expected schema."""

    def __init__(self, schema: Dict[str, Any]):
        """Initialize schema validator.

        Args:
            schema: Expected schema definition
        """
        self.schema = schema

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against schema.

        Args:
            data: Data to validate

        Returns:
            ValidationResult
        """
        issues = []

        # Check required fields
        required = self.schema.get("required", [])
        for field_name in required:
            if field_name not in data:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="schema",
                    message=f"Missing required field: {field_name}",
                ))

        # Check field types
        properties = self.schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if field_name not in data:
                continue

            value = data[field_name]
            expected_type = field_schema.get("type")

            if not self._check_type(value, expected_type):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="schema",
                    message=f"Invalid type for {field_name}: expected {expected_type}",
                    details={"actual_type": type(value).__name__},
                ))

            # Check constraints
            if "minimum" in field_schema and value < field_schema["minimum"]:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="schema",
                    message=f"{field_name} below minimum: {value} < {field_schema['minimum']}",
                ))

            if "maximum" in field_schema and value > field_schema["maximum"]:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="schema",
                    message=f"{field_name} above maximum: {value} > {field_schema['maximum']}",
                ))

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(is_valid=is_valid, issues=issues)

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_map.get(expected_type)
        if expected is None:
            return True

        return isinstance(value, expected)


class DriftDetector:
    """Detect distribution drift in features."""

    def __init__(
        self,
        reference_data: Optional[List[Dict[str, Any]]] = None,
        feature_columns: Optional[List[str]] = None,
        drift_threshold: float = 0.1,
    ):
        """Initialize drift detector.

        Args:
            reference_data: Reference/baseline data
            feature_columns: Feature columns to monitor
            drift_threshold: Threshold for drift detection
        """
        self.feature_columns = feature_columns or []
        self.drift_threshold = drift_threshold

        # Reference statistics
        self._reference_stats: Dict[str, Dict[str, float]] = {}

        if reference_data:
            self.set_reference(reference_data)

    def set_reference(self, data: List[Dict[str, Any]]):
        """Set reference data for drift comparison.

        Args:
            data: Reference dataset
        """
        if not data:
            return

        # Compute reference statistics for each feature
        for feature in self.feature_columns:
            values = [d.get(feature) for d in data if d.get(feature) is not None]

            if not values:
                continue

            # Handle nested features
            if isinstance(values[0], dict):
                continue

            try:
                values = [float(v) for v in values]
            except (TypeError, ValueError):
                continue

            self._reference_stats[feature] = self._compute_stats(values)

        logger.info(f"Reference set with {len(data)} samples, {len(self._reference_stats)} features")

    def _compute_stats(self, values: List[float]) -> Dict[str, float]:
        """Compute statistics for a feature."""
        if not values:
            return {}

        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        std = math.sqrt(variance) if variance > 0 else 0

        sorted_values = sorted(values)
        median = sorted_values[n // 2]
        p25 = sorted_values[n // 4] if n >= 4 else sorted_values[0]
        p75 = sorted_values[3 * n // 4] if n >= 4 else sorted_values[-1]

        return {
            "count": n,
            "mean": mean,
            "std": std,
            "min": min(values),
            "max": max(values),
            "median": median,
            "p25": p25,
            "p75": p75,
        }

    def detect_drift(
        self,
        current_data: List[Dict[str, Any]],
        method: str = "ks",
    ) -> DriftReport:
        """Detect drift between reference and current data.

        Args:
            current_data: Current data to compare
            method: Detection method (ks, psi, wasserstein)

        Returns:
            DriftReport
        """
        if not self._reference_stats:
            return DriftReport(has_drift=False, details={"error": "No reference data"})

        feature_drifts = {}
        max_drift = 0.0

        for feature in self.feature_columns:
            if feature not in self._reference_stats:
                continue

            # Extract current values
            values = [d.get(feature) for d in current_data if d.get(feature) is not None]
            if not values:
                continue

            try:
                values = [float(v) for v in values]
            except (TypeError, ValueError):
                continue

            # Compute drift score
            drift_score = self._compute_drift(
                self._reference_stats[feature],
                values,
                method,
            )

            feature_drifts[feature] = drift_score
            max_drift = max(max_drift, drift_score)

        has_drift = max_drift > self.drift_threshold

        return DriftReport(
            has_drift=has_drift,
            drift_type=DriftType.FEATURE_DRIFT if has_drift else None,
            drift_score=max_drift,
            threshold=self.drift_threshold,
            feature_drifts=feature_drifts,
            details={
                "method": method,
                "reference_size": self._reference_stats.get(self.feature_columns[0], {}).get("count", 0)
                    if self.feature_columns else 0,
                "current_size": len(current_data),
            },
        )

    def _compute_drift(
        self,
        reference_stats: Dict[str, float],
        current_values: List[float],
        method: str,
    ) -> float:
        """Compute drift score for a single feature."""
        if not current_values:
            return 0.0

        current_stats = self._compute_stats(current_values)

        if method == "ks" and HAS_SCIPY:
            # Kolmogorov-Smirnov test (approximate using stats)
            # Compare CDFs
            ref_mean = reference_stats["mean"]
            ref_std = max(reference_stats["std"], 1e-6)
            cur_mean = current_stats["mean"]
            cur_std = max(current_stats["std"], 1e-6)

            # Simplified KS-like score based on distribution overlap
            mean_diff = abs(cur_mean - ref_mean) / ref_std
            std_ratio = max(cur_std / ref_std, ref_std / cur_std)

            return min(1.0, mean_diff * 0.5 + (std_ratio - 1) * 0.5)

        elif method == "psi":
            # Population Stability Index
            return self._compute_psi(reference_stats, current_stats)

        else:
            # Simple mean/std comparison
            ref_mean = reference_stats["mean"]
            ref_std = max(reference_stats["std"], 1e-6)
            cur_mean = current_stats["mean"]

            return min(1.0, abs(cur_mean - ref_mean) / ref_std)

    def _compute_psi(
        self,
        reference_stats: Dict[str, float],
        current_stats: Dict[str, float],
    ) -> float:
        """Compute Population Stability Index."""
        # Simplified PSI based on mean shift
        ref_mean = reference_stats["mean"]
        cur_mean = current_stats["mean"]
        ref_std = max(reference_stats["std"], 1e-6)

        # Normalized difference
        z_score = abs(cur_mean - ref_mean) / ref_std

        # Map to 0-1 range
        return min(1.0, z_score / 3)  # 3 sigma = 1.0


class QualityChecker:
    """Check data quality metrics."""

    def __init__(
        self,
        null_threshold: float = 0.1,
        duplicate_threshold: float = 0.05,
        outlier_threshold: float = 0.05,
    ):
        """Initialize quality checker.

        Args:
            null_threshold: Max allowed null rate
            duplicate_threshold: Max allowed duplicate rate
            outlier_threshold: Max allowed outlier rate
        """
        self.null_threshold = null_threshold
        self.duplicate_threshold = duplicate_threshold
        self.outlier_threshold = outlier_threshold

    def check(
        self,
        data: List[Dict[str, Any]],
        id_column: Optional[str] = None,
    ) -> ValidationResult:
        """Check data quality.

        Args:
            data: Data to check
            id_column: Column to use for duplicate detection

        Returns:
            ValidationResult
        """
        issues = []
        stats = {}

        if not data:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="quality",
                message="No data provided",
            ))
            return ValidationResult(is_valid=False, issues=issues)

        n = len(data)
        stats["total_records"] = n

        # Check null rates per column
        null_rates = {}
        if data:
            columns = set()
            for record in data:
                columns.update(record.keys())

            for col in columns:
                null_count = sum(1 for d in data if d.get(col) is None)
                null_rate = null_count / n
                null_rates[col] = null_rate

                if null_rate > self.null_threshold:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="quality",
                        message=f"High null rate for {col}: {null_rate:.1%}",
                        details={"column": col, "null_rate": null_rate},
                    ))

        stats["null_rates"] = null_rates

        # Check duplicates
        if id_column:
            ids = [d.get(id_column) for d in data]
            unique_ids = set(ids)
            duplicate_rate = 1 - len(unique_ids) / n

            stats["duplicate_rate"] = duplicate_rate

            if duplicate_rate > self.duplicate_threshold:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="quality",
                    message=f"High duplicate rate: {duplicate_rate:.1%}",
                    details={"duplicate_rate": duplicate_rate},
                ))

        # Check for outliers in numeric columns
        outlier_stats = {}
        for col in list(data[0].keys()) if data else []:
            values = []
            for d in data:
                v = d.get(col)
                if v is not None:
                    try:
                        values.append(float(v))
                    except (TypeError, ValueError):
                        pass

            if len(values) > 10:
                outlier_rate = self._detect_outliers(values)
                outlier_stats[col] = outlier_rate

                if outlier_rate > self.outlier_threshold:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        category="quality",
                        message=f"Outliers detected in {col}: {outlier_rate:.1%}",
                        details={"column": col, "outlier_rate": outlier_rate},
                    ))

        stats["outlier_rates"] = outlier_stats

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(is_valid=is_valid, issues=issues, stats=stats)

    def _detect_outliers(self, values: List[float]) -> float:
        """Detect outlier rate using IQR method."""
        if len(values) < 4:
            return 0.0

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outliers = sum(1 for v in values if v < lower or v > upper)
        return outliers / n


class DataValidator:
    """Unified data validator combining schema, drift, and quality checks."""

    def __init__(
        self,
        schema: Optional[Dict[str, Any]] = None,
        drift_threshold: float = 0.1,
        feature_columns: Optional[List[str]] = None,
    ):
        """Initialize data validator.

        Args:
            schema: Data schema
            drift_threshold: Threshold for drift detection
            feature_columns: Feature columns to monitor
        """
        self.schema_validator = SchemaValidator(schema or {})
        self.drift_detector = DriftDetector(
            feature_columns=feature_columns or [],
            drift_threshold=drift_threshold,
        )
        self.quality_checker = QualityChecker()

        self._reference_data: Optional[List[Dict[str, Any]]] = None

    def set_reference_data(self, data: List[Dict[str, Any]]):
        """Set reference data for drift detection.

        Args:
            data: Reference dataset
        """
        self._reference_data = data
        self.drift_detector.set_reference(data)

    def validate(
        self,
        data: List[Dict[str, Any]],
        check_schema: bool = True,
        check_drift: bool = True,
        check_quality: bool = True,
    ) -> ValidationResult:
        """Validate data comprehensively.

        Args:
            data: Data to validate
            check_schema: Whether to check schema
            check_drift: Whether to check drift
            check_quality: Whether to check quality

        Returns:
            ValidationResult
        """
        all_issues = []
        all_stats = {}

        # Schema validation (sample)
        if check_schema and data:
            for record in data[:10]:
                result = self.schema_validator.validate(record)
                all_issues.extend(result.issues)

        # Drift detection
        if check_drift and self._reference_data:
            drift_report = self.drift_detector.detect_drift(data)
            all_stats["drift"] = drift_report.to_dict()

            if drift_report.has_drift:
                all_issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="drift",
                    message=f"Data drift detected (score: {drift_report.drift_score:.3f})",
                    details=drift_report.to_dict(),
                ))

        # Quality checks
        if check_quality:
            quality_result = self.quality_checker.check(data)
            all_issues.extend(quality_result.issues)
            all_stats["quality"] = quality_result.stats

        is_valid = not any(
            i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
            for i in all_issues
        )

        return ValidationResult(
            is_valid=is_valid,
            issues=all_issues,
            stats=all_stats,
        )

    def validate_for_training(
        self,
        data: List[Dict[str, Any]],
        min_samples: int = 1000,
    ) -> ValidationResult:
        """Validate data is suitable for training.

        Args:
            data: Training data
            min_samples: Minimum required samples

        Returns:
            ValidationResult
        """
        result = self.validate(data)

        # Additional training-specific checks
        if len(data) < min_samples:
            result.issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="training",
                message=f"Insufficient samples: {len(data)} < {min_samples}",
            ))
            result.is_valid = False

        return result
