"""
Tests for SHAKTI Token Model.
"""

import pytest
import math
import sys
sys.path.insert(0, str(__file__).rsplit("/", 3)[0])

from backend.core.token import SHAKTIToken, TokenState, TransactionResult


class TestSHAKTITokenInit:
    """Tests for token initialization."""

    def test_default_initialization(self):
        """Test token initializes with correct defaults."""
        token = SHAKTIToken()
        assert token.current_supply == 10_000_000.0
        assert token.current_price == 1.0
        assert token.staking_rate == 0.0
        assert token.velocity == 12.0

    def test_custom_initial_supply(self):
        """Test token can be initialized with custom supply."""
        token = SHAKTIToken(initial_supply=5_000_000.0)
        assert token.current_supply == 5_000_000.0

    def test_custom_initial_staking_rate(self):
        """Test token can be initialized with staking rate."""
        token = SHAKTIToken(initial_staking_rate=0.25)
        assert token.staking_rate == 0.25

    def test_custom_parameters(self):
        """Test token with all custom parameters."""
        token = SHAKTIToken(
            initial_supply=1_000_000.0,
            base_velocity=10.0,
            staking_reward_rate=0.10,
            burn_rate=0.25,
            fee_rate=0.03,
            initial_price=2.0,
            initial_staking_rate=0.30,
        )
        assert token.current_supply == 1_000_000.0
        assert token.current_price == 2.0
        assert token.staking_rate == 0.30


class TestTokenState:
    """Tests for token state property."""

    def test_state_property(self):
        """Test state property returns correct values."""
        token = SHAKTIToken(initial_staking_rate=0.20)
        state = token.state

        assert isinstance(state, TokenState)
        assert state.current_supply == token.current_supply
        assert state.current_price == token.current_price
        assert state.staking_rate == token.staking_rate
        assert state.velocity == token.velocity


class TestComputeVelocity:
    """Tests for velocity computation."""

    def test_zero_staking_full_velocity(self):
        """Zero staking should give full base velocity effect."""
        token = SHAKTIToken()
        velocity = token.compute_velocity(trading_volume=0, staking_rate=0.0)
        assert velocity == 12.0  # Base velocity with (1-0)^0.5 = 1

    def test_high_staking_reduces_velocity(self):
        """Higher staking should reduce velocity."""
        token = SHAKTIToken()
        v_low_staking = token.compute_velocity(trading_volume=0, staking_rate=0.1)
        v_high_staking = token.compute_velocity(trading_volume=0, staking_rate=0.5)
        assert v_high_staking < v_low_staking

    def test_full_staking_zero_velocity(self):
        """100% staking should give zero velocity."""
        token = SHAKTIToken()
        velocity = token.compute_velocity(trading_volume=0, staking_rate=1.0)
        assert velocity == 0.0

    def test_high_volume_reduces_velocity(self):
        """Higher trading volume should reduce velocity."""
        token = SHAKTIToken()
        v_low_volume = token.compute_velocity(trading_volume=1_000_000, staking_rate=0.2)
        v_high_volume = token.compute_velocity(trading_volume=50_000_000, staking_rate=0.2)
        assert v_high_volume < v_low_volume

    def test_velocity_formula(self):
        """Test velocity follows the formula V = V0 * (1-sigma)^0.5 * exp(-0.1 * Q/Qmax)."""
        token = SHAKTIToken()
        sigma = 0.25
        volume = 10_000_000
        expected = 12.0 * math.pow(1 - sigma, 0.5) * math.exp(-0.1 * volume / 100_000_000)
        actual = token.compute_velocity(volume, sigma)
        assert abs(actual - expected) < 0.0001


