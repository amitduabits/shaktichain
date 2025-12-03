# ML-003: Feature Pipeline Failure

## Overview
**Alert**: FeatureDataStale
**Severity**: Warning → Critical (if prolonged)
**Component**: Feature Pipeline, Data Ingestion
**SLO Impact**: Yes - features required for predictions

## Symptoms
- Features not updating (staleness > 10 minutes)
- Missing feature values
- Feature pipeline errors in logs
- ML predictions using stale data
- Health check failures

## Investigation Steps

### 1. Check Feature Staleness
```bash
# Check all stale features
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_staleness_seconds > 600' | jq

# Get staleness values
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_staleness_seconds' | jq

# Check feature update timestamps
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_last_updated_timestamp' | jq
```

### 2. Check Pipeline Status
```bash
# Check if feature pipeline is running
docker ps | grep feature-pipeline

# Check pipeline logs
docker logs shakti-feature-pipeline --tail 100

# Check for errors
docker logs shakti-feature-pipeline --tail 500 | grep -i error

# Check pipeline health
curl http://feature-pipeline:8080/health
```

### 3. Check Data Sources
```bash
# Check data collector status
cd /app/shaktichain/ml
python scripts/check_data_sources.py

# Test IEX connectivity
curl "https://api.iexcloud.io/stable/data-points/market/SYMBOL?token=YOUR_TOKEN"

# Test POSOCO connectivity
curl "https://posoco.in/api/v1/data"

# Test weather API
curl "https://api.openweathermap.org/data/2.5/weather?q=Delhi&appid=YOUR_KEY"
```

### 4. Check Dependencies
```bash
# Check Redis (feature store)
docker exec shakti-redis redis-cli ping
docker exec shakti-redis redis-cli info stats

# Check if features exist in Redis
docker exec shakti-redis redis-cli KEYS "feature:*"

# Check PostgreSQL (if used)
docker exec shakti-postgres psql -U shakti -c "SELECT COUNT(*) FROM features;"
```

### 5. Check Resource Usage
```bash
# Check pipeline container resources
docker stats shakti-feature-pipeline --no-stream

# Check disk space
docker exec shakti-feature-pipeline df -h

# Check memory
docker exec shakti-feature-pipeline free -h
```

### 6. Review Recent Changes
```bash
# Check for recent deployments
git log --oneline --since="24 hours ago" src/features/

# Check environment variables
docker exec shakti-feature-pipeline env | grep FEATURE

# Check configuration
docker exec shakti-feature-pipeline cat /app/config/feature_pipeline.yaml
```

## Common Causes & Solutions

### Cause 1: Data Source Unavailable
**Symptoms**: No data collected, connection errors
**Solution**:
```bash
# Check connectivity to each source
cd /app/shaktichain/ml
python scripts/test_data_sources.py --verbose

# Check API credentials
docker exec shakti-feature-pipeline cat /app/.env | grep API_KEY

# Restart with debug logging
docker-compose restart feature-pipeline
docker logs -f shakti-feature-pipeline
```

### Cause 2: Pipeline Process Crashed
**Symptoms**: Container running but no updates
**Solution**:
```bash
# Check process status
docker exec shakti-feature-pipeline ps aux

# Restart pipeline
docker-compose restart feature-pipeline

# If restart doesn't work, rebuild
docker-compose build feature-pipeline
docker-compose up -d feature-pipeline
```

### Cause 3: Database/Redis Connection Lost
**Symptoms**: Connection timeouts, Redis errors
**Solution**:
```bash
# Check Redis connectivity from pipeline
docker exec shakti-feature-pipeline nc -zv redis 6379

# Restart Redis if needed
docker-compose restart redis

# Check Redis logs
docker logs shakti-redis --tail 100

# Verify Redis persistence
docker exec shakti-redis redis-cli CONFIG GET save
```

### Cause 4: Rate Limiting
**Symptoms**: 429 errors, API quota exceeded
**Solution**:
```bash
# Check API usage
docker logs shakti-feature-pipeline | grep "429\|rate limit"

# Increase polling interval temporarily
# Edit configs/feature_pipeline.yaml:
#   collection_interval: 300  # Increase from 60 to 300 seconds

docker-compose restart feature-pipeline

# Use alternative data source if available
# Edit configs/feature_pipeline.yaml:
#   data_sources:
#     primary: backup_source
```

### Cause 5: Data Schema Change
**Symptoms**: Parsing errors, validation failures
**Solution**:
```bash
# Check validation errors
docker logs shakti-feature-pipeline | grep "validation\|schema"

# Inspect raw data
cd /app/shaktichain/ml
python scripts/inspect_raw_data.py --source iex --limit 10

# Update data parsers
# Edit src/data/collectors/iex.py to match new schema

# Rebuild and restart
docker-compose build feature-pipeline
docker-compose up -d feature-pipeline
```

