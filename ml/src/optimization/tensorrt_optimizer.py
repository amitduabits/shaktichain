"""TensorRT optimization for GPU inference acceleration.

Provides:
- ONNX to TensorRT conversion
- FP16/INT8 precision optimization
- Dynamic shape support
- Benchmark utilities
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Optional imports
try:
    import tensorrt as trt
    TRT_AVAILABLE = True
    TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
except ImportError:
    TRT_AVAILABLE = False

try:
    import pycuda.driver as cuda
    import pycuda.autoinit
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False


@dataclass
class TRTConfig:
    """TensorRT optimization configuration."""

    precision: str = "fp16"  # "fp32", "fp16", "int8"
    max_workspace_size: int = 1 << 30  # 1GB
    max_batch_size: int = 32
    min_batch_size: int = 1
    opt_batch_size: int = 8
    dynamic_shapes: bool = True
    strict_type_constraints: bool = False
    # INT8 calibration
    calibration_cache: Optional[str] = None
    calibration_data: Optional[Any] = None


@dataclass
class TRTEngineInfo:
    """Information about TensorRT engine."""

    path: str
    precision: str
    max_batch_size: int
    input_shapes: Dict[str, Tuple]
    output_shapes: Dict[str, Tuple]
    size_mb: float
    num_layers: int
    device_memory_mb: float


class TensorRTOptimizer:
    """Optimize models using NVIDIA TensorRT.

    Example:
        >>> optimizer = TensorRTOptimizer()
        >>> engine_path = optimizer.build_engine(
        ...     "model.onnx",
        ...     "model.trt",
        ...     precision="fp16"
        ... )
        >>> runner = TensorRTRunner(engine_path)
        >>> output = runner.infer(input_data)
    """

    def __init__(self, config: Optional[TRTConfig] = None):
        """Initialize TensorRT optimizer.

        Args:
            config: TensorRT configuration
        """
        if not TRT_AVAILABLE:
            raise ImportError(
                "TensorRT required. Install from NVIDIA: "
                "https://developer.nvidia.com/tensorrt"
            )

        self.config = config or TRTConfig()

    def build_engine(
        self,
        onnx_path: Union[str, Path],
        output_path: Union[str, Path],
        precision: Optional[str] = None,
        dynamic_shapes: Optional[Dict[str, Dict[str, Tuple]]] = None,
    ) -> TRTEngineInfo:
        """Build TensorRT engine from ONNX model.

        Args:
            onnx_path: Path to ONNX model
            output_path: Path to save TensorRT engine
            precision: Override precision ("fp32", "fp16", "int8")
            dynamic_shapes: Dynamic shape profiles
                e.g., {"input": {"min": (1, 10), "opt": (8, 10), "max": (32, 10)}}

        Returns:
            TRTEngineInfo with engine details
        """
        onnx_path = Path(onnx_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        precision = precision or self.config.precision

        logger.info(f"Building TensorRT engine: {onnx_path} -> {output_path}")
        logger.info(f"Precision: {precision}")

        # Create builder
        builder = trt.Builder(TRT_LOGGER)
        network = builder.create_network(
            1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        )
        parser = trt.OnnxParser(network, TRT_LOGGER)

        # Parse ONNX
        with open(onnx_path, "rb") as f:
            if not parser.parse(f.read()):
                for i in range(parser.num_errors):
                    logger.error(f"ONNX parse error: {parser.get_error(i)}")
                raise RuntimeError("Failed to parse ONNX model")

        # Configure builder
        config = builder.create_builder_config()
        config.max_workspace_size = self.config.max_workspace_size

        # Set precision
        if precision == "fp16":
            if builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)
                logger.info("FP16 enabled")
            else:
                logger.warning("FP16 not supported on this platform")

        elif precision == "int8":
            if builder.platform_has_fast_int8:
                config.set_flag(trt.BuilderFlag.INT8)
                if self.config.calibration_data is not None:
                    calibrator = self._create_int8_calibrator()
                    config.int8_calibrator = calibrator
                logger.info("INT8 enabled")
            else:
                logger.warning("INT8 not supported on this platform")

        # Configure dynamic shapes
        if self.config.dynamic_shapes or dynamic_shapes:
            profile = builder.create_optimization_profile()

            for i in range(network.num_inputs):
                input_tensor = network.get_input(i)
                name = input_tensor.name
                shape = input_tensor.shape

                if dynamic_shapes and name in dynamic_shapes:
                    shapes = dynamic_shapes[name]
                    min_shape = shapes.get("min", tuple(1 if d == -1 else d for d in shape))
                    opt_shape = shapes.get("opt", tuple(self.config.opt_batch_size if d == -1 else d for d in shape))
                    max_shape = shapes.get("max", tuple(self.config.max_batch_size if d == -1 else d for d in shape))
                else:
                    # Default dynamic batch
                    min_shape = tuple(self.config.min_batch_size if d == -1 else d for d in shape)
                    opt_shape = tuple(self.config.opt_batch_size if d == -1 else d for d in shape)
                    max_shape = tuple(self.config.max_batch_size if d == -1 else d for d in shape)

                profile.set_shape(name, min_shape, opt_shape, max_shape)
                logger.info(f"Dynamic shape for {name}: min={min_shape}, opt={opt_shape}, max={max_shape}")

            config.add_optimization_profile(profile)

        # Build engine
        logger.info("Building engine (this may take a while)...")
        engine = builder.build_engine(network, config)

        if engine is None:
            raise RuntimeError("Failed to build TensorRT engine")

        # Serialize and save
        with open(output_path, "wb") as f:
            f.write(engine.serialize())

        # Get engine info
        info = self._get_engine_info(engine, output_path, precision)

        logger.info(f"TensorRT engine built: {info.size_mb:.2f} MB, {info.num_layers} layers")

        return info

    def _create_int8_calibrator(self):
        """Create INT8 calibrator for quantization."""

        class Calibrator(trt.IInt8EntropyCalibrator2):
            def __init__(self, data, cache_file):
                super().__init__()
                self.data = data
                self.cache_file = cache_file
                self.current_index = 0

                # Allocate device memory
                self.device_input = cuda.mem_alloc(data[0].nbytes)

            def get_batch_size(self):
                return 1

            def get_batch(self, names):
                if self.current_index >= len(self.data):
                    return None

                # Copy data to device
                cuda.memcpy_htod(self.device_input, self.data[self.current_index])
                self.current_index += 1
                return [int(self.device_input)]

            def read_calibration_cache(self):
                if self.cache_file and os.path.exists(self.cache_file):
                    with open(self.cache_file, "rb") as f:
                        return f.read()
                return None

            def write_calibration_cache(self, cache):
                if self.cache_file:
                    with open(self.cache_file, "wb") as f:
                        f.write(cache)

        return Calibrator(
            self.config.calibration_data,
            self.config.calibration_cache,
        )

    def _get_engine_info(
        self,
        engine: "trt.ICudaEngine",
        path: Path,
        precision: str,
    ) -> TRTEngineInfo:
        """Get information about TensorRT engine."""
        input_shapes = {}
        output_shapes = {}

        for i in range(engine.num_bindings):
            name = engine.get_binding_name(i)
            shape = engine.get_binding_shape(i)

            if engine.binding_is_input(i):
                input_shapes[name] = tuple(shape)
            else:
                output_shapes[name] = tuple(shape)

        return TRTEngineInfo(
            path=str(path),
            precision=precision,
            max_batch_size=engine.max_batch_size,
            input_shapes=input_shapes,
            output_shapes=output_shapes,
            size_mb=path.stat().st_size / (1024 * 1024),
            num_layers=engine.num_layers,
            device_memory_mb=engine.device_memory_size / (1024 * 1024),
        )


class TensorRTRunner:
    """Run inference with TensorRT engine.

    Example:
        >>> runner = TensorRTRunner("model.trt")
        >>> output = runner.infer(input_data)
        >>> benchmark = runner.benchmark(input_data)
    """

    def __init__(self, engine_path: Union[str, Path]):
        """Initialize TensorRT runner.

        Args:
            engine_path: Path to TensorRT engine file
        """
        if not TRT_AVAILABLE:
            raise ImportError("TensorRT required")
        if not CUDA_AVAILABLE:
            raise ImportError("PyCUDA required. Install with: pip install pycuda")

        self.engine_path = Path(engine_path)

        # Load engine
        with open(engine_path, "rb") as f:
            runtime = trt.Runtime(TRT_LOGGER)
            self.engine = runtime.deserialize_cuda_engine(f.read())

        self.context = self.engine.create_execution_context()

        # Allocate buffers
        self._allocate_buffers()

        logger.info(f"TensorRT engine loaded: {engine_path}")

    def _allocate_buffers(self):
        """Allocate device and host buffers."""
        self.inputs = []
        self.outputs = []
        self.bindings = []
        self.stream = cuda.Stream()

        for i in range(self.engine.num_bindings):
            binding_shape = self.engine.get_binding_shape(i)
            size = trt.volume(binding_shape)
            dtype = trt.nptype(self.engine.get_binding_dtype(i))

            # Allocate host and device memory
            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)

            self.bindings.append(int(device_mem))

            if self.engine.binding_is_input(i):
                self.inputs.append({"host": host_mem, "device": device_mem, "shape": binding_shape})
            else:
                self.outputs.append({"host": host_mem, "device": device_mem, "shape": binding_shape})

    def infer(
        self,
        inputs: Union[np.ndarray, Dict[str, np.ndarray]],
    ) -> Union[np.ndarray, Dict[str, np.ndarray]]:
        """Run inference.

        Args:
            inputs: Input array(s)

        Returns:
            Output array(s)
        """
        # Prepare inputs
        if isinstance(inputs, np.ndarray):
            np.copyto(self.inputs[0]["host"], inputs.ravel())
        else:
            for i, (name, data) in enumerate(inputs.items()):
                np.copyto(self.inputs[i]["host"], data.ravel())

        # Transfer input to device
        for inp in self.inputs:
            cuda.memcpy_htod_async(inp["device"], inp["host"], self.stream)

        # Execute
        self.context.execute_async_v2(
            bindings=self.bindings,
            stream_handle=self.stream.handle,
        )

        # Transfer output to host
        for out in self.outputs:
            cuda.memcpy_dtoh_async(out["host"], out["device"], self.stream)

        # Synchronize
        self.stream.synchronize()

        # Return outputs
        if len(self.outputs) == 1:
            return self.outputs[0]["host"].reshape(self.outputs[0]["shape"])

        return {
            f"output_{i}": out["host"].reshape(out["shape"])
            for i, out in enumerate(self.outputs)
        }

    def warmup(self, num_iterations: int = 10):
        """Warm up the engine."""
        sample_input = np.random.randn(*self.inputs[0]["shape"]).astype(np.float32)
        for _ in range(num_iterations):
            self.infer(sample_input)
        logger.info(f"Warmup complete ({num_iterations} iterations)")

    def benchmark(
        self,
        inputs: np.ndarray,
        num_iterations: int = 100,
        warmup_iterations: int = 10,
    ) -> Dict[str, float]:
        """Benchmark inference performance.

        Args:
            inputs: Input data
            num_iterations: Number of benchmark iterations
            warmup_iterations: Warmup iterations

        Returns:
            Benchmark results
        """
        import time

        # Warmup
        for _ in range(warmup_iterations):
            self.infer(inputs)

        # Benchmark
        latencies = []
        for _ in range(num_iterations):
            start = time.perf_counter()
            self.infer(inputs)
            latencies.append((time.perf_counter() - start) * 1000)

        latencies = np.array(latencies)

        return {
            "mean_ms": float(np.mean(latencies)),
            "std_ms": float(np.std(latencies)),
            "min_ms": float(np.min(latencies)),
            "max_ms": float(np.max(latencies)),
            "p50_ms": float(np.percentile(latencies, 50)),
            "p95_ms": float(np.percentile(latencies, 95)),
            "p99_ms": float(np.percentile(latencies, 99)),
            "throughput_rps": float(1000 / np.mean(latencies)),
        }

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, "context"):
            del self.context
        if hasattr(self, "engine"):
            del self.engine


def optimize_for_tensorrt(
    onnx_path: Union[str, Path],
    output_path: Union[str, Path],
    precision: str = "fp16",
    **kwargs,
) -> TRTEngineInfo:
    """Convenience function to optimize ONNX model with TensorRT.

    Args:
        onnx_path: Path to ONNX model
        output_path: Path for TensorRT engine
        precision: "fp32", "fp16", or "int8"
        **kwargs: Additional TRTConfig parameters

    Returns:
        TRTEngineInfo
    """
    config = TRTConfig(precision=precision, **kwargs)
    optimizer = TensorRTOptimizer(config)
    return optimizer.build_engine(onnx_path, output_path)
