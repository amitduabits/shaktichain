"""
Peg Stability Tester for SHAKTI-CHAIN Token Economics (Domain 4).

Tests the 1:1 token-to-kWh redemption rate stability.
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
class RedemptionEvent:
    """
    A token redemption event.

    Attributes:
        timestamp: Unix timestamp
        tokens_burned: Amount of tokens burned
        kwh_delivered: Amount of kWh delivered
        exchange_rate: kwh_delivered / tokens_burned
        agent_id: Agent performing redemption
        redemption_type: Type of redemption ('standard', 'bulk', 'emergency')
    """
    timestamp: float
    tokens_burned: float
    kwh_delivered: float
    exchange_rate: float
    agent_id: str = ""
    redemption_type: str = "standard"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tokens_burned": float(self.tokens_burned),
            "kwh_delivered": float(self.kwh_delivered),
            "exchange_rate": float(self.exchange_rate),
            "agent_id": self.agent_id,
            "redemption_type": self.redemption_type,
        }

    @property
    def datetime(self) -> datetime:
        """Get datetime from timestamp."""
        return datetime.fromtimestamp(self.timestamp)

    @property
    def deviation_from_target(self) -> float:
        """Calculate deviation from 1:1 peg."""
        return abs(self.exchange_rate - 1.0)


@dataclass
class PegTestResult:
    """
    Result of peg stability test.

    Attributes:
        is_stable: Whether peg is within tolerance
        mean_rate: Mean exchange rate
        std_rate: Standard deviation of rate
        deviation_from_target: |mean_rate - 1.0|
        t_statistic: T-test statistic
        p_value: P-value
        ci_lower: Lower confidence interval
        ci_upper: Upper confidence interval
        target_rate: Target exchange rate
        tolerance: Tolerance used
        sample_size: Number of redemptions
    """
    is_stable: bool
    mean_rate: float
    std_rate: float
    deviation_from_target: float
    t_statistic: float
    p_value: float
    ci_lower: float
    ci_upper: float
    target_rate: float
    tolerance: float
    sample_size: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_stable": self.is_stable,
            "mean_rate": float(self.mean_rate),
            "std_rate": float(self.std_rate),
            "deviation_from_target": float(self.deviation_from_target),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "ci_lower": float(self.ci_lower),
            "ci_upper": float(self.ci_upper),
            "target_rate": float(self.target_rate),
            "tolerance": float(self.tolerance),
            "sample_size": self.sample_size,
        }


@dataclass
class PegStatistics:
    """
    Aggregate peg statistics.

    Attributes:
        mean_rate: Mean exchange rate
        std_rate: Standard deviation
        min_rate: Minimum rate
        max_rate: Maximum rate
        median_rate: Median rate
        num_redemptions: Total redemptions
        total_tokens_redeemed: Total tokens redeemed
        total_kwh_delivered: Total kWh delivered
        peg_breaks: Number of redemptions outside tolerance
    """
    mean_rate: float
    std_rate: float
    min_rate: float
    max_rate: float
    median_rate: float
    num_redemptions: int
    total_tokens_redeemed: float
    total_kwh_delivered: float
    peg_breaks: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean_rate": float(self.mean_rate),
            "std_rate": float(self.std_rate),
            "min_rate": float(self.min_rate),
            "max_rate": float(self.max_rate),
            "median_rate": float(self.median_rate),
            "num_redemptions": self.num_redemptions,
            "total_tokens_redeemed": float(self.total_tokens_redeemed),
            "total_kwh_delivered": float(self.total_kwh_delivered),
            "peg_breaks": self.peg_breaks,
        }


class PegStabilityTester:
    """
    Test token-to-kWh peg stability.

    Tests hypothesis H4.4: Redemption rate = 1.0 +/- 1%
    """

    def __init__(self, target_rate: float = 1.0):
        """
        Initialize peg stability tester.

        Args:
            target_rate: Target exchange rate (default 1.0 for 1:1 peg)
        """
        self.target_rate = target_rate
        self.redemptions: List[RedemptionEvent] = []

    def record_redemption(
        self,
        timestamp: float,
        tokens_burned: float,
        kwh_delivered: float,
        agent_id: str = "",
        redemption_type: str = "standard",
    ):
        """
        Record a redemption event.

        Args:
            timestamp: Unix timestamp
            tokens_burned: Tokens burned
            kwh_delivered: kWh delivered
            agent_id: Agent ID
            redemption_type: Type of redemption
        """
        if tokens_burned <= 0:
            logger.warning("Invalid redemption: tokens_burned must be positive")
            return

        exchange_rate = kwh_delivered / tokens_burned

        event = RedemptionEvent(
            timestamp=timestamp,
            tokens_burned=tokens_burned,
            kwh_delivered=kwh_delivered,
            exchange_rate=exchange_rate,
            agent_id=agent_id,
            redemption_type=redemption_type,
        )
        self.redemptions.append(event)

    def add_redemption(self, event: RedemptionEvent):
        """Add a redemption event."""
        self.redemptions.append(event)

    def test_peg_accuracy(
        self,
        tolerance: float = 0.01,
        alpha: float = 0.05,
    ) -> PegTestResult:
        """
        Test if mean redemption rate = target +/- tolerance.

        Tests H4.4: Redemption rate = 1.0 +/- 1%

        Uses one-sample t-test with equivalence margin.

        Args:
            tolerance: Maximum allowed deviation (default 1%)
            alpha: Significance level

        Returns:
            PegTestResult
        """
        if len(self.redemptions) < 2:
            return PegTestResult(
                is_stable=True,
                mean_rate=self.target_rate,
                std_rate=0,
                deviation_from_target=0,
                t_statistic=0,
                p_value=1.0,
                ci_lower=self.target_rate,
                ci_upper=self.target_rate,
                target_rate=self.target_rate,
                tolerance=tolerance,
                sample_size=len(self.redemptions),
            )

        rates = np.array([r.exchange_rate for r in self.redemptions])
        n = len(rates)

        mean_rate = float(np.mean(rates))
        std_rate = float(np.std(rates, ddof=1))
        deviation = abs(mean_rate - self.target_rate)

        # One-sample t-test against target rate
        t_stat, p_value = scipy_stats.ttest_1samp(rates, self.target_rate)

        # Confidence interval
        se = std_rate / np.sqrt(n)
        t_crit = scipy_stats.t.ppf(1 - alpha / 2, n - 1)
        ci_lower = mean_rate - t_crit * se
        ci_upper = mean_rate + t_crit * se

        # Peg is stable if:
        # 1. Mean deviation from target < tolerance
        # 2. Confidence interval is within tolerance bounds
        ci_within_bounds = (
            ci_lower >= self.target_rate - tolerance and
            ci_upper <= self.target_rate + tolerance
        )
        is_stable = deviation < tolerance and ci_within_bounds

        return PegTestResult(
            is_stable=is_stable,
            mean_rate=mean_rate,
            std_rate=std_rate,
            deviation_from_target=deviation,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            target_rate=self.target_rate,
            tolerance=tolerance,
            sample_size=n,
        )

    def test_equivalence(
        self,
        tolerance: float = 0.01,
        alpha: float = 0.05,
    ) -> PegTestResult:
        """
        Test peg using two one-sided t-tests (TOST) for equivalence.

        More rigorous test that requires the rate to be within
        [target - tolerance, target + tolerance].

        Args:
            tolerance: Equivalence margin
            alpha: Significance level

        Returns:
            PegTestResult
        """
        if len(self.redemptions) < 2:
            return PegTestResult(
                is_stable=True,
                mean_rate=self.target_rate,
                std_rate=0,
                deviation_from_target=0,
                t_statistic=0,
                p_value=1.0,
                ci_lower=self.target_rate,
                ci_upper=self.target_rate,
                target_rate=self.target_rate,
                tolerance=tolerance,
                sample_size=len(self.redemptions),
            )

        rates = np.array([r.exchange_rate for r in self.redemptions])
        n = len(rates)

        mean_rate = float(np.mean(rates))
        std_rate = float(np.std(rates, ddof=1))
        se = std_rate / np.sqrt(n)

        # Lower bound test: H0: mu <= target - tolerance
        t_lower = (mean_rate - (self.target_rate - tolerance)) / se
        p_lower = 1 - scipy_stats.t.cdf(t_lower, n - 1)

        # Upper bound test: H0: mu >= target + tolerance
        t_upper = (mean_rate - (self.target_rate + tolerance)) / se
        p_upper = scipy_stats.t.cdf(t_upper, n - 1)

        # TOST p-value is the maximum of the two
        p_value = max(p_lower, p_upper)

        # Equivalence is established if p_value < alpha
        is_stable = p_value < alpha

        # Confidence interval
        t_crit = scipy_stats.t.ppf(1 - alpha / 2, n - 1)
        ci_lower = mean_rate - t_crit * se
        ci_upper = mean_rate + t_crit * se

        deviation = abs(mean_rate - self.target_rate)

        return PegTestResult(
            is_stable=is_stable,
            mean_rate=mean_rate,
            std_rate=std_rate,
            deviation_from_target=deviation,
            t_statistic=float((t_lower + t_upper) / 2),  # Combined statistic
            p_value=float(p_value),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            target_rate=self.target_rate,
            tolerance=tolerance,
            sample_size=n,
        )

    def detect_peg_breaks(
        self,
        deviation_threshold: float = 0.05,
    ) -> List[RedemptionEvent]:
        """
        Identify redemptions where rate deviated significantly.

        Args:
            deviation_threshold: Maximum allowed deviation

        Returns:
            List of RedemptionEvents that broke the peg
        """
        peg_breaks = []

        for redemption in self.redemptions:
            if redemption.deviation_from_target > deviation_threshold:
                peg_breaks.append(redemption)

        return peg_breaks

    def analyze_by_type(self) -> Dict[str, PegTestResult]:
        """
        Analyze peg stability by redemption type.

        Returns:
            Dictionary of redemption_type -> PegTestResult
        """
        by_type: Dict[str, List[RedemptionEvent]] = {}

        for redemption in self.redemptions:
            if redemption.redemption_type not in by_type:
                by_type[redemption.redemption_type] = []
            by_type[redemption.redemption_type].append(redemption)

        results = {}
        for rtype, redemptions in by_type.items():
            # Create temporary tester for this type
            tester = PegStabilityTester(self.target_rate)
            tester.redemptions = redemptions
            results[rtype] = tester.test_peg_accuracy()

        return results

    def get_statistics(
        self,
        tolerance: float = 0.01,
    ) -> PegStatistics:
        """
        Get aggregate peg statistics.

        Args:
            tolerance: Tolerance for peg break counting

        Returns:
            PegStatistics
        """
        if not self.redemptions:
            return PegStatistics(
                mean_rate=self.target_rate,
                std_rate=0,
                min_rate=self.target_rate,
                max_rate=self.target_rate,
                median_rate=self.target_rate,
                num_redemptions=0,
                total_tokens_redeemed=0,
                total_kwh_delivered=0,
                peg_breaks=0,
            )

        rates = np.array([r.exchange_rate for r in self.redemptions])
        peg_breaks = len(self.detect_peg_breaks(tolerance))

        return PegStatistics(
            mean_rate=float(np.mean(rates)),
            std_rate=float(np.std(rates)),
            min_rate=float(np.min(rates)),
            max_rate=float(np.max(rates)),
            median_rate=float(np.median(rates)),
            num_redemptions=len(self.redemptions),
            total_tokens_redeemed=sum(r.tokens_burned for r in self.redemptions),
            total_kwh_delivered=sum(r.kwh_delivered for r in self.redemptions),
            peg_breaks=peg_breaks,
        )

    def get_rate_series(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get time series of exchange rates.

        Returns:
            Tuple of (timestamps, rates)
        """
        timestamps = np.array([r.timestamp for r in self.redemptions])
        rates = np.array([r.exchange_rate for r in self.redemptions])

        # Sort by timestamp
        sort_idx = np.argsort(timestamps)
        return timestamps[sort_idx], rates[sort_idx]

    def clear(self):
        """Clear all redemptions."""
        self.redemptions = []


