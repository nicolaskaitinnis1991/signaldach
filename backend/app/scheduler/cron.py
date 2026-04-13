from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import get_db
from app.scrapers.base import BaseScraper
from app.scrapers.rss_scraper import RssScraper
from app.ai.pipeline import process_batch
from app.ai.entities import extract_entities
from app.ai.trends import update_keyword_trends, store_entity_mentions
from app.error_handling import circuit_breaker, retry, record_scraper_error, clear_scraper_error

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Lazy imports for optional scrapers to avoid import errors if deps missing
SCRAPER_MAP: Dict[str, BaseScraper] = {
    "rss": RssScraper(),
}

try:
    from app.scrapers.reddit_scraper import RedditScraper
    SCRAPER_MAP["reddit"] = RedditScraper()
except ImportError:
    logger.debug("Reddit scraper not available")

try:
    from app.scrapers.twitter_scraper import TwitterScraper
    SCRAPER_MAP["twitter"] = TwitterScraper()
except ImportError:
    logger.debug("Twitter scraper not available")

try:
    from app.scrapers.telegram_scraper import TelegramScraper
    SCRAPER_MAP["telegram"] = TelegramScraper()
except ImportError:
    logger.debug("Telegram scraper not available")

from app.scrapers.coingecko_scraper import CoinGeckoScraper
SCRAPER_MAP["coingecko"] = CoinGeckoScraper()

from app.scrapers.defillama_scraper import DefiLlamaScraper
SCRAPER_MAP["defillama"] = DefiLlamaScraper()

from app.scrapers.fear_greed_scraper import FearGreedScraper
SCRAPER_MAP["fear_greed"] = FearGreedScraper()

from app.scrapers.whale_alert_scraper import WhaleAlertScraper
SCRAPER_MAP["whale_alert"] = WhaleAlertScraper()


async def _do_scrape(scraper: BaseScraper, source: dict) -> list:
    """Inner scrape function (wrapped by retry)."""
    return await scraper.scrape(source)


