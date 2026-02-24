"""Data validation and quality checks for SHAKTI-CHAIN."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation."""

    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQualityReport:
    """Comprehensive data quality report."""

    timestamp: datetime
    total_records: int
    date_range: Tuple[datetime, datetime]
    missing_timestamps: int
    missing_values: Dict[str, int]
    outliers: Dict[str, int]
    value_ranges: Dict[str, Tuple[float, float]]
    anomalies: List[Dict[str, Any]]
    completeness_score: float
    validity_score: float
    consistency_score: float
    overall_score: float


class DataValidator:
    """Validator for SHAKTI-CHAIN energy data."""

    # Expected ranges for different data types
    RANGES = {
        "load_mw": (0, 200000),  # Max possible load across all regions
        "frequency_hz": (48.5, 51.5),  # Extended range for anomalies
        "temperature_c": (-10, 55),  # India temperature range
        "humidity_pct": (0, 100),
        "wind_speed_ms": (0, 50),
        "price_inr_mwh": (0, 50000),  # Max price seen in Indian markets
    }

    # Expected frequency (should be hourly)
    EXPECTED_FREQUENCY = "1h"

    def __init__(
        self,
        timezone: str = "Asia/Kolkata",
        outlier_threshold: float = 3.0,
        missing_threshold: float = 0.05,  # 5% missing allowed
    ):
        """Initialize data validator.

        Args:
            timezone: Timezone for data (default: IST)
            outlier_threshold: Z-score threshold for outliers
            missing_threshold: Maximum allowed missing data ratio
        """
        self.timezone = timezone
        self.outlier_threshold = outlier_threshold
        self.missing_threshold = missing_threshold

    def validate_timestamps(self, df: pd.DataFrame) -> ValidationResult:
        """Validate timestamps in the data.

        Checks:
        - Timestamp column exists
        - Timestamps are in chronological order
        - No duplicate timestamps
        - Consistent frequency (hourly)
        - Timezone is correct

        Args:
            df: Input DataFrame

        Returns:
            Validation result
        """
        result = ValidationResult(passed=True)

        # Check timestamp column exists
        if "timestamp" not in df.columns:
            result.passed = False
            result.errors.append("Missing 'timestamp' column")
            return result

        # Check if datetime
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            try:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception as e:
                result.passed = False
                result.errors.append(f"Cannot convert timestamp to datetime: {e}")
                return result

        has_region = "region" in df.columns
        duplicate_subset = ["timestamp", "region"] if has_region else ["timestamp"]

        # Check for duplicates (timestamp+region for multi-region data)
        duplicates = df.duplicated(subset=duplicate_subset).sum()
        if duplicates > 0:
            result.passed = False
            result.errors.append(f"Found {duplicates} duplicate timestamps")

        # Check chronological order
        if has_region:
            non_monotonic_regions = 0
            for _, group in df.groupby("region"):
                if not group.sort_values("timestamp")["timestamp"].is_monotonic_increasing:
                    non_monotonic_regions += 1
            if non_monotonic_regions > 0:
                result.warnings.append(
                    f"Timestamps are not in chronological order for {non_monotonic_regions} regions"
                )
        else:
            if not df["timestamp"].is_monotonic_increasing:
                result.warnings.append("Timestamps are not in chronological order")

        # Check frequency
        expected_diff = pd.Timedelta(hours=1)
        irregular = 0
        missing_count = 0

        if has_region:
            for _, group in df.groupby("region"):
                df_sorted = group.sort_values("timestamp")
                unique_group = df_sorted.drop_duplicates(subset=["timestamp"])

                time_diffs = unique_group["timestamp"].diff()
                irregular += int((time_diffs.dropna() != expected_diff).sum())

                date_range = pd.date_range(
                    start=unique_group["timestamp"].min(),
                    end=unique_group["timestamp"].max(),
                    freq="h",
                )
                missing_count += max(0, len(date_range) - len(unique_group))
        else:
            df_sorted = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])
            time_diffs = df_sorted["timestamp"].diff()
            irregular = int((time_diffs.dropna() != expected_diff).sum())
            date_range = pd.date_range(
                start=df_sorted["timestamp"].min(),
                end=df_sorted["timestamp"].max(),
                freq="h",
            )
            missing_count = max(0, len(date_range) - len(df_sorted))

        if irregular > len(df) * 0.01:  # More than 1% irregular
            result.warnings.append(
                f"Found {irregular} irregular time intervals "
                f"(expected hourly frequency)"
            )

        # Check timezone
        if df["timestamp"].dt.tz is None:
            result.warnings.append("Timestamps have no timezone information")
        elif str(df["timestamp"].dt.tz) != self.timezone:
            result.warnings.append(
                f"Timezone is {df['timestamp'].dt.tz}, expected {self.timezone}"
            )

        if missing_count > 0:
            result.warnings.append(f"Missing {missing_count} timestamps in range")
            result.metrics["missing_timestamps"] = missing_count

        result.metrics["total_records"] = len(df)
        result.metrics["date_range"] = (df["timestamp"].min(), df["timestamp"].max())

        return result

    def validate_value_ranges(self, df: pd.DataFrame) -> ValidationResult:
        """Validate that values are within expected ranges.

        Args:
            df: Input DataFrame

        Returns:
            Validation result
        """
        result = ValidationResult(passed=True)

        for column, (min_val, max_val) in self.RANGES.items():
            if column not in df.columns:
                continue

            # Check min
            below_min = (df[column] < min_val).sum()
            if below_min > 0:
                result.passed = False
                result.errors.append(
                    f"{column}: {below_min} values below minimum ({min_val})"
                )

            # Check max
            above_max = (df[column] > max_val).sum()
            if above_max > 0:
                result.passed = False
                result.errors.append(
                    f"{column}: {above_max} values above maximum ({max_val})"
                )

            # Store actual range
            result.metrics[f"{column}_range"] = (
                df[column].min(),
                df[column].max()
            )

        return result

    def detect_outliers(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None
    ) -> ValidationResult:
        """Detect outliers using z-score method.

        Args:
            df: Input DataFrame
            columns: Columns to check (None = all numeric)

        Returns:
            Validation result with outlier counts
        """
        result = ValidationResult(passed=True)

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        outlier_summary = {}

        for column in columns:
            if column not in df.columns:
                continue

            # Calculate z-scores
            mean = df[column].mean()
            std = df[column].std()

            if std == 0:
                continue

            z_scores = np.abs((df[column] - mean) / std)
            outliers = z_scores > self.outlier_threshold

            outlier_count = outliers.sum()

            if outlier_count > 0:
                outlier_pct = (outlier_count / len(df)) * 100
                outlier_summary[column] = outlier_count

                if outlier_pct > 5:  # More than 5% outliers
                    result.warnings.append(
                        f"{column}: {outlier_count} outliers ({outlier_pct:.2f}%)"
                    )

        result.metrics["outliers"] = outlier_summary
        return result

    def validate_missing_values(self, df: pd.DataFrame) -> ValidationResult:
        """Validate missing values.

        Args:
            df: Input DataFrame

        Returns:
            Validation result
        """
        result = ValidationResult(passed=True)

        missing = df.isnull().sum()
        missing_cols = missing[missing > 0]

        if len(missing_cols) > 0:
            for col, count in missing_cols.items():
                missing_pct = (count / len(df)) * 100

                if missing_pct > self.missing_threshold * 100:
                    result.passed = False
                    result.errors.append(
                        f"{col}: {count} missing values ({missing_pct:.2f}%)"
                    )
                else:
                    result.warnings.append(
                        f"{col}: {count} missing values ({missing_pct:.2f}%)"
                    )

        result.metrics["missing_values"] = missing_cols.to_dict()
        return result

    def detect_anomalies(self, df: pd.DataFrame) -> ValidationResult:
        """Detect anomalous patterns in the data.

        Checks for:
        - Consecutive identical values (stuck sensors)
        - Sudden spikes or drops
        - Impossible combinations

        Args:
            df: Input DataFrame

        Returns:
            Validation result with anomalies
        """
        result = ValidationResult(passed=True)
        anomalies = []

        has_region = "region" in df.columns
        grouped = (
            [(region, grp.sort_values("timestamp")) for region, grp in df.groupby("region")]
            if has_region
            else [("all", df.sort_values("timestamp"))]
        )

        # Check for consecutive identical values
        for column in ["load_mw", "temperature_c", "price_inr_mwh"]:
            if column not in df.columns:
                continue

            stuck_points = 0
            for _, grp in grouped:
                if column not in grp.columns:
                    continue
                consecutive = (grp[column] == grp[column].shift()).astype(int)
                consecutive_sum = consecutive.rolling(window=6).sum()
                stuck_points += int((consecutive_sum >= 5).sum())

            if stuck_points > 0:
                result.warnings.append(
                    f"{column}: {stuck_points} potentially stuck values"
                )
                anomalies.append({
                    "type": "stuck_values",
                    "column": column,
                    "count": stuck_points
                })

        # Check for sudden changes
        for column in ["load_mw", "temperature_c"]:
            if column not in df.columns:
                continue

            sudden_changes = 0
            for _, grp in grouped:
                if column not in grp.columns:
                    continue
                change = grp[column].diff().abs()
                threshold = grp[column].std() * 3
                if pd.notna(threshold) and threshold > 0:
                    sudden_changes += int((change > threshold).sum())

            if sudden_changes > len(df) * 0.01:  # More than 1%
                result.warnings.append(
                    f"{column}: {sudden_changes} sudden changes detected"
                )
                anomalies.append({
                    "type": "sudden_change",
                    "column": column,
                    "count": sudden_changes
                })

        # Check for impossible combinations
        if "temperature_c" in df.columns and "humidity_pct" in df.columns:
            # Very high temperature with very high humidity is rare
            impossible = (
                (df["temperature_c"] > 40) & (df["humidity_pct"] > 90)
            ).sum()

            if impossible > 0:
                result.warnings.append(
                    f"Found {impossible} records with unusual temp/humidity combination"
                )

        result.metrics["anomalies"] = anomalies
        return result

    def validate_all(self, df: pd.DataFrame) -> ValidationResult:
        """Run all validations.

        Args:
            df: Input DataFrame

        Returns:
            Combined validation result
        """
        logger.info("Running comprehensive data validation...")

        results = [
            ("Timestamps", self.validate_timestamps(df)),
            ("Value Ranges", self.validate_value_ranges(df)),
            ("Missing Values", self.validate_missing_values(df)),
            ("Outliers", self.detect_outliers(df)),
            ("Anomalies", self.detect_anomalies(df)),
        ]

        # Combine results
        combined = ValidationResult(passed=True)

        for name, result in results:
            logger.info(f"  {name}: {'✓ PASS' if result.passed else '✗ FAIL'}")

            combined.passed = combined.passed and result.passed
            combined.errors.extend(result.errors)
            combined.warnings.extend(result.warnings)
            combined.metrics.update(result.metrics)

        logger.info(f"Overall validation: {'✓ PASS' if combined.passed else '✗ FAIL'}")
        logger.info(f"  Errors: {len(combined.errors)}")
        logger.info(f"  Warnings: {len(combined.warnings)}")

        return combined

    def generate_quality_report(self, df: pd.DataFrame) -> DataQualityReport:
        """Generate comprehensive data quality report.

        Args:
            df: Input DataFrame

        Returns:
            Data quality report
        """
        logger.info("Generating data quality report...")

        # Run validation
        validation = self.validate_all(df)

        # Calculate scores
        total_cells = len(df) * len(df.columns)
        missing_cells = df.isnull().sum().sum()
        completeness = 1.0 - (missing_cells / total_cells)

        # Validity score (based on range violations)
        validity = 1.0 if validation.passed else 0.8

        # Consistency score (based on anomalies)
        anomaly_count = len(validation.metrics.get("anomalies", []))
        consistency = max(0, 1.0 - (anomaly_count / 10))

        # Overall score
        overall = (completeness + validity + consistency) / 3

        report = DataQualityReport(
            timestamp=datetime.now(),
            total_records=len(df),
            date_range=(df["timestamp"].min(), df["timestamp"].max()),
            missing_timestamps=validation.metrics.get("missing_timestamps", 0),
            missing_values=validation.metrics.get("missing_values", {}),
            outliers=validation.metrics.get("outliers", {}),
            value_ranges={
                k: v for k, v in validation.metrics.items()
                if k.endswith("_range")
            },
            anomalies=validation.metrics.get("anomalies", []),
            completeness_score=completeness,
            validity_score=validity,
            consistency_score=consistency,
            overall_score=overall,
        )

        logger.info(f"Data Quality Scores:")
        logger.info(f"  Completeness: {completeness:.2%}")
        logger.info(f"  Validity: {validity:.2%}")
        logger.info(f"  Consistency: {consistency:.2%}")
        logger.info(f"  Overall: {overall:.2%}")

        return report

    def save_report(
        self,
        report: DataQualityReport,
        output_path: Path
    ) -> None:
        """Save quality report to file.

        Args:
            report: Data quality report
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create report content
        content = f"""SHAKTI-CHAIN Data Quality Report
{'=' * 60}

Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Dataset Overview
{'-' * 60}
Total Records: {report.total_records:,}
Date Range: {report.date_range[0]} to {report.date_range[1]}
Duration: {(report.date_range[1] - report.date_range[0]).days} days

