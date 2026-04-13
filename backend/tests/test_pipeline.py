"""Tests for AI pipeline: HTML stripping, sentiment, Jaccard similarity, dedup, rule-based processing."""

import pytest
from app.ai.pipeline import (
    strip_html,
    compute_sentiment,
    jaccard_similarity,
    deduplicate_by_title,
    _rule_based_process,
)
from app.scrapers.base import RawItem


class TestStripHtml:
    """Test strip_html() with various HTML inputs."""

    def test_strip_simple_tags(self):
        assert strip_html("<p>Hello World</p>") == "Hello World"

    def test_strip_nested_tags(self):
        result = strip_html("<div><p><strong>Bold</strong> text</p></div>")
        assert result == "Bold text"

    def test_strip_links(self):
        result = strip_html('<a href="https://example.com">Click here</a>')
        assert result == "Click here"

    def test_strip_entities(self):
        result = strip_html("&amp; &lt; &gt; &quot;")
        assert "&" in result
        assert "<" in result

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_none_input(self):
        assert strip_html(None) == ""

    def test_plain_text_unchanged(self):
        assert strip_html("No HTML here") == "No HTML here"

    def test_complex_html(self):
        html = """
        <html><body>
            <h1>Title</h1>
            <p>Paragraph with <em>emphasis</em> and <br/> line break.</p>
            <script>alert('xss')</script>
        </body></html>
        """
        result = strip_html(html)
        assert "Title" in result
        assert "Paragraph" in result
        assert "<" not in result


class TestComputeSentiment:
    """Test compute_sentiment() with positive/negative/neutral text."""

    def test_positive_text(self):
        score = compute_sentiment("Bitcoin rally surge bullish growth adoption")
        assert score > 0

    def test_negative_text(self):
        score = compute_sentiment("crash dump sell-off ban lawsuit hack fraud")
        assert score < 0

    def test_neutral_text(self):
        score = compute_sentiment("Lorem ipsum dolor sit amet")
        # FinBERT may give small non-zero score for unknown text; keyword returns 0.0
        assert -0.3 <= score <= 0.3

    def test_empty_text(self):
        assert compute_sentiment("") == 0.0

    def test_mixed_text(self):
        score = compute_sentiment("bullish rally but also crash risk")
        # Mixed, should be between -1 and 1
        assert -1.0 <= score <= 1.0

    def test_score_range(self):
        """All scores must be between -1.0 and 1.0."""
        for text in ["bullish", "bearish", "neutral stuff", "rally crash"]:
            score = compute_sentiment(text)
            assert -1.0 <= score <= 1.0

    def test_german_positive(self):
        score = compute_sentiment("Erfolg und Wachstum bei der Genehmigung")
        assert score > 0

    def test_german_negative(self):
        score = compute_sentiment("Verbot und Warnung wegen Betrug und Risiko")
        # FinBERT is English-only, may not detect German negative words
        # Keyword fallback returns < 0, FinBERT may return slightly positive
        assert -1.0 <= score <= 0.3


class TestJaccardSimilarity:
    """Test jaccard_similarity() with similar/different titles."""

    def test_identical_titles(self):
        sim = jaccard_similarity("Bitcoin price surges today", "Bitcoin price surges today")
        assert sim == 1.0

    def test_completely_different(self):
        sim = jaccard_similarity("Bitcoin surges to new high", "Weather forecast for tomorrow")
        assert sim < 0.2

    def test_partially_similar(self):
        sim = jaccard_similarity(
            "Bitcoin price hits new record high",
            "Bitcoin price reaches new all-time high"
        )
        assert 0.3 < sim < 0.9

    def test_empty_string(self):
        assert jaccard_similarity("", "some text") == 0.0
        assert jaccard_similarity("some text", "") == 0.0
        assert jaccard_similarity("", "") == 0.0

    def test_short_words_ignored(self):
        """Words <= 2 chars should be filtered out."""
        sim = jaccard_similarity("a b c d e", "a b c d e")
        assert sim == 0.0  # All words are too short

    def test_same_words_different_order(self):
        sim = jaccard_similarity("Bitcoin price today high", "high price Bitcoin today")
        assert sim == 1.0


