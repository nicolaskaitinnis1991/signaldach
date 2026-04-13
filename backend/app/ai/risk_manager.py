"""Fund Risk Manager — enforces risk limits and provides fund-level analytics.

Designed for MiCA-compliant crypto fund operations:
- Position limits (max per asset, max per sector)
- Drawdown circuit breaker (halt trading if fund drawdown exceeds threshold)
- Exposure monitoring (long/short, leverage)
- Daily risk report generation
- Regulatory capital adequacy check
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fund Configuration (defaults, overridable per-fund)
# ---------------------------------------------------------------------------

DEFAULT_RISK_LIMITS = {
    "max_position_pct": 25.0,       # Max 25% of fund in single asset
    "max_sector_pct": 40.0,         # Max 40% in one sector (DeFi, L1, L2, etc.)
    "max_drawdown_pct": 15.0,       # Circuit breaker at 15% drawdown
    "max_daily_loss_pct": 5.0,      # Stop loss per day
    "max_leverage": 1.0,            # No leverage by default (1x = spot only)
    "min_cash_reserve_pct": 10.0,   # Keep 10% in stables/fiat
    "max_correlation_exposure": 0.8, # Warn if assets too correlated
    "min_capital_eur": 125000,      # MiCA minimum for CASP (Art. 67)
}

SECTOR_MAP = {
    "BTC": "store_of_value",
    "ETH": "smart_contract_platform",
    "SOL": "smart_contract_platform",
    "BNB": "exchange_token",
    "XRP": "payment",
    "ADA": "smart_contract_platform",
    "DOT": "interoperability",
    "AVAX": "smart_contract_platform",
    "MATIC": "layer2",
    "LINK": "oracle",
    "UNI": "defi",
    "AAVE": "defi",
    "MKR": "defi",
    "CRV": "defi",
    "LDO": "liquid_staking",
    "ARB": "layer2",
    "OP": "layer2",
    "DOGE": "memecoin",
    "SHIB": "memecoin",
    "USDT": "stablecoin",
    "USDC": "stablecoin",
    "DAI": "stablecoin",
}


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class RiskCheck:
    """Result of a single risk check."""
    rule: str
    status: str  # "pass", "warn", "breach"
    current_value: float
    limit_value: float
    message: str
    severity: str = "info"  # "info", "warning", "critical"


@dataclass
class FundPosition:
    """A position in the fund."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    sector: str = ""

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        return ((self.current_price - self.entry_price) / self.entry_price * 100) if self.entry_price > 0 else 0


@dataclass
class FundState:
    """Current state of the fund."""
    positions: list[FundPosition]
    cash_usd: float = 0.0
    fund_name: str = "SignalDACH Fund"
    inception_date: str = ""
    high_water_mark: float = 0.0

    @property
    def total_value(self) -> float:
        return sum(p.market_value for p in self.positions) + self.cash_usd

    @property
    def total_pnl(self) -> float:
        return sum(p.pnl for p in self.positions)

    def allocation(self) -> dict[str, float]:
        """Percentage allocation per asset."""
        total = self.total_value
        if total <= 0:
            return {}
        result = {}
        for p in self.positions:
            sym = p.symbol.split("/")[0] if "/" in p.symbol else p.symbol
            result[sym] = (p.market_value / total) * 100
        result["CASH"] = (self.cash_usd / total) * 100
        return result

    def sector_allocation(self) -> dict[str, float]:
        """Percentage allocation per sector."""
        total = self.total_value
        if total <= 0:
            return {}
        sectors: dict[str, float] = {}
        for p in self.positions:
            sym = p.symbol.split("/")[0] if "/" in p.symbol else p.symbol
            sector = p.sector or SECTOR_MAP.get(sym, "other")
            sectors[sector] = sectors.get(sector, 0) + (p.market_value / total) * 100
        return sectors


# ---------------------------------------------------------------------------
# Risk Checks
# ---------------------------------------------------------------------------

