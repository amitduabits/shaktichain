"""
Tests for the Agent module.

Tests cover:
- SOC updates correctly
- Role switching based on SOC
- Bid generation is within valid range
"""

import pytest
from core.agents import Prosumer, Bid


class TestProsumerSOCUpdates:
    """Test SOC update functionality."""

    def test_soc_increases_when_buying(self):
        """SOC should increase when buying (charging)."""
        prosumer = Prosumer(
            agent_id="test-1",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.5
        )

        initial_soc = prosumer.current_soc
        prosumer.update_soc(quantity=10.0, is_buying=True)

        expected_soc = initial_soc + (10.0 / 50.0)  # 0.5 + 0.2 = 0.7
        assert prosumer.current_soc == pytest.approx(expected_soc)

    def test_soc_decreases_when_selling(self):
        """SOC should decrease when selling (discharging)."""
        prosumer = Prosumer(
            agent_id="test-2",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.8
        )

        initial_soc = prosumer.current_soc
        prosumer.update_soc(quantity=10.0, is_buying=False)

        expected_soc = initial_soc - (10.0 / 50.0)  # 0.8 - 0.2 = 0.6
        assert prosumer.current_soc == pytest.approx(expected_soc)

    def test_soc_capped_at_one_when_overcharging(self):
        """SOC should not exceed 1.0 even if charged beyond capacity."""
        prosumer = Prosumer(
            agent_id="test-3",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.9
        )

        prosumer.update_soc(quantity=20.0, is_buying=True)  # Would be 1.3 without cap

        assert prosumer.current_soc == 1.0

    def test_soc_floored_at_zero_when_overdischarging(self):
        """SOC should not go below 0.0 even if discharged beyond available."""
        prosumer = Prosumer(
            agent_id="test-4",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.1
        )

        prosumer.update_soc(quantity=20.0, is_buying=False)  # Would be -0.3 without floor

        assert prosumer.current_soc == 0.0

    def test_soc_update_rejects_negative_quantity(self):
        """update_soc should raise ValueError for negative quantity."""
        prosumer = Prosumer(
            agent_id="test-5",
            agent_type="residential"
        )

        with pytest.raises(ValueError, match="quantity must be non-negative"):
            prosumer.update_soc(quantity=-5.0, is_buying=True)


class TestProsumerRoleSwitching:
    """Test role decision based on SOC and time."""

    def test_low_soc_always_buyer(self):
        """With low SOC (< 0.2), prosumer should always be a buyer."""
        prosumer = Prosumer(
            agent_id="test-6",
            agent_type="residential",
            current_soc=0.1  # Below min_soc_threshold
        )

        # Test across different hours including peak
        for hour in [0, 6, 12, 18, 23]:
            assert prosumer.decide_role(hour) == "buyer"

    def test_high_soc_always_seller(self):
        """With high SOC (> 0.8), prosumer should always be a seller."""
        prosumer = Prosumer(
            agent_id="test-7",
            agent_type="commercial",
            current_soc=0.9  # Above max_soc_threshold
        )

        # Test across different hours
        for hour in [0, 6, 12, 18, 23]:
            assert prosumer.decide_role(hour) == "seller"

    def test_medium_soc_seller_during_peak(self):
        """With medium SOC during peak hours, prosumer should be seller."""
        prosumer = Prosumer(
            agent_id="test-8",
            agent_type="fleet",
            current_soc=0.5  # Medium SOC
        )

        # Peak hours are 17, 18, 19, 20, 21
        for hour in [17, 18, 19, 20, 21]:
            assert prosumer.decide_role(hour) == "seller"

    def test_medium_soc_buyer_during_offpeak(self):
        """With medium SOC during off-peak hours, prosumer should be buyer."""
        prosumer = Prosumer(
            agent_id="test-9",
            agent_type="residential",
            current_soc=0.5  # Medium SOC
        )

        # Off-peak hours
        for hour in [0, 6, 10, 14, 22]:
            assert prosumer.decide_role(hour) == "buyer"

    def test_role_decision_rejects_invalid_hour(self):
        """decide_role should raise ValueError for invalid hour."""
        prosumer = Prosumer(
            agent_id="test-10",
            agent_type="residential"
        )

        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            prosumer.decide_role(24)

        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            prosumer.decide_role(-1)


