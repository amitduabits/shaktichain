"""
Token Supply Tracker for SHAKTI-CHAIN Token Economics (Domain 4).

Tracks token supply over time and calculates stability metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TokenSupplySnapshot:
    """
    Snapshot of token supply at a point in time.

    Attributes:
        timestamp: Unix timestamp
        total_supply: Total tokens in existence
        circulating_supply: Tokens actively circulating
        staked_supply: Tokens locked in staking
        treasury_reserve: Tokens held in protocol treasury
        burned_cumulative: Cumulative tokens burned
        minted_cumulative: Cumulative tokens minted
    """
    timestamp: float
    total_supply: float
    circulating_supply: float
    staked_supply: float = 0.0
    treasury_reserve: float = 0.0
    burned_cumulative: float = 0.0
    minted_cumulative: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "total_supply": float(self.total_supply),
            "circulating_supply": float(self.circulating_supply),
            "staked_supply": float(self.staked_supply),
            "treasury_reserve": float(self.treasury_reserve),
            "burned_cumulative": float(self.burned_cumulative),
            "minted_cumulative": float(self.minted_cumulative),
        }

    @property
    def datetime(self) -> datetime:
        """Get datetime from timestamp."""
        return datetime.fromtimestamp(self.timestamp)


@dataclass
class SupplyStabilityMetrics:
    """
    Token supply stability metrics.

    Attributes:
        mean_supply: Mean supply over period
        std_supply: Standard deviation
        cv: Coefficient of variation
        min_supply: Minimum supply
        max_supply: Maximum supply
        supply_range_pct: (max - min) / mean as percentage
        num_snapshots: Number of data points
    """
    mean_supply: float
    std_supply: float
    cv: float
    min_supply: float
    max_supply: float
    supply_range_pct: float
    num_snapshots: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_supply": float(self.mean_supply),
            "std_supply": float(self.std_supply),
            "cv": float(self.cv),
            "min_supply": float(self.min_supply),
            "max_supply": float(self.max_supply),
            "supply_range_pct": float(self.supply_range_pct),
            "num_snapshots": self.num_snapshots,
        }


@dataclass
class RollingStabilityResult:
    """
    Result of rolling window stability analysis.

    Attributes:
        window_days: Window size in days
        mean_cv: Mean coefficient of variation across windows
        max_cv: Maximum CV observed
        min_cv: Minimum CV observed
        std_cv: Standard deviation of CVs
        windows_above_threshold: Number of windows exceeding CV threshold
        threshold: CV threshold used
        cv_values: All CV values computed
    """
    window_days: int
    mean_cv: float
    max_cv: float
    min_cv: float
    std_cv: float
    windows_above_threshold: int
    threshold: float
    cv_values: np.ndarray

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "window_days": self.window_days,
            "mean_cv": float(self.mean_cv),
            "max_cv": float(self.max_cv),
            "min_cv": float(self.min_cv),
            "std_cv": float(self.std_cv),
            "windows_above_threshold": self.windows_above_threshold,
            "threshold": self.threshold,
            "cv_values_summary": {
                "count": len(self.cv_values),
                "percentiles": {
                    "p25": float(np.percentile(self.cv_values, 25)),
                    "p50": float(np.percentile(self.cv_values, 50)),
                    "p75": float(np.percentile(self.cv_values, 75)),
                    "p95": float(np.percentile(self.cv_values, 95)),
                }
            }
        }


class TokenSupplyTracker:
    """
    Track token supply over time and analyze stability.

    Monitors total supply, circulating supply, and calculates
    stability metrics including coefficient of variation.
    """

    def __init__(
        self,
        initial_supply: float = 1_000_000.0,
        snapshot_interval_hours: float = 1.0,
    ):
        """
        Initialize token supply tracker.

        Args:
            initial_supply: Initial token supply
            snapshot_interval_hours: Expected interval between snapshots
        """
        self.initial_supply = initial_supply
        self.snapshot_interval_hours = snapshot_interval_hours
        self.snapshots: List[TokenSupplySnapshot] = []

        # Initialize with initial supply
        initial_snapshot = TokenSupplySnapshot(
            timestamp=datetime.now().timestamp(),
            total_supply=initial_supply,
            circulating_supply=initial_supply,
            staked_supply=0.0,
            treasury_reserve=0.0,
            burned_cumulative=0.0,
            minted_cumulative=0.0,
        )
        self.snapshots.append(initial_snapshot)

    def record_snapshot(self, snapshot: TokenSupplySnapshot):
        """
        Record a supply snapshot.

        Args:
            snapshot: TokenSupplySnapshot to record
        """
        self.snapshots.append(snapshot)

    def record_supply(
        self,
        timestamp: float,
        total_supply: float,
        circulating_supply: Optional[float] = None,
        staked_supply: float = 0.0,
        treasury_reserve: float = 0.0,
        burned_cumulative: float = 0.0,
        minted_cumulative: float = 0.0,
    ):
        """
        Record supply at a given timestamp.

        Args:
            timestamp: Unix timestamp
            total_supply: Total token supply
            circulating_supply: Circulating supply (defaults to total)
            staked_supply: Staked tokens
            treasury_reserve: Treasury tokens
            burned_cumulative: Cumulative burned
            minted_cumulative: Cumulative minted
        """
        if circulating_supply is None:
            circulating_supply = total_supply - staked_supply - treasury_reserve

        snapshot = TokenSupplySnapshot(
            timestamp=timestamp,
            total_supply=total_supply,
            circulating_supply=circulating_supply,
            staked_supply=staked_supply,
            treasury_reserve=treasury_reserve,
            burned_cumulative=burned_cumulative,
            minted_cumulative=minted_cumulative,
        )
        self.record_snapshot(snapshot)

    def get_supply_series(self, supply_type: str = "total") -> Tuple[np.ndarray, np.ndarray]:
        """
        Get time series of supply values.

        Args:
            supply_type: 'total', 'circulating', 'staked', or 'treasury'

        Returns:
            Tuple of (timestamps, supply_values)
        """
        timestamps = np.array([s.timestamp for s in self.snapshots])

        if supply_type == "total":
            values = np.array([s.total_supply for s in self.snapshots])
        elif supply_type == "circulating":
            values = np.array([s.circulating_supply for s in self.snapshots])
        elif supply_type == "staked":
            values = np.array([s.staked_supply for s in self.snapshots])
        elif supply_type == "treasury":
            values = np.array([s.treasury_reserve for s in self.snapshots])
        else:
            raise ValueError(f"Unknown supply_type: {supply_type}")

        return timestamps, values

    def calculate_overall_stability(
        self,
        supply_type: str = "total",
    ) -> SupplyStabilityMetrics:
        """
        Calculate overall supply stability metrics.

        Args:
            supply_type: Type of supply to analyze

        Returns:
            SupplyStabilityMetrics
        """
        _, values = self.get_supply_series(supply_type)

        if len(values) < 2:
            return SupplyStabilityMetrics(
                mean_supply=values[0] if len(values) > 0 else 0,
                std_supply=0,
                cv=0,
                min_supply=values[0] if len(values) > 0 else 0,
                max_supply=values[0] if len(values) > 0 else 0,
                supply_range_pct=0,
                num_snapshots=len(values),
            )

        mean_supply = float(np.mean(values))
        std_supply = float(np.std(values))
        cv = std_supply / mean_supply if mean_supply > 0 else 0
        min_supply = float(np.min(values))
        max_supply = float(np.max(values))
        supply_range_pct = (max_supply - min_supply) / mean_supply * 100 if mean_supply > 0 else 0

        return SupplyStabilityMetrics(
            mean_supply=mean_supply,
            std_supply=std_supply,
            cv=cv,
            min_supply=min_supply,
            max_supply=max_supply,
            supply_range_pct=supply_range_pct,
            num_snapshots=len(values),
        )

    def calculate_rolling_stability(
        self,
        window_days: int = 30,
        cv_threshold: float = 0.05,
        supply_type: str = "total",
    ) -> RollingStabilityResult:
        """
        Calculate supply stability over rolling windows.

        Args:
            window_days: Window size in days
            cv_threshold: CV threshold for stability (default 5%)
            supply_type: Type of supply to analyze

        Returns:
            RollingStabilityResult with CV statistics
        """
        timestamps, values = self.get_supply_series(supply_type)

        if len(values) < 2:
            return RollingStabilityResult(
                window_days=window_days,
                mean_cv=0,
                max_cv=0,
                min_cv=0,
                std_cv=0,
                windows_above_threshold=0,
                threshold=cv_threshold,
                cv_values=np.array([0]),
            )

        # Convert window to number of snapshots
        hours_per_window = window_days * 24
        snapshots_per_window = int(hours_per_window / self.snapshot_interval_hours)
        snapshots_per_window = max(2, min(snapshots_per_window, len(values)))

        # Calculate rolling CV
        cv_values = []
        for i in range(len(values) - snapshots_per_window + 1):
            window_values = values[i:i + snapshots_per_window]
            mean_val = np.mean(window_values)
            std_val = np.std(window_values)
            cv = std_val / mean_val if mean_val > 0 else 0
            cv_values.append(cv)

        cv_values = np.array(cv_values)

        if len(cv_values) == 0:
            cv_values = np.array([0])

        return RollingStabilityResult(
            window_days=window_days,
            mean_cv=float(np.mean(cv_values)),
            max_cv=float(np.max(cv_values)),
            min_cv=float(np.min(cv_values)),
            std_cv=float(np.std(cv_values)),
            windows_above_threshold=int(np.sum(cv_values > cv_threshold)),
            threshold=cv_threshold,
            cv_values=cv_values,
        )

    def detect_supply_anomalies(
        self,
        threshold_std: float = 3.0,
        supply_type: str = "total",
    ) -> List[Tuple[TokenSupplySnapshot, float]]:
        """
        Identify supply changes exceeding threshold standard deviations.

        Args:
            threshold_std: Number of standard deviations for anomaly
            supply_type: Type of supply to analyze

        Returns:
            List of (snapshot, z_score) tuples for anomalies
        """
        timestamps, values = self.get_supply_series(supply_type)

        if len(values) < 3:
            return []

        # Calculate period-over-period changes
        changes = np.diff(values)
        mean_change = np.mean(changes)
        std_change = np.std(changes)

        if std_change == 0:
            return []

        anomalies = []
        for i, change in enumerate(changes):
            z_score = (change - mean_change) / std_change
            if abs(z_score) > threshold_std:
                # Return the snapshot AFTER the anomalous change
                anomalies.append((self.snapshots[i + 1], z_score))

        return anomalies

    def calculate_supply_growth_rate(
        self,
        period_days: int = 365,
    ) -> float:
        """
        Calculate annualized supply growth rate.

        Args:
            period_days: Period over which to calculate

        Returns:
            Annualized growth rate (e.g., 0.05 for 5%)
        """
        timestamps, values = self.get_supply_series("total")

        if len(values) < 2:
            return 0.0

        # Get values at start and end of period
        start_value = values[0]
        end_value = values[-1]

        # Calculate actual period in days
        actual_days = (timestamps[-1] - timestamps[0]) / (24 * 3600)

        if actual_days <= 0 or start_value <= 0:
            return 0.0

        # Calculate growth rate
        growth_ratio = end_value / start_value
        daily_rate = growth_ratio ** (1 / actual_days) - 1
        annual_rate = (1 + daily_rate) ** 365 - 1

        return float(annual_rate)

    def get_latest_snapshot(self) -> Optional[TokenSupplySnapshot]:
        """Get the most recent snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    def get_snapshots_in_range(
        self,
        start_timestamp: float,
        end_timestamp: float,
    ) -> List[TokenSupplySnapshot]:
        """Get snapshots within a time range."""
        return [
            s for s in self.snapshots
            if start_timestamp <= s.timestamp <= end_timestamp
        ]

    def clear(self):
        """Clear all snapshots except the initial one."""
        if self.snapshots:
            initial = self.snapshots[0]
            self.snapshots = [initial]


