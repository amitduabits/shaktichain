"""
Availability Monitor for SHAKTI-CHAIN System Performance Testing (Domain 3).

Tracks system uptime, downtime events, and calculates availability metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np


class SystemState(Enum):
    """System availability states."""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


@dataclass
class DowntimeEvent:
    """
    Record of a downtime event.

    Attributes:
        start_time: When downtime started (Unix timestamp)
        end_time: When downtime ended (None if ongoing)
        duration_seconds: Total duration of downtime
        state: Type of unavailability
        reason: Description of the cause
        impact: Severity impact (1-10)
    """
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    state: SystemState = SystemState.DOWN
    reason: str = "unknown"
    impact: int = 5

    def __post_init__(self):
        """Calculate duration if end_time is set."""
        if self.end_time is not None and self.duration_seconds is None:
            self.duration_seconds = self.end_time - self.start_time

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "state": self.state.value,
            "reason": self.reason,
            "impact": self.impact,
        }


@dataclass
class AvailabilityMetrics:
    """
    System availability metrics.

    Attributes:
        availability_pct: Overall availability percentage
        uptime_seconds: Total uptime
        downtime_seconds: Total downtime
        monitoring_period_seconds: Total monitoring period
        num_downtime_events: Number of downtime events
        mtbf_seconds: Mean time between failures
        mttr_seconds: Mean time to recovery
        longest_downtime_seconds: Longest single downtime
        availability_by_day: Daily availability breakdown
    """
    availability_pct: float
    uptime_seconds: float
    downtime_seconds: float
    monitoring_period_seconds: float
    num_downtime_events: int
    mtbf_seconds: float
    mttr_seconds: float
    longest_downtime_seconds: float
    availability_by_day: Dict[str, float]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "availability_pct": float(self.availability_pct),
            "uptime_seconds": float(self.uptime_seconds),
            "downtime_seconds": float(self.downtime_seconds),
            "monitoring_period_seconds": float(self.monitoring_period_seconds),
            "num_downtime_events": self.num_downtime_events,
            "mtbf_seconds": float(self.mtbf_seconds),
            "mttr_seconds": float(self.mttr_seconds),
            "longest_downtime_seconds": float(self.longest_downtime_seconds),
            "availability_by_day": self.availability_by_day,
        }

    @property
    def meets_sla(self) -> bool:
        """Check if availability meets 99.9% SLA."""
        return self.availability_pct >= 99.9


@dataclass
class SettlementFinalityMetrics:
    """
    Settlement finality metrics.

    Attributes:
        total_settlements: Total number of settlements
        finalized_within_target: Number finalized within target time
        finality_rate: Fraction finalized within target
        mean_finality_time_seconds: Mean time to finality
        p95_finality_time_seconds: 95th percentile finality time
        p99_finality_time_seconds: 99th percentile finality time
        max_finality_time_seconds: Maximum finality time observed
    """
    total_settlements: int
    finalized_within_target: int
    finality_rate: float
    mean_finality_time_seconds: float
    p95_finality_time_seconds: float
    p99_finality_time_seconds: float
    max_finality_time_seconds: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_settlements": self.total_settlements,
            "finalized_within_target": self.finalized_within_target,
            "finality_rate": float(self.finality_rate),
            "mean_finality_time_seconds": float(self.mean_finality_time_seconds),
            "p95_finality_time_seconds": float(self.p95_finality_time_seconds),
            "p99_finality_time_seconds": float(self.p99_finality_time_seconds),
            "max_finality_time_seconds": float(self.max_finality_time_seconds),
        }


class AvailabilityMonitor:
    """
    Monitor system availability and track downtime events.

    Provides methods for recording status, calculating metrics,
    and analyzing availability patterns.
    """

    def __init__(self):
        """Initialize availability monitor."""
        self.downtime_events: List[DowntimeEvent] = []
        self.status_history: List[Tuple[float, SystemState]] = []
        self.monitoring_start: Optional[float] = None
        self.monitoring_end: Optional[float] = None
        self.current_state: SystemState = SystemState.UP
        self._current_downtime_start: Optional[float] = None

    def start_monitoring(self):
        """Start the monitoring period."""
        self.monitoring_start = time.time()
        self.status_history.append((self.monitoring_start, SystemState.UP))

    def stop_monitoring(self):
        """Stop the monitoring period."""
        self.monitoring_end = time.time()

        # Close any ongoing downtime
        if self._current_downtime_start is not None:
            self.record_recovery(reason="monitoring_ended")

    def record_downtime(
        self,
        state: SystemState = SystemState.DOWN,
        reason: str = "unknown",
        impact: int = 5,
    ):
        """
        Record the start of a downtime event.

        Args:
            state: Type of unavailability
            reason: Reason for downtime
            impact: Severity (1-10)
        """
        current_time = time.time()

        if self._current_downtime_start is not None:
            # Already in downtime, update reason
            return

        self._current_downtime_start = current_time
        self.current_state = state
        self.status_history.append((current_time, state))

        # Create event (will complete on recovery)
        event = DowntimeEvent(
            start_time=current_time,
            state=state,
            reason=reason,
            impact=impact,
        )
        self.downtime_events.append(event)

    def record_recovery(
        self,
        reason: str = "recovered",
    ):
        """
        Record recovery from downtime.

        Args:
            reason: Recovery reason/notes
        """
        current_time = time.time()

        if self._current_downtime_start is None:
            # Not in downtime
            return

        # Complete the current downtime event
        if self.downtime_events:
            event = self.downtime_events[-1]
            if event.end_time is None:
                event.end_time = current_time
                event.duration_seconds = current_time - event.start_time

        self._current_downtime_start = None
        self.current_state = SystemState.UP
        self.status_history.append((current_time, SystemState.UP))

    def record_status(self, state: SystemState):
        """
        Record current status.

        Args:
            state: Current system state
        """
        current_time = time.time()

        if state != self.current_state:
            if state == SystemState.UP:
                self.record_recovery()
            elif state in [SystemState.DOWN, SystemState.DEGRADED]:
                self.record_downtime(state=state)

        self.current_state = state
        self.status_history.append((current_time, state))

    def add_downtime_event(self, event: DowntimeEvent):
        """
        Add a historical downtime event.

        Args:
            event: DowntimeEvent to add
        """
        self.downtime_events.append(event)

    def calculate_metrics(self) -> AvailabilityMetrics:
        """
        Calculate availability metrics.

        Returns:
            AvailabilityMetrics with calculated values
        """
        if self.monitoring_start is None:
            self.monitoring_start = time.time() - 3600  # Default 1 hour ago

        if self.monitoring_end is None:
            self.monitoring_end = time.time()

        total_period = self.monitoring_end - self.monitoring_start

        # Calculate total downtime
        total_downtime = 0.0
        for event in self.downtime_events:
            if event.duration_seconds is not None:
                # Clip to monitoring period
                event_start = max(event.start_time, self.monitoring_start)
                event_end = event.end_time or self.monitoring_end
                event_end = min(event_end, self.monitoring_end)
                if event_end > event_start:
                    total_downtime += event_end - event_start

        total_uptime = total_period - total_downtime
        availability_pct = (total_uptime / total_period * 100) if total_period > 0 else 100.0

        # MTBF and MTTR
        completed_events = [e for e in self.downtime_events if e.duration_seconds is not None]
        n_events = len(completed_events)

        if n_events > 0:
            mttr = np.mean([e.duration_seconds for e in completed_events])
            longest = max(e.duration_seconds for e in completed_events)
        else:
            mttr = 0.0
            longest = 0.0

        if n_events > 1:
            mtbf = total_uptime / n_events
        elif n_events == 1:
            mtbf = total_uptime
        else:
            mtbf = total_period

        # Daily breakdown
        availability_by_day = self._calculate_daily_availability()

        return AvailabilityMetrics(
            availability_pct=availability_pct,
            uptime_seconds=total_uptime,
            downtime_seconds=total_downtime,
            monitoring_period_seconds=total_period,
            num_downtime_events=n_events,
            mtbf_seconds=mtbf,
            mttr_seconds=mttr,
            longest_downtime_seconds=longest,
            availability_by_day=availability_by_day,
        )

    def _calculate_daily_availability(self) -> Dict[str, float]:
        """Calculate availability for each day in the monitoring period."""
        if self.monitoring_start is None or self.monitoring_end is None:
            return {}

        daily_availability = {}

        # Create day boundaries
        start_date = datetime.fromtimestamp(self.monitoring_start).date()
        end_date = datetime.fromtimestamp(self.monitoring_end).date()

        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time()).timestamp()
            day_end = day_start + 86400  # 24 hours

            # Clip to monitoring period
            day_start = max(day_start, self.monitoring_start)
            day_end = min(day_end, self.monitoring_end)

            if day_end <= day_start:
                current_date += timedelta(days=1)
                continue

            day_duration = day_end - day_start

            # Calculate downtime for this day
            day_downtime = 0.0
            for event in self.downtime_events:
                event_start = event.start_time
                event_end = event.end_time or self.monitoring_end

                # Check overlap with day
                overlap_start = max(event_start, day_start)
                overlap_end = min(event_end, day_end)

                if overlap_end > overlap_start:
                    day_downtime += overlap_end - overlap_start

            day_availability = (day_duration - day_downtime) / day_duration * 100
            daily_availability[current_date.isoformat()] = day_availability

            current_date += timedelta(days=1)

        return daily_availability

    def get_availability_time_series(
        self,
        interval_seconds: float = 3600,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get availability as time series.

        Args:
            interval_seconds: Aggregation interval

        Returns:
            Tuple of (timestamps, availability_pct) arrays
        """
        if self.monitoring_start is None or self.monitoring_end is None:
            return np.array([]), np.array([])

        timestamps = []
        availabilities = []

        current = self.monitoring_start
        while current < self.monitoring_end:
            interval_end = min(current + interval_seconds, self.monitoring_end)
            interval_duration = interval_end - current

            # Calculate downtime in interval
            interval_downtime = 0.0
            for event in self.downtime_events:
                event_start = event.start_time
                event_end = event.end_time or self.monitoring_end

                overlap_start = max(event_start, current)
                overlap_end = min(event_end, interval_end)

                if overlap_end > overlap_start:
                    interval_downtime += overlap_end - overlap_start

            availability = (interval_duration - interval_downtime) / interval_duration * 100

            timestamps.append(current)
            availabilities.append(availability)

            current = interval_end

        return np.array(timestamps), np.array(availabilities)

    def clear(self):
        """Clear all monitoring data."""
        self.downtime_events = []
        self.status_history = []
        self.monitoring_start = None
        self.monitoring_end = None
        self.current_state = SystemState.UP
        self._current_downtime_start = None


