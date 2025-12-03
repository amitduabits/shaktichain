"""SHAKTI-CHAIN ML Model Serving API.

FastAPI application for serving:
- Load and price forecasting
- Trading action recommendations
- Anomaly detection scoring

Features:
- Model loading from MLflow registry
- In-memory caching with Redis
- A/B testing support
- Prometheus metrics
- Health checks and graceful shutdown
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge

from app.routers import forecast, trading, anomaly
from app.models.model_loader import ModelLoader
from app.models.model_cache import ModelCache
from app.utils.config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'ml_service_requests_total',
    'Total request count',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'ml_service_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.2, 0.5, 1.0, 2.5]
)

MODEL_LOAD_TIME = Histogram(
    'ml_service_model_load_seconds',
    'Model loading time in seconds',
    ['model_type']
)

ACTIVE_MODELS = Gauge(
    'ml_service_active_models',
    'Number of active models in cache',
    ['model_type']
)

PREDICTION_DISTRIBUTION = Histogram(
    'ml_service_prediction_distribution',
    'Distribution of prediction values',
    ['model_type', 'metric'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    logger.info("Starting SHAKTI-CHAIN ML Service...")

    # Initialize model loader and cache
    app.state.model_loader = ModelLoader(
        mlflow_tracking_uri=settings.mlflow_tracking_uri,
        mlflow_registry_uri=settings.mlflow_registry_uri,
    )
    app.state.model_cache = ModelCache(
        redis_url=settings.redis_url,
        max_memory_models=settings.max_memory_models,
    )

    # Warm up models
    if settings.warmup_on_startup:
        logger.info("Warming up models...")
        await warmup_models(app)

    logger.info("ML Service started successfully")
    yield

    # Shutdown
    logger.info("Shutting down ML Service...")
    await app.state.model_cache.close()
    logger.info("ML Service shutdown complete")


async def warmup_models(app: FastAPI):
    """Pre-load frequently used models."""
    warmup_configs = [
        ("forecast_load", "production", "tft"),
        ("forecast_price", "production", "ensemble"),
        ("trading_agent", "production", "ppo"),
        ("anomaly_detector", "production", "isolation_forest"),
    ]

    for model_name, stage, model_type in warmup_configs:
        try:
            start = time.time()
            await app.state.model_loader.load_model(model_name, stage)
            duration = time.time() - start
            MODEL_LOAD_TIME.labels(model_type=model_type).observe(duration)
            logger.info(f"Loaded {model_name} ({stage}) in {duration:.2f}s")
        except Exception as e:
            logger.warning(f"Failed to warmup {model_name}: {e}")


# Create FastAPI app
app = FastAPI(
    title="SHAKTI-CHAIN ML Service",
    description="ML model serving for V2G energy trading platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_metrics(request: Request, call_next):
    """Add timing and metrics to all requests."""
    start_time = time.time()

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        raise
    finally:
        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method

        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    # Add timing header
    response.headers["X-Response-Time"] = f"{duration:.4f}s"
    return response


# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Include routers
app.include_router(forecast.router, prefix="/forecast", tags=["Forecast"])
app.include_router(trading.router, prefix="/trading", tags=["Trading"])
app.include_router(anomaly.router, prefix="/anomaly", tags=["Anomaly"])


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "SHAKTI-CHAIN ML Service",
        "version": "1.0.0",
        "status": "healthy",
        "endpoints": {
            "forecast": "/forecast",
            "trading": "/trading",
            "anomaly": "/anomaly",
            "metrics": "/metrics",
            "health": "/health",
        }
    }


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "components": {}
    }

    # Check model cache
    try:
        cache_status = await request.app.state.model_cache.health_check()
        health_status["components"]["cache"] = cache_status
    except Exception as e:
        health_status["components"]["cache"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    # Check model loader
    try:
        loader_status = await request.app.state.model_loader.health_check()
        health_status["components"]["model_loader"] = loader_status
    except Exception as e:
        health_status["components"]["model_loader"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/ready")
async def readiness_check(request: Request):
    """Readiness check for Kubernetes."""
    # Check if critical models are loaded
    required_models = ["forecast_load", "trading_agent"]

    for model_name in required_models:
        if not await request.app.state.model_cache.is_loaded(model_name):
            return JSONResponse(
                content={"ready": False, "reason": f"Model {model_name} not loaded"},
                status_code=503
            )

    return {"ready": True}


@app.get("/models")
async def list_models(request: Request):
    """List all available models."""
    return await request.app.state.model_loader.list_models()


@app.post("/models/reload")
async def reload_models(request: Request):
    """Force reload all models."""
    await request.app.state.model_cache.clear()
    await warmup_models(request.app)
    return {"status": "reloaded"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers,
    )
