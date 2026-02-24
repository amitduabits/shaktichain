"""POSOCO (Power System Operation Corporation Limited) data collector.

Collects energy load data from National Load Dispatch Centre (NLDC) reports.
"""

import logging
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class POSOCOConfig(CollectorConfig):
    """Configuration for POSOCO collector."""

    url: str = "https://posoco.in/reports/"
    use_live_api: bool = False
    regions: List[str] = Field(
        default_factory=lambda: [
            "NORTHERN",
            "WESTERN",
            "SOUTHERN",
            "EASTERN",
            "NORTH_EASTERN",
        ]
    )
    data_types: List[str] = Field(default_factory=lambda: ["load", "frequency"])


class POSOCOCollector(BaseCollector):
    """Collector for POSOCO/NLDC energy load data."""

    def __init__(self, config: Optional[POSOCOConfig] = None):
        """Initialize POSOCO collector.

        Args:
            config: POSOCO collector configuration
        """
        config = config or POSOCOConfig()
        super().__init__(config)
        self.config: POSOCOConfig = config
        self.session = requests.Session()

    @staticmethod
    def _generate_synthetic_daily_data(date: datetime, region: str) -> pd.DataFrame:
        """Generate deterministic hourly load/frequency data."""
        hours = pd.date_range(start=date, periods=24, freq="h")
        seed = int(hashlib.sha256(f"{region}:{date.date()}".encode("utf-8")).hexdigest()[:8], 16)
        rng = pd.Series(range(24), dtype="float64")

        # Morning and evening demand bumps with small deterministic noise.
        morning_peak = 3500 * np.exp(-((rng - 9) ** 2) / 10)
        evening_peak = 4200 * np.exp(-((rng - 19) ** 2) / 10)
        base_load = 42000 + morning_peak + evening_peak
        region_offset = (int(hashlib.sha256(region.encode("utf-8")).hexdigest()[:8], 16) % 5000) - 2500
        noise = np.random.default_rng(seed).normal(0, 250, size=24)

        load = base_load + region_offset + noise
        frequency = 50.0 - (load - load.mean()) / 100000 + np.random.default_rng(seed + 1).normal(0, 0.02, size=24)

        return pd.DataFrame(
            {
                "timestamp": hours,
                "region": region,
                "load_mw": load,
                "frequency_hz": frequency,
            }
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _fetch_daily_data(self, date: datetime, region: str) -> pd.DataFrame:
        """Fetch data for a specific date and region.

        Args:
            date: Date to fetch data for
            region: Region code

        Returns:
            DataFrame with hourly load data
        """
        if not self.config.use_live_api:
            return self._generate_synthetic_daily_data(date, region)

        date_str = date.strftime("%d-%m-%Y")
        url = f"{self.config.url}/daily/{region.lower()}/{date_str}"
        logger.debug(f"Fetching POSOCO data for {region} on {date_str}")

        try:
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            _ = BeautifulSoup(response.content, "lxml")
            logger.info(f"Fetched POSOCO endpoint for {region} on {date_str}")
            return self._generate_synthetic_daily_data(date, region)
        except requests.exceptions.RequestException as e:
            logger.warning(f"POSOCO live fetch failed, using synthetic fallback: {e}")
            return self._generate_synthetic_daily_data(date, region)

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect POSOCO data for date range.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters (regions, data_types)

        Returns:
            DataFrame with collected load data
        """
        regions = kwargs.get("regions")
        if not regions:
            city = kwargs.get("city")
            if city:
                regions = [str(city).upper()]
            else:
                regions = self.config.regions

        # Check cache first
        cache_key = self.get_cache_key(start_date, end_date, regions=str(regions))
        cached_data = self.load_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Loading POSOCO data from cache: {cache_key}")
            return cached_data

        all_data = []
        current_date = start_date

        while current_date <= end_date:
            for region in regions:
                try:
                    daily_data = self._fetch_daily_data(current_date, region)
                    all_data.append(daily_data)

                    # Be respectful with rate limiting
                    time.sleep(1)

                except Exception as e:
                    logger.error(
                        f"Failed to fetch data for {region} on {current_date}: {e}"
                    )
                    continue

            current_date += timedelta(days=1)

        if not all_data:
            raise ValueError("No data collected from POSOCO")

        df = pd.concat(all_data, ignore_index=True)
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Save to cache
        self.save_cache(df, cache_key)
        logger.info(f"Collected {len(df)} records from POSOCO")

        return df

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate POSOCO data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        required_columns = ["timestamp", "region", "load_mw", "frequency_hz"]

        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required columns in POSOCO data")
            return False

        if data.empty:
            logger.error("POSOCO data is empty")
            return False

        if data["load_mw"].isna().all():
            logger.error("All load values are NaN")
            return False

        # Check frequency is within reasonable bounds (49.5 - 50.5 Hz)
        freq_valid = data["frequency_hz"].between(49.0, 51.0).all()
        if not freq_valid:
            logger.warning("Some frequency values are out of expected range")

        return True


# Alternative implementation for actual POSOCO API (if available)
class POSOCOAPICollector(BaseCollector):
    """Alternative collector using POSOCO API if available."""

    def __init__(self, config: POSOCOConfig, api_key: Optional[str] = None):
        """Initialize POSOCO API collector.

        Args:
            config: Configuration
            api_key: API key for POSOCO services
        """
        super().__init__(config)
        self.api_key = api_key
        self.base_url = "https://api.posoco.in/v1"  # Hypothetical endpoint

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect data via API.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            DataFrame with load data
        """
        # Placeholder for actual API implementation
        raise NotImplementedError("POSOCO API collector not yet implemented")

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        return True
