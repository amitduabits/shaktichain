"""Streaming feature processor for real-time feature computation.

Computes:
- Rolling statistics (1h, 24h, 168h windows)
- VWAP (Volume-Weighted Average Price)
- Price velocity and momentum
- Order book imbalance
- Demand/supply ratio
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import threading

import numpy as np

from .events import Event, EventType, TradeEvent, PriceEvent, GridEvent

logger = logging.getLogger(__name__)


class FeatureWindow(Enum):
    """Time windows for rolling features."""
    MINUTE_1 = 60
    MINUTE_5 = 300
    MINUTE_15 = 900
    HOUR_1 = 3600
    HOUR_4 = 14400
    HOUR_24 = 86400
    HOUR_168 = 604800  # 1 week


@dataclass
class RollingStatistics:
    """Rolling statistics for a numeric series."""
    window_seconds: int
    values: deque = field(default_factory=deque)
    timestamps: deque = field(default_factory=deque)

    # Cached statistics
    _sum: float = 0.0
    _sum_sq: float = 0.0
    _count: int = 0
    _min: float = float('inf')
    _max: float = float('-inf')

    def add(self, value: float, timestamp: Optional[datetime] = None):
        """Add a value to the rolling window."""
        if timestamp is None:
            timestamp = datetime.now()

        # Add new value
        self.values.append(value)
        self.timestamps.append(timestamp)
        self._sum += value
        self._sum_sq += value ** 2
        self._count += 1
        self._min = min(self._min, value)
        self._max = max(self._max, value)

        # Remove old values
        self._evict_old(timestamp)

    def _evict_old(self, current_time: datetime):
        """Remove values outside the window."""
        cutoff = current_time - timedelta(seconds=self.window_seconds)

        while self.timestamps and self.timestamps[0] < cutoff:
            old_value = self.values.popleft()
            self.timestamps.popleft()
            self._sum -= old_value
            self._sum_sq -= old_value ** 2
            self._count -= 1

        # Recalculate min/max if needed (expensive, do periodically)
        if self._count > 0 and len(self.values) < self._count * 0.5:
            self._recalculate_minmax()

    def _recalculate_minmax(self):
        """Recalculate min/max from scratch."""
        if self.values:
            self._min = min(self.values)
            self._max = max(self.values)
        else:
            self._min = float('inf')
            self._max = float('-inf')

    @property
    def count(self) -> int:
        return self._count

    @property
    def sum(self) -> float:
        return self._sum

    @property
    def mean(self) -> float:
        if self._count == 0:
            return 0.0
        return self._sum / self._count

    @property
    def variance(self) -> float:
        if self._count < 2:
            return 0.0
        mean = self.mean
        return (self._sum_sq / self._count) - (mean ** 2)

    @property
    def std(self) -> float:
        return np.sqrt(max(0, self.variance))

    @property
    def min(self) -> float:
        return self._min if self._count > 0 else 0.0

    @property
    def max(self) -> float:
        return self._max if self._count > 0 else 0.0

    @property
    def range(self) -> float:
        if self._count == 0:
            return 0.0
        return self._max - self._min

    def percentile(self, p: float) -> float:
        """Calculate percentile (0-100)."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        idx = int(len(sorted_values) * p / 100)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    def to_dict(self) -> Dict[str, float]:
        """Export statistics as dictionary."""
        return {
            'count': self.count,
            'sum': self.sum,
            'mean': self.mean,
            'std': self.std,
            'min': self.min,
            'max': self.max,
            'range': self.range,
            'p25': self.percentile(25),
            'p50': self.percentile(50),
            'p75': self.percentile(75),
        }


@dataclass
class VWAPCalculator:
    """Volume-Weighted Average Price calculator."""
    window_seconds: int
    prices: deque = field(default_factory=deque)
    volumes: deque = field(default_factory=deque)
    timestamps: deque = field(default_factory=deque)

    _sum_pv: float = 0.0  # Sum of price * volume
    _sum_v: float = 0.0   # Sum of volume

    def add(self, price: float, volume: float, timestamp: Optional[datetime] = None):
        """Add a trade to VWAP calculation."""
        if timestamp is None:
            timestamp = datetime.now()

        self.prices.append(price)
        self.volumes.append(volume)
        self.timestamps.append(timestamp)
        self._sum_pv += price * volume
        self._sum_v += volume

        self._evict_old(timestamp)

    def _evict_old(self, current_time: datetime):
        """Remove old entries."""
        cutoff = current_time - timedelta(seconds=self.window_seconds)

        while self.timestamps and self.timestamps[0] < cutoff:
            old_price = self.prices.popleft()
            old_volume = self.volumes.popleft()
            self.timestamps.popleft()
            self._sum_pv -= old_price * old_volume
            self._sum_v -= old_volume

    @property
    def vwap(self) -> float:
        """Calculate VWAP."""
        if self._sum_v == 0:
            return 0.0
        return self._sum_pv / self._sum_v

    @property
    def total_volume(self) -> float:
        return self._sum_v

    @property
    def trade_count(self) -> int:
        return len(self.prices)


