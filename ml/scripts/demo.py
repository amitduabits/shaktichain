"""Demo script to showcase the ML platform."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors import (
    CalendarCollector,
    CalendarConfig,
    WeatherSimulator,
    WeatherConfig,
    LocationConfig,
)
from src.data.processors import DataPreprocessor, FeatureEngineer
from src.features import ParquetFeatureStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Run demo of the ML platform."""
    logger.info("=" * 60)
    logger.info("SHAKTI-CHAIN V2G ML Platform Demo")
    logger.info("=" * 60)
    logger.info("")

    # 1. Data Collection Demo
    logger.info("Step 1: Data Collection")
    logger.info("-" * 60)

    # Collect calendar data
    logger.info("Collecting calendar data...")
    calendar_config = CalendarConfig(country="IN", include_festivals=True)
    calendar_collector = CalendarCollector(calendar_config)

    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()

    calendar_data = calendar_collector.collect(start_date, end_date)
    logger.info(f"✓ Collected {len(calendar_data)} calendar records")

    # Collect weather data (simulated)
    logger.info("Collecting weather data...")
    weather_config = WeatherConfig(
        locations=[
            LocationConfig(name="Delhi", lat=28.6139, lon=77.2090),
            LocationConfig(name="Mumbai", lat=19.0760, lon=72.8777),
        ]
    )
    weather_simulator = WeatherSimulator(weather_config)
    weather_data = weather_simulator.collect(start_date, end_date)
    logger.info(f"✓ Collected {len(weather_data)} weather records")
    logger.info("")

    # 2. Data Preprocessing Demo
    logger.info("Step 2: Data Preprocessing")
    logger.info("-" * 60)

    # Merge data
    logger.info("Merging datasets...")
    merged_data = calendar_data.merge(weather_data, on="timestamp", how="left")
    logger.info(f"✓ Merged data shape: {merged_data.shape}")

    # Feature engineering
    logger.info("Engineering features...")
    feature_engineer = FeatureEngineer()
    merged_data = feature_engineer.create_all_features(merged_data)
    logger.info(f"✓ Feature engineering complete. Shape: {merged_data.shape}")

    # Preprocessing
    logger.info("Preprocessing data...")
    preprocessor = DataPreprocessor(
        missing_value_strategy="interpolate",
        outlier_detection=True,
        normalization="standard"
    )

    numeric_cols = merged_data.select_dtypes(include=["float64", "int64"]).columns.tolist()
    normalize_cols = [col for col in numeric_cols if col not in ["timestamp"]]

    processed_data = preprocessor.process(
        merged_data,
        fit=True,
        normalize_columns=normalize_cols[:5],  # Normalize first 5 numeric columns
    )
    logger.info(f"✓ Preprocessing complete. Shape: {processed_data.shape}")
    logger.info("")

    # 3. Feature Store Demo
    logger.info("Step 3: Feature Store")
    logger.info("-" * 60)

    # Initialize feature store
    logger.info("Initializing feature store...")
    feature_store = ParquetFeatureStore("data/features")

    # Save features
    logger.info("Saving features...")
    feature_store.save_features(processed_data, "demo_features")
    logger.info("✓ Features saved to feature store")

    # Load features
    logger.info("Loading features from store...")
    loaded_features = feature_store.load_features("demo_features")
    logger.info(f"✓ Loaded {len(loaded_features)} records from feature store")
    logger.info("")

    # 4. Summary
    logger.info("Step 4: Summary")
    logger.info("-" * 60)
    logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Total records: {len(processed_data)}")
    logger.info(f"Total features: {len(processed_data.columns)}")
    logger.info("")
    logger.info("Sample features:")
    for col in list(processed_data.columns)[:10]:
        logger.info(f"  - {col}")
    if len(processed_data.columns) > 10:
        logger.info(f"  ... and {len(processed_data.columns) - 10} more")
    logger.info("")

    logger.info("=" * 60)
    logger.info("Demo Complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Run 'python scripts/collect_data.py' for full data collection")
    logger.info("2. Run 'python scripts/preprocess_data.py' to preprocess all data")
    logger.info("3. Run 'python scripts/train.py' to train a forecasting model")
    logger.info("4. Run 'mlflow ui' to view experiment results")
    logger.info("")
    logger.info("See QUICKSTART.md for detailed instructions")


if __name__ == "__main__":
    main()
