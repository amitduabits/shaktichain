# SHAKTI-CHAIN V2G ML Platform

Production-ready machine learning pipeline for energy load forecasting and V2G optimization.

## Overview

This ML platform provides:
- **Data Collection**: Automated collectors for POSOCO, IEX, Weather, and Calendar data
- **Feature Engineering**: Comprehensive temporal and domain-specific features
- **Model Training**: PyTorch Lightning with LSTM and Transformer architectures
- **Experiment Tracking**: MLflow for versioning and model registry
- **Data Versioning**: DVC for reproducible data pipelines
- **Configuration Management**: Hydra for flexible experiment configuration

## Project Structure

```
ml/
├── configs/               # Hydra configurations
│   ├── data/             # Data collection & processing configs
│   ├── model/            # Model architecture configs
│   ├── training/         # Training configs
│   └── logging/          # Logging configs
├── src/
│   ├── data/
│   │   ├── collectors/   # Data collection modules
│   │   ├── processors/   # Data preprocessing
│   │   └── loaders/      # PyTorch datasets
│   ├── features/         # Feature store
│   ├── models/           # Model architectures
│   ├── training/         # Training modules
│   └── inference/        # Inference pipeline
├── scripts/              # Utility scripts
├── tests/                # Unit tests
└── notebooks/            # Jupyter notebooks
```

## Installation

### Prerequisites
- Python 3.10+
- pip or conda

### Setup

1. **Clone the repository**
```bash
cd ShaktiChain/ml
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -e .
```

4. **Install development dependencies**
```bash
pip install -e ".[dev]"
```

5. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

6. **Initialize DVC**
```bash
dvc init
```

## Quick Start

### 1. Data Collection

Collect data from all sources:

```bash
python scripts/collect_data.py
```

This will fetch:
- POSOCO: Energy load data from NLDC
- IEX: Market prices (DAM & RTM)
- Weather: Temperature, humidity from OpenWeatherMap
- Calendar: Indian holidays and festivals

### 2. Data Preprocessing

Process and engineer features:

```bash
python scripts/preprocess_data.py
```

### 3. Train Model

Train a forecasting model:

```bash
# Train LSTM model
python scripts/train.py model=lstm

# Train Transformer model
python scripts/train.py model=transformer

# Override parameters
python scripts/train.py model=lstm training.epochs=50 training.optimizer.lr=0.0001
```

### 4. View Results

Start MLflow UI:

```bash
mlflow ui --backend-store-uri ./logs/mlruns
```

Open http://localhost:5000 in your browser.

## Data Collectors

### POSOCO Collector
```python
from src.data.collectors import POSOCOCollector, POSOCOConfig

config = POSOCOConfig(
    url="https://posoco.in/reports/",
    regions=["NORTHERN", "WESTERN"],
    enabled=True
)
collector = POSOCOCollector(config)
data = collector.collect(start_date, end_date)
```

### IEX Collector
```python
from src.data.collectors import IEXCollector, IEXConfig

config = IEXConfig(
    url="https://www.iexindia.com/marketdata/areaprices.aspx",
    markets=["DAM", "RTM"],
    enabled=True
)
collector = IEXCollector(config)
data = collector.collect(start_date, end_date)
```

### Weather Collector
```python
from src.data.collectors import WeatherCollector, WeatherConfig, LocationConfig

config = WeatherConfig(
    api_key="your_api_key",
    locations=[
        LocationConfig(name="Delhi", lat=28.6139, lon=77.2090),
        LocationConfig(name="Mumbai", lat=19.0760, lon=72.8777),
    ]
)
collector = WeatherCollector(config)
data = collector.collect(start_date, end_date)
```

### Calendar Collector
```python
from src.data.collectors import CalendarCollector, CalendarConfig

config = CalendarConfig(
    country="IN",
    include_festivals=True
)
collector = CalendarCollector(config)
data = collector.collect(start_date, end_date)
```

## Configuration

### Modify Model Architecture

Edit `configs/model/lstm.yaml` or `configs/model/transformer.yaml`:

```yaml
model:
  architecture:
    hidden_size: 256
    num_layers: 3
    dropout: 0.3
```

### Modify Training Settings

Edit `configs/training/default.yaml`:

```yaml
training:
  epochs: 100
  optimizer:
    lr: 0.001
  early_stopping:
    patience: 10
```

## Feature Store

### Using Parquet Feature Store

```python
from src.features import ParquetFeatureStore

store = ParquetFeatureStore("data/features")

# Save features
store.save_features(features_df, "hourly_features")

# Load features
features = store.load_features("hourly_features")

# Get recent features
recent = store.get_latest_features("hourly_features", lookback_hours=168)
```

## Model Architectures

### LSTM Forecaster
- Bidirectional LSTM with multiple layers
- Dropout for regularization
- Multi-horizon forecasting support

### Transformer Forecaster
- Multi-head self-attention
- Positional encoding
- Encoder-decoder or encoder-only variants

### Attention LSTM
- LSTM with attention mechanism
- Learns to focus on important time steps

## MLflow Integration

### Track Experiments

```python
import mlflow

mlflow.set_experiment("shakti-chain-v2g")

with mlflow.start_run():
    mlflow.log_params({"lr": 0.001, "batch_size": 64})
    mlflow.log_metrics({"loss": 0.5, "mae": 0.3})
    mlflow.pytorch.log_model(model, "model")
```

### Register Models

```python
# Register best model
mlflow.register_model(
    model_uri="runs:/<run_id>/model",
    name="shakti-lstm-forecaster"
)
```

## Data Versioning with DVC

### Track data files

```bash
dvc add data/raw/merged_data.parquet
git add data/raw/merged_data.parquet.dvc .gitignore
git commit -m "Add raw data"
```

### Push to remote storage

```bash
dvc remote add -d storage s3://my-bucket/dvc-storage
dvc push
```

### Pull data

```bash
dvc pull
```

## Testing

Run tests:

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_collectors.py
```

## Development

### Code Formatting

```bash
# Format with black
black src/ scripts/

# Sort imports
isort src/ scripts/

# Lint with ruff
ruff check src/ scripts/
```

### Type Checking

```bash
mypy src/
```

## Deployment

### Export Model

```bash
# Export to ONNX
python scripts/export_model.py --format onnx

# Export to TorchScript
python scripts/export_model.py --format torchscript
```

### Inference API

```bash
# Start FastAPI server
uvicorn src.inference.api:app --reload
```

## Monitoring

### MLflow Tracking Server

```bash
mlflow server \
    --backend-store-uri sqlite:///mlflow.db \
    --default-artifact-root ./mlruns \
    --host 0.0.0.0 \
    --port 5000
```

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure `.env` file has valid API keys
2. **Memory Issues**: Reduce batch size or sequence length
3. **CUDA Errors**: Check PyTorch installation and GPU drivers

### Logs

Check logs in:
- Training logs: `logs/app.log`
- MLflow runs: `logs/mlruns/`
- TensorBoard: `logs/tensorboard/`

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

Copyright BITS Pilani. All rights reserved. See the repository root `LICENSE`. This directory is not MIT-licensed.

## Support

For issues and questions:
- GitHub Issues: https://github.com/shakti-chain/ml/issues
- Email: team@shaktichain.com

## Acknowledgments

- POSOCO for energy data
- IEX for market prices
- OpenWeatherMap for weather data
- PyTorch Lightning team
- MLflow team
