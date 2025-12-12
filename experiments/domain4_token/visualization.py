"""
Domain 4: Token Economics Visualization Module

Generates plots for token economics analysis:
1. Token supply over time (line plot)
2. Daily mint vs burn volumes (dual bar chart)
3. Velocity: actual vs predicted (scatter with regression line)
4. Redemption rate distribution (histogram with target marked)
5. Inflation rate over time (line plot with 10% threshold)
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .token_supply_tracker import TokenSupplyTracker, TokenSupplySnapshot
from .mint_burn_analyzer import MintBurnAnalyzer, DailyMintBurnStats
from .velocity_calculator import VelocityCalculator, VelocityMeasurement
from .peg_stability_tester import PegStabilityTester, RedemptionEvent
from .inflation_monitor import InflationMonitor, InflationMeasurement
from .hypothesis_tests import TokenHypothesisTester, TokenHypothesisResult


class TokenVisualization:
    """Generates visualizations for token economics experiments."""

    def __init__(self, output_dir: str = "results/domain4_token"):
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
            'mint': '#28A745',
            'burn': '#DC3545',
            'actual': '#2E86AB',
            'predicted': '#A23B72',
            'threshold': '#DC3545',
            'target': '#28A745'
        }

    def plot_supply_over_time(
        self,
        snapshots: List[TokenSupplySnapshot],
        title: str = "Token Supply Over Time",
        filename: str = "supply_over_time.png",
        show_cv_windows: bool = True,
        window_days: int = 30
    ) -> str:
        """
        Plot token supply over time with optional CV window highlights.

        Args:
            snapshots: List of supply snapshots
            title: Plot title
            filename: Output filename
            show_cv_windows: Whether to highlight 30-day CV windows
            window_days: CV calculation window size

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])

        timestamps = [s.timestamp for s in snapshots]
        supplies = [s.total_supply for s in snapshots]

        # Main supply plot
        ax1 = axes[0]
        ax1.plot(timestamps, supplies, color=self.colors['primary'],
                linewidth=2, label='Total Supply')
        ax1.fill_between(timestamps, supplies, alpha=0.3, color=self.colors['primary'])

        # Add mean line
        mean_supply = np.mean(supplies)
        ax1.axhline(y=mean_supply, color=self.colors['secondary'],
                   linestyle='--', linewidth=1.5, label=f'Mean: {mean_supply:,.0f}')

        # Add ±5% CV bounds
        cv_lower = mean_supply * 0.95
        cv_upper = mean_supply * 1.05
        ax1.axhline(y=cv_lower, color=self.colors['warning'],
                   linestyle=':', linewidth=1, alpha=0.7)
        ax1.axhline(y=cv_upper, color=self.colors['warning'],
                   linestyle=':', linewidth=1, alpha=0.7, label='±5% CV bounds')
        ax1.fill_between(timestamps, cv_lower, cv_upper, alpha=0.1, color=self.colors['warning'])

        ax1.set_xlabel('Time', fontsize=12)
        ax1.set_ylabel('Total Supply (SHAKTI)', fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

        # Format y-axis with comma separators
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

        # Rolling CV plot
        ax2 = axes[1]
        if len(snapshots) >= window_days:
            cv_values = []
            cv_dates = []
            for i in range(window_days, len(snapshots) + 1):
                window_supplies = [s.total_supply for s in snapshots[i-window_days:i]]
                cv = np.std(window_supplies) / np.mean(window_supplies)
                cv_values.append(cv * 100)  # Convert to percentage
                cv_dates.append(snapshots[i-1].timestamp)

            ax2.plot(cv_dates, cv_values, color=self.colors['secondary'],
                    linewidth=2, label=f'{window_days}-day Rolling CV')
            ax2.axhline(y=5.0, color=self.colors['danger'], linestyle='--',
                       linewidth=2, label='5% Threshold (H4.1)')
            ax2.fill_between(cv_dates, cv_values, alpha=0.3, color=self.colors['secondary'])

            ax2.set_xlabel('Time', fontsize=12)
            ax2.set_ylabel('Coefficient of Variation (%)', fontsize=12)
            ax2.set_title(f'{window_days}-Day Rolling CV', fontsize=12)
            ax2.legend(loc='upper right')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, max(max(cv_values) * 1.2, 6))

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_mint_burn_volumes(
        self,
        daily_stats: List[DailyMintBurnStats],
        title: str = "Daily Mint vs Burn Volumes",
        filename: str = "mint_burn_volumes.png"
    ) -> str:
        """
        Plot daily mint and burn volumes as dual bar chart.

        Args:
            daily_stats: List of daily mint/burn statistics
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])

        dates = [s.date for s in daily_stats]
        mint_volumes = [s.mint_volume for s in daily_stats]
        burn_volumes = [s.burn_volume for s in daily_stats]
        net_changes = [s.net_change for s in daily_stats]

        x = np.arange(len(dates))
        width = 0.35

        # Dual bar chart
        ax1 = axes[0]
        bars1 = ax1.bar(x - width/2, mint_volumes, width, label='Mint Volume',
                       color=self.colors['mint'], alpha=0.8)
        bars2 = ax1.bar(x + width/2, burn_volumes, width, label='Burn Volume',
                       color=self.colors['burn'], alpha=0.8)

        ax1.set_xlabel('Date', fontsize=12)
        ax1.set_ylabel('Volume (SHAKTI)', fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3, axis='y')

        # Format x-axis - show subset of dates
        step = max(1, len(dates) // 10)
        ax1.set_xticks(x[::step])
        # dates are already strings in YYYY-MM-DD format
        ax1.set_xticklabels([d[5:] for d in dates[::step]], rotation=45)  # Extract MM-DD portion

        # Net change plot
        ax2 = axes[1]
        colors = [self.colors['mint'] if nc >= 0 else self.colors['burn'] for nc in net_changes]
        ax2.bar(x, net_changes, color=colors, alpha=0.8)
        ax2.axhline(y=0, color='black', linewidth=1)

        # Add equilibrium bands (±10%)
        mean_volume = np.mean([(m + b) / 2 for m, b in zip(mint_volumes, burn_volumes)])
        equilibrium_band = mean_volume * 0.1
        ax2.axhline(y=equilibrium_band, color=self.colors['warning'],
                   linestyle='--', linewidth=1.5, alpha=0.7)
        ax2.axhline(y=-equilibrium_band, color=self.colors['warning'],
                   linestyle='--', linewidth=1.5, alpha=0.7, label='±10% Equilibrium Band')

        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Net Change (SHAKTI)', fontsize=12)
        ax2.set_title('Net Supply Change (Mint - Burn)', fontsize=12)
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3, axis='y')

        ax2.set_xticks(x[::step])
        ax2.set_xticklabels([d[5:] for d in dates[::step]], rotation=45)

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_velocity_comparison(
        self,
        measurements: List[VelocityMeasurement],
        title: str = "Token Velocity: Actual vs Predicted (Fisher Equation)",
        filename: str = "velocity_comparison.png"
    ) -> str:
        """
        Plot actual vs predicted velocity with regression line.

        Args:
            measurements: List of velocity measurements
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        actual = [m.actual_velocity for m in measurements]
        predicted = [m.predicted_velocity for m in measurements]
        timestamps = [m.period_end for m in measurements]

        # Scatter plot with regression
        ax1 = axes[0]
        ax1.scatter(predicted, actual, color=self.colors['primary'],
                   alpha=0.6, s=50, label='Observations')

        # Perfect prediction line
        min_val = min(min(predicted), min(actual))
        max_val = max(max(predicted), max(actual))
        ax1.plot([min_val, max_val], [min_val, max_val],
                color=self.colors['target'], linestyle='--',
                linewidth=2, label='Perfect Prediction (y=x)')

        # Regression line
        z = np.polyfit(predicted, actual, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min_val, max_val, 100)
        ax1.plot(x_line, p(x_line), color=self.colors['secondary'],
                linewidth=2, label=f'Regression: y={z[0]:.3f}x+{z[1]:.3f}')

        # ±20% tolerance bands
        ax1.fill_between(x_line, x_line * 0.8, x_line * 1.2,
                        alpha=0.2, color=self.colors['warning'], label='±20% Tolerance')

        ax1.set_xlabel('Predicted Velocity (V = PQ/M)', fontsize=12)
        ax1.set_ylabel('Actual Velocity', fontsize=12)
        ax1.set_title('Actual vs Predicted Velocity', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # R-squared annotation
        correlation = np.corrcoef(predicted, actual)[0, 1]
        r_squared = correlation ** 2
        ax1.annotate(f'R² = {r_squared:.4f}', xy=(0.95, 0.05),
                    xycoords='axes fraction', fontsize=11,
                    ha='right', va='bottom',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Time series comparison
        ax2 = axes[1]
        ax2.plot(timestamps, actual, color=self.colors['actual'],
                linewidth=2, label='Actual Velocity', marker='o', markersize=4)
        ax2.plot(timestamps, predicted, color=self.colors['predicted'],
                linewidth=2, label='Predicted Velocity', marker='s', markersize=4)

        ax2.set_xlabel('Time', fontsize=12)
        ax2.set_ylabel('Velocity', fontsize=12)
        ax2.set_title('Velocity Over Time', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_redemption_distribution(
        self,
        events: List[RedemptionEvent],
        title: str = "Redemption Rate Distribution",
        filename: str = "redemption_distribution.png"
    ) -> str:
        """
        Plot redemption rate distribution histogram with target marked.

        Args:
            events: List of redemption events
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        rates = [e.exchange_rate for e in events]

        # Histogram
        ax1 = axes[0]
        n, bins, patches = ax1.hist(rates, bins=50, color=self.colors['primary'],
                                    alpha=0.7, edgecolor='white', density=True)

        # Color bars based on tolerance
        for i, (patch, bin_val) in enumerate(zip(patches, bins[:-1])):
            if 0.99 <= bin_val <= 1.01:
                patch.set_facecolor(self.colors['success'])
            elif 0.98 <= bin_val <= 1.02:
                patch.set_facecolor(self.colors['warning'])
            else:
                patch.set_facecolor(self.colors['danger'])

        # Target line
        ax1.axvline(x=1.0, color=self.colors['target'], linestyle='-',
                   linewidth=3, label='Target Rate (1.0)')

        # Tolerance bounds
        ax1.axvline(x=0.99, color=self.colors['warning'], linestyle='--',
                   linewidth=2, alpha=0.7)
        ax1.axvline(x=1.01, color=self.colors['warning'], linestyle='--',
                   linewidth=2, alpha=0.7, label='±1% Tolerance')

        # Fill tolerance region
        ax1.axvspan(0.99, 1.01, alpha=0.2, color=self.colors['success'], label='Acceptable Range')

        ax1.set_xlabel('Redemption Rate (SHAKTI/kWh)', fontsize=12)
        ax1.set_ylabel('Density', fontsize=12)
        ax1.set_title('Redemption Rate Distribution', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3, axis='y')

        # Add statistics annotation
        mean_rate = np.mean(rates)
        std_rate = np.std(rates)
        within_tolerance = sum(1 for r in rates if 0.99 <= r <= 1.01) / len(rates) * 100

        stats_text = f'Mean: {mean_rate:.4f}\nStd: {std_rate:.4f}\nWithin ±1%: {within_tolerance:.1f}%'
        ax1.annotate(stats_text, xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=10, va='top', ha='left',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Time series of rates
        ax2 = axes[1]
        timestamps = [e.timestamp for e in events]
        ax2.scatter(timestamps, rates, c=self.colors['primary'], alpha=0.5, s=20)

        # Rolling mean
        window = min(50, len(rates) // 10 + 1)
        if len(rates) >= window:
            rolling_mean = np.convolve(rates, np.ones(window)/window, mode='valid')
            rolling_timestamps = timestamps[window-1:]
            ax2.plot(rolling_timestamps, rolling_mean, color=self.colors['secondary'],
                    linewidth=2, label=f'{window}-point Rolling Mean')

        ax2.axhline(y=1.0, color=self.colors['target'], linestyle='-', linewidth=2)
        ax2.axhline(y=0.99, color=self.colors['warning'], linestyle='--', linewidth=1.5)
        ax2.axhline(y=1.01, color=self.colors['warning'], linestyle='--', linewidth=1.5)
        ax2.fill_between(timestamps, 0.99, 1.01, alpha=0.2, color=self.colors['success'])

        ax2.set_xlabel('Time', fontsize=12)
        ax2.set_ylabel('Redemption Rate', fontsize=12)
        ax2.set_title('Redemption Rate Over Time', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_inflation_over_time(
        self,
        measurements: List[InflationMeasurement],
        title: str = "Inflation Rate Over Time",
        filename: str = "inflation_over_time.png",
        threshold: float = 0.10
    ) -> str:
        """
        Plot inflation rate over time with threshold line.

        Args:
            measurements: List of inflation measurements
            title: Plot title
            filename: Output filename
            threshold: Hyperinflation threshold (default 10%)

        Returns:
            Path to saved figure
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])

        timestamps = [m.period_end for m in measurements]
        annualized_rates = [m.annualized_rate * 100 for m in measurements]  # Convert to %
        supplies = [m.end_supply for m in measurements]

        # Annualized inflation rate
        ax1 = axes[0]
        ax1.plot(timestamps, annualized_rates, color=self.colors['primary'],
                linewidth=2, label='Annualized Inflation Rate')
        ax1.fill_between(timestamps, annualized_rates, alpha=0.3, color=self.colors['primary'])

        # Threshold line
        threshold_pct = threshold * 100
        ax1.axhline(y=threshold_pct, color=self.colors['danger'], linestyle='--',
                   linewidth=2, label=f'{threshold_pct:.0f}% Threshold (H4.5)')
        ax1.axhline(y=0, color='black', linewidth=1)

        # Color regions
        ax1.fill_between(timestamps, 0, threshold_pct, alpha=0.1, color=self.colors['success'])
        ax1.fill_between(timestamps, threshold_pct, max(max(annualized_rates), threshold_pct + 5),
                        alpha=0.1, color=self.colors['danger'])

        ax1.set_xlabel('Time', fontsize=12)
        ax1.set_ylabel('Annualized Inflation Rate (%)', fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

        # Statistics
        mean_inflation = np.mean(annualized_rates)
        max_inflation = max(annualized_rates)
        days_above = sum(1 for r in annualized_rates if r > threshold_pct)

        stats_text = f'Mean: {mean_inflation:.2f}%\nMax: {max_inflation:.2f}%\nDays > {threshold_pct:.0f}%: {days_above}'
        ax1.annotate(stats_text, xy=(0.02, 0.98), xycoords='axes fraction',
                    fontsize=10, va='top', ha='left',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Supply over time (secondary)
        ax2 = axes[1]
        ax2.plot(timestamps, supplies, color=self.colors['secondary'], linewidth=2)
        ax2.fill_between(timestamps, supplies, alpha=0.3, color=self.colors['secondary'])

        # Initial supply reference
        initial_supply = supplies[0]
        ax2.axhline(y=initial_supply, color=self.colors['target'], linestyle='--',
                   linewidth=1.5, label=f'Initial Supply: {initial_supply:,.0f}')
        ax2.axhline(y=initial_supply * (1 + threshold), color=self.colors['danger'],
                   linestyle=':', linewidth=1.5, label=f'+{threshold_pct:.0f}% Annual Target')

        ax2.set_xlabel('Time', fontsize=12)
        ax2.set_ylabel('Total Supply (SHAKTI)', fontsize=12)
        ax2.set_title('Token Supply Growth', fontsize=12)
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.3)
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

        plt.tight_layout()
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def plot_hypothesis_summary(
        self,
        results: Dict[str, TokenHypothesisResult],
        title: str = "Domain 4: Token Economics Hypothesis Results",
        filename: str = "hypothesis_summary.png"
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
        p_values = [results[h].p_value if results[h].p_value else 0 for h in hypotheses]
        effect_sizes = [results[h].effect_size if results[h].effect_size else 0 for h in hypotheses]

        # Pass/Fail bar chart
        ax1 = axes[0]
        colors = [self.colors['success'] if p else self.colors['danger'] for p in passed]
        bars = ax1.barh(hypotheses, [1] * len(hypotheses), color=colors, alpha=0.8)

        # Add pass/fail labels
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
            'H4.1': 'Supply Stability (CV < 5%)',
            'H4.2': 'Mint-Burn Equilibrium',
            'H4.3': 'Velocity Prediction',
            'H4.4': 'Peg Stability (±1%)',
            'H4.5': 'No Hyperinflation'
        }

        for i, h in enumerate(hypotheses):
            desc = descriptions.get(h, h)
            ax1.text(1.02, i, desc, ha='left', va='center', fontsize=10)

        # P-value and Effect Size comparison
        ax2 = axes[1]
        x = np.arange(len(hypotheses))
        width = 0.35

        # Normalize effect sizes for visualization
        max_effect = max(effect_sizes) if max(effect_sizes) > 0 else 1
        normalized_effects = [e / max_effect for e in effect_sizes]

        bars1 = ax2.bar(x - width/2, p_values, width, label='P-Value',
                       color=self.colors['primary'], alpha=0.8)
        bars2 = ax2.bar(x + width/2, normalized_effects, width, label='Effect Size (normalized)',
                       color=self.colors['secondary'], alpha=0.8)

        # Significance threshold
        ax2.axhline(y=0.05, color=self.colors['danger'], linestyle='--',
                   linewidth=2, label='α = 0.05')

        ax2.set_xlabel('Hypothesis', fontsize=12)
        ax2.set_ylabel('Value', fontsize=12)
        ax2.set_title('P-Values and Effect Sizes', fontsize=12, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(hypotheses)
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3, axis='y')

        # Summary statistics
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
        supply_tracker: TokenSupplyTracker,
        mint_burn_analyzer: MintBurnAnalyzer,
        velocity_calculator: VelocityCalculator,
        peg_tester: PegStabilityTester,
        inflation_monitor: InflationMonitor,
        hypothesis_results: Optional[Dict[str, TokenHypothesisResult]] = None
    ) -> Dict[str, str]:
        """
        Generate all visualization plots.

        Args:
            supply_tracker: Tracker with supply data
            mint_burn_analyzer: Analyzer with mint/burn data
            velocity_calculator: Calculator with velocity data
            peg_tester: Tester with redemption data
            inflation_monitor: Monitor with inflation data
            hypothesis_results: Optional hypothesis test results

        Returns:
            Dictionary mapping plot names to file paths
        """
        plots = {}

        # Supply over time
        if supply_tracker.snapshots:
            plots['supply'] = self.plot_supply_over_time(supply_tracker.snapshots)

        # Mint/burn volumes
        if mint_burn_analyzer.daily_stats:
            plots['mint_burn'] = self.plot_mint_burn_volumes(mint_burn_analyzer.daily_stats)

        # Velocity comparison
        if velocity_calculator.measurements:
            plots['velocity'] = self.plot_velocity_comparison(velocity_calculator.measurements)

        # Redemption distribution
        if peg_tester.events:
            plots['redemption'] = self.plot_redemption_distribution(peg_tester.events)

        # Inflation over time
        if inflation_monitor.measurements:
            plots['inflation'] = self.plot_inflation_over_time(inflation_monitor.measurements)

        # Hypothesis summary
        if hypothesis_results:
            plots['hypothesis_summary'] = self.plot_hypothesis_summary(hypothesis_results)

        return plots


def create_visualization_report(
    output_dir: str = "results/domain4_token"
) -> TokenVisualization:
    """
    Factory function to create a visualization instance.

    Args:
        output_dir: Directory for saving plots

    Returns:
        TokenVisualization instance
    """
    return TokenVisualization(output_dir=output_dir)
