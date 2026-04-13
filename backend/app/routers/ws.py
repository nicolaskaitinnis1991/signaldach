"""WebSocket endpoint for real-time feed updates.

Connected clients at /ws/feed receive new items as they are scraped.
Uses Redis Pub/Sub for cross-worker broadcast (falls back to local-only).
Requires authentication via query parameter ?token=<jwt> or first message auth.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Active WebSocket connections on THIS worker
_connections: Set[WebSocket] = set()

# Redis Pub/Sub channel for cross-worker broadcast
_WS_CHANNEL = "ws:broadcast"

# Background task handle for the subscriber
_subscriber_task: asyncio.Task | None = None


async def _redis_subscriber():
    """Background task: listen on Redis Pub/Sub and forward to local WS clients."""
    try:
        from app.redis_client import is_redis_available, subscribe

        if not is_redis_available():
            logger.debug("Redis unavailable, WS subscriber not started")
            return

        async for message in subscribe(_WS_CHANNEL):
            if not _connections:
                continue
            disconnected: list[WebSocket] = []
            for ws in list(_connections):
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
                    try:
                        await ws.close()
                    except Exception:
                        pass
            for ws in disconnected:
                _connections.discard(ws)
            if disconnected:
                logger.info("Cleaned up %d dead WebSocket connections", len(disconnected))
    except asyncio.CancelledError:
        return
    except Exception as e:
        logger.warning("Redis WS subscriber error: %s", e)


def start_ws_subscriber():
    """Start the Redis Pub/Sub subscriber task. Call during app startup."""
    global _subscriber_task
    if _subscriber_task is None or _subscriber_task.done():
        _subscriber_task = asyncio.create_task(_redis_subscriber())
        logger.info("WebSocket Redis subscriber started")


def stop_ws_subscriber():
    """Cancel the subscriber task. Call during app shutdown."""
    global _subscriber_task
    if _subscriber_task and not _subscriber_task.done():
        _subscriber_task.cancel()
        _subscriber_task = None


def _authenticate_ws(token: Optional[str]) -> Optional[dict]:
    """Validate JWT token for WebSocket connection. Returns user dict or None."""
    if not token:
        return None
    try:
        from app.auth import verify_token, get_user_by_id
        payload = verify_token(token, expected_type="access")
        return get_user_by_id(payload["sub"])
    except Exception:
        return None


@router.websocket("/ws/feed")
async def ws_feed(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint that streams new items to connected clients.

    Authentication: pass ?token=<jwt> query parameter.
    When auth is disabled (dev mode), connections are accepted without token.
    """
    from app.config import settings

    # Authenticate before accepting the connection
    if settings.auth_enabled:
        user = _authenticate_ws(token)
        if user is None:
            await websocket.close(code=4001, reason="Authentication required")
            return
        logger.info("WebSocket authenticated: user=%s role=%s", user["email"], user["role"])
    else:
        user = None

    await websocket.accept()
    _connections.add(websocket)
    logger.info("WebSocket client connected. Total: %d", len(_connections))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except (json.JSONDecodeError, TypeError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(_connections))


async def broadcast_new_items(items: list[dict]):
    """Broadcast newly scraped items to all connected WebSocket clients.

    Publishes to Redis Pub/Sub so all workers receive the broadcast.
    Falls back to local-only delivery if Redis is unavailable.
    """
    if not items:
        return

    payload = json.dumps({
        "type": "new_items",
        "count": len(items),
        "items": items,
    })

    # Try Redis Pub/Sub first (reaches all workers)
    try:
        from app.redis_client import is_redis_available, publish

        if is_redis_available():
            subscribers = await publish(_WS_CHANNEL, payload)
            logger.info(
                "Broadcast %d items via Redis Pub/Sub (%d subscribers)", len(items), subscribers
            )
            return
    except Exception as e:
        logger.debug("Redis publish failed, falling back to local: %s", e)

    # Fallback: local-only broadcast
    if not _connections:
        return

    disconnected: list[WebSocket] = []
    for ws in list(_connections):
        try:
            await ws.send_text(payload)
        except Exception as e:
            logger.warning("WebSocket send failed, removing dead connection: %s", e)
            disconnected.append(ws)
            try:
                await ws.close()
            except Exception:
                pass

    for ws in disconnected:
        _connections.discard(ws)
    if disconnected:
        logger.info("Cleaned up %d dead WebSocket connections", len(disconnected))
    logger.info("Broadcast %d items to %d local clients", len(items), len(_connections))
