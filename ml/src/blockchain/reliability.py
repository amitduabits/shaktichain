"""Reliability layer for blockchain integration.

Provides:
- Retry logic with exponential backoff
- Dead letter queue for failed events
- Checkpoint management for block processing
- Circuit breaker pattern
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import random

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(Enum):
    """Retry strategies."""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"
    LINEAR = "linear"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    retryable_exceptions: tuple = (Exception,)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt.

        Args:
            attempt: Attempt number (1-based)

        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.FIXED:
            delay = self.initial_delay

        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.initial_delay * attempt

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.initial_delay * (2 ** (attempt - 1))

        elif self.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base_delay = self.initial_delay * (2 ** (attempt - 1))
            # Add jitter: random value between 0 and base_delay
            delay = base_delay + random.uniform(0, base_delay * 0.5)

        else:
            delay = self.initial_delay

        return min(delay, self.max_delay)


class RetryableOperation(Generic[T]):
    """Execute operation with retry logic."""

    def __init__(
        self,
        operation: Callable[..., T],
        policy: Optional[RetryPolicy] = None,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        on_failure: Optional[Callable[[Exception], None]] = None,
    ):
        """Initialize retryable operation.

        Args:
            operation: Operation to execute
            policy: Retry policy
            on_retry: Callback on retry
            on_failure: Callback on final failure
        """
        self.operation = operation
        self.policy = policy or RetryPolicy()
        self.on_retry = on_retry
        self.on_failure = on_failure

    async def execute(self, *args, **kwargs) -> T:
        """Execute operation with retries.

        Returns:
            Operation result

        Raises:
            Last exception if all retries fail
        """
        last_exception = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(self.operation):
                    return await self.operation(*args, **kwargs)
                else:
                    return self.operation(*args, **kwargs)

            except self.policy.retryable_exceptions as e:
                last_exception = e

                if attempt < self.policy.max_attempts:
                    delay = self.policy.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s..."
                    )

                    if self.on_retry:
                        self.on_retry(attempt, e)

                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.policy.max_attempts} attempts failed")

                    if self.on_failure:
                        self.on_failure(e)

        raise last_exception


@dataclass
class DeadLetterItem:
    """Item in the dead letter queue."""
    id: str
    event_type: str
    payload: Dict[str, Any]
    error: str
    attempts: int
    first_failed_at: datetime
    last_failed_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "payload": self.payload,
            "error": self.error,
            "attempts": self.attempts,
            "first_failed_at": self.first_failed_at.isoformat(),
            "last_failed_at": self.last_failed_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeadLetterItem":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            event_type=data["event_type"],
            payload=data["payload"],
            error=data["error"],
            attempts=data["attempts"],
            first_failed_at=datetime.fromisoformat(data["first_failed_at"]),
            last_failed_at=datetime.fromisoformat(data["last_failed_at"]),
            metadata=data.get("metadata", {}),
        )


class DeadLetterQueue:
    """Queue for failed events that need manual intervention."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_size: int = 10000,
        retention_days: int = 7,
    ):
        """Initialize dead letter queue.

        Args:
            storage_path: Path for persistent storage
            max_size: Maximum queue size
            retention_days: Days to retain items
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_size = max_size
        self.retention_days = retention_days

        self._items: Dict[str, DeadLetterItem] = {}
        self._stats = {
            "items_added": 0,
            "items_processed": 0,
            "items_expired": 0,
        }

        # Load from storage
        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self):
        """Load items from storage."""
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                for item_data in data.get("items", []):
                    item = DeadLetterItem.from_dict(item_data)
                    self._items[item.id] = item
            logger.info(f"Loaded {len(self._items)} DLQ items from storage")
        except Exception as e:
            logger.error(f"Failed to load DLQ: {e}")

    def _save(self):
        """Save items to storage."""
        if not self.storage_path:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                data = {
                    "items": [item.to_dict() for item in self._items.values()],
                    "stats": self._stats,
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save DLQ: {e}")

    def add(
        self,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        error: str,
        attempts: int = 1,
    ):
        """Add item to dead letter queue.

        Args:
            event_id: Event identifier
            event_type: Type of event
            payload: Event payload
            error: Error message
            attempts: Number of failed attempts
        """
        now = datetime.now()

        if event_id in self._items:
            # Update existing item
            item = self._items[event_id]
            item.attempts += 1
            item.last_failed_at = now
            item.error = error
        else:
            # Create new item
            if len(self._items) >= self.max_size:
                # Remove oldest item
                oldest = min(self._items.values(), key=lambda x: x.first_failed_at)
                del self._items[oldest.id]

            item = DeadLetterItem(
                id=event_id,
                event_type=event_type,
                payload=payload,
                error=error,
                attempts=attempts,
                first_failed_at=now,
                last_failed_at=now,
            )
            self._items[event_id] = item
            self._stats["items_added"] += 1

        self._save()
        logger.warning(f"Added to DLQ: {event_id} ({event_type})")

    def get(self, event_id: str) -> Optional[DeadLetterItem]:
        """Get item from queue."""
        return self._items.get(event_id)

    def remove(self, event_id: str) -> bool:
        """Remove item from queue after successful processing."""
        if event_id in self._items:
            del self._items[event_id]
            self._stats["items_processed"] += 1
            self._save()
            return True
        return False

    def get_all(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeadLetterItem]:
        """Get items from queue.

        Args:
            event_type: Filter by event type
            limit: Maximum items to return

        Returns:
            List of items
        """
        items = list(self._items.values())

        if event_type:
            items = [i for i in items if i.event_type == event_type]

        # Sort by last failed time (oldest first)
        items.sort(key=lambda x: x.last_failed_at)

        return items[:limit]

    def cleanup(self):
        """Remove expired items."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        expired = [
            item_id for item_id, item in self._items.items()
            if item.last_failed_at < cutoff
        ]

        for item_id in expired:
            del self._items[item_id]
            self._stats["items_expired"] += 1

        if expired:
            self._save()
            logger.info(f"Expired {len(expired)} DLQ items")

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            **self._stats,
            "current_size": len(self._items),
            "by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count items by event type."""
        counts: Dict[str, int] = {}
        for item in self._items.values():
            counts[item.event_type] = counts.get(item.event_type, 0) + 1
        return counts


