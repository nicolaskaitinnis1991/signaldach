"""Anomaly Detection for market data using Isolation Forest.

Detects unusual patterns in:
- Price movements (unusual volatility)
- Volume spikes
- On-chain metric outliers (TVL drops, whale movements)
- Funding rate extremes

Uses scikit-learn's IsolationForest when available, falls back to
Z-score based detection.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)

# Anomaly detection config
Z_SCORE_THRESHOLD = 2.5  # Standard deviations for Z-score fallback
ISOLATION_CONTAMINATION = 0.05  # Expected % of anomalies


def _get_recent_values(
    table: str,
    value_column: str,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    hours: int = 168,  # 7 days
    limit: int = 1000,
) -> list[dict]:
    """Fetch recent time-series values from a table."""
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []

        if USE_POSTGRES:
            conditions.append(f"ts > NOW() - INTERVAL '{hours} hours'")
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            conditions.append("ts > ?")
            params.append(cutoff)

        if filter_column and filter_value:
            conditions.append(f"{filter_column} = ?")
            params.append(filter_value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        cur.execute(
            f"SELECT ts, {value_column} as value FROM {table} {where} ORDER BY ts DESC LIMIT ?",
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def _zscore_anomalies(values: list[float], timestamps: list[str]) -> list[dict]:
    """Detect anomalies using Z-score method."""
    if len(values) < 10:
        return []

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance) if variance > 0 else 1.0

    anomalies = []
    for i, (v, ts) in enumerate(zip(values, timestamps)):
        z = (v - mean) / std if std > 0 else 0
        if abs(z) >= Z_SCORE_THRESHOLD:
            anomalies.append({
                "ts": ts,
                "value": v,
                "z_score": round(z, 3),
                "mean": round(mean, 4),
                "std": round(std, 4),
                "direction": "high" if z > 0 else "low",
                "method": "zscore",
            })

    return anomalies


def _isolation_forest_anomalies(values: list[float], timestamps: list[str]) -> list[dict]:
    """Detect anomalies using Isolation Forest."""
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return _zscore_anomalies(values, timestamps)

    if len(values) < 20:
        return _zscore_anomalies(values, timestamps)

    X = np.array(values).reshape(-1, 1)
    clf = IsolationForest(
        contamination=ISOLATION_CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    predictions = clf.fit_predict(X)
    scores = clf.decision_function(X)

    mean = float(np.mean(values))
    std = float(np.std(values))

    anomalies = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:  # Anomaly
            anomalies.append({
                "ts": timestamps[i],
                "value": values[i],
                "anomaly_score": round(float(score), 4),
                "z_score": round((values[i] - mean) / std, 3) if std > 0 else 0,
                "mean": round(mean, 4),
                "std": round(std, 4),
                "direction": "high" if values[i] > mean else "low",
                "method": "isolation_forest",
            })

    return anomalies


def detect_price_anomalies(
    symbol: str = "BTC/USDT",
    hours: int = 168,
) -> dict:
    """Detect anomalous price movements for a symbol."""
    rows = _get_recent_values(
        "price_ticks", "price",
        filter_column="symbol", filter_value=symbol,
        hours=hours,
    )

    if not rows:
        return {"symbol": symbol, "anomalies": [], "data_points": 0}

    values = [r["value"] for r in rows]
    timestamps = [r["ts"] for r in rows]

    # Compute returns (% changes) instead of raw prices for better anomaly detection
    returns = []
    return_ts = []
    for i in range(1, len(values)):
        if values[i - 1] != 0:
            ret = (values[i] - values[i - 1]) / values[i - 1] * 100
            returns.append(ret)
            return_ts.append(timestamps[i])

    anomalies = _isolation_forest_anomalies(returns, return_ts) if returns else []

    return {
        "symbol": symbol,
        "period_hours": hours,
        "data_points": len(values),
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def detect_volume_anomalies(hours: int = 168) -> dict:
    """Detect anomalous volume spikes across all tracked symbols."""
    rows = _get_recent_values("price_ticks", "volume_24h", hours=hours, limit=2000)

    if not rows:
        return {"anomalies": [], "data_points": 0}

    values = [r["value"] for r in rows if r["value"] is not None and r["value"] > 0]
    timestamps = [r["ts"] for r in rows if r["value"] is not None and r["value"] > 0]

    anomalies = _isolation_forest_anomalies(values, timestamps)

    return {
        "period_hours": hours,
        "data_points": len(values),
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def detect_metric_anomalies(
    metric_type: str = "funding_rate",
    hours: int = 168,
) -> dict:
    """Detect anomalies in market metrics (funding rates, OI, etc.)."""
    rows = _get_recent_values(
        "market_metrics", "value",
        filter_column="metric_type", filter_value=metric_type,
        hours=hours,
    )

    if not rows:
        return {"metric_type": metric_type, "anomalies": [], "data_points": 0}

    values = [r["value"] for r in rows]
    timestamps = [r["ts"] for r in rows]

    anomalies = _isolation_forest_anomalies(values, timestamps)

    return {
        "metric_type": metric_type,
        "period_hours": hours,
        "data_points": len(values),
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def detect_onchain_anomalies(
    metric_type: str = "tvl",
    hours: int = 168,
) -> dict:
    """Detect anomalies in on-chain metrics."""
    rows = _get_recent_values(
        "onchain_metrics", "value",
        filter_column="metric_type", filter_value=metric_type,
        hours=hours,
    )

    if not rows:
        return {"metric_type": metric_type, "anomalies": [], "data_points": 0}

    values = [r["value"] for r in rows]
    timestamps = [r["ts"] for r in rows]

    anomalies = _isolation_forest_anomalies(values, timestamps)

    return {
        "metric_type": metric_type,
        "period_hours": hours,
        "data_points": len(values),
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


def run_full_anomaly_scan() -> dict:
    """Run anomaly detection across all data sources."""
    results = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "price": detect_price_anomalies("BTC/USDT"),
        "volume": detect_volume_anomalies(),
        "funding_rate": detect_metric_anomalies("funding_rate"),
        "fear_greed": detect_metric_anomalies("fear_greed_index"),
        "tvl": detect_onchain_anomalies("tvl"),
    }

    total_anomalies = sum(
        r.get("anomaly_count", 0) for r in results.values() if isinstance(r, dict)
    )
    results["total_anomalies"] = total_anomalies

    return results
