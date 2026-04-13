"""News-to-Price Correlation Engine.

Implements Event Study Methodology to measure how news affects prices:
1. Detects significant news events (high urgency/relevance items)
2. Captures price windows before/after the event
3. Computes abnormal returns vs. expected returns
4. Stores correlation scores for backtesting

This is the core of our predictive capability — answering
"Does our signal actually predict price movement?"
"""

from __future__ import annotations

import json
import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)

# Event windows (in minutes)
PRE_EVENT_WINDOW = 60  # 1 hour before
POST_EVENT_WINDOWS = [15, 60, 240, 1440]  # 15min, 1h, 4h, 24h after


def get_price_at_time(
    symbol: str,
    target_time: datetime,
    tolerance_minutes: int = 10,
) -> Optional[float]:
    """Get the closest price tick to a target time."""
    with get_db() as conn:
        cur = conn.cursor()
        ts_str = target_time.isoformat()
        tol_str = str(tolerance_minutes)

        if USE_POSTGRES:
            cur.execute(
                """SELECT price, ts FROM price_ticks
                   WHERE symbol = %s
                   AND ts BETWEEN %s - INTERVAL '%s minutes' AND %s + INTERVAL '%s minutes'
                   ORDER BY ABS(EXTRACT(EPOCH FROM (ts - %s::timestamp)))
                   LIMIT 1""",
                (symbol, ts_str, tol_str, ts_str, tol_str, ts_str),
            )
        else:
            before = (target_time - timedelta(minutes=tolerance_minutes)).isoformat()
            after = (target_time + timedelta(minutes=tolerance_minutes)).isoformat()
            cur.execute(
                """SELECT price, ts FROM price_ticks
                   WHERE symbol LIKE ?
                   AND ts BETWEEN ? AND ?
                   ORDER BY ABS(julianday(ts) - julianday(?))
                   LIMIT 1""",
                (f"%{symbol}%", before, after, ts_str),
            )

        row = cur.fetchone()
        return dict(row)["price"] if row else None


def compute_event_impact(
    event_time: datetime,
    symbol: str = "BTC/USDT",
) -> Optional[dict]:
    """Compute price impact around a news event.

    Returns abnormal returns for multiple post-event windows.
    """
    # Pre-event price
    pre_price = get_price_at_time(symbol, event_time - timedelta(minutes=PRE_EVENT_WINDOW))
    event_price = get_price_at_time(symbol, event_time)

    if pre_price is None or event_price is None:
        return None

    results = {
        "symbol": symbol,
        "event_time": event_time.isoformat(),
        "pre_price": pre_price,
        "event_price": event_price,
        "windows": {},
    }

    for window_min in POST_EVENT_WINDOWS:
        post_time = event_time + timedelta(minutes=window_min)
        post_price = get_price_at_time(symbol, post_time)

        if post_price is not None:
            # Raw return
            raw_return = (post_price - event_price) / event_price
            # Pre-event drift (expected return)
            expected_return = (event_price - pre_price) / pre_price
            # Abnormal return = actual - expected
            abnormal_return = raw_return - expected_return

            results["windows"][f"{window_min}m"] = {
                "post_price": post_price,
                "raw_return_pct": round(raw_return * 100, 4),
                "expected_return_pct": round(expected_return * 100, 4),
                "abnormal_return_pct": round(abnormal_return * 100, 4),
            }

    return results


def analyze_news_correlation(
    days: int = 7,
    min_relevance: int = 7,
    symbol: str = "BTC/USDT",
) -> dict:
    """Analyze correlation between high-relevance news and price movements.

    Looks at all items with relevance >= min_relevance in the last N days,
    computes event impacts, and returns aggregate statistics.
    """
    with get_db() as conn:
        cur = conn.cursor()

        if USE_POSTGRES:
            cur.execute(
                """SELECT id, title, published_at, category, relevance_score, urgency, sentiment
                   FROM items
                   WHERE relevance_score >= %s
                   AND published_at > NOW() - INTERVAL '%s days'
                   ORDER BY published_at DESC""",
                (min_relevance, days),
            )
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            cur.execute(
                """SELECT id, title, published_at, category, relevance_score, urgency, sentiment
                   FROM items
                   WHERE relevance_score >= ?
                   AND published_at > ?
                   ORDER BY published_at DESC""",
                (min_relevance, cutoff),
            )

        items = [dict(r) for r in cur.fetchall()]

    if not items:
        return {"events_analyzed": 0, "message": "No high-relevance items found"}

    impacts = []
    for item in items:
        pub_at = item.get("published_at")
        if not pub_at:
            continue
        if isinstance(pub_at, str):
            try:
                event_time = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
            except ValueError:
                continue
        else:
            event_time = pub_at

        impact = compute_event_impact(event_time, symbol)
        if impact and impact.get("windows"):
            impact["item_id"] = item["id"]
            impact["title"] = item["title"]
            impact["category"] = item["category"]
            impact["sentiment"] = item.get("sentiment")
            impact["relevance"] = item["relevance_score"]
            impacts.append(impact)

    if not impacts:
        return {
            "events_analyzed": len(items),
            "events_with_price_data": 0,
            "message": "No price data available for event windows",
        }

    # Aggregate statistics
    abnormal_returns_1h = [
        i["windows"]["60m"]["abnormal_return_pct"]
        for i in impacts if "60m" in i["windows"]
    ]
    abnormal_returns_4h = [
        i["windows"]["240m"]["abnormal_return_pct"]
        for i in impacts if "240m" in i["windows"]
    ]

    def _stats(values):
        if not values:
            return None
        return {
            "mean": round(statistics.mean(values), 4),
            "median": round(statistics.median(values), 4),
            "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
            "positive_pct": round(sum(1 for v in values if v > 0) / len(values) * 100, 1),
            "count": len(values),
        }

    # Correlation between sentiment and price movement
    sentiment_return_pairs = [
        (i.get("sentiment", 0) or 0, i["windows"]["60m"]["abnormal_return_pct"])
        for i in impacts if "60m" in i["windows"] and i.get("sentiment") is not None
    ]

    correlation = None
    if len(sentiment_return_pairs) >= 5:
        sentiments = [p[0] for p in sentiment_return_pairs]
        returns = [p[1] for p in sentiment_return_pairs]
        # Pearson correlation
        n = len(sentiments)
        mean_s = statistics.mean(sentiments)
        mean_r = statistics.mean(returns)
        try:
            cov = sum((s - mean_s) * (r - mean_r) for s, r in zip(sentiments, returns)) / n
            std_s = statistics.stdev(sentiments)
            std_r = statistics.stdev(returns)
            if std_s > 0 and std_r > 0:
                correlation = round(cov / (std_s * std_r), 4)
        except Exception:
            pass

    return {
        "events_analyzed": len(items),
        "events_with_price_data": len(impacts),
        "symbol": symbol,
        "period_days": days,
        "abnormal_returns_1h": _stats(abnormal_returns_1h),
        "abnormal_returns_4h": _stats(abnormal_returns_4h),
        "sentiment_price_correlation": correlation,
        "top_impact_events": sorted(
            impacts,
            key=lambda i: abs(i["windows"].get("60m", {}).get("abnormal_return_pct", 0)),
            reverse=True,
        )[:5],
    }
