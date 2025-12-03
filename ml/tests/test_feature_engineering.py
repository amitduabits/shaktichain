"""Tests for feature engineering."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features import FeatureEngineering


class TestFeatureEngineering:
    """Tests for FeatureEngineering class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        dates = pd.date_range("2024-01-01", periods=200, freq="H")

        data = pd.DataFrame({
            "timestamp": dates,
            "load_mw_northern": np.random.normal(50000, 5000, len(dates)),
            "temperature_c_delhi": np.random.normal(25, 5, len(dates)),
            "humidity_pct_delhi": np.random.uniform(40, 80, len(dates)),
            "price_inr_mwh_dam": np.random.normal(3000, 500, len(dates)),
        })

        return data

    def test_initialization(self):
        """Test FeatureEngineering initialization."""
        fe = FeatureEngineering()
        assert fe is not None
        assert not fe.is_fitted

    def test_temporal_features(self, sample_data):
        """Test temporal feature creation."""
        fe = FeatureEngineering(
            include_temporal=True,
            include_lags=False,
            include_rolling=False,
            include_weather=False,
            include_derived=False,
            include_interactions=False,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Check temporal features exist
        assert "hour" in result.columns
        assert "day_of_week" in result.columns
        assert "month" in result.columns
        assert "is_weekend" in result.columns

        # Check cyclical encoding
        assert "hour_sin" in result.columns
        assert "hour_cos" in result.columns
        assert "day_of_week_sin" in result.columns
        assert "day_of_week_cos" in result.columns

        # Check values are valid
        assert result["hour"].between(0, 23).all()
        assert result["day_of_week"].between(0, 6).all()
        assert result["hour_sin"].between(-1, 1).all()
        assert result["hour_cos"].between(-1, 1).all()

    def test_lag_features(self, sample_data):
        """Test lag feature creation."""
        fe = FeatureEngineering(
            include_temporal=False,
            include_lags=True,
            lag_hours=[1, 2, 24],
            lag_columns=["load_mw_northern"],
            include_rolling=False,
            include_weather=False,
            include_derived=False,
            include_interactions=False,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Check lag features exist
        assert "load_mw_northern_lag_1h" in result.columns
        assert "load_mw_northern_lag_2h" in result.columns
        assert "load_mw_northern_lag_24h" in result.columns

        # Check lag values are correct (allowing for NaN in first rows)
        original_values = sample_data["load_mw_northern"].values
        lag_1h_values = result["load_mw_northern_lag_1h"].values

        # Compare non-NaN values
        valid_idx = ~np.isnan(lag_1h_values)
        assert np.allclose(
            original_values[:-1][valid_idx[1:]],
            lag_1h_values[1:][valid_idx[1:]]
        )

    def test_rolling_features(self, sample_data):
        """Test rolling statistics features."""
        fe = FeatureEngineering(
            include_temporal=False,
            include_lags=False,
            include_rolling=True,
            rolling_windows=[24],
            rolling_statistics=["mean", "std", "min", "max"],
            rolling_columns=["load_mw_northern"],
            include_weather=False,
            include_derived=False,
            include_interactions=False,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Check rolling features exist
        assert "load_mw_northern_rolling_mean_24h" in result.columns
        assert "load_mw_northern_rolling_std_24h" in result.columns
        assert "load_mw_northern_rolling_min_24h" in result.columns
        assert "load_mw_northern_rolling_max_24h" in result.columns

        # Check rolling mean is reasonable
        rolling_mean = result["load_mw_northern_rolling_mean_24h"].dropna()
        original_mean = sample_data["load_mw_northern"].mean()

        assert abs(rolling_mean.mean() - original_mean) < original_mean * 0.1

    def test_weather_features(self, sample_data):
        """Test weather-derived features."""
        fe = FeatureEngineering(
            include_temporal=False,
            include_lags=False,
            include_rolling=False,
            include_weather=True,
            include_derived=False,
            include_interactions=False,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Check weather features exist
        assert "hdd_delhi" in result.columns
        assert "cdd_delhi" in result.columns
        assert "apparent_temp_delhi" in result.columns
        assert "discomfort_delhi" in result.columns

        # Check HDD/CDD are non-negative
        assert (result["hdd_delhi"] >= 0).all()
        assert (result["cdd_delhi"] >= 0).all()

    def test_derived_features(self, sample_data):
        """Test derived features."""
        fe = FeatureEngineering(
            include_temporal=True,  # Need hour for peak detection
            include_lags=False,
            include_rolling=False,
            include_weather=False,
            include_derived=True,
            include_interactions=False,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Check derived features exist
        assert "load_mw_northern_diff_1h" in result.columns
        assert "load_mw_northern_pct_change_1h" in result.columns
        assert "is_peak_hour" in result.columns
        assert "is_shoulder_hour" in result.columns
        assert "is_offpeak_hour" in result.columns

        # Check peak hours are correctly identified
        peak_hours = result[result["is_peak_hour"] == 1]["hour"].unique()
        assert set(peak_hours).issubset(set(range(18, 23)))

    def test_interaction_features(self, sample_data):
        """Test interaction features."""
        fe = FeatureEngineering(
            include_temporal=True,
            include_lags=False,
            include_rolling=False,
            include_weather=False,
            include_derived=False,
            include_interactions=True,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Check interaction features exist
        interaction_cols = [col for col in result.columns if "interaction" in col]
        assert len(interaction_cols) > 0

        # Should have temperature-load interaction
        temp_load_interactions = [col for col in interaction_cols if "temp_load" in col]
        assert len(temp_load_interactions) > 0

    def test_fit_transform_workflow(self, sample_data):
        """Test fit/transform workflow."""
        fe = FeatureEngineering()

        # Fit
        fe.fit(sample_data)
        assert fe.is_fitted

        # Transform
        result = fe.transform(sample_data)
        assert len(result) > 0

        # Feature names available
        feature_names = fe.get_feature_names()
        assert len(feature_names) > 0

        # Statistics available
        stats = fe.get_feature_statistics()
        assert "n_features" in stats
        assert stats["n_features"] > 0

    def test_fit_transform_shortcut(self, sample_data):
        """Test fit_transform shortcut method."""
        fe = FeatureEngineering()

        result = fe.fit_transform(sample_data)

        assert fe.is_fitted
        assert len(result) > 0

    def test_transform_before_fit_raises_error(self, sample_data):
        """Test that transform before fit raises error."""
        fe = FeatureEngineering()

        with pytest.raises(ValueError, match="must be fitted"):
            fe.transform(sample_data)

    def test_save_and_load(self, sample_data):
        """Test saving and loading fitted FeatureEngineering."""
        fe = FeatureEngineering()
        fe.fit(sample_data)

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "feature_engineering.pkl"

            # Save
            fe.save(save_path)
            assert save_path.exists()

            # Load
            fe_loaded = FeatureEngineering.load(save_path)

            # Check state is preserved
            assert fe_loaded.is_fitted
            assert fe_loaded.get_feature_names() == fe.get_feature_names()
            assert fe_loaded.get_feature_statistics() == fe.get_feature_statistics()

            # Check transform produces same results
            result1 = fe.transform(sample_data)
            result2 = fe_loaded.transform(sample_data)

            pd.testing.assert_frame_equal(result1, result2)

    def test_scaling(self, sample_data):
        """Test feature scaling."""
        fe = FeatureEngineering(
            include_temporal=True,
            include_lags=True,
            lag_hours=[1, 2],
            include_rolling=False,
            include_weather=False,
            include_derived=False,
            include_interactions=False,
            scale_features=True
        )

        result = fe.fit_transform(sample_data)

        # Check that numerical features are scaled
        # (scaled features should have mean ≈ 0, std ≈ 1)
        load_col = "load_mw_northern_lag_1h"
        if load_col in result.columns:
            scaled_values = result[load_col].dropna()
            assert abs(scaled_values.mean()) < 0.5  # Close to 0
            assert abs(scaled_values.std() - 1.0) < 0.5  # Close to 1

    def test_comprehensive_feature_creation(self, sample_data):
        """Test comprehensive feature creation with all options."""
        fe = FeatureEngineering(
            include_temporal=True,
            include_lags=True,
            lag_hours=[1, 24],
            include_rolling=True,
            rolling_windows=[24],
            include_weather=True,
            include_derived=True,
            include_interactions=True,
            scale_features=False
        )

        result = fe.fit_transform(sample_data)

        # Should have created many features
        assert len(result.columns) > len(sample_data.columns)

        # Check statistics
        stats = fe.get_feature_statistics()
        assert stats["n_temporal"] > 0
        assert stats["n_lag"] > 0
        assert stats["n_rolling"] > 0
        assert stats["n_weather"] > 0
        assert stats["n_derived"] > 0
        assert stats["n_interaction"] > 0

    def test_handle_missing_columns_gracefully(self):
        """Test that missing columns are handled gracefully."""
        # Data without some expected columns
        data = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="H"),
            "some_value": np.random.random(100)
        })

        fe = FeatureEngineering()

        # Should not raise error, just warn
        result = fe.fit_transform(data)

        # Should still create some features (temporal)
        assert len(result.columns) > len(data.columns)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
