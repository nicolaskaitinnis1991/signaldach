import logging
from datetime import datetime, timezone

import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

DEFAULT_REDDIT_SOURCES = [
    {
        "id": "reddit-crypto",
        "name": "r/cryptocurrency",
        "type": "reddit",
        "category": "sentiment",
        "url": "https://www.reddit.com/r/cryptocurrency",
        "frequency": 5,
    },
    {
        "id": "reddit-bitcoin",
        "name": "r/bitcoin",
        "type": "reddit",
        "category": "sentiment",
        "url": "https://www.reddit.com/r/bitcoin",
        "frequency": 5,
    },
    {
        "id": "reddit-finanzen",
        "name": "r/Finanzen",
        "type": "reddit",
        "category": "sentiment",
        "url": "https://www.reddit.com/r/Finanzen",
        "frequency": 15,
    },
]


class RedditScraper(BaseScraper):
    source_type = "reddit"

    async def scrape(self, source: dict) -> list[RawItem]:
        url = source.get("url", "").rstrip("/")
        if not url:
            return []

        json_url = f"{url}/hot.json?limit=25"
        headers = {"User-Agent": "SignalDACH/0.1 (market intelligence bot)"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(json_url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"Reddit scrape failed for {url}: {e}")
            return []

        items = []
        for post in data.get("data", {}).get("children", []):
            d = post.get("data", {})
            if d.get("stickied"):
                continue

            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            content = d.get("selftext", "")[:2000]
            title = d.get("title", "")

            items.append(
                RawItem(
                    title=title,
                    content=content,
                    url=f"https://reddit.com{d.get('permalink', '')}",
                    author=d.get("author", ""),
                    published_at=created,
                    external_id=d.get("id", ""),
                    source_meta={
                        "score": d.get("score", 0),
                        "num_comments": d.get("num_comments", 0),
                        "subreddit": d.get("subreddit", ""),
                    },
                )
            )

        logger.info(f"Reddit scraped {len(items)} posts from {url}")
        return items
