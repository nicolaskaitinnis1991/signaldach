"""Tests for German language support in sentiment analysis."""

import asyncio
import os
import pytest

# Ensure feature flags are set before imports
os.environ["SIGNALDACH_FF_ML_GERMAN_SENTIMENT"] = "true"

from app.ai.sentiment import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    _keyword_sentiment,
    analyze_sentiment,
    detect_language,
    sentiment_to_score,
)


class TestDetectLanguage:
    """Language detection tests."""

    def test_detect_language_german(self):
        """German regulatory text is detected as 'de'."""
        text = "Die BaFin hat eine neue Verordnung für Kryptowährung erlassen und wird diese durchsetzen"
        assert detect_language(text) == "de"

    def test_detect_language_english(self):
        """English text is detected as 'en'."""
        text = "Bitcoin surges past $100K as ETF inflows reach record levels"
        assert detect_language(text) == "en"

    def test_detect_language_mixed_german_dominant(self):
        """Mixed text with enough German words is detected as 'de'."""
        text = "Die neue Bitcoin Regulierung ist ein Durchbruch für den Markt"
        assert detect_language(text) == "de"

    def test_detect_language_short_english(self):
        """Short English text without German words returns 'en'."""
        text = "BTC price up"
        assert detect_language(text) == "en"

    def test_detect_language_german_financial(self):
        """German financial terms trigger detection."""
        text = "Die Finanzaufsicht hat die Regulierung der Kryptowährung verschärft"
        assert detect_language(text) == "de"


class TestKeywordSentimentGerman:
    """German keyword sentiment tests."""

    def test_keyword_sentiment_german_positive(self):
        """German positive keywords produce positive sentiment."""
        text = "BaFin erteilt Genehmigung und Zulassung für neues Krypto-Produkt"
        result = _keyword_sentiment(text)
        assert result["label"] == "positive"
        assert result["scores"]["positive"] > 0

    def test_keyword_sentiment_german_negative(self):
        """German negative keywords produce negative sentiment."""
        text = "Warnung vor Betrug und Risiko bei Krypto-Absturz und Geldwäsche"
        result = _keyword_sentiment(text)
        assert result["label"] == "negative"
        assert result["scores"]["negative"] > 0

    def test_keyword_sentiment_german_negative_new_words(self):
        """Newly added German negative keywords are recognized."""
        text = "Regulierungsrisiko und drohende Bußgeld wegen Marktmanipulation"
        result = _keyword_sentiment(text)
        assert result["label"] == "negative"

    def test_keyword_sentiment_german_positive_new_words(self):
        """Newly added German positive keywords are recognized."""
        text = "Neue Lizenz und Kaufempfehlung, MICA-konform zugelassen"
        result = _keyword_sentiment(text)
        assert result["label"] == "positive"

    def test_keyword_sentiment_includes_language(self):
        """Keyword sentiment result includes language field."""
        text = "Die BaFin hat eine Warnung für alle Betrug-Fälle erlassen"
        result = _keyword_sentiment(text)
        assert "language" in result


class TestAnalyzeSentiment:
    """Async analyze_sentiment tests."""

    def test_analyze_sentiment_returns_result(self):
        """analyze_sentiment returns a dict with expected keys."""
        result = asyncio.run(
            analyze_sentiment("Bitcoin steigt auf neues Allzeithoch mit Genehmigung der BaFin")
        )
        assert isinstance(result, dict)
        assert "label" in result
        assert "score" in result
        assert "scores" in result
        assert "method" in result

    def test_sentiment_to_score_range(self):
        """sentiment_to_score returns value between -1 and 1."""
        result = asyncio.run(
            analyze_sentiment("Die Regulierung ist ein großer Durchbruch für den Kryptomarkt")
        )
        score = sentiment_to_score(result)
        assert -1.0 <= score <= 1.0

    def test_analyze_sentiment_empty_text(self):
        """Empty text returns neutral with 'empty' method."""
        result = asyncio.run(
            analyze_sentiment("")
        )
        assert result["label"] == "neutral"
        assert result["method"] == "empty"

    def test_analyze_sentiment_language_override(self):
        """Language override is respected."""
        # Force English even though text looks German
        result = asyncio.run(
            analyze_sentiment("Die BaFin hat eine neue Verordnung erlassen", language="en")
        )
        # Should use English path (finbert or keyword fallback)
        assert result.get("language") in ("en", None) or result["method"] in ("finbert", "keyword")


class TestGermanKeywordPresence:
    """Verify German keywords are in the word lists."""

    def test_positive_words_contain_german(self):
        """POSITIVE_WORDS contains German financial terms."""
        german_positive = {"genehmigung", "zulassung", "lizenz", "kaufempfehlung"}
        assert german_positive.issubset(set(POSITIVE_WORDS))

    def test_negative_words_contain_german(self):
        """NEGATIVE_WORDS contains German financial terms."""
        german_negative = {"bußgeld", "regulierungsrisiko", "marktmanipulation", "kursverfall"}
        assert german_negative.issubset(set(NEGATIVE_WORDS))
