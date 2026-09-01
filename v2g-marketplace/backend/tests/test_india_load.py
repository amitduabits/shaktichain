"""
Tests for Indian electricity demand load profiles.

These tests verify the IndiaLoadProfile class correctly models
demand patterns and compare realistic vs flat demand simulations.
"""

import pytest
from datetime import datetime

import sys
sys.path.insert(0, str(__file__).rsplit("/", 3)[0])

from backend.core.demand.india_load import (
    IndiaLoadProfile,
    Season,
    Region,
    DemandMultipliers,
)


class TestIndiaLoadProfile:
    """Test suite for IndiaLoadProfile class."""

    @pytest.fixture
    def profile(self):
        """Create a default IndiaLoadProfile instance."""
        return IndiaLoadProfile()

    @pytest.fixture
    def profile_with_base_load(self):
        """Create an IndiaLoadProfile with custom base load."""
        return IndiaLoadProfile(base_load_mw=5000.0)

    # ==================== Hourly Multiplier Tests ====================

    def test_hourly_multiplier_morning_peak(self, profile):
        """Test morning peak hours have multipliers in expected range."""
        for hour in [6, 7, 8, 9, 10]:
            mult = profile.get_hourly_multiplier(hour)
            assert 0.85 <= mult <= 1.5, f"Hour {hour} should be in morning peak range"

    def test_hourly_multiplier_evening_peak(self, profile):
        """Test evening peak hours have highest multipliers."""
        for hour in [18, 19, 20, 21, 22]:
            mult = profile.get_hourly_multiplier(hour)
            assert 1.4 <= mult <= 1.8, f"Hour {hour} should be in evening peak range"

    def test_hourly_multiplier_night_low(self, profile):
        """Test night hours have low multipliers."""
        for hour in [0, 1, 2, 3, 4, 5, 23]:
            mult = profile.get_hourly_multiplier(hour)
            assert 0.5 <= mult <= 0.85, f"Hour {hour} should be in night low range"

    def test_hourly_multiplier_afternoon(self, profile):
        """Test afternoon hours have moderate multipliers."""
        for hour in [11, 12, 13, 14, 15, 16, 17]:
            mult = profile.get_hourly_multiplier(hour)
            assert 0.9 <= mult <= 1.1, f"Hour {hour} should be in afternoon range"

    def test_hourly_multiplier_invalid_hour(self, profile):
        """Test that invalid hours raise ValueError."""
        with pytest.raises(ValueError, match="Hour must be 0-23"):
            profile.get_hourly_multiplier(24)
        with pytest.raises(ValueError, match="Hour must be 0-23"):
            profile.get_hourly_multiplier(-1)

    def test_peak_hour_at_8pm_is_maximum(self, profile):
        """Test that 8 PM (hour 20) has the highest hourly multiplier."""
        max_hour = max(range(24), key=lambda h: profile.get_hourly_multiplier(h))
        assert max_hour == 20, "8 PM should have peak demand"
        assert profile.get_hourly_multiplier(20) == 1.8

    def test_minimum_demand_at_night(self, profile):
        """Test that minimum demand occurs during night hours."""
        min_hour = min(range(24), key=lambda h: profile.get_hourly_multiplier(h))
        assert min_hour in [2, 3], "2-3 AM should have minimum demand"
        assert profile.get_hourly_multiplier(min_hour) == 0.5

    # ==================== Day of Week Tests ====================

    def test_weekday_multiplier(self, profile):
        """Test weekday multipliers are consistent."""
        for day in range(5):  # Monday to Friday
            assert profile.get_day_of_week_multiplier(day) == 1.1

    def test_weekend_multipliers(self, profile):
        """Test weekend has lower multipliers than weekdays."""
        saturday = profile.get_day_of_week_multiplier(5)
        sunday = profile.get_day_of_week_multiplier(6)
        weekday = profile.get_day_of_week_multiplier(0)

        assert saturday < weekday, "Saturday should be lower than weekday"
        assert sunday < saturday, "Sunday should be lowest"
        assert saturday == 0.95
        assert sunday == 0.85

    def test_day_of_week_invalid(self, profile):
        """Test that invalid day of week raises ValueError."""
        with pytest.raises(ValueError, match="Day of week must be 0-6"):
            profile.get_day_of_week_multiplier(7)
        with pytest.raises(ValueError, match="Day of week must be 0-6"):
            profile.get_day_of_week_multiplier(-1)

    # ==================== Seasonal Tests ====================

    def test_summer_highest_seasonal_multiplier(self, profile):
        """Test summer months have highest seasonal multiplier (AC load)."""
        for month in [4, 5, 6]:  # Apr, May, Jun
            assert profile.get_seasonal_multiplier(month) == 1.3

    def test_monsoon_baseline_multiplier(self, profile):
        """Test monsoon months have baseline multiplier."""
        for month in [7, 8, 9]:  # Jul, Aug, Sep
            assert profile.get_seasonal_multiplier(month) == 1.0

    def test_winter_moderate_multiplier(self, profile):
        """Test winter months have moderate multiplier."""
        for month in [10, 11, 12, 1]:  # Oct, Nov, Dec, Jan
            assert profile.get_seasonal_multiplier(month) == 1.1

    def test_spring_lowest_multiplier(self, profile):
        """Test spring months have lowest multiplier."""
        for month in [2, 3]:  # Feb, Mar
            assert profile.get_seasonal_multiplier(month) == 0.95

    def test_seasonal_invalid_month(self, profile):
        """Test that invalid months raise ValueError."""
        with pytest.raises(ValueError, match="Month must be 1-12"):
            profile.get_seasonal_multiplier(0)
        with pytest.raises(ValueError, match="Month must be 1-12"):
            profile.get_seasonal_multiplier(13)

    # ==================== Regional Tests ====================

    def test_chennai_highest_regional_multiplier(self, profile):
        """Test Chennai has highest regional multiplier (hot climate)."""
        assert profile.get_regional_multiplier("Chennai") == 1.25
        assert profile.get_regional_multiplier("chennai") == 1.25  # Case insensitive

    def test_delhi_regional_multiplier(self, profile):
        """Test Delhi regional multiplier."""
        assert profile.get_regional_multiplier("Delhi") == 1.2

    def test_mumbai_regional_multiplier(self, profile):
        """Test Mumbai regional multiplier."""
        assert profile.get_regional_multiplier("Mumbai") == 1.15

    def test_bangalore_regional_multiplier(self, profile):
        """Test Bangalore regional multiplier (pleasant climate)."""
        assert profile.get_regional_multiplier("Bangalore") == 1.1

    def test_kolkata_regional_multiplier(self, profile):
        assert profile.get_regional_multiplier("Kolkata") == 1.15
        assert profile.get_regional_multiplier("kolkata") == 1.15

    def test_unknown_region_returns_default(self, profile):
        """Test unknown regions return default multiplier."""
        assert profile.get_regional_multiplier("UnknownCity") == 1.0
        assert profile.get_regional_multiplier("") == 1.0

    # ==================== Combined Multiplier Tests ====================

    def test_combined_multiplier_peak_summer_delhi(self, profile):
        """Test peak evening in summer Delhi on weekday is very high."""
        # 8 PM, Monday, May, Delhi
        mult = profile.get_demand_multiplier(
            hour=20, day_of_week=0, month=5, region="Delhi"
        )
        # 1.8 * 1.1 * 1.3 * 1.2 = 3.09
        expected = 1.8 * 1.1 * 1.3 * 1.2
        assert abs(mult - expected) < 0.01

    def test_combined_multiplier_low_sunday_monsoon(self, profile):
        """Test low demand scenario: night, Sunday, monsoon, Bangalore."""
        # 3 AM, Sunday, August, Bangalore
        mult = profile.get_demand_multiplier(
            hour=3, day_of_week=6, month=8, region="Bangalore"
        )
        # 0.5 * 0.85 * 1.0 * 1.1 = 0.4675
        expected = 0.5 * 0.85 * 1.0 * 1.1
        assert abs(mult - expected) < 0.01

    def test_combined_multiplier_default_region(self, profile):
        """Test combined multiplier uses Delhi as default region."""
        mult1 = profile.get_demand_multiplier(hour=12, day_of_week=0, month=1)
        mult2 = profile.get_demand_multiplier(
            hour=12, day_of_week=0, month=1, region="Delhi"
        )
        assert mult1 == mult2

    # ==================== Detailed Multiplier Tests ====================

    def test_detailed_multiplier_returns_all_components(self, profile):
        """Test get_demand_multiplier_detailed returns all components."""
        result = profile.get_demand_multiplier_detailed(
            hour=20, day_of_week=0, month=5, region="Delhi"
        )

        assert isinstance(result, DemandMultipliers)
        assert result.hourly == 1.8
        assert result.day_of_week == 1.1
        assert result.seasonal == 1.3
        assert result.regional == 1.2
        assert abs(result.combined - (1.8 * 1.1 * 1.3 * 1.2)) < 0.01

    # ==================== Absolute Demand Tests ====================

    def test_absolute_demand_calculation(self, profile_with_base_load):
        """Test absolute demand calculation with base load."""
        # Flat conditions: hour with mult=1.0 doesn't exist, use multiplier
        # Let's use hour 13 (1.0), weekday (1.1), monsoon (1.0), default region (1.0)
        profile = IndiaLoadProfile(base_load_mw=1000.0)
        demand = profile.get_absolute_demand_mw(
            hour=13, day_of_week=0, month=7, region="UnknownCity"
        )
        # 1.0 * 1.1 * 1.0 * 1.0 * 1000 = 1100
        assert demand == 1100.0

    def test_absolute_demand_peak(self, profile_with_base_load):
        """Test absolute demand at peak time."""
        demand = profile_with_base_load.get_absolute_demand_mw(
            hour=20, day_of_week=0, month=5, region="Chennai"
        )
        # 1.8 * 1.1 * 1.3 * 1.25 * 5000 = 16087.5
        expected = 1.8 * 1.1 * 1.3 * 1.25 * 5000
        assert abs(demand - expected) < 0.1

    # ==================== Daily Profile Tests ====================

    def test_daily_profile_returns_24_hours(self, profile):
        """Test daily profile returns values for all 24 hours."""
        daily = profile.get_daily_profile(day_of_week=0, month=5, region="Delhi")

        assert len(daily) == 24
        assert all(hour in daily for hour in range(24))

    def test_daily_profile_values_consistent(self, profile):
        """Test daily profile values match individual calculations."""
        daily = profile.get_daily_profile(day_of_week=2, month=8, region="Mumbai")

        for hour in range(24):
            expected = profile.get_demand_multiplier(
                hour=hour, day_of_week=2, month=8, region="Mumbai"
            )
            assert daily[hour] == expected

    # ==================== Peak Hour Tests ====================

    def test_peak_hours_identification(self, profile):
        """Test peak hour identification."""
        peaks = profile.get_peak_hours()

        assert "morning_peak" in peaks
        assert "evening_peak" in peaks
        assert len(peaks["evening_peak"]) > len(peaks["morning_peak"])

    def test_is_peak_hour(self, profile):
        """Test is_peak_hour method."""
        assert profile.is_peak_hour(20)  # 8 PM
        assert profile.is_peak_hour(19)  # 7 PM
        assert not profile.is_peak_hour(3)  # 3 AM
        assert not profile.is_peak_hour(14)  # 2 PM

    def test_off_peak_hours(self, profile):
        """Test off-peak hours identification."""
        off_peak = profile.get_off_peak_hours()

        # Night hours should be off-peak
        assert 2 in off_peak
        assert 3 in off_peak
        # Evening peak should not be off-peak
        assert 20 not in off_peak

    def test_v2g_opportunity_hours(self, profile):
        """Test V2G opportunity hours identification."""
        v2g_hours = profile.get_v2g_opportunity_hours()

        # Evening peak hours should be opportunities
        assert 18 in v2g_hours
        assert 19 in v2g_hours
        assert 20 in v2g_hours
        # Night hours should not be
        assert 3 not in v2g_hours

    # ==================== Season Detection Tests ====================

    def test_season_detection(self, profile):
        """Test season detection from month."""
        assert profile.get_season(5) == Season.SUMMER
        assert profile.get_season(8) == Season.MONSOON
        assert profile.get_season(11) == Season.WINTER
        assert profile.get_season(1) == Season.WINTER
        assert profile.get_season(2) == Season.SPRING


