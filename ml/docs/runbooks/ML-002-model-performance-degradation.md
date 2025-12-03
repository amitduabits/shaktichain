# ML-002: Model Performance Degradation

## Overview
**Alert**: ForecastAccuracyDegraded / FeatureDriftDetected / AnomalyRateSpike
**Severity**: Warning
**Component**: ML Models, Data Quality
**SLO Impact**: Potential - affects prediction accuracy

## Symptoms
- MAPE exceeds 15% for 1+ hour
- Feature drift score > 0.5
- Sudden spike in anomaly detection rate
- Increasing forecast errors over time
- User complaints about prediction quality

## Investigation Steps

### 1. Check Current Forecast Accuracy
```bash
# Check MAPE by model and horizon
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_forecast_accuracy{metric="mape"}' | jq

# Check forecast error distribution
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.95, rate(ml_forecast_error_bucket[1h])) by (model, horizon)' | jq

# Compare with historical baseline
curl -s http://prometheus:9090/api/v1/query_range \
  --data-urlencode 'query=ml_forecast_accuracy{metric="mape"}' \
  --data-urlencode 'start=-24h' \
  --data-urlencode 'end=now' \
  --data-urlencode 'step=1h' | jq
```

### 2. Check Feature Drift
```bash
# Check drift scores for all features
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_drift_score{drift_type="ks"} > 0.5' | jq

# Get top drifting features
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=topk(10, ml_feature_drift_score)' | jq
```

### 3. Check Feature Staleness
```bash
# Check if features are stale
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_staleness_seconds > 600' | jq

# Check feature update timestamps
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_last_updated_timestamp' | jq
```

### 4. Check Data Quality
```bash
# Check for missing values
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_missing_rate > 0.1' | jq

# Check for out-of-bounds values
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(ml_feature_out_of_bounds_total[10m])' | jq

# Check feature statistics
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_value' | jq
```

### 5. Check Model Version
```bash
# Check current model version
curl http://ml-service:8000/models | jq '.[] | {model: .name, version: .version, updated: .last_updated}'

# Check when model was last updated
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_model_last_updated_timestamp' | jq
```

### 6. Review Recent Changes
```bash
# Check for recent model updates
curl -s http://prometheus:9090/api/v1/query_range \
  --data-urlencode 'query=changes(ml_model_last_updated_timestamp[5m])' \
  --data-urlencode 'start=-7d' \
  --data-urlencode 'end=now' \
  --data-urlencode 'step=1h' | jq

# Check MLflow for recent experiments
curl http://mlflow:5000/api/2.0/mlflow/experiments/list | jq

# Review model registry
curl http://mlflow:5000/api/2.0/mlflow/registered-models/list | jq
```

## Common Causes & Solutions

### Cause 1: Feature Drift
**Symptoms**: High drift scores, accuracy degradation
**Solution**:
```bash
# Analyze drift
cd /app/shaktichain/ml
python scripts/analyze_drift.py --model tft --lookback 7d

# Retrain model with recent data
python scripts/train_tft.py \
  --config configs/training/tft.yaml \
  --experiment drift-retrain-$(date +%Y%m%d)

# Deploy new model
python scripts/deploy_model.py \
  --model tft \
  --version latest \
  --stage production
```

### Cause 2: Stale Features
**Symptoms**: Features not updating, high staleness
**Solution**:
```bash
# Check feature pipeline status
docker logs shakti-feature-pipeline --tail 100

# Restart feature pipeline
docker-compose restart feature-pipeline

# Manually trigger feature refresh
curl -X POST http://feature-pipeline:8080/refresh \
  -H "Content-Type: application/json" \
  -d '{"features": ["all"]}'
```

### Cause 3: Data Quality Issues
**Symptoms**: High missing rate, OOB values
**Solution**:
```bash
# Run data validation
cd /app/shaktichain/ml
python scripts/validate_data.py \
  --input data/raw/latest \
  --output data/validation_report.json

# Check data sources
python scripts/check_data_sources.py

# Re-collect data if corrupted
python scripts/collect_and_validate.py --backfill 7d
```

### Cause 4: Concept Drift / Seasonality
**Symptoms**: Gradual accuracy decrease, seasonal patterns
**Solution**:
```bash
# Analyze prediction residuals
cd /app/shaktichain/ml
python scripts/analyze_residuals.py \
  --model tft \
  --period 30d

# Retrain with adaptive window
python scripts/train_tft.py \
  --config configs/training/tft.yaml \
  --adaptive-window \
  --experiment concept-drift-$(date +%Y%m%d)

# Enable online learning if available
# Edit configs/training/tft.yaml:
#   continuous_learning:
#     enabled: true
#     retrain_threshold: 0.15
```

