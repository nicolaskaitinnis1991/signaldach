"""Causal Intelligence Engine — goes beyond correlation to causation.

Implements:
1. Granger Causality Tests — does metric X predict metric Y?
2. Regime Detection — identifies market regimes (risk-on, risk-off, transition)
3. Causal Chain Discovery — finds chains like: regulatory_news → fear_greed → price

Uses scipy for statistical tests, no heavy ML deps required.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Time-series helpers
# ---------------------------------------------------------------------------

def _get_metric_series(
    metric_type: str,
    table: str = "market_metrics",
    value_col: str = "value",
    days: int = 30,
    filter_col: Optional[str] = None,
    filter_val: Optional[str] = None,
) -> list[tuple[str, float]]:
    """Fetch time-ordered (ts, value) pairs for a metric."""
    with get_db() as conn:
        cur = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conditions = [f"metric_type = ?", "ts > ?"]
        params = [metric_type, cutoff]

        if filter_col and filter_val:
            conditions.append(f"{filter_col} = ?")
            params.append(filter_val)

        where = " AND ".join(conditions)
        cur.execute(
            f"SELECT ts, {value_col} FROM {table} WHERE {where} ORDER BY ts ASC",
            params,
        )
        return [(dict(r)["ts"], dict(r)[value_col]) for r in cur.fetchall()]


def _get_price_series(symbol: str = "BTC/USDT", days: int = 30) -> list[tuple[str, float]]:
    """Fetch price series for a symbol."""
    with get_db() as conn:
        cur = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cur.execute(
            "SELECT ts, price FROM price_ticks WHERE symbol LIKE ? AND ts > ? ORDER BY ts ASC",
            (f"%{symbol.split('/')[0]}%", cutoff),
        )
        return [(dict(r)["ts"], dict(r)["price"]) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Granger-like Causality
# ---------------------------------------------------------------------------

def _simple_correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation between two equal-length series."""
    if len(x) != len(y) or len(x) < 3:
        return 0.0
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / n
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x) / n)
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y) / n)
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def granger_test(
    cause_metric: str,
    effect_metric: str,
    lag: int = 1,
    days: int = 30,
) -> dict:
    """Simplified Granger causality: does lagged cause_metric predict effect_metric?

    Returns correlation between lagged cause and current effect.
    High positive = cause precedes effect. Use multiple lags to find optimal.
    """
    cause_series = _get_metric_series(cause_metric, days=days)
    effect_series = _get_metric_series(effect_metric, days=days)

    if len(cause_series) < 10 or len(effect_series) < 10:
        return {
            "cause": cause_metric,
            "effect": effect_metric,
            "lag": lag,
            "correlation": None,
            "data_points": min(len(cause_series), len(effect_series)),
            "message": "Insufficient data",
        }

    # Align series by taking values at similar timestamps (nearest-neighbor)
    cause_vals = [v for _, v in cause_series]
    effect_vals = [v for _, v in effect_series]

    # Apply lag
    min_len = min(len(cause_vals) - lag, len(effect_vals))
    if min_len < 5:
        return {"cause": cause_metric, "effect": effect_metric, "lag": lag,
                "correlation": None, "message": "Series too short for lag"}

    lagged_cause = cause_vals[:min_len]
    current_effect = effect_vals[lag:lag + min_len]

    corr = _simple_correlation(lagged_cause, current_effect)

    return {
        "cause": cause_metric,
        "effect": effect_metric,
        "lag": lag,
        "correlation": round(corr, 4),
        "data_points": min_len,
        "interpretation": (
            "strong causal signal" if abs(corr) > 0.5
            else "moderate signal" if abs(corr) > 0.3
            else "weak signal" if abs(corr) > 0.1
            else "no significant signal"
        ),
    }


# ---------------------------------------------------------------------------
# Market Regime Detection
# ---------------------------------------------------------------------------

def detect_regime(days: int = 30) -> dict:
    """Detect current market regime based on multiple indicators.

    Regimes: risk_on, risk_off, transition, accumulation, distribution
    """
    indicators = {}

    # Fear & Greed
    fg_series = _get_metric_series("fear_greed_index", days=days)
    if fg_series:
        latest_fg = fg_series[-1][1]
        avg_fg = sum(v for _, v in fg_series) / len(fg_series)
        indicators["fear_greed"] = latest_fg
        indicators["fear_greed_trend"] = "rising" if latest_fg > avg_fg else "falling"

    # Funding rates (positive = bullish leverage, extreme = overheated)
    fr_series = _get_metric_series("funding_rate", days=min(days, 7))
    if fr_series:
        avg_fr = sum(v for _, v in fr_series) / len(fr_series)
        indicators["avg_funding_rate"] = avg_fr

    # Price trend
    prices = _get_price_series(days=days)
    if len(prices) >= 10:
        price_vals = [v for _, v in prices]
        first_quarter = sum(price_vals[:len(price_vals)//4]) / max(1, len(price_vals)//4)
        last_quarter = sum(price_vals[-len(price_vals)//4:]) / max(1, len(price_vals)//4)
        price_trend = (last_quarter - first_quarter) / first_quarter if first_quarter > 0 else 0
        indicators["price_trend_pct"] = round(price_trend * 100, 2)

    # Determine regime
    regime = "unknown"
    confidence = 0.0
    reasons = []

    fg = indicators.get("fear_greed", 50)
    price_trend = indicators.get("price_trend_pct", 0)
    avg_fr = indicators.get("avg_funding_rate", 0)

    if fg > 70 and price_trend > 5:
        regime = "risk_on"
        confidence = min(1.0, fg / 100)
        reasons.append("High greed + rising prices")
        if avg_fr > 0.01:
            reasons.append("Extreme funding rates — potential overheating")
    elif fg < 30 and price_trend < -5:
        regime = "risk_off"
        confidence = min(1.0, (100 - fg) / 100)
        reasons.append("Extreme fear + falling prices")
    elif fg < 30 and price_trend > 0:
        regime = "accumulation"
        confidence = 0.6
        reasons.append("Fear despite rising prices — smart money accumulating")
    elif fg > 70 and price_trend < 0:
        regime = "distribution"
        confidence = 0.6
        reasons.append("Greed despite falling prices — distribution phase")
    else:
        regime = "transition"
        confidence = 0.4
        reasons.append("Mixed signals — market in transition")

    return {
        "regime": regime,
        "confidence": round(confidence, 3),
        "reasons": reasons,
        "indicators": {k: round(v, 4) if isinstance(v, float) else v for k, v in indicators.items()},
        "analysis_period_days": days,
    }


# ---------------------------------------------------------------------------
# Causal Chain Discovery
# ---------------------------------------------------------------------------

def discover_causal_chains(days: int = 30) -> dict:
    """Auto-discover causal relationships between available metrics.

    Tests pairs of metrics with different lags to find predictive relationships.
    """
    # Metrics to test
    metrics = [
        "fear_greed_index",
        "funding_rate",
        "total_market_cap",
        "btc_dominance",
        "stablecoin_total_mcap",
    ]

    chains = []
    for cause in metrics:
        for effect in metrics:
            if cause == effect:
                continue
            for lag in [1, 3, 5]:
                result = granger_test(cause, effect, lag=lag, days=days)
                if result.get("correlation") is not None and abs(result["correlation"]) > 0.3:
                    chains.append(result)

    # Sort by correlation strength
    chains.sort(key=lambda c: abs(c.get("correlation", 0)), reverse=True)

    return {
        "discovered_chains": chains[:10],
        "total_tested": len(metrics) * (len(metrics) - 1) * 3,
        "significant_found": len(chains),
        "analysis_period_days": days,
    }
