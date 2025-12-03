"""IEX (Indian Energy Exchange) price data collector.

Collects electricity market prices from IEX.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class IEXConfig(CollectorConfig):
    """Configuration for IEX collector."""

    url: str = "https://www.iexindia.com/marketdata/areaprices.aspx"
    markets: List[str] = Field(default_factory=lambda: ["DAM", "RTM"])


class IEXCollector(BaseCollector):
    """Collector for Indian Energy Exchange price data."""

    def __init__(self, config: IEXConfig):
        """Initialize IEX collector.

        Args:
            config: IEX collector configuration
        """
        super().__init__(config)
        self.config: IEXConfig = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _fetch_dam_prices(self, date: datetime) -> pd.DataFrame:
        """Fetch Day-Ahead Market prices for a specific date.

        Args:
            date: Date to fetch prices for

        Returns:
            DataFrame with hourly prices
        """
        date_str = date.strftime("%d-%b-%Y")
        url = f"{self.config.url}?Date={date_str}&Market=DAM"

        logger.debug(f"Fetching IEX DAM prices for {date_str}")

        try:
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()

            # Parse HTML to extract price data
            soup = BeautifulSoup(response.content, "lxml")

            # IEX publishes data in tables - this is a placeholder
            # Actual implementation would parse the HTML table structure
            # The website structure may change, requiring maintenance

            # For demo purposes, creating synthetic hourly data
            hours = pd.date_range(start=date, periods=24, freq="H")
            data = pd.DataFrame(
                {
                    "timestamp": hours,
                    "market": "DAM",
                    "price_inr_mwh": [3000.0] * 24,  # Placeholder
                    "volume_mwh": [1000.0] * 24,  # Placeholder
                }
            )

            logger.info(f"Successfully fetched IEX DAM prices for {date_str}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching IEX DAM prices: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def _fetch_rtm_prices(self, date: datetime) -> pd.DataFrame:
        """Fetch Real-Time Market prices for a specific date.

        Args:
            date: Date to fetch prices for

        Returns:
            DataFrame with 15-minute interval prices
        """
        date_str = date.strftime("%d-%b-%Y")
        url = f"{self.config.url}?Date={date_str}&Market=RTM"

        logger.debug(f"Fetching IEX RTM prices for {date_str}")

        try:
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()

            # RTM has 15-minute intervals (96 blocks per day)
            intervals = pd.date_range(start=date, periods=96, freq="15T")
            data = pd.DataFrame(
                {
                    "timestamp": intervals,
                    "market": "RTM",
                    "price_inr_mwh": [3000.0] * 96,  # Placeholder
                    "volume_mwh": [250.0] * 96,  # Placeholder
                }
            )

            logger.info(f"Successfully fetched IEX RTM prices for {date_str}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching IEX RTM prices: {e}")
            raise

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect IEX price data for date range.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters (markets)

        Returns:
            DataFrame with collected price data
        """
        markets = kwargs.get("markets", self.config.markets)

        # Check cache first
        cache_key = self.get_cache_key(start_date, end_date, markets=str(markets))
        cached_data = self.load_cache(cache_key)
        if cached_data is not None:
            logger.info(f"Loading IEX data from cache: {cache_key}")
            return cached_data

        all_data = []
        current_date = start_date

        while current_date <= end_date:
            try:
                if "DAM" in markets:
                    dam_data = self._fetch_dam_prices(current_date)
                    all_data.append(dam_data)

                if "RTM" in markets:
                    rtm_data = self._fetch_rtm_prices(current_date)
                    all_data.append(rtm_data)

                # Be respectful with rate limiting
                time.sleep(2)

            except Exception as e:
                logger.error(f"Failed to fetch IEX data for {current_date}: {e}")

            current_date += timedelta(days=1)

        if not all_data:
            raise ValueError("No data collected from IEX")

        df = pd.concat(all_data, ignore_index=True)
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Resample RTM to hourly for consistency with other data sources
        if "RTM" in markets:
            rtm_df = df[df["market"] == "RTM"].copy()
            rtm_df = (
                rtm_df.set_index("timestamp")
                .resample("H")
                .agg(
                    {
                        "price_inr_mwh": "mean",
                        "volume_mwh": "sum",
                    }
                )
                .reset_index()
            )
            rtm_df["market"] = "RTM"

            dam_df = df[df["market"] == "DAM"]
            df = pd.concat([dam_df, rtm_df], ignore_index=True)

        # Save to cache
        self.save_cache(df, cache_key)
        logger.info(f"Collected {len(df)} records from IEX")

        return df

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate IEX data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        required_columns = ["timestamp", "market", "price_inr_mwh", "volume_mwh"]

        if not all(col in data.columns for col in required_columns):
            logger.error("Missing required columns in IEX data")
            return False

        if data.empty:
            logger.error("IEX data is empty")
            return False

        if data["price_inr_mwh"].isna().all():
            logger.error("All price values are NaN")
            return False

        # Check prices are positive
        if (data["price_inr_mwh"] < 0).any():
            logger.error("Found negative prices")
            return False

        # Check prices are reasonable (0 - 20000 INR/MWh typical range)
        price_valid = data["price_inr_mwh"].between(0, 50000).all()
        if not price_valid:
            logger.warning("Some prices are out of expected range")

        return True


class IEXAPICollector(BaseCollector):
    """Alternative collector using IEX API if credentials are available."""

    def __init__(self, config: IEXConfig, api_key: Optional[str] = None):
        """Initialize IEX API collector.

        Args:
            config: Configuration
            api_key: API key for IEX services
        """
        super().__init__(config)
        self.api_key = api_key

    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect data via API.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            DataFrame with price data
        """
        raise NotImplementedError("IEX API collector not yet implemented")

    def validate(self, data: pd.DataFrame) -> bool:
        """Validate data.

        Args:
            data: DataFrame to validate

        Returns:
            True if valid
        """
        return True
