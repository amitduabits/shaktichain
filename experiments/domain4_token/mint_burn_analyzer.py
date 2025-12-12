"""
Mint-Burn Analyzer for SHAKTI-CHAIN Token Economics (Domain 4).

Analyzes token minting and burning dynamics to test equilibrium hypothesis.
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
class MintBurnEvent:
    """
    A token mint or burn event.

    Attributes:
        timestamp: Unix timestamp of event
        event_type: 'mint' or 'burn'
        amount: Token amount
        trigger: Reason for event ('energy_sale', 'redemption', etc.)
        agent_id: ID of agent involved
        kwh_equivalent: Energy equivalent if applicable
    """
    timestamp: float
    event_type: str  # 'mint' or 'burn'
    amount: float
    trigger: str
    agent_id: str
    kwh_equivalent: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "amount": float(self.amount),
            "trigger": self.trigger,
            "agent_id": self.agent_id,
            "kwh_equivalent": float(self.kwh_equivalent),
        }

    @property
    def datetime(self) -> datetime:
        """Get datetime from timestamp."""
        return datetime.fromtimestamp(self.timestamp)

    @property
    def is_mint(self) -> bool:
        """Check if this is a mint event."""
        return self.event_type == "mint"

    @property
    def is_burn(self) -> bool:
        """Check if this is a burn event."""
        return self.event_type == "burn"


@dataclass
class DailyMintBurnStats:
    """
    Daily aggregated mint/burn statistics.

    Attributes:
        date: Date string (YYYY-MM-DD)
        mint_volume: Total minted
        burn_volume: Total burned
        mint_count: Number of mint events
        burn_count: Number of burn events
        net_change: mint - burn
        mint_burn_ratio: mint / burn (inf if burn=0)
    """
    date: str
    mint_volume: float
    burn_volume: float
    mint_count: int
    burn_count: int
    net_change: float
    mint_burn_ratio: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "mint_volume": float(self.mint_volume),
            "burn_volume": float(self.burn_volume),
            "mint_count": self.mint_count,
            "burn_count": self.burn_count,
            "net_change": float(self.net_change),
            "mint_burn_ratio": float(self.mint_burn_ratio),
        }


@dataclass
class EquilibriumTestResult:
    """
    Result of mint-burn equilibrium test.

    Attributes:
        is_equilibrium: Whether mint and burn are in equilibrium
        mean_mint_rate: Mean daily mint volume
        mean_burn_rate: Mean daily burn volume
        rate_difference: |mint - burn| / avg
        t_statistic: Paired t-test statistic
        p_value: P-value from test
        ci_lower: Lower bound of CI for difference
        ci_upper: Upper bound of CI for difference
        tolerance: Tolerance threshold used
        sample_size: Number of days analyzed
    """
    is_equilibrium: bool
    mean_mint_rate: float
    mean_burn_rate: float
    rate_difference: float
    t_statistic: float
    p_value: float
    ci_lower: float
    ci_upper: float
    tolerance: float
    sample_size: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_equilibrium": self.is_equilibrium,
            "mean_mint_rate": float(self.mean_mint_rate),
            "mean_burn_rate": float(self.mean_burn_rate),
            "rate_difference": float(self.rate_difference),
            "t_statistic": float(self.t_statistic),
            "p_value": float(self.p_value),
            "ci_lower": float(self.ci_lower),
            "ci_upper": float(self.ci_upper),
            "tolerance": float(self.tolerance),
            "sample_size": self.sample_size,
        }


@dataclass
class MintBurnSummary:
    """
    Overall mint/burn activity summary.

    Attributes:
        total_minted: Total tokens minted
        total_burned: Total tokens burned
        net_supply_change: Total change in supply
        num_mint_events: Number of mint events
        num_burn_events: Number of burn events
        mean_mint_size: Average mint amount
        mean_burn_size: Average burn amount
        by_trigger: Breakdown by trigger type
        by_agent: Top agents by activity
    """
    total_minted: float
    total_burned: float
    net_supply_change: float
    num_mint_events: int
    num_burn_events: int
    mean_mint_size: float
    mean_burn_size: float
    by_trigger: Dict[str, Dict[str, float]]
    by_agent: Dict[str, Dict[str, float]]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_minted": float(self.total_minted),
            "total_burned": float(self.total_burned),
            "net_supply_change": float(self.net_supply_change),
            "num_mint_events": self.num_mint_events,
            "num_burn_events": self.num_burn_events,
            "mean_mint_size": float(self.mean_mint_size),
            "mean_burn_size": float(self.mean_burn_size),
            "by_trigger": self.by_trigger,
            "by_agent": self.by_agent,
        }


class MintBurnAnalyzer:
    """
    Analyze token minting and burning dynamics.

    Tests hypothesis H4.2: |Mint_rate - Burn_rate| / Avg_rate < 10%
    """

    def __init__(self):
        """Initialize mint/burn analyzer."""
        self.events: List[MintBurnEvent] = []

    def add_event(self, event: MintBurnEvent):
        """
        Add a mint or burn event.

        Args:
            event: MintBurnEvent to add
        """
        self.events.append(event)

    def record_mint(
        self,
        timestamp: float,
        amount: float,
        trigger: str = "energy_sale",
        agent_id: str = "",
        kwh_equivalent: float = 0.0,
    ):
        """
        Record a mint event.

        Args:
            timestamp: Unix timestamp
            amount: Tokens minted
            trigger: Reason for minting
            agent_id: Agent ID
            kwh_equivalent: kWh equivalent
        """
        event = MintBurnEvent(
            timestamp=timestamp,
            event_type="mint",
            amount=amount,
            trigger=trigger,
            agent_id=agent_id,
            kwh_equivalent=kwh_equivalent,
        )
        self.add_event(event)

    def record_burn(
        self,
        timestamp: float,
        amount: float,
        trigger: str = "redemption",
        agent_id: str = "",
        kwh_equivalent: float = 0.0,
    ):
        """
        Record a burn event.

        Args:
            timestamp: Unix timestamp
            amount: Tokens burned
            trigger: Reason for burning
            agent_id: Agent ID
            kwh_equivalent: kWh equivalent
        """
        event = MintBurnEvent(
            timestamp=timestamp,
            event_type="burn",
            amount=amount,
            trigger=trigger,
            agent_id=agent_id,
            kwh_equivalent=kwh_equivalent,
        )
        self.add_event(event)

    def get_events_by_type(self, event_type: str) -> List[MintBurnEvent]:
        """Get events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_in_range(
        self,
        start_timestamp: float,
        end_timestamp: float,
    ) -> List[MintBurnEvent]:
        """Get events within a time range."""
        return [
            e for e in self.events
            if start_timestamp <= e.timestamp <= end_timestamp
        ]

    def calculate_daily_rates(self) -> List[DailyMintBurnStats]:
        """
        Aggregate mint and burn by day.

        Returns:
            List of DailyMintBurnStats, one per day
        """
        if not self.events:
            return []

        # Group events by date
        by_date: Dict[str, Dict[str, list]] = {}

        for event in self.events:
            date_str = event.datetime.strftime("%Y-%m-%d")
            if date_str not in by_date:
                by_date[date_str] = {"mint": [], "burn": []}
            by_date[date_str][event.event_type].append(event.amount)

        # Calculate daily stats
        daily_stats = []
        for date_str in sorted(by_date.keys()):
            mint_amounts = by_date[date_str]["mint"]
            burn_amounts = by_date[date_str]["burn"]

            mint_volume = sum(mint_amounts)
            burn_volume = sum(burn_amounts)
            net_change = mint_volume - burn_volume

            # Calculate ratio (handle zero burn)
            if burn_volume > 0:
                mint_burn_ratio = mint_volume / burn_volume
            else:
                mint_burn_ratio = float('inf') if mint_volume > 0 else 1.0

            stats = DailyMintBurnStats(
                date=date_str,
                mint_volume=mint_volume,
                burn_volume=burn_volume,
                mint_count=len(mint_amounts),
                burn_count=len(burn_amounts),
                net_change=net_change,
                mint_burn_ratio=mint_burn_ratio,
            )
            daily_stats.append(stats)

        return daily_stats

    def test_equilibrium(
        self,
        tolerance: float = 0.1,
        alpha: float = 0.05,
    ) -> EquilibriumTestResult:
        """
        Test if mint and burn rates are balanced.

        Tests H4.2: |Mint_rate - Burn_rate| / Avg_rate < tolerance

        Uses paired t-test on daily (mint_rate - burn_rate).

        Args:
            tolerance: Maximum allowed relative difference (default 10%)
            alpha: Significance level

        Returns:
            EquilibriumTestResult
        """
        daily_stats = self.calculate_daily_rates()

        if len(daily_stats) < 2:
            return EquilibriumTestResult(
                is_equilibrium=True,
                mean_mint_rate=0,
                mean_burn_rate=0,
                rate_difference=0,
                t_statistic=0,
                p_value=1.0,
                ci_lower=0,
                ci_upper=0,
                tolerance=tolerance,
                sample_size=len(daily_stats),
            )

        mint_rates = np.array([s.mint_volume for s in daily_stats])
        burn_rates = np.array([s.burn_volume for s in daily_stats])

        mean_mint = float(np.mean(mint_rates))
        mean_burn = float(np.mean(burn_rates))
        avg_rate = (mean_mint + mean_burn) / 2

        # Calculate relative difference
        if avg_rate > 0:
            rate_difference = abs(mean_mint - mean_burn) / avg_rate
        else:
            rate_difference = 0.0

        # Paired t-test on differences
        differences = mint_rates - burn_rates
        n = len(differences)

        if n < 2 or np.std(differences) == 0:
            t_stat = 0.0
            p_value = 1.0
            ci_lower = float(np.mean(differences))
            ci_upper = float(np.mean(differences))
        else:
            # T-test: H0 is that mean difference = 0
            t_stat, p_value = scipy_stats.ttest_1samp(differences, 0)

            # Confidence interval for mean difference
            se = np.std(differences, ddof=1) / np.sqrt(n)
            t_crit = scipy_stats.t.ppf(1 - alpha / 2, n - 1)
            mean_diff = np.mean(differences)
            ci_lower = float(mean_diff - t_crit * se)
            ci_upper = float(mean_diff + t_crit * se)

        # Check if equilibrium: relative difference < tolerance
        is_equilibrium = rate_difference < tolerance

        return EquilibriumTestResult(
            is_equilibrium=is_equilibrium,
            mean_mint_rate=mean_mint,
            mean_burn_rate=mean_burn,
            rate_difference=rate_difference,
            t_statistic=float(t_stat),
            p_value=float(p_value),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            tolerance=tolerance,
            sample_size=n,
        )

    def calculate_summary(self) -> MintBurnSummary:
        """
        Calculate overall mint/burn summary statistics.

        Returns:
            MintBurnSummary
        """
        mint_events = self.get_events_by_type("mint")
        burn_events = self.get_events_by_type("burn")

        total_minted = sum(e.amount for e in mint_events)
        total_burned = sum(e.amount for e in burn_events)
        net_change = total_minted - total_burned

        mean_mint_size = total_minted / len(mint_events) if mint_events else 0
        mean_burn_size = total_burned / len(burn_events) if burn_events else 0

        # Breakdown by trigger
        by_trigger: Dict[str, Dict[str, float]] = {}
        for event in self.events:
            if event.trigger not in by_trigger:
                by_trigger[event.trigger] = {"mint": 0, "burn": 0, "count": 0}
            by_trigger[event.trigger][event.event_type] += event.amount
            by_trigger[event.trigger]["count"] += 1

        # Top agents by activity (volume)
        agent_volumes: Dict[str, Dict[str, float]] = {}
        for event in self.events:
            if event.agent_id not in agent_volumes:
                agent_volumes[event.agent_id] = {"mint": 0, "burn": 0, "total": 0}
            agent_volumes[event.agent_id][event.event_type] += event.amount
            agent_volumes[event.agent_id]["total"] += event.amount

        # Get top 10 agents
        sorted_agents = sorted(
            agent_volumes.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )[:10]
        by_agent = {agent: stats for agent, stats in sorted_agents}

        return MintBurnSummary(
            total_minted=total_minted,
            total_burned=total_burned,
            net_supply_change=net_change,
            num_mint_events=len(mint_events),
            num_burn_events=len(burn_events),
            mean_mint_size=mean_mint_size,
            mean_burn_size=mean_burn_size,
            by_trigger=by_trigger,
            by_agent=by_agent,
        )

    def detect_imbalance_periods(
        self,
        threshold_ratio: float = 2.0,
        min_consecutive_days: int = 3,
    ) -> List[Tuple[str, str, str]]:
        """
        Detect periods of significant mint/burn imbalance.

        Args:
            threshold_ratio: Ratio threshold for imbalance
            min_consecutive_days: Minimum consecutive days

        Returns:
            List of (start_date, end_date, direction) tuples
        """
        daily_stats = self.calculate_daily_rates()

        if len(daily_stats) < min_consecutive_days:
            return []

        imbalance_periods = []
        current_start = None
        current_direction = None
        consecutive_count = 0

        for stats in daily_stats:
            ratio = stats.mint_burn_ratio

            # Determine direction of imbalance
            if ratio > threshold_ratio:
                direction = "minting"
            elif ratio < 1 / threshold_ratio:
                direction = "burning"
            else:
                direction = None

            if direction == current_direction and direction is not None:
                consecutive_count += 1
            else:
                # Check if previous period was long enough
                if (consecutive_count >= min_consecutive_days and
                        current_start is not None and current_direction is not None):
                    imbalance_periods.append((
                        current_start,
                        daily_stats[daily_stats.index(stats) - 1].date,
                        current_direction
                    ))

                # Start new period
                current_start = stats.date
                current_direction = direction
                consecutive_count = 1 if direction else 0

        # Check last period
        if consecutive_count >= min_consecutive_days and current_direction is not None:
            imbalance_periods.append((
                current_start,
                daily_stats[-1].date,
                current_direction
            ))

        return imbalance_periods

    def clear(self):
        """Clear all events."""
        self.events = []


