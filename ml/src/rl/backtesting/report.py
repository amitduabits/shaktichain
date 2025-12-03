"""Report generator for backtesting results.

Generates comprehensive markdown reports with:
- Executive summary
- Performance metrics
- Statistical analysis
- Visualizations
- Recommendations
"""

import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import logging

from .backtester import BacktestRun
from .metrics import PerformanceMetrics
from .statistics import BootstrapCI, StatisticalTests, MonteCarloSimulation

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate comprehensive backtest reports in Markdown format."""

    def __init__(
        self,
        strategy_run: BacktestRun,
        baseline_runs: Optional[Dict[str, BacktestRun]] = None,
        strategy_name: str = "PPO Trading Agent",
    ):
        """Initialize report generator.

        Args:
            strategy_run: Main strategy backtest results
            baseline_runs: Dictionary of baseline results
            strategy_name: Name of the strategy
        """
        self.strategy_run = strategy_run
        self.baseline_runs = baseline_runs or {}
        self.strategy_name = strategy_name

        # Calculate metrics
        self.metrics = PerformanceMetrics(strategy_run)
        self.all_metrics = self.metrics.calculate_all()

        # Calculate baseline metrics
        self.baseline_metrics = {}
        for name, run in self.baseline_runs.items():
            self.baseline_metrics[name] = PerformanceMetrics(run).calculate_all()

    def generate_report(
        self,
        output_path: str = "backtest_report.md",
        include_plots: bool = True,
        plot_dir: str = "./plots",
    ) -> str:
        """Generate complete markdown report.

        Args:
            output_path: Path to save report
            include_plots: Whether to include plot references
            plot_dir: Directory containing plots

        Returns:
            Report content as string
        """
        sections = [
            self._generate_header(),
            self._generate_executive_summary(),
            self._generate_return_metrics(),
            self._generate_trading_metrics(),
            self._generate_risk_metrics(),
            self._generate_operational_metrics(),
            self._generate_baseline_comparison(),
            self._generate_statistical_analysis(),
            self._generate_monte_carlo_analysis(),
        ]

        if include_plots:
            sections.append(self._generate_visualizations(plot_dir))

        sections.extend([
            self._generate_recommendations(),
            self._generate_appendix(),
        ])

        report = "\n\n".join(sections)

        # Save report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"Report saved to {output_path}")
        return report

    def _generate_header(self) -> str:
        """Generate report header."""
        return f"""# SHAKTI-CHAIN V2G Trading Backtest Report

**Strategy:** {self.strategy_name}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Backtest Period:** {self.strategy_run.start_date.strftime('%Y-%m-%d')} to {self.strategy_run.end_date.strftime('%Y-%m-%d')}
**Total Days:** {self.strategy_run.total_days}

---"""

    def _generate_executive_summary(self) -> str:
        """Generate executive summary."""
        returns = self.all_metrics['returns']
        trading = self.all_metrics['trading']
        risk = self.all_metrics['risk']

        # Determine overall assessment
        roi_target = 15.0
        roi_achieved = returns.total_return
        target_met = roi_achieved >= roi_target

        status_emoji = "✅" if target_met else "⚠️"
        status_text = "TARGET ACHIEVED" if target_met else "TARGET NOT MET"

        # Best baseline comparison
        best_baseline = None
        best_baseline_roi = float('-inf')
        for name, metrics in self.baseline_metrics.items():
            if metrics['returns'].total_return > best_baseline_roi:
                best_baseline_roi = metrics['returns'].total_return
                best_baseline = name

        outperformance = roi_achieved - best_baseline_roi if best_baseline else roi_achieved

        return f"""## Executive Summary

### Performance Overview

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Total Return** | {roi_achieved:.2f}% | {roi_target:.0f}% | {status_emoji} {status_text} |
| **Sharpe Ratio** | {returns.sharpe_ratio:.2f} | >1.0 | {'✅' if returns.sharpe_ratio > 1 else '⚠️'} |
| **Win Rate** | {trading.win_rate*100:.1f}% | >50% | {'✅' if trading.win_rate > 0.5 else '⚠️'} |
| **Max Drawdown** | {returns.max_drawdown:.2f}% | <-20% | {'✅' if returns.max_drawdown > -20 else '⚠️'} |

