"""
Liquidity Metrics for SHAKTI-CHAIN Economic Performance (Domain 2).

Implements market liquidity and quality measures:
- Bid-ask spread
- Market depth
- Order fill rate
- Price volatility (coefficient of variation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Order:
    """Representation of a market order."""
    order_id: str
    agent_id: str
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    timestamp: float
    status: str = "open"  # "open", "filled", "partial", "cancelled"
    filled_quantity: float = 0.0

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.filled_quantity >= self.quantity

    @property
    def fill_rate(self) -> float:
        """Get fill rate for this order."""
        if self.quantity <= 0:
            return 0.0
        return self.filled_quantity / self.quantity


@dataclass
class OrderBookSnapshot:
    """
    Snapshot of order book at a point in time.

    Attributes:
        timestamp: Time of snapshot
        bids: List of (price, quantity) tuples for buy orders (sorted desc by price)
        asks: List of (price, quantity) tuples for sell orders (sorted asc by price)
        best_bid: Best (highest) bid price
        best_ask: Best (lowest) ask price
        mid_price: Mid-point between best bid and ask
        spread: Absolute spread (ask - bid)
        spread_pct: Percentage spread relative to mid-price
    """
    timestamp: float
    bids: List[Tuple[float, float]]  # (price, quantity) pairs
    asks: List[Tuple[float, float]]  # (price, quantity) pairs
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    mid_price: Optional[float] = None
    spread: Optional[float] = None
    spread_pct: Optional[float] = None

    def __post_init__(self):
        """Calculate derived fields."""
        if self.bids and self.best_bid is None:
            self.best_bid = max(p for p, _ in self.bids)
        if self.asks and self.best_ask is None:
            self.best_ask = min(p for p, _ in self.asks)

        if self.best_bid is not None and self.best_ask is not None:
            if self.mid_price is None:
                self.mid_price = (self.best_bid + self.best_ask) / 2
            if self.spread is None:
                self.spread = self.best_ask - self.best_bid
            if self.spread_pct is None and self.mid_price > 0:
                self.spread_pct = self.spread / self.mid_price

    def get_depth(self, levels: int = 5) -> Tuple[float, float]:
        """
        Get total volume within n price levels.

        Returns:
            Tuple of (bid_depth, ask_depth)
        """
        bid_depth = sum(q for _, q in self.bids[:levels]) if self.bids else 0.0
        ask_depth = sum(q for _, q in self.asks[:levels]) if self.asks else 0.0
        return (bid_depth, ask_depth)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "num_bid_levels": len(self.bids),
            "num_ask_levels": len(self.asks),
        }


@dataclass
class SpreadMetrics:
    """
    Bid-ask spread metrics.

    Attributes:
        mean_spread: Average absolute spread
        mean_spread_pct: Average percentage spread
        median_spread_pct: Median percentage spread
        min_spread_pct: Minimum percentage spread
        max_spread_pct: Maximum percentage spread
        std_spread_pct: Standard deviation of percentage spread
        time_weighted_spread: Time-weighted average spread
        effective_spread: Effective spread from executed trades
        quoted_spread_samples: Number of spread samples
    """
    mean_spread: float
    mean_spread_pct: float
    median_spread_pct: float
    min_spread_pct: float
    max_spread_pct: float
    std_spread_pct: float
    time_weighted_spread: float
    effective_spread: Optional[float]
    quoted_spread_samples: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_spread": float(self.mean_spread),
            "mean_spread_pct": float(self.mean_spread_pct),
            "median_spread_pct": float(self.median_spread_pct),
            "min_spread_pct": float(self.min_spread_pct),
            "max_spread_pct": float(self.max_spread_pct),
            "std_spread_pct": float(self.std_spread_pct),
            "time_weighted_spread": float(self.time_weighted_spread),
            "effective_spread": float(self.effective_spread) if self.effective_spread else None,
            "quoted_spread_samples": self.quoted_spread_samples,
        }


@dataclass
class DepthMetrics:
    """
    Market depth metrics.

    Attributes:
        avg_bid_depth: Average bid-side depth
        avg_ask_depth: Average ask-side depth
        total_avg_depth: Average total depth (bid + ask)
        depth_imbalance: Average imbalance (bid - ask) / (bid + ask)
        depth_at_levels: Average depth at each price level
    """
    avg_bid_depth: float
    avg_ask_depth: float
    total_avg_depth: float
    depth_imbalance: float
    depth_at_levels: Dict[int, Tuple[float, float]]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "avg_bid_depth": float(self.avg_bid_depth),
            "avg_ask_depth": float(self.avg_ask_depth),
            "total_avg_depth": float(self.total_avg_depth),
            "depth_imbalance": float(self.depth_imbalance),
            "depth_at_levels": {
                str(k): {"bid": v[0], "ask": v[1]}
                for k, v in self.depth_at_levels.items()
            },
        }


@dataclass
class VolatilityMetrics:
    """
    Price volatility metrics.

    Attributes:
        cv: Coefficient of variation (std / mean)
        std: Standard deviation of prices
        mean: Mean price
        range_pct: (max - min) / mean
        realized_volatility: Annualized realized volatility
        high_volatility_periods: Number of periods with CV > threshold
    """
    cv: float
    std: float
    mean: float
    range_pct: float
    realized_volatility: float
    high_volatility_periods: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cv": float(self.cv),
            "std": float(self.std),
            "mean": float(self.mean),
            "range_pct": float(self.range_pct),
            "realized_volatility": float(self.realized_volatility),
            "high_volatility_periods": self.high_volatility_periods,
        }


def calculate_bid_ask_spread(
    order_book_snapshots: List[OrderBookSnapshot],
    trades: Optional[List[dict]] = None,
) -> SpreadMetrics:
    """
    Calculate bid-ask spread metrics from order book snapshots.

    Spread = (best_ask - best_bid) / mid_price

    Args:
        order_book_snapshots: List of OrderBookSnapshot objects
        trades: Optional list of executed trades for effective spread

    Returns:
        SpreadMetrics with all spread measures
    """
    if not order_book_snapshots:
        return SpreadMetrics(
            mean_spread=0.0,
            mean_spread_pct=0.0,
            median_spread_pct=0.0,
            min_spread_pct=0.0,
            max_spread_pct=0.0,
            std_spread_pct=0.0,
            time_weighted_spread=0.0,
            effective_spread=None,
            quoted_spread_samples=0,
        )

    # Extract valid spread data
    spreads_abs = []
    spreads_pct = []
    timestamps = []

    for snapshot in order_book_snapshots:
        if snapshot.spread is not None and snapshot.spread_pct is not None:
            spreads_abs.append(snapshot.spread)
            spreads_pct.append(snapshot.spread_pct)
            timestamps.append(snapshot.timestamp)

    if not spreads_pct:
        return SpreadMetrics(
            mean_spread=0.0,
            mean_spread_pct=0.0,
            median_spread_pct=0.0,
            min_spread_pct=0.0,
            max_spread_pct=0.0,
            std_spread_pct=0.0,
            time_weighted_spread=0.0,
            effective_spread=None,
            quoted_spread_samples=0,
        )

    spreads_pct_arr = np.array(spreads_pct)
    spreads_abs_arr = np.array(spreads_abs)

    # Time-weighted average spread
    if len(timestamps) > 1:
        durations = np.diff(timestamps)
        # Use spreads at the start of each interval
        time_weighted = np.sum(spreads_pct_arr[:-1] * durations) / np.sum(durations)
    else:
        time_weighted = spreads_pct_arr[0] if len(spreads_pct_arr) > 0 else 0.0

    # Effective spread (from trades)
    effective_spread = None
    if trades:
        effective_spreads = []
        for trade in trades:
            # Find closest snapshot
            trade_time = trade.get("timestamp", 0)
            closest_snapshot = min(
                order_book_snapshots,
                key=lambda s: abs(s.timestamp - trade_time),
                default=None,
            )
            if closest_snapshot and closest_snapshot.mid_price:
                # Effective spread = 2 * |trade_price - mid_price| / mid_price
                eff = 2 * abs(trade["price"] - closest_snapshot.mid_price) / closest_snapshot.mid_price
                effective_spreads.append(eff)

        if effective_spreads:
            effective_spread = float(np.mean(effective_spreads))

    return SpreadMetrics(
        mean_spread=float(np.mean(spreads_abs_arr)),
        mean_spread_pct=float(np.mean(spreads_pct_arr)),
        median_spread_pct=float(np.median(spreads_pct_arr)),
        min_spread_pct=float(np.min(spreads_pct_arr)),
        max_spread_pct=float(np.max(spreads_pct_arr)),
        std_spread_pct=float(np.std(spreads_pct_arr)),
        time_weighted_spread=float(time_weighted),
        effective_spread=effective_spread,
        quoted_spread_samples=len(spreads_pct),
    )


def calculate_fill_rate(
    submitted_orders: List[Order],
    executed_trades: Optional[List[dict]] = None,
) -> float:
    """
    Calculate order fill rate.

    Fill Rate = Number of filled orders / Total submitted orders

    Args:
        submitted_orders: List of Order objects
        executed_trades: Optional list of executed trades

    Returns:
        Fill rate as proportion [0, 1]
    """
    if not submitted_orders:
        return 0.0

    total_orders = len(submitted_orders)
    filled_orders = sum(1 for order in submitted_orders if order.is_filled)

    return float(filled_orders / total_orders)


def calculate_volume_fill_rate(
    submitted_orders: List[Order],
) -> float:
    """
    Calculate volume-weighted fill rate.

    Volume Fill Rate = Total filled volume / Total submitted volume

    Args:
        submitted_orders: List of Order objects

    Returns:
        Volume fill rate as proportion [0, 1]
    """
    if not submitted_orders:
        return 0.0

    total_volume = sum(order.quantity for order in submitted_orders)
    filled_volume = sum(order.filled_quantity for order in submitted_orders)

    if total_volume == 0:
        return 0.0

    return float(filled_volume / total_volume)


def calculate_fill_rate_by_side(
    submitted_orders: List[Order],
) -> Dict[str, float]:
    """
    Calculate fill rate separated by buy/sell side.

    Args:
        submitted_orders: List of Order objects

    Returns:
        Dictionary with 'buy' and 'sell' fill rates
    """
    buy_orders = [o for o in submitted_orders if o.side == "buy"]
    sell_orders = [o for o in submitted_orders if o.side == "sell"]

    buy_fill = calculate_fill_rate(buy_orders) if buy_orders else np.nan
    sell_fill = calculate_fill_rate(sell_orders) if sell_orders else np.nan

    return {
        "buy": float(buy_fill),
        "sell": float(sell_fill),
        "overall": calculate_fill_rate(submitted_orders),
    }


def calculate_market_depth(
    order_book: OrderBookSnapshot,
    price_levels: int = 5,
) -> DepthMetrics:
    """
    Calculate market depth metrics from a single order book snapshot.

    Total volume within n price levels of best bid/ask.

    Args:
        order_book: OrderBookSnapshot object
        price_levels: Number of price levels to consider (default 5)

    Returns:
        DepthMetrics with depth statistics
    """
    bid_depth, ask_depth = order_book.get_depth(price_levels)
    total_depth = bid_depth + ask_depth

    # Depth imbalance
    if total_depth > 0:
        imbalance = (bid_depth - ask_depth) / total_depth
    else:
        imbalance = 0.0

    # Depth at each level
    depth_at_levels = {}
    for level in range(1, price_levels + 1):
        b_depth = sum(q for _, q in order_book.bids[:level]) if order_book.bids else 0.0
        a_depth = sum(q for _, q in order_book.asks[:level]) if order_book.asks else 0.0
        depth_at_levels[level] = (b_depth, a_depth)

    return DepthMetrics(
        avg_bid_depth=bid_depth,
        avg_ask_depth=ask_depth,
        total_avg_depth=total_depth,
        depth_imbalance=imbalance,
        depth_at_levels=depth_at_levels,
    )


def calculate_average_market_depth(
    order_book_snapshots: List[OrderBookSnapshot],
    price_levels: int = 5,
) -> DepthMetrics:
    """
    Calculate average market depth across multiple snapshots.

    Args:
        order_book_snapshots: List of OrderBookSnapshot objects
        price_levels: Number of price levels to consider

    Returns:
        DepthMetrics with average depth statistics
    """
    if not order_book_snapshots:
        return DepthMetrics(
            avg_bid_depth=0.0,
            avg_ask_depth=0.0,
            total_avg_depth=0.0,
            depth_imbalance=0.0,
            depth_at_levels={},
        )

    bid_depths = []
    ask_depths = []
    imbalances = []
    level_depths = {i: ([], []) for i in range(1, price_levels + 1)}

    for snapshot in order_book_snapshots:
        metrics = calculate_market_depth(snapshot, price_levels)
        bid_depths.append(metrics.avg_bid_depth)
        ask_depths.append(metrics.avg_ask_depth)
        imbalances.append(metrics.depth_imbalance)

        for level, (b, a) in metrics.depth_at_levels.items():
            if level in level_depths:
                level_depths[level][0].append(b)
                level_depths[level][1].append(a)

    avg_bid = float(np.mean(bid_depths))
    avg_ask = float(np.mean(ask_depths))

    avg_level_depths = {
        level: (float(np.mean(bids)), float(np.mean(asks)))
        for level, (bids, asks) in level_depths.items()
        if bids  # Only if we have data
    }

    return DepthMetrics(
        avg_bid_depth=avg_bid,
        avg_ask_depth=avg_ask,
        total_avg_depth=avg_bid + avg_ask,
        depth_imbalance=float(np.mean(imbalances)),
        depth_at_levels=avg_level_depths,
    )


def calculate_price_volatility(
    prices: List[float],
    period_length_hours: float = 1.0,
    trading_hours_per_day: float = 24.0,
    high_volatility_threshold: float = 0.15,
) -> VolatilityMetrics:
    """
    Calculate price volatility metrics.

    Coefficient of Variation (CV) = std / mean

    Args:
        prices: List of price observations
        period_length_hours: Length of each observation period in hours
        trading_hours_per_day: Trading hours per day for annualization
        high_volatility_threshold: CV threshold for "high volatility"

    Returns:
        VolatilityMetrics with volatility statistics
    """
    if not prices or len(prices) < 2:
        return VolatilityMetrics(
            cv=0.0,
            std=0.0,
            mean=0.0 if not prices else prices[0],
            range_pct=0.0,
            realized_volatility=0.0,
            high_volatility_periods=0,
        )

    prices_arr = np.array(prices)

    mean_price = float(np.mean(prices_arr))
    std_price = float(np.std(prices_arr, ddof=1))

    # Coefficient of variation
    cv = std_price / mean_price if mean_price > 0 else 0.0

    # Range as percentage
    range_pct = (np.max(prices_arr) - np.min(prices_arr)) / mean_price if mean_price > 0 else 0.0

    # Realized volatility (annualized)
    # Based on log returns
    log_returns = np.diff(np.log(prices_arr))
    if len(log_returns) > 0:
        # Annualization factor
        periods_per_day = trading_hours_per_day / period_length_hours
        periods_per_year = periods_per_day * 365
        realized_vol = float(np.std(log_returns) * np.sqrt(periods_per_year))
    else:
        realized_vol = 0.0

    # Count high volatility periods (rolling windows)
    window_size = max(10, len(prices) // 10)  # 10% of data as window
    high_vol_count = 0

    if len(prices) >= window_size:
        for i in range(len(prices) - window_size + 1):
            window = prices_arr[i:i + window_size]
            window_cv = np.std(window) / np.mean(window) if np.mean(window) > 0 else 0
            if window_cv > high_volatility_threshold:
                high_vol_count += 1

    return VolatilityMetrics(
        cv=float(cv),
        std=std_price,
        mean=mean_price,
        range_pct=float(range_pct),
        realized_volatility=realized_vol,
        high_volatility_periods=high_vol_count,
    )


def bootstrap_cv_ci(
    prices: List[float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    random_state: Optional[int] = None,
) -> Tuple[float, float]:
    """
    Calculate bootstrap confidence interval for coefficient of variation.

    Args:
        prices: List of prices
        n_bootstrap: Number of bootstrap iterations
        confidence: Confidence level
        random_state: Random seed

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if len(prices) < 2:
        return (0.0, 0.0)

    prices_arr = np.array(prices)

    if random_state is not None:
        np.random.seed(random_state)

    bootstrap_cvs = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        resample = np.random.choice(prices_arr, size=len(prices_arr), replace=True)
        mean_r = np.mean(resample)
        std_r = np.std(resample, ddof=1)
        bootstrap_cvs[i] = std_r / mean_r if mean_r > 0 else 0.0

    alpha = 1 - confidence
    lower = np.percentile(bootstrap_cvs, 100 * alpha / 2)
    upper = np.percentile(bootstrap_cvs, 100 * (1 - alpha / 2))

    return (float(lower), float(upper))


