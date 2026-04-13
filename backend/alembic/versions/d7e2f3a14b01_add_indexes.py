"""add indexes

Revision ID: d7e2f3a14b01
Revises: c09db5a25440
Create Date: 2026-04-07

Add all indexes for query performance. Each index uses IF NOT EXISTS
(via raw SQL) so this is safe on databases bootstrapped by init_db().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e2f3a14b01"
down_revision: Union[str, Sequence[str], None] = "c09db5a25440"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all indexes (idempotent via IF NOT EXISTS)."""

    _INDEXES = [
        # items
        "CREATE INDEX IF NOT EXISTS idx_items_tenant_category ON items(tenant_id, category)",
        "CREATE INDEX IF NOT EXISTS idx_items_tenant_urgency ON items(tenant_id, urgency)",
        "CREATE INDEX IF NOT EXISTS idx_items_tenant_relevance ON items(tenant_id, relevance_score)",
        "CREATE INDEX IF NOT EXISTS idx_items_tenant_external ON items(tenant_id, external_id)",
        # keyword_trends
        "CREATE INDEX IF NOT EXISTS idx_keyword_trends_date ON keyword_trends(date)",
        "CREATE INDEX IF NOT EXISTS idx_keyword_trends_spike ON keyword_trends(is_spike, date)",
        # entity_mentions
        "CREATE INDEX IF NOT EXISTS idx_entity_mentions_name ON entity_mentions(entity_name, entity_type)",
        "CREATE INDEX IF NOT EXISTS idx_entity_mentions_item ON entity_mentions(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_entity_mentions_date ON entity_mentions(mentioned_at)",
        # users / auth
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(token_jti)",
        # audit_log
        "CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_category ON audit_log(category, ts)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, ts)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action, ts)",
        # time-series
        "CREATE INDEX IF NOT EXISTS idx_price_ticks_symbol_ts ON price_ticks(symbol, ts)",
        "CREATE INDEX IF NOT EXISTS idx_price_ticks_exchange_ts ON price_ticks(exchange, ts)",
        "CREATE INDEX IF NOT EXISTS idx_market_metrics_type_ts ON market_metrics(metric_type, ts)",
        "CREATE INDEX IF NOT EXISTS idx_market_metrics_symbol_ts ON market_metrics(symbol, ts)",
        "CREATE INDEX IF NOT EXISTS idx_signal_scores_symbol_ts ON signal_scores(symbol, ts)",
        "CREATE INDEX IF NOT EXISTS idx_signal_scores_type_ts ON signal_scores(signal_type, ts)",
        "CREATE INDEX IF NOT EXISTS idx_onchain_metrics_type_ts ON onchain_metrics(metric_type, ts)",
        "CREATE INDEX IF NOT EXISTS idx_onchain_metrics_chain_ts ON onchain_metrics(chain, ts)",
        "CREATE INDEX IF NOT EXISTS idx_onchain_metrics_protocol_ts ON onchain_metrics(protocol, ts)",
        # ensemble
        "CREATE INDEX IF NOT EXISTS idx_ensemble_weights_agent ON ensemble_weights(agent_name)",
        # entity graph
        "CREATE INDEX IF NOT EXISTS idx_entity_rel_a ON entity_relationships(entity_a, entity_a_type)",
        "CREATE INDEX IF NOT EXISTS idx_entity_rel_b ON entity_relationships(entity_b, entity_b_type)",
        "CREATE INDEX IF NOT EXISTS idx_entity_rel_weight ON entity_relationships(weight)",
        # paper trading
        "CREATE INDEX IF NOT EXISTS idx_paper_orders_portfolio ON paper_orders(portfolio_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol ON paper_orders(symbol, status)",
        "CREATE INDEX IF NOT EXISTS idx_nav_snapshots_portfolio_date ON nav_snapshots(portfolio_id, snapshot_date)",
    ]

    for stmt in _INDEXES:
        op.execute(sa.text(stmt))


def downgrade() -> None:
    """Drop all custom indexes."""

    _INDEX_NAMES = [
        "idx_items_tenant_category",
        "idx_items_tenant_urgency",
        "idx_items_tenant_relevance",
        "idx_items_tenant_external",
        "idx_keyword_trends_date",
        "idx_keyword_trends_spike",
        "idx_entity_mentions_name",
        "idx_entity_mentions_item",
        "idx_entity_mentions_date",
        "idx_users_email",
        "idx_api_keys_hash",
        "idx_api_keys_user",
        "idx_token_blacklist_jti",
        "idx_audit_log_ts",
        "idx_audit_log_category",
        "idx_audit_log_user",
        "idx_audit_log_action",
        "idx_price_ticks_symbol_ts",
        "idx_price_ticks_exchange_ts",
        "idx_market_metrics_type_ts",
        "idx_market_metrics_symbol_ts",
        "idx_signal_scores_symbol_ts",
        "idx_signal_scores_type_ts",
        "idx_onchain_metrics_type_ts",
        "idx_onchain_metrics_chain_ts",
        "idx_onchain_metrics_protocol_ts",
        "idx_ensemble_weights_agent",
        "idx_entity_rel_a",
        "idx_entity_rel_b",
        "idx_entity_rel_weight",
        "idx_paper_orders_portfolio",
        "idx_paper_orders_symbol",
        "idx_nav_snapshots_portfolio_date",
    ]

    for name in _INDEX_NAMES:
        op.drop_index(name)
