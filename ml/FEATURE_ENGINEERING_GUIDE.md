# SHAKTI-CHAIN Feature Engineering Guide

Comprehensive guide to feature engineering for energy load forecasting.

## Overview

The `FeatureEngineering` class provides a sklearn-style fit/transform interface for creating comprehensive features from raw time series data.

### Key Features

- ✅ **Temporal Features**: Hour, day, week, month with cyclical encoding
- ✅ **Lag Features**: Historical values (1h to 1 year)
- ✅ **Rolling Statistics**: Moving windows (mean, std, min, max)
- ✅ **Weather-Derived**: HDD, CDD, apparent temperature
- ✅ **Derived Features**: Differences, percentage changes
- ✅ **Interaction Features**: Temperature-load, hour-temperature
- ✅ **Automatic Scaling**: StandardScaler for numerical features
- ✅ **Persistence**: Save/load fitted state

## Quick Start

```python
from src.features import FeatureEngineering

# Initialize
fe = FeatureEngineering()

# Fit on training data
fe.fit(train_df)

# Transform
train_features = fe.transform(train_df)
test_features = fe.transform(test_df)

# Or fit_transform
train_features = fe.fit_transform(train_df)
```

## Feature Categories

### 1. Temporal Features

**Purpose**: Capture time-based patterns (daily, weekly, seasonal)

**Features Created**:
- `hour` (0-23)
- `day_of_week` (0-6, Monday=0)
- `day_of_month` (1-31)
- `month` (1-12)
- `quarter` (1-4)
- `week_of_year` (1-52)
- `is_weekend` (0/1)
- `is_month_start`, `is_month_end` (0/1)

**Cyclical Encoding**:
```python
hour_sin = sin(2π * hour / 24)
hour_cos = cos(2π * hour / 24)
```

Why: Captures cyclic nature (23:00 is close to 00:00)

**Example**:
```python
fe = FeatureEngineering(
    include_temporal=True,
    cyclical_features=["hour", "day_of_week", "month"]
)
```

### 2. Lag Features

**Purpose**: Use historical values as features

**Default Lags**:
- Short-term: 1h, 2h, 3h, 6h, 12h
- Daily: 24h (same hour yesterday)
- Weekly: 168h (same hour last week)
- Yearly: 8760h (same hour last year)

**Features Created**:
```python
load_mw_lag_1h    # Load 1 hour ago
load_mw_lag_24h   # Load same hour yesterday
load_mw_lag_168h  # Load same hour last week
```

**Example**:
```python
fe = FeatureEngineering(
    include_lags=True,
    lag_hours=[1, 2, 3, 24, 168, 8760],
    lag_columns=["load_mw", "price_inr_mwh"]
)
```

**Best Practices**:
- Always include 24h lag (strong daily pattern)
- Include 168h for weekly patterns
- Yearly lag (8760h) useful for seasonal patterns
- More lags = more features but also more NaN rows

### 3. Rolling Statistics

**Purpose**: Capture trends and variability

**Statistics**:
- `mean`: Average over window
- `std`: Volatility/variability
- `min`: Minimum in window
- `max`: Maximum in window
- `median`: Robust average

**Default Windows**:
- 24h: Daily patterns
- 168h: Weekly patterns

**Features Created**:
```python
load_mw_rolling_mean_24h  # 24-hour moving average
load_mw_rolling_std_24h   # 24-hour volatility
load_mw_rolling_min_24h   # 24-hour minimum
load_mw_rolling_max_24h   # 24-hour maximum
```

**Example**:
```python
fe = FeatureEngineering(
    include_rolling=True,
    rolling_windows=[24, 168],
    rolling_statistics=["mean", "std", "min", "max"],
    rolling_columns=["load_mw"]
)
```

### 4. Weather-Derived Features

**Purpose**: Derive meaningful weather metrics

**Features Created**:

#### Heating Degree Days (HDD)
```python
HDD = max(base_temp - current_temp, 0)
```
When heating is needed (winter)

#### Cooling Degree Days (CDD)
```python
CDD = max(current_temp - base_temp, 0)
```
When cooling is needed (summer)

#### Apparent Temperature (Heat Index)
```python
apparent_temp = T + 0.5555 * (vapor_pressure * (RH/100) - 10)
```
How hot it "feels" (accounts for humidity)

#### Discomfort Index
```python
discomfort = T - 0.55 * (1 - RH/100) * (T - 14.5)
```
Thermal comfort metric