def check_position_limits(fund: FundState, limits: dict | None = None) -> list[RiskCheck]:
    """Check if any position exceeds max allocation."""
    lim = limits or DEFAULT_RISK_LIMITS
    max_pct = lim["max_position_pct"]
    checks = []

    alloc = fund.allocation()
    for sym, pct in alloc.items():
        if sym == "CASH":
            continue
        if pct > max_pct:
            checks.append(RiskCheck(
                rule="max_position_pct",
                status="breach",
                current_value=round(pct, 2),
                limit_value=max_pct,
                message=f"{sym} allocation {pct:.1f}% exceeds max {max_pct}%",
                severity="critical",
            ))
        elif pct > max_pct * 0.8:
            checks.append(RiskCheck(
                rule="max_position_pct",
                status="warn",
                current_value=round(pct, 2),
                limit_value=max_pct,
                message=f"{sym} allocation {pct:.1f}% approaching limit {max_pct}%",
                severity="warning",
            ))

    return checks


def check_sector_concentration(fund: FundState, limits: dict | None = None) -> list[RiskCheck]:
    """Check sector concentration risk."""
    lim = limits or DEFAULT_RISK_LIMITS
    max_pct = lim["max_sector_pct"]
    checks = []

    sectors = fund.sector_allocation()
    for sector, pct in sectors.items():
        if pct > max_pct:
            checks.append(RiskCheck(
                rule="max_sector_pct",
                status="breach",
                current_value=round(pct, 2),
                limit_value=max_pct,
                message=f"Sector '{sector}' at {pct:.1f}% exceeds max {max_pct}%",
                severity="critical",
            ))
        elif pct > max_pct * 0.8:
            checks.append(RiskCheck(
                rule="max_sector_pct",
                status="warn",
                current_value=round(pct, 2),
                limit_value=max_pct,
                message=f"Sector '{sector}' at {pct:.1f}% approaching limit {max_pct}%",
                severity="warning",
            ))

    return checks


def check_cash_reserve(fund: FundState, limits: dict | None = None) -> list[RiskCheck]:
    """Ensure minimum cash/stablecoin reserve."""
    lim = limits or DEFAULT_RISK_LIMITS
    min_pct = lim["min_cash_reserve_pct"]

    total = fund.total_value
    if total <= 0:
        return []

    # Count stablecoins as cash equivalent
    stable_value = sum(
        p.market_value for p in fund.positions
        if SECTOR_MAP.get(p.symbol.split("/")[0], "") == "stablecoin"
    )
    cash_equivalent = fund.cash_usd + stable_value
    cash_pct = (cash_equivalent / total) * 100

    if cash_pct < min_pct:
        return [RiskCheck(
            rule="min_cash_reserve_pct",
            status="breach",
            current_value=round(cash_pct, 2),
            limit_value=min_pct,
            message=f"Cash reserve {cash_pct:.1f}% below minimum {min_pct}%",
            severity="critical",
        )]
    return []


def check_drawdown(fund: FundState, limits: dict | None = None) -> list[RiskCheck]:
    """Check if fund drawdown exceeds circuit breaker threshold."""
    lim = limits or DEFAULT_RISK_LIMITS
    max_dd = lim["max_drawdown_pct"]

    if fund.high_water_mark <= 0:
        return []

    current_dd = ((fund.high_water_mark - fund.total_value) / fund.high_water_mark) * 100
    if current_dd <= 0:
        return []  # At or above high water mark

    if current_dd > max_dd:
        return [RiskCheck(
            rule="max_drawdown_pct",
            status="breach",
            current_value=round(current_dd, 2),
            limit_value=max_dd,
            message=f"Fund drawdown {current_dd:.1f}% EXCEEDS circuit breaker {max_dd}% — HALT TRADING",
            severity="critical",
        )]
    elif current_dd > max_dd * 0.7:
        return [RiskCheck(
            rule="max_drawdown_pct",
            status="warn",
            current_value=round(current_dd, 2),
            limit_value=max_dd,
            message=f"Fund drawdown {current_dd:.1f}% approaching circuit breaker {max_dd}%",
            severity="warning",
        )]

    return []


