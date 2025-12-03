"""Benchmarking utilities for SHAKTI-CHAIN ML models.

Provides:
- Latency benchmarking (p50, p95, p99)
- Throughput measurement
- Memory profiling
- Comparison tools
"""

import gc
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""

    # Latency metrics (milliseconds)
    latency_mean_ms: float
    latency_std_ms: float
    latency_min_ms: float
    latency_max_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float

    # Throughput
    throughput_rps: float

    # Memory
    memory_mb: float
    peak_memory_mb: float

    # Configuration
    batch_size: int
    num_iterations: int
    warmup_iterations: int

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model_name: str = ""
    device: str = "cpu"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latency": {
                "mean_ms": self.latency_mean_ms,
                "std_ms": self.latency_std_ms,
                "min_ms": self.latency_min_ms,
                "max_ms": self.latency_max_ms,
                "p50_ms": self.latency_p50_ms,
                "p95_ms": self.latency_p95_ms,
                "p99_ms": self.latency_p99_ms,
            },
            "throughput_rps": self.throughput_rps,
            "memory": {
                "current_mb": self.memory_mb,
                "peak_mb": self.peak_memory_mb,
            },
            "config": {
                "batch_size": self.batch_size,
                "num_iterations": self.num_iterations,
                "warmup_iterations": self.warmup_iterations,
            },
            "metadata": {
                "timestamp": self.timestamp,
                "model_name": self.model_name,
                "device": self.device,
                "notes": self.notes,
            },
        }

    def meets_target(self, target: "PerformanceTarget") -> Dict[str, bool]:
        """Check if benchmark meets performance targets."""
        return {
            "p50": self.latency_p50_ms <= target.p50_ms,
            "p95": self.latency_p95_ms <= target.p95_ms,
            "p99": self.latency_p99_ms <= target.p99_ms,
            "throughput": self.throughput_rps >= target.min_rps,
            "memory": self.memory_mb <= target.max_memory_mb,
        }


@dataclass
class PerformanceTarget:
    """Performance target for benchmarking."""

    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_rps: float
    max_memory_mb: float = 1000.0

    @classmethod
    def for_endpoint(cls, endpoint: str) -> "PerformanceTarget":
        """Get performance target for a specific endpoint."""
        targets = {
            "/forecast/load": cls(p50_ms=100, p95_ms=200, p99_ms=500, min_rps=100),
            "/forecast/price": cls(p50_ms=50, p95_ms=100, p99_ms=200, min_rps=200),
            "/trading/action": cls(p50_ms=20, p95_ms=50, p99_ms=100, min_rps=500),
            "/anomaly/score": cls(p50_ms=30, p95_ms=80, p99_ms=150, min_rps=300),
        }
        return targets.get(endpoint, cls(p50_ms=100, p95_ms=200, p99_ms=500, min_rps=100))


