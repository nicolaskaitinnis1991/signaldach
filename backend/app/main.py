import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Sentry error tracking (only if DSN is configured)
if settings.sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            environment="production" if settings.auth_enabled else "development",
        )
    except ImportError:
        pass  # sentry-sdk not installed
from app.database import init_db
from app.middleware import SecurityMiddleware
from app.routers import health, items, sources, analytics, alerts_api, ws
from app.routers.market_data import router as market_data_router
from app.routers.entity_graph import router as entity_graph_router
from app.routers.signals import router as signals_router
from app.routers.portfolio import router as portfolio_router
from app.routers.chat import router as chat_router
from app.routers.scorecard import router as scorecard_router
from app.routers.fund import router as fund_router
from app.routers.auth_router import router as auth_router
from app.routers.paper_trading import router as paper_trading_router
from app.routers.report import router as report_router
from app.routers.tax_calculator import router as tax_router
from app.routers.horizon import router as horizon_router
from app.routers.compliance import router as compliance_router
from app.routers.scam_monitor import router as scam_monitor_router
from app.routers.audit_router import router as audit_router
from app.scheduler.cron import start_scheduler, shutdown_scheduler
from app.error_handling import register_exception_handlers
from app.monitoring import router as monitoring_router, metrics as app_metrics

if settings.log_format == "json":
    import json as _json

    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return _json.dumps({
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.") + f"{record.msecs:03.0f}Z",
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
                **({"exc": self.formatException(record.exc_info)} if record.exc_info else {}),
            })

    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    logging.root.handlers = [_handler]
    logging.root.setLevel(getattr(logging, settings.log_level))
else:
    logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SignalDACH backend...")

    # Validate environment variables before anything else
    from app.env_validation import validate_environment
    env_status = validate_environment()
    if not env_status["valid"]:
        for w in env_status["warnings"]:
            logger.warning("ENV: %s", w)
    else:
        for w in env_status["warnings"]:
            logger.warning("ENV: %s", w)
        for i in env_status["info"]:
            logger.info("ENV: %s", i)
    logger.info("Environment: %s (valid=%s)", env_status["environment"], env_status["valid"])

    init_db()
    from app.trading.paper_db import init_paper_tables
    init_paper_tables()
    logger.info("Database initialized.")

    # Redis connection pool + stream consumer groups
    from app.redis_client import init_redis, shutdown_redis, ensure_stream_groups
    await init_redis()
    await ensure_stream_groups()

    # Auto-seed sources on first startup if DB is empty
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sources")
            source_count = cur.fetchone()[0]
            if source_count == 0:
                logger.info("No sources found — auto-seeding defaults...")
                from app.scrapers.rss_scraper import DEFAULT_RSS_SOURCES
                for source in DEFAULT_RSS_SOURCES:
                    try:
                        cur.execute(
                            """INSERT OR IGNORE INTO sources (id, tenant_id, name, type, category, url, scrape_frequency_minutes)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (source["id"], "default", source["name"], source["type"],
                             source["category"], source["url"], source["frequency"]),
                        )
                    except Exception as e:
                        logger.warning("Failed to auto-seed source %s: %s", source.get("id", "?"), e)
                conn.commit()
                logger.info(f"Auto-seeded {len(DEFAULT_RSS_SOURCES)} sources.")
    except Exception as e:
        logger.warning(f"Auto-seed failed: {e}")

    # Start WebSocket Redis subscriber for cross-worker broadcast
    from app.routers.ws import start_ws_subscriber, stop_ws_subscriber
    start_ws_subscriber()

    start_scheduler()
    logger.info("Scheduler started.")
    yield
    shutdown_scheduler()
    stop_ws_subscriber()
    await shutdown_redis()
    logger.info("SignalDACH backend shut down.")


app = FastAPI(
    title="SignalDACH",
    description="Market Intelligence & Regulatory Tracker for Crypto Funds (DACH)",
    version="0.3.0",
    lifespan=lifespan,
)

# Security middleware (rate limiting, request IDs, security headers, logging)
app.add_middleware(SecurityMiddleware)

# CORS middleware (must be added after SecurityMiddleware so it runs first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers
register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth_router)
app.include_router(items.router)
app.include_router(sources.router)
app.include_router(analytics.router)
app.include_router(alerts_api.router)
app.include_router(ws.router)
app.include_router(monitoring_router)

# Prometheus expects /metrics at root
from app.monitoring import prometheus_metrics as _prom_handler
app.get("/metrics", include_in_schema=False)(_prom_handler)
app.include_router(report_router)
app.include_router(tax_router)
app.include_router(horizon_router)
app.include_router(compliance_router)
app.include_router(scam_monitor_router)
app.include_router(audit_router)
app.include_router(market_data_router)
app.include_router(entity_graph_router)
app.include_router(signals_router)
app.include_router(portfolio_router)
app.include_router(chat_router)
app.include_router(scorecard_router)
app.include_router(fund_router)
app.include_router(paper_trading_router)

# API v1 — all endpoints also available under /api/v1/ prefix
from app.api_v1 import v1_router
app.include_router(v1_router)


# ---------------------------------------------------------------------------
# Additional endpoints (called by frontend)
# ---------------------------------------------------------------------------

@app.get("/api/flags", tags=["system"])
async def feature_flags_status():
    """Feature flags — current state of all flags (admin)."""
    from app.feature_flags import get_flag_info
    return {"flags": get_flag_info()}


@app.get("/status", tags=["system"])
async def system_status():
    """System status endpoint for frontend health checks."""
    from app.database import get_db, USE_POSTGRES
    import time

    status_info = {
        "status": "ok",
        "service": "signal-dach",
        "version": app.version,
        "database": "postgresql" if USE_POSTGRES else "sqlite",
        "auth_enabled": settings.auth_enabled,
    }

    # Quick DB connectivity check
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM sources")
            row = cur.fetchone()
            status_info["sources_count"] = row["cnt"] if isinstance(row, dict) else row[0]
            cur.execute("SELECT COUNT(*) as cnt FROM items")
            row = cur.fetchone()
            status_info["items_count"] = row["cnt"] if isinstance(row, dict) else row[0]
            status_info["database_status"] = "connected"
    except Exception as e:
        status_info["database_status"] = "error"
        status_info["database_error"] = str(e)
        logger.warning(f"Database health check failed: {e}")

    return status_info


@app.post("/webhooks/test", tags=["webhooks"])
async def webhook_test(payload: dict = {}):
    """Test webhook endpoint for frontend webhook configuration testing."""
    logger.info(f"Webhook test received: {list(payload.keys()) if payload else 'empty'}")
    return {
        "status": "received",
        "message": "Webhook test successful",
        "received_keys": list(payload.keys()) if payload else [],
    }
