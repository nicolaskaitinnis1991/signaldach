"""Signal Scorecard & Backtesting Engine.

Tracks historical signal accuracy and provides performance metrics:
1. Signal Storage — stores every composite + agent signal in signal_scores
2. Outcome Evaluation — compares signal vs actual price movement after N hours
3. Scorecard — win rate, avg return, Sharpe, accuracy per agent
4. Backtesting — replay signals over historical data to measure strategy performance
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal Storage (into signal_scores table)
# ---------------------------------------------------------------------------

def store_signal(
    symbol: str,
    signal_type: str,
    score: float,
    confidence: float,
    components: dict | None = None,
    reasoning: str = "",
) -> None:
    """Persist a signal into signal_scores table."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO signal_scores (symbol, signal_type, score, confidence, components_json, reasoning) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                symbol,
                signal_type,
                round(score, 6),
                round(confidence, 4),
                json.dumps(components or {}),
                reasoning,
            ),
        )
        conn.commit()


def store_composite_signal(result_dict: dict) -> None:
    """Store a full composite signal (from get_market_signal) with all agent breakdowns."""
    symbol = result_dict.get("symbol", "BTC/USDT")

    # Store composite
    store_signal(
        symbol=symbol,
        signal_type="composite",
        score=result_dict.get("overall_score", 0.0),
        confidence=result_dict.get("confidence", 0.0),
        components={
            "signal": result_dict.get("overall_signal"),
            "key_drivers": result_dict.get("key_drivers", []),
            "risk_factors": result_dict.get("risk_factors", []),
        },
        reasoning=result_dict.get("reasoning", ""),
    )

    # Store individual agent signals
    for agent in result_dict.get("agents", []):
        store_signal(
            symbol=symbol,
            signal_type=agent.get("agent", "unknown"),
            score=agent.get("score", 0.0),
            confidence=agent.get("confidence", 0.0),
            reasoning=agent.get("reasoning", ""),
        )


# ---------------------------------------------------------------------------
# Outcome Evaluation
# ---------------------------------------------------------------------------

def _get_price_at(symbol: str, ts: str) -> Optional[float]:
    """Get closest price to a given timestamp."""
    with get_db() as conn:
        cur = conn.cursor()
        short = symbol.split("/")[0] if "/" in symbol else symbol
        # Get the closest price within 1 hour window
        cur.execute(
            "SELECT price FROM price_ticks "
            "WHERE symbol LIKE ? AND ts >= ? "
            "ORDER BY ts ASC LIMIT 1",
            (f"%{short}%", ts),
        )
        row = cur.fetchone()
        if row:
            return dict(row)["price"]

        # Fallback: closest before
        cur.execute(
            "SELECT price FROM price_ticks "
            "WHERE symbol LIKE ? AND ts <= ? "
            "ORDER BY ts DESC LIMIT 1",
            (f"%{short}%", ts),
        )
        row = cur.fetchone()
        return dict(row)["price"] if row else None