### Cause 6: Resource Exhaustion
**Symptoms**: OOM errors, high CPU, slow processing
**Solution**:
```bash
# Check container limits
docker inspect shakti-feature-pipeline | jq '.[0].HostConfig'

# Increase resources
# Edit docker-compose.yml:
#   feature-pipeline:
#     deploy:
#       resources:
#         limits:
#           memory: 4G
#           cpus: '2'

docker-compose up -d feature-pipeline
```

## Resolution Steps

### Immediate Mitigation
1. **Use cached features**: If recent cache available
   ```bash
   # Check cache age
   docker exec shakti-redis redis-cli TTL feature:cache:latest

   # Extend cache TTL temporarily
   docker exec shakti-redis redis-cli EXPIRE feature:cache:latest 3600
   ```

2. **Use backup data source**: Switch to alternative source
   ```bash
   # Switch to synthetic data temporarily
   curl -X POST http://feature-pipeline:8080/config \
     -H "Content-Type: application/json" \
     -d '{"data_source": "synthetic"}'
   ```

3. **Manual feature refresh**: Trigger manual collection
   ```bash
   # Trigger refresh
   curl -X POST http://feature-pipeline:8080/refresh \
     -H "Content-Type: application/json" \
     -d '{"features": ["all"], "force": true}'
   ```

### Fix Pipeline
1. **Identify root cause**: Use investigation steps
2. **Fix issue**: Apply appropriate solution
3. **Restart pipeline**: Clean restart
   ```bash
   docker-compose stop feature-pipeline
   docker-compose rm -f feature-pipeline
   docker-compose up -d feature-pipeline
   ```

### Backfill Data
1. **Determine gap**: Calculate missing data period
   ```bash
   # Check last successful update
   curl -s http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=ml_feature_last_updated_timestamp' | jq
   ```

2. **Backfill missing data**:
   ```bash
   cd /app/shaktichain/ml
   python scripts/backfill_features.py \
     --start "2024-12-03T10:00:00" \
     --end "2024-12-03T12:00:00" \
     --features all
   ```

3. **Verify backfill**:
   ```bash
   # Check feature staleness
   curl -s http://prometheus:9090/api/v1/query \
     --data-urlencode 'query=ml_feature_staleness_seconds' | jq
   ```

## Verification
```bash
# Check pipeline is healthy
curl http://feature-pipeline:8080/health

# Check features are updating
watch -n 10 'docker exec shakti-redis redis-cli GET feature:load:delhi:latest'

# Verify staleness decreasing
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_feature_staleness_seconds' | jq

# Check alert resolved
curl -s http://prometheus:9090/api/v1/alerts | \
  jq '.data.alerts[] | select(.labels.alertname=="FeatureDataStale")'
```

## Prevention

### Monitoring
1. **Feature freshness**: Alert on staleness
2. **Pipeline health**: Regular health checks
3. **Data source status**: Monitor API availability
4. **Resource usage**: Track memory and CPU

### Resilience
1. **Retry logic**: Implement exponential backoff
2. **Fallback sources**: Multiple data providers
3. **Circuit breakers**: Prevent cascade failures
4. **Graceful degradation**: Use cached data when fresh unavailable

### Maintenance
1. **Regular testing**: Weekly data source tests
2. **Schema validation**: Automated schema checks
3. **Dependency updates**: Keep libraries current
4. **Capacity planning**: Monitor growth trends

## Escalation
- **If unresolved after 30 minutes**: Escalate to Data Engineering
- **If multiple sources failing**: Escalate to Infrastructure Team
- **If affecting production predictions**: Alert ML Engineering Lead
- **If vendor API issue**: Contact vendor support

## Related Dashboards
- [ML Service Overview](http://grafana:3000/d/ml-service-overview)
- [Feature Pipeline Health](http://grafana:3000/d/feature-pipeline)
- [Data Sources Status](http://grafana:3000/d/data-sources)

## Related Runbooks
- ML-001: High Latency Troubleshooting
- ML-002: Model Performance Degradation
- INFRA-001: Redis Cache Issues
- DATA-001: Data Source Outage

## Post-Incident Actions
1. **Root cause analysis**: Why pipeline failed
2. **Improve resilience**: Add redundancy
3. **Update monitoring**: Catch earlier next time
4. **Test recovery**: Ensure backfill works
5. **Document**: Update runbook with learnings

## Metadata
- **Created**: 2024-12-03
- **Last Updated**: 2024-12-03
- **Owner**: Data Engineering Team
- **Reviewers**: ML Engineering, SRE Team
