"""
Pareto Analysis for SHAKTI-CHAIN Benchmarking (Domain 8).

Implements multi-objective optimization analysis:
- Pareto front identification
- Hypervolume indicator calculation
- Dominance relationships
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """
    Metrics for a trading system.

    Attributes:
        name: System name
        efficiency: Allocative efficiency (0-1)
        roi: Return on investment (%)
        fairness: Fairness metric (1 - Gini coefficient)
        throughput: Trading throughput (trades/hour)
        cost: Transaction cost (INR/kWh)
        latency: Average latency (ms)
    """
    name: str
    efficiency: float
    roi: float
    fairness: float
    throughput: float
    cost: float = 0.0
    latency: float = 0.0

    def to_array(self, objectives: List[str] = None) -> np.ndarray:
        """
        Convert to numpy array.

        Args:
            objectives: List of objectives to include

        Returns:
            Numpy array of objective values
        """
        if objectives is None:
            objectives = ['efficiency', 'roi', 'fairness', 'throughput']

        values = []
        for obj in objectives:
            if obj == 'efficiency':
                values.append(self.efficiency)
            elif obj == 'roi':
                values.append(self.roi)
            elif obj == 'fairness':
                values.append(self.fairness)
            elif obj == 'throughput':
                values.append(self.throughput)
            elif obj == 'cost':
                values.append(-self.cost)  # Minimize cost
            elif obj == 'latency':
                values.append(-self.latency)  # Minimize latency

        return np.array(values)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "efficiency": self.efficiency,
            "roi": self.roi,
            "fairness": self.fairness,
            "throughput": self.throughput,
            "cost": self.cost,
            "latency": self.latency,
        }


@dataclass
class ParetoResult:
    """
    Result of Pareto analysis.

    Attributes:
        pareto_optimal: List of Pareto-optimal system names
        dominated: List of dominated system names
        hypervolume: Hypervolume indicator value
        dominance_matrix: Matrix of dominance relationships
        rankings: System rankings by hypervolume contribution
    """
    pareto_optimal: List[str] = field(default_factory=list)
    dominated: List[str] = field(default_factory=list)
    hypervolume: float = 0.0
    dominance_matrix: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    rankings: Dict[str, int] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pareto_optimal": self.pareto_optimal,
            "dominated": self.dominated,
            "hypervolume": self.hypervolume,
            "rankings": self.rankings,
            "contributions": self.contributions,
        }


class ParetoAnalyzer:
    """
    Multi-objective Pareto analysis.

    Identifies Pareto-optimal solutions and calculates hypervolume.
    """

    def __init__(
        self,
        systems: List[SystemMetrics],
        objectives: List[str] = None,
    ):
        """
        Initialize analyzer.

        Args:
            systems: List of system metrics
            objectives: Objectives to consider (all maximized)
        """
        self.systems = systems
        self.objectives = objectives or ['efficiency', 'roi', 'fairness', 'throughput']
        self.n_objectives = len(self.objectives)

    def find_pareto_front(self) -> List[str]:
        """
        Identify Pareto-optimal systems.

        A system is Pareto-optimal if no other system is better
        in all objectives.

        Returns:
            List of Pareto-optimal system names
        """
        objectives = np.array([
            s.to_array(self.objectives) for s in self.systems
        ])

        pareto_mask = self._compute_pareto_mask(objectives)
        return [self.systems[i].name for i in range(len(self.systems)) if pareto_mask[i]]

    def _compute_pareto_mask(self, objectives: np.ndarray) -> np.ndarray:
        """
        Compute boolean mask of Pareto-optimal points.

        Args:
            objectives: Matrix of objective values (n_systems x n_objectives)

        Returns:
            Boolean mask where True = Pareto-optimal
        """
        n = objectives.shape[0]
        is_pareto = np.ones(n, dtype=bool)

        for i in range(n):
            for j in range(n):
                if i != j:
                    # Check if j dominates i
                    # j dominates i if j >= i in all objectives and j > i in at least one
                    if np.all(objectives[j] >= objectives[i]) and np.any(objectives[j] > objectives[i]):
                        is_pareto[i] = False
                        break

        return is_pareto

    def compute_dominance_matrix(self) -> Dict[str, Dict[str, bool]]:
        """
        Compute dominance relationships between all systems.

        Returns:
            Dict mapping (system_a, system_b) to whether a dominates b
        """
        objectives = np.array([
            s.to_array(self.objectives) for s in self.systems
        ])

        n = len(self.systems)
        dominance = {}

        for i in range(n):
            dominance[self.systems[i].name] = {}
            for j in range(n):
                if i != j:
                    # Check if i dominates j
                    dominates = (
                        np.all(objectives[i] >= objectives[j]) and
                        np.any(objectives[i] > objectives[j])
                    )
                    dominance[self.systems[i].name][self.systems[j].name] = dominates

        return dominance

    def calculate_hypervolume(
        self,
        reference_point: np.ndarray = None,
    ) -> float:
        """
        Calculate hypervolume indicator.

        Higher hypervolume = better coverage of objective space.

        Args:
            reference_point: Reference point (dominated by all solutions)

        Returns:
            Hypervolume value
        """
        objectives = np.array([
            s.to_array(self.objectives) for s in self.systems
        ])

        if reference_point is None:
            # Use point dominated by all solutions
            reference_point = np.min(objectives, axis=0) - 0.1

        # Get Pareto front
        pareto_mask = self._compute_pareto_mask(objectives)
        pareto_points = objectives[pareto_mask]

        if len(pareto_points) == 0:
            return 0.0

        # Simple hypervolume calculation (exact for 2D, approximate for higher)
        if self.n_objectives == 2:
            return self._hypervolume_2d(pareto_points, reference_point)
        else:
            return self._hypervolume_monte_carlo(pareto_points, reference_point)

    def _hypervolume_2d(
        self,
        points: np.ndarray,
        reference: np.ndarray,
    ) -> float:
        """Calculate exact 2D hypervolume."""
        # Sort by first objective (descending)
        sorted_idx = np.argsort(-points[:, 0])
        sorted_points = points[sorted_idx]

        hv = 0.0
        prev_y = reference[1]

        for point in sorted_points:
            if point[1] > prev_y:
                hv += (point[0] - reference[0]) * (point[1] - prev_y)
                prev_y = point[1]

        return hv

    def _hypervolume_monte_carlo(
        self,
        points: np.ndarray,
        reference: np.ndarray,
        n_samples: int = 10000,
    ) -> float:
        """Approximate hypervolume using Monte Carlo sampling."""
        # Find bounding box
        upper = np.max(points, axis=0)

        # Generate random samples
        samples = np.random.uniform(
            reference, upper, size=(n_samples, self.n_objectives)
        )

        # Count samples dominated by at least one Pareto point
        dominated_count = 0
        for sample in samples:
            for point in points:
                if np.all(point >= sample):
                    dominated_count += 1
                    break

        # Estimate hypervolume
        box_volume = np.prod(upper - reference)
        return box_volume * dominated_count / n_samples

    def calculate_contributions(
        self,
        reference_point: np.ndarray = None,
    ) -> Dict[str, float]:
        """
        Calculate hypervolume contribution of each system.

        Args:
            reference_point: Reference point

        Returns:
            Dict mapping system name to contribution
        """
        objectives = np.array([
            s.to_array(self.objectives) for s in self.systems
        ])

        if reference_point is None:
            reference_point = np.min(objectives, axis=0) - 0.1

        total_hv = self.calculate_hypervolume(reference_point)
        contributions = {}

        for i, system in enumerate(self.systems):
            # Calculate hypervolume without this system
            remaining = np.delete(objectives, i, axis=0)
            if len(remaining) > 0:
                pareto_mask = self._compute_pareto_mask(remaining)
                pareto_points = remaining[pareto_mask]
                if len(pareto_points) > 0:
                    if self.n_objectives == 2:
                        hv_without = self._hypervolume_2d(pareto_points, reference_point)
                    else:
                        hv_without = self._hypervolume_monte_carlo(pareto_points, reference_point)
                else:
                    hv_without = 0.0
            else:
                hv_without = 0.0

            contributions[system.name] = total_hv - hv_without

        return contributions

    def analyze(
        self,
        reference_point: np.ndarray = None,
    ) -> ParetoResult:
        """
        Perform complete Pareto analysis.

        Args:
            reference_point: Reference point for hypervolume

        Returns:
            ParetoResult with all analysis
        """
        pareto_optimal = self.find_pareto_front()
        dominated = [s.name for s in self.systems if s.name not in pareto_optimal]
        dominance_matrix = self.compute_dominance_matrix()
        hypervolume = self.calculate_hypervolume(reference_point)
        contributions = self.calculate_contributions(reference_point)

        # Rank by contribution
        sorted_systems = sorted(
            contributions.items(),
            key=lambda x: x[1],
            reverse=True
        )
        rankings = {name: rank + 1 for rank, (name, _) in enumerate(sorted_systems)}

        return ParetoResult(
            pareto_optimal=pareto_optimal,
            dominated=dominated,
            hypervolume=hypervolume,
            dominance_matrix=dominance_matrix,
            rankings=rankings,
            contributions=contributions,
        )


def create_benchmark_systems(
    shakti_metrics: Dict[str, float],
    baseline_metrics: Dict[str, Dict[str, float]],
) -> List[SystemMetrics]:
    """
    Create SystemMetrics from benchmark data.

    Args:
        shakti_metrics: SHAKTI-CHAIN metrics
        baseline_metrics: Dict mapping baseline name to metrics

    Returns:
        List of SystemMetrics
    """
    systems = []

    # SHAKTI-CHAIN
    systems.append(SystemMetrics(
        name="SHAKTI-CHAIN",
        efficiency=shakti_metrics.get('efficiency', 0.9),
        roi=shakti_metrics.get('roi', 15.0),
        fairness=shakti_metrics.get('fairness', 0.85),
        throughput=shakti_metrics.get('throughput', 100.0),
        cost=shakti_metrics.get('cost', 0.5),
        latency=shakti_metrics.get('latency', 50.0),
    ))

    # Baselines
    for name, metrics in baseline_metrics.items():
        systems.append(SystemMetrics(
            name=name,
            efficiency=metrics.get('efficiency', 0.7),
            roi=metrics.get('roi', 10.0),
            fairness=metrics.get('fairness', 0.7),
            throughput=metrics.get('throughput', 50.0),
            cost=metrics.get('cost', 1.0),
            latency=metrics.get('latency', 100.0),
        ))

    return systems


def analyze_pareto_optimality(
    systems: List[SystemMetrics],
    objectives: List[str] = None,
) -> ParetoResult:
    """
    Analyze Pareto optimality of systems.

    Args:
        systems: List of system metrics
        objectives: Objectives to consider

    Returns:
        ParetoResult
    """
    analyzer = ParetoAnalyzer(systems, objectives)
    return analyzer.analyze()


def test_shakti_pareto_optimal(
    shakti_metrics: Dict[str, float],
    baseline_metrics: Dict[str, Dict[str, float]],
) -> Tuple[bool, ParetoResult]:
    """
    Test if SHAKTI-CHAIN is Pareto optimal.

    Args:
        shakti_metrics: SHAKTI-CHAIN metrics
        baseline_metrics: Baseline metrics

    Returns:
        (is_pareto_optimal, analysis_result)
    """
    systems = create_benchmark_systems(shakti_metrics, baseline_metrics)
    result = analyze_pareto_optimality(systems)

    is_optimal = "SHAKTI-CHAIN" in result.pareto_optimal
    return is_optimal, result
