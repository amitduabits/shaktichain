"""
India Load Profiles - City-specific load profiles for Indian metros.

Provides demand patterns, EV adoption rates, and grid characteristics
for Delhi, Mumbai, Bangalore, Chennai, and Kolkata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np


class Season(Enum):
    """Indian seasons."""
    WINTER = "winter"      # Dec-Feb
    SUMMER = "summer"      # Mar-May
    MONSOON = "monsoon"    # Jun-Sep
    AUTUMN = "autumn"      # Oct-Nov


@dataclass
class CityProfile:
    """Profile for an Indian city."""
    name: str
    state: str
    timezone: str = "Asia/Kolkata"
    population_millions: float = 10.0
    ev_adoption_rate: float = 0.02
    grid_reliability: float = 0.95
    avg_temperature_c: float = 28.0
    peak_hours: tuple = (14, 15, 16, 17)
    evening_peak_hours: tuple = (18, 19, 20, 21)

    # Electricity prices (INR/kWh)
    off_peak_rate: float = 3.0
    standard_rate: float = 5.5
    peak_rate: float = 8.0

    # Load characteristics
    base_load_mw: float = 5000.0
    industrial_fraction: float = 0.3
    commercial_fraction: float = 0.25
    residential_fraction: float = 0.35
    agricultural_fraction: float = 0.1


# Pre-defined city profiles
DELHI = CityProfile(
    name="Delhi",
    state="NCT",
    population_millions=32.9,
    ev_adoption_rate=0.02,
    grid_reliability=0.95,
    avg_temperature_c=25.0,
    peak_hours=(14, 15, 16, 17),
    evening_peak_hours=(18, 19, 20, 21),
    off_peak_rate=3.0,
    standard_rate=5.5,
    peak_rate=8.0,
    base_load_mw=7500.0,
    industrial_fraction=0.2,
    commercial_fraction=0.35,
    residential_fraction=0.4,
    agricultural_fraction=0.05,
)

MUMBAI = CityProfile(
    name="Mumbai",
    state="Maharashtra",
    population_millions=21.7,
    ev_adoption_rate=0.025,
    grid_reliability=0.97,
    avg_temperature_c=27.0,
    peak_hours=(14, 15, 16, 17),
    evening_peak_hours=(18, 19, 20, 21),
    off_peak_rate=3.4,
    standard_rate=4.5,
    peak_rate=5.85,
    base_load_mw=4500.0,
    industrial_fraction=0.25,
    commercial_fraction=0.4,
    residential_fraction=0.3,
    agricultural_fraction=0.05,
)

BANGALORE = CityProfile(
    name="Bangalore",
    state="Karnataka",
    population_millions=13.2,
    ev_adoption_rate=0.035,
    grid_reliability=0.96,
    avg_temperature_c=24.0,
    peak_hours=(14, 15, 16, 17),
    evening_peak_hours=(18, 19, 20, 21),
    off_peak_rate=4.15,
    standard_rate=5.55,
    peak_rate=7.40,
    base_load_mw=3500.0,
    industrial_fraction=0.25,
    commercial_fraction=0.35,
    residential_fraction=0.35,
    agricultural_fraction=0.05,
)

CHENNAI = CityProfile(
    name="Chennai",
    state="Tamil Nadu",
    population_millions=11.5,
    ev_adoption_rate=0.02,
    grid_reliability=0.94,
    avg_temperature_c=29.0,
    peak_hours=(14, 15, 16, 17, 18),
    evening_peak_hours=(19, 20, 21),
    off_peak_rate=3.5,
    standard_rate=4.6,
    peak_rate=6.35,
    base_load_mw=3000.0,
    industrial_fraction=0.35,
    commercial_fraction=0.25,
    residential_fraction=0.3,
    agricultural_fraction=0.1,
)

KOLKATA = CityProfile(
    name="Kolkata",
    state="West Bengal",
    population_millions=15.1,
    ev_adoption_rate=0.015,
    grid_reliability=0.93,
    avg_temperature_c=27.0,
    peak_hours=(14, 15, 16, 17),
    evening_peak_hours=(18, 19, 20, 21),
    off_peak_rate=4.39,
    standard_rate=5.48,
    peak_rate=7.18,
    base_load_mw=2800.0,
    industrial_fraction=0.3,
    commercial_fraction=0.25,
    residential_fraction=0.35,
    agricultural_fraction=0.1,
)


class IndiaLoadProfiles:
    """
    Manager for India-specific load profiles.

    Provides methods to generate demand curves, temperature profiles,
    and EV usage patterns for Indian metro cities.
    """

    def __init__(self, random_seed: int = 42):
        """
        Initialize with city profiles.

        Args:
            random_seed: Random seed for reproducibility
        """
        self._rng = np.random.RandomState(random_seed)

        self.cities = {
            "Delhi": DELHI,
            "Mumbai": MUMBAI,
            "Bangalore": BANGALORE,
            "Chennai": CHENNAI,
            "Kolkata": KOLKATA,
        }

        # Monthly temperature profiles (average max temperatures)
        self._monthly_temps = {
            "Delhi": [21, 24, 30, 36, 40, 40, 35, 34, 34, 33, 28, 23],
            "Mumbai": [31, 32, 33, 33, 33, 32, 30, 30, 31, 33, 33, 32],
            "Bangalore": [28, 31, 33, 34, 33, 30, 28, 28, 29, 28, 27, 26],
            "Chennai": [29, 31, 33, 35, 38, 38, 36, 35, 34, 32, 29, 28],
            "Kolkata": [26, 29, 34, 36, 36, 34, 32, 32, 32, 32, 29, 26],
        }

    def get_city_profile(self, city: str) -> CityProfile:
        """Get profile for a city."""
        return self.cities.get(city, DELHI)

    def get_season(self, date: datetime) -> Season:
        """Determine season for a date."""
        month = date.month
        if month in [12, 1, 2]:
            return Season.WINTER
        elif month in [3, 4, 5]:
            return Season.SUMMER
        elif month in [6, 7, 8, 9]:
            return Season.MONSOON
        else:
            return Season.AUTUMN

    def get_temperature(
        self,
        city: str,
        date: datetime,
        hour: int,
    ) -> float:
        """
        Get temperature for city, date, and hour.

        Args:
            city: City name
            date: Date
            hour: Hour of day

        Returns:
            Temperature in Celsius
        """
        month_temps = self._monthly_temps.get(city, self._monthly_temps["Delhi"])
        base_temp = month_temps[date.month - 1]

        # Diurnal variation (about 8°C range)
        # Min at 5 AM, max at 2 PM
        phase = 2 * np.pi * (hour - 14) / 24
        variation = 4 * np.cos(phase)

        # Add some randomness
        noise = self._rng.normal(0, 1)

        return base_temp + variation + noise

    def get_hourly_demand(
        self,
        city: str,
        date: datetime,
        hour: int,
        scale_factor: float = 1.0,
    ) -> float:
        """
        Get hourly demand for a city.

        Args:
            city: City name
            date: Date
            hour: Hour of day
            scale_factor: Scaling factor for demand

        Returns:
            Demand in kWh
        """
        profile = self.get_city_profile(city)
        season = self.get_season(date)
        temp = self.get_temperature(city, date, hour)
        is_weekend = date.weekday() >= 5

        # Base load pattern
        demand = self._calculate_base_demand(profile, hour, is_weekend)

        # Seasonal adjustment
        demand *= self._get_seasonal_factor(season, city)

        # Temperature adjustment (AC/heating load)
        demand *= self._get_temperature_factor(temp, city)

        # Add noise
        noise = 1 + self._rng.normal(0, 0.05)
        demand *= max(0.7, noise)

        return demand * scale_factor

    def _calculate_base_demand(
        self,
        profile: CityProfile,
        hour: int,
        is_weekend: bool,
    ) -> float:
        """Calculate base demand pattern."""
        # Diurnal pattern
        phase = 2 * np.pi * (hour - 15) / 24
        # Max demand near 15:00, minimum in early night/morning.
        diurnal = 0.5 * (1 + np.cos(phase))

        # Scale between 0.6 and 1.4
        multiplier = 0.6 + 0.8 * diurnal

        # Morning peak
        if hour in [8, 9, 10]:
            multiplier *= 1.1

        # Evening peak (residential cooking, lighting)
        if hour in profile.evening_peak_hours:
            multiplier *= 1.15

        # Weekend adjustments
        if is_weekend:
            if hour in [8, 9, 10]:
                multiplier *= 0.9  # Less morning activity
            elif hour in [11, 12, 13]:
                multiplier *= 1.05  # More midday activity
            else:
                multiplier *= 0.95

        return profile.base_load_mw * multiplier / 1000  # Convert to kWh equivalent

    def _get_seasonal_factor(self, season: Season, city: str) -> float:
        """Get seasonal adjustment factor."""
        # Summer has highest demand (AC), winter lowest
        factors = {
            Season.SUMMER: {"Delhi": 1.4, "Mumbai": 1.2, "Bangalore": 1.1, "Chennai": 1.3, "Kolkata": 1.35},
            Season.MONSOON: {"Delhi": 1.1, "Mumbai": 1.15, "Bangalore": 1.0, "Chennai": 1.1, "Kolkata": 1.1},
            Season.AUTUMN: {"Delhi": 1.0, "Mumbai": 1.05, "Bangalore": 1.0, "Chennai": 1.1, "Kolkata": 1.0},
            Season.WINTER: {"Delhi": 0.9, "Mumbai": 0.95, "Bangalore": 0.95, "Chennai": 1.0, "Kolkata": 0.9},
        }

        return factors.get(season, {}).get(city, 1.0)

    def _get_temperature_factor(self, temp: float, city: str) -> float:
        """Get temperature-based demand adjustment."""
        # AC load increases significantly above 30°C
        if temp > 35:
            return 1.3
        elif temp > 30:
            return 1.0 + 0.06 * (temp - 30)
        elif temp < 15:
            return 1.0 + 0.02 * (15 - temp)  # Heating
        else:
            return 1.0

    def get_daily_profile(
        self,
        city: str,
        date: datetime,
        resolution_minutes: int = 60,
    ) -> list[dict]:
        """
        Get complete daily demand profile.

        Args:
            city: City name
            date: Date
            resolution_minutes: Time resolution

        Returns:
            List of demand points
        """
        points_per_hour = 60 // resolution_minutes
        profile = []

        for hour in range(24):
            for sub in range(points_per_hour):
                minute = sub * resolution_minutes
                demand = self.get_hourly_demand(city, date, hour)

                # Add sub-hourly variation
                sub_variation = 1 + self._rng.normal(0, 0.02)
                demand *= sub_variation

                profile.append({
                    "hour": hour,
                    "minute": minute,
                    "demand_kwh": demand,
                    "temperature_c": self.get_temperature(city, date, hour),
                })

        return profile

    def get_ev_charging_pattern(
        self,
        city: str,
        num_evs: int = 100,
        date: datetime = None,
    ) -> dict:
        """
        Get EV charging demand pattern.

        Args:
            city: City name
            num_evs: Number of EVs in the area
            date: Date for the pattern

        Returns:
            Dictionary with hourly EV charging demand
        """
        date = date or datetime.now()
        profile = self.get_city_profile(city)

        is_weekend = date.weekday() >= 5
        hourly_demand = {}

        for hour in range(24):
            # Charging patterns
            if is_weekend:
                # More spread out on weekends
                if 8 <= hour <= 18:
                    charging_fraction = 0.2
                elif 18 <= hour <= 22:
                    charging_fraction = 0.3
                else:
                    charging_fraction = 0.4
            else:
                # Weekday: office hours and evening
                if 9 <= hour <= 17:
                    charging_fraction = 0.15  # Work charging
                elif 18 <= hour <= 22:
                    charging_fraction = 0.35  # Home charging peak
                elif 22 <= hour or hour <= 5:
                    charging_fraction = 0.4  # Overnight charging
                else:
                    charging_fraction = 0.1

            # Average EV battery: 50 kWh, average charging: 7 kW
            avg_charging_power = 7.0
            charging_evs = num_evs * charging_fraction * profile.ev_adoption_rate * 10

            hourly_demand[hour] = charging_evs * avg_charging_power

        return hourly_demand

    def get_price_schedule(
        self,
        city: str,
    ) -> dict:
        """
        Get time-of-use price schedule.

        Args:
            city: City name

        Returns:
            Dictionary mapping hours to prices
        """
        profile = self.get_city_profile(city)
        schedule = {}

        for hour in range(24):
            if hour in profile.peak_hours or hour in profile.evening_peak_hours:
                schedule[hour] = profile.peak_rate
            elif hour in [22, 23, 0, 1, 2, 3, 4, 5]:
                schedule[hour] = profile.off_peak_rate
            else:
                schedule[hour] = profile.standard_rate

        return schedule

    def compare_cities(self) -> dict:
        """Compare key metrics across cities."""
        comparison = {}

        for city_name, profile in self.cities.items():
            comparison[city_name] = {
                "population_millions": profile.population_millions,
                "ev_adoption_rate": profile.ev_adoption_rate,
                "grid_reliability": profile.grid_reliability,
                "peak_rate": profile.peak_rate,
                "off_peak_rate": profile.off_peak_rate,
                "base_load_mw": profile.base_load_mw,
                "industrial_fraction": profile.industrial_fraction,
            }

        return comparison
