"""Tests for data collectors."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors import (
    CalendarCollector,
    CalendarConfig,
    WeatherSimulator,
    WeatherConfig,
    LocationConfig,
)


class TestCalendarCollector:
    """Tests for CalendarCollector."""

    def test_calendar_collector_initialization(self):
        """Test calendar collector initialization."""
        config = CalendarConfig(country="IN")
        collector = CalendarCollector(config)
        assert collector is not None

    def test_calendar_data_collection(self):
        """Test calendar data collection."""
        config = CalendarConfig(country="IN", include_festivals=True)
        collector = CalendarCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        data = collector.collect(start_date, end_date)

        assert len(data) > 0
        assert "timestamp" in data.columns
        assert "is_holiday" in data.columns
        assert "is_weekend" in data.columns
        assert "hour" in data.columns

    def test_calendar_validation(self):
        """Test calendar data validation."""
        config = CalendarConfig(country="IN")
        collector = CalendarCollector(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 7)

        data = collector.collect(start_date, end_date)

        assert collector.validate(data) is True


class TestWeatherSimulator:
    """Tests for WeatherSimulator."""

    def test_weather_simulator_initialization(self):
        """Test weather simulator initialization."""
        config = WeatherConfig(
            locations=[
                LocationConfig(name="Delhi", lat=28.6139, lon=77.2090)
            ]
        )
        simulator = WeatherSimulator(config)
        assert simulator is not None

    def test_weather_simulation(self):
        """Test weather data simulation."""
        config = WeatherConfig(
            locations=[
                LocationConfig(name="Delhi", lat=28.6139, lon=77.2090),
                LocationConfig(name="Mumbai", lat=19.0760, lon=72.8777),
            ]
        )
        simulator = WeatherSimulator(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 7)

        data = simulator.collect(start_date, end_date)

        assert len(data) > 0
        assert "timestamp" in data.columns
        assert "temperature_c" in data.columns
        assert "humidity_pct" in data.columns
        assert "location" in data.columns

    def test_weather_validation(self):
        """Test weather data validation."""
        config = WeatherConfig(
            locations=[LocationConfig(name="Delhi", lat=28.6139, lon=77.2090)]
        )
        simulator = WeatherSimulator(config)

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)

        data = simulator.collect(start_date, end_date)

        assert simulator.validate(data) is True


if __name__ == "__main__":
    pytest.main([__file__])
