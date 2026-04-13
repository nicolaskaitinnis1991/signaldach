"""Tests for PDF Investor Report Generator — no mocks, real generation."""

import pytest
import os

# Force SQLite test database BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///test_signaldach.db"
os.environ["SIGNALDACH_DATABASE_URL"] = "sqlite:///test_signaldach.db"
os.environ["SIGNALDACH_OPENAI_API_KEY"] = ""
os.environ["SIGNALDACH_AUTH_ENABLED"] = "false"

import app.database as db_module
db_module.DB_PATH = "test_signaldach.db"


@pytest.fixture(autouse=True)
def _init_db():
    db_module.DB_PATH = "test_signaldach.db"
    db_module.init_db()
    yield
    for suffix in ("", "-shm", "-wal"):
        try:
            os.remove(f"test_signaldach.db{suffix}")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_FUND_DATA = {
    "fund_name": "SignalDACH Fund",
    "period": "March 2026",
    "nav": 312_500.00,
    "nav_change_pct": 4.2,
    "total_aum": 312_500.00,
    "cash_reserve_pct": 18.5,
    "positions": [
        {"symbol": "BTC/USDT", "allocation_pct": 35.0, "pnl_pct": 6.8},
        {"symbol": "ETH/USDT", "allocation_pct": 25.0, "pnl_pct": 3.2},
        {"symbol": "SOL/USDT", "allocation_pct": 12.0, "pnl_pct": -1.5},
    ],
    "risk_metrics": {
        "var_95": 4.2,
        "sharpe_ratio": 1.85,
        "max_drawdown_pct": 8.5,
        "win_rate": 0.62,
    },
    "signal_accuracy": {
        "total_signals": 147,
        "correct": 91,
        "accuracy_pct": 61.9,
    },
    "top_trades": [
        {"symbol": "BTC/USDT", "side": "long", "return_pct": 8.3, "date": "2026-03-05"},
        {"symbol": "ETH/USDT", "side": "long", "return_pct": 5.1, "date": "2026-03-12"},
        {"symbol": "SOL/USDT", "side": "short", "return_pct": -2.8, "date": "2026-03-20"},
    ],
    "compliance_status": "compliant",
    "outlook": "Market conditions remain constructive for digital assets in the DACH region.",
}


# ---------------------------------------------------------------------------
# Tests: PDF Generator
# ---------------------------------------------------------------------------


class TestPdfGenerator:
    def test_generate_pdf_returns_bytes(self):
        from app.reporting.pdf_generator import generate_monthly_report

        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=SAMPLE_FUND_DATA,
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_starts_with_magic_bytes(self):
        from app.reporting.pdf_generator import generate_monthly_report

        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=SAMPLE_FUND_DATA,
        )
        assert result[:5] == b"%PDF-"

    def test_pdf_contains_fund_name(self):
        from app.reporting.pdf_generator import generate_monthly_report

        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=SAMPLE_FUND_DATA,
        )
        # Fund name should appear in the PDF content
        assert b"SignalDACH" in result

    def test_pdf_with_positions(self):
        from app.reporting.pdf_generator import generate_monthly_report

        data = {**SAMPLE_FUND_DATA, "positions": [
            {"symbol": "BTC/USDT", "allocation_pct": 50.0, "pnl_pct": 10.0},
            {"symbol": "ETH/USDT", "allocation_pct": 30.0, "pnl_pct": -5.0},
            {"symbol": "AVAX/USDT", "allocation_pct": 20.0, "pnl_pct": 2.5},
        ]}
        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=data,
        )
        assert result[:5] == b"%PDF-"
        assert len(result) > 100

    def test_pdf_with_empty_data(self):
        from app.reporting.pdf_generator import generate_monthly_report

        result = generate_monthly_report(
            fund_name="Empty Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data={},
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Should still produce a valid PDF (or text fallback starting with %PDF)
        assert result[:5] == b"%PDF-"

    def test_pdf_risk_metrics(self):
        """Risk metrics with custom values produce a valid PDF of reasonable size."""
        from app.reporting.pdf_generator import generate_monthly_report

        data = {**SAMPLE_FUND_DATA, "risk_metrics": {
            "var_95": 5.5,
            "sharpe_ratio": 2.10,
            "max_drawdown_pct": 12.3,
            "win_rate": 0.71,
        }}
        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=data,
        )
        assert result[:5] == b"%PDF-"
        # PDF with risk metrics should be multi-page / substantial
        assert len(result) > 500

    def test_pdf_with_review_needed_compliance(self):
        """Compliance status 'review_needed' generates a valid PDF."""
        from app.reporting.pdf_generator import generate_monthly_report

        data = {**SAMPLE_FUND_DATA, "compliance_status": "review_needed"}
        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=data,
        )
        assert result[:5] == b"%PDF-"
        # Both compliant and review_needed should produce valid output
        assert len(result) > 500

    def test_pdf_with_no_trades(self):
        """Empty trades list still produces a valid PDF."""
        from app.reporting.pdf_generator import generate_monthly_report

        data = {**SAMPLE_FUND_DATA, "top_trades": []}
        result = generate_monthly_report(
            fund_name="SignalDACH Fund",
            period_start="2026-03-01",
            period_end="2026-03-31",
            fund_data=data,
        )
        assert result[:5] == b"%PDF-"
        assert len(result) > 500


# ---------------------------------------------------------------------------
# Tests: API Endpoint
# ---------------------------------------------------------------------------


class TestPdfApiEndpoint:
    def test_pdf_api_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/report/pdf?fund_name=TestFund&period=2026-03")
        assert resp.status_code == 200

    def test_pdf_api_content_type(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/report/pdf?period=2026-03")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "SignalDACH_Report_2026-03.pdf" in resp.headers.get("content-disposition", "")

    def test_pdf_api_default_period(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/report/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
