"""
Velocity Calculator for SHAKTI-CHAIN Token Economics (Domain 4).

Validates Fisher equation: MV = PQ for token velocity prediction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


@dataclass
class VelocityMeasurement:
    """
    A velocity measurement for a period.

    Attributes:
        period_start: Start timestamp
        period_end: End timestamp
        transaction_volume: Total token volume transacted
        average_supply: Average token supply during period
        average_price: Average price per kWh
        total_quantity: Total kWh traded
        actual_velocity: V_actual = volume / supply
        predicted_velocity: V_predicted = P * Q / M
    """
    period_start: float
    period_end: float
    transaction_volume: float
    average_supply: float
    average_price: float
    total_quantity: float
    actual_velocity: float
    predicted_velocity: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "transaction_volume": float(self.transaction_volume),
            "average_supply": float(self.average_supply),
            "average_price": float(self.average_price),
            "total_quantity": float(self.total_quantity),
            "actual_velocity": float(self.actual_velocity),
            "predicted_velocity": float(self.predicted_velocity),
        }

    @property
    def prediction_error(self) -> float:
        """Calculate prediction error."""
        if self.predicted_velocity > 0:
            return abs(self.actual_velocity - self.predicted_velocity) / self.predicted_velocity
        return 0.0

    @property
    def period_days(self) -> float:
        """Get period duration in days."""
        return (self.period_end - self.period_start) / (24 * 3600)


@dataclass
class VelocityTestResult:
    """
    Result of Fisher equation validation test.

    Attributes:
        is_valid: Whether Fisher equation holds within tolerance
        mean_actual_velocity: Mean actual velocity
        mean_predicted_velocity: Mean predicted velocity
        mean_absolute_error: Mean |actual - predicted| / predicted
        correlation: Correlation between actual and predicted
        r_squared: R-squared from regression
        t_statistic: Paired t-test statistic
        p_value: P-value
        tolerance: Tolerance threshold used
        sample_size: Number of periods analyzed
    """
    is_valid: bool
    mean_actual_velocity: float
    mean_predicted_velocity: float
    mean_absolute_error: float
    correlation: float
    r_squared: float
    t_statistic: float
    p_value: float
    tolerance: float
    sample_size: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "mean_actual_velocity": float(self.mean_actual_velocity),
            "mean_predicted_velocity": float(self.mean_predicted_velocity),
            "mean_absolute_error": float(self.mean_absolute_error),
            "correlation": float(self.correlation),
            "r_squared": float(self.r_squared),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "tolerance": float(self.tolerance),
            "sample_size": self.sample_size,
        }


@dataclass
class VelocityStatistics:
    """
    Aggregate velocity statistics.

    Attributes:
        mean_velocity: Mean token velocity
        std_velocity: Standard deviation
        min_velocity: Minimum velocity
        max_velocity: Maximum velocity
        median_velocity: Median velocity
        annualized_velocity: Annualized velocity
    """
    mean_velocity: float
    std_velocity: float
    min_velocity: float
    max_velocity: float
    median_velocity: float
    annualized_velocity: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_velocity": float(self.mean_velocity),
            "std_velocity": float(self.std_velocity),
            "min_velocity": float(self.min_velocity),
            "max_velocity": float(self.max_velocity),
            "median_velocity": float(self.median_velocity),
            "annualized_velocity": float(self.annualized_velocity),
        }


class VelocityCalculator:
    """
    Calculate and validate token velocity using Fisher equation.

    Fisher Equation: MV = PQ

    Where:
        M = Token supply (SHAKTI tokens)
        V = Velocity (transactions per token per period)
        P = Average price per kWh
        Q = Total kWh traded

    Tests hypothesis H4.3: |V_actual - V_predicted| / V_predicted < 20%
    """

    def __init__(self):
        """Initialize velocity calculator."""
        self.measurements: List[VelocityMeasurement] = []

    def calculate_actual_velocity(
        self,
        transaction_volume: float,
        average_supply: float,
        period_days: int = 1,
    ) -> float:
        """
        Calculate actual velocity from transaction data.

        V_actual = Total_transaction_volume / Average_supply

        Args:
            transaction_volume: Total token volume transacted
            average_supply: Average token supply during period
            period_days: Number of days in period

        Returns:
            Actual velocity (transactions per token)
        """
        if average_supply <= 0:
            return 0.0

        # Velocity per period
        velocity = transaction_volume / average_supply

        return float(velocity)

    def calculate_predicted_velocity(
        self,
        average_price: float,
        total_quantity: float,
        average_supply: float,
    ) -> float:
        """
        Calculate predicted velocity using Fisher equation.

        V_predicted = P * Q / M

        Args:
            average_price: Average price per kWh (in tokens)
            total_quantity: Total kWh traded
            average_supply: Average token supply (M)

        Returns:
            Predicted velocity from Fisher equation
        """
        if average_supply <= 0:
            return 0.0

        # Fisher: MV = PQ, so V = PQ/M
        predicted_v = (average_price * total_quantity) / average_supply

        return float(predicted_v)

    def add_measurement(
        self,
        period_start: float,
        period_end: float,
        transaction_volume: float,
        average_supply: float,
        average_price: float,
        total_quantity: float,
    ):
        """
        Add a velocity measurement.

        Args:
            period_start: Period start timestamp
            period_end: Period end timestamp
            transaction_volume: Total tokens transacted
            average_supply: Average token supply
            average_price: Average price per kWh
            total_quantity: Total kWh traded
        """
        period_days = (period_end - period_start) / (24 * 3600)

        actual_v = self.calculate_actual_velocity(
            transaction_volume,
            average_supply,
            int(period_days),
        )

        predicted_v = self.calculate_predicted_velocity(
            average_price,
            total_quantity,
            average_supply,
        )

        measurement = VelocityMeasurement(
            period_start=period_start,
            period_end=period_end,
            transaction_volume=transaction_volume,
            average_supply=average_supply,
            average_price=average_price,
            total_quantity=total_quantity,
            actual_velocity=actual_v,
            predicted_velocity=predicted_v,
        )

        self.measurements.append(measurement)

    def test_fisher_equation(
        self,
        tolerance: float = 0.20,
        alpha: float = 0.05,
    ) -> VelocityTestResult:
        """
        Test Fisher equation validity.

        Tests H4.3: |V_actual - V_predicted| / V_predicted < tolerance

        Uses paired t-test on (actual - predicted) velocities.

        Args:
            tolerance: Maximum allowed relative error (default 20%)
            alpha: Significance level

        Returns:
            VelocityTestResult
        """
        if len(self.measurements) < 2:
            return VelocityTestResult(
                is_valid=True,
                mean_actual_velocity=0,
                mean_predicted_velocity=0,
                mean_absolute_error=0,
                correlation=1.0,
                r_squared=1.0,
                t_statistic=0,
                p_value=1.0,
                tolerance=tolerance,
                sample_size=len(self.measurements),
            )

        actual = np.array([m.actual_velocity for m in self.measurements])
        predicted = np.array([m.predicted_velocity for m in self.measurements])

        # Filter out zeros to avoid division issues
        valid_mask = predicted > 0
        if np.sum(valid_mask) < 2:
            return VelocityTestResult(
                is_valid=True,
                mean_actual_velocity=float(np.mean(actual)),
                mean_predicted_velocity=float(np.mean(predicted)),
                mean_absolute_error=0,
                correlation=1.0,
                r_squared=1.0,
                t_statistic=0,
                p_value=1.0,
                tolerance=tolerance,
                sample_size=len(self.measurements),
            )

        actual_valid = actual[valid_mask]
        predicted_valid = predicted[valid_mask]

        # Calculate relative errors
        relative_errors = np.abs(actual_valid - predicted_valid) / predicted_valid
        mean_absolute_error = float(np.mean(relative_errors))

        # Correlation
        if len(actual_valid) > 1 and np.std(actual_valid) > 0 and np.std(predicted_valid) > 0:
            correlation = float(np.corrcoef(actual_valid, predicted_valid)[0, 1])
        else:
            correlation = 1.0

        # R-squared from regression
        if len(actual_valid) > 1:
            ss_res = np.sum((actual_valid - predicted_valid) ** 2)
            ss_tot = np.sum((actual_valid - np.mean(actual_valid)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
            r_squared = max(0, min(1, r_squared))  # Clamp to [0, 1]
        else:
            r_squared = 1.0

        # Paired t-test on differences
        differences = actual_valid - predicted_valid
        n = len(differences)

        if np.std(differences) > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(differences, 0)
        else:
            t_stat = 0.0
            p_value = 1.0

        # Check if Fisher equation holds: mean absolute error < tolerance
        is_valid = mean_absolute_error < tolerance

        return VelocityTestResult(
            is_valid=is_valid,
            mean_actual_velocity=float(np.mean(actual)),
            mean_predicted_velocity=float(np.mean(predicted)),
            mean_absolute_error=mean_absolute_error,
            correlation=correlation,
            r_squared=float(r_squared),
            t_statistic=float(t_stat),
            p_value=float(p_value),
            tolerance=tolerance,
            sample_size=n,
        )

    def test_with_arrays(
        self,
        actual_velocities: np.ndarray,
        predicted_velocities: np.ndarray,
        tolerance: float = 0.20,
    ) -> VelocityTestResult:
        """
        Test Fisher equation with pre-computed velocity arrays.

        Args:
            actual_velocities: Array of actual velocities
            predicted_velocities: Array of predicted velocities
            tolerance: Maximum allowed relative error

        Returns:
            VelocityTestResult
        """
        if len(actual_velocities) < 2 or len(predicted_velocities) < 2:
            return VelocityTestResult(
                is_valid=True,
                mean_actual_velocity=float(np.mean(actual_velocities)) if len(actual_velocities) > 0 else 0,
                mean_predicted_velocity=float(np.mean(predicted_velocities)) if len(predicted_velocities) > 0 else 0,
                mean_absolute_error=0,
                correlation=1.0,
                r_squared=1.0,
                t_statistic=0,
                p_value=1.0,
                tolerance=tolerance,
                sample_size=min(len(actual_velocities), len(predicted_velocities)),
            )

        # Ensure same length
        n = min(len(actual_velocities), len(predicted_velocities))
        actual = actual_velocities[:n]
        predicted = predicted_velocities[:n]

        # Filter zeros
        valid_mask = predicted > 0
        if np.sum(valid_mask) < 2:
            return VelocityTestResult(
                is_valid=True,
                mean_actual_velocity=float(np.mean(actual)),
                mean_predicted_velocity=float(np.mean(predicted)),
                mean_absolute_error=0,
                correlation=1.0,
                r_squared=1.0,
                t_statistic=0,
                p_value=1.0,
                tolerance=tolerance,
                sample_size=n,
            )

        actual_valid = actual[valid_mask]
        predicted_valid = predicted[valid_mask]

        # Calculate metrics
        relative_errors = np.abs(actual_valid - predicted_valid) / predicted_valid
        mean_absolute_error = float(np.mean(relative_errors))

        if np.std(actual_valid) > 0 and np.std(predicted_valid) > 0:
            correlation = float(np.corrcoef(actual_valid, predicted_valid)[0, 1])
        else:
            correlation = 1.0

        ss_res = np.sum((actual_valid - predicted_valid) ** 2)
        ss_tot = np.sum((actual_valid - np.mean(actual_valid)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
        r_squared = max(0, min(1, r_squared))

        differences = actual_valid - predicted_valid
        if np.std(differences) > 0:
            t_stat, p_value = scipy_stats.ttest_1samp(differences, 0)
        else:
            t_stat, p_value = 0.0, 1.0

        is_valid = mean_absolute_error < tolerance

        return VelocityTestResult(
            is_valid=is_valid,
            mean_actual_velocity=float(np.mean(actual)),
            mean_predicted_velocity=float(np.mean(predicted)),
            mean_absolute_error=mean_absolute_error,
            correlation=correlation,
            r_squared=float(r_squared),
            t_statistic=float(t_stat),
            p_value=float(p_value),
            tolerance=tolerance,
            sample_size=int(np.sum(valid_mask)),
        )

    def get_statistics(self) -> VelocityStatistics:
        """
        Get aggregate velocity statistics.

        Returns:
            VelocityStatistics
        """
        if not self.measurements:
            return VelocityStatistics(
                mean_velocity=0,
                std_velocity=0,
                min_velocity=0,
                max_velocity=0,
                median_velocity=0,
                annualized_velocity=0,
            )

        velocities = np.array([m.actual_velocity for m in self.measurements])

        # Calculate average period length for annualization
        total_days = sum(m.period_days for m in self.measurements)
        avg_period_days = total_days / len(self.measurements) if self.measurements else 1

        mean_v = float(np.mean(velocities))
        annualized = mean_v * (365 / avg_period_days) if avg_period_days > 0 else mean_v

        return VelocityStatistics(
            mean_velocity=mean_v,
            std_velocity=float(np.std(velocities)),
            min_velocity=float(np.min(velocities)),
            max_velocity=float(np.max(velocities)),
            median_velocity=float(np.median(velocities)),
            annualized_velocity=annualized,
        )

    def get_velocity_series(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get time series of velocities.

        Returns:
            Tuple of (timestamps, actual_velocities, predicted_velocities)
        """
        timestamps = np.array([m.period_end for m in self.measurements])
        actual = np.array([m.actual_velocity for m in self.measurements])
        predicted = np.array([m.predicted_velocity for m in self.measurements])

        return timestamps, actual, predicted

    def clear(self):
        """Clear all measurements."""
        self.measurements = []


