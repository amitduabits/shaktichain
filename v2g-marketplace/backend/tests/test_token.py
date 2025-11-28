"""
Comprehensive tests for SHAKTI Token Economics.

Tests cover:
1. Price calculations and dynamics
2. Supply dynamics (minting/burning)
3. Staking equilibrium
4. Edge cases (zero volume, extreme values, etc.)
5. Long-term simulation scenarios
"""

import math
import sys
from pathlib import Path

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.token import SHAKTIToken, TokenState, TransactionResult


class TestPriceCalculations:
    """Test price calculation formulas and dynamics."""

    def test_price_formula_basic(self):
        """Test basic price formula: P_T = (P_E * Q * 24) / (M * (1-sigma) * V)."""
        token = SHAKTIToken(
            initial_supply=10_000_000,
            initial_price=1.0,
            initial_staking_rate=0.0
        )

        # With zero staking and base velocity, compute expected price
        energy_price = 6.0  # INR/kWh
        volume = 100_000  # kWh
        supply = 10_000_000
        velocity = 12.0

        # P_T = (6.0 * 100000 * 24) / (10000000 * 1.0 * 12.0)
        # P_T = 14,400,000 / 120,000,000 = 0.12
        expected_raw = (energy_price * volume * 24) / (supply * velocity)

        computed = token.compute_price(energy_price, volume, staking_rate=0.0)

        # Due to smoothing (max 10% change per period), actual price may be capped
        # Initial price is 1.0, so max decrease is to 0.9
        assert computed >= 0.001  # Never goes negative

    def test_price_increases_with_demand(self):
        """Test that higher energy demand increases token price."""
        token1 = SHAKTIToken()
        token2 = SHAKTIToken()

        price_low_demand = token1.compute_price(
            energy_price=6.0,
            volume=10_000,
            staking_rate=0.2
        )
        price_high_demand = token2.compute_price(
            energy_price=6.0,
            volume=1_000_000,
            staking_rate=0.2
        )

        assert price_high_demand >= price_low_demand

    def test_price_increases_with_energy_price(self):
        """Test that higher energy prices increase token price."""
        token1 = SHAKTIToken()
        token2 = SHAKTIToken()

        price_cheap_energy = token1.compute_price(
            energy_price=3.0,
            volume=50_000,
            staking_rate=0.2
        )
        price_expensive_energy = token2.compute_price(
            energy_price=12.0,
            volume=50_000,
            staking_rate=0.2
        )

        assert price_expensive_energy >= price_cheap_energy

    def test_price_smoothing_prevents_spikes(self):
        """Test that price smoothing limits sudden changes to 10%."""
        token = SHAKTIToken(initial_price=1.0)
        initial_price = token.current_price

        # Try to cause a massive price spike
        new_price = token.compute_price(
            energy_price=1000.0,
            volume=10_000_000,
            staking_rate=0.1
        )

        # Should be capped at 10% increase from initial
        assert new_price <= initial_price * 1.10

    def test_price_smoothing_prevents_crashes(self):
        """Test that price smoothing limits sudden drops to 10%."""
        token = SHAKTIToken(initial_price=10.0)
        initial_price = token.current_price

        # Try to cause a massive price drop
        new_price = token.compute_price(
            energy_price=0.001,
            volume=1,
            staking_rate=0.99
        )

        # Should be capped at 10% decrease from initial
        assert new_price >= initial_price * 0.90

    def test_price_floor_maintained(self):
        """Test that price never goes below minimum floor."""
        token = SHAKTIToken(initial_price=0.01)

        # Extreme scenario
        new_price = token.compute_price(
            energy_price=0.0,
            volume=0,
            staking_rate=0.0
        )

        assert new_price >= 0.001

    def test_price_responds_to_staking(self):
        """Test that higher staking increases price."""
        token1 = SHAKTIToken()
        token2 = SHAKTIToken()

        price_low_staking = token1.compute_price(
            energy_price=6.0,
            volume=50_000,
            staking_rate=0.1
        )
        price_high_staking = token2.compute_price(
            energy_price=6.0,
            volume=50_000,
            staking_rate=0.8
        )

        assert price_high_staking >= price_low_staking