class TestDemandPatternComparison:
    """Tests comparing realistic vs flat demand patterns."""

    @pytest.fixture
    def profile(self):
        """Create a default IndiaLoadProfile instance."""
        return IndiaLoadProfile(base_load_mw=1000.0)

    def test_realistic_has_higher_variance_than_flat(self, profile):
        """Test that realistic demand has higher variance than flat."""
        # Get 24-hour profile for a summer weekday
        daily = profile.get_daily_profile(day_of_week=0, month=5, region="Delhi")

        values = list(daily.values())
        variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)

        # Flat would have variance of 0
        # Realistic should have significant variance
        assert variance > 0.1, "Realistic demand should have significant variance"

    def test_peak_to_trough_ratio(self, profile):
        """Test peak-to-trough ratio is realistic for Indian grid."""
        daily = profile.get_daily_profile(day_of_week=0, month=5, region="Delhi")

        peak = max(daily.values())
        trough = min(daily.values())
        ratio = peak / trough

        # Indian grid typically has 3-6x peak-to-trough ratio
        assert 3.0 <= ratio <= 7.0, f"Peak-to-trough ratio {ratio:.1f} should be 3-6x"

    def test_summer_vs_monsoon_demand(self, profile):
        """Test summer has higher average demand than monsoon."""
        summer_daily = profile.get_daily_profile(day_of_week=0, month=5, region="Delhi")
        monsoon_daily = profile.get_daily_profile(day_of_week=0, month=8, region="Delhi")

        summer_avg = sum(summer_daily.values()) / len(summer_daily)
        monsoon_avg = sum(monsoon_daily.values()) / len(monsoon_daily)

        assert summer_avg > monsoon_avg, "Summer should have higher average demand"
        assert summer_avg / monsoon_avg == pytest.approx(1.3, rel=0.01)

    def test_weekday_vs_weekend_demand(self, profile):
        """Test weekday has higher demand than weekend."""
        weekday_daily = profile.get_daily_profile(day_of_week=0, month=5, region="Delhi")
        sunday_daily = profile.get_daily_profile(day_of_week=6, month=5, region="Delhi")

        weekday_avg = sum(weekday_daily.values()) / len(weekday_daily)
        sunday_avg = sum(sunday_daily.values()) / len(sunday_daily)

        assert weekday_avg > sunday_avg, "Weekday should have higher average demand"

    def test_regional_demand_ordering(self, profile):
        """Test regional demand ordering matches climate expectations."""
        regions = ["Chennai", "Delhi", "Mumbai", "Bangalore"]
        avg_demands = {}

        for region in regions:
            daily = profile.get_daily_profile(day_of_week=0, month=5, region=region)
            avg_demands[region] = sum(daily.values()) / len(daily)

        # Chennai (hottest) should have highest demand
        assert avg_demands["Chennai"] > avg_demands["Delhi"]
        # Bangalore (pleasant) should have lowest among these
        assert avg_demands["Bangalore"] < avg_demands["Mumbai"]

    def test_v2g_revenue_opportunity(self, profile):
        """Test V2G has revenue opportunity during peak vs off-peak."""
        peak_mult = profile.get_demand_multiplier(20, 0, 5, "Delhi")
        offpeak_mult = profile.get_demand_multiplier(3, 0, 5, "Delhi")

        # Peak should be much higher than off-peak
        assert peak_mult > 2.5 * offpeak_mult

    def test_ev_charging_optimization_potential(self, profile):
        """Test significant savings potential from smart charging."""
        # Compare charging at peak vs off-peak
        summer_weekday_peak = profile.get_demand_multiplier(20, 0, 5, "Delhi")
        summer_weekday_offpeak = profile.get_demand_multiplier(3, 0, 5, "Delhi")

        savings_ratio = summer_weekday_peak / summer_weekday_offpeak

        # Should see >3x price difference potential
        assert savings_ratio > 3.0, "Smart charging should offer >3x savings"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_all_hours_have_valid_multipliers(self):
        """Test all hours 0-23 have valid multipliers."""
        profile = IndiaLoadProfile()
        for hour in range(24):
            mult = profile.get_hourly_multiplier(hour)
            assert 0 < mult < 3, f"Hour {hour} multiplier {mult} out of range"

    def test_all_months_have_valid_multipliers(self):
        """Test all months 1-12 have valid multipliers."""
        profile = IndiaLoadProfile()
        for month in range(1, 13):
            mult = profile.get_seasonal_multiplier(month)
            assert 0.5 < mult < 2, f"Month {month} multiplier {mult} out of range"

    def test_all_days_have_valid_multipliers(self):
        """Test all days 0-6 have valid multipliers."""
        profile = IndiaLoadProfile()
        for day in range(7):
            mult = profile.get_day_of_week_multiplier(day)
            assert 0.5 < mult < 2, f"Day {day} multiplier {mult} out of range"

    def test_combined_multiplier_reasonable_bounds(self):
        """Test combined multiplier stays within reasonable bounds."""
        profile = IndiaLoadProfile()

        # Test all combinations would be too many, sample key points
        test_cases = [
            (0, 0, 1, "Delhi"),    # Midnight, Monday, January
            (20, 6, 5, "Chennai"),  # Peak, Sunday, May (extreme high)
            (3, 6, 2, "Bangalore"),  # Night, Sunday, Feb (extreme low)
        ]

        for hour, day, month, region in test_cases:
            mult = profile.get_demand_multiplier(hour, day, month, region)
            assert 0.3 < mult < 4.0, f"Combined multiplier {mult} out of bounds"

    def test_zero_base_load(self):
        """Test with zero base load."""
        profile = IndiaLoadProfile(base_load_mw=0.0)
        demand = profile.get_absolute_demand_mw(20, 0, 5, "Delhi")
        assert demand == 0.0

    def test_case_insensitive_regions(self):
        """Test region names are case-insensitive."""
        profile = IndiaLoadProfile()

        assert profile.get_regional_multiplier("DELHI") == \
               profile.get_regional_multiplier("delhi") == \
               profile.get_regional_multiplier("Delhi")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
