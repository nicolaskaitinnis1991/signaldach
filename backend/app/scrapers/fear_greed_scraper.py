"""Fear & Greed Index scraper (alternative.me - free, no key needed).

The Fear & Greed Index is THE most-cited crypto market indicator.
Scale: 0 = Extreme Fear, 100 = Extreme Greed.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

API_URL = "https://api.alternative.me/fng/?limit=1&format=json"
HISTORY_URL = "https://api.alternative.me/fng/?limit=30&format=json"


def _label_color(value: int) -> str:
    """Return sentiment label for the index value."""
    if value <= 20:
        return "Extreme Fear"
    elif value <= 40:
        return "Fear"
    elif value <= 60:
        return "Neutral"
    elif value <= 80:
        return "Greed"
    else:
        return "Extreme Greed"


class FearGreedScraper(BaseScraper):
    source_type = "fear_greed"

    async def scrape(self, source: dict) -> list[RawItem]:
        items: list[RawItem] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=15) as client:
            # Current value
            try:
                resp = await client.get(API_URL)
                resp.raise_for_status()
                data = resp.json()
                current = data.get("data", [{}])[0]
            except httpx.HTTPError as e:
                logger.error(f"Fear & Greed API failed: {e}")
                return []

            value = int(current.get("value", 50))
            label = current.get("value_classification", _label_color(value))

            # Get 30-day history for trend
            try:
                resp_hist = await client.get(HISTORY_URL)
                resp_hist.raise_for_status()
                hist_data = resp_hist.json().get("data", [])
            except httpx.HTTPError:
                hist_data = []

            # Calculate trend
            trend = ""
            if len(hist_data) >= 7:
                week_ago = int(hist_data[6].get("value", value))
                diff = value - week_ago
                trend = f" | 7d change: {'+' if diff > 0 else ''}{diff}"

            month_avg = ""
            if len(hist_data) >= 30:
                avg = sum(int(d.get("value", 50)) for d in hist_data) / len(hist_data)
                month_avg = f" | 30d avg: {avg:.0f}"

            title = f"Fear & Greed Index: {value}/100 ({label}){trend}"
            content = (
                f"Current Value: {value}/100\n"
                f"Classification: {label}\n"
                f"Trend: {trend.strip(' |')}\n"
                f"30-day Average: {month_avg.strip(' |')}\n\n"
                f"The Fear & Greed Index measures market sentiment on a scale of 0 (Extreme Fear) "
                f"to 100 (Extreme Greed). Values below 25 historically indicate buying opportunities, "
                f"while values above 75 suggest overheated markets."
            )

            ext_id = hashlib.sha256(
                f"fng-{now.strftime('%Y-%m-%d-%H')}".encode()
            ).hexdigest()[:16]

            items.append(
                RawItem(
                    title=title,
                    content=content,
                    url="https://alternative.me/crypto/fear-and-greed-index/",
                    author="Alternative.me",
                    published_at=now,
                    external_id=ext_id,
                    source_meta={
                        "fear_greed_value": value,
                        "classification": label,
                        "history_30d": [
                            {"value": int(d.get("value", 0)), "date": d.get("timestamp", "")}
                            for d in hist_data[:30]
                        ] if hist_data else [],
                    },
                )
            )

        logger.info(f"Fear & Greed scraped: {value}/100 ({label})")
        return items