### Key Findings

- **Total Profit:** ₹{returns.total_profit:.2f} from initial ₹{self.strategy_run.config.initial_balance:.2f}
- **Trading Activity:** {trading.total_trades} trades over {self.strategy_run.total_days} days ({trading.trades_per_day:.1f}/day)
- **Risk-Adjusted Return:** Sortino Ratio of {returns.sortino_ratio:.2f}
- **Value at Risk (95%):** {risk.var_95:.2f}% daily
{f'- **Outperformance vs Best Baseline ({best_baseline}):** {outperformance:+.2f}%' if best_baseline else ''}

### Verdict

{self._generate_verdict(returns, trading, risk)}"""

    def _generate_verdict(self, returns, trading, risk) -> str:
        """Generate overall verdict text."""
        score = 0
        comments = []

        if returns.total_return >= 15:
            score += 3
            comments.append("Excellent returns exceeding 15% target")
        elif returns.total_return >= 10:
            score += 2
            comments.append("Good returns above 10%")
        elif returns.total_return > 0:
            score += 1
            comments.append("Positive returns but below target")
        else:
            comments.append("Negative returns - strategy needs improvement")

        if returns.sharpe_ratio >= 1.5:
            score += 2
            comments.append("Strong risk-adjusted performance")
        elif returns.sharpe_ratio >= 1.0:
            score += 1
            comments.append("Acceptable risk-adjusted returns")

        if trading.win_rate >= 0.55:
            score += 1
            comments.append("Consistent winning trades")

        if returns.max_drawdown > -15:
            score += 1
            comments.append("Well-controlled drawdowns")

        if score >= 6:
            verdict = "**EXCELLENT** - Strategy is production-ready with strong risk-adjusted returns."
        elif score >= 4:
            verdict = "**GOOD** - Strategy shows promise but may benefit from optimization."
        elif score >= 2:
            verdict = "**MODERATE** - Strategy has potential but needs significant improvements."
        else:
            verdict = "**POOR** - Strategy requires fundamental redesign."

        return f"{verdict}\n\n" + "\n".join(f"- {c}" for c in comments)

    def _generate_return_metrics(self) -> str:
        """Generate return metrics section."""
        r = self.all_metrics['returns']

        return f"""## Return Metrics

### Absolute Returns

| Metric | Value |
|--------|-------|
| Total Return | {r.total_return:.2f}% |
| Total Profit | ₹{r.total_profit:.2f} |
| Annualized Return | {r.annualized_return:.2f}% |

### Daily Returns

| Metric | Value |
|--------|-------|
| Mean Daily Return | {r.daily_return_mean:.3f}% |
| Std Daily Return | {r.daily_return_std:.3f}% |
| Annualized Volatility | {r.annualized_volatility:.2f}% |

### Risk-Adjusted Returns

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Sharpe Ratio | {r.sharpe_ratio:.2f} | {'Excellent' if r.sharpe_ratio > 1.5 else 'Good' if r.sharpe_ratio > 1 else 'Acceptable' if r.sharpe_ratio > 0.5 else 'Poor'} |
| Sortino Ratio | {r.sortino_ratio:.2f} | {'Excellent' if r.sortino_ratio > 2 else 'Good' if r.sortino_ratio > 1 else 'Acceptable' if r.sortino_ratio > 0.5 else 'Poor'} |
| Calmar Ratio | {r.calmar_ratio:.2f} | {'Excellent' if r.calmar_ratio > 3 else 'Good' if r.calmar_ratio > 1 else 'Poor'} |
| Profit Factor | {r.profit_factor:.2f} | {'Excellent' if r.profit_factor > 2 else 'Good' if r.profit_factor > 1.5 else 'Acceptable' if r.profit_factor > 1 else 'Loss-making'} |

### Drawdown Analysis

| Metric | Value |
|--------|-------|
| Maximum Drawdown | {r.max_drawdown:.2f}% |
| Drawdown Duration | {r.max_drawdown_duration} days |
| Recovery Time | {r.recovery_time} days |"""

    def _generate_trading_metrics(self) -> str:
        """Generate trading metrics section."""
        t = self.all_metrics['trading']

        return f"""## Trading Metrics

