"""Tests for data collection and preprocessing pipeline."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors.synthetic_grid import SyntheticGridCollector, SyntheticGridConfig
from src.data.processors.advanced_preprocessor import AdvancedPreprocessor
from src.data.validators import DataValidator


class TestSyntheticGridCollector:
    """Tests for synthetic grid data collector."""

    def test_initialization(self):
        """Test collector initialization."""
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)
        assert collector is not None

    def test_data_generation(self):
        """Test synthetic data generation."""
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 7)

        data = collector.collect(start_date, end_date)

        assert len(data) > 0
        assert "timestamp" in data.columns
        assert "region" in data.columns
        assert "load_mw" in data.columns
        assert "frequency_hz" in data.columns

    def test_hourly_patterns(self):
        """Test that hourly patterns are realistic."""
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)

        data = collector.collect(start_date, end_date)

        # Morning peak should be higher than night valley
        morning_peak = data[data["timestamp"].dt.hour == 9]["load_mw"].mean()
        night_valley = data[data["timestamp"].dt.hour == 2]["load_mw"].mean()

        assert morning_peak > night_valley

    def test_validation(self):
        """Test data validation."""
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        data = collector.collect(start_date, end_date)

        assert collector.validate(data) is True

    def test_frequency_range(self):
        """Test that frequency is within valid range."""
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 7)

        data = collector.collect(start_date, end_date)

        assert data["frequency_hz"].between(49.5, 50.5).all()


class TestDataValidator:
    """Tests for data validator."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        dates = pd.date_range("2024-01-01", "2024-01-07", freq="H")
        data = pd.DataFrame({
            "timestamp": dates,
            "load_mw": np.random.normal(50000, 5000, len(dates)),
            "temperature_c": np.random.normal(25, 5, len(dates)),
            "humidity_pct": np.random.uniform(40, 80, len(dates)),
            "frequency_hz": np.random.normal(50.0, 0.1, len(dates)),
        })
        return data

    def test_initialization(self):
        """Test validator initialization."""
        validator = DataValidator()
        assert validator is not None

    def test_timestamp_validation(self, sample_data):
        """Test timestamp validation."""
        validator = DataValidator()
        result = validator.validate_timestamps(sample_data)

        assert result is not None
        assert result.passed is True

    def test_value_range_validation(self, sample_data):
        """Test value range validation."""
        validator = DataValidator()
        result = validator.validate_value_ranges(sample_data)

        assert result is not None
        # Should pass with normal data
        assert result.passed is True

    def test_outlier_detection(self, sample_data):
        """Test outlier detection."""
        # Add some outliers
        data_with_outliers = sample_data.copy()
        data_with_outliers.loc[10, "load_mw"] = 200000  # Extreme value

        validator = DataValidator()
        result = validator.detect_outliers(data_with_outliers)

        assert result is not None
        assert "load_mw" in result.metrics.get("outliers", {})

    def test_missing_value_detection(self, sample_data):
        """Test missing value detection."""
        # Add missing values
        data_with_missing = sample_data.copy()
        data_with_missing.loc[5:10, "load_mw"] = np.nan

        validator = DataValidator()
        result = validator.validate_missing_values(data_with_missing)

        assert result is not None
        assert "load_mw" in result.metrics.get("missing_values", {})

    def test_quality_report_generation(self, sample_data):
        """Test quality report generation."""
        validator = DataValidator()
        report = validator.generate_quality_report(sample_data)

        assert report is not None
        assert report.total_records == len(sample_data)
        assert 0 <= report.completeness_score <= 1
        assert 0 <= report.validity_score <= 1
        assert 0 <= report.overall_score <= 1


class TestAdvancedPreprocessor:
    """Tests for advanced preprocessor."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        dates = pd.date_range("2024-01-01", "2024-01-07", freq="H")
        data = pd.DataFrame({
            "timestamp": dates,
            "load_mw": np.random.normal(50000, 5000, len(dates)),
            "temperature_c": np.random.normal(25, 5, len(dates)),
        })
        return data

    def test_initialization(self):
        """Test preprocessor initialization."""
        preprocessor = AdvancedPreprocessor()
        assert preprocessor is not None

    def test_timezone_normalization(self, sample_data):
        """Test timezone normalization."""
        preprocessor = AdvancedPreprocessor(timezone="Asia/Kolkata")
        result = preprocessor.normalize_timezone(sample_data)

        assert result is not None
        assert pd.api.types.is_datetime64_any_dtype(result["timestamp"])

    def test_missing_value_handling(self, sample_data):
        """Test missing value handling."""
        # Add some missing values
        data_with_missing = sample_data.copy()
        data_with_missing.loc[5:7, "load_mw"] = np.nan  # 3-hour gap

        preprocessor = AdvancedPreprocessor(interpolation_max_gap=3)
        result = preprocessor.handle_missing_values_smart(data_with_missing)

        assert result is not None
        # Should have interpolated the small gap
        assert result["load_mw"].isnull().sum() == 0

    def test_outlier_capping(self, sample_data):
        """Test outlier capping."""
        # Add outliers
        data_with_outliers = sample_data.copy()
        data_with_outliers.loc[10, "load_mw"] = 200000  # Extreme value

        preprocessor = AdvancedPreprocessor(
            outlier_method="sigma",
            outlier_threshold=3.0
        )
        result = preprocessor.detect_and_cap_outliers(data_with_outliers)

        assert result is not None
        # Outlier should be capped
        assert result["load_mw"].max() < 200000

    def test_full_pipeline(self, sample_data):
        """Test full preprocessing pipeline."""
        preprocessor = AdvancedPreprocessor()
        result = preprocessor.process(sample_data)

        assert result is not None
        assert len(result) > 0
        # Should have added quality flags
        assert "is_weekend" in result.columns
        assert "is_peak_hour" in result.columns


class TestEndToEndPipeline:
    """Integration tests for end-to-end pipeline."""

    def test_collect_and_validate(self):
        """Test full collection and validation pipeline."""
        # Collect synthetic data
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 7)

        data = collector.collect(start_date, end_date)

        # Validate
        validator = DataValidator()
        validation = validator.validate_all(data)

        assert validation.passed is True

        # Generate report
        report = validator.generate_quality_report(data)

        assert report.overall_score > 0.8  # Should be high quality

    def test_collect_preprocess_validate(self):
        """Test collection, preprocessing, and validation."""
        # Collect data
        config = SyntheticGridConfig()
        collector = SyntheticGridCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        data = collector.collect(start_date, end_date)

        # Preprocess
        preprocessor = AdvancedPreprocessor()
        processed = preprocessor.process(data)

        # Validate
        validator = DataValidator()
        validation = validator.validate_all(processed)

        # Should still be valid after preprocessing
        assert len(processed) > 0
        assert processed["load_mw"].notnull().all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
