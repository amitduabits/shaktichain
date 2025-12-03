"""Comprehensive performance metrics for backtesting.

Calculates:
- Return metrics (ROI, Sharpe, Sortino, drawdown)
- Trading metrics (win rate, profit factor)
- Risk metrics (VaR, Expected Shortfall)
- Operational metrics (SOC, battery cycles)
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from scipy import stats
import logging

from .backtester import BacktestRun, Trade, TradeType

logger = logging.getLogger(__name__)


@dataclass
class ReturnMetrics:
    """Return-based performance metrics."""
    total_return: float  # Total ROI (%)
    total_profit: float  # Absolute profit
    daily_return_mean: float
    daily_return_std: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # Days
    recovery_time: int  # Days to recover from max drawdown
    profit_factor: float
    cumulative_returns: List[float]


@dataclass
class TradingMetrics:
    """Trading activity metrics."""
    total_trades: int
    buy_trades: int
    sell_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float
    avg_profit_per_trade: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    avg_trade_duration: float  # Hours between trades
    trades_per_day: float
    expectancy: float  # Expected value per trade
    kelly_criterion: float


@dataclass
class RiskMetrics:
    """Risk assessment metrics."""
    var_95: float  # Value at Risk 95%
    var_99: float  # Value at Risk 99%
    cvar_95: float  # Conditional VaR (Expected Shortfall) 95%
    cvar_99: float  # Conditional VaR 99%
    daily_volatility: float
    downside_volatility: float
    beta: float  # If benchmark provided
    information_ratio: float
    tail_ratio: float  # 95th percentile / 5th percentile of returns
    skewness: float
    kurtosis: float
    max_consecutive_losses: int
    max_consecutive_wins: int


@dataclass
class OperationalMetrics:
    """Battery and operational metrics."""
    avg_soc: float
    min_soc: float
    max_soc: float
    soc_std: float
    total_battery_cycles: float
    cycles_per_day: float
    total_energy_traded: float  # kWh
    energy_efficiency: float  # Output/Input
    delivery_success_rate: float
    avg_charge_depth: float
    avg_discharge_depth: float


class PerformanceMetrics:
    """Calculate comprehensive performance metrics from backtest results."""

    def __init__(
        self,
        backtest_run: BacktestRun,
        risk_free_rate: float = 0.04,  # Annual risk-free rate
        benchmark_returns: Optional[List[float]] = None,
    ):
        """Initialize metrics calculator.

        Args:
            backtest_run: Completed backtest run
            risk_free_rate: Annual risk-free rate for Sharpe calculation
            benchmark_returns: Optional benchmark returns for comparison
        """
        self.run = backtest_run
        self.risk_free_rate = risk_free_rate
        self.benchmark_returns = benchmark_returns

        # Pre-compute common values
        self.daily_returns = np.array(backtest_run.daily_returns)
        self.equity_curve = np.array(backtest_run.equity_curve)
        self.trades = backtest_run.all_trades

    def calculate_all(self) -> Dict[str, Any]:
        """Calculate all metrics.

        Returns:
            Dictionary with all metric categories
        """
        return {
            'returns': self.calculate_return_metrics(),
            'trading': self.calculate_trading_metrics(),
            'risk': self.calculate_risk_metrics(),
            'operational': self.calculate_operational_metrics(),
        }

    def calculate_return_metrics(self) -> ReturnMetrics:
        """Calculate return-based metrics."""
        returns = self.daily_returns

        # Basic returns
        total_return = self.run.total_return
        total_profit = self.run.total_profit
        daily_mean = np.mean(returns) * 100 if len(returns) > 0 else 0
        daily_std = np.std(returns) * 100 if len(returns) > 0 else 0

        # Annualized metrics (assuming 252 trading days)
        trading_days = 365
        annualized_return = ((1 + np.mean(returns)) ** trading_days - 1) * 100 if len(returns) > 0 else 0
        annualized_vol = np.std(returns) * np.sqrt(trading_days) * 100 if len(returns) > 0 else 0

        # Sharpe ratio
        daily_rf = self.risk_free_rate / trading_days
        excess_returns = returns - daily_rf
        sharpe = (np.mean(excess_returns) / (np.std(returns) + 1e-8)) * np.sqrt(trading_days) if len(returns) > 0 else 0

        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 1e-8
        sortino = (np.mean(excess_returns) / downside_std) * np.sqrt(trading_days) if len(returns) > 0 else 0

        # Maximum drawdown
        max_dd, max_dd_duration, recovery_time = self._calculate_drawdown()

        # Calmar ratio
        calmar = annualized_return / (abs(max_dd) + 1e-8) if max_dd != 0 else 0

        # Profit factor
        gains = sum(r for r in returns if r > 0)
        losses = abs(sum(r for r in returns if r < 0))
        profit_factor = gains / (losses + 1e-8)

        # Cumulative returns
        cumulative = np.cumprod(1 + returns).tolist() if len(returns) > 0 else []

        return ReturnMetrics(
            total_return=total_return,
            total_profit=total_profit,
            daily_return_mean=daily_mean,
            daily_return_std=daily_std,
            annualized_return=annualized_return,
            annualized_volatility=annualized_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            recovery_time=recovery_time,
            profit_factor=profit_factor,
            cumulative_returns=cumulative,
        )

    def calculate_trading_metrics(self) -> TradingMetrics:
        """Calculate trading activity metrics."""
        trades = self.trades

        if not trades:
            return TradingMetrics(
                total_trades=0, buy_trades=0, sell_trades=0,
                win_trades=0, loss_trades=0, win_rate=0,
                avg_profit_per_trade=0, avg_win=0, avg_loss=0,
                largest_win=0, largest_loss=0, profit_factor=0,
                avg_trade_duration=0, trades_per_day=0,
                expectancy=0, kelly_criterion=0,
            )

        # Count trades
        total = len(trades)
        buys = sum(1 for t in trades if t.trade_type == TradeType.BUY)
        sells = sum(1 for t in trades if t.trade_type == TradeType.SELL)
        wins = sum(1 for t in trades if t.profit > 0)
        losses = sum(1 for t in trades if t.profit < 0)

        # Win rate
        win_rate = wins / total if total > 0 else 0

        # Profit stats
        profits = [t.profit for t in trades]
        avg_profit = np.mean(profits)

        winning_trades = [t.profit for t in trades if t.profit > 0]
        losing_trades = [t.profit for t in trades if t.profit < 0]

        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        largest_win = max(winning_trades) if winning_trades else 0
        largest_loss = min(losing_trades) if losing_trades else 0

        # Profit factor
        gross_profit = sum(winning_trades) if winning_trades else 0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 1e-8
        profit_factor = gross_profit / gross_loss

        # Trade frequency
        trades_per_day = total / max(self.run.total_days, 1)

        # Calculate average duration between trades
        if len(trades) > 1:
            durations = []
            for i in range(1, len(trades)):
                duration = (trades[i].timestamp - trades[i-1].timestamp).total_seconds() / 3600
                durations.append(duration)
            avg_duration = np.mean(durations)
        else:
            avg_duration = 0

        # Expectancy
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        # Kelly criterion
        if avg_loss != 0 and win_rate > 0:
            win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            kelly = win_rate - (1 - win_rate) / (win_loss_ratio + 1e-8)
        else:
            kelly = 0

        return TradingMetrics(
            total_trades=total,
            buy_trades=buys,
            sell_trades=sells,
            win_trades=wins,
            loss_trades=losses,
            win_rate=win_rate,
            avg_profit_per_trade=avg_profit,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            avg_trade_duration=avg_duration,
            trades_per_day=trades_per_day,
            expectancy=expectancy,
            kelly_criterion=kelly,
        )

    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate risk assessment metrics."""
        returns = self.daily_returns

        if len(returns) < 2:
            return RiskMetrics(
                var_95=0, var_99=0, cvar_95=0, cvar_99=0,
                daily_volatility=0, downside_volatility=0,
                beta=0, information_ratio=0, tail_ratio=0,
                skewness=0, kurtosis=0,
                max_consecutive_losses=0, max_consecutive_wins=0,
            )

        # Value at Risk (Historical)
        var_95 = np.percentile(returns, 5) * 100
        var_99 = np.percentile(returns, 1) * 100

        # Conditional VaR (Expected Shortfall)
        cvar_95 = np.mean(returns[returns <= np.percentile(returns, 5)]) * 100
        cvar_99 = np.mean(returns[returns <= np.percentile(returns, 1)]) * 100

        # Volatility
        daily_vol = np.std(returns) * 100
        downside_returns = returns[returns < 0]
        downside_vol = np.std(downside_returns) * 100 if len(downside_returns) > 0 else 0

        # Beta and Information Ratio (if benchmark provided)
        beta = 0
        info_ratio = 0
        if self.benchmark_returns is not None and len(self.benchmark_returns) == len(returns):
            bench = np.array(self.benchmark_returns)
            cov = np.cov(returns, bench)[0, 1]
            var_bench = np.var(bench)
            beta = cov / var_bench if var_bench > 0 else 0

            tracking_error = np.std(returns - bench)
            info_ratio = (np.mean(returns) - np.mean(bench)) / tracking_error if tracking_error > 0 else 0

        # Tail ratio
        upper_tail = np.percentile(returns, 95)
        lower_tail = abs(np.percentile(returns, 5))
        tail_ratio = upper_tail / lower_tail if lower_tail > 0 else 0

        # Distribution shape
        skewness = stats.skew(returns) if len(returns) > 2 else 0
        kurtosis = stats.kurtosis(returns) if len(returns) > 3 else 0

        # Consecutive wins/losses
        max_cons_losses, max_cons_wins = self._calculate_consecutive_streaks()

        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            daily_volatility=daily_vol,
            downside_volatility=downside_vol,
            beta=beta,
            information_ratio=info_ratio,
            tail_ratio=tail_ratio,
            skewness=skewness,
            kurtosis=kurtosis,
            max_consecutive_losses=max_cons_losses,
            max_consecutive_wins=max_cons_wins,
        )

    def calculate_operational_metrics(self) -> OperationalMetrics:
        """Calculate battery and operational metrics."""
        daily_results = self.run.daily_results

        if not daily_results:
            return OperationalMetrics(
                avg_soc=0.5, min_soc=0.2, max_soc=0.95, soc_std=0,
                total_battery_cycles=0, cycles_per_day=0,
                total_energy_traded=0, energy_efficiency=0,
                delivery_success_rate=0, avg_charge_depth=0, avg_discharge_depth=0,
            )

        # SOC statistics
        all_soc = self.run.soc_history
        avg_soc = np.mean(all_soc) if all_soc else 0.5
        min_soc = np.min(all_soc) if all_soc else 0.2
        max_soc = np.max(all_soc) if all_soc else 0.95
        soc_std = np.std(all_soc) if all_soc else 0

        # Battery cycles
        total_cycles = sum(d.battery_cycles for d in daily_results)
        cycles_per_day = total_cycles / len(daily_results) if daily_results else 0

        # Energy traded
        trades = self.run.all_trades
        buy_energy = sum(t.quantity_kwh for t in trades if t.trade_type == TradeType.BUY)
        sell_energy = sum(t.quantity_kwh for t in trades if t.trade_type == TradeType.SELL)
        total_energy = buy_energy + sell_energy
        efficiency = sell_energy / (buy_energy + 1e-8) if buy_energy > 0 else 0

        # Delivery success (assuming all executed trades are delivered)
        delivery_rate = 1.0  # Would need failure tracking

        # Charge/discharge depths
        charge_depths = []
        discharge_depths = []
        for t in trades:
            if t.trade_type == TradeType.BUY:
                charge_depths.append(t.soc_after - t.soc_before)
            else:
                discharge_depths.append(t.soc_before - t.soc_after)

        avg_charge_depth = np.mean(charge_depths) if charge_depths else 0
        avg_discharge_depth = np.mean(discharge_depths) if discharge_depths else 0

        return OperationalMetrics(
            avg_soc=avg_soc,
            min_soc=min_soc,
            max_soc=max_soc,
            soc_std=soc_std,
            total_battery_cycles=total_cycles,
            cycles_per_day=cycles_per_day,
            total_energy_traded=total_energy,
            energy_efficiency=efficiency,
            delivery_success_rate=delivery_rate,
            avg_charge_depth=avg_charge_depth,
            avg_discharge_depth=avg_discharge_depth,
        )

    def _calculate_drawdown(self) -> Tuple[float, int, int]:
        """Calculate maximum drawdown and related metrics.

        Returns:
            (max_drawdown_pct, duration_days, recovery_days)
        """
        equity = self.equity_curve
        if len(equity) < 2:
            return 0.0, 0, 0

        # Running maximum
        running_max = np.maximum.accumulate(equity)

        # Drawdown series
        drawdown = (equity - running_max) / running_max * 100

        # Maximum drawdown
        max_dd = np.min(drawdown)

        # Find drawdown duration
        max_dd_idx = np.argmin(drawdown)
        peak_idx = np.argmax(equity[:max_dd_idx + 1])
        duration = max_dd_idx - peak_idx

        # Recovery time
        recovery_idx = max_dd_idx
        for i in range(max_dd_idx, len(equity)):
            if equity[i] >= equity[peak_idx]:
                recovery_idx = i
                break

        recovery_time = recovery_idx - max_dd_idx

        return max_dd, duration, recovery_time

    def _calculate_consecutive_streaks(self) -> Tuple[int, int]:
        """Calculate maximum consecutive wins and losses.

        Returns:
            (max_consecutive_losses, max_consecutive_wins)
        """
        returns = self.daily_returns
        if len(returns) == 0:
            return 0, 0

        max_losses = 0
        max_wins = 0
        current_losses = 0
        current_wins = 0

        for r in returns:
            if r < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            elif r > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses = 0
                current_wins = 0

        return max_losses, max_wins

    def summary_dict(self) -> Dict[str, float]:
        """Get flat dictionary of key metrics for comparison."""
        all_metrics = self.calculate_all()

        return {
            'total_return': all_metrics['returns'].total_return,
            'total_profit': all_metrics['returns'].total_profit,
            'sharpe_ratio': all_metrics['returns'].sharpe_ratio,
            'sortino_ratio': all_metrics['returns'].sortino_ratio,
            'max_drawdown': all_metrics['returns'].max_drawdown,
            'win_rate': all_metrics['trading'].win_rate,
            'profit_factor': all_metrics['trading'].profit_factor,
            'total_trades': all_metrics['trading'].total_trades,
            'var_95': all_metrics['risk'].var_95,
            'avg_soc': all_metrics['operational'].avg_soc,
            'battery_cycles': all_metrics['operational'].total_battery_cycles,
        }
