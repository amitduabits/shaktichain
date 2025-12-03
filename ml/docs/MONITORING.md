# SHAKTI-CHAIN ML Production Monitoring

Complete monitoring stack for SHAKTI-CHAIN ML services including metrics collection, alerting, dashboards, and runbooks.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Metrics](#metrics)
5. [Dashboards](#dashboards)
6. [Alerts](#alerts)
7. [Runbooks](#runbooks)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

## Overview

The monitoring stack provides comprehensive observability for:
- **ML Service Performance**: Latency, throughput, errors
- **Model Performance**: Prediction quality, inference time, drift
- **Feature Quality**: Freshness, drift, data quality
- **Business Metrics**: Trading P&L, forecast accuracy, anomalies
- **Infrastructure**: Resource usage, dependencies health

### Components

- **Prometheus**: Metrics collection and alerting
- **AlertManager**: Alert routing and notification
- **Grafana**: Visualization and dashboards
- **MLflow**: Model registry and experiment tracking

### Access Points

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Grafana | http://localhost:3000 | admin / shakti123 |
| Prometheus | http://localhost:9090 | - |
| AlertManager | http://localhost:9093 | - |
| MLflow | http://localhost:5000 | - |
| ML Service | http://localhost:8000 | - |
| Metrics Endpoint | http://localhost:8000/metrics | - |

## Architecture

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  ML Service  │────→│  Prometheus   │────→│  Grafana     │
│   (FastAPI)  │     │  (Metrics)    │     │ (Dashboards) │
└──────────────┘     └───────────────┘     └──────────────┘
       │                     │
       │                     ↓
       │              ┌──────────────┐
       │              │ AlertManager │
       │              └──────────────┘
       │                     │
       ↓                     ↓
┌──────────────┐     ┌──────────────┐
│    Redis     │     │ Notifications│
│   (Cache)    │     │ PD/Slack/Mail│
└──────────────┘     └──────────────┘
```

## Quick Start

### 1. Start Monitoring Stack

```bash
cd shaktichain/ml/ml-service

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Check logs
docker-compose logs -f ml-service prometheus grafana alertmanager
```

### 2. Configure Alert Channels

Create `.env` file with notification settings:

```bash
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# PagerDuty
PAGERDUTY_ROUTING_KEY=your-pagerduty-integration-key
PAGERDUTY_TRADING_KEY=your-trading-team-key

# Email
EMAIL_RECIPIENTS=ml-team@shaktichain.io,ops@shaktichain.io
SMTP_SMARTHOST=smtp.gmail.com:587
SMTP_USERNAME=alerts@shaktichain.io
SMTP_PASSWORD=your-app-password
```

Restart AlertManager:
```bash
docker-compose restart alertmanager
```

### 3. Access Grafana Dashboards

1. Open http://localhost:3000
2. Login: `admin` / `shakti123`
3. Navigate to Dashboards → Browse
4. Available dashboards:
   - **ML Service Overview**: Overall service health
   - **Forecast Performance**: Prediction accuracy
   - **Trading Performance**: Trading metrics and P&L
   - **Anomaly Detection**: Anomaly rates and scores

### 4. Test Alerts

```bash
# Trigger a test alert
curl -X POST http://localhost:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning",
      "component": "test"
    },
    "annotations": {
      "summary": "Test alert from monitoring setup"
    }
  }]'

# Check alert in Prometheus
curl http://localhost:9090/api/v1/alerts | jq

# Check AlertManager
curl http://localhost:9093/api/v2/alerts | jq
```

## Metrics

### 1. Request Metrics

Track API performance and usage:

```promql
# Request rate by endpoint
rate(ml_request_total[5m])

# Error rate
rate(ml_request_total{status=~"5.."}[5m]) / rate(ml_request_total[5m])

# P99 latency
histogram_quantile(0.99, rate(ml_request_latency_seconds_bucket[5m]))

# Requests in progress
ml_requests_in_progress
```

### 2. Model Metrics

Monitor model performance and health:

```promql
# Inference latency by model
ml_inference_latency_seconds{model="tft"}

# Prediction distribution
ml_prediction_value{model="tft"}

# Model version
ml_model_info{model="tft"}

# Model last updated
ml_model_last_updated_timestamp{model="tft"}

# Cache hit rate
rate(ml_cache_hits_total[5m]) /
  (rate(ml_cache_hits_total[5m]) + rate(ml_cache_misses_total[5m]))

# Prediction errors
rate(ml_prediction_errors_total[5m])
```

### 3. Feature Metrics

Track data quality and freshness:

```promql
# Feature staleness
ml_feature_staleness_seconds

# Feature drift
ml_feature_drift_score{drift_type="ks"}

# Feature statistics
ml_feature_value{stat="mean"}

# Missing values
ml_feature_missing_rate

# Out of bounds
rate(ml_feature_out_of_bounds_total[5m])
```

### 4. Business Metrics

Monitor business outcomes:

```promql
# Trading P&L
ml_pnl_current{period="daily"}

# Trading profit/loss
increase(ml_trading_profit_total[24h]) - increase(ml_trading_loss_total[24h])

# Trading volume
rate(ml_trade_volume_kwh_total[1h])

# Forecast accuracy (MAPE)
ml_forecast_accuracy{metric="mape"}

# Forecast error distribution
histogram_quantile(0.95, rate(ml_forecast_error_bucket[1h]))

# Anomaly rate
rate(ml_anomaly_alerts_total[15m])

# Battery SOC
ml_battery_soc
```

## Dashboards

### Dashboard 1: ML Service Overview

**Purpose**: Overall service health and performance
**URL**: http://localhost:3000/d/ml-service-overview
**Key Panels**:
- Request rate and latency
- Error rate
- Active models and versions
- Resource utilization (CPU, memory)
- Cache performance

**Use Cases**:
- Daily health check
- Incident investigation
- Capacity planning

### Dashboard 2: Forecast Performance

**Purpose**: Monitor prediction accuracy
**URL**: http://localhost:3000/d/forecast-performance
**Key Panels**:
- Real-time MAPE by horizon
- Prediction vs actual overlay
- Feature importance trending
- Drift detection scores
- Forecast error distribution

**Use Cases**:
- Model performance review
- Drift detection
- Retraining decision

### Dashboard 3: Trading Performance

**Purpose**: Track trading operations
**URL**: http://localhost:3000/d/trading-performance
**Key Panels**:
- Daily P&L
- Trade volume and frequency
- Action distribution (buy/sell/hold)
- Battery SOC distribution
- Win rate and Sharpe ratio

**Use Cases**:
- Daily P&L review
- Strategy evaluation
- Risk management

### Dashboard 4: Anomaly Detection

**Purpose**: Monitor anomaly detection system
**URL**: http://localhost:3000/d/anomaly-detection
**Key Panels**:
- Anomaly score distribution
- Alert rate over time
- Anomaly types breakdown
- Severity distribution
- False positive tracking

**Use Cases**:
- Security monitoring
- System health
- Investigation queue

## Alerts

### Alert Severity Levels

| Severity | Description | Response Time | Channel |
|----------|-------------|---------------|---------|
| **Critical** | Service down, data loss, revenue impact | < 15 minutes | PagerDuty + Slack |
| **Warning** | Degraded performance, potential issues | < 1 hour | Slack |
| **Info** | Informational, no action required | Next business day | Email |

### Critical Alerts (PagerDuty)

#### MLServiceHighErrorRate
- **Condition**: Error rate > 5% for 5 minutes
- **Impact**: Users experiencing failures
- **Runbook**: [ML-001](./runbooks/ML-001-high-latency.md)

#### MLServiceHighLatency
- **Condition**: P99 latency > 2s for 10 minutes
- **Impact**: Slow predictions
- **Runbook**: [ML-001](./runbooks/ML-001-high-latency.md)

#### MLModelServingFailed
- **Condition**: Model errors > 10/sec for 5 minutes
- **Impact**: Predictions failing
- **Runbook**: [ML-002](./runbooks/ML-002-model-performance-degradation.md)

#### TradingAgentOffline
- **Condition**: No updates for 10 minutes
- **Impact**: Trading stopped
- **Runbook**: [ML-004](./runbooks/ML-004-trading-agent-incident.md)

#### MLServiceDown
- **Condition**: Service not responding
- **Impact**: Complete outage
- **Runbook**: [ML-003](./runbooks/ML-003-feature-pipeline-failure.md)

### Warning Alerts (Slack)

#### ForecastAccuracyDegraded
- **Condition**: MAPE > 15% for 1 hour
- **Impact**: Poor predictions
- **Runbook**: [ML-002](./runbooks/ML-002-model-performance-degradation.md)

#### FeatureDataStale
- **Condition**: Feature staleness > 10 minutes
- **Impact**: Predictions using old data
- **Runbook**: [ML-003](./runbooks/ML-003-feature-pipeline-failure.md)

#### FeatureDriftDetected
- **Condition**: Drift score > 0.5 for 30 minutes
- **Impact**: Model may be outdated
- **Runbook**: [ML-002](./runbooks/ML-002-model-performance-degradation.md)

#### AnomalyRateSpike
- **Condition**: Anomaly rate > 2x normal
- **Impact**: Potential system issues
- **Runbook**: [ML-002](./runbooks/ML-002-model-performance-degradation.md)

### Info Alerts (Email)

- Model retraining completed
- Daily performance summary
- Weekly model report

## Runbooks

Detailed troubleshooting guides for common incidents:

### [ML-001: High Latency Troubleshooting](./runbooks/ML-001-high-latency.md)
**When**: P99 latency exceeds SLO
**Actions**:
1. Check service health
2. Identify slow endpoints
3. Analyze resource usage
4. Scale if needed

### [ML-002: Model Performance Degradation](./runbooks/ML-002-model-performance-degradation.md)
**When**: Forecast accuracy drops
**Actions**:
1. Check feature drift
2. Validate data quality
3. Analyze residuals
4. Consider retraining

### [ML-003: Feature Pipeline Failure](./runbooks/ML-003-feature-pipeline-failure.md)
**When**: Features not updating
**Actions**:
1. Check pipeline status
2. Verify data sources
3. Restart pipeline
4. Backfill data if needed

### [ML-004: Trading Agent Incident](./runbooks/ML-004-trading-agent-incident.md)
**When**: Trading agent offline or underperforming
**Actions**:
1. Check agent health
2. Review recent trades
3. Pause trading if needed
4. Switch to safe mode

## Configuration

### Prometheus Configuration

Location: `ml-service/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ml-service'
    static_configs:
      - targets: ['ml-service:8000']
    metrics_path: /metrics
    scrape_interval: 10s
```

### AlertManager Configuration

Location: `ml-service/alertmanager/alertmanager.yml`

Key settings:
- **Routing**: Critical → PagerDuty, Warning → Slack, Info → Email
- **Grouping**: By alertname, component, severity
- **Inhibition**: Suppress warnings when critical firing

### Grafana Provisioning

Dashboards auto-loaded from:
- `monitoring/grafana/dashboards/*.json`

Data sources configured in:
- `ml-service/grafana/provisioning/datasources/datasources.yml`

### Alert Rules

Location: `ml-service/prometheus/alerts/ml_service_alerts.yml`

To add new alert:
1. Add rule to appropriate group (critical/warning/info)
2. Define condition, duration, labels, annotations
3. Reload Prometheus: `curl -X POST http://localhost:9090/-/reload`

## Troubleshooting

### Metrics Not Showing

```bash
# Check if ML service exposing metrics
curl http://localhost:8000/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# Check Prometheus logs
docker logs shakti-prometheus --tail 100

# Verify service labels
curl http://localhost:8000/metrics | grep ml_service_info
```

### Alerts Not Firing

```bash
# Check alert rules loaded
curl http://localhost:9090/api/v1/rules | jq

# Check alert state
curl http://localhost:9090/api/v1/alerts | jq

# Check AlertManager config
docker exec shakti-alertmanager amtool config show

# Test alert routing
docker exec shakti-alertmanager amtool config routes test \
  --config.file=/etc/alertmanager/alertmanager.yml \
  alertname=TestAlert severity=critical
```

### Dashboard Not Loading

```bash
# Check Grafana logs
docker logs shakti-grafana --tail 100

# Verify datasource connection
curl -u admin:shakti123 http://localhost:3000/api/datasources

# Test Prometheus from Grafana
curl -u admin:shakti123 \
  http://localhost:3000/api/datasources/proxy/1/api/v1/query \
  --data-urlencode 'query=up'

# Reimport dashboard
curl -u admin:shakti123 \
  -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana/dashboards/ml-service-overview.json
```

### Notifications Not Sending

```bash
# Check AlertManager status
curl http://localhost:9093/api/v2/status | jq

# Check notification queue
curl http://localhost:9093/api/v2/alerts | jq

# Test Slack webhook
curl -X POST $SLACK_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"text": "Test notification from SHAKTI-CHAIN"}'

# Check AlertManager logs
docker logs shakti-alertmanager --tail 100 | grep -i slack

# Validate AlertManager config
docker exec shakti-alertmanager amtool check-config \
  /etc/alertmanager/alertmanager.yml
```

### High Cardinality Issues

If Prometheus using too much memory:

```bash
# Check series count
curl http://localhost:9090/api/v1/status/tsdb | jq '.data.seriesCountByMetricName'

# Identify high cardinality metrics
curl http://localhost:9090/api/v1/status/tsdb | jq '.data.seriesCountByMetricName | sort_by(.value) | reverse | .[0:10]'

# Add metric relabeling in prometheus.yml to drop labels
# Or increase retention time and resources
```

## Best Practices

### 1. Monitoring Strategy
- **RED Method**: Rate, Errors, Duration for all APIs
- **USE Method**: Utilization, Saturation, Errors for resources
- **Business Metrics**: Track what matters to users

### 2. Alert Design
- **Clear actionable alerts**: Every alert should have clear next steps
- **Appropriate severity**: Don't over-alert or under-alert
- **Runbook links**: Include runbook in alert annotations
- **Context in alerts**: Provide enough info to triage

### 3. Dashboard Design
- **Focus on SLOs**: Highlight what affects users
- **Time windows**: Show appropriate time ranges
- **Drill-down**: Link related dashboards
- **Annotations**: Mark deployments and incidents

### 4. Incident Response
- **Acknowledge quickly**: Let team know you're on it
- **Follow runbook**: Don't improvise unless necessary
- **Document**: Log what you tried and what worked
- **Post-mortem**: Learn and improve

### 5. Continuous Improvement
- **Review alerts weekly**: Tune thresholds, reduce noise
- **Update runbooks**: Add learnings from incidents
- **Test regularly**: Ensure monitoring catches issues
- **Capacity planning**: Proactively scale before issues

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [AlertManager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)

## Support

For monitoring issues:
- **Slack**: #ml-monitoring
- **Email**: sre-team@shaktichain.io
- **On-call**: PagerDuty escalation

## Changelog

### 2024-12-03
- Initial monitoring stack setup
- Added comprehensive alert rules
- Created 4 Grafana dashboards
- Documented 4 runbooks
- Configured AlertManager with multi-channel routing
