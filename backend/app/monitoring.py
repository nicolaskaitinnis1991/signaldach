"""Monitoring endpoints: health check, Prometheus metrics, source status, structured logging."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# ---------------------------------------------------------------------------
# Structured JSON Logging
# ---------------------------------------------------------------------------

class StructuredFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        # Merge any extra fields attached via logger.info("msg", extra={...})
        for key in ("source_id", "source_name", "items_count", "duration_ms", "error"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


def setup_structured_logging(level: str = "INFO") -> None:
    """Replace the root logger handler with structured JSON output."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


# ---------------------------------------------------------------------------
# In-memory Metrics Counters (lightweight, no external deps)
# ---------------------------------------------------------------------------

class _Metrics:
    def __init__(self):
        self.startup_time: float = time.time()
        self.items_total: int = 0
        self.scrapes_total: int = 0
        self.scrape_errors_total: int = 0
        # source_id -> list of recent durations (keep last 100)
        self.scrape_durations: Dict[str, list[float]] = {}
        # HTTP request tracking
        self.http_requests_total: int = 0
        self.http_errors_total: int = 0  # 5xx only
        self.http_latency_sum_ms: float = 0.0
        self.http_latency_count: int = 0
        # Per-endpoint latency tracking (keep last 200 per path)
        self.endpoint_latencies: Dict[str, list[float]] = {}
        # WebSocket
        self.ws_connections_active: int = 0
        self.ws_connections_total: int = 0
        # Signals
        self.signals_generated: int = 0

    def record_scrape(self, source_id: str, duration_s: float, items_count: int, error: bool = False):
        self.scrapes_total += 1
        self.items_total += items_count
        if error:
            self.scrape_errors_total += 1
        durations = self.scrape_durations.setdefault(source_id, [])
        durations.append(duration_s)
        if len(durations) > 100:
            self.scrape_durations[source_id] = durations[-100:]

    def record_request(self, path: str, status_code: int, latency_ms: float):
        self.http_requests_total += 1
        if status_code >= 500:
            self.http_errors_total += 1
        self.http_latency_sum_ms += latency_ms
        self.http_latency_count += 1
        # Per-endpoint
        bucket = self.endpoint_latencies.setdefault(path, [])
        bucket.append(latency_ms)
        if len(bucket) > 200:
            self.endpoint_latencies[path] = bucket[-200:]


