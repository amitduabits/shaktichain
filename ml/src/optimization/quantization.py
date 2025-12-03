"""Model quantization utilities for reduced memory and faster inference.

Supports:
- Dynamic quantization (INT8 weights, FP32 activations)
- Static quantization (INT8 weights and activations)
- FP16 quantization (half precision)
- ONNX quantization
"""

import logging
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
    from torch.quantization import quantize_dynamic as torch_quantize_dynamic
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import onnx
    from onnxruntime.quantization import (
        quantize_dynamic as onnx_quantize_dynamic,
        quantize_static as onnx_quantize_static,
        CalibrationDataReader,
        QuantType,
    )
    ONNX_QUANT_AVAILABLE = True
except ImportError:
    ONNX_QUANT_AVAILABLE = False


class QuantizationType(Enum):
    """Quantization type."""
    DYNAMIC_INT8 = "dynamic_int8"
    STATIC_INT8 = "static_int8"
    FP16 = "fp16"
    INT4 = "int4"  # For weight-only quantization


@dataclass
class QuantizationConfig:
    """Configuration for model quantization."""

    quant_type: QuantizationType = QuantizationType.DYNAMIC_INT8
    modules_to_quantize: Optional[List[str]] = None  # e.g., ["Linear", "LSTM"]
    modules_to_exclude: Optional[List[str]] = None
    calibration_samples: int = 100
    per_channel: bool = True
    symmetric: bool = True
    optimize_model: bool = True
    # For static quantization
    calibration_data: Optional[Any] = None


@dataclass
class QuantizationResult:
    """Result of quantization."""

    original_size_mb: float
    quantized_size_mb: float
    compression_ratio: float
    original_latency_ms: float
    quantized_latency_ms: float
    speedup: float
    accuracy_delta: Optional[float] = None
    output_path: Optional[str] = None


class QuantizedModel:
    """Wrapper for quantized PyTorch model."""

    def __init__(
        self,
        model: "nn.Module",
        quant_type: QuantizationType,
        original_size_mb: float,
    ):
        self.model = model
        self.quant_type = quant_type
        self.original_size_mb = original_size_mb
        self._quantized_size_mb = None

    @property
    def quantized_size_mb(self) -> float:
        """Get quantized model size."""
        if self._quantized_size_mb is None:
            self._quantized_size_mb = self._calculate_size()
        return self._quantized_size_mb

    def _calculate_size(self) -> float:
        """Calculate model size in MB."""
        import io
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        return buffer.tell() / (1024 * 1024)

    def __call__(self, *args, **kwargs):
        return self.model(*args, **kwargs)

    def eval(self):
        self.model.eval()
        return self

    def to(self, device):
        self.model.to(device)
        return self


def quantize_model(
    model: "nn.Module",
    config: Optional[QuantizationConfig] = None,
    sample_input: Optional["torch.Tensor"] = None,
) -> QuantizedModel:
    """Quantize a PyTorch model.

    Args:
        model: PyTorch model to quantize
        config: Quantization configuration
        sample_input: Sample input for calibration (static quant)

    Returns:
        QuantizedModel wrapper
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required for quantization")

    config = config or QuantizationConfig()

    # Calculate original size
    original_size = _calculate_model_size(model)

    if config.quant_type == QuantizationType.DYNAMIC_INT8:
        quantized = quantize_dynamic(model, config)
    elif config.quant_type == QuantizationType.STATIC_INT8:
        if sample_input is None:
            raise ValueError("sample_input required for static quantization")
        quantized = quantize_static(model, config, sample_input)
    elif config.quant_type == QuantizationType.FP16:
        quantized = quantize_fp16(model)
    else:
        raise ValueError(f"Unsupported quantization type: {config.quant_type}")

    return QuantizedModel(quantized, config.quant_type, original_size)


def quantize_dynamic(
    model: "nn.Module",
    config: Optional[QuantizationConfig] = None,
) -> "nn.Module":
    """Apply dynamic quantization (INT8 weights).

    Dynamic quantization quantizes weights to INT8 but computes
    activations in FP32. Good for models with small batch sizes.

    Args:
        model: PyTorch model
        config: Quantization config

    Returns:
        Dynamically quantized model
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required")

    config = config or QuantizationConfig()
    model.eval()

    # Determine which modules to quantize
    modules_to_quantize = config.modules_to_quantize
    if modules_to_quantize is None:
        modules_to_quantize = {nn.Linear, nn.LSTM, nn.GRU, nn.LSTMCell, nn.GRUCell}
    else:
        modules_to_quantize = {getattr(nn, m) for m in modules_to_quantize}

    # Apply dynamic quantization
    quantized_model = torch_quantize_dynamic(
        model,
        modules_to_quantize,
        dtype=torch.qint8,
    )

    logger.info(f"Applied dynamic INT8 quantization to {modules_to_quantize}")

    return quantized_model