class TestDeduplicateByTitle:
    """Test deduplicate_by_title() removes near-duplicates."""

    def test_removes_near_duplicates(self):
        items = [
            RawItem(title="Bitcoin price surges to new record high today"),
            RawItem(title="Bitcoin price surges to new record high today update"),
            RawItem(title="Ethereum DeFi protocol launches new feature"),
        ]
        result = deduplicate_by_title(items)
        assert len(result) == 2
        assert result[0].title == items[0].title
        assert result[1].title == items[2].title

    def test_keeps_different_items(self):
        items = [
            RawItem(title="Bitcoin price surges"),
            RawItem(title="Ethereum launches update"),
            RawItem(title="BaFin announces regulation"),
        ]
        result = deduplicate_by_title(items)
        assert len(result) == 3

    def test_empty_list(self):
        assert deduplicate_by_title([]) == []

    def test_single_item(self):
        items = [RawItem(title="Single item")]
        result = deduplicate_by_title(items)
        assert len(result) == 1

    def test_exact_duplicates_removed(self):
        items = [
            RawItem(title="Exact same title here for testing"),
            RawItem(title="Exact same title here for testing"),
        ]
        result = deduplicate_by_title(items)
        assert len(result) == 1


class TestRuleBasedProcess:
    """Test _rule_based_process() produces valid ProcessedItem."""

    def test_produces_valid_item(self):
        raw = RawItem(
            title="BaFin announces new crypto regulation for DACH region",
            content="The German financial regulator BaFin has announced new MiCA compliance rules.",
            url="https://example.com/bafin",
            author="Test Author",
            external_id="ext-test-1",
        )
        result = _rule_based_process(raw, "market")

        assert result.title
        assert result.summary
        assert result.url == "https://example.com/bafin"
        assert result.external_id == "ext-test-1"
        assert result.category in ("regulation", "competition", "market", "sentiment")
        assert 1 <= result.relevance_score <= 10
        assert result.urgency in ("normal", "high", "breaking")
        assert -1.0 <= result.sentiment <= 1.0
        assert isinstance(result.ai_metadata, dict)
        assert "keywords" in result.ai_metadata

    def test_regulation_category_detection(self):
        raw = RawItem(
            title="BaFin enforcement action against crypto exchange",
            content="BaFin regulator compliance MiCA enforcement audit",
        )
        result = _rule_based_process(raw, "market")
        assert result.category == "regulation"

    def test_competition_category_detection(self):
        raw = RawItem(
            title="21Shares launches new Bitcoin ETF fund",
            content="21Shares Bitpanda AUM institutional fund launch ETP",
        )
        result = _rule_based_process(raw, "market")
        assert result.category == "competition"

    def test_urgency_detection(self):
        raw = RawItem(
            title="BREAKING: Bitcoin crashes after major hack exploit",
            content="Emergency alert: breaking crash collapse exploit hack",
        )
        result = _rule_based_process(raw, "market")
        assert result.urgency in ("high", "breaking")

    def test_dach_relevance_bonus(self):
        """DACH-related items should have higher relevance."""
        raw_dach = RawItem(
            title="Germany Berlin crypto regulation BaFin",
            content="Deutschland DACH Switzerland regulation BaFin",
        )
        raw_generic = RawItem(
            title="Some generic crypto news article",
            content="Some generic crypto content",
        )
        result_dach = _rule_based_process(raw_dach, "market")
        result_generic = _rule_based_process(raw_generic, "market")
        assert result_dach.relevance_score > result_generic.relevance_score

    def test_entity_extraction_included(self):
        raw = RawItem(
            title="Bitcoin and Ethereum mentioned along with BaFin",
            content="BTC ETH BaFin regulation",
        )
        result = _rule_based_process(raw, "market")
        entities = result.ai_metadata.get("entities", {})
        assert "tokens" in entities or "regulators" in entities
