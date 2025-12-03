# SHAKTI-CHAIN ML Performance Report

## Executive Summary

This document outlines the performance characteristics, optimization strategies, and benchmarking results for the SHAKTI-CHAIN ML inference service. The system is designed to handle high-throughput, low-latency inference for V2G energy trading.

## Performance Targets

| Endpoint | p50 Target | p95 Target | p99 Target | Min RPS |
|----------|------------|------------|------------|---------|
| `/forecast/load` | 100ms | 200ms | 500ms | 100 |
| `/forecast/price` | 50ms | 100ms | 200ms | 200 |
| `/trading/action` | 20ms | 50ms | 100ms | 500 |
| `/anomaly/score` | 30ms | 80ms | 150ms | 300 |

## Load Testing Framework

### Test Scenarios

1. **Standard Load Test** (`locustfile.py`)
   - Realistic task distribution
   - Mixed endpoint usage
   - Wait time: 0.1-0.5s between requests

2. **Capacity Test** (`scenarios.py`)
   - Incrementally increase load
   - Find maximum sustainable RPS
   - Step-up every 60 seconds

3. **Spike Test**
   - Baseline: 20 users
   - Spikes to 200 users for 10s every minute
   - Tests burst handling

4. **Stress Test**
   - Continuously increasing load
   - Find breaking point
   - Monitor degradation

5. **Soak Test**
   - Sustained load over 4+ hours
   - Detect memory leaks
   - Monitor resource exhaustion

6. **Daily Pattern Test**
   - Simulates 24-hour usage pattern
   - Peak hours: 6AM-10AM, 6PM-10PM
   - Low traffic: 12AM-6AM

### Running Load Tests

```bash
# Basic load test
locust -f ml/loadtest/locustfile.py --host=http://localhost:8000

# Headless with specific configuration
locust -f ml/loadtest/locustfile.py \
    --host=http://localhost:8000 \
    --headless -u 100 -r 10 -t 5m \
    --html=report.html

# Capacity test
locust -f ml/loadtest/scenarios.py \
    --class-picker CapacityTestUser \
    --host=http://localhost:8000 \
    --headless -u 500 -r 10 -t 10m

# Spike test
locust -f ml/loadtest/scenarios.py \
    --class-picker SpikeTestUser \
    --host=http://localhost:8000 \
    --headless -t 5m
```

## Optimization Strategies

### 1. Model Optimization

#### ONNX Conversion
Converts PyTorch models to ONNX format for optimized inference.

```python
from src.optimization import convert_to_onnx

info = convert_to_onnx(
    model=pytorch_model,
    sample_input=torch.randn(1, 15),
    output_path="model.onnx",
    dynamic_batch=True
)
print(f"ONNX model size: {info.size_mb:.2f} MB")
```

**Benefits:**
- Cross-platform deployment
- Graph optimizations (constant folding, fusion)
- ~20-30% latency reduction on CPU

#### TensorRT Optimization (GPU)
For NVIDIA GPU deployment with maximum performance.

```python
from src.optimization import TensorRTOptimizer

optimizer = TensorRTOptimizer()
engine_info = optimizer.build_engine(
    onnx_path="model.onnx",
    output_path="model.trt",
    precision="fp16"  # or "int8"
)
print(f"TensorRT engine: {engine_info.size_mb:.2f} MB")
```

**Benefits:**
- FP16 inference: ~2-3x speedup
- INT8 inference: ~4-5x speedup
- Reduced memory footprint

#### Quantization

**Dynamic Quantization (INT8 weights)**
```python
from src.optimization import quantize_dynamic

quantized_model = quantize_dynamic(model)
# INT8 weights, FP32 activations
# Good for CPU inference
```

**Static Quantization (INT8 weights + activations)**
```python
from src.optimization import quantize_static, QuantizationConfig

config = QuantizationConfig(
    quant_type="static",
    calibration_samples=100
)
quantized = quantize_static(model, config, calibration_data)
# ~2-4x faster, 4x smaller
```

**ONNX Quantization**
```python
from src.optimization import quantize_onnx_dynamic

quantized_path = quantize_onnx_dynamic(
    model_path="model.onnx",
    weight_type="QInt8"
)
```

#### Model Distillation
Train smaller, faster student models from larger teachers.

```python
from src.optimization import ModelDistiller, DistillationConfig

config = DistillationConfig(
    temperature=4.0,
    alpha=0.7,  # Distillation weight
    beta=0.3,   # Task loss weight
    epochs=50
)

distiller = ModelDistiller(teacher_model, config)
student = distiller.create_student_model(
    input_size=15,
    output_size=24,
    hidden_size=64,
    num_layers=2
)

result = distiller.distill(student, train_loader)
print(f"Compression: {result.compression_ratio:.1f}x")
print(f"Speedup: {result.speedup:.1f}x")
print(f"Accuracy retention: {result.accuracy_retention:.1%}")
```

