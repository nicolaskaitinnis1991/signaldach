"""Whale Alert scraper - tracks large crypto transactions.

Uses the free Whale Alert API (no key needed for recent transactions feed).
Whale movements are one of the strongest leading indicators in crypto.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.scrapers.base import BaseScraper, RawItem

logger = logging.getLogger(__name__)

# Cached BTC price to avoid hitting CoinGecko on every scrape
_btc_price_cache: dict = {"price": 60000.0, "timestamp": 0.0}
_BTC_PRICE_CACHE_TTL = 300  # 5 minutes


async def _fetch_btc_price(client: "httpx.AsyncClient") -> float:
    """Fetch current BTC/USD price from CoinGecko with caching and fallback."""
    import time as _time
    now = _time.monotonic()
    if now - _btc_price_cache["timestamp"] < _BTC_PRICE_CACHE_TTL:
        return _btc_price_cache["price"]

    try:
        resp = await client.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            headers={"User-Agent": "SignalDACH/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        price = resp.json().get("bitcoin", {}).get("usd")
        if price and isinstance(price, (int, float)) and price > 0:
            _btc_price_cache["price"] = float(price)
            _btc_price_cache["timestamp"] = now
            return float(price)
    except Exception as e:
        logger.warning(f"CoinGecko BTC price fetch failed, using cached value: {e}")

    return _btc_price_cache["price"]


# Free endpoint - recent large transactions
WHALE_API = "https://api.whale-alert.io/feed"
# Fallback: scrape their public RSS/status page
WHALE_STATUS = "https://whale-alert.io"


def _fmt_amount(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


class WhaleAlertScraper(BaseScraper):
    """Scrapes whale-alert.io for large crypto movements.

    Since the full API requires a paid key, this scraper uses the
    public blockchain.info API for large BTC transactions as a free alternative.
    """
    source_type = "whale_alert"

    async def scrape(self, source: dict) -> list[RawItem]:
        items: list[RawItem] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=20) as client:
            # Use blockchain.info unconfirmed transactions (free, no key)
            # Filter for large ones (>100 BTC)
            try:
                resp = await client.get(
                    "https://blockchain.info/unconfirmed-transactions?format=json",
                    headers={"User-Agent": "SignalDACH/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()
                txs = data.get("txs", [])
            except httpx.HTTPError as e:
                logger.warning(f"Blockchain.info API failed: {e}")
                txs = []

            # Fetch current BTC price from CoinGecko (with fallback)
            btc_price = await _fetch_btc_price(client)
            whale_txs = []
            for tx in txs:
                total_output = sum(o.get("value", 0) for o in tx.get("out", [])) / 100_000_000  # satoshi to BTC
                if total_output >= 10:  # >10 BTC
                    whale_txs.append({
                        "hash": tx.get("hash", "")[:16],
                        "btc_amount": total_output,
                        "usd_amount": total_output * btc_price,
                        "inputs": len(tx.get("inputs", [])),
                        "outputs": len(tx.get("out", [])),
                    })

            whale_txs.sort(key=lambda x: x["btc_amount"], reverse=True)

            # Create summary item
            if whale_txs:
                top5 = whale_txs[:5]
                total_btc = sum(t["btc_amount"] for t in whale_txs)
                total_usd = sum(t["usd_amount"] for t in whale_txs)

                title = (
                    f"Whale Alert: {len(whale_txs)} large BTC transactions detected | "
                    f"Total: {total_btc:.1f} BTC (~{_fmt_amount(total_usd)})"
                )

                details = []
                for t in top5:
                    details.append(
                        f"- {t['btc_amount']:.2f} BTC (~{_fmt_amount(t['usd_amount'])}) "
                        f"| {t['inputs']} inputs -> {t['outputs']} outputs"
                    )

                content = (
                    f"Whale Transaction Summary (last batch):\n"
                    f"Total whale txs (>10 BTC): {len(whale_txs)}\n"
                    f"Total volume: {total_btc:.1f} BTC (~{_fmt_amount(total_usd)})\n\n"
                    f"Top 5 largest:\n" + "\n".join(details)
                )

                ext_id = hashlib.sha256(
                    f"whale-btc-{now.strftime('%Y-%m-%d-%H-%M')}".encode()
                ).hexdigest()[:16]

                urgency = "high" if any(t["btc_amount"] >= 100 for t in whale_txs) else "normal"

                items.append(
                    RawItem(
                        title=title,
                        content=content,
                        url="https://whale-alert.io/",
                        author="Whale Alert (blockchain.info)",
                        published_at=now,
                        external_id=ext_id,
                        source_meta={
                            "whale_count": len(whale_txs),
                            "total_btc": round(total_btc, 2),
                            "total_usd": round(total_usd, 0),
                            "largest_btc": round(top5[0]["btc_amount"], 2) if top5 else 0,
                            "urgency_override": urgency,
                        },
                    )
                )

            # Also check for significant ETH movements via Etherscan (free tier)
            try:
                # Top ETH gas usage = network activity indicator
                resp = await client.get(
                    "https://api.etherscan.io/api?module=gastracker&action=gasoracle",
                    headers={"User-Agent": "SignalDACH/1.0"},
                )
                resp.raise_for_status()
                gas_data = resp.json().get("result", {})
                if gas_data and isinstance(gas_data, dict):
                    safe_gas = gas_data.get("SafeGasPrice", "?")
                    fast_gas = gas_data.get("FastGasPrice", "?")
                    avg_gas = gas_data.get("ProposeGasPrice", "?")

                    gas_title = f"ETH Gas: {avg_gas} Gwei (Safe: {safe_gas} | Fast: {fast_gas})"
                    gas_content = (
                        f"Ethereum Gas Prices:\n"
                        f"Safe: {safe_gas} Gwei\n"
                        f"Standard: {avg_gas} Gwei\n"
                        f"Fast: {fast_gas} Gwei\n\n"
                        f"High gas prices indicate heavy network usage, "
                        f"often correlated with market volatility or NFT/DeFi activity."
                    )

                    ext_id = hashlib.sha256(
                        f"eth-gas-{now.strftime('%Y-%m-%d-%H')}".encode()
                    ).hexdigest()[:16]

                    items.append(
                        RawItem(
                            title=gas_title,
                            content=gas_content,
                            url="https://etherscan.io/gastracker",
                            author="Etherscan",
                            published_at=now,
                            external_id=ext_id,
                            source_meta={
                                "safe_gas": safe_gas,
                                "standard_gas": avg_gas,
                                "fast_gas": fast_gas,
                            },
                        )
                    )
            except httpx.HTTPError as e:
                logger.debug(f"Etherscan gas tracker failed: {e}")

        logger.info(f"Whale Alert scraped: {len(items)} items ({len(whale_txs) if whale_txs else 0} whale txs)")
        return items
