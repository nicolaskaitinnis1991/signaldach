"""One-shot scraper: fetches all RSS sources, processes them, stores in SQLite."""
import asyncio
import json
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_db, init_db
from app.scrapers.rss_scraper import RssScraper
from app.ai.pipeline import process_batch


async def scrape_all():
    init_db()

    scraper = RssScraper()
    total_stored = 0

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM sources WHERE type = 'rss' AND enabled = 1")
        sources = [dict(row) for row in cur.fetchall()]

    print(f"\n{'='*60}")
    print(f"SignalDACH — Scraping {len(sources)} RSS sources")
    print(f"{'='*60}\n")

    for source in sources:
        print(f"\n--- Scraping: {source['name']} ---")
        print(f"    URL: {source['url']}")

        try:
            raw_items = await scraper.scrape(source)
            print(f"    Fetched: {len(raw_items)} raw items")

            if not raw_items:
                continue

            # Deduplicate
            with get_db() as conn:
                new_items = await scraper.deduplicate(raw_items, source["tenant_id"], conn)
            print(f"    New items: {len(new_items)}")

            if not new_items:
                continue

            # Process through AI pipeline (rule-based without API key)
            processed = await process_batch(new_items, source["category"])

            # Store
            with get_db() as conn:
                cur = conn.cursor()
                for item in processed:
                    item_id = uuid.uuid4().hex[:12]
                    pub_at = item.published_at.isoformat() if item.published_at else None
                    cur.execute(
                        """INSERT OR IGNORE INTO items
                           (id, tenant_id, source_id, external_id, title, summary, content,
                            url, author, published_at, category, relevance_score, urgency,
                            sentiment, ai_metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            item_id,
                            source["tenant_id"],
                            source["id"],
                            item.external_id,
                            item.title,
                            item.summary,
                            item.content,
                            item.url,
                            item.author,
                            pub_at,
                            item.category,
                            item.relevance_score,
                            item.urgency,
                            item.sentiment,
                            json.dumps(item.ai_metadata),
                        ),
                    )
                total_stored += len(processed)

            # Print top 3 items
            for i, item in enumerate(processed[:3]):
                print(f"    [{item.urgency.upper()}] (relevance:{item.relevance_score}) {item.title[:80]}")
                if item.ai_metadata.get("keywords"):
                    print(f"       Keywords: {', '.join(item.ai_metadata['keywords'])}")

        except Exception as e:
            print(f"    ERROR: {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_stored} items stored")
    print(f"{'='*60}\n")

    # Show category breakdown
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT category, COUNT(*) as c FROM items GROUP BY category ORDER BY c DESC")
        print("By category:")
        for row in cur.fetchall():
            print(f"  {row['category']}: {row['c']} items")

        cur.execute("SELECT urgency, COUNT(*) as c FROM items GROUP BY urgency ORDER BY c DESC")
        print("\nBy urgency:")
        for row in cur.fetchall():
            print(f"  {row['urgency']}: {row['c']} items")

        # Top relevance items
        cur.execute("SELECT title, relevance_score, urgency, category FROM items ORDER BY relevance_score DESC LIMIT 10")
        print("\n--- TOP 10 Most Relevant Items ---")
        for i, row in enumerate(cur.fetchall(), 1):
            print(f"  {i}. [{row['urgency']}] (score:{row['relevance_score']}) [{row['category']}] {row['title'][:80]}")


if __name__ == "__main__":
    asyncio.run(scrape_all())
