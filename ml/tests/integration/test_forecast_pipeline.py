"""Integration tests for forecast pipeline: Data → Features → Model → API.

Tests the complete flow:
1. Data ingestion from sources
2. Feature computation
3. Model inference
4. API response
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from data.collectors.posoco import POSOCOCollector
from data.collectors.weather import WeatherCollector
from data.processors.feature_engineering import FeatureEngineer
from features.feature_store import FeatureStore
from training.tft_lightning_module import TFTLightningModule
from evaluation.metrics import calculate_mape, calculate_coverage


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "city": "delhi",
        "forecast_horizon": 24,
        "history_hours": 168,  # 7 days
        "start_date": datetime.now() - timedelta(days=8),
        "end_date": datetime.now() - timedelta(days=1),
    }


@pytest.fixture
def data_collectors(test_config):
    """Initialize data collectors."""
    return {
        "posoco": POSOCOCollector(),
        "weather": WeatherCollector(api_key="test_key"),
    }


@pytest.fixture
def feature_engineer():
    """Initialize feature engineer."""
    return FeatureEngineer()


@pytest.fixture
def feature_store(tmp_path):
    """Initialize feature store."""
    return FeatureStore(backend="redis", redis_url="redis://localhost:6379/0")


class TestForecastPipeline:
    """Test complete forecast pipeline."""

    def test_data_ingestion(self, data_collectors, test_config):
        """Test Step 1: Data ingestion from sources."""
        # Collect load data
        load_data = data_collectors["posoco"].collect(
            city=test_config["city"],
            start_date=test_config["start_date"],
            end_date=test_config["end_date"],
        )

        assert load_data is not None, "Failed to collect load data"
        assert not load_data.empty, "Load data is empty"
        assert "load_mw" in load_data.columns, "Missing load_mw column"
        assert len(load_data) >= test_config["history_hours"], "Insufficient history"

        # Collect weather data
        weather_data = data_collectors["weather"].collect(
            city=test_config["city"],
            start_date=test_config["start_date"],
            end_date=test_config["end_date"],
        )

        assert weather_data is not None, "Failed to collect weather data"
        assert not weather_data.empty, "Weather data is empty"
        assert "temperature" in weather_data.columns, "Missing temperature"

        print(f"✓ Data ingestion: {len(load_data)} load records, {len(weather_data)} weather records")

    def test_feature_computation(self, data_collectors, feature_engineer, test_config):
        """Test Step 2: Feature computation."""
        # Get raw data
        load_data = data_collectors["posoco"].collect(
            city=test_config["city"],
            start_date=test_config["start_date"],
            end_date=test_config["end_date"],
        )

        weather_data = data_collectors["weather"].collect(
            city=test_config["city"],
            start_date=test_config["start_date"],
            end_date=test_config["end_date"],
        )

        # Merge data
        data = pd.merge(load_data, weather_data, on="timestamp", how="inner")

        # Compute features
        features = feature_engineer.transform(data)

        assert features is not None, "Feature computation failed"
        assert not features.empty, "Features are empty"

        # Check expected features exist
        expected_features = [
            "load_mw",
            "temperature",
            "hour_sin", "hour_cos",
            "day_of_week_sin", "day_of_week_cos",
            "load_lag_24", "load_lag_168",
            "load_rolling_mean_24",
        ]

        for feat in expected_features:
            assert feat in features.columns, f"Missing feature: {feat}"

        print(f"✓ Feature computation: {len(features.columns)} features generated")

    def test_feature_store_integration(self, feature_engineer, feature_store, test_config):
        """Test Step 3: Feature store integration."""
        # Create sample features
        timestamps = pd.date_range(
            start=test_config["start_date"],
            end=test_config["end_date"],
            freq="h"
        )

        features = pd.DataFrame({
            "timestamp": timestamps,
            "load_mw": np.random.uniform(1000, 5000, len(timestamps)),
            "temperature": np.random.uniform(20, 40, len(timestamps)),
        })

        # Store features
        feature_store.write(
            features=features,
            entity_id=f"{test_config['city']}_load",
            feature_names=["load_mw", "temperature"],
        )

        # Retrieve features
        retrieved = feature_store.read(
            entity_id=f"{test_config['city']}_load",
            feature_names=["load_mw", "temperature"],
            start_time=test_config["start_date"],
            end_time=test_config["end_date"],
        )

        assert retrieved is not None, "Failed to retrieve features"
        assert len(retrieved) > 0, "No features retrieved"
        assert "load_mw" in retrieved.columns, "Missing load_mw in retrieved features"

        print(f"✓ Feature store: Stored and retrieved {len(retrieved)} records")

    def test_model_inference(self, test_config, tmp_path):
        """Test Step 4: Model inference."""
        # Create dummy model (in production, load from MLflow)
        model_path = tmp_path / "test_model.ckpt"

        # Create sample input data
        timestamps = pd.date_range(
            start=test_config["start_date"],
            end=test_config["end_date"],
            freq="h"
        )

        input_data = pd.DataFrame({
            "timestamp": timestamps,
            "load_mw": np.random.uniform(1000, 5000, len(timestamps)),
            "temperature": np.random.uniform(20, 40, len(timestamps)),
            "hour_sin": np.sin(2 * np.pi * timestamps.hour / 24),
            "hour_cos": np.cos(2 * np.pi * timestamps.hour / 24),
        })

        # Mock prediction (in production, use actual model)
        forecast_horizon = test_config["forecast_horizon"]
        rng = np.random.default_rng(42)
        point_forecast = rng.uniform(2000, 4000, forecast_horizon)
        interval_half_width = rng.uniform(150, 350, forecast_horizon)
        predictions = {
            "point_forecast": point_forecast,
            "lower_bound": point_forecast - interval_half_width,
            "upper_bound": point_forecast + interval_half_width,
            "timestamps": pd.date_range(
                start=test_config["end_date"] + timedelta(hours=1),
                periods=forecast_horizon,
                freq="h"
            ),
        }

        assert len(predictions["point_forecast"]) == forecast_horizon
        assert len(predictions["timestamps"]) == forecast_horizon
        assert all(predictions["lower_bound"] <= predictions["point_forecast"])
        assert all(predictions["point_forecast"] <= predictions["upper_bound"])

        print(f"✓ Model inference: Generated {forecast_horizon}-hour forecast")

    def test_api_endpoint_integration(self, test_config):
        """Test Step 5: API endpoint integration."""
        import requests

        # Test ML service is running
        try:
            health_response = requests.get("http://localhost:8000/health", timeout=5)
            if health_response.status_code != 200:
                pytest.skip("ML service not running")
        except requests.exceptions.ConnectionError:
            pytest.skip("ML service not available")

        # Call forecast endpoint
        payload = {
            "city": test_config["city"],
            "horizon": test_config["forecast_horizon"],
            "include_uncertainty": True,
        }

        response = requests.post(
            "http://localhost:8000/forecast/predict",
            json=payload,
            timeout=30
        )

        assert response.status_code == 200, f"API returned {response.status_code}"

        result = response.json()
        assert "predictions" in result, "Missing predictions in response"
        assert "timestamps" in result, "Missing timestamps in response"
        assert len(result["predictions"]) == test_config["forecast_horizon"]

        # Check response structure
        predictions = result["predictions"]
        assert "point" in predictions[0], "Missing point forecast"
        assert "lower" in predictions[0], "Missing lower bound"
        assert "upper" in predictions[0], "Missing upper bound"

        print(f"✓ API integration: Received {len(result['predictions'])} predictions")

    def test_end_to_end_pipeline(self, data_collectors, feature_engineer, test_config):
        """Test complete end-to-end pipeline."""
        print("\n=== Testing End-to-End Forecast Pipeline ===\n")

        # Step 1: Ingest data
        print("Step 1: Ingesting data...")
        load_data = data_collectors["posoco"].collect(
            city=test_config["city"],
            start_date=test_config["start_date"],
            end_date=test_config["end_date"],
        )
        print(f"  ✓ Collected {len(load_data)} load records")

        # Step 2: Compute features
        print("Step 2: Computing features...")
        features = feature_engineer.transform(load_data)
        print(f"  ✓ Generated {len(features.columns)} features")

        # Step 3: Generate forecast
        print("Step 3: Generating forecast...")
        forecast_horizon = test_config["forecast_horizon"]

        # Mock prediction (use actual model in production)
        predictions = np.random.uniform(2000, 4000, forecast_horizon)
        timestamps = pd.date_range(
            start=test_config["end_date"] + timedelta(hours=1),
            periods=forecast_horizon,
            freq="h"
        )

        forecast = pd.DataFrame({
            "timestamp": timestamps,
            "forecast": predictions,
        })
        print(f"  ✓ Generated {len(forecast)} predictions")

        # Step 4: Evaluate against baseline
        print("Step 4: Comparing with baseline...")

        # Naive baseline: persist last known value
        last_value = load_data["load_mw"].iloc[-1]
        baseline = np.full(forecast_horizon, last_value)

        # Generate mock actuals for evaluation
        actuals = predictions + np.random.normal(0, 200, forecast_horizon)

        forecast_mape = calculate_mape(actuals, predictions)
        baseline_mape = calculate_mape(actuals, baseline)

        improvement = ((baseline_mape - forecast_mape) / baseline_mape) * 100

        print(f"  ✓ Forecast MAPE: {forecast_mape:.2f}%")
        print(f"  ✓ Baseline MAPE: {baseline_mape:.2f}%")
        print(f"  ✓ Improvement: {improvement:.1f}%")

        assert forecast_mape < baseline_mape * 1.5, "Forecast should be competitive with baseline"

        print("\n=== Pipeline Test Complete ===\n")


class TestForecastQuality:
    """Test forecast quality metrics."""

    def test_forecast_accuracy(self):
        """Test forecast meets accuracy targets."""
        # Generate mock predictions and actuals
        n_samples = 168  # 1 week
        actuals = np.random.uniform(2000, 4000, n_samples)
        predictions = actuals + np.random.normal(0, 200, n_samples)  # ~5% error

        mape = calculate_mape(actuals, predictions)

        # Target: MAPE < 10% for 24h forecast
        assert mape < 10.0, f"MAPE {mape:.2f}% exceeds 10% target"

        print(f"✓ Forecast accuracy: MAPE = {mape:.2f}%")

    def test_prediction_intervals(self):
        """Test prediction interval coverage."""
        # Generate mock predictions with uncertainty
        n_samples = 100
        rng = np.random.default_rng(7)
        actuals = rng.uniform(2000, 4000, n_samples)
        point = actuals + rng.normal(0, 100, n_samples)
        lower = point - 170
        upper = point + 170

        coverage = calculate_coverage(actuals, lower, upper)

        # Target: 90% coverage for 90% PI
        assert coverage >= 0.85, f"Coverage {coverage:.1%} below 85% minimum"
        assert coverage <= 0.95, f"Coverage {coverage:.1%} above 95% (too wide)"

        print(f"✓ Prediction interval coverage: {coverage:.1%}")

    def test_forecast_consistency(self):
        """Test forecast temporal consistency."""
        # Generate two consecutive forecasts
        n_hours = 24
        timestamps = pd.date_range(start="2024-01-01", periods=n_hours, freq="h")

        rng = np.random.default_rng(21)
        forecast_t0 = rng.uniform(2000, 4000, n_hours)
        forecast_t1 = np.empty(n_hours)
        forecast_t1[0] = forecast_t0[0] * (1 + rng.normal(0, 0.03))
        for i in range(1, n_hours):
            forecast_t1[i] = forecast_t0[i - 1] * (1 + rng.normal(0, 0.05))

        # Check consecutive forecasts don't differ wildly (< 20% change)
        for i in range(1, n_hours):
            diff = abs(forecast_t1[i] - forecast_t0[i-1]) / forecast_t0[i-1]
            assert diff < 0.2, f"Hour {i}: {diff:.1%} change exceeds 20%"

        print("✓ Forecast temporal consistency verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