class ModelBenchmark:
    """Benchmark model inference performance.

    Example:
        >>> benchmark = ModelBenchmark(model)
        >>> result = benchmark.run(sample_input, num_iterations=100)
        >>> print(f"p99 latency: {result.latency_p99_ms:.2f}ms")
        >>> print(f"Throughput: {result.throughput_rps:.0f} RPS")
    """

    def __init__(
        self,
        model: Any,
        model_name: str = "model",
        device: str = "cpu",
    ):
        """Initialize benchmark.

        Args:
            model: Model to benchmark
            model_name: Name for reporting
            device: Device for inference
        """
        self.model = model
        self.model_name = model_name
        self.device = device

        if TORCH_AVAILABLE and hasattr(model, "to"):
            self.model = model.to(device)

    def run(
        self,
        inputs: Union[np.ndarray, "torch.Tensor"],
        num_iterations: int = 100,
        warmup_iterations: int = 10,
        batch_sizes: Optional[List[int]] = None,
    ) -> Union[BenchmarkResult, List[BenchmarkResult]]:
        """Run benchmark.

        Args:
            inputs: Input data (single sample)
            num_iterations: Number of benchmark iterations
            warmup_iterations: Warmup iterations
            batch_sizes: If provided, benchmark multiple batch sizes

        Returns:
            BenchmarkResult or list of results for each batch size
        """
        if batch_sizes:
            results = []
            for batch_size in batch_sizes:
                result = self._run_single(inputs, num_iterations, warmup_iterations, batch_size)
                results.append(result)
            return results

        return self._run_single(inputs, num_iterations, warmup_iterations, 1)

    def _run_single(
        self,
        inputs: Union[np.ndarray, "torch.Tensor"],
        num_iterations: int,
        warmup_iterations: int,
        batch_size: int,
    ) -> BenchmarkResult:
        """Run benchmark for a single configuration."""
        # Prepare batched input
        if TORCH_AVAILABLE and isinstance(inputs, torch.Tensor):
            if inputs.dim() == 1:
                inputs = inputs.unsqueeze(0)
            batched_input = inputs.repeat(batch_size, *([1] * (inputs.dim() - 1)))
            batched_input = batched_input.to(self.device)
        else:
            if inputs.ndim == 1:
                inputs = inputs.reshape(1, -1)
            batched_input = np.tile(inputs, (batch_size, 1))

        # Enable eval mode
        if hasattr(self.model, "eval"):
            self.model.eval()

        # Clear cache
        gc.collect()
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        # Warmup
        for _ in range(warmup_iterations):
            self._run_inference(batched_input)

        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.synchronize()

        # Benchmark
        latencies = []
        memory_samples = []

        for _ in range(num_iterations):
            # Record memory before
            if PSUTIL_AVAILABLE:
                memory_before = psutil.Process().memory_info().rss / (1024 * 1024)

            # Time inference
            start = time.perf_counter()
            self._run_inference(batched_input)

            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.synchronize()

            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

            # Record memory after
            if PSUTIL_AVAILABLE:
                memory_after = psutil.Process().memory_info().rss / (1024 * 1024)
                memory_samples.append(memory_after)

        latencies = np.array(latencies)

        # Calculate metrics
        memory_mb = np.mean(memory_samples) if memory_samples else 0.0
        peak_memory_mb = np.max(memory_samples) if memory_samples else 0.0

        # Per-sample latency
        per_sample_latencies = latencies / batch_size

        return BenchmarkResult(
            latency_mean_ms=float(np.mean(per_sample_latencies)),
            latency_std_ms=float(np.std(per_sample_latencies)),
            latency_min_ms=float(np.min(per_sample_latencies)),
            latency_max_ms=float(np.max(per_sample_latencies)),
            latency_p50_ms=float(np.percentile(per_sample_latencies, 50)),
            latency_p95_ms=float(np.percentile(per_sample_latencies, 95)),
            latency_p99_ms=float(np.percentile(per_sample_latencies, 99)),
            throughput_rps=float(1000 * batch_size / np.mean(latencies)),
            memory_mb=memory_mb,
            peak_memory_mb=peak_memory_mb,
            batch_size=batch_size,
            num_iterations=num_iterations,
            warmup_iterations=warmup_iterations,
            model_name=self.model_name,
            device=self.device,
        )

    def _run_inference(self, inputs: Any) -> Any:
        """Run single inference."""
        if TORCH_AVAILABLE:
            with torch.no_grad():
                if hasattr(self.model, "run"):
                    # ONNX Runtime
                    if isinstance(inputs, torch.Tensor):
                        inputs = inputs.cpu().numpy()
                    return self.model.run(inputs)
                elif hasattr(self.model, "infer"):
                    # TensorRT
                    if isinstance(inputs, torch.Tensor):
                        inputs = inputs.cpu().numpy()
                    return self.model.infer(inputs)
                else:
                    return self.model(inputs)
        else:
            return self.model(inputs)


