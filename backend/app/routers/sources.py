import logging

from fastapi import APIRouter, Query
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
async def list_sources(
    tenant_id: str = Query(default="default", max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"),
):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM sources WHERE tenant_id = ? ORDER BY category, name",
            [tenant_id],
        )
        rows = [dict(row) for row in cur.fetchall()]
    return {"sources": rows}


@router.post("/seed-defaults")
async def seed_default_sources(
    tenant_id: str = Query(default="default", max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"),
):
    """Seed the default regulatory and news sources."""
    from app.scrapers.rss_scraper import DEFAULT_RSS_SOURCES

    seeded = 0
    with get_db() as conn:
        cur = conn.cursor()
        for source in DEFAULT_RSS_SOURCES:
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO sources (id, tenant_id, name, type, category, url, scrape_frequency_minutes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        source["id"],
                        tenant_id,
                        source["name"],
                        source["type"],
                        source["category"],
                        source["url"],
                        source["frequency"],
                    ),
                )
                seeded += 1
            except Exception as e:
                logger.warning("Failed to seed source %s: %s", source.get("id", "?"), e)
        conn.commit()
    return {"status": "seeded", "seeded": seeded, "total": len(DEFAULT_RSS_SOURCES)}
