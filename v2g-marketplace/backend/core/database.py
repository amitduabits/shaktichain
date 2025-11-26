"""
SQLite database module for V2G Marketplace.

Provides simple database operations without external ORM dependencies.
"""

import sqlite3
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

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
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

        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_periods_simulation
            ON market_periods(simulation_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_timestamp
            ON price_history(timestamp DESC)
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
        conn = self._get_connection()
        cursor = conn.cursor()

        sim_id = sim_data.get("id", str(uuid.uuid4()))
        created_at = sim_data.get("created_at", datetime.utcnow().isoformat())
        n_agents = sim_data["n_agents"]
        n_days = sim_data["n_days"]
        status = sim_data.get("status", "pending")
        avg_price = sim_data.get("avg_price")
        total_volume = sim_data.get("total_volume")

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
        conn = self._get_connection()
        cursor = conn.cursor()

        allowed_fields = {"status", "avg_price", "total_volume"}
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

        if not update_fields:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in update_fields)
        values = list(update_fields.values()) + [sim_id]

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
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]


# Singleton instance for convenience
_db_instance: Optional[Database] = None


def get_database(db_path: str = "data/v2g.db") -> Database:
    """
    Get or create the database singleton instance.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Database instance.
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
        _db_instance.init_db()
    return _db_instance
