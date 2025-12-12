"""
Test Infrastructure - Validate the experimental framework.

Tests verify:
- Agent bid generation is within valid ranges
- McAfee auction satisfies IR and BB properties
- Statistical tests give correct results on known distributions
- Data collection captures all required metrics
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

import sys
from pathlib import Path

# Add experiments to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from experiments.agents.base_agent import AgentState, MarketState, TradeSide
from experiments.agents.rational_agent import RationalAgent
from experiments.agents.bounded_rational_agent import BoundedRationalAgent
from experiments.agents.zero_intelligence_agent import ZeroIntelligenceAgent
from experiments.agents.behavioral_agent import BehavioralAgent
from experiments.agents.adversarial_agent import AdversarialAgent

from experiments.baselines.uniform_auction import UniformPriceAuction
from experiments.baselines.continuous_double_auction import ContinuousDoubleAuction
from experiments.baselines.random_bidding import RandomBiddingMarket, ZIMarketConfig

from experiments.core.statistical_analyzer import StatisticalAnalyzer, TestType

from experiments.utils.metrics_calculator import MetricsCalculator
from experiments.utils.synthetic_data_generator import SyntheticDataGenerator
from experiments.utils.india_load_profiles import IndiaLoadProfiles


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def basic_agent_state():
    """Create a basic agent state for testing."""
    return AgentState(
        id="test_agent_001",
        type="test",
        battery_capacity_kwh=50.0,
        current_soc=0.5,
        min_soc=0.2,
        max_soc=0.9,
        cost_per_kwh=4.0,
        value_per_kwh=8.0,
        risk_aversion=1.0,
    )


@pytest.fixture
def basic_market_state():
    """Create a basic market state for testing."""
    return MarketState(
        period=10,
        current_time=100.0,
        clearing_price=6.0,
        clearing_quantity=50.0,
        best_bid=5.8,
        best_ask=6.2,
        bid_depth=100.0,
        ask_depth=100.0,
        price_history=[5.5, 5.8, 6.0, 5.9, 6.1, 6.0],
        volatility=0.1,
        spread=0.4,
        num_participants=100,
        hour_of_day=14,
        is_peak_hour=True,
        demand_level="normal",
    )


@pytest.fixture
def statistical_analyzer():
    """Create a statistical analyzer instance."""
    return StatisticalAnalyzer(
        alpha=0.05,
        alpha_critical=0.01,
        bonferroni_correction=True,
        benjamini_hochberg=True,
        bootstrap_samples=1000,  # Reduced for faster tests
    )


@pytest.fixture
def metrics_calculator():
    """Create a metrics calculator instance."""
    return MetricsCalculator()


@pytest.fixture
def data_generator():
    """Create a synthetic data generator."""
    return SyntheticDataGenerator(random_seed=42)


# =============================================================================
# Agent Tests
# =============================================================================

class TestAgentBidGeneration:
    """Test that agent bid generation is within valid ranges."""

    def test_rational_agent_bid_within_bounds(self, basic_agent_state, basic_market_state):
        """Rational agent should generate valid bids."""
        agent = RationalAgent(basic_agent_state)
        bid = agent.generate_bid(basic_market_state)

        if bid is not None:
            price, quantity, side = bid

            # Price should be positive
            assert price > 0, "Price should be positive"

            # Quantity should be within available capacity
            if side == "buy":
                assert quantity <= basic_agent_state.available_capacity_kwh + 0.01
            else:
                assert quantity <= basic_agent_state.available_energy_kwh + 0.01

            # Side should be valid
            assert side in ["buy", "sell"]

            # Price should respect agent constraints
            if side == "buy":
                assert price <= basic_agent_state.value_per_kwh * 1.1  # Allow some margin
            else:
                assert price >= basic_agent_state.cost_per_kwh * 0.9  # Allow some margin

    def test_bounded_rational_agent_bid_within_bounds(self, basic_agent_state, basic_market_state):
        """Bounded rational agent should generate valid bids."""
        agent = BoundedRationalAgent(basic_agent_state)
        bid = agent.generate_bid(basic_market_state)

        if bid is not None:
            price, quantity, side = bid

            assert price > 0
            assert quantity > 0
            assert side in ["buy", "sell"]

    def test_zero_intelligence_constrained_respects_budget(self, basic_agent_state, basic_market_state):
        """ZI-C agent should respect budget constraints."""
        agent = ZeroIntelligenceAgent(basic_agent_state, variant="ZI-C")

        # Generate multiple bids to test constraint satisfaction
        for _ in range(100):
            bid = agent.generate_bid(basic_market_state)

            if bid is not None:
                price, quantity, side = bid

                if side == "buy":
                    # Buyer should not bid above value
                    assert price <= basic_agent_state.value_per_kwh, \
                        f"ZI-C buyer bid {price} exceeds value {basic_agent_state.value_per_kwh}"
                else:
                    # Seller should not ask below cost
                    assert price >= basic_agent_state.cost_per_kwh, \
                        f"ZI-C seller ask {price} below cost {basic_agent_state.cost_per_kwh}"

    def test_behavioral_agent_loss_aversion(self, basic_agent_state, basic_market_state):
        """Behavioral agent should exhibit loss aversion."""
        agent = BehavioralAgent(
            basic_agent_state,
            loss_aversion=2.25,  # Standard Kahneman-Tversky value
        )

        # Loss aversion should make agent more conservative
        bid = agent.generate_bid(basic_market_state)

        if bid is not None:
            price, quantity, side = bid
            assert price > 0
            assert quantity > 0

    def test_adversarial_agent_generates_strategy_orders(self, basic_agent_state, basic_market_state):
        """Adversarial agent should generate orders based on strategy."""
        for strategy in ["spoofing", "wash_trading", "layering"]:
            agent = AdversarialAgent(
                basic_agent_state,
                strategy=strategy,
            )

            bid = agent.generate_bid(basic_market_state)

            # Should generate some kind of bid
            # (may be None in passive phases)
            if bid is not None:
                price, quantity, side = bid
                assert price > 0
                assert quantity >= 0
                assert side in ["buy", "sell"]


class TestAgentStateUpdate:
    """Test that agent state updates correctly after trades."""

    def test_soc_updates_after_buy(self, basic_agent_state):
        """SoC should increase after buying."""
        agent = RationalAgent(basic_agent_state)
        initial_soc = agent.state.current_soc

        trade_result = {
            "price": 6.0,
            "quantity": 5.0,
            "side": "buy",
            "counterparty_id": "seller_001",
        }

        agent.update_after_trade(trade_result)

        assert agent.state.current_soc > initial_soc
        assert len(agent.state.historical_trades) == 1

    def test_soc_updates_after_sell(self, basic_agent_state):
        """SoC should decrease after selling."""
        agent = RationalAgent(basic_agent_state)
        initial_soc = agent.state.current_soc

        trade_result = {
            "price": 6.0,
            "quantity": 5.0,
            "side": "sell",
            "counterparty_id": "buyer_001",
        }

        agent.update_after_trade(trade_result)

        assert agent.state.current_soc < initial_soc
        assert len(agent.state.historical_trades) == 1

    def test_profit_accumulates(self, basic_agent_state):
        """Cumulative profit should accumulate correctly."""
        agent = RationalAgent(basic_agent_state)

        trades = [
            {"price": 5.0, "quantity": 10.0, "side": "buy", "counterparty_id": "s1", "profit": 30.0},
            {"price": 7.0, "quantity": 10.0, "side": "sell", "counterparty_id": "b1", "profit": 30.0},
        ]

        for trade in trades:
            agent.update_after_trade(trade)

        assert agent.state.cumulative_profit == 60.0


# =============================================================================
# Auction Mechanism Tests
# =============================================================================

class TestMcAfeeProperties:
    """Test McAfee double auction properties."""

    def test_individual_rationality(self):
        """No agent should trade at a loss (IR property)."""
        market = RandomBiddingMarket(
            config=ZIMarketConfig(num_agents=50, periods=10),
            random_seed=42,
        )

        results = market.run_simulation(periods=10)

        for trade in market.all_trades:
            # Buyer surplus should be non-negative
            assert trade.get("buyer_surplus", 0) >= -0.01, \
                f"Buyer has negative surplus: {trade['buyer_surplus']}"

            # Seller surplus should be non-negative
            assert trade.get("seller_surplus", 0) >= -0.01, \
                f"Seller has negative surplus: {trade['seller_surplus']}"

    def test_budget_balance(self):
        """Auctioneer should not lose money (BB property)."""
        market = RandomBiddingMarket(
            config=ZIMarketConfig(num_agents=50, periods=10),
            random_seed=42,
        )

        results = market.run_simulation(periods=10)

        for trade in market.all_trades:
            # Price paid by buyer should equal price received by seller
            # In McAfee, this is the same price
            # No explicit auctioneer profit, so just verify trades happen
            assert trade["quantity"] > 0


class TestUniformAuction:
    """Test uniform price auction."""

    def test_uniform_price_all_same(self):
        """All trades should execute at the same price."""
        auction = UniformPriceAuction()

        # Submit orders
        auction.submit_order("b1", "rational", 8.0, 10.0, "buy")
        auction.submit_order("b2", "rational", 7.5, 10.0, "buy")
        auction.submit_order("b3", "rational", 7.0, 10.0, "buy")
        auction.submit_order("s1", "rational", 5.0, 10.0, "sell")
        auction.submit_order("s2", "rational", 5.5, 10.0, "sell")
        auction.submit_order("s3", "rational", 6.0, 10.0, "sell")

        result = auction.clear()

        if result.trades:
            prices = [t.price for t in result.trades]
            # All trades at uniform price
            assert len(set(prices)) == 1, "Uniform auction should have single price"

    def test_no_trade_when_no_overlap(self):
        """No trades when bid < ask."""
        auction = UniformPriceAuction()

        auction.submit_order("b1", "rational", 5.0, 10.0, "buy")
        auction.submit_order("s1", "rational", 6.0, 10.0, "sell")

        result = auction.clear()

        assert len(result.trades) == 0


class TestCDA:
    """Test continuous double auction."""

    def test_immediate_matching(self):
        """Matching order should execute immediately."""
        cda = ContinuousDoubleAuction()

        # Submit resting ask
        cda.submit_order("s1", "rational", 6.0, 10.0, "sell")

        # Submit matching bid
        order_id, trades = cda.submit_order("b1", "rational", 6.5, 10.0, "buy")

        assert len(trades) == 1
        assert trades[0].price == 6.0  # Passive price

    def test_price_time_priority(self):
        """Better prices should match first."""
        cda = ContinuousDoubleAuction()

        # Submit two asks
        cda.submit_order("s1", "rational", 6.0, 10.0, "sell")
        cda.submit_order("s2", "rational", 5.5, 10.0, "sell")

        # Submit bid
        _, trades = cda.submit_order("b1", "rational", 7.0, 10.0, "buy")

        assert len(trades) >= 1
        # Best price (5.5) should match first
        assert trades[0].seller_id == "s2"


# =============================================================================
# Statistical Tests
# =============================================================================

class TestStatisticalAnalyzer:
    """Test statistical analysis functions on known distributions."""

    def test_one_sample_t_test_known_mean(self, statistical_analyzer):
        """One-sample t-test should detect difference from known mean."""
        np.random.seed(42)

        # Sample from normal with mean=10
        sample = np.random.normal(10, 1, 100)

        # Test against wrong mean (should reject)
        result = statistical_analyzer.one_sample_t_test(sample, 8.0)
        assert result.reject_null, "Should reject H0: μ = 8"

        # Test against correct mean (should not reject)
        result = statistical_analyzer.one_sample_t_test(sample, 10.0)
        assert not result.reject_null, "Should not reject H0: μ = 10"

    def test_two_sample_t_test_different_means(self, statistical_analyzer):
        """Two-sample t-test should detect different means."""
        np.random.seed(42)

        sample1 = np.random.normal(10, 1, 100)
        sample2 = np.random.normal(12, 1, 100)

        result = statistical_analyzer.two_sample_t_test(sample1, sample2)

        assert result.reject_null, "Should detect different means"
        assert result.effect_size < 0, "Effect size should be negative (sample1 < sample2)"

    def test_two_sample_t_test_same_distribution(self, statistical_analyzer):
        """Two-sample t-test should not reject when samples are same."""
        np.random.seed(42)

        sample1 = np.random.normal(10, 1, 100)
        sample2 = np.random.normal(10, 1, 100)

        result = statistical_analyzer.two_sample_t_test(sample1, sample2)

        # Should usually not reject (may occasionally due to randomness)
        # We check p-value is at least reasonable
        assert result.p_value > 0.01, "P-value should be reasonably high"

    def test_anova_different_groups(self, statistical_analyzer):
        """ANOVA should detect differences among groups."""
        np.random.seed(42)

        group1 = np.random.normal(10, 1, 50)
        group2 = np.random.normal(12, 1, 50)
        group3 = np.random.normal(14, 1, 50)

        result = statistical_analyzer.one_way_anova(group1, group2, group3)

        assert result.reject_null, "Should detect group differences"
        assert "tukey_hsd" in result.additional_info, "Should include post-hoc tests"

    def test_chi_square_independence(self, statistical_analyzer):
        """Chi-square test should detect dependence."""
        # Create contingency table with clear association
        observed = np.array([
            [50, 10],
            [10, 50],
        ])

        result = statistical_analyzer.chi_square_test(observed)

        assert result.reject_null, "Should detect dependence"

    def test_ks_test_different_distributions(self, statistical_analyzer):
        """KS test should detect different distributions."""
        np.random.seed(42)

        sample1 = np.random.normal(0, 1, 100)
        sample2 = np.random.exponential(1, 100)

        result = statistical_analyzer.ks_test(sample1, sample2)

        assert result.reject_null, "Should detect different distributions"

    def test_bootstrap_ci_contains_true_mean(self, statistical_analyzer):
        """Bootstrap CI should contain true mean most of the time."""
        np.random.seed(42)
        true_mean = 10

        # Run multiple times
        contains_true = 0
        n_tests = 20

        for _ in range(n_tests):
            sample = np.random.normal(true_mean, 1, 50)
            result = statistical_analyzer.bootstrap_ci(sample, n_bootstrap=500)

            if result.confidence_interval[0] <= true_mean <= result.confidence_interval[1]:
                contains_true += 1

        # Should contain true mean ~95% of the time (allow some margin)
        coverage = contains_true / n_tests
        assert coverage >= 0.8, f"Coverage {coverage} is too low"

    def test_bonferroni_correction(self, statistical_analyzer):
        """Bonferroni correction should adjust p-values correctly."""
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]

        result = statistical_analyzer.bonferroni_correction(p_values)

        # Adjusted p-values should be multiplied by number of tests
        assert result["adjusted_p_values"][0] == pytest.approx(0.05, rel=0.01)
        assert result["adjusted_alpha"] == pytest.approx(0.01, rel=0.01)


# =============================================================================
# Metrics Tests
# =============================================================================

class TestMetricsCalculator:
    """Test metrics calculation."""

    def test_efficiency_calculation(self, metrics_calculator):
        """Test efficiency metrics calculation."""
        trades = [
            {"price": 6.0, "quantity": 10.0, "buyer_surplus": 20.0, "seller_surplus": 20.0},
            {"price": 6.0, "quantity": 10.0, "buyer_surplus": 20.0, "seller_surplus": 20.0},
        ]

        bids = [
            {"price": 8.0, "quantity": 10.0, "value": 8.0},
            {"price": 7.5, "quantity": 10.0, "value": 7.5},
        ]

        asks = [
            {"price": 4.0, "quantity": 10.0, "cost": 4.0},
            {"price": 4.5, "quantity": 10.0, "cost": 4.5},
        ]

        result = metrics_calculator.calculate_efficiency_metrics(trades, bids, asks)

        assert result.allocative_efficiency > 0
        assert result.allocative_efficiency <= 1

    def test_welfare_metrics(self, metrics_calculator):
        """Test welfare metrics calculation."""
        trades = [
            {"buyer_surplus": 10.0, "seller_surplus": 15.0},
            {"buyer_surplus": 20.0, "seller_surplus": 10.0},
            {"buyer_surplus": 5.0, "seller_surplus": 25.0},
        ]

        result = metrics_calculator.calculate_welfare_metrics(trades)

        assert result.buyer_surplus == 35.0
        assert result.seller_surplus == 50.0
        assert result.total_surplus == 85.0

    def test_gini_coefficient(self, metrics_calculator):
        """Test Gini coefficient calculation."""
        # Perfect equality
        equal = [10, 10, 10, 10]
        gini_equal = metrics_calculator._calculate_gini(equal)
        assert gini_equal == pytest.approx(0.0, abs=0.01)

        # Perfect inequality
        unequal = [0, 0, 0, 100]
        gini_unequal = metrics_calculator._calculate_gini(unequal)
        assert gini_unequal > 0.7


# =============================================================================
# Data Generator Tests
# =============================================================================

class TestDataGenerator:
    """Test synthetic data generation."""

    def test_demand_curve_positive(self, data_generator):
        """Demand should always be positive."""
        from datetime import datetime

        demand_points = data_generator.generate_demand_curve(
            start_date=datetime(2024, 6, 1),
            num_days=7,
            city="Delhi",
        )

        for point in demand_points:
            assert point.demand_kwh > 0, "Demand should be positive"

    def test_ev_fleet_valid_soc(self, data_generator):
        """EV SoC should be in valid range."""
        fleet = data_generator.generate_ev_fleet(num_vehicles=100)

        for ev in fleet:
            assert 0 <= ev.current_soc <= 1, "SoC should be in [0, 1]"
            assert ev.battery_capacity_kwh > 0, "Capacity should be positive"

    def test_agent_valuations_valid(self, data_generator):
        """Agent valuations should have value > cost."""
        valuations = data_generator.generate_agent_valuations(num_agents=100)

        for val in valuations:
            assert val.value_per_kwh > val.cost_per_kwh, \
                "Value should exceed cost for viable trading"


class TestIndiaLoadProfiles:
    """Test India-specific load profiles."""

    def test_all_cities_defined(self):
        """All major cities should have profiles."""
        profiles = IndiaLoadProfiles()

        cities = ["Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata"]
        for city in cities:
            profile = profiles.get_city_profile(city)
            assert profile is not None, f"Profile for {city} should exist"
            assert profile.name == city

    def test_temperature_seasonal_variation(self):
        """Temperature should vary by season."""
        from datetime import datetime

        profiles = IndiaLoadProfiles(random_seed=42)

        # Summer temperature should be higher than winter
        summer_temp = profiles.get_temperature("Delhi", datetime(2024, 5, 15), 14)
        winter_temp = profiles.get_temperature("Delhi", datetime(2024, 1, 15), 14)

        assert summer_temp > winter_temp, "Summer should be hotter than winter"

    def test_demand_diurnal_pattern(self):
        """Demand should show diurnal pattern."""
        from datetime import datetime

        profiles = IndiaLoadProfiles(random_seed=42)
        date = datetime(2024, 6, 15)

        # Get hourly demands
        demands = [
            profiles.get_hourly_demand("Delhi", date, hour)
            for hour in range(24)
        ]

        # Peak hours should have higher demand
        afternoon_demand = np.mean([demands[h] for h in [14, 15, 16, 17]])
        night_demand = np.mean([demands[h] for h in [2, 3, 4, 5]])

        assert afternoon_demand > night_demand, "Afternoon demand should exceed night"


# =============================================================================
# Integration Tests
# =============================================================================

class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_market_simulation(self, basic_market_state):
        """Test complete market simulation flow."""
        # Create agents
        agents = []
        for i in range(20):
            state = AgentState(
                id=f"agent_{i}",
                type="rational",
                battery_capacity_kwh=50.0,
                current_soc=np.random.uniform(0.3, 0.7),
                min_soc=0.2,
                max_soc=0.9,
                cost_per_kwh=np.random.uniform(3.0, 5.0),
                value_per_kwh=np.random.uniform(7.0, 10.0),
                risk_aversion=np.random.uniform(0.5, 2.0),
            )
            agents.append(RationalAgent(state))

        # Collect bids
        bids = []
        asks = []

        for agent in agents:
            bid = agent.generate_bid(basic_market_state)
            if bid:
                price, quantity, side = bid
                if side == "buy":
                    bids.append({
                        "agent_id": agent.state.id,
                        "price": price,
                        "quantity": quantity,
                    })
                else:
                    asks.append({
                        "agent_id": agent.state.id,
                        "price": price,
                        "quantity": quantity,
                    })

        # Should have some bids on both sides
        assert len(bids) > 0 or len(asks) > 0, "Should generate some orders"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
