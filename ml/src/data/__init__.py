"""Data module for SHAKTI-CHAIN V2G platform."""

try:
    from .datamodule import V2GDataModule, TimeSeriesDataset
except ImportError:
    V2GDataModule = None
    TimeSeriesDataset = None

try:
    from .price_datamodule import PriceDataModule, PriceDataset
except ImportError:
    PriceDataModule = None
    PriceDataset = None

__all__ = [
    "V2GDataModule",
    "TimeSeriesDataset",
    "PriceDataModule",
    "PriceDataset",
]
