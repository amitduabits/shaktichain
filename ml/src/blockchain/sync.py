"""Historical sync for blockchain data.

Provides:
- Initial sync of historical trades and auctions
- Cursor-based resumption
- Feature store population from historical data
- Progress tracking and reporting
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of sync operation."""
    IDLE = "idle"
    SYNCING = "syncing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncCursor:
    """Cursor for tracking sync progress."""
    entity_type: str  # trades, auctions
    last_timestamp: int
    last_id: Optional[str] = None
    records_synced: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_type": self.entity_type,
            "last_timestamp": self.last_timestamp,
            "last_id": self.last_id,
            "records_synced": self.records_synced,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncCursor":
        """Create from dictionary."""
        return cls(
            entity_type=data["entity_type"],
            last_timestamp=data["last_timestamp"],
            last_id=data.get("last_id"),
            records_synced=data.get("records_synced", 0),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
        )


@dataclass
class SyncProgress:
    """Progress of sync operation."""
    entity_type: str
    status: SyncStatus
    start_timestamp: int
    end_timestamp: int
    current_timestamp: int
    records_synced: int
    estimated_total: Optional[int] = None
    errors: int = 0
    started_at: Optional[datetime] = None
    eta_seconds: Optional[float] = None

    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        total_range = self.end_timestamp - self.start_timestamp
        if total_range <= 0:
            return 100.0
        current_progress = self.current_timestamp - self.start_timestamp
        return min(100.0, (current_progress / total_range) * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_type": self.entity_type,
            "status": self.status.value,
            "progress_pct": self.progress_pct,
            "records_synced": self.records_synced,
            "estimated_total": self.estimated_total,
            "errors": self.errors,
            "eta_seconds": self.eta_seconds,
        }


