"""Circuit breaker, retry logic, and global exception handling for SignalDACH.

Circuit breaker state is stored in Redis when available, with in-memory fallback.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Error Codes
# ---------------------------------------------------------------------------

class ErrorCode:
    """Taxonomy of error codes. Clients use `retryable` to decide retry vs. fail."""

    # Auth / Access
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_INSUFFICIENT_ROLE = "AUTH_INSUFFICIENT_ROLE"
    AUTH_ACCOUNT_LOCKED = "AUTH_ACCOUNT_LOCKED"

    # Rate Limiting
    RATE_LIMITED = "RATE_LIMITED"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # Scrapers / Collectors
    SCRAPER_CIRCUIT_OPEN = "SCRAPER_CIRCUIT_OPEN"
    SCRAPER_TIMEOUT = "SCRAPER_TIMEOUT"
    SCRAPER_PARSE_ERROR = "SCRAPER_PARSE_ERROR"
    COLLECTOR_UNAVAILABLE = "COLLECTOR_UNAVAILABLE"

    # AI / Signals
    SIGNAL_TIMEOUT = "SIGNAL_TIMEOUT"
    SIGNAL_NO_DATA = "SIGNAL_NO_DATA"
    AI_PROVIDER_ERROR = "AI_PROVIDER_ERROR"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"

    # Fund / Trading
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    POSITION_REJECTED = "POSITION_REJECTED"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"

    # Infrastructure
    DATABASE_ERROR = "DATABASE_ERROR"
    REDIS_UNAVAILABLE = "REDIS_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


# Map error codes to whether the client should retry
_RETRYABLE = {
    ErrorCode.RATE_LIMITED,
    ErrorCode.SCRAPER_TIMEOUT,
    ErrorCode.COLLECTOR_UNAVAILABLE,
    ErrorCode.SIGNAL_TIMEOUT,
    ErrorCode.AI_PROVIDER_ERROR,
    ErrorCode.DATABASE_ERROR,
    ErrorCode.REDIS_UNAVAILABLE,
    ErrorCode.INTERNAL_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE,
}


def error_response(
    status_code: int,
    error_code: str,
    message: str,
    path: str = "",
    details: dict | None = None,
) -> JSONResponse:
    """Build a structured JSON error response."""
    body: dict = {
        "error_code": error_code,
        "message": message,
        "retryable": error_code in _RETRYABLE,
    }
    if path:
        body["path"] = path
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState:
    CLOSED = "closed"          # normal operation
    OPEN = "open"              # too many failures, rejecting calls
    HALF_OPEN = "half_open"    # testing if service recovered


class CircuitBreaker:
    """Per-source circuit breaker with Redis-backed state (in-memory fallback).

    - Opens after `failure_threshold` consecutive failures.
    - Stays open for `recovery_timeout` seconds, then moves to half-open.
    - A single success in half-open resets to closed.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        # In-memory fallback state
        self._states: Dict[str, dict] = {}

    def _get_local(self, source_id: str) -> dict:
        """Get or create in-memory state for a source."""
        if source_id not in self._states:
            self._states[source_id] = {
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "last_failure_time": 0.0,
            }
        return self._states[source_id]

    async def _get_state_dict(self, source_id: str) -> dict:
        """Get state from Redis if available, otherwise in-memory."""
        try:
            from app.redis_client import is_redis_available, cb_get_state
            if is_redis_available():
                redis_state = await cb_get_state(source_id)
                if redis_state is not None:
                    return redis_state
                # Not in Redis yet, return default
                return {
                    "state": CircuitState.CLOSED,
                    "failure_count": 0,
                    "last_failure_time": 0.0,
                }
        except Exception:
            pass
        return self._get_local(source_id)

    async def _set_state_dict(self, source_id: str, info: dict) -> None:
        """Persist state to Redis if available, always update in-memory."""
        # Always update local state
        self._states[source_id] = info.copy()

        try:
            from app.redis_client import is_redis_available, cb_set_state
            if is_redis_available():
                await cb_set_state(
                    source_id,
                    info["state"],
                    info["failure_count"],
                    info["last_failure_time"],
                )
        except Exception:
            pass

    # Synchronous API (kept for backward compatibility with existing callers)
    def _get(self, source_id: str) -> dict:
        return self._get_local(source_id)

    def state(self, source_id: str) -> str:
        info = self._get(source_id)
        if info["state"] == CircuitState.OPEN:
            elapsed = time.monotonic() - info["last_failure_time"]
            if elapsed >= self.recovery_timeout:
                info["state"] = CircuitState.HALF_OPEN
                logger.info(f"Circuit half-open for source {source_id}")
        return info["state"]

    def allow_request(self, source_id: str) -> bool:
        st = self.state(source_id)
        return st in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self, source_id: str) -> None:
        info = self._get(source_id)
        info["state"] = CircuitState.CLOSED
        info["failure_count"] = 0
        logger.debug(f"Circuit closed for source {source_id}")

    def record_failure(self, source_id: str) -> None:
        info = self._get(source_id)
        info["failure_count"] += 1
        info["last_failure_time"] = time.monotonic()
        if info["failure_count"] >= self.failure_threshold:
            info["state"] = CircuitState.OPEN
            logger.warning(
                f"Circuit OPEN for source {source_id} after "
                f"{info['failure_count']} consecutive failures"
            )

    def reset(self, source_id: str) -> None:
        self._states.pop(source_id, None)

    # Async API (preferred for new code)
    async def async_state(self, source_id: str) -> str:
        info = await self._get_state_dict(source_id)
        if info["state"] == CircuitState.OPEN:
            elapsed = time.monotonic() - info["last_failure_time"]
            if elapsed >= self.recovery_timeout:
                info["state"] = CircuitState.HALF_OPEN
                await self._set_state_dict(source_id, info)
                logger.info(f"Circuit half-open for source {source_id}")
        return info["state"]

    async def async_allow_request(self, source_id: str) -> bool:
        st = await self.async_state(source_id)
        return st in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    async def async_record_success(self, source_id: str) -> None:
        info = await self._get_state_dict(source_id)
        info["state"] = CircuitState.CLOSED
        info["failure_count"] = 0
        await self._set_state_dict(source_id, info)
        logger.debug(f"Circuit closed for source {source_id}")

    async def async_record_failure(self, source_id: str) -> None:
        info = await self._get_state_dict(source_id)
        info["failure_count"] += 1
        info["last_failure_time"] = time.monotonic()
        if info["failure_count"] >= self.failure_threshold:
            info["state"] = CircuitState.OPEN
            logger.warning(
                f"Circuit OPEN for source {source_id} after "
                f"{info['failure_count']} consecutive failures"
            )
        await self._set_state_dict(source_id, info)

    async def async_reset(self, source_id: str) -> None:
        self._states.pop(source_id, None)
        try:
            from app.redis_client import is_redis_available, cb_delete
            if is_redis_available():
                await cb_delete(source_id)
        except Exception:
            pass


