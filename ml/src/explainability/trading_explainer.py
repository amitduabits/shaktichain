"""Trading Decision Explainability for RL Agents.

Provides interpretable explanations for trading decisions made by
reinforcement learning agents in the SHAKTI-CHAIN V2G marketplace.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from stable_baselines3 import PPO, A2C, SAC
    from stable_baselines3.common.base_class import BaseAlgorithm
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False


class ActionType(Enum):
    """Trading action types."""
    HOLD = 0
    BUY = 1
    SELL = 2
    CHARGE = 1  # Alias for BUY
    DISCHARGE = 2  # Alias for SELL


@dataclass
class ActionReason:
    """Individual reason for a trading action."""

    reason: str
    factor: str  # Feature/condition that triggered this reason
    value: Any  # Current value of the factor
    threshold: Optional[float] = None  # Threshold that was crossed
    contribution: float = 0.0  # Contribution to action confidence
    direction: str = "neutral"  # "positive", "negative", "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "factor": self.factor,
            "value": self.value,
            "threshold": self.threshold,
            "contribution": self.contribution,
            "direction": self.direction,
        }


@dataclass
class AlternativeAction:
    """Alternative action that could have been taken."""

    action: ActionType
    expected_value: float  # Q-value or expected return
    probability: float  # Action probability from policy
    reasons: List[str]  # Why this wasn't chosen

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.name,
            "expected_value": self.expected_value,
            "probability": self.probability,
            "reasons": self.reasons,
        }


@dataclass
class TradingExplanation:
    """Complete explanation for a trading decision."""

    # Action taken
    action: ActionType
    quantity: float  # kWh
    target_price: float  # ₹/kWh
    confidence: float  # 0-1

    # Reasoning
    reasons: List[ActionReason]
    text_explanation: str

    # Alternatives
    alternative_actions: List[AlternativeAction]
    action_probabilities: Dict[str, float]

    # Feature analysis
    feature_contributions: Dict[str, float]
    state_summary: Dict[str, Any]

    # Risk assessment
    risk_factors: List[str]
    expected_profit: float
    expected_risk: float

    # Visualization data
    visualization_data: Dict[str, Any] = field(default_factory=dict)

    # Counterfactual
    counterfactual_analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.name,
            "quantity": self.quantity,
            "target_price": self.target_price,
            "confidence": self.confidence,
            "reasons": [r.to_dict() for r in self.reasons],
            "text_explanation": self.text_explanation,
            "alternative_actions": [a.to_dict() for a in self.alternative_actions],
            "action_probabilities": self.action_probabilities,
            "feature_contributions": self.feature_contributions,
            "state_summary": self.state_summary,
            "risk_factors": self.risk_factors,
            "expected_profit": self.expected_profit,
            "expected_risk": self.expected_risk,
            "visualization_data": self.visualization_data,
            "counterfactual_analysis": self.counterfactual_analysis,
        }


class TradingExplainer:
    """Explainer for RL-based trading agent decisions.

    Provides interpretable explanations through:
    1. Feature contribution analysis
    2. Action probability decomposition
    3. Counterfactual analysis
    4. Natural language explanations

    Example:
        >>> explainer = TradingExplainer(agent, feature_names)
        >>> state = {"spot_price": 4.5, "soc": 0.8, ...}
        >>> explanation = explainer.explain_action(state, action)
        >>> print(explanation.text_explanation)
        "Decision: SELL 50 kWh @ ₹4.50/kWh
         Reasons:
         1. Price forecast shows 20% increase in next 2 hours
         2. Current SOC (80%) is above threshold for selling
         3. Grid is in peak demand period
         Confidence: 85%"
    """

    # Feature descriptions for natural language
    FEATURE_DESCRIPTIONS = {
        "spot_price": "Current spot price",
        "price_velocity_1m": "Price momentum (1 min)",
        "price_velocity_1h": "Price momentum (1 hour)",
        "volatility_1h": "Price volatility",
        "order_imbalance": "Order book imbalance",
        "grid_load": "Grid load",
        "grid_frequency": "Grid frequency",
        "soc": "Battery state of charge",
        "position": "Current position",
        "pnl_today": "Today's P&L",
        "hour_sin": "Time of day",
        "hour_cos": "Time of day",
        "is_peak": "Peak hours",
        "is_weekend": "Weekend",
        "price_forecast_2h": "2-hour price forecast",
        "price_forecast_6h": "6-hour price forecast",
    }

    # Thresholds for rule-based reasoning
    THRESHOLDS = {
        "high_soc": 0.7,
        "low_soc": 0.3,
        "high_volatility": 0.2,
        "strong_momentum": 0.5,
        "imbalance_buy_signal": 0.3,
        "imbalance_sell_signal": -0.3,
        "peak_grid_load": 25000,  # MW
        "frequency_deviation": 0.05,  # Hz from 50
    }

    def __init__(
        self,
        agent: Any,
        feature_names: List[str],
        action_names: Optional[List[str]] = None,
        device: str = "cpu",
    ):
        """Initialize trading explainer.

        Args:
            agent: Trading agent (PPO, A2C, or custom)
            feature_names: Names of state features
            action_names: Names of actions (default: HOLD, BUY, SELL)
            device: Device for inference
        """
        self.agent = agent
        self.feature_names = feature_names
        self.action_names = action_names or ["HOLD", "BUY", "SELL"]
        self.device = device

        # Extract policy if SB3 agent
        self.policy = self._extract_policy()

        logger.info(
            f"TradingExplainer initialized with {len(feature_names)} features, "
            f"{len(self.action_names)} actions"
        )

    def _extract_policy(self) -> Any:
        """Extract policy network from agent."""
        if SB3_AVAILABLE and isinstance(self.agent, BaseAlgorithm):
            return self.agent.policy
        elif hasattr(self.agent, "policy"):
            return self.agent.policy
        elif hasattr(self.agent, "model"):
            return self.agent.model
        return self.agent

    def explain_action(
        self,
        state: Union[Dict[str, float], np.ndarray],
        action: Optional[ActionType] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
    ) -> TradingExplanation:
        """Generate explanation for a trading action.

        Args:
            state: Current state (dict or array)
            action: Action taken (if None, will predict)
            quantity: Trade quantity in kWh
            price: Target price

        Returns:
            TradingExplanation with detailed reasoning
        """
        # Convert state to array and dict formats
        state_array, state_dict = self._prepare_state(state)

        # Get action probabilities and values
        action_probs, q_values = self._get_action_analysis(state_array)

        # Determine action if not provided
        if action is None:
            action_idx = np.argmax(action_probs)
            action = ActionType(action_idx)

        # Calculate feature contributions
        feature_contributions = self._calculate_feature_contributions(
            state_array, action
        )

        # Generate reasons for the action
        reasons = self._generate_reasons(state_dict, action, feature_contributions)

        # Get alternative actions
        alternatives = self._get_alternatives(
            action, action_probs, q_values, state_dict
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            action, action_probs, q_values, state_dict
        )

        # Assess risk
        risk_factors, expected_profit, expected_risk = self._assess_risk(
            state_dict, action, quantity or 100, price or state_dict.get("spot_price", 4.0)
        )

        # Generate natural language explanation
        text_explanation = self._generate_text_explanation(
            action, quantity, price, reasons, confidence, risk_factors
        )

        # Prepare visualization data
        viz_data = self._prepare_visualization_data(
            state_dict, action_probs, q_values, feature_contributions
        )

        # Counterfactual analysis
        counterfactual = self._counterfactual_analysis(state_array, action)

        return TradingExplanation(
            action=action,
            quantity=quantity or 100,
            target_price=price or state_dict.get("spot_price", 4.0),
            confidence=confidence,
            reasons=reasons,
            text_explanation=text_explanation,
            alternative_actions=alternatives,
            action_probabilities={
                name: float(prob)
                for name, prob in zip(self.action_names, action_probs)
            },
            feature_contributions=feature_contributions,
            state_summary=self._summarize_state(state_dict),
            risk_factors=risk_factors,
            expected_profit=expected_profit,
            expected_risk=expected_risk,
            visualization_data=viz_data,
            counterfactual_analysis=counterfactual,
        )

    def _prepare_state(
        self,
        state: Union[Dict[str, float], np.ndarray],
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Prepare state in both array and dict formats."""
        if isinstance(state, dict):
            state_dict = state
            state_array = np.array([
                state.get(name, 0.0)
                for name in self.feature_names
            ])
        else:
            state_array = np.asarray(state)
            state_dict = {
                name: float(state_array[i])
                for i, name in enumerate(self.feature_names)
                if i < len(state_array)
            }

        return state_array.reshape(1, -1), state_dict

    def _get_action_analysis(
        self,
        state_array: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Get action probabilities and Q-values."""
        action_probs = np.ones(len(self.action_names)) / len(self.action_names)
        q_values = np.zeros(len(self.action_names))

        try:
            if SB3_AVAILABLE and hasattr(self.policy, "get_distribution"):
                # SB3 policy
                if TORCH_AVAILABLE:
                    obs = torch.tensor(state_array, dtype=torch.float32)
                    if hasattr(self.policy, "device"):
                        obs = obs.to(self.policy.device)

                    with torch.no_grad():
                        dist = self.policy.get_distribution(obs)
                        action_probs = dist.distribution.probs.cpu().numpy().flatten()

                        if hasattr(self.policy, "predict_values"):
                            values = self.policy.predict_values(obs)
                            q_values = values.cpu().numpy().flatten()

            elif hasattr(self.agent, "predict_proba"):
                # Custom agent with predict_proba
                action_probs = self.agent.predict_proba(state_array).flatten()

            elif hasattr(self.agent, "q_values"):
                # Q-learning style agent
                q_values = self.agent.q_values(state_array).flatten()
                # Convert to probabilities via softmax
                exp_q = np.exp(q_values - np.max(q_values))
                action_probs = exp_q / exp_q.sum()

        except Exception as e:
            logger.warning(f"Could not get action analysis: {e}")

        return action_probs, q_values

    def _calculate_feature_contributions(
        self,
        state_array: np.ndarray,
        action: ActionType,
    ) -> Dict[str, float]:
        """Calculate feature contributions to the action."""
        contributions = {}

        try:
            # Simple gradient-based attribution if PyTorch available
            if TORCH_AVAILABLE and hasattr(self.policy, "parameters"):
                obs = torch.tensor(state_array, dtype=torch.float32, requires_grad=True)

                if hasattr(self.policy, "device"):
                    obs = obs.to(self.policy.device)

                # Forward pass
                if hasattr(self.policy, "get_distribution"):
                    dist = self.policy.get_distribution(obs)
                    action_logits = dist.distribution.logits
                    action_logit = action_logits[0, action.value]
                elif hasattr(self.policy, "forward"):
                    out = self.policy(obs)
                    if isinstance(out, tuple):
                        out = out[0]
                    action_logit = out[0, action.value]
                else:
                    action_logit = None

                if action_logit is not None:
                    # Backward pass
                    action_logit.backward()
                    grads = obs.grad.cpu().numpy().flatten()

                    # Feature contribution = gradient * feature value
                    feature_values = state_array.flatten()
                    raw_contributions = grads * feature_values

                    # Normalize
                    total = np.abs(raw_contributions).sum()
                    if total > 0:
                        raw_contributions = raw_contributions / total

                    contributions = {
                        name: float(raw_contributions[i])
                        for i, name in enumerate(self.feature_names)
                        if i < len(raw_contributions)
                    }

        except Exception as e:
            logger.debug(f"Gradient attribution failed: {e}")

        # Fallback: rule-based contributions
        if not contributions:
            contributions = self._rule_based_contributions(
                state_array.flatten(), action
            )

        return contributions

    def _rule_based_contributions(
        self,
        state: np.ndarray,
        action: ActionType,
    ) -> Dict[str, float]:
        """Calculate contributions using rule-based heuristics."""
        contributions = {name: 0.0 for name in self.feature_names}

        state_dict = {
            name: float(state[i])
            for i, name in enumerate(self.feature_names)
            if i < len(state)
        }

        if action == ActionType.BUY:
            # Features that support buying
            if "price_velocity_1m" in state_dict:
                contributions["price_velocity_1m"] = max(0, state_dict["price_velocity_1m"]) * 0.3
            if "order_imbalance" in state_dict:
                contributions["order_imbalance"] = max(0, state_dict["order_imbalance"]) * 0.2
            if "soc" in state_dict:
                contributions["soc"] = (1 - state_dict["soc"]) * 0.2
            if "spot_price" in state_dict:
                # Lower price = more incentive to buy
                contributions["spot_price"] = max(0, 1 - state_dict["spot_price"] / 10) * 0.3

        elif action == ActionType.SELL:
            # Features that support selling
            if "price_velocity_1m" in state_dict:
                contributions["price_velocity_1m"] = max(0, -state_dict["price_velocity_1m"]) * 0.3
            if "order_imbalance" in state_dict:
                contributions["order_imbalance"] = max(0, -state_dict["order_imbalance"]) * 0.2
            if "soc" in state_dict:
                contributions["soc"] = state_dict["soc"] * 0.2
            if "spot_price" in state_dict:
                # Higher price = more incentive to sell
                contributions["spot_price"] = min(1, state_dict["spot_price"] / 10) * 0.3

        # Normalize
        total = sum(abs(v) for v in contributions.values())
        if total > 0:
            contributions = {k: v / total for k, v in contributions.items()}

        return contributions

    def _generate_reasons(
        self,
        state_dict: Dict[str, float],
        action: ActionType,
        contributions: Dict[str, float],
    ) -> List[ActionReason]:
        """Generate human-readable reasons for the action."""
        reasons = []

        # Price-based reasons
        if "spot_price" in state_dict:
            price = state_dict["spot_price"]
            if action == ActionType.SELL and price > 5.0:
                reasons.append(ActionReason(
                    reason=f"Current price (₹{price:.2f}/kWh) is favorable for selling",
                    factor="spot_price",
                    value=price,
                    threshold=5.0,
                    contribution=contributions.get("spot_price", 0),
                    direction="positive",
                ))
            elif action == ActionType.BUY and price < 4.0:
                reasons.append(ActionReason(
                    reason=f"Current price (₹{price:.2f}/kWh) is favorable for buying",
                    factor="spot_price",
                    value=price,
                    threshold=4.0,
                    contribution=contributions.get("spot_price", 0),
                    direction="positive",
                ))

        # Momentum-based reasons
        if "price_velocity_1m" in state_dict:
            velocity = state_dict["price_velocity_1m"]
            if abs(velocity) > self.THRESHOLDS["strong_momentum"]:
                direction = "upward" if velocity > 0 else "downward"
                reasons.append(ActionReason(
                    reason=f"Strong {direction} price momentum detected",
                    factor="price_velocity_1m",
                    value=velocity,
                    threshold=self.THRESHOLDS["strong_momentum"],
                    contribution=contributions.get("price_velocity_1m", 0),
                    direction="positive" if (velocity > 0) == (action == ActionType.BUY) else "negative",
                ))

        # SOC-based reasons
        if "soc" in state_dict:
            soc = state_dict["soc"]
            if action == ActionType.SELL and soc > self.THRESHOLDS["high_soc"]:
                reasons.append(ActionReason(
                    reason=f"Battery SOC ({soc*100:.0f}%) is above selling threshold",
                    factor="soc",
                    value=soc,
                    threshold=self.THRESHOLDS["high_soc"],
                    contribution=contributions.get("soc", 0),
                    direction="positive",
                ))
            elif action == ActionType.BUY and soc < self.THRESHOLDS["low_soc"]:
                reasons.append(ActionReason(
                    reason=f"Battery SOC ({soc*100:.0f}%) is below buying threshold",
                    factor="soc",
                    value=soc,
                    threshold=self.THRESHOLDS["low_soc"],
                    contribution=contributions.get("soc", 0),
                    direction="positive",
                ))

        # Grid-based reasons
        if "grid_load" in state_dict:
            load = state_dict["grid_load"]
            if load > self.THRESHOLDS["peak_grid_load"]:
                reasons.append(ActionReason(
                    reason=f"Grid is in peak demand period ({load/1000:.1f} GW)",
                    factor="grid_load",
                    value=load,
                    threshold=self.THRESHOLDS["peak_grid_load"],
                    contribution=contributions.get("grid_load", 0),
                    direction="positive" if action == ActionType.SELL else "neutral",
                ))

        # Order imbalance reasons
        if "order_imbalance" in state_dict:
            imbalance = state_dict["order_imbalance"]
            if imbalance > self.THRESHOLDS["imbalance_buy_signal"]:
                reasons.append(ActionReason(
                    reason="Buy pressure detected in order book",
                    factor="order_imbalance",
                    value=imbalance,
                    threshold=self.THRESHOLDS["imbalance_buy_signal"],
                    contribution=contributions.get("order_imbalance", 0),
                    direction="positive" if action == ActionType.BUY else "negative",
                ))
            elif imbalance < self.THRESHOLDS["imbalance_sell_signal"]:
                reasons.append(ActionReason(
                    reason="Sell pressure detected in order book",
                    factor="order_imbalance",
                    value=imbalance,
                    threshold=self.THRESHOLDS["imbalance_sell_signal"],
                    contribution=contributions.get("order_imbalance", 0),
                    direction="positive" if action == ActionType.SELL else "negative",
                ))

        # Volatility reasons
        if "volatility_1h" in state_dict:
            vol = state_dict["volatility_1h"]
            if vol > self.THRESHOLDS["high_volatility"]:
                reasons.append(ActionReason(
                    reason=f"High price volatility ({vol*100:.1f}%) - caution advised",
                    factor="volatility_1h",
                    value=vol,
                    threshold=self.THRESHOLDS["high_volatility"],
                    contribution=contributions.get("volatility_1h", 0),
                    direction="negative",
                ))

        # Sort by contribution
        reasons.sort(key=lambda r: abs(r.contribution), reverse=True)

        # Default reason if none found
        if not reasons:
            reasons.append(ActionReason(
                reason=f"Action {action.name} selected based on overall state assessment",
                factor="policy",
                value=None,
                contribution=1.0,
                direction="neutral",
            ))

        return reasons[:5]  # Top 5 reasons

    def _get_alternatives(
        self,
        chosen_action: ActionType,
        action_probs: np.ndarray,
        q_values: np.ndarray,
        state_dict: Dict[str, float],
    ) -> List[AlternativeAction]:
        """Get alternative actions with expected values."""
        alternatives = []

        for i, (name, prob, q) in enumerate(zip(self.action_names, action_probs, q_values)):
            action = ActionType(i)
            if action == chosen_action:
                continue

            # Reasons why this wasn't chosen
            not_chosen_reasons = self._why_not_chosen(action, chosen_action, state_dict, prob)

            alternatives.append(AlternativeAction(
                action=action,
                expected_value=float(q),
                probability=float(prob),
                reasons=not_chosen_reasons,
            ))

        # Sort by expected value
        alternatives.sort(key=lambda a: a.expected_value, reverse=True)

        return alternatives

    def _why_not_chosen(
        self,
        action: ActionType,
        chosen: ActionType,
        state_dict: Dict[str, float],
        prob: float,
    ) -> List[str]:
        """Generate reasons why an alternative action wasn't chosen."""
        reasons = []

        if prob < 0.2:
            reasons.append(f"Low probability ({prob*100:.1f}%)")

        soc = state_dict.get("soc", 0.5)
        if action == ActionType.SELL and soc < 0.3:
            reasons.append("Battery SOC too low for selling")
        if action == ActionType.BUY and soc > 0.9:
            reasons.append("Battery SOC too high for buying")

        if action == ActionType.HOLD and chosen != ActionType.HOLD:
            reasons.append("Market conditions favor trading")

        if not reasons:
            reasons.append(f"Lower expected value than {chosen.name}")

        return reasons

    def _calculate_confidence(
        self,
        action: ActionType,
        action_probs: np.ndarray,
        q_values: np.ndarray,
        state_dict: Dict[str, float],
    ) -> float:
        """Calculate confidence in the decision."""
        # Base confidence from action probability
        action_prob = action_probs[action.value]

        # Adjust for Q-value margin
        q_margin = 0
        if len(q_values) > 1:
            sorted_q = np.sort(q_values)[::-1]
            q_margin = (sorted_q[0] - sorted_q[1]) / (abs(sorted_q[0]) + 1e-6)

        # Adjust for volatility
        volatility = state_dict.get("volatility_1h", 0.1)
        vol_penalty = min(0.3, volatility)

        confidence = min(0.95, action_prob * 0.6 + q_margin * 0.2 + 0.2 - vol_penalty)

        return max(0.1, confidence)

    def _assess_risk(
        self,
        state_dict: Dict[str, float],
        action: ActionType,
        quantity: float,
        price: float,
    ) -> Tuple[List[str], float, float]:
        """Assess risk factors for the trade."""
        risk_factors = []
        expected_profit = 0
        expected_risk = 0

        # Volatility risk
        volatility = state_dict.get("volatility_1h", 0.1)
        if volatility > 0.2:
            risk_factors.append(f"High volatility ({volatility*100:.1f}%)")
            expected_risk += volatility * quantity * price

        # Position size risk
        if quantity > 500:
            risk_factors.append("Large position size")
            expected_risk += quantity * price * 0.05

        # Grid stability risk
        frequency = state_dict.get("grid_frequency", 50.0)
        if abs(frequency - 50.0) > 0.1:
            risk_factors.append(f"Grid frequency deviation ({frequency:.2f} Hz)")
            expected_risk += quantity * price * 0.02

        # Calculate expected profit based on price forecast
        price_forecast_2h = state_dict.get("price_forecast_2h", price)
        if action == ActionType.SELL:
            expected_profit = quantity * price
        elif action == ActionType.BUY:
            expected_profit = quantity * (price_forecast_2h - price)

        return risk_factors, expected_profit, expected_risk

    def _generate_text_explanation(
        self,
        action: ActionType,
        quantity: Optional[float],
        price: Optional[float],
        reasons: List[ActionReason],
        confidence: float,
        risk_factors: List[str],
    ) -> str:
        """Generate natural language explanation."""
        lines = []

        # Action summary
        qty_str = f"{quantity:.0f} kWh" if quantity else "TBD"
        price_str = f"₹{price:.2f}/kWh" if price else "market price"

        if action == ActionType.HOLD:
            lines.append("Decision: HOLD (no trade)")
        else:
            lines.append(f"Decision: {action.name} {qty_str} @ {price_str}")

        # Confidence
        lines.append(f"Confidence: {confidence*100:.0f}%")

        # Reasons
        lines.append("\nKey Factors:")
        for i, reason in enumerate(reasons[:5], 1):
            indicator = "✓" if reason.direction == "positive" else "⚠" if reason.direction == "negative" else "•"
            lines.append(f"  {i}. {indicator} {reason.reason}")

        # Risk warning
        if risk_factors:
            lines.append("\nRisk Factors:")
            for factor in risk_factors:
                lines.append(f"  ⚠ {factor}")

        return "\n".join(lines)

    def _summarize_state(self, state_dict: Dict[str, float]) -> Dict[str, Any]:
        """Create human-readable state summary."""
        summary = {}

        if "spot_price" in state_dict:
            summary["price"] = f"₹{state_dict['spot_price']:.2f}/kWh"

        if "soc" in state_dict:
            summary["battery"] = f"{state_dict['soc']*100:.0f}% SOC"

        if "grid_load" in state_dict:
            summary["grid"] = f"{state_dict['grid_load']/1000:.1f} GW load"

        if "volatility_1h" in state_dict:
            summary["volatility"] = f"{state_dict['volatility_1h']*100:.1f}%"

        return summary

    def _prepare_visualization_data(
        self,
        state_dict: Dict[str, float],
        action_probs: np.ndarray,
        q_values: np.ndarray,
        contributions: Dict[str, float],
    ) -> Dict[str, Any]:
        """Prepare data for visualizations."""
        return {
            "action_probabilities": {
                "actions": self.action_names,
                "probabilities": action_probs.tolist(),
                "q_values": q_values.tolist(),
            },
            "feature_contributions": {
                "features": list(contributions.keys()),
                "contributions": list(contributions.values()),
            },
            "state_radar": {
                "features": list(state_dict.keys()),
                "values": [float(v) for v in state_dict.values()],
            },
            "decision_tree": self._build_decision_tree_data(state_dict),
        }

    def _build_decision_tree_data(
        self,
        state_dict: Dict[str, float],
    ) -> Dict[str, Any]:
        """Build decision tree visualization data."""
        nodes = [
            {"id": "root", "label": "Market State", "type": "root"},
        ]
        edges = []

        # Price branch
        price = state_dict.get("spot_price", 4.0)
        if price > 5.0:
            nodes.append({"id": "high_price", "label": "High Price", "type": "condition"})
            edges.append({"from": "root", "to": "high_price"})
        elif price < 3.5:
            nodes.append({"id": "low_price", "label": "Low Price", "type": "condition"})
            edges.append({"from": "root", "to": "low_price"})

        # SOC branch
        soc = state_dict.get("soc", 0.5)
        if soc > 0.7:
            nodes.append({"id": "high_soc", "label": "High SOC", "type": "condition"})
            edges.append({"from": "root", "to": "high_soc"})
        elif soc < 0.3:
            nodes.append({"id": "low_soc", "label": "Low SOC", "type": "condition"})
            edges.append({"from": "root", "to": "low_soc"})

        return {"nodes": nodes, "edges": edges}

    def _counterfactual_analysis(
        self,
        state_array: np.ndarray,
        action: ActionType,
    ) -> Dict[str, Any]:
        """Analyze what would need to change for a different action."""
        counterfactuals = {}

        # Find minimal changes for each alternative action
        for alt_action in ActionType:
            if alt_action == action:
                continue

            changes = self._find_minimal_changes(state_array, action, alt_action)
            if changes:
                counterfactuals[alt_action.name] = changes

        return {
            "current_action": action.name,
            "counterfactuals": counterfactuals,
            "interpretation": self._interpret_counterfactuals(counterfactuals),
        }

    def _find_minimal_changes(
        self,
        state_array: np.ndarray,
        current_action: ActionType,
        target_action: ActionType,
    ) -> Optional[Dict[str, Any]]:
        """Find minimal feature changes to flip action."""
        # Simple heuristic-based counterfactual
        changes = []
        state = state_array.flatten()

        state_dict = {
            name: float(state[i])
            for i, name in enumerate(self.feature_names)
            if i < len(state)
        }

        if target_action == ActionType.BUY and current_action != ActionType.BUY:
            if "spot_price" in state_dict:
                changes.append({
                    "feature": "spot_price",
                    "from": state_dict["spot_price"],
                    "to": state_dict["spot_price"] * 0.8,
                    "description": "Reduce price by 20%",
                })
            if "soc" in state_dict:
                changes.append({
                    "feature": "soc",
                    "from": state_dict["soc"],
                    "to": 0.2,
                    "description": "Lower SOC to 20%",
                })

        elif target_action == ActionType.SELL and current_action != ActionType.SELL:
            if "spot_price" in state_dict:
                changes.append({
                    "feature": "spot_price",
                    "from": state_dict["spot_price"],
                    "to": state_dict["spot_price"] * 1.3,
                    "description": "Increase price by 30%",
                })
            if "soc" in state_dict:
                changes.append({
                    "feature": "soc",
                    "from": state_dict["soc"],
                    "to": 0.9,
                    "description": "Raise SOC to 90%",
                })

        return {"changes": changes} if changes else None

    def _interpret_counterfactuals(
        self,
        counterfactuals: Dict[str, Dict],
    ) -> str:
        """Generate interpretation of counterfactual analysis."""
        if not counterfactuals:
            return "No clear counterfactuals identified."

        lines = ["To change the decision:"]
        for action_name, cf in counterfactuals.items():
            if cf and cf.get("changes"):
                change = cf["changes"][0]
                lines.append(
                    f"  • For {action_name}: {change['description']}"
                )

        return "\n".join(lines)
