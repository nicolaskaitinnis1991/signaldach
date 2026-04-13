"""Regulatory Horizon Scanner — relevance scoring for YOUR business.

Queries regulation items from the database and scores each one based
on the specified business type and jurisdictions. Groups results into
actionable categories: "directly_affects_you", "monitor", "low_relevance".
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.database import get_db

router = APIRouter(prefix="/horizon", tags=["horizon"])


# ---------------------------------------------------------------------------
# Business-type keyword mappings for relevance scoring
# ---------------------------------------------------------------------------

_BUSINESS_KEYWORDS: dict[str, list[str]] = {
    "fund": [
        "fund", "asset management", "vermögensverwaltung", "portfolio",
        "kwg", "kagb", "aifm", "ucits", "investment fund", "hedge fund",
        "crypto fund", "digital asset fund", "aifmd", "fondsmanagement",
        "kapitalanlagegesetzbuch", "kapitalverwaltungsgesellschaft",
    ],
    "casp": [
        "casp", "crypto-asset service provider", "exchange", "trading platform",
        "broker", "custody", "wallet", "mica", "dora", "payment services",
        "zahlungsdienst", "e-money", "stablecoin", "token issuance",
        "kryptowerte-transferverordnung", "transfer of funds",
    ],
    "issuer": [
        "issuer", "token", "ico", "sto", "ieo", "whitepaper", "prospectus",
        "security token", "asset-referenced token", "e-money token",
        "stablecoin", "mica title III", "mica title IV", "art token",
        "tokenization", "tokenisierung", "emission",
    ],
    "custody": [
        "custody", "custodian", "verwahrung", "kryptoverwahrung",
        "kryptowertpapier", "wallet", "cold storage", "hot wallet",
        "private key", "safekeeping", "depotgeschäft", "kwg §1",
    ],
}

_JURISDICTION_KEYWORDS: dict[str, list[str]] = {
    "DE": [
        "bafin", "germany", "deutschland", "german", "bundestag",
        "bundesfinanzministerium", "bmf", "bundesrat", "kwg", "kagb",
    ],
    "CH": [
        "finma", "switzerland", "schweiz", "swiss", "zurich", "zürich",
        "geneva", "genf", "zug", "crypto valley", "sro", "vqf",
    ],
    "AT": [
        "fma", "austria", "österreich", "austrian", "wien", "vienna",
        "nationalrat", "finanzmarktaufsicht",
    ],
    "EU": [
        "esma", "eba", "eu", "european", "brussels", "brüssel",
        "mica", "dora", "aml", "amld", "emir", "mifid",
        "european commission", "european parliament",
    ],
}

_ENFORCEMENT_KEYWORDS = [
    "enforcement", "warning", "fine", "penalty", "sanction", "ban",
    "prohibition", "investigation", "cease and desist", "bußgeld",
    "ordnungswidrigkeit", "strafanzeige", "verwaltungsverfahren",
    "untersagung", "abmahnung",
]

_COMPETITOR_NAMES = [
    "21shares", "bitcoin suisse", "seba", "sygnum", "bitpanda",
    "bsdex", "boerse stuttgart", "börse stuttgart", "coinbase",
    "kraken", "binance", "crypto finance", "leonteq", "vontobel",
    "eto gruppe", "blocktopia", "immutable insight", "coinfinity",
]

_URGENCY_KEYWORDS = [
    "deadline", "effective date", "compliance", "mandatory",
    "required by", "enforceable", "in force", "transition period",
    "übergangsfrist", "stichtag", "frist", "verpflichtend",
]


def _score_item(
    item: dict,
    business_type: str,
    jurisdictions: list[str],
) -> dict:
    """Score a regulation item for personal relevance to the specified business."""
    text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('content', '')}".lower()

    base_relevance = item.get("relevance_score", 5)
    personal_score = base_relevance  # Start from the original relevance

    reasons: list[str] = []
    tags: list[str] = []

    # --- Business type matching ---
    biz_keywords = _BUSINESS_KEYWORDS.get(business_type, [])
    biz_matches = [kw for kw in biz_keywords if kw in text]
    if biz_matches:
        boost = min(len(biz_matches) * 1.5, 4)  # max +4 from business keywords
        personal_score += boost
        reasons.append(
            f"Matches {business_type} keywords: {', '.join(biz_matches[:3])}"
        )

    # --- Jurisdiction matching ---
    matched_jurisdictions: list[str] = []
    for j in jurisdictions:
        j_keywords = _JURISDICTION_KEYWORDS.get(j.upper(), [])
        j_matches = [kw for kw in j_keywords if kw in text]
        if j_matches:
            personal_score += 1.5
            matched_jurisdictions.append(j.upper())

    if matched_jurisdictions:
        reasons.append(f"Relevant to jurisdictions: {', '.join(matched_jurisdictions)}")

    # --- Enforcement boost ---
    enforcement_matches = [kw for kw in _ENFORCEMENT_KEYWORDS if kw in text]
    if enforcement_matches:
        personal_score += 2
        reasons.append(f"Enforcement/warning language detected: {', '.join(enforcement_matches[:2])}")
        tags.append("enforcement")

    # --- Competitor tagging ---
    competitor_matches = [name for name in _COMPETITOR_NAMES if name in text]
    if competitor_matches:
        personal_score += 0.5
        tags.append("competition")
        reasons.append(f"Mentions competitors: {', '.join(competitor_matches[:3])}")

    # --- Urgency keywords ---
    urgency_matches = [kw for kw in _URGENCY_KEYWORDS if kw in text]
    if urgency_matches:
        personal_score += 1
        tags.append("deadline")
        reasons.append(f"Contains deadline/compliance language")

    # --- Original urgency boost ---
    urgency = item.get("urgency", "normal")
    if urgency == "breaking":
        personal_score += 2
    elif urgency == "high":
        personal_score += 1

    # Clamp to 0-10
    personal_score = max(0, min(10, round(personal_score, 1)))

    # Categorize
    if personal_score >= 8:
        category = "directly_affects_you"
    elif personal_score >= 5:
        category = "monitor"
    else:
        category = "low_relevance"

    # Generate recommended action
    recommended_action = _generate_action(category, business_type, tags, reasons)

    # Detect deadline from text
    deadline = _extract_deadline(text)

    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "url": item.get("url", ""),
        "original_relevance": base_relevance,
        "personal_relevance": personal_score,
        "relevance_reason": " | ".join(reasons) if reasons else "General regulatory news with limited direct relevance.",
        "category": category,
        "recommended_action": recommended_action,
        "deadline": deadline,
        "source": item.get("source_name", item.get("author", "Unknown")),
        "date": item.get("published_at") or item.get("created_at", ""),
        "urgency": urgency,
        "tags": tags,
    }


def _generate_action(
    category: str, business_type: str, tags: list[str], reasons: list[str]
) -> str:
    """Generate a recommended action based on the category and context."""
    biz_label = {
        "fund": "fund operations",
        "casp": "CASP license and operations",
        "issuer": "token issuance activities",
        "custody": "custody service operations",
    }.get(business_type, "business operations")

    if category == "directly_affects_you":
        if "enforcement" in tags:
            return f"URGENT: Review your compliance posture for {biz_label}. Check if this enforcement action has implications for your operations. Consult legal counsel."
        if "deadline" in tags:
            return f"ACTION REQUIRED: Check the compliance deadline and ensure your {biz_label} meets requirements before the effective date."
        return f"Review this regulation carefully and assess impact on your {biz_label}. Consider scheduling a compliance review."
    elif category == "monitor":
        if "competition" in tags:
            return f"Monitor competitor developments. Assess if this creates opportunities or threats for your {biz_label}."
        return f"Keep this on your radar. No immediate action required but could affect {biz_label} in the future."
    else:
        return "Low relevance to your business. No action needed at this time."


def _extract_deadline(text: str) -> Optional[str]:
    """Try to extract a date from the text that looks like a deadline."""
    # Match common date patterns
    patterns = [
        r"(\d{1,2})[./](\d{1,2})[./](20\d{2})",  # DD.MM.YYYY or DD/MM/YYYY
        r"(20\d{2})-(\d{2})-(\d{2})",              # YYYY-MM-DD
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups[0]) == 4:  # YYYY-MM-DD
                return f"{groups[0]}-{groups[1]}-{groups[2]}"
            else:  # DD.MM.YYYY
                return f"{groups[2]}-{groups[1]}-{groups[0]}"
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/scan")
async def horizon_scan(
    business_type: str = Query(
        default="fund",
        pattern="^(fund|casp|issuer|custody)$",
        description="Business type: fund, casp, issuer, or custody",
    ),
    jurisdictions: str = Query(
        default="DE,CH",
        description="Comma-separated jurisdiction codes: DE, CH, AT, EU",
    ),
    days: int = Query(default=30, ge=1, le=365, description="Look-back period in days"),
    limit: int = Query(default=50, ge=1, le=200, description="Max items to return"),
):
    """Scan recent regulations and score them for relevance to your business."""
    jurisdiction_list = [j.strip().upper() for j in jurisdictions.split(",") if j.strip()]

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT i.*, s.name as source_name
               FROM items i
               LEFT JOIN sources s ON i.source_id = s.id
               WHERE i.category = 'regulation'
                 AND i.created_at >= datetime('now', ? || ' days')
               ORDER BY i.published_at DESC, i.created_at DESC
               LIMIT ?""",
            [-days, limit * 3],  # Fetch more to allow filtering
        )
        rows = [dict(r) for r in cur.fetchall()]

    # Score each item
    scored = [_score_item(r, business_type, jurisdiction_list) for r in rows]

    # Sort by personal relevance descending
    scored.sort(key=lambda x: x["personal_relevance"], reverse=True)

    # Limit results
    scored = scored[:limit]

    # Group counts
    critical = sum(1 for s in scored if s["category"] == "directly_affects_you")
    monitor = sum(1 for s in scored if s["category"] == "monitor")
    low = sum(1 for s in scored if s["category"] == "low_relevance")

    return {
        "business_type": business_type,
        "jurisdictions": jurisdiction_list,
        "scan_date": str(date.today()),
        "summary": {
            "critical": critical,
            "monitor": monitor,
            "low_relevance": low,
            "total_scanned": len(scored),
        },
        "items": scored,
    }


@router.get("/business-types")
async def list_business_types():
    """Return available business types and their descriptions."""
    return {
        "business_types": [
            {
                "id": "fund",
                "name": "Crypto Fund / Asset Manager",
                "description": "Investment funds, AIFMs, portfolio management, crypto fund operations",
                "keywords_count": len(_BUSINESS_KEYWORDS["fund"]),
            },
            {
                "id": "casp",
                "name": "Crypto-Asset Service Provider (CASP)",
                "description": "Exchanges, trading platforms, brokers, wallet providers",
                "keywords_count": len(_BUSINESS_KEYWORDS["casp"]),
            },
            {
                "id": "issuer",
                "name": "Token Issuer",
                "description": "ICO/STO issuers, stablecoin issuers, tokenization platforms",
                "keywords_count": len(_BUSINESS_KEYWORDS["issuer"]),
            },
            {
                "id": "custody",
                "name": "Custody Provider",
                "description": "Crypto custody, key management, safekeeping services",
                "keywords_count": len(_BUSINESS_KEYWORDS["custody"]),
            },
        ]
    }
