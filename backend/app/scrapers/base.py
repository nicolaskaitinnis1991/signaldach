from __future__ import annotations
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RawItem:
    title: str
    content: str = ""
    url: str = ""
    author: str = ""
    published_at: Optional[datetime] = None
    external_id: str = ""
    source_meta: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.external_id and self.url:
            self.external_id = hashlib.sha256(self.url.encode()).hexdigest()[:16]


@dataclass
class ProcessedItem:
    title: str
    summary: str
    content: str
    url: str
    author: str
    published_at: Optional[datetime]
    external_id: str
    category: str
    relevance_score: int
    urgency: str
    sentiment: Optional[float]
    ai_metadata: Dict


class BaseScraper(ABC):
    source_type: str = "unknown"

    @abstractmethod
    async def scrape(self, source: dict) -> list[RawItem]:
        """Fetch raw items from a source."""
        ...

    async def deduplicate(self, items: list[RawItem], tenant_id: str, conn) -> list[RawItem]:
        """Remove items already in the database."""
        if not items:
            return []

        cur = conn.cursor()
        external_ids = [i.external_id for i in items if i.external_id]
        if not external_ids:
            return items

        placeholders = ",".join(["?"] * len(external_ids))
        cur.execute(
            f"SELECT external_id FROM items WHERE tenant_id = ? AND external_id IN ({placeholders})",
            [tenant_id] + external_ids,
        )
        existing = {row[0] for row in cur.fetchall()}
        new_items = [i for i in items if i.external_id not in existing]
        logger.info(f"Dedup: {len(items)} total, {len(existing)} existing, {len(new_items)} new")
        return new_items