def simulate_redemptions(
    num_redemptions: int = 1000,
    duration_days: int = 30,
    target_rate: float = 1.0,
    rate_std: float = 0.005,
    mean_redemption_size: float = 100.0,
    num_agents: int = 50,
    seed: Optional[int] = None,
) -> PegStabilityTester:
    """
    Simulate redemption events.

    Args:
        num_redemptions: Number of redemptions
        duration_days: Duration to simulate
        target_rate: Target exchange rate
        rate_std: Standard deviation of rate noise
        mean_redemption_size: Mean tokens per redemption
        num_agents: Number of agents
        seed: Random seed

    Returns:
        PegStabilityTester with simulated data
    """
    rng = np.random.default_rng(seed)

    tester = PegStabilityTester(target_rate=target_rate)
    start_time = datetime.now().timestamp()

    agent_ids = [f"agent_{i}" for i in range(num_agents)]
    redemption_types = ["standard", "bulk", "emergency"]
    type_probs = [0.8, 0.15, 0.05]

    for _ in range(num_redemptions):
        # Random timestamp
        timestamp = start_time + rng.uniform(0, duration_days * 24 * 3600)

        # Random redemption size (log-normal)
        tokens_burned = rng.lognormal(
            np.log(mean_redemption_size),
            0.5
        )

        # Exchange rate with noise around target
        exchange_rate = rng.normal(target_rate, rate_std)
        exchange_rate = max(0.9, min(1.1, exchange_rate))  # Clamp to reasonable range

        kwh_delivered = tokens_burned * exchange_rate

        # Random agent and type
        agent_id = rng.choice(agent_ids)
        redemption_type = rng.choice(redemption_types, p=type_probs)

        tester.record_redemption(
            timestamp=timestamp,
            tokens_burned=tokens_burned,
            kwh_delivered=kwh_delivered,
            agent_id=agent_id,
            redemption_type=redemption_type,
        )

    return tester


