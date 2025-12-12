"""
Network Partition Simulator for SHAKTI-CHAIN Stress Testing (Domain 6).

Tests hypothesis H6.5: No inconsistency after partition heal.
Simulates network split (split-brain) scenarios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set
import hashlib

import numpy as np

logger = logging.getLogger(__name__)


class PartitionType(Enum):
    """Types of network partitions."""
    SYMMETRIC = "symmetric"       # Clean 50/50 split
    ASYMMETRIC = "asymmetric"     # Uneven split
    MINORITY_ISOLATED = "minority_isolated"  # Small group isolated
    LEADER_ISOLATED = "leader_isolated"      # Leader node isolated
    CASCADING = "cascading"       # Progressive partition


@dataclass
class PartitionScenario:
    """
    Configuration for a network partition scenario.

    Attributes:
        name: Scenario name
        partition_type: Type of partition
        partition_ratio: Split ratio (e.g., 0.5 for even split)
        duration_seconds: Duration of partition
        heal_delay_seconds: Delay before partition heals
    """
    name: str
    partition_type: PartitionType
    partition_ratio: float
    duration_seconds: float
    heal_delay_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "partition_type": self.partition_type.value,
            "partition_ratio": float(self.partition_ratio),
            "duration_seconds": float(self.duration_seconds),
            "heal_delay_seconds": float(self.heal_delay_seconds),
        }


# Predefined partition scenarios
SYMMETRIC_SPLIT = PartitionScenario(
    name="Symmetric 50/50 Split",
    partition_type=PartitionType.SYMMETRIC,
    partition_ratio=0.5,
    duration_seconds=30.0,
)

ASYMMETRIC_SPLIT = PartitionScenario(
    name="Asymmetric 70/30 Split",
    partition_type=PartitionType.ASYMMETRIC,
    partition_ratio=0.3,
    duration_seconds=30.0,
)

MINORITY_ISOLATED = PartitionScenario(
    name="Minority Isolation (20%)",
    partition_type=PartitionType.MINORITY_ISOLATED,
    partition_ratio=0.2,
    duration_seconds=20.0,
)

LEADER_ISOLATED = PartitionScenario(
    name="Leader Isolation",
    partition_type=PartitionType.LEADER_ISOLATED,
    partition_ratio=0.1,  # Just leader + few followers
    duration_seconds=15.0,
)

PARTITION_SCENARIOS = [
    SYMMETRIC_SPLIT,
    ASYMMETRIC_SPLIT,
    MINORITY_ISOLATED,
    LEADER_ISOLATED,
]


@dataclass
class Transaction:
    """A simulated transaction."""
    tx_id: str
    sender: str
    receiver: str
    amount: float
    timestamp: float
    partition_side: Optional[str] = None  # "A" or "B"

    def hash(self) -> str:
        """Generate transaction hash."""
        data = f"{self.tx_id}:{self.sender}:{self.receiver}:{self.amount}:{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class PartitionResult:
    """
    Result of a network partition simulation.

    Attributes:
        scenario: The partition scenario tested
        consistency_maintained: True if no double-spends or conflicts
        state_divergence: Measure of state difference between partitions
        transactions_lost: Count of lost transactions
        double_spend_count: Number of double-spend attempts
        reconciliation_time_seconds: Time to converge after heal
        partition_a_txns: Transactions in partition A
        partition_b_txns: Transactions in partition B
        conflicts_detected: Number of conflicts during reconciliation
    """
    scenario: PartitionScenario
    consistency_maintained: bool
    state_divergence: float
    transactions_lost: int
    double_spend_count: int
    reconciliation_time_seconds: float
    partition_a_txns: int
    partition_b_txns: int
    conflicts_detected: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario.to_dict(),
            "consistency_maintained": self.consistency_maintained,
            "state_divergence": float(self.state_divergence),
            "transactions_lost": self.transactions_lost,
            "double_spend_count": self.double_spend_count,
            "reconciliation_time_seconds": float(self.reconciliation_time_seconds),
            "partition_a_txns": self.partition_a_txns,
            "partition_b_txns": self.partition_b_txns,
            "conflicts_detected": self.conflicts_detected,
        }


@dataclass
class PartitionToleranceResult:
    """
    Result of partition tolerance hypothesis test (H6.5).

    Attributes:
        passed: Whether no inconsistency after partition heal
        inconsistency_count: Number of simulations with inconsistency
        total_simulations: Total simulations run
        mean_reconciliation_time: Mean time to reconcile
        mean_conflicts: Mean conflicts per simulation
        individual_results: Results from each simulation
    """
    passed: bool
    inconsistency_count: int
    total_simulations: int
    mean_reconciliation_time: float
    mean_conflicts: float
    individual_results: List[PartitionResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "inconsistency_count": self.inconsistency_count,
            "total_simulations": self.total_simulations,
            "mean_reconciliation_time": float(self.mean_reconciliation_time),
            "mean_conflicts": float(self.mean_conflicts),
        }


class Node:
    """A simulated network node."""

    def __init__(
        self,
        node_id: str,
        is_leader: bool = False,
    ):
        self.node_id = node_id
        self.is_leader = is_leader
        self.ledger: Dict[str, Transaction] = {}
        self.balances: Dict[str, float] = {}
        self.pending_txns: List[Transaction] = []

    def receive_transaction(self, txn: Transaction) -> bool:
        """
        Receive and validate a transaction.

        Returns:
            True if transaction accepted
        """
        # Check for double-spend
        sender_balance = self.balances.get(txn.sender, 100.0)
        pending_amount = sum(
            t.amount for t in self.pending_txns
            if t.sender == txn.sender
        )

        if sender_balance - pending_amount < txn.amount:
            return False  # Insufficient balance

        self.pending_txns.append(txn)
        return True

    def commit_block(self) -> List[Transaction]:
        """
        Commit pending transactions to ledger.

        Returns:
            List of committed transactions
        """
        committed = []

        for txn in self.pending_txns:
            sender_balance = self.balances.get(txn.sender, 100.0)

            if sender_balance >= txn.amount:
                self.balances[txn.sender] = sender_balance - txn.amount
                self.balances[txn.receiver] = self.balances.get(txn.receiver, 100.0) + txn.amount
                self.ledger[txn.tx_id] = txn
                committed.append(txn)

        self.pending_txns = []
        return committed

    def get_state_hash(self) -> str:
        """Get hash of current state."""
        state = sorted([(k, v) for k, v in self.balances.items()])
        data = str(state)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class NetworkPartitionSimulator:
    """
    Simulate network partition (split-brain) scenarios.

    Tests H6.5: No inconsistency after partition heal.
    """

    def __init__(
        self,
        n_nodes: int = 10,
        seed: Optional[int] = None,
    ):
        """
        Initialize partition simulator.

        Args:
            n_nodes: Number of network nodes
            seed: Random seed
        """
        self.n_nodes = n_nodes
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Create nodes
        self.nodes: List[Node] = []
        for i in range(n_nodes):
            node = Node(
                node_id=f"node_{i}",
                is_leader=(i == 0),
            )
            # Initialize balances
            for j in range(20):
                node.balances[f"user_{j}"] = 100.0
            self.nodes.append(node)

    def create_partition(
        self,
        partition_ratio: float = 0.5,
    ) -> Tuple[List[Node], List[Node]]:
        """
        Split nodes into two disconnected groups.

        Args:
            partition_ratio: Fraction of nodes in partition A

        Returns:
            (partition_a, partition_b)
        """
        split_point = max(1, int(self.n_nodes * partition_ratio))
        return self.nodes[:split_point], self.nodes[split_point:]

    def generate_transactions(
        self,
        n_transactions: int,
        partition_side: str = "A",
    ) -> List[Transaction]:
        """
        Generate random transactions.

        Args:
            n_transactions: Number of transactions
            partition_side: Which partition generated this

        Returns:
            List of transactions
        """
        transactions = []

        for i in range(n_transactions):
            sender = f"user_{self.rng.integers(0, 20)}"
            receiver = f"user_{self.rng.integers(0, 20)}"

            while receiver == sender:
                receiver = f"user_{self.rng.integers(0, 20)}"

            txn = Transaction(
                tx_id=f"tx_{partition_side}_{i}_{self.rng.integers(0, 100000)}",
                sender=sender,
                receiver=receiver,
                amount=self.rng.uniform(1, 20),
                timestamp=float(i),
                partition_side=partition_side,
            )
            transactions.append(txn)

        return transactions

    def simulate_partition(
        self,
        scenario: PartitionScenario,
    ) -> PartitionResult:
        """
        Simulate a network partition event.

        Args:
            scenario: Partition scenario configuration

        Returns:
            PartitionResult with consistency metrics
        """
        # Reset nodes
        for node in self.nodes:
            node.ledger = {}
            node.pending_txns = []
            for j in range(20):
                node.balances[f"user_{j}"] = 100.0

        # Create partition
        partition_a, partition_b = self.create_partition(scenario.partition_ratio)

        # Calculate number of transactions during partition
        txn_rate_per_second = 10
        n_txns_per_side = int(scenario.duration_seconds * txn_rate_per_second)

        # Generate transactions for each partition
        txns_a = self.generate_transactions(n_txns_per_side, "A")
        txns_b = self.generate_transactions(n_txns_per_side, "B")

        # Process transactions in each partition independently
        committed_a = []
        committed_b = []

        # Partition A processing
        for txn in txns_a:
            for node in partition_a:
                node.receive_transaction(txn)

        for node in partition_a:
            committed_a.extend(node.commit_block())

        # Partition B processing
        for txn in txns_b:
            for node in partition_b:
                node.receive_transaction(txn)

        for node in partition_b:
            committed_b.extend(node.commit_block())

        # Get state hashes before reconciliation
        state_a = partition_a[0].get_state_hash() if partition_a else ""
        state_b = partition_b[0].get_state_hash() if partition_b else ""

        # Calculate state divergence
        if state_a == state_b:
            state_divergence = 0.0
        else:
            # Compare balance differences
            balances_a = partition_a[0].balances if partition_a else {}
            balances_b = partition_b[0].balances if partition_b else {}

            all_users = set(balances_a.keys()) | set(balances_b.keys())
            total_diff = sum(
                abs(balances_a.get(u, 0) - balances_b.get(u, 0))
                for u in all_users
            )
            state_divergence = total_diff / len(all_users) if all_users else 0.0

        # Reconciliation phase
        # Check for conflicts (same user transacted in both partitions)
        users_in_a = set(t.sender for t in committed_a) | set(t.receiver for t in committed_a)
        users_in_b = set(t.sender for t in committed_b) | set(t.receiver for t in committed_b)
        conflicting_users = users_in_a & users_in_b

        # Count potential double-spends
        double_spend_count = 0
        for user in conflicting_users:
            spent_a = sum(t.amount for t in committed_a if t.sender == user)
            spent_b = sum(t.amount for t in committed_b if t.sender == user)
            if spent_a + spent_b > 100.0:  # Initial balance
                double_spend_count += 1

        conflicts_detected = len(conflicting_users)

        # Reconciliation time (proportional to conflicts)
        base_reconciliation = 1.0
        reconciliation_time = base_reconciliation + 0.5 * conflicts_detected

        # Lost transactions (simplified: minority partition transactions may be lost)
        if len(partition_a) < len(partition_b):
            transactions_lost = len(committed_a) // 2
        elif len(partition_b) < len(partition_a):
            transactions_lost = len(committed_b) // 2
        else:
            transactions_lost = 0

        # Consistency maintained if no double-spends detected
        consistency_maintained = double_spend_count == 0

        return PartitionResult(
            scenario=scenario,
            consistency_maintained=consistency_maintained,
            state_divergence=float(state_divergence),
            transactions_lost=transactions_lost,
            double_spend_count=double_spend_count,
            reconciliation_time_seconds=float(reconciliation_time),
            partition_a_txns=len(committed_a),
            partition_b_txns=len(committed_b),
            conflicts_detected=conflicts_detected,
        )

    def test_partition_tolerance(
        self,
        scenario: Optional[PartitionScenario] = None,
        n_simulations: int = 30,
    ) -> PartitionToleranceResult:
        """
        Test H6.5: No inconsistency after partition heal.

        Args:
            scenario: Partition scenario (uses default if None)
            n_simulations: Number of simulations

        Returns:
            PartitionToleranceResult
        """
        if scenario is None:
            scenario = SYMMETRIC_SPLIT

        results = []
        inconsistency_count = 0
        reconciliation_times = []
        conflicts_list = []

        for sim_idx in range(n_simulations):
            sim_seed = self.seed + sim_idx if self.seed else None
            self.rng = np.random.default_rng(sim_seed)

            result = self.simulate_partition(scenario)
            results.append(result)

            if not result.consistency_maintained:
                inconsistency_count += 1

            reconciliation_times.append(result.reconciliation_time_seconds)
            conflicts_list.append(result.conflicts_detected)

        # Passed if no inconsistencies (binary outcome)
        passed = inconsistency_count == 0

        return PartitionToleranceResult(
            passed=passed,
            inconsistency_count=inconsistency_count,
            total_simulations=n_simulations,
            mean_reconciliation_time=float(np.mean(reconciliation_times)),
            mean_conflicts=float(np.mean(conflicts_list)),
            individual_results=results,
        )

    def run_all_scenarios(self) -> Dict[str, PartitionResult]:
        """
        Run all predefined partition scenarios.

        Returns:
            Dictionary mapping scenario name to result
        """
        results = {}

        for scenario in PARTITION_SCENARIOS:
            logger.info(f"Running scenario: {scenario.name}")
            result = self.simulate_partition(scenario)
            results[scenario.name] = result

        return results


def simulate_partition_test(
    partition_ratio: float = 0.5,
    duration_seconds: float = 30.0,
    n_simulations: int = 30,
    seed: Optional[int] = None,
) -> PartitionToleranceResult:
    """
    Run a partition tolerance test.

    Args:
        partition_ratio: Split ratio for partition
        duration_seconds: Duration of partition
        n_simulations: Number of simulations
        seed: Random seed

    Returns:
        PartitionToleranceResult
    """
    simulator = NetworkPartitionSimulator(seed=seed)

    scenario = PartitionScenario(
        name=f"Test Partition ({partition_ratio*100:.0f}%)",
        partition_type=PartitionType.SYMMETRIC,
        partition_ratio=partition_ratio,
        duration_seconds=duration_seconds,
    )

    return simulator.test_partition_tolerance(
        scenario=scenario,
        n_simulations=n_simulations,
    )
