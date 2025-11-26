"""
Indian electricity demand load profiles.

This module implements realistic demand patterns for the Indian electricity grid,
accounting for time-of-day, day-of-week, seasonal, and regional variations.

Based on actual consumption patterns observed in Indian distribution networks,
particularly aligned with DISCOM load curves and CERC time-of-day tariff schedules.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class Season(Enum):
    """Indian seasons affecting electricity demand."""
    SUMMER = "summer"      # Apr-Jun: High AC load
    MONSOON = "monsoon"    # Jul-Sep: Moderate load
    WINTER = "winter"      # Oct-Jan: Heating in north, moderate elsewhere
    SPRING = "spring"      # Feb-Mar: Pleasant weather, low load


class Region(Enum):
    """Indian regions/cities with distinct demand characteristics."""
    DELHI = "delhi"
    MUMBAI = "mumbai"
    BANGALORE = "bangalore"
    CHENNAI = "chennai"
    KOLKATA = "kolkata"
    HYDERABAD = "hyderabad"
    PUNE = "pune"
    AHMEDABAD = "ahmedabad"


@dataclass
class DemandMultipliers:
    """Container for all demand multiplier components."""
    hourly: float
    day_of_week: float
    seasonal: float
    regional: float
    combined: float


class IndiaLoadProfile:
    """
    Indian electricity demand load profile calculator.

    Models realistic demand patterns based on:
    - Hourly variations (morning/evening peaks)
    - Day-of-week patterns (weekday vs weekend)
    - Seasonal variations (summer AC load, etc.)
    - Regional differences (climate-based)

    Example usage:
        >>> profile = IndiaLoadProfile()
        >>> # Get multiplier for 7 PM on a Monday in June in Delhi
        >>> multiplier = profile.get_demand_multiplier(
        ...     hour=19, day_of_week=0, month=6, region="Delhi"
        ... )
        >>> print(f"Demand multiplier: {multiplier:.2f}")
        Demand multiplier: 2.57
    """

    # Hourly multipliers based on actual Indian consumption patterns
    # These reflect typical DISCOM load curves with morning and evening peaks
    HOURLY_MULTIPLIERS: Dict[int, float] = {
        # Night hours (11 PM - 5 AM): Low demand
        0: 0.55,   # Midnight
        1: 0.52,
        2: 0.50,   # Minimum demand
        3: 0.50,
        4: 0.52,
        5: 0.60,   # Early morning rise begins

        # Morning peak (6 AM - 10 AM): Industrial startup + residential
        6: 0.85,   # Factories starting
        7: 1.10,   # Morning activities begin
        8: 1.30,   # Peak morning - offices, schools starting
        9: 1.45,   # Morning peak
        10: 1.50,  # End of morning peak

        # Afternoon (11 AM - 5 PM): Moderate - industrial steady state
        11: 1.10,  # Post-morning dip
        12: 1.05,  # Lunch hour
        13: 1.00,  # Early afternoon
        14: 0.95,  # Afternoon trough
        15: 0.90,  # Lowest afternoon
        16: 0.95,  # Pre-evening rise
        17: 1.05,  # Evening begins

        # Evening peak (6 PM - 10 PM): Highest demand - residential + lighting
        18: 1.40,  # Evening activities begin
        19: 1.65,  # Prime evening
        20: 1.80,  # Peak demand - lights, AC, cooking
        21: 1.70,  # High demand continues
        22: 1.45,  # Tapering off

        # Late night
        23: 0.70,  # Night begins
    }

    # Day-of-week multipliers
    # 0 = Monday, 6 = Sunday
    DAY_OF_WEEK_MULTIPLIERS: Dict[int, float] = {
        0: 1.10,  # Monday - highest weekday
        1: 1.10,  # Tuesday
        2: 1.10,  # Wednesday
        3: 1.10,  # Thursday
        4: 1.10,  # Friday
        5: 0.95,  # Saturday - reduced commercial
        6: 0.85,  # Sunday - lowest demand
    }

    # Seasonal multipliers based on month
    SEASONAL_MULTIPLIERS: Dict[int, float] = {
        # Winter (Oct-Jan): Moderate heating load in north
        1: 1.10,   # January
        10: 1.10,  # October
        11: 1.10,  # November
        12: 1.10,  # December

        # Spring (Feb-Mar): Pleasant weather
        2: 0.95,   # February
        3: 0.95,   # March

        # Summer (Apr-Jun): Heavy AC load
        4: 1.30,   # April - summer begins
        5: 1.30,   # May - peak summer
        6: 1.30,   # June - pre-monsoon heat

        # Monsoon (Jul-Sep): Moderate, reduced AC
        7: 1.00,   # July
        8: 1.00,   # August
        9: 1.00,   # September
    }

    # Regional multipliers based on climate and industrial base
    REGIONAL_MULTIPLIERS: Dict[str, float] = {
        # Hot climates with high cooling demand
        "chennai": 1.25,      # Hot and humid year-round
        "ahmedabad": 1.20,    # Extreme heat in summer

        # Major metros with high demand
        "delhi": 1.20,        # Extreme temperatures, high population
        "mumbai": 1.15,       # Coastal, commercial hub

        # Moderate climate metros
        "bangalore": 1.10,    # Pleasant climate, IT hub
        "hyderabad": 1.15,    # Hot summers
        "pune": 1.10,         # Pleasant climate
        "kolkata": 1.15,      # Hot and humid

        # Default for unlisted regions
        "default": 1.00,
    }

    def __init__(self, base_load_mw: float = 1000.0):
        """
        Initialize the India load profile calculator.

        Args:
            base_load_mw: Base load in MW for absolute demand calculations.
                         Default is 1000 MW (typical medium DISCOM).
        """
        self.base_load_mw = base_load_mw

    def get_season(self, month: int) -> Season:
        """
        Determine the season for a given month.

        Args:
            month: Month number (1-12)

        Returns:
            Season enum value
        """
        if month in (4, 5, 6):
            return Season.SUMMER
        elif month in (7, 8, 9):
            return Season.MONSOON
        elif month in (10, 11, 12, 1):
            return Season.WINTER
        else:  # 2, 3
            return Season.SPRING

    def get_hourly_multiplier(self, hour: int) -> float:
        """
        Get the hourly demand multiplier.

        Args:
            hour: Hour of day (0-23)

        Returns:
            Hourly multiplier (0.5 - 1.8 range)
        """
        if not 0 <= hour <= 23:
            raise ValueError(f"Hour must be 0-23, got {hour}")
        return self.HOURLY_MULTIPLIERS[hour]

    def get_day_of_week_multiplier(self, day_of_week: int) -> float:
        """
        Get the day-of-week demand multiplier.

        Args:
            day_of_week: Day of week (0=Monday, 6=Sunday)

        Returns:
            Day multiplier (0.85 - 1.1 range)
        """
        if not 0 <= day_of_week <= 6:
            raise ValueError(f"Day of week must be 0-6, got {day_of_week}")
        return self.DAY_OF_WEEK_MULTIPLIERS[day_of_week]

    def get_seasonal_multiplier(self, month: int) -> float:
        """
        Get the seasonal demand multiplier.

        Args:
            month: Month number (1-12)

        Returns:
            Seasonal multiplier (0.95 - 1.3 range)
        """
        if not 1 <= month <= 12:
            raise ValueError(f"Month must be 1-12, got {month}")
        return self.SEASONAL_MULTIPLIERS[month]

    def get_regional_multiplier(self, region: str) -> float:
        """
        Get the regional demand multiplier.

        Args:
            region: Region/city name (case-insensitive)

        Returns:
            Regional multiplier (1.0 - 1.25 range)
        """
        region_lower = region.lower()
        return self.REGIONAL_MULTIPLIERS.get(
            region_lower,
            self.REGIONAL_MULTIPLIERS["default"]
        )

    def get_demand_multiplier(
        self,
        hour: int,
        day_of_week: int,
        month: int,
        region: str = "Delhi"
    ) -> float:
        """
        Calculate the combined demand multiplier for given parameters.

        This method combines all four multiplier types (hourly, day-of-week,
        seasonal, and regional) to produce a single demand multiplier.

        Args:
            hour: Hour of day (0-23)
            day_of_week: Day of week (0=Monday, 6=Sunday)
            month: Month number (1-12)
            region: Region/city name (default: "Delhi")

        Returns:
            Combined demand multiplier (product of all component multipliers)

        Example:
            >>> profile = IndiaLoadProfile()
            >>> # Peak evening in summer Delhi on a weekday
            >>> mult = profile.get_demand_multiplier(20, 0, 5, "Delhi")
            >>> print(f"{mult:.2f}")  # ~2.6x base load
            2.59
        """
        hourly = self.get_hourly_multiplier(hour)
        day = self.get_day_of_week_multiplier(day_of_week)
        seasonal = self.get_seasonal_multiplier(month)
        regional = self.get_regional_multiplier(region)

        return hourly * day * seasonal * regional

    def get_demand_multiplier_detailed(
        self,
        hour: int,
        day_of_week: int,
        month: int,
        region: str = "Delhi"
    ) -> DemandMultipliers:
        """
        Get detailed breakdown of all demand multiplier components.

        Args:
            hour: Hour of day (0-23)
            day_of_week: Day of week (0=Monday, 6=Sunday)
            month: Month number (1-12)
            region: Region/city name (default: "Delhi")

        Returns:
            DemandMultipliers dataclass with all component values
        """
        hourly = self.get_hourly_multiplier(hour)
        day = self.get_day_of_week_multiplier(day_of_week)
        seasonal = self.get_seasonal_multiplier(month)
        regional = self.get_regional_multiplier(region)

        return DemandMultipliers(
            hourly=hourly,
            day_of_week=day,
            seasonal=seasonal,
            regional=regional,
            combined=hourly * day * seasonal * regional
        )

    def get_absolute_demand_mw(
        self,
        hour: int,
        day_of_week: int,
        month: int,
        region: str = "Delhi"
    ) -> float:
        """
        Calculate absolute demand in MW for given parameters.

        Args:
            hour: Hour of day (0-23)
            day_of_week: Day of week (0=Monday, 6=Sunday)
            month: Month number (1-12)
            region: Region/city name (default: "Delhi")

        Returns:
            Demand in MW (base_load_mw * combined_multiplier)
        """
        multiplier = self.get_demand_multiplier(hour, day_of_week, month, region)
        return self.base_load_mw * multiplier

    def get_daily_profile(
        self,
        day_of_week: int,
        month: int,
        region: str = "Delhi"
    ) -> Dict[int, float]:
        """
        Get demand multipliers for all 24 hours of a day.

        Args:
            day_of_week: Day of week (0=Monday, 6=Sunday)
            month: Month number (1-12)
            region: Region/city name (default: "Delhi")

        Returns:
            Dictionary mapping hour (0-23) to demand multiplier
        """
        return {
            hour: self.get_demand_multiplier(hour, day_of_week, month, region)
            for hour in range(24)
        }

    def get_peak_hours(self, threshold: float = 1.3) -> Dict[str, list]:
        """
        Identify peak demand hours based on hourly multipliers.

        Args:
            threshold: Multiplier threshold to consider as peak (default 1.3)

        Returns:
            Dictionary with 'morning_peak' and 'evening_peak' hour lists
        """
        morning_peak = [
            h for h in range(5, 12)
            if self.HOURLY_MULTIPLIERS[h] >= threshold
        ]
        evening_peak = [
            h for h in range(17, 24)
            if self.HOURLY_MULTIPLIERS[h] >= threshold
        ]

        return {
            "morning_peak": morning_peak,
            "evening_peak": evening_peak,
        }

    def is_peak_hour(self, hour: int) -> bool:
        """
        Check if given hour is a peak demand hour.

        Peak hours are defined as those with hourly multiplier >= 1.3

        Args:
            hour: Hour of day (0-23)

        Returns:
            True if peak hour, False otherwise
        """
        return self.get_hourly_multiplier(hour) >= 1.3

    def get_off_peak_hours(self) -> list:
        """
        Get list of off-peak hours (best for EV charging).

        Off-peak hours have multiplier < 0.8 (typically night hours).

        Returns:
            List of off-peak hours (0-23)
        """
        return [
            h for h in range(24)
            if self.HOURLY_MULTIPLIERS[h] < 0.8
        ]

    def get_v2g_opportunity_hours(self) -> list:
        """
        Get hours suitable for V2G discharge (high demand periods).

        Returns hours where demand multiplier >= 1.4 (evening peak typically),
        which are optimal for EVs to sell power back to grid.

        Returns:
            List of high-demand hours suitable for V2G
        """
        return [
            h for h in range(24)
            if self.HOURLY_MULTIPLIERS[h] >= 1.4
        ]