class CursorStorage:
    """Storage for sync cursors."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize cursor storage.

        Args:
            storage_path: Path to store cursors (JSON file)
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self._cursors: Dict[str, SyncCursor] = {}

        # Load existing cursors
        if self.storage_path and self.storage_path.exists():
            self._load()

    def _load(self):
        """Load cursors from storage."""
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
                for key, cursor_data in data.items():
                    self._cursors[key] = SyncCursor.from_dict(cursor_data)
            logger.info(f"Loaded {len(self._cursors)} cursors from storage")
        except Exception as e:
            logger.error(f"Failed to load cursors: {e}")

    def _save(self):
        """Save cursors to storage."""
        if not self.storage_path:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                data = {k: v.to_dict() for k, v in self._cursors.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cursors: {e}")

    def get(self, entity_type: str) -> Optional[SyncCursor]:
        """Get cursor for entity type."""
        return self._cursors.get(entity_type)

    def set(self, cursor: SyncCursor):
        """Set cursor for entity type."""
        cursor.updated_at = datetime.now()
        self._cursors[cursor.entity_type] = cursor
        self._save()

    def delete(self, entity_type: str):
        """Delete cursor for entity type."""
        if entity_type in self._cursors:
            del self._cursors[entity_type]
            self._save()


class HistoricalSync:
    """Sync historical blockchain data to feature store."""

    def __init__(
        self,
        subgraph_client,
        event_processor,
        feature_store=None,
        cursor_storage: Optional[CursorStorage] = None,
        sync_days: int = 30,
        batch_size: int = 1000,
        max_concurrent: int = 5,
    ):
        """Initialize historical sync.

        Args:
            subgraph_client: SubgraphClient instance
            event_processor: BlockchainEventProcessor instance
            feature_store: Feature store for population
            cursor_storage: Cursor storage for resumption
            sync_days: Number of days to sync
            batch_size: Records per batch
            max_concurrent: Max concurrent requests
        """
        self.subgraph = subgraph_client
        self.processor = event_processor
        self.feature_store = feature_store
        self.cursor_storage = cursor_storage or CursorStorage()
        self.sync_days = sync_days
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

        # Sync state
        self._status: Dict[str, SyncStatus] = {
            "trades": SyncStatus.IDLE,
            "auctions": SyncStatus.IDLE,
        }
        self._progress: Dict[str, SyncProgress] = {}
        self._running = False

        # Statistics
        self._stats = {
            "trades_synced": 0,
            "auctions_synced": 0,
            "features_created": 0,
            "errors": 0,
            "sync_time_seconds": 0,
        }

    async def start(self, entity_types: Optional[List[str]] = None):
        """Start historical sync.

        Args:
            entity_types: Types to sync (trades, auctions). Defaults to all.
        """
        self._running = True
        entity_types = entity_types or ["trades", "auctions"]

        logger.info(f"Starting historical sync for: {entity_types}")

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=self.sync_days)
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        # Start sync tasks
        tasks = []
        for entity_type in entity_types:
            if entity_type == "trades":
                tasks.append(self._sync_trades(start_ts, end_ts))
            elif entity_type == "auctions":
                tasks.append(self._sync_auctions(start_ts, end_ts))

        # Run concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        self._running = False
        logger.info("Historical sync completed")

    async def stop(self):
        """Stop historical sync."""
        self._running = False
        for entity_type in self._status:
            if self._status[entity_type] == SyncStatus.SYNCING:
                self._status[entity_type] = SyncStatus.PAUSED

    async def _sync_trades(self, start_ts: int, end_ts: int):
        """Sync historical trades."""
        entity_type = "trades"
        self._status[entity_type] = SyncStatus.SYNCING

        # Check for existing cursor
        cursor = self.cursor_storage.get(entity_type)
        if cursor and cursor.last_timestamp > start_ts:
            start_ts = cursor.last_timestamp
            logger.info(f"Resuming trades sync from {datetime.fromtimestamp(start_ts)}")

        # Initialize progress
        self._progress[entity_type] = SyncProgress(
            entity_type=entity_type,
            status=SyncStatus.SYNCING,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            current_timestamp=start_ts,
            records_synced=cursor.records_synced if cursor else 0,
            started_at=datetime.now(),
        )

        try:
            async for trade in self.subgraph.get_historical_trades(start_ts, end_ts):
                if not self._running:
                    break

                # Process trade
                await self.processor.process_trade(trade)
                self._stats["trades_synced"] += 1

                # Update cursor
                trade_ts = int(trade.get("timestamp", start_ts))
                cursor = SyncCursor(
                    entity_type=entity_type,
                    last_timestamp=trade_ts,
                    last_id=trade.get("id"),
                    records_synced=self._stats["trades_synced"],
                )
                self.cursor_storage.set(cursor)

                # Update progress
                self._progress[entity_type].current_timestamp = trade_ts
                self._progress[entity_type].records_synced = self._stats["trades_synced"]

                # Log progress periodically
                if self._stats["trades_synced"] % 1000 == 0:
                    progress = self._progress[entity_type].progress_pct
                    logger.info(f"Trades sync: {progress:.1f}% ({self._stats['trades_synced']} records)")

            self._status[entity_type] = SyncStatus.COMPLETED

        except Exception as e:
            logger.error(f"Trades sync failed: {e}")
            self._status[entity_type] = SyncStatus.FAILED
            self._stats["errors"] += 1
            raise

    async def _sync_auctions(self, start_ts: int, end_ts: int):
        """Sync historical auctions."""
        entity_type = "auctions"
        self._status[entity_type] = SyncStatus.SYNCING

        # Check for existing cursor
        cursor = self.cursor_storage.get(entity_type)
        if cursor and cursor.last_timestamp > start_ts:
            start_ts = cursor.last_timestamp
            logger.info(f"Resuming auctions sync from {datetime.fromtimestamp(start_ts)}")

        # Initialize progress
        self._progress[entity_type] = SyncProgress(
            entity_type=entity_type,
            status=SyncStatus.SYNCING,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            current_timestamp=start_ts,
            records_synced=cursor.records_synced if cursor else 0,
            started_at=datetime.now(),
        )

        try:
            async for auction in self.subgraph.get_historical_auctions(start_ts, end_ts):
                if not self._running:
                    break

                # Process auction
                await self.processor.process_auction_close(auction)
                self._stats["auctions_synced"] += 1

                # Update cursor
                auction_ts = int(auction.get("endTime", start_ts))
                cursor = SyncCursor(
                    entity_type=entity_type,
                    last_timestamp=auction_ts,
                    last_id=auction.get("id"),
                    records_synced=self._stats["auctions_synced"],
                )
                self.cursor_storage.set(cursor)

                # Update progress
                self._progress[entity_type].current_timestamp = auction_ts
                self._progress[entity_type].records_synced = self._stats["auctions_synced"]

            self._status[entity_type] = SyncStatus.COMPLETED

        except Exception as e:
            logger.error(f"Auctions sync failed: {e}")
            self._status[entity_type] = SyncStatus.FAILED
            self._stats["errors"] += 1
            raise

    async def populate_feature_store(self):
        """Populate feature store from synced historical data.

        This is called after sync to build aggregated features.
        """
        if not self.feature_store:
            logger.warning("No feature store configured")
            return

        logger.info("Populating feature store from historical data...")

        try:
            # Get processor stats for feature creation
            stats = self.processor.get_stats()

            # The processor already updates the feature store during sync
            # This method can be used for additional aggregations

            self._stats["features_created"] = stats.get("trade_processor", {}).get("trades_processed", 0)

            logger.info(f"Feature store populated with {self._stats['features_created']} features")

        except Exception as e:
            logger.error(f"Feature store population failed: {e}")
            self._stats["errors"] += 1

    def get_progress(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Get sync progress.

        Args:
            entity_type: Specific entity type or None for all

        Returns:
            Progress information
        """
        if entity_type:
            progress = self._progress.get(entity_type)
            return progress.to_dict() if progress else {}

        return {
            entity: prog.to_dict()
            for entity, prog in self._progress.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get sync statistics."""
        return {
            **self._stats,
            "status": {k: v.value for k, v in self._status.items()},
            "progress": self.get_progress(),
        }

    def reset(self, entity_type: Optional[str] = None):
        """Reset sync state.

        Args:
            entity_type: Specific type to reset or None for all
        """
        if entity_type:
            self.cursor_storage.delete(entity_type)
            self._status[entity_type] = SyncStatus.IDLE
            if entity_type in self._progress:
                del self._progress[entity_type]
        else:
            for et in ["trades", "auctions"]:
                self.cursor_storage.delete(et)
                self._status[et] = SyncStatus.IDLE
            self._progress.clear()

        logger.info(f"Reset sync state for: {entity_type or 'all'}")
