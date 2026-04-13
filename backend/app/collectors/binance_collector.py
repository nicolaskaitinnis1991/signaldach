"""Binance real-time data collector.

Two modes:
1. REST polling (collect_prices) — called by scheduler every 1-5 min
2. WebSocket streaming (run_ws_stream) — persistent connection for real-time ticks

Both are free, no auth needed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from app.collectors.base import store_price_ticks, store_market_metrics, publish_to_stream
from app.error_handling import CircuitBreaker

logger = logging.getLogger(__name__)

BINANCE_REST = "https://api.binance.com/api/v3"
BINANCE_FUTURES_REST = "https://fapi.binance.com/fapi/v1"
BINANCE_WS = "wss://stream.binance.com:9443/ws"

_cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
_CB_SOURCE = "binance"

# Symbols to track — major pairs
TRACKED_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "ATOMUSDT", "UNIUSDT", "LTCUSDT", "NEARUSDT",
    "ARBUSDT", "OPUSDT", "APTUSDT", "SUIUSDT", "SEIUSDT",
]


def _symbol_to_pair(symbol: str) -> str:
    """Convert 'BTCUSDT' to 'BTC/USDT'."""
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}/USDT"
    return symbol


async def collect_prices() -> int:
    """Fetch current prices via REST API (24hr ticker).

    Stores price ticks + 24h volume data. Called by scheduler.
    """
    if not _cb.allow_request(_CB_SOURCE):
        logger.warning("Binance circuit breaker OPEN, skipping")
        return 0

    now = datetime.now(timezone.utc)
    ticks: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Binance expects symbols as JSON array directly in the query string
            symbols_json = json.dumps(TRACKED_SYMBOLS, separators=(",", ":"))
            url = f"{BINANCE_REST}/ticker/24hr?symbols={symbols_json}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        for ticker in data:
            symbol = ticker.get("symbol", "")
            price = float(ticker.get("lastPrice", 0))
            if price <= 0:
                continue

            ticks.append({
                "ts": now,
                "symbol": _symbol_to_pair(symbol),
                "exchange": "binance",
                "price": price,
                "volume_24h": float(ticker.get("quoteVolume", 0)),
                "change_pct_24h": float(ticker.get("priceChangePercent", 0)),
            })

        stored = await store_price_ticks(ticks)
        _cb.record_success(_CB_SOURCE)

        btc_price = next((t["price"] for t in ticks if "BTC" in t["symbol"]), 0)
        await publish_to_stream("signals:prices", {
            "source": "binance",
            "count": str(stored),
            "ts": now.isoformat(),
            "btc": f"{btc_price:.2f}",
        })

        logger.info("Binance: stored %d price ticks", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("Binance price collection failed: %s", e)
        return 0


async def collect_funding_rates() -> int:
    """Fetch perpetual futures funding rates (free, no auth)."""
    if not _cb.allow_request(_CB_SOURCE):
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BINANCE_FUTURES_REST}/premiumIndex")
            resp.raise_for_status()
            data = resp.json()

        for item in data:
            symbol = item.get("symbol", "")
            if symbol not in TRACKED_SYMBOLS:
                continue

            funding = float(item.get("lastFundingRate", 0))
            mark_price = float(item.get("markPrice", 0))

            metrics.append({
                "ts": now,
                "metric_type": "funding_rate",
                "symbol": _symbol_to_pair(symbol),
                "exchange": "binance",
                "value": funding,
                "metadata_json": json.dumps({"mark_price": mark_price}),
            })

        stored = await store_market_metrics(metrics)
        _cb.record_success(_CB_SOURCE)
        logger.info("Binance: stored %d funding rates", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("Binance funding rates failed: %s", e)
        return 0


async def collect_open_interest() -> int:
    """Fetch open interest for tracked futures pairs."""
    if not _cb.allow_request(_CB_SOURCE):
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for symbol in TRACKED_SYMBOLS[:10]:  # Top 10 to stay within limits
                try:
                    resp = await client.get(
                        f"{BINANCE_FUTURES_REST}/openInterest",
                        params={"symbol": symbol},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    oi = float(data.get("openInterest", 0))
                    if oi > 0:
                        metrics.append({
                            "ts": now,
                            "metric_type": "open_interest",
                            "symbol": _symbol_to_pair(symbol),
                            "exchange": "binance",
                            "value": oi,
                        })
                except httpx.HTTPError:
                    continue

        stored = await store_market_metrics(metrics)
        _cb.record_success(_CB_SOURCE)
        logger.info("Binance: stored %d open interest metrics", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("Binance OI collection failed: %s", e)
        return 0


async def collect_all() -> int:
    """Run all Binance REST collections."""
    total = 0
    total += await collect_prices()
    total += await collect_funding_rates()
    total += await collect_open_interest()
    return total


# ---------------------------------------------------------------------------
# WebSocket streaming (run as background task)
# ---------------------------------------------------------------------------

_ws_task: asyncio.Task | None = None


async def _ws_stream_loop():
    """Persistent WebSocket connection to Binance for real-time trade data.

    Subscribes to miniTicker streams for all tracked symbols.
    Batches ticks and stores every 10 seconds.
    """
    import websockets

    streams = "/".join(f"{s.lower()}@miniTicker" for s in TRACKED_SYMBOLS)
    url = f"{BINANCE_WS}/{streams}"

    batch: list[dict] = []
    last_flush = asyncio.get_event_loop().time()

    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                logger.info("Binance WS connected (%d streams)", len(TRACKED_SYMBOLS))

                async for raw in ws:
                    data = json.loads(raw)
                    symbol = data.get("s", "")
                    price = float(data.get("c", 0))
                    if price <= 0:
                        continue

                    batch.append({
                        "ts": datetime.now(timezone.utc),
                        "symbol": _symbol_to_pair(symbol),
                        "exchange": "binance_ws",
                        "price": price,
                        "volume_24h": float(data.get("q", 0)),
                        "change_pct_24h": float(data.get("P", 0)) if data.get("P") else None,
                    })

                    now = asyncio.get_event_loop().time()
                    if now - last_flush >= 10 and batch:
                        stored = await store_price_ticks(batch)
                        await publish_to_stream("signals:prices", {
                            "source": "binance_ws",
                            "count": str(stored),
                            "ts": datetime.now(timezone.utc).isoformat(),
                        })
                        batch.clear()
                        last_flush = now

        except asyncio.CancelledError:
            logger.info("Binance WS stream cancelled")
            return
        except Exception as e:
            logger.warning("Binance WS error, reconnecting in 5s: %s", e)
            if batch:
                await store_price_ticks(batch)
                batch.clear()
            await asyncio.sleep(5)


def start_ws_stream():
    """Start the Binance WebSocket stream as a background task."""
    global _ws_task
    try:
        import websockets  # noqa: F401
    except ImportError:
        logger.info("websockets not installed, Binance WS stream disabled")
        return

    if _ws_task is None or _ws_task.done():
        _ws_task = asyncio.create_task(_ws_stream_loop())
        logger.info("Binance WS stream started")


def stop_ws_stream():
    """Stop the Binance WebSocket stream."""
    global _ws_task
    if _ws_task and not _ws_task.done():
        _ws_task.cancel()
        _ws_task = None
