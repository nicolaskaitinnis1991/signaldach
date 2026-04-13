"""Email Digest — Daily/Weekly summary emails for investors.

Uses Resend API for sending. Generates HTML emails with:
- Market summary (top movers, total market cap change)
- Signal alerts (new signals above threshold)
- Fund performance (if positions exist)
- Risk alerts (any breaches)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class DigestFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class DigestConfig:
    user_email: str
    frequency: DigestFrequency = DigestFrequency.DAILY
    min_relevance: int = 7
    include_signals: bool = True
    include_market: bool = True
    include_fund: bool = True


# ---------------------------------------------------------------------------
# Data Gathering Helpers
# ---------------------------------------------------------------------------


def _get_market_summary(days: int = 1) -> dict[str, Any]:
    """Fetch recent price data for the market summary section."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result: dict[str, Any] = {"top_movers": [], "total_items": 0}

    try:
        with get_db() as conn:
            cur = conn.cursor()
            # Get latest price for each symbol
            cur.execute(
                """SELECT symbol, price, change_pct_24h, volume_24h
                   FROM price_ticks
                   WHERE ts >= ?
                   GROUP BY symbol
                   ORDER BY ts DESC""",
                [cutoff],
            )
            rows = cur.fetchall()
            movers = []
            for row in rows:
                r = dict(row) if not isinstance(row, dict) else row
                movers.append({
                    "symbol": r.get("symbol", ""),
                    "price": r.get("price", 0),
                    "change_pct": r.get("change_pct_24h", 0),
                    "volume": r.get("volume_24h", 0),
                })
            # Sort by absolute change
            movers.sort(key=lambda x: abs(x.get("change_pct", 0)), reverse=True)
            result["top_movers"] = movers[:5]

    except Exception as e:
        logger.debug("Market summary data unavailable: %s", e)

    # Count recent items
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM items WHERE published_at >= ?",
                [cutoff],
            )
            row = cur.fetchone()
            result["total_items"] = row[0] if row else 0
    except Exception:
        pass

    return result


def _get_recent_signals(days: int = 1, min_score: float = 0.6) -> list[dict]:
    """Fetch recent high-confidence signals."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    signals: list[dict] = []

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT ts, symbol, signal_type, score, confidence, reasoning
                   FROM signal_scores
                   WHERE ts >= ? AND score >= ?
                   ORDER BY score DESC
                   LIMIT 10""",
                [cutoff, min_score],
            )
            for row in cur.fetchall():
                r = dict(row) if not isinstance(row, dict) else row
                signals.append(r)
    except Exception as e:
        logger.debug("Signal data unavailable for digest: %s", e)

    return signals


