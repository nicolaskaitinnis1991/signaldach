from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.database import get_db

router = APIRouter(prefix="/items", tags=["items"])


@router.get("")
async def list_items(
    tenant_id: str = Query(default="default", max_length=100),
    category: Optional[str] = Query(default=None, pattern="^(regulation|competition|market|sentiment)$"),
    urgency: Optional[str] = Query(default=None, pattern="^(normal|high|breaking)$"),
    q: Optional[str] = Query(default=None, max_length=200),
    sort: Optional[str] = Query(default="newest", pattern="^(newest|relevance|urgency)$"),
    lang: Optional[str] = Query(default=None, pattern="^(en|de|fr|es)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with get_db() as conn:
        cur = conn.cursor()
        query = "SELECT * FROM items WHERE tenant_id = ?"
        params: List = [tenant_id]

        if category:
            query += " AND category = ?"
            params.append(category)
        if urgency:
            query += " AND urgency = ?"
            params.append(urgency)
        if q:
            query += " AND (title LIKE ? OR summary LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])

        # Sort order
        sort_clauses = {
            "newest": "published_at DESC",
            "relevance": "relevance_score DESC, published_at DESC",
            "urgency": "CASE urgency WHEN 'breaking' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, published_at DESC",
        }
        order_by = sort_clauses.get(sort or "newest", "published_at DESC")
        query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]

        # Get total count for pagination
        count_query = "SELECT COUNT(*) as total FROM items WHERE tenant_id = ?"
        count_params: List = [tenant_id]
        if category:
            count_query += " AND category = ?"
            count_params.append(category)
        if urgency:
            count_query += " AND urgency = ?"
            count_params.append(urgency)
        if q:
            count_query += " AND (title LIKE ? OR summary LIKE ?)"
            count_params.extend([f"%{q}%", f"%{q}%"])
        cur.execute(count_query, count_params)
        total = cur.fetchone()["total"]

    # Translate title + summary if lang is set and not English
    if lang and lang != "en":
        try:
            from app.ai.translator import translate_items_batch
            rows = await translate_items_batch(rows, lang)
        except Exception:
            pass  # Return originals on failure

    return {"items": rows, "count": len(rows), "total": total}


@router.get("/{item_id}")
async def get_item(item_id: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM items WHERE id = ?", [item_id])
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return dict(row)
