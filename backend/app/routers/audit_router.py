"""Audit Log API — read-only access to the immutable audit trail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user, require_role
from app.database import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs", dependencies=[Depends(require_role("admin"))])
async def get_audit_logs(
    category: str = Query("", max_length=30, description="Filter by category (auth, signal, risk, fund, config, system)"),
    action: str = Query("", max_length=100, description="Filter by action"),
    user_id: str = Query("", max_length=100, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Query audit logs. Admin-only. Results ordered newest-first."""
    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if action:
        conditions.append("action = ?")
        params.append(action)
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # Total count
            cur.execute(f"SELECT COUNT(*) FROM audit_log {where}", params)
            row = cur.fetchone()
            total = row[0] if isinstance(row, (tuple, list)) else row["COUNT(*)"] if isinstance(row, dict) else 0

            # Results
            cur.execute(
                f"SELECT id, ts, category, action, user_id, detail, ip_address, request_id "
                f"FROM audit_log {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            )
            rows = cur.fetchall()
    except Exception:
        # Table may not exist yet (pre-migration)
        return {"logs": [], "total": 0, "limit": limit, "offset": offset}

    logs = []
    for r in rows:
        if isinstance(r, dict):
            logs.append(r)
        else:
            logs.append({
                "id": r[0], "ts": r[1], "category": r[2], "action": r[3],
                "user_id": r[4], "detail": r[5], "ip_address": r[6], "request_id": r[7],
            })

    return {"logs": logs, "total": total, "limit": limit, "offset": offset}


@router.get("/summary", dependencies=[Depends(require_role("admin"))])
async def audit_summary():
    """Quick summary of audit activity (last 24h)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT category, COUNT(*) as cnt FROM audit_log "
                "WHERE ts >= datetime('now', '-1 day') GROUP BY category ORDER BY cnt DESC"
            )
            rows = cur.fetchall()
    except Exception:
        return {"period": "24h", "by_category": {}}

    categories = {}
    for r in rows:
        if isinstance(r, dict):
            categories[r["category"]] = r["cnt"]
        else:
            categories[r[0]] = r[1]

    return {"period": "24h", "by_category": categories}
