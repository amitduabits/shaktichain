## SHAKTI-CHAIN Data Collection and Preprocessing Guide

Comprehensive guide for the data collection and preprocessing pipeline.

## Overview

The data pipeline collects, validates, and preprocesses energy data from multiple sources for the SHAKTI-CHAIN V2G platform.

### Data Sources

1. **Grid Load Data**: Regional electricity demand in MW
2. **Weather Data**: Temperature, humidity, wind speed for major cities
3. **Price Data**: IEX day-ahead and real-time market prices
4. **Calendar Data**: Holidays, festivals, and temporal features

### Pipeline Stages

```
Collection → Validation → Preprocessing → Feature Engineering → Training
```

## Quick Start

### Run Complete Pipeline

```bash
python scripts/collect_and_validate.py
```

This will:
1. Collect data from all sources
2. Merge datasets
3. Validate data quality
4. Preprocess and clean data
5. Generate quality reports
6. Save processed data

### Expected Output

```
ml/
├── data/
│   ├── raw/
│   │   ├── merged_data.parquet          # Raw merged data
│   │   └── data_quality_report.txt      # Initial quality report
│   └── processed/
│       ├── processed_data.parquet       # Clean, preprocessed data
│       └── final_quality_report.txt     # Final quality report
```

## Data Sources

### 1. Grid Load Data

**Source**: Synthetic generator based on Indian power system patterns

**Features**:
- Hourly load in MW for 5 regions
- Grid frequency in Hz
- Regional patterns (Northern, Western, Southern, Eastern, North-Eastern)

**Patterns Modeled**:
- Daily cycles (morning/evening peaks, night valleys)
- Weekly patterns (weekday vs weekend)
- Seasonal variations (summer AC load, winter heating)
- Special events (holidays, festivals)

**Base Loads**:
- Northern: 50,000 MW
- Western: 45,000 MW
- Southern: 40,000 MW
- Eastern: 30,000 MW
- North-Eastern: 8,000 MW

**Example**:
```python
from src.data.collectors.synthetic_grid import SyntheticGridCollector, SyntheticGridConfig

config = SyntheticGridConfig()
collector = SyntheticGridCollector(config)
data = collector.collect(start_date, end_date)
```

### 2. Weather Data

**Source**: OpenWeatherMap API or Simulator

**Cities**: Delhi, Mumbai, Bangalore, Chennai, Kolkata

**Features**:
- Temperature (°C)
- Humidity (%)
- Wind speed (m/s)
- Cloud cover (%)

**API Requirements**:
- Free tier: 1,000 calls/day
- Historical data requires paid subscription
- Simulator available for development

**Example**:
```python
from src.data.collectors import WeatherSimulator, WeatherConfig, LocationConfig

config = WeatherConfig(
    locations=[
        LocationConfig(name="Delhi", lat=28.6139, lon=77.2090)
    ]
)
simulator = WeatherSimulator(config)
data = simulator.collect(start_date, end_date)
```

### 3. Price Data

**Source**: Indian Energy Exchange (IEX)

**Markets**:
- DAM (Day-Ahead Market): 24 hourly prices
- RTM (Real-Time Market): 96 15-minute prices

**Features**:
- Price in INR/MWh
- Volume in MWh

**Note**: Current implementation uses synthetic data. Real IEX data requires web scraping or API access.

### 4. Calendar Data

**Source**: Python holidays library + custom festivals

**Features**:
- National holidays
- Regional festivals
- Temporal features (hour, day, week, month)
- Cyclical encodings

**Indian Festivals**:
- Diwali, Holi, Eid, Christmas
- Ugadi, Onam, Pongal
- Republic Day, Independence Day

## Data Validation

### DataValidator Class

Comprehensive validation with multiple checks:

#### 1. Timestamp Validation
- Chronological order
- No duplicates
- Consistent hourly frequency
- Timezone consistency (IST)
- Missing timestamps detection

#### 2. Value Range Validation
- Load: 0 - 200,000 MW
- Frequency: 48.5 - 51.5 Hz
- Temperature: -10 to 55°C
- Humidity: 0 - 100%
- Price: 0 - 50,000 INR/MWh

#### 3. Outlier Detection
- Z-score method (3 sigma threshold)
- IQR method (1.5 * IQR)
- Configurable thresholds

#### 4. Missing Value Analysis
- Count and percentage per column
- Gap size identification
- Interpolation feasibility

