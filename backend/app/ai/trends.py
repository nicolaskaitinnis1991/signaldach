"""Trend detection for keyword frequency spikes.

Tracks keyword counts per day and detects sudden spikes
(>2x the 7-day rolling average).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger(__name__)

# Spike threshold: a keyword count must exceed this multiple of the 7-day average
SPIKE_MULTIPLIER = 2.0


def update_keyword_trends(items: list[dict], conn=None, today: str | None = None):
    """Update keyword_trends table with counts from newly processed items.

    Args:
        items: List of processed item dicts, each with ai_metadata containing keywords.
        conn: Optional existing DB connection. If None, opens a new one.
        today: Date string (YYYY-MM-DD). Defaults to current UTC date.
    """
    if not items:
        return

    if today is None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Collect keyword frequencies from the new batch
    keyword_counts: dict[str, int] = {}
    for item in items:
        metadata = item.get("ai_metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        keywords = metadata.get("keywords", [])
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if kw_lower:
                keyword_counts[kw_lower] = keyword_counts.get(kw_lower, 0) + 1

    if not keyword_counts:
        return

    def _do_update(c):
        cur = c.cursor()
        for keyword, count in keyword_counts.items():
            cur.execute(
                """SELECT id, count FROM keyword_trends
                   WHERE keyword = ? AND date = ?""",
                [keyword, today],
            )
            existing = cur.fetchone()

            if existing:
                new_count = existing["count"] + count
                cur.execute(
                    "UPDATE keyword_trends SET count = ? WHERE id = ?",
                    [new_count, existing["id"]],
                )
            else:
                trend_id = uuid.uuid4().hex[:12]
                cur.execute(
                    """INSERT INTO keyword_trends (id, keyword, date, count, avg_count_7d, is_spike)
                       VALUES (?, ?, ?, ?, 0.0, 0)""",
                    [trend_id, keyword, today, count],
                )

            cur.execute(
                """SELECT AVG(count) as avg_count
                   FROM keyword_trends
                   WHERE keyword = ?
                     AND date < ?
                     AND date >= date(?, '-7 days')""",
                [keyword, today, today],
            )
            avg_row = cur.fetchone()
            avg_7d = float(avg_row["avg_count"]) if avg_row and avg_row["avg_count"] else 0.0

            cur.execute(
                "SELECT count FROM keyword_trends WHERE keyword = ? AND date = ?",
                [keyword, today],
            )
            today_row = cur.fetchone()
            today_count = today_row["count"] if today_row else count

            is_spike = 0
            if avg_7d > 0 and today_count > avg_7d * SPIKE_MULTIPLIER:
                is_spike = 1

            cur.execute(
                """UPDATE keyword_trends
                   SET avg_count_7d = ?, is_spike = ?
                   WHERE keyword = ? AND date = ?""",
                [round(avg_7d, 2), is_spike, keyword, today],
            )

        logger.info(f"Updated trends for {len(keyword_counts)} keywords on {today}")

    if conn is not None:
        _do_update(conn)
    else:
        with get_db() as c:
            _do_update(c)


def store_entity_mentions(item_id: str, entities: list[dict], conn=None):
    """Store extracted entities in entity_mentions table.

    Args:
        item_id: The item ID these entities were extracted from.
        entities: List of Entity-like dicts with name, entity_type fields.
        conn: Optional existing DB connection. If None, opens a new one.
    """
    if not entities:
        return

    def _do_store(c):
        cur = c.cursor()
        now = datetime.now(timezone.utc).isoformat()

        for entity in entities:
            mention_id = uuid.uuid4().hex[:12]
            cur.execute(
                """INSERT INTO entity_mentions (id, entity_name, entity_type, item_id, mentioned_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [mention_id, entity.get("name", ""), entity.get("entity_type", ""),
                 item_id, now],
            )

        logger.debug(f"Stored {len(entities)} entity mentions for item {item_id}")

    if conn is not None:
        _do_store(conn)
    else:
        with get_db() as c:
            _do_store(c)


def get_trending_keywords(days: int = 7, limit: int = 20) -> list[dict]:
    """Get keywords with highest frequency and any spikes in the given period."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT keyword,
                      SUM(count) as total_count,
                      MAX(is_spike) as has_spike,
                      MAX(avg_count_7d) as latest_avg
               FROM keyword_trends
               WHERE date >= date('now', ? || ' days')
               GROUP BY keyword
               ORDER BY total_count DESC
               LIMIT ?""",
            [-days, limit],
        )
        return [dict(row) for row in cur.fetchall()]


def get_active_spikes() -> list[dict]:
    """Get keywords that are currently spiking (today or yesterday)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT keyword, date, count, avg_count_7d
               FROM keyword_trends
               WHERE is_spike = 1
                 AND date >= date('now', '-1 day')
               ORDER BY count DESC"""
        )
        return [dict(row) for row in cur.fetchall()]


def get_keyword_history(keyword: str, days: int = 30) -> list[dict]:
    """Get daily counts for a specific keyword."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT date, count, avg_count_7d, is_spike
               FROM keyword_trends
               WHERE keyword = ?
                 AND date >= date('now', ? || ' days')
               ORDER BY date""",
            [keyword.lower(), -days],
        )
        return [dict(row) for row in cur.fetchall()]
