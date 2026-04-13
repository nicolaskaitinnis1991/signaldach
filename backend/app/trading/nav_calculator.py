"""NAV Calculator -- Daily Net Asset Value calculation for the fund.

NAV = Sum of all position market values + Cash
Tracks historical NAV for performance reporting.
Calculates management fees and performance fees.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database import get_db
from app.trading.paper_engine import get_paper_portfolio

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NAV Calculation
# ---------------------------------------------------------------------------


def calculate_nav(portfolio_id: str = "default") -> dict:
    """Calculate the current NAV for a portfolio.

    Returns:
        Dict with nav, positions_value, cash, and timestamp.
    """
    portfolio = get_paper_portfolio()

    positions_value = sum(p.market_value for p in portfolio.positions.values())
    cash = portfolio.cash
    nav = positions_value + cash

    return {
        "nav": round(nav, 2),
        "positions_value": round(positions_value, 2),
        "cash": round(cash, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# NAV Snapshots (persistence)
# ---------------------------------------------------------------------------


def record_nav_snapshot(portfolio_id: str = "default") -> dict:
    """Save the current NAV to the database for historical tracking.

    This is designed to be called daily (e.g. by the scheduler at 16:00 UTC).
    Uses UNIQUE(portfolio_id, snapshot_date) to prevent duplicates.

    Returns:
        The snapshot data that was recorded.
    """
    nav_data = calculate_nav(portfolio_id)
    portfolio = get_paper_portfolio()

    # Get or initialize high water mark from portfolio state
    hwm = portfolio._high_water_mark

    # Calculate fees based on current state
    fees = calculate_all_fees(portfolio_id)

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    snapshot = {
        "portfolio_id": portfolio_id,
        "nav": nav_data["nav"],
        "positions_value": nav_data["positions_value"],
        "cash": nav_data["cash"],
        "management_fee": fees.get("management_fee", {}).get("daily_fee", 0.0),
        "performance_fee": fees.get("performance_fee", {}).get("performance_fee", 0.0),
        "high_water_mark": hwm,
        "snapshot_date": snapshot_date,
    }

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT OR REPLACE INTO nav_snapshots
                   (portfolio_id, nav, positions_value, cash,
                    management_fee, performance_fee, high_water_mark, snapshot_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot["portfolio_id"],
                    snapshot["nav"],
                    snapshot["positions_value"],
                    snapshot["cash"],
                    snapshot["management_fee"],
                    snapshot["performance_fee"],
                    snapshot["high_water_mark"],
                    snapshot["snapshot_date"],
                ),
            )
        logger.info("NAV snapshot recorded: %.2f on %s", snapshot["nav"], snapshot_date)
    except Exception as exc:
        logger.warning("Failed to record NAV snapshot: %s", exc)

    # Audit trail
    try:
        from app.audit import log_fund
        log_fund("nav_snapshot", detail=snapshot)
    except Exception:
        pass

    return snapshot


def get_nav_history(days: int = 30, portfolio_id: str = "default") -> list[dict]:
    """Get historical NAV snapshots for the last N days.

    Returns:
        List of snapshot dicts sorted by date ascending.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT portfolio_id, nav, positions_value, cash,
                          management_fee, performance_fee, high_water_mark,
                          snapshot_date, created_at
                   FROM nav_snapshots
                   WHERE portfolio_id = ?
                   ORDER BY snapshot_date DESC
                   LIMIT ?""",
                (portfolio_id, days),
            )
            rows = cur.fetchall()
            return [dict(row) for row in reversed(rows)]
    except Exception as exc:
        logger.warning("Failed to get NAV history: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Fee Calculations
# ---------------------------------------------------------------------------


def calculate_management_fee(aum: float, annual_rate: float = 0.02) -> dict:
    """Calculate management fee based on AUM and annual rate.

    Standard fund management fee: 2% annual on AUM.
    Charged daily (divided by 365).

    Args:
        aum: Assets Under Management (total NAV).
        annual_rate: Annual management fee rate (default 2%).

    Returns:
        Dict with annual_rate, daily_fee, monthly_fee.
    """
    daily_fee = (aum * annual_rate) / 365.0
    monthly_fee = (aum * annual_rate) / 12.0

    return {
        "annual_rate": annual_rate,
        "daily_fee": round(daily_fee, 2),
        "monthly_fee": round(monthly_fee, 2),
        "annual_fee": round(aum * annual_rate, 2),
        "aum": round(aum, 2),
    }


def calculate_performance_fee(
    current_nav: float,
    high_water_mark: float,
    fee_rate: float = 0.20,
) -> dict:
    """Calculate performance fee using high-water mark model.

    Performance fee is only charged on profits ABOVE the high-water mark.
    Standard: 20% of profits above HWM.

    Args:
        current_nav: Current Net Asset Value.
        high_water_mark: Previous highest NAV.
        fee_rate: Performance fee rate (default 20%).

    Returns:
        Dict with fee_rate, hwm, profit_above_hwm, performance_fee, new_hwm.
    """
    profit_above_hwm = max(0.0, current_nav - high_water_mark)
    performance_fee = profit_above_hwm * fee_rate
    new_hwm = max(current_nav, high_water_mark)

    return {
        "fee_rate": fee_rate,
        "hwm": round(high_water_mark, 2),
        "current_nav": round(current_nav, 2),
        "profit_above_hwm": round(profit_above_hwm, 2),
        "performance_fee": round(performance_fee, 2),
        "new_hwm": round(new_hwm, 2),
    }


def calculate_all_fees(portfolio_id: str = "default") -> dict:
    """Calculate all fees for a portfolio -- combined summary.

    Returns:
        Dict with management_fee, performance_fee, and total_fees.
    """
    nav_data = calculate_nav(portfolio_id)
    portfolio = get_paper_portfolio()
    hwm = portfolio._high_water_mark

    mgmt = calculate_management_fee(nav_data["nav"])
    perf = calculate_performance_fee(nav_data["nav"], hwm)

    return {
        "portfolio_id": portfolio_id,
        "nav": nav_data["nav"],
        "management_fee": mgmt,
        "performance_fee": perf,
        "total_daily_fees": round(mgmt["daily_fee"] + perf["performance_fee"], 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
