"""
Synthetic Load Generator for SHAKTI-CHAIN Load Forecasting (Domain 7).

Generates realistic synthetic electricity load data for Indian cities
with daily, weekly, and seasonal patterns plus special events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CityLoadProfile:
    """
    Load profile configuration for an Indian city.

    Attributes:
        name: City name
        base_load_mw: Average base load in MW
        daily_pattern: 24 hourly multipliers (index 0 = midnight)
        weekly_pattern: 7 daily multipliers (index 0 = Sunday)
        seasonal_amplitude: Seasonal variation (0-1)
        peak_month: Month with highest demand (1-12)
        noise_std: Standard deviation of random noise
        temperature_sensitivity: Load change per degree C
    """
    name: str
    base_load_mw: float
    daily_pattern: np.ndarray
    weekly_pattern: np.ndarray
    seasonal_amplitude: float
    peak_month: int
    noise_std: float
    temperature_sensitivity: float = 0.02  # 2% per degree

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "base_load_mw": float(self.base_load_mw),
            "seasonal_amplitude": float(self.seasonal_amplitude),
            "peak_month": self.peak_month,
            "noise_std": float(self.noise_std),
            "temperature_sensitivity": float(self.temperature_sensitivity),
        }


# India-specific city profiles
DELHI_PROFILE = CityLoadProfile(
    name="Delhi",
    base_load_mw=5000,
    daily_pattern=np.array([
        0.60, 0.55, 0.50, 0.50, 0.55, 0.65, 0.80, 0.90,
        0.95, 1.00, 1.05, 1.10, 1.10, 1.15, 1.20, 1.15,
        1.10, 1.05, 1.00, 0.95, 0.90, 0.85, 0.75, 0.65
    ]),
    weekly_pattern=np.array([0.90, 1.00, 1.00, 1.00, 1.00, 0.95, 0.85]),  # Sun-Sat
    seasonal_amplitude=0.30,
    peak_month=6,  # June (summer)
    noise_std=0.05
)

MUMBAI_PROFILE = CityLoadProfile(
    name="Mumbai",
    base_load_mw=4000,
    daily_pattern=np.array([
        0.70, 0.65, 0.60, 0.60, 0.65, 0.70, 0.85, 0.95,
        1.00, 1.05, 1.05, 1.10, 1.05, 1.00, 1.00, 1.05,
        1.10, 1.15, 1.10, 1.00, 0.95, 0.90, 0.85, 0.75
    ]),
    weekly_pattern=np.array([0.85, 1.00, 1.00, 1.00, 1.00, 1.00, 0.90]),
    seasonal_amplitude=0.15,  # Less seasonal (coastal)
    peak_month=5,  # May (pre-monsoon)
    noise_std=0.04
)

BANGALORE_PROFILE = CityLoadProfile(
    name="Bangalore",
    base_load_mw=3500,
    daily_pattern=np.array([
        0.65, 0.60, 0.55, 0.55, 0.60, 0.70, 0.85, 0.95,
        1.00, 1.10, 1.15, 1.15, 1.10, 1.05, 1.05, 1.10,
        1.15, 1.10, 1.00, 0.95, 0.90, 0.85, 0.75, 0.70
    ]),
    weekly_pattern=np.array([0.80, 1.00, 1.05, 1.05, 1.05, 1.00, 0.85]),
    seasonal_amplitude=0.10,  # Mild climate
    peak_month=4,  # April
    noise_std=0.04
)

CHENNAI_PROFILE = CityLoadProfile(
    name="Chennai",
    base_load_mw=3000,
    daily_pattern=np.array([
        0.65, 0.60, 0.55, 0.55, 0.60, 0.70, 0.85, 0.95,
        1.00, 1.05, 1.10, 1.15, 1.15, 1.10, 1.10, 1.15,
        1.20, 1.15, 1.05, 0.95, 0.90, 0.85, 0.80, 0.70
    ]),
    weekly_pattern=np.array([0.85, 1.00, 1.00, 1.00, 1.00, 0.95, 0.85]),
    seasonal_amplitude=0.20,
    peak_month=5,  # May (hottest)
    noise_std=0.05
)

KOLKATA_PROFILE = CityLoadProfile(
    name="Kolkata",
    base_load_mw=2500,
    daily_pattern=np.array([
        0.60, 0.55, 0.50, 0.50, 0.55, 0.65, 0.80, 0.90,
        0.95, 1.00, 1.05, 1.10, 1.10, 1.05, 1.05, 1.10,
        1.15, 1.10, 1.00, 0.95, 0.90, 0.85, 0.75, 0.65
    ]),
    weekly_pattern=np.array([0.85, 1.00, 1.00, 1.00, 1.00, 0.95, 0.80]),
    seasonal_amplitude=0.25,
    peak_month=5,  # May
    noise_std=0.05
)

HYDERABAD_PROFILE = CityLoadProfile(
    name="Hyderabad",
    base_load_mw=3200,
    daily_pattern=np.array([
        0.62, 0.58, 0.52, 0.52, 0.58, 0.68, 0.82, 0.92,
        0.98, 1.05, 1.10, 1.12, 1.10, 1.08, 1.08, 1.12,
        1.18, 1.12, 1.02, 0.95, 0.88, 0.82, 0.75, 0.68
    ]),
    weekly_pattern=np.array([0.82, 1.00, 1.02, 1.02, 1.02, 0.98, 0.85]),
    seasonal_amplitude=0.18,
    peak_month=5,
    noise_std=0.04
)

# All city profiles
INDIA_CITY_PROFILES = [
    DELHI_PROFILE,
    MUMBAI_PROFILE,
    BANGALORE_PROFILE,
    CHENNAI_PROFILE,
    KOLKATA_PROFILE,
    HYDERABAD_PROFILE,
]


@dataclass
class SpecialEvent:
    """A special event affecting load."""
    name: str
    date: str  # YYYY-MM-DD format
    load_multiplier: float  # 1.2 = 20% increase
    hours_affected: List[int] = field(default_factory=lambda: list(range(24)))
    duration_days: int = 1


# Indian festivals and holidays
INDIAN_HOLIDAYS_2024 = [
    SpecialEvent("Republic Day", "2024-01-26", 0.85, list(range(10, 18))),
    SpecialEvent("Holi", "2024-03-25", 0.90, list(range(8, 20))),
    SpecialEvent("Independence Day", "2024-08-15", 0.85, list(range(8, 18))),
    SpecialEvent("Diwali", "2024-11-01", 1.25, list(range(17, 24)), duration_days=3),
    SpecialEvent("Christmas", "2024-12-25", 0.95),
    SpecialEvent("New Year", "2024-01-01", 1.10, list(range(0, 6)) + list(range(20, 24))),
]


class SyntheticLoadGenerator:
    """
    Generate synthetic electricity load data for Indian cities.

    Creates realistic load patterns with:
    - Daily patterns (peak hours, off-peak)
    - Weekly patterns (weekday vs weekend)
    - Seasonal patterns (summer peaks, monsoon dips)
    - Special events (festivals, holidays)
    - Random noise
    - Temperature correlation
    """

    def __init__(
        self,
        profiles: Optional[List[CityLoadProfile]] = None,
        seed: Optional[int] = None,
    ):
        """
        Initialize generator.

        Args:
            profiles: List of city profiles (uses defaults if None)
            seed: Random seed
        """
        if profiles is None:
            profiles = INDIA_CITY_PROFILES

        self.profiles = {p.name: p for p in profiles}
        self.rng = np.random.default_rng(seed)

    def generate(
        self,
        city: str,
        start_date: str,
        end_date: str,
        resolution_minutes: int = 60,
        include_temperature: bool = True,
        include_events: bool = True,
    ) -> pd.DataFrame:
        """
        Generate synthetic load data.

        Args:
            city: City name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            resolution_minutes: Time resolution (15, 30, or 60)
            include_temperature: Whether to include temperature
            include_events: Whether to include special events

        Returns:
            DataFrame with columns:
                timestamp, load_mw, temperature, is_holiday, is_festival,
                hour, day_of_week, month, city
        """
        if city not in self.profiles:
            raise ValueError(f"Unknown city: {city}. Available: {list(self.profiles.keys())}")

        profile = self.profiles[city]

        # Generate timestamp range
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(minutes=resolution_minutes)
        timestamps = pd.date_range(start, end, freq=f"{resolution_minutes}min")

        # Initialize DataFrame
        df = pd.DataFrame({"timestamp": timestamps})
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek  # 0=Monday
        df["month"] = df["timestamp"].dt.month
        df["day_of_year"] = df["timestamp"].dt.dayofyear
        df["city"] = city

        # Calculate base load with patterns
        df["load_mw"] = self._calculate_load(df, profile)

        # Add temperature if requested
        if include_temperature:
            df["temperature"] = self._generate_temperature(df, profile)
            # Adjust load based on temperature
            temp_deviation = df["temperature"] - 25  # Reference temp
            df["load_mw"] *= (1 + profile.temperature_sensitivity * temp_deviation)

        # Add special events
        df["is_holiday"] = False
        df["is_festival"] = False

        if include_events:
            df = self._add_special_events(df, profile)

        # Add random noise
        noise = self.rng.normal(0, profile.noise_std, len(df))
        df["load_mw"] *= (1 + noise)

        # Ensure positive load
        df["load_mw"] = df["load_mw"].clip(lower=profile.base_load_mw * 0.2)

        return df

    def _calculate_load(
        self,
        df: pd.DataFrame,
        profile: CityLoadProfile,
    ) -> np.ndarray:
        """Calculate load based on daily, weekly, and seasonal patterns."""
        n = len(df)
        load = np.full(n, profile.base_load_mw)

        # Daily pattern
        daily_factors = profile.daily_pattern[df["hour"].values]

        # Weekly pattern (adjust for Monday=0 indexing)
        # Profile uses Sunday=0, pandas uses Monday=0
        adjusted_dow = (df["day_of_week"].values + 1) % 7
        weekly_factors = profile.weekly_pattern[adjusted_dow]

        # Seasonal pattern (sinusoidal with peak at peak_month)
        day_of_year = df["day_of_year"].values
        peak_day = (profile.peak_month - 1) * 30 + 15  # Approximate
        seasonal_phase = 2 * np.pi * (day_of_year - peak_day) / 365
        seasonal_factors = 1 + profile.seasonal_amplitude * np.cos(seasonal_phase)

        # Combine all factors
        load = load * daily_factors * weekly_factors * seasonal_factors

        return load

    def _generate_temperature(
        self,
        df: pd.DataFrame,
        profile: CityLoadProfile,
    ) -> np.ndarray:
        """Generate synthetic temperature data."""
        n = len(df)

        # Base temperature varies by city (rough averages)
        city_base_temps = {
            "Delhi": 25,
            "Mumbai": 28,
            "Bangalore": 24,
            "Chennai": 29,
            "Kolkata": 27,
            "Hyderabad": 26,
        }
        base_temp = city_base_temps.get(profile.name, 26)

        # Seasonal variation
        day_of_year = df["day_of_year"].values
        # Peak temperature in May-June (day ~150)
        seasonal_temp = 8 * np.sin(2 * np.pi * (day_of_year - 100) / 365)

        # Daily variation (warmer afternoon)
        hour = df["hour"].values
        daily_temp = 5 * np.sin(2 * np.pi * (hour - 6) / 24)

        # Random variation
        noise = self.rng.normal(0, 2, n)

        temperature = base_temp + seasonal_temp + daily_temp + noise

        return temperature

    def _add_special_events(
        self,
        df: pd.DataFrame,
        profile: CityLoadProfile,
    ) -> pd.DataFrame:
        """Add special event effects to load data."""
        for event in INDIAN_HOLIDAYS_2024:
            event_date = pd.Timestamp(event.date)

            for day_offset in range(event.duration_days):
                current_date = event_date + pd.Timedelta(days=day_offset)

                mask = (
                    (df["timestamp"].dt.date == current_date.date()) &
                    (df["hour"].isin(event.hours_affected))
                )

                if mask.any():
                    df.loc[mask, "load_mw"] *= event.load_multiplier

                    if "Diwali" in event.name or "Holi" in event.name:
                        df.loc[mask, "is_festival"] = True
                    else:
                        df.loc[mask, "is_holiday"] = True

        return df

    def generate_multi_city(
        self,
        start_date: str,
        end_date: str,
        cities: Optional[List[str]] = None,
        resolution_minutes: int = 60,
    ) -> pd.DataFrame:
        """
        Generate load data for multiple cities.

        Args:
            start_date: Start date
            end_date: End date
            cities: List of city names (uses all if None)
            resolution_minutes: Time resolution

        Returns:
            Combined DataFrame with all cities
        """
        if cities is None:
            cities = list(self.profiles.keys())

        dfs = []
        for city in cities:
            df = self.generate(
                city=city,
                start_date=start_date,
                end_date=end_date,
                resolution_minutes=resolution_minutes,
            )
            dfs.append(df)

        return pd.concat(dfs, ignore_index=True)

    def add_forecast_features(
        self,
        df: pd.DataFrame,
        lag_hours: List[int] = None,
        rolling_windows: List[int] = None,
    ) -> pd.DataFrame:
        """
        Add features useful for forecasting.

        Args:
            df: Load data DataFrame
            lag_hours: Lag features to add (e.g., [1, 24, 168])
            rolling_windows: Rolling mean windows (e.g., [24, 168])

        Returns:
            DataFrame with additional features
        """
        if lag_hours is None:
            lag_hours = [1, 24, 168]  # 1 hour, 1 day, 1 week

        if rolling_windows is None:
            rolling_windows = [24, 168]

        df = df.copy()

        # Sort by timestamp within each city
        df = df.sort_values(["city", "timestamp"])

        # Add lag features
        for lag in lag_hours:
            df[f"load_lag_{lag}h"] = df.groupby("city")["load_mw"].shift(lag)

        # Add rolling mean features
        for window in rolling_windows:
            df[f"load_rolling_{window}h"] = df.groupby("city")["load_mw"].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Add time encoding (cyclical)
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
        df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

        return df


def generate_sample_data(
    n_days: int = 365,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """
    Generate sample load data for testing.

    Args:
        n_days: Number of days to generate
        seed: Random seed

    Returns:
        DataFrame with load data for all cities
    """
    generator = SyntheticLoadGenerator(seed=seed)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_days)

    return generator.generate_multi_city(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        resolution_minutes=60,
    )


# City profiles dictionary (for easy lookup by name)
CITY_PROFILES = {
    "Delhi": DELHI_PROFILE,
    "Mumbai": MUMBAI_PROFILE,
    "Bangalore": BANGALORE_PROFILE,
    "Chennai": CHENNAI_PROFILE,
    "Kolkata": KOLKATA_PROFILE,
    "Hyderabad": HYDERABAD_PROFILE,
}

# List of Indian cities
INDIA_CITIES = list(CITY_PROFILES.keys())

# Alias for special events
INDIA_SPECIAL_EVENTS = INDIAN_HOLIDAYS_2024


def generate_india_load_data(
    cities: Optional[List[str]] = None,
    days: int = 365,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """
    Generate load data for Indian cities.

    Args:
        cities: List of cities (uses all if None)
        days: Number of days to generate
        seed: Random seed

    Returns:
        DataFrame with load data
    """
    generator = SyntheticLoadGenerator(seed=seed)

    if cities is None:
        cities = INDIA_CITIES

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    return generator.generate_multi_city(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        cities=cities,
        resolution_minutes=60,
    )


# Add generate_city_load method to SyntheticLoadGenerator
def _generate_city_load(
    self,
    profile: CityLoadProfile,
    days: int = 365,
    include_events: bool = True,
) -> pd.DataFrame:
    """
    Generate load data for a single city using its profile.

    Args:
        profile: CityLoadProfile for the city
        days: Number of days to generate
        include_events: Whether to include special events

    Returns:
        DataFrame with load data
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    return self.generate(
        city=profile.name,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        resolution_minutes=60,
        include_events=include_events,
    )


# Monkey-patch the method onto the class
SyntheticLoadGenerator.generate_city_load = _generate_city_load