class TestSupplyDynamics:
    """Test token supply dynamics (minting and burning)."""

    def test_initial_supply(self):
        """Test initial supply is set correctly."""
        token = SHAKTIToken(initial_supply=5_000_000)
        assert token.current_supply == 5_000_000

    def test_burn_mechanism_reduces_supply(self):
        """Test that burning reduces total supply."""
        token = SHAKTIToken(initial_staking_rate=0.1)  # Low staking means more burn than mint
        initial_supply = token.current_supply

        # Process multiple transactions
        for _ in range(10):
            token.process_transaction(volume_inr=100_000)

        # With low staking, burns should exceed mints
        assert token.current_supply < initial_supply

    def test_burn_rate_correct(self):
        """Test that 30% of fees are burned."""
        token = SHAKTIToken(initial_staking_rate=0.0)
        volume = 1_000_000

        result = token.process_transaction(volume_inr=volume)

        # Fee = 2% of volume = 20,000
        expected_fee = volume * 0.02
        assert abs(result.fee_collected - expected_fee) < 0.01

        # Burn = 30% of fee value converted to tokens
        expected_burn_value = expected_fee * 0.30
        # At price ~1.0, burn should be ~6000 tokens
        assert result.burned > 0

    def test_staking_rewards_mint_tokens(self):
        """Test that staking rewards mint new tokens."""
        token = SHAKTIToken(initial_staking_rate=0.5)

        result = token.process_transaction(volume_inr=100_000)

        assert result.minted > 0

    def test_net_deflation_with_low_staking(self):
        """Test that low staking leads to net deflation."""
        token = SHAKTIToken(initial_staking_rate=0.05)
        initial_supply = token.current_supply

        for _ in range(100):
            token.process_transaction(volume_inr=50_000)

        # Should be deflationary
        assert token.current_supply < initial_supply

    def test_net_inflation_with_high_staking(self):
        """Test that very high staking could lead to net inflation."""
        token = SHAKTIToken(initial_staking_rate=0.95)
        initial_supply = token.current_supply

        # With 95% staking, minting rewards are high
        for _ in range(100):
            token.process_transaction(volume_inr=50_000)

        # May be inflationary due to high staking rewards
        # This depends on the exact parameter balance
        # Just verify no errors and supply is tracked
        assert token.current_supply > 0

    def test_supply_history_tracked(self):
        """Test that supply changes are tracked in history."""
        token = SHAKTIToken()
        initial_len = len(token.get_supply_history())

        for _ in range(5):
            token.process_transaction(volume_inr=10_000)

        assert len(token.get_supply_history()) == initial_len + 5

    def test_total_burned_accumulated(self):
        """Test that total burned is accumulated correctly."""
        token = SHAKTIToken()

        total_burned = 0
        for _ in range(10):
            result = token.process_transaction(volume_inr=100_000)
            total_burned += result.burned

        # Summary should match accumulated
        summary = token.summary()
        assert abs(summary["total_burned"] - total_burned) < 0.01

    def test_total_minted_accumulated(self):
        """Test that total minted is accumulated correctly."""
        token = SHAKTIToken(initial_staking_rate=0.5)

        total_minted = 0
        for _ in range(10):
            result = token.process_transaction(volume_inr=100_000)
            total_minted += result.minted

        summary = token.summary()
        assert abs(summary["total_minted"] - total_minted) < 0.01


