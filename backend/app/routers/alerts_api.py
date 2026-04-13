"""Alert configuration and manual scrape trigger endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------
ALLOWED_CONDITION_KEYS = {"category", "urgency", "keyword", "symbol", "min_relevance"}
ALLOWED_CHANNEL_KEYS = {"email", "webhook", "slack", "push"}


# ──────────────────────────────────────────────
#  Request / Response models
# ──────────────────────────────────────────────

class AlertConfigCreate(BaseModel):
    tenant_id: str = Field(default="default", max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    user_id: Optional[str] = None
    name: str = Field(..., max_length=200)
    enabled: bool = True
    conditions: dict = Field(default_factory=dict)
    channels: dict = Field(default_factory=dict)

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: dict) -> dict:
        if len(v) > 10:
            raise ValueError("Too many condition entries (max 10)")
        invalid_keys = set(v.keys()) - ALLOWED_CONDITION_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid condition keys: {invalid_keys}. "
                f"Allowed: {ALLOWED_CONDITION_KEYS}"
            )
        return v

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: dict) -> dict:
        if len(v) > 10:
            raise ValueError("Too many channel entries (max 10)")
        invalid_keys = set(v.keys()) - ALLOWED_CHANNEL_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid channel keys: {invalid_keys}. "
                f"Allowed: {ALLOWED_CHANNEL_KEYS}"
            )
        return v


class AlertConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    enabled: Optional[bool] = None
    conditions: Optional[dict] = None
    channels: Optional[dict] = None

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("Too many condition entries (max 10)")
        invalid_keys = set(v.keys()) - ALLOWED_CONDITION_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid condition keys: {invalid_keys}. "
                f"Allowed: {ALLOWED_CONDITION_KEYS}"
            )
        return v

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("Too many channel entries (max 10)")
        invalid_keys = set(v.keys()) - ALLOWED_CHANNEL_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid channel keys: {invalid_keys}. "
                f"Allowed: {ALLOWED_CHANNEL_KEYS}"
            )
        return v


# ──────────────────────────────────────────────
#  Alert config CRUD
# ──────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    tenant_id: str = Query(default="default", max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"),
):
    """List all alert configurations for a tenant."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM alert_configs WHERE tenant_id = ? ORDER BY created_at DESC",
            [tenant_id],
        )
        rows = [dict(row) for row in cur.fetchall()]

    # Parse JSON fields
    for row in rows:
        for field in ("conditions", "channels"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass

    return {"alerts": rows}


@router.post("/alerts", status_code=201)
async def create_alert(config: AlertConfigCreate):
    """Create a new alert configuration."""
    alert_id = uuid.uuid4().hex[:12]

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO alert_configs (id, tenant_id, user_id, name, enabled, conditions, channels)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                alert_id,
                config.tenant_id,
                config.user_id,
                config.name,
                1 if config.enabled else 0,
                json.dumps(config.conditions),
                json.dumps(config.channels),
            ],
        )

    return {"id": alert_id, "status": "created"}


@router.put("/alerts/{alert_id}")
async def update_alert(alert_id: str, update: AlertConfigUpdate):
    """Update an existing alert configuration."""
    with get_db() as conn:
        cur = conn.cursor()

        # Check existence
        cur.execute("SELECT id FROM alert_configs WHERE id = ?", [alert_id])
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alert config not found")

        # Build dynamic update
        fields = []
        params = []

        if update.name is not None:
            fields.append("name = ?")
            params.append(update.name)
        if update.enabled is not None:
            fields.append("enabled = ?")
            params.append(1 if update.enabled else 0)
        if update.conditions is not None:
            fields.append("conditions = ?")
            params.append(json.dumps(update.conditions))
        if update.channels is not None:
            fields.append("channels = ?")
            params.append(json.dumps(update.channels))

        if not fields:
            return {"status": "no changes"}

        fields.append("updated_at = datetime('now')")
        params.append(alert_id)

        query = f"UPDATE alert_configs SET {', '.join(fields)} WHERE id = ?"
        cur.execute(query, params)

    return {"id": alert_id, "status": "updated"}


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert configuration and its history."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM alert_configs WHERE id = ?", [alert_id])
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alert config not found")

        # Delete history first (FK constraint)
        cur.execute("DELETE FROM alert_history WHERE alert_config_id = ?", [alert_id])
        cur.execute("DELETE FROM alert_configs WHERE id = ?", [alert_id])

    return {"id": alert_id, "status": "deleted"}


@router.get("/alerts/{alert_id}/history")
async def alert_history(alert_id: str, limit: int = 50):
    """Get dispatch history for a specific alert config."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM alert_configs WHERE id = ?", [alert_id])
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alert config not found")

        cur.execute(
            """SELECT ah.*, i.title as item_title, i.url as item_url
               FROM alert_history ah
               LEFT JOIN items i ON ah.item_id = i.id
               WHERE ah.alert_config_id = ?
               ORDER BY ah.sent_at DESC
               LIMIT ?""",
            [alert_id, limit],
        )
        rows = [dict(row) for row in cur.fetchall()]

    return {"history": rows}


# ──────────────────────────────────────────────
#  Manual scrape trigger
# ──────────────────────────────────────────────

@router.post("/scrape/trigger")
async def trigger_scrape(
    tenant_id: str = Query(default="default", max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"),
):
    """Manually trigger a scrape of all enabled sources.

    Runs asynchronously in the background via the scheduler's job runner.
    """
    from app.scheduler.cron import run_scraper_job

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name FROM sources WHERE tenant_id = ? AND enabled = 1",
            [tenant_id],
        )
        sources = [dict(row) for row in cur.fetchall()]

    if not sources:
        return {"status": "no_sources", "message": "No enabled sources found"}

    # Run all scraper jobs
    results = []
    for source in sources:
        try:
            await run_scraper_job(source["id"])
            results.append({"source": source["name"], "status": "ok"})
        except Exception as e:
            logger.error(f"Manual scrape failed for {source['name']}: {e}")
            results.append({"source": source["name"], "status": "error", "error": str(e)})

    return {
        "status": "completed",
        "sources_scraped": len(results),
        "results": results,
    }