def calculate_amihud_illiquidity(
    returns: List[float],
    volumes: List[float],
) -> float:
    """
    Calculate Amihud illiquidity ratio.

    ILLIQ = (1/N) * SUM |return_i| / volume_i

    Higher values indicate less liquid markets.

    Args:
        returns: List of returns (price changes)
        volumes: List of trading volumes

    Returns:
        Amihud illiquidity ratio
    """
    if not returns or not volumes or len(returns) != len(volumes):
        return np.nan

    illiq_values = []
    for ret, vol in zip(returns, volumes):
        if vol > 0:
            illiq_values.append(abs(ret) / vol)

    if not illiq_values:
        return np.nan

    return float(np.mean(illiq_values))


def calculate_turnover_ratio(
    total_traded_volume: float,
    average_outstanding_volume: float,
) -> float:
    """
    Calculate turnover ratio.

    Turnover = Total traded volume / Average outstanding volume

    Args:
        total_traded_volume: Total volume traded in period
        average_outstanding_volume: Average volume available

    Returns:
        Turnover ratio
    """
    if average_outstanding_volume <= 0:
        return np.nan

    return float(total_traded_volume / average_outstanding_volume)


@dataclass
class LiquidityMetrics:
    """Combined liquidity metrics."""
    spread_metrics: SpreadMetrics
    depth_metrics: DepthMetrics
    fill_rate: float
    volume_fill_rate: float
    volatility_metrics: VolatilityMetrics
    amihud_illiquidity: float
    turnover_ratio: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "spread": self.spread_metrics.to_dict(),
            "depth": self.depth_metrics.to_dict(),
            "fill_rate": float(self.fill_rate),
            "volume_fill_rate": float(self.volume_fill_rate),
            "volatility": self.volatility_metrics.to_dict(),
            "amihud_illiquidity": float(self.amihud_illiquidity) if not np.isnan(self.amihud_illiquidity) else None,
            "turnover_ratio": float(self.turnover_ratio) if not np.isnan(self.turnover_ratio) else None,
        }


