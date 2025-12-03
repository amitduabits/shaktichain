"""Feature serving API for model service integration.

Provides:
- REST API for feature retrieval
- Point-in-time feature vectors
- Batch feature fetching
- Feature freshness validation
- Fallback to last-known values
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from .store import (
    FeatureStore,
    FeatureKey,
    FeatureValue,
    FeatureCategory,
)

logger = logging.getLogger(__name__)


class FeatureStatus(Enum):
    """Status of feature retrieval."""
    FRESH = "fresh"
    STALE = "stale"
    FALLBACK = "fallback"
    MISSING = "missing"


@dataclass
class FeatureVector:
    """A vector of features for model input."""
    features: Dict[str, Any]
    timestamp: datetime
    status: Dict[str, FeatureStatus] = field(default_factory=dict)
    latency_ms: float = 0.0

    @property
    def is_complete(self) -> bool:
        """Check if all features are present."""
        return FeatureStatus.MISSING not in self.status.values()

    @property
    def is_fresh(self) -> bool:
        """Check if all features are fresh."""
        return all(s == FeatureStatus.FRESH for s in self.status.values())

    @property
    def stale_features(self) -> List[str]:
        """Get list of stale features."""
        return [k for k, v in self.status.items() if v == FeatureStatus.STALE]

    @property
    def missing_features(self) -> List[str]:
        """Get list of missing features."""
        return [k for k, v in self.status.items() if v == FeatureStatus.MISSING]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "features": self.features,
            "timestamp": self.timestamp.isoformat(),
            "status": {k: v.value for k, v in self.status.items()},
            "is_complete": self.is_complete,
            "is_fresh": self.is_fresh,
            "latency_ms": self.latency_ms,
        }


@dataclass
class FeatureSpec:
    """Specification for a feature to retrieve."""
    name: str
    entity_type: str = "global"
    entity_id: str = "default"
    default_value: Any = None
    max_staleness_seconds: float = 60.0
    required: bool = True


@dataclass
class FeatureSet:
    """A named set of features for a specific use case."""
    name: str
    features: List[FeatureSpec]
    description: str = ""

    def get_keys(self, entity_id: Optional[str] = None) -> List[FeatureKey]:
        """Get feature keys for this set."""
        keys = []
        for spec in self.features:
            keys.append(FeatureKey(
                name=spec.name,
                entity_type=spec.entity_type,
                entity_id=entity_id or spec.entity_id,
            ))
        return keys


class FeatureServer:
    """Serve features to model service with freshness guarantees."""

    # Default feature sets for different models
    TRADING_FEATURES = FeatureSet(
        name="trading",
        description="Features for trading agent",
        features=[
            FeatureSpec("spot_price", "market", "spot", default_value=0.0, max_staleness_seconds=5),
            FeatureSpec("price_velocity_1m", "market", "spot", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("price_velocity_5m", "market", "spot", default_value=0.0, max_staleness_seconds=300),
            FeatureSpec("volatility_1h", "market", "spot", default_value=0.0, max_staleness_seconds=300),
            FeatureSpec("vwap_1h", "market", "spot", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("order_imbalance", "market", "spot", default_value=0.0, max_staleness_seconds=10),
            FeatureSpec("trade_count_1h", "market", "spot", default_value=0, max_staleness_seconds=60),
            FeatureSpec("volume_1h", "market", "spot", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("grid_load", "grid", "default", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("grid_frequency", "grid", "default", default_value=50.0, max_staleness_seconds=30),
        ]
    )

    FORECAST_FEATURES = FeatureSet(
        name="forecast",
        description="Features for load/price forecasting",
        features=[
            FeatureSpec("grid_load", "grid", "default", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("grid_frequency", "grid", "default", default_value=50.0, max_staleness_seconds=60),
            FeatureSpec("temperature", "weather", "default", default_value=20.0, max_staleness_seconds=300),
            FeatureSpec("humidity", "weather", "default", default_value=50.0, max_staleness_seconds=300),
            FeatureSpec("solar_irradiance", "weather", "default", default_value=0.0, max_staleness_seconds=300),
            FeatureSpec("spot_price", "market", "spot", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("price_mean_24h", "market", "spot", default_value=0.0, max_staleness_seconds=3600),
            FeatureSpec("load_mean_24h", "grid", "default", default_value=0.0, max_staleness_seconds=3600),
            FeatureSpec("hour_of_day", "time", "default", default_value=12, max_staleness_seconds=3600),
            FeatureSpec("day_of_week", "time", "default", default_value=0, max_staleness_seconds=86400),
        ]
    )

    ANOMALY_FEATURES = FeatureSet(
        name="anomaly",
        description="Features for anomaly detection",
        features=[
            FeatureSpec("spot_price", "market", "spot", default_value=0.0, max_staleness_seconds=10),
            FeatureSpec("price_velocity_1m", "market", "spot", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("volatility_1h", "market", "spot", default_value=0.0, max_staleness_seconds=300),
            FeatureSpec("trade_count_1h", "market", "spot", default_value=0, max_staleness_seconds=60),
            FeatureSpec("volume_1h", "market", "spot", default_value=0.0, max_staleness_seconds=60),
            FeatureSpec("order_imbalance", "market", "spot", default_value=0.0, max_staleness_seconds=10),
            FeatureSpec("grid_frequency", "grid", "default", default_value=50.0, max_staleness_seconds=30),
            FeatureSpec("grid_load", "grid", "default", default_value=0.0, max_staleness_seconds=60),
        ]
    )

    def __init__(
        self,
        store: FeatureStore,
        timeout_seconds: float = 1.0,
        enable_fallback: bool = True,
    ):
        """Initialize feature server.

        Args:
            store: Feature store backend
            timeout_seconds: Timeout for feature retrieval
            enable_fallback: Enable fallback to default values
        """
        self.store = store
        self.timeout_seconds = timeout_seconds
        self.enable_fallback = enable_fallback

        # Feature sets
        self._feature_sets: Dict[str, FeatureSet] = {
            "trading": self.TRADING_FEATURES,
            "forecast": self.FORECAST_FEATURES,
            "anomaly": self.ANOMALY_FEATURES,
        }

        # Last known values for fallback
        self._last_known: Dict[str, FeatureValue] = {}

        # Statistics
        self._stats = {
            "requests": 0,
            "hits": 0,
            "misses": 0,
            "stale": 0,
            "fallbacks": 0,
            "timeouts": 0,
            "total_latency_ms": 0.0,
        }

    def register_feature_set(self, feature_set: FeatureSet):
        """Register a custom feature set."""
        self._feature_sets[feature_set.name] = feature_set

    async def get_features(
        self,
        feature_set_name: str,
        entity_id: Optional[str] = None,
        point_in_time: Optional[datetime] = None,
    ) -> FeatureVector:
        """Get features for a named feature set.

        Args:
            feature_set_name: Name of the feature set
            entity_id: Optional entity ID override
            point_in_time: Optional point-in-time for historical lookup

        Returns:
            FeatureVector with features and status
        """
        start_time = time.perf_counter()
        self._stats["requests"] += 1

        feature_set = self._feature_sets.get(feature_set_name)
        if not feature_set:
            raise ValueError(f"Unknown feature set: {feature_set_name}")

        features = {}
        status = {}

        try:
            # Get all features with timeout
            result = await asyncio.wait_for(
                self._fetch_features(feature_set, entity_id, point_in_time),
                timeout=self.timeout_seconds,
            )
            features, status = result

        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching features for {feature_set_name}")
            self._stats["timeouts"] += 1

            # Use fallbacks on timeout
            if self.enable_fallback:
                features, status = self._get_fallbacks(feature_set)

        latency_ms = (time.perf_counter() - start_time) * 1000
        self._stats["total_latency_ms"] += latency_ms

        return FeatureVector(
            features=features,
            timestamp=point_in_time or datetime.now(),
            status=status,
            latency_ms=latency_ms,
        )

    async def _fetch_features(
        self,
        feature_set: FeatureSet,
        entity_id: Optional[str],
        point_in_time: Optional[datetime],
    ) -> tuple[Dict[str, Any], Dict[str, FeatureStatus]]:
        """Fetch features from store."""
        features = {}
        status = {}

        # Build keys
        keys = []
        specs_by_key = {}
        for spec in feature_set.features:
            key = FeatureKey(
                name=spec.name,
                entity_type=spec.entity_type,
                entity_id=entity_id or spec.entity_id,
            )
            keys.append(key)
            specs_by_key[key.to_redis_key()] = spec

        # Fetch all at once
        values = await self.store.get_many(keys)

        # Process results
        for spec in feature_set.features:
            key = FeatureKey(
                name=spec.name,
                entity_type=spec.entity_type,
                entity_id=entity_id or spec.entity_id,
            )
            redis_key = key.to_redis_key()
            value = values.get(redis_key)

            if value is None:
                self._stats["misses"] += 1

                # Try fallback
                if self.enable_fallback:
                    fallback = self._last_known.get(redis_key)
                    if fallback:
                        features[spec.name] = fallback.value
                        status[spec.name] = FeatureStatus.FALLBACK
                        self._stats["fallbacks"] += 1
                    elif spec.default_value is not None:
                        features[spec.name] = spec.default_value
                        status[spec.name] = FeatureStatus.FALLBACK
                        self._stats["fallbacks"] += 1
                    else:
                        status[spec.name] = FeatureStatus.MISSING
                else:
                    status[spec.name] = FeatureStatus.MISSING
            else:
                self._stats["hits"] += 1

                # Check staleness
                value.check_staleness(spec.max_staleness_seconds)

                if value.is_stale:
                    self._stats["stale"] += 1
                    status[spec.name] = FeatureStatus.STALE
                else:
                    status[spec.name] = FeatureStatus.FRESH

                features[spec.name] = value.value

                # Update last known
                self._last_known[redis_key] = value

        return features, status

    def _get_fallbacks(
        self,
        feature_set: FeatureSet,
    ) -> tuple[Dict[str, Any], Dict[str, FeatureStatus]]:
        """Get fallback values for all features."""
        features = {}
        status = {}

        for spec in feature_set.features:
            key = FeatureKey(
                name=spec.name,
                entity_type=spec.entity_type,
                entity_id=spec.entity_id,
            )
            redis_key = key.to_redis_key()

            # Try last known
            fallback = self._last_known.get(redis_key)
            if fallback:
                features[spec.name] = fallback.value
                status[spec.name] = FeatureStatus.FALLBACK
            elif spec.default_value is not None:
                features[spec.name] = spec.default_value
                status[spec.name] = FeatureStatus.FALLBACK
            else:
                status[spec.name] = FeatureStatus.MISSING

        return features, status

    async def get_single_feature(
        self,
        feature_name: str,
        entity_type: str = "global",
        entity_id: str = "default",
        default_value: Any = None,
    ) -> tuple[Any, FeatureStatus]:
        """Get a single feature value.

        Args:
            feature_name: Name of the feature
            entity_type: Entity type
            entity_id: Entity ID
            default_value: Default value if not found

        Returns:
            Tuple of (value, status)
        """
        key = FeatureKey(
            name=feature_name,
            entity_type=entity_type,
            entity_id=entity_id,
        )

        try:
            value = await asyncio.wait_for(
                self.store.get(key),
                timeout=self.timeout_seconds,
            )

            if value is None:
                if default_value is not None:
                    return default_value, FeatureStatus.FALLBACK
                return None, FeatureStatus.MISSING

            value.check_staleness()

            if value.is_stale:
                return value.value, FeatureStatus.STALE

            return value.value, FeatureStatus.FRESH

        except asyncio.TimeoutError:
            if default_value is not None:
                return default_value, FeatureStatus.FALLBACK
            return None, FeatureStatus.MISSING

    async def get_batch_features(
        self,
        requests: List[Dict[str, Any]],
    ) -> List[FeatureVector]:
        """Get features for multiple requests in batch.

        Args:
            requests: List of request dicts with feature_set, entity_id keys

        Returns:
            List of FeatureVectors
        """
        tasks = []
        for req in requests:
            task = self.get_features(
                feature_set_name=req.get("feature_set", "trading"),
                entity_id=req.get("entity_id"),
                point_in_time=req.get("point_in_time"),
            )
            tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def get_point_in_time_features(
        self,
        feature_set_name: str,
        timestamps: List[datetime],
        entity_id: Optional[str] = None,
    ) -> List[FeatureVector]:
        """Get features at multiple points in time.

        Useful for backtesting and training data generation.

        Args:
            feature_set_name: Name of feature set
            timestamps: List of timestamps
            entity_id: Optional entity ID

        Returns:
            List of FeatureVectors at each timestamp
        """
        tasks = []
        for ts in timestamps:
            task = self.get_features(
                feature_set_name=feature_set_name,
                entity_id=entity_id,
                point_in_time=ts,
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    def get_stats(self) -> Dict[str, Any]:
        """Get serving statistics."""
        total_requests = max(self._stats["requests"], 1)

        return {
            **self._stats,
            "hit_rate": self._stats["hits"] / max(self._stats["hits"] + self._stats["misses"], 1),
            "stale_rate": self._stats["stale"] / total_requests,
            "fallback_rate": self._stats["fallbacks"] / total_requests,
            "timeout_rate": self._stats["timeouts"] / total_requests,
            "avg_latency_ms": self._stats["total_latency_ms"] / total_requests,
            "feature_sets": list(self._feature_sets.keys()),
        }


# FastAPI integration
try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


if HAS_FASTAPI:

    class FeatureRequest(BaseModel):
        """Request for features."""
        feature_set: str = Field(default="trading", description="Feature set name")
        entity_id: Optional[str] = Field(default=None, description="Entity ID")
        point_in_time: Optional[datetime] = Field(default=None, description="Point in time")

    class BatchFeatureRequest(BaseModel):
        """Batch feature request."""
        requests: List[FeatureRequest]

    class FeatureResponse(BaseModel):
        """Feature response."""
        features: Dict[str, Any]
        timestamp: str
        status: Dict[str, str]
        is_complete: bool
        is_fresh: bool
        latency_ms: float

    class HealthResponse(BaseModel):
        """Health check response."""
        status: str
        stats: Dict[str, Any]

    def create_feature_router(server: FeatureServer) -> "APIRouter":
        """Create FastAPI router for feature serving.

        Args:
            server: FeatureServer instance

        Returns:
            FastAPI router
        """
        router = APIRouter(prefix="/features", tags=["features"])

        @router.get("/health", response_model=HealthResponse)
        async def health():
            """Health check endpoint."""
            return HealthResponse(
                status="healthy",
                stats=server.get_stats(),
            )

        @router.post("/get", response_model=FeatureResponse)
        async def get_features(request: FeatureRequest):
            """Get features for a feature set."""
            try:
                vector = await server.get_features(
                    feature_set_name=request.feature_set,
                    entity_id=request.entity_id,
                    point_in_time=request.point_in_time,
                )
                return FeatureResponse(**vector.to_dict())
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @router.post("/batch", response_model=List[FeatureResponse])
        async def get_batch_features(request: BatchFeatureRequest):
            """Get features for multiple requests."""
            try:
                vectors = await server.get_batch_features(
                    [r.model_dump() for r in request.requests]
                )
                responses = []
                for v in vectors:
                    if isinstance(v, Exception):
                        responses.append(FeatureResponse(
                            features={},
                            timestamp=datetime.now().isoformat(),
                            status={},
                            is_complete=False,
                            is_fresh=False,
                            latency_ms=0,
                        ))
                    else:
                        responses.append(FeatureResponse(**v.to_dict()))
                return responses
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @router.get("/single/{feature_name}")
        async def get_single_feature(
            feature_name: str,
            entity_type: str = Query(default="global"),
            entity_id: str = Query(default="default"),
        ):
            """Get a single feature value."""
            value, status = await server.get_single_feature(
                feature_name=feature_name,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            return {
                "feature": feature_name,
                "value": value,
                "status": status.value,
            }

        @router.get("/sets")
        async def list_feature_sets():
            """List available feature sets."""
            return {
                name: {
                    "description": fs.description,
                    "features": [f.name for f in fs.features],
                }
                for name, fs in server._feature_sets.items()
            }

        @router.get("/stats")
        async def get_stats():
            """Get serving statistics."""
            return server.get_stats()

        return router


class FeatureClient:
    """Client for consuming features from the feature server.

    Used by model service to fetch features via HTTP.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout_seconds: float = 1.0,
    ):
        """Initialize client.

        Args:
            base_url: Feature server URL
            timeout_seconds: Request timeout
        """
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._session = None

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None:
            try:
                import aiohttp
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
                )
            except ImportError:
                raise RuntimeError("aiohttp is required for FeatureClient")
        return self._session

    async def close(self):
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def get_features(
        self,
        feature_set: str,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get features from server.

        Args:
            feature_set: Feature set name
            entity_id: Optional entity ID

        Returns:
            Feature response dict
        """
        session = await self._get_session()

        payload = {
            "feature_set": feature_set,
            "entity_id": entity_id,
        }

        async with session.post(
            f"{self.base_url}/features/get",
            json=payload,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_trading_features(
        self,
        market: str = "spot",
    ) -> Dict[str, Any]:
        """Get trading features.

        Args:
            market: Market ID

        Returns:
            Trading features
        """
        return await self.get_features("trading", market)

    async def get_forecast_features(self) -> Dict[str, Any]:
        """Get forecast features."""
        return await self.get_features("forecast")

    async def get_anomaly_features(self) -> Dict[str, Any]:
        """Get anomaly detection features."""
        return await self.get_features("anomaly")

    async def health_check(self) -> bool:
        """Check if feature server is healthy."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/features/health") as response:
                return response.status == 200
        except Exception:
            return False
