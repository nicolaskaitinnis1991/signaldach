"""Collector scheduler — registers all data collectors with APScheduler.

Call register_collector_jobs(scheduler) during app startup.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _run_async(coro_fn):
    """Wrapper to run async collector in sync APScheduler context.

    APScheduler executes jobs in worker threads, which have no event loop
    on Python >=3.12 (asyncio.get_event_loop() raises there). Run each job
    in its own loop via asyncio.run().
    """
    def wrapper():
        try:
            asyncio.run(coro_fn())
        except Exception as e:
            logger.error("Collector job failed: %s", e)
    return wrapper


def register_collector_jobs(scheduler) -> None:
    """Register all data collector jobs with the APScheduler instance.

    Intervals:
    - Binance REST prices: every 2 minutes
    - CoinGecko prices: every 5 minutes (lower rate limit)
    - Binance funding rates: every 15 minutes
    - Binance open interest: every 15 minutes
    - CoinGecko global metrics: every 10 minutes
    - DefiLlama protocol TVL: every 30 minutes
    - DefiLlama chain TVL: every 30 minutes
    - DefiLlama stablecoins: every 60 minutes
    - DefiLlama yields: every 60 minutes
    - Fear & Greed Index: every 60 minutes
    """
    from app.collectors.binance_collector import (
        collect_prices as binance_prices,
        collect_funding_rates,
        collect_open_interest,
    )
    from app.collectors.coingecko_collector import (
        collect_prices as cg_prices,
        collect_global_metrics,
    )
    from app.collectors.defillama_collector import (
        collect_protocol_tvl,
        collect_chain_tvl,
        collect_stablecoin_metrics,
        collect_top_yields,
    )
    from app.collectors.fear_greed_collector import collect_fear_greed

    jobs = [
        ("binance_prices", binance_prices, 2),
        ("binance_funding", collect_funding_rates, 15),
        ("binance_oi", collect_open_interest, 15),
        ("coingecko_prices", cg_prices, 5),
        ("coingecko_global", collect_global_metrics, 10),
        ("defillama_protocols", collect_protocol_tvl, 30),
        ("defillama_chains", collect_chain_tvl, 30),
        ("defillama_stablecoins", collect_stablecoin_metrics, 60),
        ("defillama_yields", collect_top_yields, 60),
        ("fear_greed", collect_fear_greed, 60),
    ]

    # Stagger initial runs over the first 30 seconds so all collectors fire
    # shortly after startup (avoids empty market page on fresh boot) but not
    # all at the exact same moment.
    now = datetime.now(timezone.utc)
    for idx, (job_id, coro_fn, interval_min) in enumerate(jobs):
        scheduler.add_job(
            _run_async(coro_fn),
            "interval",
            minutes=interval_min,
            id=f"collector_{job_id}",
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=60,
            next_run_time=now + timedelta(seconds=3 + idx * 2),
        )

    logger.info("Registered %d collector jobs (initial runs staggered over startup)", len(jobs))
