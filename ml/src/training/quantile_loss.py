"""Quantile loss function for TFT."""

import torch
import torch.nn as nn


class QuantileLoss(nn.Module):
    """Quantile loss for multi-quantile forecasting.

    Implements the pinball loss (also known as quantile loss):
        L(y, ŷ, q) = max(q * (y - ŷ), (q - 1) * (y - ŷ))

    Where:
        y: True value
        ŷ: Predicted value
        q: Quantile level (e.g., 0.5 for median)

    For multiple quantiles, the loss is the average across all quantiles.

    Args:
        quantiles: List of quantile levels to predict
    """

    def __init__(self, quantiles: list):
        super().__init__()
        self.quantiles = quantiles
        self.num_quantiles = len(quantiles)

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """Calculate quantile loss.

        Args:
            predictions: Predicted quantiles (batch, seq_len, output_size, num_quantiles)
            targets: True values (batch, seq_len, output_size)

        Returns:
            Average quantile loss
        """
        # Expand targets to match predictions shape
        targets_expanded = targets.unsqueeze(-1).expand_as(predictions)

        # Calculate errors
        errors = targets_expanded - predictions

        # Calculate quantile loss for each quantile
        losses = []
        for i, q in enumerate(self.quantiles):
            # Pinball loss
            loss_q = torch.max(
                q * errors[..., i],
                (q - 1) * errors[..., i]
            )
            losses.append(loss_q.mean())

        # Average across quantiles
        total_loss = torch.stack(losses).mean()

        return total_loss


class NormalizedQuantileLoss(nn.Module):
    """Normalized quantile loss.

    Normalizes the quantile loss by the scale of the target variable.
    Useful when dealing with different scales across time series.

    Args:
        quantiles: List of quantile levels
    """

    def __init__(self, quantiles: list):
        super().__init__()
        self.quantiles = quantiles
        self.num_quantiles = len(quantiles)

    def forward(
        self,
        predictions: torch.Tensor,
        targets: torch.Tensor,
    ) -> torch.Tensor:
        """Calculate normalized quantile loss.

        Args:
            predictions: Predicted quantiles
            targets: True values

        Returns:
            Normalized quantile loss
        """
        # Expand targets
        targets_expanded = targets.unsqueeze(-1).expand_as(predictions)

        # Calculate errors
        errors = targets_expanded - predictions

        # Calculate scale (avoid division by zero)
        scale = targets.abs().mean() + 1e-8

        # Normalized quantile loss
        losses = []
        for i, q in enumerate(self.quantiles):
            loss_q = torch.max(
                q * errors[..., i],
                (q - 1) * errors[..., i]
            )
            losses.append((loss_q / scale).mean())

        # Average across quantiles
        total_loss = torch.stack(losses).mean()

        return total_loss