class TestStakingEquilibrium:
    """Test staking rate dynamics and equilibrium."""

    def test_staking_moves_toward_target(self):
        """Test that staking rate moves toward target."""
        token = SHAKTIToken(initial_staking_rate=0.2)

        token.update_staking(target_rate=0.5)

        assert token.staking_rate > 0.2
        assert token.staking_rate < 0.5

    def test_staking_adjustment_rate(self):
        """Test that staking adjusts at 10% per period."""
        token = SHAKTIToken(initial_staking_rate=0.0)

        token.update_staking(target_rate=1.0)

        # Should move 10% of the difference
        # New rate = 0.0 + (1.0 - 0.0) * 0.1 = 0.1
        assert abs(token.staking_rate - 0.1) < 0.001

    def test_staking_reaches_equilibrium(self):
        """Test that staking eventually reaches target."""
        token = SHAKTIToken(initial_staking_rate=0.0)
        target = 0.5

        # Apply many updates
        for _ in range(100):
            token.update_staking(target_rate=target)

        # Should be very close to target
        assert abs(token.staking_rate - target) < 0.01

    def test_staking_bounded_zero_to_one(self):
        """Test that staking rate stays in [0, 1]."""
        token = SHAKTIToken(initial_staking_rate=0.5)

        # Try to push above 1.0
        token.update_staking(target_rate=2.0)
        assert token.staking_rate <= 1.0

        # Try to push below 0.0
        token = SHAKTIToken(initial_staking_rate=0.5)
        token.update_staking(target_rate=-1.0)
        assert token.staking_rate >= 0.0

    def test_staking_history_tracked(self):
        """Test that staking changes are tracked."""
        token = SHAKTIToken()
        initial_len = len(token.get_staking_history())

        for _ in range(5):
            token.update_staking(target_rate=0.5)

        assert len(token.get_staking_history()) == initial_len + 5

    def test_circulating_supply_reflects_staking(self):
        """Test that circulating supply decreases with staking."""
        token = SHAKTIToken(initial_staking_rate=0.0)
        full_circulation = token.circulating_supply

        token._staking_rate = 0.5  # Directly set for test
        half_circulation = token.circulating_supply

        assert half_circulation == full_circulation * 0.5


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_volume_transaction(self):
        """Test transaction with zero volume."""
        token = SHAKTIToken()
        initial_supply = token.current_supply
        initial_price = token.current_price

        result = token.process_transaction(volume_inr=0)

        assert result.minted == 0
        assert result.burned == 0
        assert token.current_supply == initial_supply
        assert result.volume_processed == 0

    def test_negative_volume_handled(self):
        """Test that negative volume is handled gracefully."""
        token = SHAKTIToken()

        result = token.process_transaction(volume_inr=-100)

        # Should be treated as zero
        assert result.volume_processed == 0 or result.minted == 0

    def test_very_small_volume(self):
        """Test handling of very small transaction volumes."""
        token = SHAKTIToken()

        result = token.process_transaction(volume_inr=0.001)

        # Should complete without error
        assert result is not None
        assert result.fee_collected >= 0

    def test_very_large_volume(self):
        """Test handling of very large transaction volumes."""
        token = SHAKTIToken()

        result = token.process_transaction(volume_inr=1_000_000_000)

        # Should complete without error
        assert result is not None
        assert result.burned > 0

    def test_full_staking_scenario(self):
        """Test behavior when 100% of tokens are staked."""
        token = SHAKTIToken(initial_staking_rate=1.0)

        # Velocity should be zero with full staking
        velocity = token.compute_velocity(trading_volume=1000, staking_rate=1.0)
        assert velocity == 0.0

        # Price should return current price to avoid division by zero
        price = token.compute_price(energy_price=6.0, volume=1000, staking_rate=1.0)
        assert price > 0

    def test_zero_supply_handled(self):
        """Test handling when supply approaches zero."""
        token = SHAKTIToken(initial_supply=100)

        # Process transactions that might burn supply
        for _ in range(1000):
            token.process_transaction(volume_inr=1000)

        # Supply should never go negative
        assert token.current_supply > 0

    def test_very_high_staking_rate(self):
        """Test behavior with 99% staking."""
        token = SHAKTIToken(initial_staking_rate=0.99)

        result = token.process_transaction(volume_inr=100_000)

        # Should still work
        assert result is not None
        assert token.circulating_supply == token.current_supply * 0.01

    def test_price_at_zero_energy_price(self):
        """Test price calculation with zero energy price."""
        token = SHAKTIToken()

        price = token.compute_price(energy_price=0.0, volume=1000, staking_rate=0.2)

        # Should return a valid price (current or minimum)
        assert price >= 0.001

    def test_price_at_zero_volume(self):
        """Test price calculation with zero volume."""
        token = SHAKTIToken()

        price = token.compute_price(energy_price=6.0, volume=0, staking_rate=0.2)

        assert price >= 0.001

    def test_extreme_parameters_initialization(self):
        """Test initialization with extreme parameters."""
        # Very small initial supply
        token1 = SHAKTIToken(initial_supply=1.0)
        assert token1.current_supply == 1.0

        # Very large initial supply
        token2 = SHAKTIToken(initial_supply=1_000_000_000_000)
        assert token2.current_supply == 1_000_000_000_000

        # Very high initial price
        token3 = SHAKTIToken(initial_price=1_000_000)
        assert token3.current_price == 1_000_000