Quality Scores
{'-' * 60}
Overall Quality: {report.overall_score:.2%} {'✓' if report.overall_score > 0.9 else '⚠'}
  - Completeness: {report.completeness_score:.2%}
  - Validity: {report.validity_score:.2%}
  - Consistency: {report.consistency_score:.2%}

Missing Data
{'-' * 60}
Missing Timestamps: {report.missing_timestamps:,}
Missing Values by Column:
"""

        for col, count in report.missing_values.items():
            pct = (count / report.total_records) * 100
            content += f"  - {col}: {count:,} ({pct:.2f}%)\n"

        content += f"""
Outliers Detected
{'-' * 60}
"""
        for col, count in report.outliers.items():
            pct = (count / report.total_records) * 100
            content += f"  - {col}: {count:,} ({pct:.2f}%)\n"

        content += f"""
Value Ranges
{'-' * 60}
"""
        for col, (min_val, max_val) in report.value_ranges.items():
            content += f"  - {col}: [{min_val:.2f}, {max_val:.2f}]\n"

        content += f"""
Anomalies
{'-' * 60}
Total anomalies detected: {len(report.anomalies)}
"""
        for anomaly in report.anomalies:
            content += f"  - {anomaly['type']} in {anomaly['column']}: {anomaly['count']} occurrences\n"

        content += f"""
{'=' * 60}
End of Report
"""

        # Write to file
        with open(output_path, "w") as f:
            f.write(content)

        logger.info(f"Quality report saved to {output_path}")
