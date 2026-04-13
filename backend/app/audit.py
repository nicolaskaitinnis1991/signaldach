"""Audit trail logging for SignalDACH.

All fund operations, auth events, and configuration changes are written
to an immutable append-only audit_log table.  Functions here are
fire-and-forget — failures are logged but never raise.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger(__name__)


def log_event(
    category: str,
    action: str,
    *,
    user_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> None:
    """Insert a single audit record.  Never raises."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO audit_log (ts, category, action, user_id, detail, ip_address, request_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    datetime.now(timezone.utc).isoformat(),
                    category,
                    action,
                    user_id,
                    json.dumps(detail or {}),
                    ip_address,
                    request_id,
                ],
            )
    except Exception as exc:
        logger.debug("Audit log write failed: %s", exc)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def log_auth(action: str, *, user_id: str | None = None, ip: str | None = None, **extra: object) -> None:
    log_event("auth", action, user_id=user_id, ip_address=ip, detail=dict(extra) if extra else None)


def log_signal(action: str, *, detail: dict | None = None) -> None:
    log_event("signal", action, detail=detail)


def log_risk(action: str, *, user_id: str | None = None, detail: dict | None = None) -> None:
    log_event("risk", action, user_id=user_id, detail=detail)


def log_fund(action: str, *, user_id: str | None = None, detail: dict | None = None) -> None:
    log_event("fund", action, user_id=user_id, detail=detail)


def log_config(action: str, *, user_id: str | None = None, detail: dict | None = None) -> None:
    log_event("config", action, user_id=user_id, detail=detail)


def log_system(action: str, *, detail: dict | None = None) -> None:
    log_event("system", action, detail=detail)