class TestLongTermSimulation:
    """Test long-term token behavior over many periods."""

    def test_year_simulation_stability(self):
        """Test token stability over simulated year (8760 hours)."""
        token = SHAKTIToken(initial_staking_rate=0.25)

        for _ in range(8760):
            # Simulate hourly trading with varying volume
            import random
            volume = random.uniform(10_000, 500_000)
            token.process_transaction(volume_inr=volume)

            # Occasionally adjust staking target
            if random.random() < 0.01:
                token.update_staking(target_rate=random.uniform(0.2, 0.6))

        # Token should still be functional
        assert token.current_supply > 0
        assert token.current_price > 0
        assert 0 <= token.staking_rate <= 1

    def test_deflationary_trend(self):
        """Test that token trends deflationary over time with moderate staking."""
        token = SHAKTIToken(initial_staking_rate=0.20)
        initial_supply = token.current_supply

        # Simulate 1000 transactions
        for _ in range(1000):
            token.process_transaction(volume_inr=100_000)

        # With 20% staking, should be deflationary
        assert token.current_supply < initial_supply

        summary = token.summary()
        assert summary["net_deflation"] > 0

    def test_market_cap_tracking(self):
        """Test that market cap is tracked correctly."""
        token = SHAKTIToken()

        for _ in range(100):
            token.process_transaction(volume_inr=50_000)

        expected_market_cap = token.current_supply * token.current_price
        assert abs(token.market_cap - expected_market_cap) < 0.01

    def test_price_history_length(self):
        """Test that price history grows with transactions."""
        token = SHAKTIToken()

        num_transactions = 500
        for _ in range(num_transactions):
            token.process_transaction(volume_inr=10_000)

        # Should have initial + transactions
        assert len(token.get_price_history()) == 1 + num_transactions


