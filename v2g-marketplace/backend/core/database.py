"""
SQLite database module for V2G Marketplace.

Provides simple database operations without external ORM dependencies.
"""

import os
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid


class Database:
    """SQLite database handler for V2G marketplace data."""

    def __init__(self, db_path: str = "data/v2g.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
        self._write_lock = threading.RLock()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            self._connection.row_factory = sqlite3.Row
            # Improve concurrency behavior for multi-threaded test runs.
            self._connection.execute("PRAGMA journal_mode=WAL;")
            self._connection.execute("PRAGMA synchronous=NORMAL;")
            self._connection.execute("PRAGMA busy_timeout=5000;")
            self._connection.execute("PRAGMA foreign_keys=ON;")
        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create simulations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                n_agents INTEGER NOT NULL,
                n_days INTEGER NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
                avg_price REAL,
                total_volume REAL
            )
        """)

        # Create market_periods table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                simulation_id TEXT NOT NULL,
                period INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                clearing_price REAL,
                volume REAL,
                n_buyers INTEGER,
                n_sellers INTEGER,
                FOREIGN KEY (simulation_id) REFERENCES simulations(id)
            )
        """)

        # Create price_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price REAL NOT NULL,
                source TEXT CHECK(source IN ('simulation', 'live'))
            )
        """)

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user' CHECK(role IN ('user', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create auction rounds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auction_rounds (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reveal_deadline TIMESTAMP NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open', 'settled', 'cancelled')),
                clearing_price REAL,
                matched_orders INTEGER DEFAULT 0,
                settled_volume REAL DEFAULT 0
            )
        """)

        # Create auction orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auction_orders (
                id TEXT PRIMARY KEY,
                round_id TEXT NOT NULL,
                prosumer_id TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
                quantity REAL NOT NULL,
                commit_hash TEXT NOT NULL,
                price REAL,
                nonce TEXT,
                status TEXT NOT NULL CHECK(status IN ('committed', 'revealed', 'matched', 'settled', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (round_id) REFERENCES auction_rounds(id)
            )
        """)

        # Create auction matches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auction_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id TEXT NOT NULL,
                buy_order_id TEXT NOT NULL,
                sell_order_id TEXT NOT NULL,
                quantity REAL NOT NULL,
                clearing_price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (round_id) REFERENCES auction_rounds(id)
            )
        """)

        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_periods_simulation
            ON market_periods(simulation_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_timestamp
            ON price_history(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_auction_orders_round
            ON auction_orders(round_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_auction_orders_round_status
            ON auction_orders(round_id, status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_auction_matches_round
            ON auction_matches(round_id)
        """)

        conn.commit()

    def save_simulation(self, sim_data: dict) -> str:
        """
        Save a simulation record.

        Args:
            sim_data: Dictionary with simulation data.
                Required: n_agents, n_days
                Optional: id, status, avg_price, total_volume

        Returns:
            The simulation ID.
        """
        sim_id = sim_data.get("id", str(uuid.uuid4()))
        created_at = sim_data.get("created_at", datetime.utcnow().isoformat())
        n_agents = sim_data["n_agents"]
        n_days = sim_data["n_days"]
        status = sim_data.get("status", "pending")
        avg_price = sim_data.get("avg_price")
        total_volume = sim_data.get("total_volume")

        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO simulations (id, created_at, n_agents, n_days, status, avg_price, total_volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    avg_price = excluded.avg_price,
                    total_volume = excluded.total_volume
            """, (sim_id, created_at, n_agents, n_days, status, avg_price, total_volume))
            conn.commit()
        return sim_id

    def get_simulation(self, sim_id: str) -> Optional[dict]:
        """
        Get a simulation by ID.

        Args:
            sim_id: Simulation ID.

        Returns:
            Simulation data as dictionary or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, n_agents, n_days, status, avg_price, total_volume
            FROM simulations
            WHERE id = ?
        """, (sim_id,))

        row = cursor.fetchone()
        if row is None:
            return None

        return dict(row)

    def update_simulation(self, sim_id: str, updates: dict) -> bool:
        """
        Update a simulation record.

        Args:
            sim_id: Simulation ID.
            updates: Dictionary of fields to update.

        Returns:
            True if updated, False if simulation not found.
        """
        allowed_fields = {"status", "avg_price", "total_volume"}
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

        if not update_fields:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in update_fields)
        values = list(update_fields.values()) + [sim_id]

        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE simulations
                SET {set_clause}
                WHERE id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0

    def list_simulations(self, limit: int = 50) -> list[dict]:
        """
        List recent simulations.

        Args:
            limit: Maximum number of simulations to return.

        Returns:
            List of simulation dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, n_agents, n_days, status, avg_price, total_volume
            FROM simulations
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def save_period(self, period_data: dict) -> int:
        """
        Save a market period record.

        Args:
            period_data: Dictionary with period data.
                Required: simulation_id, period, hour
                Optional: clearing_price, volume, n_buyers, n_sellers

        Returns:
            The period record ID.
        """
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO market_periods
                (simulation_id, period, hour, clearing_price, volume, n_buyers, n_sellers)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                period_data["simulation_id"],
                period_data["period"],
                period_data["hour"],
                period_data.get("clearing_price"),
                period_data.get("volume"),
                period_data.get("n_buyers"),
                period_data.get("n_sellers")
            ))

            conn.commit()
            return cursor.lastrowid

    def get_periods(self, simulation_id: str) -> list[dict]:
        """
        Get all periods for a simulation.

        Args:
            simulation_id: Simulation ID.

        Returns:
            List of period dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, simulation_id, period, hour, clearing_price, volume, n_buyers, n_sellers
            FROM market_periods
            WHERE simulation_id = ?
            ORDER BY period ASC
        """, (simulation_id,))

        return [dict(row) for row in cursor.fetchall()]

    def save_price(self, price: float, source: str = "simulation") -> int:
        """
        Save a price history record.

        Args:
            price: The price value.
            source: Price source ('simulation' or 'live').

        Returns:
            The price record ID.
        """
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO price_history (timestamp, price, source)
                VALUES (?, ?, ?)
            """, (datetime.utcnow().isoformat(), price, source))

            conn.commit()
            return cursor.lastrowid

    def get_price_history(self, limit: int = 100) -> list[dict]:
        """
        Get recent price history.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of price history dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, timestamp, price, source
            FROM price_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def create_user(self, user_data: dict) -> str:
        """
        Create a new user.

        Args:
            user_data: Dictionary with user data.
                Required: email, password_hash
                Optional: id, role

        Returns:
            The user ID.
        """
        user_id = user_data.get("id", str(uuid.uuid4()))
        email = user_data["email"]
        password_hash = user_data["password_hash"]
        role = user_data.get("role", "user")

        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            """, (user_id, email, password_hash, role))
            conn.commit()
        return user_id

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """
        Get a user by email.

        Args:
            email: User email.

        Returns:
            User data as dictionary or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, email, password_hash, role, created_at
            FROM users
            WHERE email = ?
        """, (email,))

        row = cursor.fetchone()
        if row is None:
            return None

        return dict(row)

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """
        Get a user by ID.

        Args:
            user_id: User ID.

        Returns:
            User data as dictionary or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, email, password_hash, role, created_at
            FROM users
            WHERE id = ?
        """, (user_id,))

        row = cursor.fetchone()
        if row is None:
            return None

        return dict(row)

    def create_auction_round(self, reveal_deadline: str, round_id: Optional[str] = None) -> str:
        """Create a new auction round."""
        resolved_round_id = round_id or str(uuid.uuid4())
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO auction_rounds (id, reveal_deadline, status)
                VALUES (?, ?, 'open')
            """, (resolved_round_id, reveal_deadline))
            conn.commit()
        return resolved_round_id

    def get_auction_round(self, round_id: str) -> Optional[dict]:
        """Fetch auction round by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, created_at, reveal_deadline, status, clearing_price, matched_orders, settled_volume
            FROM auction_rounds
            WHERE id = ?
        """, (round_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_auction_round(
        self,
        round_id: str,
        *,
        status: Optional[str] = None,
        clearing_price: Optional[float] = None,
        matched_orders: Optional[int] = None,
        settled_volume: Optional[float] = None,
    ) -> bool:
        """Update auction round fields."""
        updates = {}
        if status is not None:
            updates["status"] = status
        if clearing_price is not None:
            updates["clearing_price"] = clearing_price
        if matched_orders is not None:
            updates["matched_orders"] = matched_orders
        if settled_volume is not None:
            updates["settled_volume"] = settled_volume
        if not updates:
            return False

        set_clause = ", ".join(f"{field} = ?" for field in updates.keys())
        values = list(updates.values()) + [round_id]

        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE auction_rounds
                SET {set_clause}
                WHERE id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0

    def save_auction_commit(self, order_data: dict) -> str:
        """Persist committed order hash for an auction round."""
        order_id = order_data.get("id", str(uuid.uuid4()))
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO auction_orders
                (id, round_id, prosumer_id, side, quantity, commit_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, 'committed')
            """, (
                order_id,
                order_data["round_id"],
                order_data["prosumer_id"],
                order_data["side"],
                order_data["quantity"],
                order_data["commit_hash"],
            ))
            conn.commit()
        return order_id

    def get_auction_order(self, round_id: str, order_id: str) -> Optional[dict]:
        """Get single auction order by round and order IDs."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, round_id, prosumer_id, side, quantity, commit_hash, price, nonce, status, created_at
            FROM auction_orders
            WHERE round_id = ? AND id = ?
        """, (round_id, order_id))
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_auction_order_by_commit(self, round_id: str, prosumer_id: str, commit_hash: str) -> Optional[dict]:
        """Find committed order by round, prosumer and commit hash."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, round_id, prosumer_id, side, quantity, commit_hash, price, nonce, status, created_at
            FROM auction_orders
            WHERE round_id = ? AND prosumer_id = ? AND commit_hash = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (round_id, prosumer_id, commit_hash))
        row = cursor.fetchone()
        return dict(row) if row else None

    def reveal_auction_order(self, round_id: str, order_id: str, price: float, nonce: str) -> bool:
        """Store revealed order details after commit verification."""
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE auction_orders
                SET price = ?, nonce = ?, status = 'revealed'
                WHERE round_id = ? AND id = ? AND status = 'committed'
            """, (price, nonce, round_id, order_id))
            conn.commit()
            return cursor.rowcount > 0

    def list_auction_orders(self, round_id: str, status: Optional[str] = None) -> list[dict]:
        """List auction orders for a round, optionally filtered by status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if status is None:
            cursor.execute("""
                SELECT id, round_id, prosumer_id, side, quantity, commit_hash, price, nonce, status, created_at
                FROM auction_orders
                WHERE round_id = ?
                ORDER BY created_at ASC
            """, (round_id,))
        else:
            cursor.execute("""
                SELECT id, round_id, prosumer_id, side, quantity, commit_hash, price, nonce, status, created_at
                FROM auction_orders
                WHERE round_id = ? AND status = ?
                ORDER BY created_at ASC
            """, (round_id, status))
        return [dict(row) for row in cursor.fetchall()]

    def mark_auction_order_status(self, round_id: str, order_id: str, status: str) -> bool:
        """Update status for one auction order."""
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE auction_orders
                SET status = ?
                WHERE round_id = ? AND id = ?
            """, (status, round_id, order_id))
            conn.commit()
            return cursor.rowcount > 0

    def save_auction_match(
        self,
        round_id: str,
        buy_order_id: str,
        sell_order_id: str,
        quantity: float,
        clearing_price: float,
    ) -> int:
        """Persist one auction settlement match."""
        with self._write_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO auction_matches (round_id, buy_order_id, sell_order_id, quantity, clearing_price)
                VALUES (?, ?, ?, ?, ?)
            """, (round_id, buy_order_id, sell_order_id, quantity, clearing_price))
            conn.commit()
            return cursor.lastrowid

    def list_auction_matches(self, round_id: str) -> list[dict]:
        """List settlement matches for a round."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, round_id, buy_order_id, sell_order_id, quantity, clearing_price, created_at
            FROM auction_matches
            WHERE round_id = ?
            ORDER BY id ASC
        """, (round_id,))
        return [dict(row) for row in cursor.fetchall()]


# Singleton instance for convenience
_db_instance: Optional[Database] = None
_db_path: Optional[str] = None


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    """Resolve DB path from explicit value, env variables, or default."""
    if db_path:
        return db_path

    env_path = os.getenv("V2G_DB_PATH")
    if env_path:
        return env_path

    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("sqlite:///"):
        # Handles sqlite:///relative/path and sqlite:////absolute/path
        return database_url.replace("sqlite:///", "", 1)

    return "data/v2g.db"


def get_database(db_path: str = "data/v2g.db") -> Database:
    """
    Get or create the database singleton instance.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Database instance.
    """
    global _db_instance, _db_path
    resolved_path = _resolve_db_path(db_path if db_path != "data/v2g.db" else None)

    if _db_instance is None or _db_path != resolved_path or not Path(resolved_path).exists():
        if _db_instance is not None:
            _db_instance.close()
        _db_instance = Database(resolved_path)
        _db_instance.init_db()
        _db_path = resolved_path
    return _db_instance


def reset_database() -> None:
    """Reset singleton database instance (used by tests and lifecycle reload)."""
    global _db_instance, _db_path
    if _db_instance is not None:
        _db_instance.close()
    _db_instance = None
    _db_path = None


# Ensure both import paths resolve to the same module object.
_current_module = sys.modules[__name__]
if __name__ == "core.database":
    sys.modules.setdefault("backend.core.database", _current_module)
elif __name__ == "backend.core.database":
    sys.modules.setdefault("core.database", _current_module)
