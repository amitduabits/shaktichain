"""
Demand modeling module for V2G Marketplace.

This module provides demand pattern modeling for Indian electricity markets,
including time-of-day, seasonal, and regional variations.
"""

from .india_load import IndiaLoadProfile

__all__ = ["IndiaLoadProfile"]
