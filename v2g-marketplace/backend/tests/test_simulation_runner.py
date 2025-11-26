"""
Tests for V2G Marketplace Simulation Runner.

These tests verify the simulation runner correctly integrates
Indian demand patterns and produces meaningful comparisons.
"""

import pytest
from datetime import datetime

import sys
sys.path.insert(0, str(__file__).rsplit("/", 3)[0])

from simulation.runner import (
    SimulationRunner,
    SimulationConfig,
    SimulationResult,
    DemandMode,
    HourlyStats,
)


class TestSimulationConfig:
    """Test suite for SimulationConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SimulationConfig()

        assert config.duration_hours == 24
        assert config.time_step_minutes == 60
        assert config.demand_mode == DemandMode.REALISTIC
        assert config.base_demand_mw == 1000.0
        assert config.region == "Delhi"
        assert config.num_evs == 100

    def test_custom_config(self):
        """Test custom configuration."""
        config = SimulationConfig(
            duration_hours=48,
            demand_mode=DemandMode.FLAT,
            region="Mumbai",
            num_evs=500,
        )

        assert config.duration_hours == 48
        assert config.demand_mode == DemandMode.FLAT
        assert config.region == "Mumbai"
        assert config.num_evs == 500


class TestSimulationRunner:
    """Test suite for SimulationRunner."""

    @pytest.fixture
    def runner_realistic(self):
        """Create a runner with realistic demand mode."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            demand_mode=DemandMode.REALISTIC,
            region="Delhi",
            num_evs=50,
            random_seed=42,
        )
        return SimulationRunner(config)

    @pytest.fixture
    def runner_flat(self):
        """Create a runner with flat demand mode."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            demand_mode=DemandMode.FLAT,
            region="Delhi",
            num_evs=50,
            random_seed=42,
        )
        return SimulationRunner(config)

    # ==================== Basic Functionality Tests ====================

    def test_runner_initialization(self, runner_realistic):
        """Test runner initializes correctly."""
        assert runner_realistic.config is not None
        assert runner_realistic.load_profile is not None
        assert len(runner_realistic.ev_soc) == 50

    def test_ev_fleet_initialization(self, runner_realistic):
        """Test EV fleet SOC is within expected range."""
        for soc in runner_realistic.ev_soc:
            assert 0.3 <= soc <= 0.8

    def test_run_produces_result(self, runner_realistic):
        """Test simulation run produces a result."""
        result = runner_realistic.run()

        assert isinstance(result, SimulationResult)
        assert len(result.hourly_stats) == 24
        assert result.config == runner_realistic.config

    def test_hourly_stats_structure(self, runner_realistic):
        """Test hourly stats have correct structure."""
        result = runner_realistic.run()

        for stat in result.hourly_stats:
            assert isinstance(stat, HourlyStats)
            assert stat.demand_multiplier > 0
            assert stat.grid_demand_mw > 0
            assert stat.energy_price_inr > 0
            assert stat.evs_discharging >= 0
            assert stat.evs_charging >= 0
            assert stat.evs_idle >= 0

    # ==================== Demand Mode Tests ====================

    def test_flat_demand_constant(self, runner_flat):
        """Test flat demand mode produces constant multiplier."""
        result = runner_flat.run()

        multipliers = [stat.demand_multiplier for stat in result.hourly_stats]
        assert all(m == 1.0 for m in multipliers)

    def test_realistic_demand_varies(self, runner_realistic):
        """Test realistic demand mode produces varying multipliers."""
        result = runner_realistic.run()

        multipliers = [stat.demand_multiplier for stat in result.hourly_stats]
        assert min(multipliers) < max(multipliers)
        assert max(multipliers) > 2.0  # Should have significant peaks

    def test_hourly_only_mode(self):
        """Test hourly-only demand mode."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            demand_mode=DemandMode.HOURLY_ONLY,
            random_seed=42,
        )
        runner = SimulationRunner(config)
        result = runner.run()

        multipliers = [stat.demand_multiplier for stat in result.hourly_stats]
        # Should vary by hour only
        assert min(multipliers) < max(multipliers)
        # But less variance than full realistic (no seasonal/regional)
        assert max(multipliers) < 2.0  # Hourly max is 1.8

    # ==================== Comparison Tests ====================

    def test_compare_demand_modes(self, runner_realistic):
        """Test demand mode comparison functionality."""
        results = runner_realistic.compare_demand_modes()

        assert DemandMode.FLAT in results
        assert DemandMode.REALISTIC in results
        assert isinstance(results[DemandMode.FLAT], SimulationResult)
        assert isinstance(results[DemandMode.REALISTIC], SimulationResult)

    def test_realistic_has_higher_variance(self):
        """Test realistic mode has higher demand variance than flat."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            random_seed=42,
        )
        runner = SimulationRunner(config)
        results = runner.compare_demand_modes()

        flat_demands = [s.grid_demand_mw for s in results[DemandMode.FLAT].hourly_stats]
        real_demands = [s.grid_demand_mw for s in results[DemandMode.REALISTIC].hourly_stats]

        flat_variance = sum((d - sum(flat_demands)/len(flat_demands))**2 for d in flat_demands)
        real_variance = sum((d - sum(real_demands)/len(real_demands))**2 for d in real_demands)

        assert real_variance > flat_variance

    def test_realistic_has_price_variation(self):
        """Test realistic mode has price variation."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            random_seed=42,
        )
        runner = SimulationRunner(config)
        results = runner.compare_demand_modes()

        flat_result = results[DemandMode.FLAT]
        real_result = results[DemandMode.REALISTIC]

        # Flat should have constant price
        flat_prices = [s.energy_price_inr for s in flat_result.hourly_stats]
        assert max(flat_prices) - min(flat_prices) < 0.01

        # Realistic should have variable prices
        real_prices = [s.energy_price_inr for s in real_result.hourly_stats]
        assert max(real_prices) > min(real_prices) * 1.5

    # ==================== V2G Behavior Tests ====================

    def test_v2g_discharge_during_peaks(self, runner_realistic):
        """Test V2G discharge occurs during peak demand."""
        result = runner_realistic.run()

        # Find hours with discharge
        discharge_hours = [
            stat for stat in result.hourly_stats
            if stat.v2g_discharge_kwh > 0
        ]

        # Discharge should happen during high demand
        for stat in discharge_hours:
            assert stat.demand_multiplier >= 1.4

    def test_charging_during_low_demand(self, runner_realistic):
        """Test charging occurs during low demand periods."""
        result = runner_realistic.run()

        # Find hours with charging
        charging_hours = [
            stat for stat in result.hourly_stats
            if stat.charging_kwh > 0
        ]

        # Charging should happen during low demand
        for stat in charging_hours:
            assert stat.demand_multiplier < 0.8

    def test_ev_count_consistency(self, runner_realistic):
        """Test EV counts sum to total fleet size."""
        result = runner_realistic.run()

        for stat in result.hourly_stats:
            total = stat.evs_discharging + stat.evs_charging + stat.evs_idle
            assert total == runner_realistic.config.num_evs

    # ==================== Revenue and Economics Tests ====================

    def test_revenue_calculation(self, runner_realistic):
        """Test revenue is calculated correctly."""
        result = runner_realistic.run()

        # Verify total revenue matches sum of hourly
        hourly_sum = sum(stat.revenue_inr for stat in result.hourly_stats)
        assert abs(result.total_revenue_inr - hourly_sum) < 0.01

    def test_price_increases_with_demand(self, runner_realistic):
        """Test price increases with higher demand."""
        low_price = runner_realistic.calculate_price(0.5)
        high_price = runner_realistic.calculate_price(2.0)

        assert high_price > low_price

    def test_realistic_generates_more_v2g_revenue(self):
        """Test realistic demand generates more V2G revenue opportunity."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            num_evs=100,
            random_seed=42,
        )
        runner = SimulationRunner(config)
        results = runner.compare_demand_modes()

        flat_discharge = results[DemandMode.FLAT].total_v2g_discharge_kwh
        real_discharge = results[DemandMode.REALISTIC].total_v2g_discharge_kwh

        # Realistic should have V2G discharge, flat won't (no peaks)
        assert real_discharge > 0
        assert flat_discharge == 0  # Flat demand never triggers V2G threshold

    # ==================== Summary Metrics Tests ====================

    def test_summary_metrics_calculated(self, runner_realistic):
        """Test summary metrics are properly calculated."""
        result = runner_realistic.run()

        assert result.peak_demand_mw > result.min_demand_mw
        assert result.avg_demand_mw > 0
        assert result.peak_price_inr >= result.min_price_inr
        assert result.avg_price_inr > 0

    def test_peak_hours_identified(self, runner_realistic):
        """Test peak hours are identified in results."""
        result = runner_realistic.run()

        assert len(result.peak_hours) > 0
        assert len(result.off_peak_hours) > 0
        assert len(result.v2g_opportunity_hours) > 0

    # ==================== Multi-Day Tests ====================

    def test_multi_day_simulation(self):
        """Test simulation runs correctly over multiple days."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=72,  # 3 days
            random_seed=42,
        )
        runner = SimulationRunner(config)
        result = runner.run()

        assert len(result.hourly_stats) == 72

    def test_week_simulation_with_weekend(self):
        """Test week-long simulation captures weekday/weekend differences."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 13),  # Monday
            duration_hours=168,  # 7 days
            random_seed=42,
        )
        runner = SimulationRunner(config)
        result = runner.run()

        # Get average demand by day of week
        daily_demands = {}
        for stat in result.hourly_stats:
            dow = stat.timestamp.weekday()
            if dow not in daily_demands:
                daily_demands[dow] = []
            daily_demands[dow].append(stat.demand_multiplier)

        weekday_avg = sum(sum(daily_demands[d]) for d in range(5)) / sum(len(daily_demands[d]) for d in range(5))
        sunday_avg = sum(daily_demands[6]) / len(daily_demands[6])

        assert weekday_avg > sunday_avg


class TestDemandModeComparison:
    """Dedicated tests comparing demand modes."""

    @pytest.fixture
    def comparison_results(self):
        """Run comparison and return results."""
        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),  # Summer weekday
            duration_hours=24,
            num_evs=100,
            random_seed=42,
        )
        runner = SimulationRunner(config)
        return runner.compare_demand_modes([
            DemandMode.FLAT,
            DemandMode.HOURLY_ONLY,
            DemandMode.REALISTIC,
        ])

    def test_flat_has_lowest_variance(self, comparison_results):
        """Test flat mode has lowest demand variance."""
        def variance(result):
            demands = [s.grid_demand_mw for s in result.hourly_stats]
            avg = sum(demands) / len(demands)
            return sum((d - avg)**2 for d in demands) / len(demands)

        flat_var = variance(comparison_results[DemandMode.FLAT])
        hourly_var = variance(comparison_results[DemandMode.HOURLY_ONLY])
        real_var = variance(comparison_results[DemandMode.REALISTIC])

        assert flat_var < hourly_var < real_var

    def test_realistic_has_highest_peaks(self, comparison_results):
        """Test realistic mode has highest peak demand."""
        flat_peak = comparison_results[DemandMode.FLAT].peak_demand_mw
        hourly_peak = comparison_results[DemandMode.HOURLY_ONLY].peak_demand_mw
        real_peak = comparison_results[DemandMode.REALISTIC].peak_demand_mw

        assert flat_peak < hourly_peak < real_peak

    def test_only_realistic_triggers_v2g(self, comparison_results):
        """Test only realistic mode triggers V2G discharge."""
        flat_v2g = comparison_results[DemandMode.FLAT].total_v2g_discharge_kwh
        real_v2g = comparison_results[DemandMode.REALISTIC].total_v2g_discharge_kwh

        # Flat never hits 1.4 threshold
        assert flat_v2g == 0
        # Realistic has peak hours above threshold
        assert real_v2g > 0


class TestCustomDemandMode:
    """Tests for custom demand function mode."""

    def test_custom_demand_function(self):
        """Test custom demand function is used correctly."""
        def custom_fn(timestamp: datetime) -> float:
            # Simple function: high during working hours
            if 9 <= timestamp.hour <= 17:
                return 2.0
            return 0.5

        config = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            demand_mode=DemandMode.CUSTOM,
            custom_demand_fn=custom_fn,
            random_seed=42,
        )
        runner = SimulationRunner(config)
        result = runner.run()

        for stat in result.hourly_stats:
            hour = stat.timestamp.hour
            if 9 <= hour <= 17:
                assert stat.demand_multiplier == 2.0
            else:
                assert stat.demand_multiplier == 0.5


class TestReproducibility:
    """Tests for simulation reproducibility."""

    def test_same_seed_same_results(self):
        """Test same random seed produces identical results."""
        config1 = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            random_seed=12345,
        )
        config2 = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            random_seed=12345,
        )

        runner1 = SimulationRunner(config1)
        runner2 = SimulationRunner(config2)

        result1 = runner1.run()
        result2 = runner2.run()

        assert result1.total_v2g_discharge_kwh == result2.total_v2g_discharge_kwh
        assert result1.total_revenue_inr == result2.total_revenue_inr

    def test_different_seed_different_results(self):
        """Test different random seeds produce different results."""
        config1 = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            random_seed=11111,
        )
        config2 = SimulationConfig(
            start_time=datetime(2024, 5, 15),
            duration_hours=24,
            random_seed=22222,
        )

        runner1 = SimulationRunner(config1)
        runner2 = SimulationRunner(config2)

        result1 = runner1.run()
        result2 = runner2.run()

        # Initial EV SOC differs, so results should differ
        assert result1.total_v2g_discharge_kwh != result2.total_v2g_discharge_kwh


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