**Example**:
```python
fe = FeatureEngineering(
    include_weather=True,
    base_temperature=18.0  # Comfortable temp in °C
)
```

### 5. Derived Features

**Purpose**: Capture changes and time-based indicators

**Difference Features**:
```python
load_diff_1h = load(t) - load(t-1)     # Hourly change
load_diff_24h = load(t) - load(t-24)   # Day-over-day change
```

**Percentage Changes**:
```python
load_pct_change_1h = (load(t) - load(t-1)) / load(t-1)
```

**Time Indicators**:
- `is_peak_hour`: 18:00-22:00 (high demand)
- `is_shoulder_hour`: 06:00-09:00, 16:00-18:00
- `is_offpeak_hour`: 22:00-06:00 (low demand)
- `is_working_hour`: 09:00-18:00 on weekdays

**Example**:
```python
fe = FeatureEngineering(include_derived=True)
```

### 6. Interaction Features

**Purpose**: Capture non-linear relationships

**Temperature-Load Interaction**:
```python
temp_load_interaction = temperature * load
```
Load response to temperature varies by load level

**Hour-Temperature Interaction**:
```python
hour_temp_interaction = hour * temperature
```
Temperature impact varies by time of day

**Weekend-Hour Interaction**:
```python
weekend_hour_interaction = is_weekend * hour
```
Weekend patterns differ from weekdays

**Example**:
```python
fe = FeatureEngineering(include_interactions=True)
```

## Configuration

### Full Configuration Example

```python
fe = FeatureEngineering(
    # Temporal
    include_temporal=True,
    cyclical_features=["hour", "day_of_week", "month"],

    # Lags
    include_lags=True,
    lag_hours=[1, 2, 3, 6, 12, 24, 48, 168, 8760],
    lag_columns=["load_mw", "price_inr_mwh"],

    # Rolling
    include_rolling=True,
    rolling_windows=[24, 168],
    rolling_statistics=["mean", "std", "min", "max"],
    rolling_columns=["load_mw"],

    # Weather
    include_weather=True,

    # Derived
    include_derived=True,

    # Interactions
    include_interactions=True,

    # Scaling
    scale_features=True
)
```

### Minimal Configuration (Fast)

```python
fe = FeatureEngineering(
    include_temporal=True,
    include_lags=True,
    lag_hours=[1, 24, 168],  # Only key lags
    include_rolling=False,
    include_weather=False,
    include_derived=True,
    include_interactions=False,
    scale_features=False
)
```

## Usage Patterns

### Pattern 1: Training Pipeline

```python
# Load data
train_df = pd.read_parquet("train.parquet")
val_df = pd.read_parquet("val.parquet")
test_df = pd.read_parquet("test.parquet")

# Initialize
fe = FeatureEngineering()

# Fit on training data only
fe.fit(train_df)

# Transform all sets
train_features = fe.transform(train_df)
val_features = fe.transform(val_df)
test_features = fe.transform(test_df)

# Save fitted feature engineering
fe.save("feature_engineering.pkl")
```

### Pattern 2: Inference

```python
# Load fitted feature engineering
fe = FeatureEngineering.load("feature_engineering.pkl")

# Transform new data
new_features = fe.transform(new_data)
```

### Pattern 3: Feature Selection

```python
# Create all features
fe = FeatureEngineering()
features = fe.fit_transform(data)

# Get feature names
all_features = fe.get_feature_names()

# Select important features (from analysis)
important_features = [
    "load_mw_lag_24h",
    "load_mw_lag_168h",
    "load_mw_rolling_mean_24h",
    "hour_sin",
    "hour_cos",
    "is_peak_hour",
    "temperature_c_delhi",
    "cdd_delhi"
]

# Use only important features
X = features[important_features]
```

## Best Practices

### 1. Always Fit on Training Data Only

```python
# ✓ Correct
fe.fit(train_df)
train_features = fe.transform(train_df)
test_features = fe.transform(test_df)

# ✗ Wrong (data leakage)
fe.fit(pd.concat([train_df, test_df]))
```

### 2. Handle NaN Values

Lag and rolling features create NaN values in first rows:

```python
# Option 1: Drop NaN rows
features = features.dropna()

# Option 2: Use min_periods in rolling
fe = FeatureEngineering(
    rolling_windows=[24],
    # Will compute with available data
)

# Option 3: Forward fill (use with caution)
features = features.fillna(method='ffill')
```

### 3. Feature Scaling

For deep learning models, scale features:

```python
fe = FeatureEngineering(scale_features=True)
```