class TestProsumerBidGeneration:
    """Test bid generation functionality."""

    def test_bid_has_correct_agent_id(self):
        """Generated bid should have correct agent_id."""
        prosumer = Prosumer(
            agent_id="test-11",
            agent_type="residential",
            current_soc=0.5
        )

        bid = prosumer.generate_bid(current_price=5.0, hour=12)

        assert bid.agent_id == "test-11"

    def test_bid_role_matches_decide_role(self):
        """Bid role should match the decide_role output."""
        prosumer = Prosumer(
            agent_id="test-12",
            agent_type="residential",
            current_soc=0.1  # Low SOC = buyer
        )

        bid = prosumer.generate_bid(current_price=5.0, hour=12)

        assert bid.role == "buyer"

    def test_bid_price_within_valid_range(self):
        """Bid price should be near true valuation (within ±15% considering noise and market)."""
        prosumer = Prosumer(
            agent_id="test-13",
            agent_type="commercial",
            true_valuation=6.0,
            current_soc=0.5
        )

        # Generate multiple bids to test price range
        for _ in range(20):
            bid = prosumer.generate_bid(current_price=6.0, hour=12)
            # Price should be within reasonable range of valuation
            assert 4.0 <= bid.price <= 8.0

    def test_bid_quantity_positive(self):
        """Bid quantity should be positive when there's available capacity."""
        prosumer = Prosumer(
            agent_id="test-14",
            agent_type="fleet",
            battery_capacity=100.0,
            current_soc=0.5
        )

        bid = prosumer.generate_bid(current_price=5.0, hour=12)

        assert bid.quantity >= 0

    def test_bid_quantity_limited_by_capacity(self):
        """Bid quantity should not exceed 30% of battery capacity."""
        prosumer = Prosumer(
            agent_id="test-15",
            agent_type="fleet",
            battery_capacity=100.0,
            current_soc=0.5
        )

        bid = prosumer.generate_bid(current_price=5.0, hour=12)

        max_quantity = 100.0 * 0.3  # 30% of capacity
        assert bid.quantity <= max_quantity

    def test_buyer_bid_quantity_limited_by_energy_needed(self):
        """Buyer bid quantity should not exceed energy needed to full charge."""
        prosumer = Prosumer(
            agent_id="test-16",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.75  # Below max_threshold, off-peak = buyer, needs 12.5 kWh
        )

        bid = prosumer.generate_bid(current_price=5.0, hour=12)  # Off-peak = buyer

        assert bid.role == "buyer"
        assert bid.quantity <= prosumer.energy_needed

    def test_seller_bid_quantity_limited_by_available_energy(self):
        """Seller bid quantity should not exceed available sellable energy."""
        prosumer = Prosumer(
            agent_id="test-17",
            agent_type="commercial",
            battery_capacity=50.0,
            current_soc=0.9  # High SOC = seller
        )

        bid = prosumer.generate_bid(current_price=5.0, hour=18)  # Peak hour

        assert bid.quantity <= prosumer.available_energy


class TestProsumerUtility:
    """Test utility computation."""

    def test_buyer_positive_utility_when_buying_cheap(self):
        """Buyer should have positive utility when price < valuation."""
        prosumer = Prosumer(
            agent_id="test-18",
            agent_type="residential",
            true_valuation=6.0
        )

        # Buying at 4 INR/kWh when valuation is 6 INR/kWh
        utility = prosumer.compute_buyer_utility(price=4.0, quantity=10.0)

        assert utility == pytest.approx(20.0)  # (6 - 4) * 10

    def test_seller_positive_utility_when_selling_high(self):
        """Seller should have positive utility when price > valuation."""
        prosumer = Prosumer(
            agent_id="test-19",
            agent_type="commercial",
            true_valuation=6.0
        )

        # Selling at 8 INR/kWh when valuation is 6 INR/kWh
        utility = prosumer.compute_seller_utility(price=8.0, quantity=10.0)

        assert utility == pytest.approx(20.0)  # (8 - 6) * 10

    def test_buyer_negative_utility_when_buying_expensive(self):
        """Buyer should have negative utility when price > valuation."""
        prosumer = Prosumer(
            agent_id="test-20",
            agent_type="residential",
            true_valuation=6.0
        )

        utility = prosumer.compute_buyer_utility(price=8.0, quantity=10.0)

        assert utility == pytest.approx(-20.0)  # (6 - 8) * 10


class TestProsumerValidation:
    """Test input validation."""

    def test_rejects_invalid_soc(self):
        """Should reject SOC outside 0-1 range."""
        with pytest.raises(ValueError, match="current_soc must be between 0 and 1"):
            Prosumer(
                agent_id="test-21",
                agent_type="residential",
                current_soc=1.5
            )

        with pytest.raises(ValueError, match="current_soc must be between 0 and 1"):
            Prosumer(
                agent_id="test-22",
                agent_type="residential",
                current_soc=-0.1
            )

    def test_rejects_negative_battery_capacity(self):
        """Should reject non-positive battery capacity."""
        with pytest.raises(ValueError, match="battery_capacity must be positive"):
            Prosumer(
                agent_id="test-23",
                agent_type="fleet",
                battery_capacity=-50.0
            )

    def test_rejects_negative_valuation(self):
        """Should reject negative true valuation."""
        with pytest.raises(ValueError, match="true_valuation must be non-negative"):
            Prosumer(
                agent_id="test-24",
                agent_type="commercial",
                true_valuation=-1.0
            )


class TestProsumerProperties:
    """Test computed properties."""

    def test_available_energy_calculation(self):
        """available_energy should respect minimum SOC threshold."""
        prosumer = Prosumer(
            agent_id="test-25",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.5,
            min_soc_threshold=0.2
        )

        # Available = (0.5 - 0.2) * 50 = 15 kWh
        assert prosumer.available_energy == pytest.approx(15.0)

    def test_available_energy_zero_when_below_threshold(self):
        """available_energy should be zero when SOC < min threshold."""
        prosumer = Prosumer(
            agent_id="test-26",
            agent_type="residential",
            battery_capacity=50.0,
            current_soc=0.15,
            min_soc_threshold=0.2
        )

        assert prosumer.available_energy == pytest.approx(0.0)

    def test_energy_needed_calculation(self):
        """energy_needed should calculate correctly."""
        prosumer = Prosumer(
            agent_id="test-27",
            agent_type="fleet",
            battery_capacity=100.0,
            current_soc=0.7
        )

        # Needed = (1 - 0.7) * 100 = 30 kWh
        assert prosumer.energy_needed == pytest.approx(30.0)
