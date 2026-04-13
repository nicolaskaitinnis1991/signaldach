"""Portfolio-aware Intelligence + Scenario Simulation.

Enables:
1. Portfolio tracking — positions, P&L, exposure
2. Risk metrics — VaR, max drawdown, Sharpe ratio
3. Scenario simulation — "What if BTC drops 30%?", "What if MiCA enforcement?"
4. Position-aware signals — signals weighted by portfolio exposure
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Portfolio data structures
# ---------------------------------------------------------------------------

@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0

    @property
    def value(self) -> float:
        return self.quantity * self.current_price

    @property
    def pnl(self) -> float:
        return self.quantity * (self.current_price - self.entry_price)

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * 100


@dataclass
class Portfolio:
    positions: list[Position] = field(default_factory=list)
    cash_usd: float = 0.0

    @property
    def total_value(self) -> float:
        return sum(p.value for p in self.positions) + self.cash_usd

    @property
    def total_pnl(self) -> float:
        return sum(p.pnl for p in self.positions)

    def get_allocation(self) -> dict[str, float]:
        """Get % allocation per asset."""
        total = self.total_value
        if total == 0:
            return {}
        result = {}
        for p in self.positions:
            result[p.symbol] = round(p.value / total * 100, 2)
        if self.cash_usd > 0:
            result["CASH"] = round(self.cash_usd / total * 100, 2)
        return result


# ---------------------------------------------------------------------------
# Price lookups
# ---------------------------------------------------------------------------

def _get_latest_price(symbol: str) -> Optional[float]:
    """Get latest price for a symbol from price_ticks."""
    with get_db() as conn:
        cur = conn.cursor()
        short = symbol.split("/")[0] if "/" in symbol else symbol
        cur.execute(
            "SELECT price FROM price_ticks WHERE symbol LIKE ? ORDER BY ts DESC LIMIT 1",
            (f"%{short}%",),
        )
        row = cur.fetchone()
        return dict(row)["price"] if row else None


def _get_price_history(symbol: str, days: int = 30) -> list[float]:
    """Get daily closing prices."""
    with get_db() as conn:
        cur = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        short = symbol.split("/")[0] if "/" in symbol else symbol
        cur.execute(
            "SELECT price FROM price_ticks WHERE symbol LIKE ? AND ts > ? ORDER BY ts ASC",
            (f"%{short}%", cutoff),
        )
        return [dict(r)["price"] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Risk Metrics
# ---------------------------------------------------------------------------

def compute_var(returns: list[float], confidence: float = 0.95) -> float:
    """Historical Value at Risk."""
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    idx = int((1 - confidence) * len(sorted_returns))
    return sorted_returns[max(0, idx)]


def compute_max_drawdown(prices: list[float]) -> float:
    """Maximum drawdown from peak."""
    if len(prices) < 2:
        return 0.0
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
    return max_dd


def compute_sharpe(returns: list[float], risk_free_rate: float = 0.04) -> float:
    """Annualized Sharpe ratio."""
    if len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns))
    if std_ret == 0:
        return 0.0
    daily_rf = risk_free_rate / 365
    return (mean_ret - daily_rf) / std_ret * math.sqrt(365)


def portfolio_risk_metrics(portfolio: Portfolio, days: int = 30) -> dict:
    """Compute risk metrics for a portfolio."""
    # Get returns for each position
    all_returns = []
    position_metrics = []

    for pos in portfolio.positions:
        prices = _get_price_history(pos.symbol, days=days)
        if len(prices) < 5:
            continue

        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices)) if prices[i-1] > 0]

        weight = pos.value / portfolio.total_value if portfolio.total_value > 0 else 0
        weighted_returns = [r * weight for r in returns]
        all_returns.extend(weighted_returns)

        position_metrics.append({
            "symbol": pos.symbol,
            "weight": round(weight * 100, 2),
            "var_95": round(compute_var(returns) * 100, 2),
            "max_drawdown": round(compute_max_drawdown(prices) * 100, 2),
            "sharpe": round(compute_sharpe(returns), 2),
            "volatility": round(
                math.sqrt(sum(r**2 for r in returns) / len(returns)) * math.sqrt(365) * 100, 2
            ) if returns else 0,
        })

    portfolio_var = compute_var(all_returns) if all_returns else 0
    portfolio_sharpe = compute_sharpe(all_returns) if all_returns else 0

    return {
        "total_value": round(portfolio.total_value, 2),
        "total_pnl": round(portfolio.total_pnl, 2),
        "allocation": portfolio.get_allocation(),
        "portfolio_var_95": round(portfolio_var * 100, 4),
        "portfolio_sharpe": round(portfolio_sharpe, 2),
        "positions": position_metrics,
        "period_days": days,
    }


# ---------------------------------------------------------------------------
# Scenario Simulation
# ---------------------------------------------------------------------------

def simulate_scenario(
    portfolio: Portfolio,
    scenarios: dict[str, float],
) -> dict:
    """Simulate portfolio impact under given price change scenarios.

    Args:
        portfolio: Current portfolio
        scenarios: {symbol: pct_change} e.g. {"BTC/USDT": -30, "ETH/USDT": -40}

    Returns portfolio value before/after with P&L impact.
    """
    before_value = portfolio.total_value
    after_positions = []

    for pos in portfolio.positions:
        short_sym = pos.symbol.split("/")[0] if "/" in pos.symbol else pos.symbol
        pct_change = None

        # Match scenario to position
        for sc_sym, sc_pct in scenarios.items():
            sc_short = sc_sym.split("/")[0] if "/" in sc_sym else sc_sym
            if sc_short.upper() == short_sym.upper():
                pct_change = sc_pct
                break

        if pct_change is None:
            # Estimate correlation-based impact for non-specified assets
            # Use BTC change as proxy (beta ~ 1.0 for most crypto)
            btc_change = scenarios.get("BTC/USDT", scenarios.get("BTC", 0))
            pct_change = btc_change * 0.8  # 80% beta assumption

        new_price = pos.current_price * (1 + pct_change / 100)
        after_positions.append({
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "before_price": pos.current_price,
            "after_price": round(new_price, 2),
            "before_value": round(pos.value, 2),
            "after_value": round(pos.quantity * new_price, 2),
            "impact": round(pos.quantity * (new_price - pos.current_price), 2),
            "change_pct": round(pct_change, 2),
        })

    after_value = sum(p["after_value"] for p in after_positions) + portfolio.cash_usd

    return {
        "scenario": scenarios,
        "before_value": round(before_value, 2),
        "after_value": round(after_value, 2),
        "total_impact": round(after_value - before_value, 2),
        "impact_pct": round((after_value - before_value) / before_value * 100, 2) if before_value > 0 else 0,
        "positions": after_positions,
    }


# Preset scenarios
PRESET_SCENARIOS = {
    "btc_crash_30": {"name": "BTC -30% Crash", "changes": {"BTC/USDT": -30, "ETH/USDT": -35}},
    "bull_run": {"name": "Bull Run +50%", "changes": {"BTC/USDT": 50, "ETH/USDT": 70}},
    "mica_enforcement": {"name": "MiCA Enforcement (stablecoin depegs)", "changes": {"BTC/USDT": -10, "ETH/USDT": -15}},
    "eth_flippening": {"name": "ETH Flippening", "changes": {"BTC/USDT": -5, "ETH/USDT": 100}},
    "black_swan": {"name": "Black Swan -50%", "changes": {"BTC/USDT": -50, "ETH/USDT": -60}},
    "stablecoin_crisis": {"name": "Stablecoin Crisis", "changes": {"BTC/USDT": -20, "ETH/USDT": -25}},
}
