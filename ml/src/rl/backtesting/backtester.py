"""V2G Backtesting Engine.

Main backtesting class for simulating trading strategies
on historical or simulated data.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TradeType(Enum):
    """Trade type enumeration."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Trade:
    """Record of a single trade."""
    timestamp: datetime
    hour: int
    trade_type: TradeType
    quantity_kwh: float
    price: float
    cost: float  # Negative for buys, positive for sells
    profit: float
    soc_before: float
    soc_after: float
    market_price: float
    fees: float = 0.0


@dataclass
class DailyResult:
    """Results for a single trading day."""
    date: datetime
    trades: List[Trade]
    total_profit: float
    total_trades: int
    buy_trades: int
    sell_trades: int
    win_trades: int
    loss_trades: int
    starting_soc: float
    ending_soc: float
    min_soc: float
    max_soc: float
    avg_soc: float
    battery_cycles: float
    prices: List[float]
    hourly_profits: List[float]
    hourly_soc: List[float]


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""
    # Battery parameters
    battery_capacity_kwh: float = 60.0
    max_charge_rate_kw: float = 11.0
    max_discharge_rate_kw: float = 11.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    min_soc: float = 0.2
    max_soc: float = 0.95
    initial_soc: float = 0.5
    degradation_per_cycle: float = 0.0001
    cycle_cost_per_kwh: float = 0.05

    # Market parameters
    transaction_fee: float = 0.01
    bid_ask_spread: float = 0.05
    min_trade_kwh: float = 1.0
    max_trade_kwh: float = 50.0

    # Initial capital
    initial_balance: float = 1000.0

    # Simulation parameters
    hours_per_day: int = 24
    step_duration_hours: float = 1.0


@dataclass
class BacktestRun:
    """Complete backtest run results."""
    config: BacktestConfig
    start_date: datetime
    end_date: datetime
    daily_results: List[DailyResult]
    all_trades: List[Trade]

    # Aggregate metrics
    total_profit: float = 0.0
    total_return: float = 0.0
    total_days: int = 0
    total_trades: int = 0

    # Time series
    equity_curve: List[float] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    soc_history: List[float] = field(default_factory=list)
    price_history: List[float] = field(default_factory=list)


