"""Market data API endpoints for time-series data.

Serves price history, market metrics, and on-chain data
from the time-series tables populated by data collectors.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market-data"])

# ---------------------------------------------------------------------------
# Symbol validation
# ---------------------------------------------------------------------------
ALLOWED_SYMBOLS = {
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "AVAX/USDT", "DOT/USDT", "MATIC/USDT", "LINK/USDT",
    "DOGE/USDT", "UNI/USDT",
}


def _validate_symbol(symbol: str) -> str:
    """Validate and normalize symbol input."""
    s = symbol.strip().upper()
    if s not in ALLOWED_SYMBOLS:
        # Allow any SYMBOL/USDT pattern (alphanumeric)
        if not re.match(r'^[A-Z0-9]{2,10}/[A-Z]{3,5}$', s):
            raise HTTPException(status_code=400, detail=f"Invalid symbol format: {symbol}")
    return s


def _placeholder(n: int) -> str:
    return "%s" if USE_POSTGRES else "?"


@router.get("/prices/latest")
async def get_latest_prices(
    symbols: Optional[str] = Query(None, max_length=500, description="Comma-separated symbols, e.g. BTC/USDT,ETH/USDT"),
    limit: int = Query(20, ge=1, le=200),
):
    """Get latest price ticks, optionally filtered by symbols.

    Returns the newest tick per symbol (deduped) so the UI shows one row per
    asset rather than historical duplicates.
    """
    with get_db() as conn:
        cur = conn.cursor()
        if symbols:
            symbol_list = [_validate_symbol(s) for s in symbols.split(",")]
            placeholders = ",".join([_placeholder(i) for i in range(len(symbol_list))])
            cur.execute(
                f"SELECT * FROM price_ticks WHERE symbol IN ({placeholders}) "
                f"ORDER BY ts DESC LIMIT {_placeholder(0)}",
                symbol_list + [limit * 10],
            )
        else:
            cur.execute(
                f"SELECT * FROM price_ticks ORDER BY ts DESC LIMIT {_placeholder(0)}",
                [limit * 10],
            )
        rows = cur.fetchall()
        # Deduplicate by symbol, keeping the newest tick per symbol
        seen: set[str] = set()
        prices: list[dict] = []
        for r in rows:
            d = dict(r)
            sym = d.get("symbol")
            if sym in seen:
                continue
            seen.add(sym)
            prices.append(d)
            if len(prices) >= limit:
                break
        return {"prices": prices}


@router.get("/prices/history")
async def get_price_history(
    symbol: str = Query(..., max_length=20, description="Symbol, e.g. BTC/USDT"),
    hours: int = Query(24, ge=1, le=720),
    exchange: Optional[str] = Query(None, max_length=50),
):
    """Get price history for a symbol over the last N hours."""
    symbol = _validate_symbol(symbol)
    with get_db() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            time_filter = "ts > NOW() - INTERVAL '%s hours'"
        else:
            time_filter = "ts > datetime('now', '-' || ? || ' hours')"

        params = [symbol, hours]
        exchange_filter = ""
        if exchange:
            exchange_filter = f" AND exchange = {_placeholder(0)}"
            params.append(exchange)

        cur.execute(
            f"SELECT * FROM price_ticks WHERE symbol = {_placeholder(0)} "
            f"AND {time_filter}{exchange_filter} ORDER BY ts ASC",
            params,
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]


@router.get("/metrics/latest")
async def get_latest_metrics(
    metric_type: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Get latest market metrics (funding rates, OI, fear/greed, etc.)."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []

        if metric_type:
            conditions.append(f"metric_type = {_placeholder(0)}")
            params.append(metric_type)
        if symbol:
            validated_symbol = _validate_symbol(symbol)
            conditions.append(f"symbol = {_placeholder(0)}")
            params.append(validated_symbol)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        cur.execute(
            f"SELECT * FROM market_metrics{where} ORDER BY ts DESC LIMIT {_placeholder(0)}",
            params,
        )
        rows = cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("metadata_json"):
                try:
                    d["metadata"] = json.loads(d["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results


@router.get("/onchain/latest")
async def get_latest_onchain(
    metric_type: Optional[str] = Query(None),
    chain: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Get latest on-chain metrics (TVL, yields, stablecoin data)."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []

        if metric_type:
            conditions.append(f"metric_type = {_placeholder(0)}")
            params.append(metric_type)
        if chain:
            conditions.append(f"chain = {_placeholder(0)}")
            params.append(chain)
        if protocol:
            conditions.append(f"protocol = {_placeholder(0)}")
            params.append(protocol)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        cur.execute(
            f"SELECT * FROM onchain_metrics{where} ORDER BY ts DESC LIMIT {_placeholder(0)}",
            params,
        )
        rows = cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("metadata_json"):
                try:
                    d["metadata"] = json.loads(d["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results


@router.get("/summary")
async def get_market_summary():
    """Quick market summary — latest BTC/ETH price, fear/greed, total TVL."""
    from app.cache import cache_get, cache_set, CACHE_TTLS

    cached = await cache_get("market_summary")
    if cached:
        return cached

    with get_db() as conn:
        cur = conn.cursor()
        summary: dict = {
            "btc": None,
            "eth": None,
            "fear_greed": None,
            "global": {"total_market_cap": None, "btc_dominance": None},
            "data_freshness": {},
        }

        # Latest BTC price — parameterized query, supports both BTC/USDT and BTCUSDT formats
        ph = _placeholder(0)
        ph2 = _placeholder(0)
        cur.execute(
            f"SELECT symbol, price, change_pct_24h, volume_24h, ts FROM price_ticks "
            f"WHERE (symbol = {ph} OR symbol = {ph2}) ORDER BY ts DESC LIMIT 1",
            ["BTC/USDT", "BTCUSDT"],
        )
        btc = cur.fetchone()
        if btc:
            summary["btc"] = dict(btc)

        # Latest ETH price — parameterized query, supports both formats
        cur.execute(
            f"SELECT symbol, price, change_pct_24h, volume_24h, ts FROM price_ticks "
            f"WHERE (symbol = {ph} OR symbol = {ph2}) ORDER BY ts DESC LIMIT 1",
            ["ETH/USDT", "ETHUSDT"],
        )
        eth = cur.fetchone()
        if eth:
            summary["eth"] = dict(eth)

        # Fear & Greed — flatten classification from metadata_json into top-level field
        # so the frontend can render it without parsing.
        cur.execute(
            "SELECT value, metadata_json, ts FROM market_metrics "
            "WHERE metric_type = 'fear_greed_index' ORDER BY ts DESC LIMIT 1"
        )
        fg = cur.fetchone()
        if fg:
            d = dict(fg)
            classification = ""
            if d.get("metadata_json"):
                try:
                    meta = json.loads(d["metadata_json"])
                    classification = meta.get("classification", "")
                except (json.JSONDecodeError, TypeError):
                    pass
            summary["fear_greed"] = {
                "value": d["value"],
                "classification": classification,
                "ts": d["ts"],
            }

        # Global: total market cap + BTC dominance (both produced by CoinGecko global collector)
        cur.execute(
            "SELECT value, ts FROM market_metrics "
            "WHERE metric_type = 'total_market_cap' ORDER BY ts DESC LIMIT 1"
        )
        mcap = cur.fetchone()
        if mcap:
            summary["global"]["total_market_cap"] = dict(mcap)["value"]

        cur.execute(
            "SELECT value, ts FROM market_metrics "
            "WHERE metric_type = 'btc_dominance' ORDER BY ts DESC LIMIT 1"
        )
        dom = cur.fetchone()
        if dom:
            summary["global"]["btc_dominance"] = dict(dom)["value"]

        # Data freshness stats — table names are hardcoded constants, not user input
        _FRESHNESS_TABLES = ("price_ticks", "market_metrics", "onchain_metrics")
        for table in _FRESHNESS_TABLES:
            cur.execute(f"SELECT COUNT(*) as cnt, MAX(ts) as latest FROM {table}")
            row = cur.fetchone()
            if row:
                rd = dict(row)
                summary[f"{table}_count"] = rd["cnt"]
                summary[f"{table}_latest"] = rd["latest"]
                summary["data_freshness"][table] = rd["latest"]

        await cache_set("market_summary", summary, CACHE_TTLS["market_summary"])
        return summary


@router.post("/collect/trigger")
async def trigger_collection(
    collector: str = Query(..., max_length=20, pattern=r"^(binance|coingecko|defillama|fear_greed|all)$", description="Collector to run: binance, coingecko, defillama, fear_greed, all"),
):
    """Manually trigger a data collection run."""
    results = {}

    if collector in ("binance", "all"):
        from app.collectors.binance_collector import collect_all as binance_all
        results["binance"] = await binance_all()

    if collector in ("coingecko", "all"):
        from app.collectors.coingecko_collector import collect_all as cg_all
        results["coingecko"] = await cg_all()

    if collector in ("defillama", "all"):
        from app.collectors.defillama_collector import collect_all as dl_all
        results["defillama"] = await dl_all()

    if collector in ("fear_greed", "all"):
        from app.collectors.fear_greed_collector import collect_all as fg_all
        results["fear_greed"] = await fg_all()

    if not results:
        return {"error": f"Unknown collector: {collector}"}

    total = sum(results.values())
    return {"collected": total, "breakdown": results}
