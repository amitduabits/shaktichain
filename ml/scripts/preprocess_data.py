"""Script to preprocess and engineer features."""

import logging
import sys
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.processors import DataPreprocessor, FeatureEngineer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """Preprocess data and engineer features.

    Args:
        cfg: Hydra configuration
    """
    logger.info("Starting data preprocessing...")

    # Load raw data
    input_path = Path(cfg.paths.raw_data_dir) / "merged_data.parquet"

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        logger.error("Please run collect_data.py first")
        return

    logger.info(f"Loading data from {input_path}")
    data = pd.read_parquet(input_path)
    logger.info(f"Loaded {len(data)} records with {len(data.columns)} columns")

    # Initialize processors
    preprocessor = DataPreprocessor(
        missing_value_strategy=cfg.data.processing.missing_value_strategy,
        outlier_detection=cfg.data.processing.outlier_detection,
        outlier_threshold=cfg.data.processing.outlier_threshold,
        normalization=cfg.data.processing.normalization,
    )

    feature_engineer = FeatureEngineer()

    # Feature engineering
    logger.info("Engineering features...")

    if cfg.data.features.temporal_features.enabled:
        data = feature_engineer.create_temporal_features(data)

    if cfg.data.features.cyclical_encoding.enabled:
        cyclical_features = cfg.data.features.cyclical_encoding.features
        data = feature_engineer.create_cyclical_features(data, cyclical_features)

    data = feature_engineer.create_demand_features(data)
    data = feature_engineer.create_weather_features(data)
    data = feature_engineer.create_price_features(data)

    # Preprocessing
    logger.info("Preprocessing data...")

    # Define columns for lag and rolling features
    target_cols = ["load_mw", "price_inr_mwh"]
    numeric_cols = data.select_dtypes(include=["float64", "int64"]).columns.tolist()
    normalize_cols = [col for col in numeric_cols if col not in ["timestamp"]]

    # Configure lag features
    lag_config = None
    if cfg.data.features.lag_features.enabled:
        lag_config = {
            "columns": target_cols,
            "lags": cfg.data.features.lag_features.lags,
        }

    # Configure rolling features
    rolling_config = None
    if cfg.data.features.rolling_features.enabled:
        rolling_config = {
            "columns": target_cols,
            "windows": cfg.data.features.rolling_features.windows,
            "statistics": cfg.data.features.rolling_features.statistics,
        }

    # Process data
    data = preprocessor.process(
        data,
        fit=True,
        normalize_columns=normalize_cols,
        lag_config=lag_config,
        rolling_config=rolling_config,
    )

    # Save processed data
    output_path = Path(cfg.paths.processed_data_dir) / "processed_data.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data.to_parquet(output_path, index=False)

    logger.info(f"Saved processed data to {output_path}")
    logger.info(f"Final shape: {data.shape}")
    logger.info(f"Columns: {list(data.columns)}")
    logger.info("Preprocessing complete!")


if __name__ == "__main__":
    main()
