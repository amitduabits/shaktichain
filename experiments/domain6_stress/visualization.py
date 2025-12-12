"""
Domain 6: Stress Testing Visualization Module

Generates plots for stress testing analysis:
1. Efficiency vs demand multiplier
2. Recovery time distribution
3. Price series during shock/recovery
4. System behavior under volatility (heatmap)
5. Byzantine tolerance curve
6. Partition timeline visualization
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from .peak_demand_simulator import PeakDemandResult, PeakDemandTestResult
from .supply_shock_simulator import SupplyShockResult, RecoveryTestResult
from .volatility_injector import VolatilityTestResult, StabilityTestResult
from .overload_tester import OverloadResult, DegradationTestResult
from .partition_simulator import PartitionResult, PartitionToleranceResult
from .byzantine_tester import ByzantineTestResult, ByzantineToleranceResult
from .hypothesis_tests import StressHypothesisResult

logger = logging.getLogger(__name__)


class StressVisualization:
    """Generates visualizations for stress testing experiments."""

    def __init__(self, output_dir: str = "results/domain6_stress"):
        """
        Initialize visualization.

        Args:
            output_dir: Directory for saving plots
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set style
        plt.style.use('seaborn-v0_8-whitegrid')
        self.colors = {
            'primary': '#2E86AB',
            'secondary': '#A23B72',
            'success': '#28A745',
            'warning': '#FFC107',
            'danger': '#DC3545',
            'threshold': '#DC3545',
            'baseline': '#28A745',
            'stress': '#DC3545',
            'recovery': '#2E86AB',
        }

    def plot_efficiency_vs_demand(
        self,
        results: List[PeakDemandResult],
        title: str = "Efficiency vs Demand Multiplier",
        filename: str = "efficiency_vs_demand.png",
    ) -> str:
        """
        Plot efficiency as a function of demand multiplier.

        Args:
            results: List of peak demand results
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        multipliers = [r.scenario.multiplier for r in results]
        efficiencies = [r.efficiency_during_peak for r in results]
        min_efficiencies = [r.efficiency_min for r in results]

        # Sort by multiplier
        sorted_idx = np.argsort(multipliers)
        multipliers = [multipliers[i] for i in sorted_idx]
        efficiencies = [efficiencies[i] for i in sorted_idx]
        min_efficiencies = [min_efficiencies[i] for i in sorted_idx]

        ax.plot(multipliers, efficiencies, 'o-', color=self.colors['primary'],
                linewidth=2, markersize=8, label='Mean Efficiency')
        ax.plot(multipliers, min_efficiencies, 's--', color=self.colors['warning'],
                linewidth=2, markersize=6, label='Minimum Efficiency')

        # 90% threshold
        ax.axhline(y=0.90, color=self.colors['threshold'], linestyle='--',
                   linewidth=2, label='90% Threshold (H6.1)')

        # 2.5x marker
        ax.axvline(x=2.5, color=self.colors['secondary'], linestyle=':',
                   linewidth=2, alpha=0.7, label='2.5x Target')

        ax.set_xlabel('Demand Multiplier', fontsize=12)
        ax.set_ylabel('Efficiency', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='lower left')
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_recovery_distribution(
        self,
        results: List[SupplyShockResult],
        threshold: int = 10,
        title: str = "Recovery Time Distribution",
        filename: str = "recovery_distribution.png",
    ) -> str:
        """
        Plot distribution of recovery times.

        Args:
            results: List of shock results
            threshold: Recovery threshold (rounds)
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        recovery_times = [r.recovery_rounds for r in results]

        # Histogram
        ax1 = axes[0]
        counts, bins, _ = ax1.hist(recovery_times, bins=20, color=self.colors['primary'],
                                    alpha=0.7, edgecolor='black')

        ax1.axvline(x=threshold, color=self.colors['threshold'], linestyle='--',
                    linewidth=2, label=f'Threshold: {threshold} rounds')
        ax1.axvline(x=np.mean(recovery_times), color=self.colors['success'],
                    linestyle='-', linewidth=2, label=f'Mean: {np.mean(recovery_times):.1f}')

        ax1.set_xlabel('Recovery Rounds', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title('Recovery Time Histogram', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Box plot by shock type
        ax2 = axes[1]
        shock_names = [r.shock_event.name[:20] for r in results]

        # Group by shock type
        unique_shocks = list(set(shock_names))
        grouped_times = [[r.recovery_rounds for r in results if r.shock_event.name[:20] == s]
                         for s in unique_shocks]

        bp = ax2.boxplot(grouped_times, labels=[s[:15] for s in unique_shocks],
                         patch_artist=True)

        for patch in bp['boxes']:
            patch.set_facecolor(self.colors['primary'])
            patch.set_alpha(0.7)

        ax2.axhline(y=threshold, color=self.colors['threshold'], linestyle='--',
                    linewidth=2, label='Threshold')

        ax2.set_xlabel('Shock Type', fontsize=12)
        ax2.set_ylabel('Recovery Rounds', fontsize=12)
        ax2.set_title('Recovery by Shock Type', fontsize=12)
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_shock_recovery(
        self,
        result: SupplyShockResult,
        title: str = "Shock and Recovery Dynamics",
        filename: str = "shock_recovery.png",
    ) -> str:
        """
        Plot price and efficiency series during shock/recovery.

        Args:
            result: Shock simulation result
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

        rounds = np.arange(len(result.efficiency_series))
        shock_round = result.shock_event.trigger_round

        # Supply fraction
        ax1 = axes[0]
        ax1.plot(rounds, result.supply_fraction_series, color=self.colors['danger'],
                 linewidth=2)
        ax1.axvline(x=shock_round, color='gray', linestyle='--', alpha=0.7,
                    label='Shock Start')
        ax1.fill_between(rounds, result.supply_fraction_series, alpha=0.3,
                         color=self.colors['danger'])
        ax1.set_ylabel('Supply Fraction', fontsize=11)
        ax1.set_title('Supply Level', fontsize=12)
        ax1.set_ylim(0, 1.1)
        ax1.legend(loc='lower right')
        ax1.grid(True, alpha=0.3)

        # Efficiency
        ax2 = axes[1]
        ax2.plot(rounds, result.efficiency_series, color=self.colors['primary'],
                 linewidth=2)
        ax2.axvline(x=shock_round, color='gray', linestyle='--', alpha=0.7)
        ax2.axhline(y=result.efficiency_pre_shock * 0.9, color=self.colors['success'],
                    linestyle=':', linewidth=2, label='90% Recovery')
        ax2.axhline(y=result.efficiency_pre_shock, color=self.colors['baseline'],
                    linestyle='--', linewidth=2, alpha=0.7, label='Baseline')
        ax2.set_ylabel('Efficiency', fontsize=11)
        ax2.set_title('Market Efficiency', fontsize=12)
        ax2.legend(loc='lower right')
        ax2.grid(True, alpha=0.3)

        # Price
        ax3 = axes[2]
        ax3.plot(rounds, result.price_series, color=self.colors['secondary'],
                 linewidth=2)
        ax3.axvline(x=shock_round, color='gray', linestyle='--', alpha=0.7)
        ax3.axhline(y=result.price_pre_shock, color=self.colors['baseline'],
                    linestyle='--', linewidth=2, alpha=0.7, label='Baseline Price')
        ax3.set_ylabel('Price', fontsize=11)
        ax3.set_xlabel('Round', fontsize=12)
        ax3.set_title('Clearing Price', fontsize=12)
        ax3.legend(loc='upper right')
        ax3.grid(True, alpha=0.3)

        plt.suptitle(f"{title}\n{result.shock_event.name}", fontsize=14, fontweight='bold')
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_volatility_heatmap(
        self,
        results: List[VolatilityTestResult],
        title: str = "System Behavior Under Volatility",
        filename: str = "volatility_heatmap.png",
    ) -> str:
        """
        Plot heatmap of system behavior under different volatility levels.

        Args:
            results: List of volatility test results
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Extract metrics
        scenarios = [r.scenario.name[:20] for r in results]
        variances = [r.scenario.variance_multiplier for r in results]
        efficiencies = [r.mean_efficiency for r in results]
        failures = [1 if r.market_failed else 0 for r in results]

        # Efficiency bar chart
        ax1 = axes[0]
        colors = [self.colors['success'] if e > 0.7 else
                  self.colors['warning'] if e > 0.5 else
                  self.colors['danger'] for e in efficiencies]

        bars = ax1.barh(scenarios, efficiencies, color=colors, alpha=0.8)

        ax1.axvline(x=0.7, color='gray', linestyle='--', linewidth=2)
        ax1.set_xlabel('Mean Efficiency', fontsize=12)
        ax1.set_title('Efficiency by Scenario', fontsize=12)
        ax1.set_xlim(0, 1)
        ax1.grid(True, alpha=0.3, axis='x')

        # Failure indicator
        ax2 = axes[1]
        failure_colors = [self.colors['danger'] if f else self.colors['success'] for f in failures]
        ax2.barh(scenarios, [1] * len(scenarios), color=failure_colors, alpha=0.8)

        for i, (name, failed) in enumerate(zip(scenarios, failures)):
            label = "FAILED" if failed else "STABLE"
            ax2.text(0.5, i, label, ha='center', va='center',
                     fontsize=11, fontweight='bold', color='white')

        ax2.set_xlabel('')
        ax2.set_xlim(0, 1)
        ax2.set_xticks([])
        ax2.set_title('Market Stability', fontsize=12)

        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_byzantine_tolerance(
        self,
        results: List[ByzantineTestResult],
        title: str = "Byzantine Fault Tolerance",
        filename: str = "byzantine_tolerance.png",
    ) -> str:
        """
        Plot Byzantine tolerance curve.

        Args:
            results: List of Byzantine test results
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        # Sort by Byzantine fraction
        sorted_results = sorted(results, key=lambda r: r.scenario.byzantine_fraction)

        fractions = [r.scenario.byzantine_fraction * 100 for r in sorted_results]
        agreement_rates = [r.honest_agreement_rate * 100 for r in sorted_results]
        success = [r.consensus_achieved for r in sorted_results]

        # Agreement rate line
        ax.plot(fractions, agreement_rates, 'o-', color=self.colors['primary'],
                linewidth=2, markersize=8, label='Agreement Rate')

        # Color markers by success
        for i, (f, a, s) in enumerate(zip(fractions, agreement_rates, success)):
            color = self.colors['success'] if s else self.colors['danger']
            ax.scatter([f], [a], c=color, s=100, zorder=5)

        # Theoretical threshold (n/3)
        ax.axvline(x=33.3, color=self.colors['threshold'], linestyle='--',
                   linewidth=2, label='n/3 Threshold (33%)')

        # 30% target
        ax.axvline(x=30, color=self.colors['secondary'], linestyle=':',
                   linewidth=2, alpha=0.7, label='H6.6 Target (30%)')

        ax.set_xlabel('Byzantine Fraction (%)', fontsize=12)
        ax.set_ylabel('Honest Agreement Rate (%)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='lower left')
        ax.set_xlim(0, 50)
        ax.set_ylim(0, 110)
        ax.grid(True, alpha=0.3)

        # Add success/fail annotation
        ax.annotate('Consensus Achieved', xy=(0.95, 0.95), xycoords='axes fraction',
                    fontsize=10, ha='right', color=self.colors['success'],
                    fontweight='bold')
        ax.annotate('Consensus Failed', xy=(0.95, 0.90), xycoords='axes fraction',
                    fontsize=10, ha='right', color=self.colors['danger'],
                    fontweight='bold')

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_partition_timeline(
        self,
        result: PartitionResult,
        title: str = "Network Partition Timeline",
        filename: str = "partition_timeline.png",
    ) -> str:
        """
        Visualize network partition event timeline.

        Args:
            result: Partition simulation result
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        duration = result.scenario.duration_seconds

        # Create timeline
        events = [
            (0, "Normal Operation", self.colors['success']),
            (5, "Partition Starts", self.colors['danger']),
            (5 + duration / 3, "Partition A Active", self.colors['warning']),
            (5 + 2 * duration / 3, "Partition B Active", self.colors['secondary']),
            (5 + duration, "Partition Heals", self.colors['success']),
            (5 + duration + result.reconciliation_time_seconds, "Reconciled", self.colors['success']),
        ]

        for i, (time, event, color) in enumerate(events):
            ax.axvline(x=time, color=color, linestyle='-', linewidth=3, alpha=0.7)
            ax.annotate(event, xy=(time, 0.5 + 0.1 * (i % 2)),
                        fontsize=10, ha='center', rotation=45)

        # Partition regions
        ax.axvspan(5, 5 + duration, alpha=0.2, color=self.colors['danger'],
                   label='Partition Active')
        ax.axvspan(5 + duration, 5 + duration + result.reconciliation_time_seconds,
                   alpha=0.2, color=self.colors['warning'], label='Reconciliation')

        # Metrics annotation
        metrics_text = (
            f"Partition A Txns: {result.partition_a_txns}\n"
            f"Partition B Txns: {result.partition_b_txns}\n"
            f"Conflicts: {result.conflicts_detected}\n"
            f"Consistency: {'Maintained' if result.consistency_maintained else 'VIOLATED'}"
        )

        ax.annotate(metrics_text, xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=10, ha='left', va='top',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_yticks([])
        ax.set_title(f"{title}\n{result.scenario.name}", fontsize=14, fontweight='bold')
        ax.legend(loc='lower right')
        ax.set_xlim(-2, 5 + duration + result.reconciliation_time_seconds + 5)
        ax.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_hypothesis_summary(
        self,
        results: Dict[str, StressHypothesisResult],
        title: str = "Domain 6: Stress Testing Hypothesis Results",
        filename: str = "hypothesis_summary.png",
    ) -> str:
        """
        Create summary visualization of all hypothesis test results.

        Args:
            results: Dictionary of hypothesis test results
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        hypotheses = list(results.keys())
        passed = [results[h].passed for h in hypotheses]
        p_values = [results[h].p_value for h in hypotheses]

        # Pass/Fail bar chart
        ax1 = axes[0]
        colors = [self.colors['success'] if p else self.colors['danger'] for p in passed]
        bars = ax1.barh(hypotheses, [1] * len(hypotheses), color=colors, alpha=0.8)

        for i, (h, p) in enumerate(zip(hypotheses, passed)):
            label = "PASS" if p else "FAIL"
            ax1.text(0.5, i, label, ha='center', va='center',
                     fontsize=12, fontweight='bold', color='white')

        ax1.set_xlabel('')
        ax1.set_xlim(0, 1)
        ax1.set_xticks([])
        ax1.set_title('Hypothesis Test Results', fontsize=12, fontweight='bold')
        ax1.invert_yaxis()

        # Add descriptions
        descriptions = {
            'H6.1': 'Peak Demand (90% @ 2.5x)',
            'H6.2': 'Recovery (<10 rounds)',
            'H6.3': 'Volatility (no fail @ 3σ)',
            'H6.4': 'Degradation (50% @ 2x)',
            'H6.5': 'Partition (no inconsist.)',
            'H6.6': 'Byzantine (30% tolerance)',
        }

        for i, h in enumerate(hypotheses):
            desc = descriptions.get(h, h)
            ax1.text(1.02, i, desc, ha='left', va='center', fontsize=10)

        # P-values plot
        ax2 = axes[1]
        x = np.arange(len(hypotheses))

        bars2 = ax2.bar(x, p_values, color=self.colors['primary'], alpha=0.8)

        # Significance threshold
        ax2.axhline(y=0.05, color=self.colors['danger'], linestyle='--',
                    linewidth=2, label='α = 0.05')

        ax2.set_xlabel('Hypothesis', fontsize=12)
        ax2.set_ylabel('P-Value', fontsize=12)
        ax2.set_title('P-Values', fontsize=12, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(hypotheses)
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3, axis='y')

        # Summary
        total = len(hypotheses)
        passed_count = sum(passed)
        pass_rate = passed_count / total * 100

        plt.suptitle(f'{title}\n({passed_count}/{total} Passed - {pass_rate:.1f}%)',
                     fontsize=14, fontweight='bold')
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_all_plots(
        self,
        peak_results: Optional[List[PeakDemandResult]] = None,
        shock_results: Optional[List[SupplyShockResult]] = None,
        volatility_results: Optional[List[VolatilityTestResult]] = None,
        byzantine_results: Optional[List[ByzantineTestResult]] = None,
        partition_result: Optional[PartitionResult] = None,
        hypothesis_results: Optional[Dict[str, StressHypothesisResult]] = None,
    ) -> Dict[str, str]:
        """
        Generate all visualization plots.

        Returns:
            Dictionary mapping plot names to file paths
        """
        plots = {}

        if peak_results:
            plots['efficiency_vs_demand'] = self.plot_efficiency_vs_demand(peak_results)

        if shock_results:
            plots['recovery_distribution'] = self.plot_recovery_distribution(shock_results)
            if shock_results:
                plots['shock_recovery'] = self.plot_shock_recovery(shock_results[0])

        if volatility_results:
            plots['volatility_heatmap'] = self.plot_volatility_heatmap(volatility_results)

        if byzantine_results:
            plots['byzantine_tolerance'] = self.plot_byzantine_tolerance(byzantine_results)

        if partition_result:
            plots['partition_timeline'] = self.plot_partition_timeline(partition_result)

        if hypothesis_results:
            plots['hypothesis_summary'] = self.plot_hypothesis_summary(hypothesis_results)

        return plots


def create_visualization_report(
    output_dir: str = "results/domain6_stress",
) -> StressVisualization:
    """
    Factory function to create a visualization instance.

    Args:
        output_dir: Directory for saving plots

    Returns:
        StressVisualization instance
    """
    return StressVisualization(output_dir=output_dir)