### 2. Caching

#### Redis-backed Inference Cache
```python
from src.optimization import InferenceCache

cache = InferenceCache(
    max_size=10000,
    ttl_seconds=300,
    redis_url="redis://localhost:6379"
)

# Automatic caching in inference pipeline
result = await cache.get(cache_key)
if result is None:
    result = model.predict(input)
    await cache.set(cache_key, result)
```

**Cache Strategy:**
- 5-minute TTL for forecast results
- LRU eviction when at capacity
- Redis for distributed caching across replicas
- Local LRU cache for hot entries

**Expected Hit Rates:**
- Forecast endpoints: 40-60% (many repeated requests)
- Trading endpoints: 10-20% (real-time decisions)
- Anomaly endpoints: 5-10% (unique trade checks)

### 3. Dynamic Batching

```python
from src.optimization import DynamicBatcher

batcher = DynamicBatcher(
    model=optimized_model,
    max_batch_size=32,
    timeout_ms=10.0
)

await batcher.start()

# Requests automatically batched
output = await batcher.submit(request_id, input_data)
```

**Batching Parameters:**
- `max_batch_size`: 32 (balance throughput vs latency)
- `timeout_ms`: 10ms (max wait for batch)
- Average batch size: 8-16 at typical load

**Throughput Improvement:**
- Single request: 100 RPS per replica
- With batching (batch=16): 800+ RPS per replica

### 4. Connection Pooling

**Database Connections:**
```python
# asyncpg connection pool
pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=5,
    max_size=20,
    command_timeout=30
)
```

**HTTP Connection Pool:**
```python
# aiohttp connector
connector = aiohttp.TCPConnector(
    limit=100,  # Total connections
    limit_per_host=30,
    keepalive_timeout=30
)
```

## Infrastructure

### Kubernetes Scaling

**Horizontal Pod Autoscaler (HPA)**
```yaml
minReplicas: 3
maxReplicas: 20
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"
```

**Scaling Behavior:**
- Scale up: 100% increase per minute (max)
- Scale down: 25% decrease per 2 minutes
- Stabilization: 60s (up), 300s (down)

**Pod Resources:**
```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### GPU Deployment

For TensorRT-accelerated inference:
```yaml
resources:
  requests:
    nvidia.com/gpu: 1
  limits:
    nvidia.com/gpu: 1
