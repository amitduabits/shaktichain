"""Script to collect data from all sources."""

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
    POSOCOCollector,
    POSOCOConfig,
    WeatherCollector,
    WeatherConfig,
    WeatherSimulator,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """Collect data from all sources.

    Args:
        cfg: Hydra configuration
    """
    logger.info("Starting data collection...")

    # Parse dates
    start_date = datetime.strptime(cfg.data.collection.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(cfg.data.collection.end_date, "%Y-%m-%d")

    logger.info(f"Collection period: {start_date} to {end_date}")

    # Prepare cache directory
    cache_dir = Path(cfg.paths.raw_data_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    all_data = {}

    # Collect POSOCO data
    if cfg.data.sources.posoco.enabled:
        try:
            logger.info("Collecting POSOCO data...")
            posoco_config = POSOCOConfig(
                **cfg.data.sources.posoco,
                cache_dir=cache_dir / "posoco"
            )
            posoco_collector = POSOCOCollector(posoco_config)

            posoco_data = posoco_collector.collect(
                start_date,
                end_date,
                regions=cfg.data.sources.posoco.regions,
            )

            if posoco_collector.validate(posoco_data):
                all_data["posoco"] = posoco_data
                logger.info(f"Collected {len(posoco_data)} POSOCO records")
            else:
                logger.error("POSOCO data validation failed")

        except Exception as e:
            logger.error(f"Error collecting POSOCO data: {e}")

    # Collect IEX data
    if cfg.data.sources.iex.enabled:
        try:
            logger.info("Collecting IEX data...")
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
                all_data["iex"] = iex_data
                logger.info(f"Collected {len(iex_data)} IEX records")
            else:
                logger.error("IEX data validation failed")

        except Exception as e:
            logger.error(f"Error collecting IEX data: {e}")

    # Collect Weather data
    if cfg.data.sources.weather.enabled:
        try:
            logger.info("Collecting Weather data...")
            weather_config = WeatherConfig(
                **cfg.data.sources.weather,
                cache_dir=cache_dir / "weather"
            )

            # Use simulator if no API key
            if weather_config.api_key:
                weather_collector = WeatherCollector(weather_config)
            else:
                logger.info("No API key found, using weather simulator")
                weather_collector = WeatherSimulator(weather_config)

            weather_data = weather_collector.collect(start_date, end_date)

            if weather_collector.validate(weather_data):
                all_data["weather"] = weather_data
                logger.info(f"Collected {len(weather_data)} weather records")
            else:
                logger.error("Weather data validation failed")

        except Exception as e:
            logger.error(f"Error collecting weather data: {e}")

    # Collect Calendar data
    if cfg.data.sources.calendar.enabled:
        try:
            logger.info("Collecting Calendar data...")
            calendar_config = CalendarConfig(
                **cfg.data.sources.calendar,
                cache_dir=cache_dir / "calendar"
            )
            calendar_collector = CalendarCollector(calendar_config)

            calendar_data = calendar_collector.collect(start_date, end_date)

            if calendar_collector.validate(calendar_data):
                all_data["calendar"] = calendar_data
                logger.info(f"Collected {len(calendar_data)} calendar records")
            else:
                logger.error("Calendar data validation failed")

        except Exception as e:
            logger.error(f"Error collecting calendar data: {e}")

    # Merge all data
    if not all_data:
        logger.error("No data collected!")
        return

    logger.info("Merging datasets...")

    # Start with calendar data (has all timestamps)
    merged_data = all_data.get("calendar")

    if merged_data is None:
        logger.error("Calendar data is required for merging")
        return

    # Merge other datasets
    for name, data in all_data.items():
        if name == "calendar":
            continue

        logger.info(f"Merging {name} data...")
        merged_data = merged_data.merge(
            data, on="timestamp", how="left", suffixes=("", f"_{name}")
        )

    # Save merged data
    output_path = Path(cfg.paths.raw_data_dir) / "merged_data.parquet"
    merged_data.to_parquet(output_path, index=False)

    logger.info(f"Saved merged data to {output_path}")
    logger.info(f"Total records: {len(merged_data)}")
    logger.info(f"Columns: {list(merged_data.columns)}")
    logger.info("Data collection complete!")


if __name__ == "__main__":
    main()
