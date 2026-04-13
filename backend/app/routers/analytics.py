from __future__ import annotations

import json
import time
from collections import Counter

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import get_db, USE_POSTGRES

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])

# Cache for top keywords (avoid loading all ai_metadata on every request)
_keywords_cache: dict = {"data": [], "timestamp": 0.0, "key": ""}
_KEYWORDS_CACHE_TTL = 60  # seconds


def _date_offset_expr(days_param_index: int = 1) -> str:
    """Return a SQL expression for 'now minus N days' compatible with both SQLite and PostgreSQL.

    For SQLite:    datetime('now', ? || ' days')   — expects e.g. '-7'
    For PostgreSQL: NOW() + (? || ' days')::INTERVAL  — expects e.g. '-7'
    """
    if USE_POSTGRES:
        return "NOW() + (? || ' days')::INTERVAL"
    return "datetime('now', ? || ' days')"


def _extract_dow() -> str:
    """Day-of-week extraction: SQLite strftime vs PostgreSQL EXTRACT."""
    if USE_POSTGRES:
        return "EXTRACT(DOW FROM created_at)::INTEGER"
    return "CAST(strftime('%w', created_at) AS INTEGER)"


def _extract_hour() -> str:
    """Hour extraction: SQLite strftime vs PostgreSQL EXTRACT."""
    if USE_POSTGRES:
        return "EXTRACT(HOUR FROM created_at)::INTEGER"
    return "CAST(strftime('%H', created_at) AS INTEGER)"


@router.get("")
async def get_analytics(tenant_id: str = "default", days: int = 7):
    """Return aggregated analytics for the dashboard."""
    with get_db() as conn:
        cur = conn.cursor()

        date_filter = _date_offset_expr()

        # Items by category
        cur.execute(
            f"""SELECT category, COUNT(*) as count
               FROM items
               WHERE tenant_id = ?
                 AND created_at >= {date_filter}
               GROUP BY category
               ORDER BY count DESC""",
            [tenant_id, -days],
        )
        by_category = [{"category": r["category"], "count": r["count"]} for r in cur.fetchall()]

        # Items by urgency
        cur.execute(
            f"""SELECT urgency, COUNT(*) as count
               FROM items
               WHERE tenant_id = ?
                 AND created_at >= {date_filter}
               GROUP BY urgency""",
            [tenant_id, -days],
        )
        by_urgency = [{"urgency": r["urgency"], "count": r["count"]} for r in cur.fetchall()]

        # Items per day
        cur.execute(
            f"""SELECT DATE(created_at) as day, category, COUNT(*) as count
               FROM items
               WHERE tenant_id = ?
                 AND created_at >= {date_filter}
               GROUP BY DATE(created_at), category
               ORDER BY day""",
            [tenant_id, -days],
        )
        daily = [
            {"day": r["day"], "category": r["category"], "count": r["count"]}
            for r in cur.fetchall()
        ]

        # Average sentiment per day
        cur.execute(
            f"""SELECT DATE(created_at) as day, AVG(sentiment) as avg_sentiment,
                      COUNT(*) as count
               FROM items
               WHERE tenant_id = ?
                 AND sentiment IS NOT NULL
                 AND created_at >= {date_filter}
               GROUP BY DATE(created_at)
               ORDER BY day""",
            [tenant_id, -days],
        )
        sentiment_trend = [
            {"day": r["day"], "avg_sentiment": round(float(r["avg_sentiment"]), 3), "count": r["count"]}
            for r in cur.fetchall()
        ]

        # Total stats
        cur.execute(
            f"""SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN urgency = 'breaking' THEN 1 ELSE 0 END) as breaking,
                 SUM(CASE WHEN urgency = 'high' THEN 1 ELSE 0 END) as high,
                 AVG(relevance_score) as avg_relevance,
                 AVG(CASE WHEN sentiment IS NOT NULL THEN sentiment END) as avg_sentiment
               FROM items
               WHERE tenant_id = ?
                 AND created_at >= {date_filter}""",
            [tenant_id, -days],
        )
        row = cur.fetchone()
        summary = {
            "total_items": row["total"],
            "breaking_count": row["breaking"] or 0,
            "high_count": row["high"] or 0,
            "avg_relevance": round(float(row["avg_relevance"]), 1) if row["avg_relevance"] else 0,
            "avg_sentiment": round(float(row["avg_sentiment"]), 3) if row["avg_sentiment"] else None,
        }

        # --- Top keywords extraction from ai_metadata ---
        top_keywords = _extract_top_keywords(cur, tenant_id, days)

        # --- Source breakdown ---
        cur.execute(
            f"""SELECT s.name as source_name, s.category as source_category,
                      COUNT(i.id) as item_count,
                      AVG(i.relevance_score) as avg_relevance
               FROM items i
               JOIN sources s ON i.source_id = s.id
               WHERE i.tenant_id = ?
                 AND i.created_at >= {date_filter}
               GROUP BY s.id, s.name, s.category
               ORDER BY item_count DESC""",
            [tenant_id, -days],
        )
        source_breakdown = [
            {
                "source_name": r["source_name"],
                "source_category": r["source_category"],
                "item_count": r["item_count"],
                "avg_relevance": round(float(r["avg_relevance"]), 1) if r["avg_relevance"] else 0,
            }
            for r in cur.fetchall()
        ]

        # --- Hourly activity heatmap ---
        dow_expr = _extract_dow()
        hour_expr = _extract_hour()
        cur.execute(
            f"""SELECT
                 {dow_expr} as day_of_week,
                 {hour_expr} as hour,
                 COUNT(*) as count
               FROM items
               WHERE tenant_id = ?
                 AND created_at >= {date_filter}
               GROUP BY day_of_week, hour
               ORDER BY day_of_week, hour""",
            [tenant_id, -days],
        )
        hourly_heatmap = [
            {
                "day_of_week": r["day_of_week"],
                "hour": r["hour"],
                "count": r["count"],
            }
            for r in cur.fetchall()
        ]

    return {
        "period_days": days,
        "summary": summary,
        "by_category": by_category,
        "by_urgency": by_urgency,
        "daily": daily,
        "sentiment_trend": sentiment_trend,
        "top_keywords": top_keywords,
        "source_breakdown": source_breakdown,
        "hourly_heatmap": hourly_heatmap,
    }