def check_capital_adequacy(fund: FundState, eur_rate: float = 1.08, limits: dict | None = None) -> list[RiskCheck]:
    """MiCA Art. 67: CASP must maintain minimum EUR 125K own funds."""
    lim = limits or DEFAULT_RISK_LIMITS
    min_eur = lim["min_capital_eur"]

    fund_value_eur = fund.total_value / eur_rate
    if fund_value_eur < min_eur:
        return [RiskCheck(
            rule="min_capital_eur",
            status="breach",
            current_value=round(fund_value_eur, 0),
            limit_value=min_eur,
            message=f"Fund value EUR {fund_value_eur:,.0f} below MiCA minimum EUR {min_eur:,.0f}",
            severity="critical",
        )]
    return []


# ---------------------------------------------------------------------------
# Full Risk Assessment
# ---------------------------------------------------------------------------

def run_risk_assessment(fund: FundState, limits: dict | None = None) -> dict:
    """Run all risk checks and produce a consolidated risk report."""
    all_checks: list[RiskCheck] = []
    all_checks.extend(check_position_limits(fund, limits))
    all_checks.extend(check_sector_concentration(fund, limits))
    all_checks.extend(check_cash_reserve(fund, limits))
    all_checks.extend(check_drawdown(fund, limits))
    all_checks.extend(check_capital_adequacy(fund, limits=limits))

    breaches = [c for c in all_checks if c.status == "breach"]
    warnings = [c for c in all_checks if c.status == "warn"]

    # Overall risk level
    if len(breaches) > 0:
        risk_level = "critical"
    elif len(warnings) > 0:
        risk_level = "elevated"
    else:
        risk_level = "normal"

    # Trading recommendation
    halt_trading = any(c.rule == "max_drawdown_pct" and c.status == "breach" for c in all_checks)

    return {
        "fund_name": fund.fund_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_value_usd": round(fund.total_value, 2),
        "total_pnl_usd": round(fund.total_pnl, 2),
        "risk_level": risk_level,
        "halt_trading": halt_trading,
        "breaches": len(breaches),
        "warnings": len(warnings),
        "checks": [
            {
                "rule": c.rule,
                "status": c.status,
                "current": c.current_value,
                "limit": c.limit_value,
                "message": c.message,
                "severity": c.severity,
            }
            for c in all_checks
        ],
        "allocation": fund.allocation(),
        "sector_allocation": fund.sector_allocation(),
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "market_value": round(p.market_value, 2),
                "pnl": round(p.pnl, 2),
                "pnl_pct": round(p.pnl_pct, 2),
                "sector": p.sector or SECTOR_MAP.get(p.symbol.split("/")[0], "other"),
            }
            for p in fund.positions
        ],
    }


# ---------------------------------------------------------------------------
# Position Sizing (Kelly Criterion variant)
# ---------------------------------------------------------------------------

def optimal_position_size(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    fund_value: float,
    max_position_pct: float = 25.0,
    kelly_fraction: float = 0.5,  # Half-Kelly for safety
) -> dict:
    """Calculate optimal position size using fractional Kelly Criterion.

    kelly_fraction=0.5 means we use half the Kelly-optimal size for safety.
    """
    if avg_loss_pct == 0 or win_rate <= 0:
        return {"recommended_pct": 0, "recommended_usd": 0, "method": "kelly", "note": "Insufficient data"}

    # Kelly: f* = (p * b - q) / b where b = avg_win/avg_loss, p = win_rate, q = 1-p
    b = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0
    q = 1 - win_rate
    kelly = ((win_rate * b) - q) / b if b > 0 else 0

    # Apply fraction and clamp
    recommended = max(0, min(kelly * kelly_fraction * 100, max_position_pct))

    return {
        "full_kelly_pct": round(kelly * 100, 2),
        "recommended_pct": round(recommended, 2),
        "recommended_usd": round(fund_value * recommended / 100, 2),
        "kelly_fraction": kelly_fraction,
        "max_position_pct": max_position_pct,
        "method": "half_kelly",
        "inputs": {
            "win_rate": win_rate,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
        },
    }
