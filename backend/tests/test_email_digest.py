"""Tests for email digest functionality — no mocks, real HTML generation."""

import pytest

from app.alerts.email_digest import (
    DigestConfig,
    DigestFrequency,
    generate_digest_html,
    send_digest,
)


class TestDigestConfig:
    """Test DigestConfig defaults and creation."""

    def test_digest_config_defaults(self):
        config = DigestConfig(user_email="test@example.com")
        assert config.user_email == "test@example.com"
        assert config.frequency == DigestFrequency.DAILY
        assert config.min_relevance == 7
        assert config.include_signals is True
        assert config.include_market is True
        assert config.include_fund is True

    def test_digest_config_weekly(self):
        config = DigestConfig(
            user_email="test@example.com",
            frequency=DigestFrequency.WEEKLY,
            min_relevance=5,
        )
        assert config.frequency == DigestFrequency.WEEKLY
        assert config.min_relevance == 5


class TestGenerateDigestHtml:
    """Test HTML digest generation."""

    def test_generate_digest_html_returns_string(self):
        config = DigestConfig(user_email="test@example.com")
        html = generate_digest_html(config)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_digest_html_contains_signaldach(self):
        config = DigestConfig(user_email="test@example.com")
        html = generate_digest_html(config)
        assert "SignalDACH" in html

    def test_digest_html_contains_sections(self):
        config = DigestConfig(user_email="test@example.com")
        html = generate_digest_html(config)
        assert "Market Summary" in html
        assert "Signal Alerts" in html
        assert "Fund Performance" in html
        assert "View Dashboard" in html

    def test_digest_html_has_unsubscribe(self):
        config = DigestConfig(user_email="test@example.com")
        html = generate_digest_html(config)
        assert "Unsubscribe" in html

    def test_digest_html_weekly_label(self):
        config = DigestConfig(
            user_email="test@example.com",
            frequency=DigestFrequency.WEEKLY,
        )
        html = generate_digest_html(config)
        assert "Weekly" in html

    def test_digest_html_daily_label(self):
        config = DigestConfig(
            user_email="test@example.com",
            frequency=DigestFrequency.DAILY,
        )
        html = generate_digest_html(config)
        assert "Daily" in html


class TestSendDigest:
    """Test digest sending (without real API key)."""

    @pytest.mark.asyncio
    async def test_send_without_resend_key(self):
        """Without a Resend API key configured, send_digest returns False."""
        config = DigestConfig(user_email="test@example.com")
        result = await send_digest(config)
        assert result is False


class TestDigestPreviewEndpoint:
    """Test the preview API endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_digest_preview_endpoint(self, client):
        resp = client.post("/report/digest/preview?email=test@example.com")
        assert resp.status_code == 200
        assert "SignalDACH" in resp.text
        assert "text/html" in resp.headers.get("content-type", "")