metrics = _Metrics()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check(request: Request):
    """Detailed health check: DB connectivity, scraper info, uptime, memory."""
    checks: Dict[str, Any] = {}

    # Database
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sources")
            source_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM items")
            item_count = cur.fetchone()[0]
        checks["database"] = {"status": "ok", "sources": source_count, "items": item_count}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # Uptime
    uptime_s = time.time() - metrics.startup_time
    checks["uptime"] = {
        "started_at": datetime.fromtimestamp(metrics.startup_time, tz=timezone.utc).isoformat(),
        "uptime_seconds": round(uptime_s, 1),
    }

    # Memory (basic, via /proc or os)
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        checks["memory"] = {"rss_mb": round(rusage.ru_maxrss / 1024, 1)}  # macOS gives bytes, Linux KB
    except Exception:
        checks["memory"] = {"status": "unavailable"}

    # Scraper stats
    checks["scrapers"] = {
        "total_scrapes": metrics.scrapes_total,
        "total_errors": metrics.scrape_errors_total,
        "total_items_ingested": metrics.items_total,
    }

    overall = "healthy" if checks["database"].get("status") == "ok" else "degraded"
    return JSONResponse({"status": overall, "checks": checks})


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible metrics in text exposition format."""
    lines = [
        "# HELP signaldach_items_total Total items ingested",
        "# TYPE signaldach_items_total counter",
        f"signaldach_items_total {metrics.items_total}",
        "",
        "# HELP signaldach_scrapes_total Total scrape runs",
        "# TYPE signaldach_scrapes_total counter",
        f"signaldach_scrapes_total {metrics.scrapes_total}",
        "",
        "# HELP signaldach_scrape_errors_total Total scrape errors",
        "# TYPE signaldach_scrape_errors_total counter",
        f"signaldach_scrape_errors_total {metrics.scrape_errors_total}",
        "",
        "# HELP signaldach_uptime_seconds Seconds since startup",
        "# TYPE signaldach_uptime_seconds gauge",
        f"signaldach_uptime_seconds {time.time() - metrics.startup_time:.1f}",
    ]

    # HTTP request metrics
    lines.extend([
        "",
        "# HELP signaldach_http_requests_total Total HTTP requests",
        "# TYPE signaldach_http_requests_total counter",
        f"signaldach_http_requests_total {metrics.http_requests_total}",
        "",
        "# HELP signaldach_http_errors_total Total 5xx errors",
        "# TYPE signaldach_http_errors_total counter",
        f"signaldach_http_errors_total {metrics.http_errors_total}",
        "",
        "# HELP signaldach_http_latency_avg_ms Average request latency (ms)",
        "# TYPE signaldach_http_latency_avg_ms gauge",
        f"signaldach_http_latency_avg_ms {(metrics.http_latency_sum_ms / max(metrics.http_latency_count, 1)):.1f}",
        "",
        "# HELP signaldach_ws_connections_active Active WebSocket connections",
        "# TYPE signaldach_ws_connections_active gauge",
        f"signaldach_ws_connections_active {metrics.ws_connections_active}",
        "",
        "# HELP signaldach_ws_connections_total Total WebSocket connections since start",
        "# TYPE signaldach_ws_connections_total counter",
        f"signaldach_ws_connections_total {metrics.ws_connections_total}",
        "",
        "# HELP signaldach_signals_generated_total Total AI signals generated",
        "# TYPE signaldach_signals_generated_total counter",
        f"signaldach_signals_generated_total {metrics.signals_generated}",
    ])

    # Per-source scrape durations (last value)
    if metrics.scrape_durations:
        lines.append("")
        lines.append("# HELP signaldach_scrape_duration_seconds Duration of last scrape per source")
        lines.append("# TYPE signaldach_scrape_duration_seconds gauge")
        for source_id, durations in metrics.scrape_durations.items():
            if durations:
                lines.append(
                    f'signaldach_scrape_duration_seconds{{source_id="{source_id}"}} {durations[-1]:.3f}'
                )

    # Per-endpoint p50/p95 latencies (top 10 by request count)
    if metrics.endpoint_latencies:
        lines.append("")
        lines.append("# HELP signaldach_endpoint_latency_p50_ms 50th percentile latency (ms)")
        lines.append("# TYPE signaldach_endpoint_latency_p50_ms gauge")
        top_endpoints = sorted(
            metrics.endpoint_latencies.items(),
            key=lambda kv: len(kv[1]),
            reverse=True,
        )[:10]
        for path, lats in top_endpoints:
            sorted_lats = sorted(lats)
            n = len(sorted_lats)
            p50 = sorted_lats[int(n * 0.5)] if n else 0
            p95 = sorted_lats[int(n * 0.95)] if n else 0
            safe_path = path.replace('"', '\\"')
            lines.append(f'signaldach_endpoint_latency_p50_ms{{path="{safe_path}"}} {p50:.1f}')
            lines.append(f'signaldach_endpoint_latency_p95_ms{{path="{safe_path}"}} {p95:.1f}')

    lines.append("")
    return "\n".join(lines)


@router.get("/sources/status")
async def sources_status():
    """Per-source health: last scrape, error rate, items count."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    s.id,
                    s.name,
                    s.type,
                    s.enabled,
                    s.last_scraped_at,
                    COALESCE(s.error_count, 0) AS error_count,
                    s.last_error,
                    s.last_error_at,
                    COUNT(i.id) AS items_count
                FROM sources s
                LEFT JOIN items i ON i.source_id = s.id
                GROUP BY s.id
                ORDER BY s.name
            """)
            rows = cur.fetchall()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    sources = []
    for row in rows:
        sources.append({
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "enabled": bool(row["enabled"]),
            "last_scraped_at": row["last_scraped_at"],
            "error_count": row["error_count"],
            "last_error": row["last_error"],
            "last_error_at": row["last_error_at"],
            "items_count": row["items_count"],
        })

    return {"sources": sources, "total": len(sources)}
