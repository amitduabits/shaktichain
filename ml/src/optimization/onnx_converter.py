"""ONNX conversion utilities for portable model inference.

Converts PyTorch models to ONNX format for:
- Cross-platform deployment
- Optimized inference with ONNX Runtime
- Integration with TensorRT, OpenVINO, etc.
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
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import onnx
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False


@dataclass
class ONNXConversionConfig:
    """Configuration for ONNX conversion."""

    opset_version: int = 14
    dynamic_axes: Optional[Dict[str, Dict[int, str]]] = None
    input_names: Optional[List[str]] = None
    output_names: Optional[List[str]] = None
    do_constant_folding: bool = True
    verbose: bool = False
    optimize: bool = True


@dataclass
class ONNXModelInfo:
    """Information about converted ONNX model."""

    path: str
    input_shapes: Dict[str, Tuple]
    output_shapes: Dict[str, Tuple]
    opset_version: int
    size_mb: float
    num_nodes: int
    providers: List[str]


class ONNXConverter:
    """Convert PyTorch models to ONNX format.

    Example:
        >>> converter = ONNXConverter()
        >>> info = converter.convert(
        ...     model=pytorch_model,
        ...     sample_input=torch.randn(1, 10),
        ...     output_path="model.onnx"
        ... )
        >>> print(f"Converted model: {info.path}")
        >>> print(f"Size: {info.size_mb:.2f} MB")
    """

    def __init__(self, config: Optional[ONNXConversionConfig] = None):
        """Initialize converter.

        Args:
            config: Conversion configuration
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required. Install with: pip install torch")
        if not ONNX_AVAILABLE:
            raise ImportError("ONNX required. Install with: pip install onnx onnxruntime")

        self.config = config or ONNXConversionConfig()

    def convert(
        self,
        model: "nn.Module",
        sample_input: Union["torch.Tensor", Tuple["torch.Tensor", ...]],
        output_path: Union[str, Path],
        input_names: Optional[List[str]] = None,
        output_names: Optional[List[str]] = None,
        dynamic_batch: bool = True,
        dynamic_sequence: bool = False,
    ) -> ONNXModelInfo:
        """Convert PyTorch model to ONNX.

        Args:
            model: PyTorch model to convert
            sample_input: Sample input tensor(s) for tracing
            output_path: Path to save ONNX model
            input_names: Names for input tensors
            output_names: Names for output tensors
            dynamic_batch: Allow dynamic batch size
            dynamic_sequence: Allow dynamic sequence length

        Returns:
            ONNXModelInfo with conversion details
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare model
        model.eval()

        # Determine input/output names
        if input_names is None:
            if isinstance(sample_input, tuple):
                input_names = [f"input_{i}" for i in range(len(sample_input))]
            else:
                input_names = ["input"]

        if output_names is None:
            output_names = ["output"]

        # Build dynamic axes
        dynamic_axes = self.config.dynamic_axes
        if dynamic_axes is None and (dynamic_batch or dynamic_sequence):
            dynamic_axes = {}
            for name in input_names:
                axes = {}
                if dynamic_batch:
                    axes[0] = "batch_size"
                if dynamic_sequence:
                    axes[1] = "sequence_length"
                dynamic_axes[name] = axes

            for name in output_names:
                axes = {}
                if dynamic_batch:
                    axes[0] = "batch_size"
                dynamic_axes[name] = axes

        # Export to ONNX
        logger.info(f"Converting model to ONNX: {output_path}")

        with torch.no_grad():
            torch.onnx.export(
                model,
                sample_input,
                str(output_path),
                input_names=input_names,
                output_names=output_names,
                dynamic_axes=dynamic_axes,
                opset_version=self.config.opset_version,
                do_constant_folding=self.config.do_constant_folding,
                verbose=self.config.verbose,
            )

        # Optimize if requested
        if self.config.optimize:
            self._optimize_model(output_path)

        # Validate
        self._validate_model(output_path)

        # Get model info
        info = self._get_model_info(output_path)

        logger.info(f"ONNX conversion complete: {info.size_mb:.2f} MB, {info.num_nodes} nodes")

        return info

    def _optimize_model(self, model_path: Path):
        """Apply ONNX optimizations."""
        try:
            from onnxruntime.transformers import optimizer

            optimized_path = model_path.with_suffix(".optimized.onnx")
            optimizer.optimize_model(
                str(model_path),
                model_type="bert",  # Generic transformer optimization
                num_heads=0,
                hidden_size=0,
            ).save_model_to_file(str(optimized_path))

            # Replace original with optimized
            os.replace(optimized_path, model_path)
            logger.info("Applied ONNX Runtime optimizations")

        except Exception as e:
            logger.warning(f"Could not apply optimizations: {e}")

    def _validate_model(self, model_path: Path):
        """Validate ONNX model."""
        model = onnx.load(str(model_path))
        onnx.checker.check_model(model)
        logger.info("ONNX model validation passed")

    def _get_model_info(self, model_path: Path) -> ONNXModelInfo:
        """Get information about ONNX model."""
        model = onnx.load(str(model_path))

        # Get input shapes
        input_shapes = {}
        for inp in model.graph.input:
            shape = []
            for dim in inp.type.tensor_type.shape.dim:
                if dim.dim_param:
                    shape.append(dim.dim_param)
                else:
                    shape.append(dim.dim_value)
            input_shapes[inp.name] = tuple(shape)

        # Get output shapes
        output_shapes = {}
        for out in model.graph.output:
            shape = []
            for dim in out.type.tensor_type.shape.dim:
                if dim.dim_param:
                    shape.append(dim.dim_param)
                else:
                    shape.append(dim.dim_value)
            output_shapes[out.name] = tuple(shape)

        # Get size
        size_mb = model_path.stat().st_size / (1024 * 1024)

        # Count nodes
        num_nodes = len(model.graph.node)

        # Get available providers
        providers = ort.get_available_providers()

        return ONNXModelInfo(
            path=str(model_path),
            input_shapes=input_shapes,
            output_shapes=output_shapes,
            opset_version=model.opset_import[0].version,
            size_mb=size_mb,
            num_nodes=num_nodes,
            providers=providers,
        )

    def verify_outputs(
        self,
        pytorch_model: "nn.Module",
        onnx_path: Union[str, Path],
        sample_input: Union["torch.Tensor", Tuple["torch.Tensor", ...]],
        rtol: float = 1e-3,
        atol: float = 1e-5,
    ) -> Dict[str, Any]:
        """Verify ONNX outputs match PyTorch outputs.

        Args:
            pytorch_model: Original PyTorch model
            onnx_path: Path to ONNX model
            sample_input: Sample input for comparison
            rtol: Relative tolerance
            atol: Absolute tolerance

        Returns:
            Verification results with max difference
        """
        pytorch_model.eval()

        # Get PyTorch output
        with torch.no_grad():
            if isinstance(sample_input, tuple):
                pt_output = pytorch_model(*sample_input)
            else:
                pt_output = pytorch_model(sample_input)

        if isinstance(pt_output, tuple):
            pt_output = pt_output[0]
        pt_output = pt_output.cpu().numpy()

        # Get ONNX output
        session = ort.InferenceSession(str(onnx_path))

        if isinstance(sample_input, tuple):
            ort_inputs = {
                f"input_{i}": inp.cpu().numpy()
                for i, inp in enumerate(sample_input)
            }
        else:
            ort_inputs = {"input": sample_input.cpu().numpy()}

        ort_output = session.run(None, ort_inputs)[0]

        # Compare
        max_diff = np.max(np.abs(pt_output - ort_output))
        mean_diff = np.mean(np.abs(pt_output - ort_output))
        matches = np.allclose(pt_output, ort_output, rtol=rtol, atol=atol)

        return {
            "matches": matches,
            "max_difference": float(max_diff),
            "mean_difference": float(mean_diff),
            "rtol": rtol,
            "atol": atol,
        }


class ONNXInferenceSession:
    """Optimized ONNX inference session.

    Example:
        >>> session = ONNXInferenceSession("model.onnx")
        >>> output = session.run(input_data)
    """

    def __init__(
        self,
        model_path: Union[str, Path],
        providers: Optional[List[str]] = None,
        num_threads: int = 4,
        enable_profiling: bool = False,
    ):
        """Initialize inference session.

        Args:
            model_path: Path to ONNX model
            providers: Execution providers (default: auto-detect)
            num_threads: Number of threads for CPU execution
            enable_profiling: Enable performance profiling
        """
        if not ONNX_AVAILABLE:
            raise ImportError("ONNX Runtime required. Install with: pip install onnxruntime")

        self.model_path = Path(model_path)

        # Auto-detect providers
        if providers is None:
            available = ort.get_available_providers()
            providers = []
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
            if "TensorrtExecutionProvider" in available:
                providers.append("TensorrtExecutionProvider")
            providers.append("CPUExecutionProvider")

        # Session options
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = num_threads
        sess_options.inter_op_num_threads = num_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        if enable_profiling:
            sess_options.enable_profiling = True

        # Create session
        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=providers,
        )

        # Cache input/output info
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]

        logger.info(f"ONNX session initialized with providers: {providers}")

    def run(
        self,
        inputs: Union[np.ndarray, Dict[str, np.ndarray]],
        output_names: Optional[List[str]] = None,
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """Run inference.

        Args:
            inputs: Input array(s)
            output_names: Specific outputs to return (default: all)

        Returns:
            Output array(s)
        """
        # Prepare inputs
        if isinstance(inputs, np.ndarray):
            ort_inputs = {self.input_names[0]: inputs}
        elif isinstance(inputs, dict):
            ort_inputs = inputs
        else:
            raise ValueError(f"Unsupported input type: {type(inputs)}")

        # Ensure float32
        ort_inputs = {
            k: v.astype(np.float32) if v.dtype != np.float32 else v
            for k, v in ort_inputs.items()
        }

        # Run
        outputs = self.session.run(output_names, ort_inputs)

        if len(outputs) == 1:
            return outputs[0]
        return outputs

    def warmup(self, num_iterations: int = 10):
        """Warm up the session for consistent benchmarks."""
        # Get sample input shapes
        sample_inputs = {}
        for inp in self.session.get_inputs():
            shape = []
            for dim in inp.shape:
                if isinstance(dim, str):
                    shape.append(1)  # Dynamic dim
                else:
                    shape.append(dim)
            sample_inputs[inp.name] = np.random.randn(*shape).astype(np.float32)

        for _ in range(num_iterations):
            self.run(sample_inputs)

        logger.info(f"Warmup complete ({num_iterations} iterations)")

    def benchmark(
        self,
        inputs: Union[np.ndarray, Dict[str, np.ndarray]],
        num_iterations: int = 100,
        warmup_iterations: int = 10,
    ) -> Dict[str, float]:
        """Benchmark inference performance.

        Args:
            inputs: Input data
            num_iterations: Number of iterations
            warmup_iterations: Warmup iterations

        Returns:
            Benchmark results (latency stats)
        """
        import time

        # Warmup
        for _ in range(warmup_iterations):
            self.run(inputs)

        # Benchmark
        latencies = []
        for _ in range(num_iterations):
            start = time.perf_counter()
            self.run(inputs)
            latencies.append((time.perf_counter() - start) * 1000)  # ms

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


def convert_to_onnx(
    model: "nn.Module",
    sample_input: Union["torch.Tensor", Tuple["torch.Tensor", ...]],
    output_path: Union[str, Path],
    **kwargs,
) -> ONNXModelInfo:
    """Convenience function to convert model to ONNX.

    Args:
        model: PyTorch model
        sample_input: Sample input for tracing
        output_path: Output path
        **kwargs: Additional arguments for ONNXConverter.convert()

    Returns:
        ONNXModelInfo
    """
    converter = ONNXConverter()
    return converter.convert(model, sample_input, output_path, **kwargs)