For tree-based models, scaling not needed:

```python
fe = FeatureEngineering(scale_features=False)
```

### 4. Monitor Feature Count

```python
stats = fe.get_feature_statistics()
print(f"Total features: {stats['n_features']}")
print(f"Lag features: {stats['n_lag']}")
print(f"Rolling features: {stats['n_rolling']}")
```

Too many features can cause:
- Overfitting
- Slow training
- Memory issues

**Solution**: Use feature selection

### 5. Save Fitted State

Always save fitted feature engineering for production:

```python
# After fitting
fe.save("models/feature_engineering.pkl")

# In production
fe = FeatureEngineering.load("models/feature_engineering.pkl")
```

## Feature Importance

Use the notebook `02_feature_importance_analysis.ipynb` to analyze:

1. **Correlation** with target
2. **Random Forest** importance
3. **Permutation** importance
4. **Feature categories** analysis

Example output:
```
Top 10 Features:
1. load_mw_lag_24h         (0.89)
2. load_mw_lag_168h        (0.82)
3. load_mw_rolling_mean_24h (0.76)
4. hour_sin                (0.65)
5. temperature_c_delhi     (0.58)
...
```

## Performance Tips

### 1. Reduce Feature Count

```python
# Use fewer lags
lag_hours=[1, 24, 168]  # Instead of [1,2,3,6,12,24,48,168]

# Use fewer rolling windows
rolling_windows=[24]  # Instead of [24, 168]

# Disable expensive features
include_interactions=False
```

### 2. Batch Processing

For large datasets:

```python
chunk_size = 10000
results = []

for chunk in pd.read_parquet("data.parquet", chunksize=chunk_size):
    features = fe.transform(chunk)
    results.append(features)

all_features = pd.concat(results)
```

### 3. Parallelize

Rolling statistics can be slow. Use Dask for parallelization:

```python
import dask.dataframe as dd

# Convert to Dask DataFrame
ddf = dd.from_pandas(df, npartitions=4)

# Apply feature engineering per partition
```

## Troubleshooting

### Issue: Too Many NaN Values

**Cause**: Large lag/rolling windows

**Solution**:
```python
# Reduce maximum lag
lag_hours=[1, 24, 168]  # Remove 8760h

# Use smaller rolling windows
rolling_windows=[24]  # Remove 168h

# Drop NaN after feature creation
features = features.dropna()
```

### Issue: Memory Error

**Cause**: Too many features * too many samples

**Solution**:
```python
# 1. Reduce features
fe = FeatureEngineering(
    include_rolling=False,
    include_interactions=False
)

# 2. Use float32 instead of float64
features = features.astype(np.float32)

# 3. Process in chunks
for chunk in pd.read_parquet(..., chunksize=10000):
    process(chunk)
```

### Issue: Features Have Wrong Values

**Cause**: Not fitted or loaded incorrect state

**Solution**:
```python
# Check if fitted
if not fe.is_fitted:
    fe.fit(train_df)

# Verify loaded correctly
fe_loaded = FeatureEngineering.load("path.pkl")
print(fe_loaded.get_feature_statistics())
```

## Advanced Usage

### Custom Feature Engineering

Extend the class:

```python
class CustomFeatureEngineering(FeatureEngineering):
    def _create_custom_features(self, df):
        df = df.copy()

        # Add custom logic
        df["custom_feature"] = ...

        return df

    def _transform_impl(self, df, is_fitting=False):
        df = super()._transform_impl(df, is_fitting)
        df = self._create_custom_features(df)
        return df
```

### Feature Selection Pipeline

```python
from sklearn.feature_selection import SelectKBest, f_regression

# Create all features
fe = FeatureEngineering()
X = fe.fit_transform(train_df)

# Select best features
selector = SelectKBest(f_regression, k=50)
X_selected = selector.fit_transform(X, y)

# Get selected feature names
selected_features = X.columns[selector.get_support()].tolist()

# Use only selected features in production
X_prod = X[selected_features]
```

## Examples

See notebooks:
- `01_data_exploration.ipynb`: Data overview
- `02_feature_importance_analysis.ipynb`: Feature analysis

## References

- [Feature Engineering for Time Series](https://www.kaggle.com/code/andradaolteanu/feature-engineering-for-time-series-forecasting)
- [Cyclical Features](https://ianlondon.github.io/blog/encoding-cyclical-features-24hour-time/)
- [Degree Days](https://en.wikipedia.org/wiki/Heating_degree_day)