# Singleton instance used across the app
circuit_breaker = CircuitBreaker()


# ---------------------------------------------------------------------------
# Retry with Exponential Backoff
# ---------------------------------------------------------------------------

class RetryWithBackoff:
    """Retry an async callable with exponential backoff.

    Default: 3 attempts, delays 1s -> 2s -> 4s.
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 16.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, func: Callable, *args, **kwargs):
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                    logger.warning(
                        f"Attempt {attempt}/{self.max_retries} failed: {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} attempts failed: {exc}")
        raise last_exc  # type: ignore[misc]


retry = RetryWithBackoff()


# ---------------------------------------------------------------------------
# Scraper Error Tracking (persisted to DB)
# ---------------------------------------------------------------------------

def record_scraper_error(source_id: str, error_msg: str) -> None:
    """Increment error_count and store last_error for a source."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE sources
                   SET error_count = COALESCE(error_count, 0) + 1,
                       last_error = ?,
                       last_error_at = ?
                   WHERE id = ?""",
                [error_msg[:500], datetime.now(timezone.utc).isoformat(), source_id],
            )
    except Exception as e:
        logger.debug(f"Could not record scraper error: {e}")


def clear_scraper_error(source_id: str) -> None:
    """Reset error tracking on success."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """UPDATE sources
                   SET error_count = 0,
                       last_error = NULL,
                       last_error_at = NULL
                   WHERE id = ?""",
                [source_id],
            )
    except Exception as e:
        logger.debug(f"Could not clear scraper error: {e}")


# ---------------------------------------------------------------------------
# Global FastAPI Exception Handler
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register catch-all exception handlers on the FastAPI app."""

    from fastapi.exceptions import RequestValidationError

    def _get_request_id(request: Request) -> str:
        return getattr(request.state, "request_id", "") if hasattr(request, "state") else ""

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        rid = _get_request_id(request)
        logger.warning("Validation error on %s %s [%s]: %s", request.method, request.url.path, rid, exc.errors())
        # Sanitize errors: pydantic ctx may contain non-serializable objects
        safe_errors = []
        for err in exc.errors():
            safe_err = {k: v for k, v in err.items() if k != "ctx"}
            if "ctx" in err and err["ctx"]:
                safe_err["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
            safe_errors.append(safe_err)
        resp = error_response(
            422,
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            path=str(request.url.path),
            details={"errors": safe_errors},
        )
        if rid:
            resp.headers["X-Request-ID"] = rid
        return resp

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        rid = _get_request_id(request)
        logger.error("Unhandled exception on %s %s [%s]: %s", request.method, request.url.path, rid, exc, exc_info=True)
        resp = error_response(
            500,
            ErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred. Please try again later.",
            path=str(request.url.path),
        )
        if rid:
            resp.headers["X-Request-ID"] = rid
        return resp

    @app.exception_handler(404)
    async def _not_found_handler(request: Request, exc):
        rid = _get_request_id(request)
        resp = error_response(
            404,
            ErrorCode.NOT_FOUND,
            f"Route {request.url.path} not found.",
            path=str(request.url.path),
        )
        if rid:
            resp.headers["X-Request-ID"] = rid
        return resp