def evaluate_signal_outcome(
    signal_ts: str,
    symbol: str,
    signal_score: float,
    eval_hours: int = 24,
) -> Optional[dict]:
    """Evaluate a signal by comparing predicted direction vs actual price move.

    Returns:
        dict with actual_return, signal_correct, signal_score, etc.
        None if price data unavailable.
    """
    price_at_signal = _get_price_at(symbol, signal_ts)
    if price_at_signal is None or price_at_signal <= 0:
        return None

    # Parse timestamp and add eval_hours
    try:
        dt = datetime.fromisoformat(signal_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None

    eval_ts = (dt + timedelta(hours=eval_hours)).isoformat()
    price_after = _get_price_at(symbol, eval_ts)
    if price_after is None:
        return None

    actual_return = (price_after - price_at_signal) / price_at_signal
    predicted_direction = 1 if signal_score > 0.05 else (-1 if signal_score < -0.05 else 0)
    actual_direction = 1 if actual_return > 0.005 else (-1 if actual_return < -0.005 else 0)

    correct = (
        predicted_direction == actual_direction
        or predicted_direction == 0  # neutral is never "wrong"
    )

    return {
        "signal_ts": signal_ts,
        "eval_ts": eval_ts,
        "symbol": symbol,
        "signal_score": signal_score,
        "predicted_direction": predicted_direction,
        "price_at_signal": price_at_signal,
        "price_after": price_after,
        "actual_return_pct": round(actual_return * 100, 4),
        "actual_direction": actual_direction,
        "correct": correct,
        "eval_hours": eval_hours,
    }


# ---------------------------------------------------------------------------
# Signal Scorecard
# ---------------------------------------------------------------------------

def get_signal_history(
    symbol: str = "BTC/USDT",
    signal_type: str = "composite",
    days: int = 30,
    limit: int = 500,
) -> list[dict]:
    """Fetch historical signals from signal_scores."""
    with get_db() as conn:
        cur = conn.cursor()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cur.execute(
            "SELECT ts, symbol, signal_type, score, confidence, components_json, reasoning "
            "FROM signal_scores "
            "WHERE symbol = ? AND signal_type = ? AND ts > ? "
            "ORDER BY ts DESC LIMIT ?",
            (symbol, signal_type, cutoff, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def compute_scorecard(
    symbol: str = "BTC/USDT",
    signal_type: str = "composite",
    days: int = 30,
    eval_hours: int = 24,
) -> dict:
    """Compute a full performance scorecard for a signal type.

    Returns win rate, avg return when following signal, accuracy metrics, etc.
    """
    signals = get_signal_history(symbol, signal_type, days)
    if not signals:
        return {
            "symbol": symbol,
            "signal_type": signal_type,
            "period_days": days,
            "total_signals": 0,
            "message": "No signals found for this period",
        }

    evaluated = []
    for sig in signals:
        outcome = evaluate_signal_outcome(
            signal_ts=sig["ts"],
            symbol=symbol,
            signal_score=sig["score"],
            eval_hours=eval_hours,
        )
        if outcome:
            evaluated.append({**sig, **outcome})

    if not evaluated:
        return {
            "symbol": symbol,
            "signal_type": signal_type,
            "period_days": days,
            "total_signals": len(signals),
            "evaluated": 0,
            "message": "No price data available for evaluation",
        }

    # Metrics
    total = len(evaluated)
    correct = sum(1 for e in evaluated if e["correct"])
    win_rate = correct / total if total > 0 else 0

    # Returns when following signal direction
    returns_following = []
    for e in evaluated:
        if e["predicted_direction"] == 1:
            returns_following.append(e["actual_return_pct"])
        elif e["predicted_direction"] == -1:
            returns_following.append(-e["actual_return_pct"])  # Short = inverse return

    avg_return = sum(returns_following) / len(returns_following) if returns_following else 0
    positive_returns = [r for r in returns_following if r > 0]
    negative_returns = [r for r in returns_following if r < 0]

    # Profit factor
    gross_profit = sum(positive_returns) if positive_returns else 0
    gross_loss = abs(sum(negative_returns)) if negative_returns else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # Sharpe-like ratio on signal returns
    if len(returns_following) >= 2:
        mean_r = sum(returns_following) / len(returns_following)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns_following) / len(returns_following))
        signal_sharpe = (mean_r / std_r * math.sqrt(365 / max(1, eval_hours / 24))) if std_r > 0 else 0
    else:
        signal_sharpe = 0

    # Confidence calibration: are high-confidence signals more accurate?
    high_conf = [e for e in evaluated if e.get("confidence", 0) > 0.5]
    low_conf = [e for e in evaluated if e.get("confidence", 0) <= 0.5]
    high_conf_accuracy = sum(1 for e in high_conf if e["correct"]) / len(high_conf) if high_conf else None
    low_conf_accuracy = sum(1 for e in low_conf if e["correct"]) / len(low_conf) if low_conf else None

    # Best and worst signals
    sorted_by_return = sorted(evaluated, key=lambda e: e["actual_return_pct"], reverse=True)

    return {
        "symbol": symbol,
        "signal_type": signal_type,
        "period_days": days,
        "eval_hours": eval_hours,
        "total_signals": len(signals),
        "evaluated": total,
        "win_rate": round(win_rate, 4),
        "avg_return_pct": round(avg_return, 4),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "signal_sharpe": round(signal_sharpe, 2),
        "gross_profit_pct": round(gross_profit, 2),
        "gross_loss_pct": round(gross_loss, 2),
        "confidence_calibration": {
            "high_confidence_accuracy": round(high_conf_accuracy, 4) if high_conf_accuracy is not None else None,
            "low_confidence_accuracy": round(low_conf_accuracy, 4) if low_conf_accuracy is not None else None,
            "high_confidence_count": len(high_conf),
            "low_confidence_count": len(low_conf),
        },
        "best_signal": {
            "ts": sorted_by_return[0]["signal_ts"],
            "score": sorted_by_return[0]["signal_score"],
            "return_pct": sorted_by_return[0]["actual_return_pct"],
        } if sorted_by_return else None,
        "worst_signal": {
            "ts": sorted_by_return[-1]["signal_ts"],
            "score": sorted_by_return[-1]["signal_score"],
            "return_pct": sorted_by_return[-1]["actual_return_pct"],
        } if sorted_by_return else None,
    }


# ---------------------------------------------------------------------------
# Agent Comparison
# ---------------------------------------------------------------------------

def compare_agents(
    symbol: str = "BTC/USDT",
    days: int = 30,
    eval_hours: int = 24,
) -> dict:
    """Compare performance of all individual agents vs composite."""
    agent_types = ["composite", "sentiment", "technical", "onchain", "regulatory"]
    results = {}

    for agent_type in agent_types:
        scorecard = compute_scorecard(
            symbol=symbol,
            signal_type=agent_type,
            days=days,
            eval_hours=eval_hours,
        )
        results[agent_type] = {
            "total_signals": scorecard.get("total_signals", 0),
            "evaluated": scorecard.get("evaluated", 0),
            "win_rate": scorecard.get("win_rate", 0),
            "avg_return_pct": scorecard.get("avg_return_pct", 0),
            "profit_factor": scorecard.get("profit_factor", 0),
            "signal_sharpe": scorecard.get("signal_sharpe", 0),
        }

    # Rank agents
    ranked = sorted(
        [(k, v) for k, v in results.items() if v["evaluated"] > 0],
        key=lambda x: x[1]["signal_sharpe"],
        reverse=True,
    )

    return {
        "symbol": symbol,
        "period_days": days,
        "eval_hours": eval_hours,
        "agents": results,
        "ranking": [{"agent": k, **v} for k, v in ranked],
    }


# ---------------------------------------------------------------------------
# Simple Backtester
# ---------------------------------------------------------------------------

def backtest_strategy(
    symbol: str = "BTC/USDT",
    days: int = 30,
    signal_type: str = "composite",
    buy_threshold: float = 0.2,
    sell_threshold: float = -0.2,
    initial_capital: float = 10000.0,
) -> dict:
    """Backtest a simple long/short strategy based on historical signals.

    Strategy:
    - Signal > buy_threshold → go long (or hold)
    - Signal < sell_threshold → go short (or exit)
    - Otherwise → hold current position

    Returns equity curve and performance metrics.
    """
    signals = get_signal_history(symbol, signal_type, days, limit=1000)
    if not signals:
        return {"error": "No signals available for backtesting", "symbol": symbol}

    # Sort chronologically
    signals.sort(key=lambda s: s["ts"])

    capital = initial_capital
    position = 0  # 0 = flat, 1 = long, -1 = short
    entry_price = 0.0
    trades = []
    equity_curve = [{"ts": signals[0]["ts"], "equity": capital}]

    for i, sig in enumerate(signals):
        current_price = _get_price_at(symbol, sig["ts"])
        if current_price is None:
            continue

        score = sig["score"]

        # Close existing position if signal reverses
        if position == 1 and score < sell_threshold:
            pnl = (current_price - entry_price) / entry_price * capital
            capital += pnl
            trades.append({
                "type": "close_long",
                "ts": sig["ts"],
                "price": current_price,
                "pnl": round(pnl, 2),
                "pnl_pct": round((current_price - entry_price) / entry_price * 100, 2),
            })
            position = 0

        elif position == -1 and score > buy_threshold:
            pnl = (entry_price - current_price) / entry_price * capital
            capital += pnl
            trades.append({
                "type": "close_short",
                "ts": sig["ts"],
                "price": current_price,
                "pnl": round(pnl, 2),
                "pnl_pct": round((entry_price - current_price) / entry_price * 100, 2),
            })
            position = 0

        # Open new position
        if position == 0:
            if score > buy_threshold:
                position = 1
                entry_price = current_price
                trades.append({"type": "open_long", "ts": sig["ts"], "price": current_price, "score": score})
            elif score < sell_threshold:
                position = -1
                entry_price = current_price
                trades.append({"type": "open_short", "ts": sig["ts"], "price": current_price, "score": score})

        equity_curve.append({"ts": sig["ts"], "equity": round(capital, 2)})

    # Close any remaining position at last known price
    if position != 0 and signals:
        last_price = _get_price_at(symbol, signals[-1]["ts"])
        if last_price:
            if position == 1:
                pnl = (last_price - entry_price) / entry_price * capital
            else:
                pnl = (entry_price - last_price) / entry_price * capital
            capital += pnl
            trades.append({
                "type": "close_final",
                "ts": signals[-1]["ts"],
                "price": last_price,
                "pnl": round(pnl, 2),
            })

    # Metrics
    total_return = (capital - initial_capital) / initial_capital * 100
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

    # Max drawdown from equity curve
    peak = initial_capital
    max_dd = 0
    for point in equity_curve:
        if point["equity"] > peak:
            peak = point["equity"]
        dd = (peak - point["equity"]) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    return {
        "symbol": symbol,
        "signal_type": signal_type,
        "period_days": days,
        "buy_threshold": buy_threshold,
        "sell_threshold": sell_threshold,
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "total_return_pct": round(total_return, 2),
        "total_trades": len([t for t in trades if "pnl" in t]),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(len(winning_trades) / max(1, len(winning_trades) + len(losing_trades)), 4),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "trades": trades[-20:],  # Last 20 trades
        "equity_curve": equity_curve[::max(1, len(equity_curve) // 50)],  # Sampled to ~50 points
    }