class EndpointBenchmark:
    """Benchmark API endpoints.

    Example:
        >>> benchmark = EndpointBenchmark("http://localhost:8000")
        >>> result = benchmark.run_endpoint("/trading/action", request_data)
        >>> print(f"p99 latency: {result.latency_p99_ms:.2f}ms")
    """

    def __init__(self, base_url: str):
        """Initialize endpoint benchmark.

        Args:
            base_url: Base URL of the API
        """
        self.base_url = base_url.rstrip("/")

    def run_endpoint(
        self,
        endpoint: str,
        request_data: Dict[str, Any],
        num_iterations: int = 100,
        warmup_iterations: int = 10,
        concurrent_requests: int = 1,
    ) -> BenchmarkResult:
        """Benchmark an API endpoint.

        Args:
            endpoint: Endpoint path (e.g., "/trading/action")
            request_data: Request payload
            num_iterations: Number of iterations
            warmup_iterations: Warmup iterations
            concurrent_requests: Number of concurrent requests

        Returns:
            BenchmarkResult
        """
        import requests

        url = f"{self.base_url}{endpoint}"

        # Warmup
        for _ in range(warmup_iterations):
            requests.post(url, json=request_data)

        # Benchmark
        latencies = []

        for _ in range(num_iterations):
            start = time.perf_counter()
            response = requests.post(url, json=request_data)
            elapsed = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                latencies.append(elapsed)

        if not latencies:
            raise RuntimeError("All requests failed")

        latencies = np.array(latencies)

        return BenchmarkResult(
            latency_mean_ms=float(np.mean(latencies)),
            latency_std_ms=float(np.std(latencies)),
            latency_min_ms=float(np.min(latencies)),
            latency_max_ms=float(np.max(latencies)),
            latency_p50_ms=float(np.percentile(latencies, 50)),
            latency_p95_ms=float(np.percentile(latencies, 95)),
            latency_p99_ms=float(np.percentile(latencies, 99)),
            throughput_rps=float(1000 / np.mean(latencies)),
            memory_mb=0.0,
            peak_memory_mb=0.0,
            batch_size=1,
            num_iterations=num_iterations,
            warmup_iterations=warmup_iterations,
            model_name=endpoint,
            device="api",
        )

    async def run_concurrent(
        self,
        endpoint: str,
        request_data: Dict[str, Any],
        num_requests: int = 100,
        concurrency: int = 10,
    ) -> BenchmarkResult:
        """Benchmark endpoint with concurrent requests.

        Args:
            endpoint: Endpoint path
            request_data: Request payload
            num_requests: Total number of requests
            concurrency: Number of concurrent requests

        Returns:
            BenchmarkResult
        """
        import asyncio
        import aiohttp

        url = f"{self.base_url}{endpoint}"
        latencies = []
        semaphore = asyncio.Semaphore(concurrency)

        async def make_request():
            async with semaphore:
                async with aiohttp.ClientSession() as session:
                    start = time.perf_counter()
                    async with session.post(url, json=request_data) as response:
                        await response.read()
                        elapsed = (time.perf_counter() - start) * 1000
                        if response.status == 200:
                            latencies.append(elapsed)

        tasks = [make_request() for _ in range(num_requests)]
        start_time = time.perf_counter()
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time

        if not latencies:
            raise RuntimeError("All requests failed")

        latencies = np.array(latencies)

        return BenchmarkResult(
            latency_mean_ms=float(np.mean(latencies)),
            latency_std_ms=float(np.std(latencies)),
            latency_min_ms=float(np.min(latencies)),
            latency_max_ms=float(np.max(latencies)),
            latency_p50_ms=float(np.percentile(latencies, 50)),
            latency_p95_ms=float(np.percentile(latencies, 95)),
            latency_p99_ms=float(np.percentile(latencies, 99)),
            throughput_rps=float(len(latencies) / total_time),
            memory_mb=0.0,
            peak_memory_mb=0.0,
            batch_size=1,
            num_iterations=num_requests,
            warmup_iterations=0,
            model_name=endpoint,
            device="api",
            notes=f"concurrency={concurrency}",
        )


def compare_models(
    models: Dict[str, Any],
    sample_input: Union[np.ndarray, "torch.Tensor"],
    num_iterations: int = 100,
) -> Dict[str, BenchmarkResult]:
    """Compare multiple models.

    Args:
        models: Dictionary of model_name -> model
        sample_input: Sample input for benchmarking
        num_iterations: Number of iterations

    Returns:
        Dictionary of model_name -> BenchmarkResult
    """
    results = {}

    for name, model in models.items():
        logger.info(f"Benchmarking {name}...")
        benchmark = ModelBenchmark(model, model_name=name)
        results[name] = benchmark.run(sample_input, num_iterations=num_iterations)
        logger.info(f"  p99: {results[name].latency_p99_ms:.2f}ms, throughput: {results[name].throughput_rps:.0f} RPS")

    return results


