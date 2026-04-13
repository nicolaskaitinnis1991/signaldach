"""Persistence layer for Paper Trading Engine.

Stores paper orders, positions, and portfolio state in SQLite/PostgreSQL.
Uses the existing database abstraction from app.database.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

_SQLITE_PAPER_TABLES = """
    CREATE TABLE IF NOT EXISTS paper_orders (
        id TEXT PRIMARY KEY,
        portfolio_id TEXT NOT NULL DEFAULT 'default',
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL,
        status TEXT NOT NULL DEFAULT 'pending',
        fill_price REAL,
        fill_quantity REAL,
        reason TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        filled_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_paper_orders_portfolio ON paper_orders(portfolio_id, status);
    CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol ON paper_orders(symbol, status);

    CREATE TABLE IF NOT EXISTS paper_positions (
        portfolio_id TEXT NOT NULL DEFAULT 'default',
        symbol TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 0.0,
        avg_entry_price REAL NOT NULL DEFAULT 0.0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (portfolio_id, symbol)
    );

    CREATE TABLE IF NOT EXISTS paper_portfolio_state (
        portfolio_id TEXT PRIMARY KEY DEFAULT 'default',
        initial_cash REAL NOT NULL DEFAULT 100000.0,
        current_cash REAL NOT NULL DEFAULT 100000.0,
        high_water_mark REAL NOT NULL DEFAULT 100000.0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS nav_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id TEXT NOT NULL DEFAULT 'default',
        nav REAL NOT NULL,
        positions_value REAL NOT NULL,
        cash REAL NOT NULL,
        management_fee REAL DEFAULT 0,
        performance_fee REAL DEFAULT 0,
        high_water_mark REAL NOT NULL,
        snapshot_date TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(portfolio_id, snapshot_date)
    );
    CREATE INDEX IF NOT EXISTS idx_nav_snapshots_portfolio_date ON nav_snapshots(portfolio_id, snapshot_date);
"""

_PG_PAPER_TABLES = """
    CREATE TABLE IF NOT EXISTS paper_orders (
        id TEXT PRIMARY KEY,
        portfolio_id TEXT NOT NULL DEFAULT 'default',
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity DOUBLE PRECISION NOT NULL,
        price DOUBLE PRECISION,
        status TEXT NOT NULL DEFAULT 'pending',
        fill_price DOUBLE PRECISION,
        fill_quantity DOUBLE PRECISION,
        reason TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        filled_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_paper_orders_portfolio ON paper_orders(portfolio_id, status);
    CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol ON paper_orders(symbol, status);

    CREATE TABLE IF NOT EXISTS paper_positions (
        portfolio_id TEXT NOT NULL DEFAULT 'default',
        symbol TEXT NOT NULL,
        quantity DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        avg_entry_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (portfolio_id, symbol)
    );

    CREATE TABLE IF NOT EXISTS paper_portfolio_state (
        portfolio_id TEXT PRIMARY KEY DEFAULT 'default',
        initial_cash DOUBLE PRECISION NOT NULL DEFAULT 100000.0,
        current_cash DOUBLE PRECISION NOT NULL DEFAULT 100000.0,
        high_water_mark DOUBLE PRECISION NOT NULL DEFAULT 100000.0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS nav_snapshots (
        id SERIAL PRIMARY KEY,
        portfolio_id TEXT NOT NULL DEFAULT 'default',
        nav DOUBLE PRECISION NOT NULL,
        positions_value DOUBLE PRECISION NOT NULL,
        cash DOUBLE PRECISION NOT NULL,
        management_fee DOUBLE PRECISION DEFAULT 0,
        performance_fee DOUBLE PRECISION DEFAULT 0,
        high_water_mark DOUBLE PRECISION NOT NULL,
        snapshot_date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(portfolio_id, snapshot_date)
    );
    CREATE INDEX IF NOT EXISTS idx_nav_snapshots_portfolio_date ON nav_snapshots(portfolio_id, snapshot_date);
"""


def init_paper_tables() -> None:
    """Create paper trading tables if they don't exist."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if USE_POSTGRES:
                cur.execute(_PG_PAPER_TABLES)
            else:
                cur.executescript(_SQLITE_PAPER_TABLES)
        logger.info("Paper trading tables initialized.")
    except Exception as exc:
        logger.warning("Failed to init paper trading tables: %s", exc)


# ---------------------------------------------------------------------------
# Order persistence
# ---------------------------------------------------------------------------

def save_order(order_dict: dict) -> None:
    """Insert or update a paper order."""
    with get_db() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(
                """INSERT INTO paper_orders
                   (id, portfolio_id, symbol, side, order_type, quantity, price, status,
                    fill_price, fill_quantity, reason, created_at, filled_at)
                   VALUES (%(id)s, %(portfolio_id)s, %(symbol)s, %(side)s, %(order_type)s,
                           %(quantity)s, %(price)s, %(status)s, %(fill_price)s,
                           %(fill_quantity)s, %(reason)s, %(created_at)s, %(filled_at)s)
                   ON CONFLICT (id) DO UPDATE SET
                       status = EXCLUDED.status,
                       fill_price = EXCLUDED.fill_price,
                       fill_quantity = EXCLUDED.fill_quantity,
                       reason = EXCLUDED.reason,
                       filled_at = EXCLUDED.filled_at
                """,
                order_dict,
            )
        else:
            cur.execute(
                """INSERT OR REPLACE INTO paper_orders
                   (id, portfolio_id, symbol, side, order_type, quantity, price, status,
                    fill_price, fill_quantity, reason, created_at, filled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_dict["id"],
                    order_dict.get("portfolio_id", "default"),
                    order_dict["symbol"],
                    order_dict["side"],
                    order_dict["order_type"],
                    order_dict["quantity"],
                    order_dict.get("price"),
                    order_dict["status"],
                    order_dict.get("fill_price"),
                    order_dict.get("fill_quantity"),
                    order_dict.get("reason"),
                    order_dict.get("created_at"),
                    order_dict.get("filled_at"),
                ),
            )


def load_orders(
    portfolio_id: str = "default",
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Load paper orders with optional filters."""
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT * FROM paper_orders WHERE portfolio_id = ?"
        params: list = [portfolio_id]

        if status:
            query += " AND status = ?"
            params.append(status)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Position persistence
# ---------------------------------------------------------------------------

def save_position(portfolio_id: str, symbol: str, quantity: float, avg_entry_price: float) -> None:
    """Insert or update a paper position."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.cursor()
        if quantity <= 0:
            # Remove closed positions
            cur.execute(
                "DELETE FROM paper_positions WHERE portfolio_id = ? AND symbol = ?",
                (portfolio_id, symbol),
            )
        elif USE_POSTGRES:
            cur.execute(
                """INSERT INTO paper_positions (portfolio_id, symbol, quantity, avg_entry_price, updated_at)
                   VALUES (%(pid)s, %(sym)s, %(qty)s, %(avg)s, %(now)s)
                   ON CONFLICT (portfolio_id, symbol) DO UPDATE SET
                       quantity = EXCLUDED.quantity,
                       avg_entry_price = EXCLUDED.avg_entry_price,
                       updated_at = EXCLUDED.updated_at
                """,
                {"pid": portfolio_id, "sym": symbol, "qty": quantity, "avg": avg_entry_price, "now": now},
            )
        else:
            cur.execute(
                """INSERT OR REPLACE INTO paper_positions
                   (portfolio_id, symbol, quantity, avg_entry_price, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (portfolio_id, symbol, quantity, avg_entry_price, now),
            )


def load_positions(portfolio_id: str = "default") -> list[dict]:
    """Load all open paper positions for a portfolio."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM paper_positions WHERE portfolio_id = ? AND quantity > 0",
            (portfolio_id,),
        )
        return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Portfolio state persistence
# ---------------------------------------------------------------------------

def save_portfolio_state(
    portfolio_id: str,
    initial_cash: float,
    current_cash: float,
    high_water_mark: float,
) -> None:
    """Save portfolio state (cash, HWM)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(
                """INSERT INTO paper_portfolio_state
                   (portfolio_id, initial_cash, current_cash, high_water_mark, updated_at)
                   VALUES (%(pid)s, %(ic)s, %(cc)s, %(hwm)s, %(now)s)
                   ON CONFLICT (portfolio_id) DO UPDATE SET
                       current_cash = EXCLUDED.current_cash,
                       high_water_mark = EXCLUDED.high_water_mark,
                       updated_at = EXCLUDED.updated_at
                """,
                {"pid": portfolio_id, "ic": initial_cash, "cc": current_cash, "hwm": high_water_mark, "now": now},
            )
        else:
            cur.execute(
                """INSERT OR REPLACE INTO paper_portfolio_state
                   (portfolio_id, initial_cash, current_cash, high_water_mark, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (portfolio_id, initial_cash, current_cash, high_water_mark, now),
            )


def load_portfolio_state(portfolio_id: str = "default") -> Optional[dict]:
    """Load portfolio state. Returns None if not found."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM paper_portfolio_state WHERE portfolio_id = ?",
            (portfolio_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def delete_portfolio_data(portfolio_id: str = "default") -> None:
    """Delete all paper trading data for a portfolio (used by reset)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM paper_orders WHERE portfolio_id = ?", (portfolio_id,))
        cur.execute("DELETE FROM paper_positions WHERE portfolio_id = ?", (portfolio_id,))
        cur.execute("DELETE FROM paper_portfolio_state WHERE portfolio_id = ?", (portfolio_id,))
