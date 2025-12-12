"""
Inflation Monitor for SHAKTI-CHAIN Token Economics (Domain 4).

Tracks token supply growth and tests inflation hypothesis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class InflationMeasurement:
    """
    An inflation measurement for a period.

    Attributes:
        period_start: Start timestamp
        period_end: End timestamp
        start_supply: Supply at period start
        end_supply: Supply at period end
        inflation_rate: (end - start) / start for the period
        annualized_rate: Inflation rate annualized
        net_minted: Net tokens minted in period
    """
    period_start: float
    period_end: float
    start_supply: float
    end_supply: float
    inflation_rate: float
    annualized_rate: float
    net_minted: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "start_supply": float(self.start_supply),
            "end_supply": float(self.end_supply),
            "inflation_rate": float(self.inflation_rate),
            "annualized_rate": float(self.annualized_rate),
            "net_minted": float(self.net_minted),
        }

    @property
    def period_days(self) -> float:
        """Get period duration in days."""
        return (self.period_end - self.period_start) / (24 * 3600)


@dataclass
class InflationTestResult:
    """
    Result of inflation hypothesis test.

    Attributes:
        is_acceptable: Whether inflation is below threshold
        mean_annual_inflation: Mean annualized inflation rate
        std_inflation: Standard deviation
        max_inflation: Maximum observed
        min_inflation: Minimum observed (could be negative)
        t_statistic: T-test statistic
        p_value: P-value
        ci_lower: Lower confidence interval
        ci_upper: Upper confidence interval
        threshold: Inflation threshold used
        sample_size: Number of periods analyzed
    """
    is_acceptable: bool
    mean_annual_inflation: float
    std_inflation: float
    max_inflation: float
    min_inflation: float
    t_statistic: float
    p_value: float
    ci_lower: float
    ci_upper: float
    threshold: float
    sample_size: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_acceptable": self.is_acceptable,
            "mean_annual_inflation": float(self.mean_annual_inflation),
            "std_inflation": float(self.std_inflation),
            "max_inflation": float(self.max_inflation),
            "min_inflation": float(self.min_inflation),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "ci_lower": float(self.ci_lower),
            "ci_upper": float(self.ci_upper),
            "threshold": float(self.threshold),
            "sample_size": self.sample_size,
        }


@dataclass
class InflationStatistics:
    """
    Aggregate inflation statistics.

    Attributes:
        total_inflation: Total supply change as percentage
        mean_monthly_rate: Average monthly inflation rate
        mean_annual_rate: Average annualized rate
        current_supply: Latest supply value
        initial_supply: Starting supply value
        supply_change: Absolute change in supply
        hyperinflation_periods: Number of periods exceeding threshold
    """
    total_inflation: float
    mean_monthly_rate: float
    mean_annual_rate: float
    current_supply: float
    initial_supply: float
    supply_change: float
    hyperinflation_periods: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_inflation": float(self.total_inflation),
            "mean_monthly_rate": float(self.mean_monthly_rate),
            "mean_annual_rate": float(self.mean_annual_rate),
            "current_supply": float(self.current_supply),
            "initial_supply": float(self.initial_supply),
            "supply_change": float(self.supply_change),
            "hyperinflation_periods": self.hyperinflation_periods,
        }


class InflationMonitor:
    """
    Monitor token supply inflation.

    Tests hypothesis H4.5: Annual inflation < 10%
    """

    def __init__(
        self,
        initial_supply: float = 1_000_000.0,
        inflation_threshold: float = 0.10,
    ):
        """
        Initialize inflation monitor.

        Args:
            initial_supply: Initial token supply
            inflation_threshold: Annual inflation threshold (default 10%)
        """
        self.initial_supply = initial_supply
        self.inflation_threshold = inflation_threshold
        self.measurements: List[InflationMeasurement] = []
        self._supply_history: List[Tuple[float, float]] = []  # (timestamp, supply)

        # Initialize with initial supply
        now = datetime.now().timestamp()
        self._supply_history.append((now, initial_supply))

    def record_supply(self, timestamp: float, supply: float):
        """
        Record a supply observation.

        Args:
            timestamp: Unix timestamp
            supply: Token supply at timestamp
        """
        self._supply_history.append((timestamp, supply))

        # Sort by timestamp
        self._supply_history.sort(key=lambda x: x[0])

    def calculate_period_inflation(
        self,
        period_days: int = 30,
    ) -> List[InflationMeasurement]:
        """
        Calculate inflation for each period of given length.

        Args:
            period_days: Days per period

        Returns:
            List of InflationMeasurement for each period
        """
        if len(self._supply_history) < 2:
            return []

        # Sort history
        sorted_history = sorted(self._supply_history, key=lambda x: x[0])
        start_timestamp = sorted_history[0][0]
        end_timestamp = sorted_history[-1][0]

        period_seconds = period_days * 24 * 3600
        measurements = []

        current_start = start_timestamp
        while current_start + period_seconds <= end_timestamp:
            period_end = current_start + period_seconds

            # Find supply values at start and end of period
            start_supply = self._get_supply_at(current_start, sorted_history)
            end_supply = self._get_supply_at(period_end, sorted_history)

            if start_supply > 0:
                inflation_rate = (end_supply - start_supply) / start_supply

                # Annualize the rate
                # (1 + annual_rate) = (1 + period_rate) ^ (365 / period_days)
                if inflation_rate > -1:  # Avoid log of negative
                    annualized_rate = (1 + inflation_rate) ** (365 / period_days) - 1
                else:
                    annualized_rate = -1.0  # Complete loss
            else:
                inflation_rate = 0.0
                annualized_rate = 0.0

            measurement = InflationMeasurement(
                period_start=current_start,
                period_end=period_end,
                start_supply=start_supply,
                end_supply=end_supply,
                inflation_rate=inflation_rate,
                annualized_rate=annualized_rate,
                net_minted=end_supply - start_supply,
            )
            measurements.append(measurement)

            current_start = period_end

        self.measurements = measurements
        return measurements

    def _get_supply_at(
        self,
        timestamp: float,
        sorted_history: List[Tuple[float, float]],
    ) -> float:
        """
        Get supply value at a given timestamp (interpolated).

        Args:
            timestamp: Target timestamp
            sorted_history: Sorted supply history

        Returns:
            Supply value at timestamp
        """
        if not sorted_history:
            return 0.0

        # Find surrounding points
        before = None
        after = None

        for i, (ts, supply) in enumerate(sorted_history):
            if ts <= timestamp:
                before = (ts, supply)
            else:
                after = (ts, supply)
                break

        if before is None:
            return sorted_history[0][1]
        if after is None:
            return sorted_history[-1][1]

        # Linear interpolation
        t_before, s_before = before
        t_after, s_after = after

        if t_after == t_before:
            return s_before

        ratio = (timestamp - t_before) / (t_after - t_before)
        return s_before + ratio * (s_after - s_before)

    def test_inflation(
        self,
        threshold: Optional[float] = None,
        alpha: float = 0.05,
    ) -> InflationTestResult:
        """
        Test if inflation is below threshold.

        Tests H4.5: Annual inflation < 10%

        Uses one-sample t-test on annualized rates.

        Args:
            threshold: Inflation threshold (default from init)
            alpha: Significance level

        Returns:
            InflationTestResult
        """
        if threshold is None:
            threshold = self.inflation_threshold

        if not self.measurements:
            self.calculate_period_inflation()

        if len(self.measurements) < 2:
            return InflationTestResult(
                is_acceptable=True,
                mean_annual_inflation=0,
                std_inflation=0,
                max_inflation=0,
                min_inflation=0,
                t_statistic=0,
                p_value=1.0,
                ci_lower=0,
                ci_upper=0,
                threshold=threshold,
                sample_size=len(self.measurements),
            )

        annual_rates = np.array([m.annualized_rate for m in self.measurements])
        n = len(annual_rates)

        mean_rate = float(np.mean(annual_rates))
        std_rate = float(np.std(annual_rates, ddof=1))

        # One-sample t-test: H0: mean >= threshold, H1: mean < threshold
        # This is a one-tailed test
        if std_rate > 0:
            t_stat = (mean_rate - threshold) / (std_rate / np.sqrt(n))
            p_value = scipy_stats.t.cdf(t_stat, n - 1)  # Left tail
        else:
            t_stat = 0.0
            p_value = 1.0 if mean_rate >= threshold else 0.0

        # Confidence interval
        se = std_rate / np.sqrt(n) if n > 0 else 0
        t_crit = scipy_stats.t.ppf(1 - alpha / 2, max(n - 1, 1))
        ci_lower = mean_rate - t_crit * se
        ci_upper = mean_rate + t_crit * se

        # Acceptable if mean inflation < threshold
        # And we can reject H0 at significance level
        is_acceptable = mean_rate < threshold and p_value < alpha

        return InflationTestResult(
            is_acceptable=is_acceptable,
            mean_annual_inflation=mean_rate,
            std_inflation=std_rate,
            max_inflation=float(np.max(annual_rates)),
            min_inflation=float(np.min(annual_rates)),
            t_statistic=float(t_stat),
            p_value=float(p_value),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            threshold=threshold,
            sample_size=n,
        )

    def detect_hyperinflation_periods(
        self,
        threshold: Optional[float] = None,
    ) -> List[InflationMeasurement]:
        """
        Identify periods with inflation exceeding threshold.

        Args:
            threshold: Inflation threshold

        Returns:
            List of periods with hyperinflation
        """
        if threshold is None:
            threshold = self.inflation_threshold

        if not self.measurements:
            self.calculate_period_inflation()

        return [m for m in self.measurements if m.annualized_rate >= threshold]

    def get_statistics(
        self,
        threshold: Optional[float] = None,
    ) -> InflationStatistics:
        """
        Get aggregate inflation statistics.

        Args:
            threshold: Threshold for hyperinflation counting

        Returns:
            InflationStatistics
        """
        if threshold is None:
            threshold = self.inflation_threshold

        if not self.measurements:
            self.calculate_period_inflation()

        if not self._supply_history:
            return InflationStatistics(
                total_inflation=0,
                mean_monthly_rate=0,
                mean_annual_rate=0,
                current_supply=self.initial_supply,
                initial_supply=self.initial_supply,
                supply_change=0,
                hyperinflation_periods=0,
            )

        sorted_history = sorted(self._supply_history, key=lambda x: x[0])
        initial = sorted_history[0][1]
        current = sorted_history[-1][1]
        supply_change = current - initial

        if initial > 0:
            total_inflation = supply_change / initial
        else:
            total_inflation = 0

        if self.measurements:
            monthly_rates = [m.inflation_rate for m in self.measurements]
            annual_rates = [m.annualized_rate for m in self.measurements]
            mean_monthly = float(np.mean(monthly_rates))
            mean_annual = float(np.mean(annual_rates))
            hyperinflation_periods = sum(1 for r in annual_rates if r >= threshold)
        else:
            mean_monthly = 0
            mean_annual = 0
            hyperinflation_periods = 0

        return InflationStatistics(
            total_inflation=total_inflation,
            mean_monthly_rate=mean_monthly,
            mean_annual_rate=mean_annual,
            current_supply=current,
            initial_supply=initial,
            supply_change=supply_change,
            hyperinflation_periods=hyperinflation_periods,
        )

    def get_inflation_series(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get time series of inflation.

        Returns:
            Tuple of (timestamps, period_rates, annualized_rates)
        """
        if not self.measurements:
            self.calculate_period_inflation()

        timestamps = np.array([m.period_end for m in self.measurements])
        period_rates = np.array([m.inflation_rate for m in self.measurements])
        annual_rates = np.array([m.annualized_rate for m in self.measurements])

        return timestamps, period_rates, annual_rates

    def get_supply_series(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get supply time series.

        Returns:
            Tuple of (timestamps, supplies)
        """
        sorted_history = sorted(self._supply_history, key=lambda x: x[0])
        timestamps = np.array([ts for ts, _ in sorted_history])
        supplies = np.array([supply for _, supply in sorted_history])

        return timestamps, supplies

    def clear(self):
        """Clear all data except initial supply."""
        now = datetime.now().timestamp()
        self._supply_history = [(now, self.initial_supply)]
        self.measurements = []


def simulate_inflation_data(
    initial_supply: float = 1_000_000.0,
    duration_days: int = 365,
    daily_mint_rate: float = 0.0002,  # 0.02% per day ~ 7.5% annual
    daily_burn_rate: float = 0.00015,  # 0.015% per day
    volatility: float = 0.5,
    snapshot_interval_hours: float = 24.0,
    seed: Optional[int] = None,
) -> InflationMonitor:
    """
    Simulate inflation data.

    Args:
        initial_supply: Initial token supply
        duration_days: Duration to simulate
        daily_mint_rate: Mean daily mint rate as fraction of supply
        daily_burn_rate: Mean daily burn rate as fraction of supply
        volatility: Volatility of rates
        snapshot_interval_hours: Hours between snapshots
        seed: Random seed

    Returns:
        InflationMonitor with simulated data
    """
    rng = np.random.default_rng(seed)

    monitor = InflationMonitor(
        initial_supply=initial_supply,
        inflation_threshold=0.10,
    )

    # Clear default history
    monitor._supply_history = []

    current_supply = initial_supply
    start_time = datetime.now().timestamp()
    num_snapshots = int(duration_days * 24 / snapshot_interval_hours)

    for i in range(num_snapshots):
        timestamp = start_time + i * snapshot_interval_hours * 3600

        # Daily rates normalized to snapshot interval
        interval_factor = snapshot_interval_hours / 24

        # Generate mint and burn with volatility
        mint_rate = max(0, rng.normal(daily_mint_rate, daily_mint_rate * volatility))
        burn_rate = max(0, rng.normal(daily_burn_rate, daily_burn_rate * volatility))

        # Apply rates
        mint_amount = current_supply * mint_rate * interval_factor
        burn_amount = min(current_supply * 0.01, current_supply * burn_rate * interval_factor)

        current_supply = current_supply + mint_amount - burn_amount

        monitor.record_supply(timestamp, current_supply)

    # Calculate period inflation
    monitor.calculate_period_inflation(period_days=30)

    return monitor


def simulate_inflation_scenarios(
    duration_days: int = 365,
    seed: Optional[int] = None,
) -> Dict[str, InflationMonitor]:
    """
    Simulate multiple inflation scenarios.

    Args:
        duration_days: Duration to simulate
        seed: Random seed

    Returns:
        Dictionary of scenario name -> InflationMonitor
    """
    scenarios = {}

    # Low inflation (healthy)
    scenarios["low_inflation"] = simulate_inflation_data(
        duration_days=duration_days,
        daily_mint_rate=0.00015,  # ~5.6% annual
        daily_burn_rate=0.00012,  # ~4.5% annual
        seed=seed,
    )

    # Balanced (near zero inflation)
    scenarios["balanced"] = simulate_inflation_data(
        duration_days=duration_days,
        daily_mint_rate=0.00015,
        daily_burn_rate=0.00015,
        seed=seed + 1 if seed else None,
    )

    # Moderate inflation
    scenarios["moderate_inflation"] = simulate_inflation_data(
        duration_days=duration_days,
        daily_mint_rate=0.0003,  # ~11.6% annual
        daily_burn_rate=0.0002,
        seed=seed + 2 if seed else None,
    )

    # High inflation (hyperinflation risk)
    scenarios["high_inflation"] = simulate_inflation_data(
        duration_days=duration_days,
        daily_mint_rate=0.0005,  # ~20% annual
        daily_burn_rate=0.0002,
        seed=seed + 3 if seed else None,
    )

    # Deflationary
    scenarios["deflationary"] = simulate_inflation_data(
        duration_days=duration_days,
        daily_mint_rate=0.0001,
        daily_burn_rate=0.0002,  # More burning
        seed=seed + 4 if seed else None,
    )

    return scenarios


def simulate_mint_attack(
    initial_supply: float = 1_000_000.0,
    attack_multiplier: float = 10.0,
    attack_duration_days: int = 7,
    total_duration_days: int = 30,
    seed: Optional[int] = None,
) -> InflationMonitor:
    """
    Simulate a mint attack scenario.

    Models an attempt to flood the supply through excessive minting.

    Args:
        initial_supply: Initial supply
        attack_multiplier: How much more minting during attack
        attack_duration_days: Duration of attack
        total_duration_days: Total simulation duration
        seed: Random seed

    Returns:
        InflationMonitor with attack scenario
    """
    rng = np.random.default_rng(seed)

    monitor = InflationMonitor(
        initial_supply=initial_supply,
        inflation_threshold=0.10,
    )
    monitor._supply_history = []

    current_supply = initial_supply
    start_time = datetime.now().timestamp()

    # Attack starts in the middle
    attack_start_day = (total_duration_days - attack_duration_days) // 2
    attack_end_day = attack_start_day + attack_duration_days

    base_daily_mint = 0.0002  # Normal mint rate
    base_daily_burn = 0.00015

    for day in range(total_duration_days):
        timestamp = start_time + day * 24 * 3600

        # During attack, minting is multiplied
        if attack_start_day <= day < attack_end_day:
            mint_rate = base_daily_mint * attack_multiplier
            # Assume some defensive burning kicks in
            burn_rate = base_daily_burn * 2
        else:
            mint_rate = base_daily_mint
            burn_rate = base_daily_burn

        # Add noise
        mint_rate = max(0, rng.normal(mint_rate, mint_rate * 0.2))
        burn_rate = max(0, rng.normal(burn_rate, burn_rate * 0.2))

        mint_amount = current_supply * mint_rate
        burn_amount = current_supply * burn_rate

        current_supply = current_supply + mint_amount - burn_amount

        monitor.record_supply(timestamp, current_supply)

    monitor.calculate_period_inflation(period_days=7)

    return monitor