def generate_benchmark_report(
    results: Dict[str, BenchmarkResult],
    targets: Optional[Dict[str, PerformanceTarget]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Generate benchmark report.

    Args:
        results: Benchmark results
        targets: Performance targets
        output_path: Optional path to save report

    Returns:
        Report as string
    """
    lines = [
        "# SHAKTI-CHAIN ML Benchmark Report",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Summary",
        "",
        "| Model | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (RPS) | Memory (MB) |",
        "|-------|----------|----------|----------|------------------|-------------|",
    ]

    for name, result in results.items():
        lines.append(
            f"| {name} | {result.latency_p50_ms:.2f} | {result.latency_p95_ms:.2f} | "
            f"{result.latency_p99_ms:.2f} | {result.throughput_rps:.0f} | {result.memory_mb:.1f} |"
        )

    lines.append("")

    # Target compliance
    if targets:
        lines.extend([
            "## Target Compliance",
            "",
            "| Model | p50 | p95 | p99 | Throughput | Memory |",
            "|-------|-----|-----|-----|------------|--------|",
        ])

        for name, result in results.items():
            if name in targets:
                compliance = result.meets_target(targets[name])
                lines.append(
                    f"| {name} | {'✓' if compliance['p50'] else '✗'} | "
                    f"{'✓' if compliance['p95'] else '✗'} | "
                    f"{'✓' if compliance['p99'] else '✗'} | "
                    f"{'✓' if compliance['throughput'] else '✗'} | "
                    f"{'✓' if compliance['memory'] else '✗'} |"
                )

        lines.append("")

    # Detailed results
    lines.extend([
        "## Detailed Results",
        "",
    ])

    for name, result in results.items():
        lines.extend([
            f"### {name}",
            "",
            f"- **Latency (ms)**",
            f"  - Mean: {result.latency_mean_ms:.3f} ± {result.latency_std_ms:.3f}",
            f"  - Min: {result.latency_min_ms:.3f}, Max: {result.latency_max_ms:.3f}",
            f"  - p50: {result.latency_p50_ms:.3f}, p95: {result.latency_p95_ms:.3f}, p99: {result.latency_p99_ms:.3f}",
            f"- **Throughput**: {result.throughput_rps:.1f} requests/second",
            f"- **Memory**: {result.memory_mb:.1f} MB (peak: {result.peak_memory_mb:.1f} MB)",
            f"- **Configuration**: batch_size={result.batch_size}, iterations={result.num_iterations}",
            "",
        ])

    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report)
        logger.info(f"Report saved to {output_path}")

    return report


def run_full_benchmark_suite(
    models: Dict[str, Any],
    sample_inputs: Dict[str, np.ndarray],
    output_dir: Union[str, Path] = "benchmark_results",
) -> Dict[str, Any]:
    """Run full benchmark suite.

    Args:
        models: Dictionary of model_name -> model
        sample_inputs: Dictionary of model_name -> sample_input
        output_dir: Directory for results

    Returns:
        Full benchmark results
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Single batch benchmarks
    logger.info("Running single-batch benchmarks...")
    for name, model in models.items():
        if name in sample_inputs:
            benchmark = ModelBenchmark(model, model_name=name)
            results[name] = benchmark.run(sample_inputs[name], num_iterations=100)

    # Multi-batch benchmarks
    logger.info("Running multi-batch benchmarks...")
    batch_results = {}
    for name, model in models.items():
        if name in sample_inputs:
            benchmark = ModelBenchmark(model, model_name=name)
            batch_results[name] = benchmark.run(
                sample_inputs[name],
                num_iterations=100,
                batch_sizes=[1, 4, 8, 16, 32],
            )

    # Generate report
    targets = {
        "load_forecast": PerformanceTarget.for_endpoint("/forecast/load"),
        "price_forecast": PerformanceTarget.for_endpoint("/forecast/price"),
        "trading_agent": PerformanceTarget.for_endpoint("/trading/action"),
        "anomaly_detector": PerformanceTarget.for_endpoint("/anomaly/score"),
    }

    report = generate_benchmark_report(results, targets, output_dir / "benchmark_report.md")

    # Save raw results
    import json
    with open(output_dir / "results.json", "w") as f:
        json.dump({
            name: result.to_dict()
            for name, result in results.items()
        }, f, indent=2)

    return {
        "results": results,
        "batch_results": batch_results,
        "report_path": str(output_dir / "benchmark_report.md"),
    }
