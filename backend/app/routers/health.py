"""Health check endpoints — liveness, readiness, and startup probes."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_startup_time = time.time()


@router.get("/health")
async def health_check():
    """Basic liveness probe — is the process running?"""
    return {"status": "ok", "service": "signal-dach"}


@router.get("/health/live")
async def liveness():
    """Liveness probe — process is alive and responding."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """Readiness probe — all critical dependencies connected."""
    checks = {}

    # Database
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis
    try:
        from app.redis_client import is_redis_available
        checks["redis"] = "ok" if is_redis_available() else "unavailable"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "uptime_seconds": round(time.time() - _startup_time, 1),
    }


@router.get("/health/startup")
async def startup_probe():
    """Startup probe — application initialized, scheduler running."""
    checks = {}

    # Database initialized
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sources")
            count = cur.fetchone()[0]
        checks["database"] = "ok"
        checks["sources_count"] = count
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Scheduler running
    try:
        from app.scheduler.cron import _scheduler
        if _scheduler and _scheduler.running:
            checks["scheduler"] = "running"
            checks["scheduled_jobs"] = len(_scheduler.get_jobs())
        else:
            checks["scheduler"] = "not_running"
    except Exception:
        checks["scheduler"] = "unknown"

    # Uptime
    checks["uptime_seconds"] = round(time.time() - _startup_time, 1)

    return {
        "status": "started" if checks.get("database") == "ok" else "starting",
        "checks": checks,
    }


@router.get("/health/cache")
async def cache_stats():
    """Redis cache statistics — key count and memory usage."""
    try:
        from app.redis_client import is_redis_available, get_redis
        if not is_redis_available():
            return {"status": "unavailable", "message": "Redis not connected"}
        redis = await get_redis()
        if redis is None:
            return {"status": "unavailable", "message": "Redis not connected"}
        info = await redis.info("memory")
        key_count = 0
        async for _ in redis.scan_iter("cache:*"):
            key_count += 1
        return {
            "status": "ok",
            "cached_keys": key_count,
            "memory_used": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/health/env")
async def env_status():
    """Environment validation status (admin only in production)."""
    from app.env_validation import validate_environment
    result = validate_environment()
    # Redact actual values for security
    return {
        "environment": result["environment"],
        "valid": result["valid"],
        "warnings_count": len(result["warnings"]),
        "warnings": result["warnings"],
    }