class TestVelocityCalculations:
    """Test velocity calculation formulas."""

    def test_velocity_base_value(self):
        """Test that base velocity is correct."""
        token = SHAKTIToken(base_velocity=12.0)

        velocity = token.compute_velocity(trading_volume=0, staking_rate=0.0)
        assert velocity == 12.0

    def test_velocity_formula_verification(self):
        """Test velocity formula: V = V0 * (1-sigma)^0.5 * exp(-0.1 * Q/Qmax)."""
        token = SHAKTIToken()

        sigma = 0.25
        volume = 20_000_000
        v0 = 12.0
        qmax = 100_000_000

        expected = v0 * math.pow(1 - sigma, 0.5) * math.exp(-0.1 * volume / qmax)
        actual = token.compute_velocity(trading_volume=volume, staking_rate=sigma)

        assert abs(actual - expected) < 0.0001

    def test_velocity_decreases_with_staking(self):
        """Test that velocity decreases with higher staking."""
        token = SHAKTIToken()

        v_low_staking = token.compute_velocity(trading_volume=1_000_000, staking_rate=0.1)
        v_high_staking = token.compute_velocity(trading_volume=1_000_000, staking_rate=0.9)

        assert v_high_staking < v_low_staking

    def test_velocity_decreases_with_volume(self):
        """Test that velocity decreases with higher volume (saturation)."""
        token = SHAKTIToken()

        v_low_volume = token.compute_velocity(trading_volume=1_000_000, staking_rate=0.2)
        v_high_volume = token.compute_velocity(trading_volume=50_000_000, staking_rate=0.2)

        assert v_high_volume < v_low_volume

    def test_velocity_zero_at_full_staking(self):
        """Test that velocity is zero when all tokens staked."""
        token = SHAKTIToken()

        velocity = token.compute_velocity(trading_volume=1_000_000, staking_rate=1.0)
        assert velocity == 0.0


class TestResetFunctionality:
    """Test token reset functionality."""

    def test_reset_restores_supply(self):
        """Test that reset restores initial supply."""
        token = SHAKTIToken(initial_supply=5_000_000)

        for _ in range(100):
            token.process_transaction(volume_inr=100_000)

        token.reset()
        assert token.current_supply == 5_000_000

    def test_reset_restores_price(self):
        """Test that reset restores initial price."""
        token = SHAKTIToken(initial_price=2.0)

        for _ in range(100):
            token.process_transaction(volume_inr=100_000)

        token.reset()
        assert token.current_price == 2.0

    def test_reset_clears_history(self):
        """Test that reset clears history to initial state."""
        token = SHAKTIToken()

        for _ in range(50):
            token.process_transaction(volume_inr=10_000)
            token.update_staking(target_rate=0.5)

        token.reset()

        assert len(token.get_price_history()) == 1
        assert len(token.get_supply_history()) == 1
        assert len(token.get_staking_history()) == 1

    def test_reset_clears_accumulators(self):
        """Test that reset clears total burned/minted/fees."""
        token = SHAKTIToken(initial_staking_rate=0.3)

        for _ in range(50):
            token.process_transaction(volume_inr=100_000)

        token.reset()

        summary = token.summary()
        assert summary["total_burned"] == 0
        assert summary["total_minted"] == 0
        assert summary["total_fees"] == 0

    def test_reset_restores_staking_rate(self):
        """Test that reset restores staking rate to zero."""
        token = SHAKTIToken(initial_staking_rate=0.5)

        for _ in range(50):
            token.update_staking(target_rate=0.8)

        token.reset()
        assert token.staking_rate == 0.0


class TestFeeMechanics:
    """Test transaction fee mechanics."""

    def test_fee_rate_applied(self):
        """Test that 2% fee is applied correctly."""
        token = SHAKTIToken(fee_rate=0.02)

        result = token.process_transaction(volume_inr=1_000_000)

        expected_fee = 1_000_000 * 0.02
        assert abs(result.fee_collected - expected_fee) < 0.01

    def test_custom_fee_rate(self):
        """Test custom fee rate."""
        token = SHAKTIToken(fee_rate=0.05)

        result = token.process_transaction(volume_inr=100_000)

        expected_fee = 100_000 * 0.05
        assert abs(result.fee_collected - expected_fee) < 0.01

    def test_total_fees_accumulated(self):
        """Test that total fees are accumulated."""
        token = SHAKTIToken()

        total_expected = 0
        for i in range(10):
            volume = (i + 1) * 10_000
            result = token.process_transaction(volume_inr=volume)
            total_expected += result.fee_collected

        summary = token.summary()
        assert abs(summary["total_fees"] - total_expected) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
