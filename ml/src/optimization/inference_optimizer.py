"""Unified inference optimization for SHAKTI-CHAIN ML models.

Provides:
- Automatic optimization pipeline
- Caching layer
- Dynamic batching
- Performance monitoring
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class OptimizationLevel(Enum):
    """Optimization levels."""
    NONE = 0
    BASIC = 1      # JIT compilation
    STANDARD = 2   # ONNX + quantization
    AGGRESSIVE = 3 # TensorRT + INT8


@dataclass
class OptimizationConfig:
    """Configuration for inference optimization."""

    level: OptimizationLevel = OptimizationLevel.STANDARD

    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    cache_max_size: int = 10000
    redis_url: Optional[str] = None

    # Batching
    enable_batching: bool = True
    max_batch_size: int = 32
    batch_timeout_ms: float = 10.0

    # ONNX
    use_onnx: bool = True
    onnx_opset: int = 14

    # Quantization
    use_quantization: bool = True
    quantization_type: str = "dynamic"  # "dynamic", "static", "fp16"

    # TensorRT
    use_tensorrt: bool = False
    tensorrt_precision: str = "fp16"

    # Monitoring
    enable_profiling: bool = True
    log_slow_requests_ms: float = 100.0


@dataclass
class OptimizedModel:
    """Container for optimized model with metadata."""

    model: Any
    optimization_level: OptimizationLevel
    original_size_mb: float
    optimized_size_mb: float
    compression_ratio: float
    avg_latency_ms: float
    backend: str  # "pytorch", "onnx", "tensorrt"
    dtype: str  # "fp32", "fp16", "int8"

    def __call__(self, *args, **kwargs):
        return self.model(*args, **kwargs)


class InferenceCache:
    """LRU cache with optional Redis backend."""

    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: int = 300,
        redis_url: Optional[str] = None,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.redis_url = redis_url
        self._local_cache: Dict[str, Tuple[Any, float]] = {}
        self._access_order: List[str] = []
        self._redis: Optional["aioredis.Redis"] = None
        self._hits = 0
        self._misses = 0

    async def connect(self):
        """Connect to Redis if configured."""
        if self.redis_url and REDIS_AVAILABLE:
            self._redis = await aioredis.from_url(self.redis_url)
            logger.info(f"Connected to Redis: {self.redis_url}")

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        # Check local cache first
        if key in self._local_cache:
            value, timestamp = self._local_cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                self._hits += 1
                self._update_access_order(key)
                return value
            else:
                del self._local_cache[key]

        # Check Redis
        if self._redis:
            try:
                data = await self._redis.get(f"inf:{key}")
                if data:
                    import pickle
                    value = pickle.loads(data)
                    self._local_cache[key] = (value, time.time())
                    self._hits += 1
                    return value
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        self._misses += 1
        return None

    async def set(self, key: str, value: Any):
        """Set cached value."""
        # Evict if needed
        while len(self._local_cache) >= self.max_size:
            self._evict_oldest()

        self._local_cache[key] = (value, time.time())
        self._access_order.append(key)

        # Store in Redis
        if self._redis:
            try:
                import pickle
                data = pickle.dumps(value)
                await self._redis.setex(f"inf:{key}", self.ttl_seconds, data)
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

    def _update_access_order(self, key: str):
        """Update LRU access order."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _evict_oldest(self):
        """Evict least recently used entry."""
        if self._access_order:
            oldest_key = self._access_order.pop(0)
            self._local_cache.pop(oldest_key, None)

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._local_cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "redis_connected": self._redis is not None,
        }


class DynamicBatcher:
    """Dynamic batching for inference requests.

    Collects requests and batches them for efficient inference.
    """

    def __init__(
        self,
        model: Callable,
        max_batch_size: int = 32,
        timeout_ms: float = 10.0,
    ):
        self.model = model
        self.max_batch_size = max_batch_size
        self.timeout_ms = timeout_ms
        self._queue: asyncio.Queue = asyncio.Queue()
        self._results: Dict[str, asyncio.Future] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._batch_count = 0
        self._total_requests = 0

    async def start(self):
        """Start the batcher."""
        self._running = True
        self._task = asyncio.create_task(self._batch_loop())
        logger.info("Dynamic batcher started")

    async def stop(self):
        """Stop the batcher."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def submit(self, request_id: str, inputs: np.ndarray) -> np.ndarray:
        """Submit a request for batched inference.

        Args:
            request_id: Unique request identifier
            inputs: Input array

        Returns:
            Model output
        """
        self._total_requests += 1
        future = asyncio.get_event_loop().create_future()
        self._results[request_id] = future

        await self._queue.put((request_id, inputs))

        return await future

    async def _batch_loop(self):
        """Main batching loop."""
        while self._running:
            try:
                batch = []
                request_ids = []

                # Collect requests up to max batch size or timeout
                deadline = time.time() + (self.timeout_ms / 1000)

                while len(batch) < self.max_batch_size:
                    timeout = max(0, deadline - time.time())
                    try:
                        request_id, inputs = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=timeout if batch else None
                        )
                        batch.append(inputs)
                        request_ids.append(request_id)
                    except asyncio.TimeoutError:
                        break

                if not batch:
                    continue

                # Process batch
                self._batch_count += 1
                batch_input = np.stack(batch, axis=0)

                try:
                    outputs = self.model(batch_input)
                    if TORCH_AVAILABLE and isinstance(outputs, torch.Tensor):
                        outputs = outputs.cpu().numpy()

                    # Distribute results
                    for i, request_id in enumerate(request_ids):
                        if request_id in self._results:
                            self._results[request_id].set_result(outputs[i])
                            del self._results[request_id]

                except Exception as e:
                    logger.error(f"Batch inference error: {e}")
                    for request_id in request_ids:
                        if request_id in self._results:
                            self._results[request_id].set_exception(e)
                            del self._results[request_id]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batcher loop error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get batcher statistics."""
        return {
            "batch_count": self._batch_count,
            "total_requests": self._total_requests,
            "avg_batch_size": self._total_requests / max(self._batch_count, 1),
            "queue_size": self._queue.qsize(),
        }