def quantize_static(
    model: "nn.Module",
    config: QuantizationConfig,
    calibration_data: Union["torch.Tensor", List["torch.Tensor"]],
) -> "nn.Module":
    """Apply static quantization (INT8 weights and activations).

    Static quantization requires calibration data to determine
    activation ranges. Provides best performance for inference.

    Args:
        model: PyTorch model
        config: Quantization config
        calibration_data: Data for calibration

    Returns:
        Statically quantized model
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required")

    model.eval()

    # Prepare model for static quantization
    model.qconfig = torch.quantization.get_default_qconfig("fbgemm")

    # Fuse modules (Conv-BN-ReLU, etc.)
    model_fused = torch.quantization.fuse_modules(
        model,
        _find_fuseable_modules(model),
        inplace=False,
    )

    # Prepare model
    model_prepared = torch.quantization.prepare(model_fused, inplace=False)

    # Calibrate with data
    logger.info("Calibrating quantization ranges...")
    with torch.no_grad():
        if isinstance(calibration_data, list):
            for data in calibration_data[:config.calibration_samples]:
                model_prepared(data)
        else:
            model_prepared(calibration_data)

    # Convert to quantized model
    quantized_model = torch.quantization.convert(model_prepared, inplace=False)

    logger.info("Applied static INT8 quantization")

    return quantized_model


def quantize_fp16(model: "nn.Module") -> "nn.Module":
    """Convert model to FP16 (half precision).

    Args:
        model: PyTorch model

    Returns:
        FP16 model
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required")

    model.eval()
    model_fp16 = model.half()

    logger.info("Converted model to FP16")

    return model_fp16


def _find_fuseable_modules(model: "nn.Module") -> List[List[str]]:
    """Find module sequences that can be fused."""
    fuseable = []

    # Common fusion patterns
    patterns = [
        (nn.Conv2d, nn.BatchNorm2d, nn.ReLU),
        (nn.Conv2d, nn.BatchNorm2d),
        (nn.Conv2d, nn.ReLU),
        (nn.Linear, nn.ReLU),
        (nn.Linear, nn.BatchNorm1d, nn.ReLU),
    ]

    # This is a simplified implementation
    # In practice, would need to traverse the model graph
    return fuseable


def _calculate_model_size(model: "nn.Module") -> float:
    """Calculate model size in MB."""
    import io
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.tell() / (1024 * 1024)


# ============================================================================
# ONNX Quantization
# ============================================================================


class ONNXCalibrationDataReader(CalibrationDataReader if ONNX_QUANT_AVAILABLE else object):
    """Calibration data reader for ONNX static quantization."""

    def __init__(
        self,
        data: List[Dict[str, np.ndarray]],
        batch_size: int = 1,
    ):
        self.data = data
        self.batch_size = batch_size
        self.current_idx = 0

    def get_next(self) -> Optional[Dict[str, np.ndarray]]:
        if self.current_idx >= len(self.data):
            return None
        result = self.data[self.current_idx]
        self.current_idx += 1
        return result

    def rewind(self):
        self.current_idx = 0