### Trade Summary

| Metric | Value |
|--------|-------|
| Total Trades | {t.total_trades} |
| Buy Trades | {t.buy_trades} |
| Sell Trades | {t.sell_trades} |
| Trades per Day | {t.trades_per_day:.1f} |

### Win/Loss Analysis

| Metric | Value |
|--------|-------|
| Winning Trades | {t.win_trades} ({t.win_rate*100:.1f}%) |
| Losing Trades | {t.loss_trades} ({(1-t.win_rate)*100:.1f}%) |
| Win Rate | {t.win_rate*100:.1f}% |

### Profit Analysis

| Metric | Value |
|--------|-------|
| Average Profit/Trade | ₹{t.avg_profit_per_trade:.2f} |
| Average Win | ₹{t.avg_win:.2f} |
| Average Loss | ₹{t.avg_loss:.2f} |
| Largest Win | ₹{t.largest_win:.2f} |
| Largest Loss | ₹{t.largest_loss:.2f} |
| Profit Factor | {t.profit_factor:.2f} |

### Advanced Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| Expectancy | ₹{t.expectancy:.2f} | Expected profit per trade |
| Kelly Criterion | {t.kelly_criterion*100:.1f}% | Optimal position sizing |
| Avg Trade Duration | {t.avg_trade_duration:.1f}h | Time between trades |"""

    def _generate_risk_metrics(self) -> str:
        """Generate risk metrics section."""
        r = self.all_metrics['risk']

        return f"""## Risk Metrics

### Value at Risk (VaR)

| Confidence | Daily VaR | Interpretation |
|------------|-----------|----------------|
| 95% | {r.var_95:.2f}% | 95% of days, losses won't exceed this |
| 99% | {r.var_99:.2f}% | 99% of days, losses won't exceed this |

### Conditional VaR (Expected Shortfall)

| Confidence | CVaR | Interpretation |
|------------|------|----------------|
| 95% | {r.cvar_95:.2f}% | Average loss in worst 5% of days |
| 99% | {r.cvar_99:.2f}% | Average loss in worst 1% of days |

### Volatility Metrics

| Metric | Value |
|--------|-------|
| Daily Volatility | {r.daily_volatility:.2f}% |
| Downside Volatility | {r.downside_volatility:.2f}% |
| Tail Ratio | {r.tail_ratio:.2f} |

### Distribution Characteristics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Skewness | {r.skewness:.2f} | {'Positive (good)' if r.skewness > 0 else 'Negative (bad)'} |
| Kurtosis | {r.kurtosis:.2f} | {'Fat tails' if r.kurtosis > 0 else 'Thin tails'} |
| Max Consecutive Losses | {r.max_consecutive_losses} days | |
| Max Consecutive Wins | {r.max_consecutive_wins} days | |"""

    def _generate_operational_metrics(self) -> str:
        """Generate operational metrics section."""
        o = self.all_metrics['operational']

        return f"""## Operational Metrics

### Battery Utilization

| Metric | Value |
|--------|-------|
| Average SOC | {o.avg_soc*100:.1f}% |
| Min SOC | {o.min_soc*100:.1f}% |
| Max SOC | {o.max_soc*100:.1f}% |
| SOC Std Dev | {o.soc_std*100:.1f}% |

### Battery Cycling

| Metric | Value |
|--------|-------|
| Total Cycles | {o.total_battery_cycles:.2f} |
| Cycles per Day | {o.cycles_per_day:.2f} |
| Total Energy Traded | {o.total_energy_traded:.1f} kWh |
| Energy Efficiency | {o.energy_efficiency*100:.1f}% |

### Delivery Performance