@dataclass
class Checkpoint:
    """Checkpoint for tracking processed blocks."""
    entity_type: str
    block_number: int
    block_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    events_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_type": self.entity_type,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "timestamp": self.timestamp.isoformat(),
            "events_processed": self.events_processed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            entity_type=data["entity_type"],
            block_number=data["block_number"],
            block_hash=data.get("block_hash"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            events_processed=data.get("events_processed", 0),
        )


class CheckpointManager:
    """Manage checkpoints for block processing."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        save_interval: int = 100,  # Save every N blocks
    ):
        """Initialize checkpoint manager.

        Args:
            storage_path: Path for persistent storage
            save_interval: Blocks between saves
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.save_interval = save_interval

        self._checkpoints: Dict[str, Checkpoint] = {}
        self._pending_saves = 0

        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self):
        """Load checkpoints from storage."""
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                for cp_data in data.get("checkpoints", []):
                    cp = Checkpoint.from_dict(cp_data)
                    self._checkpoints[cp.entity_type] = cp
            logger.info(f"Loaded {len(self._checkpoints)} checkpoints")
        except Exception as e:
            logger.error(f"Failed to load checkpoints: {e}")

    def _save(self):
        """Save checkpoints to storage."""
        if not self.storage_path:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                data = {
                    "checkpoints": [cp.to_dict() for cp in self._checkpoints.values()],
                    "saved_at": datetime.now().isoformat(),
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoints: {e}")

    def get(self, entity_type: str) -> Optional[Checkpoint]:
        """Get checkpoint for entity type."""
        return self._checkpoints.get(entity_type)

    def update(
        self,
        entity_type: str,
        block_number: int,
        block_hash: Optional[str] = None,
        events_processed: int = 0,
        force_save: bool = False,
    ):
        """Update checkpoint.

        Args:
            entity_type: Type of entity (trades, auctions)
            block_number: Latest processed block
            block_hash: Block hash for verification
            events_processed: Events in this block
            force_save: Force immediate save
        """
        existing = self._checkpoints.get(entity_type)

        if existing:
            existing.block_number = block_number
            existing.block_hash = block_hash
            existing.timestamp = datetime.now()
            existing.events_processed += events_processed
        else:
            self._checkpoints[entity_type] = Checkpoint(
                entity_type=entity_type,
                block_number=block_number,
                block_hash=block_hash,
                events_processed=events_processed,
            )

        self._pending_saves += 1

        if force_save or self._pending_saves >= self.save_interval:
            self._save()
            self._pending_saves = 0

    def get_all(self) -> Dict[str, Checkpoint]:
        """Get all checkpoints."""
        return dict(self._checkpoints)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for failing dependencies."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    # State
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    half_open_calls: int = 0

    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
            return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self):
        """Record successful execution."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                # Recovery confirmed
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker closed (recovered)")
        else:
            self.failure_count = 0

    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failed during recovery test
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker reopened")

        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }


class ReliabilityLayer:
    """Unified reliability layer for blockchain operations."""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        """Initialize reliability layer.

        Args:
            storage_dir: Directory for persistent storage
            retry_policy: Default retry policy
        """
        storage_path = Path(storage_dir) if storage_dir else None

        self.retry_policy = retry_policy or RetryPolicy()

        self.dlq = DeadLetterQueue(
            storage_path=str(storage_path / "dlq.json") if storage_path else None,
        )

        self.checkpoints = CheckpointManager(
            storage_path=str(storage_path / "checkpoints.json") if storage_path else None,
        )

        # Circuit breakers for different services
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        self._stats = {
            "operations_executed": 0,
            "retries": 0,
            "failures": 0,
        }

    def get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = CircuitBreaker()
        return self._circuit_breakers[service]

    async def execute_with_retry(
        self,
        operation: Callable[..., T],
        *args,
        service: Optional[str] = None,
        policy: Optional[RetryPolicy] = None,
        **kwargs,
    ) -> T:
        """Execute operation with retry and circuit breaker.

        Args:
            operation: Operation to execute
            *args: Operation arguments
            service: Service name for circuit breaker
            policy: Override retry policy
            **kwargs: Operation keyword arguments

        Returns:
            Operation result
        """
        self._stats["operations_executed"] += 1

        # Check circuit breaker
        if service:
            cb = self.get_circuit_breaker(service)
            if not cb.can_execute():
                raise RuntimeError(f"Circuit breaker open for {service}")

        policy = policy or self.retry_policy

        def on_retry(attempt: int, error: Exception):
            self._stats["retries"] += 1

        def on_failure(error: Exception):
            self._stats["failures"] += 1
            if service:
                cb = self.get_circuit_breaker(service)
                cb.record_failure()

        retryable = RetryableOperation(
            operation=operation,
            policy=policy,
            on_retry=on_retry,
            on_failure=on_failure,
        )

        try:
            result = await retryable.execute(*args, **kwargs)

            if service:
                cb = self.get_circuit_breaker(service)
                cb.record_success()

            return result

        except Exception as e:
            raise

    async def process_event_safely(
        self,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        processor: Callable[[Dict[str, Any]], Any],
    ) -> bool:
        """Process event with full reliability guarantees.

        Args:
            event_id: Event identifier
            event_type: Type of event
            payload: Event payload
            processor: Processing function

        Returns:
            True if processed successfully
        """
        try:
            await self.execute_with_retry(
                processor,
                payload,
                service=event_type,
            )
            return True

        except Exception as e:
            # Add to DLQ
            self.dlq.add(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                error=str(e),
            )
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get reliability statistics."""
        return {
            **self._stats,
            "dlq": self.dlq.get_stats(),
            "checkpoints": {
                k: v.to_dict()
                for k, v in self.checkpoints.get_all().items()
            },
            "circuit_breakers": {
                k: v.get_status()
                for k, v in self._circuit_breakers.items()
            },
        }