class SettlementFinalityTracker:
    """
    Track settlement finality times.

    Records time from trade execution to settlement confirmation.
    """

    def __init__(
        self,
        target_seconds: float = 30.0,
    ):
        """
        Initialize finality tracker.

        Args:
            target_seconds: Target finality time for SLA
        """
        self.target_seconds = target_seconds
        self.finality_times: List[float] = []
        self._pending: Dict[str, float] = {}  # settlement_id -> start_time

    def start_settlement(self, settlement_id: str):
        """
        Record start of settlement process.

        Args:
            settlement_id: Unique settlement identifier
        """
        self._pending[settlement_id] = time.time()

    def complete_settlement(self, settlement_id: str) -> Optional[float]:
        """
        Record completion of settlement.

        Args:
            settlement_id: Unique settlement identifier

        Returns:
            Finality time in seconds, or None if not found
        """
        if settlement_id not in self._pending:
            return None

        start_time = self._pending.pop(settlement_id)
        finality_time = time.time() - start_time
        self.finality_times.append(finality_time)

        return finality_time

    def record_finality_time(self, finality_seconds: float):
        """
        Record a finality time directly.

        Args:
            finality_seconds: Time to finality
        """
        self.finality_times.append(finality_seconds)

    def record_batch(self, finality_times: List[float]):
        """
        Record a batch of finality times.

        Args:
            finality_times: List of finality times in seconds
        """
        self.finality_times.extend(finality_times)

    def calculate_metrics(self) -> SettlementFinalityMetrics:
        """
        Calculate finality metrics.

        Returns:
            SettlementFinalityMetrics
        """
        if not self.finality_times:
            return SettlementFinalityMetrics(
                total_settlements=0,
                finalized_within_target=0,
                finality_rate=1.0,
                mean_finality_time_seconds=0,
                p95_finality_time_seconds=0,
                p99_finality_time_seconds=0,
                max_finality_time_seconds=0,
            )

        arr = np.array(self.finality_times)
        n = len(arr)

        within_target = np.sum(arr <= self.target_seconds)
        finality_rate = within_target / n

        return SettlementFinalityMetrics(
            total_settlements=n,
            finalized_within_target=int(within_target),
            finality_rate=float(finality_rate),
            mean_finality_time_seconds=float(np.mean(arr)),
            p95_finality_time_seconds=float(np.percentile(arr, 95)),
            p99_finality_time_seconds=float(np.percentile(arr, 99)),
            max_finality_time_seconds=float(np.max(arr)),
        )

    def check_sla(self, required_rate: float = 0.999) -> Tuple[bool, float]:
        """
        Check if finality SLA is met.

        Args:
            required_rate: Required fraction within target time

        Returns:
            Tuple of (meets_sla, actual_rate)
        """
        if not self.finality_times:
            return (True, 1.0)

        arr = np.array(self.finality_times)
        actual_rate = np.mean(arr <= self.target_seconds)

        return (actual_rate >= required_rate, float(actual_rate))

    def clear(self):
        """Clear all finality data."""
        self.finality_times = []
        self._pending = {}