| Metric | Value |
|--------|-------|
| Delivery Success Rate | {o.delivery_success_rate*100:.1f}% |
| Avg Charge Depth | {o.avg_charge_depth*100:.1f}% |
| Avg Discharge Depth | {o.avg_discharge_depth*100:.1f}% |"""

    def _generate_baseline_comparison(self) -> str:
        """Generate baseline comparison section."""
        if not self.baseline_metrics:
            return "## Baseline Comparison\n\n*No baselines provided for comparison.*"

        # Build comparison table
        headers = ["Strategy", "Return", "Sharpe", "Win Rate", "Max DD", "Trades"]
        rows = []

        # Add main strategy
        r = self.all_metrics['returns']
        t = self.all_metrics['trading']
        rows.append([
            f"**{self.strategy_name}**",
            f"{r.total_return:.2f}%",
            f"{r.sharpe_ratio:.2f}",
            f"{t.win_rate*100:.1f}%",
            f"{r.max_drawdown:.2f}%",
            str(t.total_trades),
        ])

        # Add baselines
        for name, metrics in self.baseline_metrics.items():
            br = metrics['returns']
            bt = metrics['trading']
            rows.append([
                name,
                f"{br.total_return:.2f}%",
                f"{br.sharpe_ratio:.2f}",
                f"{bt.win_rate*100:.1f}%",
                f"{br.max_drawdown:.2f}%",
                str(bt.total_trades),
            ])

        # Build table
        table = "| " + " | ".join(headers) + " |\n"
        table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            table += "| " + " | ".join(row) + " |\n"

        # Determine best performers
        best_return = max([self.all_metrics['returns'].total_return] +
                         [m['returns'].total_return for m in self.baseline_metrics.values()])
        best_sharpe = max([self.all_metrics['returns'].sharpe_ratio] +
                         [m['returns'].sharpe_ratio for m in self.baseline_metrics.values()])

        strategy_best_return = self.all_metrics['returns'].total_return == best_return
        strategy_best_sharpe = self.all_metrics['returns'].sharpe_ratio == best_sharpe

        return f"""## Baseline Comparison

{table}

### Analysis

- **Return Leader:** {'Strategy' if strategy_best_return else 'Baseline'} with {best_return:.2f}%
- **Risk-Adjusted Leader:** {'Strategy' if strategy_best_sharpe else 'Baseline'} with Sharpe of {best_sharpe:.2f}
- Strategy {'outperforms' if strategy_best_return else 'underperforms'} baselines on absolute returns
- Strategy {'outperforms' if strategy_best_sharpe else 'underperforms'} baselines on risk-adjusted basis"""

    def _generate_statistical_analysis(self) -> str:
        """Generate statistical analysis section."""
        if not self.baseline_runs:
            return "## Statistical Analysis\n\n*No baselines provided for statistical testing.*"

        strategy_returns = np.array(self.strategy_run.daily_returns)

        results_text = []
        tests = StatisticalTests(alpha=0.05)

        for name, baseline_run in self.baseline_runs.items():
            baseline_returns = np.array(baseline_run.daily_returns)

            # Run tests
            test_results = tests.run_all_tests(strategy_returns, baseline_returns)

            results_text.append(f"\n### vs {name}\n")

            for test_name, result in test_results.items():
                sig = "✅ Significant" if result.is_significant else "❌ Not Significant"
                results_text.append(
                    f"- **{result.test_name}:** p={result.p_value:.4f} ({sig})\n"
                    f"  - Effect Size: {result.effect_size:.3f}\n"
                    f"  - {result.interpretation}"
                )

        # Bootstrap confidence intervals
        bootstrap = BootstrapCI(n_bootstrap=10000, random_state=42)

        ci_return = bootstrap.calculate(strategy_returns, np.mean, confidence_level=0.95)
        ci_sharpe = bootstrap.calculate(
            strategy_returns,
            lambda x: np.mean(x) / (np.std(x) + 1e-8) * np.sqrt(365),
            confidence_level=0.95
        )

        return f"""## Statistical Analysis

### Bootstrap Confidence Intervals (95%)

| Metric | Point Estimate | 95% CI Lower | 95% CI Upper | Std Error |
|--------|---------------|--------------|--------------|-----------|
| Daily Return | {ci_return.point_estimate*100:.3f}% | {ci_return.ci_lower*100:.3f}% | {ci_return.ci_upper*100:.3f}% | {ci_return.std_error*100:.4f}% |
| Sharpe Ratio | {ci_sharpe.point_estimate:.2f} | {ci_sharpe.ci_lower:.2f} | {ci_sharpe.ci_upper:.2f} | {ci_sharpe.std_error:.3f} |