#### 5. Anomaly Detection
- Stuck values (sensor failures)
- Sudden changes
- Impossible combinations

### Quality Scores

**Completeness**: Ratio of non-missing values
**Validity**: Values within expected ranges
**Consistency**: Absence of anomalous patterns
**Overall**: Average of above three

### Example Usage

```python
from src.data.validators import DataValidator

validator = DataValidator(
    timezone="Asia/Kolkata",
    outlier_threshold=3.0,
    missing_threshold=0.05  # 5% max missing
)

# Run validation
result = validator.validate_all(data)

# Generate report
report = validator.generate_quality_report(data)
print(f"Overall Quality: {report.overall_score:.2%}")

# Save report
validator.save_report(report, "quality_report.txt")
```

## Preprocessing

### AdvancedPreprocessor Class

Sophisticated preprocessing with multiple strategies:

#### 1. Timezone Normalization
- Converts all timestamps to IST (Asia/Kolkata)
- Handles timezone-naive data
- Preserves DST transitions

#### 2. Resampling
- Ensures consistent hourly frequency
- Aggregation methods: mean, median, sum
- Handles irregular time intervals

#### 3. Missing Value Handling

**Smart Interpolation**:
- Gaps ≤ 3 hours: Time-based interpolation
- Gaps > 3 hours: Forward/backward fill with flagging
- Remaining: Median imputation

**Flagging**:
Creates `{column}_large_gap_filled` boolean columns to track imputed values.

#### 4. Outlier Capping

**Sigma Method** (default):
- Calculate μ ± 3σ bounds
- Clip values outside bounds

**IQR Method**:
- Calculate Q1 - 1.5*IQR and Q3 + 1.5*IQR
- Clip values outside bounds

**Capping Strategies**:
- `clip`: Hard clip to bounds
- `winsorize`: Replace with bound values

#### 5. Data Quality Flags

Adds useful boolean flags:
- `is_weekend`: Saturday or Sunday
- `is_night`: 00:00 - 06:00
- `is_peak_hour`: 09:00-12:00 or 18:00-23:00

### Example Usage

```python
from src.data.processors.advanced_preprocessor import AdvancedPreprocessor

preprocessor = AdvancedPreprocessor(
    timezone="Asia/Kolkata",
    interpolation_max_gap=3,
    outlier_method="sigma",
    outlier_threshold=3.0,
    capping_method="clip"
)

# Run full pipeline
processed = preprocessor.process(
    data,
    normalize_tz=True,
    resample=True,
    handle_missing=True,
    cap_outliers=True,
    add_flags=True
)
```

## Configuration

### Hydra Config

Edit `configs/data/default.yaml`:

```yaml
data:
  collection:
    start_date: "2022-01-01"
    end_date: "2024-12-31"
    frequency: "1H"

  sources:
    weather:
      locations:
        - name: "Delhi"
          lat: 28.6139
          lon: 77.2090

  processing:
    missing_value_strategy: "interpolate"
    outlier_detection: true
    outlier_threshold: 3.0
```

### Override from Command Line

```bash
python scripts/collect_and_validate.py \
    data.collection.start_date="2023-01-01" \
    data.collection.end_date="2023-12-31" \
    data.processing.outlier_threshold=4.0
```

## Data Quality Report

### Report Format

```
SHAKTI-CHAIN Data Quality Report
============================================================

Generated: 2024-12-02 10:30:00

Dataset Overview
------------------------------------------------------------
Total Records: 17,520
Date Range: 2024-01-01 to 2024-12-31
Duration: 365 days

Quality Scores
------------------------------------------------------------
Overall Quality: 95.5% ✓
  - Completeness: 98.2%
  - Validity: 96.5%
  - Consistency: 91.8%

Missing Data
------------------------------------------------------------
Missing Timestamps: 24
Missing Values by Column:
  - load_mw_northern: 12 (0.07%)
  - temperature_c_delhi: 8 (0.05%)

Outliers Detected
------------------------------------------------------------
  - load_mw_northern: 145 (0.83%)
  - price_inr_mwh_dam: 89 (0.51%)

Anomalies
------------------------------------------------------------
Total anomalies detected: 3
  - sudden_change in load_mw_northern: 2 occurrences
  - stuck_values in temperature_c_mumbai: 1 occurrences
```

## Best Practices

### 1. Data Collection

