# ML-001: High Latency Troubleshooting

## Overview
**Alert**: MLServiceHighLatency / MLServiceElevatedLatency
**Severity**: Critical (P99 > 2s) / Warning (P95 > 1s)
**Component**: ML Service
**SLO Impact**: Yes - affects user experience

## Symptoms
- P99 latency exceeds 2 seconds for 10+ minutes (Critical)
- P95 latency exceeds 1 second for 15+ minutes (Warning)
- Users experiencing slow predictions
- Increased timeout errors

## Investigation Steps

### 1. Check Current Latency
```bash
# Check current P99 latency by endpoint
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.99, rate(ml_request_latency_seconds_bucket[5m]))' | jq

# Check which endpoint is slow
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=topk(5, histogram_quantile(0.99, rate(ml_request_latency_seconds_bucket[5m])))' | jq
```

### 2. Check Service Health
```bash
# Check ML service health
curl http://ml-service:8000/health

# Check service logs
docker logs shakti-ml-service --tail 100

# Check for errors in last 5 minutes
docker logs shakti-ml-service --since 5m | grep -i error
```

### 3. Check Resource Utilization
```bash
# Check CPU and memory usage
docker stats shakti-ml-service --no-stream

# Check if container is hitting memory limits
docker inspect shakti-ml-service | jq '.[0].HostConfig.Memory'
```

### 4. Check Model Inference Time
```bash
# Check inference latency by model
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.99, rate(ml_inference_latency_seconds_bucket[5m])) by (model)' | jq
```

### 5. Check Cache Performance
```bash
# Check cache hit rate
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(ml_cache_hits_total[5m])/(rate(ml_cache_hits_total[5m])+rate(ml_cache_misses_total[5m]))' | jq

# Check Redis health
docker exec shakti-redis redis-cli ping
docker exec shakti-redis redis-cli info stats
```

### 6. Check Upstream Dependencies
```bash
# Check MLflow health
curl http://mlflow:5000/health

# Check Redis latency
docker exec shakti-redis redis-cli --latency
```

## Common Causes & Solutions

### Cause 1: Model Not Optimized
**Symptoms**: High inference latency for specific model
**Solution**:
```bash
# Check model backend and size
curl http://ml-service:8000/models | jq

# Consider model optimization
# - Quantization
# - ONNX conversion
# - TensorRT optimization
# See: /docs/optimization/README.md
```

### Cause 2: Cache Miss Rate High
**Symptoms**: Low cache hit rate (<80%)
**Solution**:
```bash
# Check cache configuration
docker exec shakti-redis redis-cli CONFIG GET maxmemory

# Increase cache size if needed
docker exec shakti-redis redis-cli CONFIG SET maxmemory 1gb

# Restart service to update cache strategy
docker-compose restart ml-service
```

### Cause 3: Resource Exhaustion
**Symptoms**: High CPU/memory usage
**Solution**:
```bash
# Increase container resources
# Edit docker-compose.yml:
#   deploy:
#     resources:
#       limits:
#         memory: 8G
#         cpus: '4'

docker-compose up -d ml-service
```

### Cause 4: Too Many Concurrent Requests
**Symptoms**: High request rate, many in-progress requests
**Solution**:
```bash
# Check current request rate
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(ml_request_total[1m])' | jq

# Check in-progress requests
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_requests_in_progress' | jq

# Scale up workers
# Edit docker-compose.yml:
#   environment:
#     - ML_SERVICE_WORKERS=8

docker-compose up -d ml-service
```

### Cause 5: Network Latency
**Symptoms**: All endpoints slow, external dependencies slow
**Solution**:
```bash
# Check network latency to Redis
docker exec shakti-ml-service ping -c 10 redis

# Check network latency to MLflow
docker exec shakti-ml-service ping -c 10 mlflow

# Check if running on same network
docker network inspect ml-network
```

## Resolution Steps

### Immediate Mitigation
1. **Scale horizontally**: Add more service replicas
   ```bash
   docker-compose up -d --scale ml-service=3
   ```

2. **Reduce traffic**: Enable rate limiting if available
   ```bash
   # Contact backend team to enable rate limiting
   ```

3. **Clear cache**: If cache is corrupted
   ```bash
   docker exec shakti-redis redis-cli FLUSHALL
   docker-compose restart ml-service
   ```

### Long-term Solutions
1. **Optimize models**: Use quantization, ONNX, TensorRT
2. **Implement batching**: Batch predictions for efficiency
3. **Add CDN/edge caching**: Cache predictions closer to users
4. **Horizontal scaling**: Use Kubernetes HPA
5. **Database indexing**: Optimize feature store queries

## Verification
```bash
# Wait 5 minutes, then check latency again
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=histogram_quantile(0.99, rate(ml_request_latency_seconds_bucket[5m]))' | jq

# Check alert status
curl -s http://prometheus:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="MLServiceHighLatency")'
```

## Escalation
- **If unresolved after 30 minutes**: Escalate to ML Engineering Lead
- **If affecting production trading**: Page on-call SRE
- **If related to infrastructure**: Escalate to Infrastructure team

## Related Dashboards
- [ML Service Overview](http://grafana:3000/d/ml-service-overview)
- [Forecast Performance](http://grafana:3000/d/forecast-performance)

## Related Runbooks
- ML-002: Model Performance Degradation
- ML-003: Feature Pipeline Failure
- INFRA-001: Redis Cache Issues

## Post-Incident Actions
1. Document root cause in incident report
2. Update this runbook if new patterns discovered
3. Create follow-up tasks for long-term solutions
4. Review and update SLOs if needed
5. Conduct blameless postmortem

## Metadata
- **Created**: 2024-12-03
- **Last Updated**: 2024-12-03
- **Owner**: ML Platform Team
- **Reviewers**: SRE Team, ML Engineering
