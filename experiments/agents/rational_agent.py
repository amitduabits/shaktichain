"""
Rational Agent - Utility-maximizing agent with full information.

Implements a fully rational agent that maximizes expected utility
with risk-adjusted bidding based on the risk_aversion parameter.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .base_agent import AgentState, BaseAgent, MarketState, TradeSide


class RationalAgent(BaseAgent):
    """
    Fully rational agent that maximizes expected utility.

    Features:
    - Full information assumption
    - Risk-adjusted bidding (CARA utility)
    - Price prediction using exponential smoothing
    - Strategic bid shading
    """

    def __init__(
        self,
        state: AgentState,
        bid_shading_factor: float = 0.9,
        learning_rate: float = 0.1,
        price_smoothing_alpha: float = 0.3,
    ):
        """
        Initialize the rational agent.

        Args:
            state: Agent state
            bid_shading_factor: Factor for bid shading (0.9 = bid 90% of true value)
            learning_rate: Learning rate for strategy adaptation
            price_smoothing_alpha: Smoothing parameter for price prediction
        """
        super().__init__(state)
        self.state.type = "rational"

        self.bid_shading_factor = bid_shading_factor
        self.learning_rate = learning_rate
        self.price_smoothing_alpha = price_smoothing_alpha

        # Price expectations
        self._expected_price: Optional[float] = None
        self._price_variance: float = 1.0

        # Strategy adaptation
        self._bid_success_rate: float = 0.5
        self._cumulative_regret: float = 0.0

    def generate_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Generate a utility-maximizing bid.

        The rational agent:
        1. Decides whether to buy or sell based on SoC and price expectations
        2. Determines optimal quantity
        3. Calculates optimal price with bid shading and risk adjustment

        Args:
            market_state: Current market information

        Returns:
            (price, quantity, side) tuple or None
        """
        # Update price expectations
        self._update_price_expectations(market_state)

        # Decide side
        side = self._decide_optimal_side(market_state)
        if side is None:
            return None

        # Determine quantity
        quantity = self._determine_optimal_quantity(side, market_state)
        if quantity < 0.1:
            return None

        # Calculate optimal price
        price = self._calculate_optimal_price(side, market_state)
        if price is None:
            return None

        return (price, quantity, side.value)

    def _update_price_expectations(self, market_state: MarketState) -> None:
        """Update price expectations using exponential smoothing."""
        if market_state.clearing_price is not None:
            current_price = market_state.clearing_price

            if self._expected_price is None:
                self._expected_price = current_price
            else:
                # Exponential smoothing
                alpha = self.price_smoothing_alpha
                self._expected_price = (
                    alpha * current_price + (1 - alpha) * self._expected_price
                )

            # Update variance estimate
            if len(market_state.price_history) > 1:
                self._price_variance = float(np.var(market_state.price_history[-20:]))

    def _decide_optimal_side(self, market_state: MarketState) -> Optional[TradeSide]:
        """
        Decide optimal trading side based on expected utility.

        Returns:
            Optimal side or None if neither is profitable
        """
        can_buy = self.state.available_capacity_kwh > 0.1
        can_sell = self.state.available_energy_kwh > 0.1

        if not can_buy and not can_sell:
            return None

        expected_price = self._expected_price or market_state.clearing_price
        if expected_price is None:
            expected_price = (self.state.value_per_kwh + self.state.cost_per_kwh) / 2

        # Calculate expected utility for each side
        buy_utility = 0.0
        sell_utility = 0.0

        if can_buy:
            buy_quantity = min(self.state.available_capacity_kwh, 10.0)
            buy_utility = self.compute_risk_adjusted_utility(
                expected_price, buy_quantity, "buy",
                probability=self._estimate_fill_probability("buy", expected_price, market_state),
            )

        if can_sell:
            sell_quantity = min(self.state.available_energy_kwh, 10.0)
            sell_utility = self.compute_risk_adjusted_utility(
                expected_price, sell_quantity, "sell",
                probability=self._estimate_fill_probability("sell", expected_price, market_state),
            )

        # Choose higher utility option if positive
        if buy_utility > sell_utility and buy_utility > 0:
            return TradeSide.BUY
        elif sell_utility > buy_utility and sell_utility > 0:
            return TradeSide.SELL
        elif buy_utility > 0:
            return TradeSide.BUY
        elif sell_utility > 0:
            return TradeSide.SELL
        else:
            return None

    def _estimate_fill_probability(
        self,
        side: str,
        price: float,
        market_state: MarketState,
    ) -> float:
        """
        Estimate probability of order being filled at given price.

        Uses historical success rate and price competitiveness.
        """
        if market_state.clearing_price is None:
            return 0.5

        clearing_price = market_state.clearing_price

        if side == "buy":
            # Higher bid = higher fill probability
            if price >= clearing_price:
                return 0.9
            else:
                ratio = price / clearing_price if clearing_price > 0 else 0.5
                return max(0.1, min(0.9, ratio))
        else:
            # Lower ask = higher fill probability
            if price <= clearing_price:
                return 0.9
            else:
                ratio = clearing_price / price if price > 0 else 0.5
                return max(0.1, min(0.9, ratio))

    def _determine_optimal_quantity(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> float:
        """
        Determine optimal quantity considering risk.

        Risk-averse agents trade smaller quantities.
        """
        if side == TradeSide.BUY:
            max_quantity = self.state.available_capacity_kwh
        else:
            max_quantity = self.state.available_energy_kwh

        # Risk adjustment: more risk-averse = smaller trades
        risk_factor = 1.0 / (1.0 + self.state.risk_aversion * 0.5)
        optimal_quantity = max_quantity * risk_factor

        # Don't trade very small amounts
        return max(0.0, min(max_quantity, optimal_quantity))

    def _calculate_optimal_price(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> Optional[float]:
        """
        Calculate optimal bid/ask price with bid shading.

        Uses the revelation principle with shading to account for
        the strategic value of not revealing true valuation.
        """
        if side == TradeSide.BUY:
            # For buyers: shade bid below true value
            true_value = self.state.value_per_kwh

            # Adjust shading based on competition
            if market_state.bid_depth > market_state.ask_depth:
                # More competition, bid higher
                shading = self.bid_shading_factor + 0.05
            else:
                shading = self.bid_shading_factor

            # Consider current market price
            if self._expected_price is not None:
                reference_price = min(true_value, self._expected_price * 1.1)
            else:
                reference_price = true_value

            price = reference_price * min(1.0, shading)

            # Ensure we're not bidding above true value
            price = min(price, true_value)

        else:
            # For sellers: shade ask above true cost
            true_cost = self.state.cost_per_kwh

            # Adjust shading based on competition
            if market_state.ask_depth > market_state.bid_depth:
                # More competition, ask lower
                shading = 2.0 - self.bid_shading_factor - 0.05
            else:
                shading = 2.0 - self.bid_shading_factor

            # Consider current market price
            if self._expected_price is not None:
                reference_price = max(true_cost, self._expected_price * 0.9)
            else:
                reference_price = true_cost

            price = reference_price * max(1.0, shading)

            # Ensure we're not asking below true cost
            price = max(price, true_cost)

        # Add noise based on price variance (to avoid deterministic behavior)
        if self._price_variance > 0:
            noise = np.random.normal(0, np.sqrt(self._price_variance) * 0.05)
            price = price + noise

        return max(0.5, price)  # Minimum price bound

    def update_after_trade(self, trade_result: dict) -> None:
        """
        Update agent state and learning after a trade.

        Adapts bidding strategy based on success/failure.
        """
        # Record the trade
        self.record_trade(trade_result)

        # Update success rate
        was_profitable = trade_result.get("profit", 0) > 0
        self._bid_success_rate = (
            (1 - self.learning_rate) * self._bid_success_rate +
            self.learning_rate * (1.0 if was_profitable else 0.0)
        )

        # Adapt bid shading based on performance
        if was_profitable:
            # Was successful, could try to extract more surplus
            self.bid_shading_factor = max(0.7, self.bid_shading_factor - 0.01)
        else:
            # Was unsuccessful, be more aggressive
            self.bid_shading_factor = min(0.98, self.bid_shading_factor + 0.02)

    def update_after_no_trade(self, bid_price: float, side: str) -> None:
        """
        Update state when bid was not executed.

        Args:
            bid_price: The price we bid
            side: 'buy' or 'sell'
        """
        # Update success rate
        self._bid_success_rate = (
            (1 - self.learning_rate) * self._bid_success_rate
        )

        # Be more aggressive next time
        if side == "buy":
            self.bid_shading_factor = min(0.98, self.bid_shading_factor + 0.02)
        else:
            self.bid_shading_factor = max(0.7, self.bid_shading_factor - 0.02)
