# SHAKTI-CHAIN ML Platform - Quick Start Guide

Get up and running with the SHAKTI-CHAIN ML platform in 10 minutes!

## Prerequisites

- Python 3.10 or higher
- Git (for version control)
- 8GB+ RAM recommended
- (Optional) GPU with CUDA for faster training

## Installation

### Option 1: Automated Setup (Recommended)

**On Linux/Mac:**
```bash
cd ShaktiChain/ml
chmod +x setup.sh
./setup.sh
```

**On Windows (PowerShell):**
```powershell
cd ShaktiChain\ml
.\setup.ps1
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -e .

# Initialize DVC
dvc init

# Create environment file
cp .env.example .env
```

## Configuration

Edit `.env` file with your API keys:

```bash
# Required for weather data
OPENWEATHER_API_KEY=your_openweathermap_api_key

# Optional: For production deployment
MLFLOW_TRACKING_URI=http://localhost:5000
```

To get an OpenWeatherMap API key:
1. Visit https://openweathermap.org/api
2. Sign up for a free account
3. Get your API key from the dashboard

## Running the Pipeline

### Step 1: Collect Data

```bash
python scripts/collect_data.py
```

This will:
- Fetch energy load data from POSOCO
- Collect price data from IEX
- Get weather data (or use simulator if no API key)
- Generate calendar features (holidays, festivals)
- Merge all data sources
- Save to `data/raw/merged_data.parquet`

**Duration:** 5-30 minutes (depending on date range and data sources)

### Step 2: Preprocess Data

```bash
python scripts/preprocess_data.py
```

This will:
- Engineer temporal features
- Create lag and rolling features
- Handle missing values
- Detect and handle outliers
- Normalize features
- Save to `data/processed/processed_data.parquet`

**Duration:** 2-5 minutes

### Step 3: Train Model

```bash
# Train LSTM model (default)
python scripts/train.py

# Train Transformer model
python scripts/train.py model=transformer

# Quick test with 1 epoch
python scripts/train.py training.epochs=1 training.fast_dev_run=true

# Custom configuration
python scripts/train.py \
    model=lstm \
    training.epochs=50 \
    training.optimizer.lr=0.0001 \
    data.loader.batch_size=128
```

**Duration:** 10-60 minutes (depending on model and hardware)

### Step 4: View Results

```bash
# Start MLflow UI
mlflow ui --backend-store-uri ./logs/mlruns
```

Open http://localhost:5000 in your browser to view:
- Training metrics (loss, MAE, RMSE, R²)
- Model parameters
- Training curves
- Experiment comparisons

## Project Structure Overview

```
ml/
├── configs/              # Hydra configs (modify for experiments)
│   ├── config.yaml      # Main config
│   ├── data/            # Data configs
│   ├── model/           # Model configs
│   └── training/        # Training configs
│
├── data/                # Data storage (gitignored)
│   ├── raw/            # Raw collected data
│   ├── processed/      # Processed features
│   └── features/       # Feature store
│
├── src/                 # Source code
│   ├── data/           # Data collection & processing
│   ├── models/         # Model architectures
│   ├── training/       # Training logic
│   └── features/       # Feature store
│
├── scripts/            # Executable scripts
│   ├── collect_data.py    # Data collection
│   ├── preprocess_data.py # Preprocessing
│   └── train.py          # Training
│
├── notebooks/          # Jupyter notebooks
├── tests/             # Unit tests
└── logs/              # Training logs & models
```

## Common Workflows

### Experiment with Different Models

```bash
# Try different architectures
python scripts/train.py model=lstm
python scripts/train.py model=transformer

# Adjust model size
python scripts/train.py model=lstm model.architecture.hidden_size=256
python scripts/train.py model=transformer model.architecture.d_model=256
```

### Hyperparameter Tuning

```bash
# Learning rate
python scripts/train.py training.optimizer.lr=0.001
python scripts/train.py training.optimizer.lr=0.0001

# Batch size
python scripts/train.py data.loader.batch_size=32
python scripts/train.py data.loader.batch_size=128

# Regularization
python scripts/train.py model.architecture.dropout=0.1
python scripts/train.py model.architecture.dropout=0.3
```

### Data Collection Customization

Edit `configs/data/default.yaml`:

```yaml
data:
  collection:
    start_date: "2023-01-01"  # Change date range
    end_date: "2024-12-31"

  sources:
    weather:
      locations:
        - name: "Delhi"
          lat: 28.6139
          lon: 77.2090
        # Add more locations
```

### Working with Feature Store

```python
from src.features import ParquetFeatureStore

# Initialize store
store = ParquetFeatureStore("data/features")

# Save features
store.save_features(my_features_df, "custom_features")

# Load features
features = store.load_features("custom_features")

# Get recent data
recent = store.get_latest_features("custom_features", lookback_hours=168)
```

## Development Workflow

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test
pytest tests/test_collectors.py
```

### Code Formatting

```bash
# Format code
black src/ scripts/
isort src/ scripts/

# Lint
ruff check src/ scripts/
mypy src/
```

### Using Makefile

```bash
# See all commands
make help

# Install dependencies
make install

# Run full data pipeline
make data

# Train model
make train

# Start MLflow UI
make mlflow

# Run tests
make test
```

## Troubleshooting

### Issue: "No module named 'src'"

**Solution:** Make sure you're in the correct directory and have installed the package:
```bash
cd ShaktiChain/ml
pip install -e .
```

### Issue: "OPENWEATHER_API_KEY not found"

**Solution:** The system will automatically use a weather simulator. To use real data:
1. Get API key from https://openweathermap.org/api
2. Add to `.env` file: `OPENWEATHER_API_KEY=your_key`

### Issue: "CUDA out of memory"

**Solution:** Reduce batch size:
```bash
python scripts/train.py data.loader.batch_size=32
```

Or use CPU:
```bash
python scripts/train.py training.accelerator=cpu
```

### Issue: "Data file not found"

**Solution:** Run data collection first:
```bash
python scripts/collect_data.py
python scripts/preprocess_data.py
```

## Next Steps

1. **Explore Data**: Use notebooks in `notebooks/01_data_exploration.ipynb`
2. **Customize Models**: Edit configs in `configs/model/`
3. **Add New Features**: Modify `src/data/processors/feature_engineering.py`
4. **Deploy Model**: See README.md for deployment options

## Getting Help

- **Documentation**: See [README.md](README.md) for detailed information
- **Issues**: Report bugs at GitHub Issues
- **Examples**: Check `notebooks/` for examples

## Quick Reference

```bash
# Full pipeline
python scripts/collect_data.py
python scripts/preprocess_data.py
python scripts/train.py
mlflow ui

# With custom config
python scripts/train.py model=transformer training.epochs=100

# View logs
tail -f logs/app.log

# Clean up
make clean
```

## Performance Tips

1. **Use GPU**: Significantly faster training
   ```bash
   python scripts/train.py training.accelerator=gpu training.devices=1
   ```

2. **Increase Workers**: Faster data loading
   ```bash
   python scripts/train.py data.loader.num_workers=8
   ```

3. **Mixed Precision**: Faster training with less memory
   ```bash
   python scripts/train.py training.precision=16
   ```

4. **Accumulate Gradients**: Simulate larger batch sizes
   ```bash
   python scripts/train.py training.accumulate_grad_batches=4
   ```

Happy Forecasting! 🚀⚡
