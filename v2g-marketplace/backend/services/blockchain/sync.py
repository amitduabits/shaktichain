"""
Blockchain Sync Module.

Synchronizes blockchain events with the local database.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from threading import Thread, Event

from .provider import Web3Provider, get_web3_provider
from .contracts import ContractManager, get_contract_manager
from .events import EventListener, BlockchainEvent

logger = logging.getLogger(__name__)


@dataclass
class SyncState:
    """Tracks synchronization state."""
    last_synced_block: int
    last_sync_time: float
    total_events_synced: int
    is_syncing: bool
    error: Optional[str] = None


class BlockchainSync:
    """
    Synchronizes blockchain events with the local database.

    Features:
    - Syncs trade events to database
    - Tracks sync progress
    - Handles chain reorganizations
    - Background sync with configurable interval
    """

    def __init__(
        self,
        database: Any,  # Database instance
        provider: Optional[Web3Provider] = None,
        contract_manager: Optional[ContractManager] = None,
        sync_interval: int = 30,
        batch_size: int = 1000,
    ):
        """
        Initialize blockchain sync.

        Args:
            database: Database instance for storing synced data.
            provider: Web3Provider instance.
            contract_manager: ContractManager instance.
            sync_interval: Background sync interval in seconds.
            batch_size: Number of blocks to sync per batch.
        """
        self.database = database
        self.provider = provider or get_web3_provider()
        self.contracts = contract_manager or get_contract_manager(self.provider)
        self.event_listener = EventListener(self.provider, self.contracts)

        self.sync_interval = sync_interval
        self.batch_size = batch_size

        self._state = SyncState(
            last_synced_block=0,
            last_sync_time=0,
            total_events_synced=0,
            is_syncing=False,
        )
        self._running = False
        self._stop_event = Event()
        self._sync_thread: Optional[Thread] = None

    @property
    def state(self) -> SyncState:
        """Get current sync state."""
        return self._state

    def _load_last_synced_block(self) -> int:
        """Load last synced block from database."""
        try:
            # Try to get from database settings
            conn = self.database._get_connection()
            cursor = conn.cursor()

            # Create sync_state table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_sync_state (
                    id INTEGER PRIMARY KEY,
                    last_synced_block INTEGER NOT NULL,
                    last_sync_time TEXT NOT NULL,
                    total_events_synced INTEGER DEFAULT 0
                )
            """)
            conn.commit()

            cursor.execute("SELECT last_synced_block FROM blockchain_sync_state WHERE id = 1")
            row = cursor.fetchone()

            if row:
                return row[0]

            return 0

        except Exception as e:
            logger.warning(f"Failed to load sync state: {e}")
            return 0

    def _save_sync_state(self) -> None:
        """Save sync state to database."""
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO blockchain_sync_state
                (id, last_synced_block, last_sync_time, total_events_synced)
                VALUES (1, ?, ?, ?)
            """, (
                self._state.last_synced_block,
                datetime.utcnow().isoformat(),
                self._state.total_events_synced,
            ))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")

    def _ensure_tables_exist(self) -> None:
        """Ensure blockchain-related tables exist."""
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            # Create blockchain_trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_id INTEGER NOT NULL,
                    trade_id INTEGER NOT NULL,
                    buyer TEXT NOT NULL,
                    seller TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    block_number INTEGER NOT NULL,
                    transaction_hash TEXT NOT NULL,
                    timestamp INTEGER,
                    synced_at TEXT NOT NULL,
                    UNIQUE(round_id, trade_id)
                )
            """)

            # Create blockchain_bids table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_id INTEGER NOT NULL,
                    order_id INTEGER NOT NULL,
                    trader TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    block_number INTEGER NOT NULL,
                    transaction_hash TEXT NOT NULL,
                    timestamp INTEGER,
                    synced_at TEXT NOT NULL,
                    UNIQUE(round_id, order_id)
                )
            """)

            # Create blockchain_staking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_staking_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_address TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    shares TEXT,
                    block_number INTEGER NOT NULL,
                    transaction_hash TEXT NOT NULL,
                    timestamp INTEGER,
                    synced_at TEXT NOT NULL
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_blockchain_trades_round
                ON blockchain_trades(round_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_blockchain_bids_round
                ON blockchain_bids(round_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_blockchain_trades_block
                ON blockchain_trades(block_number)
            """)

            conn.commit()
            logger.info("Blockchain tables initialized")

        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def _sync_trade_event(self, event: BlockchainEvent) -> bool:
        """
        Sync a TradeExecuted event to database.

        Args:
            event: BlockchainEvent object.

        Returns:
            True if synced, False if already exists.
        """
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO blockchain_trades
                (round_id, trade_id, buyer, seller, quantity, price,
                 block_number, transaction_hash, timestamp, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.args.get("roundId"),
                event.args.get("tradeId"),
                event.args.get("buyer"),
                event.args.get("seller"),
                str(event.args.get("quantity", 0)),
                str(event.args.get("price", 0)),
                event.block_number,
                event.transaction_hash,
                event.timestamp,
                datetime.utcnow().isoformat(),
            ))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to sync trade event: {e}")
            return False

    def _sync_bid_event(self, event: BlockchainEvent, order_type: str) -> bool:
        """
        Sync a Bid/Ask submitted event to database.

        Args:
            event: BlockchainEvent object.
            order_type: "bid" or "ask".

        Returns:
            True if synced, False if already exists.
        """
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO blockchain_bids
                (round_id, order_id, trader, quantity, price, order_type,
                 block_number, transaction_hash, timestamp, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.args.get("roundId"),
                event.args.get("orderId"),
                event.args.get("trader"),
                str(event.args.get("quantity", 0)),
                str(event.args.get("maxPrice") or event.args.get("minPrice", 0)),
                order_type,
                event.block_number,
                event.transaction_hash,
                event.timestamp,
                datetime.utcnow().isoformat(),
            ))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to sync bid event: {e}")
            return False

    def _sync_staking_event(self, event: BlockchainEvent, event_type: str) -> bool:
        """
        Sync a staking event to database.

        Args:
            event: BlockchainEvent object.
            event_type: "stake", "unstake", or "claim".

        Returns:
            True if synced.
        """
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO blockchain_staking_events
                (user_address, event_type, amount, shares,
                 block_number, transaction_hash, timestamp, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.args.get("user"),
                event_type,
                str(event.args.get("amount", 0)),
                str(event.args.get("shares")) if event.args.get("shares") else None,
                event.block_number,
                event.transaction_hash,
                event.timestamp,
                datetime.utcnow().isoformat(),
            ))

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to sync staking event: {e}")
            return False

    def sync_blocks(self, from_block: int, to_block: int) -> int:
        """
        Sync events from a range of blocks.

        Args:
            from_block: Starting block.
            to_block: Ending block.

        Returns:
            Number of events synced.
        """
        events_synced = 0

        # Sync TradeExecuted events
        trades = self.event_listener.get_events("EnergyAuction", "TradeExecuted", from_block, to_block)
        for event in trades:
            if self._sync_trade_event(event):
                events_synced += 1

        # Sync BidSubmitted events
        bids = self.event_listener.get_events("EnergyAuction", "BidSubmitted", from_block, to_block)
        for event in bids:
            if self._sync_bid_event(event, "bid"):
                events_synced += 1

        # Sync AskSubmitted events
        asks = self.event_listener.get_events("EnergyAuction", "AskSubmitted", from_block, to_block)
        for event in asks:
            if self._sync_bid_event(event, "ask"):
                events_synced += 1

        # Sync staking events
        staked = self.event_listener.get_events("StakingPool", "Staked", from_block, to_block)
        for event in staked:
            if self._sync_staking_event(event, "stake"):
                events_synced += 1

        unstaked = self.event_listener.get_events("StakingPool", "Unstaked", from_block, to_block)
        for event in unstaked:
            if self._sync_staking_event(event, "unstake"):
                events_synced += 1

        claimed = self.event_listener.get_events("StakingPool", "RewardsClaimed", from_block, to_block)
        for event in claimed:
            if self._sync_staking_event(event, "claim"):
                events_synced += 1

        return events_synced

    def sync_to_latest(self) -> int:
        """
        Sync all events up to the latest block.

        Returns:
            Total number of events synced.
        """
        self._state.is_syncing = True
        self._state.error = None
        total_synced = 0

        try:
            current_block = self.provider.web3.eth.block_number
            from_block = self._state.last_synced_block + 1

            if from_block > current_block:
                logger.debug("Already synced to latest block")
                return 0

            logger.info(f"Syncing blocks {from_block} to {current_block}")

            # Sync in batches
            while from_block <= current_block:
                to_block = min(from_block + self.batch_size - 1, current_block)

                events_synced = self.sync_blocks(from_block, to_block)
                total_synced += events_synced

                self._state.last_synced_block = to_block
                self._state.total_events_synced += events_synced
                self._save_sync_state()

                logger.debug(f"Synced blocks {from_block}-{to_block}: {events_synced} events")

                from_block = to_block + 1

            self._state.last_sync_time = time.time()
            logger.info(f"Sync complete: {total_synced} events synced")

        except Exception as e:
            self._state.error = str(e)
            logger.error(f"Sync error: {e}")

        finally:
            self._state.is_syncing = False

        return total_synced

    def _background_sync(self) -> None:
        """Background sync loop."""
        while not self._stop_event.is_set():
            try:
                self.sync_to_latest()
            except Exception as e:
                logger.error(f"Background sync error: {e}")

            self._stop_event.wait(self.sync_interval)

    def start_background_sync(self, from_block: Optional[int] = None) -> None:
        """
        Start background synchronization.

        Args:
            from_block: Starting block. Uses last synced if None.
        """
        if self._running:
            logger.warning("Background sync already running")
            return

        # Initialize tables
        self._ensure_tables_exist()

        # Load or set starting block
        if from_block is not None:
            self._state.last_synced_block = from_block
        else:
            self._state.last_synced_block = self._load_last_synced_block()

        self._running = True
        self._stop_event.clear()
        self._sync_thread = Thread(target=self._background_sync, daemon=True)
        self._sync_thread.start()

        logger.info(f"Background sync started from block {self._state.last_synced_block}")

    def stop_background_sync(self) -> None:
        """Stop background synchronization."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._sync_thread:
            self._sync_thread.join(timeout=10)
            self._sync_thread = None

        logger.info("Background sync stopped")

    @property
    def is_running(self) -> bool:
        """Check if background sync is running."""
        return self._running

    def get_synced_trades(
        self,
        round_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get synced trades from database.

        Args:
            round_id: Filter by round ID.
            limit: Maximum records to return.

        Returns:
            List of trade records.
        """
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            if round_id is not None:
                cursor.execute("""
                    SELECT * FROM blockchain_trades
                    WHERE round_id = ?
                    ORDER BY block_number DESC
                    LIMIT ?
                """, (round_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM blockchain_trades
                    ORDER BY block_number DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get synced trades: {e}")
            return []

    def get_synced_bids(
        self,
        round_id: Optional[int] = None,
        order_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get synced bids/asks from database.

        Args:
            round_id: Filter by round ID.
            order_type: Filter by "bid" or "ask".
            limit: Maximum records to return.

        Returns:
            List of bid records.
        """
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM blockchain_bids WHERE 1=1"
            params: List[Any] = []

            if round_id is not None:
                query += " AND round_id = ?"
                params.append(round_id)

            if order_type is not None:
                query += " AND order_type = ?"
                params.append(order_type)

            query += " ORDER BY block_number DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get synced bids: {e}")
            return []
