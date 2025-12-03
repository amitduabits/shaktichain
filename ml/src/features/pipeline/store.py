"""Feature store for real-time and historical features.

Provides:
- Redis-based real-time feature storage with TTL
- Feature versioning and timestamps
- Point-in-time feature retrieval
- Feature freshness tracking
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)

# Optional Redis import
try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class FeatureCategory(Enum):
    """Categories of features."""
    REAL_TIME = "realtime"      # Updated on each event
    ROLLING = "rolling"          # Rolling window statistics
    SCHEDULED = "scheduled"      # Periodically refreshed
    HISTORICAL = "historical"    # From batch processing
    DERIVED = "derived"          # Computed from other features


@dataclass
class FeatureKey:
    """Unique identifier for a feature."""
    name: str
    entity_type: str = "global"    # global, market, account, etc.
    entity_id: str = "default"     # Specific entity ID
    version: str = "v1"

    def to_redis_key(self) -> str:
        """Convert to Redis key string."""
        return f"feature:{self.entity_type}:{self.entity_id}:{self.name}:{self.version}"

    @classmethod
    def from_redis_key(cls, key: str) -> 'FeatureKey':
        """Parse from Redis key string."""
        parts = key.split(':')
        if len(parts) >= 5:
            return cls(
                name=parts[3],
                entity_type=parts[1],
                entity_id=parts[2],
                version=parts[4] if len(parts) > 4 else "v1",
            )
        return cls(name=key)


@dataclass
class FeatureValue:
    """Feature value with metadata."""
    value: Any
    timestamp: datetime
    category: FeatureCategory = FeatureCategory.REAL_TIME
    ttl_seconds: Optional[int] = None
    source: str = "pipeline"
    version: str = "v1"

    # Quality indicators
    is_stale: bool = False
    staleness_seconds: float = 0.0
    quality: str = "good"  # good, estimated, missing

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category.value,
            'ttl_seconds': self.ttl_seconds,
            'source': self.source,
            'version': self.version,
            'quality': self.quality,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureValue':
        """Create from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        else:
            timestamp = datetime.now()

        category = data.get('category', 'realtime')
        try:
            category = FeatureCategory(category)
        except ValueError:
            category = FeatureCategory.REAL_TIME

        return cls(
            value=data.get('value'),
            timestamp=timestamp,
            category=category,
            ttl_seconds=data.get('ttl_seconds'),
            source=data.get('source', 'unknown'),
            version=data.get('version', 'v1'),
            quality=data.get('quality', 'good'),
        )

    def check_staleness(self, max_age_seconds: float = 60.0) -> 'FeatureValue':
        """Update staleness indicators."""
        age = (datetime.now() - self.timestamp).total_seconds()
        self.staleness_seconds = age
        self.is_stale = age > max_age_seconds
        return self


class FeatureStore(ABC):
    """Abstract feature store interface."""

    @abstractmethod
    async def set(
        self,
        key: FeatureKey,
        value: FeatureValue,
    ) -> bool:
        """Store a feature value."""
        pass

    @abstractmethod
    async def get(
        self,
        key: FeatureKey,
    ) -> Optional[FeatureValue]:
        """Retrieve a feature value."""
        pass

    @abstractmethod
    async def get_many(
        self,
        keys: List[FeatureKey],
    ) -> Dict[str, FeatureValue]:
        """Retrieve multiple feature values."""
        pass

    @abstractmethod
    async def delete(self, key: FeatureKey) -> bool:
        """Delete a feature."""
        pass

    @abstractmethod
    async def list_keys(
        self,
        pattern: str = "*",
    ) -> List[FeatureKey]:
        """List feature keys matching pattern."""
        pass


class InMemoryFeatureStore(FeatureStore):
    """In-memory feature store for testing."""

    def __init__(self):
        self._store: Dict[str, FeatureValue] = {}
        self._expiry: Dict[str, datetime] = {}

    async def set(
        self,
        key: FeatureKey,
        value: FeatureValue,
    ) -> bool:
        redis_key = key.to_redis_key()
        self._store[redis_key] = value

        if value.ttl_seconds:
            self._expiry[redis_key] = datetime.now() + timedelta(seconds=value.ttl_seconds)

        return True

    async def get(
        self,
        key: FeatureKey,
    ) -> Optional[FeatureValue]:
        redis_key = key.to_redis_key()

        # Check expiry
        if redis_key in self._expiry:
            if datetime.now() > self._expiry[redis_key]:
                del self._store[redis_key]
                del self._expiry[redis_key]
                return None

        value = self._store.get(redis_key)
        if value:
            value.check_staleness()
        return value

    async def get_many(
        self,
        keys: List[FeatureKey],
    ) -> Dict[str, FeatureValue]:
        result = {}
        for key in keys:
            value = await self.get(key)
            if value:
                result[key.name] = value
        return result

    async def delete(self, key: FeatureKey) -> bool:
        redis_key = key.to_redis_key()
        if redis_key in self._store:
            del self._store[redis_key]
            if redis_key in self._expiry:
                del self._expiry[redis_key]
            return True
        return False

    async def list_keys(
        self,
        pattern: str = "*",
    ) -> List[FeatureKey]:
        import fnmatch
        keys = []
        for key in self._store.keys():
            if fnmatch.fnmatch(key, f"feature:{pattern}"):
                keys.append(FeatureKey.from_redis_key(key))
        return keys


