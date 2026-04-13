"""SQLAlchemy ORM models for SignalDACH.

These models are the single source of truth for the database schema.
Alembic autogenerate reads these to create migrations.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Core tables (existing schema, now as ORM models)
# ---------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    plan = Column(String, default="free")
    settings = Column(Text, default="{}")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    sources = relationship("Source", back_populates="tenant")
    items = relationship("Item", back_populates="tenant")


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    url = Column(String)
    config = Column(Text, default="{}")
    scrape_frequency_minutes = Column(Integer, default=60)
    enabled = Column(Integer, default=1)
    last_scraped_at = Column(DateTime)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    last_error_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="sources")
    items = relationship("Item", back_populates="source")


class Item(Base):
    __tablename__ = "items"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False)
    external_id = Column(String)
    title = Column(String, nullable=False)
    summary = Column(Text)
    content = Column(Text)
    url = Column(String)
    author = Column(String)
    published_at = Column(DateTime)
    category = Column(String, nullable=False)
    relevance_score = Column(Integer, default=5)
    urgency = Column(String, default="normal")
    sentiment = Column(Float)
    ai_metadata = Column(Text, default="{}")
    raw_data = Column(Text, default="{}")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_items_tenant_external"),
        Index("idx_items_tenant_category", "tenant_id", "category"),
        Index("idx_items_tenant_urgency", "tenant_id", "urgency"),
        Index("idx_items_tenant_relevance", "tenant_id", "relevance_score"),
        Index("idx_items_tenant_external", "tenant_id", "external_id"),
    )

    tenant = relationship("Tenant", back_populates="items")
    source = relationship("Source", back_populates="items")
    entity_mentions = relationship("EntityMention", back_populates="item")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String)
    name = Column(String, nullable=False)
    enabled = Column(Integer, default=1)
    conditions = Column(Text, nullable=False, default="{}")
    channels = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(String, primary_key=True)
    alert_config_id = Column(String, ForeignKey("alert_configs.id"), nullable=False)
    item_id = Column(String, ForeignKey("items.id"), nullable=False)
    channel = Column(String, nullable=False)
    status = Column(String, nullable=False)
    sent_at = Column(DateTime, server_default=func.now())
    extra_metadata = Column("metadata", Text, default="{}")


class KeywordTrend(Base):
    __tablename__ = "keyword_trends"

    id = Column(String, primary_key=True)
    keyword = Column(String, nullable=False)
    date = Column(String, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    avg_count_7d = Column(Float, default=0.0)
    is_spike = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("keyword", "date", name="uq_keyword_trends_kw_date"),
        Index("idx_keyword_trends_date", "date"),
        Index("idx_keyword_trends_spike", "is_spike", "date"),
    )


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    id = Column(String, primary_key=True)
    entity_name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    item_id = Column(String, ForeignKey("items.id"), nullable=False)
    mentioned_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_entity_mentions_name", "entity_name", "entity_type"),
        Index("idx_entity_mentions_item", "item_id"),
        Index("idx_entity_mentions_date", "mentioned_at"),
    )

    item = relationship("Item", back_populates="entity_mentions")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="viewer")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    api_keys = relationship("ApiKey", back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String, nullable=False)
    name = Column(String)
    permissions = Column(Text, default="{}")
    is_active = Column(Integer, default=1)
    last_used_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_api_keys_hash", "key_hash"),
        Index("idx_api_keys_user", "user_id"),
    )

    user = relationship("User", back_populates="api_keys")


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(String, primary_key=True)
    token_jti = Column(String, unique=True, nullable=False)
    blacklisted_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)


# ---------------------------------------------------------------------------
# Time-series tables (Phase 1B — for market data)
# ---------------------------------------------------------------------------


class PriceTick(Base):
    """Real-time price data from exchanges. High-frequency time-series.

    On TimescaleDB this becomes a hypertable partitioned by `ts`.
    On SQLite it's a regular table with indexes.
    """

    __tablename__ = "price_ticks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, server_default=func.now())
    symbol = Column(String(20), nullable=False)  # e.g. "BTC/USDT"
    exchange = Column(String(30), nullable=False)  # e.g. "binance"
    price = Column(Float, nullable=False)
    volume_24h = Column(Float)
    market_cap = Column(Float)
    change_pct_24h = Column(Float)

    __table_args__ = (
        Index("idx_price_ticks_symbol_ts", "symbol", "ts"),
        Index("idx_price_ticks_exchange_ts", "exchange", "ts"),
    )


class MarketMetric(Base):
    """Aggregated market metrics — funding rates, OI, liquidations, fear/greed.

    Collected at regular intervals (1m–5m). Hypertable on TimescaleDB.
    """

    __tablename__ = "market_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, server_default=func.now())
    metric_type = Column(String(50), nullable=False)  # funding_rate, open_interest, ...
    symbol = Column(String(20))  # nullable for global metrics
    exchange = Column(String(30))
    value = Column(Float, nullable=False)
    metadata_json = Column(Text, default="{}")

    __table_args__ = (
        Index("idx_market_metrics_type_ts", "metric_type", "ts"),
        Index("idx_market_metrics_symbol_ts", "symbol", "ts"),
    )


class SignalScore(Base):
    """AI-generated signal scores per asset/topic over time.

    Each row = one signal evaluation at a point in time. Hypertable on TimescaleDB.
    """

    __tablename__ = "signal_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, server_default=func.now())
    symbol = Column(String(20), nullable=False)
    signal_type = Column(String(50), nullable=False)  # sentiment, momentum, anomaly, composite
    score = Column(Float, nullable=False)  # -1.0 to 1.0
    confidence = Column(Float)  # 0.0 to 1.0
    components_json = Column(Text, default="{}")  # breakdown of sub-scores
    reasoning = Column(Text)  # AI explanation

    __table_args__ = (
        Index("idx_signal_scores_symbol_ts", "symbol", "ts"),
        Index("idx_signal_scores_type_ts", "signal_type", "ts"),
    )


class AuditLog(Base):
    """Immutable, append-only audit trail for fund operations and security events.

    Categories:
      - auth: login, logout, token_refresh, failed_login
      - signal: signal_generated, signal_evaluated
      - risk: risk_assessment, limit_breach, drawdown_alert
      - fund: position_change, nav_calculated, fee_charged
      - config: settings_changed, source_toggled, alert_modified
      - system: scraper_error, circuit_breaker, deployment
    """

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, server_default=func.now())
    category = Column(String(30), nullable=False)
    action = Column(String(100), nullable=False)
    user_id = Column(String, nullable=True)
    detail = Column(Text, default="{}")
    ip_address = Column(String(45), nullable=True)
    request_id = Column(String(36), nullable=True)

    __table_args__ = (
        Index("idx_audit_log_ts", "ts"),
        Index("idx_audit_log_category", "category", "ts"),
        Index("idx_audit_log_user", "user_id", "ts"),
        Index("idx_audit_log_action", "action", "ts"),
    )


class OnChainMetric(Base):
    """On-chain data — whale movements, TVL, gas, stablecoin flows.

    From Etherscan, DefiLlama, whale trackers. Hypertable on TimescaleDB.
    """

    __tablename__ = "onchain_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, server_default=func.now())
    metric_type = Column(String(50), nullable=False)  # whale_transfer, tvl, gas_price, ...
    chain = Column(String(30))  # ethereum, bitcoin, solana, ...
    protocol = Column(String(50))  # aave, uniswap, ...
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # USD, ETH, BTC, ...
    metadata_json = Column(Text, default="{}")

    __table_args__ = (
        Index("idx_onchain_metrics_type_ts", "metric_type", "ts"),
        Index("idx_onchain_metrics_chain_ts", "chain", "ts"),
        Index("idx_onchain_metrics_protocol_ts", "protocol", "ts"),
    )


# ---------------------------------------------------------------------------
# Ensemble weights (adaptive agent calibration)
# ---------------------------------------------------------------------------


class EnsembleWeight(Base):
    """Calibrated weights for multi-agent signal ensemble."""

    __tablename__ = "ensemble_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    accuracy = Column(Float)
    sample_count = Column(Integer)
    calibrated_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("agent_name", "calibrated_at", name="uq_ensemble_agent_calibrated"),
        Index("idx_ensemble_weights_agent", "agent_name"),
    )


# ---------------------------------------------------------------------------
# Entity knowledge graph (Phase 2B)
# ---------------------------------------------------------------------------


class EntityRelationship(Base):
    """Co-occurrence and explicit relationships between entities."""

    __tablename__ = "entity_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_a = Column(String, nullable=False)
    entity_a_type = Column(String, nullable=False)
    entity_b = Column(String, nullable=False)
    entity_b_type = Column(String, nullable=False)
    relationship = Column(String, nullable=False, default="co_occurrence")
    weight = Column(Float, nullable=False, default=1.0)
    first_seen = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime, server_default=func.now())
    item_count = Column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint(
            "entity_a", "entity_a_type", "entity_b", "entity_b_type", "relationship",
            name="uq_entity_rel",
        ),
        Index("idx_entity_rel_a", "entity_a", "entity_a_type"),
        Index("idx_entity_rel_b", "entity_b", "entity_b_type"),
        Index("idx_entity_rel_weight", "weight"),
    )


# ---------------------------------------------------------------------------
# Paper trading (simulation engine)
# ---------------------------------------------------------------------------


class PaperOrder(Base):
    """Simulated trading orders."""

    __tablename__ = "paper_orders"

    id = Column(String, primary_key=True)
    portfolio_id = Column(String, nullable=False, default="default")
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    order_type = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    status = Column(String, nullable=False, default="pending")
    fill_price = Column(Float)
    fill_quantity = Column(Float)
    reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    filled_at = Column(DateTime)

    __table_args__ = (
        Index("idx_paper_orders_portfolio", "portfolio_id", "status"),
        Index("idx_paper_orders_symbol", "symbol", "status"),
    )


class PaperPosition(Base):
    """Current simulated positions per portfolio."""

    __tablename__ = "paper_positions"

    portfolio_id = Column(String, nullable=False, default="default", primary_key=True)
    symbol = Column(String, nullable=False, primary_key=True)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_entry_price = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PaperPortfolioState(Base):
    """Cash and high-water-mark state for paper portfolios."""

    __tablename__ = "paper_portfolio_state"

    portfolio_id = Column(String, primary_key=True, default="default")
    initial_cash = Column(Float, nullable=False, default=100000.0)
    current_cash = Column(Float, nullable=False, default=100000.0)
    high_water_mark = Column(Float, nullable=False, default=100000.0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class NavSnapshot(Base):
    """Daily NAV snapshots for paper portfolios."""

    __tablename__ = "nav_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(String, nullable=False, default="default")
    nav = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    management_fee = Column(Float, default=0)
    performance_fee = Column(Float, default=0)
    high_water_mark = Column(Float, nullable=False)
    snapshot_date = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("portfolio_id", "snapshot_date", name="uq_nav_portfolio_date"),
        Index("idx_nav_snapshots_portfolio_date", "portfolio_id", "snapshot_date"),
    )
