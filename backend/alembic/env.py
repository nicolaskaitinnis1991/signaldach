"""Alembic environment configuration for SignalDACH.

Reads DATABASE_URL from environment (SIGNALDACH_DATABASE_URL or DATABASE_URL).
Falls back to SQLite for local development.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

from alembic import context

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Resolve database URL from environment
# ---------------------------------------------------------------------------

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "signaldach.db")

# Only override the ini/programmatic URL if an explicit env var is set.
# This lets tests (and alembic.ini) control the URL without env.py clobbering it.
_ENV_URL = os.environ.get("SIGNALDACH_DATABASE_URL") or os.environ.get("DATABASE_URL")

if _ENV_URL:
    config.set_main_option("sqlalchemy.url", _ENV_URL)
else:
    # If no env var AND no URL was set programmatically, fall back to local SQLite
    current_url = config.get_main_option("sqlalchemy.url")
    if not current_url or current_url == "driver://user:pass@localhost/dbname":
        config.set_main_option("sqlalchemy.url", f"sqlite:///{_DB_PATH}")

_DATABASE_URL = config.get_main_option("sqlalchemy.url")
_IS_POSTGRES = _DATABASE_URL.startswith("postgresql://") or _DATABASE_URL.startswith("postgres://")


# ---------------------------------------------------------------------------
# TimescaleDB hypertable creation helper
# ---------------------------------------------------------------------------

_HYPERTABLES = ["price_ticks", "market_metrics", "signal_scores", "onchain_metrics"]


def _create_timescaledb_hypertables(connection) -> None:
    """Convert time-series tables to TimescaleDB hypertables if extension is available."""
    if not _IS_POSTGRES:
        return

    try:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        connection.commit()
    except Exception:
        # TimescaleDB not installed — skip silently
        connection.rollback()
        return

    for table in _HYPERTABLES:
        try:
            connection.execute(
                text(
                    f"SELECT create_hypertable('{table}', 'ts', "
                    f"if_not_exists => TRUE, migrate_data => TRUE)"
                )
            )
            connection.commit()
        except Exception:
            connection.rollback()


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connected to database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

        # After migrations: create hypertables on PostgreSQL + TimescaleDB
        _create_timescaledb_hypertables(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