def simulate_token_supply(
    initial_supply: float = 1_000_000.0,
    duration_days: int = 90,
    snapshot_interval_hours: float = 1.0,
    daily_mint_mean: float = 1000.0,
    daily_burn_mean: float = 1000.0,
    volatility: float = 0.1,
    seed: Optional[int] = None,
) -> TokenSupplyTracker:
    """
    Simulate token supply over time.

    Args:
        initial_supply: Initial token supply
        duration_days: Duration to simulate
        snapshot_interval_hours: Hours between snapshots
        daily_mint_mean: Mean daily mint volume
        daily_burn_mean: Mean daily burn volume
        volatility: Volatility of mint/burn (as fraction of mean)
        seed: Random seed

    Returns:
        TokenSupplyTracker with simulated data
    """
    rng = np.random.default_rng(seed)

    tracker = TokenSupplyTracker(
        initial_supply=initial_supply,
        snapshot_interval_hours=snapshot_interval_hours,
    )

    # Remove default initial snapshot and start fresh
    tracker.snapshots = []

    current_supply = initial_supply
    cumulative_minted = 0.0
    cumulative_burned = 0.0

    # Calculate per-snapshot rates
    snapshots_per_day = 24 / snapshot_interval_hours
    mint_per_snapshot = daily_mint_mean / snapshots_per_day
    burn_per_snapshot = daily_burn_mean / snapshots_per_day

    start_time = datetime.now().timestamp()
    num_snapshots = int(duration_days * snapshots_per_day)

    for i in range(num_snapshots):
        timestamp = start_time + i * snapshot_interval_hours * 3600

        # Generate mint/burn with volatility
        mint_amount = max(0, rng.normal(mint_per_snapshot, mint_per_snapshot * volatility))
        burn_amount = max(0, rng.normal(burn_per_snapshot, burn_per_snapshot * volatility))

        # Ensure burn doesn't exceed supply
        burn_amount = min(burn_amount, current_supply * 0.01)  # Max 1% per snapshot

        cumulative_minted += mint_amount
        cumulative_burned += burn_amount
        current_supply = initial_supply + cumulative_minted - cumulative_burned

        # Random staking fraction (5-15% of supply)
        staked_fraction = rng.uniform(0.05, 0.15)
        staked_supply = current_supply * staked_fraction

        # Treasury reserve (1-3% of supply)
        treasury_fraction = rng.uniform(0.01, 0.03)
        treasury_reserve = current_supply * treasury_fraction

        circulating_supply = current_supply - staked_supply - treasury_reserve

        snapshot = TokenSupplySnapshot(
            timestamp=timestamp,
            total_supply=current_supply,
            circulating_supply=circulating_supply,
            staked_supply=staked_supply,
            treasury_reserve=treasury_reserve,
            burned_cumulative=cumulative_burned,
            minted_cumulative=cumulative_minted,
        )
        tracker.record_snapshot(snapshot)

    return tracker


