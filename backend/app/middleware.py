"""
Security middleware for SignalDACH.

Provides:
- Rate limiting (per-IP, separate limits for auth endpoints)
  -> Redis-backed sliding window (falls back to in-memory if Redis unavailable)
- Request ID tracking (X-Request-ID header)
- Security headers (X-Content-Type-Options, X-Frame-Options, HSTS)
- Request logging with timing
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory rate limiter (fallback when Redis is unavailable)
# ---------------------------------------------------------------------------
class _RateLimitStore:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        bucket = self._requests[key]

        # Prune expired entries
        cutoff = now - window_seconds
        self._requests[key] = [t for t in bucket if t > cutoff]
        bucket = self._requests[key]

        if len(bucket) >= limit:
            return False

        bucket.append(now)
        return True

    def cleanup(self, max_age: float = 300.0) -> None:
        """Remove keys with no recent activity to prevent memory growth."""
        now = time.monotonic()
        stale = [k for k, v in self._requests.items() if not v or v[-1] < now - max_age]
        for k in stale:
            del self._requests[k]


_rate_store = _RateLimitStore()
_cleanup_counter = 0


async def _check_rate_limit(rate_key: str, limit: int, window_seconds: int = 60) -> bool:
    """Check rate limit, preferring Redis, falling back to in-memory.

    Returns True if the request is allowed.
    """
    try:
        from app.redis_client import is_redis_available, rate_limit_check
        if is_redis_available():
            redis_key = f"rl:{rate_key}"
            return await rate_limit_check(redis_key, limit, window_seconds)
    except Exception:
        pass

    # Fallback to in-memory
    return _rate_store.is_allowed(rate_key, limit, window_seconds)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
class SecurityMiddleware(BaseHTTPMiddleware):
    """Combined security middleware for SignalDACH."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        global _cleanup_counter
        start = time.perf_counter()

        # --- Request ID ---
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # --- Client IP (trusted proxy validation) ---
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Only trust X-Forwarded-For if the direct connection comes from a trusted proxy
            direct_ip = request.client.host if request.client else ""
            trusted = set(settings.trusted_proxy_ips)
            if direct_ip in trusted:
                client_ip = forwarded.split(",")[0].strip()
            else:
                logger.debug(
                    "Ignoring X-Forwarded-For from untrusted source %s", direct_ip
                )

        # --- Rate limiting ---
        path = request.url.path
        is_auth_endpoint = path.startswith("/auth/")

        if is_auth_endpoint:
            limit = settings.rate_limit_auth_per_minute
            rate_key = f"auth:{client_ip}"
        else:
            limit = settings.rate_limit_per_minute
            rate_key = f"api:{client_ip}"

        allowed = await _check_rate_limit(rate_key, limit, window_seconds=60)
        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s [%s]", client_ip, path, request_id)
            import json
            return Response(
                content=json.dumps({
                    "error_code": "RATE_LIMITED",
                    "message": "Rate limit exceeded. Try again later.",
                    "retryable": True,
                    "path": path,
                }),
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-Request-ID": request_id,
                },
            )

        # --- Per-user rate limiting (for authenticated requests) ---
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt as _jwt
                token = auth_header.split(" ", 1)[1]
                # Decode without full verification for rate-limit keying only
                payload = _jwt.decode(
                    token,
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_exp": False},
                )
                user_id = payload.get("sub", "")
                if user_id:
                    user_rate_key = f"user:{user_id}"
                    user_allowed = await _check_rate_limit(
                        user_rate_key, settings.rate_limit_user_per_minute, 60
                    )
                    if not user_allowed:
                        import json
                        logger.warning(
                            "Per-user rate limit exceeded for user=%s on %s [%s]",
                            user_id, path, request_id,
                        )
                        return Response(
                            content=json.dumps({
                                "error_code": "RATE_LIMITED",
                                "message": "Per-user rate limit exceeded. Try again later.",
                                "retryable": True,
                                "path": path,
                            }),
                            status_code=429,
                            media_type="application/json",
                            headers={
                                "Retry-After": "60",
                                "X-Request-ID": request_id,
                            },
                        )
            except Exception:
                pass  # Token invalid or missing jwt — skip per-user limiting

        # Periodic cleanup of stale in-memory rate-limit entries
        _cleanup_counter += 1
        if _cleanup_counter % 1000 == 0:
            _rate_store.cleanup()

        # --- Process request ---
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error processing %s %s", request.method, path)
            raise

        # --- Timing + Metrics ---
        elapsed_ms = (time.perf_counter() - start) * 1000
        try:
            from app.monitoring import metrics as app_metrics
            app_metrics.record_request(path, response.status_code, elapsed_ms)
        except Exception:
            pass

        # --- Security headers ---
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://api.binance.com https://api.coingecko.com https://api.alternative.me https://api.llama.fi; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"

        # --- Request logging ---
        logger.info(
            "%s %s %s %s %.1fms [%s]",
            client_ip,
            request.method,
            path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response