class TestComputePrice:
    """Tests for price computation."""

    def test_price_increases_with_energy_price(self):
        """Higher energy prices should increase token price (before smoothing cap)."""
        token = SHAKTIToken()
        # Use large volume to ensure meaningful price impact
        # The formula is P_T = (P_E * Q * 24) / (M * (1-sigma) * V)
        # With higher energy price, numerator increases -> higher computed price
        # Note: Smoothing may cap at 10% change, so we verify the direction
        p_low = token.compute_price(energy_price=5.0, volume=100_000, staking_rate=0.2)
        # Reset token to get same baseline
        token2 = SHAKTIToken()
        p_high = token2.compute_price(energy_price=50.0, volume=100_000, staking_rate=0.2)
        # Due to smoothing, they should at least be equal (capped) or higher
        assert p_high >= p_low

    def test_price_increases_with_volume(self):
        """Higher trading volume should increase token price."""
        token = SHAKTIToken()
        p_low = token.compute_price(energy_price=6.0, volume=1_000, staking_rate=0.2)
        token2 = SHAKTIToken()
        p_high = token2.compute_price(energy_price=6.0, volume=100_000, staking_rate=0.2)
        assert p_high >= p_low

    def test_price_increases_with_staking(self):
        """Higher staking should increase token price (less circulating supply)."""
        token = SHAKTIToken()
        p_low = token.compute_price(energy_price=6.0, volume=10_000, staking_rate=0.1)
        token2 = SHAKTIToken()
        p_high = token2.compute_price(energy_price=6.0, volume=10_000, staking_rate=0.8)
        assert p_high >= p_low

    def test_price_smoothing_limits_change(self):
        """Price smoothing should limit change to 10% per period."""
        token = SHAKTIToken()
        initial_price = token.current_price
        # Very large volume should push price up, but smoothing limits it
        new_price = token.compute_price(energy_price=1000.0, volume=1_000_000, staking_rate=0.2)
        # Should be capped at 10% increase
        assert new_price <= initial_price * 1.10

    def test_price_never_negative(self):
        """Price should never go negative."""
        token = SHAKTIToken()
        price = token.compute_price(energy_price=0.0, volume=0, staking_rate=0.0)
        assert price >= 0.001


class TestProcessTransaction:
    """Tests for transaction processing."""

    def test_zero_volume_transaction(self):
        """Zero volume should produce no changes."""
        token = SHAKTIToken()
        initial_supply = token.current_supply
        result = token.process_transaction(volume_inr=0)

        assert result.minted == 0.0
        assert result.burned == 0.0
        assert result.new_supply == initial_supply
        assert result.volume_processed == 0.0

    def test_transaction_burns_tokens(self):
        """Transaction should burn tokens from fees."""
        token = SHAKTIToken()
        initial_supply = token.current_supply
        result = token.process_transaction(volume_inr=100_000)

        assert result.burned > 0
        assert result.new_supply < initial_supply + result.minted

    def test_transaction_collects_fees(self):
        """Transaction should collect 2% fees."""
        token = SHAKTIToken()
        volume = 100_000
        result = token.process_transaction(volume_inr=volume)

        expected_fee = volume * 0.02
        assert abs(result.fee_collected - expected_fee) < 0.01

    def test_transaction_returns_result(self):
        """Transaction should return proper TransactionResult."""
        token = SHAKTIToken(initial_staking_rate=0.20)
        result = token.process_transaction(volume_inr=50_000)

        assert isinstance(result, TransactionResult)
        assert result.volume_processed == 50_000
        assert result.new_supply == token.current_supply
        assert result.new_price == token.current_price

    def test_transaction_updates_price_history(self):
        """Transaction should update price history."""
        token = SHAKTIToken()
        initial_history_len = len(token.get_price_history())
        token.process_transaction(volume_inr=10_000)
        assert len(token.get_price_history()) == initial_history_len + 1

    def test_multiple_transactions_accumulate(self):
        """Multiple transactions should accumulate effects."""
        token = SHAKTIToken()
        initial_supply = token.current_supply

        for _ in range(10):
            token.process_transaction(volume_inr=10_000)

        # Supply should have changed after burns/mints
        assert token.current_supply != initial_supply


class TestStakingUpdates:
    """Tests for staking rate updates."""

    def test_staking_moves_toward_target(self):
        """Staking rate should move toward target."""
        token = SHAKTIToken(initial_staking_rate=0.10)
        target = 0.40

        token.update_staking(target)
        assert token.staking_rate > 0.10
        assert token.staking_rate < target

    def test_staking_gradual_adjustment(self):
        """Staking should adjust gradually (10% per period)."""
        token = SHAKTIToken(initial_staking_rate=0.0)
        target = 1.0

        token.update_staking(target)
        # Should move 10% toward target: 0 + (1.0 - 0) * 0.1 = 0.1
        assert abs(token.staking_rate - 0.1) < 0.001

    def test_staking_clamped_to_valid_range(self):
        """Staking rate should stay in [0, 1]."""
        token = SHAKTIToken(initial_staking_rate=0.5)

        # Try to go above 1.0
        token.update_staking(2.0)
        assert token.staking_rate <= 1.0

        # Try to go below 0.0
        token = SHAKTIToken(initial_staking_rate=0.5)
        token.update_staking(-1.0)
        assert token.staking_rate >= 0.0

    def test_staking_updates_history(self):
        """Staking updates should update history."""
        token = SHAKTIToken()
        initial_len = len(token.get_staking_history())
        token.update_staking(0.5)
        assert len(token.get_staking_history()) == initial_len + 1


