"""Configuration settings for ML Service."""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of workers")
    debug: bool = Field(default=False, description="Debug mode")

    # CORS settings
    cors_origins: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )

    # MLflow settings
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000",
        description="MLflow tracking server URI"
    )
    mlflow_registry_uri: str = Field(
        default="http://localhost:5000",
        description="MLflow model registry URI"
    )

    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # Model settings
    max_memory_models: int = Field(
        default=10,
        description="Maximum models to keep in memory"
    )
    warmup_on_startup: bool = Field(
        default=True,
        description="Pre-load models on startup"
    )
    model_cache_ttl: int = Field(
        default=3600,
        description="Model cache TTL in seconds"
    )

    # A/B Testing settings
    ab_test_enabled: bool = Field(
        default=True,
        description="Enable A/B testing"
    )
    challenger_traffic_pct: float = Field(
        default=0.1,
        description="Percentage of traffic to challenger model"
    )

    # Latency targets (ms)
    forecast_latency_target_ms: int = Field(default=200)
    trading_latency_target_ms: int = Field(default=50)
    anomaly_latency_target_ms: int = Field(default=100)

    # Feature flags
    enable_drift_detection: bool = Field(default=True)
    enable_explanation: bool = Field(default=True)

    class Config:
        env_file = ".env"
        env_prefix = "ML_SERVICE_"


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
