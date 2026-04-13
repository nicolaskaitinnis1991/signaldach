"""BaFin/FINMA scam and warning monitor — surfaces regulatory warnings from the items database."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Query

from app.database import get_db

router = APIRouter(prefix="/scam-monitor", tags=["scam-monitor"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WARNING_KEYWORDS_SQL = (
    "(title LIKE '%warn%' OR title LIKE '%unauthorized%' OR title LIKE '%fraud%'"
    " OR title LIKE '%scam%' OR title LIKE '%Warnung%' OR title LIKE '%unerlaubt%'"
    " OR title LIKE '%Betrug%' OR title LIKE '%suspend%' OR title LIKE '%prohibit%'"
    " OR title LIKE '%verboten%' OR title LIKE '%Untersagung%'"
    " OR title LIKE '%blacklist%' OR title LIKE '%investigation%'"
    " OR summary LIKE '%warn%' OR summary LIKE '%unauthorized%'"
    " OR summary LIKE '%fraud%' OR summary LIKE '%scam%'"
    " OR summary LIKE '%Warnung%' OR summary LIKE '%unerlaubt%'"
    " OR summary LIKE '%Betrug%')"
)

_REGULATOR_PATTERNS: list[tuple[str, list[str]]] = [
    ("BaFin", ["bafin", "bundesanstalt"]),
    ("FINMA", ["finma"]),
    ("FCA", ["fca", "financial conduct authority"]),
    ("ESMA", ["esma"]),
    ("SEC", ["sec ", "securities and exchange"]),
    ("FMA", ["fma austria", "finanzmarktaufsicht"]),
]

_SEVERITY_KEYWORDS = {
    "critical": ["fraud", "betrug", "scam", "ponzi", "criminal", "strafbar", "arrest"],
    "high": ["unauthorized", "unerlaubt", "suspend", "prohibit", "verboten", "untersagung", "warning", "warnung"],
    "medium": ["investigation", "inquiry", "review", "caution", "ermittlung"],
}


def _detect_regulator(text: str) -> str:
    """Detect which regulator issued the warning based on text content."""
    text_lower = text.lower()
    for regulator, keywords in _REGULATOR_PATTERNS:
        if any(kw in text_lower for kw in keywords):
            return regulator
    return "Unknown"


def _detect_severity(text: str) -> str:
    """Classify severity of the warning based on keywords."""
    text_lower = text.lower()
    for severity, keywords in _SEVERITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return severity
    return "low"


def _classify_type(text: str) -> str:
    """Classify the type of warning."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["unauthorized", "unerlaubt", "unlicensed", "ohne erlaubnis"]):
        return "unauthorized_service"
    if any(w in text_lower for w in ["fraud", "betrug", "scam", "ponzi"]):
        return "fraud"
    if any(w in text_lower for w in ["suspend", "prohibit", "verboten", "untersagung"]):
        return "suspension"
    if any(w in text_lower for w in ["investigation", "ermittlung"]):
        return "investigation"
    return "general_warning"


def _extract_entities(title: str) -> list[str]:
    """Try to extract company/website names from warning titles."""
    entities: list[str] = []
    # Pattern: quoted names
    quoted = re.findall(r'["\u201c\u201e]([^"\u201d\u201c]+)["\u201d]', title)
    entities.extend(quoted)

    # Pattern: domain-like names
    domains = re.findall(r'\b[\w-]+\.(?:com|de|ch|io|org|net|exchange|finance|capital)\b', title, re.IGNORECASE)
    entities.extend(domains)

    # Pattern: words after "against" or "gegen"
    after_against = re.findall(r'(?:against|gegen|warns?\s+about)\s+([A-Z][\w\s]+?)(?:\s+(?:for|due|wegen|Ltd|GmbH|AG)|\s*$)', title)
    entities.extend([e.strip() for e in after_against if len(e.strip()) > 2])

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for e in entities:
        lower = e.lower().strip()
        if lower not in seen and len(lower) > 1:
            seen.add(lower)
            result.append(e.strip())
    return result


