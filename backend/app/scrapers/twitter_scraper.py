from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import List, Dict

import httpx

from app.config import settings
from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

DEFAULT_TWITTER_SOURCES = [
    {
        "id": "twitter-bafin",
        "name": "BaFin (Twitter)",
        "type": "twitter",
        "category": "regulation",
        "url": "",
        "frequency": 15,
        "config": {"usernames": ["BaFin_Bund"]},
    },
    {
        "id": "twitter-crypto-dach",
        "name": "Crypto Influencers DACH",
        "type": "twitter",
        "category": "sentiment",
        "url": "",
        "frequency": 5,
        "config": {
            "search_query": "(crypto OR bitcoin OR ethereum) (regulation OR BaFin OR FINMA OR MiCA) lang:en -is:retweet",
        },
    },
    {
        "id": "twitter-crypto-whales",
        "name": "Crypto Whale Alerts",
        "type": "twitter",
        "category": "market",
        "url": "",
        "frequency": 5,
        "config": {"usernames": ["whale_alert", "lookonchain"]},
    },
]

TWITTER_API_BASE = "https://api.twitter.com/2"


class TwitterScraper(BaseScraper):
    source_type = "twitter"

    async def scrape(self, source: Dict) -> List[RawItem]:
        token = settings.twitter_bearer_token
        if not token:
            logger.warning("No Twitter bearer token configured, skipping Twitter scrape")
            return []

        config = source.get("config", {})
        if isinstance(config, str):
            import json
            config = json.loads(config)

        headers = {"Authorization": f"Bearer {token}"}

        # Decide: search query or user timeline
        if config.get("search_query"):
            return await self._search_tweets(config["search_query"], headers, source)
        elif config.get("usernames"):
            items = []
            for username in config["usernames"]:
                items.extend(await self._user_tweets(username, headers, source))
            return items

        return []

    async def _search_tweets(
        self, query: str, headers: Dict, source: Dict
    ) -> List[RawItem]:
        url = f"{TWITTER_API_BASE}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": 20,
            "tweet.fields": "created_at,author_id,public_metrics,text",
            "expansions": "author_id",
            "user.fields": "username,name",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 429:
                    logger.warning("Twitter rate limit hit, backing off")
                    return []
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Twitter search failed: {e}")
            return []

        return self._parse_tweets(data, source)

    async def _user_tweets(
        self, username: str, headers: Dict, source: Dict
    ) -> List[RawItem]:
        # First get user ID
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                user_resp = await client.get(
                    f"{TWITTER_API_BASE}/users/by/username/{username}",
                    headers=headers,
                )
                if user_resp.status_code != 200:
                    logger.warning(f"Could not find Twitter user: {username}")
                    return []
                user_id = user_resp.json()["data"]["id"]

                # Get recent tweets
                resp = await client.get(
                    f"{TWITTER_API_BASE}/users/{user_id}/tweets",
                    headers=headers,
                    params={
                        "max_results": 10,
                        "tweet.fields": "created_at,public_metrics,text",
                        "exclude": "retweets,replies",
                    },
                )
                if resp.status_code == 429:
                    logger.warning("Twitter rate limit hit")
                    return []
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Twitter user timeline failed for {username}: {e}")
            return []

        items = []
        for tweet in data.get("data", []):
            metrics = tweet.get("public_metrics", {})
            created = None
            if tweet.get("created_at"):
                created = datetime.fromisoformat(
                    tweet["created_at"].replace("Z", "+00:00")
                )

            items.append(
                RawItem(
                    title=tweet.get("text", "")[:120],
                    content=tweet.get("text", ""),
                    url=f"https://x.com/{username}/status/{tweet['id']}",
                    author=f"@{username}",
                    published_at=created,
                    external_id=tweet["id"],
                    source_meta={
                        "likes": metrics.get("like_count", 0),
                        "retweets": metrics.get("retweet_count", 0),
                        "replies": metrics.get("reply_count", 0),
                        "impressions": metrics.get("impression_count", 0),
                    },
                )
            )

        logger.info(f"Twitter scraped {len(items)} tweets from @{username}")
        return items

    def _parse_tweets(self, data: Dict, source: Dict) -> List[RawItem]:
        # Build author lookup from includes
        authors: Dict[str, str] = {}
        for user in data.get("includes", {}).get("users", []):
            authors[user["id"]] = user.get("username", "")

        items = []
        for tweet in data.get("data", []):
            metrics = tweet.get("public_metrics", {})
            author_id = tweet.get("author_id", "")
            username = authors.get(author_id, "unknown")
            created = None
            if tweet.get("created_at"):
                created = datetime.fromisoformat(
                    tweet["created_at"].replace("Z", "+00:00")
                )

            items.append(
                RawItem(
                    title=tweet.get("text", "")[:120],
                    content=tweet.get("text", ""),
                    url=f"https://x.com/{username}/status/{tweet['id']}",
                    author=f"@{username}",
                    published_at=created,
                    external_id=tweet["id"],
                    source_meta={
                        "likes": metrics.get("like_count", 0),
                        "retweets": metrics.get("retweet_count", 0),
                        "replies": metrics.get("reply_count", 0),
                    },
                )
            )

        logger.info(f"Twitter search returned {len(items)} tweets")
        return items
