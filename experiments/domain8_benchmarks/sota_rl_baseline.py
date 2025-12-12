"""
SOTA RL Bidding Baseline for SHAKTI-CHAIN Benchmarking (Domain 8).

Implements SOTA RL bidding agent from IEEE Trans. Industrial Informatics 2024.
Uses Deep Q-Network (DQN) for bid price selection.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Check for PyTorch availability
PYTORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    PYTORCH_AVAILABLE = True
except ImportError:
    logger.info("PyTorch not available, using simple Q-table fallback")


@dataclass
class RLState:
    """
    RL agent state representation.

    Attributes:
        market_price: Current market price
        price_trend: Price trend (positive = rising)
        inventory: Own energy inventory
        hour_of_day: Hour of day (0-23)
        day_of_week: Day of week (0-6)
        demand_level: Demand level (low/medium/high)
    """
    market_price: float
    price_trend: float
    inventory: float
    hour_of_day: int
    day_of_week: int
    demand_level: float

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([
            self.market_price / 10.0,  # Normalize
            self.price_trend,
            self.inventory / 100.0,
            self.hour_of_day / 24.0,
            self.day_of_week / 7.0,
            self.demand_level,
        ], dtype=np.float32)


@dataclass
class Experience:
    """Experience tuple for replay buffer."""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    """Experience replay buffer for DQN."""

    def __init__(self, capacity: int = 10000):
        """
        Initialize buffer.

        Args:
            capacity: Maximum buffer size
        """
        self.buffer = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        """Add experience to buffer."""
        self.buffer.append(Experience(state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch from buffer."""
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        return [self.buffer[i] for i in indices]

    def __len__(self) -> int:
        return len(self.buffer)