@dataclass
class OrderBookImbalance:
    """Track order book imbalance."""
    window_seconds: int
    buy_volumes: deque = field(default_factory=deque)
    sell_volumes: deque = field(default_factory=deque)
    timestamps: deque = field(default_factory=deque)

    _sum_buy: float = 0.0
    _sum_sell: float = 0.0

    def add_order(
        self,
        side: str,
        volume: float,
        timestamp: Optional[datetime] = None,
    ):
        """Add an order to tracking."""
        if timestamp is None:
            timestamp = datetime.now()

        self.timestamps.append(timestamp)

        if side.lower() == 'buy':
            self.buy_volumes.append(volume)
            self.sell_volumes.append(0)
            self._sum_buy += volume
        else:
            self.buy_volumes.append(0)
            self.sell_volumes.append(volume)
            self._sum_sell += volume

        self._evict_old(timestamp)

    def _evict_old(self, current_time: datetime):
        """Remove old entries."""
        cutoff = current_time - timedelta(seconds=self.window_seconds)

        while self.timestamps and self.timestamps[0] < cutoff:
            old_buy = self.buy_volumes.popleft()
            old_sell = self.sell_volumes.popleft()
            self.timestamps.popleft()
            self._sum_buy -= old_buy
            self._sum_sell -= old_sell

    @property
    def imbalance(self) -> float:
        """Calculate imbalance ratio (-1 to 1)."""
        total = self._sum_buy + self._sum_sell
        if total == 0:
            return 0.0
        return (self._sum_buy - self._sum_sell) / total

    @property
    def buy_pressure(self) -> float:
        """Calculate buy pressure (0 to 1)."""
        total = self._sum_buy + self._sum_sell
        if total == 0:
            return 0.5
        return self._sum_buy / total