def simulate_mint_burn_events(
    duration_days: int = 30,
    daily_events_mean: int = 100,
    mint_burn_ratio: float = 1.0,
    event_size_mean: float = 10.0,
    event_size_std: float = 5.0,
    num_agents: int = 50,
    seed: Optional[int] = None,
) -> MintBurnAnalyzer:
    """
    Simulate mint and burn events.

    Args:
        duration_days: Duration to simulate
        daily_events_mean: Mean events per day
        mint_burn_ratio: Ratio of mint to burn events
        event_size_mean: Mean event size
        event_size_std: Standard deviation of event size
        num_agents: Number of agents
        seed: Random seed

    Returns:
        MintBurnAnalyzer with simulated events
    """
    rng = np.random.default_rng(seed)

    analyzer = MintBurnAnalyzer()
    start_time = datetime.now().timestamp()

    # Triggers for mint and burn
    mint_triggers = ["energy_sale", "reward", "staking_reward"]
    burn_triggers = ["redemption", "fee_burn", "penalty"]

    agent_ids = [f"agent_{i}" for i in range(num_agents)]

    total_events = int(daily_events_mean * duration_days)

    # Distribute events over time
    for _ in range(total_events):
        # Random timestamp within duration
        timestamp = start_time + rng.uniform(0, duration_days * 24 * 3600)

        # Determine if mint or burn based on ratio
        mint_prob = mint_burn_ratio / (1 + mint_burn_ratio)
        is_mint = rng.random() < mint_prob

        # Event size (positive, log-normal)
        amount = max(0.1, rng.lognormal(np.log(event_size_mean), event_size_std / event_size_mean))

        # Random agent and trigger
        agent_id = rng.choice(agent_ids)

        if is_mint:
            trigger = rng.choice(mint_triggers)
            analyzer.record_mint(
                timestamp=timestamp,
                amount=amount,
                trigger=trigger,
                agent_id=agent_id,
                kwh_equivalent=amount,  # 1:1 for SHAKTI
            )
        else:
            trigger = rng.choice(burn_triggers)
            analyzer.record_burn(
                timestamp=timestamp,
                amount=amount,
                trigger=trigger,
                agent_id=agent_id,
                kwh_equivalent=amount,
            )

    return analyzer


def simulate_equilibrium_scenarios(
    duration_days: int = 30,
    seed: Optional[int] = None,
) -> Dict[str, MintBurnAnalyzer]:
    """
    Simulate multiple mint/burn equilibrium scenarios.

    Args:
        duration_days: Duration to simulate
        seed: Random seed

    Returns:
        Dictionary of scenario name -> MintBurnAnalyzer
    """
    scenarios = {}

    # Balanced: mint ≈ burn
    scenarios["balanced"] = simulate_mint_burn_events(
        duration_days=duration_days,
        mint_burn_ratio=1.0,
        seed=seed,
    )

    # Inflationary: more minting
    scenarios["inflationary"] = simulate_mint_burn_events(
        duration_days=duration_days,
        mint_burn_ratio=1.5,
        seed=seed + 1 if seed else None,
    )

    # Deflationary: more burning
    scenarios["deflationary"] = simulate_mint_burn_events(
        duration_days=duration_days,
        mint_burn_ratio=0.7,
        seed=seed + 2 if seed else None,
    )

    # Highly imbalanced
    scenarios["imbalanced"] = simulate_mint_burn_events(
        duration_days=duration_days,
        mint_burn_ratio=2.0,
        seed=seed + 3 if seed else None,
    )

    return scenarios
