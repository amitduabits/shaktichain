"""Base collector class for all data sources."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from pydantic import BaseModel, Field


class CollectorConfig(BaseModel):
    """Base configuration for data collectors."""

    enabled: bool = True
    retry_attempts: int = 3
    timeout: int = 30
    cache_dir: Optional[Path] = None


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""

    def __init__(self, config: CollectorConfig):
        """Initialize the collector.

        Args:
            config: Collector configuration
        """
        self.config = config
        self.cache_dir = config.cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def collect(
        self, start_date: datetime, end_date: datetime, **kwargs: Any
    ) -> pd.DataFrame:
        """Collect data from the source.

        Args:
            start_date: Start date for data collection
            end_date: End date for data collection
            **kwargs: Additional parameters specific to the collector

        Returns:
            DataFrame with collected data
        """
        pass

    @abstractmethod
    def validate(self, data: pd.DataFrame) -> bool:
        """Validate collected data.

        Args:
            data: DataFrame to validate

        Returns:
            True if data is valid, False otherwise
        """
        pass

    def save_cache(self, data: pd.DataFrame, filename: str) -> None:
        """Save data to cache.

        Args:
            data: DataFrame to cache
            filename: Cache filename
        """
        if self.cache_dir:
            cache_path = self.cache_dir / filename
            data.to_parquet(cache_path, index=False)

    def load_cache(self, filename: str) -> Optional[pd.DataFrame]:
        """Load data from cache.

        Args:
            filename: Cache filename

        Returns:
            Cached DataFrame or None if not found
        """
        if self.cache_dir:
            cache_path = self.cache_dir / filename
            if cache_path.exists():
                return pd.read_parquet(cache_path)
        return None

    def get_cache_key(self, start_date: datetime, end_date: datetime, **kwargs: Any) -> str:
        """Generate cache key for given parameters.

        Args:
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            Cache key string
        """
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        extra = "_".join(f"{k}_{v}" for k, v in sorted(kwargs.items()))
        key = f"{self.__class__.__name__}_{start_str}_{end_str}"
        if extra:
            key += f"_{extra}"
        return f"{key}.parquet"
