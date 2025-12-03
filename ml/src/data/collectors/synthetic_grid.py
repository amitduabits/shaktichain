"""Synthetic grid load data generator based on Indian power system patterns.

Generates realistic hourly load data for Indian regional grids based on:
- Daily patterns (peak hours, off-peak)
- Weekly patterns (weekday vs weekend)
- Seasonal variations
- Regional differences
- Special events (holidays, festivals)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel

from .base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class SyntheticGridConfig(CollectorConfig):
    """Configuration for synthetic grid data generator."""

    regions: List[str] = ["NORTHERN", "WESTERN", "SOUTHERN", "EASTERN", "NORTH_EASTERN"]
    base_loads: Dict[str, float] = {
        "NORTHERN": 50000,  # MW
        "WESTERN": 45000,
        "SOUTHERN": 40000,
        "EASTERN": 30000,
        "NORTH_EASTERN": 8000,
    }
    noise_level: float = 0.05  # 5% random noise


class SyntheticGridCollector(BaseCollector):
    """Generates synthetic grid load data based on realistic patterns."""

    def __init__(self, config: SyntheticGridConfig):
        """Initialize synthetic grid collector.

        Args:
            config: Configuration for synthetic data generation
        """
        super().__init__(config)
        self.config: SyntheticGridConfig = config

        # Set random seed for reproducibility
        np.random.seed(42)

    def _get_base_load(self, region: str) -> float:
        """Get base load for a region.

        Args:
            region: Region name

        Returns:
            Base load in MW
        """
        return self.config.base_loads.get(region, 40000)

    def _calculate_hourly_factor(self, hour: int) -> float:
        """Calculate hourly demand factor.

        Peak hours in India:
        - Morning peak: 6 AM - 10 AM
        - Evening peak: 6 PM - 11 PM
        - Night valley: 11 PM - 5 AM

        Args:
            hour: Hour of day (0-23)

        Returns:
            Demand factor (0.6 to 1.2)
        """
        if hour in range(6, 11):  # Morning peak
            return 1.0 + 0.15 * np.sin((hour - 6) * np.pi / 4)
        elif hour in range(11, 18):  # Afternoon
            return 0.95
        elif hour in range(18, 23):  # Evening peak
            return 1.1 + 0.1 * np.sin((hour - 18) * np.pi / 5)
        else:  # Night valley
            return 0.65 + 0.05 * np.random.random()

    def _calculate_day_factor(self, day_of_week: int) -> float:
        """Calculate daily demand factor.

        Weekdays have higher demand than weekends.

        Args:
            day_of_week: Day of week (0=Monday, 6=Sunday)

        Returns:
            Day factor (0.85 to 1.0)
        """
        if day_of_week < 5:  # Weekday
            return 1.0
        elif day_of_week == 5:  # Saturday
            return 0.90
        else:  # Sunday
            return 0.85

    def _calculate_seasonal_factor(self, month: int, day: int) -> float:
        """Calculate seasonal demand factor.

        Indian seasons:
        - Summer (Mar-Jun): High AC load
        - Monsoon (Jul-Sep): Moderate load
        - Winter (Oct-Feb): High heating load in north

        Args:
            month: Month (1-12)
            day: Day of year (1-365)

        Returns:
            Seasonal factor (0.9 to 1.2)
        """
        # Create sinusoidal pattern with peaks in summer and winter
        seasonal_value = 1.0 + 0.15 * np.sin((day - 80) * 2 * np.pi / 365)

        # Additional summer boost (March-June)
        if month in [3, 4, 5, 6]:
            seasonal_value += 0.1

        return np.clip(seasonal_value, 0.9, 1.2)

    def _calculate_special_day_factor(
        self,
        timestamp: datetime,
        is_holiday: bool = False,
        is_festival: bool = False
    ) -> float:
        """Calculate factor for special days.

        Args:
            timestamp: Current timestamp
            is_holiday: Whether it's a holiday
            is_festival: Whether it's a festival

        Returns:
            Special day factor
        """
        if is_festival:
            # Festivals like Diwali have high evening demand due to lighting
            if timestamp.hour in range(18, 23):
                return 1.15
            return 0.95

        if is_holiday:
            return 0.90

        return 1.0

    def _generate_hourly_load(
        self,
        timestamp: datetime,
        region: str,
        is_holiday: bool = False,
        is_festival: bool = False,
    ) -> float:
        """Generate load for a specific hour.

        Args:
            timestamp: Timestamp for generation
            region: Region name
            is_holiday: Whether it's a holiday
            is_festival: Whether it's a festival

        Returns:
            Load in MW
        """
        # Base load for region
        base_load = self._get_base_load(region)

        # Calculate factors
        hourly_factor = self._calculate_hourly_factor(timestamp.hour)
        day_factor = self._calculate_day_factor(timestamp.weekday())
        seasonal_factor = self._calculate_seasonal_factor(
            timestamp.month,
            timestamp.timetuple().tm_yday
        )
        special_factor = self._calculate_special_day_factor(
            timestamp, is_holiday, is_festival
        )

        # Calculate load
        load = (
            base_load
            * hourly_factor
            * day_factor
            * seasonal_factor
            * special_factor
        )

        # Add random noise
        noise = np.random.normal(1.0, self.config.noise_level)
        load *= noise

        # Add some autocorrelation (load changes gradually)
        # This is simplified - in production you'd want proper ARIMA

        return max(load, base_load * 0.5)  # Minimum 50% of base load

    def _generate_frequency(self, load: float, base_load: float) -> float:
        """Generate grid frequency based on load.

        Indian grid nominal frequency: 50 Hz
        Operating range: 49.5 - 50.5 Hz

        Args:
            load: Current load in MW
            base_load: Base load in MW

        Returns:
            Frequency in Hz
        """
        # Frequency drops when load is high
        load_ratio = load / base_load

        if load_ratio > 1.1:  # Overload
            frequency = 49.7 + np.random.normal(0, 0.1)
        elif load_ratio < 0.8:  # Underload
            frequency = 50.3 + np.random.normal(0, 0.1)
        else:  # Normal
            frequency = 50.0 + np.random.normal(0, 0.05)

        return np.clip(frequency, 49.5, 50.5)

    def collect(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any
    ) -> pd.DataFrame:
        """Generate synthetic grid load data.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters (regions, holidays, festivals)

        Returns:
            DataFrame with synthetic load data
        """
        regions = kwargs.get("regions", self.config.regions)
        holidays = kwargs.get("holidays", set())
        festivals = kwargs.get("festivals", set())

        logger.info(f"Generating synthetic grid data from {start_date} to {end_date}")

        # Check cache
        cache_key = self.get_cache_key(start_date, end_date, regions=str(regions))
        cached_data = self.load_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Loading synthetic data from cache: {cache_key}")
            return cached_data

        all_data = []
        current_time = start_date

        # Generate hourly data
        while current_time <= end_date:
            date_only = current_time.date()
            is_holiday = date_only in holidays
            is_festival = date_only in festivals

            for region in regions:
                # Generate load
                load = self._generate_hourly_load(
                    current_time,
                    region,
                    is_holiday,
                    is_festival
                )

                # Generate frequency
                base_load = self._get_base_load(region)
                frequency = self._generate_frequency(load, base_load)

                all_data.append({
                    "timestamp": current_time,
                    "region": region,
                    "load_mw": round(load, 2),
                    "frequency_hz": round(frequency, 3),
                    "is_holiday": is_holiday,
                    "is_festival": is_festival,
                })

            current_time += timedelta(hours=1)

        df = pd.DataFrame(all_data)

        # Save to cache
        self.save_cache(df, cache_key)

        logger.info(f"Generated {len(df)} synthetic records")
        return df

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate synthetic data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        required_columns = ["timestamp", "region", "load_mw", "frequency_hz"]

        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required columns")
            return False

        if data.empty:
            logger.error("Data is empty")
            return False

        # Check load is positive
        if (data["load_mw"] <= 0).any():
            logger.error("Found non-positive load values")
            return False

        # Check frequency is in valid range
        if not data["frequency_hz"].between(49.0, 51.0).all():
            logger.error("Frequency values out of range")
            return False

        # Check for reasonable load values (not too high or low)
        for region in data["region"].unique():
            region_data = data[data["region"] == region]
            base_load = self._get_base_load(region)

            if (region_data["load_mw"] < base_load * 0.4).any():
                logger.warning(f"Very low load values found for {region}")

            if (region_data["load_mw"] > base_load * 1.5).any():
                logger.warning(f"Very high load values found for {region}")

        logger.info("Synthetic data validation passed")
        return True
