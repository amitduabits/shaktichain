"""Risk management for SHAKTI-CHAIN trading.

Provides:
- Maximum transaction size limits
- Daily loss limits
- Slippage protection
- Position limits
- Trading frequency limits
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class RiskViolationType(Enum):
    """Types of risk violations."""
    MAX_TRADE_SIZE = "max_trade_size"
    MAX_POSITION = "max_position"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DAILY_TRADE_COUNT = "daily_trade_count"
    TRADE_FREQUENCY = "trade_frequency"
    SLIPPAGE = "slippage"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    MARKET_CLOSED = "market_closed"
    COOLDOWN = "cooldown"


@dataclass
class RiskLimits:
    """Risk limits configuration."""
    # Trade size limits
    max_trade_size: float = 1000.0  # Max kWh per trade
    max_trade_value: float = 50000.0  # Max value per trade

    # Position limits
    max_long_position: float = 10000.0  # Max kWh long
    max_short_position: float = 5000.0  # Max kWh short
    max_total_position: float = 15000.0  # Max total position

    # Daily limits
    max_daily_loss: float = 5000.0  # Max daily loss in tokens
    max_daily_trades: int = 100  # Max trades per day
    max_daily_volume: float = 50000.0  # Max daily volume

    # Frequency limits
    min_trade_interval_seconds: float = 5.0  # Min time between trades
    max_trades_per_minute: int = 10  # Max trades per minute

    # Price limits
    max_slippage_pct: float = 2.0  # Max allowed slippage
    max_price_deviation_pct: float = 10.0  # Max deviation from oracle price

    # Loss limits
    max_consecutive_losses: int = 5  # Max consecutive losing trades
    loss_cooldown_minutes: int = 30  # Cooldown after consecutive losses


@dataclass
class RiskConfig:
    """Risk manager configuration."""
    limits: RiskLimits = field(default_factory=RiskLimits)
    enabled: bool = True
    alert_threshold_pct: float = 80.0  # Alert at 80% of limits
    enforce_hard_limits: bool = True


@dataclass
class RiskCheck:
    """Result of a risk check."""
    approved: bool
    violations: List["RiskViolation"] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "approved": self.approved,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "reason": self.reason,
        }


@dataclass
class RiskViolation:
    """A risk limit violation."""
    violation_type: RiskViolationType
    limit_value: float
    actual_value: float
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.violation_type.value,
            "limit": self.limit_value,
            "actual": self.actual_value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TradeRecord:
    """Record of a trade for risk tracking."""
    timestamp: datetime
    action_type: str
    quantity: float
    price: float
    pnl: float = 0.0
    is_loss: bool = False


class RiskManager:
    """Manage trading risk and enforce limits."""

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        feature_store=None,
    ):
        """Initialize risk manager.

        Args:
            config: Risk configuration
            feature_store: Feature store for price data
        """
        self.config = config or RiskConfig()
        self.feature_store = feature_store

        # Position tracking
        self._current_position: float = 0.0  # Net position in kWh
        self._position_value: float = 0.0  # Position value

        # Daily tracking
        self._daily_pnl: float = 0.0
        self._daily_trades: int = 0
        self._daily_volume: float = 0.0
        self._day_start: datetime = datetime.now().replace(hour=0, minute=0, second=0)

        # Trade history
        self._recent_trades: deque = deque(maxlen=1000)
        self._last_trade_time: Optional[datetime] = None
        self._consecutive_losses: int = 0

        # Cooldown state
        self._in_cooldown: bool = False
        self._cooldown_until: Optional[datetime] = None

        # Minute-level tracking
        self._trades_this_minute: deque = deque(maxlen=100)

        # Statistics
        self._stats = {
            "checks_performed": 0,
            "approvals": 0,
            "rejections": 0,
            "violations_by_type": {},
        }

    async def check_action(self, action) -> RiskCheck:
        """Check if a trading action passes risk limits.

        Args:
            action: TradingAction to check

        Returns:
            RiskCheck result
        """
        self._stats["checks_performed"] += 1

        if not self.config.enabled:
            return RiskCheck(approved=True)

        # Reset daily counters if new day
        self._check_daily_reset()

        violations = []
        warnings = []

        # Check cooldown
        if self._in_cooldown:
            if datetime.now() < self._cooldown_until:
                violations.append(RiskViolation(
                    violation_type=RiskViolationType.COOLDOWN,
                    limit_value=self.config.limits.loss_cooldown_minutes,
                    actual_value=0,
                    message=f"In cooldown until {self._cooldown_until}",
                ))

        # Check trade size
        size_check = self._check_trade_size(action)
        if size_check:
            violations.append(size_check)

        # Check position limits
        position_check = self._check_position_limits(action)
        if position_check:
            violations.append(position_check)

        # Check daily loss limit
        loss_check = self._check_daily_loss()
        if loss_check:
            violations.append(loss_check)

        # Check daily trade count
        if self._daily_trades >= self.config.limits.max_daily_trades:
            violations.append(RiskViolation(
                violation_type=RiskViolationType.DAILY_TRADE_COUNT,
                limit_value=self.config.limits.max_daily_trades,
                actual_value=self._daily_trades,
                message=f"Daily trade limit reached: {self._daily_trades}",
            ))

        # Check trade frequency
        freq_check = self._check_trade_frequency()
        if freq_check:
            violations.append(freq_check)

        # Check slippage
        slippage_check = await self._check_slippage(action)
        if slippage_check:
            if slippage_check.actual_value > self.config.limits.max_slippage_pct:
                violations.append(slippage_check)
            else:
                warnings.append(f"Slippage warning: {slippage_check.actual_value:.2f}%")

        # Check consecutive losses
        if self._consecutive_losses >= self.config.limits.max_consecutive_losses:
            violations.append(RiskViolation(
                violation_type=RiskViolationType.COOLDOWN,
                limit_value=self.config.limits.max_consecutive_losses,
                actual_value=self._consecutive_losses,
                message=f"Consecutive losses: {self._consecutive_losses}",
            ))

        # Generate warnings for approaching limits
        warnings.extend(self._check_limit_warnings())

        # Determine approval
        approved = len(violations) == 0 or not self.config.enforce_hard_limits

        if approved:
            self._stats["approvals"] += 1
        else:
            self._stats["rejections"] += 1
            for v in violations:
                self._stats["violations_by_type"][v.violation_type.value] = \
                    self._stats["violations_by_type"].get(v.violation_type.value, 0) + 1

        reason = violations[0].message if violations else None

        return RiskCheck(
            approved=approved,
            violations=violations,
            warnings=warnings,
            reason=reason,
        )

    def _check_daily_reset(self):
        """Reset daily counters if new day."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if today_start > self._day_start:
            logger.info("Resetting daily risk counters")
            self._daily_pnl = 0.0
            self._daily_trades = 0
            self._daily_volume = 0.0
            self._day_start = today_start

    def _check_trade_size(self, action) -> Optional[RiskViolation]:
        """Check trade size limits."""
        if action.quantity > self.config.limits.max_trade_size:
            return RiskViolation(
                violation_type=RiskViolationType.MAX_TRADE_SIZE,
                limit_value=self.config.limits.max_trade_size,
                actual_value=action.quantity,
                message=f"Trade size {action.quantity} exceeds limit {self.config.limits.max_trade_size}",
            )

        total_value = action.quantity * action.price
        if total_value > self.config.limits.max_trade_value:
            return RiskViolation(
                violation_type=RiskViolationType.MAX_TRADE_SIZE,
                limit_value=self.config.limits.max_trade_value,
                actual_value=total_value,
                message=f"Trade value {total_value} exceeds limit {self.config.limits.max_trade_value}",
            )

        return None

    def _check_position_limits(self, action) -> Optional[RiskViolation]:
        """Check position limits after proposed trade."""
        # Calculate new position
        if action.action_type.value == "buy":
            new_position = self._current_position + action.quantity
        elif action.action_type.value == "sell":
            new_position = self._current_position - action.quantity
        else:
            return None

        # Check long limit
        if new_position > self.config.limits.max_long_position:
            return RiskViolation(
                violation_type=RiskViolationType.MAX_POSITION,
                limit_value=self.config.limits.max_long_position,
                actual_value=new_position,
                message=f"Long position {new_position} would exceed limit {self.config.limits.max_long_position}",
            )

        # Check short limit
        if new_position < -self.config.limits.max_short_position:
            return RiskViolation(
                violation_type=RiskViolationType.MAX_POSITION,
                limit_value=self.config.limits.max_short_position,
                actual_value=abs(new_position),
                message=f"Short position {abs(new_position)} would exceed limit {self.config.limits.max_short_position}",
            )

        return None

    def _check_daily_loss(self) -> Optional[RiskViolation]:
        """Check daily loss limit."""
        if self._daily_pnl < -self.config.limits.max_daily_loss:
            return RiskViolation(
                violation_type=RiskViolationType.DAILY_LOSS_LIMIT,
                limit_value=self.config.limits.max_daily_loss,
                actual_value=abs(self._daily_pnl),
                message=f"Daily loss {abs(self._daily_pnl):.2f} exceeds limit {self.config.limits.max_daily_loss}",
            )
        return None

    def _check_trade_frequency(self) -> Optional[RiskViolation]:
        """Check trade frequency limits."""
        now = datetime.now()

        # Check minimum interval
        if self._last_trade_time:
            elapsed = (now - self._last_trade_time).total_seconds()
            if elapsed < self.config.limits.min_trade_interval_seconds:
                return RiskViolation(
                    violation_type=RiskViolationType.TRADE_FREQUENCY,
                    limit_value=self.config.limits.min_trade_interval_seconds,
                    actual_value=elapsed,
                    message=f"Trade too soon ({elapsed:.1f}s < {self.config.limits.min_trade_interval_seconds}s)",
                )

        # Check trades per minute
        minute_ago = now - timedelta(minutes=1)
        self._trades_this_minute = deque(
            [t for t in self._trades_this_minute if t > minute_ago],
            maxlen=100,
        )

        if len(self._trades_this_minute) >= self.config.limits.max_trades_per_minute:
            return RiskViolation(
                violation_type=RiskViolationType.TRADE_FREQUENCY,
                limit_value=self.config.limits.max_trades_per_minute,
                actual_value=len(self._trades_this_minute),
                message=f"Trades per minute ({len(self._trades_this_minute)}) at limit",
            )

        return None

    async def _check_slippage(self, action) -> Optional[RiskViolation]:
        """Check price slippage against oracle price."""
        if not self.feature_store:
            return None

        try:
            # Get oracle price from feature store
            from ..features.pipeline.store import FeatureKey
            key = FeatureKey(name="oracle_price", entity_type="oracle", entity_id="price")
            value = await self.feature_store.get(key)

            if not value:
                return None

            oracle_price = value.value
            slippage_pct = abs(action.price - oracle_price) / oracle_price * 100

            if slippage_pct > self.config.limits.max_slippage_pct:
                return RiskViolation(
                    violation_type=RiskViolationType.SLIPPAGE,
                    limit_value=self.config.limits.max_slippage_pct,
                    actual_value=slippage_pct,
                    message=f"Slippage {slippage_pct:.2f}% exceeds limit {self.config.limits.max_slippage_pct}%",
                )

        except Exception as e:
            logger.warning(f"Slippage check failed: {e}")

        return None

    def _check_limit_warnings(self) -> List[str]:
        """Check for approaching limits and generate warnings."""
        warnings = []
        threshold = self.config.alert_threshold_pct / 100

        # Daily loss warning
        if abs(self._daily_pnl) > self.config.limits.max_daily_loss * threshold:
            pct = abs(self._daily_pnl) / self.config.limits.max_daily_loss * 100
            warnings.append(f"Daily loss at {pct:.0f}% of limit")

        # Daily trade count warning
        if self._daily_trades > self.config.limits.max_daily_trades * threshold:
            pct = self._daily_trades / self.config.limits.max_daily_trades * 100
            warnings.append(f"Daily trades at {pct:.0f}% of limit")

        # Position warning
        if abs(self._current_position) > self.config.limits.max_total_position * threshold:
            pct = abs(self._current_position) / self.config.limits.max_total_position * 100
            warnings.append(f"Position at {pct:.0f}% of limit")

        return warnings

    def record_trade(
        self,
        action_type: str,
        quantity: float,
        price: float,
        pnl: float = 0.0,
    ):
        """Record a completed trade for risk tracking.

        Args:
            action_type: Type of action (buy/sell)
            quantity: Trade quantity
            price: Trade price
            pnl: Realized P&L
        """
        now = datetime.now()

        # Update position
        if action_type == "buy":
            self._current_position += quantity
        elif action_type == "sell":
            self._current_position -= quantity

        # Update daily stats
        self._daily_trades += 1
        self._daily_volume += quantity
        self._daily_pnl += pnl

        # Track consecutive losses
        if pnl < 0:
            self._consecutive_losses += 1
            if self._consecutive_losses >= self.config.limits.max_consecutive_losses:
                self._in_cooldown = True
                self._cooldown_until = now + timedelta(
                    minutes=self.config.limits.loss_cooldown_minutes
                )
                logger.warning(f"Entering cooldown until {self._cooldown_until}")
        else:
            self._consecutive_losses = 0
            self._in_cooldown = False

        # Update trade timing
        self._last_trade_time = now
        self._trades_this_minute.append(now)

        # Store trade record
        self._recent_trades.append(TradeRecord(
            timestamp=now,
            action_type=action_type,
            quantity=quantity,
            price=price,
            pnl=pnl,
            is_loss=pnl < 0,
        ))

    def get_position(self) -> Dict[str, Any]:
        """Get current position information."""
        return {
            "current_position": self._current_position,
            "position_value": self._position_value,
            "daily_pnl": self._daily_pnl,
            "daily_trades": self._daily_trades,
            "daily_volume": self._daily_volume,
            "consecutive_losses": self._consecutive_losses,
            "in_cooldown": self._in_cooldown,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get risk manager statistics."""
        return {
            **self._stats,
            "position": self.get_position(),
            "limits": {
                "max_trade_size": self.config.limits.max_trade_size,
                "max_daily_loss": self.config.limits.max_daily_loss,
                "max_daily_trades": self.config.limits.max_daily_trades,
            },
        }

    def reset_daily(self):
        """Manually reset daily counters."""
        self._daily_pnl = 0.0
        self._daily_trades = 0
        self._daily_volume = 0.0
        self._day_start = datetime.now().replace(hour=0, minute=0, second=0)
        logger.info("Daily risk counters reset")

    def reset_position(self):
        """Reset position tracking."""
        self._current_position = 0.0
        self._position_value = 0.0
        self._consecutive_losses = 0
        self._in_cooldown = False
        logger.info("Position reset")
