"""enable TimescaleDB hypertables for time-series tables

Revision ID: e8f4a5b26c12
Revises: d7e2f3a14b01
Create Date: 2026-04-07

Only runs on PostgreSQL with TimescaleDB extension installed.
On SQLite this migration is a no-op.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f4a5b26c12"
down_revision: Union[str, Sequence[str], None] = "d7e2f3a14b01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_HYPERTABLES = ["price_ticks", "market_metrics", "signal_scores", "onchain_metrics"]


def upgrade() -> None:
    """Convert time-series tables to TimescaleDB hypertables with compression."""
    conn = op.get_bind()

    # Only run on PostgreSQL
    if conn.dialect.name != "postgresql":
        return

    # Enable TimescaleDB extension
    try:
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
    except Exception:
        # TimescaleDB not installed — skip silently
        return

    # Convert to hypertables
    for table in _HYPERTABLES:
        try:
            op.execute(
                sa.text(
                    f"SELECT create_hypertable('{table}', 'ts', "
                    f"if_not_exists => TRUE, migrate_data => TRUE)"
                )
            )
        except Exception:
            pass  # Already a hypertable or not supported

    # Compression policies for high-frequency tables
    for table in ["price_ticks", "market_metrics"]:
        try:
            op.execute(
                sa.text(
                    f"ALTER TABLE {table} SET ("
                    f"timescaledb.compress, "
                    f"timescaledb.compress_segmentby = 'symbol')"
                )
            )
            op.execute(
                sa.text(
                    f"SELECT add_compression_policy('{table}', "
                    f"INTERVAL '30 days', if_not_exists => TRUE)"
                )
            )
        except Exception:
            pass


def downgrade() -> None:
    """Remove compression policies. Hypertables cannot be reverted without data loss."""
    conn = op.get_bind()

    if conn.dialect.name != "postgresql":
        return

    for table in ["price_ticks", "market_metrics"]:
        try:
            op.execute(
                sa.text(f"SELECT remove_compression_policy('{table}', if_exists => TRUE)")
            )
        except Exception:
            pass
