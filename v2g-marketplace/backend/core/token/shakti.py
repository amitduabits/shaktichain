"""
SHAKTI Token Model for V2G Marketplace.

This module implements the SHAKTI token economic model with velocity-based
pricing, staking mechanics, and deflationary burn mechanisms.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math


@dataclass
class TokenState:
    """Current state of the SHAKTI token."""
    current_supply: float
    current_price: float  # INR
    staking_rate: float  # 0-1
    velocity: float


@dataclass
class TransactionResult:
    """Result of a token transaction."""
    minted: float
    burned: float
    new_supply: float
    new_price: float
    fee_collected: float
    volume_processed: float


class SHAKTIToken:
    """
    SHAKTI Token economic model for V2G energy marketplace.

    The token serves as the medium of exchange in the V2G marketplace,
    with price discovery based on energy trading volume, velocity, and
    staking participation.

    Key mechanics:
    - Velocity-based pricing: Token velocity decreases with staking
    - Deflationary burns: 30% of transaction fees are burned
    - Staking rewards: 8% APY for staked tokens
    - Transaction fees: 2% on all transactions

    Example:
        >>> token = SHAKTIToken()
        >>> result = token.process_transaction(volume_inr=10000)
        >>> print(f"Burned: {result.burned:.2f}, New price: {result.new_price:.4f}")
    """

    # Token parameters (constants)
    INITIAL_SUPPLY: float = 10_000_000.0  # 10 million tokens
    BASE_VELOCITY: float = 12.0  # Monthly turnover rate
    STAKING_REWARD_RATE: float = 0.08  # 8% APY
    BURN_RATE: float = 0.30  # 30% of fees burned
    FEE_RATE: float = 0.02  # 2% transaction fee

    # Max trading volume for velocity calculation (INR)
    MAX_TRADING_VOLUME: float = 100_000_000.0  # 100 million INR

    # Initial price parameters
    INITIAL_PRICE: float = 1.0  # 1 INR per token at launch

    def __init__(
        self,
        initial_supply: Optional[float] = None,
        base_velocity: Optional[float] = None,
        staking_reward_rate: Optional[float] = None,
        burn_rate: Optional[float] = None,
        fee_rate: Optional[float] = None,
        initial_price: Optional[float] = None,
        initial_staking_rate: float = 0.0,
    ):
        """
        Initialize the SHAKTI token model.

        Args:
            initial_supply: Total token supply at launch (default: 10M)
            base_velocity: Base token velocity/turnover (default: 12)
            staking_reward_rate: Annual staking reward rate (default: 0.08)
            burn_rate: Fraction of fees to burn (default: 0.30)
            fee_rate: Transaction fee rate (default: 0.02)
            initial_price: Starting token price in INR (default: 1.0)
            initial_staking_rate: Initial fraction of tokens staked (default: 0.0)
        """
        # Override defaults if provided
        self._initial_supply = initial_supply or self.INITIAL_SUPPLY
        self._base_velocity = base_velocity or self.BASE_VELOCITY
        self._staking_reward_rate = staking_reward_rate or self.STAKING_REWARD_RATE
        self._burn_rate = burn_rate or self.BURN_RATE
        self._fee_rate = fee_rate or self.FEE_RATE
        self._initial_price = initial_price or self.INITIAL_PRICE

        # Initialize state
        self._current_supply = self._initial_supply
        self._current_price = self._initial_price
        self._staking_rate = initial_staking_rate
        self._velocity = self._base_velocity

        # Historical tracking
        self._price_history: List[float] = [self._current_price]
        self._supply_history: List[float] = [self._current_supply]
        self._staking_history: List[float] = [self._staking_rate]
        self._total_burned: float = 0.0
        self._total_minted: float = 0.0
        self._total_fees: float = 0.0

    @property
    def state(self) -> TokenState:
        """Get current token state."""
        return TokenState(
            current_supply=self._current_supply,
            current_price=self._current_price,
            staking_rate=self._staking_rate,
            velocity=self._velocity,
        )

    @property
    def current_supply(self) -> float:
        """Current circulating supply."""
        return self._current_supply

    @property
    def current_price(self) -> float:
        """Current token price in INR."""
        return self._current_price

    @property
    def staking_rate(self) -> float:
        """Current staking rate (0-1)."""
        return self._staking_rate

    @property
    def velocity(self) -> float:
        """Current token velocity."""
        return self._velocity

    @property
    def market_cap(self) -> float:
        """Current market capitalization in INR."""
        return self._current_supply * self._current_price

    @property
    def circulating_supply(self) -> float:
        """Non-staked circulating supply."""
        return self._current_supply * (1 - self._staking_rate)

    def compute_velocity(
        self,
        trading_volume: float,
        staking_rate: Optional[float] = None,
    ) -> float:
        """
        Compute token velocity based on trading volume and staking.

        Formula: V = V0 * (1-sigma)^0.5 * exp(-0.1 * Q/Qmax)

        Where:
        - V0: Base velocity (12)
        - sigma: Staking rate (0-1)
        - Q: Trading volume
        - Qmax: Maximum trading volume for normalization

        Higher staking reduces velocity (more tokens locked).
        Higher volume relative to max slightly reduces velocity (saturation).

        Args:
            trading_volume: Trading volume in INR
            staking_rate: Staking rate override (uses current if not provided)

        Returns:
            Computed velocity
        """
        sigma = staking_rate if staking_rate is not None else self._staking_rate

        # Clamp staking rate to valid range
        sigma = max(0.0, min(1.0, sigma))

        # Avoid division issues
        if sigma >= 1.0:
            return 0.0

        # V = V0 * (1-sigma)^0.5 * exp(-0.1 * Q/Qmax)
        staking_factor = math.pow(1 - sigma, 0.5)
        volume_factor = math.exp(-0.1 * trading_volume / self.MAX_TRADING_VOLUME)

        return self._base_velocity * staking_factor * volume_factor

    def compute_price(
        self,
        energy_price: float,
        volume: float,
        supply: Optional[float] = None,
        staking_rate: Optional[float] = None,
    ) -> float:
        """
        Compute token price based on energy trading activity.

        Formula: P_T = (P_E * Q * 24) / (M * (1-sigma) * V)

        Where:
        - P_E: Energy price (INR/kWh)
        - Q: Energy trading volume (kWh)
        - M: Total token supply
        - sigma: Staking rate
        - V: Token velocity
        - 24: Hours per day (annualization factor for daily calculations)

        This follows the equation of exchange: MV = PQ, solved for token price.

        Args:
            energy_price: Energy price in INR per kWh
            volume: Energy trading volume in kWh
            supply: Token supply override (uses current if not provided)
            staking_rate: Staking rate override (uses current if not provided)

        Returns:
            Token price in INR
        """
        M = supply if supply is not None else self._current_supply
        sigma = staking_rate if staking_rate is not None else self._staking_rate

        # Compute velocity for this scenario
        # Convert energy volume to INR for velocity calculation
        volume_inr = energy_price * volume
        V = self.compute_velocity(volume_inr, sigma)

        # Avoid division by zero
        if M <= 0 or V <= 0:
            return self._current_price

        # Circulating (non-staked) supply
        circulating = M * (1 - sigma)
        if circulating <= 0:
            return self._current_price

        # P_T = (P_E * Q * 24) / (M * (1-sigma) * V)
        price = (energy_price * volume * 24) / (circulating * V)

        # Apply smoothing to prevent extreme price swings
        # Price can move max 10% per period
        max_change = 0.10
        if price > self._current_price * (1 + max_change):
            price = self._current_price * (1 + max_change)
        elif price < self._current_price * (1 - max_change):
            price = self._current_price * (1 - max_change)

        # Ensure price stays positive
        return max(price, 0.001)

    def process_transaction(self, volume_inr: float) -> TransactionResult:
        """
        Process a transaction and update token state.

        Transaction flow:
        1. Calculate fee (2% of volume)
        2. Burn 30% of fee
        3. Remainder goes to protocol/stakers
        4. Update supply and recalculate price

        Args:
            volume_inr: Transaction volume in INR

        Returns:
            TransactionResult with minted, burned, new_supply, new_price
        """
        if volume_inr <= 0:
            return TransactionResult(
                minted=0.0,
                burned=0.0,
                new_supply=self._current_supply,
                new_price=self._current_price,
                fee_collected=0.0,
                volume_processed=0.0,
            )

        # Calculate fee
        fee = volume_inr * self._fee_rate
        self._total_fees += fee

        # Calculate burn amount (in tokens)
        burn_value_inr = fee * self._burn_rate
        tokens_burned = burn_value_inr / self._current_price if self._current_price > 0 else 0

        # Calculate staking rewards minted (distributed proportionally to stakers)
        # Rewards are calculated per transaction as fraction of annual rate
        # Assuming ~365*24 hourly transactions per year for rate conversion
        hourly_rate = self._staking_reward_rate / (365 * 24)
        staked_supply = self._current_supply * self._staking_rate
        tokens_minted = staked_supply * hourly_rate

        # Update supply
        new_supply = self._current_supply - tokens_burned + tokens_minted
        self._current_supply = new_supply
        self._total_burned += tokens_burned
        self._total_minted += tokens_minted

        # Update velocity based on trading activity
        self._velocity = self.compute_velocity(volume_inr, self._staking_rate)

        # Update price based on equation of exchange
        # For transaction processing, use volume_inr directly
        if self._velocity > 0 and self._current_supply > 0:
            circulating = self._current_supply * (1 - self._staking_rate)
            if circulating > 0:
                # P = Transaction Volume / (Circulating * V) * adjustment
                implied_price = volume_inr / (circulating * self._velocity / 12)
                # Smooth price update
                self._current_price = 0.9 * self._current_price + 0.1 * implied_price

        # Ensure price stays positive
        self._current_price = max(self._current_price, 0.001)

        # Record history
        self._price_history.append(self._current_price)
        self._supply_history.append(self._current_supply)
        self._staking_history.append(self._staking_rate)

        return TransactionResult(
            minted=tokens_minted,
            burned=tokens_burned,
            new_supply=self._current_supply,
            new_price=self._current_price,
            fee_collected=fee,
            volume_processed=volume_inr,
        )

    def update_staking(self, target_rate: float) -> float:
        """
        Gradually adjust staking rate toward target equilibrium.

        Uses smooth adjustment to prevent abrupt changes:
        - Rate moves 10% toward target per period
        - Clamped to valid range [0, 1]

        Args:
            target_rate: Target staking rate (0-1)

        Returns:
            New staking rate
        """
        # Clamp target to valid range
        target_rate = max(0.0, min(1.0, target_rate))

        # Gradual adjustment (10% per period toward target)
        adjustment_speed = 0.10
        delta = target_rate - self._staking_rate
        self._staking_rate += delta * adjustment_speed

        # Ensure valid range
        self._staking_rate = max(0.0, min(1.0, self._staking_rate))

        # Record history
        self._staking_history.append(self._staking_rate)

        return self._staking_rate

    def get_price_history(self) -> List[float]:
        """Get historical token prices."""
        return self._price_history.copy()

    def get_supply_history(self) -> List[float]:
        """Get historical supply values."""
        return self._supply_history.copy()

    def get_staking_history(self) -> List[float]:
        """Get historical staking rates."""
        return self._staking_history.copy()

    def reset(self):
        """Reset token to initial state."""
        self._current_supply = self._initial_supply
        self._current_price = self._initial_price
        self._staking_rate = 0.0
        self._velocity = self._base_velocity
        self._price_history = [self._current_price]
        self._supply_history = [self._current_supply]
        self._staking_history = [self._staking_rate]
        self._total_burned = 0.0
        self._total_minted = 0.0
        self._total_fees = 0.0

    def summary(self) -> Dict:
        """Get summary statistics for the token."""
        return {
            "current_supply": self._current_supply,
            "current_price": self._current_price,
            "market_cap": self.market_cap,
            "staking_rate": self._staking_rate,
            "velocity": self._velocity,
            "total_burned": self._total_burned,
            "total_minted": self._total_minted,
            "total_fees": self._total_fees,
            "net_deflation": self._total_burned - self._total_minted,
            "price_change_pct": (
                (self._current_price - self._initial_price) / self._initial_price * 100
                if self._initial_price > 0 else 0
            ),
            "supply_change_pct": (
                (self._current_supply - self._initial_supply) / self._initial_supply * 100
                if self._initial_supply > 0 else 0
            ),
        }
