# SHAKTI-CHAIN V2G ML Platform - Project Summary

## Overview

A production-ready machine learning platform for energy load forecasting and Vehicle-to-Grid (V2G) optimization. Built with modern MLOps practices including experiment tracking, data versioning, and reproducible pipelines.

## Key Features

### 1. Data Collection System
- **POSOCOCollector**: Fetches energy load data from India's National Load Dispatch Centre
- **IEXCollector**: Collects electricity market prices from Indian Energy Exchange (DAM & RTM)
- **WeatherCollector**: Retrieves weather data from OpenWeatherMap API
- **CalendarCollector**: Generates calendar features including Indian holidays and festivals
- Automatic caching and retry mechanisms
- Configurable date ranges and regions

### 2. Data Processing Pipeline
- **DataPreprocessor**: Handles missing values, outlier detection, and normalization
- **FeatureEngineer**: Creates 50+ engineered features:
  - Temporal features (hour, day, week, month)
  - Cyclical encodings (sin/cos transformations)
  - Lag features (1h, 2h, 3h, 24h, 168h)
  - Rolling window statistics (mean, std, min, max)
  - Domain-specific features (peak hours, working hours, seasons)
  - Weather-derived features (heat index, temperature categories)
  - Price volatility features

### 3. Feature Store
- **ParquetFeatureStore**: Efficient Parquet-based feature storage
- **Feast Integration**: (Optional) Enterprise-grade feature store
- Time-travel capabilities for historical features
- Feature versioning and lineage tracking

### 4. Model Architectures

#### LSTM Models
- **LSTMForecaster**: Single-step forecasting
- **MultiHorizonLSTM**: Multi-step ahead forecasting
- **AttentionLSTM**: LSTM with attention mechanism
- Configurable layers, hidden sizes, dropout

#### Transformer Models
- **TransformerForecaster**: Full encoder-decoder transformer
- **SimpleTransformerForecaster**: Encoder-only variant
- **TimeSeriesTransformer**: Optimized for time series
- Multi-head attention, positional encoding

### 5. Training Infrastructure
- **PyTorch Lightning**: Simplified training loops
- **MLflow Integration**: Experiment tracking and model registry
- **TensorBoard**: Real-time training visualization
- **Hydra Configuration**: Flexible experiment management
- Callbacks: Early stopping, model checkpointing
- Mixed precision training support
- Multi-GPU training ready

### 6. Experiment Tracking
- MLflow tracking server
- Automatic logging of:
  - Hyperparameters
  - Metrics (MAE, RMSE, R², MAPE)
  - Model artifacts
  - Training curves
  - System metrics
- Model versioning and registry
- Experiment comparison tools

### 7. Data Versioning
- DVC (Data Version Control) integration
- Track data files with Git-like workflow
- Remote storage support (S3, Azure, GCP)
- Reproducible data pipelines
- Data lineage tracking

## Technical Stack

### Core ML/DL
- PyTorch 2.1+
- PyTorch Lightning 2.1+
- NumPy, Pandas, Scikit-learn

### MLOps
- MLflow (Experiment tracking)
- DVC (Data versioning)
- Hydra (Configuration management)

### Data
- Feast (Feature store)
- PyArrow, Fastparquet (Data storage)
- Requests, HTTPX, BeautifulSoup (Data collection)

### Utilities
- Pydantic (Configuration validation)
- Tenacity (Retry mechanisms)
- Python-dotenv (Environment management)

## Project Structure

```
ml/
├── configs/                    # Hydra configurations
│   ├── config.yaml            # Main config
│   ├── data/                  # Data configs
│   │   └── default.yaml
│   ├── model/                 # Model configs
│   │   ├── lstm.yaml
│   │   └── transformer.yaml
│   ├── training/              # Training configs
│   │   └── default.yaml
│   └── logging/               # Logging configs
│       └── default.yaml
│
├── src/                       # Source code
│   ├── data/
│   │   ├── collectors/       # Data collection
│   │   │   ├── base.py
│   │   │   ├── posoco.py
│   │   │   ├── iex.py
│   │   │   ├── weather.py
│   │   │   └── calendar.py
│   │   ├── processors/       # Data processing
│   │   │   ├── preprocessor.py
│   │   │   └── feature_engineering.py
│   │   └── loaders/          # PyTorch datasets
│   │       ├── dataset.py
│   │       └── datamodule.py
│   ├── features/             # Feature store
│   │   └── feature_store.py
│   ├── models/               # Model architectures
│   │   ├── lstm.py
│   │   └── transformer.py
│   ├── training/             # Training modules
│   │   └── lightning_module.py
│   └── inference/            # Inference pipeline
│
├── scripts/                   # Utility scripts
│   ├── collect_data.py       # Data collection
│   ├── preprocess_data.py    # Preprocessing
│   ├── train.py              # Training
│   └── demo.py               # Demo script
│
├── tests/                     # Unit tests
│   └── test_collectors.py
│
├── notebooks/                 # Jupyter notebooks
│   └── 01_data_exploration.ipynb
│
├── data/                      # Data storage (gitignored)
│   ├── raw/
│   ├── processed/
│   └── features/
│
├── models/                    # Trained models
├── logs/                      # Logs and artifacts
│   ├── mlruns/               # MLflow runs
│   └── tensorboard/          # TensorBoard logs
│
├── pyproject.toml            # Project metadata
├── requirements.txt          # Dependencies
├── setup.sh / setup.ps1      # Setup scripts
├── Makefile                  # Common commands
├── README.md                 # Full documentation
├── QUICKSTART.md             # Quick start guide
└── .env.example              # Environment template
```

