"""
Zero Intelligence Agent - Random bidding agent.

Implements the Zero Intelligence trader from Gode & Sunder (1993).
Two variants:
- ZI-U: Unconstrained (can trade at any price)
- ZI-C: Constrained (respects budget constraints)
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .base_agent import AgentState, BaseAgent, MarketState, TradeSide


class ZeroIntelligenceAgent(BaseAgent):
    """
    Zero Intelligence agent that submits random bids.

    Used as a baseline to measure how much of market efficiency
    comes from the market mechanism versus agent intelligence.
    """

    def __init__(
        self,
        state: AgentState,
        variant: str = "ZI-C",
        bid_probability: float = 0.8,
        price_distribution: str = "uniform",
        price_std_factor: float = 0.2,
    ):
        """
        Initialize the zero intelligence agent.

        Args:
            state: Agent state
            variant: "ZI-C" (constrained) or "ZI-U" (unconstrained)
            bid_probability: Probability of submitting a bid
            price_distribution: "uniform" or "normal"
            price_std_factor: Std dev factor for normal distribution
        """
        super().__init__(state)
        self.state.type = "zero_intelligence"

        self.variant = variant
        self.bid_probability = bid_probability
        self.price_distribution = price_distribution
        self.price_std_factor = price_std_factor

        # Price bounds for unconstrained
        self.global_min_price = 0.5
        self.global_max_price = 20.0

    def generate_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Generate a random bid.

        For ZI-C: Respects budget constraints (no loss trades)
        For ZI-U: Any price within global bounds

        Args:
            market_state: Current market information

        Returns:
            (price, quantity, side) tuple or None
        """
        # Random decision to bid
        if np.random.random() > self.bid_probability:
            return None

        # Decide side based on SoC
        side = self._decide_side_random(market_state)
        if side is None:
            return None

        # Generate random quantity
        quantity = self._generate_random_quantity(side)
        if quantity < 0.1:
            return None

        # Generate random price
        price = self._generate_random_price(side, market_state)
        if price is None:
            return None

        return (round(price, 2), round(quantity, 2), side.value)

    def _decide_side_random(self, market_state: MarketState) -> Optional[TradeSide]:
        """
        Decide trading side.

        Uses SoC-based thresholds with some randomness.
        """
        can_buy = self.state.available_capacity_kwh > 0.1
        can_sell = self.state.available_energy_kwh > 0.1

        if not can_buy and not can_sell:
            return None

        soc = self.state.current_soc

        # SoC-based with thresholds
        if soc < 0.3 and can_buy:
            return TradeSide.BUY
        elif soc > 0.7 and can_sell:
            return TradeSide.SELL
        elif can_buy and can_sell:
            # Random choice weighted by position
            buy_weight = 1 - soc  # Higher SoC -> less likely to buy
            return TradeSide.BUY if np.random.random() < buy_weight else TradeSide.SELL
        elif can_buy:
            return TradeSide.BUY
        else:
            return TradeSide.SELL

    def _generate_random_quantity(self, side: TradeSide) -> float:
        """Generate random quantity."""
        if side == TradeSide.BUY:
            max_qty = self.state.available_capacity_kwh
        else:
            max_qty = self.state.available_energy_kwh

        # Random quantity from exponential distribution (smaller trades more likely)
        mean_qty = max_qty * 0.3
        quantity = np.random.exponential(mean_qty)

        return min(quantity, max_qty)

    def _generate_random_price(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> Optional[float]:
        """
        Generate random price.

        ZI-C: Constrained to profitable range
        ZI-U: Any price in global range
        """
        if self.variant == "ZI-C":
            return self._generate_constrained_price(side, market_state)
        else:
            return self._generate_unconstrained_price(side, market_state)

    def _generate_constrained_price(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> Optional[float]:
        """Generate price respecting budget constraint."""
        if side == TradeSide.BUY:
            # Buyer: price <= value (no overpaying)
            max_price = self.state.value_per_kwh
            min_price = self.global_min_price
        else:
            # Seller: price >= cost (no selling at loss)
            min_price = self.state.cost_per_kwh
            max_price = self.global_max_price

        if min_price >= max_price:
            return None

        if self.price_distribution == "uniform":
            return np.random.uniform(min_price, max_price)
        else:
            # Normal distribution centered on midpoint
            mid = (min_price + max_price) / 2
            std = (max_price - min_price) * self.price_std_factor
            price = np.random.normal(mid, std)
            return max(min_price, min(max_price, price))

    def _generate_unconstrained_price(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> float:
        """Generate any price in global range (ZI-U)."""
        if self.price_distribution == "uniform":
            return np.random.uniform(self.global_min_price, self.global_max_price)
        else:
            mid = (self.global_min_price + self.global_max_price) / 2
            std = (self.global_max_price - self.global_min_price) * self.price_std_factor
            price = np.random.normal(mid, std)
            return max(self.global_min_price, min(self.global_max_price, price))

    def update_after_trade(self, trade_result: dict) -> None:
        """
        Update state after trade.

        ZI agents don't learn, just record.
        """
        self.record_trade(trade_result)

    def update_after_no_trade(self) -> None:
        """ZI agents don't update on no-trade."""
        pass