class RedisFeatureStore(FeatureStore):
    """Redis-based feature store with TTL support."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "shakti:features",
        default_ttl: int = 3600,
    ):
        """Initialize Redis feature store.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all feature keys
            default_ttl: Default TTL in seconds
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

        self._redis: Optional[Any] = None
        self._connected = False

    async def _ensure_connection(self) -> bool:
        """Ensure Redis connection is established."""
        if not HAS_REDIS:
            logger.warning("Redis not available")
            return False

        if self._redis is not None and self._connected:
            return True

        try:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis feature store")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._connected = False
            return False

    def _make_key(self, key: FeatureKey) -> str:
        """Create full Redis key with prefix."""
        return f"{self.key_prefix}:{key.to_redis_key()}"

    async def set(
        self,
        key: FeatureKey,
        value: FeatureValue,
    ) -> bool:
        """Store a feature value with optional TTL."""
        if not await self._ensure_connection():
            return False

        try:
            redis_key = self._make_key(key)
            data = json.dumps(value.to_dict())

            ttl = value.ttl_seconds or self.default_ttl
            await self._redis.setex(redis_key, ttl, data)

            # Also store in a sorted set for time-series queries
            score = value.timestamp.timestamp()
            await self._redis.zadd(
                f"{self.key_prefix}:timeline:{key.name}",
                {redis_key: score},
            )

            return True
        except Exception as e:
            logger.error(f"Failed to set feature: {e}")
            return False

    async def get(
        self,
        key: FeatureKey,
    ) -> Optional[FeatureValue]:
        """Retrieve a feature value."""
        if not await self._ensure_connection():
            return None

        try:
            redis_key = self._make_key(key)
            data = await self._redis.get(redis_key)

            if not data:
                return None

            value = FeatureValue.from_dict(json.loads(data))
            value.check_staleness()
            return value

        except Exception as e:
            logger.error(f"Failed to get feature: {e}")
            return None

    async def get_many(
        self,
        keys: List[FeatureKey],
    ) -> Dict[str, FeatureValue]:
        """Retrieve multiple feature values efficiently."""
        if not await self._ensure_connection():
            return {}

        try:
            redis_keys = [self._make_key(k) for k in keys]
            values = await self._redis.mget(redis_keys)

            result = {}
            for key, data in zip(keys, values):
                if data:
                    value = FeatureValue.from_dict(json.loads(data))
                    value.check_staleness()
                    result[key.name] = value

            return result

        except Exception as e:
            logger.error(f"Failed to get features: {e}")
            return {}

    async def set_many(
        self,
        features: Dict[FeatureKey, FeatureValue],
    ) -> int:
        """Store multiple features efficiently."""
        if not await self._ensure_connection():
            return 0

        try:
            pipe = self._redis.pipeline()
            count = 0

            for key, value in features.items():
                redis_key = self._make_key(key)
                data = json.dumps(value.to_dict())
                ttl = value.ttl_seconds or self.default_ttl
                pipe.setex(redis_key, ttl, data)
                count += 1

            await pipe.execute()
            return count

        except Exception as e:
            logger.error(f"Failed to set features: {e}")
            return 0

    async def delete(self, key: FeatureKey) -> bool:
        """Delete a feature."""
        if not await self._ensure_connection():
            return False

        try:
            redis_key = self._make_key(key)
            result = await self._redis.delete(redis_key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete feature: {e}")
            return False

    async def list_keys(
        self,
        pattern: str = "*",
    ) -> List[FeatureKey]:
        """List feature keys matching pattern."""
        if not await self._ensure_connection():
            return []

        try:
            full_pattern = f"{self.key_prefix}:feature:{pattern}"
            keys = []

            async for key in self._redis.scan_iter(match=full_pattern):
                # Remove prefix to get feature key
                feature_key = key.replace(f"{self.key_prefix}:", "")
                keys.append(FeatureKey.from_redis_key(feature_key))

            return keys

        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            return []

    async def get_history(
        self,
        feature_name: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[FeatureValue]:
        """Get historical feature values."""
        if not await self._ensure_connection():
            return []

        try:
            timeline_key = f"{self.key_prefix}:timeline:{feature_name}"
            start_score = start_time.timestamp()
            end_score = end_time.timestamp()

            # Get keys from sorted set
            keys = await self._redis.zrangebyscore(
                timeline_key,
                start_score,
                end_score,
                start=0,
                num=limit,
            )

            if not keys:
                return []

            # Get values
            values = await self._redis.mget(keys)
            result = []

            for data in values:
                if data:
                    value = FeatureValue.from_dict(json.loads(data))
                    result.append(value)

            return result

        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def get_latest(
        self,
        entity_type: str = "global",
        entity_id: str = "default",
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, FeatureValue]:
        """Get latest values for all features of an entity."""
        if not await self._ensure_connection():
            return {}

        try:
            pattern = f"{self.key_prefix}:feature:{entity_type}:{entity_id}:*"
            features = {}

            async for key in self._redis.scan_iter(match=pattern):
                data = await self._redis.get(key)
                if data:
                    feature_key = FeatureKey.from_redis_key(
                        key.replace(f"{self.key_prefix}:", "")
                    )

                    if feature_names is None or feature_key.name in feature_names:
                        value = FeatureValue.from_dict(json.loads(data))
                        value.check_staleness()
                        features[feature_key.name] = value

            return features

        except Exception as e:
            logger.error(f"Failed to get latest features: {e}")
            return {}

    async def get_freshness_report(self) -> Dict[str, Any]:
        """Get a report on feature freshness."""
        if not await self._ensure_connection():
            return {}

        try:
            report = {
                'total_features': 0,
                'fresh_features': 0,
                'stale_features': 0,
                'by_category': {},
                'stalest_features': [],
            }

            pattern = f"{self.key_prefix}:feature:*"
            staleness_list = []

            async for key in self._redis.scan_iter(match=pattern):
                data = await self._redis.get(key)
                if data:
                    value = FeatureValue.from_dict(json.loads(data))
                    value.check_staleness()

                    report['total_features'] += 1
                    if value.is_stale:
                        report['stale_features'] += 1
                    else:
                        report['fresh_features'] += 1

                    category = value.category.value
                    if category not in report['by_category']:
                        report['by_category'][category] = {'fresh': 0, 'stale': 0}

                    if value.is_stale:
                        report['by_category'][category]['stale'] += 1
                    else:
                        report['by_category'][category]['fresh'] += 1

                    staleness_list.append((key, value.staleness_seconds))

            # Get top 10 stalest
            staleness_list.sort(key=lambda x: x[1], reverse=True)
            report['stalest_features'] = [
                {'key': k, 'staleness_seconds': s}
                for k, s in staleness_list[:10]
            ]

            return report

        except Exception as e:
            logger.error(f"Failed to generate freshness report: {e}")
            return {}

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._connected = False


class FeatureStoreWriter:
    """High-level interface for writing features to store."""

    def __init__(
        self,
        store: FeatureStore,
        default_entity_type: str = "market",
        default_entity_id: str = "spot",
    ):
        """Initialize writer.

        Args:
            store: Underlying feature store
            default_entity_type: Default entity type
            default_entity_id: Default entity ID
        """
        self.store = store
        self.default_entity_type = default_entity_type
        self.default_entity_id = default_entity_id

        # TTL defaults by category
        self.ttl_defaults = {
            FeatureCategory.REAL_TIME: 300,      # 5 minutes
            FeatureCategory.ROLLING: 3600,       # 1 hour
            FeatureCategory.SCHEDULED: 7200,     # 2 hours
            FeatureCategory.HISTORICAL: 86400,   # 1 day
            FeatureCategory.DERIVED: 600,        # 10 minutes
        }

    async def write_features(
        self,
        features: Dict[str, Any],
        category: FeatureCategory = FeatureCategory.REAL_TIME,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """Write multiple features to store.

        Args:
            features: Dictionary of feature name to value
            category: Feature category
            entity_type: Entity type (default: market)
            entity_id: Entity ID (default: spot)
            ttl_seconds: TTL override

        Returns:
            Number of features written
        """
        entity_type = entity_type or self.default_entity_type
        entity_id = entity_id or self.default_entity_id
        ttl = ttl_seconds or self.ttl_defaults.get(category, 3600)

        timestamp = datetime.now()
        to_store = {}

        for name, value in features.items():
            if name in ['timestamp', 'feature_type', 'market']:
                continue  # Skip metadata

            key = FeatureKey(
                name=name,
                entity_type=entity_type,
                entity_id=entity_id,
            )

            feature_value = FeatureValue(
                value=value,
                timestamp=timestamp,
                category=category,
                ttl_seconds=ttl,
                source="pipeline",
            )

            to_store[key] = feature_value

        # Use batch write if available
        if hasattr(self.store, 'set_many'):
            return await self.store.set_many(to_store)
        else:
            count = 0
            for key, value in to_store.items():
                if await self.store.set(key, value):
                    count += 1
            return count

    async def write_feature(
        self,
        name: str,
        value: Any,
        category: FeatureCategory = FeatureCategory.REAL_TIME,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Write a single feature to store."""
        return await self.write_features(
            {name: value},
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
            ttl_seconds=ttl_seconds,
        ) > 0
