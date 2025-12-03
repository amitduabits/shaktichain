"""Baseline trading strategies for comparison.

Implements:
- Rule-based: Sell peak, buy off-peak
- Threshold: Price threshold based
- Random: Random valid actions
- Oracle: Perfect foresight (upper bound)
- Momentum: Trend following
- Mean Reversion: Buy low, sell high
"""

import numpy as np
from typing import Dict, Any, Optional, List, Tuple, Union
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def __call__(self, state: Dict[str, Any]) -> Union[np.ndarray, Tuple[float, float]]:
        """Generate action from state.

        Args:
            state: Current state dictionary

        Returns:
            Action tuple (quantity_normalized, price_aggressiveness)
        """
        pass

    def reset(self):
        """Reset any internal state."""
        pass


class RuleBasedStrategy(BaseStrategy):
    """Simple rule-based strategy: Sell during peak, buy during off-peak.

    Peak hours: 18-22 (evening peak in India)
    Off-peak hours: 0-6 (night)
    """

    def __init__(
        self,
        peak_hours: List[int] = None,
        offpeak_hours: List[int] = None,
        charge_soc_threshold: float = 0.8,
        discharge_soc_threshold: float = 0.4,
        trade_size: float = 0.7,
    ):
        super().__init__("Rule-Based (Peak Arbitrage)")
        self.peak_hours = peak_hours or [18, 19, 20, 21, 22]
        self.offpeak_hours = offpeak_hours or [0, 1, 2, 3, 4, 5, 6]
        self.charge_threshold = charge_soc_threshold
        self.discharge_threshold = discharge_soc_threshold
        self.trade_size = trade_size

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        hour = state.get('hour', 12)
        soc = state.get('soc', 0.5)

        # Off-peak: charge if SOC below threshold
        if hour in self.offpeak_hours and soc < self.charge_threshold:
            return (self.trade_size, 0.5)

        # Peak: discharge if SOC above threshold
        elif hour in self.peak_hours and soc > self.discharge_threshold:
            return (-self.trade_size, 0.6)

        # Otherwise hold
        return (0.0, 0.5)


class ThresholdStrategy(BaseStrategy):
    """Price threshold strategy: Buy when price low, sell when high."""

    def __init__(
        self,
        buy_threshold_pct: float = 0.85,  # Buy when price < 85% of avg
        sell_threshold_pct: float = 1.15,  # Sell when price > 115% of avg
        avg_price: float = 5.0,
        soc_min: float = 0.3,
        soc_max: float = 0.8,
        trade_size: float = 0.6,
    ):
        super().__init__("Threshold")
        self.buy_threshold = buy_threshold_pct
        self.sell_threshold = sell_threshold_pct
        self.avg_price = avg_price
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.trade_size = trade_size

        # Running price estimate
        self.prices = []
        self.window = 24  # 24 hours

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        price = state.get('price', self.avg_price)
        soc = state.get('soc', 0.5)

        # Update price history
        self.prices.append(price)
        if len(self.prices) > self.window:
            self.prices = self.prices[-self.window:]

        # Calculate dynamic threshold
        avg_price = np.mean(self.prices) if self.prices else self.avg_price

        # Buy signal
        if price < avg_price * self.buy_threshold and soc < self.soc_max:
            return (self.trade_size, 0.5)

        # Sell signal
        elif price > avg_price * self.sell_threshold and soc > self.soc_min:
            return (-self.trade_size, 0.5)

        return (0.0, 0.5)

    def reset(self):
        self.prices = []


class RandomStrategy(BaseStrategy):
    """Random trading strategy for baseline comparison."""

    def __init__(
        self,
        action_probability: float = 0.3,  # Probability of taking action
        seed: Optional[int] = None,
    ):
        super().__init__("Random")
        self.action_prob = action_probability
        self.rng = np.random.default_rng(seed)

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        if self.rng.random() > self.action_prob:
            return (0.0, 0.5)  # Hold

        # Random action
        quantity = self.rng.uniform(-1, 1)
        aggressiveness = self.rng.uniform(0.3, 0.7)

        return (quantity, aggressiveness)


class OracleStrategy(BaseStrategy):
    """Oracle strategy with perfect foresight.

    Uses future price information to make optimal decisions.
    This represents the theoretical upper bound of performance.
    """

    def __init__(
        self,
        price_forecast: List[float],
        lookahead: int = 24,
        soc_min: float = 0.25,
        soc_max: float = 0.9,
    ):
        super().__init__("Oracle (Perfect Foresight)")
        self.price_forecast = price_forecast
        self.lookahead = lookahead
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.current_idx = 0

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        soc = state.get('soc', 0.5)
        current_price = state.get('price', 5.0)

        # Get future prices
        future_start = self.current_idx + 1
        future_end = min(future_start + self.lookahead, len(self.price_forecast))
        future_prices = self.price_forecast[future_start:future_end]

        self.current_idx += 1

        if len(future_prices) == 0:
            return (0.0, 0.5)

        max_future = max(future_prices)
        min_future = min(future_prices)
        avg_future = np.mean(future_prices)

        # If current price is at/near minimum and SOC low -> buy aggressively
        if current_price <= min_future * 1.02 and soc < self.soc_max:
            return (0.9, 0.7)

        # If current price is at/near maximum and SOC high -> sell aggressively
        if current_price >= max_future * 0.98 and soc > self.soc_min:
            return (-0.9, 0.7)

        # If price significantly below average and SOC allows -> buy
        if current_price < avg_future * 0.9 and soc < self.soc_max - 0.1:
            return (0.6, 0.5)

        # If price significantly above average and SOC allows -> sell
        if current_price > avg_future * 1.1 and soc > self.soc_min + 0.1:
            return (-0.6, 0.5)

        return (0.0, 0.5)

    def reset(self):
        self.current_idx = 0


