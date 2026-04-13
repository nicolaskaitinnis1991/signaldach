from __future__ import annotations

import json
import logging
from typing import List, Optional

from bs4 import BeautifulSoup

from app.config import settings
from app.scrapers.base import ProcessedItem, RawItem
from app.ai.entities import extract_entities, entities_to_dict

logger = logging.getLogger(__name__)

# Lazy imports for LLM providers
_openai_client = None
_anthropic_client = None

SYSTEM_PROMPT = """You are a market intelligence analyst for a crypto trading fund in the DACH region
(Germany, Austria, Switzerland). Analyze the following news item and return a JSON object with:

1. "category": one of "regulation", "competition", "market", "sentiment"
2. "relevance_score": integer 1-10 (10 = critical for DACH crypto fund operations)
3. "urgency": one of "normal", "high", "breaking"
4. "summary": 2-3 sentence summary in English (always English — translation happens separately)
5. "keywords": list of 3-5 key terms
6. "sentiment_score": float -1.0 to 1.0 (negative = bearish/concerning, positive = bullish/favorable)

Focus on relevance to: crypto regulation (BaFin, FINMA, MiCA), fund management,
HNWI crypto adoption, institutional crypto in DACH, and competitive landscape.

IMPORTANT: Regardless of the source language (Chinese, Japanese, Korean, Russian, etc.),
always analyze the content and produce the summary in English.

Return ONLY valid JSON, no markdown."""


# ──────────────────────────────────────────────
#  HTML stripping
# ──────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Remove all HTML tags and decode entities. Returns plain text."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)


# ──────────────────────────────────────────────
#  Sentiment scoring (keyword-based fallback)
# ──────────────────────────────────────────────

POSITIVE_WORDS = [
    "bullish", "rally", "surge", "gain", "growth", "adoption", "approval",
    "partnership", "launch", "record high", "all-time high", "ath",
    "institutional", "inflow", "accumulation", "upgrade", "breakout",
    "profit", "innovation", "milestone", "green light", "recovery",
    "optimistic", "momentum", "breakthrough", "integration", "expansion",
    "kursanstieg", "genehmigung", "zulassung", "durchbruch", "wachstum",
    "erfolg", "partnerschaft", "kooperation", "steigerung",
]

NEGATIVE_WORDS = [
    "bearish", "crash", "dump", "sell-off", "selloff", "decline", "loss",
    "ban", "lawsuit", "hack", "exploit", "fraud", "scam", "rug pull",
    "rugpull", "ponzi", "collapse", "bankruptcy", "insolvency", "liquidation",
    "enforcement", "fine", "penalty", "warning", "risk", "investigation",
    "probe", "crackdown", "delisting", "outflow", "capitulation",
    "verbot", "betrug", "warnung", "risiko", "verlust", "insolvenz",
    "geldwaesche", "geldwäsche", "strafverfolgung", "razzia", "absturz",
]


def compute_sentiment(text: str) -> float:
    """Compute sentiment score from -1.0 to 1.0.

    Uses FinBERT when available (sync wrapper), falls back to keyword-based.
    For async code, use app.ai.sentiment.analyze_sentiment() directly.
    """
    if not text:
        return 0.0

    try:
        from app.ai.sentiment import _finbert_sentiment, sentiment_to_score
        result = _finbert_sentiment(text)
        return sentiment_to_score(result)
    except Exception:
        pass

    # Keyword fallback
    text_lower = text.lower()
    pos_hits = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in text_lower)

    total = pos_hits + neg_hits
    if total == 0:
        return 0.0

    raw = (pos_hits - neg_hits) / total
    return round(max(-1.0, min(1.0, raw)), 3)


# ──────────────────────────────────────────────
#  Duplicate detection (Jaccard on title words)
# ──────────────────────────────────────────────

def _title_words(title: str) -> set[str]:
    """Tokenize a title into a set of lowercase words, ignoring short ones."""
    return {w for w in title.lower().split() if len(w) > 2}


def jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two title strings."""
    set_a = _title_words(a)
    set_b = _title_words(b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


DUPLICATE_THRESHOLD = 0.7  # titles with >=70% Jaccard overlap are considered duplicates


def deduplicate_by_title(items: list[RawItem]) -> list[RawItem]:
    """Remove items whose titles are too similar to an earlier item in the batch."""
    if not items:
        return []

    unique: list[RawItem] = []
    for item in items:
        is_dup = False
        for kept in unique:
            if jaccard_similarity(item.title, kept.title) >= DUPLICATE_THRESHOLD:
                is_dup = True
                logger.debug(
                    f"Duplicate detected: '{item.title[:60]}' ~ '{kept.title[:60]}'"
                )
                break
        if not is_dup:
            unique.append(item)

    removed = len(items) - len(unique)
    if removed:
        logger.info(f"Title dedup: removed {removed} duplicates from {len(items)} items")
    return unique


# ──────────────────────────────────────────────
#  Keyword lists for rule-based processing
# ──────────────────────────────────────────────

REGULATION_KEYWORDS = [
    "bafin", "finma", "mica", "kmag", "casp", "kryptoverwahrgeschäft",
    "crypto regulation", "krypto-regulierung", "verordnung", "lizenz",
    "license", "enforcement", "aufsicht", "geldwäsche", "aml", "kyc",
    "regulatory", "regulator", "compliance", "legal framework",
    "gesetzgebung", "richtlinie", "directive", "supervisory",
    "mifid", "esma", "dora", "travel rule", "sanctions",
    "geldwäschegesetz", "gwg", "kryptoregulierung",
]

COMPETITION_KEYWORDS = [
    "21shares", "bitcoin suisse", "amina", "seba", "crypto finance",
    "dda", "coinshares", "haic", "bitpanda", "scalable",
    "fund launch", "new fund", "aum", "assets under management",
    "sygnum", "trade republic", "swissborg", "boerse stuttgart",
    "bsdex", "etf", "etp", "crypto fund", "digital assets fund",
    "custody", "verwahrung", "institutional", "family office",
]

MARKET_KEYWORDS = [
    "bitcoin", "ethereum", "btc", "eth", "crypto market",
    "price", "kurs", "rally", "correction", "volatility",
    "trading volume", "market cap", "defi", "staking",
    "yield", "liquidity", "halving", "merge", "layer 2",
]

DACH_KEYWORDS = [
    "germany", "deutschland", "austria", "österreich", "switzerland", "schweiz",
    "dach", "zurich", "zürich", "berlin", "frankfurt", "vienna", "wien",
    "munich", "münchen", "crypto valley", "zug", "liechtenstein",
    "swiss", "german", "austrian",
]

URGENCY_KEYWORDS = [
    "breaking", "sofort", "ban", "verbot", "enforcement action",
    "emergency", "hack", "exploit", "crash", "collapse",
    "alert", "urgent", "immediately", "dringend", "eilmeldung",
    "flash crash", "circuit breaker", "halt", "suspended",
]


def _get_llm_provider() -> tuple[Optional[str], Optional[object]]:
    """Get the best available LLM provider. Returns (provider_name, client) or (None, None)."""
    global _openai_client, _anthropic_client

    provider = settings.llm_provider

    # Try Anthropic first if auto or explicitly set
    if provider in ("auto", "anthropic") and settings.anthropic_api_key:
        try:
            import anthropic
            if _anthropic_client is None:
                _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            return "anthropic", _anthropic_client
        except ImportError:
            logger.debug("anthropic package not installed, trying openai")

    # Try OpenAI
    if provider in ("auto", "openai") and settings.openai_api_key:
        try:
            from openai import OpenAI
            if _openai_client is None:
                _openai_client = OpenAI(api_key=settings.openai_api_key)
            return "openai", _openai_client
        except ImportError:
            logger.debug("openai package not installed")

    return None, None


async def process_item(raw: RawItem, source_category: str = "market") -> ProcessedItem:
    """Run AI pipeline on a single raw item. Falls back to rule-based if no API key."""
    raw.content = strip_html(raw.content)

    provider, client = _get_llm_provider()

    if provider and client:
        try:
            if provider == "anthropic":
                return await _anthropic_process(client, raw, source_category)
            else:
                return await _openai_process(client, raw, source_category)
        except Exception as e:
            logger.warning(f"AI processing failed ({provider}), falling back to rules: {e}")

    return _rule_based_process(raw, source_category)


async def _anthropic_process(client, raw: RawItem, source_category: str) -> ProcessedItem:
    """Process with Anthropic Claude API (runs sync client in thread to avoid blocking)."""
    import asyncio

    user_content = f"Title: {raw.title}\n\nContent: {raw.content[:1500]}\n\nSource URL: {raw.url}"

    response = await asyncio.to_thread(
        client.messages.create,
        model=settings.llm_model_anthropic,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        temperature=0.2,
    )

    result = json.loads(response.content[0].text)
    return _build_ai_result(result, raw, source_category, f"claude:{settings.llm_model_anthropic}")


async def _openai_process(client, raw: RawItem, source_category: str) -> ProcessedItem:
    """Process with OpenAI API (runs sync client in thread to avoid blocking)."""
    import asyncio

    user_content = f"Title: {raw.title}\n\nContent: {raw.content[:1500]}\n\nSource URL: {raw.url}"

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=settings.llm_model_openai,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    return _build_ai_result(result, raw, source_category, f"openai:{settings.llm_model_openai}")


def _build_ai_result(result: dict, raw: RawItem, source_category: str, model_name: str) -> ProcessedItem:
    """Build ProcessedItem from LLM JSON response."""
    full_text = f"{raw.title} {raw.content[:2000]}"
    entities = extract_entities(full_text)
    entity_dict = entities_to_dict(entities)

    summary = strip_html(result.get("summary", ""))

    return ProcessedItem(
        title=strip_html(raw.title),
        summary=summary,
        content=raw.content[:2000],
        url=raw.url,
        author=raw.author,
        published_at=raw.published_at,
        external_id=raw.external_id,
        category=result.get("category", source_category),
        relevance_score=min(10, max(1, result.get("relevance_score", 5))),
        urgency=result.get("urgency", "normal"),
        sentiment=result.get("sentiment_score"),
        ai_metadata={
            "keywords": result.get("keywords", []),
            "model": model_name,
            "source_category": source_category,
            "entities": entity_dict,
        },
    )


def _rule_based_process(raw: RawItem, source_category: str) -> ProcessedItem:
    """Keyword-based processing when no AI API key is configured."""
    text = f"{raw.title} {raw.content}".lower()

    # Category detection with expanded keywords
    category = source_category
    reg_hits = sum(1 for kw in REGULATION_KEYWORDS if kw in text)
    comp_hits = sum(1 for kw in COMPETITION_KEYWORDS if kw in text)
    market_hits = sum(1 for kw in MARKET_KEYWORDS if kw in text)

    scores = {
        "regulation": reg_hits,
        "competition": comp_hits,
        "market": market_hits,
    }
    best_cat = max(scores, key=scores.get)
    if scores[best_cat] > 0:
        category = best_cat

    # DACH relevance bonus
    dach_hits = sum(1 for kw in DACH_KEYWORDS if kw in text)

    # Relevance scoring: base 3, +1 per keyword hit, +2 per DACH hit (max 10)
    all_keywords = REGULATION_KEYWORDS + COMPETITION_KEYWORDS + MARKET_KEYWORDS
    keyword_hits = sum(1 for kw in all_keywords if kw in text)
    relevance = min(10, 3 + keyword_hits + dach_hits * 2)

    # Urgency
    urgency = "normal"
    urgency_hits = sum(1 for kw in URGENCY_KEYWORDS if kw in text)
    if urgency_hits >= 2:
        urgency = "breaking"
    elif urgency_hits >= 1:
        urgency = "high"

    # Sentiment
    sentiment = compute_sentiment(text)

    # Entity extraction
    full_text = f"{raw.title} {raw.content[:2000]}"
    entities = extract_entities(full_text)
    entity_dict = entities_to_dict(entities)

    # Keywords: collect matched keywords
    matched_keywords = [kw for kw in all_keywords if kw in text][:5]

    # Simple summary (first 200 chars of clean content)
    summary = raw.content[:200].strip()
    if len(raw.content) > 200:
        summary += "..."

    return ProcessedItem(
        title=strip_html(raw.title),
        summary=strip_html(summary),
        content=raw.content[:2000],
        url=raw.url,
        author=raw.author,
        published_at=raw.published_at,
        external_id=raw.external_id,
        category=category,
        relevance_score=relevance,
        urgency=urgency,
        sentiment=sentiment,
        ai_metadata={
            "keywords": matched_keywords,
            "model": "rule-based",
            "source_category": source_category,
            "entities": entity_dict,
            "dach_relevance_hits": dach_hits,
        },
    )


async def process_batch(
    raw_items: list[RawItem], source_category: str = "market"
) -> list[ProcessedItem]:
    """Process a batch of raw items through the AI pipeline.

    Applies title-based deduplication before processing.
    """
    # Deduplicate by title similarity within the batch
    unique_items = deduplicate_by_title(raw_items)

    results = []
    for item in unique_items:
        processed = await process_item(item, source_category)
        results.append(processed)
    return results
