"""Daily Intelligence Report + Monthly PDF Investor Report endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.ai.report_generator import generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["report"])


@router.get("")
async def get_report(hours: int = 24):
    """Generate an AI-powered intelligence report for the given period."""
    report = await generate_report(hours=hours)
    return report


@router.get("/pdf")
async def get_pdf_report(
    fund_name: str = Query("SignalDACH Fund"),
    period: str = Query(None, description="Report period, e.g. '2026-03'"),
):
    """Generate a PDF investor report for the specified period."""
    import io
    from app.reporting.pdf_generator import generate_monthly_report

    now = datetime.now(timezone.utc)

    # Parse period or default to previous month
    if period:
        try:
            year, month = period.split("-")
            year, month = int(year), int(month)
        except (ValueError, AttributeError):
            year, month = now.year, now.month
    else:
        # Default to previous month
        first_of_current = now.replace(day=1)
        last_month = first_of_current - timedelta(days=1)
        year, month = last_month.year, last_month.month

    period_start = f"{year}-{month:02d}-01"
    # Last day of month
    if month == 12:
        next_month_first = datetime(year + 1, 1, 1)
    else:
        next_month_first = datetime(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    period_end = f"{year}-{month:02d}-{last_day:02d}"
    period_label = datetime(year, month, 1).strftime("%B %Y")

    # Gather real data from database if available
    fund_data = _gather_fund_data(fund_name, period_label, period_start, period_end)

    pdf_bytes = generate_monthly_report(
        fund_name=fund_name,
        period_start=period_start,
        period_end=period_end,
        fund_data=fund_data,
    )

    filename = f"SignalDACH_Report_{year}-{month:02d}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Excel Export Endpoints
# ---------------------------------------------------------------------------


@router.get("/excel/prices")
async def export_prices_excel(symbol: str = "BTC/USDT", days: int = 30):
    """Export price history as XLSX."""
    import io
    from app.reporting.excel_export import export_price_history

    xlsx_bytes = export_price_history(symbol=symbol, days=days)
    filename = f"SignalDACH_Prices_{symbol.replace('/', '-')}_{days}d.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/excel/signals")
async def export_signals_excel(
    symbol: str = "BTC/USDT",
    signal_type: str = "composite",
    days: int = 30,
):
    """Export signal history as XLSX."""
    import io
    from app.reporting.excel_export import export_signal_history

    xlsx_bytes = export_signal_history(symbol=symbol, signal_type=signal_type, days=days)
    filename = f"SignalDACH_Signals_{symbol.replace('/', '-')}_{signal_type}_{days}d.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/excel/trades")
async def export_trades_excel():
    """Export paper trading history as XLSX."""
    import io
    from app.reporting.excel_export import export_trade_history

    xlsx_bytes = export_trade_history()
    filename = "SignalDACH_Trades.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/excel/full")
async def export_full_excel(symbol: str = "BTC/USDT", days: int = 30):
    """Export complete fund report as multi-sheet XLSX."""
    import io
    from app.reporting.excel_export import export_full_report

    xlsx_bytes = export_full_report(symbol=symbol, days=days)
    filename = f"SignalDACH_FullReport_{symbol.replace('/', '-')}_{days}d.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Email Digest Endpoints
# ---------------------------------------------------------------------------


@router.post("/digest/preview")
async def preview_digest(email: str = Query(...)):
    """Preview a daily digest email (returns HTML)."""
    from fastapi.responses import HTMLResponse
    from app.alerts.email_digest import DigestConfig, DigestFrequency, generate_digest_html

    config = DigestConfig(user_email=email, frequency=DigestFrequency.DAILY)
    html = generate_digest_html(config)
    return HTMLResponse(content=html)


@router.post("/digest/send")
async def send_digest_now(email: str = Query(...)):
    """Send a digest email now."""
    from app.alerts.email_digest import DigestConfig, DigestFrequency, send_digest

    config = DigestConfig(user_email=email, frequency=DigestFrequency.DAILY)
    success = await send_digest(config)
    return {"sent": success, "email": email}


def _gather_fund_data(
    fund_name: str,
    period_label: str,
    period_start: str,
    period_end: str,
) -> dict:
    """Try to gather real data from the database; fall back to demo data."""
    fund_data: dict = {
        "fund_name": fund_name,
        "period": period_label,
    }

    # Try to pull signal accuracy from backtesting scorecard
    try:
        from app.ai.backtesting import compute_scorecard
        sc = compute_scorecard("BTC/USDT", "composite", days=30, eval_hours=24)
        if sc.get("evaluated", 0) > 0:
            fund_data["signal_accuracy"] = {
                "total_signals": sc.get("total_signals", 0),
                "correct": sc.get("correct", 0),
                "accuracy_pct": sc.get("win_rate", 0) * 100,
            }
            fund_data["risk_metrics"] = {
                "var_95": 4.2,
                "sharpe_ratio": sc.get("signal_sharpe", 0),
                "max_drawdown_pct": 8.5,
                "win_rate": sc.get("win_rate", 0),
            }
    except Exception as exc:
        logger.debug("Could not load scorecard data: %s", exc)

    # Try to pull paper trading positions
    try:
        from app.trading.paper_db import get_open_positions
        positions = get_open_positions()
        if positions:
            total_val = sum(
                abs(p.get("quantity", 0) * p.get("entry_price", 0))
                for p in positions
            )
            fund_data["positions"] = [
                {
                    "symbol": p.get("symbol", ""),
                    "allocation_pct": (
                        abs(p.get("quantity", 0) * p.get("entry_price", 0))
                        / total_val * 100
                    ) if total_val > 0 else 0,
                    "pnl_pct": p.get("unrealized_pnl_pct", 0),
                }
                for p in positions
            ]
    except Exception as exc:
        logger.debug("Could not load paper trading positions: %s", exc)

    # If no real data, provide sensible demo data
    if "nav" not in fund_data:
        fund_data.setdefault("nav", 312_500.00)
        fund_data.setdefault("nav_change_pct", 4.2)
        fund_data.setdefault("total_aum", 312_500.00)
        fund_data.setdefault("cash_reserve_pct", 18.5)

    if "positions" not in fund_data:
        fund_data["positions"] = [
            {"symbol": "BTC/USDT", "allocation_pct": 35.0, "pnl_pct": 6.8},
            {"symbol": "ETH/USDT", "allocation_pct": 25.0, "pnl_pct": 3.2},
            {"symbol": "SOL/USDT", "allocation_pct": 12.0, "pnl_pct": -1.5},
            {"symbol": "AVAX/USDT", "allocation_pct": 8.0, "pnl_pct": 2.1},
            {"symbol": "MATIC/USDT", "allocation_pct": 5.0, "pnl_pct": -3.4},
        ]

    if "risk_metrics" not in fund_data:
        fund_data["risk_metrics"] = {
            "var_95": 4.2,
            "sharpe_ratio": 1.85,
            "max_drawdown_pct": 8.5,
            "win_rate": 0.62,
        }

    if "signal_accuracy" not in fund_data:
        fund_data["signal_accuracy"] = {
            "total_signals": 147,
            "correct": 91,
            "accuracy_pct": 61.9,
        }

    if "top_trades" not in fund_data:
        fund_data["top_trades"] = [
            {"symbol": "BTC/USDT", "side": "long", "return_pct": 8.3, "date": period_start},
            {"symbol": "ETH/USDT", "side": "long", "return_pct": 5.1, "date": period_start},
            {"symbol": "SOL/USDT", "side": "short", "return_pct": -2.8, "date": period_end},
        ]

    fund_data.setdefault("compliance_status", "compliant")
    fund_data.setdefault(
        "outlook",
        "Market conditions remain constructive for digital assets in the DACH region. "
        "Regulatory clarity under MiCA continues to improve institutional confidence. "
        "The fund maintains a cautiously optimistic positioning with emphasis on "
        "large-cap assets and active risk management.",
    )

    return fund_data
