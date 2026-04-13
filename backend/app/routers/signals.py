"""Signal Intelligence API — multi-agent reasoning, correlation, anomaly detection."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user

router = APIRouter(prefix="/api/signals", tags=["signals"], dependencies=[Depends(get_current_user)])


@router.get("/analyze")
async def analyze_signal(
    symbol: str = Query("BTC/USDT", description="Symbol to analyze"),
):
    """Run the multi-agent reasoning engine and get a composite market signal."""
    from app.ai.agents.synthesis import get_market_signal
    return await get_market_signal(symbol)


@router.get("/agents")
async def list_agents():
    """List available analysis agents and their descriptions."""
    return {
        "agents": [
            {"name": "sentiment", "description": "News & social sentiment via FinBERT"},
            {"name": "technical", "description": "Price patterns, momentum, RSI, SMA"},
            {"name": "onchain", "description": "DeFi TVL, stablecoin flows, yield analysis"},
            {"name": "regulatory", "description": "DACH regulation impact assessment"},
        ],
        "synthesis": "Weighted combination of all agents into composite signal",
    }


@router.get("/correlation")
async def news_price_correlation(
    days: int = Query(7, ge=1, le=90),
    min_relevance: int = Query(7, ge=1, le=10),
    symbol: str = Query("BTC/USDT"),
):
    """Analyze correlation between high-relevance news and price movements."""
    from app.ai.correlation import analyze_news_correlation
    return analyze_news_correlation(days=days, min_relevance=min_relevance, symbol=symbol)


@router.get("/anomalies")
async def anomaly_scan(
    type: str = Query("all", description="Type: all, price, volume, funding_rate, tvl"),
    symbol: str = Query("BTC/USDT"),
    hours: int = Query(168, ge=1, le=720),
):
    """Run anomaly detection on market data."""
    if type == "all":
        from app.ai.anomaly import run_full_anomaly_scan
        return run_full_anomaly_scan()

    from app.ai.anomaly import (
        detect_price_anomalies,
        detect_volume_anomalies,
        detect_metric_anomalies,
        detect_onchain_anomalies,
    )

    if type == "price":
        return detect_price_anomalies(symbol=symbol, hours=hours)
    elif type == "volume":
        return detect_volume_anomalies(hours=hours)
    elif type in ("funding_rate", "fear_greed"):
        return detect_metric_anomalies(metric_type=type, hours=hours)
    elif type == "tvl":
        return detect_onchain_anomalies(metric_type="tvl", hours=hours)
    else:
        return {"error": f"Unknown anomaly type: {type}"}


@router.get("/event-impact")
async def event_impact(
    event_time: str = Query(..., description="ISO timestamp of the event"),
    symbol: str = Query("BTC/USDT"),
):
    """Compute price impact around a specific event time."""
    from datetime import datetime
    from app.ai.correlation import compute_event_impact

    try:
        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError:
        return {"error": "Invalid timestamp format. Use ISO 8601."}

    result = compute_event_impact(dt, symbol=symbol)
    if result is None:
        return {"error": "No price data available for this event window"}
    return result


@router.get("/regime")
async def market_regime(
    days: int = Query(30, ge=1, le=90),
):
    """Detect current market regime (risk-on, risk-off, accumulation, etc.)."""
    from app.ai.causal import detect_regime
    return detect_regime(days=days)


@router.get("/causal")
async def causal_chains(
    days: int = Query(30, ge=7, le=90),
):
    """Discover causal relationships between market metrics."""
    from app.ai.causal import discover_causal_chains
    return discover_causal_chains(days=days)


@router.get("/granger")
async def granger_causality(
    cause: str = Query(..., description="Cause metric, e.g. fear_greed_index"),
    effect: str = Query(..., description="Effect metric, e.g. funding_rate"),
    lag: int = Query(1, ge=1, le=10),
    days: int = Query(30, ge=7, le=90),
):
    """Test Granger causality between two metrics."""
    from app.ai.causal import granger_test
    return granger_test(cause, effect, lag=lag, days=days)
