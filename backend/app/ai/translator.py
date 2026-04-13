"""On-demand translation service for feed items.

Translates title + summary into the user's chosen locale using the configured
LLM provider (Anthropic / OpenAI).  Results are cached in a ``translations``
DB table so each string is only translated once.

When no LLM key is available the original text is returned unchanged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Optional

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

LANG_NAMES = {
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "en": "English",
}

# ── DB cache ────────────────────────────────────────────────────────────────

def _text_hash(text: str, lang: str) -> str:
    """Deterministic hash for (text, lang) pair."""
    return hashlib.sha256(f"{lang}:{text}".encode()).hexdigest()[:32]


def _cache_get(text: str, lang: str) -> Optional[str]:
    """Look up a cached translation.  Returns None on miss."""
    h = _text_hash(text, lang)
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT translated FROM translations WHERE hash = ? AND lang = ?",
                [h, lang],
            )
            row = cur.fetchone()
            if row:
                return row["translated"] if hasattr(row, "keys") else row[0]
    except Exception:
        pass
    return None


def _cache_set(text: str, lang: str, translated: str) -> None:
    """Store a translation in the cache."""
    h = _text_hash(text, lang)
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO translations (hash, lang, original, translated) VALUES (?, ?, ?, ?)",
                [h, lang, text[:500], translated],
            )
    except Exception as exc:
        logger.debug("translation cache write failed: %s", exc)


# ── LLM translation ────────────────────────────────────────────────────────

_TRANSLATE_PROMPT = (
    "Translate the following JSON object's values into {lang_name}. "
    "Keep the JSON keys exactly as they are. Only translate the values. "
    "Return ONLY valid JSON, no markdown, no explanation.\n\n{payload}"
)


def _get_llm_provider():
    """Reuse pipeline's provider logic."""
    from app.ai.pipeline import _get_llm_provider as _plp
    return _plp()


async def _llm_translate(title: str, summary: str, lang: str) -> dict[str, str]:
    """Translate title+summary via LLM.  Returns {"title": ..., "summary": ...}."""
    lang_name = LANG_NAMES.get(lang, lang)
    payload = json.dumps({"title": title, "summary": summary}, ensure_ascii=False)
    prompt = _TRANSLATE_PROMPT.format(lang_name=lang_name, payload=payload)

    provider, client = _get_llm_provider()
    if not provider or not client:
        return {"title": title, "summary": summary}

    try:
        if provider == "anthropic":
            resp = await asyncio.to_thread(
                client.messages.create,
                model=settings.llm_model_anthropic,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw = resp.content[0].text
        else:
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=settings.llm_model_openai,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content

        result = json.loads(raw)
        return {
            "title": result.get("title", title),
            "summary": result.get("summary", summary),
        }
    except Exception as exc:
        logger.warning("LLM translation failed (%s): %s", provider, exc)
        return {"title": title, "summary": summary}


# ── Public API ──────────────────────────────────────────────────────────────

async def translate_item(title: str, summary: str, lang: str) -> dict[str, str]:
    """Translate title + summary into *lang*, using cache first.

    Returns ``{"title": ..., "summary": ...}`` always — originals on failure.
    """
    if lang == "en":
        return {"title": title, "summary": summary}

    # Check cache for both fields
    cached_title = _cache_get(title, lang)
    cached_summary = _cache_get(summary, lang) if summary else summary

    if cached_title and (cached_summary or not summary):
        return {"title": cached_title, "summary": cached_summary or ""}

    # LLM translate
    result = await _llm_translate(title, summary or "", lang)

    # Cache results
    if result["title"] != title:
        _cache_set(title, lang, result["title"])
    if summary and result["summary"] != summary:
        _cache_set(summary, lang, result["summary"])

    return result


async def translate_items_batch(
    items: list[dict], lang: str
) -> list[dict]:
    """Translate a list of item dicts (must have 'title' and 'summary' keys).

    Modifies items in-place and returns them.  Translates uncached items in
    parallel (up to 5 concurrent LLM calls).
    """
    if lang == "en":
        return items

    sem = asyncio.Semaphore(5)

    async def _do(item: dict) -> None:
        async with sem:
            result = await translate_item(
                item.get("title", ""),
                item.get("summary", ""),
                lang,
            )
            item["title"] = result["title"]
            item["summary"] = result["summary"]

    await asyncio.gather(*[_do(it) for it in items])
    return items