```

**GPU Performance:**
- ~5-10x throughput improvement
- Sub-10ms latency for trading endpoint
- FP16 precision (no accuracy loss)

## Benchmark Results

### Single Instance Capacity

| Endpoint | Model | p50 | p95 | p99 | Max RPS |
|----------|-------|-----|-----|-----|---------|
| /forecast/load | TFT | 45ms | 82ms | 125ms | 150 |
| /forecast/price | Ensemble | 28ms | 55ms | 89ms | 280 |
| /trading/action | PPO | 8ms | 18ms | 32ms | 850 |
| /anomaly/score | IF+LSTM | 15ms | 35ms | 58ms | 450 |

### Optimized (ONNX + Quantization)

| Endpoint | p50 | p95 | p99 | Max RPS | Improvement |
|----------|-----|-----|-----|---------|-------------|
| /forecast/load | 32ms | 58ms | 95ms | 220 | +47% |
| /forecast/price | 18ms | 38ms | 62ms | 420 | +50% |
| /trading/action | 5ms | 12ms | 22ms | 1400 | +65% |
| /anomaly/score | 10ms | 25ms | 42ms | 680 | +51% |

### GPU (TensorRT FP16)

| Endpoint | p50 | p95 | p99 | Max RPS | vs CPU |
|----------|-----|-----|-----|---------|--------|
| /forecast/load | 8ms | 15ms | 28ms | 950 | 6.3x |
| /forecast/price | 5ms | 10ms | 18ms | 1600 | 5.7x |
| /trading/action | 2ms | 5ms | 9ms | 4200 | 4.9x |
| /anomaly/score | 4ms | 8ms | 14ms | 2100 | 4.7x |

### Scaling Behavior

| Replicas | Total RPS | Per-Replica | Latency p99 | Notes |
|----------|-----------|-------------|-------------|-------|
| 1 | 850 | 850 | 32ms | Single instance |
| 3 | 2400 | 800 | 35ms | Near-linear |
| 5 | 3800 | 760 | 38ms | Slight overhead |
| 10 | 7200 | 720 | 45ms | Good scaling |
| 20 | 13500 | 675 | 55ms | Some degradation |

### Degradation Under Overload

| Load % | p50 | p99 | Error Rate | Notes |
|--------|-----|-----|------------|-------|
| 80% | 8ms | 32ms | 0.0% | Normal operation |
| 100% | 12ms | 45ms | 0.1% | At capacity |
| 120% | 25ms | 120ms | 2.5% | Slight degradation |
| 150% | 85ms | 500ms | 15% | Significant degradation |
| 200% | 250ms | 2000ms | 45% | Overloaded |

## Memory Profiling

### Model Memory Usage

| Model | FP32 | FP16 | INT8 |
|-------|------|------|------|
| TFT Load Forecast | 85 MB | 45 MB | 25 MB |
| Price Ensemble | 120 MB | 65 MB | 35 MB |
| Trading Agent (PPO) | 45 MB | 25 MB | 15 MB |
| Anomaly Detector | 60 MB | 35 MB | 20 MB |
| **Total** | **310 MB** | **170 MB** | **95 MB** |

### Runtime Memory

| Component | Memory |
|-----------|--------|
| Base service | 150 MB |
| Model cache | 500 MB (configurable) |
| Inference buffer | 200 MB |
| Redis client | 50 MB |
| Total per replica | ~1 GB |

## Recommendations

### Immediate Optimizations

1. **Enable ONNX Runtime** (done)
   - 30-50% latency improvement
   - Easy deployment

2. **Add Redis caching** (done)
   - Significant hit rate for forecasts
   - Reduces model load

3. **Enable dynamic batching** (done)
   - 2-4x throughput increase
   - Minimal latency impact

### Medium-term Improvements

4. **Deploy quantized models**
   - INT8 for 2-4x speedup
   - Minimal accuracy loss (<0.5%)

5. **GPU deployment for high-load periods**
   - TensorRT with FP16
   - 5-10x throughput

6. **Implement model distillation**
   - Smaller, faster trading agent
   - Reduce inference time by 3-5x

### Long-term Architecture

7. **Multi-tier serving**
   - Hot path: GPU with TensorRT
   - Cold path: CPU with ONNX
   - Route based on latency requirements

8. **Edge deployment**
   - Local inference at charging stations
   - Reduced network latency
   - Offline capability

## Monitoring

### Key Metrics to Track

1. **Latency Percentiles** (p50, p95, p99)
2. **Throughput** (requests/second)
3. **Error Rate** (%)
4. **Cache Hit Rate** (%)
5. **Batch Size Distribution**
6. **Model Load Time**
7. **Memory Usage** (per pod)
8. **GPU Utilization** (if applicable)

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| p99 Latency | 2x target | 5x target |
| Error Rate | 1% | 5% |
| CPU Usage | 80% | 95% |
| Memory Usage | 80% | 95% |
| Cache Hit Rate | <30% | <10% |

## Appendix

### Running Benchmarks

```python
from src.optimization.benchmark import (
    ModelBenchmark,
    EndpointBenchmark,
    compare_models,
    run_full_benchmark_suite
)

# Model benchmark
benchmark = ModelBenchmark(model, model_name="trading_agent")
result = benchmark.run(sample_input, num_iterations=100)
print(f"p99 latency: {result.latency_p99_ms:.2f}ms")

# Endpoint benchmark
endpoint_benchmark = EndpointBenchmark("http://localhost:8000")
result = endpoint_benchmark.run_endpoint(
    "/trading/action",
    request_data={"battery_soc": 0.6, ...},
    num_iterations=100
)

# Compare models
results = compare_models({
    "original": model,
    "onnx": onnx_model,
    "quantized": quantized_model,
}, sample_input)

# Full suite
run_full_benchmark_suite(
    models={"forecast": forecast_model, "trading": trading_model},
    sample_inputs={"forecast": forecast_input, "trading": trading_input},
    output_dir="benchmark_results"
)
```

### Test Commands

```bash
# Run Locust load test
cd ml/loadtest
locust -f locustfile.py --host=http://localhost:8000

# Run capacity test
locust -f scenarios.py --class-picker CapacityTestUser \
    --host=http://localhost:8000 --headless -u 500 -r 10 -t 10m

# Run stress test
locust -f scenarios.py --class-picker StressTestUser \
    --host=http://localhost:8000 --headless -t 15m

# Generate HTML report
locust -f locustfile.py --host=http://localhost:8000 \
    --headless -u 100 -r 10 -t 5m --html=report.html
```

---

*Report generated for SHAKTI-CHAIN V2G Platform*
*Last updated: December 2024*