### Cause 5: Model Overfitting
**Symptoms**: Good training metrics, poor production metrics
**Solution**:
```bash
# Evaluate model on holdout set
cd /app/shaktichain/ml
python scripts/evaluate_models.py \
  --model tft \
  --split test

# Retrain with regularization
python scripts/train_tft.py \
  --config configs/training/tft.yaml \
  --dropout 0.3 \
  --weight-decay 0.01 \
  --experiment regularized-$(date +%Y%m%d)
```

### Cause 6: External Factors
**Symptoms**: Sudden accuracy drop, correlated with external events
**Solution**:
```bash
# Check for external events
# - Weather anomalies
# - Grid events
# - Holidays
# - Market changes

# Add event features
cd /app/shaktichain/ml
python scripts/add_event_features.py \
  --events data/external_events.json

# Retrain with event features
python scripts/train_tft.py \
  --config configs/training/tft.yaml \
  --include-events \
  --experiment events-$(date +%Y%m%d)
```

## Resolution Steps

### Immediate Actions
1. **Monitor impact**: Check how many users affected
   ```bash
   # Check request rate and error rate
   curl -s http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=rate(ml_request_total[5m])' | jq
   ```

2. **Rollback if recent update**: If accuracy dropped after deployment
   ```bash
   # Rollback to previous model version
   curl -X POST http://ml-service:8000/models/rollback \
     -H "Content-Type: application/json" \
     -d '{"model": "tft", "version": "previous"}'
   ```

3. **Enable fallback**: Use ensemble or baseline model
   ```bash
   # Switch to ensemble model
   curl -X POST http://ml-service:8000/models/switch \
     -H "Content-Type: application/json" \
     -d '{"model": "tft", "backend": "ensemble"}'
   ```

### Investigation & Fix
1. **Analyze root cause**: Use investigation steps above
2. **Fix data pipeline**: If data quality issue
3. **Retrain model**: If drift detected
4. **Add monitoring**: For new failure modes

### Validation
1. **Backtest new model**:
   ```bash
   cd /app/shaktichain/ml
   python scripts/run_backtest.py \
     --model tft-new \
     --start -30d \
     --end now
   ```

2. **A/B test**:
   ```bash
   # Deploy as challenger
   curl -X POST http://ml-service:8000/models/deploy \
     -H "Content-Type: application/json" \
     -d '{
       "model": "tft",
       "version": "new",
       "stage": "challenger",
       "traffic_pct": 0.1
     }'

   # Monitor for 24h, then promote if better
   ```

3. **Monitor metrics**:
   ```bash
   # Check MAPE after deployment
   watch -n 60 'curl -s http://prometheus:9090/api/v1/query \
     --data-urlencode "query=ml_forecast_accuracy{metric=\"mape\"}" | jq'
   ```

## Prevention

### Monitoring
1. **Set up drift detection**: Automatic daily checks
2. **Configure alerts**: Early warning for accuracy drops
3. **Dashboard reviews**: Daily review of forecast dashboard

### Process
1. **Regular retraining**: Weekly/monthly schedule
2. **Data validation**: Automated data quality checks
3. **Model evaluation**: Continuous holdout set evaluation
4. **Feature monitoring**: Track feature distributions

### Documentation
1. **Maintain model cards**: Document model behavior
2. **Track experiments**: Use MLflow for all experiments
3. **Document incidents**: Learn from past degradations

## Escalation
- **If MAPE > 20%**: Escalate to ML Engineering Lead
- **If affecting trading P&L**: Alert Trading Team
- **If data pipeline broken**: Escalate to Data Engineering
- **If unresolved after 24h**: Schedule incident review

## Related Dashboards
- [Forecast Performance](http://grafana:3000/d/forecast-performance)
- [ML Service Overview](http://grafana:3000/d/ml-service-overview)
- [Anomaly Detection](http://grafana:3000/d/anomaly-detection)

## Related Runbooks
- ML-001: High Latency Troubleshooting
- ML-003: Feature Pipeline Failure
- ML-004: Trading Agent Incident

## Post-Incident Actions
1. **Root cause analysis**: Identify why performance degraded
2. **Update monitoring**: Add checks to catch earlier
3. **Improve pipeline**: Fix data quality issues
4. **Retrain schedule**: Adjust if needed
5. **Document learnings**: Update runbook and wiki

## Metadata
- **Created**: 2024-12-03
- **Last Updated**: 2024-12-03
- **Owner**: ML Engineering Team
- **Reviewers**: Data Science, SRE Team
