"""Tests for RSS scraper and deduplication logic."""

import pytest
import pytest_asyncio
from app.scrapers.rss_scraper import RssScraper
from app.scrapers.base import RawItem, BaseScraper
from app.database import get_db


class TestRssScraper:
    """Test RssScraper.scrape() with a real public feed."""

    @pytest.mark.asyncio
    async def test_scrape_cointelegraph(self):
        """Scrape CoinTelegraph RSS feed and verify results."""
        scraper = RssScraper()
        source = {
            "id": "cointelegraph-rss",
            "name": "CoinTelegraph",
            "type": "rss",
            "category": "market",
            "url": "https://cointelegraph.com/rss",
        }
        items = await scraper.scrape(source)

        # Should return some items (feed may be temporarily down, so allow 0)
        assert isinstance(items, list)
        if len(items) > 0:
            item = items[0]
            assert isinstance(item, RawItem)
            assert item.title
            assert item.url
            assert item.external_id  # auto-generated from URL

    @pytest.mark.asyncio
    async def test_scrape_empty_url(self):
        """Should return empty list for source without URL."""
        scraper = RssScraper()
        source = {"name": "No URL Source", "type": "rss", "category": "market"}
        items = await scraper.scrape(source)
        assert items == []

    @pytest.mark.asyncio
    async def test_scrape_invalid_url(self):
        """Should return empty list for invalid URL."""
        scraper = RssScraper()
        source = {
            "name": "Bad Source",
            "type": "rss",
            "category": "market",
            "url": "https://this-domain-does-not-exist-xyz123.com/feed",
        }
        items = await scraper.scrape(source)
        assert items == []

    @pytest.mark.asyncio
    async def test_scraped_items_have_required_fields(self):
        """All scraped items must have title, url, and external_id."""
        scraper = RssScraper()
        source = {
            "id": "cointelegraph-rss",
            "name": "CoinTelegraph",
            "type": "rss",
            "category": "market",
            "url": "https://cointelegraph.com/rss",
        }
        items = await scraper.scrape(source)

        for item in items:
            assert item.title, "Item must have a title"
            assert item.url, "Item must have a URL"
            assert item.external_id, "Item must have an external_id"


class TestDeduplication:
    """Test database-level deduplication in BaseScraper."""

    @pytest.mark.asyncio
    async def test_dedup_removes_existing_items(self):
        """Items already in the DB should be filtered out."""
        scraper = RssScraper()

        # Insert a source and item into the DB
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO sources (id, tenant_id, name, type, category, url)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ["src1", "default", "Test Source", "rss", "market", "https://example.com"],
            )
            cur.execute(
                """INSERT INTO items (id, tenant_id, source_id, external_id, title, category)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ["item1", "default", "src1", "ext-123", "Existing Item", "market"],
            )

        # Create raw items, one matching the existing external_id
        raw_items = [
            RawItem(title="Existing Item", url="https://example.com/1", external_id="ext-123"),
            RawItem(title="New Item", url="https://example.com/2", external_id="ext-456"),
        ]

        with get_db() as conn:
            new_items = await scraper.deduplicate(raw_items, "default", conn)

        assert len(new_items) == 1
        assert new_items[0].external_id == "ext-456"

    @pytest.mark.asyncio
    async def test_dedup_keeps_all_when_none_exist(self):
        """All items should be kept when none exist in DB."""
        scraper = RssScraper()
        raw_items = [
            RawItem(title="Item A", url="https://example.com/a", external_id="ext-a"),
            RawItem(title="Item B", url="https://example.com/b", external_id="ext-b"),
        ]

        with get_db() as conn:
            new_items = await scraper.deduplicate(raw_items, "default", conn)

        assert len(new_items) == 2

    @pytest.mark.asyncio
    async def test_dedup_empty_list(self):
        """Empty input should return empty output."""
        scraper = RssScraper()
        with get_db() as conn:
            new_items = await scraper.deduplicate([], "default", conn)
        assert new_items == []
