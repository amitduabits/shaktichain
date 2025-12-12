"""
Bounded Rational Agent - Satisficing agent with limited computation.

Implements Herbert Simon's satisficing behavior where the agent
searches for a satisfactory option rather than the optimal one.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .base_agent import AgentState, BaseAgent, MarketState, TradeSide


class BoundedRationalAgent(BaseAgent):
    """
    Bounded rational agent using satisficing behavior.

    Features:
    - Limited search: evaluates k random alternatives
    - Aspiration level: accepts first option meeting threshold
    - Aspiration adaptation: adjusts threshold based on success/failure
    - Simplified decision rules
    """

    def __init__(
        self,
        state: AgentState,
        aspiration_level: float = 0.5,
        max_alternatives: int = 10,
        aspiration_increase_rate: float = 0.05,
        aspiration_decrease_rate: float = 0.1,
        memory_window: int = 20,
    ):
        """
        Initialize the bounded rational agent.

        Args:
            state: Agent state
            aspiration_level: Initial aspiration level [0, 1] relative to max possible utility
            max_alternatives: Maximum number of alternatives to consider
            aspiration_increase_rate: Rate of aspiration increase on success
            aspiration_decrease_rate: Rate of aspiration decrease on failure
            memory_window: Number of past periods to remember
        """
        super().__init__(state)
        self.state.type = "bounded_rational"

        self.aspiration_level = aspiration_level
        self.max_alternatives = max_alternatives
        self.aspiration_increase_rate = aspiration_increase_rate
        self.aspiration_decrease_rate = aspiration_decrease_rate
        self.memory_window = memory_window

        # Limited memory
        self._price_memory: list[float] = []
        self._success_memory: list[bool] = []

    def generate_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Generate a bid using satisficing search.

        The bounded rational agent:
        1. Determines feasible side
        2. Generates k random bid alternatives
        3. Accepts first satisfactory option (above aspiration)
        4. If none found, takes best available

        Args:
            market_state: Current market information

        Returns:
            (price, quantity, side) tuple or None
        """
        # Update memory
        self._update_memory(market_state)

        # Decide side using simple heuristic
        side = self._decide_side_heuristic(market_state)
        if side is None:
            return None

        # Determine quantity using simple rule
        quantity = self._determine_quantity_simple(side)
        if quantity < 0.1:
            return None

        # Generate and evaluate alternatives
        price = self._satisficing_search(side, quantity, market_state)
        if price is None:
            return None

        return (price, quantity, side.value)

    def _update_memory(self, market_state: MarketState) -> None:
        """Update limited memory with recent prices."""
        if market_state.clearing_price is not None:
            self._price_memory.append(market_state.clearing_price)
            if len(self._price_memory) > self.memory_window:
                self._price_memory.pop(0)

    def _decide_side_heuristic(self, market_state: MarketState) -> Optional[TradeSide]:
        """
        Decide trading side using simple heuristics.

        Uses rules of thumb rather than optimization.
        """
        can_buy = self.state.available_capacity_kwh > 0.1
        can_sell = self.state.available_energy_kwh > 0.1

        if not can_buy and not can_sell:
            return None

        # Simple SoC-based rule
        soc = self.state.current_soc
        target_soc = 0.6  # Simple target

        if soc < target_soc - 0.15 and can_buy:
            return TradeSide.BUY
        elif soc > target_soc + 0.15 and can_sell:
            return TradeSide.SELL
        elif can_buy and not can_sell:
            return TradeSide.BUY
        elif can_sell and not can_buy:
            return TradeSide.SELL
        else:
            # Use price heuristic
            if self._price_memory:
                avg_price = np.mean(self._price_memory[-5:])
                if avg_price < (self.state.value_per_kwh + self.state.cost_per_kwh) / 2:
                    return TradeSide.BUY if can_buy else TradeSide.SELL
                else:
                    return TradeSide.SELL if can_sell else TradeSide.BUY
            return TradeSide.BUY if can_buy else TradeSide.SELL

    def _determine_quantity_simple(self, side: TradeSide) -> float:
        """Determine quantity using simple rules."""
        if side == TradeSide.BUY:
            max_qty = self.state.available_capacity_kwh
        else:
            max_qty = self.state.available_energy_kwh

        # Simple rule: trade half of available capacity
        return min(max_qty, max_qty * 0.5 + 0.5)

    def _satisficing_search(
        self,
        side: TradeSide,
        quantity: float,
        market_state: MarketState,
    ) -> Optional[float]:
        """
        Search for a satisfactory price.

        Generates random alternatives and accepts first one
        meeting aspiration level.
        """
        # Determine price bounds
        if side == TradeSide.BUY:
            min_price = self.state.cost_per_kwh * 0.5
            max_price = self.state.value_per_kwh
            max_utility = (self.state.value_per_kwh - self.state.cost_per_kwh) * quantity
        else:
            min_price = self.state.cost_per_kwh
            max_price = self.state.value_per_kwh * 1.5
            max_utility = (self.state.value_per_kwh - self.state.cost_per_kwh) * quantity

        aspiration_utility = self.aspiration_level * max_utility

        # Generate and evaluate alternatives
        best_price = None
        best_utility = float("-inf")

        for _ in range(self.max_alternatives):
            # Generate random price
            price = np.random.uniform(min_price, max_price)

            # Calculate utility
            utility = self.compute_utility(price, quantity, side.value)

            # Check if satisfactory
            if utility >= aspiration_utility:
                return round(price, 2)

            # Track best in case no satisfactory option found
            if utility > best_utility:
                best_utility = utility
                best_price = price

        # No satisfactory option found, return best if positive utility
        if best_utility > 0 and best_price is not None:
            return round(best_price, 2)

        return None

    def update_after_trade(self, trade_result: dict) -> None:
        """
        Update agent state and adapt aspiration level.

        Increases aspiration on success, decreases on failure.
        """
        # Record trade
        self.record_trade(trade_result)

        # Determine if outcome was good
        profit = trade_result.get("profit", 0)
        quantity = trade_result.get("quantity", 1)

        # Compare to aspiration
        max_possible = abs(self.state.value_per_kwh - self.state.cost_per_kwh) * quantity
        achieved_fraction = profit / max_possible if max_possible > 0 else 0

        was_good = achieved_fraction >= self.aspiration_level

        # Update success memory
        self._success_memory.append(was_good)
        if len(self._success_memory) > self.memory_window:
            self._success_memory.pop(0)

        # Adapt aspiration level
        if was_good:
            self.aspiration_level = min(
                0.9,
                self.aspiration_level + self.aspiration_increase_rate,
            )
        else:
            self.aspiration_level = max(
                0.1,
                self.aspiration_level - self.aspiration_decrease_rate,
            )

    def update_after_no_trade(self) -> None:
        """Update state when bid was not executed."""
        self._success_memory.append(False)
        if len(self._success_memory) > self.memory_window:
            self._success_memory.pop(0)

        # Lower aspiration when not trading
        self.aspiration_level = max(
            0.1,
            self.aspiration_level - self.aspiration_decrease_rate * 0.5,
        )

    def get_aspiration_stats(self) -> dict:
        """Get aspiration-related statistics."""
        return {
            "current_aspiration": self.aspiration_level,
            "success_rate": (
                sum(self._success_memory) / len(self._success_memory)
                if self._success_memory else 0.5
            ),
            "price_expectation": np.mean(self._price_memory) if self._price_memory else None,
        }
