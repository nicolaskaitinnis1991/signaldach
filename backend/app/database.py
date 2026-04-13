"""Database abstraction supporting both SQLite and PostgreSQL.

How to switch to PostgreSQL:
    Set the environment variable (or .env file):
        SIGNALDACH_DATABASE_URL=postgresql://user:password@host:port/dbname

    If DATABASE_URL starts with "postgresql://" -> psycopg/psycopg2 is used.
    If DATABASE_URL starts with "sqlite://" or is not set -> SQLite is used (default).

    For PostgreSQL you need: pip install psycopg[binary]
    (already listed in pyproject.toml dependencies)
"""

import sqlite3
import os
import logging
import threading
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Slow query threshold (ms) — queries slower than this get logged as warnings
SLOW_QUERY_THRESHOLD_MS = float(os.environ.get("SIGNALDACH_SLOW_QUERY_MS", "100"))

# Connection pool for PostgreSQL
_pg_pool = None
_pg_pool_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Determine backend from DATABASE_URL
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "SIGNALDACH_DATABASE_URL",
    os.environ.get("DATABASE_URL", ""),
)

USE_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

# SQLite fallback path (used when DATABASE_URL is empty or starts with sqlite://)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "signaldach.db")


# ---------------------------------------------------------------------------
# Connection factories
# ---------------------------------------------------------------------------

def _sqlite_connection():
    """Create a SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_pg_pool():
    """Get or create a PostgreSQL connection pool (thread-safe singleton)."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    with _pg_pool_lock:
        if _pg_pool is not None:
            return _pg_pool

        try:
            from psycopg_pool import ConnectionPool
            from psycopg.rows import dict_row

            _pg_pool = ConnectionPool(
                DATABASE_URL,
                min_size=2,
                max_size=20,
                kwargs={"row_factory": dict_row},
                open=True,
            )
            logger.info("PostgreSQL connection pool created (min=2, max=20)")
            return _pg_pool
        except ImportError:
            logger.warning("psycopg_pool not available, falling back to single connections")

    return None


def _pg_connection():
    """Get a PostgreSQL connection from the pool (or create a single one as fallback)."""
    pool = _get_pg_pool()
    if pool is not None:
        return pool.getconn()

    try:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn
    except ImportError:
        pass

    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    except ImportError:
        raise ImportError(
            "PostgreSQL driver not found. Install with: pip install 'psycopg[binary]' "
            "or pip install psycopg2-binary"
        )


def _return_pg_connection(conn):
    """Return a PostgreSQL connection to the pool (or close it)."""
    pool = _pg_pool
    if pool is not None:
        try:
            pool.putconn(conn)
            return
        except Exception:
            pass
    try:
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------

def get_connection():
    """Get a database connection (SQLite or PostgreSQL based on DATABASE_URL)."""
    if USE_POSTGRES:
        return _pg_connection()
    return _sqlite_connection()


@contextmanager
def get_db():
    """Context manager that yields a DB connection with auto-commit/rollback.

    Logs slow transactions (> SLOW_QUERY_THRESHOLD_MS).
    """
    start = time.perf_counter()
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
            logger.warning("Slow DB transaction: %.1fms (threshold: %.0fms)", elapsed_ms, SLOW_QUERY_THRESHOLD_MS)
        if USE_POSTGRES:
            _return_pg_connection(conn)
        else:
            conn.close()


# ---------------------------------------------------------------------------
# Schema: PostgreSQL DDL
# ---------------------------------------------------------------------------

