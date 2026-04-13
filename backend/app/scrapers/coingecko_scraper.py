"""CoinGecko market data scraper (free API, no key needed)."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
MARKETS_URL = f"{COINGECKO_BASE}/coins/markets"
GLOBAL_URL = f"{COINGECKO_BASE}/global"


def _fmt_market_cap(value: Optional) -> str:
    """Format large numbers into human-readable strings."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def _fmt_price(value: Optional) -> str:
    if value is None:
        return "N/A"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.6f}"


def _fmt_pct(value: Optional) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


class CoinGeckoScraper(BaseScraper):
    source_type = "coingecko"

    async def scrape(self, source: dict) -> list[RawItem]:
        items: list[RawItem] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=30) as client:
            # --- Top coins by market cap ---
            try:
                resp = await client.get(
                    MARKETS_URL,
                    params={
                        "vs_currency": "usd",
                        "order": "market_cap_desc",
                        "per_page": 50,
                        "sparkline": "false",
                    },
                )
                resp.raise_for_status()
                coins = resp.json()
            except httpx.HTTPError as e:
                logger.error(f"CoinGecko markets request failed: {e}")
                coins = []

            for coin in coins:
                symbol = (coin.get("symbol") or "").upper()
                price = _fmt_price(coin.get("current_price"))
                change_24h = _fmt_pct(coin.get("price_change_percentage_24h"))
                mcap = _fmt_market_cap(coin.get("market_cap"))

                title = f"{symbol}: {price} ({change_24h} 24h) | Market Cap: {mcap}"

                vol_24h = _fmt_market_cap(coin.get("total_volume"))
                high_24h = _fmt_price(coin.get("high_24h"))
                low_24h = _fmt_price(coin.get("low_24h"))
                content = (
                    f"{coin.get('name', symbol)} ({symbol})\n"
                    f"Price: {price} | 24h Change: {change_24h}\n"
                    f"Market Cap: {mcap} | 24h Volume: {vol_24h}\n"
                    f"24h Range: {low_24h} - {high_24h}"
                )

                ext_id = hashlib.sha256(
                    f"coingecko-{coin.get('id')}-{now.strftime('%Y-%m-%d-%H')}".encode()
                ).hexdigest()[:16]

                items.append(
                    RawItem(
                        title=title,
                        content=content,
                        url=f"https://www.coingecko.com/en/coins/{coin.get('id', '')}",
                        author="CoinGecko",
                        published_at=now,
                        external_id=ext_id,
                        source_meta={
                            "coin_id": coin.get("id"),
                            "symbol": symbol,
                            "price_usd": coin.get("current_price"),
                            "market_cap": coin.get("market_cap"),
                            "price_change_24h_pct": coin.get("price_change_percentage_24h"),
                            "total_volume": coin.get("total_volume"),
                        },
                    )
                )

            # --- Global market data ---
            try:
                resp = await client.get(GLOBAL_URL)
                resp.raise_for_status()
                global_data = resp.json().get("data", {})
            except httpx.HTTPError as e:
                logger.error(f"CoinGecko global request failed: {e}")
                global_data = {}

            if global_data:
                total_mcap = global_data.get("total_market_cap", {}).get("usd")
                btc_dom = global_data.get("market_cap_percentage", {}).get("btc")
                eth_dom = global_data.get("market_cap_percentage", {}).get("eth")
                active_coins = global_data.get("active_cryptocurrencies", 0)
                mcap_change = global_data.get("market_cap_change_percentage_24h_usd")

                title = (
                    f"Global Crypto Market: {_fmt_market_cap(total_mcap)} "
                    f"({_fmt_pct(mcap_change)} 24h) | "
                    f"BTC: {btc_dom:.1f}% | ETH: {eth_dom:.1f}%"
                )
                content = (
                    f"Total Market Cap: {_fmt_market_cap(total_mcap)}\n"
                    f"24h Change: {_fmt_pct(mcap_change)}\n"
                    f"BTC Dominance: {btc_dom:.1f}%\n"
                    f"ETH Dominance: {eth_dom:.1f}%\n"
                    f"Active Cryptocurrencies: {active_coins:,}"
                )

                ext_id = hashlib.sha256(
                    f"coingecko-global-{now.strftime('%Y-%m-%d-%H')}".encode()
                ).hexdigest()[:16]

                items.append(
                    RawItem(
                        title=title,
                        content=content,
                        url="https://www.coingecko.com/en/global-charts",
                        author="CoinGecko",
                        published_at=now,
                        external_id=ext_id,
                        source_meta={
                            "total_market_cap_usd": total_mcap,
                            "btc_dominance": btc_dom,
                            "eth_dominance": eth_dom,
                            "market_cap_change_24h_pct": mcap_change,
                        },
                    )
                )

        logger.info(f"CoinGecko scraped {len(items)} items")
        return items
