"""
Load Generator for SHAKTI-CHAIN System Performance Testing (Domain 3).

Generates synthetic transaction load for stress testing and performance validation.
Uses Poisson arrival process for realistic load patterns.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Callable, Dict, List, Optional, Tuple

import numpy as np


class TransactionType(Enum):
    """Types of transactions in V2G marketplace."""
    BID_SUBMIT = "bid_submit"
    ASK_SUBMIT = "ask_submit"
    ORDER_CANCEL = "order_cancel"
    TRADE_SETTLEMENT = "trade_settlement"
    BALANCE_QUERY = "balance_query"
    MARKET_DATA = "market_data"


@dataclass
class Transaction:
    """
    Represents a synthetic transaction for load testing.

    Attributes:
        tx_id: Unique transaction identifier
        tx_type: Type of transaction
        user_id: ID of the user/agent submitting
        timestamp: Creation timestamp
        payload_size: Size of transaction payload in bytes
        priority: Transaction priority (1-10)
        data: Additional transaction data
    """
    tx_id: str
    tx_type: TransactionType
    user_id: str
    timestamp: float
    payload_size: int
    priority: int = 5
    data: Dict = field(default_factory=dict)

    @classmethod
    def create_random(cls, user_id: str) -> "Transaction":
        """Create a random transaction."""
        tx_type = random.choice(list(TransactionType))

        # Payload size varies by transaction type
        size_ranges = {
            TransactionType.BID_SUBMIT: (200, 500),
            TransactionType.ASK_SUBMIT: (200, 500),
            TransactionType.ORDER_CANCEL: (100, 200),
            TransactionType.TRADE_SETTLEMENT: (500, 1500),
            TransactionType.BALANCE_QUERY: (50, 100),
            TransactionType.MARKET_DATA: (100, 300),
        }
        size_range = size_ranges[tx_type]
        payload_size = random.randint(*size_range)

        return cls(
            tx_id=str(uuid.uuid4()),
            tx_type=tx_type,
            user_id=user_id,
            timestamp=time.time(),
            payload_size=payload_size,
            priority=random.randint(1, 10),
            data={
                "price": random.uniform(5.0, 15.0),
                "quantity": random.uniform(1.0, 100.0),
            }
        )


@dataclass
class LoadProfile:
    """
    Load profile configuration.

    Attributes:
        target_tps: Target transactions per second
        concurrent_users: Number of concurrent users
        duration_seconds: Duration of load test
        ramp_up_seconds: Time to ramp up to target load
        ramp_down_seconds: Time to ramp down
        tx_type_distribution: Distribution of transaction types
    """
    target_tps: int
    concurrent_users: int
    duration_seconds: int
    ramp_up_seconds: int = 10
    ramp_down_seconds: int = 5
    tx_type_distribution: Dict[TransactionType, float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tx_type_distribution:
            # Default distribution
            self.tx_type_distribution = {
                TransactionType.BID_SUBMIT: 0.30,
                TransactionType.ASK_SUBMIT: 0.30,
                TransactionType.ORDER_CANCEL: 0.10,
                TransactionType.TRADE_SETTLEMENT: 0.15,
                TransactionType.BALANCE_QUERY: 0.10,
                TransactionType.MARKET_DATA: 0.05,
            }


@dataclass
class LoadGeneratorStats:
    """Statistics from load generation."""
    total_transactions: int
    actual_tps_mean: float
    actual_tps_std: float
    actual_tps_min: float
    actual_tps_max: float
    duration_actual: float
    transactions_by_type: Dict[str, int]
    errors: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_transactions": self.total_transactions,
            "actual_tps_mean": float(self.actual_tps_mean),
            "actual_tps_std": float(self.actual_tps_std),
            "actual_tps_min": float(self.actual_tps_min),
            "actual_tps_max": float(self.actual_tps_max),
            "duration_actual": float(self.duration_actual),
            "transactions_by_type": self.transactions_by_type,
            "errors": self.errors,
        }


class LoadGenerator:
    """
    Generate synthetic transaction load for performance testing.

    Uses Poisson arrival process for realistic inter-arrival times.
    Supports ramping, sustained load, and stress testing patterns.
    """

    def __init__(
        self,
        target_tps: int,
        seed: Optional[int] = None,
    ):
        """
        Initialize load generator.

        Args:
            target_tps: Target transactions per second
            seed: Random seed for reproducibility
        """
        self.target_tps = target_tps
        self.seed = seed
        self._rng = np.random.default_rng(seed)
        self._running = False
        self._generated_count = 0
        self._error_count = 0
        self._tps_samples: List[float] = []

    def _poisson_interarrival_time(self, rate: float) -> float:
        """
        Generate inter-arrival time using Poisson process.

        For a Poisson process with rate lambda, inter-arrival times
        follow an exponential distribution with rate lambda.

        Args:
            rate: Average number of arrivals per second

        Returns:
            Time until next arrival in seconds
        """
        if rate <= 0:
            return float('inf')
        return self._rng.exponential(1.0 / rate)

    def _select_transaction_type(
        self,
        distribution: Dict[TransactionType, float],
    ) -> TransactionType:
        """Select transaction type based on distribution."""
        types = list(distribution.keys())
        probs = list(distribution.values())
        return self._rng.choice(types, p=probs)

    async def generate_load(
        self,
        duration_seconds: int,
        concurrent_users: int,
        tx_callback: Optional[Callable[[Transaction], None]] = None,
    ) -> AsyncGenerator[Transaction, None]:
        """
        Generate transactions at target TPS using Poisson arrival process.

        Args:
            duration_seconds: Duration to generate load
            concurrent_users: Number of simulated concurrent users
            tx_callback: Optional callback for each generated transaction

        Yields:
            Transaction objects at Poisson-distributed intervals
        """
        self._running = True
        self._generated_count = 0
        self._tps_samples = []

        start_time = time.time()
        end_time = start_time + duration_seconds

        # Track TPS per second
        second_start = start_time
        second_count = 0

        # Create user pool
        users = [f"user_{i}" for i in range(concurrent_users)]

        try:
            while time.time() < end_time and self._running:
                current_time = time.time()

                # Track per-second TPS
                if current_time - second_start >= 1.0:
                    self._tps_samples.append(second_count)
                    second_start = current_time
                    second_count = 0

                # Generate transaction
                user_id = random.choice(users)
                tx = Transaction.create_random(user_id)

                self._generated_count += 1
                second_count += 1

                if tx_callback:
                    try:
                        tx_callback(tx)
                    except Exception:
                        self._error_count += 1

                yield tx

                # Calculate sleep time using Poisson process
                sleep_time = self._poisson_interarrival_time(self.target_tps)

                # Ensure we don't sleep too long
                remaining = end_time - time.time()
                if remaining > 0:
                    await asyncio.sleep(min(sleep_time, remaining))

        finally:
            self._running = False

    async def generate_load_sync(
        self,
        duration_seconds: int,
        concurrent_users: int,
    ) -> Tuple[List[Transaction], LoadGeneratorStats]:
        """
        Generate load and collect all transactions.

        Non-streaming version for simpler usage.

        Args:
            duration_seconds: Duration to generate load
            concurrent_users: Number of concurrent users

        Returns:
            Tuple of (list of transactions, statistics)
        """
        transactions: List[Transaction] = []
        start_time = time.time()

        async for tx in self.generate_load(duration_seconds, concurrent_users):
            transactions.append(tx)

        duration_actual = time.time() - start_time

        # Count by type
        tx_by_type: Dict[str, int] = {}
        for tx in transactions:
            tx_type = tx.tx_type.value
            tx_by_type[tx_type] = tx_by_type.get(tx_type, 0) + 1

        # Calculate statistics
        tps_arr = np.array(self._tps_samples) if self._tps_samples else np.array([0])

        stats = LoadGeneratorStats(
            total_transactions=len(transactions),
            actual_tps_mean=float(np.mean(tps_arr)),
            actual_tps_std=float(np.std(tps_arr)),
            actual_tps_min=float(np.min(tps_arr)),
            actual_tps_max=float(np.max(tps_arr)),
            duration_actual=duration_actual,
            transactions_by_type=tx_by_type,
            errors=self._error_count,
        )

        return transactions, stats

    async def ramp_up_load(
        self,
        start_tps: int,
        end_tps: int,
        ramp_duration: int,
        concurrent_users: int,
    ) -> AsyncGenerator[Tuple[Transaction, int], None]:
        """
        Gradually increase load for stress testing.

        Args:
            start_tps: Starting TPS
            end_tps: Ending TPS
            ramp_duration: Duration of ramp in seconds
            concurrent_users: Number of concurrent users

        Yields:
            Tuple of (Transaction, current_target_tps)
        """
        self._running = True
        start_time = time.time()

        users = [f"user_{i}" for i in range(concurrent_users)]

        while time.time() - start_time < ramp_duration and self._running:
            elapsed = time.time() - start_time
            progress = elapsed / ramp_duration

            # Linear interpolation of TPS
            current_tps = start_tps + (end_tps - start_tps) * progress

            # Generate transaction
            user_id = random.choice(users)
            tx = Transaction.create_random(user_id)

            yield tx, int(current_tps)

            # Sleep based on current TPS
            sleep_time = self._poisson_interarrival_time(current_tps)
            await asyncio.sleep(sleep_time)

        self._running = False

    async def burst_load(
        self,
        burst_tps: int,
        burst_duration: float,
        concurrent_users: int,
    ) -> List[Transaction]:
        """
        Generate a short burst of high load.

        Useful for testing system behavior under sudden load spikes.

        Args:
            burst_tps: TPS during burst
            burst_duration: Duration of burst in seconds
            concurrent_users: Number of concurrent users

        Returns:
            List of generated transactions
        """
        original_tps = self.target_tps
        self.target_tps = burst_tps

        transactions, _ = await self.generate_load_sync(
            int(burst_duration),
            concurrent_users,
        )

        self.target_tps = original_tps
        return transactions

    def stop(self):
        """Stop load generation."""
        self._running = False

    def get_stats(self) -> Dict:
        """Get current generation statistics."""
        tps_arr = np.array(self._tps_samples) if self._tps_samples else np.array([0])
        return {
            "generated_count": self._generated_count,
            "error_count": self._error_count,
            "mean_tps": float(np.mean(tps_arr)),
            "current_tps_samples": len(self._tps_samples),
        }


class SyntheticLoadGenerator:
    """
    Generate synthetic load without actual network calls.

    For simulation-based testing where we model system behavior
    rather than testing actual infrastructure.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
    ):
        """
        Initialize synthetic load generator.

        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed
        self._rng = np.random.default_rng(seed)

    def generate_tps_samples(
        self,
        target_tps: int,
        duration_seconds: int,
        noise_factor: float = 0.1,
    ) -> np.ndarray:
        """
        Generate synthetic TPS measurements.

        Models TPS as target with Gaussian noise and occasional drops.

        Args:
            target_tps: Target TPS
            duration_seconds: Number of seconds to simulate
            noise_factor: Standard deviation as fraction of target

        Returns:
            Array of TPS values, one per second
        """
        n_samples = duration_seconds

        # Base TPS with Gaussian noise
        noise_std = target_tps * noise_factor
        tps = self._rng.normal(target_tps, noise_std, n_samples)

        # Occasional performance dips (simulate GC pauses, etc.)
        dip_probability = 0.02
        dip_mask = self._rng.random(n_samples) < dip_probability
        dip_factor = self._rng.uniform(0.5, 0.8, n_samples)
        tps[dip_mask] *= dip_factor[dip_mask]

        # Ensure non-negative
        tps = np.maximum(tps, 0)

        return tps

    def generate_latency_samples(
        self,
        n_samples: int,
        base_latency_ms: float = 10.0,
        p99_target_ms: float = 100.0,
    ) -> np.ndarray:
        """
        Generate synthetic latency measurements.

        Models latency as log-normal distribution (common for response times).

        Args:
            n_samples: Number of latency samples to generate
            base_latency_ms: Base/median latency
            p99_target_ms: Target 99th percentile latency

        Returns:
            Array of latency values in milliseconds
        """
        # Log-normal parameters
        # median = exp(mu), so mu = ln(median)
        mu = np.log(base_latency_ms)

        # For log-normal, p99 = exp(mu + 2.326*sigma)
        # So sigma = (ln(p99) - mu) / 2.326
        sigma = (np.log(p99_target_ms) - mu) / 2.326
        sigma = max(sigma, 0.1)  # Ensure positive

        latencies = self._rng.lognormal(mu, sigma, n_samples)

        return latencies

    def generate_settlement_times(
        self,
        n_samples: int,
        target_seconds: float = 30.0,
        success_rate: float = 0.999,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate synthetic settlement finality times.

        Args:
            n_samples: Number of samples
            target_seconds: Target finality time
            success_rate: Fraction settling within target

        Returns:
            Tuple of (settlement_times, within_target_mask)
        """
        # Most settle quickly (exponential distribution)
        base_times = self._rng.exponential(target_seconds / 3, n_samples)

        # Small fraction take longer
        slow_fraction = 1 - success_rate
        n_slow = int(n_samples * slow_fraction * 2)  # Some buffer

        if n_slow > 0:
            slow_indices = self._rng.choice(n_samples, min(n_slow, n_samples), replace=False)
            base_times[slow_indices] = self._rng.uniform(
                target_seconds * 0.8,
                target_seconds * 2.0,
                len(slow_indices),
            )

        within_target = base_times <= target_seconds

        return base_times, within_target

    def generate_scalability_data(
        self,
        agent_counts: List[int],
        complexity: str = "nlogn",
        noise_factor: float = 0.1,
    ) -> List[Tuple[int, float]]:
        """
        Generate synthetic scalability measurements.

        Args:
            agent_counts: List of agent counts to simulate
            complexity: "linear", "nlogn", or "quadratic"
            noise_factor: Noise level

        Returns:
            List of (n_agents, time_ms) tuples
        """
        measurements = []
        base_time = 0.1  # Base time per operation in ms

        for n in agent_counts:
            if complexity == "linear":
                time_ms = base_time * n
            elif complexity == "nlogn":
                time_ms = base_time * n * np.log(max(n, 2))
            elif complexity == "quadratic":
                time_ms = base_time * n * n / 1000  # Scale down quadratic
            else:
                raise ValueError(f"Unknown complexity: {complexity}")

            # Add noise
            noise = self._rng.normal(1, noise_factor)
            time_ms *= max(noise, 0.5)

            measurements.append((n, time_ms))

        return measurements

    def generate_gas_costs(
        self,
        n_transactions: int,
        base_gas: int = 65000,
        settlement_gas: int = 150000,
        settlement_fraction: float = 0.15,
        gas_price_gwei: float = 30.0,
        matic_inr_rate: float = 80.0,
    ) -> np.ndarray:
        """
        Generate synthetic gas cost samples.

        Args:
            n_transactions: Number of transactions
            base_gas: Base gas for simple transactions
            settlement_gas: Gas for settlement transactions
            settlement_fraction: Fraction that are settlements
            gas_price_gwei: Gas price in Gwei
            matic_inr_rate: MATIC/INR exchange rate

        Returns:
            Array of transaction costs in INR
        """
        # Determine which are settlements
        is_settlement = self._rng.random(n_transactions) < settlement_fraction

        # Gas used
        gas_used = np.where(
            is_settlement,
            self._rng.normal(settlement_gas, settlement_gas * 0.1, n_transactions),
            self._rng.normal(base_gas, base_gas * 0.1, n_transactions),
        )
        gas_used = np.maximum(gas_used, 21000)  # Minimum gas

        # Gas price variation
        gas_price_variation = self._rng.normal(gas_price_gwei, gas_price_gwei * 0.2, n_transactions)
        gas_price_variation = np.maximum(gas_price_variation, 1.0)

        # Cost in INR
        # Cost = gas_used * gas_price_gwei * MATIC_INR / 1e9
        costs_inr = gas_used * gas_price_variation * matic_inr_rate / 1e9

        return costs_inr

    def generate_availability_data(
        self,
        duration_hours: int,
        target_availability: float = 0.999,
        mtbf_hours: float = 720.0,  # Mean time between failures
        mttr_minutes: float = 15.0,  # Mean time to recovery
    ) -> Tuple[np.ndarray, List[Tuple[float, float]]]:
        """
        Generate synthetic availability/uptime data.

        Args:
            duration_hours: Total duration to simulate
            target_availability: Target availability (e.g., 0.999)
            mtbf_hours: Mean time between failures
            mttr_minutes: Mean time to recovery

        Returns:
            Tuple of (minute-by-minute uptime array, list of (start, duration) downtime events)
        """
        n_minutes = duration_hours * 60
        uptime = np.ones(n_minutes, dtype=bool)
        downtime_events = []

        # Generate failures using Poisson process
        current_minute = 0
        while current_minute < n_minutes:
            # Time to next failure (exponential distribution)
            time_to_failure = self._rng.exponential(mtbf_hours * 60)
            failure_start = current_minute + int(time_to_failure)

            if failure_start >= n_minutes:
                break

            # Duration of failure (exponential distribution)
            failure_duration = int(self._rng.exponential(mttr_minutes))
            failure_duration = max(1, failure_duration)  # At least 1 minute
            failure_end = min(failure_start + failure_duration, n_minutes)

            # Record downtime
            uptime[failure_start:failure_end] = False
            downtime_events.append((failure_start / 60, failure_duration))  # In hours and minutes

            current_minute = failure_end

        return uptime, downtime_events


