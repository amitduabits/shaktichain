"""Calendar data collector for holidays and festivals.

Provides information about Indian holidays, festivals, and special events.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import holidays
import pandas as pd
from pydantic import BaseModel, Field

from .base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class CalendarConfig(CollectorConfig):
    """Configuration for Calendar collector."""

    country: str = "IN"
    include_festivals: bool = True
    custom_holidays: List[Dict[str, str]] = Field(default_factory=list)


class CalendarCollector(BaseCollector):
    """Collector for calendar data including holidays and festivals."""

    # Major Indian festivals (approximate dates, as many are based on lunar calendar)
    INDIAN_FESTIVALS = {
        "Makar Sankranti": [(1, 14)],
        "Republic Day": [(1, 26)],
        "Maha Shivaratri": [(2, 18), (3, 8)],  # Varies by lunar calendar
        "Holi": [(3, 8), (3, 25)],  # Varies
        "Ugadi": [(3, 22), (4, 9)],  # Varies
        "Ram Navami": [(3, 30), (4, 17)],  # Varies
        "Mahavir Jayanti": [(4, 4), (4, 21)],  # Varies
        "Good Friday": [(3, 29), (4, 15)],  # Varies
        "Eid ul-Fitr": [(4, 21), (5, 2)],  # Varies (Islamic calendar)
        "Buddha Purnima": [(5, 5), (5, 23)],  # Varies
        "Eid ul-Adha": [(6, 28), (7, 9)],  # Varies (Islamic calendar)
        "Independence Day": [(8, 15)],
        "Janmashtami": [(8, 18), (9, 6)],  # Varies
        "Ganesh Chaturthi": [(8, 31), (9, 19)],  # Varies
        "Onam": [(8, 20), (9, 8)],  # Varies
        "Dussehra": [(10, 12), (10, 24)],  # Varies
        "Diwali": [(10, 24), (11, 12)],  # Varies
        "Guru Nanak Jayanti": [(11, 8), (11, 27)],  # Varies
        "Christmas": [(12, 25)],
    }

    def __init__(self, config: CalendarConfig):
        """Initialize Calendar collector.

        Args:
            config: Calendar collector configuration
        """
        super().__init__(config)
        self.config: CalendarConfig = config

        # Initialize holidays object for India
        self.holidays = holidays.India(years=range(2020, 2030))

        # Add custom holidays
        for custom in config.custom_holidays:
            date_str = custom.get("date")
            name = custom.get("name")
            if date_str and name:
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    self.holidays.append({date: name})
                except ValueError:
                    logger.warning(f"Invalid custom holiday date: {date_str}")

    def _is_festival(self, date: datetime) -> tuple[bool, Optional[str]]:
        """Check if a date is a festival.

        Args:
            date: Date to check

        Returns:
            Tuple of (is_festival, festival_name)
        """
        month_day = (date.month, date.day)

        for festival_name, dates in self.INDIAN_FESTIVALS.items():
            if month_day in dates:
                return True, festival_name

        return False, None

    def _get_season(self, date: datetime) -> str:
        """Get season for a date.

        Args:
            date: Date to check

        Returns:
            Season name
        """
        month = date.month

        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8, 9]:
            return "monsoon"
        else:  # 10, 11
            return "autumn"

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect calendar data for date range.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            DataFrame with calendar features
        """
        # Check cache first
        cache_key = self.get_cache_key(start_date, end_date)
        cached_data = self.load_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Loading calendar data from cache: {cache_key}")
            return cached_data

        # Generate hourly timestamps
        timestamps = pd.date_range(start=start_date, end=end_date, freq="h")

        data = []
        for ts in timestamps:
            date = ts.date()

            # Check if it's a holiday
            is_holiday = date in self.holidays
            holiday_name = self.holidays.get(date) if is_holiday else None

            # Check if it's a festival
            is_festival, festival_name = (
                self._is_festival(ts) if self.config.include_festivals else (False, None)
            )

            # Get season
            season = self._get_season(ts)

            # Calculate various temporal features
            data.append(
                {
                    "timestamp": ts,
                    "year": ts.year,
                    "month": ts.month,
                    "day": ts.day,
                    "hour": ts.hour,
                    "day_of_week": ts.dayofweek,  # Monday=0, Sunday=6
                    "day_of_year": ts.dayofyear,
                    "week_of_year": ts.isocalendar()[1],
                    "quarter": ts.quarter,
                    "is_weekend": ts.dayofweek >= 5,
                    "is_holiday": is_holiday,
                    "holiday_name": holiday_name,
                    "is_festival": is_festival,
                    "festival_name": festival_name,
                    "season": season,
                    "is_month_start": ts.is_month_start,
                    "is_month_end": ts.is_month_end,
                    "is_quarter_start": ts.is_quarter_start,
                    "is_quarter_end": ts.is_quarter_end,
                    "is_year_start": ts.is_year_start,
                    "is_year_end": ts.is_year_end,
                }
            )

        df = pd.DataFrame(data)

        # Add cyclical encodings for hour, day_of_week, month
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["day_of_week_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["day_of_week_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

        # Save to cache
        self.save_cache(df, cache_key)
        logger.info(f"Collected {len(df)} calendar records")

        return df

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate calendar data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        required_columns = [
            "timestamp",
            "hour",
            "day_of_week",
            "is_weekend",
            "is_holiday",
            "is_festival",
        ]

        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required columns in calendar data")
            return False

        if data.empty:
            logger.error("Calendar data is empty")
            return False

        # Check hour is 0-23
        if not data["hour"].between(0, 23).all():
            logger.error("Hour values out of valid range")
            return False

        # Check day_of_week is 0-6
        if not data["day_of_week"].between(0, 6).all():
            logger.error("Day of week values out of valid range")
            return False

        return True


# Import numpy for cyclical encoding
import numpy as np
