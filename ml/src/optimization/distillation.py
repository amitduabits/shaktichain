"""Knowledge distillation for model compression.

Train smaller, faster models that approximate the behavior
of larger teacher models.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


@dataclass
class DistillationConfig:
    """Configuration for knowledge distillation."""

    # Temperature for softening distributions
    temperature: float = 4.0

    # Loss weights
    alpha: float = 0.7  # Weight for distillation loss
    beta: float = 0.3   # Weight for task loss

    # Training
    learning_rate: float = 1e-4
    epochs: int = 50
    batch_size: int = 32

    # Architecture
    student_hidden_size: Optional[int] = None
    student_num_layers: Optional[int] = None

    # Advanced
    use_attention_transfer: bool = False
    use_feature_matching: bool = False
    intermediate_layers: Optional[List[str]] = None


@dataclass
class DistillationResult:
    """Result of knowledge distillation."""

    teacher_size_mb: float
    student_size_mb: float
    compression_ratio: float
    teacher_latency_ms: float
    student_latency_ms: float
    speedup: float
    teacher_accuracy: float
    student_accuracy: float
    accuracy_retention: float  # student/teacher accuracy ratio
    final_loss: float
    epochs_trained: int


class DistillationLoss(nn.Module):
    """Combined loss for knowledge distillation.

    Combines:
    - Soft target loss (KL divergence from teacher)
    - Hard target loss (cross-entropy with true labels)
    - Optional: Feature matching loss
    """

    def __init__(
        self,
        temperature: float = 4.0,
        alpha: float = 0.7,
        beta: float = 0.3,
    ):
        """Initialize distillation loss.

        Args:
            temperature: Softmax temperature
            alpha: Weight for soft target loss
            beta: Weight for hard target loss
        """
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha
        self.beta = beta

    def forward(
        self,
        student_logits: "torch.Tensor",
        teacher_logits: "torch.Tensor",
        labels: Optional["torch.Tensor"] = None,
        task_loss_fn: Optional[Callable] = None,
    ) -> "torch.Tensor":
        """Compute distillation loss.

        Args:
            student_logits: Student model outputs
            teacher_logits: Teacher model outputs
            labels: True labels (optional)
            task_loss_fn: Custom task loss function

        Returns:
            Combined loss
        """
        # Soft target loss (KL divergence)
        soft_targets = F.softmax(teacher_logits / self.temperature, dim=-1)
        soft_predictions = F.log_softmax(student_logits / self.temperature, dim=-1)

        # KL divergence * T^2 (to match gradient magnitude)
        distillation_loss = F.kl_div(
            soft_predictions,
            soft_targets,
            reduction="batchmean",
        ) * (self.temperature ** 2)

        # Hard target loss (if labels provided)
        if labels is not None and self.beta > 0:
            if task_loss_fn is not None:
                task_loss = task_loss_fn(student_logits, labels)
            else:
                task_loss = F.cross_entropy(student_logits, labels)

            total_loss = self.alpha * distillation_loss + self.beta * task_loss
        else:
            total_loss = distillation_loss

        return total_loss


class RegressionDistillationLoss(nn.Module):
    """Distillation loss for regression tasks."""

    def __init__(self, alpha: float = 0.7, beta: float = 0.3):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.mse = nn.MSELoss()

    def forward(
        self,
        student_output: "torch.Tensor",
        teacher_output: "torch.Tensor",
        labels: Optional["torch.Tensor"] = None,
    ) -> "torch.Tensor":
        """Compute regression distillation loss."""
        distillation_loss = self.mse(student_output, teacher_output)

        if labels is not None and self.beta > 0:
            task_loss = self.mse(student_output, labels)
            return self.alpha * distillation_loss + self.beta * task_loss

        return distillation_loss


class ModelDistiller:
    """Knowledge distillation trainer.

    Example:
        >>> distiller = ModelDistiller(teacher_model, config)
        >>> student = distiller.create_student_model(input_size, output_size)
        >>> result = distiller.distill(student, train_loader, val_loader)
        >>> print(f"Compression: {result.compression_ratio:.1f}x")
        >>> print(f"Speedup: {result.speedup:.1f}x")
    """

    def __init__(
        self,
        teacher: "nn.Module",
        config: Optional[DistillationConfig] = None,
        device: str = "cpu",
    ):
        """Initialize distiller.

        Args:
            teacher: Teacher model
            config: Distillation configuration
            device: Device for training
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required for distillation")

        self.teacher = teacher
        self.config = config or DistillationConfig()
        self.device = device

        self.teacher.to(device)
        self.teacher.eval()

        # Calculate teacher size
        self.teacher_size_mb = self._calculate_model_size(teacher)

    def create_student_model(
        self,
        input_size: int,
        output_size: int,
        hidden_size: Optional[int] = None,
        num_layers: Optional[int] = None,
        model_type: str = "mlp",
    ) -> "nn.Module":
        """Create a smaller student model.

        Args:
            input_size: Input feature size
            output_size: Output size
            hidden_size: Hidden layer size (default: half of teacher)
            num_layers: Number of hidden layers (default: half of teacher)
            model_type: Model architecture ("mlp", "lstm", "attention")

        Returns:
            Student model
        """
        hidden_size = hidden_size or self.config.student_hidden_size or 64
        num_layers = num_layers or self.config.student_num_layers or 2

        if model_type == "mlp":
            layers = []
            prev_size = input_size

            for i in range(num_layers):
                layers.extend([
                    nn.Linear(prev_size, hidden_size),
                    nn.ReLU(),
                    nn.Dropout(0.1),
                ])
                prev_size = hidden_size

            layers.append(nn.Linear(hidden_size, output_size))

            return nn.Sequential(*layers)

        elif model_type == "lstm":
            return _LSTMStudent(input_size, hidden_size, output_size, num_layers)

        elif model_type == "attention":
            return _AttentionStudent(input_size, hidden_size, output_size, num_layers)

        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def distill(
        self,
        student: "nn.Module",
        train_loader: "DataLoader",
        val_loader: Optional["DataLoader"] = None,
        task: str = "classification",
    ) -> DistillationResult:
        """Train student model through distillation.

        Args:
            student: Student model to train
            train_loader: Training data loader
            val_loader: Validation data loader
            task: "classification" or "regression"

        Returns:
            DistillationResult
        """
        student = student.to(self.device)
        student.train()

        # Setup loss
        if task == "classification":
            criterion = DistillationLoss(
                temperature=self.config.temperature,
                alpha=self.config.alpha,
                beta=self.config.beta,
            )
        else:
            criterion = RegressionDistillationLoss(
                alpha=self.config.alpha,
                beta=self.config.beta,
            )

        # Setup optimizer
        optimizer = torch.optim.AdamW(
            student.parameters(),
            lr=self.config.learning_rate,
        )

        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=self.config.epochs,
        )

        # Training loop
        best_loss = float("inf")
        history = []

        for epoch in range(self.config.epochs):
            student.train()
            epoch_loss = 0.0

            for batch in train_loader:
                if isinstance(batch, (list, tuple)):
                    inputs, labels = batch[0].to(self.device), batch[1].to(self.device)
                else:
                    inputs = batch.to(self.device)
                    labels = None

                # Get teacher predictions
                with torch.no_grad():
                    teacher_output = self.teacher(inputs)
                    if isinstance(teacher_output, tuple):
                        teacher_output = teacher_output[0]

                # Get student predictions
                student_output = student(inputs)
                if isinstance(student_output, tuple):
                    student_output = student_output[0]

                # Compute loss
                loss = criterion(student_output, teacher_output, labels)

                # Backward pass
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

            scheduler.step()

            avg_loss = epoch_loss / len(train_loader)
            history.append(avg_loss)

            if avg_loss < best_loss:
                best_loss = avg_loss

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.config.epochs}, Loss: {avg_loss:.4f}")

        # Evaluate
        teacher_metrics = self._evaluate(self.teacher, val_loader or train_loader, task)
        student_metrics = self._evaluate(student, val_loader or train_loader, task)

        # Benchmark
        sample_input = next(iter(train_loader))
        if isinstance(sample_input, (list, tuple)):
            sample_input = sample_input[0]
        sample_input = sample_input[:1].to(self.device)

        teacher_latency = self._benchmark_latency(self.teacher, sample_input)
        student_latency = self._benchmark_latency(student, sample_input)

        student_size = self._calculate_model_size(student)

        return DistillationResult(
            teacher_size_mb=self.teacher_size_mb,
            student_size_mb=student_size,
            compression_ratio=self.teacher_size_mb / student_size,
            teacher_latency_ms=teacher_latency,
            student_latency_ms=student_latency,
            speedup=teacher_latency / student_latency,
            teacher_accuracy=teacher_metrics["accuracy"],
            student_accuracy=student_metrics["accuracy"],
            accuracy_retention=student_metrics["accuracy"] / (teacher_metrics["accuracy"] + 1e-6),
            final_loss=best_loss,
            epochs_trained=self.config.epochs,
        )

    def _evaluate(
        self,
        model: "nn.Module",
        data_loader: "DataLoader",
        task: str,
    ) -> Dict[str, float]:
        """Evaluate model performance."""
        model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch in data_loader:
                if isinstance(batch, (list, tuple)):
                    inputs, labels = batch[0].to(self.device), batch[1].to(self.device)
                else:
                    continue  # Skip if no labels

                outputs = model(inputs)
                if isinstance(outputs, tuple):
                    outputs = outputs[0]

                if task == "classification":
                    _, predicted = outputs.max(1)
                    total += labels.size(0)
                    correct += predicted.eq(labels).sum().item()
                else:
                    total_loss += F.mse_loss(outputs, labels).item()
                    total += 1

        if task == "classification":
            accuracy = correct / total if total > 0 else 0.0
        else:
            accuracy = 1.0 / (1.0 + total_loss / max(total, 1))  # Inverse MSE as "accuracy"

        return {"accuracy": accuracy}

    def _benchmark_latency(
        self,
        model: "nn.Module",
        sample_input: "torch.Tensor",
        num_iterations: int = 100,
    ) -> float:
        """Benchmark model latency."""
        import time

        model.eval()

        # Warmup
        with torch.no_grad():
            for _ in range(10):
                model(sample_input)

        # Benchmark
        latencies = []
        with torch.no_grad():
            for _ in range(num_iterations):
                start = time.perf_counter()
                model(sample_input)
                latencies.append((time.perf_counter() - start) * 1000)

        return np.mean(latencies)

    def _calculate_model_size(self, model: "nn.Module") -> float:
        """Calculate model size in MB."""
        import io
        buffer = io.BytesIO()
        torch.save(model.state_dict(), buffer)
        return buffer.tell() / (1024 * 1024)


