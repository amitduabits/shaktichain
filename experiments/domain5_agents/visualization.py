"""
Domain 5: Agent Behavior Visualization Module

Generates plots for agent behavior analysis:
1. Truthful vs strategic utility scatter plot
2. Convergence: price series with equilibrium marked
3. Efficiency by agent composition (stacked bar)
4. Manipulation gain by strategy (bar chart)
5. Utility vs Sybil count (scatter with regression)
6. Collusion gain sensitivity analysis
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from .incentive_compatibility import ICTestResult, AgentICResult
from .convergence_analyzer import ConvergenceTestResult, EfficiencyResult
from .manipulation_simulator import ManipulationResult, ManipulationTestResult
from .sybil_tester import SybilTestResult, SybilTestPoint
from .collusion_detector import CollusionTestResult, CollusionSimResult
from .hypothesis_tests import AgentHypothesisResult

logger = logging.getLogger(__name__)


class AgentVisualization:
    """Generates visualizations for agent behavior experiments."""

    def __init__(self, output_dir: str = "results/domain5_agents"):
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
            'truthful': '#28A745',
            'strategic': '#DC3545',
            'threshold': '#DC3545',
            'equilibrium': '#28A745',
        }

    def plot_ic_scatter(
        self,
        ic_result: ICTestResult,
        title: str = "Truthful vs Strategic Utility",
        filename: str = "ic_scatter.png",
    ) -> str:
        """
        Plot truthful vs strategic utility scatter plot.

        Args:
            ic_result: IC test result
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(10, 8))

        truthful_utilities = []
        max_strategic_utilities = []

        for agent_result in ic_result.agent_results:
            truthful_utilities.append(agent_result.utility_truthful)
            max_strategic_utilities.append(agent_result.utility_deviate_max)

        truthful_utilities = np.array(truthful_utilities)
        max_strategic_utilities = np.array(max_strategic_utilities)

        # Scatter plot
        profitable = max_strategic_utilities > truthful_utilities
        ax.scatter(
            truthful_utilities[~profitable],
            max_strategic_utilities[~profitable],
            c=self.colors['truthful'],
            alpha=0.6,
            s=50,
            label='Truthful Optimal'
        )
        ax.scatter(
            truthful_utilities[profitable],
            max_strategic_utilities[profitable],
            c=self.colors['strategic'],
            alpha=0.6,
            s=50,
            label='Strategic Better'
        )

        # 45-degree line (y = x)
        min_val = min(truthful_utilities.min(), max_strategic_utilities.min())
        max_val = max(truthful_utilities.max(), max_strategic_utilities.max())
        ax.plot([min_val, max_val], [min_val, max_val],
                'k--', linewidth=2, label='y = x (IC boundary)')

        ax.set_xlabel('Truthful Bidding Utility', fontsize=12)
        ax.set_ylabel('Best Strategic Utility', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)

        # Add statistics annotation
        success_rate = ic_result.deviation_success_rate * 100
        stats_text = f'Deviation Success Rate: {success_rate:.1f}%\np-value: {ic_result.binomial_p_value:.4f}'
        ax.annotate(stats_text, xy=(0.95, 0.05), xycoords='axes fraction',
                    fontsize=10, ha='right', va='bottom',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_convergence(
        self,
        price_series: np.ndarray,
        equilibrium_price: float,
        convergence_round: Optional[int] = None,
        title: str = "Price Convergence",
        filename: str = "convergence.png",
    ) -> str:
        """
        Plot price series with equilibrium marked.

        Args:
            price_series: Array of prices over time
            equilibrium_price: Theoretical equilibrium price
            convergence_round: Round at which convergence detected
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        rounds = np.arange(len(price_series))

        # Price series
        ax.plot(rounds, price_series, color=self.colors['primary'],
                linewidth=2, label='Market Price')

        # Equilibrium price
        ax.axhline(y=equilibrium_price, color=self.colors['equilibrium'],
                   linestyle='--', linewidth=2, label=f'Equilibrium: {equilibrium_price:.2f}')

        # 50-round threshold
        ax.axvline(x=50, color=self.colors['warning'],
                   linestyle=':', linewidth=2, alpha=0.7, label='50-round threshold')

        # Convergence point
        if convergence_round is not None:
            ax.axvline(x=convergence_round, color=self.colors['success'],
                       linestyle='-', linewidth=2, alpha=0.7,
                       label=f'Converged at round {convergence_round}')
            ax.scatter([convergence_round], [price_series[min(convergence_round, len(price_series)-1)]],
                       color=self.colors['success'], s=100, zorder=5)

        ax.set_xlabel('Trading Round', fontsize=12)
        ax.set_ylabel('Price', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_efficiency_by_composition(
        self,
        efficiency_results: List[EfficiencyResult],
        title: str = "Efficiency by Agent Composition",
        filename: str = "efficiency_composition.png",
    ) -> str:
        """
        Plot efficiency by agent composition (stacked bar).

        Args:
            efficiency_results: List of efficiency results
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        # Group by composition
        compositions = []
        efficiencies = []
        rational_fracs = []
        br_fracs = []
        zi_fracs = []

        for result in efficiency_results:
            label = f"R:{result.rational_fraction:.0%}\nBR:{result.bounded_rational_fraction:.0%}"
            compositions.append(label)
            efficiencies.append(result.achieved_efficiency)
            rational_fracs.append(result.rational_fraction)
            br_fracs.append(result.bounded_rational_fraction)
            zi_fracs.append(result.zero_intelligence_fraction)

        x = np.arange(len(compositions))
        width = 0.35

        # Efficiency bars
        bars = ax.bar(x, efficiencies, width, color=self.colors['primary'], alpha=0.8,
                      label='Achieved Efficiency')

        # 85% threshold
        ax.axhline(y=0.85, color=self.colors['threshold'], linestyle='--',
                   linewidth=2, label='85% Threshold (H5.3)')

        ax.set_xlabel('Agent Composition', fontsize=12)
        ax.set_ylabel('Efficiency', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(compositions, fontsize=9)
        ax.legend(loc='upper right')
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3, axis='y')

        # Color bars based on threshold
        for bar, eff in zip(bars, efficiencies):
            if eff >= 0.85:
                bar.set_color(self.colors['success'])
            else:
                bar.set_color(self.colors['danger'])

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_manipulation_gains(
        self,
        manipulation_result: ManipulationTestResult,
        title: str = "Manipulation Gain by Strategy",
        filename: str = "manipulation_gains.png",
    ) -> str:
        """
        Plot manipulation gain by strategy (bar chart).

        Args:
            manipulation_result: Manipulation test result
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        strategies = list(manipulation_result.results_by_strategy.keys())
        gains = [manipulation_result.results_by_strategy[s].manipulation_gain * 100
                 for s in strategies]

        x = np.arange(len(strategies))
        colors = [self.colors['success'] if g < 5 else self.colors['danger'] for g in gains]

        bars = ax.bar(x, gains, color=colors, alpha=0.8)

        # 5% threshold
        ax.axhline(y=5, color=self.colors['threshold'], linestyle='--',
                   linewidth=2, label='5% Threshold (H5.4)')

        ax.set_xlabel('Manipulation Strategy', fontsize=12)
        ax.set_ylabel('Manipulation Gain (%)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace('_', '\n') for s in strategies], fontsize=10)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3, axis='y')

        # Add value labels
        for bar, gain in zip(bars, gains):
            height = bar.get_height()
            ax.annotate(f'{gain:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_sybil_regression(
        self,
        sybil_result: SybilTestResult,
        title: str = "Utility vs Number of Identities",
        filename: str = "sybil_regression.png",
    ) -> str:
        """
        Plot utility vs Sybil count with regression line.

        Args:
            sybil_result: Sybil test result
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        n_values = [p.num_identities for p in sybil_result.test_points]
        utilities = [p.total_utility for p in sybil_result.test_points]

        # Scatter points
        ax.scatter(n_values, utilities, color=self.colors['primary'],
                   s=100, zorder=5, label='Observed')

        # Regression line
        x_line = np.linspace(min(n_values), max(n_values), 100)
        y_line = sybil_result.intercept + sybil_result.regression_slope * x_line
        ax.plot(x_line, y_line, color=self.colors['secondary'],
                linewidth=2, linestyle='--',
                label=f'Regression (slope={sybil_result.regression_slope:.4f})')

        # Horizontal line at single-identity utility
        ax.axhline(y=sybil_result.utility_single_identity, color=self.colors['equilibrium'],
                   linestyle=':', linewidth=2, alpha=0.7,
                   label=f'Single Identity: {sybil_result.utility_single_identity:.2f}')

        ax.set_xlabel('Number of Identities', fontsize=12)
        ax.set_ylabel('Total Utility', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        # Statistics annotation
        status = "Profitable" if sybil_result.sybil_profitable else "Not Profitable"
        stats_text = f'Sybil: {status}\nSlope p-value: {sybil_result.slope_p_value:.4f}\nR²: {sybil_result.r_squared:.4f}'
        ax.annotate(stats_text, xy=(0.95, 0.05), xycoords='axes fraction',
                    fontsize=10, ha='right', va='bottom',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_collusion_sensitivity(
        self,
        collusion_result: CollusionTestResult,
        title: str = "Collusion Gain vs Coalition Size",
        filename: str = "collusion_sensitivity.png",
    ) -> str:
        """
        Plot collusion gain sensitivity to coalition size.

        Args:
            collusion_result: Collusion test result
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Left: Gain by strategy
        ax1 = axes[0]
        strategies = list(collusion_result.results_by_strategy.keys())
        gains = [collusion_result.results_by_strategy[s].collusion_gain * 100
                 for s in strategies]

        x = np.arange(len(strategies))
        colors = [self.colors['success'] if g < 10 else self.colors['danger'] for g in gains]

        bars = ax1.bar(x, gains, color=colors, alpha=0.8)
        ax1.axhline(y=10, color=self.colors['threshold'], linestyle='--',
                    linewidth=2, label='10% Threshold (H5.6)')

        ax1.set_xlabel('Collusion Strategy', fontsize=12)
        ax1.set_ylabel('Collusion Gain (%)', fontsize=12)
        ax1.set_title('Gain by Strategy', fontsize=12, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels([s.replace('_', '\n') for s in strategies], fontsize=9)
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3, axis='y')

        # Right: Gain by coalition size
        ax2 = axes[1]
        sizes = sorted(collusion_result.coalition_size_effect.keys())
        size_gains = [collusion_result.coalition_size_effect[s] * 100 for s in sizes]

        ax2.plot(sizes, size_gains, 'o-', color=self.colors['primary'],
                 linewidth=2, markersize=8, label='Observed')
        ax2.axhline(y=10, color=self.colors['threshold'], linestyle='--',
                    linewidth=2, label='10% Threshold')

        ax2.set_xlabel('Coalition Size', fontsize=12)
        ax2.set_ylabel('Collusion Gain (%)', fontsize=12)
        ax2.set_title('Gain vs Coalition Size', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_hypothesis_summary(
        self,
        results: Dict[str, AgentHypothesisResult],
        title: str = "Domain 5: Agent Behavior Hypothesis Results",
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
        effect_sizes = [results[h].effect_size if results[h].effect_size else 0 for h in hypotheses]

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
            'H5.1': 'Incentive Compatibility',
            'H5.2': 'Convergence (50 rounds)',
            'H5.3': 'Robustness (85% eff)',
            'H5.4': 'Manipulation (<5%)',
            'H5.5': 'Sybil Resistance',
            'H5.6': 'Collusion (<10%)',
        }

        for i, h in enumerate(hypotheses):
            desc = descriptions.get(h, h)
            ax1.text(1.02, i, desc, ha='left', va='center', fontsize=10)

        # P-values plot
        ax2 = axes[1]
        x = np.arange(len(hypotheses))
        width = 0.35

        bars1 = ax2.bar(x - width/2, p_values, width, label='P-Value',
                        color=self.colors['primary'], alpha=0.8)

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
        ic_result: Optional[ICTestResult] = None,
        price_series: Optional[np.ndarray] = None,
        equilibrium_price: float = 8.0,
        convergence_round: Optional[int] = None,
        efficiency_results: Optional[List[EfficiencyResult]] = None,
        manipulation_result: Optional[ManipulationTestResult] = None,
        sybil_result: Optional[SybilTestResult] = None,
        collusion_result: Optional[CollusionTestResult] = None,
        hypothesis_results: Optional[Dict[str, AgentHypothesisResult]] = None,
    ) -> Dict[str, str]:
        """
        Generate all visualization plots.

        Returns:
            Dictionary mapping plot names to file paths
        """
        plots = {}

        if ic_result is not None:
            plots['ic_scatter'] = self.plot_ic_scatter(ic_result)

        if price_series is not None:
            plots['convergence'] = self.plot_convergence(
                price_series, equilibrium_price, convergence_round
            )

        if efficiency_results is not None:
            plots['efficiency'] = self.plot_efficiency_by_composition(efficiency_results)

        if manipulation_result is not None:
            plots['manipulation'] = self.plot_manipulation_gains(manipulation_result)

        if sybil_result is not None:
            plots['sybil'] = self.plot_sybil_regression(sybil_result)

        if collusion_result is not None:
            plots['collusion'] = self.plot_collusion_sensitivity(collusion_result)

        if hypothesis_results is not None:
            plots['hypothesis_summary'] = self.plot_hypothesis_summary(hypothesis_results)

        return plots


def create_visualization_report(
    output_dir: str = "results/domain5_agents",
) -> AgentVisualization:
    """
    Factory function to create a visualization instance.

    Args:
        output_dir: Directory for saving plots

    Returns:
        AgentVisualization instance
    """
    return AgentVisualization(output_dir=output_dir)