### Hypothesis Tests vs Baselines

{"".join(results_text)}"""

    def _generate_monte_carlo_analysis(self) -> str:
        """Generate Monte Carlo analysis section."""
        strategy_returns = np.array(self.strategy_run.daily_returns)

        if len(strategy_returns) < 30:
            return "## Monte Carlo Analysis\n\n*Insufficient data for Monte Carlo simulation.*"

        mc = MonteCarloSimulation(n_simulations=10000, random_state=42)

        # Simulate returns
        mc_returns = mc.simulate_returns(
            strategy_returns,
            n_days=365,
            method='bootstrap',
            target_return=0.15,
        )

        # Simulate drawdowns
        mc_drawdown = mc.simulate_drawdown(strategy_returns, n_days=365)

        return f"""## Monte Carlo Analysis

*{mc_returns.n_simulations:,} simulations of 365-day forward performance*

### Return Distribution

| Percentile | Annual Return |
|------------|---------------|
| 5th (Pessimistic) | {mc_returns.percentile_5*100:.1f}% |
| 25th | {mc_returns.percentile_25*100:.1f}% |
| 50th (Median) | {mc_returns.median*100:.1f}% |
| 75th | {mc_returns.percentile_75*100:.1f}% |
| 95th (Optimistic) | {mc_returns.percentile_95*100:.1f}% |

### Probability Analysis

| Scenario | Probability |
|----------|-------------|
| Positive Return | {mc_returns.probability_positive*100:.1f}% |
| Return > 15% Target | {mc_returns.probability_above_target*100:.1f}% |

### Drawdown Risk

| Percentile | Max Drawdown |
|------------|--------------|
| 5th (Best Case) | {mc_drawdown.percentile_95*100:.1f}% |
| 50th (Typical) | {mc_drawdown.median*100:.1f}% |
| 95th (Worst Case) | {mc_drawdown.percentile_5*100:.1f}% |

### Interpretation

The Monte Carlo simulation suggests:
- **Expected annual return:** {mc_returns.mean*100:.1f}% (±{mc_returns.std*100:.1f}%)
- **{mc_returns.probability_above_target*100:.0f}% probability** of achieving the 15% target
- **Typical maximum drawdown:** {mc_drawdown.median*100:.1f}%
- **Worst-case drawdown (95% confidence):** {mc_drawdown.percentile_5*100:.1f}%"""

    def _generate_visualizations(self, plot_dir: str) -> str:
        """Generate visualizations section."""
        return f"""## Visualizations

### Equity Curve
![Equity Curve]({plot_dir}/equity_curve.png)

### Trade Analysis
![Trade Analysis]({plot_dir}/trade_analysis.png)

### Battery SOC Analysis
![SOC Analysis]({plot_dir}/soc_analysis.png)

### Daily Performance
![Daily Analysis]({plot_dir}/daily_analysis.png)

### Strategy Comparison
![Comparison]({plot_dir}/comparison.png)"""

    def _generate_recommendations(self) -> str:
        """Generate recommendations section."""
        r = self.all_metrics['returns']
        t = self.all_metrics['trading']
        risk = self.all_metrics['risk']
        ops = self.all_metrics['operational']

        recommendations = []

        # Return-based recommendations
        if r.total_return < 15:
            recommendations.append(
                "**Improve Returns:** Consider increasing position sizes during high-confidence signals "
                "or optimizing entry/exit timing."
            )

        if r.sharpe_ratio < 1:
            recommendations.append(
                "**Improve Risk-Adjusted Returns:** Focus on reducing volatility through better "
                "position sizing and stop-loss mechanisms."
            )

        # Trading recommendations
        if t.win_rate < 0.5:
            recommendations.append(
                "**Improve Win Rate:** Review trade entry criteria and consider more selective filtering."
            )

        if t.profit_factor < 1.5:
            recommendations.append(
                "**Improve Profit Factor:** Focus on letting winners run longer or cutting losses faster."
            )

        # Risk recommendations
        if r.max_drawdown < -20:
            recommendations.append(
                "**Reduce Drawdown:** Implement position sizing rules that reduce exposure during "
                "drawdown periods."
            )

        if risk.max_consecutive_losses > 5:
            recommendations.append(
                "**Address Losing Streaks:** Consider implementing a 'cool-off' mechanism after "
                "consecutive losses."
            )

        # Operational recommendations
        if ops.cycles_per_day > 1:
            recommendations.append(
                "**Reduce Battery Cycling:** High cycling accelerates degradation. Consider "
                "implementing minimum hold periods."
            )

        if not recommendations:
            recommendations.append(
                "**Maintain Current Strategy:** Performance metrics are satisfactory. Consider "
                "paper trading for a longer period before deployment."
            )

        return f"""## Recommendations