def calculate_all_liquidity_metrics(
    order_book_snapshots: List[OrderBookSnapshot],
    submitted_orders: List[Order],
    trades: List[dict],
    prices: List[float],
    total_traded_volume: float,
    average_outstanding_volume: float,
) -> LiquidityMetrics:
    """
    Calculate comprehensive liquidity metrics.

    Args:
        order_book_snapshots: List of order book snapshots
        submitted_orders: List of submitted orders
        trades: List of executed trades
        prices: List of observed prices
        total_traded_volume: Total traded volume
        average_outstanding_volume: Average outstanding volume

    Returns:
        LiquidityMetrics with all measures
    """
    spread_metrics = calculate_bid_ask_spread(order_book_snapshots, trades)
    depth_metrics = calculate_average_market_depth(order_book_snapshots)
    fill_rate = calculate_fill_rate(submitted_orders)
    volume_fill_rate = calculate_volume_fill_rate(submitted_orders)
    volatility_metrics = calculate_price_volatility(prices)

    # Calculate returns for Amihud
    if len(prices) > 1:
        returns = list(np.diff(prices) / np.array(prices[:-1]))
        volumes = [t.get("quantity", 0) for t in trades[:len(returns)]]
        amihud = calculate_amihud_illiquidity(returns, volumes)
    else:
        amihud = np.nan

    turnover = calculate_turnover_ratio(total_traded_volume, average_outstanding_volume)

    return LiquidityMetrics(
        spread_metrics=spread_metrics,
        depth_metrics=depth_metrics,
        fill_rate=fill_rate,
        volume_fill_rate=volume_fill_rate,
        volatility_metrics=volatility_metrics,
        amihud_illiquidity=amihud,
        turnover_ratio=turnover,
    )
