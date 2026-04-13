"""Financial sentiment analysis using FinBERT with German language support.

FinBERT (ProsusAI/finbert) is a BERT model fine-tuned on financial text.
It classifies into {positive, negative, neutral} with high accuracy (F1 ~91%).

German texts (BaFin, FINMA regulations) are routed to oliverguhr/german-sentiment-bert
when the ml_german_sentiment feature flag is enabled.

Falls back to keyword-based scoring if transformers/torch not installed.

Usage:
    from app.ai.sentiment import analyze_sentiment
    result = await analyze_sentiment("Bitcoin surges past $100K on ETF inflows")
    # {"label": "positive", "score": 0.87, "scores": {"positive": 0.87, "negative": 0.05, "neutral": 0.08}}

    result = await analyze_sentiment("BaFin erteilt Genehmigung für Krypto-Verwahrung")
    # {"label": "positive", "score": 0.82, ..., "language": "de", "method": "german_bert"}
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# FinBERT model (lazy-loaded)
_pipeline = None
_model_available: Optional[bool] = None

# German sentiment model (lazy-loaded)
_german_pipeline = None
_german_model_available: Optional[bool] = None

GERMAN_MODEL = "oliverguhr/german-sentiment-bert"


def _load_finbert():
    """Lazy-load the FinBERT model. Returns the pipeline or None."""
    global _pipeline, _model_available
    if _model_available is not None:
        return _pipeline

    try:
        from transformers import pipeline as hf_pipeline
        _pipeline = hf_pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
            max_length=512,
        )
        _model_available = True
        logger.info("FinBERT model loaded successfully")
        return _pipeline
    except ImportError:
        logger.info("transformers/torch not installed, using keyword fallback")
        _model_available = False
        return None
    except Exception as e:
        logger.warning("FinBERT load failed, using keyword fallback: %s", e)
        _model_available = False
        return None


def _load_german_model():
    """Lazy-load German sentiment model."""
    global _german_pipeline, _german_model_available
    if _german_model_available is not None:
        return _german_pipeline
    try:
        from transformers import pipeline as hf_pipeline
        _german_pipeline = hf_pipeline(
            "sentiment-analysis",
            model=GERMAN_MODEL,
            truncation=True,
            max_length=512,
        )
        _german_model_available = True
        logger.info("German sentiment model loaded: %s", GERMAN_MODEL)
        return _german_pipeline
    except Exception as e:
        logger.info("German model not available: %s", e)
        _german_model_available = False
        return None


# ──────────────────────────────────────────────
#  Language detection (no external deps)
# ──────────────────────────────────────────────

_GERMAN_INDICATORS = {
    "der", "die", "das", "und", "ist", "von", "für", "mit", "auf", "den",
    "des", "ein", "eine", "nicht", "sich", "dem", "wird", "werden", "hat",
    "auch", "oder", "nach", "bei", "über", "wie", "aber", "dann", "noch",
    "kann", "nur", "zum", "zur", "aus", "wenn", "mehr", "sehr", "durch",
    "regulierung", "verordnung", "finanzmarkt", "kryptowährung", "aufsicht",
    "geldwäsche", "finanzaufsicht", "bundesanstalt", "eidgenössische",
}


def detect_language(text: str) -> str:
    """Simple language detection: 'de' or 'en'. No external deps."""
    words = set(text.lower().split())
    german_count = len(words & _GERMAN_INDICATORS)
    return "de" if german_count >= 3 else "en"


# ──────────────────────────────────────────────
#  Keyword fallback (imported from pipeline.py logic)
# ──────────────────────────────────────────────

POSITIVE_WORDS = [
    "bullish", "rally", "surge", "gain", "growth", "adoption", "approval",
    "partnership", "launch", "record high", "all-time high", "ath",
    "institutional", "inflow", "accumulation", "upgrade", "breakout",
    "profit", "innovation", "milestone", "green light", "recovery",
    "optimistic", "momentum", "breakthrough", "integration", "expansion",
    "kursanstieg", "genehmigung", "zulassung", "durchbruch", "wachstum",
    "erfolg", "partnerschaft", "kooperation", "steigerung",
    "lizenz", "regulierungskonform", "mica-konform", "zugelassen",
    "kursziel", "kaufempfehlung", "outperform", "übergewichten", "aufwertung",
    "marktkapitalisierung", "handelsvolumen", "institutionelle anleger",
]

NEGATIVE_WORDS = [
    "bearish", "crash", "dump", "sell-off", "selloff", "decline", "loss",
    "ban", "lawsuit", "hack", "exploit", "fraud", "scam", "rug pull",
    "rugpull", "ponzi", "collapse", "bankruptcy", "insolvency", "liquidation",
    "enforcement", "fine", "penalty", "warning", "risk", "investigation",
    "probe", "crackdown", "delisting", "outflow", "capitulation",
    "verbot", "betrug", "warnung", "risiko", "verlust", "insolvenz",
    "geldwaesche", "geldwäsche", "strafverfolgung", "razzia", "absturz",
    "regulierungsrisiko", "bußgeld", "strafzahlung", "marktmanipulation",
    "kursverfall", "verkaufsempfehlung", "untergewichten", "abwertung",
    "kapitalbindung", "liquiditätsrisiko", "systemrisiko", "ausfallrisiko",
]


def _keyword_sentiment(text: str) -> dict:
    """Keyword-based sentiment scoring (fallback)."""
    if not text:
        return {"label": "neutral", "score": 0.0, "scores": {"positive": 0.0, "negative": 0.0, "neutral": 1.0}}

    text_lower = text.lower()
    pos_hits = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in text_lower)

    total = pos_hits + neg_hits
    if total == 0:
        return {"label": "neutral", "score": 0.5, "scores": {"positive": 0.0, "negative": 0.0, "neutral": 1.0}}

    pos_ratio = pos_hits / total
    neg_ratio = neg_hits / total
    neutral_ratio = max(0, 1.0 - pos_ratio - neg_ratio)

    if pos_ratio > neg_ratio:
        label = "positive"
        score = pos_ratio
    elif neg_ratio > pos_ratio:
        label = "negative"
        score = neg_ratio
    else:
        label = "neutral"
        score = 0.5

    return {
        "label": label,
        "score": round(score, 3),
        "scores": {
            "positive": round(pos_ratio, 3),
            "negative": round(neg_ratio, 3),
            "neutral": round(neutral_ratio, 3),
        },
        "method": "keyword",
        "language": detect_language(text),
    }


# ──────────────────────────────────────────────
#  FinBERT analysis (English)
# ──────────────────────────────────────────────

def _finbert_sentiment(text: str) -> dict:
    """Run FinBERT on a single text. Returns structured result."""
    pipe = _load_finbert()
    if pipe is None:
        return _keyword_sentiment(text)

    # Truncate to ~500 chars for speed (FinBERT max_length=512 tokens)
    truncated = text[:1500]
    result = pipe(truncated)[0]

    label = result["label"].lower()  # "positive", "negative", "neutral"
    confidence = result["score"]

    # Get all class scores if available
    all_results = pipe(truncated, top_k=None)
    # top_k=None may return list-of-lists or flat list depending on version
    if all_results and isinstance(all_results[0], list):
        all_results = all_results[0]
    scores = {r["label"].lower(): round(r["score"], 4) for r in all_results if isinstance(r, dict)}

    return {
        "label": label,
        "score": round(confidence, 4),
        "scores": scores,
        "method": "finbert",
        "language": "en",
    }


# ──────────────────────────────────────────────
#  German sentiment analysis
# ──────────────────────────────────────────────

# Label mapping: oliverguhr model uses "positive", "negative", "neutral"
_GERMAN_LABEL_MAP = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
}


def _german_sentiment(text: str) -> dict:
    """Run German sentiment model on text. Falls back to keyword if unavailable."""
    pipe = _load_german_model()
    if pipe is None:
        return _keyword_sentiment(text)

    truncated = text[:1500]
    result = pipe(truncated)[0]

    raw_label = result["label"].lower()
    label = _GERMAN_LABEL_MAP.get(raw_label, "neutral")
    confidence = result["score"]

    # Get all class scores
    try:
        all_results = pipe(truncated, top_k=None)
        # top_k=None may return list[list[dict]] or list[dict]
        if all_results and isinstance(all_results[0], list):
            all_results = all_results[0]
        scores = {}
        for r in all_results:
            mapped = _GERMAN_LABEL_MAP.get(r["label"].lower(), r["label"].lower())
            scores[mapped] = round(r["score"], 4)
    except Exception:
        scores = {label: round(confidence, 4)}

    # Ensure all three keys exist
    for k in ("positive", "negative", "neutral"):
        scores.setdefault(k, 0.0)

    return {
        "label": label,
        "score": round(confidence, 4),
        "scores": scores,
        "method": "german_bert",
        "language": "de",
    }


async def analyze_sentiment(text: str, language: str | None = None) -> dict:
    """Analyze financial sentiment with language-aware model selection.

    Uses German model for German text (when ml_german_sentiment flag is on),
    FinBERT for English text, and keyword fallback if models unavailable.

    Args:
        text: The text to analyze.
        language: Optional language override ('de' or 'en'). Auto-detected if None.

    Returns: {"label": str, "score": float, "scores": dict, "method": str, "language": str}
    """
    if not text or not text.strip():
        return {
            "label": "neutral",
            "score": 0.0,
            "scores": {"positive": 0.0, "negative": 0.0, "neutral": 1.0},
            "method": "empty",
            "language": language or "en",
        }

    lang = language or detect_language(text)

    if lang == "de":
        # Try German model first (feature-flag gated)
        from app.feature_flags import is_enabled
        if is_enabled("ml_german_sentiment"):
            result = await asyncio.to_thread(_german_sentiment, text)
            if result.get("method") != "keyword":
                return result
        # German text but model not available/not enabled: keyword fallback
        kw_result = _keyword_sentiment(text)
        kw_result["language"] = "de"
        return kw_result

    # English path: FinBERT in thread pool
    return await asyncio.to_thread(_finbert_sentiment, text)


async def analyze_batch(texts: list[str]) -> list[dict]:
    """Analyze sentiment for a batch of texts."""
    pipe = _load_finbert()
    if pipe is None:
        return [_keyword_sentiment(t) for t in texts]

    def _batch():
        truncated = [t[:1500] for t in texts]
        results = pipe(truncated, batch_size=16)
        all_scores = pipe(truncated, batch_size=16, top_k=None)

        output = []
        for res, scores_list in zip(results, all_scores):
            scores = {r["label"].lower(): round(r["score"], 4) for r in scores_list}
            output.append({
                "label": res["label"].lower(),
                "score": round(res["score"], 4),
                "scores": scores,
                "method": "finbert",
            })
        return output

    return await asyncio.to_thread(_batch)


def sentiment_to_score(result: dict) -> float:
    """Convert sentiment result to a single -1.0 to 1.0 score.

    Compatible with the existing pipeline.compute_sentiment() interface.
    """
    scores = result.get("scores", {})
    pos = scores.get("positive", 0.0)
    neg = scores.get("negative", 0.0)
    return round(pos - neg, 4)


def is_finbert_available() -> bool:
    """Check if FinBERT model is loaded and available."""
    _load_finbert()
    return _model_available is True
