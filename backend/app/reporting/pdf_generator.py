"""PDF Report Generator — Monthly Investor Reports.

Generates institutional-grade PDF reports with:
- Fund performance summary
- Risk metrics (VaR, Sharpe, Max Drawdown)
- Signal accuracy scorecard
- Top trades of the month
- Asset allocation breakdown
- Regulatory compliance status
- AI-generated outlook
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color scheme
# ---------------------------------------------------------------------------
DARK_BLUE = (0x1E / 255, 0x29 / 255, 0x3B / 255)  # #1e293b
ACCENT_BLUE = (0x3B / 255, 0x82 / 255, 0xF6 / 255)  # #3b82f6
WHITE = (1, 1, 1)
LIGHT_GRAY = (0.95, 0.95, 0.95)
TEXT_DARK = (0.15, 0.15, 0.15)
TEXT_MUTED = (0.45, 0.45, 0.45)
GREEN = (0.13, 0.69, 0.30)
RED = (0.86, 0.20, 0.20)

# Hex versions for reportlab Color objects
DARK_BLUE_HEX = "#1e293b"
ACCENT_BLUE_HEX = "#3b82f6"
GREEN_HEX = "#22b04c"
RED_HEX = "#dc3333"


def _default_fund_data() -> dict[str, Any]:
    """Return minimal default fund data so generation never crashes."""
    return {
        "fund_name": "SignalDACH Fund",
        "period": datetime.now(timezone.utc).strftime("%B %Y"),
        "nav": 0.0,
        "nav_change_pct": 0.0,
        "total_aum": 0.0,
        "cash_reserve_pct": 0.0,
        "positions": [],
        "risk_metrics": {
            "var_95": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate": 0.0,
        },
        "signal_accuracy": {
            "total_signals": 0,
            "correct": 0,
            "accuracy_pct": 0.0,
        },
        "top_trades": [],
        "compliance_status": "compliant",
        "outlook": "No outlook available for this period.",
    }


def generate_monthly_report(
    fund_name: str,
    period_start: str,
    period_end: str,
    fund_data: dict[str, Any],
) -> bytes:
    """Generate a monthly investor PDF report.

    Parameters
    ----------
    fund_name:
        Display name of the fund.
    period_start / period_end:
        ISO date strings defining the reporting period.
    fund_data:
        Dict containing performance, risk, positions, etc.

    Returns
    -------
    bytes
        The generated PDF file content.
    """
    # Merge with defaults so missing keys don't crash
    data = {**_default_fund_data(), **fund_data}
    data["fund_name"] = fund_name or data["fund_name"]

    try:
        return _generate_reportlab_pdf(data, period_start, period_end)
    except ImportError:
        logger.warning("reportlab not installed — falling back to text-based report")
        return _generate_text_fallback(data, period_start, period_end)


# ---------------------------------------------------------------------------
# reportlab-based PDF generation
# ---------------------------------------------------------------------------


def _generate_reportlab_pdf(
    data: dict[str, Any],
    period_start: str,
    period_end: str,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )

    buf = io.BytesIO()
    page_w, page_h = A4

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
        title=f"{data['fund_name']} — Monthly Report",
        author="SignalDACH",
    )

    # Styles ----------------------------------------------------------------
    styles = getSampleStyleSheet()

    s_title = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor(DARK_BLUE_HEX),
        spaceAfter=4 * mm,
    )
    s_subtitle = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=8 * mm,
    )
    s_section = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor(ACCENT_BLUE_HEX),
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        borderWidth=0,
        borderPadding=0,
    )
    s_body = ParagraphStyle(
        "BodyText2",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1e293b"),
        leading=14,
    )
    s_small = ParagraphStyle(
        "SmallText",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#94a3b8"),
    )
    s_metric_value = ParagraphStyle(
        "MetricValue",
        parent=styles["Normal"],
        fontSize=18,
        textColor=colors.HexColor(DARK_BLUE_HEX),
        alignment=TA_CENTER,
        leading=22,
    )
    s_metric_label = ParagraphStyle(
        "MetricLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
    )

    # Helpers ---------------------------------------------------------------
    col_dark = colors.HexColor(DARK_BLUE_HEX)
    col_accent = colors.HexColor(ACCENT_BLUE_HEX)
    col_light_bg = colors.HexColor("#f1f5f9")
    col_white = colors.white

    def _fmt_pct(val: float) -> str:
        prefix = "+" if val > 0 else ""
        return f"{prefix}{val:.2f}%"

    def _fmt_currency(val: float) -> str:
        if val >= 1_000_000:
            return f"EUR {val / 1_000_000:,.2f}M"
        if val >= 1_000:
            return f"EUR {val / 1_000:,.1f}K"
        return f"EUR {val:,.2f}"

    def _color_pct(val: float) -> str:
        c = GREEN_HEX if val >= 0 else RED_HEX
        return f'<font color="{c}">{_fmt_pct(val)}</font>'

    def _metric_cell(value_text: str, label_text: str) -> list:
        return [
            Paragraph(value_text, s_metric_value),
            Paragraph(label_text, s_metric_label),
        ]

    generated_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build story -----------------------------------------------------------
    story: list = []

    # --- Header ---
    story.append(Paragraph(data["fund_name"], s_title))
    story.append(Paragraph(
        f"Monthly Investor Report  |  {data.get('period', '')}  |  Generated {generated_ts}",
        s_subtitle,
    ))

    # --- Section 1: Performance Summary ---
    story.append(Paragraph("1. Performance Summary", s_section))

    nav_change = data.get("nav_change_pct", 0)
    perf_data = [
        ["Metric", "Value"],
        ["Net Asset Value (NAV)", _fmt_currency(data.get("nav", 0))],
        ["Monthly Return", _color_pct(nav_change)],
        ["Total AUM", _fmt_currency(data.get("total_aum", 0))],
        ["Cash Reserve", f"{data.get('cash_reserve_pct', 0):.1f}%"],
    ]
    perf_table = Table(perf_data, colWidths=[80 * mm, 80 * mm])
    perf_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), col_dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), col_white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("BACKGROUND", (0, 1), (-1, -1), col_light_bg),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [col_white, col_light_bg]),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(perf_table)
    story.append(Spacer(1, 4 * mm))

    # --- Section 2: Risk Metrics (2x2 grid) ---
    story.append(Paragraph("2. Risk Metrics", s_section))

    rm = data.get("risk_metrics", {})
    risk_grid = [
        [
            _metric_cell(f"{rm.get('var_95', 0):.2f}%", "Value at Risk (95%)"),
            _metric_cell(f"{rm.get('sharpe_ratio', 0):.2f}", "Sharpe Ratio"),
        ],
        [
            _metric_cell(f"{rm.get('max_drawdown_pct', 0):.2f}%", "Max Drawdown"),
            _metric_cell(f"{rm.get('win_rate', 0) * 100:.1f}%", "Win Rate"),
        ],
    ]
    # Flatten the nested lists into proper cells using inner tables
    flat_grid = []
    for row in risk_grid:
        flat_row = []
        for cell_items in row:
            inner = Table([[item] for item in cell_items], colWidths=[70 * mm])
            inner.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            flat_row.append(inner)
        flat_grid.append(flat_row)

    risk_table = Table(flat_grid, colWidths=[80 * mm, 80 * mm])
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), col_light_bg),
        ("BOX", (0, 0), (-1, -1), 1, col_accent),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 4 * mm))

    # --- Section 3: Portfolio Allocation ---
    story.append(Paragraph("3. Portfolio Allocation", s_section))

    positions = data.get("positions", [])
    if positions:
        pos_header = ["Symbol", "Allocation %", "P&L %"]
        pos_rows = [pos_header]
        for p in positions:
            pos_rows.append([
                p.get("symbol", ""),
                f"{p.get('allocation_pct', 0):.1f}%",
                _color_pct(p.get("pnl_pct", 0)),
            ])
        pos_table = Table(pos_rows, colWidths=[60 * mm, 50 * mm, 50 * mm])
        pos_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), col_dark),
            ("TEXTCOLOR", (0, 0), (-1, 0), col_white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [col_white, col_light_bg]),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(pos_table)
    else:
        story.append(Paragraph("No positions held during this period.", s_body))
    story.append(Spacer(1, 4 * mm))

    # --- Section 4: Signal Scorecard ---
    story.append(Paragraph("4. Signal Scorecard", s_section))

    sa = data.get("signal_accuracy", {})
    sig_data = [
        ["Metric", "Value"],
        ["Total Signals", str(sa.get("total_signals", 0))],
        ["Correct Signals", str(sa.get("correct", 0))],
        ["Accuracy", f"{sa.get('accuracy_pct', 0):.1f}%"],
    ]
    sig_table = Table(sig_data, colWidths=[80 * mm, 80 * mm])
    sig_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), col_dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), col_white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [col_white, col_light_bg]),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 4 * mm))

    # --- Section 5: Top Trades ---
    story.append(Paragraph("5. Top Trades", s_section))

    trades = data.get("top_trades", [])
    if trades:
        trade_header = ["Symbol", "Side", "Return %", "Date"]
        trade_rows = [trade_header]
        for t in trades:
            trade_rows.append([
                t.get("symbol", ""),
                t.get("side", "").upper(),
                _color_pct(t.get("return_pct", 0)),
                t.get("date", ""),
            ])
        trade_table = Table(trade_rows, colWidths=[40 * mm, 30 * mm, 40 * mm, 50 * mm])
        trade_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), col_dark),
            ("TEXTCOLOR", (0, 0), (-1, 0), col_white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [col_white, col_light_bg]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(trade_table)
    else:
        story.append(Paragraph("No trades executed during this period.", s_body))
    story.append(Spacer(1, 4 * mm))

    # --- Section 6: Compliance ---
    story.append(Paragraph("6. MiCA Compliance Status", s_section))

    compliance = data.get("compliance_status", "compliant")
    if compliance == "compliant":
        comp_text = (
            '<font color="#22b04c"><b>COMPLIANT</b></font> — '
            "The fund operates in full compliance with MiCA regulatory requirements."
        )
    else:
        comp_text = (
            '<font color="#dc3333"><b>REVIEW NEEDED</b></font> — '
            "One or more compliance items require attention. See details in the compliance dashboard."
        )
    story.append(Paragraph(comp_text, s_body))
    story.append(Spacer(1, 4 * mm))

    # --- Section 7: Outlook ---
    story.append(Paragraph("7. Market Outlook", s_section))
    outlook = data.get("outlook", "No outlook available.")
    story.append(Paragraph(outlook, s_body))

    # Footer drawing function -----------------------------------------------
    def _draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        # Footer line
        canvas_obj.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas_obj.setLineWidth(0.5)
        y_line = 18 * mm
        canvas_obj.line(20 * mm, y_line, page_w - 20 * mm, y_line)

        # Left: confidential notice
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor("#94a3b8"))
        canvas_obj.drawString(
            20 * mm, 13 * mm,
            "Confidential \u2014 For Authorized Investors Only",
        )
        # Center: generated timestamp
        canvas_obj.drawCentredString(
            page_w / 2, 13 * mm,
            f"Generated: {generated_ts}",
        )
        # Right: page number
        canvas_obj.drawRightString(
            page_w - 20 * mm, 13 * mm,
            f"Page {doc_obj.page}",
        )
        canvas_obj.restoreState()

    # Build the PDF ---------------------------------------------------------
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Text fallback (no reportlab)
# ---------------------------------------------------------------------------


def _generate_text_fallback(
    data: dict[str, Any],
    period_start: str,
    period_end: str,
) -> bytes:
    """Generate a simple text-based PDF-like report when reportlab is unavailable."""
    lines: list[str] = []
    generated_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append(f"%PDF-1.0")
    lines.append(f"% SignalDACH Text Fallback Report")
    lines.append("")
    lines.append("=" * 60)
    lines.append(f"  {data['fund_name']}")
    lines.append(f"  Monthly Investor Report  |  {data.get('period', '')}")
    lines.append(f"  Period: {period_start} to {period_end}")
    lines.append(f"  Generated: {generated_ts}")
    lines.append("=" * 60)
    lines.append("")

    # Performance
    lines.append("1. PERFORMANCE SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  NAV:            EUR {data.get('nav', 0):,.2f}")
    nav_change = data.get("nav_change_pct", 0)
    sign = "+" if nav_change >= 0 else ""
    lines.append(f"  Monthly Return: {sign}{nav_change:.2f}%")
    lines.append(f"  Total AUM:      EUR {data.get('total_aum', 0):,.2f}")
    lines.append(f"  Cash Reserve:   {data.get('cash_reserve_pct', 0):.1f}%")
    lines.append("")

    # Risk
    rm = data.get("risk_metrics", {})
    lines.append("2. RISK METRICS")
    lines.append("-" * 40)
    lines.append(f"  VaR (95%):      {rm.get('var_95', 0):.2f}%")
    lines.append(f"  Sharpe Ratio:   {rm.get('sharpe_ratio', 0):.2f}")
    lines.append(f"  Max Drawdown:   {rm.get('max_drawdown_pct', 0):.2f}%")
    lines.append(f"  Win Rate:       {rm.get('win_rate', 0) * 100:.1f}%")
    lines.append("")

    # Positions
    lines.append("3. PORTFOLIO ALLOCATION")
    lines.append("-" * 40)
    for p in data.get("positions", []):
        pnl = p.get("pnl_pct", 0)
        pnl_sign = "+" if pnl >= 0 else ""
        lines.append(
            f"  {p.get('symbol', ''):12s}  "
            f"Alloc: {p.get('allocation_pct', 0):5.1f}%  "
            f"P&L: {pnl_sign}{pnl:.2f}%"
        )
    if not data.get("positions"):
        lines.append("  No positions held.")
    lines.append("")

    # Signals
    sa = data.get("signal_accuracy", {})
    lines.append("4. SIGNAL SCORECARD")
    lines.append("-" * 40)
    lines.append(f"  Total Signals:  {sa.get('total_signals', 0)}")
    lines.append(f"  Correct:        {sa.get('correct', 0)}")
    lines.append(f"  Accuracy:       {sa.get('accuracy_pct', 0):.1f}%")
    lines.append("")

    # Top trades
    lines.append("5. TOP TRADES")
    lines.append("-" * 40)
    for t in data.get("top_trades", []):
        ret = t.get("return_pct", 0)
        ret_sign = "+" if ret >= 0 else ""
        lines.append(
            f"  {t.get('symbol', ''):12s}  "
            f"{t.get('side', '').upper():5s}  "
            f"Return: {ret_sign}{ret:.2f}%  "
            f"Date: {t.get('date', '')}"
        )
    if not data.get("top_trades"):
        lines.append("  No trades executed.")
    lines.append("")

    # Compliance
    lines.append("6. MiCA COMPLIANCE STATUS")
    lines.append("-" * 40)
    status = data.get("compliance_status", "compliant")
    lines.append(f"  Status: {status.upper()}")
    lines.append("")

    # Outlook
    lines.append("7. MARKET OUTLOOK")
    lines.append("-" * 40)
    lines.append(f"  {data.get('outlook', 'No outlook available.')}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("  Confidential - For Authorized Investors Only")
    lines.append("=" * 60)

    return "\n".join(lines).encode("utf-8")