- **Start small**: Test with 1 week before running full 2 years
- **Monitor API limits**: Weather API has rate limits
- **Cache data**: Collectors automatically cache to avoid re-fetching
- **Validate early**: Run validation immediately after collection

### 2. Preprocessing

- **Preserve raw data**: Always keep original data
- **Document changes**: Quality reports track all modifications
- **Check assumptions**: Verify outlier thresholds make sense for your data
- **Iterate**: May need multiple passes for best results

### 3. Quality Control

- **Set thresholds**: Adjust based on your quality requirements
- **Review reports**: Always check quality reports manually
- **Track scores**: Monitor quality scores over time
- **Investigate anomalies**: Understand why anomalies occur

### 4. Production

- **Automate**: Use cron jobs or schedulers for regular updates
- **Monitor**: Set up alerts for quality score drops
- **Version data**: Use DVC to track data versions
- **Document**: Keep records of any manual interventions

## Troubleshooting

### Issue: Low Completeness Score

**Causes**:
- Data source unavailable
- Network issues
- API rate limits exceeded

**Solutions**:
```python
# Increase retry attempts
config.retry_attempts = 5

# Use longer timeouts
config.timeout = 60

# Check API keys
print(os.getenv("OPENWEATHER_API_KEY"))
```

### Issue: Many Outliers Detected

**Causes**:
- Threshold too strict
- Genuine extreme events
- Data quality issues

**Solutions**:
```python
# Adjust threshold
preprocessor = AdvancedPreprocessor(outlier_threshold=4.0)

# Use IQR method instead
preprocessor = AdvancedPreprocessor(outlier_method="iqr")

# Review specific outliers
outliers = data[data["load_mw"] > threshold]
```

### Issue: Large Missing Gaps

**Causes**:
- Data source downtime
- Collection script failures
- Network interruptions

**Solutions**:
```python
# Increase interpolation limit
preprocessor = AdvancedPreprocessor(interpolation_max_gap=6)

# Manual review and filling
gaps = data[data["load_mw"].isnull()]
print(gaps["timestamp"])

# Use alternative data source
# Switch to backup collector
```

### Issue: Timezone Confusion

**Causes**:
- Mixed timezone data
- Daylight saving time
- Data from multiple sources

**Solutions**:
```python
# Ensure IST normalization
preprocessor = AdvancedPreprocessor(timezone="Asia/Kolkata")
processed = preprocessor.normalize_timezone(data)

# Check timezone
print(data["timestamp"].dt.tz)

# Manually set if needed
data["timestamp"] = data["timestamp"].dt.tz_localize("UTC")
data["timestamp"] = data["timestamp"].dt.tz_convert("Asia/Kolkata")
```

## Advanced Usage

### Custom Validation Rules

```python
from src.data.validators import DataValidator

class CustomValidator(DataValidator):
    def validate_custom_rules(self, df):
        # Add your custom validation logic
        result = ValidationResult(passed=True)

        # Example: Check load during peak hours
        peak_hours = df[df["is_peak_hour"]]
        if (peak_hours["load_mw"] < 30000).any():
            result.warnings.append("Low load during peak hours")

        return result

validator = CustomValidator()
result = validator.validate_custom_rules(data)
```

### Custom Preprocessing

```python
from src.data.processors.advanced_preprocessor import AdvancedPreprocessor

class CustomPreprocessor(AdvancedPreprocessor):
    def custom_transform(self, df):
        # Add your custom preprocessing
        df = df.copy()

        # Example: Calculate load factor
        df["load_factor"] = df["load_mw"] / df["load_mw"].max()

        return df

preprocessor = CustomPreprocessor()
processed = preprocessor.custom_transform(data)
```

## Performance Tips

1. **Use caching**: Collectors cache data automatically
2. **Parallel processing**: Collect different sources in parallel
3. **Batch processing**: Process data in chunks for large datasets
4. **Optimize Parquet**: Use appropriate compression
5. **Monitor memory**: Watch memory usage for large date ranges

## Next Steps

After successful data collection and preprocessing:

1. **Feature Engineering**: Run `preprocess_data.py`
2. **Exploratory Analysis**: Use notebooks in `notebooks/`
3. **Model Training**: Run `train.py`
4. **Monitor Quality**: Set up regular quality checks

## References

- [POSOCO Website](https://posoco.in/)
- [IEX India](https://www.iexindia.com/)
- [OpenWeatherMap API](https://openweathermap.org/api)
- [Indian Holidays](https://www.calendarlabs.com/holidays/india/)