_PG_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        plan TEXT DEFAULT 'free',
        settings TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL REFERENCES tenants(id),
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT NOT NULL,
        url TEXT,
        config TEXT DEFAULT '{}',
        scrape_frequency_minutes INTEGER DEFAULT 60,
        enabled INTEGER DEFAULT 1,
        last_scraped_at TIMESTAMP,
        error_count INTEGER DEFAULT 0,
        last_error TEXT,
        last_error_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL REFERENCES tenants(id),
        source_id TEXT NOT NULL REFERENCES sources(id),
        external_id TEXT,
        title TEXT NOT NULL,
        summary TEXT,
        content TEXT,
        url TEXT,
        author TEXT,
        published_at TIMESTAMP,
        category TEXT NOT NULL,
        relevance_score INTEGER DEFAULT 5,
        urgency TEXT DEFAULT 'normal',
        sentiment REAL,
        ai_metadata TEXT DEFAULT '{}',
        raw_data TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(tenant_id, external_id)
    );

    CREATE TABLE IF NOT EXISTS alert_configs (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL REFERENCES tenants(id),
        user_id TEXT,
        name TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        conditions TEXT NOT NULL DEFAULT '{}',
        channels TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS alert_history (
        id TEXT PRIMARY KEY,
        alert_config_id TEXT NOT NULL REFERENCES alert_configs(id),
        item_id TEXT NOT NULL REFERENCES items(id),
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        sent_at TIMESTAMP DEFAULT NOW(),
        metadata TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS keyword_trends (
        id TEXT PRIMARY KEY,
        keyword TEXT NOT NULL,
        date TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        avg_count_7d REAL DEFAULT 0.0,
        is_spike INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS entity_mentions (
        id TEXT PRIMARY KEY,
        entity_name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        item_id TEXT NOT NULL REFERENCES items(id),
        mentioned_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'viewer',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS api_keys (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        key_hash TEXT NOT NULL,
        name TEXT,
        permissions TEXT DEFAULT '{}',
        is_active INTEGER DEFAULT 1,
        last_used_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS token_blacklist (
        id TEXT PRIMARY KEY,
        token_jti TEXT UNIQUE NOT NULL,
        blacklisted_at TIMESTAMP DEFAULT NOW(),
        expires_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        ts TIMESTAMP NOT NULL DEFAULT NOW(),
        category VARCHAR(30) NOT NULL,
        action VARCHAR(100) NOT NULL,
        user_id TEXT,
        detail TEXT DEFAULT '{}',
        ip_address VARCHAR(45),
        request_id VARCHAR(36)
    );

    CREATE TABLE IF NOT EXISTS ensemble_weights (
        id SERIAL PRIMARY KEY,
        agent_name TEXT NOT NULL,
        weight REAL NOT NULL,
        accuracy REAL,
        sample_count INTEGER,
        calibrated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(agent_name, calibrated_at)
    );

    CREATE TABLE IF NOT EXISTS translations (
        hash TEXT NOT NULL,
        lang TEXT NOT NULL,
        original TEXT NOT NULL,
        translated TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (hash, lang)
    );
    CREATE INDEX IF NOT EXISTS idx_translations_hash_lang ON translations(hash, lang);

    INSERT INTO tenants (id, name, slug, plan)
    VALUES ('default', 'SignalDACH', 'signaldach', 'pro')
    ON CONFLICT (id) DO NOTHING;
"""

_PG_INDEXES = """
    CREATE INDEX IF NOT EXISTS idx_items_tenant_category
        ON items(tenant_id, category, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_items_tenant_urgency
        ON items(tenant_id, urgency, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_items_tenant_relevance
        ON items(tenant_id, relevance_score DESC);
    CREATE INDEX IF NOT EXISTS idx_items_tenant_external
        ON items(tenant_id, external_id);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_keyword_trends_kw_date
        ON keyword_trends(keyword, date);
    CREATE INDEX IF NOT EXISTS idx_keyword_trends_date
        ON keyword_trends(date);
    CREATE INDEX IF NOT EXISTS idx_keyword_trends_spike
        ON keyword_trends(is_spike, date);

    CREATE INDEX IF NOT EXISTS idx_entity_mentions_name
        ON entity_mentions(entity_name, entity_type);
    CREATE INDEX IF NOT EXISTS idx_entity_mentions_item
        ON entity_mentions(item_id);
    CREATE INDEX IF NOT EXISTS idx_entity_mentions_date
        ON entity_mentions(mentioned_at);

    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
    CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
    CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(token_jti);

    CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts);
    CREATE INDEX IF NOT EXISTS idx_audit_log_category ON audit_log(category, ts);
    CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, ts);
    CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action, ts);

    CREATE INDEX IF NOT EXISTS idx_ensemble_weights_agent
        ON ensemble_weights(agent_name, calibrated_at DESC);

    CREATE INDEX IF NOT EXISTS idx_items_published_category
        ON items(published_at DESC, category);
    CREATE INDEX IF NOT EXISTS idx_signal_scores_symbol_type_ts
        ON signal_scores(symbol, signal_type, ts DESC);
    CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_exchange
        ON price_ticks(symbol, exchange, ts DESC);
"""

# ---------------------------------------------------------------------------
# Schema: SQLite DDL
# ---------------------------------------------------------------------------

_SQLITE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        plan TEXT DEFAULT 'free',
        settings TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL REFERENCES tenants(id),
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT NOT NULL,
        url TEXT,
        config TEXT DEFAULT '{}',
        scrape_frequency_minutes INTEGER DEFAULT 60,
        enabled INTEGER DEFAULT 1,
        last_scraped_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL REFERENCES tenants(id),
        source_id TEXT NOT NULL REFERENCES sources(id),
        external_id TEXT,
        title TEXT NOT NULL,
        summary TEXT,
        content TEXT,
        url TEXT,
        author TEXT,
        published_at TEXT,
        category TEXT NOT NULL,
        relevance_score INTEGER DEFAULT 5,
        urgency TEXT DEFAULT 'normal',
        sentiment REAL,
        ai_metadata TEXT DEFAULT '{}',
        raw_data TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(tenant_id, external_id)
    );

    CREATE TABLE IF NOT EXISTS alert_configs (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL REFERENCES tenants(id),
        user_id TEXT,
        name TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        conditions TEXT NOT NULL DEFAULT '{}',
        channels TEXT NOT NULL DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS alert_history (
        id TEXT PRIMARY KEY,
        alert_config_id TEXT NOT NULL REFERENCES alert_configs(id),
        item_id TEXT NOT NULL REFERENCES items(id),
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        sent_at TEXT DEFAULT (datetime('now')),
        metadata TEXT DEFAULT '{}'
    );

    CREATE INDEX IF NOT EXISTS idx_items_tenant_category
        ON items(tenant_id, category, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_items_tenant_urgency
        ON items(tenant_id, urgency, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_items_tenant_relevance
        ON items(tenant_id, relevance_score DESC);
    CREATE INDEX IF NOT EXISTS idx_items_tenant_external
        ON items(tenant_id, external_id);
    CREATE INDEX IF NOT EXISTS idx_items_published_category
        ON items(published_at DESC, category);

    CREATE TABLE IF NOT EXISTS keyword_trends (
        id TEXT PRIMARY KEY,
        keyword TEXT NOT NULL,
        date TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        avg_count_7d REAL DEFAULT 0.0,
        is_spike INTEGER DEFAULT 0
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_keyword_trends_kw_date
        ON keyword_trends(keyword, date);
    CREATE INDEX IF NOT EXISTS idx_keyword_trends_date
        ON keyword_trends(date);
    CREATE INDEX IF NOT EXISTS idx_keyword_trends_spike
        ON keyword_trends(is_spike, date);

    CREATE TABLE IF NOT EXISTS entity_mentions (
        id TEXT PRIMARY KEY,
        entity_name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        item_id TEXT NOT NULL REFERENCES items(id),
        mentioned_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_entity_mentions_name
        ON entity_mentions(entity_name, entity_type);
    CREATE INDEX IF NOT EXISTS idx_entity_mentions_item
        ON entity_mentions(item_id);
    CREATE INDEX IF NOT EXISTS idx_entity_mentions_date
        ON entity_mentions(mentioned_at);

    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'viewer',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS api_keys (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        key_hash TEXT NOT NULL,
        name TEXT,
        permissions TEXT DEFAULT '{}',
        is_active INTEGER DEFAULT 1,
        last_used_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS token_blacklist (
        id TEXT PRIMARY KEY,
        token_jti TEXT UNIQUE NOT NULL,
        blacklisted_at TEXT DEFAULT (datetime('now')),
        expires_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
    CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
    CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(token_jti);

    INSERT OR IGNORE INTO tenants (id, name, slug, plan)
    VALUES ('default', 'SignalDACH', 'signaldach', 'pro');

    -- Time-series tables (Phase 1B)
    CREATE TABLE IF NOT EXISTS price_ticks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL DEFAULT (datetime('now')),
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        price REAL NOT NULL,
        volume_24h REAL,
        market_cap REAL,
        change_pct_24h REAL
    );
    CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_ts ON price_ticks(symbol, ts);
    CREATE INDEX IF NOT EXISTS idx_price_ticks_exchange_ts ON price_ticks(exchange, ts);
    CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_exchange ON price_ticks(symbol, exchange, ts DESC);

    CREATE TABLE IF NOT EXISTS market_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL DEFAULT (datetime('now')),
        metric_type TEXT NOT NULL,
        symbol TEXT,
        exchange TEXT,
        value REAL NOT NULL,
        metadata_json TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_market_metrics_type_ts ON market_metrics(metric_type, ts);
    CREATE INDEX IF NOT EXISTS idx_market_metrics_symbol_ts ON market_metrics(symbol, ts);

    CREATE TABLE IF NOT EXISTS signal_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL DEFAULT (datetime('now')),
        symbol TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        score REAL NOT NULL,
        confidence REAL,
        components_json TEXT DEFAULT '{}',
        reasoning TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_signal_scores_symbol_ts ON signal_scores(symbol, ts);
    CREATE INDEX IF NOT EXISTS idx_signal_scores_type_ts ON signal_scores(signal_type, ts);
    CREATE INDEX IF NOT EXISTS idx_signal_scores_symbol_type_ts ON signal_scores(symbol, signal_type, ts DESC);

    CREATE TABLE IF NOT EXISTS onchain_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL DEFAULT (datetime('now')),
        metric_type TEXT NOT NULL,
        chain TEXT,
        protocol TEXT,
        value REAL NOT NULL,
        unit TEXT DEFAULT 'USD',
        metadata_json TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_onchain_metrics_type_ts ON onchain_metrics(metric_type, ts);
    CREATE INDEX IF NOT EXISTS idx_onchain_metrics_chain_ts ON onchain_metrics(chain, ts);
    CREATE INDEX IF NOT EXISTS idx_onchain_metrics_protocol_ts ON onchain_metrics(protocol, ts);

    -- Audit trail (immutable, append-only)
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL DEFAULT (datetime('now')),
        category TEXT NOT NULL,
        action TEXT NOT NULL,
        user_id TEXT,
        detail TEXT DEFAULT '{}',
        ip_address TEXT,
        request_id TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts);
    CREATE INDEX IF NOT EXISTS idx_audit_log_category ON audit_log(category, ts);
    CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, ts);
    CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action, ts);

    -- Ensemble weight calibration (adaptive agent weights)
    CREATE TABLE IF NOT EXISTS ensemble_weights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        weight REAL NOT NULL,
        accuracy REAL,
        sample_count INTEGER,
        calibrated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(agent_name, calibrated_at)
    );
    CREATE INDEX IF NOT EXISTS idx_ensemble_weights_agent
        ON ensemble_weights(agent_name, calibrated_at DESC);

    -- Translation cache (on-demand feed translation)
    CREATE TABLE IF NOT EXISTS translations (
        hash TEXT NOT NULL,
        lang TEXT NOT NULL,
        original TEXT NOT NULL,
        translated TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (hash, lang)
    );
    CREATE INDEX IF NOT EXISTS idx_translations_hash_lang ON translations(hash, lang);

    -- Entity knowledge graph (Phase 2B)
    CREATE TABLE IF NOT EXISTS entity_relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_a TEXT NOT NULL,
        entity_a_type TEXT NOT NULL,
        entity_b TEXT NOT NULL,
        entity_b_type TEXT NOT NULL,
        relationship TEXT NOT NULL DEFAULT 'co_occurrence',
        weight REAL NOT NULL DEFAULT 1.0,
        first_seen TEXT DEFAULT (datetime('now')),
        last_seen TEXT DEFAULT (datetime('now')),
        item_count INTEGER DEFAULT 1,
        UNIQUE(entity_a, entity_a_type, entity_b, entity_b_type, relationship)
    );
    CREATE INDEX IF NOT EXISTS idx_entity_rel_a ON entity_relationships(entity_a, entity_a_type);
    CREATE INDEX IF NOT EXISTS idx_entity_rel_b ON entity_relationships(entity_b, entity_b_type);
    CREATE INDEX IF NOT EXISTS idx_entity_rel_weight ON entity_relationships(weight DESC);
"""


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db():
    """Create tables if they don't exist. Works with both SQLite and PostgreSQL."""
    with get_db() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(_PG_SCHEMA)
            cur.execute(_PG_INDEXES)
            logger.info(f"PostgreSQL database initialized (URL: {DATABASE_URL[:30]}...)")
        else:
            cur.executescript(_SQLITE_SCHEMA)
            # --- Migrations: add columns if they don't exist ---
            _add_column_if_missing(cur, "sources", "error_count", "INTEGER DEFAULT 0")
            _add_column_if_missing(cur, "sources", "last_error", "TEXT")
            _add_column_if_missing(cur, "sources", "last_error_at", "TEXT")
            logger.info(f"SQLite database initialized at {DB_PATH}")


def _add_column_if_missing(cursor, table: str, column: str, col_type: str) -> None:
    """Safely add a column to a table if it doesn't already exist (SQLite only)."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        logger.info(f"Migration: added {table}.{column} ({col_type})")
