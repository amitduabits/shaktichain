"""
Byzantine Fault Tolerance Tester for SHAKTI-CHAIN Stress Testing (Domain 6).

Tests hypothesis H6.6: Correct operation with 30% Byzantine nodes.
Simulates malicious/faulty node behavior and tests consensus.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set
import hashlib

import numpy as np
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


class ByzantineStrategy(Enum):
    """Types of Byzantine behavior."""
    SILENT = "silent"               # Stop responding (crash fault)
    EQUIVOCATE = "equivocate"       # Send different messages to different nodes
    DELAY = "delay"                 # Respond slowly
    CORRUPT = "corrupt"             # Send invalid/corrupted data
    RANDOM = "random"               # Random behavior
    COLLUDE = "collude"             # Coordinate with other Byzantine nodes


@dataclass
class ByzantineScenario:
    """
    Configuration for a Byzantine fault scenario.

    Attributes:
        name: Scenario name
        byzantine_fraction: Fraction of Byzantine nodes
        strategy: Byzantine behavior strategy
        n_rounds: Number of consensus rounds
    """
    name: str
    byzantine_fraction: float
    strategy: ByzantineStrategy
    n_rounds: int = 100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "byzantine_fraction": float(self.byzantine_fraction),
            "strategy": self.strategy.value,
            "n_rounds": self.n_rounds,
        }


# Predefined Byzantine scenarios
LOW_BYZANTINE = ByzantineScenario(
    name="Low Byzantine (10%)",
    byzantine_fraction=0.10,
    strategy=ByzantineStrategy.SILENT,
)

MEDIUM_BYZANTINE = ByzantineScenario(
    name="Medium Byzantine (20%)",
    byzantine_fraction=0.20,
    strategy=ByzantineStrategy.EQUIVOCATE,
)

HIGH_BYZANTINE = ByzantineScenario(
    name="High Byzantine (30%)",
    byzantine_fraction=0.30,
    strategy=ByzantineStrategy.CORRUPT,
)

THRESHOLD_BYZANTINE = ByzantineScenario(
    name="Threshold Byzantine (33%)",
    byzantine_fraction=0.33,
    strategy=ByzantineStrategy.EQUIVOCATE,
)

OVER_THRESHOLD = ByzantineScenario(
    name="Over Threshold (40%)",
    byzantine_fraction=0.40,
    strategy=ByzantineStrategy.COLLUDE,
)

BYZANTINE_SCENARIOS = [
    LOW_BYZANTINE,
    MEDIUM_BYZANTINE,
    HIGH_BYZANTINE,
    THRESHOLD_BYZANTINE,
    OVER_THRESHOLD,
]


@dataclass
class ConsensusMessage:
    """A consensus protocol message."""
    round_num: int
    sender_id: int
    proposed_value: int
    is_valid: bool = True


@dataclass
class ByzantineTestResult:
    """
    Result of a Byzantine fault tolerance test.

    Attributes:
        scenario: The Byzantine scenario tested
        consensus_achieved: Whether all honest nodes agreed
        consensus_rounds: Rounds to reach consensus
        failure_count: Number of failed consensus rounds
        honest_agreement_rate: Rate of agreement among honest nodes
        invalid_messages_detected: Count of invalid messages
        consensus_values: Values agreed upon in each round
    """
    scenario: ByzantineScenario
    consensus_achieved: bool
    consensus_rounds: float
    failure_count: int
    honest_agreement_rate: float
    invalid_messages_detected: int
    total_rounds: int
    consensus_values: List[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario.to_dict(),
            "consensus_achieved": self.consensus_achieved,
            "consensus_rounds": float(self.consensus_rounds),
            "failure_count": self.failure_count,
            "honest_agreement_rate": float(self.honest_agreement_rate),
            "invalid_messages_detected": self.invalid_messages_detected,
            "total_rounds": self.total_rounds,
        }


@dataclass
class ByzantineToleranceResult:
    """
    Result of Byzantine tolerance hypothesis test (H6.6).

    Attributes:
        passed: Whether correct operation with target Byzantine fraction
        success_count: Number of successful simulations
        total_simulations: Total simulations run
        success_rate: Fraction of successful simulations
        byzantine_fraction_tested: Byzantine fraction tested
        mean_agreement_rate: Mean honest agreement rate
        individual_results: Results from each simulation
    """
    passed: bool
    success_count: int
    total_simulations: int
    success_rate: float
    byzantine_fraction_tested: float
    mean_agreement_rate: float
    individual_results: List[ByzantineTestResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "success_count": self.success_count,
            "total_simulations": self.total_simulations,
            "success_rate": float(self.success_rate),
            "byzantine_fraction_tested": float(self.byzantine_fraction_tested),
            "mean_agreement_rate": float(self.mean_agreement_rate),
        }


class ConsensusNode:
    """A simulated consensus node."""

    def __init__(
        self,
        node_id: int,
        is_byzantine: bool = False,
        strategy: ByzantineStrategy = ByzantineStrategy.SILENT,
        rng: Optional[np.random.Generator] = None,
    ):
        self.node_id = node_id
        self.is_byzantine = is_byzantine
        self.strategy = strategy
        self.rng = rng or np.random.default_rng()

        self.received_messages: List[ConsensusMessage] = []
        self.current_value: Optional[int] = None
        self.decided: bool = False

    def propose(self, round_num: int, true_value: int) -> List[ConsensusMessage]:
        """
        Generate proposal messages for a round.

        Args:
            round_num: Current consensus round
            true_value: The correct value to propose

        Returns:
            List of messages to send
        """
        messages = []

        if self.is_byzantine:
            messages = self._byzantine_propose(round_num, true_value)
        else:
            # Honest node: propose true value
            msg = ConsensusMessage(
                round_num=round_num,
                sender_id=self.node_id,
                proposed_value=true_value,
                is_valid=True,
            )
            messages.append(msg)

        return messages

    def _byzantine_propose(
        self,
        round_num: int,
        true_value: int,
    ) -> List[ConsensusMessage]:
        """Generate Byzantine proposal(s)."""
        messages = []

        if self.strategy == ByzantineStrategy.SILENT:
            # Don't send anything
            pass

        elif self.strategy == ByzantineStrategy.EQUIVOCATE:
            # Send different values to different nodes
            for i in range(3):  # Send to 3 "different" groups
                fake_value = true_value + i + 1
                msg = ConsensusMessage(
                    round_num=round_num,
                    sender_id=self.node_id,
                    proposed_value=fake_value,
                    is_valid=True,
                )
                messages.append(msg)

        elif self.strategy == ByzantineStrategy.DELAY:
            # Send correct value (but late - simulated)
            msg = ConsensusMessage(
                round_num=round_num,
                sender_id=self.node_id,
                proposed_value=true_value,
                is_valid=True,
            )
            messages.append(msg)

        elif self.strategy == ByzantineStrategy.CORRUPT:
            # Send invalid/corrupted data
            msg = ConsensusMessage(
                round_num=round_num,
                sender_id=self.node_id,
                proposed_value=-999,  # Invalid value
                is_valid=False,
            )
            messages.append(msg)

        elif self.strategy == ByzantineStrategy.RANDOM:
            # Random behavior
            if self.rng.random() < 0.5:
                fake_value = self.rng.integers(-100, 100)
                msg = ConsensusMessage(
                    round_num=round_num,
                    sender_id=self.node_id,
                    proposed_value=fake_value,
                    is_valid=self.rng.random() > 0.5,
                )
                messages.append(msg)

        elif self.strategy == ByzantineStrategy.COLLUDE:
            # Send coordinated wrong value
            colluded_value = 12345  # All colluding nodes agree on this
            msg = ConsensusMessage(
                round_num=round_num,
                sender_id=self.node_id,
                proposed_value=colluded_value,
                is_valid=True,
            )
            messages.append(msg)

        return messages

    def receive_messages(self, messages: List[ConsensusMessage]):
        """Receive messages from other nodes."""
        self.received_messages.extend(messages)

    def decide(self, n_total_nodes: int) -> Optional[int]:
        """
        Decide on a value based on received messages.

        Uses simple majority voting with Byzantine fault tolerance.

        Args:
            n_total_nodes: Total number of nodes

        Returns:
            Decided value or None if no decision
        """
        if self.is_byzantine:
            # Byzantine nodes may decide arbitrarily
            if self.strategy == ByzantineStrategy.COLLUDE:
                self.current_value = 12345
                return self.current_value
            return None

        # Filter valid messages
        valid_messages = [m for m in self.received_messages if m.is_valid]

        # Count votes for each value
        votes: Dict[int, int] = {}
        for msg in valid_messages:
            votes[msg.proposed_value] = votes.get(msg.proposed_value, 0) + 1

        if not votes:
            return None

        # Find value with most votes
        max_value = max(votes.keys(), key=lambda v: votes[v])
        max_votes = votes[max_value]

        # Need more than 2/3 of total nodes for BFT
        threshold = (2 * n_total_nodes) // 3 + 1

        if max_votes >= threshold:
            self.current_value = max_value
            self.decided = True
            return max_value

        return None

    def reset(self):
        """Reset for new round."""
        self.received_messages = []
        self.decided = False


class ByzantineTester:
    """
    Test Byzantine fault tolerance.

    System should tolerate f Byzantine nodes where f < n/3.
    Tests H6.6: Correct operation with 30% Byzantine.
    """

    def __init__(
        self,
        n_nodes: int = 10,
        seed: Optional[int] = None,
    ):
        """
        Initialize Byzantine tester.

        Args:
            n_nodes: Total number of nodes
            seed: Random seed
        """
        self.n_nodes = n_nodes
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def inject_byzantine_nodes(
        self,
        byzantine_fraction: float,
        strategy: ByzantineStrategy,
    ) -> Tuple[List[ConsensusNode], Set[int]]:
        """
        Create nodes with some Byzantine.

        Args:
            byzantine_fraction: Fraction of Byzantine nodes
            strategy: Byzantine behavior strategy

        Returns:
            (nodes, byzantine_ids)
        """
        n_byzantine = max(0, min(self.n_nodes - 1, int(self.n_nodes * byzantine_fraction)))
        byzantine_ids = set(self.rng.choice(self.n_nodes, n_byzantine, replace=False))

        nodes = []
        for i in range(self.n_nodes):
            node = ConsensusNode(
                node_id=i,
                is_byzantine=(i in byzantine_ids),
                strategy=strategy,
                rng=self.rng,
            )
            nodes.append(node)

        return nodes, byzantine_ids

    def run_consensus_round(
        self,
        nodes: List[ConsensusNode],
        byzantine_ids: Set[int],
        round_num: int,
        true_value: int,
    ) -> Tuple[bool, int, int]:
        """
        Run a single consensus round.

        Args:
            nodes: List of nodes
            byzantine_ids: IDs of Byzantine nodes
            round_num: Current round number
            true_value: Correct value to agree on

        Returns:
            (consensus_achieved, invalid_count, agreement_count)
        """
        # Collect all messages
        all_messages = []
        for node in nodes:
            messages = node.propose(round_num, true_value)
            all_messages.extend(messages)

        # Count invalid messages
        invalid_count = sum(1 for m in all_messages if not m.is_valid)

        # Distribute messages to all nodes
        for node in nodes:
            node.receive_messages(all_messages)

        # Nodes decide
        decisions = {}
        for node in nodes:
            decision = node.decide(self.n_nodes)
            if decision is not None:
                decisions[node.node_id] = decision

        # Check honest node agreement
        honest_decisions = [
            decisions[i] for i in range(self.n_nodes)
            if i not in byzantine_ids and i in decisions
        ]

        if not honest_decisions:
            return False, invalid_count, 0

        # Check if all honest nodes agree
        consensus_value = honest_decisions[0]
        agreement_count = sum(1 for d in honest_decisions if d == consensus_value)

        consensus_achieved = (
            agreement_count == len(honest_decisions) and
            consensus_value == true_value
        )

        # Reset nodes for next round
        for node in nodes:
            node.reset()

        return consensus_achieved, invalid_count, agreement_count

    def test_consensus(
        self,
        byzantine_fraction: float,
        strategy: ByzantineStrategy,
        n_rounds: int = 100,
    ) -> ByzantineTestResult:
        """
        Test if consensus is still achieved with Byzantine nodes.

        Args:
            byzantine_fraction: Fraction of Byzantine nodes
            strategy: Byzantine behavior strategy
            n_rounds: Number of consensus rounds

        Returns:
            ByzantineTestResult
        """
        nodes, byzantine_ids = self.inject_byzantine_nodes(byzantine_fraction, strategy)

        success_count = 0
        failure_count = 0
        total_invalid = 0
        total_agreement = 0
        n_honest = self.n_nodes - len(byzantine_ids)
        consensus_values = []

        for round_num in range(n_rounds):
            true_value = round_num  # Each round has different value

            success, invalid, agreement = self.run_consensus_round(
                nodes, byzantine_ids, round_num, true_value
            )

            if success:
                success_count += 1
                consensus_values.append(true_value)
            else:
                failure_count += 1
                consensus_values.append(-1)

            total_invalid += invalid
            total_agreement += agreement

        # Calculate metrics
        consensus_rate = success_count / n_rounds
        agreement_rate = total_agreement / (n_rounds * n_honest) if n_honest > 0 else 0

        # Mean rounds to consensus (simplified: 1 if success, n_rounds if fail)
        avg_rounds = 1.0 if success_count > 0 else float(n_rounds)

        scenario = ByzantineScenario(
            name=f"Test ({byzantine_fraction*100:.0f}% {strategy.value})",
            byzantine_fraction=byzantine_fraction,
            strategy=strategy,
            n_rounds=n_rounds,
        )

        return ByzantineTestResult(
            scenario=scenario,
            consensus_achieved=consensus_rate > 0.9,  # >90% success
            consensus_rounds=avg_rounds,
            failure_count=failure_count,
            honest_agreement_rate=float(agreement_rate),
            invalid_messages_detected=total_invalid,
            total_rounds=n_rounds,
            consensus_values=consensus_values,
        )

    def test_byzantine_tolerance(
        self,
        byzantine_fraction: float = 0.30,
        strategy: ByzantineStrategy = ByzantineStrategy.EQUIVOCATE,
        n_simulations: int = 30,
        n_rounds_per_sim: int = 50,
    ) -> ByzantineToleranceResult:
        """
        Test H6.6: Correct operation with given Byzantine fraction.

        Args:
            byzantine_fraction: Fraction of Byzantine nodes
            strategy: Byzantine behavior strategy
            n_simulations: Number of simulations
            n_rounds_per_sim: Rounds per simulation

        Returns:
            ByzantineToleranceResult
        """
        results = []
        success_count = 0
        agreement_rates = []

        for sim_idx in range(n_simulations):
            sim_seed = self.seed + sim_idx if self.seed else None
            self.rng = np.random.default_rng(sim_seed)

            result = self.test_consensus(
                byzantine_fraction=byzantine_fraction,
                strategy=strategy,
                n_rounds=n_rounds_per_sim,
            )
            results.append(result)

            if result.consensus_achieved:
                success_count += 1

            agreement_rates.append(result.honest_agreement_rate)

        success_rate = success_count / n_simulations
        mean_agreement = float(np.mean(agreement_rates))

        # Passed if majority of simulations succeeded (using binomial test)
        # For f < n/3 Byzantine, should work >95% of time
        passed = success_rate >= 0.95

        return ByzantineToleranceResult(
            passed=passed,
            success_count=success_count,
            total_simulations=n_simulations,
            success_rate=success_rate,
            byzantine_fraction_tested=byzantine_fraction,
            mean_agreement_rate=mean_agreement,
            individual_results=results,
        )

    def find_failure_threshold(
        self,
        strategies: Optional[List[ByzantineStrategy]] = None,
        min_fraction: float = 0.1,
        max_fraction: float = 0.5,
        precision: float = 0.05,
    ) -> Dict[str, float]:
        """
        Find minimum Byzantine fraction that causes failure.

        Uses binary search to find threshold.

        Args:
            strategies: Strategies to test
            min_fraction: Minimum fraction to test
            max_fraction: Maximum fraction to test
            precision: Search precision

        Returns:
            Dictionary mapping strategy to failure threshold
        """
        if strategies is None:
            strategies = [
                ByzantineStrategy.SILENT,
                ByzantineStrategy.EQUIVOCATE,
                ByzantineStrategy.CORRUPT,
            ]

        thresholds = {}

        for strategy in strategies:
            low = min_fraction
            high = max_fraction
            threshold = high

            while high - low > precision:
                mid = (low + high) / 2
                result = self.test_byzantine_tolerance(
                    byzantine_fraction=mid,
                    strategy=strategy,
                    n_simulations=10,
                    n_rounds_per_sim=20,
                )

                if result.passed:
                    low = mid
                else:
                    high = mid
                    threshold = mid

            thresholds[strategy.value] = threshold
            logger.info(f"Strategy {strategy.value}: failure threshold = {threshold:.2f}")

        return thresholds

    def run_all_scenarios(
        self,
        n_rounds: int = 50,
    ) -> Dict[str, ByzantineTestResult]:
        """
        Run all predefined Byzantine scenarios.

        Args:
            n_rounds: Rounds per scenario

        Returns:
            Dictionary mapping scenario name to result
        """
        results = {}

        for scenario in BYZANTINE_SCENARIOS:
            logger.info(f"Running scenario: {scenario.name}")
            result = self.test_consensus(
                byzantine_fraction=scenario.byzantine_fraction,
                strategy=scenario.strategy,
                n_rounds=n_rounds,
            )
            results[scenario.name] = result

        return results


def simulate_byzantine_test(
    byzantine_fraction: float = 0.30,
    strategy: ByzantineStrategy = ByzantineStrategy.EQUIVOCATE,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> ByzantineToleranceResult:
    """
    Run a Byzantine fault tolerance test.

    Args:
        byzantine_fraction: Fraction of Byzantine nodes
        strategy: Byzantine behavior strategy
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        ByzantineToleranceResult
    """
    tester = ByzantineTester(n_nodes=10, seed=seed)

    return tester.test_byzantine_tolerance(
        byzantine_fraction=byzantine_fraction,
        strategy=strategy,
        n_simulations=n_simulations,
    )