class StreamingFeatureProcessor:
    """Process events and compute streaming features."""

    def __init__(self):
        """Initialize processor with feature windows."""
        # Price statistics for different windows
        self.price_stats: Dict[str, Dict[int, RollingStatistics]] = {}

        # VWAP calculators
        self.vwap_calculators: Dict[str, Dict[int, VWAPCalculator]] = {}

        # Order book imbalance
        self.order_imbalance: Dict[str, OrderBookImbalance] = {}

        # Grid metrics
        self.grid_load_stats: Dict[int, RollingStatistics] = {}
        self.grid_frequency_stats: Dict[int, RollingStatistics] = {}

        # Demand/supply tracking
        self.demand_stats: Dict[int, RollingStatistics] = {}
        self.supply_stats: Dict[int, RollingStatistics] = {}

        # Price velocity (rate of change)
        self.last_prices: Dict[str, List[Tuple[datetime, float]]] = {}

        # Event handlers
        self._handlers: Dict[EventType, List[Callable]] = {}

        # Statistics
        self._events_processed = 0
        self._last_update = datetime.now()

        # Initialize windows
        self._init_windows()

    def _init_windows(self):
        """Initialize rolling windows for all metrics."""
        windows = [
            FeatureWindow.MINUTE_5.value,
            FeatureWindow.HOUR_1.value,
            FeatureWindow.HOUR_24.value,
            FeatureWindow.HOUR_168.value,
        ]

        # Initialize for each market
        for market in ['spot', 'day_ahead', 'default']:
            self.price_stats[market] = {}
            self.vwap_calculators[market] = {}

            for window in windows:
                self.price_stats[market][window] = RollingStatistics(window_seconds=window)
                self.vwap_calculators[market][window] = VWAPCalculator(window_seconds=window)

            self.order_imbalance[market] = OrderBookImbalance(
                window_seconds=FeatureWindow.HOUR_1.value
            )

        # Grid metrics
        for window in windows:
            self.grid_load_stats[window] = RollingStatistics(window_seconds=window)
            self.grid_frequency_stats[window] = RollingStatistics(window_seconds=window)
            self.demand_stats[window] = RollingStatistics(window_seconds=window)
            self.supply_stats[window] = RollingStatistics(window_seconds=window)

    def register_handler(self, event_type: EventType, handler: Callable):
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def process_event(self, event: Event) -> Dict[str, Any]:
        """Process an event and update features.

        Args:
            event: Event to process

        Returns:
            Updated features
        """
        self._events_processed += 1
        self._last_update = datetime.now()

        # Dispatch to appropriate handler
        if event.event_type == EventType.TRADE_EXECUTED:
            features = await self._process_trade(event)
        elif event.event_type == EventType.PRICE_UPDATED:
            features = await self._process_price(event)
        elif event.event_type in [EventType.GRID_LOAD, EventType.GRID_FREQUENCY]:
            features = await self._process_grid(event)
        elif event.event_type in [EventType.ORDER_PLACED, EventType.ORDER_CANCELLED]:
            features = await self._process_order(event)
        else:
            features = {}

        # Call registered handlers
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    await handler(event, features)
                except Exception as e:
                    logger.error(f"Handler error: {e}")

        return features

    async def _process_trade(self, event: TradeEvent) -> Dict[str, Any]:
        """Process trade event."""
        market = getattr(event, 'trade_type', 'spot')
        if market not in self.price_stats:
            market = 'default'

        price = event.price
        volume = event.quantity
        timestamp = event.timestamp

        # Update price statistics
        for window, stats in self.price_stats[market].items():
            stats.add(price, timestamp)

        # Update VWAP
        for window, vwap in self.vwap_calculators[market].items():
            vwap.add(price, volume, timestamp)

        # Track for velocity
        if market not in self.last_prices:
            self.last_prices[market] = []
        self.last_prices[market].append((timestamp, price))
        # Keep last 100 prices
        self.last_prices[market] = self.last_prices[market][-100:]

        # Update demand/supply
        energy = event.energy_kwh
        for window, stats in self.demand_stats.items():
            stats.add(energy, timestamp)

        return self._get_trade_features(market)

    async def _process_price(self, event: PriceEvent) -> Dict[str, Any]:
        """Process price update event."""
        market = event.market
        if market not in self.price_stats:
            market = 'default'

        price = event.price
        timestamp = event.timestamp

        # Update statistics (no volume for pure price updates)
        for window, stats in self.price_stats[market].items():
            stats.add(price, timestamp)

        # Track bid-ask spread
        if event.bid_price and event.ask_price:
            spread = event.ask_price - event.bid_price
            # Could track spread statistics here

        return self._get_price_features(market)

    async def _process_grid(self, event: GridEvent) -> Dict[str, Any]:
        """Process grid event."""
        timestamp = event.timestamp

        if event.event_type == EventType.GRID_LOAD:
            value = event.total_load_mw or event.value
            for window, stats in self.grid_load_stats.items():
                stats.add(value, timestamp)

        elif event.event_type == EventType.GRID_FREQUENCY:
            value = event.frequency_hz or event.value
            for window, stats in self.grid_frequency_stats.items():
                stats.add(value, timestamp)

        return self._get_grid_features()

    async def _process_order(self, event: Event) -> Dict[str, Any]:
        """Process order event."""
        # Extract order details from raw data
        raw = event.raw_data or {}
        side = raw.get('side', 'buy')
        volume = float(raw.get('quantity', 0))
        market = raw.get('market', 'spot')

        if market not in self.order_imbalance:
            market = 'default'

        self.order_imbalance[market].add_order(side, volume, event.timestamp)

        return self._get_order_features(market)

    def _get_trade_features(self, market: str) -> Dict[str, Any]:
        """Get all trade-related features."""
        features = {}

        # Price statistics for each window
        for window, stats in self.price_stats.get(market, {}).items():
            window_name = self._window_name(window)
            features[f'price_{window_name}_mean'] = stats.mean
            features[f'price_{window_name}_std'] = stats.std
            features[f'price_{window_name}_min'] = stats.min
            features[f'price_{window_name}_max'] = stats.max
            features[f'price_{window_name}_range'] = stats.range
            features[f'price_{window_name}_count'] = stats.count

        # VWAP for each window
        for window, vwap in self.vwap_calculators.get(market, {}).items():
            window_name = self._window_name(window)
            features[f'vwap_{window_name}'] = vwap.vwap
            features[f'volume_{window_name}'] = vwap.total_volume
            features[f'trades_{window_name}'] = vwap.trade_count

        # Price velocity
        features.update(self._calculate_price_velocity(market))

        # Order book imbalance
        if market in self.order_imbalance:
            imbalance = self.order_imbalance[market]
            features['order_imbalance'] = imbalance.imbalance
            features['buy_pressure'] = imbalance.buy_pressure

        features['market'] = market
        features['timestamp'] = datetime.now().isoformat()

        return features

    def _get_price_features(self, market: str) -> Dict[str, Any]:
        """Get price-specific features."""
        features = self._get_trade_features(market)
        features['feature_type'] = 'price'
        return features

    def _get_grid_features(self) -> Dict[str, Any]:
        """Get grid-related features."""
        features = {}

        # Load statistics
        for window, stats in self.grid_load_stats.items():
            window_name = self._window_name(window)
            features[f'load_{window_name}_mean'] = stats.mean
            features[f'load_{window_name}_std'] = stats.std
            features[f'load_{window_name}_min'] = stats.min
            features[f'load_{window_name}_max'] = stats.max

        # Frequency statistics
        for window, stats in self.grid_frequency_stats.items():
            window_name = self._window_name(window)
            features[f'frequency_{window_name}_mean'] = stats.mean
            features[f'frequency_{window_name}_deviation'] = abs(stats.mean - 50.0)

        # Demand/supply ratio
        for window in self.demand_stats.keys():
            demand = self.demand_stats[window].sum
            supply = self.supply_stats[window].sum
            window_name = self._window_name(window)

            if supply > 0:
                features[f'demand_supply_ratio_{window_name}'] = demand / supply
            else:
                features[f'demand_supply_ratio_{window_name}'] = 1.0

        features['feature_type'] = 'grid'
        features['timestamp'] = datetime.now().isoformat()

        return features

    def _get_order_features(self, market: str) -> Dict[str, Any]:
        """Get order book features."""
        features = {}

        if market in self.order_imbalance:
            imbalance = self.order_imbalance[market]
            features['order_imbalance'] = imbalance.imbalance
            features['buy_pressure'] = imbalance.buy_pressure

        features['market'] = market
        features['feature_type'] = 'order'
        features['timestamp'] = datetime.now().isoformat()

        return features

    def _calculate_price_velocity(self, market: str) -> Dict[str, float]:
        """Calculate price rate of change."""
        prices = self.last_prices.get(market, [])

        if len(prices) < 2:
            return {
                'price_velocity_1m': 0.0,
                'price_velocity_5m': 0.0,
                'price_momentum': 0.0,
            }

        now = datetime.now()
        velocities = {}

        # 1-minute velocity
        recent_1m = [p for t, p in prices if (now - t).total_seconds() < 60]
        if len(recent_1m) >= 2:
            velocities['price_velocity_1m'] = (recent_1m[-1] - recent_1m[0]) / recent_1m[0]
        else:
            velocities['price_velocity_1m'] = 0.0

        # 5-minute velocity
        recent_5m = [p for t, p in prices if (now - t).total_seconds() < 300]
        if len(recent_5m) >= 2:
            velocities['price_velocity_5m'] = (recent_5m[-1] - recent_5m[0]) / recent_5m[0]
        else:
            velocities['price_velocity_5m'] = 0.0

        # Momentum (acceleration)
        if len(prices) >= 10:
            first_half = [p for _, p in prices[:len(prices)//2]]
            second_half = [p for _, p in prices[len(prices)//2:]]
            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                velocities['price_momentum'] = (second_avg - first_avg) / (first_avg + 1e-8)
            else:
                velocities['price_momentum'] = 0.0
        else:
            velocities['price_momentum'] = 0.0

        return velocities

    def _window_name(self, seconds: int) -> str:
        """Convert seconds to human-readable window name."""
        if seconds <= 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"

    def get_all_features(self) -> Dict[str, Any]:
        """Get all current features."""
        features = {}

        # Trade/price features for each market
        for market in self.price_stats.keys():
            market_features = self._get_trade_features(market)
            for key, value in market_features.items():
                features[f'{market}_{key}'] = value

        # Grid features
        grid_features = self._get_grid_features()
        features.update(grid_features)

        # Metadata
        features['events_processed'] = self._events_processed
        features['last_update'] = self._last_update.isoformat()

        return features

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'events_processed': self._events_processed,
            'last_update': self._last_update.isoformat(),
            'markets_tracked': list(self.price_stats.keys()),
            'windows': [self._window_name(w) for w in self.grid_load_stats.keys()],
        }
