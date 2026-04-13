"""CoinGecko price & market data collector.

Fetches top coins by market cap and stores structured data in price_ticks.
Free API, no auth needed. Rate limit: ~10-30 req/min.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from app.collectors.base import store_price_ticks, store_market_metrics, publish_to_stream
from app.error_handling import CircuitBreaker

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
MARKETS_URL = f"{COINGECKO_BASE}/coins/markets"
GLOBAL_URL = f"{COINGECKO_BASE}/global"

_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=120)
_CB_SOURCE = "coingecko"

# Top coins to track — expand as needed
TOP_COINS_COUNT = 100


async def collect_prices() -> int:
    """Fetch top coin prices from CoinGecko and store in price_ticks.

    Returns number of ticks stored.
    """
    if not _cb.allow_request(_CB_SOURCE):
        logger.warning("CoinGecko circuit breaker OPEN, skipping")
        return 0

    now = datetime.now(timezone.utc)
    ticks: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                MARKETS_URL,
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": TOP_COINS_COUNT,
                    "sparkline": "false",
                    "price_change_percentage": "24h",
                },
            )
            resp.raise_for_status()
            coins = resp.json()

        for coin in coins:
            symbol = (coin.get("symbol") or "").upper()
            price = coin.get("current_price")
            if price is None:
                continue

            ticks.append({
                "ts": now,
                "symbol": f"{symbol}/USDT",
                "exchange": "coingecko",
                "price": float(price),
                "volume_24h": coin.get("total_volume"),
                "market_cap": coin.get("market_cap"),
                "change_pct_24h": coin.get("price_change_percentage_24h"),
            })

        stored = await store_price_ticks(ticks)
        _cb.record_success(_CB_SOURCE)

        # Publish summary to Redis Stream
        await publish_to_stream("signals:prices", {
            "source": "coingecko",
            "count": str(stored),
            "ts": now.isoformat(),
            "top_btc": str(next((t["price"] for t in ticks if "BTC" in t["symbol"]), 0)),
        })

        logger.info("CoinGecko: stored %d price ticks", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("CoinGecko collection failed: %s", e)
        return 0


async def collect_global_metrics() -> int:
    """Fetch global market metrics (total market cap, BTC dominance, etc.)."""
    if not _cb.allow_request(_CB_SOURCE):
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(GLOBAL_URL)
            resp.raise_for_status()
            data = resp.json().get("data", {})

        if not data:
            return 0

        total_mcap = data.get("total_market_cap", {}).get("usd")
        if total_mcap:
            metrics.append({
                "ts": now,
                "metric_type": "total_market_cap",
                "value": total_mcap,
                "metadata_json": json.dumps({
                    "btc_dominance": data.get("market_cap_percentage", {}).get("btc"),
                    "eth_dominance": data.get("market_cap_percentage", {}).get("eth"),
                    "active_coins": data.get("active_cryptocurrencies"),
                    "change_24h_pct": data.get("market_cap_change_percentage_24h_usd"),
                }),
            })

        btc_dom = data.get("market_cap_percentage", {}).get("btc")
        if btc_dom is not None:
            metrics.append({
                "ts": now,
                "metric_type": "btc_dominance",
                "symbol": "BTC",
                "value": btc_dom,
            })

        total_vol = data.get("total_volume", {}).get("usd")
        if total_vol:
            metrics.append({
                "ts": now,
                "metric_type": "total_volume_24h",
                "value": total_vol,
            })

        stored = await store_market_metrics(metrics)
        _cb.record_success(_CB_SOURCE)
        logger.info("CoinGecko global: stored %d metrics", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("CoinGecko global metrics failed: %s", e)
        return 0


async def collect_all() -> int:
    """Run all CoinGecko collections. Returns total items stored."""
    prices = await collect_prices()
    global_m = await collect_global_metrics()
    return prices + global_m
