"""initial schema — all tables

Revision ID: c09db5a25440
Revises:
Create Date: 2026-04-01

Complete initial schema for SignalDACH. All tables are created
with IF NOT EXISTS checks so this migration is safe to run on
databases that were bootstrapped via init_db().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c09db5a25440"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    """Check whether a table already exists (works on SQLite + PostgreSQL)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    """Create all core and time-series tables."""

    # --- tenants ---
    if not _table_exists("tenants"):
        op.create_table(
            "tenants",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), unique=True, nullable=False),
            sa.Column("plan", sa.String(), server_default="free"),
            sa.Column("settings", sa.Text(), server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- sources ---
    if not _table_exists("sources"):
        op.create_table(
            "sources",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("url", sa.String()),
            sa.Column("config", sa.Text(), server_default="{}"),
            sa.Column("scrape_frequency_minutes", sa.Integer(), server_default="60"),
            sa.Column("enabled", sa.Integer(), server_default="1"),
            sa.Column("last_scraped_at", sa.DateTime()),
            sa.Column("error_count", sa.Integer(), server_default="0"),
            sa.Column("last_error", sa.Text()),
            sa.Column("last_error_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- items ---
    if not _table_exists("items"):
        op.create_table(
            "items",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("source_id", sa.String(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("external_id", sa.String()),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("summary", sa.Text()),
            sa.Column("content", sa.Text()),
            sa.Column("url", sa.String()),
            sa.Column("author", sa.String()),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("relevance_score", sa.Integer(), server_default="5"),
            sa.Column("urgency", sa.String(), server_default="normal"),
            sa.Column("sentiment", sa.Float()),
            sa.Column("ai_metadata", sa.Text(), server_default="{}"),
            sa.Column("raw_data", sa.Text(), server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "external_id", name="uq_items_tenant_external"),
        )

    # --- alert_configs ---
    if not _table_exists("alert_configs"):
        op.create_table(
            "alert_configs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.String()),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("enabled", sa.Integer(), server_default="1"),
            sa.Column("conditions", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("channels", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- alert_history ---
    if not _table_exists("alert_history"):
        op.create_table(
            "alert_history",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "alert_config_id", sa.String(), sa.ForeignKey("alert_configs.id"), nullable=False
            ),
            sa.Column("item_id", sa.String(), sa.ForeignKey("items.id"), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("metadata", sa.Text(), server_default="{}"),
        )

    # --- keyword_trends ---
    if not _table_exists("keyword_trends"):
        op.create_table(
            "keyword_trends",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("keyword", sa.String(), nullable=False),
            sa.Column("date", sa.String(), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_count_7d", sa.Float(), server_default="0.0"),
            sa.Column("is_spike", sa.Integer(), server_default="0"),
            sa.UniqueConstraint("keyword", "date", name="uq_keyword_trends_kw_date"),
        )

    # --- entity_mentions ---
    if not _table_exists("entity_mentions"):
        op.create_table(
            "entity_mentions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("entity_name", sa.String(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("item_id", sa.String(), sa.ForeignKey("items.id"), nullable=False),
            sa.Column("mentioned_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- users ---
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("email", sa.String(), unique=True, nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("role", sa.String(), server_default="viewer"),
            sa.Column("is_active", sa.Integer(), server_default="1"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- api_keys ---
    if not _table_exists("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("key_hash", sa.String(), nullable=False),
            sa.Column("name", sa.String()),
            sa.Column("permissions", sa.Text(), server_default="{}"),
            sa.Column("is_active", sa.Integer(), server_default="1"),
            sa.Column("last_used_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- token_blacklist ---
    if not _table_exists("token_blacklist"):
        op.create_table(
            "token_blacklist",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("token_jti", sa.String(), unique=True, nullable=False),
            sa.Column("blacklisted_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime()),
        )

    # --- audit_log ---
    if not _table_exists("audit_log"):
        op.create_table(
            "audit_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("category", sa.String(30), nullable=False),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("user_id", sa.String()),
            sa.Column("detail", sa.Text(), server_default="{}"),
            sa.Column("ip_address", sa.String(45)),
            sa.Column("request_id", sa.String(36)),
        )

    # --- price_ticks ---
    if not _table_exists("price_ticks"):
        op.create_table(
            "price_ticks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("symbol", sa.String(20), nullable=False),
            sa.Column("exchange", sa.String(30), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("volume_24h", sa.Float()),
            sa.Column("market_cap", sa.Float()),
            sa.Column("change_pct_24h", sa.Float()),
        )

    # --- market_metrics ---
    if not _table_exists("market_metrics"):
        op.create_table(
            "market_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("metric_type", sa.String(50), nullable=False),
            sa.Column("symbol", sa.String(20)),
            sa.Column("exchange", sa.String(30)),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("metadata_json", sa.Text(), server_default="{}"),
        )

    # --- signal_scores ---
    if not _table_exists("signal_scores"):
        op.create_table(
            "signal_scores",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("symbol", sa.String(20), nullable=False),
            sa.Column("signal_type", sa.String(50), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("confidence", sa.Float()),
            sa.Column("components_json", sa.Text(), server_default="{}"),
            sa.Column("reasoning", sa.Text()),
        )

    # --- onchain_metrics ---
    if not _table_exists("onchain_metrics"):
        op.create_table(
            "onchain_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("metric_type", sa.String(50), nullable=False),
            sa.Column("chain", sa.String(30)),
            sa.Column("protocol", sa.String(50)),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(20)),
            sa.Column("metadata_json", sa.Text(), server_default="{}"),
        )

    # --- ensemble_weights ---
    if not _table_exists("ensemble_weights"):
        op.create_table(
            "ensemble_weights",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("agent_name", sa.String(), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False),
            sa.Column("accuracy", sa.Float()),
            sa.Column("sample_count", sa.Integer()),
            sa.Column("calibrated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "agent_name", "calibrated_at", name="uq_ensemble_agent_calibrated"
            ),
        )

    # --- entity_relationships ---
    if not _table_exists("entity_relationships"):
        op.create_table(
            "entity_relationships",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("entity_a", sa.String(), nullable=False),
            sa.Column("entity_a_type", sa.String(), nullable=False),
            sa.Column("entity_b", sa.String(), nullable=False),
            sa.Column("entity_b_type", sa.String(), nullable=False),
            sa.Column("relationship", sa.String(), nullable=False, server_default="co_occurrence"),
            sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("first_seen", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("item_count", sa.Integer(), server_default="1"),
            sa.UniqueConstraint(
                "entity_a", "entity_a_type", "entity_b", "entity_b_type", "relationship",
                name="uq_entity_rel",
            ),
        )

    # --- paper_orders ---
    if not _table_exists("paper_orders"):
        op.create_table(
            "paper_orders",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("portfolio_id", sa.String(), nullable=False, server_default="default"),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("side", sa.String(), nullable=False),
            sa.Column("order_type", sa.String(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("price", sa.Float()),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("fill_price", sa.Float()),
            sa.Column("fill_quantity", sa.Float()),
            sa.Column("reason", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("filled_at", sa.DateTime()),
        )

    # --- paper_positions ---
    if not _table_exists("paper_positions"):
        op.create_table(
            "paper_positions",
            sa.Column("portfolio_id", sa.String(), nullable=False, server_default="default"),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("avg_entry_price", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("portfolio_id", "symbol"),
        )

    # --- paper_portfolio_state ---
    if not _table_exists("paper_portfolio_state"):
        op.create_table(
            "paper_portfolio_state",
            sa.Column("portfolio_id", sa.String(), primary_key=True, server_default="default"),
            sa.Column("initial_cash", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("current_cash", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("high_water_mark", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # --- nav_snapshots ---
    if not _table_exists("nav_snapshots"):
        op.create_table(
            "nav_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("portfolio_id", sa.String(), nullable=False, server_default="default"),
            sa.Column("nav", sa.Float(), nullable=False),
            sa.Column("positions_value", sa.Float(), nullable=False),
            sa.Column("cash", sa.Float(), nullable=False),
            sa.Column("management_fee", sa.Float(), server_default="0"),
            sa.Column("performance_fee", sa.Float(), server_default="0"),
            sa.Column("high_water_mark", sa.Float(), nullable=False),
            sa.Column("snapshot_date", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("portfolio_id", "snapshot_date", name="uq_nav_portfolio_date"),
        )

    # --- Seed default tenant ---
    op.execute(
        "INSERT INTO tenants (id, name, slug, plan) "
        "VALUES ('default', 'SignalDACH', 'signaldach', 'pro') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    for table in [
        "nav_snapshots",
        "paper_portfolio_state",
        "paper_positions",
        "paper_orders",
        "entity_relationships",
        "ensemble_weights",
        "onchain_metrics",
        "signal_scores",
        "market_metrics",
        "price_ticks",
        "audit_log",
        "token_blacklist",
        "api_keys",
        "entity_mentions",
        "keyword_trends",
        "alert_history",
        "alert_configs",
        "items",
        "sources",
        "users",
        "tenants",
    ]:
        op.drop_table(table)