def create_load_scenario(
    scenario_name: str,
    seed: Optional[int] = None,
) -> LoadProfile:
    """
    Create predefined load scenarios.

    Args:
        scenario_name: One of "light", "normal", "heavy", "stress", "burst"
        seed: Random seed

    Returns:
        LoadProfile configuration
    """
    scenarios = {
        "light": LoadProfile(
            target_tps=100,
            concurrent_users=10,
            duration_seconds=60,
            ramp_up_seconds=5,
        ),
        "normal": LoadProfile(
            target_tps=1000,
            concurrent_users=100,
            duration_seconds=300,
            ramp_up_seconds=30,
        ),
        "heavy": LoadProfile(
            target_tps=5000,
            concurrent_users=500,
            duration_seconds=300,
            ramp_up_seconds=60,
        ),
        "stress": LoadProfile(
            target_tps=10000,
            concurrent_users=1000,
            duration_seconds=600,
            ramp_up_seconds=120,
        ),
        "extreme": LoadProfile(
            target_tps=20000,
            concurrent_users=2000,
            duration_seconds=300,
            ramp_up_seconds=60,
        ),
    }

    if scenario_name not in scenarios:
        raise ValueError(f"Unknown scenario: {scenario_name}. Choose from {list(scenarios.keys())}")

    return scenarios[scenario_name]
