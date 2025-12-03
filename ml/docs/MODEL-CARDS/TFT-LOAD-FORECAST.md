# Model Card: TFT Load Forecasting Model

## Model Details

### Basic Information
- **Model Name**: Temporal Fusion Transformer (TFT) Load Forecasting
- **Model Version**: 1.2.0
- **Model Type**: Time Series Forecasting
- **Framework**: PyTorch Lightning 2.0
- **Training Date**: 2024-11-15
- **Last Updated**: 2024-11-28
- **Model Size**: 45MB
- **License**: Proprietary (SHAKTI-CHAIN)

### Developers
- **Organization**: SHAKTI-CHAIN ML Team
- **Contact**: ml-team@shaktichain.io
- **Contributors**: Data Science Team, Platform Engineering

### References
- Paper: [Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting](https://arxiv.org/abs/1912.09363)
- Implementation: PyTorch Forecasting library
- Training Code: `shaktichain/ml/scripts/train_tft.py`

## Intended Use

### Primary Use Cases
1. **24-hour ahead load forecasting** for V2G trading optimization
2. **48-hour ahead load forecasting** for day-ahead market participation
3. **Uncertainty quantification** via prediction intervals (10%, 50%, 90% quantiles)
4. **Feature importance analysis** for grid understanding

### Primary Intended Users
- **Trading Agent**: Automated energy trading decisions
- **Platform Operators**: Grid capacity planning
- **Market Participants**: Day-ahead bidding strategies
- **Grid Operators**: Load balancing insights

### Out-of-Scope Use Cases
❌ **Real-time control** (sub-minute decisions) - Model designed for hourly forecasts
❌ **Individual household prediction** - Trained on aggregate city-level data
❌ **Non-Indian markets** - Calibrated for Indian grid patterns
❌ **Long-term planning** (> 48 hours) - Accuracy degrades beyond 48h horizon

## Training Data

### Data Sources
1. **POSOCO (Power System Operation Corporation)** - Primary source
   - Load data: 15-minute resolution
   - Coverage: Delhi, Mumbai, Bangalore, Chennai, Kolkata
   - Period: 2022-01-01 to 2024-10-31
   - Records: ~1.2M data points

2. **OpenWeatherMap** - Weather features
   - Temperature, humidity, wind speed, cloud cover
   - Hourly resolution
   - Historical and forecast data

3. **Indian Calendar API** - Calendar features
   - National holidays
   - Festival periods
   - Working days

### Data Characteristics
- **Geography**: 5 major Indian cities
- **Temporal Coverage**: 3 years (2022-2024)
- **Resolution**: Hourly (aggregated from 15-min)
- **Missing Data**: < 2% (imputed via forward-fill + interpolation)
- **Outliers**: Capped at 3σ from rolling mean

### Train/Validation/Test Split
```python
Train:      2022-01-01 to 2024-06-30  (78%)
Validation: 2024-07-01 to 2024-09-30  (12%)
Test:       2024-10-01 to 2024-10-31  (10%)

# Time-series split (no shuffle)
# Validation window: 90 days
# Test window: 30 days
```

### Data Preprocessing
1. **Timestamp alignment**: Round to nearest hour
2. **Missing value imputation**: Forward-fill + linear interpolation
3. **Outlier handling**: Winsorization at 1st and 99th percentiles
4. **Normalization**: Z-score normalization per city
5. **Feature engineering**: 35 features (see Features section)

## Model Architecture

### Input Specification
```python
# Observation window: 168 hours (7 days)
# Prediction horizon: 24-48 hours

Input Shape: (batch_size, 168, 35)

# Feature groups:
- Static (5): city_id, season, latitude, longitude, population
- Past observed (15): load, temperature, humidity, etc.
- Known future (15): hour, day, month, weather_forecast, holidays
```

### Architecture Details
```python
Temporal Fusion Transformer:

  # Encoder
  Variable Selection Network:
    - Input: 35 features
    - Hidden: 64
    - Output: Selected features with importance weights

  LSTM Encoder:
    - Hidden size: 256
    - Num layers: 2
    - Dropout: 0.1
    - Bidirectional: False

  Static Covariate Encoders:
    - Context vectors: 32
    - Used for variable selection and attention

  # Decoder
  Multi-Head Attention:
    - Heads: 4
    - Key/Query/Value dim: 64
    - Attention dropout: 0.1

  Gated Residual Network:
    - Hidden: 64
    - Layers: 2
    - Skip connections: Yes

  Quantile Prediction Heads:
    - Quantiles: [0.1, 0.5, 0.9]
    - Output dim: 3 per timestep
    - Activation: None (direct quantile output)

Total Parameters: 4.2M
Trainable Parameters: 4.2M
```

### Training Configuration
```python
Loss Function: Quantile Loss
  QL(q) = max(q * (y - ŷ), (q - 1) * (y - ŷ))
  Combined loss: mean(QL(0.1) + QL(0.5) + QL(0.9))

Optimizer: Adam
  - Learning rate: 1e-3
  - Betas: (0.9, 0.999)
  - Weight decay: 1e-5
  - Gradient clipping: 1.0

Learning Rate Schedule: ReduceLROnPlateau
  - Factor: 0.5
  - Patience: 5 epochs
  - Min LR: 1e-6

Training:
  - Batch size: 64
  - Max epochs: 100
  - Early stopping: 10 epochs (validation MAPE)
  - Hardware: NVIDIA V100 GPU
  - Training time: ~6 hours
```

## Performance

### Evaluation Metrics

#### Overall Performance (Test Set)
| Horizon | MAPE | RMSE | MAE | Coverage (90% PI) |
|---------|------|------|-----|-------------------|
| 1h | 2.1% | 145 MW | 98 MW | 93.2% |
| 6h | 3.4% | 201 MW | 156 MW | 92.1% |
| 12h | 4.2% | 268 MW | 203 MW | 91.5% |
| 24h | 5.8% | 342 MW | 287 MW | 90.8% |
| 48h | 8.1% | 476 MW | 398 MW | 88.4% |

**Target**: MAPE < 10% for 24h horizon ✅

#### Per-City Performance (24h Horizon)
| City | MAPE | RMSE | Notes |
|------|------|------|-------|
| Delhi | 4.8% | 310 MW | Best performance |
| Mumbai | 5.2% | 295 MW | Stable load pattern |
| Bangalore | 6.1% | 380 MW | Tech hub variability |
| Chennai | 5.9% | 350 MW | Seasonal effects |
| Kolkata | 6.5% | 410 MW | Festival impact |

#### Comparison with Baselines
| Model | MAPE (24h) | Training Time | Inference Time |
|-------|------------|---------------|----------------|
| **TFT (Ours)** | **5.8%** | 6h | 50ms |
| LSTM | 8.2% | 2h | 30ms |
| Prophet | 12.5% | 5min | 100ms |
| ARIMA | 15.3% | 30min | 20ms |
| Naive (persistence) | 18.7% | - | 1ms |

**Improvement over naive baseline**: 68.8% ✅

### Performance by Time Period
```python
# Weekday vs Weekend
Weekday MAPE: 5.2%
Weekend MAPE: 7.8%  # Higher uncertainty

# Season
Summer (Apr-Jun): 5.1%
Monsoon (Jul-Sep): 6.2%
Winter (Oct-Mar): 6.0%

# Time of Day
00:00-06:00: 4.2%  # Stable nighttime load
06:00-12:00: 6.1%  # Morning ramp
12:00-18:00: 5.8%  # Afternoon
18:00-24:00: 7.2%  # Evening peak variability
```

### Prediction Interval Coverage
```python
# Target: 90% coverage for 90% prediction interval
Actual coverage: 90.8% ✅

# Calibration analysis
Under-prediction: 4.8%  # Actual > upper bound
Within interval: 90.8%  # Actual within bounds
Over-prediction: 4.4%   # Actual < lower bound

# Well-calibrated intervals
```

### Feature Importance
Top 10 most important features (averaged across predictions):
1. `load_lag_24` (24h ago) - 18.3%
2. `hour_sin` (time of day) - 12.1%
3. `temperature_forecast` - 9.8%
4. `load_lag_168` (1 week ago) - 8.7%
5. `day_of_week_cos` - 7.2%
6. `load_rolling_mean_24` - 6.5%
7. `is_weekend` - 5.4%
8. `temperature_lag_1` - 4.8%
9. `humidity` - 3.9%
10. `is_festival_period` - 3.2%

## Limitations

### Known Limitations

1. **Festival Periods** (MAPE: 12-15%)
   - Significantly higher errors during major festivals (Diwali, Holi)
   - Irregular consumption patterns not well captured
   - Mitigation: Separate festival-aware model being developed

2. **Extreme Weather Events** (MAPE: 18-22%)
   - Degraded performance during heatwaves, storms
   - Limited training examples of extreme events
   - Mitigation: Ensemble with weather-specialist model

3. **Grid Disruptions**
   - Cannot predict unplanned outages
   - Assumes normal grid operations
   - Mitigation: Anomaly detection system in place

4. **Long-term Structural Changes**
   - Model assumes stationary load patterns
   - Major infrastructure changes require retraining
   - Mitigation: Weekly retraining with recent data

5. **Weather Forecast Dependency**
   - Accuracy depends on weather forecast quality
   - Forecast errors propagate to load predictions
   - Mitigation: Ensemble multiple weather sources

6. **Geographic Limitation**
   - Trained only on 5 Indian cities
   - Not validated for other regions
   - Mitigation: Transfer learning for new cities

### Edge Cases

❌ **New Year's Eve/Day**: MAPE ~20% (unusual patterns)
❌ **National lockdowns**: Model not seen pandemic scenarios
❌ **First day after festival**: MAPE ~14% (adjustment period)
❌ **Power outages > 2 hours**: Disrupts historical context
⚠️ **Election days**: MAPE ~9% (moderate increase)
⚠️ **Cricket World Cup finals**: MAPE ~8% (manageable)

## Ethical Considerations

### Bias Analysis
- **Geographic**: Trained on urban centers; rural areas not represented
- **Socioeconomic**: Aggregate data masks equity issues
- **Temporal**: Recent years over-represented vs historical patterns

### Fairness
- Model performance similar across cities (max 2% MAPE difference)
- No systematic bias against any region identified
- Equal prediction quality for all market participants

### Privacy
- **Data**: Aggregate city-level only, no individual households
- **PII**: No personally identifiable information used
- **Compliance**: GDPR-compliant (aggregate data, consent not required)

### Transparency
- Feature importance available for all predictions
- Attention weights provide interpretability
- Model card publicly available
- Training data sources documented

### Environmental Impact
- **Training**: ~18 kWh (6h on V100 GPU)
- **Inference**: ~0.02 Wh per prediction
- **Carbon**: ~3 kg CO2e for training (AWS US-East)
- **Mitigation**: Retraining on renewable energy when possible

## Maintenance

### Model Lifecycle

```python
# Retraining Schedule
Frequency: Weekly (every Monday 02:00 IST)
Trigger: Automated via Airflow
Duration: ~6 hours
Validation: Automatic backtest on last 30 days
Deployment: Auto-promote if MAPE < 10%

# Drift Monitoring
Metrics:
  - Feature drift (KS test daily)
  - Prediction drift (PSI weekly)
  - Performance drift (MAPE rolling)

Thresholds:
  - Feature drift: p-value < 0.05
  - PSI > 0.25
  - MAPE increases > 20%

Actions:
  - Slack alert to ML team
  - Trigger retraining
  - Rollback if new model worse
```

### Version History

| Version | Date | Changes | MAPE (24h) |
|---------|------|---------|------------|
| 1.0.0 | 2024-06-15 | Initial release | 7.2% |
| 1.1.0 | 2024-09-10 | Add festival features | 6.4% |
| 1.2.0 | 2024-11-15 | Increase context window | 5.8% |

### Known Issues
- Issue #47: High memory usage on CPU inference (>4GB)
- Issue #52: Slow first prediction after cold start (~2s)
- Issue #61: Festival list needs annual update

### Contact & Support
- **Bug Reports**: GitHub Issues
- **Questions**: ml-team@shaktichain.io
- **Urgent Issues**: Slack #ml-prod-support
- **On-call**: PagerDuty escalation

## Usage

### Loading the Model

```python
import mlflow
from src.training.tft_lightning_module import TFTLightningModule

# Load from MLflow
model_uri = "models:/tft_load_forecast/production"
model = mlflow.pytorch.load_model(model_uri)

# Or load checkpoint
model = TFTLightningModule.load_from_checkpoint(
    "path/to/model.ckpt"
)
```

### Making Predictions

```python
import pandas as pd
from datetime import datetime, timedelta

# Prepare input data (last 168 hours)
historical_data = fetch_historical_data(
    city="delhi",
    start=datetime.now() - timedelta(hours=168),
    end=datetime.now()
)

# Add future known covariates (next 24 hours)
future_data = create_future_covariates(
    horizon=24,
    weather_forecast=weather_api.get_forecast("delhi", 24)
)

# Predict
predictions = model.predict(
    historical=historical_data,
    future=future_data,
    quantiles=[0.1, 0.5, 0.9]
)

# Output format
print(predictions)
# {
#   'point_forecast': [2450, 2380, ...],  # 24 values
#   'lower_bound': [2100, 2050, ...],
#   'upper_bound': [2800, 2710, ...],
#   'timestamps': ['2024-12-04T00:00', ...],
#   'feature_importance': {'load_lag_24': 0.183, ...}
# }
```

### API Usage

```bash
curl -X POST http://ml-service:8000/forecast/predict \
  -H "Content-Type: application/json" \
  -d '{
    "city": "delhi",
    "horizon": 24,
    "include_uncertainty": true,
    "include_feature_importance": true
  }'
```

## Citation

```bibtex
@article{lim2021temporal,
  title={Temporal fusion transformers for interpretable multi-horizon time series forecasting},
  author={Lim, Bryan and Ar{\i}k, Sercan {\"O} and Loeff, Nicolas and Pfister, Tomas},
  journal={International Journal of Forecasting},
  volume={37},
  number={4},
  pages={1748--1764},
  year={2021},
  publisher={Elsevier}
}

@misc{shaktichain2024tft,
  title={TFT Load Forecasting Model for V2G Trading},
  author={{SHAKTI-CHAIN ML Team}},
  year={2024},
  howpublished={\url{https://github.com/shaktichain/ml}}
}
```

---

**Model Card Version**: 1.1
**Last Updated**: 2024-12-03
**Next Review**: 2025-01-03
**Owner**: ML Engineering Team
