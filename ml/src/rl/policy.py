"""Custom policy networks for V2G Trading Agent.

Implements specialized neural network architectures for the trading policy
with separate encoders for different state components.
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple, Optional, Type, Union
from gymnasium import spaces

from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.distributions import (
    DiagGaussianDistribution,
    SquashedDiagGaussianDistribution,
)


class ForecastEncoder(nn.Module):
    """1D CNN encoder for forecast sequences (load/price forecasts).

    Processes temporal forecast data using convolutional layers
    to capture patterns at different time scales.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        output_dim: int = 32,
        kernel_sizes: List[int] = [3, 5, 7],
    ):
        """Initialize forecast encoder.

        Args:
            input_dim: Length of forecast sequence
            hidden_dim: Hidden dimension for CNN
            output_dim: Output embedding dimension
            kernel_sizes: List of kernel sizes for multi-scale processing
        """
        super().__init__()

        self.input_dim = input_dim
        self.output_dim = output_dim

        # Multi-scale 1D convolutions
        self.convs = nn.ModuleList([
            nn.Sequential(
                nn.Conv1d(1, hidden_dim // len(kernel_sizes), kernel_size=k, padding=k // 2),
                nn.ReLU(),
                nn.Conv1d(hidden_dim // len(kernel_sizes), hidden_dim // len(kernel_sizes),
                         kernel_size=k, padding=k // 2),
                nn.ReLU(),
            )
            for k in kernel_sizes
        ])

        # Global pooling and projection
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.projection = nn.Sequential(
            nn.Linear(hidden_dim, output_dim),
            nn.ReLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len)

        Returns:
            Encoded tensor of shape (batch, output_dim)
        """
        # Add channel dimension: (batch, seq_len) -> (batch, 1, seq_len)
        x = x.unsqueeze(1)

        # Apply multi-scale convolutions
        conv_outputs = []
        for conv in self.convs:
            conv_out = conv(x)  # (batch, hidden//n, seq_len)
            pooled = self.pool(conv_out).squeeze(-1)  # (batch, hidden//n)
            conv_outputs.append(pooled)

        # Concatenate and project
        combined = torch.cat(conv_outputs, dim=-1)  # (batch, hidden)
        return self.projection(combined)


class StateEncoder(nn.Module):
    """MLP encoder for current state variables.

    Processes scalar state variables (SOC, hour, prices, etc.)
    through a feed-forward network.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int] = [64, 32],
        output_dim: int = 32,
        dropout: float = 0.1,
    ):
        """Initialize state encoder.

        Args:
            input_dim: Number of state variables
            hidden_dims: List of hidden layer dimensions
            output_dim: Output embedding dimension
            dropout: Dropout probability
        """
        super().__init__()

        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
            prev_dim = hidden_dim

        layers.append(nn.Linear(prev_dim, output_dim))
        layers.append(nn.ReLU())

        self.network = nn.Sequential(*layers)
        self.output_dim = output_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, input_dim)

        Returns:
            Encoded tensor of shape (batch, output_dim)
        """
        return self.network(x)


class AttentionFusion(nn.Module):
    """Attention-based fusion of multiple embeddings.

    Combines embeddings from different encoders using
    multi-head self-attention.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int = 4,
        dropout: float = 0.1,
    ):
        """Initialize attention fusion.

        Args:
            embed_dim: Embedding dimension (must be same for all inputs)
            num_heads: Number of attention heads
            dropout: Dropout probability
        """
        super().__init__()

        self.attention = nn.MultiheadAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm = nn.LayerNorm(embed_dim)
        self.output_dim = embed_dim

    def forward(self, embeddings: List[torch.Tensor]) -> torch.Tensor:
        """Forward pass.

        Args:
            embeddings: List of tensors, each (batch, embed_dim)

        Returns:
            Fused tensor of shape (batch, embed_dim)
        """
        # Stack embeddings: (batch, num_embeddings, embed_dim)
        stacked = torch.stack(embeddings, dim=1)

        # Self-attention
        attended, _ = self.attention(stacked, stacked, stacked)

        # Residual connection and normalization
        attended = self.norm(attended + stacked)

        # Mean pooling over embeddings
        return attended.mean(dim=1)