def simulate_peg_scenarios(
    num_redemptions: int = 500,
    duration_days: int = 30,
    seed: Optional[int] = None,
) -> Dict[str, PegStabilityTester]:
    """
    Simulate multiple peg stability scenarios.

    Args:
        num_redemptions: Redemptions per scenario
        duration_days: Duration to simulate
        seed: Random seed

    Returns:
        Dictionary of scenario name -> PegStabilityTester
    """
    scenarios = {}

    # Stable peg: low variance
    scenarios["stable"] = simulate_redemptions(
        num_redemptions=num_redemptions,
        duration_days=duration_days,
        rate_std=0.003,  # 0.3% standard deviation
        seed=seed,
    )

    # Moderate variance
    scenarios["moderate"] = simulate_redemptions(
        num_redemptions=num_redemptions,
        duration_days=duration_days,
        rate_std=0.008,  # 0.8% standard deviation
        seed=seed + 1 if seed else None,
    )

    # Unstable peg: high variance
    scenarios["unstable"] = simulate_redemptions(
        num_redemptions=num_redemptions,
        duration_days=duration_days,
        rate_std=0.02,  # 2% standard deviation
        seed=seed + 2 if seed else None,
    )

    # Biased peg: systematic deviation
    # Simulate by manually adjusting rates
    biased = simulate_redemptions(
        num_redemptions=num_redemptions,
        duration_days=duration_days,
        target_rate=1.02,  # Biased high
        rate_std=0.005,
        seed=seed + 3 if seed else None,
    )
    biased.target_rate = 1.0  # But target is still 1.0
    scenarios["biased"] = biased

    return scenarios


