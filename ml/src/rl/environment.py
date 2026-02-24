"""V2G Trading Environment for SHAKTI-CHAIN.

Implements a Gymnasium environment for training RL agents to optimize
V2G trading decisions with realistic battery and market dynamics.

Key Features:
- Realistic battery model with degradation
- Market simulation with price dynamics
- Load and price forecast integration
- Reputation system from blockchain
- Multiple reward components
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class DayType(IntEnum):
    """Day type enumeration."""
    WEEKDAY = 0
    WEEKEND = 1
    HOLIDAY = 2


class ReputationTier(IntEnum):
    """Reputation tier levels."""
    BRONZE = 0
    SILVER = 1
    GOLD = 2
    PLATINUM = 3
    DIAMOND = 4


@dataclass
class BatteryConfig:
    """Battery configuration parameters."""
    capacity_kwh: float = 60.0  # Total battery capacity
    max_charge_rate_kw: float = 11.0  # Maximum charging power
    max_discharge_rate_kw: float = 11.0  # Maximum discharging power
    charge_efficiency: float = 0.95  # Charging efficiency
    discharge_efficiency: float = 0.95  # Discharging efficiency
    min_soc: float = 0.2  # Minimum SOC for personal use reserve
    max_soc: float = 0.95  # Maximum SOC for battery health
    initial_soc: float = 0.5  # Initial state of charge
    degradation_per_cycle: float = 0.0001  # Battery degradation per full cycle
    cycle_cost_per_kwh: float = 0.05  # Cost per kWh cycled (degradation cost)


@dataclass
class MarketConfig:
    """Market configuration parameters."""
    base_price: float = 5.0  # Base price per kWh (INR)
    price_volatility: float = 0.3  # Price volatility factor
    bid_ask_spread: float = 0.05  # Default bid-ask spread
    transaction_fee: float = 0.01  # Transaction fee percentage
    min_trade_kwh: float = 1.0  # Minimum trade size
    max_trade_kwh: float = 50.0  # Maximum trade size per hour
    price_impact: float = 0.001  # Price impact of trades


@dataclass
class RewardConfig:
    """Reward function configuration."""
    profit_weight: float = 1.0
    battery_health_weight: float = 0.5
    grid_service_weight: float = 0.3
    reputation_weight: float = 0.2
    failed_delivery_penalty: float = -100.0
    low_soc_penalty: float = -10.0
    high_soc_penalty: float = -5.0
    frequency_regulation_bonus: float = 5.0


@dataclass
class EnvironmentConfig:
    """Complete environment configuration."""
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)

    # Episode settings
    episode_length: int = 24  # Hours per episode
    forecast_horizon: int = 24  # Forecast lookahead hours

    # Initial conditions
    initial_shakti_balance: float = 1000.0  # Initial SHAKTI tokens
    initial_reputation: int = ReputationTier.SILVER

    # Random seed
    seed: Optional[int] = None


class BatteryModel:
    """Realistic battery model with degradation tracking.

    Models:
    - State of charge dynamics
    - Charging/discharging efficiency
    - Degradation from cycling
    - Rate limits
    """

    def __init__(self, config: BatteryConfig):
        self.config = config
        self.reset()

    def reset(self, initial_soc: Optional[float] = None):
        """Reset battery to initial state."""
        self.soc = initial_soc if initial_soc is not None else self.config.initial_soc
        self.total_cycles = 0.0
        self.degradation = 0.0
        self.energy_throughput = 0.0

    def charge(self, power_kw: float, duration_hours: float = 1.0) -> Tuple[float, float]:
        """Charge the battery.

        Args:
            power_kw: Charging power in kW (positive)
            duration_hours: Duration in hours

        Returns:
            actual_energy: Energy actually stored (kWh)
            cost: Degradation cost
        """
        # Limit to max charge rate
        power_kw = min(power_kw, self.config.max_charge_rate_kw)
        power_kw = max(power_kw, 0)

        # Calculate energy with efficiency
        energy_in = power_kw * duration_hours
        energy_stored = energy_in * self.config.charge_efficiency

        # Check SOC limits
        available_capacity = (self.config.max_soc - self.soc) * self.config.capacity_kwh
        energy_stored = min(energy_stored, available_capacity)

        # Update SOC
        self.soc += energy_stored / self.config.capacity_kwh
        self.soc = min(self.soc, self.config.max_soc)

        # Update degradation
        cycles = energy_stored / (2 * self.config.capacity_kwh)  # Half cycle for charge
        self.total_cycles += cycles
        self.degradation += cycles * self.config.degradation_per_cycle
        self.energy_throughput += energy_stored

        cost = energy_stored * self.config.cycle_cost_per_kwh

        return energy_stored, cost

    def discharge(self, power_kw: float, duration_hours: float = 1.0) -> Tuple[float, float]:
        """Discharge the battery.

        Args:
            power_kw: Discharge power in kW (positive)
            duration_hours: Duration in hours

        Returns:
            actual_energy: Energy actually delivered (kWh)
            cost: Degradation cost
        """
        # Limit to max discharge rate
        power_kw = min(power_kw, self.config.max_discharge_rate_kw)
        power_kw = max(power_kw, 0)

        # Calculate energy with efficiency
        energy_from_battery = power_kw * duration_hours

        # Check SOC limits (reserve min SOC)
        available_energy = (self.soc - self.config.min_soc) * self.config.capacity_kwh
        energy_from_battery = min(energy_from_battery, available_energy)
        energy_from_battery = max(energy_from_battery, 0)

        # Energy delivered after efficiency loss
        energy_delivered = energy_from_battery * self.config.discharge_efficiency

        # Update SOC
        self.soc -= energy_from_battery / self.config.capacity_kwh
        self.soc = max(self.soc, self.config.min_soc)

        # Update degradation
        cycles = energy_from_battery / (2 * self.config.capacity_kwh)
        self.total_cycles += cycles
        self.degradation += cycles * self.config.degradation_per_cycle
        self.energy_throughput += energy_from_battery

        cost = energy_from_battery * self.config.cycle_cost_per_kwh

        return energy_delivered, cost

    def get_available_charge_capacity(self) -> float:
        """Get available capacity for charging (kWh)."""
        return (self.config.max_soc - self.soc) * self.config.capacity_kwh

    def get_available_discharge_capacity(self) -> float:
        """Get available capacity for discharging (kWh)."""
        return (self.soc - self.config.min_soc) * self.config.capacity_kwh

    def get_health(self) -> float:
        """Get battery health (1.0 = new, 0.0 = degraded)."""
        return max(0.0, 1.0 - self.degradation)


class MarketSimulator:
    """Simulates electricity market dynamics.

    Features:
    - Price generation based on load patterns
    - Bid-ask spread dynamics
    - Transaction execution
    - Price impact modeling
    """

    def __init__(self, config: MarketConfig, seed: Optional[int] = None):
        self.config = config
        self.rng = np.random.default_rng(seed)
        self.reset()

    def reset(self):
        """Reset market state."""
        self.current_price = self.config.base_price
        self.bid_price = self.current_price * (1 - self.config.bid_ask_spread / 2)
        self.ask_price = self.current_price * (1 + self.config.bid_ask_spread / 2)
        self.price_history = []
        self.volume_history = []

    def generate_price(self, hour: int, load_factor: float, day_type: DayType) -> float:
        """Generate market price based on conditions.

        Args:
            hour: Hour of day (0-23)
            load_factor: Current load as fraction of peak
            day_type: Type of day

        Returns:
            New market price
        """
        # Base price pattern (peak hours have higher prices)
        hour_factor = self._get_hour_factor(hour)

        # Load impact
        load_impact = 1.0 + (load_factor - 0.5) * 0.5

        # Day type impact
        day_factor = {
            DayType.WEEKDAY: 1.0,
            DayType.WEEKEND: 0.85,
            DayType.HOLIDAY: 0.75,
        }[day_type]

        # Random volatility
        noise = self.rng.normal(0, self.config.price_volatility * self.config.base_price)

        # Calculate new price
        new_price = self.config.base_price * hour_factor * load_impact * day_factor + noise
        new_price = max(new_price, self.config.base_price * 0.3)  # Floor price
        new_price = min(new_price, self.config.base_price * 5.0)  # Cap price

        self.current_price = new_price
        self._update_bid_ask()
        self.price_history.append(new_price)

        return new_price

    def _get_hour_factor(self, hour: int) -> float:
        """Get price factor based on hour of day."""
        # Morning peak (6-10), Evening peak (18-22)
        if 6 <= hour <= 10:
            return 1.2 + 0.1 * (hour - 6)
        elif 18 <= hour <= 22:
            return 1.3 + 0.15 * (hour - 18)
        elif 0 <= hour <= 5:
            return 0.7
        else:
            return 1.0

    def _update_bid_ask(self):
        """Update bid and ask prices."""
        spread = self.config.bid_ask_spread * self.current_price
        self.bid_price = self.current_price - spread / 2
        self.ask_price = self.current_price + spread / 2

    def execute_trade(
        self,
        quantity_kwh: float,
        price_aggressiveness: float,
        is_buy: bool,
    ) -> Tuple[float, float, bool]:
        """Execute a trade in the market.

        Args:
            quantity_kwh: Trade quantity (positive)
            price_aggressiveness: 0 (passive) to 1 (aggressive)
            is_buy: True for buy, False for sell

        Returns:
            executed_quantity: Actually executed quantity
            execution_price: Execution price
            success: Whether trade was successful
        """
        if quantity_kwh < self.config.min_trade_kwh:
            return 0.0, 0.0, False

        quantity_kwh = min(quantity_kwh, self.config.max_trade_kwh)

        # Determine limit price based on aggressiveness
        if is_buy:
            # More aggressive = willing to pay higher
            limit_price = self.bid_price + price_aggressiveness * (self.ask_price - self.bid_price)
            execution_price = self.ask_price - (1 - price_aggressiveness) * (self.ask_price - self.bid_price) * 0.5
        else:
            # More aggressive = willing to accept lower
            limit_price = self.ask_price - price_aggressiveness * (self.ask_price - self.bid_price)
            execution_price = self.bid_price + (1 - price_aggressiveness) * (self.ask_price - self.bid_price) * 0.5

        # Price impact
        impact = quantity_kwh * self.config.price_impact
        if is_buy:
            execution_price += impact
        else:
            execution_price -= impact

        # Check if trade executes
        if is_buy and execution_price <= limit_price:
            success = True
        elif not is_buy and execution_price >= limit_price:
            success = True
        else:
            success = self.rng.random() < price_aggressiveness  # Probabilistic execution

        if success:
            # Apply transaction fee
            fee = quantity_kwh * execution_price * self.config.transaction_fee
            if is_buy:
                execution_price += fee / quantity_kwh
            else:
                execution_price -= fee / quantity_kwh

            self.volume_history.append(quantity_kwh)
            return quantity_kwh, execution_price, True

        return 0.0, 0.0, False


class V2GTradingEnv(gym.Env):
    """V2G Trading Environment for reinforcement learning.

    State Space:
    - Battery SOC: [0, 1]
    - Current hour: [0, 23] (normalized to [0, 1])
    - Day type: one-hot [3]
    - Load forecast (next 24h): [24] normalized
    - Price forecast (next 24h): [24] normalized
    - Current market price: [0, 1] normalized
    - Bid-ask spread: [0, 1]
    - Own position: [0, 1]
    - SHAKTI balance: [0, 1] normalized
    - Reputation tier: [0, 1] normalized

    Action Space (Continuous):
    - action[0]: Quantity (-1 = full sell, 0 = hold, +1 = full buy)
    - action[1]: Price aggressiveness (0 = passive, 1 = aggressive)

    Or Discrete:
    - Quantity: [-100%, -50%, 0%, +50%, +100%]
    - Price: [bid-10%, bid-5%, mid, ask+5%, ask+10%]
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(
        self,
        config: Optional[EnvironmentConfig] = None,
        load_forecast_fn: Optional[callable] = None,
        price_forecast_fn: Optional[callable] = None,
        use_discrete_actions: bool = False,
        render_mode: Optional[str] = None,
    ):
        """Initialize environment.

        Args:
            config: Environment configuration
            load_forecast_fn: Function to generate load forecasts
            price_forecast_fn: Function to generate price forecasts
            use_discrete_actions: Use discrete action space
            render_mode: Rendering mode
        """
        super().__init__()

        self.config = config or EnvironmentConfig()
        self.use_discrete_actions = use_discrete_actions
        self.render_mode = render_mode

        # Initialize components
        self.battery = BatteryModel(self.config.battery)
        self.market = MarketSimulator(self.config.market, self.config.seed)

        # Forecast functions (use synthetic if not provided)
        self.load_forecast_fn = load_forecast_fn or self._synthetic_load_forecast
        self.price_forecast_fn = price_forecast_fn or self._synthetic_price_forecast

        # Define observation space
        # SOC (1) + Hour (1) + Day type (3) + Load forecast (24) + Price forecast (24) +
        # Current price (1) + Spread (1) + Position (1) + Balance (1) + Reputation (1)
        obs_dim = 1 + 1 + 3 + self.config.forecast_horizon * 2 + 5
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(obs_dim,),
            dtype=np.float32,
        )

        # Define action space
        if use_discrete_actions:
            # Quantity: 5 levels, Price: 5 levels
            self.action_space = spaces.MultiDiscrete([5, 5])
            self.quantity_levels = [-1.0, -0.5, 0.0, 0.5, 1.0]
            self.price_levels = [-0.1, -0.05, 0.0, 0.05, 0.1]
        else:
            # Continuous: [quantity (-1 to 1), aggressiveness (0 to 1)]
            self.action_space = spaces.Box(
                low=np.array([-1.0, 0.0]),
                high=np.array([1.0, 1.0]),
                dtype=np.float32,
            )

        # Episode state
        self.current_step = 0
        self.current_hour = 0
        self.day_type = DayType.WEEKDAY
        self.shakti_balance = self.config.initial_shakti_balance
        self.reputation = self.config.initial_reputation
        self.current_position = 0.0
        self.episode_profit = 0.0
        self.episode_trades = []

        # Forecasts
        self.load_forecast = np.zeros(self.config.forecast_horizon)
        self.price_forecast = np.zeros(self.config.forecast_horizon)

        # For rendering
        self.history = {
            "soc": [],
            "price": [],
            "action": [],
            "reward": [],
            "profit": [],
        }

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Reset environment to initial state.

        Args:
            seed: Random seed
            options: Reset options

        Returns:
            observation: Initial observation
            info: Additional information
        """
        super().reset(seed=seed)

        if seed is not None:
            self.np_random = np.random.default_rng(seed)

        # Reset battery with random initial SOC
        initial_soc = options.get("initial_soc") if options else None
        if initial_soc is None:
            initial_soc = self.np_random.uniform(0.3, 0.8)
        self.battery.reset(initial_soc)

        # Reset market
        self.market.reset()

        # Reset episode state
        self.current_step = 0
        self.current_hour = 0
        self.day_type = DayType(self.np_random.integers(0, 3))
        self.shakti_balance = self.config.initial_shakti_balance
        self.reputation = self.config.initial_reputation
        self.current_position = 0.0
        self.episode_profit = 0.0
        self.episode_trades = []

        # Generate initial forecasts
        self._update_forecasts()

        # Generate initial price
        self.market.generate_price(
            self.current_hour,
            self.load_forecast[0],
            self.day_type,
        )

        # Clear history
        self.history = {
            "soc": [self.battery.soc],
            "price": [self.market.current_price],
            "action": [],
            "reward": [],
            "profit": [0.0],
        }

        observation = self._get_observation()
        info = self._get_info()

        return observation, info

    def step(
        self,
        action: Union[np.ndarray, Tuple[int, int]],
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """Execute one step in the environment.

        Args:
            action: Agent's action

        Returns:
            observation: New observation
            reward: Step reward
            terminated: Whether episode ended
            truncated: Whether episode was truncated
            info: Additional information
        """
        # Parse action
        if self.use_discrete_actions:
            quantity_idx, price_idx = action
            quantity_normalized = self.quantity_levels[quantity_idx]
            price_aggressiveness = 0.5 + self.price_levels[price_idx]
        else:
            quantity_normalized = float(action[0])
            price_aggressiveness = float(action[1])

        # Execute action
        trade_profit, degradation_cost, trade_executed = self._execute_action(
            quantity_normalized,
            price_aggressiveness,
        )

        # Update market
        self.current_step += 1
        self.current_hour = (self.current_hour + 1) % 24

        # Update forecasts
        self._update_forecasts()

        # Generate new price
        self.market.generate_price(
            self.current_hour,
            self.load_forecast[0],
            self.day_type,
        )

        # Calculate reward
        reward = self._calculate_reward(
            trade_profit,
            degradation_cost,
            trade_executed,
        )

        # Check termination
        terminated = self._check_termination()
        truncated = self.current_step >= self.config.episode_length

        # Update history
        self.history["soc"].append(self.battery.soc)
        self.history["price"].append(self.market.current_price)
        self.history["action"].append((quantity_normalized, price_aggressiveness))
        self.history["reward"].append(reward)
        self.history["profit"].append(self.episode_profit)

        observation = self._get_observation()
        info = self._get_info()
        info["trade_executed"] = trade_executed
        info["trade_profit"] = trade_profit

        return observation, reward, terminated, truncated, info

    def _execute_action(
        self,
        quantity_normalized: float,
        price_aggressiveness: float,
    ) -> Tuple[float, float, bool]:
        """Execute trading action.

        Args:
            quantity_normalized: -1 (full sell) to +1 (full buy)
            price_aggressiveness: 0 (passive) to 1 (aggressive)

        Returns:
            profit: Trade profit
            degradation_cost: Battery degradation cost
            executed: Whether trade was executed
        """
        profit = 0.0
        degradation_cost = 0.0
        executed = False

        if abs(quantity_normalized) < 0.1:
            # Hold - no action
            return 0.0, 0.0, False

        if quantity_normalized > 0:
            # Buy energy (charge battery)
            max_charge = self.battery.get_available_charge_capacity()
            quantity_kwh = quantity_normalized * min(
                max_charge,
                self.config.market.max_trade_kwh,
            )

            if quantity_kwh >= self.config.market.min_trade_kwh:
                exec_qty, exec_price, success = self.market.execute_trade(
                    quantity_kwh,
                    price_aggressiveness,
                    is_buy=True,
                )

                if success:
                    energy_stored, deg_cost = self.battery.charge(exec_qty)
                    cost = exec_qty * exec_price
                    profit = -cost  # Negative profit for buying
                    degradation_cost = deg_cost
                    executed = True

                    self.episode_profit += profit - deg_cost
                    self.episode_trades.append({
                        "type": "buy",
                        "quantity": exec_qty,
                        "price": exec_price,
                        "hour": self.current_hour,
                    })
        else:
            # Sell energy (discharge battery)
            max_discharge = self.battery.get_available_discharge_capacity()
            quantity_kwh = abs(quantity_normalized) * min(
                max_discharge,
                self.config.market.max_trade_kwh,
            )

            if quantity_kwh >= self.config.market.min_trade_kwh:
                exec_qty, exec_price, success = self.market.execute_trade(
                    quantity_kwh,
                    price_aggressiveness,
                    is_buy=False,
                )

                if success:
                    energy_delivered, deg_cost = self.battery.discharge(exec_qty)
                    revenue = energy_delivered * exec_price
                    profit = revenue
                    degradation_cost = deg_cost
                    executed = True

                    self.episode_profit += profit - deg_cost
                    self.episode_trades.append({
                        "type": "sell",
                        "quantity": energy_delivered,
                        "price": exec_price,
                        "hour": self.current_hour,
                    })

        return profit, degradation_cost, executed

    def _calculate_reward(
        self,
        trade_profit: float,
        degradation_cost: float,
        trade_executed: bool,
    ) -> float:
        """Calculate step reward.

        Components:
        - Trading profit
        - Battery health (negative for degradation)
        - Grid service bonus
        - Reputation bonus
        - Penalties for constraint violations
        """
        cfg = self.config.reward

        # Profit component
        profit_reward = trade_profit * cfg.profit_weight

        # Battery health component (penalize degradation)
        health_reward = -degradation_cost * cfg.battery_health_weight

        # Grid service bonus (providing services during peak hours)
        grid_reward = 0.0
        if trade_executed and self.current_hour in [18, 19, 20, 21]:
            grid_reward = cfg.frequency_regulation_bonus * cfg.grid_service_weight

        # Reputation bonus
        reputation_reward = (self.reputation / ReputationTier.DIAMOND) * cfg.reputation_weight

        # Penalties
        penalties = 0.0

        # Low SOC penalty
        if self.battery.soc < self.config.battery.min_soc + 0.1:
            penalties += cfg.low_soc_penalty

        # High SOC penalty (overcharging)
        if self.battery.soc > self.config.battery.max_soc - 0.05:
            penalties += cfg.high_soc_penalty

        total_reward = profit_reward + health_reward + grid_reward + reputation_reward + penalties

        return total_reward

    def _check_termination(self) -> bool:
        """Check if episode should terminate early."""
        # Bankrupt
        if self.shakti_balance <= 0:
            return True

        # Battery completely degraded
        if self.battery.get_health() < 0.5:
            return True

        return False

    def _get_observation(self) -> np.ndarray:
        """Build observation vector."""
        obs = []

        # Battery SOC
        obs.append(self.battery.soc)

        # Current hour (normalized)
        obs.append(self.current_hour / 23.0)

        # Day type (one-hot)
        day_type_onehot = [0.0, 0.0, 0.0]
        day_type_onehot[self.day_type] = 1.0
        obs.extend(day_type_onehot)

        # Load forecast (normalized)
        load_norm = self.load_forecast / (self.load_forecast.max() + 1e-8)
        obs.extend(load_norm.tolist())

        # Price forecast (normalized)
        price_norm = self.price_forecast / (self.config.market.base_price * 5)
        obs.extend(np.clip(price_norm, 0, 1).tolist())

        # Current price (normalized)
        price_normalized = self.market.current_price / (self.config.market.base_price * 5)
        obs.append(np.clip(price_normalized, 0, 1))

        # Bid-ask spread (normalized)
        spread = (self.market.ask_price - self.market.bid_price) / self.market.current_price
        obs.append(np.clip(spread, 0, 1))

        # Current position (normalized, -1 to 1 mapped to 0 to 1)
        position_norm = (self.current_position + 1) / 2
        obs.append(np.clip(position_norm, 0, 1))

        # SHAKTI balance (normalized)
        balance_norm = self.shakti_balance / (self.config.initial_shakti_balance * 2)
        obs.append(np.clip(balance_norm, 0, 1))

        # Reputation (normalized)
        reputation_norm = self.reputation / ReputationTier.DIAMOND
        obs.append(reputation_norm)

        return np.array(obs, dtype=np.float32)

    def _get_info(self) -> Dict[str, Any]:
        """Get additional information."""
        return {
            "soc": self.battery.soc,
            "hour": self.current_hour,
            "day_type": self.day_type.name,
            "market_price": self.market.current_price,
            "bid_price": self.market.bid_price,
            "ask_price": self.market.ask_price,
            "shakti_balance": self.shakti_balance,
            "reputation": self.reputation,
            "episode_profit": self.episode_profit,
            "battery_health": self.battery.get_health(),
            "total_cycles": self.battery.total_cycles,
            "num_trades": len(self.episode_trades),
        }

    def _update_forecasts(self):
        """Update load and price forecasts."""
        self.load_forecast = self.load_forecast_fn(
            self.current_hour,
            self.day_type,
            self.config.forecast_horizon,
        )
        self.price_forecast = self.price_forecast_fn(
            self.current_hour,
            self.day_type,
            self.config.forecast_horizon,
        )

    def _synthetic_load_forecast(
        self,
        current_hour: int,
        day_type: DayType,
        horizon: int,
    ) -> np.ndarray:
        """Generate synthetic load forecast."""
        forecast = np.zeros(horizon)

        for i in range(horizon):
            hour = (current_hour + i) % 24

            # Base load pattern
            if 6 <= hour <= 10:
                base = 0.7 + 0.1 * (hour - 6)
            elif 18 <= hour <= 22:
                base = 0.8 + 0.1 * (hour - 18)
            elif 0 <= hour <= 5:
                base = 0.4
            else:
                base = 0.6

            # Day type adjustment
            if day_type == DayType.WEEKEND:
                base *= 0.85
            elif day_type == DayType.HOLIDAY:
                base *= 0.75

            # Add noise
            noise = self.np_random.normal(0, 0.05)
            forecast[i] = np.clip(base + noise, 0.2, 1.0)

        return forecast

    def _synthetic_price_forecast(
        self,
        current_hour: int,
        day_type: DayType,
        horizon: int,
    ) -> np.ndarray:
        """Generate synthetic price forecast."""
        forecast = np.zeros(horizon)
        base_price = self.config.market.base_price

        for i in range(horizon):
            hour = (current_hour + i) % 24

            # Price pattern follows load
            hour_factor = self.market._get_hour_factor(hour)

            # Day type
            day_factor = {
                DayType.WEEKDAY: 1.0,
                DayType.WEEKEND: 0.85,
                DayType.HOLIDAY: 0.75,
            }[day_type]

            price = base_price * hour_factor * day_factor

            # Add uncertainty that increases with horizon
            uncertainty = 0.05 * (1 + i / horizon)
            noise = self.np_random.normal(0, base_price * uncertainty)

            forecast[i] = max(base_price * 0.3, price + noise)

        return forecast

    def render(self):
        """Render the environment."""
        if self.render_mode == "human":
            self._render_human()
        elif self.render_mode == "rgb_array":
            return self._render_rgb_array()

    def _render_human(self):
        """Print current state to console."""
        print(f"\n{'='*50}")
        print(f"Step: {self.current_step} | Hour: {self.current_hour}:00 | {self.day_type.name}")
        print(f"{'='*50}")
        print(f"Battery SOC: {self.battery.soc*100:.1f}%")
        print(f"Battery Health: {self.battery.get_health()*100:.1f}%")
        print(f"Market Price: ₹{self.market.current_price:.2f}/kWh")
        print(f"Bid: ₹{self.market.bid_price:.2f} | Ask: ₹{self.market.ask_price:.2f}")
        print(f"Episode Profit: ₹{self.episode_profit:.2f}")
        print(f"SHAKTI Balance: {self.shakti_balance:.2f}")
        print(f"Trades: {len(self.episode_trades)}")

    def _render_rgb_array(self) -> np.ndarray:
        """Render to RGB array for visualization."""
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')

            fig, axes = plt.subplots(2, 2, figsize=(12, 8))

            # SOC history
            axes[0, 0].plot(self.history["soc"], "b-", linewidth=2)
            axes[0, 0].axhline(y=self.config.battery.min_soc, color="r", linestyle="--", label="Min SOC")
            axes[0, 0].axhline(y=self.config.battery.max_soc, color="g", linestyle="--", label="Max SOC")
            axes[0, 0].set_ylabel("SOC")
            axes[0, 0].set_title("Battery State of Charge")
            axes[0, 0].legend()
            axes[0, 0].set_ylim(0, 1)

            # Price history
            axes[0, 1].plot(self.history["price"], "g-", linewidth=2)
            axes[0, 1].set_ylabel("Price (₹/kWh)")
            axes[0, 1].set_title("Market Price")

            # Profit history
            axes[1, 0].plot(self.history["profit"], "orange", linewidth=2)
            axes[1, 0].axhline(y=0, color="k", linestyle="-", alpha=0.3)
            axes[1, 0].set_ylabel("Cumulative Profit (₹)")
            axes[1, 0].set_xlabel("Step")
            axes[1, 0].set_title("Episode Profit")

            # Reward history
            if self.history["reward"]:
                axes[1, 1].bar(range(len(self.history["reward"])), self.history["reward"])
                axes[1, 1].set_ylabel("Reward")
                axes[1, 1].set_xlabel("Step")
                axes[1, 1].set_title("Step Rewards")

            plt.tight_layout()

            # Convert to RGB array
            fig.canvas.draw()
            img = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            img = img.reshape(fig.canvas.get_width_height()[::-1] + (3,))

            plt.close(fig)

            return img
        except ImportError:
            return np.zeros((480, 640, 3), dtype=np.uint8)

    def close(self):
        """Clean up resources."""
        pass


class V2GEnvironment:
    """Backward-compatible wrapper around V2GTradingEnv for legacy tests."""

    def __init__(
        self,
        battery_capacity: float = 60.0,
        initial_soc: float = 0.5,
        max_charge_rate: float = 11.0,
        max_discharge_rate: float = 11.0,
        seed: Optional[int] = None,
    ):
        config = EnvironmentConfig(
            battery=BatteryConfig(
                capacity_kwh=battery_capacity,
                max_charge_rate_kw=max_charge_rate,
                max_discharge_rate_kw=max_discharge_rate,
                initial_soc=initial_soc,
            ),
            seed=seed,
        )
        self._initial_soc = initial_soc
        self._env = V2GTradingEnv(config=config, use_discrete_actions=True)

    def _to_legacy_obs(self, obs: np.ndarray) -> Dict[str, Any]:
        horizon = self._env.config.forecast_horizon
        current_price_idx = 5 + (2 * horizon)
        return {
            "battery_soc": float(obs[0]),
            "time_of_day": int(round(float(obs[1]) * 23)),
            "grid_price": float(obs[current_price_idx]) * self._env.config.market.base_price * 5.0,
            "observation_vector": obs,
        }

    def reset(self) -> Dict[str, Any]:
        obs, _info = self._env.reset(options={"initial_soc": self._initial_soc})
        return self._to_legacy_obs(obs)

    def step(self, action: int):
        # Legacy action mapping: 0=hold, 1=charge, 2=discharge
        action_map = {
            0: (2, 2),  # hold, mid price
            1: (3, 2),  # charge moderately
            2: (1, 2),  # discharge moderately
        }
        mapped_action = action_map.get(int(action), (2, 2))
        obs, reward, terminated, truncated, info = self._env.step(mapped_action)
        done = bool(terminated or truncated)
        return self._to_legacy_obs(obs), float(reward), done, info

    def close(self):
        self._env.close()
