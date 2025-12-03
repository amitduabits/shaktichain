"""Health check utilities for SHAKTI-CHAIN ML service.

Provides:
- Service health checks
- Dependency health checks
- Readiness and liveness probes
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    last_checked: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_checked": self.last_checked.isoformat(),
            "details": self.details,
        }


@dataclass
class ServiceHealth:
    """Overall service health status."""

    status: HealthStatus
    version: str
    uptime_seconds: float
    components: List[ComponentHealth]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat(),
            "components": [c.to_dict() for c in self.components],
        }


class HealthChecker:
    """Service health checker.

    Manages health checks for all service components and dependencies.

    Example:
        >>> checker = HealthChecker(version="1.0.0")
        >>> checker.add_check("redis", redis_health_check)
        >>> checker.add_check("model", model_health_check)
        >>> health = await checker.check_all()
        >>> print(health.status)
    """

    def __init__(
        self,
        version: str = "1.0.0",
        startup_time: Optional[datetime] = None,
    ):
        """Initialize health checker.

        Args:
            version: Service version
            startup_time: Service startup time
        """
        self.version = version
        self.startup_time = startup_time or datetime.now()
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, ComponentHealth] = {}
        self._cache_ttl = timedelta(seconds=5)
        self._last_check_time: Optional[datetime] = None

    def add_check(
        self,
        name: str,
        check_fn: Callable[[], ComponentHealth],
        critical: bool = False,
    ):
        """Add a health check.

        Args:
            name: Component name
            check_fn: Function that returns ComponentHealth
            critical: If True, failure makes service unhealthy
        """
        self._checks[name] = (check_fn, critical)

    def remove_check(self, name: str):
        """Remove a health check."""
        self._checks.pop(name, None)
        self._last_results.pop(name, None)

    async def check_all(self, use_cache: bool = True) -> ServiceHealth:
        """Run all health checks.

        Args:
            use_cache: Use cached results if recent

        Returns:
            ServiceHealth with all component statuses
        """
        now = datetime.now()

        # Use cache if recent
        if (
            use_cache and
            self._last_check_time and
            now - self._last_check_time < self._cache_ttl
        ):
            return self._build_service_health()

        # Run checks concurrently
        tasks = []
        for name, (check_fn, critical) in self._checks.items():
            tasks.append(self._run_check(name, check_fn, critical))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, ComponentHealth):
                self._last_results[result.name] = result
            elif isinstance(result, Exception):
                logger.error(f"Health check failed: {result}")

        self._last_check_time = now

        return self._build_service_health()

    async def _run_check(
        self,
        name: str,
        check_fn: Callable,
        critical: bool,
    ) -> ComponentHealth:
        """Run a single health check with timing."""
        start = time.perf_counter()

        try:
            if asyncio.iscoroutinefunction(check_fn):
                result = await asyncio.wait_for(check_fn(), timeout=5.0)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, check_fn
                )

            result.latency_ms = (time.perf_counter() - start) * 1000
            result.last_checked = datetime.now()

            return result

        except asyncio.TimeoutError:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message="Health check timed out",
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        except Exception as e:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    def _build_service_health(self) -> ServiceHealth:
        """Build overall service health from component results."""
        components = list(self._last_results.values())

        # Determine overall status
        has_unhealthy = any(
            c.status == HealthStatus.UNHEALTHY
            for c in components
            if self._checks.get(c.name, (None, False))[1]  # Critical checks
        )

        has_degraded = any(
            c.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
            for c in components
        )

        if has_unhealthy:
            overall_status = HealthStatus.UNHEALTHY
        elif has_degraded:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        uptime = (datetime.now() - self.startup_time).total_seconds()

        return ServiceHealth(
            status=overall_status,
            version=self.version,
            uptime_seconds=uptime,
            components=components,
        )

    async def check_readiness(self) -> bool:
        """Check if service is ready to receive traffic.

        Returns:
            True if ready
        """
        health = await self.check_all()
        return health.status != HealthStatus.UNHEALTHY

    async def check_liveness(self) -> bool:
        """Check if service is alive (not deadlocked).

        Returns:
            True if alive
        """
        # Simple liveness check - just verify we can respond
        return True

    def get_cached_health(self) -> Optional[ServiceHealth]:
        """Get cached health without running checks."""
        if not self._last_results:
            return None
        return self._build_service_health()


# Pre-built health check functions

async def check_redis_health(redis_client) -> ComponentHealth:
    """Check Redis connection health."""
    try:
        start = time.perf_counter()
        await redis_client.ping()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="redis",
            status=HealthStatus.HEALTHY,
            message="Connected",
            latency_ms=latency,
            details={"connected": True},
        )

    except Exception as e:
        return ComponentHealth(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=f"Connection failed: {str(e)}",
            details={"connected": False, "error": str(e)},
        )


async def check_database_health(db_pool) -> ComponentHealth:
    """Check database connection health."""
    try:
        start = time.perf_counter()
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        latency = (time.perf_counter() - start) * 1000

        pool_size = db_pool.get_size()
        pool_free = db_pool.get_idle_size()

        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connected",
            latency_ms=latency,
            details={
                "pool_size": pool_size,
                "pool_free": pool_free,
                "pool_utilization": (pool_size - pool_free) / pool_size if pool_size > 0 else 0,
            },
        )

    except Exception as e:
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Connection failed: {str(e)}",
        )


def check_model_health(model_loader) -> ComponentHealth:
    """Check model loading health."""
    try:
        loaded_models = model_loader.get_loaded_models()
        total_models = len(loaded_models)
        healthy_models = sum(1 for m in loaded_models.values() if m.get("status") == "loaded")

        if total_models == 0:
            return ComponentHealth(
                name="models",
                status=HealthStatus.DEGRADED,
                message="No models loaded",
            )

        if healthy_models < total_models:
            return ComponentHealth(
                name="models",
                status=HealthStatus.DEGRADED,
                message=f"{healthy_models}/{total_models} models loaded",
                details={"loaded": healthy_models, "total": total_models},
            )

        return ComponentHealth(
            name="models",
            status=HealthStatus.HEALTHY,
            message=f"All {total_models} models loaded",
            details={"models": list(loaded_models.keys())},
        )

    except Exception as e:
        return ComponentHealth(
            name="models",
            status=HealthStatus.UNHEALTHY,
            message=f"Model check failed: {str(e)}",
        )


def check_memory_health(threshold_mb: float = 4000) -> ComponentHealth:
    """Check memory usage health."""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)

        if memory_mb > threshold_mb:
            status = HealthStatus.DEGRADED
            message = f"High memory usage: {memory_mb:.0f} MB"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory usage: {memory_mb:.0f} MB"

        return ComponentHealth(
            name="memory",
            status=status,
            message=message,
            details={
                "rss_mb": memory_mb,
                "threshold_mb": threshold_mb,
                "utilization": memory_mb / threshold_mb,
            },
        )

    except ImportError:
        return ComponentHealth(
            name="memory",
            status=HealthStatus.HEALTHY,
            message="psutil not available",
        )


def check_disk_health(path: str = "/", threshold_pct: float = 90) -> ComponentHealth:
    """Check disk usage health."""
    try:
        import psutil
        usage = psutil.disk_usage(path)
        used_pct = usage.percent

        if used_pct > threshold_pct:
            status = HealthStatus.DEGRADED
            message = f"High disk usage: {used_pct:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Disk usage: {used_pct:.1f}%"

        return ComponentHealth(
            name="disk",
            status=status,
            message=message,
            details={
                "used_pct": used_pct,
                "free_gb": usage.free / (1024 ** 3),
                "total_gb": usage.total / (1024 ** 3),
            },
        )

    except ImportError:
        return ComponentHealth(
            name="disk",
            status=HealthStatus.HEALTHY,
            message="psutil not available",
        )


def check_gpu_health() -> ComponentHealth:
    """Check GPU health (if available)."""
    try:
        import torch
        if not torch.cuda.is_available():
            return ComponentHealth(
                name="gpu",
                status=HealthStatus.HEALTHY,
                message="No GPU available (CPU mode)",
            )

        device_count = torch.cuda.device_count()
        memory_info = []

        for i in range(device_count):
            props = torch.cuda.get_device_properties(i)
            allocated = torch.cuda.memory_allocated(i) / (1024 ** 3)
            reserved = torch.cuda.memory_reserved(i) / (1024 ** 3)
            total = props.total_memory / (1024 ** 3)

            memory_info.append({
                "device": i,
                "name": props.name,
                "allocated_gb": allocated,
                "reserved_gb": reserved,
                "total_gb": total,
                "utilization": allocated / total,
            })

        # Check if any GPU is highly utilized
        max_util = max(m["utilization"] for m in memory_info)

        if max_util > 0.95:
            status = HealthStatus.DEGRADED
            message = f"High GPU memory: {max_util:.1%}"
        else:
            status = HealthStatus.HEALTHY
            message = f"{device_count} GPU(s) available"

        return ComponentHealth(
            name="gpu",
            status=status,
            message=message,
            details={"devices": memory_info},
        )

    except ImportError:
        return ComponentHealth(
            name="gpu",
            status=HealthStatus.HEALTHY,
            message="PyTorch not available",
        )


async def check_mlflow_health(tracking_uri: str) -> ComponentHealth:
    """Check MLflow tracking server health."""
    try:
        import aiohttp

        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{tracking_uri}/health",
                timeout=5,
            ) as response:
                latency = (time.perf_counter() - start) * 1000

                if response.status == 200:
                    return ComponentHealth(
                        name="mlflow",
                        status=HealthStatus.HEALTHY,
                        message="Connected",
                        latency_ms=latency,
                    )
                else:
                    return ComponentHealth(
                        name="mlflow",
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP {response.status}",
                        latency_ms=latency,
                    )

    except Exception as e:
        return ComponentHealth(
            name="mlflow",
            status=HealthStatus.UNHEALTHY,
            message=f"Connection failed: {str(e)}",
        )