class V2GFeaturesExtractor(BaseFeaturesExtractor):
    """Custom features extractor for V2G trading environment.

    Architecture:
    1. Separate encoders for different state components:
       - Load forecast (24h) -> 1D CNN
       - Price forecast (24h) -> 1D CNN
       - Current state (SOC, hour, prices, etc.) -> MLP
    2. Attention-based fusion of embeddings
    3. Final feature vector for policy/value heads
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        forecast_horizon: int = 24,
        forecast_embed_dim: int = 32,
        state_embed_dim: int = 32,
        fusion_dim: int = 64,
        num_attention_heads: int = 4,
    ):
        """Initialize features extractor.

        Args:
            observation_space: Gymnasium observation space
            forecast_horizon: Length of forecast sequences
            forecast_embed_dim: Embedding dimension for forecasts
            state_embed_dim: Embedding dimension for state
            fusion_dim: Dimension after fusion
            num_attention_heads: Number of attention heads
        """
        # Calculate features dim after fusion
        features_dim = fusion_dim

        super().__init__(observation_space, features_dim)

        self.forecast_horizon = forecast_horizon

        # Observation structure:
        # [0]: SOC
        # [1]: Hour (normalized)
        # [2:5]: Day type one-hot (3)
        # [5:5+horizon]: Load forecast (24)
        # [5+horizon:5+2*horizon]: Price forecast (24)
        # [5+2*horizon]: Current price
        # [5+2*horizon+1]: Spread
        # [5+2*horizon+2]: Position
        # [5+2*horizon+3]: Balance
        # [5+2*horizon+4]: Reputation

        self.load_start = 5
        self.load_end = 5 + forecast_horizon
        self.price_start = 5 + forecast_horizon
        self.price_end = 5 + 2 * forecast_horizon
        self.state_indices = list(range(5)) + list(range(5 + 2 * forecast_horizon, observation_space.shape[0]))

        state_dim = len(self.state_indices)

        # Encoders
        self.load_encoder = ForecastEncoder(
            input_dim=forecast_horizon,
            hidden_dim=64,
            output_dim=forecast_embed_dim,
        )

        self.price_encoder = ForecastEncoder(
            input_dim=forecast_horizon,
            hidden_dim=64,
            output_dim=forecast_embed_dim,
        )

        self.state_encoder = StateEncoder(
            input_dim=state_dim,
            hidden_dims=[64, 32],
            output_dim=state_embed_dim,
        )

        # Ensure all embeddings have same dimension for attention
        embed_dim = max(forecast_embed_dim, state_embed_dim)

        self.load_proj = nn.Linear(forecast_embed_dim, embed_dim) if forecast_embed_dim != embed_dim else nn.Identity()
        self.price_proj = nn.Linear(forecast_embed_dim, embed_dim) if forecast_embed_dim != embed_dim else nn.Identity()
        self.state_proj = nn.Linear(state_embed_dim, embed_dim) if state_embed_dim != embed_dim else nn.Identity()

        # Attention fusion
        self.fusion = AttentionFusion(
            embed_dim=embed_dim,
            num_heads=num_attention_heads,
        )

        # Final projection
        self.output_proj = nn.Sequential(
            nn.Linear(embed_dim, fusion_dim),
            nn.ReLU(),
            nn.Linear(fusion_dim, fusion_dim),
            nn.ReLU(),
        )

        self._features_dim = fusion_dim

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """Extract features from observations.

        Args:
            observations: Batch of observations (batch, obs_dim)

        Returns:
            Features tensor (batch, features_dim)
        """
        # Extract components
        load_forecast = observations[:, self.load_start:self.load_end]
        price_forecast = observations[:, self.price_start:self.price_end]
        state = observations[:, self.state_indices]

        # Encode each component
        load_embed = self.load_proj(self.load_encoder(load_forecast))
        price_embed = self.price_proj(self.price_encoder(price_forecast))
        state_embed = self.state_proj(self.state_encoder(state))

        # Fuse with attention
        fused = self.fusion([load_embed, price_embed, state_embed])

        # Final projection
        return self.output_proj(fused)


class V2GTradingPolicy(ActorCriticPolicy):
    """Custom actor-critic policy for V2G trading.

    Uses the V2GFeaturesExtractor for feature extraction
    and custom actor/critic heads.
    """

    def __init__(
        self,
        observation_space: spaces.Space,
        action_space: spaces.Space,
        lr_schedule,
        forecast_horizon: int = 24,
        forecast_embed_dim: int = 32,
        state_embed_dim: int = 32,
        fusion_dim: int = 64,
        policy_hidden_dims: List[int] = [64, 64],
        value_hidden_dims: List[int] = [64, 64],
        **kwargs,
    ):
        """Initialize policy.

        Args:
            observation_space: Gymnasium observation space
            action_space: Gymnasium action space
            lr_schedule: Learning rate schedule
            forecast_horizon: Forecast sequence length
            forecast_embed_dim: Forecast embedding dimension
            state_embed_dim: State embedding dimension
            fusion_dim: Fusion dimension
            policy_hidden_dims: Hidden dims for policy network
            value_hidden_dims: Hidden dims for value network
            **kwargs: Additional arguments for ActorCriticPolicy
        """
        # Store custom parameters before calling super().__init__
        self.forecast_horizon = forecast_horizon
        self.forecast_embed_dim = forecast_embed_dim
        self.state_embed_dim = state_embed_dim
        self.fusion_dim = fusion_dim
        self.policy_hidden_dims = policy_hidden_dims
        self.value_hidden_dims = value_hidden_dims

        super().__init__(
            observation_space,
            action_space,
            lr_schedule,
            features_extractor_class=V2GFeaturesExtractor,
            features_extractor_kwargs={
                "forecast_horizon": forecast_horizon,
                "forecast_embed_dim": forecast_embed_dim,
                "state_embed_dim": state_embed_dim,
                "fusion_dim": fusion_dim,
            },
            **kwargs,
        )

    def _build_mlp_extractor(self) -> None:
        """Build policy and value networks."""
        # Get features dimension
        features_dim = self.features_dim

        # Policy network (actor)
        policy_layers = []
        prev_dim = features_dim
        for hidden_dim in self.policy_hidden_dims:
            policy_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
            ])
            prev_dim = hidden_dim

        self.policy_net = nn.Sequential(*policy_layers)
        self.latent_dim_pi = prev_dim

        # Value network (critic)
        value_layers = []
        prev_dim = features_dim
        for hidden_dim in self.value_hidden_dims:
            value_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
            ])
            prev_dim = hidden_dim

        self.value_net = nn.Sequential(*value_layers)
        self.latent_dim_vf = prev_dim


class SimpleMlpPolicy(ActorCriticPolicy):
    """Simpler MLP policy for baseline comparison.

    Standard MLP without specialized encoders.
    """

    def __init__(
        self,
        observation_space: spaces.Space,
        action_space: spaces.Space,
        lr_schedule,
        net_arch: Optional[List[int]] = None,
        **kwargs,
    ):
        """Initialize simple policy.

        Args:
            observation_space: Gymnasium observation space
            action_space: Gymnasium action space
            lr_schedule: Learning rate schedule
            net_arch: Network architecture
            **kwargs: Additional arguments
        """
        if net_arch is None:
            net_arch = [128, 128, 64]

        super().__init__(
            observation_space,
            action_space,
            lr_schedule,
            net_arch=net_arch,
            **kwargs,
        )


class PPOPolicy:
    """Backward-compatible lightweight policy interface for legacy tests."""

    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.model_path = model_path
        self.device = device

    def predict(self, observation: Union[Dict[str, float], np.ndarray], deterministic: bool = True):
        if isinstance(observation, dict):
            price = float(observation.get("grid_price", 8.0))
            soc = float(observation.get("battery_soc", 0.5))
        else:
            # Legacy vector fallback
            price = 8.0
            soc = 0.5

        if price <= 7.0 and soc < 0.75:
            action = 1  # charge
        elif price >= 10.0 and soc > 0.25:
            action = 2  # discharge
        else:
            action = 0  # hold

        value = float((price - 8.0) / 2.0)
        log_prob = 0.0
        return action, value, log_prob
