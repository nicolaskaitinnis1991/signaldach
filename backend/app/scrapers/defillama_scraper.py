"""DeFi Llama TVL data scraper (free API, no key needed)."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

PROTOCOLS_URL = "https://api.llama.fi/protocols"
CHAINS_URL = "https://api.llama.fi/chains"


def _fmt_tvl(value: float | int | None) -> str:
    """Format TVL into human-readable strings."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


class DefiLlamaScraper(BaseScraper):
    source_type = "defillama"

    async def scrape(self, source: dict) -> list[RawItem]:
        items: list[RawItem] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=30) as client:
            # --- Top DeFi protocols by TVL ---
            protocols = []
            try:
                resp = await client.get(PROTOCOLS_URL)
                resp.raise_for_status()
                all_protocols = resp.json()
                # Sort by TVL descending, take top 30
                all_protocols.sort(key=lambda p: p.get("tvl") or 0, reverse=True)
                protocols = all_protocols[:30]
            except httpx.HTTPError as e:
                logger.error(f"DeFi Llama protocols request failed: {e}")

            total_tvl = sum(p.get("tvl") or 0 for p in protocols)

            for proto in protocols:
                name = proto.get("name", "Unknown")
                tvl = proto.get("tvl")
                change_1d = proto.get("change_1d")
                change_7d = proto.get("change_7d")
                chain = proto.get("chain", "Multi-chain")
                category = proto.get("category", "")
                slug = proto.get("slug", name.lower().replace(" ", "-"))

                title = f"{name}: TVL {_fmt_tvl(tvl)} ({_fmt_pct(change_1d)} 1d) | {chain}"

                content = (
                    f"{name} - {category}\n"
                    f"TVL: {_fmt_tvl(tvl)}\n"
                    f"1d Change: {_fmt_pct(change_1d)} | 7d Change: {_fmt_pct(change_7d)}\n"
                    f"Chain: {chain}"
                )

                # Flag big TVL changes as high urgency via source_meta
                is_big_change = (
                    change_1d is not None and abs(change_1d) > 10
                )

                ext_id = hashlib.sha256(
                    f"defillama-proto-{slug}-{now.strftime('%Y-%m-%d-%H')}".encode()
                ).hexdigest()[:16]

                items.append(
                    RawItem(
                        title=title,
                        content=content,
                        url=f"https://defillama.com/protocol/{slug}",
                        author="DeFi Llama",
                        published_at=now,
                        external_id=ext_id,
                        source_meta={
                            "protocol": name,
                            "tvl": tvl,
                            "change_1d_pct": change_1d,
                            "change_7d_pct": change_7d,
                            "chain": chain,
                            "category": category,
                            "high_urgency": is_big_change,
                        },
                    )
                )

            # --- Chain TVL data ---
            chains = []
            try:
                resp = await client.get(CHAINS_URL)
                resp.raise_for_status()
                all_chains = resp.json()
                all_chains.sort(key=lambda c: c.get("tvl") or 0, reverse=True)
                chains = all_chains[:15]
            except httpx.HTTPError as e:
                logger.error(f"DeFi Llama chains request failed: {e}")

            if chains:
                chain_total = sum(c.get("tvl") or 0 for c in chains)
                chain_parts = [
                    f"{c.get('name', '?')}: {_fmt_tvl(c.get('tvl'))}"
                    for c in chains[:5]
                ]

                title = (
                    f"DeFi TVL Update: {_fmt_tvl(chain_total)} total | "
                    + " | ".join(chain_parts)
                )

                content_lines = ["Chain TVL Rankings:"]
                for i, c in enumerate(chains, 1):
                    content_lines.append(
                        f"{i}. {c.get('name', '?')}: {_fmt_tvl(c.get('tvl'))}"
                    )
                content = "\n".join(content_lines)

                ext_id = hashlib.sha256(
                    f"defillama-chains-{now.strftime('%Y-%m-%d-%H')}".encode()
                ).hexdigest()[:16]

                items.append(
                    RawItem(
                        title=title,
                        content=content,
                        url="https://defillama.com/chains",
                        author="DeFi Llama",
                        published_at=now,
                        external_id=ext_id,
                        source_meta={
                            "total_tvl": chain_total,
                            "top_chains": {
                                c.get("name", "?"): c.get("tvl")
                                for c in chains[:10]
                            },
                        },
                    )
                )

        logger.info(f"DeFi Llama scraped {len(items)} items")
        return items