def _row_to_warning(row: dict) -> dict:
    """Convert a database row to a warning object."""
    text = f"{row.get('title', '')} {row.get('summary', '') or ''}"
    return {
        "id": row["id"],
        "title": row["title"],
        "regulator": _detect_regulator(text),
        "severity": _detect_severity(text),
        "entities_mentioned": _extract_entities(row["title"]),
        "date": row.get("published_at") or row.get("created_at"),
        "url": row.get("url"),
        "type": _classify_type(text),
        "summary": row.get("summary"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/warnings")
async def list_warnings(
    tenant_id: str = "default",
    regulator: Optional[str] = Query(default=None, description="Filter by regulator (BaFin, FINMA, FCA, ESMA)"),
    severity: Optional[str] = Query(default=None, description="Filter by severity (critical, high, medium, low)"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    """Return all BaFin/FINMA scam and warning items from the database."""
    with get_db() as conn:
        cur = conn.cursor()

        query = (
            "SELECT id, title, summary, url, published_at, created_at, category, urgency "
            "FROM items WHERE tenant_id = ? AND category = 'regulation' AND "
            + _WARNING_KEYWORDS_SQL
            + " ORDER BY published_at DESC, created_at DESC LIMIT ? OFFSET ?"
        )
        cur.execute(query, [tenant_id, limit, offset])
        rows = [dict(r) for r in cur.fetchall()]

        # Count total
        count_query = (
            "SELECT COUNT(*) as total FROM items WHERE tenant_id = ? AND category = 'regulation' AND "
            + _WARNING_KEYWORDS_SQL
        )
        cur.execute(count_query, [tenant_id])
        total = cur.fetchone()["total"]

    warnings = [_row_to_warning(r) for r in rows]

    # Apply in-memory filters for regulator/severity (these are derived, not DB columns)
    if regulator:
        warnings = [w for w in warnings if w["regulator"].lower() == regulator.lower()]
    if severity:
        warnings = [w for w in warnings if w["severity"] == severity.lower()]

    # Aggregate stats
    by_regulator: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for w in warnings:
        by_regulator[w["regulator"]] = by_regulator.get(w["regulator"], 0) + 1
        by_severity[w["severity"]] = by_severity.get(w["severity"], 0) + 1

    return {
        "total_warnings": len(warnings),
        "total_in_database": total,
        "by_regulator": by_regulator,
        "by_severity": by_severity,
        "warnings": warnings,
    }


@router.get("/check")
async def check_entity(
    entity: str = Query(description="Company or website name to check against warnings"),
    tenant_id: str = "default",
):
    """Check if a specific company/website appears in any regulatory warnings."""
    search_term = f"%{entity}%"

    with get_db() as conn:
        cur = conn.cursor()

        query = (
            "SELECT id, title, summary, url, published_at, created_at, category, urgency "
            "FROM items WHERE tenant_id = ? AND category = 'regulation' AND "
            "(title LIKE ? OR summary LIKE ? OR content LIKE ?) "
            "ORDER BY published_at DESC, created_at DESC"
        )
        cur.execute(query, [tenant_id, search_term, search_term, search_term])
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {
            "entity": entity,
            "flagged": False,
            "match_count": 0,
            "risk_level": "none",
            "message": f"No regulatory warnings found mentioning '{entity}'.",
            "matches": [],
        }

    matches = [_row_to_warning(r) for r in rows]
    severities = [m["severity"] for m in matches]

    if "critical" in severities:
        risk_level = "critical"
    elif "high" in severities:
        risk_level = "high"
    elif "medium" in severities:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "entity": entity,
        "flagged": True,
        "match_count": len(matches),
        "risk_level": risk_level,
        "message": f"Found {len(matches)} regulatory warning(s) mentioning '{entity}'.",
        "matches": matches,
    }
