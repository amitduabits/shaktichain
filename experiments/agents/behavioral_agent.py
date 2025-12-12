"""
Behavioral Agent - Agent following prospect theory and behavioral biases.

Implements Kahneman & Tversky's prospect theory along with
various behavioral biases observed in real markets.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .base_agent import AgentState, BaseAgent, MarketState, TradeSide


class BehavioralAgent(BaseAgent):
    """
    Behavioral agent exhibiting psychological biases.

    Features:
    - Prospect theory (loss aversion, diminishing sensitivity)
    - Probability weighting
    - Reference point adaptation
    - Anchoring and adjustment
    - Herding behavior
    - Endowment effect
    - Recency bias
    """

    def __init__(
        self,
        state: AgentState,
        loss_aversion: float = 2.25,
        diminishing_sensitivity: float = 0.88,
        probability_weighting: float = 0.61,
        reference_adaptation_rate: float = 0.1,
        anchoring_weight: float = 0.4,
        herding_weight: float = 0.2,
        endowment_factor: float = 1.5,
        recency_decay: float = 0.8,
    ):
        """
        Initialize the behavioral agent.

        Args:
            state: Agent state
            loss_aversion: Lambda - loss aversion coefficient (>1 means loss averse)
            diminishing_sensitivity: Alpha - curvature of value function [0,1]
            probability_weighting: Gamma - probability distortion [0,1]
            reference_adaptation_rate: Rate of reference point adaptation
            anchoring_weight: Weight of anchor in price estimation
            herding_weight: Influence of market consensus
            endowment_factor: WTA/WTP ratio (endowment effect)
            recency_decay: Weight decay for older observations
        """
        super().__init__(state)
        self.state.type = "behavioral"

        # Prospect theory parameters (Tversky & Kahneman, 1992 defaults)
        self.loss_aversion = loss_aversion
        self.alpha = diminishing_sensitivity
        self.gamma = probability_weighting

        # Behavioral parameters
        self.reference_point = 0.0
        self.reference_adaptation_rate = reference_adaptation_rate
        self.anchoring_weight = anchoring_weight
        self.herding_weight = herding_weight
        self.endowment_factor = endowment_factor
        self.recency_decay = recency_decay

        # Emotional state
        self._recent_outcomes: list[float] = []
        self._anchor_price: Optional[float] = None
        self._in_loss_zone = False
        self._cooling_off_periods = 0

    def generate_bid(
        self,
        market_state: MarketState,
    ) -> Optional[Tuple[float, float, str]]:
        """
        Generate a bid influenced by behavioral biases.

        Args:
            market_state: Current market information

        Returns:
            (price, quantity, side) tuple or None
        """
        # Check if in cooling off period after loss
        if self._cooling_off_periods > 0:
            self._cooling_off_periods -= 1
            return None

        # Update reference point
        self._update_reference_point(market_state)

        # Decide side with emotional influences
        side = self._decide_side_behavioral(market_state)
        if side is None:
            return None

        # Determine quantity with risk perception
        quantity = self._determine_quantity_behavioral(side, market_state)
        if quantity < 0.1:
            return None

        # Calculate price with biases
        price = self._calculate_biased_price(side, market_state)
        if price is None:
            return None

        return (round(price, 2), round(quantity, 2), side.value)

    def _update_reference_point(self, market_state: MarketState) -> None:
        """Update reference point based on recent experience."""
        if market_state.clearing_price is not None:
            new_outcome = market_state.clearing_price

            if self.reference_point == 0:
                self.reference_point = new_outcome
            else:
                # Adaptive reference point
                self.reference_point = (
                    (1 - self.reference_adaptation_rate) * self.reference_point +
                    self.reference_adaptation_rate * new_outcome
                )

            # Set anchor if not set
            if self._anchor_price is None:
                self._anchor_price = new_outcome

    def _prospect_value(self, outcome: float) -> float:
        """
        Calculate prospect theory value function.

        V(x) = x^α for gains
        V(x) = -λ(-x)^α for losses

        Args:
            outcome: Outcome relative to reference point

        Returns:
            Subjective value
        """
        if outcome >= 0:
            return outcome ** self.alpha
        else:
            return -self.loss_aversion * ((-outcome) ** self.alpha)

    def _probability_weight(self, p: float) -> float:
        """
        Calculate probability weighting function.

        w(p) = p^γ / (p^γ + (1-p)^γ)^(1/γ)

        Overweights small probabilities, underweights large.

        Args:
            p: Objective probability

        Returns:
            Subjective probability weight
        """
        if p == 0:
            return 0.0
        if p == 1:
            return 1.0

        numerator = p ** self.gamma
        denominator = (numerator + (1 - p) ** self.gamma) ** (1 / self.gamma)

        return numerator / denominator if denominator > 0 else p

    def _decide_side_behavioral(self, market_state: MarketState) -> Optional[TradeSide]:
        """
        Decide side with behavioral influences.

        Incorporates loss aversion, endowment effect, and herding.
        """
        can_buy = self.state.available_capacity_kwh > 0.1
        can_sell = self.state.available_energy_kwh > 0.1

        if not can_buy and not can_sell:
            return None

        current_price = market_state.clearing_price or self.reference_point

        # Endowment effect: higher WTA than WTP
        adjusted_value = self.state.value_per_kwh
        adjusted_cost = self.state.cost_per_kwh * self.endowment_factor

        # Calculate prospect value for each option
        buy_gain = adjusted_value - current_price
        sell_gain = current_price - adjusted_cost

        buy_value = self._prospect_value(buy_gain) if can_buy else float("-inf")
        sell_value = self._prospect_value(sell_gain) if can_sell else float("-inf")

        # Herding: follow market direction
        if market_state.price_history and len(market_state.price_history) > 1:
            trend = market_state.get_price_trend()

            # Herding pushes toward trend
            if trend > 0:  # Rising prices
                buy_value *= (1 + self.herding_weight)
                sell_value *= (1 - self.herding_weight * 0.5)
            elif trend < 0:  # Falling prices
                sell_value *= (1 + self.herding_weight)
                buy_value *= (1 - self.herding_weight * 0.5)

        # Choose based on prospect values
        if buy_value > sell_value and buy_value > 0:
            return TradeSide.BUY
        elif sell_value > buy_value and sell_value > 0:
            return TradeSide.SELL
        elif buy_value > 0:
            return TradeSide.BUY
        elif sell_value > 0:
            return TradeSide.SELL

        return None

    def _determine_quantity_behavioral(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> float:
        """
        Determine quantity with behavioral influences.

        - Risk seeking in losses (bet bigger to recover)
        - Risk averse in gains (lock in smaller profits)
        - Recency bias (recent wins/losses affect sizing)
        """
        if side == TradeSide.BUY:
            max_qty = self.state.available_capacity_kwh
        else:
            max_qty = self.state.available_energy_kwh

        base_fraction = 0.5

        # Adjust based on recent outcomes (recency bias)
        if self._recent_outcomes:
            recent_perf = sum(
                o * (self.recency_decay ** i)
                for i, o in enumerate(reversed(self._recent_outcomes[-5:]))
            )

            if recent_perf > 0:
                # Recent gains: more conservative (lock in)
                base_fraction *= 0.8
            else:
                # Recent losses: more aggressive (try to recover)
                base_fraction *= 1.2

        # Are we in gain or loss zone?
        current_price = market_state.clearing_price or self.reference_point
        if current_price < self.reference_point:
            self._in_loss_zone = True
            # Risk seeking in losses: trade more
            base_fraction *= 1.3
        else:
            self._in_loss_zone = False
            # Risk averse in gains: trade less
            base_fraction *= 0.8

        return min(max_qty, max_qty * base_fraction)

    def _calculate_biased_price(
        self,
        side: TradeSide,
        market_state: MarketState,
    ) -> Optional[float]:
        """
        Calculate price with anchoring and other biases.

        Uses anchor price with insufficient adjustment.
        """
        current_price = market_state.clearing_price

        # Anchoring: use anchor with insufficient adjustment
        if self._anchor_price is not None and current_price is not None:
            # People anchor and adjust insufficiently
            adjusted_price = (
                self.anchoring_weight * self._anchor_price +
                (1 - self.anchoring_weight) * current_price
            )
        else:
            adjusted_price = current_price or (
                (self.state.value_per_kwh + self.state.cost_per_kwh) / 2
            )

        if side == TradeSide.BUY:
            # Bid lower when loss averse (fear overpaying)
            true_value = self.state.value_per_kwh

            # In loss zone: bid more aggressively to recover
            if self._in_loss_zone:
                price = adjusted_price * 1.05
            else:
                # Conservative in gain zone
                price = adjusted_price * 0.95

            # Never bid above true value
            price = min(price, true_value)

        else:
            # Endowment effect: ask higher
            true_cost = self.state.cost_per_kwh * self.endowment_factor

            # In loss zone: sell cheaper to recover
            if self._in_loss_zone:
                price = adjusted_price * 0.95
            else:
                # Hold out for more in gain zone
                price = adjusted_price * 1.05

            # Never ask below true cost
            price = max(price, true_cost)

        return max(0.5, price)

    def update_after_trade(self, trade_result: dict) -> None:
        """
        Update state with emotional response to outcome.

        Large losses trigger cooling off period.
        """
        self.record_trade(trade_result)

        profit = trade_result.get("profit", 0)

        # Track recent outcomes
        self._recent_outcomes.append(profit)
        if len(self._recent_outcomes) > 20:
            self._recent_outcomes.pop(0)

        # Emotional response to loss
        if profit < -abs(self.state.cumulative_profit) * 0.1:
            # Significant loss: cooling off period
            self._cooling_off_periods = 2

        # Update anchor based on trade
        trade_price = trade_result.get("price", 0)
        if trade_price > 0:
            self._anchor_price = trade_price

    def update_after_no_trade(self) -> None:
        """Update after not trading."""
        # Regret from not trading if price moved favorably
        pass

    def get_behavioral_stats(self) -> dict:
        """Get behavioral state statistics."""
        return {
            "reference_point": self.reference_point,
            "anchor_price": self._anchor_price,
            "in_loss_zone": self._in_loss_zone,
            "cooling_off_periods": self._cooling_off_periods,
            "recent_avg_outcome": (
                np.mean(self._recent_outcomes) if self._recent_outcomes else 0
            ),
            "loss_aversion": self.loss_aversion,
            "endowment_factor": self.endowment_factor,
        }