def simulate_availability_data(
    duration_hours: int,
    target_availability: float = 0.999,
    mtbf_hours: float = 720.0,
    mttr_minutes: float = 15.0,
    seed: Optional[int] = None,
) -> Tuple[AvailabilityMonitor, List[DowntimeEvent]]:
    """
    Simulate availability data.

    Args:
        duration_hours: Monitoring duration in hours
        target_availability: Target availability
        mtbf_hours: Mean time between failures
        mttr_minutes: Mean time to recovery
        seed: Random seed

    Returns:
        Tuple of (monitor with data, list of events)
    """
    rng = np.random.default_rng(seed)

    monitor = AvailabilityMonitor()
    start_time = time.time() - duration_hours * 3600
    monitor.monitoring_start = start_time
    monitor.monitoring_end = time.time()

    events = []

    # Generate failures using Poisson process
    current_time = start_time
    while current_time < monitor.monitoring_end:
        # Time to next failure
        time_to_failure = rng.exponential(mtbf_hours * 3600)
        failure_start = current_time + time_to_failure

        if failure_start >= monitor.monitoring_end:
            break

        # Failure duration
        failure_duration = max(60, rng.exponential(mttr_minutes * 60))
        failure_end = min(failure_start + failure_duration, monitor.monitoring_end)

        event = DowntimeEvent(
            start_time=failure_start,
            end_time=failure_end,
            duration_seconds=failure_end - failure_start,
            state=SystemState.DOWN,
            reason="simulated_failure",
            impact=rng.integers(3, 8),
        )

        events.append(event)
        monitor.add_downtime_event(event)

        current_time = failure_end

    return monitor, events


def simulate_settlement_finality(
    n_settlements: int,
    target_seconds: float = 30.0,
    success_rate: float = 0.999,
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, SettlementFinalityMetrics]:
    """
    Simulate settlement finality times.

    Args:
        n_settlements: Number of settlements
        target_seconds: Target finality time
        success_rate: Fraction that should meet target
        seed: Random seed

    Returns:
        Tuple of (finality times array, metrics)
    """
    rng = np.random.default_rng(seed)

    # Most settlements are fast (exponential distribution)
    base_times = rng.exponential(target_seconds / 3, n_settlements)

    # Some are slow
    slow_fraction = 1 - success_rate
    n_slow = int(n_settlements * slow_fraction * 1.5)

    if n_slow > 0:
        slow_indices = rng.choice(n_settlements, min(n_slow, n_settlements), replace=False)
        base_times[slow_indices] = rng.uniform(
            target_seconds * 0.8,
            target_seconds * 2.0,
            len(slow_indices),
        )

    tracker = SettlementFinalityTracker(target_seconds=target_seconds)
    tracker.record_batch(base_times.tolist())

    return base_times, tracker.calculate_metrics()