def simulate_velocity_data(
    num_periods: int = 30,
    period_days: int = 1,
    base_supply: float = 1_000_000.0,
    base_volume: float = 100_000.0,
    base_price: float = 1.0,
    volume_volatility: float = 0.2,
    price_volatility: float = 0.1,
    fisher_noise: float = 0.1,
    seed: Optional[int] = None,
) -> VelocityCalculator:
    """
    Simulate velocity data for testing.

    Args:
        num_periods: Number of periods to simulate
        period_days: Days per period
        base_supply: Base token supply
        base_volume: Base transaction volume
        base_price: Base price per kWh
        volume_volatility: Volume volatility
        price_volatility: Price volatility
        fisher_noise: Noise in Fisher equation adherence
        seed: Random seed

    Returns:
        VelocityCalculator with simulated data
    """
    rng = np.random.default_rng(seed)

    calculator = VelocityCalculator()
    start_time = datetime.now().timestamp()

    for i in range(num_periods):
        period_start = start_time + i * period_days * 24 * 3600
        period_end = period_start + period_days * 24 * 3600

        # Simulate supply (slight random walk)
        supply_change = rng.normal(0, base_supply * 0.01)
        average_supply = base_supply + supply_change

        # Simulate price with volatility
        price_factor = rng.lognormal(0, price_volatility)
        average_price = base_price * price_factor

        # Simulate quantity traded
        volume_factor = rng.lognormal(0, volume_volatility)
        total_quantity = base_volume * volume_factor

        # Transaction volume should approximately follow Fisher equation
        # with some noise
        expected_volume = average_price * total_quantity
        noise_factor = rng.normal(1, fisher_noise)
        transaction_volume = expected_volume * noise_factor

        calculator.add_measurement(
            period_start=period_start,
            period_end=period_end,
            transaction_volume=transaction_volume,
            average_supply=average_supply,
            average_price=average_price,
            total_quantity=total_quantity,
        )

    return calculator


