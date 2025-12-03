# Temporal Fusion Transformer - Usage Guide

This guide provides practical examples for using the Temporal Fusion Transformer (TFT) for load forecasting in the SHAKTI-CHAIN V2G platform.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Data Preparation](#data-preparation)
3. [Model Configuration](#model-configuration)
4. [Training](#training)
5. [Inference](#inference)
6. [Interpretability](#interpretability)
7. [Hyperparameter Tuning](#hyperparameter-tuning)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Quick Start

### Installation

Ensure all dependencies are installed:

```bash
cd ml
pip install -e .
```

### Basic Training Example

```python
import pytorch_lightning as pl
from pathlib import Path
from hydra import compose, initialize
from torch.utils.data import DataLoader

from src.training.tft_lightning_module import TFTLightningModule
from src.data import ShaktiChainDataModule

# Initialize Hydra configuration
initialize(config_path="configs", version_base=None)
cfg = compose(config_name="config", overrides=["model=tft"])

# Create data module
data_module = ShaktiChainDataModule(
    data_path="data/processed/processed_data.parquet",
    encoder_length=168,  # 1 week
    decoder_length=48,   # 2 days
    batch_size=32,
    num_workers=4,
)

# Create model
model = TFTLightningModule(
    model_config=cfg.model,
    learning_rate=1e-3,
    weight_decay=1e-5,
    optimizer="adam",
    scheduler="plateau",
)

# Create trainer
trainer = pl.Trainer(
    max_epochs=50,
    accelerator="auto",
    devices=1,
    callbacks=[
        pl.callbacks.EarlyStopping(monitor="val_loss", patience=10),
        pl.callbacks.ModelCheckpoint(monitor="val_loss", mode="min"),
    ],
    logger=pl.loggers.MLFlowLogger(experiment_name="tft_load_forecasting"),
)

# Train
trainer.fit(model, data_module)

# Test
trainer.test(model, data_module)
```

## Data Preparation

### Feature Engineering

The TFT requires three types of features:

1. **Static features**: Time-invariant (e.g., location, type)
2. **Known future features**: Available at prediction time (e.g., time, calendar)
3. **Observed features**: Only available historically (e.g., load, weather)

```python
from src.features import FeatureEngineering
import pandas as pd

# Load data
df = pd.read_parquet("data/processed/processed_data.parquet")

# Create features
feature_engineer = FeatureEngineering(
    include_temporal=True,
    include_lags=True,
    lag_hours=[1, 24],
    include_rolling=True,
    rolling_windows=[24, 168],
    include_weather=True,
    include_derived=True,
    include_interactions=False,  # Keep it simple initially
)

# Fit on training data only
train_df = df[df["timestamp"] < "2023-01-01"]
feature_engineer.fit(train_df)

# Transform all data
df_features = feature_engineer.transform(df)

# Save fitted feature engineer for production
feature_engineer.save("models/feature_engineer.joblib")
```

### Define Feature Groups

```python
# Known future features (available at prediction time)
known_future_features = [
    "hour",
    "hour_sin",
    "hour_cos",
    "day_of_week",
    "day_of_week_sin",
    "day_of_week_cos",
    "is_weekend",
    "is_holiday",
    "is_peak_hour",
    "month_sin",
]

# Observed features (only available historically)
observed_features = [
    "load_mw_lag_1h",
    "load_mw_lag_24h",
    "temperature_c_delhi",
    "price_inr_mwh_dam",
    "humidity_pct_delhi",
]

# Target
target_columns = ["load_mw"]

# Static features (if any)
static_features = []  # Not used in current configuration
```

### Create Dataset

```python
from src.data import TimeSeriesDataset

# Create dataset
dataset = TimeSeriesDataset(
    data=df_features,
    target_columns=target_columns,
    known_future_features=known_future_features,
    observed_features=observed_features,
    static_features=static_features,
    encoder_length=168,
    decoder_length=48,
    stride=24,  # Create overlapping sequences every 24 hours
)

# Split into train/val/test
train_size = int(0.7 * len(dataset))
val_size = int(0.15 * len(dataset))
test_size = len(dataset) - train_size - val_size

train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
    dataset, [train_size, val_size, test_size]
)

# Create data loaders
train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, num_workers=4)
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False, num_workers=4)
test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False, num_workers=4)
```

## Model Configuration

### Configuration File (configs/model/tft.yaml)

```yaml
model:
  name: "temporal_fusion_transformer"
  type: "tft"

  # Input dimensions (will be set dynamically based on data)
  input_dims:
    static_input_size: 0  # Not using static features
    known_input_size: 10  # Number of known future features
    observed_input_size: 5  # Number of observed features

  # Sequence lengths
  sequence_lengths:
    encoder_length: 168  # 1 week of hourly data
    decoder_length: 48   # 2 days ahead prediction

  # Architecture
  architecture:
    hidden_size: 160
    lstm_layers: 2
    num_attention_heads: 4
    dropout: 0.1

  # Output
  output:
    output_size: 1  # Number of target variables
    quantiles: [0.1, 0.5, 0.9]  # Prediction quantiles

  # Forecasting settings
  forecasting:
    target_columns: ["load_mw"]

    # Known future inputs (available at prediction time)
    known_future_features:
      - "hour"
      - "hour_sin"
      - "hour_cos"
      - "day_of_week"
      - "day_of_week_sin"
      - "day_of_week_cos"
      - "is_weekend"
      - "is_holiday"
      - "is_peak_hour"
      - "month_sin"

    # Observed inputs (only available historically)
    observed_features:
      - "load_mw_lag_1h"
      - "load_mw_lag_24h"
      - "temperature_c_delhi"
      - "price_inr_mwh_dam"
      - "humidity_pct_delhi"
```

### Programmatic Configuration

```python
model_config = {
    "input_dims": {
        "static_input_size": 0,
        "known_input_size": 10,
        "observed_input_size": 5,
    },
    "sequence_lengths": {
        "encoder_length": 168,
        "decoder_length": 48,
    },
    "architecture": {
        "hidden_size": 160,
        "lstm_layers": 2,
        "num_attention_heads": 4,
        "dropout": 0.1,
    },
    "output": {
        "output_size": 1,
        "quantiles": [0.1, 0.5, 0.9],
    },
}

# Create model
model = TFTLightningModule(
    model_config=model_config,
    learning_rate=1e-3,
    weight_decay=1e-5,
)
```

## Training

### Basic Training

```python
import pytorch_lightning as pl

# Create trainer
trainer = pl.Trainer(
    max_epochs=50,
    accelerator="auto",  # Use GPU if available
    devices=1,
    precision="16-mixed",  # Use mixed precision for faster training
    gradient_clip_val=1.0,  # Clip gradients to prevent exploding gradients
)

# Train
trainer.fit(model, train_loader, val_loader)
```

### With Callbacks

```python
from pytorch_lightning.callbacks import (
    EarlyStopping,
    ModelCheckpoint,
    LearningRateMonitor,
)

# Define callbacks
early_stopping = EarlyStopping(
    monitor="val_loss",
    patience=10,
    mode="min",
    verbose=True,
)

checkpoint_callback = ModelCheckpoint(
    dirpath="checkpoints/tft",
    filename="tft-{epoch:02d}-{val_loss:.4f}",
    monitor="val_loss",
    mode="min",
    save_top_k=3,
    save_last=True,
)

lr_monitor = LearningRateMonitor(logging_interval="epoch")

# Create trainer with callbacks
trainer = pl.Trainer(
    max_epochs=100,
    accelerator="auto",
    devices=1,
    callbacks=[early_stopping, checkpoint_callback, lr_monitor],
    logger=pl.loggers.MLFlowLogger(
        experiment_name="tft_load_forecasting",
        tracking_uri="mlruns",
    ),
)

# Train
trainer.fit(model, train_loader, val_loader)
```

### With MLflow Tracking

```python
import mlflow

# Set MLflow tracking URI
mlflow.set_tracking_uri("mlruns")

# Start MLflow run
with mlflow.start_run(run_name="tft_load_forecasting"):
    # Log parameters
    mlflow.log_params({
        "encoder_length": 168,
        "decoder_length": 48,
        "hidden_size": 160,
        "lstm_layers": 2,
        "num_attention_heads": 4,
        "learning_rate": 1e-3,
    })

    # Train
    trainer.fit(model, train_loader, val_loader)

    # Log best metrics
    mlflow.log_metrics({
        "best_val_loss": checkpoint_callback.best_model_score.item(),
    })

    # Log model
    mlflow.pytorch.log_model(model, "model")
```

## Inference

### Basic Prediction

```python
import torch

# Load trained model
model = TFTLightningModule.load_from_checkpoint("checkpoints/tft/best.ckpt")
model.eval()

# Prepare input data
batch = {
    "static_covariates": None,  # Or tensor of shape (batch, static_size)
    "historical_observed": torch.randn(1, 168, 5),  # (batch, encoder_len, observed_size)
    "historical_known": torch.randn(1, 168, 10),    # (batch, encoder_len, known_size)
    "future_known": torch.randn(1, 48, 10),         # (batch, decoder_len, known_size)
}

# Make prediction
with torch.no_grad():
    predictions, interpretability = model(
        static_covariates=batch["static_covariates"],
        historical_observed=batch["historical_observed"],
        historical_known=batch["historical_known"],
        future_known=batch["future_known"],
    )

# predictions shape: (batch, decoder_length, output_size, num_quantiles)
# For this example: (1, 48, 1, 3)

# Extract quantiles
q10 = predictions[0, :, 0, 0]  # 10th percentile
q50 = predictions[0, :, 0, 1]  # Median (50th percentile)
q90 = predictions[0, :, 0, 2]  # 90th percentile

print(f"Median prediction for next 48 hours: {q50}")
print(f"Prediction interval: [{q10}, {q90}]")
```

### Batch Prediction

```python
# Use PyTorch Lightning's predict method
predictions = trainer.predict(model, test_loader)

# predictions is a list of dictionaries, one per batch
# Each dictionary contains:
#   - "predictions": tensor of shape (batch, decoder_len, output_size, num_quantiles)
#   - "interpretability": dict with attention weights, variable importance
#   - "targets": tensor of shape (batch, decoder_len, output_size)

# Concatenate all predictions
all_predictions = torch.cat([p["predictions"] for p in predictions], dim=0)
all_targets = torch.cat([p["targets"] for p in predictions], dim=0)

# Calculate metrics
mae = torch.abs(all_predictions[..., 1] - all_targets).mean()  # MAE for median
print(f"Test MAE: {mae:.4f}")
```

### Production Inference

```python
class TFTForecaster:
    """Production forecaster using TFT."""

    def __init__(self, model_path, feature_engineer_path, device="cpu"):
        """Initialize forecaster.

        Args:
            model_path: Path to trained model checkpoint
            feature_engineer_path: Path to fitted feature engineer
            device: Device to run inference on
        """
        self.model = TFTLightningModule.load_from_checkpoint(model_path)
        self.model.eval()
        self.model.to(device)

        self.feature_engineer = FeatureEngineering.load(feature_engineer_path)
        self.device = device

    def forecast(self, historical_data: pd.DataFrame, future_timestamps: pd.DatetimeIndex):
        """Generate forecast for future timestamps.

        Args:
            historical_data: DataFrame with historical data (must contain last 168 hours)
            future_timestamps: DatetimeIndex for future predictions (up to 48 hours)

        Returns:
            DataFrame with predictions and uncertainty intervals
        """
        # Engineer features
        historical_features = self.feature_engineer.transform(historical_data)

        # Create future data with known features only
        future_data = pd.DataFrame({"timestamp": future_timestamps})
        future_features = self.feature_engineer.transform(future_data)

        # Extract feature arrays
        historical_observed = torch.tensor(
            historical_features[observed_features].iloc[-168:].values,
            dtype=torch.float32,
            device=self.device,
        ).unsqueeze(0)  # Add batch dimension

        historical_known = torch.tensor(
            historical_features[known_future_features].iloc[-168:].values,
            dtype=torch.float32,
            device=self.device,
        ).unsqueeze(0)

        future_known = torch.tensor(
            future_features[known_future_features].values[:48],
            dtype=torch.float32,
            device=self.device,
        ).unsqueeze(0)

        # Make prediction
        with torch.no_grad():
            predictions, _ = self.model(
                static_covariates=None,
                historical_observed=historical_observed,
                historical_known=historical_known,
                future_known=future_known,
            )

        # Convert to DataFrame
        predictions = predictions[0, :, 0, :].cpu().numpy()  # Remove batch and output dims

        result = pd.DataFrame({
            "timestamp": future_timestamps[:len(predictions)],
            "load_mw_q10": predictions[:, 0],
            "load_mw_q50": predictions[:, 1],
            "load_mw_q90": predictions[:, 2],
        })

        return result

# Usage
forecaster = TFTForecaster(
    model_path="checkpoints/tft/best.ckpt",
    feature_engineer_path="models/feature_engineer.joblib",
)

# Generate forecast
historical_data = pd.read_parquet("data/processed/processed_data.parquet")
future_timestamps = pd.date_range(
    start=historical_data["timestamp"].max() + pd.Timedelta(hours=1),
    periods=48,
    freq="h",
)

forecast = forecaster.forecast(historical_data, future_timestamps)
print(forecast)
```

## Interpretability

### Extract Variable Importance

```python
# Get interpretability information
with torch.no_grad():
    predictions, interpretability = model(
        static_covariates=batch["static_covariates"],
        historical_observed=batch["historical_observed"],
        historical_known=batch["historical_known"],
        future_known=batch["future_known"],
    )

# Variable importance for encoder features
if "encoder_weights" in interpretability:
    encoder_weights = interpretability["encoder_weights"]
    # Shape: (batch, encoder_length, num_encoder_vars)

    # Average across batch and time
    encoder_importance = encoder_weights.mean(dim=(0, 1))
    # Shape: (num_encoder_vars,)

    # Create DataFrame
    encoder_feature_names = observed_features + known_future_features
    importance_df = pd.DataFrame({
        "feature": encoder_feature_names,
        "importance": encoder_importance.cpu().numpy(),
    }).sort_values("importance", ascending=False)

    print("Encoder Feature Importance:")
    print(importance_df)

# Variable importance for decoder features
if "decoder_weights" in interpretability:
    decoder_weights = interpretability["decoder_weights"]
    decoder_importance = decoder_weights.mean(dim=(0, 1))

    decoder_importance_df = pd.DataFrame({
        "feature": known_future_features,
        "importance": decoder_importance.cpu().numpy(),
    }).sort_values("importance", ascending=False)

    print("\nDecoder Feature Importance:")
    print(decoder_importance_df)
```

### Visualize Attention Weights

```python
import matplotlib.pyplot as plt
import seaborn as sns

# Get attention weights
attention_weights = interpretability["attention_weights"]
# Shape: (batch, num_heads, decoder_length, encoder_length)

# Average across batch and heads
avg_attention = attention_weights.mean(dim=(0, 1)).cpu().numpy()
# Shape: (decoder_length, encoder_length)

# Plot heatmap
plt.figure(figsize=(15, 8))
sns.heatmap(
    avg_attention,
    cmap="viridis",
    xticklabels=range(-168, 0),  # Historical hours
    yticklabels=range(1, 49),    # Future hours
    cbar_kws={"label": "Attention Weight"},
)
plt.xlabel("Historical Time Steps (hours ago)")
plt.ylabel("Prediction Time Steps (hours ahead)")
plt.title("TFT Attention Weights: Which Historical Hours Matter for Each Prediction?")
plt.tight_layout()
plt.savefig("attention_weights.png", dpi=300)
plt.show()
```

### Analyze Temporal Focus

```python
# Which historical periods does the model focus on for different prediction horizons?

# Short-term predictions (1-12 hours ahead)
short_term_attention = avg_attention[:12, :].mean(axis=0)

# Medium-term predictions (13-24 hours ahead)
medium_term_attention = avg_attention[12:24, :].mean(axis=0)

# Long-term predictions (25-48 hours ahead)
long_term_attention = avg_attention[24:, :].mean(axis=0)

# Plot
plt.figure(figsize=(15, 6))
hours_ago = list(range(-168, 0))

plt.plot(hours_ago, short_term_attention, label="1-12 hours ahead", linewidth=2)
plt.plot(hours_ago, medium_term_attention, label="13-24 hours ahead", linewidth=2)
plt.plot(hours_ago, long_term_attention, label="25-48 hours ahead", linewidth=2)

plt.xlabel("Hours Ago")
plt.ylabel("Average Attention Weight")
plt.title("TFT Temporal Focus by Prediction Horizon")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("temporal_focus.png", dpi=300)
plt.show()
```

## Hyperparameter Tuning

### Grid Search with Optuna

```python
import optuna
from optuna.integration import PyTorchLightningPruningCallback

def objective(trial):
    """Optuna objective function for hyperparameter tuning."""

    # Suggest hyperparameters
    hidden_size = trial.suggest_categorical("hidden_size", [64, 128, 160, 256])
    lstm_layers = trial.suggest_int("lstm_layers", 1, 3)
    num_attention_heads = trial.suggest_categorical("num_attention_heads", [2, 4, 8])
    dropout = trial.suggest_float("dropout", 0.0, 0.3)
    learning_rate = trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True)

    # Update model config
    model_config["architecture"]["hidden_size"] = hidden_size
    model_config["architecture"]["lstm_layers"] = lstm_layers
    model_config["architecture"]["num_attention_heads"] = num_attention_heads
    model_config["architecture"]["dropout"] = dropout

    # Create model
    model = TFTLightningModule(
        model_config=model_config,
        learning_rate=learning_rate,
    )

    # Create trainer with pruning callback
    trainer = pl.Trainer(
        max_epochs=30,
        accelerator="auto",
        devices=1,
        callbacks=[PyTorchLightningPruningCallback(trial, monitor="val_loss")],
        logger=False,
        enable_checkpointing=False,
    )

    # Train
    trainer.fit(model, train_loader, val_loader)

    return trainer.callback_metrics["val_loss"].item()

# Create study
study = optuna.create_study(direction="minimize", study_name="tft_tuning")

# Optimize
study.optimize(objective, n_trials=50, timeout=3600)

# Print best parameters
print("Best hyperparameters:")
print(study.best_params)
print(f"Best validation loss: {study.best_value:.4f}")
```

## Best Practices

### 1. Data Preparation

- **Normalize features**: Use StandardScaler for continuous features
- **Handle missing values**: Interpolate or forward-fill, avoid dropping
- **Remove outliers**: Cap extreme values to prevent training instability
- **Create temporal features**: Hour, day, week, month with cyclical encoding
- **Use lag features**: Include recent history (1h, 24h, 168h)

### 2. Model Architecture

- **Start small**: Begin with hidden_size=64, lstm_layers=1 for debugging
- **Scale gradually**: Increase model size if underfitting
- **Use layer normalization**: Already included in LSTM encoder-decoder
- **Apply dropout**: 0.1-0.2 for regularization
- **Monitor attention heads**: 4 heads is a good default

### 3. Training

- **Learning rate**: Start with 1e-3, reduce on plateau
- **Batch size**: 32-128 depending on GPU memory
- **Early stopping**: Patience of 10 epochs
- **Gradient clipping**: Clip to 1.0 to prevent exploding gradients
- **Mixed precision**: Use 16-bit for faster training
- **Validation frequency**: Every epoch

### 4. Inference

- **Batch predictions**: Process multiple samples at once
- **Use GPU**: Much faster than CPU for large models
- **Cache features**: Reuse feature engineering for multiple forecasts
- **Monitor uncertainty**: Check if prediction intervals are reasonable

### 5. Production

- **Version models**: Use MLflow or DVC for model versioning
- **Log everything**: Track metrics, hyperparameters, and predictions
- **Monitor drift**: Track feature distributions and prediction accuracy
- **A/B testing**: Compare with baseline models
- **Fallback**: Have a simple model as backup

## Troubleshooting

### Issue: Model not converging

**Symptoms**: Loss stays high or increases

**Solutions**:
- Reduce learning rate (try 1e-4 or 1e-5)
- Increase batch size
- Reduce model complexity (smaller hidden_size)
- Check for data issues (NaNs, outliers)
- Use gradient clipping

### Issue: Overfitting

**Symptoms**: Low train loss, high val loss

**Solutions**:
- Increase dropout (0.2-0.3)
- Add weight decay (1e-4 to 1e-3)
- Reduce model size
- Use more training data
- Use early stopping

### Issue: Poor coverage

**Symptoms**: Actual values often outside [Q10, Q90] interval

**Solutions**:
- Use NormalizedQuantileLoss instead of QuantileLoss
- Check if data is normalized properly
- Increase model capacity
- Train longer

### Issue: Slow training

**Solutions**:
- Use mixed precision training (precision="16-mixed")
- Reduce encoder_length or decoder_length
- Reduce batch size (but increase accumulation steps)
- Use smaller model
- Use GPU with more memory

### Issue: Out of memory

**Solutions**:
- Reduce batch size
- Reduce encoder_length or decoder_length
- Reduce hidden_size
- Use gradient checkpointing
- Use CPU offloading

### Issue: NaN losses

**Symptoms**: Loss becomes NaN during training

**Solutions**:
- Reduce learning rate
- Use gradient clipping
- Check for NaNs or Infs in input data
- Use layer normalization (already included)
- Initialize weights carefully

## Example Scripts

See the `examples/` directory for complete working examples:

- `examples/train_tft.py`: Full training script with MLflow
- `examples/evaluate_tft.py`: Model evaluation and metrics
- `examples/interpret_tft.py`: Interpretability analysis
- `examples/forecast_tft.py`: Production forecasting
- `examples/tune_tft.py`: Hyperparameter tuning with Optuna

## Additional Resources

- [TFT_ARCHITECTURE.md](TFT_ARCHITECTURE.md): Detailed architecture documentation
- [Original Paper](https://arxiv.org/abs/1912.09363): Temporal Fusion Transformers paper
- [PyTorch Forecasting](https://pytorch-forecasting.readthedocs.io/): Reference implementation
