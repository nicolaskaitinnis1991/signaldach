from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import List, Dict

import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

DEFAULT_TELEGRAM_SOURCES = [
    {
        "id": "telegram-crypto-news",
        "name": "Crypto News (Telegram)",
        "type": "telegram",
        "category": "market",
        "url": "https://t.me/s/crypto",
        "frequency": 10,
    },
    {
        "id": "telegram-whale-alert",
        "name": "Whale Alert (Telegram)",
        "type": "telegram",
        "category": "market",
        "url": "https://t.me/s/whale_alert_io",
        "frequency": 5,
    },
]


class TelegramScraper(BaseScraper):
    """Scrapes public Telegram channels via their web preview (t.me/s/).

    This approach requires no API key or Telethon — it uses the public
    web preview that Telegram provides for all public channels.
    """

    source_type = "telegram"

    async def scrape(self, source: Dict) -> List[RawItem]:
        url = source.get("url", "")
        if not url:
            return []

        # Ensure we're using the web preview URL format
        if "/s/" not in url:
            # Convert https://t.me/channel to https://t.me/s/channel
            url = url.replace("t.me/", "t.me/s/")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPError as e:
            logger.error(f"Telegram scrape failed for {url}: {e}")
            return []

        return self._parse_html(html, source)

    def _parse_html(self, html: str, source: Dict) -> List[RawItem]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        items = []

        # Telegram web preview uses .tgme_widget_message elements
        messages = soup.select(".tgme_widget_message")

        for msg in messages[-25:]:  # Latest 25 messages
            # Extract message text
            text_el = msg.select_one(".tgme_widget_message_text")
            if not text_el:
                continue

            text = text_el.get_text(strip=True)
            if not text or len(text) < 10:
                continue

            # Extract message link
            link_el = msg.select_one(".tgme_widget_message_date")
            msg_url = ""
            if link_el and link_el.get("href"):
                msg_url = link_el["href"]

            # Extract message ID for dedup
            data_post = msg.get("data-post", "")
            external_id = data_post if data_post else ""

            # Extract datetime
            time_el = msg.select_one("time")
            published = None
            if time_el and time_el.get("datetime"):
                try:
                    published = datetime.fromisoformat(
                        time_el["datetime"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Extract views
            views_el = msg.select_one(".tgme_widget_message_views")
            views = 0
            if views_el:
                views_text = views_el.get_text(strip=True)
                views = self._parse_view_count(views_text)

            # Channel name
            author_el = msg.select_one(".tgme_widget_message_owner_name")
            author = author_el.get_text(strip=True) if author_el else source.get("name", "")

            items.append(
                RawItem(
                    title=text[:120],
                    content=text[:2000],
                    url=msg_url,
                    author=author,
                    published_at=published,
                    external_id=external_id,
                    source_meta={
                        "views": views,
                        "channel": source.get("name", ""),
                    },
                )
            )

        logger.info(f"Telegram scraped {len(items)} messages from {source.get('name')}")
        return items

    @staticmethod
    def _parse_view_count(text: str) -> int:
        """Parse Telegram view count strings like '1.2K', '45.3M'."""
        text = text.strip().upper()
        try:
            if text.endswith("K"):
                return int(float(text[:-1]) * 1000)
            elif text.endswith("M"):
                return int(float(text[:-1]) * 1000000)
            return int(text)
        except (ValueError, IndexError):
            return 0