def simulate_velocity_scenarios(
    num_periods: int = 30,
    seed: Optional[int] = None,
) -> Dict[str, VelocityCalculator]:
    """
    Simulate multiple velocity scenarios.

    Args:
        num_periods: Periods per scenario
        seed: Random seed

    Returns:
        Dictionary of scenario name -> VelocityCalculator
    """
    scenarios = {}

    # Baseline: Fisher equation holds well
    scenarios["baseline"] = simulate_velocity_data(
        num_periods=num_periods,
        fisher_noise=0.05,
        seed=seed,
    )

    # High volume variation
    scenarios["high_volume_var"] = simulate_velocity_data(
        num_periods=num_periods,
        volume_volatility=0.5,
        fisher_noise=0.1,
        seed=seed + 1 if seed else None,
    )

    # Fisher equation breaks down
    scenarios["fisher_deviation"] = simulate_velocity_data(
        num_periods=num_periods,
        fisher_noise=0.3,
        seed=seed + 2 if seed else None,
    )

    # Low velocity (speculative holding)
    scenarios["speculative"] = simulate_velocity_data(
        num_periods=num_periods,
        base_volume=50_000.0,  # Lower volume
        fisher_noise=0.15,
        seed=seed + 3 if seed else None,
    )

    return scenarios