class _LSTMStudent(nn.Module):
    """LSTM-based student model."""

    def __init__(self, input_size: int, hidden_size: int, output_size: int, num_layers: int):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=0.1 if num_layers > 1 else 0,
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        if x.dim() == 2:
            x = x.unsqueeze(1)
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class _AttentionStudent(nn.Module):
    """Attention-based student model."""

    def __init__(self, input_size: int, hidden_size: int, output_size: int, num_layers: int):
        super().__init__()
        self.embed = nn.Linear(input_size, hidden_size)
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(hidden_size, nhead=4, dim_feedforward=hidden_size * 2, batch_first=True)
            for _ in range(num_layers)
        ])
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        if x.dim() == 2:
            x = x.unsqueeze(1)
        x = self.embed(x)
        for layer in self.layers:
            x = layer(x)
        return self.fc(x.mean(dim=1))


def distill_trading_agent(
    teacher_agent: Any,
    env: Any,
    config: Optional[DistillationConfig] = None,
    num_episodes: int = 1000,
) -> Tuple["nn.Module", DistillationResult]:
    """Distill a trading RL agent into a smaller network.

    Args:
        teacher_agent: Trained RL agent (e.g., PPO)
        env: Trading environment
        config: Distillation config
        num_episodes: Episodes for data collection

    Returns:
        Student policy and distillation result
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required")

    config = config or DistillationConfig()

    # Collect teacher demonstrations
    logger.info(f"Collecting {num_episodes} episodes of teacher demonstrations...")
    observations = []
    actions = []
    action_probs = []

    for _ in range(num_episodes):
        obs = env.reset()
        done = False

        while not done:
            action, _ = teacher_agent.predict(obs, deterministic=False)

            # Get action probabilities
            if hasattr(teacher_agent.policy, "get_distribution"):
                with torch.no_grad():
                    obs_tensor = torch.tensor(obs).unsqueeze(0).float()
                    dist = teacher_agent.policy.get_distribution(obs_tensor)
                    probs = dist.distribution.probs.numpy().flatten()
            else:
                probs = np.zeros(env.action_space.n)
                probs[action] = 1.0

            observations.append(obs)
            actions.append(action)
            action_probs.append(probs)

            obs, _, done, _ = env.step(action)

    # Create dataset
    X = torch.tensor(np.array(observations), dtype=torch.float32)
    y_probs = torch.tensor(np.array(action_probs), dtype=torch.float32)
    y_actions = torch.tensor(np.array(actions), dtype=torch.long)

    dataset = torch.utils.data.TensorDataset(X, y_actions, y_probs)
    loader = DataLoader(dataset, batch_size=config.batch_size, shuffle=True)

    # Create student
    input_size = env.observation_space.shape[0]
    output_size = env.action_space.n
    hidden_size = config.student_hidden_size or 64

    student = nn.Sequential(
        nn.Linear(input_size, hidden_size),
        nn.ReLU(),
        nn.Linear(hidden_size, hidden_size),
        nn.ReLU(),
        nn.Linear(hidden_size, output_size),
    )

    # Train with behavior cloning + distillation
    optimizer = torch.optim.Adam(student.parameters(), lr=config.learning_rate)

    for epoch in range(config.epochs):
        total_loss = 0.0
        for batch_x, batch_actions, batch_probs in loader:
            logits = student(batch_x)

            # Combined loss: CE with actions + KL with teacher probs
            ce_loss = F.cross_entropy(logits, batch_actions)
            kl_loss = F.kl_div(
                F.log_softmax(logits / config.temperature, dim=-1),
                batch_probs,
                reduction="batchmean",
            )

            loss = config.beta * ce_loss + config.alpha * kl_loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch + 1}/{config.epochs}, Loss: {total_loss / len(loader):.4f}")

    # Calculate metrics
    teacher_size = sum(p.numel() * 4 for p in teacher_agent.policy.parameters()) / (1024 * 1024)
    student_size = sum(p.numel() * 4 for p in student.parameters()) / (1024 * 1024)

    result = DistillationResult(
        teacher_size_mb=teacher_size,
        student_size_mb=student_size,
        compression_ratio=teacher_size / student_size,
        teacher_latency_ms=0.0,  # Would need benchmarking
        student_latency_ms=0.0,
        speedup=0.0,
        teacher_accuracy=0.0,
        student_accuracy=0.0,
        accuracy_retention=0.0,
        final_loss=total_loss / len(loader),
        epochs_trained=config.epochs,
    )

    return student, result
