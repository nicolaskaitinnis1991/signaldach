"""Tests for Excel export functionality — no mocks, real openpyxl workbooks."""

import io
import pytest
from openpyxl import load_workbook

from app.reporting.excel_export import (
    export_price_history,
    export_signal_history,
    export_trade_history,
    export_full_report,
)


class TestExportPriceHistory:
    """Test price history XLSX export."""

    def test_export_price_history_returns_bytes(self):
        result = export_price_history(symbol="BTC/USDT", days=30)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_price_xlsx_valid(self):
        """Exported bytes can be opened as a valid XLSX workbook."""
        result = export_price_history(symbol="BTC/USDT", days=30)
        wb = load_workbook(io.BytesIO(result))
        assert wb.active is not None
        ws = wb.active
        assert ws.title == "Price History"
        # Header row should exist
        assert ws.cell(row=1, column=1).value == "Timestamp"
        assert ws.cell(row=1, column=4).value == "Price (USD)"
        wb.close()


class TestExportSignalHistory:
    """Test signal history XLSX export."""

    def test_signal_export(self):
        result = export_signal_history(symbol="BTC/USDT", signal_type="composite", days=30)
        assert isinstance(result, bytes)
        assert len(result) > 0
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        assert ws.title == "Signal History"
        assert ws.cell(row=1, column=1).value == "Timestamp"
        assert ws.cell(row=1, column=4).value == "Score"
        wb.close()


class TestExportTradeHistory:
    """Test trade history XLSX export."""

    def test_trade_export(self):
        result = export_trade_history()
        assert isinstance(result, bytes)
        assert len(result) > 0
        wb = load_workbook(io.BytesIO(result))
        ws = wb.active
        assert ws.title == "Trade History"
        assert ws.cell(row=1, column=2).value == "Symbol"
        wb.close()


class TestExportFullReport:
    """Test multi-sheet XLSX export."""

    def test_full_report_has_sheets(self):
        result = export_full_report(symbol="BTC/USDT", days=30)
        assert isinstance(result, bytes)
        assert len(result) > 0
        wb = load_workbook(io.BytesIO(result))
        sheet_names = wb.sheetnames
        assert "Price History" in sheet_names
        assert "Signal History" in sheet_names
        assert "Trade History" in sheet_names
        assert "Portfolio Summary" in sheet_names
        assert len(sheet_names) == 4
        wb.close()

    def test_full_report_headers_styled(self):
        """Verify header cells have bold font and blue fill."""
        result = export_full_report(symbol="BTC/USDT", days=7)
        wb = load_workbook(io.BytesIO(result))
        ws = wb["Price History"]
        header_cell = ws.cell(row=1, column=1)
        assert header_cell.font.bold is True
        assert header_cell.fill.start_color.rgb is not None
        wb.close()


class TestExcelApiEndpoints:
    """Test the FastAPI endpoints for Excel export."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_excel_api_prices(self, client):
        resp = client.get("/report/excel/prices?symbol=BTC/USDT&days=7")
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")

    def test_excel_api_full(self, client):
        resp = client.get("/report/excel/full?symbol=BTC/USDT&days=7")
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")

    def test_content_type(self, client):
        resp = client.get("/report/excel/signals?symbol=BTC/USDT&signal_type=composite&days=7")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert ct == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_excel_trades_endpoint(self, client):
        resp = client.get("/report/excel/trades")
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")