class DQNetwork:
    """
    Deep Q-Network for RL bidding.

    Architecture from IEEE Trans. Industrial Informatics 2024.
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 64,
        learning_rate: float = 0.001,
    ):
        """
        Initialize DQN.

        Args:
            state_dim: State dimension
            action_dim: Number of discrete actions
            hidden_dim: Hidden layer dimension
            learning_rate: Learning rate
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim

        if PYTORCH_AVAILABLE:
            self._init_pytorch(learning_rate)
        else:
            self._init_simple()

    def _init_pytorch(self, learning_rate: float) -> None:
        """Initialize PyTorch model."""
        self.model = nn.Sequential(
            nn.Linear(self.state_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Linear(self.hidden_dim, self.action_dim),
        )
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.loss_fn = nn.MSELoss()

    def _init_simple(self) -> None:
        """Initialize simple Q-table fallback."""
        self.q_table = np.zeros((100, self.action_dim))  # Discretized states

    def predict(self, state: np.ndarray) -> np.ndarray:
        """Predict Q-values for state."""
        if PYTORCH_AVAILABLE:
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                return self.model(state_tensor).numpy()[0]
        else:
            # Simple discretization for fallback
            state_idx = int(np.sum(state * 10) % 100)
            return self.q_table[state_idx]

    def train_step(
        self,
        states: np.ndarray,
        actions: np.ndarray,
        targets: np.ndarray,
    ) -> float:
        """
        Train on batch.

        Args:
            states: Batch of states
            actions: Batch of actions
            targets: Target Q-values

        Returns:
            Loss value
        """
        if PYTORCH_AVAILABLE:
            state_tensor = torch.FloatTensor(states)
            action_tensor = torch.LongTensor(actions)
            target_tensor = torch.FloatTensor(targets)

            # Get current Q-values
            q_values = self.model(state_tensor)
            q_values = q_values.gather(1, action_tensor.unsqueeze(1)).squeeze(1)

            # Compute loss
            loss = self.loss_fn(q_values, target_tensor)

            # Backprop
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            return loss.item()
        else:
            # Simple Q-table update
            for i, state in enumerate(states):
                state_idx = int(np.sum(state * 10) % 100)
                action = int(actions[i])
                self.q_table[state_idx, action] += 0.1 * (
                    targets[i] - self.q_table[state_idx, action]
                )
            return 0.0


class SOTARLAgent:
    """
    SOTA RL bidding agent from IEEE Trans. Industrial Informatics 2024.

    Uses Deep Q-Network (DQN) with:
    - State: Market prices, own inventory, time features
    - Action: Bid price discretized into 20 levels
    - Reward: Profit from successful trades
    """

    def __init__(
        self,
        state_dim: int = 6,
        action_dim: int = 20,
        epsilon: float = 0.1,
        gamma: float = 0.99,
        learning_rate: float = 0.001,
    ):
        """
        Initialize agent.

        Args:
            state_dim: State dimension
            action_dim: Number of price levels
            epsilon: Exploration rate
            gamma: Discount factor
            learning_rate: Learning rate
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.epsilon = epsilon
        self.gamma = gamma

        # Price multipliers (0.5x to 1.5x base price)
        self.action_space = np.linspace(0.5, 1.5, action_dim)

        # Q-network
        self.q_network = DQNetwork(state_dim, action_dim, learning_rate=learning_rate)
        self.target_network = DQNetwork(state_dim, action_dim, learning_rate=learning_rate)

        # Replay buffer
        self.replay_buffer = ReplayBuffer(capacity=10000)

        # Training stats
        self.training_losses: List[float] = []
        self.episode_rewards: List[float] = []

    def select_action(
        self,
        state: RLState,
        base_price: float = 6.0,
        training: bool = True,
    ) -> Tuple[float, int]:
        """
        Select bid price using epsilon-greedy.

        Args:
            state: Current state
            base_price: Base price to multiply
            training: Whether in training mode

        Returns:
            (bid_price, action_index)
        """
        state_array = state.to_array()

        if training and np.random.random() < self.epsilon:
            # Explore
            action_idx = np.random.randint(self.action_dim)
        else:
            # Exploit
            q_values = self.q_network.predict(state_array)
            action_idx = int(np.argmax(q_values))

        bid_price = base_price * self.action_space[action_idx]
        return bid_price, action_idx

    def train(
        self,
        batch_size: int = 64,
    ) -> Optional[float]:
        """
        Update Q-network using experience replay.

        Args:
            batch_size: Training batch size

        Returns:
            Training loss or None if buffer too small
        """
        if len(self.replay_buffer) < batch_size:
            return None

        # Sample batch
        batch = self.replay_buffer.sample(batch_size)

        states = np.array([e.state for e in batch])
        actions = np.array([e.action for e in batch])
        rewards = np.array([e.reward for e in batch])
        next_states = np.array([e.next_state for e in batch])
        dones = np.array([e.done for e in batch])

        # Calculate targets
        next_q_values = self.target_network.predict(next_states[0])
        for i, ns in enumerate(next_states[1:], 1):
            nq = self.target_network.predict(ns)
            next_q_values = np.vstack([next_q_values, nq]) if i == 1 else np.vstack([next_q_values, nq.reshape(1, -1)])

        if len(next_states) > 1:
            next_q_values = np.array([self.target_network.predict(ns) for ns in next_states])
        else:
            next_q_values = self.target_network.predict(next_states[0]).reshape(1, -1)

        max_next_q = np.max(next_q_values, axis=1)
        targets = rewards + self.gamma * max_next_q * (1 - dones)

        # Train
        loss = self.q_network.train_step(states, actions, targets)
        self.training_losses.append(loss)

        return loss

    def update_target_network(self) -> None:
        """Copy weights to target network."""
        if PYTORCH_AVAILABLE:
            self.target_network.model.load_state_dict(
                self.q_network.model.state_dict()
            )
        else:
            self.target_network.q_table = self.q_table.copy()

    def store_experience(
        self,
        state: RLState,
        action: int,
        reward: float,
        next_state: RLState,
        done: bool,
    ) -> None:
        """Store experience in replay buffer."""
        self.replay_buffer.push(
            state.to_array(),
            action,
            reward,
            next_state.to_array(),
            done,
        )


@dataclass
class RLResult:
    """
    Result from RL agent simulation.

    Attributes:
        total_reward: Total reward earned
        n_trades: Number of successful trades
        avg_reward_per_trade: Average reward per trade
        training_losses: Training loss history
        final_epsilon: Final exploration rate
    """
    total_reward: float = 0.0
    n_trades: int = 0
    avg_reward_per_trade: float = 0.0
    training_losses: List[float] = field(default_factory=list)
    final_epsilon: float = 0.1
    rewards_history: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_reward": self.total_reward,
            "n_trades": self.n_trades,
            "avg_reward_per_trade": self.avg_reward_per_trade,
            "final_epsilon": self.final_epsilon,
            "mean_training_loss": float(np.mean(self.training_losses)) if self.training_losses else 0.0,
        }


class RLSimulator:
    """
    Simulator for RL bidding agents.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize simulator.

        Args:
            seed: Random seed
        """
        self.rng = np.random.default_rng(seed)
        if seed is not None:
            np.random.seed(seed)

    def simulate(
        self,
        n_episodes: int = 100,
        episode_length: int = 24,
        n_agents: int = 10,
        train: bool = True,
    ) -> RLResult:
        """
        Simulate RL trading.

        Args:
            n_episodes: Number of episodes
            episode_length: Steps per episode
            n_agents: Number of RL agents
            train: Whether to train agents

        Returns:
            RLResult
        """
        agents = [
            SOTARLAgent(
                state_dim=6,
                action_dim=20,
                epsilon=0.3 if train else 0.0,
            )
            for _ in range(n_agents)
        ]

        all_rewards = []
        all_losses = []
        n_trades = 0

        for episode in range(n_episodes):
            episode_reward = 0.0

            # Initial state
            market_price = self.rng.uniform(4, 8)
            price_trend = 0.0

            for step in range(episode_length):
                hour = step % 24
                day = step // 24

                # Update market conditions
                market_price += self.rng.normal(0, 0.3)
                market_price = np.clip(market_price, 2, 12)
                price_trend = self.rng.uniform(-0.5, 0.5)
                demand_level = 0.5 + 0.3 * np.sin(2 * np.pi * hour / 24)

                for agent in agents:
                    # Create state
                    state = RLState(
                        market_price=market_price,
                        price_trend=price_trend,
                        inventory=self.rng.uniform(0, 50),
                        hour_of_day=hour,
                        day_of_week=day % 7,
                        demand_level=demand_level,
                    )

                    # Select action
                    bid_price, action_idx = agent.select_action(
                        state, base_price=market_price, training=train
                    )

                    # Simulate trade outcome
                    # Trade succeeds if bid is close to market price
                    price_diff = abs(bid_price - market_price) / market_price
                    trade_prob = max(0, 1 - price_diff * 2)

                    if self.rng.random() < trade_prob:
                        # Successful trade
                        quantity = self.rng.uniform(1, 5)
                        profit = (market_price - bid_price * 0.8) * quantity
                        reward = profit
                        n_trades += 1
                    else:
                        reward = -0.1  # Small penalty for failed trade

                    episode_reward += reward

                    # Next state
                    next_state = RLState(
                        market_price=market_price + self.rng.normal(0, 0.2),
                        price_trend=self.rng.uniform(-0.5, 0.5),
                        inventory=state.inventory + self.rng.uniform(-5, 5),
                        hour_of_day=(hour + 1) % 24,
                        day_of_week=day % 7,
                        demand_level=demand_level + self.rng.uniform(-0.1, 0.1),
                    )

                    # Store experience and train
                    if train:
                        agent.store_experience(
                            state, action_idx, reward, next_state,
                            done=(step == episode_length - 1)
                        )
                        loss = agent.train()
                        if loss is not None:
                            all_losses.append(loss)

            all_rewards.append(episode_reward)

            # Decay epsilon
            if train:
                for agent in agents:
                    agent.epsilon = max(0.01, agent.epsilon * 0.995)

            # Update target networks periodically
            if train and episode % 10 == 0:
                for agent in agents:
                    agent.update_target_network()

        total_reward = sum(all_rewards)
        avg_reward = total_reward / n_trades if n_trades > 0 else 0

        return RLResult(
            total_reward=total_reward,
            n_trades=n_trades,
            avg_reward_per_trade=avg_reward,
            training_losses=all_losses,
            final_epsilon=agents[0].epsilon if agents else 0.1,
            rewards_history=all_rewards,
        )


def simulate_sota_rl(
    n_episodes: int = 100,
    episode_length: int = 24,
    n_agents: int = 10,
    train: bool = True,
    seed: Optional[int] = None,
) -> RLResult:
    """
    Run SOTA RL simulation.

    Args:
        n_episodes: Number of episodes
        episode_length: Steps per episode
        n_agents: Number of agents
        train: Whether to train
        seed: Random seed

    Returns:
        RLResult
    """
    simulator = RLSimulator(seed=seed)
    return simulator.simulate(n_episodes, episode_length, n_agents, train)