class BatterySimulator:
    """Simulates battery operations during backtest."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.reset()

    def reset(self, initial_soc: Optional[float] = None):
        """Reset battery state."""
        self.soc = initial_soc or self.config.initial_soc
        self.total_cycles = 0.0
        self.energy_throughput = 0.0

    def charge(self, power_kw: float, duration_hours: float = 1.0) -> Tuple[float, float]:
        """Charge battery.

        Returns:
            (energy_stored, degradation_cost)
        """
        power_kw = min(power_kw, self.config.max_charge_rate_kw)
        power_kw = max(power_kw, 0)

        energy_in = power_kw * duration_hours
        energy_stored = energy_in * self.config.charge_efficiency

        available = (self.config.max_soc - self.soc) * self.config.battery_capacity_kwh
        energy_stored = min(energy_stored, available)

        self.soc += energy_stored / self.config.battery_capacity_kwh
        self.soc = min(self.soc, self.config.max_soc)

        cycles = energy_stored / (2 * self.config.battery_capacity_kwh)
        self.total_cycles += cycles
        self.energy_throughput += energy_stored

        cost = energy_stored * self.config.cycle_cost_per_kwh
        return energy_stored, cost

    def discharge(self, power_kw: float, duration_hours: float = 1.0) -> Tuple[float, float]:
        """Discharge battery.

        Returns:
            (energy_delivered, degradation_cost)
        """
        power_kw = min(power_kw, self.config.max_discharge_rate_kw)
        power_kw = max(power_kw, 0)

        energy_from_battery = power_kw * duration_hours
        available = (self.soc - self.config.min_soc) * self.config.battery_capacity_kwh
        energy_from_battery = min(energy_from_battery, available)
        energy_from_battery = max(energy_from_battery, 0)

        energy_delivered = energy_from_battery * self.config.discharge_efficiency

        self.soc -= energy_from_battery / self.config.battery_capacity_kwh
        self.soc = max(self.soc, self.config.min_soc)

        cycles = energy_from_battery / (2 * self.config.battery_capacity_kwh)
        self.total_cycles += cycles
        self.energy_throughput += energy_from_battery

        cost = energy_from_battery * self.config.cycle_cost_per_kwh
        return energy_delivered, cost

    def get_available_charge(self) -> float:
        """Get available charge capacity (kWh)."""
        return (self.config.max_soc - self.soc) * self.config.battery_capacity_kwh

    def get_available_discharge(self) -> float:
        """Get available discharge capacity (kWh)."""
        return (self.soc - self.config.min_soc) * self.config.battery_capacity_kwh


class V2GBacktester:
    """Main backtesting engine for V2G trading strategies.

    Simulates trading day by day with realistic battery and market dynamics.
    """

    def __init__(
        self,
        agent: Callable,
        data: pd.DataFrame,
        config: Optional[BacktestConfig] = None,
    ):
        """Initialize backtester.

        Args:
            agent: Trading agent/strategy (callable that takes state and returns action)
            data: Historical data with columns: timestamp, price, load, [forecast columns]
            config: Backtest configuration
        """
        self.agent = agent
        self.data = data
        self.config = config or BacktestConfig()
        self.battery = BatterySimulator(self.config)

    def run(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        verbose: bool = True,
    ) -> BacktestRun:
        """Run backtest simulation.

        Args:
            start_date: Start date (None = use data start)
            end_date: End date (None = use data end)
            verbose: Print progress

        Returns:
            BacktestRun with complete results
        """
        # Prepare data
        data = self._prepare_data(start_date, end_date)

        if verbose:
            logger.info(f"Running backtest from {data.index[0]} to {data.index[-1]}")

        # Initialize tracking
        daily_results: List[DailyResult] = []
        all_trades: List[Trade] = []
        equity_curve = [self.config.initial_balance]
        daily_returns = []
        soc_history = [self.config.initial_soc]
        price_history = []

        current_equity = self.config.initial_balance
        self.battery.reset()

        # Group by day
        daily_groups = data.groupby(data.index.date)

        for day_idx, (date, day_data) in enumerate(daily_groups):
            if verbose and day_idx % 30 == 0:
                logger.info(f"Processing day {day_idx + 1}/{len(daily_groups)}: {date}")

            # Run single day
            day_result = self._run_day(date, day_data, current_equity)
            daily_results.append(day_result)
            all_trades.extend(day_result.trades)

            # Update equity
            current_equity += day_result.total_profit
            equity_curve.append(current_equity)

            # Calculate daily return
            prev_equity = equity_curve[-2] if len(equity_curve) > 1 else self.config.initial_balance
            daily_return = (current_equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append(daily_return)

            # Record history
            soc_history.extend(day_result.hourly_soc)
            price_history.extend(day_result.prices)

        # Create result
        result = BacktestRun(
            config=self.config,
            start_date=data.index[0],
            end_date=data.index[-1],
            daily_results=daily_results,
            all_trades=all_trades,
            total_profit=current_equity - self.config.initial_balance,
            total_return=(current_equity / self.config.initial_balance - 1) * 100,
            total_days=len(daily_results),
            total_trades=len(all_trades),
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            soc_history=soc_history,
            price_history=price_history,
        )

        if verbose:
            logger.info(f"Backtest complete: {result.total_days} days, "
                       f"{result.total_trades} trades, "
                       f"ROI: {result.total_return:.2f}%")

        return result

    def _prepare_data(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> pd.DataFrame:
        """Prepare data for backtesting."""
        data = self.data.copy()

        # Ensure datetime index
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'timestamp' in data.columns:
                data.set_index('timestamp', inplace=True)
            data.index = pd.to_datetime(data.index)

        # Filter date range
        if start_date is not None:
            data = data[data.index >= start_date]
        if end_date is not None:
            data = data[data.index <= end_date]

        return data.sort_index()

    def _run_day(
        self,
        date: datetime,
        day_data: pd.DataFrame,
        current_equity: float,
    ) -> DailyResult:
        """Run simulation for a single day.

        Args:
            date: Trading date
            day_data: Data for this day
            current_equity: Current portfolio equity

        Returns:
            DailyResult for the day
        """
        trades: List[Trade] = []
        hourly_profits = []
        hourly_soc = []
        prices = []

        starting_soc = self.battery.soc
        min_soc = starting_soc
        max_soc = starting_soc
        daily_energy_throughput_start = self.battery.energy_throughput

        for idx, (timestamp, row) in enumerate(day_data.iterrows()):
            hour = timestamp.hour
            price = row.get('price', row.get('market_price', 5.0))
            load = row.get('load', row.get('load_mw', 0.5))

            prices.append(price)

            # Build state for agent
            state = self._build_state(row, hour, current_equity)

            # Get action from agent
            action = self.agent(state)

            # Execute action
            trade = self._execute_action(action, timestamp, hour, price)

            if trade is not None:
                trades.append(trade)
                hourly_profits.append(trade.profit)
            else:
                hourly_profits.append(0.0)

            hourly_soc.append(self.battery.soc)
            min_soc = min(min_soc, self.battery.soc)
            max_soc = max(max_soc, self.battery.soc)

        # Calculate day metrics
        total_profit = sum(t.profit for t in trades)
        buy_trades = sum(1 for t in trades if t.trade_type == TradeType.BUY)
        sell_trades = sum(1 for t in trades if t.trade_type == TradeType.SELL)
        win_trades = sum(1 for t in trades if t.profit > 0)
        loss_trades = sum(1 for t in trades if t.profit < 0)

        energy_cycled = self.battery.energy_throughput - daily_energy_throughput_start
        battery_cycles = energy_cycled / (2 * self.config.battery_capacity_kwh)

        return DailyResult(
            date=date,
            trades=trades,
            total_profit=total_profit,
            total_trades=len(trades),
            buy_trades=buy_trades,
            sell_trades=sell_trades,
            win_trades=win_trades,
            loss_trades=loss_trades,
            starting_soc=starting_soc,
            ending_soc=self.battery.soc,
            min_soc=min_soc,
            max_soc=max_soc,
            avg_soc=np.mean(hourly_soc) if hourly_soc else starting_soc,
            battery_cycles=battery_cycles,
            prices=prices,
            hourly_profits=hourly_profits,
            hourly_soc=hourly_soc,
        )

    def _build_state(
        self,
        row: pd.Series,
        hour: int,
        equity: float,
    ) -> Dict[str, Any]:
        """Build state dictionary for agent."""
        state = {
            'soc': self.battery.soc,
            'hour': hour,
            'price': row.get('price', row.get('market_price', 5.0)),
            'load': row.get('load', row.get('load_mw', 0.5)),
            'equity': equity,
            'available_charge': self.battery.get_available_charge(),
            'available_discharge': self.battery.get_available_discharge(),
        }

        # Add forecast columns if present
        for col in row.index:
            if 'forecast' in col.lower() or 'pred' in col.lower():
                state[col] = row[col]

        return state

    def _execute_action(
        self,
        action: Union[np.ndarray, Tuple, Dict],
        timestamp: datetime,
        hour: int,
        price: float,
    ) -> Optional[Trade]:
        """Execute trading action.

        Args:
            action: Agent's action (normalized quantity, price aggressiveness)
            timestamp: Current timestamp
            hour: Current hour
            price: Current market price

        Returns:
            Trade record if trade executed, None otherwise
        """
        # Parse action
        if isinstance(action, dict):
            quantity = action.get('quantity', 0.0)
            aggressiveness = action.get('aggressiveness', 0.5)
        elif isinstance(action, (tuple, list, np.ndarray)):
            quantity = float(action[0]) if len(action) > 0 else 0.0
            aggressiveness = float(action[1]) if len(action) > 1 else 0.5
        else:
            quantity = float(action)
            aggressiveness = 0.5

        # Skip small actions
        if abs(quantity) < 0.1:
            return None

        soc_before = self.battery.soc

        if quantity > 0:
            # BUY (charge)
            trade_kwh = quantity * min(
                self.battery.get_available_charge(),
                self.config.max_trade_kwh
            )

            if trade_kwh < self.config.min_trade_kwh:
                return None

            # Calculate execution price (pay ask + spread)
            spread_cost = price * self.config.bid_ask_spread * (1 - aggressiveness)
            exec_price = price * (1 + self.config.bid_ask_spread / 2) + spread_cost

            # Execute charge
            energy_stored, degradation_cost = self.battery.charge(trade_kwh)

            # Calculate costs
            trade_cost = energy_stored * exec_price
            fees = trade_cost * self.config.transaction_fee
            total_cost = trade_cost + fees + degradation_cost

            return Trade(
                timestamp=timestamp,
                hour=hour,
                trade_type=TradeType.BUY,
                quantity_kwh=energy_stored,
                price=exec_price,
                cost=-total_cost,
                profit=-total_cost,  # Immediate loss from buying
                soc_before=soc_before,
                soc_after=self.battery.soc,
                market_price=price,
                fees=fees + degradation_cost,
            )

        else:
            # SELL (discharge)
            trade_kwh = abs(quantity) * min(
                self.battery.get_available_discharge(),
                self.config.max_trade_kwh
            )

            if trade_kwh < self.config.min_trade_kwh:
                return None

            # Calculate execution price (receive bid - spread)
            spread_cost = price * self.config.bid_ask_spread * (1 - aggressiveness)
            exec_price = price * (1 - self.config.bid_ask_spread / 2) - spread_cost

            # Execute discharge
            energy_delivered, degradation_cost = self.battery.discharge(trade_kwh)

            # Calculate revenue
            trade_revenue = energy_delivered * exec_price
            fees = trade_revenue * self.config.transaction_fee
            net_revenue = trade_revenue - fees - degradation_cost

            return Trade(
                timestamp=timestamp,
                hour=hour,
                trade_type=TradeType.SELL,
                quantity_kwh=energy_delivered,
                price=exec_price,
                cost=net_revenue,
                profit=net_revenue,
                soc_before=soc_before,
                soc_after=self.battery.soc,
                market_price=price,
                fees=fees + degradation_cost,
            )

    def run_multiple(
        self,
        n_runs: int = 100,
        randomize_start_soc: bool = True,
        seed: Optional[int] = None,
    ) -> List[BacktestRun]:
        """Run multiple backtests with different conditions.

        Args:
            n_runs: Number of runs
            randomize_start_soc: Randomize initial SOC
            seed: Random seed

        Returns:
            List of BacktestRun results
        """
        if seed is not None:
            np.random.seed(seed)

        results = []
        for i in range(n_runs):
            if randomize_start_soc:
                self.config.initial_soc = np.random.uniform(0.3, 0.7)

            result = self.run(verbose=False)
            results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Completed {i + 1}/{n_runs} runs")

        return results