class MomentumStrategy(BaseStrategy):
    """Momentum/trend following strategy.

    Buy when price is rising, sell when falling.
    """

    def __init__(
        self,
        lookback: int = 6,  # Hours to look back
        momentum_threshold: float = 0.03,  # 3% change threshold
        trade_size: float = 0.5,
    ):
        super().__init__("Momentum")
        self.lookback = lookback
        self.threshold = momentum_threshold
        self.trade_size = trade_size
        self.prices = []

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        price = state.get('price', 5.0)
        soc = state.get('soc', 0.5)

        self.prices.append(price)
        if len(self.prices) > self.lookback:
            self.prices = self.prices[-self.lookback:]

        if len(self.prices) < 2:
            return (0.0, 0.5)

        # Calculate momentum (rate of change)
        momentum = (price - self.prices[0]) / self.prices[0]

        # Strong upward momentum - buy
        if momentum > self.threshold and soc < 0.8:
            return (self.trade_size, 0.5)

        # Strong downward momentum - sell
        elif momentum < -self.threshold and soc > 0.3:
            return (-self.trade_size, 0.5)

        return (0.0, 0.5)

    def reset(self):
        self.prices = []


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy.

    Assumes prices revert to mean - buy when low, sell when high.
    """

    def __init__(
        self,
        window: int = 48,  # 2 days for mean calculation
        std_threshold: float = 1.5,  # Trade when price is X std from mean
        trade_size: float = 0.6,
    ):
        super().__init__("Mean Reversion")
        self.window = window
        self.std_threshold = std_threshold
        self.trade_size = trade_size
        self.prices = []

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        price = state.get('price', 5.0)
        soc = state.get('soc', 0.5)

        self.prices.append(price)
        if len(self.prices) > self.window:
            self.prices = self.prices[-self.window:]

        if len(self.prices) < 10:
            return (0.0, 0.5)

        mean_price = np.mean(self.prices)
        std_price = np.std(self.prices)

        if std_price < 0.01:
            return (0.0, 0.5)

        z_score = (price - mean_price) / std_price

        # Price significantly below mean - expect reversion up - buy
        if z_score < -self.std_threshold and soc < 0.8:
            return (self.trade_size, 0.5)

        # Price significantly above mean - expect reversion down - sell
        elif z_score > self.std_threshold and soc > 0.3:
            return (-self.trade_size, 0.5)

        return (0.0, 0.5)

    def reset(self):
        self.prices = []


class BuyAndHoldStrategy(BaseStrategy):
    """Buy and hold - charge fully then hold."""

    def __init__(self, target_soc: float = 0.9):
        super().__init__("Buy and Hold")
        self.target_soc = target_soc

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        soc = state.get('soc', 0.5)

        if soc < self.target_soc:
            return (0.8, 0.5)
        return (0.0, 0.5)


class SellAndHoldStrategy(BaseStrategy):
    """Sell and hold - discharge fully then hold."""

    def __init__(self, target_soc: float = 0.25):
        super().__init__("Sell and Hold")
        self.target_soc = target_soc

    def __call__(self, state: Dict[str, Any]) -> Tuple[float, float]:
        soc = state.get('soc', 0.5)

        if soc > self.target_soc:
            return (-0.8, 0.5)
        return (0.0, 0.5)


class AllBaselines:
    """Container for all baseline strategies."""

    def __init__(
        self,
        price_forecast: Optional[List[float]] = None,
        seed: int = 42,
    ):
        """Initialize all baseline strategies.

        Args:
            price_forecast: Price data for Oracle strategy
            seed: Random seed
        """
        self.strategies = {
            'rule_based': RuleBasedStrategy(),
            'threshold': ThresholdStrategy(),
            'random': RandomStrategy(seed=seed),
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'buy_hold': BuyAndHoldStrategy(),
            'sell_hold': SellAndHoldStrategy(),
        }

        if price_forecast is not None:
            self.strategies['oracle'] = OracleStrategy(price_forecast)

    def get_strategy(self, name: str) -> BaseStrategy:
        """Get strategy by name."""
        if name not in self.strategies:
            raise ValueError(f"Unknown strategy: {name}. Available: {list(self.strategies.keys())}")
        return self.strategies[name]

    def get_all(self) -> Dict[str, BaseStrategy]:
        """Get all strategies."""
        return self.strategies

    def reset_all(self):
        """Reset all strategies."""
        for strategy in self.strategies.values():
            strategy.reset()