def simulate_stress_redemptions(
    total_supply: float = 1_000_000.0,
    redemption_fraction: float = 0.20,
    duration_hours: float = 1.0,
    target_rate: float = 1.0,
    stress_rate_deviation: float = 0.02,
    seed: Optional[int] = None,
) -> PegStabilityTester:
    """
    Simulate coordinated redemption stress test.

    Models a scenario where a large fraction of supply is
    redeemed in a short time.

    Args:
        total_supply: Total token supply
        redemption_fraction: Fraction to redeem
        duration_hours: Duration of redemption event
        target_rate: Target exchange rate
        stress_rate_deviation: Rate deviation under stress
        seed: Random seed

    Returns:
        PegStabilityTester with stress test data
    """
    rng = np.random.default_rng(seed)

    tester = PegStabilityTester(target_rate=target_rate)
    start_time = datetime.now().timestamp()

    total_to_redeem = total_supply * redemption_fraction
    num_redemptions = 100  # Concentrated redemptions

    for i in range(num_redemptions):
        # Timestamps concentrated in duration
        timestamp = start_time + rng.uniform(0, duration_hours * 3600)

        # Redemption sizes (some very large)
        tokens_burned = total_to_redeem / num_redemptions * rng.uniform(0.5, 1.5)

        # Under stress, rate may deviate more
        time_factor = (timestamp - start_time) / (duration_hours * 3600)
        rate_deviation = stress_rate_deviation * time_factor  # Worse as stress continues
        exchange_rate = rng.normal(target_rate, rate_deviation)

        kwh_delivered = tokens_burned * exchange_rate

        tester.record_redemption(
            timestamp=timestamp,
            tokens_burned=tokens_burned,
            kwh_delivered=kwh_delivered,
            agent_id=f"stress_agent_{i % 10}",
            redemption_type="emergency",
        )

    return tester
