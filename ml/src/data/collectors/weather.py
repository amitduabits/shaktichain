"""Weather data collector using OpenWeatherMap API.

Collects temperature, humidity, and other weather parameters.
"""

import logging
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class LocationConfig(BaseModel):
    """Configuration for a weather location."""

    name: str
    lat: float
    lon: float


class WeatherConfig(CollectorConfig):
    """Configuration for Weather collector."""

    api_url: str = "https://api.openweathermap.org/data/2.5"
    api_key: Optional[str] = None
    use_live_api: bool = False
    locations: List[LocationConfig] = Field(default_factory=list)


class WeatherCollector(BaseCollector):
    """Collector for weather data from OpenWeatherMap."""

    def __init__(
        self,
        config: Optional[WeatherConfig] = None,
        api_key: Optional[str] = None,
        locations: Optional[List[LocationConfig]] = None,
    ):
        """Initialize Weather collector.

        Args:
            config: Weather collector configuration
        """
        if config is None:
            config = WeatherConfig(
                api_key=api_key,
                locations=locations or [
                    LocationConfig(name="DELHI", lat=28.6139, lon=77.2090)
                ],
            )
        elif api_key:
            config.api_key = api_key
        elif locations:
            config.locations = locations

        super().__init__(config)
        self.config: WeatherConfig = config

        # Get API key from config or environment
        self.api_key = config.api_key or os.getenv("OPENWEATHER_API_KEY")
        if not self.api_key:
            logger.warning(
                "OpenWeatherMap API key not provided. "
                "Set OPENWEATHER_API_KEY environment variable."
            )

    @staticmethod
    def _location_from_city(city: str) -> LocationConfig:
        city_map = {
            "delhi": LocationConfig(name="DELHI", lat=28.6139, lon=77.2090),
            "mumbai": LocationConfig(name="MUMBAI", lat=19.0760, lon=72.8777),
            "bengaluru": LocationConfig(name="BENGALURU", lat=12.9716, lon=77.5946),
            "kolkata": LocationConfig(name="KOLKATA", lat=22.5726, lon=88.3639),
            "chennai": LocationConfig(name="CHENNAI", lat=13.0827, lon=80.2707),
        }
        return city_map.get(city.lower(), LocationConfig(name=city.upper(), lat=28.6139, lon=77.2090))

    @staticmethod
    def _generate_synthetic_weather(
        start_date: datetime,
        end_date: datetime,
        locations: List[LocationConfig],
    ) -> pd.DataFrame:
        timestamps = pd.date_range(start=start_date, end=end_date, freq="h")
        rows: List[Dict[str, Any]] = []

        for location in locations:
            loc_seed = int(hashlib.sha256(location.name.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(loc_seed)
            for ts in timestamps:
                hour = ts.hour
                day_of_year = ts.timetuple().tm_yday

                base_temp = 28.0 + 2.0 * np.sin((location.lat - 10.0) / 25.0)
                daily = 6.0 * np.sin((hour - 6) * np.pi / 12)
                seasonal = 8.0 * np.sin((day_of_year - 81) * 2 * np.pi / 365)
                noise = float(rng.normal(0, 0.8))
                temperature = base_temp + daily + seasonal + noise

                humidity = 60.0 + 15.0 * np.sin(hour * np.pi / 24) + float(rng.normal(0, 2.0))
                humidity = float(np.clip(humidity, 20, 95))

                rows.append(
                    {
                        "timestamp": ts,
                        "location": location.name,
                        "temperature_c": float(temperature),
                        "temperature": float(temperature),
                        "feels_like_c": float(temperature - 1.5),
                        "humidity_pct": humidity,
                        "humidity": humidity,
                        "pressure_hpa": float(1008 + rng.normal(0, 4)),
                        "wind_speed_ms": float(np.clip(rng.normal(3.5, 1.0), 0, None)),
                        "wind_direction_deg": float((180 + rng.normal(0, 30)) % 360),
                        "cloudiness_pct": float(np.clip(30 + rng.normal(0, 20), 0, 100)),
                        "weather_main": "Clear",
                        "weather_description": "synthetic-clear-sky",
                    }
                )

        return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _fetch_historical_data(
        self, lat: float, lon: float, timestamp: int
    ) -> Dict[str, Any]:
        """Fetch historical weather data for a specific timestamp.

        Args:
            lat: Latitude
            lon: Longitude
            timestamp: Unix timestamp

        Returns:
            Dictionary with weather data
        """
        # Note: Historical data requires OpenWeatherMap paid subscription
        # Using One Call API 3.0 for historical data
        url = f"{self.config.api_url}/onecall/timemachine"
        params = {
            "lat": lat,
            "lon": lon,
            "dt": timestamp,
            "appid": self.api_key,
            "units": "metric",
        }

        logger.debug(f"Fetching weather data for ({lat}, {lon}) at {timestamp}")

        try:
            response = requests.get(url, params=params, timeout=self.config.timeout)
            response.raise_for_status()
            data = response.json()

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather data: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _fetch_current_data(self, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch current weather data.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dictionary with weather data
        """
        url = f"{self.config.api_url}/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }

        logger.debug(f"Fetching current weather data for ({lat}, {lon})")

        try:
            response = requests.get(url, params=params, timeout=self.config.timeout)
            response.raise_for_status()
            data = response.json()

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching current weather data: {e}")
            raise

    def _parse_weather_response(
        self, data: Dict[str, Any], location_name: str, timestamp: datetime
    ) -> Dict[str, Any]:
        """Parse weather API response.

        Args:
            data: Raw API response
            location_name: Name of location
            timestamp: Timestamp for the data

        Returns:
            Parsed weather data
        """
        # Handle different API response formats
        if "data" in data:  # Historical API format
            weather_data = data["data"][0] if data.get("data") else data
        else:  # Current weather API format
            weather_data = data

        main = weather_data.get("main", {})
        weather = weather_data.get("weather", [{}])[0]
        wind = weather_data.get("wind", {})
        clouds = weather_data.get("clouds", {})

        return {
            "timestamp": timestamp,
            "location": location_name,
            "temperature_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "pressure_hpa": main.get("pressure"),
            "wind_speed_ms": wind.get("speed"),
            "wind_direction_deg": wind.get("deg"),
            "cloudiness_pct": clouds.get("all"),
            "weather_main": weather.get("main"),
            "weather_description": weather.get("description"),
        }

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect weather data for date range.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters (locations)

        Returns:
            DataFrame with collected weather data
        """
        locations = kwargs.get("locations", self.config.locations)
        city = kwargs.get("city")
        if city and not locations:
            locations = [self._location_from_city(str(city))]
        elif city and locations:
            locations = [self._location_from_city(str(city))]
        if not locations:
            locations = [LocationConfig(name="DELHI", lat=28.6139, lon=77.2090)]

        if not self.config.use_live_api or not self.api_key:
            return self._generate_synthetic_weather(start_date, end_date, locations)

        # Check cache first
        cache_key = self.get_cache_key(
            start_date, end_date, locations=str([loc.name for loc in locations])
        )
        cached_data = self.load_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Loading weather data from cache: {cache_key}")
            return cached_data

        all_data = []
        current_date = start_date

        while current_date <= end_date:
            for location in locations:
                try:
                    # Generate hourly timestamps for the day
                    for hour in range(24):
                        timestamp_dt = current_date.replace(hour=hour, minute=0, second=0)
                        timestamp_unix = int(timestamp_dt.timestamp())

                        # Fetch data
                        if timestamp_dt < datetime.now() - timedelta(days=5):
                            raw_data = self._fetch_historical_data(location.lat, location.lon, timestamp_unix)
                        else:
                            raw_data = self._fetch_current_data(location.lat, location.lon)

                        parsed_data = self._parse_weather_response(raw_data, location.name, timestamp_dt)
                        parsed_data["temperature"] = parsed_data.get("temperature_c")
                        parsed_data["humidity"] = parsed_data.get("humidity_pct")
                        all_data.append(parsed_data)
                        time.sleep(1)

                except Exception as e:
                    logger.error(
                        f"Failed to fetch weather for {location.name} "
                        f"at {current_date}: {e}"
                    )
                    continue

            current_date += timedelta(days=1)

        if not all_data:
            logger.warning("Live weather fetch returned no rows; using synthetic fallback")
            return self._generate_synthetic_weather(start_date, end_date, locations)

        df = pd.DataFrame(all_data)
        df = df.sort_values("timestamp").reset_index(drop=True)
        if "temperature" not in df.columns and "temperature_c" in df.columns:
            df["temperature"] = df["temperature_c"]
        if "humidity" not in df.columns and "humidity_pct" in df.columns:
            df["humidity"] = df["humidity_pct"]

        # Save to cache
        self.save_cache(df, cache_key)
        logger.info(f"Collected {len(df)} weather records")

        return df

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate weather data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        if data.empty:
            logger.warning("Weather data is empty")
            return True  # Empty is okay if API key not available

        required_columns = [
            "timestamp",
            "location",
            "temperature_c",
            "humidity_pct",
        ]

        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required columns in weather data")
            return False

        # Check temperature is reasonable (-50 to 60°C)
        temp_valid = data["temperature_c"].between(-50, 60).all()
        if not temp_valid:
            logger.error("Temperature values out of reasonable range")
            return False

        # Check humidity is 0-100%
        humidity_valid = data["humidity_pct"].between(0, 100).all()
        if not humidity_valid:
            logger.error("Humidity values out of valid range")
            return False

        return True


class WeatherSimulator(BaseCollector):
    """Simulates weather data when API is not available."""

    def __init__(self, config: WeatherConfig):
        """Initialize weather simulator.

        Args:
            config: Configuration
        """
        super().__init__(config)
        self.config: WeatherConfig = config

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Generate simulated weather data.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            DataFrame with simulated weather data
        """
        import numpy as np

        locations = kwargs.get("locations", self.config.locations)

        timestamps = pd.date_range(start=start_date, end=end_date, freq="h")
        data = []

        for location in locations:
            for ts in timestamps:
                # Simple sinusoidal pattern for temperature
                hour_of_day = ts.hour
                day_of_year = ts.timetuple().tm_yday

                # Base temperature with daily and seasonal variation
                base_temp = 25  # Average temperature
                daily_variation = 5 * np.sin((hour_of_day - 6) * np.pi / 12)
                seasonal_variation = 10 * np.sin((day_of_year - 81) * 2 * np.pi / 365)

                temperature = base_temp + daily_variation + seasonal_variation
                humidity = 60 + 20 * np.sin(hour_of_day * np.pi / 24)

                data.append(
                    {
                        "timestamp": ts,
                        "location": location.name,
                        "temperature_c": temperature,
                        "temperature": temperature,
                        "feels_like_c": temperature - 2,
                        "humidity_pct": humidity,
                        "humidity": humidity,
                        "pressure_hpa": 1013,
                        "wind_speed_ms": 3.5,
                        "wind_direction_deg": 180,
                        "cloudiness_pct": 30,
                        "weather_main": "Clear",
                        "weather_description": "clear sky",
                    }
                )

        df = pd.DataFrame(data)
        logger.info(f"Generated {len(df)} simulated weather records")
        return df

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate simulated data.

        Args:
            data: DataFrame to validate

        Returns:
            True (simulated data is always valid)
        """
        return True
