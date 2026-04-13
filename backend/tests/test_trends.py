"""Tests for keyword trend tracking and spike detection."""

import pytest
from app.ai.trends import update_keyword_trends, store_entity_mentions
from app.database import get_db


class TestUpdateKeywordTrends:
    """Test update_keyword_trends() creates entries."""

    def test_creates_trend_entries(self):
        items = [
            {
                "ai_metadata": {
                    "keywords": ["bitcoin", "regulation", "bafin"],
                }
            },
            {
                "ai_metadata": {
                    "keywords": ["bitcoin", "ethereum"],
                }
            },
        ]

        with get_db() as conn:
            update_keyword_trends(items, conn=conn, today="2026-03-30")

            cur = conn.cursor()
            cur.execute("SELECT * FROM keyword_trends WHERE date = '2026-03-30'")
            rows = [dict(r) for r in cur.fetchall()]

        keywords = {r["keyword"] for r in rows}
        assert "bitcoin" in keywords
        assert "regulation" in keywords
        assert "bafin" in keywords
        assert "ethereum" in keywords

        # Bitcoin appears in both items, so count should be 2
        btc_row = [r for r in rows if r["keyword"] == "bitcoin"][0]
        assert btc_row["count"] == 2

    def test_empty_items(self):
        """Should not crash with empty items."""
        with get_db() as conn:
            update_keyword_trends([], conn=conn)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM keyword_trends")
            assert cur.fetchone()["cnt"] == 0

    def test_items_without_keywords(self):
        """Items with no keywords should be skipped."""
        items = [{"ai_metadata": {"keywords": []}}, {"ai_metadata": {}}]
        with get_db() as conn:
            update_keyword_trends(items, conn=conn)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM keyword_trends")
            assert cur.fetchone()["cnt"] == 0

    def test_string_metadata_parsed(self):
        """ai_metadata stored as JSON string should be parsed."""
        import json
        items = [
            {"ai_metadata": json.dumps({"keywords": ["defi", "yield"]})}
        ]
        with get_db() as conn:
            update_keyword_trends(items, conn=conn, today="2026-03-30")
            cur = conn.cursor()
            cur.execute("SELECT * FROM keyword_trends")
            rows = [dict(r) for r in cur.fetchall()]

        keywords = {r["keyword"] for r in rows}
        assert "defi" in keywords
        assert "yield" in keywords

    def test_increments_existing_count(self):
        """Calling twice on the same day should increment counts."""
        items1 = [{"ai_metadata": {"keywords": ["bitcoin"]}}]
        items2 = [{"ai_metadata": {"keywords": ["bitcoin"]}}]

        with get_db() as conn:
            update_keyword_trends(items1, conn=conn, today="2026-03-30")
            update_keyword_trends(items2, conn=conn, today="2026-03-30")

            cur = conn.cursor()
            cur.execute("SELECT count FROM keyword_trends WHERE keyword = 'bitcoin' AND date = '2026-03-30'")
            row = cur.fetchone()
            assert row["count"] == 2


class TestSpikeDetection:
    """Test that spike detection works (>2x average)."""

    def test_spike_detected(self):
        """A spike should be flagged when count > 2x the 7-day average."""
        with get_db() as conn:
            # Insert 7 days of low counts (1 each)
            cur = conn.cursor()
            for i in range(1, 8):
                date = f"2026-03-{20 + i:02d}"
                cur.execute(
                    """INSERT INTO keyword_trends (id, keyword, date, count, avg_count_7d, is_spike)
                       VALUES (?, ?, ?, ?, 0.0, 0)""",
                    [f"trend-{i}", "bitcoin", date, 1],
                )

            # Now add a big spike on day 28 (count=10, avg should be ~1.0)
            items = [{"ai_metadata": {"keywords": ["bitcoin"] * 10}}]
            update_keyword_trends(items, conn=conn, today="2026-03-28")

            cur.execute(
                "SELECT is_spike, count, avg_count_7d FROM keyword_trends WHERE keyword = 'bitcoin' AND date = '2026-03-28'"
            )
            row = dict(cur.fetchone())
            assert row["is_spike"] == 1
            assert row["count"] == 10
            assert row["avg_count_7d"] > 0

    def test_no_spike_for_normal_count(self):
        """Normal counts should not be flagged as spikes."""
        with get_db() as conn:
            cur = conn.cursor()
            for i in range(1, 8):
                date = f"2026-03-{20 + i:02d}"
                cur.execute(
                    """INSERT INTO keyword_trends (id, keyword, date, count, avg_count_7d, is_spike)
                       VALUES (?, ?, ?, ?, 0.0, 0)""",
                    [f"trend-{i}", "ethereum", date, 5],
                )

            # Normal count (5) should not spike against avg of ~5
            items = [{"ai_metadata": {"keywords": ["ethereum"] * 5}}]
            update_keyword_trends(items, conn=conn, today="2026-03-28")

            cur.execute(
                "SELECT is_spike FROM keyword_trends WHERE keyword = 'ethereum' AND date = '2026-03-28'"
            )
            row = cur.fetchone()
            assert row["is_spike"] == 0


class TestStoreEntityMentions:
    """Test store_entity_mentions() stores entries."""

    def test_stores_entities(self):
        """Entities should be stored in entity_mentions table."""
        # Need an item in the DB first (FK constraint)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO sources (id, tenant_id, name, type, category)
                   VALUES (?, ?, ?, ?, ?)""",
                ["src1", "default", "Test Source", "rss", "market"],
            )
            cur.execute(
                """INSERT INTO items (id, tenant_id, source_id, external_id, title, category)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ["item1", "default", "src1", "ext-1", "Test Item", "market"],
            )

        entities = [
            {"name": "BTC", "entity_type": "token"},
            {"name": "BaFin", "entity_type": "regulator"},
            {"name": "21Shares", "entity_type": "company"},
        ]

        with get_db() as conn:
            store_entity_mentions("item1", entities, conn=conn)

            cur = conn.cursor()
            cur.execute("SELECT * FROM entity_mentions WHERE item_id = 'item1'")
            rows = [dict(r) for r in cur.fetchall()]

        assert len(rows) == 3
        names = {r["entity_name"] for r in rows}
        assert "BTC" in names
        assert "BaFin" in names
        assert "21Shares" in names

    def test_empty_entities(self):
        """Empty entity list should not crash."""
        with get_db() as conn:
            store_entity_mentions("nonexistent", [], conn=conn)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM entity_mentions")
            assert cur.fetchone()["cnt"] == 0