def simulate_supply_scenarios(
    initial_supply: float = 1_000_000.0,
    duration_days: int = 30,
    seed: Optional[int] = None,
) -> Dict[str, TokenSupplyTracker]:
    """
    Simulate multiple supply scenarios.

    Args:
        initial_supply: Initial token supply
        duration_days: Duration to simulate
        seed: Random seed

    Returns:
        Dictionary of scenario name -> TokenSupplyTracker
    """
    scenarios = {}

    # Baseline: balanced mint/burn
    scenarios["baseline"] = simulate_token_supply(
        initial_supply=initial_supply,
        duration_days=duration_days,
        daily_mint_mean=1000.0,
        daily_burn_mean=1000.0,
        volatility=0.1,
        seed=seed,
    )

    # High demand: more minting
    scenarios["high_demand"] = simulate_token_supply(
        initial_supply=initial_supply,
        duration_days=duration_days,
        daily_mint_mean=2000.0,
        daily_burn_mean=1000.0,
        volatility=0.15,
        seed=seed + 1 if seed else None,
    )

    # Low demand: more burning
    scenarios["low_demand"] = simulate_token_supply(
        initial_supply=initial_supply,
        duration_days=duration_days,
        daily_mint_mean=500.0,
        daily_burn_mean=1500.0,
        volatility=0.15,
        seed=seed + 2 if seed else None,
    )

    # High volatility
    scenarios["volatile"] = simulate_token_supply(
        initial_supply=initial_supply,
        duration_days=duration_days,
        daily_mint_mean=1000.0,
        daily_burn_mean=1000.0,
        volatility=0.5,
        seed=seed + 3 if seed else None,
    )

    return scenarios
