"""DefiLlama TVL & DeFi metrics collector.

Stores on-chain metrics (TVL per protocol, per chain, stablecoin mcap).
Completely free, no auth, no rate limit.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from app.collectors.base import store_onchain_metrics, store_market_metrics, publish_to_stream
from app.error_handling import CircuitBreaker

logger = logging.getLogger(__name__)

PROTOCOLS_URL = "https://api.llama.fi/protocols"
CHAINS_URL = "https://api.llama.fi/v2/chains"
STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
YIELDS_URL = "https://yields.llama.fi/pools"

_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=120)
_CB_SOURCE = "defillama"


async def collect_protocol_tvl() -> int:
    """Fetch top DeFi protocol TVL data."""
    if not _cb.allow_request(_CB_SOURCE):
        logger.warning("DefiLlama circuit breaker OPEN, skipping")
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(PROTOCOLS_URL)
            resp.raise_for_status()
            protocols = resp.json()

        # Sort by TVL, take top 50
        protocols.sort(key=lambda p: p.get("tvl") or 0, reverse=True)
        for proto in protocols[:50]:
            tvl = proto.get("tvl")
            if not tvl or tvl <= 0:
                continue

            metrics.append({
                "ts": now,
                "metric_type": "tvl",
                "chain": proto.get("chain", "multi"),
                "protocol": proto.get("name"),
                "value": tvl,
                "unit": "USD",
                "metadata_json": json.dumps({
                    "category": proto.get("category"),
                    "change_1d": proto.get("change_1d"),
                    "change_7d": proto.get("change_7d"),
                    "chains": proto.get("chains", []),
                }),
            })

        stored = await store_onchain_metrics(metrics)
        _cb.record_success(_CB_SOURCE)

        total_tvl = sum(m["value"] for m in metrics)
        await publish_to_stream("signals:onchain", {
            "source": "defillama",
            "type": "tvl",
            "count": str(stored),
            "total_tvl": f"{total_tvl:.0f}",
            "ts": now.isoformat(),
        })

        logger.info("DefiLlama: stored %d protocol TVL metrics", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("DefiLlama protocol TVL failed: %s", e)
        return 0


async def collect_chain_tvl() -> int:
    """Fetch TVL per blockchain."""
    if not _cb.allow_request(_CB_SOURCE):
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(CHAINS_URL)
            resp.raise_for_status()
            chains = resp.json()

        chains.sort(key=lambda c: c.get("tvl") or 0, reverse=True)
        for chain in chains[:30]:
            tvl = chain.get("tvl")
            if not tvl or tvl <= 0:
                continue

            metrics.append({
                "ts": now,
                "metric_type": "chain_tvl",
                "chain": chain.get("name") or chain.get("gecko_id", "unknown"),
                "value": tvl,
                "unit": "USD",
            })

        stored = await store_onchain_metrics(metrics)
        _cb.record_success(_CB_SOURCE)
        logger.info("DefiLlama: stored %d chain TVL metrics", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("DefiLlama chain TVL failed: %s", e)
        return 0


async def collect_stablecoin_metrics() -> int:
    """Fetch stablecoin market cap data."""
    if not _cb.allow_request(_CB_SOURCE):
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(STABLECOINS_URL)
            resp.raise_for_status()
            data = resp.json()

        stables = data.get("peggedAssets", [])
        stables.sort(key=lambda s: (s.get("circulating", {}).get("peggedUSD") or 0), reverse=True)

        total_mcap = 0.0
        for stable in stables[:20]:
            mcap = stable.get("circulating", {}).get("peggedUSD") or 0
            if mcap <= 0:
                continue
            total_mcap += mcap

            metrics.append({
                "ts": now,
                "metric_type": "stablecoin_mcap",
                "protocol": stable.get("name"),
                "value": mcap,
                "unit": "USD",
                "metadata_json": json.dumps({
                    "symbol": stable.get("symbol"),
                    "peg_type": stable.get("pegType"),
                    "chains": list(stable.get("chainCirculating", {}).keys())[:5],
                }),
            })

        # Total stablecoin market cap as a market metric
        if total_mcap > 0:
            from app.collectors.base import store_market_metrics
            await store_market_metrics([{
                "ts": now,
                "metric_type": "stablecoin_total_mcap",
                "value": total_mcap,
            }])

        stored = await store_onchain_metrics(metrics)
        _cb.record_success(_CB_SOURCE)
        logger.info("DefiLlama: stored %d stablecoin metrics (total: $%.0fB)", stored, total_mcap / 1e9)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("DefiLlama stablecoins failed: %s", e)
        return 0


async def collect_top_yields() -> int:
    """Fetch top DeFi yields for signal detection (unusual yield = risk signal)."""
    if not _cb.allow_request(_CB_SOURCE):
        return 0

    now = datetime.now(timezone.utc)
    metrics: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(YIELDS_URL)
            resp.raise_for_status()
            pools = resp.json().get("data", [])

        # Filter: only pools with >$10M TVL, sort by APY
        pools = [p for p in pools if (p.get("tvlUsd") or 0) > 10_000_000]
        pools.sort(key=lambda p: p.get("apy") or 0, reverse=True)

        for pool in pools[:30]:
            apy = pool.get("apy")
            if apy is None:
                continue

            metrics.append({
                "ts": now,
                "metric_type": "defi_yield",
                "chain": pool.get("chain"),
                "protocol": pool.get("project"),
                "value": apy,
                "unit": "APY%",
                "metadata_json": json.dumps({
                    "pool": pool.get("pool"),
                    "symbol": pool.get("symbol"),
                    "tvl_usd": pool.get("tvlUsd"),
                    "apy_base": pool.get("apyBase"),
                    "apy_reward": pool.get("apyReward"),
                    "il_risk": pool.get("ilRisk"),
                }),
            })

        stored = await store_onchain_metrics(metrics)
        _cb.record_success(_CB_SOURCE)
        logger.info("DefiLlama: stored %d yield metrics", stored)
        return stored

    except Exception as e:
        _cb.record_failure(_CB_SOURCE)
        logger.error("DefiLlama yields failed: %s", e)
        return 0


async def collect_all() -> int:
    """Run all DefiLlama collections."""
    total = 0
    total += await collect_protocol_tvl()
    total += await collect_chain_tvl()
    total += await collect_stablecoin_metrics()
    total += await collect_top_yields()
    return total