def _get_fund_performance() -> dict[str, Any]:
    """Get current paper trading portfolio performance."""
    result: dict[str, Any] = {"positions": [], "total_pnl": 0.0}

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT symbol, side, quantity, entry_price, current_price,
                          unrealized_pnl_pct, status
                   FROM paper_positions
                   WHERE status = 'open'
                   ORDER BY symbol"""
            )
            positions = []
            total_pnl = 0.0
            for row in cur.fetchall():
                r = dict(row) if not isinstance(row, dict) else row
                positions.append(r)
                total_pnl += r.get("unrealized_pnl_pct", 0)

            result["positions"] = positions
            result["total_pnl"] = total_pnl
    except Exception as e:
        logger.debug("Fund performance data unavailable: %s", e)

    return result


def _get_high_relevance_items(days: int = 1, min_relevance: int = 7) -> list[dict]:
    """Get recent items above relevance threshold."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items: list[dict] = []

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT title, summary, category, relevance_score, urgency, url, published_at
                   FROM items
                   WHERE published_at >= ? AND relevance_score >= ?
                   ORDER BY relevance_score DESC
                   LIMIT 10""",
                [cutoff, min_relevance],
            )
            for row in cur.fetchall():
                r = dict(row) if not isinstance(row, dict) else row
                items.append(r)
    except Exception as e:
        logger.debug("Items data unavailable for digest: %s", e)

    return items


# ---------------------------------------------------------------------------
# HTML Generation
# ---------------------------------------------------------------------------


def generate_digest_html(config: DigestConfig) -> str:
    """Build HTML email body for the digest.

    Returns a complete HTML string ready for sending.
    """
    days = 1 if config.frequency == DigestFrequency.DAILY else 7
    period_label = "Daily" if config.frequency == DigestFrequency.DAILY else "Weekly"
    now = datetime.now(timezone.utc)

    # Gather data
    market = _get_market_summary(days=days) if config.include_market else {}
    signals = _get_recent_signals(days=days) if config.include_signals else []
    fund = _get_fund_performance() if config.include_fund else {}
    alerts = _get_high_relevance_items(days=days, min_relevance=config.min_relevance)

    # Build sections
    market_section = _build_market_section(market)
    signals_section = _build_signals_section(signals)
    fund_section = _build_fund_section(fund)
    alerts_section = _build_alerts_section(alerts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SignalDACH {period_label} Digest</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;">
        <tr>
            <td align="center" style="padding:20px 0;">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color:#1e293b;padding:24px 32px;">
                            <h1 style="color:#ffffff;margin:0;font-size:22px;">SignalDACH</h1>
                            <p style="color:#94a3b8;margin:4px 0 0 0;font-size:13px;">
                                {period_label} Intelligence Digest &mdash; {now.strftime('%B %d, %Y')}
                            </p>
                        </td>
                    </tr>

                    <!-- Market Summary -->
                    {market_section}

                    <!-- Signals -->
                    {signals_section}

                    <!-- Fund Performance -->
                    {fund_section}

                    <!-- High-Priority Alerts -->
                    {alerts_section}

                    <!-- CTA Button -->
                    <tr>
                        <td style="padding:24px 32px;text-align:center;">
                            <a href="https://app.signaldach.com/dashboard"
                               style="display:inline-block;background-color:#3b82f6;color:#ffffff;
                                      text-decoration:none;padding:12px 32px;border-radius:6px;
                                      font-weight:bold;font-size:14px;">
                                View Dashboard
                            </a>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;">
                            <p style="color:#94a3b8;font-size:11px;margin:0;text-align:center;">
                                SignalDACH &mdash; AI-Powered Crypto Market Intelligence for DACH
                                <br>
                                <a href="#unsubscribe" style="color:#64748b;text-decoration:underline;">
                                    Unsubscribe
                                </a>
                                &nbsp;&middot;&nbsp;
                                <a href="https://app.signaldach.com/settings" style="color:#64748b;text-decoration:underline;">
                                    Email Preferences
                                </a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    return html


def _build_market_section(market: dict) -> str:
    """Build the market summary HTML section."""
    movers = market.get("top_movers", [])
    total_items = market.get("total_items", 0)

    if not movers and total_items == 0:
        return """<tr><td style="padding:20px 32px;">
            <h2 style="color:#1e293b;font-size:16px;margin:0 0 8px 0;">Market Summary</h2>
            <p style="color:#64748b;font-size:13px;">No market data available for this period.</p>
        </td></tr>"""

    rows_html = ""
    for m in movers:
        change = m.get("change_pct", 0)
        color = "#22c55e" if change >= 0 else "#ef4444"
        sign = "+" if change >= 0 else ""
        price = m.get("price", 0)
        rows_html += f"""<tr>
            <td style="padding:6px 0;font-size:13px;color:#1e293b;">{m.get('symbol', '')}</td>
            <td style="padding:6px 0;font-size:13px;color:#1e293b;text-align:right;">${price:,.2f}</td>
            <td style="padding:6px 0;font-size:13px;color:{color};text-align:right;font-weight:bold;">{sign}{change:.2f}%</td>
        </tr>"""

    return f"""<tr><td style="padding:20px 32px;">
        <h2 style="color:#1e293b;font-size:16px;margin:0 0 12px 0;">Market Summary</h2>
        <p style="color:#64748b;font-size:12px;margin:0 0 8px 0;">{total_items} new intelligence items</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr style="border-bottom:1px solid #e2e8f0;">
                <th style="text-align:left;padding:6px 0;font-size:12px;color:#64748b;">Asset</th>
                <th style="text-align:right;padding:6px 0;font-size:12px;color:#64748b;">Price</th>
                <th style="text-align:right;padding:6px 0;font-size:12px;color:#64748b;">24h Change</th>
            </tr>
            {rows_html}
        </table>
    </td></tr>"""


def _build_signals_section(signals: list[dict]) -> str:
    """Build the signals HTML section."""
    if not signals:
        return """<tr><td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
            <h2 style="color:#1e293b;font-size:16px;margin:0 0 8px 0;">Signal Alerts</h2>
            <p style="color:#64748b;font-size:13px;">No notable signals in this period.</p>
        </td></tr>"""

    rows_html = ""
    for s in signals:
        score = s.get("score", 0)
        color = "#22c55e" if score >= 0.7 else "#f59e0b" if score >= 0.4 else "#ef4444"
        rows_html += f"""<tr>
            <td style="padding:6px 0;font-size:13px;color:#1e293b;">{s.get('symbol', '')}</td>
            <td style="padding:6px 0;font-size:13px;color:#64748b;">{s.get('signal_type', '')}</td>
            <td style="padding:6px 0;font-size:13px;color:{color};text-align:right;font-weight:bold;">{score:.2f}</td>
        </tr>"""

    return f"""<tr><td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
        <h2 style="color:#1e293b;font-size:16px;margin:0 0 12px 0;">Signal Alerts</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr style="border-bottom:1px solid #e2e8f0;">
                <th style="text-align:left;padding:6px 0;font-size:12px;color:#64748b;">Symbol</th>
                <th style="text-align:left;padding:6px 0;font-size:12px;color:#64748b;">Type</th>
                <th style="text-align:right;padding:6px 0;font-size:12px;color:#64748b;">Score</th>
            </tr>
            {rows_html}
        </table>
    </td></tr>"""


def _build_fund_section(fund: dict) -> str:
    """Build the fund performance HTML section."""
    positions = fund.get("positions", [])
    total_pnl = fund.get("total_pnl", 0)

    if not positions:
        return """<tr><td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
            <h2 style="color:#1e293b;font-size:16px;margin:0 0 8px 0;">Fund Performance</h2>
            <p style="color:#64748b;font-size:13px;">No open positions.</p>
        </td></tr>"""

    pnl_color = "#22c55e" if total_pnl >= 0 else "#ef4444"
    pnl_sign = "+" if total_pnl >= 0 else ""

    rows_html = ""
    for p in positions:
        pnl = p.get("unrealized_pnl_pct", 0)
        c = "#22c55e" if pnl >= 0 else "#ef4444"
        s = "+" if pnl >= 0 else ""
        rows_html += f"""<tr>
            <td style="padding:6px 0;font-size:13px;color:#1e293b;">{p.get('symbol', '')}</td>
            <td style="padding:6px 0;font-size:13px;color:#64748b;">{p.get('side', '')}</td>
            <td style="padding:6px 0;font-size:13px;color:{c};text-align:right;">{s}{pnl:.2f}%</td>
        </tr>"""

    return f"""<tr><td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
        <h2 style="color:#1e293b;font-size:16px;margin:0 0 4px 0;">Fund Performance</h2>
        <p style="color:{pnl_color};font-size:14px;font-weight:bold;margin:0 0 12px 0;">
            Total PnL: {pnl_sign}{total_pnl:.2f}%
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr style="border-bottom:1px solid #e2e8f0;">
                <th style="text-align:left;padding:6px 0;font-size:12px;color:#64748b;">Symbol</th>
                <th style="text-align:left;padding:6px 0;font-size:12px;color:#64748b;">Side</th>
                <th style="text-align:right;padding:6px 0;font-size:12px;color:#64748b;">PnL %</th>
            </tr>
            {rows_html}
        </table>
    </td></tr>"""


def _build_alerts_section(alerts: list[dict]) -> str:
    """Build the high-priority alerts HTML section."""
    if not alerts:
        return """<tr><td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
            <h2 style="color:#1e293b;font-size:16px;margin:0 0 8px 0;">High-Priority Intelligence</h2>
            <p style="color:#64748b;font-size:13px;">No high-relevance items in this period.</p>
        </td></tr>"""

    items_html = ""
    for a in alerts:
        urgency = a.get("urgency", "normal")
        badge_color = "#ef4444" if urgency == "breaking" else "#f59e0b" if urgency == "high" else "#64748b"
        url = a.get("url", "#")
        items_html += f"""<div style="padding:8px 0;border-bottom:1px solid #f1f5f9;">
            <span style="display:inline-block;background-color:{badge_color};color:#fff;
                         font-size:10px;padding:2px 6px;border-radius:3px;margin-right:6px;">
                {urgency.upper()}
            </span>
            <span style="font-size:11px;color:#94a3b8;">{a.get('category', '')}</span>
            <br>
            <a href="{url}" style="color:#1e293b;font-size:13px;text-decoration:none;font-weight:500;">
                {a.get('title', 'Untitled')}
            </a>
            <p style="color:#64748b;font-size:12px;margin:4px 0 0 0;">
                {(a.get('summary', '') or '')[:150]}
            </p>
        </div>"""

    return f"""<tr><td style="padding:20px 32px;border-top:1px solid #e2e8f0;">
        <h2 style="color:#1e293b;font-size:16px;margin:0 0 12px 0;">High-Priority Intelligence</h2>
        {items_html}
    </td></tr>"""


# ---------------------------------------------------------------------------
# Email Sending (Resend API)
# ---------------------------------------------------------------------------


async def _send_via_resend(to_email: str, subject: str, html: str) -> bool:
    """Send an email using the Resend API."""
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured, email not sent")
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": "SignalDACH <reports@signaldach.com>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                },
            )
            if resp.status_code == 200:
                logger.info("Digest email sent to %s", to_email)
                return True
            else:
                logger.error("Resend API error %d: %s", resp.status_code, resp.text)
                return False
    except Exception as e:
        logger.error("Failed to send digest email: %s", e)
        return False


async def send_digest(config: DigestConfig) -> bool:
    """Generate and send a digest email for a single user.

    Returns True if the email was sent successfully, False otherwise.
    """
    html = generate_digest_html(config)
    period_label = "Daily" if config.frequency == DigestFrequency.DAILY else "Weekly"
    now = datetime.now(timezone.utc)
    subject = f"SignalDACH {period_label} Digest - {now.strftime('%b %d, %Y')}"
    return await _send_via_resend(config.user_email, subject, html)


async def send_all_digests(frequency: DigestFrequency) -> dict:
    """Send digest emails to all configured users.

    Looks for users with digest preferences in the database.
    Returns a summary dict with sent/failed counts.
    """
    results = {"sent": 0, "failed": 0, "skipped": 0}

    # Try to load user emails from the database
    emails: list[str] = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT email FROM users WHERE is_active = 1")
            for row in cur.fetchall():
                r = dict(row) if not isinstance(row, dict) else row
                emails.append(r["email"])
    except Exception as e:
        logger.warning("Could not load users for digest: %s", e)

    if not emails:
        logger.info("No users configured for %s digest", frequency.value)
        results["skipped"] = 1
        return results

    for email in emails:
        config = DigestConfig(user_email=email, frequency=frequency)
        try:
            success = await send_digest(config)
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            logger.error("Digest send failed for %s: %s", email, e)
            results["failed"] += 1

    return results