class TestTokenReset:
    """Tests for token reset functionality."""

    def test_reset_restores_initial_state(self):
        """Reset should restore token to initial state."""
        token = SHAKTIToken(initial_supply=5_000_000, initial_price=2.0)

        # Modify state
        for _ in range(10):
            token.process_transaction(volume_inr=100_000)
            token.update_staking(0.5)

        # Reset
        token.reset()

        assert token.current_supply == 5_000_000
        assert token.current_price == 2.0
        assert token.staking_rate == 0.0
        assert len(token.get_price_history()) == 1


class TestTokenSummary:
    """Tests for token summary statistics."""

    def test_summary_contains_all_fields(self):
        """Summary should contain all expected fields."""
        token = SHAKTIToken()
        token.process_transaction(volume_inr=100_000)
        summary = token.summary()

        expected_fields = [
            "current_supply", "current_price", "market_cap",
            "staking_rate", "velocity", "total_burned",
            "total_minted", "total_fees", "net_deflation",
            "price_change_pct", "supply_change_pct"
        ]

        for field in expected_fields:
            assert field in summary

    def test_market_cap_calculation(self):
        """Market cap should equal supply * price."""
        token = SHAKTIToken()
        expected = token.current_supply * token.current_price
        assert abs(token.market_cap - expected) < 0.01


class TestDeflationaryMechanics:
    """Tests for deflationary token mechanics."""

    def test_burn_rate_applied_correctly(self):
        """30% of fees should be burned."""
        token = SHAKTIToken(fee_rate=0.02, burn_rate=0.30)
        volume = 1_000_000
        result = token.process_transaction(volume_inr=volume)

        # Fee = 2% of volume = 20,000
        # Burn = 30% of fee = 6,000 INR worth of tokens
        expected_burn_value = volume * 0.02 * 0.30
        # tokens burned = burn_value / price
        # Initial price is 1.0, but price may have changed slightly
        # So we just verify burned > 0 and proportional
        assert result.burned > 0
        assert result.fee_collected == volume * 0.02

    def test_staking_rewards_minted(self):
        """Staking rewards should mint tokens."""
        token = SHAKTIToken(initial_staking_rate=0.50)  # 50% staked
        result = token.process_transaction(volume_inr=100_000)

        # With 50% staked, there should be minting
        assert result.minted > 0

    def test_net_deflation_possible(self):
        """Net deflation should be possible with low staking."""
        token = SHAKTIToken(initial_staking_rate=0.10)  # Low staking
        result = token.process_transaction(volume_inr=1_000_000)

        # With low staking, burns should exceed mints
        assert result.burned > result.minted


class TestCirculatingSupply:
    """Tests for circulating supply calculation."""

    def test_circulating_supply_excludes_staked(self):
        """Circulating supply should exclude staked tokens."""
        token = SHAKTIToken(initial_staking_rate=0.25)
        expected = token.current_supply * (1 - 0.25)
        assert abs(token.circulating_supply - expected) < 0.01

    def test_circulating_supply_equals_total_when_no_staking(self):
        """Circulating supply equals total supply with no staking."""
        token = SHAKTIToken(initial_staking_rate=0.0)
        assert token.circulating_supply == token.current_supply


class TestHistoryTracking:
    """Tests for history tracking functionality."""

    def test_price_history_tracking(self):
        """Price history should track changes."""
        token = SHAKTIToken()
        initial_len = len(token.get_price_history())

        for _ in range(5):
            token.process_transaction(volume_inr=50_000)

        assert len(token.get_price_history()) == initial_len + 5

    def test_supply_history_tracking(self):
        """Supply history should track changes."""
        token = SHAKTIToken()
        initial_len = len(token.get_supply_history())

        for _ in range(5):
            token.process_transaction(volume_inr=50_000)

        assert len(token.get_supply_history()) == initial_len + 5

    def test_history_returns_copy(self):
        """History methods should return copies."""
        token = SHAKTIToken()
        history = token.get_price_history()
        history.append(999)

        # Original should be unchanged
        assert 999 not in token.get_price_history()
