# Changelog

All notable changes to the SHAKTI-CHAIN ML Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-02

### Added

#### Data Collection
- POSOCOCollector for energy load data from National Load Dispatch Centre
- IEXCollector for electricity market prices (DAM and RTM)
- WeatherCollector for OpenWeatherMap API integration
- WeatherSimulator for development without API key
- CalendarCollector for Indian holidays and festivals
- Base collector class with caching and retry mechanisms
- Configurable data collection via Hydra

#### Data Processing
- DataPreprocessor with multiple strategies:
  - Missing value handling (interpolate, forward fill, drop)
  - Outlier detection using z-score method
  - Normalization (standard, minmax, robust)
- FeatureEngineer with 50+ features:
  - Temporal features (hour, day, week, month, quarter)
  - Cyclical encodings (sin/cos transformations)
  - Lag features (configurable periods)
  - Rolling window statistics
  - Domain-specific features (peak hours, seasons, etc.)
  - Weather-derived features
  - Price volatility features

#### Feature Store
- ParquetFeatureStore for efficient feature storage
- ShaktiChainFeatureStore wrapper for Feast integration
- Feature versioning and time-travel capabilities
- Feature merging utilities

#### Models
- LSTM architectures:
  - LSTMForecaster (single-step)
  - MultiHorizonLSTM (multi-step)
  - AttentionLSTM (with attention mechanism)
- Transformer architectures:
  - TransformerForecaster (full encoder-decoder)
  - SimpleTransformerForecaster (encoder-only)
  - TimeSeriesTransformer (time series optimized)
- Configurable architecture parameters

#### Training Infrastructure
- PyTorch Lightning integration
- ForecastingLightningModule with:
  - Multiple optimizers (Adam, AdamW, SGD)
  - Learning rate schedulers (ReduceOnPlateau, Cosine, Step)
  - Loss functions (MSE, MAE, Huber)
  - Metrics (MAE, RMSE, MAPE, R²)
- Early stopping and model checkpointing
- Mixed precision training support
- Multi-GPU training ready

#### Experiment Tracking
- MLflow integration for:
  - Experiment tracking
  - Model registry
  - Artifact logging
  - Parameter logging
- TensorBoard logging
- Comprehensive metrics tracking

#### Data Versioning
- DVC initialization and configuration
- .dvcignore for proper file filtering
- Data tracking templates

#### Configuration Management
- Hydra configuration system
- Hierarchical configs:
  - Data configuration
  - Model configurations (LSTM, Transformer)
  - Training configuration
  - Logging configuration
- Command-line override support
- Environment variable interpolation

#### Scripts
- collect_data.py: Automated data collection from all sources
- preprocess_data.py: Data preprocessing and feature engineering
- train.py: Model training with MLflow tracking
- demo.py: Platform demonstration script

#### Testing
- Unit tests for data collectors
- Test infrastructure setup
- pytest configuration

#### Documentation
- Comprehensive README.md
- QUICKSTART.md for fast onboarding
- PROJECT_SUMMARY.md for technical overview
- Code documentation and docstrings

#### Development Tools
- setup.sh for Linux/Mac setup
- setup.ps1 for Windows PowerShell setup
- Makefile with common commands
- .env.example for environment configuration
- .gitignore for proper file exclusion

#### Project Structure
- Organized src/ directory with:
  - data/ (collectors, processors, loaders)
  - features/ (feature store)
  - models/ (architectures)
  - training/ (training modules)
  - inference/ (deployment ready)
- tests/ directory for unit tests
- notebooks/ for exploration
- scripts/ for automation

### Configuration Files
- pyproject.toml with full dependency specification
- requirements.txt for pip installation
- DVC configuration files
- Hydra config hierarchy

### Features
- Support for Python 3.10+
- Type hints throughout codebase
- Pydantic models for configuration validation
- Comprehensive logging
- Error handling and retry mechanisms
- Caching for data collectors
- Reproducible training with seed setting

### Documentation
- Installation instructions
- Usage examples
- Configuration guide
- API documentation
- Troubleshooting guide

## [Unreleased]

### Planned Features
- Real-time inference API
- Model export (ONNX, TorchScript)
- Hyperparameter tuning with Optuna
- Additional model architectures (N-BEATS, DeepAR)
- Model monitoring and drift detection
- A/B testing framework
- Distributed training support
- AutoML capabilities

### Under Consideration
- Web-based dashboard
- Kubernetes deployment
- Real-time data streaming
- Multi-modal learning
- Reinforcement learning integration
- Federated learning
- Edge deployment

## Notes

This is the initial release of the SHAKTI-CHAIN ML Platform. The platform is production-ready but will continue to evolve with additional features and improvements.

For detailed information about each component, see the README.md and PROJECT_SUMMARY.md files.