def quantize_onnx_dynamic(
    model_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    weight_type: str = "QInt8",
) -> str:
    """Apply dynamic quantization to ONNX model.

    Args:
        model_path: Path to ONNX model
        output_path: Output path (default: model_quant.onnx)
        weight_type: Weight quantization type ("QInt8" or "QUInt8")

    Returns:
        Path to quantized model
    """
    if not ONNX_QUANT_AVAILABLE:
        raise ImportError("ONNX Runtime quantization required. Install with: pip install onnxruntime")

    model_path = Path(model_path)
    if output_path is None:
        output_path = model_path.with_stem(model_path.stem + "_quant_dynamic")
    output_path = Path(output_path)

    quant_type = QuantType.QInt8 if weight_type == "QInt8" else QuantType.QUInt8

    onnx_quantize_dynamic(
        str(model_path),
        str(output_path),
        weight_type=quant_type,
    )

    logger.info(f"ONNX dynamic quantization complete: {output_path}")

    return str(output_path)


def quantize_onnx_static(
    model_path: Union[str, Path],
    calibration_data: List[Dict[str, np.ndarray]],
    output_path: Optional[Union[str, Path]] = None,
    per_channel: bool = True,
) -> str:
    """Apply static quantization to ONNX model.

    Args:
        model_path: Path to ONNX model
        calibration_data: Calibration data as list of input dicts
        output_path: Output path
        per_channel: Use per-channel quantization

    Returns:
        Path to quantized model
    """
    if not ONNX_QUANT_AVAILABLE:
        raise ImportError("ONNX Runtime quantization required")

    model_path = Path(model_path)
    if output_path is None:
        output_path = model_path.with_stem(model_path.stem + "_quant_static")
    output_path = Path(output_path)

    # Create calibration reader
    calibration_reader = ONNXCalibrationDataReader(calibration_data)

    onnx_quantize_static(
        str(model_path),
        str(output_path),
        calibration_reader,
        quant_format=QuantType.QInt8,
        per_channel=per_channel,
    )

    logger.info(f"ONNX static quantization complete: {output_path}")

    return str(output_path)


def benchmark_quantization(
    original_model: "nn.Module",
    quantized_model: Union["nn.Module", QuantizedModel],
    sample_input: "torch.Tensor",
    num_iterations: int = 100,
) -> QuantizationResult:
    """Benchmark original vs quantized model.

    Args:
        original_model: Original PyTorch model
        quantized_model: Quantized model
        sample_input: Sample input tensor
        num_iterations: Number of benchmark iterations

    Returns:
        QuantizationResult with comparison metrics
    """
    import time

    original_model.eval()
    if isinstance(quantized_model, QuantizedModel):
        quantized_model.eval()
    else:
        quantized_model.eval()

    # Measure sizes
    original_size = _calculate_model_size(original_model)
    if isinstance(quantized_model, QuantizedModel):
        quantized_size = quantized_model.quantized_size_mb
    else:
        quantized_size = _calculate_model_size(quantized_model)

    # Benchmark original
    with torch.no_grad():
        # Warmup
        for _ in range(10):
            original_model(sample_input)

        start = time.perf_counter()
        for _ in range(num_iterations):
            original_model(sample_input)
        original_time = (time.perf_counter() - start) / num_iterations * 1000

    # Benchmark quantized
    with torch.no_grad():
        # Warmup
        for _ in range(10):
            if isinstance(quantized_model, QuantizedModel):
                quantized_model(sample_input)
            else:
                quantized_model(sample_input)

        start = time.perf_counter()
        for _ in range(num_iterations):
            if isinstance(quantized_model, QuantizedModel):
                quantized_model(sample_input)
            else:
                quantized_model(sample_input)
        quantized_time = (time.perf_counter() - start) / num_iterations * 1000

    return QuantizationResult(
        original_size_mb=original_size,
        quantized_size_mb=quantized_size,
        compression_ratio=original_size / quantized_size,
        original_latency_ms=original_time,
        quantized_latency_ms=quantized_time,
        speedup=original_time / quantized_time,
    )
