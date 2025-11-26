"""
Report Generator for V2G Marketplace.

Generates HTML, CSV, and JSON reports from simulation results.
Uses only standard library for data processing and matplotlib for charts.
"""

import base64
import csv
import io
import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

# Matplotlib imports for chart generation
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class ReportGenerator:
    """
    Generates reports from V2G marketplace simulation results.

    Supports multiple output formats:
    - HTML: Standalone HTML file with embedded charts
    - CSV: Tabular data export
    - JSON: Condensed summary metrics
    """

    def __init__(self):
        """Initialize the report generator."""
        self._chart_dpi = 100
        self._chart_figsize = (10, 4)

    def generate_html_report(self, results_dict: Dict[str, Any], output_path: str) -> None:
        """
        Generate a standalone HTML report with embedded charts.

        Args:
            results_dict: Simulation results dictionary containing clearing_results and metadata
            output_path: Path to save the HTML file
        """
        summary = self.generate_summary_json(results_dict)
        metadata = results_dict.get('metadata', {})
        clearing_results = results_dict.get('clearing_results', [])

        # Generate charts as base64 images
        price_chart = self._generate_price_time_series_chart(clearing_results)
        volume_chart = self._generate_volume_histogram_chart(clearing_results)
        token_chart = self._generate_token_price_chart(clearing_results)

        # Build HTML content
        html_content = self._build_html_document(
            summary=summary,
            metadata=metadata,
            clearing_results=clearing_results,
            price_chart=price_chart,
            volume_chart=volume_chart,
            token_chart=token_chart
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def generate_csv_export(self, results_dict: Dict[str, Any], output_path: str) -> None:
        """
        Generate CSV export with clearing results data.

        Creates CSV with columns:
        period, hour, day, price, volume, token_price, staking_rate

        Args:
            results_dict: Simulation results dictionary
            output_path: Path to save the CSV file
        """
        clearing_results = results_dict.get('clearing_results', [])

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                'period', 'hour', 'day', 'price', 'volume',
                'token_price', 'staking_rate'
            ])

            # Write data rows
            for i, result in enumerate(clearing_results):
                hour = result.get('hour_of_day', i % 24)
                day = i // 24 + 1
                price = result.get('clearing_price', 0)
                volume = result.get('total_volume_kwh', 0)

                # Calculate simulated token metrics based on market activity
                token_price = self._calculate_token_price(price, volume, i)
                staking_rate = self._calculate_staking_rate(price, volume, i)

                writer.writerow([
                    i + 1,  # period (1-indexed)
                    hour,
                    day,
                    round(price, 4),
                    round(volume, 4),
                    round(token_price, 6),
                    round(staking_rate, 4)
                ])

    def generate_summary_json(self, results_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate condensed summary metrics from results.

        Returns:
            Dictionary containing:
            - avg_price, min_price, max_price
            - total_volume, avg_daily_volume
            - price_volatility
            - final_token_price
            - total_welfare
        """
        clearing_results = results_dict.get('clearing_results', [])
        metadata = results_dict.get('metadata', {})

        if not clearing_results:
            return self._empty_summary()

        # Extract price and volume data
        prices = [r.get('clearing_price', 0) for r in clearing_results]
        volumes = [r.get('total_volume_kwh', 0) for r in clearing_results]

        # Filter out zero values for meaningful statistics
        valid_prices = [p for p in prices if p > 0]
        valid_volumes = [v for v in volumes if v > 0]

        # Price statistics
        avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0
        min_price = min(valid_prices) if valid_prices else 0
        max_price = max(valid_prices) if valid_prices else 0

        # Volume statistics
        total_volume = sum(volumes)
        num_days = metadata.get('num_days', max(1, len(clearing_results) // 24))
        avg_daily_volume = total_volume / num_days if num_days > 0 else 0

        # Price volatility (standard deviation)
        if len(valid_prices) > 1:
            variance = sum((p - avg_price) ** 2 for p in valid_prices) / len(valid_prices)
            price_volatility = math.sqrt(variance)
        else:
            price_volatility = 0

        # Token price calculation (simulated based on market dynamics)
        final_token_price = self._calculate_token_price(
            avg_price,
            avg_daily_volume / 24 if avg_daily_volume > 0 else 0,
            len(clearing_results) - 1
        )

        # Welfare calculation (consumer + producer surplus approximation)
        total_welfare = self._calculate_total_welfare(clearing_results)

        return {
            'avg_price': round(avg_price, 4),
            'min_price': round(min_price, 4),
            'max_price': round(max_price, 4),
            'total_volume': round(total_volume, 4),
            'avg_daily_volume': round(avg_daily_volume, 4),
            'price_volatility': round(price_volatility, 4),
            'final_token_price': round(final_token_price, 6),
            'total_welfare': round(total_welfare, 4)
        }

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            'avg_price': 0,
            'min_price': 0,
            'max_price': 0,
            'total_volume': 0,
            'avg_daily_volume': 0,
            'price_volatility': 0,
            'final_token_price': 0,
            'total_welfare': 0
        }

    def _calculate_token_price(self, price: float, volume: float, period: int) -> float:
        """
        Calculate simulated token price based on market activity.

        Token price is modeled as a function of:
        - Base price derived from energy price
        - Volume-weighted activity factor
        - Time-based appreciation
        """
        base_token_value = 1.0  # Starting token value in INR

        # Price influence: higher energy prices increase token demand
        price_factor = 1 + (price / 100) * 0.1  # 10% increase per 100 INR

        # Volume influence: higher volumes indicate more network activity
        volume_factor = 1 + math.log1p(volume) * 0.01

        # Time-based appreciation (small daily increase)
        time_factor = 1 + (period / 24) * 0.001  # 0.1% daily appreciation

        return base_token_value * price_factor * volume_factor * time_factor

    def _calculate_staking_rate(self, price: float, volume: float, period: int) -> float:
        """
        Calculate simulated staking rate based on market conditions.

        Staking rate varies with market activity and price levels.
        """
        base_rate = 5.0  # 5% base APY

        # Higher prices incentivize staking
        price_bonus = min(price / 50, 3.0)  # Up to 3% bonus

        # Higher volume provides more fee rewards
        volume_bonus = min(math.log1p(volume) * 0.5, 2.0)  # Up to 2% bonus

        return base_rate + price_bonus + volume_bonus

    def _calculate_total_welfare(self, clearing_results: List[Dict]) -> float:
        """
        Calculate total market welfare (consumer + producer surplus).

        Approximated as the sum of:
        - Volume * price spread from baseline for each period
        """
        if not clearing_results:
            return 0

        # Calculate baseline price (off-peak average)
        offpeak_prices = [
            r.get('clearing_price', 0)
            for r in clearing_results
            if not r.get('is_peak_hour', False) and r.get('clearing_price', 0) > 0
        ]
        baseline_price = sum(offpeak_prices) / len(offpeak_prices) if offpeak_prices else 5.0

        total_welfare = 0
        for result in clearing_results:
            price = result.get('clearing_price', 0)
            volume = result.get('total_volume_kwh', 0)

            if volume > 0:
                # Welfare approximation: surplus from trade
                # Sellers gain when price > their cost, buyers gain when price < their valuation
                price_spread = abs(price - baseline_price)
                welfare_contribution = volume * price_spread * 0.5
                total_welfare += welfare_contribution

        return total_welfare

    def _generate_price_time_series_chart(self, clearing_results: List[Dict]) -> Optional[str]:
        """Generate price time series chart as base64 PNG."""
        if not MATPLOTLIB_AVAILABLE or not clearing_results:
            return None

        try:
            fig, ax = plt.subplots(figsize=self._chart_figsize, dpi=self._chart_dpi)

            periods = list(range(len(clearing_results)))
            prices = [r.get('clearing_price', 0) for r in clearing_results]

            # Identify peak hours for coloring
            colors = ['#e74c3c' if r.get('is_peak_hour', False) else '#3498db'
                     for r in clearing_results]

            ax.scatter(periods, prices, c=colors, alpha=0.6, s=20)
            ax.plot(periods, prices, color='#2c3e50', alpha=0.7, linewidth=1)

            ax.set_xlabel('Period (Hours)', fontsize=10)
            ax.set_ylabel('Clearing Price (INR/kWh)', fontsize=10)
            ax.set_title('Energy Price Time Series', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)

            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#e74c3c', label='Peak Hours'),
                Patch(facecolor='#3498db', label='Off-Peak Hours')
            ]
            ax.legend(handles=legend_elements, loc='upper right')

            plt.tight_layout()
            return self._fig_to_base64(fig)
        except Exception:
            return None
        finally:
            plt.close('all')

    def _generate_volume_histogram_chart(self, clearing_results: List[Dict]) -> Optional[str]:
        """Generate volume histogram chart as base64 PNG."""
        if not MATPLOTLIB_AVAILABLE or not clearing_results:
            return None

        try:
            fig, ax = plt.subplots(figsize=self._chart_figsize, dpi=self._chart_dpi)

            volumes = [r.get('total_volume_kwh', 0) for r in clearing_results]
            valid_volumes = [v for v in volumes if v > 0]

            if not valid_volumes:
                plt.close(fig)
                return None

            ax.hist(valid_volumes, bins=30, color='#27ae60', edgecolor='#1e8449', alpha=0.7)
            ax.set_xlabel('Volume (kWh)', fontsize=10)
            ax.set_ylabel('Frequency', fontsize=10)
            ax.set_title('Trading Volume Distribution', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')

            # Add statistics annotation
            mean_vol = sum(valid_volumes) / len(valid_volumes)
            ax.axvline(mean_vol, color='#c0392b', linestyle='--', linewidth=2, label=f'Mean: {mean_vol:.1f} kWh')
            ax.legend()

            plt.tight_layout()
            return self._fig_to_base64(fig)
        except Exception:
            return None
        finally:
            plt.close('all')

    def _generate_token_price_chart(self, clearing_results: List[Dict]) -> Optional[str]:
        """Generate token price evolution chart as base64 PNG."""
        if not MATPLOTLIB_AVAILABLE or not clearing_results:
            return None

        try:
            fig, ax = plt.subplots(figsize=self._chart_figsize, dpi=self._chart_dpi)

            periods = list(range(len(clearing_results)))
            token_prices = []
            staking_rates = []

            for i, result in enumerate(clearing_results):
                price = result.get('clearing_price', 0)
                volume = result.get('total_volume_kwh', 0)
                token_prices.append(self._calculate_token_price(price, volume, i))
                staking_rates.append(self._calculate_staking_rate(price, volume, i))

            # Primary axis: token price
            color1 = '#9b59b6'
            ax.plot(periods, token_prices, color=color1, linewidth=2, label='Token Price')
            ax.fill_between(periods, token_prices, alpha=0.3, color=color1)
            ax.set_xlabel('Period (Hours)', fontsize=10)
            ax.set_ylabel('Token Price (INR)', fontsize=10, color=color1)
            ax.tick_params(axis='y', labelcolor=color1)

            # Secondary axis: staking rate
            ax2 = ax.twinx()
            color2 = '#f39c12'
            ax2.plot(periods, staking_rates, color=color2, linewidth=2, linestyle='--', label='Staking Rate')
            ax2.set_ylabel('Staking Rate (% APY)', fontsize=10, color=color2)
            ax2.tick_params(axis='y', labelcolor=color2)

            ax.set_title('Token Economics Evolution', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)

            # Combined legend
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

            plt.tight_layout()
            return self._fig_to_base64(fig)
        except Exception:
            return None
        finally:
            plt.close('all')

    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 encoded PNG."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def _build_html_document(
        self,
        summary: Dict[str, Any],
        metadata: Dict[str, Any],
        clearing_results: List[Dict],
        price_chart: Optional[str],
        volume_chart: Optional[str],
        token_chart: Optional[str]
    ) -> str:
        """Build the complete HTML document."""

        # Calculate additional statistics for the report
        peak_results = [r for r in clearing_results if r.get('is_peak_hour', False)]
        offpeak_results = [r for r in clearing_results if not r.get('is_peak_hour', False)]

        avg_peak_price = (sum(r.get('clearing_price', 0) for r in peak_results) / len(peak_results)) if peak_results else 0
        avg_offpeak_price = (sum(r.get('clearing_price', 0) for r in offpeak_results) / len(offpeak_results)) if offpeak_results else 0

        total_bids = sum(r.get('num_bids_matched', 0) for r in clearing_results)
        total_asks = sum(r.get('num_asks_matched', 0) for r in clearing_results)

        generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Build chart sections
        price_chart_html = f'<img src="data:image/png;base64,{price_chart}" alt="Price Time Series">' if price_chart else '<p class="no-chart">Chart not available (matplotlib required)</p>'
        volume_chart_html = f'<img src="data:image/png;base64,{volume_chart}" alt="Volume Histogram">' if volume_chart else '<p class="no-chart">Chart not available (matplotlib required)</p>'
        token_chart_html = f'<img src="data:image/png;base64,{token_chart}" alt="Token Price Evolution">' if token_chart else '<p class="no-chart">Chart not available (matplotlib required)</p>'

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V2G Marketplace Report</title>
    <style>
        :root {{
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --accent-color: #27ae60;
            --warning-color: #e74c3c;
            --background-color: #f8f9fa;
            --card-background: #ffffff;
            --text-color: #2c3e50;
            --border-color: #dee2e6;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: var(--background-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}

        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        header .subtitle {{
            opacity: 0.9;
            font-size: 1.1em;
        }}

        .meta-info {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}

        .meta-item {{
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 5px;
        }}

        .section {{
            background: var(--card-background);
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}

        .section h2 {{
            color: var(--primary-color);
            border-bottom: 3px solid var(--secondary-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .stat-card {{
            background: var(--background-color);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid var(--secondary-color);
        }}

        .stat-card.highlight {{
            border-left-color: var(--accent-color);
        }}

        .stat-card.warning {{
            border-left-color: var(--warning-color);
        }}

        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--primary-color);
        }}

        .stat-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}

        .chart-container {{
            text-align: center;
            margin: 20px 0;
        }}

        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .no-chart {{
            padding: 40px;
            background: var(--background-color);
            border-radius: 8px;
            color: #666;
            font-style: italic;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}

        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background: var(--primary-color);
            color: white;
            font-weight: 600;
        }}

        tr:nth-child(even) {{
            background: var(--background-color);
        }}

        tr:hover {{
            background: #e8f4f8;
        }}

        .peak-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 600;
        }}

        .peak-badge.peak {{
            background: #ffeaea;
            color: var(--warning-color);
        }}

        .peak-badge.offpeak {{
            background: #e8f8f5;
            color: var(--accent-color);
        }}

        footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            header h1 {{
                font-size: 1.8em;
            }}

            .meta-info {{
                flex-direction: column;
                align-items: center;
            }}

            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>V2G Marketplace Report</h1>
            <p class="subtitle">Vehicle-to-Grid Energy Trading Simulation Analysis</p>
            <div class="meta-info">
                <div class="meta-item">
                    <strong>Agents:</strong> {metadata.get('num_agents', 'N/A')}
                </div>
                <div class="meta-item">
                    <strong>Duration:</strong> {metadata.get('num_days', 'N/A')} days
                </div>
                <div class="meta-item">
                    <strong>Intervals:</strong> {metadata.get('total_intervals', len(clearing_results))}
                </div>
                <div class="meta-item">
                    <strong>Generated:</strong> {generation_time}
                </div>
            </div>
        </header>

        <section class="section">
            <h2>Summary Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card highlight">
                    <div class="stat-value">{summary['avg_price']:.2f}</div>
                    <div class="stat-label">Avg Price (INR/kWh)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary['min_price']:.2f}</div>
                    <div class="stat-label">Min Price (INR/kWh)</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-value">{summary['max_price']:.2f}</div>
                    <div class="stat-label">Max Price (INR/kWh)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary['price_volatility']:.2f}</div>
                    <div class="stat-label">Price Volatility (Std Dev)</div>
                </div>
                <div class="stat-card highlight">
                    <div class="stat-value">{summary['total_volume']:,.0f}</div>
                    <div class="stat-label">Total Volume (kWh)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary['avg_daily_volume']:,.0f}</div>
                    <div class="stat-label">Avg Daily Volume (kWh)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary['final_token_price']:.4f}</div>
                    <div class="stat-label">Final Token Price (INR)</div>
                </div>
                <div class="stat-card highlight">
                    <div class="stat-value">{summary['total_welfare']:,.0f}</div>
                    <div class="stat-label">Total Welfare (INR)</div>
                </div>
            </div>
        </section>

        <section class="section">
            <h2>Peak vs Off-Peak Analysis</h2>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Peak Hours (6PM-10PM)</th>
                        <th>Off-Peak Hours</th>
                        <th>Difference</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Average Price (INR/kWh)</td>
                        <td>{avg_peak_price:.2f}</td>
                        <td>{avg_offpeak_price:.2f}</td>
                        <td>{avg_peak_price - avg_offpeak_price:+.2f}</td>
                    </tr>
                    <tr>
                        <td>Number of Periods</td>
                        <td>{len(peak_results)}</td>
                        <td>{len(offpeak_results)}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>Total Bids Matched</td>
                        <td colspan="3" style="text-align: center;">{total_bids}</td>
                    </tr>
                    <tr>
                        <td>Total Asks Matched</td>
                        <td colspan="3" style="text-align: center;">{total_asks}</td>
                    </tr>
                </tbody>
            </table>
        </section>

        <section class="section">
            <h2>Price Time Series</h2>
            <div class="chart-container">
                {price_chart_html}
            </div>
            <p style="text-align: center; color: #666; margin-top: 10px;">
                Red points indicate peak hours, blue points indicate off-peak hours
            </p>
        </section>

        <section class="section">
            <h2>Volume Distribution</h2>
            <div class="chart-container">
                {volume_chart_html}
            </div>
        </section>

        <section class="section">
            <h2>Token Price Evolution</h2>
            <div class="chart-container">
                {token_chart_html}
            </div>
            <p style="text-align: center; color: #666; margin-top: 10px;">
                Token price and staking rate are simulated based on market activity
            </p>
        </section>

        <footer>
            <p>Generated by V2G Marketplace Report Generator</p>
            <p>ShaktiChain - Decentralized Energy Trading Platform</p>
        </footer>
    </div>
</body>
</html>'''

        return html