Based on the backtest analysis, here are actionable recommendations:

{chr(10).join(f'{i+1}. {rec}' for i, rec in enumerate(recommendations))}

### Next Steps

1. **Validation:** Run additional backtests with different market conditions
2. **Paper Trading:** Deploy in simulation mode for 30+ days
3. **Risk Management:** Implement the recommended position sizing and stop-loss rules
4. **Monitoring:** Set up alerts for drawdown and performance degradation"""

    def _generate_appendix(self) -> str:
        """Generate appendix with raw data."""
        config = self.strategy_run.config

        return f"""## Appendix

### Backtest Configuration

```json
{{
    "battery_capacity_kwh": {config.battery_capacity_kwh},
    "max_charge_rate_kw": {config.max_charge_rate_kw},
    "max_discharge_rate_kw": {config.max_discharge_rate_kw},
    "charge_efficiency": {config.charge_efficiency},
    "discharge_efficiency": {config.discharge_efficiency},
    "min_soc": {config.min_soc},
    "max_soc": {config.max_soc},
    "initial_soc": {config.initial_soc},
    "transaction_fee": {config.transaction_fee},
    "bid_ask_spread": {config.bid_ask_spread},
    "initial_balance": {config.initial_balance}
}}
```

### Data Summary

- **Start Date:** {self.strategy_run.start_date}
- **End Date:** {self.strategy_run.end_date}
- **Total Trading Days:** {self.strategy_run.total_days}
- **Total Data Points:** {len(self.strategy_run.price_history)}

---

*Report generated by SHAKTI-CHAIN Backtesting Framework v1.0*
*For questions or issues, please contact the development team.*"""

    def export_json(self, output_path: str = "backtest_results.json") -> str:
        """Export results as JSON.

        Args:
            output_path: Output file path

        Returns:
            JSON string
        """
        data = {
            'strategy_name': self.strategy_name,
            'period': {
                'start': str(self.strategy_run.start_date),
                'end': str(self.strategy_run.end_date),
                'days': self.strategy_run.total_days,
            },
            'metrics': {
                'returns': {
                    'total_return': self.all_metrics['returns'].total_return,
                    'total_profit': self.all_metrics['returns'].total_profit,
                    'sharpe_ratio': self.all_metrics['returns'].sharpe_ratio,
                    'sortino_ratio': self.all_metrics['returns'].sortino_ratio,
                    'max_drawdown': self.all_metrics['returns'].max_drawdown,
                },
                'trading': {
                    'total_trades': self.all_metrics['trading'].total_trades,
                    'win_rate': self.all_metrics['trading'].win_rate,
                    'profit_factor': self.all_metrics['trading'].profit_factor,
                },
                'risk': {
                    'var_95': self.all_metrics['risk'].var_95,
                    'cvar_95': self.all_metrics['risk'].cvar_95,
                },
                'operational': {
                    'avg_soc': self.all_metrics['operational'].avg_soc,
                    'battery_cycles': self.all_metrics['operational'].total_battery_cycles,
                },
            },
            'baselines': {
                name: {
                    'total_return': m['returns'].total_return,
                    'sharpe_ratio': m['returns'].sharpe_ratio,
                    'win_rate': m['trading'].win_rate,
                }
                for name, m in self.baseline_metrics.items()
            },
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"JSON results saved to {output_path}")
        return json.dumps(data, indent=2)