class InferenceOptimizer:
    """Unified inference optimization manager.

    Example:
        >>> optimizer = InferenceOptimizer(config)
        >>> optimized = await optimizer.optimize(model, sample_input)
        >>> output = await optimizer.infer(optimized, input_data)
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()
        self._cache: Optional[InferenceCache] = None
        self._batchers: Dict[str, DynamicBatcher] = {}
        self._metrics: Dict[str, List[float]] = defaultdict(list)

        if self.config.enable_caching:
            self._cache = InferenceCache(
                max_size=self.config.cache_max_size,
                ttl_seconds=self.config.cache_ttl_seconds,
                redis_url=self.config.redis_url,
            )

    async def initialize(self):
        """Initialize async components."""
        if self._cache:
            await self._cache.connect()

    async def optimize(
        self,
        model: "nn.Module",
        sample_input: Union[np.ndarray, "torch.Tensor"],
        model_name: str = "model",
    ) -> OptimizedModel:
        """Optimize a model for inference.

        Args:
            model: PyTorch model
            sample_input: Sample input for optimization
            model_name: Name for the model

        Returns:
            OptimizedModel with optimized inference
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required")

        original_size = self._calculate_model_size(model)
        model.eval()

        # Convert sample input to tensor
        if isinstance(sample_input, np.ndarray):
            sample_input = torch.tensor(sample_input, dtype=torch.float32)

        optimized_model = model
        backend = "pytorch"
        dtype = "fp32"

        if self.config.level == OptimizationLevel.NONE:
            pass

        elif self.config.level == OptimizationLevel.BASIC:
            # JIT compilation
            optimized_model = torch.jit.trace(model, sample_input)
            backend = "torchscript"
            logger.info("Applied TorchScript JIT compilation")

        elif self.config.level >= OptimizationLevel.STANDARD:
            if self.config.use_onnx:
                # Convert to ONNX
                from .onnx_converter import ONNXConverter, ONNXInferenceSession

                onnx_path = Path(f"/tmp/{model_name}.onnx")
                converter = ONNXConverter()
                converter.convert(model, sample_input, onnx_path)

                if self.config.use_quantization:
                    from .quantization import quantize_onnx_dynamic
                    quant_path = quantize_onnx_dynamic(onnx_path)
                    onnx_path = Path(quant_path)
                    dtype = "int8"

                optimized_model = ONNXInferenceSession(onnx_path)
                backend = "onnx"
                logger.info("Converted to ONNX with quantization")

            elif self.config.use_quantization:
                # PyTorch quantization
                from .quantization import quantize_dynamic
                optimized_model = quantize_dynamic(model)
                dtype = "int8"
                logger.info("Applied PyTorch dynamic quantization")

        if self.config.level == OptimizationLevel.AGGRESSIVE and self.config.use_tensorrt:
            try:
                from .tensorrt_optimizer import TensorRTOptimizer, TensorRTRunner

                trt_path = Path(f"/tmp/{model_name}.trt")
                optimizer = TensorRTOptimizer()
                optimizer.build_engine(onnx_path, trt_path, precision=self.config.tensorrt_precision)
                optimized_model = TensorRTRunner(trt_path)
                backend = "tensorrt"
                dtype = self.config.tensorrt_precision
                logger.info("Optimized with TensorRT")

            except Exception as e:
                logger.warning(f"TensorRT optimization failed: {e}")

        # Benchmark
        latency = self._benchmark_latency(optimized_model, sample_input)
        optimized_size = self._calculate_model_size(optimized_model) if hasattr(optimized_model, "state_dict") else original_size

        # Setup batcher
        if self.config.enable_batching:
            self._batchers[model_name] = DynamicBatcher(
                optimized_model,
                max_batch_size=self.config.max_batch_size,
                timeout_ms=self.config.batch_timeout_ms,
            )
            await self._batchers[model_name].start()

        return OptimizedModel(
            model=optimized_model,
            optimization_level=self.config.level,
            original_size_mb=original_size,
            optimized_size_mb=optimized_size,
            compression_ratio=original_size / optimized_size,
            avg_latency_ms=latency,
            backend=backend,
            dtype=dtype,
        )

    async def infer(
        self,
        optimized: OptimizedModel,
        inputs: Union[np.ndarray, "torch.Tensor"],
        use_cache: bool = True,
        model_name: str = "model",
    ) -> np.ndarray:
        """Run optimized inference.

        Args:
            optimized: Optimized model
            inputs: Input data
            use_cache: Whether to use caching
            model_name: Model name for batching

        Returns:
            Model output
        """
        start_time = time.perf_counter()

        # Convert to numpy
        if TORCH_AVAILABLE and isinstance(inputs, torch.Tensor):
            inputs = inputs.cpu().numpy()

        # Check cache
        if use_cache and self._cache:
            cache_key = self._compute_cache_key(inputs)
            cached = await self._cache.get(cache_key)
            if cached is not None:
                self._record_metric("cache_hit", 1)
                return cached

        # Use batcher if available
        if model_name in self._batchers:
            request_id = hashlib.md5(inputs.tobytes()).hexdigest()
            output = await self._batchers[model_name].submit(request_id, inputs)
        else:
            # Direct inference
            output = optimized.model(inputs)
            if TORCH_AVAILABLE and isinstance(output, torch.Tensor):
                output = output.cpu().numpy()

        # Cache result
        if use_cache and self._cache:
            await self._cache.set(cache_key, output)

        # Record metrics
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._record_metric("latency_ms", latency_ms)

        if latency_ms > self.config.log_slow_requests_ms:
            logger.warning(f"Slow inference: {latency_ms:.1f}ms")

        return output

    def _compute_cache_key(self, inputs: np.ndarray) -> str:
        """Compute cache key for inputs."""
        return hashlib.md5(inputs.tobytes()).hexdigest()

    def _calculate_model_size(self, model: Any) -> float:
        """Calculate model size in MB."""
        if not TORCH_AVAILABLE:
            return 0.0

        if hasattr(model, "state_dict"):
            import io
            buffer = io.BytesIO()
            torch.save(model.state_dict(), buffer)
            return buffer.tell() / (1024 * 1024)
        return 0.0

    def _benchmark_latency(
        self,
        model: Any,
        sample_input: "torch.Tensor",
        num_iterations: int = 100,
    ) -> float:
        """Benchmark model latency."""
        if TORCH_AVAILABLE and isinstance(sample_input, torch.Tensor):
            sample_np = sample_input.cpu().numpy()
        else:
            sample_np = sample_input

        # Warmup
        for _ in range(10):
            if hasattr(model, "run"):
                model.run(sample_np)
            else:
                model(sample_input)

        # Benchmark
        latencies = []
        for _ in range(num_iterations):
            start = time.perf_counter()
            if hasattr(model, "run"):
                model.run(sample_np)
            else:
                model(sample_input)
            latencies.append((time.perf_counter() - start) * 1000)

        return np.mean(latencies)

    def _record_metric(self, name: str, value: float):
        """Record a metric."""
        self._metrics[name].append(value)
        # Keep only last 1000
        if len(self._metrics[name]) > 1000:
            self._metrics[name] = self._metrics[name][-1000:]

    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        stats = {
            "config": {
                "level": self.config.level.name,
                "caching": self.config.enable_caching,
                "batching": self.config.enable_batching,
            },
        }

        if self._cache:
            stats["cache"] = self._cache.get_stats()

        for name, batcher in self._batchers.items():
            stats[f"batcher_{name}"] = batcher.get_stats()

        # Metrics summary
        for name, values in self._metrics.items():
            if values:
                stats[f"metric_{name}"] = {
                    "mean": np.mean(values),
                    "p50": np.percentile(values, 50),
                    "p95": np.percentile(values, 95),
                    "p99": np.percentile(values, 99),
                }

        return stats


def optimize_for_inference(
    model: "nn.Module",
    sample_input: "torch.Tensor",
    level: OptimizationLevel = OptimizationLevel.STANDARD,
) -> OptimizedModel:
    """Synchronous convenience function to optimize a model.

    Args:
        model: PyTorch model
        sample_input: Sample input tensor
        level: Optimization level

    Returns:
        OptimizedModel
    """
    config = OptimizationConfig(level=level, enable_batching=False)
    optimizer = InferenceOptimizer(config)

    # Run synchronously
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(optimizer.optimize(model, sample_input))
    finally:
        loop.close()
