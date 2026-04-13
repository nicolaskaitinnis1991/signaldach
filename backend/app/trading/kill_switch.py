"""Kill Switch -- Emergency trading halt mechanism.

Provides instant ability to:
- Halt all trading activity
- Cancel all pending paper orders
- Freeze position changes
- Log the kill switch activation to audit trail

The kill switch state is stored in-memory and optionally in Redis for cross-worker sync.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class KillSwitchState:
    active: bool = False
    activated_at: Optional[str] = None
    activated_by: Optional[str] = None
    reason: str = ""


# Global state -- protected by a lock for thread safety
_state = KillSwitchState()
_lock = threading.Lock()
_kill_switch_history: list[dict] = []

REDIS_KEY = "signaldach:kill_switch"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def activate_kill_switch(user_id: str, reason: str = "Manual activation") -> KillSwitchState:
    """Activate the kill switch -- halt all trading immediately.

    1. Sets state to active
    2. Cancels all pending paper orders
    3. Logs to audit trail
    4. Syncs to Redis for cross-worker awareness
    """
    global _state

    now = datetime.now(timezone.utc).isoformat()

    with _lock:
        _state = KillSwitchState(
            active=True,
            activated_at=now,
            activated_by=user_id,
            reason=reason,
        )

        _kill_switch_history.append({
            "action": "activated",
            "user_id": user_id,
            "reason": reason,
            "timestamp": now,
        })

    # Cancel all pending paper orders
    _cancel_all_pending_orders()

    # Audit trail
    try:
        from app.audit import log_risk
        log_risk("kill_switch_activated", user_id=user_id, detail={
            "reason": reason,
            "timestamp": now,
        })
    except Exception as exc:
        logger.debug("Audit log for kill switch activation failed: %s", exc)

    # Sync to Redis
    _sync_to_redis()

    logger.warning("KILL SWITCH ACTIVATED by %s: %s", user_id, reason)

    return KillSwitchState(
        active=_state.active,
        activated_at=_state.activated_at,
        activated_by=_state.activated_by,
        reason=_state.reason,
    )


def deactivate_kill_switch(user_id: str) -> KillSwitchState:
    """Deactivate the kill switch -- resume trading."""
    global _state

    now = datetime.now(timezone.utc).isoformat()

    with _lock:
        was_active = _state.active
        _state = KillSwitchState(active=False)

        _kill_switch_history.append({
            "action": "deactivated",
            "user_id": user_id,
            "timestamp": now,
            "was_active": was_active,
        })

    # Audit trail
    try:
        from app.audit import log_risk
        log_risk("kill_switch_deactivated", user_id=user_id, detail={
            "timestamp": now,
            "was_active": was_active,
        })
    except Exception as exc:
        logger.debug("Audit log for kill switch deactivation failed: %s", exc)

    # Sync to Redis
    _sync_to_redis()

    logger.info("Kill switch deactivated by %s", user_id)

    return KillSwitchState(active=False)


def is_kill_switch_active() -> bool:
    """Check if the kill switch is currently active."""
    with _lock:
        return _state.active


def get_kill_switch_status() -> dict:
    """Get full kill switch status including history."""
    with _lock:
        return {
            "active": _state.active,
            "activated_at": _state.activated_at,
            "activated_by": _state.activated_by,
            "reason": _state.reason,
            "history": list(_kill_switch_history),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cancel_all_pending_orders() -> None:
    """Cancel all pending paper trading orders."""
    try:
        from app.trading.paper_engine import get_paper_portfolio

        portfolio = get_paper_portfolio()
        cancelled_count = 0
        with portfolio._lock:
            for order in portfolio._order_history:
                if order.status.value == "pending":
                    from app.trading.paper_engine import OrderStatus
                    order.status = OrderStatus.CANCELLED
                    order.reason = "Kill switch activated"
                    cancelled_count += 1

        if cancelled_count > 0:
            logger.info("Kill switch cancelled %d pending orders", cancelled_count)

    except Exception as exc:
        logger.warning("Failed to cancel pending orders during kill switch: %s", exc)


def _sync_to_redis() -> None:
    """Try to sync kill switch state to Redis for cross-worker awareness."""
    try:
        from app.redis_client import is_redis_available

        if not is_redis_available():
            return

        import asyncio

        async def _do_sync():
            from app.redis_client import cache_set

            with _lock:
                state_json = json.dumps({
                    "active": _state.active,
                    "activated_at": _state.activated_at,
                    "activated_by": _state.activated_by,
                    "reason": _state.reason,
                })
            await cache_set(REDIS_KEY, state_json, ttl=86400)  # 24h TTL

        # Try to run in existing event loop, otherwise skip
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_do_sync())
        except RuntimeError:
            # No running event loop -- skip Redis sync
            pass

    except Exception as exc:
        logger.debug("Redis sync for kill switch failed: %s", exc)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _reset_kill_switch() -> None:
    """Reset kill switch state. Used by tests."""
    global _state
    with _lock:
        _state = KillSwitchState()
        _kill_switch_history.clear()
