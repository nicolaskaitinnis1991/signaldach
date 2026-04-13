"""Fear & Greed Index collector.

Stores the index as a market metric for time-series analysis.
Free API from alternative.me, no auth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from app.collectors.base import store_market_metrics, publish_to_stream
from app.error_handling import CircuitBreaker

logger = logging.getLogger(__name__)

API_URL = "https://api.alternative.me/fng/?limit=30&format=json"

_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
_CB_SOURCE = "fear_greed"


async def collect_fear_greed() -> int:
    """Fetch Fear & Greed Index and store as market metrics."""
    if not _cb.allow_request(_CB_SOURCE):
        logger.warning("Fear & Greed circuit breaker OPEN, skipping")
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(API_URL)
            resp.raise_for_status()
            data = resp.json()

        entries = data.get("data", [])
        if not entries:
            return 0

        current = entries[0]
        value = int(current.get("value", 50))
        classification = current.get("value_classification", "")

        # Store current value
        metrics.append({
            "ts": now,
            "metric_type": "fear_greed_index",
            "value": float(value),
            "metadata_json": json.dumps({
                "classification": classification,
                "timestamp": current.get("timestamp"),
            }),
        })

        # Calculate 7d and 30d averages if we have history
        if len(entries) >= 7:
            avg_7d = sum(int(e.get("value", 50)) for e in entries[:7]) / 7
            metrics.append({
                "ts": now,
                "metric_type": "fear_greed_7d_avg",
                "value": avg_7d,
            })

        if len(entries) >= 30:
            avg_30d = sum(int(e.get("value", 50)) for e in entries[:30]) / 30
            metrics.append({
                "ts": now,
                "metric_type": "fear_greed_30d_avg",
                "value": avg_30d,
            })

        stored = await store_market_metrics(metrics)
        _cb.record_success(_CB_SOURCE)

        await publish_to_stream("signals:prices", {
            "source": "fear_greed",
            "value": str(value),
            "classification": classification,
            "ts": now.isoformat(),
        })

        logger.info("Fear & Greed: %d/100 (%s), stored %d metrics", value, classification, stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("Fear & Greed collection failed: %s", e)
        return 0


async def collect_all() -> int:
    return await collect_fear_greed()
