# SHAKTI-CHAIN TFT Training Container
# Multi-stage build for optimized image size

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.10-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install pytorch-lightning mlflow optuna hydra-core omegaconf && \
    pip install pandas numpy scikit-learn pyarrow && \
    pip install rich tqdm pyyaml

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.10-slim as runtime

# Labels
LABEL maintainer="SHAKTI-CHAIN Team" \
    version="1.0.0" \
    description="SHAKTI-CHAIN TFT Model Training Container"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

# Create directories for data and outputs
RUN mkdir -p /app/data/raw \
    /app/data/processed \
    /app/checkpoints \
    /app/mlruns \
    /app/logs

# Set default volume mounts
VOLUME ["/app/data", "/app/checkpoints", "/app/mlruns"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import torch; import pytorch_lightning; print('OK')" || exit 1

# Default command: run training
CMD ["python", "scripts/train_tft.py"]

# =============================================================================
# Stage 3: GPU Runtime (optional)
# =============================================================================
FROM nvidia/cuda:11.8-runtime-ubuntu22.04 as gpu-runtime

# Labels
LABEL maintainer="SHAKTI-CHAIN Team" \
    version="1.0.0" \
    description="SHAKTI-CHAIN TFT Model Training Container (GPU)"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    DEBIAN_FRONTEND=noninteractive

# Install Python and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-venv \
    python3-pip \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies with CUDA support
RUN pip install --upgrade pip && \
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 && \
    pip install pytorch-lightning mlflow optuna hydra-core omegaconf && \
    pip install pandas numpy scikit-learn pyarrow && \
    pip install rich tqdm pyyaml

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

# Create directories
RUN mkdir -p /app/data/raw \
    /app/data/processed \
    /app/checkpoints \
    /app/mlruns \
    /app/logs

# Set default volume mounts
VOLUME ["/app/data", "/app/checkpoints", "/app/mlruns"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')" || exit 1

# Default command: run training
CMD ["python", "scripts/train_tft.py"]