async def run_scraper_job(source_id: str):
    """Execute a single scraper job for a given source with circuit breaker, retry, and metrics."""
    import time as _time
    start = _time.monotonic()

    # Lazy import to avoid circular imports at module level
    try:
        from app.monitoring import metrics as app_metrics
    except ImportError:
        app_metrics = None

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM sources WHERE id = ? AND enabled = 1", [source_id])
        row = cur.fetchone()
        if not row:
            return
        source = dict(row)

    scraper = SCRAPER_MAP.get(source["type"])
    if not scraper:
        logger.warning(f"No scraper for type: {source['type']}")
        return

    # Circuit breaker check
    if not circuit_breaker.allow_request(source_id):
        logger.warning(f"Circuit OPEN for {source['name']} - skipping scrape")
        return

    try:
        # Retry with exponential backoff
        raw_items = await retry.execute(_do_scrape, scraper, source)

        with get_db() as conn:
            new_items = await scraper.deduplicate(raw_items, source["tenant_id"], conn)

        if not new_items:
            logger.info(f"No new items from {source['name']}")
            circuit_breaker.record_success(source_id)
            clear_scraper_error(source_id)
            duration = _time.monotonic() - start
            if app_metrics:
                app_metrics.record_scrape(source_id, duration, 0)
            return

        processed = await process_batch(new_items, source["category"])

        stored_items = []
        with get_db() as conn:
            cur = conn.cursor()
            for item in processed:
                item_id = uuid.uuid4().hex[:12]
                pub_at = item.published_at.isoformat() if item.published_at else None
                ai_meta_json = json.dumps(item.ai_metadata)

                cur.execute(
                    """INSERT OR IGNORE INTO items
                       (id, tenant_id, source_id, external_id, title, summary, content,
                        url, author, published_at, category, relevance_score, urgency,
                        sentiment, ai_metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item_id,
                        source["tenant_id"],
                        source["id"],
                        item.external_id,
                        item.title,
                        item.summary,
                        item.content,
                        item.url,
                        item.author,
                        pub_at,
                        item.category,
                        item.relevance_score,
                        item.urgency,
                        item.sentiment,
                        ai_meta_json,
                    ),
                )

                # Build dict for broadcasting and trend tracking
                item_dict = {
                    "id": item_id,
                    "title": item.title,
                    "summary": item.summary,
                    "url": item.url,
                    "category": item.category,
                    "relevance_score": item.relevance_score,
                    "urgency": item.urgency,
                    "sentiment": item.sentiment,
                    "published_at": pub_at,
                    "source_name": source["name"],
                    "ai_metadata": item.ai_metadata,
                }
                stored_items.append(item_dict)

                # Store entity mentions
                entities = item.ai_metadata.get("entities", {})
                entity_list = []
                for etype, names in entities.items():
                    # etype is "tokens", "companies", "regulators" - singularize
                    singular = etype.rstrip("s") if etype.endswith("s") else etype
                    for name in names:
                        entity_list.append({"name": name, "entity_type": singular})
                if entity_list:
                    store_entity_mentions(item_id, entity_list, conn=conn)

                # Build entity co-occurrence graph
                try:
                    from app.ai.knowledge_graph import build_co_occurrences
                    from app.ai.entities import extract_entities as _extract
                    all_entities = _extract(f"{item.title} {item.content}")
                    if len(all_entities) >= 2:
                        build_co_occurrences(all_entities, conn=conn)
                except Exception as eg:
                    logger.debug("Knowledge graph update failed: %s", eg)

            # Update keyword trends within the same connection
            if stored_items:
                update_keyword_trends(stored_items, conn=conn)

            # Update last_scraped_at
            cur.execute(
                "UPDATE sources SET last_scraped_at = ? WHERE id = ?",
                [datetime.now(timezone.utc).isoformat(), source_id],
            )

        # Broadcast to WebSocket clients
        if stored_items:
            try:
                from app.routers.ws import broadcast_new_items
                await broadcast_new_items(stored_items)
            except Exception as e:
                logger.debug(f"WebSocket broadcast skipped: {e}")

        # Check alert conditions
        if stored_items:
            try:
                from app.alerts.dispatcher import check_and_dispatch_alerts
                await check_and_dispatch_alerts(source["tenant_id"], stored_items)
            except Exception as e:
                logger.warning(f"Alert dispatch failed: {e}")

        logger.info(f"Stored {len(processed)} items from {source['name']}")

        # Record success
        circuit_breaker.record_success(source_id)
        clear_scraper_error(source_id)
        duration = _time.monotonic() - start
        if app_metrics:
            app_metrics.record_scrape(source_id, duration, len(stored_items))

    except Exception as e:
        logger.error(f"Scraper job failed for {source['name']}: {e}", exc_info=True)
        circuit_breaker.record_failure(source_id)
        record_scraper_error(source_id, str(e))
        duration = _time.monotonic() - start
        if app_metrics:
            app_metrics.record_scrape(source_id, duration, 0, error=True)


def start_scheduler():
    """Load all enabled sources and schedule their scraper jobs."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, type, scrape_frequency_minutes FROM sources WHERE enabled = 1")
            sources = cur.fetchall()
    except Exception:
        logger.warning("No sources table yet, scheduler starting empty.")
        sources = []

    for row in sources:
        source_id, name, source_type, freq = row["id"], row["name"], row["type"], row["scrape_frequency_minutes"]
        if source_type not in SCRAPER_MAP:
            continue
        scheduler.add_job(
            run_scraper_job,
            trigger=IntervalTrigger(minutes=freq),
            args=[source_id],
            id=f"scrape_{source_id}",
            name=f"Scrape {name}",
            replace_existing=True,
        )
        logger.info(f"Scheduled: {name} every {freq}min")

    # Register data collector jobs (time-series pipeline)
    try:
        from app.collectors.scheduler import register_collector_jobs
        register_collector_jobs(scheduler)
    except Exception as e:
        logger.warning("Could not register collector jobs: %s", e)

    # Email digest jobs (daily 07:00 UTC, weekly Monday 07:00 UTC)
    try:
        from apscheduler.triggers.cron import CronTrigger

        async def _send_daily_digest():
            try:
                from app.alerts.email_digest import DigestFrequency, send_all_digests
                result = await send_all_digests(DigestFrequency.DAILY)
                logger.info("Daily digest: sent=%d failed=%d", result["sent"], result["failed"])
            except Exception as e:
                logger.warning("Daily digest job failed: %s", e)

        async def _send_weekly_digest():
            try:
                from app.alerts.email_digest import DigestFrequency, send_all_digests
                result = await send_all_digests(DigestFrequency.WEEKLY)
                logger.info("Weekly digest: sent=%d failed=%d", result["sent"], result["failed"])
            except Exception as e:
                logger.warning("Weekly digest job failed: %s", e)

        scheduler.add_job(
            _send_daily_digest,
            trigger=CronTrigger(hour=7, minute=0),
            id="digest_daily",
            name="Daily Email Digest",
            replace_existing=True,
        )
        scheduler.add_job(
            _send_weekly_digest,
            trigger=CronTrigger(day_of_week="mon", hour=7, minute=0),
            id="digest_weekly",
            name="Weekly Email Digest",
            replace_existing=True,
        )
        logger.info("Email digest jobs scheduled (daily 07:00 UTC, weekly Mon 07:00 UTC)")
    except Exception as e:
        logger.warning("Could not register email digest jobs: %s", e)

    # Daily NAV snapshot at 16:00 UTC
    try:
        from apscheduler.triggers.cron import CronTrigger as _CronTrigger

        async def _daily_nav_snapshot():
            try:
                from app.trading.nav_calculator import record_nav_snapshot
                snapshot = record_nav_snapshot()
                logger.info("Daily NAV snapshot: %.2f", snapshot.get("nav", 0))
            except Exception as e:
                logger.warning("Daily NAV snapshot job failed: %s", e)

        scheduler.add_job(
            _daily_nav_snapshot,
            trigger=_CronTrigger(hour=16, minute=0),
            id="nav_snapshot",
            name="Daily NAV Snapshot",
            replace_existing=True,
        )
        logger.info("NAV snapshot job scheduled (daily 16:00 UTC)")
    except Exception as e:
        logger.warning("Could not register NAV snapshot job: %s", e)

    # Weekly ensemble weight calibration (Sunday 03:00 UTC)
    try:
        from apscheduler.triggers.cron import CronTrigger as _EnsembleCron
        from app.ai.signal_ensemble import _ensemble

        def _calibrate_ensemble():
            try:
                result = _ensemble.calibrate_weights(days=30)
                logger.info("Ensemble calibration complete: %s", result)
            except Exception as e:
                logger.warning("Ensemble calibration failed: %s", e)

        scheduler.add_job(
            _calibrate_ensemble,
            trigger=_EnsembleCron(day_of_week="sun", hour=3, minute=0),
            id="ensemble_calibration",
            name="Ensemble Weight Calibration",
            replace_existing=True,
        )
        logger.info("Ensemble calibration job scheduled (Sunday 03:00 UTC)")
    except Exception as e:
        logger.warning("Could not register ensemble calibration job: %s", e)

    scheduler.start()


def shutdown_scheduler():
    # Stop Binance WebSocket stream if running
    try:
        from app.collectors.binance_collector import stop_ws_stream
        stop_ws_stream()
    except Exception:
        pass
    scheduler.shutdown(wait=False)
