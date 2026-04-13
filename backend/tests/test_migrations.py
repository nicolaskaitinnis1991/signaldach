"""Tests for Alembic migration setup.

Verifies configuration files exist and that migrations can run
successfully on a fresh SQLite database.
"""

import os
import sqlite3
import tempfile
from contextlib import contextmanager

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))


@contextmanager
def _temp_alembic_db():
    """Create a temporary SQLite DB and configure Alembic to use it.

    Temporarily clears DATABASE_URL env vars so env.py doesn't override
    the programmatic URL.
    """
    from alembic.config import Config

    saved = {}
    for key in ("SIGNALDACH_DATABASE_URL", "DATABASE_URL"):
        saved[key] = os.environ.pop(key, None)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_migrations.db")
            url = f"sqlite:///{db_path}"

            cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
            cfg.set_main_option("sqlalchemy.url", url)

            yield cfg, db_path
    finally:
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val


def test_alembic_config_exists():
    """alembic.ini must be present in the backend root."""
    path = os.path.join(BACKEND_DIR, "alembic.ini")
    assert os.path.isfile(path), f"Missing {path}"


def test_alembic_env_exists():
    """alembic/env.py must be present."""
    path = os.path.join(BACKEND_DIR, "alembic", "env.py")
    assert os.path.isfile(path), f"Missing {path}"


def test_initial_migration_exists():
    """The initial schema migration (c09db5a25440) must exist."""
    versions_dir = os.path.join(BACKEND_DIR, "alembic", "versions")
    files = os.listdir(versions_dir)
    initial_files = [f for f in files if "c09db5a25440" in f]
    assert len(initial_files) == 1, f"Expected initial migration, found: {files}"


def test_index_migration_exists():
    """The index migration (d7e2f3a14b01) must exist."""
    versions_dir = os.path.join(BACKEND_DIR, "alembic", "versions")
    files = os.listdir(versions_dir)
    index_files = [f for f in files if "d7e2f3a14b01" in f]
    assert len(index_files) == 1, f"Expected index migration, found: {files}"


def test_timescaledb_migration_exists():
    """The TimescaleDB migration (e8f4a5b26c12) must exist."""
    versions_dir = os.path.join(BACKEND_DIR, "alembic", "versions")
    files = os.listdir(versions_dir)
    ts_files = [f for f in files if "e8f4a5b26c12" in f]
    assert len(ts_files) == 1, f"Expected TimescaleDB migration, found: {files}"


def test_migration_script_exists():
    """scripts/migrate.sh must exist and be executable."""
    path = os.path.join(BACKEND_DIR, "scripts", "migrate.sh")
    assert os.path.isfile(path), f"Missing {path}"
    assert os.access(path, os.X_OK), f"{path} is not executable"


def test_all_tables_exist_after_upgrade():
    """Running alembic upgrade head on a fresh SQLite DB creates all expected tables."""
    from alembic import command

    with _temp_alembic_db() as (alembic_cfg, db_path):
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {
            "tenants", "sources", "items",
            "alert_configs", "alert_history",
            "keyword_trends", "entity_mentions",
            "users", "api_keys", "token_blacklist",
            "audit_log",
            "price_ticks", "market_metrics", "signal_scores", "onchain_metrics",
            "ensemble_weights", "entity_relationships",
            "paper_orders", "paper_positions", "paper_portfolio_state", "nav_snapshots",
            "alembic_version",
        }

        missing = expected_tables - tables
        assert not missing, f"Missing tables after migration: {missing}"


def test_default_tenant_seeded():
    """The default tenant must be seeded after running migrations."""
    from alembic import command

    with _temp_alembic_db() as (alembic_cfg, db_path):
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT id, slug FROM tenants WHERE id = 'default'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Default tenant not seeded"
        assert row[1] == "signaldach", f"Default tenant slug wrong: {row[1]}"


def test_migrations_idempotent_on_existing_db():
    """Migrations must be safe to run on a DB that already has tables (from init_db)."""
    from alembic import command

    with _temp_alembic_db() as (alembic_cfg, db_path):
        # First run
        command.upgrade(alembic_cfg, "head")

        # Second run should not raise
        command.upgrade(alembic_cfg, "head")

        # Verify still at head
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version_num FROM alembic_version")
        version = cursor.fetchone()
        conn.close()

        assert version is not None, "No alembic version after double upgrade"
