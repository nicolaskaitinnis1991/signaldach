"""Base collector with DB persistence and Redis Stream publishing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)


async def store_price_ticks(ticks: list[dict[str, Any]]) -> int:
    """Batch-insert price ticks into the price_ticks table.

    Each tick dict: {symbol, exchange, price, volume_24h?, market_cap?, change_pct_24h?, ts?}
    Returns number of rows inserted.
    """
    if not ticks:
        return 0

    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cur = conn.cursor()
        inserted = 0
        for t in ticks:
            ts = t.get("ts", now)
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            ts_str = ts.isoformat() if not USE_POSTGRES else ts

            params = (
                ts_str,
                t["symbol"],
                t["exchange"],
                t["price"],
                t.get("volume_24h"),
                t.get("market_cap"),
                t.get("change_pct_24h"),
            )

            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO price_ticks (ts, symbol, exchange, price, volume_24h, market_cap, change_pct_24h) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    params,
                )
            else:
                cur.execute(
                    "INSERT INTO price_ticks (ts, symbol, exchange, price, volume_24h, market_cap, change_pct_24h) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    params,
                )
            inserted += 1
        return inserted


async def store_market_metrics(metrics: list[dict[str, Any]]) -> int:
    """Batch-insert market metrics.

    Each dict: {metric_type, value, symbol?, exchange?, metadata_json?, ts?}
    """
    if not metrics:
        return 0

    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cur = conn.cursor()
        inserted = 0
        for m in metrics:
            ts = m.get("ts", now)
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            ts_str = ts.isoformat() if not USE_POSTGRES else ts

            params = (
                ts_str,
                m["metric_type"],
                m.get("symbol"),
                m.get("exchange"),
                m["value"],
                m.get("metadata_json", "{}"),
            )

            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO market_metrics (ts, metric_type, symbol, exchange, value, metadata_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    params,
                )
            else:
                cur.execute(
                    "INSERT INTO market_metrics (ts, metric_type, symbol, exchange, value, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    params,
                )
            inserted += 1
        return inserted


async def store_onchain_metrics(metrics: list[dict[str, Any]]) -> int:
    """Batch-insert on-chain metrics.

    Each dict: {metric_type, value, chain?, protocol?, unit?, metadata_json?, ts?}
    """
    if not metrics:
        return 0

    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cur = conn.cursor()
        inserted = 0
        for m in metrics:
            ts = m.get("ts", now)
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            ts_str = ts.isoformat() if not USE_POSTGRES else ts

            params = (
                ts_str,
                m["metric_type"],
                m.get("chain"),
                m.get("protocol"),
                m["value"],
                m.get("unit", "USD"),
                m.get("metadata_json", "{}"),
            )

            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO onchain_metrics (ts, metric_type, chain, protocol, value, unit, metadata_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    params,
                )
            else:
                cur.execute(
                    "INSERT INTO onchain_metrics (ts, metric_type, chain, protocol, value, unit, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    params,
                )
            inserted += 1
        return inserted


async def publish_to_stream(stream: str, data: dict[str, str]) -> None:
    """Publish data to a Redis Stream (best-effort, non-blocking)."""
    try:
        from app.redis_client import is_redis_available, stream_publish
        if is_redis_available():
            await stream_publish(stream, data)
    except Exception as e:
        logger.debug("Redis stream publish failed (non-critical): %s", e)
