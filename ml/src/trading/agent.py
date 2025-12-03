"""Trading agent for SHAKTI-CHAIN.

Provides:
- RL-based trading decisions
- Feature observation from store
- Action execution via blockchain
- State management
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from .executor import BlockchainTradingExecutor, TradingAction, ActionType, TransactionResult

logger = logging.getLogger(__name__)


class AgentMode(Enum):
    """Agent operating modes."""
    LIVE = "live"  # Real trading
    PAPER = "paper"  # Paper trading (dry run)
    BACKTEST = "backtest"  # Backtesting mode


@dataclass
class AgentConfig:
    """Trading agent configuration."""
    # Mode
    mode: AgentMode = AgentMode.PAPER

    # Model
    model_path: Optional[str] = None
    model_name: str = "ppo_trading_agent"

    # Features
    feature_set: str = "trading"
    observation_window: int = 24  # hours

    # Trading parameters
    min_confidence: float = 0.6  # Minimum confidence to trade
    position_sizing: str = "fixed"  # fixed, kelly, volatility
    base_position_size: float = 100.0  # kWh

    # Execution
    execution_delay_seconds: float = 0.0
    max_retries: int = 3


@dataclass
class AgentState:
    """Current state of the trading agent."""
    position: float = 0.0  # Current position in kWh
    position_value: float = 0.0  # Position value
    last_action: Optional[ActionType] = None
    last_action_time: Optional[datetime] = None
    trades_today: int = 0
    pnl_today: float = 0.0
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position": self.position,
            "position_value": self.position_value,
            "last_action": self.last_action.value if self.last_action else None,
            "last_action_time": self.last_action_time.isoformat() if self.last_action_time else None,
            "trades_today": self.trades_today,
            "pnl_today": self.pnl_today,
            "is_active": self.is_active,
        }


@dataclass
class TradingDecision:
    """A trading decision from the agent."""
    action: ActionType
    quantity: float
    price: float
    confidence: float
    reasoning: str
    features_used: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_action(self) -> TradingAction:
        """Convert to TradingAction."""
        return TradingAction(
            action_type=self.action,
            quantity=self.quantity,
            price=self.price,
            metadata={
                "confidence": self.confidence,
                "reasoning": self.reasoning,
            },
        )


class TradingAgent:
    """RL-based trading agent for SHAKTI-CHAIN."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        executor: Optional[BlockchainTradingExecutor] = None,
        feature_store=None,
        risk_manager=None,
        pnl_tracker=None,
    ):
        """Initialize trading agent.

        Args:
            config: Agent configuration
            executor: Blockchain executor for trades
            feature_store: Feature store for observations
            risk_manager: Risk manager for safety
            pnl_tracker: P&L tracker
        """
        self.config = config or AgentConfig()
        self.executor = executor
        self.feature_store = feature_store
        self.risk_manager = risk_manager
        self.pnl_tracker = pnl_tracker

        # State
        self.state = AgentState()
        self._model = None
        self._running = False

        # Callbacks
        self._decision_callbacks: List[callable] = []
        self._execution_callbacks: List[callable] = []

        # Statistics
        self._stats = {
            "decisions_made": 0,
            "trades_executed": 0,
            "trades_skipped": 0,
            "total_pnl": 0.0,
        }

        # Load model if specified
        if self.config.model_path:
            self._load_model()

    def _load_model(self):
        """Load the RL model."""
        try:
            # Try loading from various sources
            import torch

            if self.config.model_path.endswith(".pt"):
                self._model = torch.load(self.config.model_path)
                logger.info(f"Loaded PyTorch model from {self.config.model_path}")
            else:
                # Try stable-baselines3
                from stable_baselines3 import PPO
                self._model = PPO.load(self.config.model_path)
                logger.info(f"Loaded SB3 model from {self.config.model_path}")

        except ImportError:
            logger.warning("PyTorch/SB3 not available, using rule-based fallback")
        except Exception as e:
            logger.error(f"Model loading failed: {e}")

    def on_decision(self, callback: callable):
        """Register callback for trading decisions."""
        self._decision_callbacks.append(callback)

    def on_execution(self, callback: callable):
        """Register callback for trade executions."""
        self._execution_callbacks.append(callback)

    async def start(self):
        """Start the trading agent."""
        self._running = True
        self.state.is_active = True
        logger.info(f"Trading agent started in {self.config.mode.value} mode")

    async def stop(self):
        """Stop the trading agent."""
        self._running = False
        self.state.is_active = False
        logger.info("Trading agent stopped")

    async def observe_and_act(self) -> Optional[TransactionResult]:
        """Main agent loop: observe state, decide, execute.

        Returns:
            Transaction result if trade executed, None otherwise
        """
        if not self._running:
            return None

        # Get observation
        observation = await self._get_observation()
        if not observation:
            logger.warning("Failed to get observation")
            return None

        # Make decision
        decision = await self._make_decision(observation)
        self._stats["decisions_made"] += 1

        # Dispatch to callbacks
        for callback in self._decision_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(decision)
                else:
                    callback(decision)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")

        # Check if we should trade
        if decision.action == ActionType.HOLD:
            return None

        if decision.confidence < self.config.min_confidence:
            logger.info(f"Skipping trade: confidence {decision.confidence:.2f} < {self.config.min_confidence}")
            self._stats["trades_skipped"] += 1
            return None

        # Execute trade
        result = await self._execute_decision(decision)

        return result

    async def _get_observation(self) -> Optional[Dict[str, Any]]:
        """Get observation from feature store."""
        if not self.feature_store:
            # Return mock observation for testing
            return self._get_mock_observation()

        try:
            from ..features.pipeline.serving import FeatureServer

            server = FeatureServer(self.feature_store)
            vector = await server.get_features(self.config.feature_set)

            return {
                "features": vector.features,
                "timestamp": vector.timestamp,
                "is_fresh": vector.is_fresh,
            }

        except Exception as e:
            logger.error(f"Observation error: {e}")
            return None

    def _get_mock_observation(self) -> Dict[str, Any]:
        """Generate mock observation for testing."""
        import random

        return {
            "features": {
                "spot_price": 50.0 + random.gauss(0, 2),
                "price_velocity_1m": random.gauss(0, 0.5),
                "volatility_1h": random.uniform(0.5, 2.0),
                "order_imbalance": random.uniform(-0.5, 0.5),
                "grid_load": random.uniform(25000, 35000),
                "grid_frequency": 50.0 + random.gauss(0, 0.02),
            },
            "timestamp": datetime.now(),
            "is_fresh": True,
        }

    async def _make_decision(self, observation: Dict[str, Any]) -> TradingDecision:
        """Make trading decision based on observation.

        Args:
            observation: Current market observation

        Returns:
            TradingDecision
        """
        features = observation["features"]

        if self._model:
            # Use RL model
            return await self._model_decision(features)
        else:
            # Use rule-based fallback
            return self._rule_based_decision(features)

    async def _model_decision(self, features: Dict[str, Any]) -> TradingDecision:
        """Make decision using RL model."""
        try:
            import numpy as np

            # Convert features to observation vector
            obs = np.array([
                features.get("spot_price", 50.0),
                features.get("price_velocity_1m", 0.0),
                features.get("volatility_1h", 1.0),
                features.get("order_imbalance", 0.0),
                features.get("grid_load", 30000.0) / 30000.0,  # Normalize
                (features.get("grid_frequency", 50.0) - 50.0) * 100,  # Deviation * 100
                self.state.position / 1000.0,  # Normalize position
            ], dtype=np.float32)

            # Get model prediction
            action, _states = self._model.predict(obs, deterministic=True)

            # Map action to trading decision
            # Assuming action space: 0=hold, 1=buy, 2=sell
            if action == 0:
                action_type = ActionType.HOLD
                quantity = 0.0
            elif action == 1:
                action_type = ActionType.BUY
                quantity = self._calculate_position_size(features)
            else:
                action_type = ActionType.SELL
                quantity = self._calculate_position_size(features)

            return TradingDecision(
                action=action_type,
                quantity=quantity,
                price=features.get("spot_price", 50.0),
                confidence=0.8,  # TODO: Get from model
                reasoning="RL model prediction",
                features_used=features,
            )

        except Exception as e:
            logger.error(f"Model decision error: {e}")
            return self._rule_based_decision(features)

    def _rule_based_decision(self, features: Dict[str, Any]) -> TradingDecision:
        """Make decision using rule-based strategy."""
        price = features.get("spot_price", 50.0)
        velocity = features.get("price_velocity_1m", 0.0)
        imbalance = features.get("order_imbalance", 0.0)
        volatility = features.get("volatility_1h", 1.0)

        # Simple momentum strategy
        action = ActionType.HOLD
        confidence = 0.5
        reasoning = "No clear signal"

        # Strong buy signal: price momentum up + buy imbalance
        if velocity > 0.5 and imbalance > 0.3:
            action = ActionType.BUY
            confidence = min(0.9, 0.5 + velocity * 0.2 + imbalance * 0.3)
            reasoning = f"Bullish: velocity={velocity:.2f}, imbalance={imbalance:.2f}"

        # Strong sell signal: price momentum down + sell imbalance
        elif velocity < -0.5 and imbalance < -0.3:
            action = ActionType.SELL
            confidence = min(0.9, 0.5 + abs(velocity) * 0.2 + abs(imbalance) * 0.3)
            reasoning = f"Bearish: velocity={velocity:.2f}, imbalance={imbalance:.2f}"

        # Mean reversion in high volatility
        elif volatility > 1.5:
            if velocity > 1.0:  # Overextended up
                action = ActionType.SELL
                confidence = 0.6
                reasoning = f"Mean reversion sell: volatility={volatility:.2f}"
            elif velocity < -1.0:  # Overextended down
                action = ActionType.BUY
                confidence = 0.6
                reasoning = f"Mean reversion buy: volatility={volatility:.2f}"

        quantity = self._calculate_position_size(features) if action != ActionType.HOLD else 0.0

        return TradingDecision(
            action=action,
            quantity=quantity,
            price=price,
            confidence=confidence,
            reasoning=reasoning,
            features_used=features,
        )

    def _calculate_position_size(self, features: Dict[str, Any]) -> float:
        """Calculate position size based on strategy."""
        base_size = self.config.base_position_size

        if self.config.position_sizing == "fixed":
            return base_size

        elif self.config.position_sizing == "volatility":
            volatility = features.get("volatility_1h", 1.0)
            # Reduce size in high volatility
            adjustment = 1.0 / max(volatility, 0.5)
            return base_size * min(adjustment, 2.0)

        elif self.config.position_sizing == "kelly":
            # Simplified Kelly criterion
            # Would need win rate and avg win/loss from history
            return base_size * 0.5  # Conservative

        return base_size

    async def _execute_decision(self, decision: TradingDecision) -> Optional[TransactionResult]:
        """Execute a trading decision.

        Args:
            decision: Trading decision to execute

        Returns:
            Transaction result
        """
        if not self.executor:
            logger.warning("No executor configured")
            return None

        action = decision.to_action()

        # Add execution delay if configured
        if self.config.execution_delay_seconds > 0:
            await asyncio.sleep(self.config.execution_delay_seconds)

        # Execute with retries
        result = None
        for attempt in range(self.config.max_retries):
            try:
                result = await self.executor.execute_action(action)

                if result.is_success or result.status.value == "dry_run":
                    break

                logger.warning(f"Execution attempt {attempt + 1} failed: {result.error_message}")

            except Exception as e:
                logger.error(f"Execution error: {e}")
                if attempt == self.config.max_retries - 1:
                    return None

        if result and result.is_success:
            self._stats["trades_executed"] += 1
            self._update_state(decision, result)

            # Record in P&L tracker
            if self.pnl_tracker:
                self.pnl_tracker.record_trade(
                    action_type=decision.action.value,
                    quantity=decision.quantity,
                    price=decision.price,
                    gas_cost=result.gas_cost_wei / 1e18 if result.gas_cost_wei else 0,
                )

            # Dispatch to callbacks
            for callback in self._execution_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(decision, result)
                    else:
                        callback(decision, result)
                except Exception as e:
                    logger.error(f"Execution callback error: {e}")

        return result

    def _update_state(self, decision: TradingDecision, result: TransactionResult):
        """Update agent state after trade."""
        if decision.action == ActionType.BUY:
            self.state.position += decision.quantity
        elif decision.action == ActionType.SELL:
            self.state.position -= decision.quantity

        self.state.last_action = decision.action
        self.state.last_action_time = datetime.now()
        self.state.trades_today += 1

    async def on_price_update(self, price: float, change_pct: float):
        """Handle price update event.

        Args:
            price: New price
            change_pct: Price change percentage
        """
        logger.debug(f"Price update: {price} ({change_pct:+.2%})")

        # Re-evaluate if significant change
        if abs(change_pct) > 0.02:  # > 2% change
            await self.observe_and_act()

    async def on_auction_close(self, features: Dict[str, Any], event: Dict[str, Any]):
        """Handle auction close event.

        Args:
            features: Extracted features
            event: Auction event
        """
        logger.info(f"Auction closed: clearing price={features.get('clearing_price')}")

        # Re-evaluate position
        await self.observe_and_act()

    async def reevaluate(self):
        """Force re-evaluation of position."""
        await self.observe_and_act()

    def get_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        return self.state.to_dict()

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            **self._stats,
            "state": self.state.to_dict(),
            "config": {
                "mode": self.config.mode.value,
                "min_confidence": self.config.min_confidence,
                "position_sizing": self.config.position_sizing,
            },
        }
