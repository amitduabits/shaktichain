"""End-to-end data collection, preprocessing, and validation script."""

import logging
import sys
from datetime import datetime
from pathlib import Path

import hydra
import pandas as pd
from omegaconf import DictConfig

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors import (
    CalendarCollector,
    CalendarConfig,
    IEXCollector,
    IEXConfig,
    WeatherCollector,
    WeatherConfig,
    WeatherSimulator,
)
from src.data.collectors.synthetic_grid import SyntheticGridCollector, SyntheticGridConfig
from src.data.processors.advanced_preprocessor import AdvancedPreprocessor
from src.data.validators import DataValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def collect_all_data(cfg: DictConfig, start_date: datetime, end_date: datetime) -> dict:
    """Collect data from all sources.

    Args:
        cfg: Configuration
        start_date: Start date
        end_date: End date

    Returns:
        Dictionary of collected datasets
    """
    cache_dir = Path(cfg.paths.raw_data_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    collected_data = {}

    # 1. Collect Grid Load Data (Synthetic)
    logger.info("=" * 60)
    logger.info("Step 1: Collecting Grid Load Data")
    logger.info("=" * 60)

    try:
        grid_config = SyntheticGridConfig(
            enabled=True,
            cache_dir=cache_dir / "grid"
        )
        grid_collector = SyntheticGridCollector(grid_config)

        # Get holidays and festivals from calendar first
        calendar_config = CalendarConfig(
            country="IN",
            include_festivals=True,
            cache_dir=cache_dir / "calendar"
        )
        calendar_collector = CalendarCollector(calendar_config)
        calendar_data = calendar_collector.collect(start_date, end_date)

        # Extract holidays and festivals
        holidays = set(
            calendar_data[calendar_data["is_holiday"]]["timestamp"].dt.date
        )
        festivals = set(
            calendar_data[calendar_data["is_festival"]]["timestamp"].dt.date
        )

        # Collect grid data with holidays
        grid_data = grid_collector.collect(
            start_date,
            end_date,
            holidays=holidays,
            festivals=festivals
        )

        if grid_collector.validate(grid_data):
            collected_data["grid"] = grid_data
            logger.info(f"✓ Collected {len(grid_data)} grid load records")
        else:
            logger.error("✗ Grid data validation failed")

    except Exception as e:
        logger.error(f"✗ Error collecting grid data: {e}")

    # 2. Collect IEX Price Data
    logger.info("")
    logger.info("=" * 60)
    logger.info("Step 2: Collecting IEX Price Data")
    logger.info("=" * 60)

    if cfg.data.sources.iex.enabled:
        try:
            iex_config = IEXConfig(
                **cfg.data.sources.iex,
                cache_dir=cache_dir / "iex"
            )
            iex_collector = IEXCollector(iex_config)

            iex_data = iex_collector.collect(
                start_date,
                end_date,
                markets=cfg.data.sources.iex.markets,
            )

            if iex_collector.validate(iex_data):
                collected_data["iex"] = iex_data
                logger.info(f"✓ Collected {len(iex_data)} IEX price records")
            else:
                logger.error("✗ IEX data validation failed")

        except Exception as e:
            logger.error(f"✗ Error collecting IEX data: {e}")

    # 3. Collect Weather Data
    logger.info("")
    logger.info("=" * 60)
    logger.info("Step 3: Collecting Weather Data")
    logger.info("=" * 60)

    if cfg.data.sources.weather.enabled:
        try:
            weather_config = WeatherConfig(
                **cfg.data.sources.weather,
                cache_dir=cache_dir / "weather"
            )

            # Use simulator if no API key
            if weather_config.api_key:
                weather_collector = WeatherCollector(weather_config)
                logger.info("Using OpenWeatherMap API")
            else:
                weather_collector = WeatherSimulator(weather_config)
                logger.info("Using Weather Simulator (no API key)")

            weather_data = weather_collector.collect(start_date, end_date)

            if weather_collector.validate(weather_data):
                collected_data["weather"] = weather_data
                logger.info(f"✓ Collected {len(weather_data)} weather records")
            else:
                logger.error("✗ Weather data validation failed")

        except Exception as e:
            logger.error(f"✗ Error collecting weather data: {e}")

    # 4. Calendar data (already collected)
    if calendar_collector.validate(calendar_data):
        collected_data["calendar"] = calendar_data
        logger.info(f"✓ Using {len(calendar_data)} calendar records")

    return collected_data


def merge_datasets(data_dict: dict) -> pd.DataFrame:
    """Merge all collected datasets.

    Args:
        data_dict: Dictionary of datasets

    Returns:
        Merged DataFrame
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("Merging Datasets")
    logger.info("=" * 60)

    if not data_dict:
        logger.error("No data to merge!")
        return pd.DataFrame()

    # Start with calendar (has all timestamps)
    merged = data_dict.get("calendar")

    if merged is None:
        logger.error("Calendar data is required for merging")
        return pd.DataFrame()

    logger.info(f"Starting with calendar: {merged.shape}")

    # Merge grid data
    if "grid" in data_dict:
        grid_data = data_dict["grid"]
        # Pivot grid data by region
        grid_pivot = grid_data.pivot_table(
            index="timestamp",
            columns="region",
            values=["load_mw", "frequency_hz"]
        )
        grid_pivot.columns = [f"{col[0]}_{col[1].lower()}" for col in grid_pivot.columns]
        grid_pivot = grid_pivot.reset_index()

        merged = merged.merge(grid_pivot, on="timestamp", how="left")
        logger.info(f"After grid merge: {merged.shape}")

    # Merge IEX data
    if "iex" in data_dict:
        iex_data = data_dict["iex"]
        # Pivot by market
        iex_pivot = iex_data.pivot_table(
            index="timestamp",
            columns="market",
            values=["price_inr_mwh", "volume_mwh"]
        )
        iex_pivot.columns = [f"{col[0]}_{col[1].lower()}" for col in iex_pivot.columns]
        iex_pivot = iex_pivot.reset_index()

        merged = merged.merge(iex_pivot, on="timestamp", how="left")
        logger.info(f"After IEX merge: {merged.shape}")

    # Merge weather data
    if "weather" in data_dict:
        weather_data = data_dict["weather"]
        # Pivot by location
        weather_pivot = weather_data.pivot_table(
            index="timestamp",
            columns="location",
            values=["temperature_c", "humidity_pct", "wind_speed_ms", "cloudiness_pct"]
        )
        weather_pivot.columns = [f"{col[0]}_{col[1].lower()}" for col in weather_pivot.columns]
        weather_pivot = weather_pivot.reset_index()

        merged = merged.merge(weather_pivot, on="timestamp", how="left")
        logger.info(f"After weather merge: {merged.shape}")

    logger.info(f"Final merged shape: {merged.shape}")
    logger.info(f"Columns: {len(merged.columns)}")

    return merged


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """Main data collection, preprocessing, and validation pipeline.

    Args:
        cfg: Hydra configuration
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("SHAKTI-CHAIN Data Collection and Validation Pipeline")
    logger.info("=" * 70)
    logger.info("")

    # Parse dates
    start_date = datetime.strptime(cfg.data.collection.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(cfg.data.collection.end_date, "%Y-%m-%d")

    logger.info(f"Collection period: {start_date.date()} to {end_date.date()}")
    logger.info(f"Duration: {(end_date - start_date).days} days")
    logger.info("")

    # Step 1: Collect data
    collected_data = collect_all_data(cfg, start_date, end_date)

    if not collected_data:
        logger.error("No data collected. Exiting.")
        return

    # Step 2: Merge datasets
    merged_data = merge_datasets(collected_data)

    if merged_data.empty:
        logger.error("Merged data is empty. Exiting.")
        return

    # Save raw merged data
    raw_output_path = Path(cfg.paths.raw_data_dir) / "merged_data.parquet"
    merged_data.to_parquet(raw_output_path, index=False)
    logger.info(f"Saved raw merged data to {raw_output_path}")
    logger.info("")

    # Step 3: Validate raw data
    logger.info("=" * 60)
    logger.info("Step 4: Validating Raw Data")
    logger.info("=" * 60)

    validator = DataValidator(
        timezone="Asia/Kolkata",
        outlier_threshold=3.0,
        missing_threshold=0.05
    )

    validation_result = validator.validate_all(merged_data)

    if validation_result.errors:
        logger.error("Validation errors found:")
        for error in validation_result.errors:
            logger.error(f"  ✗ {error}")

    if validation_result.warnings:
        logger.warning("Validation warnings:")
        for warning in validation_result.warnings:
            logger.warning(f"  ⚠ {warning}")

    # Generate quality report
    logger.info("")
    logger.info("Generating data quality report...")
    quality_report = validator.generate_quality_report(merged_data)

    # Save report
    report_path = Path(cfg.paths.raw_data_dir) / "data_quality_report.txt"
    validator.save_report(quality_report, report_path)

    # Step 4: Preprocess data
    logger.info("")
    logger.info("=" * 60)
    logger.info("Step 5: Preprocessing Data")
    logger.info("=" * 60)

    preprocessor = AdvancedPreprocessor(
        timezone="Asia/Kolkata",
        interpolation_max_gap=3,
        outlier_method="sigma",
        outlier_threshold=3.0,
        capping_method="clip"
    )

    processed_data = preprocessor.process(
        merged_data,
        normalize_tz=True,
        resample=True,
        handle_missing=True,
        cap_outliers=True,
        add_flags=True
    )

    # Step 5: Validate processed data
    logger.info("")
    logger.info("=" * 60)
    logger.info("Step 6: Validating Processed Data")
    logger.info("=" * 60)

    processed_validation = validator.validate_all(processed_data)

    if processed_validation.passed:
        logger.info("✓ Processed data validation PASSED")
    else:
        logger.error("✗ Processed data validation FAILED")

    # Generate final quality report
    final_quality_report = validator.generate_quality_report(processed_data)

    # Save processed data
    processed_output_path = Path(cfg.paths.processed_data_dir) / "processed_data.parquet"
    processed_output_path.parent.mkdir(parents=True, exist_ok=True)
    processed_data.to_parquet(processed_output_path, index=False)
    logger.info(f"Saved processed data to {processed_output_path}")

    # Save final report
    final_report_path = Path(cfg.paths.processed_data_dir) / "final_quality_report.txt"
    validator.save_report(final_quality_report, final_report_path)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("Pipeline Complete!")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Summary:")
    logger.info(f"  Raw data records: {len(merged_data):,}")
    logger.info(f"  Processed data records: {len(processed_data):,}")
    logger.info(f"  Features: {len(processed_data.columns)}")
    logger.info("")
    logger.info("Quality Improvement:")
    logger.info(f"  Before: {quality_report.overall_score:.2%}")
    logger.info(f"  After:  {final_quality_report.overall_score:.2%}")
    logger.info(f"  Change: {(final_quality_report.overall_score - quality_report.overall_score):.2%}")
    logger.info("")
    logger.info("Output files:")
    logger.info(f"  Raw data: {raw_output_path}")
    logger.info(f"  Processed data: {processed_output_path}")
    logger.info(f"  Raw quality report: {report_path}")
    logger.info(f"  Final quality report: {final_report_path}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Review quality reports")
    logger.info("  2. Run feature engineering: python scripts/preprocess_data.py")
    logger.info("  3. Train model: python scripts/train.py")
    logger.info("")


if __name__ == "__main__":
    main()