## Configuration System

### Hierarchical Configuration with Hydra

All configurations are managed through Hydra, allowing:
- Override parameters from command line
- Compose configurations from multiple files
- Environment variable interpolation
- Configuration validation

Example:
```bash
python scripts/train.py \
    model=lstm \
    model.architecture.hidden_size=256 \
    training.epochs=100 \
    training.optimizer.lr=0.0001
```

### Configuration Files

1. **Data Config** (`configs/data/default.yaml`)
   - Data sources (POSOCO, IEX, Weather, Calendar)
   - Date ranges and frequencies
   - Processing strategies
   - Feature engineering settings
   - Train/val/test splits

2. **Model Config** (`configs/model/*.yaml`)
   - Architecture parameters
   - Input/output dimensions
   - Dropout, layers, hidden sizes
   - Forecasting horizons

3. **Training Config** (`configs/training/default.yaml`)
   - Optimizer settings
   - Learning rate schedules
   - Loss functions
   - Early stopping
   - Checkpointing

4. **Logging Config** (`configs/logging/default.yaml`)
   - MLflow settings
   - TensorBoard settings
   - Console and file logging

## Data Flow

```
1. Data Collection
   ├─ POSOCO → Energy load data
   ├─ IEX → Market prices
   ├─ Weather → Temperature, humidity
   └─ Calendar → Holidays, temporal features
   ↓
2. Data Merging
   └─ Merge on timestamp → merged_data.parquet
   ↓
3. Feature Engineering
   ├─ Temporal features
   ├─ Lag features
   ├─ Rolling features
   └─ Domain features
   ↓
4. Preprocessing
   ├─ Handle missing values
   ├─ Detect outliers
   └─ Normalize features
   ↓
5. Feature Store
   └─ Save to Parquet/Feast → processed_data.parquet
   ↓
6. Model Training
   ├─ Create PyTorch datasets
   ├─ Train with Lightning
   └─ Log to MLflow
   ↓
7. Model Registry
   └─ Register best model in MLflow
```

## Key Design Decisions

### 1. Modular Architecture
- Separate collectors for each data source
- Pluggable preprocessing components
- Interchangeable model architectures

### 2. Configuration-Driven
- All settings in YAML files
- No hardcoded parameters
- Easy experimentation

### 3. Production-Ready
- Error handling and retries
- Data validation
- Logging and monitoring
- Caching for efficiency

### 4. Reproducibility
- Fixed random seeds
- DVC for data versioning
- MLflow for experiment tracking
- Version-controlled configs

### 5. Scalability
- Multi-GPU support
- Efficient data loading
- Batch processing
- Feature store for serving

## Metrics and Evaluation

The platform tracks multiple metrics:

1. **Regression Metrics**
   - MAE (Mean Absolute Error)
   - RMSE (Root Mean Squared Error)
   - MAPE (Mean Absolute Percentage Error)
   - R² (Coefficient of Determination)

2. **Training Metrics**
   - Training loss
   - Validation loss
   - Learning rate
   - Gradient norms

3. **System Metrics**
   - Training time
   - Memory usage
   - GPU utilization

## Usage Patterns

### 1. Quick Experimentation
```bash
python scripts/train.py training.fast_dev_run=true
```

### 2. Hyperparameter Search
```bash
for lr in 0.001 0.0001 0.00001; do
    python scripts/train.py training.optimizer.lr=$lr
done
```

### 3. Model Comparison
```bash
python scripts/train.py model=lstm
python scripts/train.py model=transformer
mlflow ui  # Compare results
```

### 4. Production Training
```bash
python scripts/train.py \
    training.epochs=100 \
    training.accelerator=gpu \
    training.devices=4 \
    training.precision=16
```

## Future Enhancements

### Short-term
- [ ] Real-time inference API (FastAPI)
- [ ] Model export (ONNX, TorchScript)
- [ ] Automated hyperparameter tuning (Optuna)
- [ ] More model architectures (N-BEATS, DeepAR)

### Medium-term
- [ ] Distributed training (DDP, DeepSpeed)
- [ ] Model monitoring and drift detection
- [ ] A/B testing framework
- [ ] AutoML capabilities

### Long-term
- [ ] Multi-modal forecasting (text, images)
- [ ] Reinforcement learning for V2G optimization
- [ ] Federated learning for privacy
- [ ] Edge deployment

## Performance Benchmarks

Expected performance on standard hardware:

- **Data Collection**: 10-30 min for 2 years
- **Preprocessing**: 2-5 min for 2 years
- **Training (LSTM)**: 15-30 min per 100 epochs
- **Training (Transformer)**: 30-60 min per 100 epochs
- **Inference**: <10ms per prediction

## Maintenance

### Regular Updates
- Update dependencies quarterly
- Review and update data sources
- Retrain models monthly
- Monitor data drift

### Monitoring
- Check MLflow for failed runs
- Review data quality metrics
- Monitor prediction accuracy
- Track system resources

## License

Copyright BITS Pilani. All rights reserved. See the repository root `LICENSE`.

## Contributors

SHAKTI-CHAIN Team

## Acknowledgments

- POSOCO for energy data
- IEX for market data
- OpenWeatherMap for weather data
- PyTorch Lightning team
- MLflow team
- DVC team
