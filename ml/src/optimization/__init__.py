"""Model optimization utilities for SHAKTI-CHAIN ML.

Provides:
- ONNX conversion for portable inference
- TensorRT optimization for GPU inference
- Quantization (FP16/INT8) for reduced memory and faster inference
- Model distillation for smaller, faster models
"""

from .onnx_converter import ONNXConverter, convert_to_onnx
from .quantization import (
    QuantizationConfig,
    quantize_model,
    quantize_dynamic,
    quantize_static,
)
from .tensorrt_optimizer import TensorRTOptimizer
from .distillation import ModelDistiller, DistillationConfig
from .inference_optimizer import (
    InferenceOptimizer,
    OptimizedModel,
    optimize_for_inference,
)

__all__ = [
    # ONNX
    "ONNXConverter",
    "convert_to_onnx",
    # Quantization
    "QuantizationConfig",
    "quantize_model",
    "quantize_dynamic",
    "quantize_static",
    # TensorRT
    "TensorRTOptimizer",
    # Distillation
    "ModelDistiller",
    "DistillationConfig",
    # Inference
    "InferenceOptimizer",
    "OptimizedModel",
    "optimize_for_inference",
]