def _extract_top_keywords(cur, tenant_id: str, days: int, limit: int = 20) -> list[dict]:
    """Extract top keywords from ai_metadata JSON stored in items.

    Uses an in-memory cache (TTL 60s) to avoid loading all JSON blobs on every request.
    """
    cache_key = f"{tenant_id}:{days}:{limit}"
    now = time.monotonic()
    if (
        _keywords_cache["key"] == cache_key
        and (now - _keywords_cache["timestamp"]) < _KEYWORDS_CACHE_TTL
    ):
        return _keywords_cache["data"]

    date_filter = _date_offset_expr()
    cur.execute(
        f"""SELECT ai_metadata
           FROM items
           WHERE tenant_id = ?
             AND created_at >= {date_filter}
             AND ai_metadata IS NOT NULL
             AND ai_metadata != '{{}}'""",
        [tenant_id, -days],
    )

    keyword_counter: Counter = Counter()
    for row in cur.fetchall():
        raw = row["ai_metadata"]
        if not raw:
            continue
        try:
            metadata = json.loads(raw) if isinstance(raw, str) else raw
            keywords = metadata.get("keywords", [])
            for kw in keywords:
                if isinstance(kw, str) and kw.strip():
                    keyword_counter[kw.lower().strip()] += 1
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    result = [
        {"keyword": kw, "count": count}
        for kw, count in keyword_counter.most_common(limit)
    ]

    # Update cache
    _keywords_cache["data"] = result
    _keywords_cache["timestamp"] = now
    _keywords_cache["key"] = cache_key

    return result
