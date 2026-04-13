"""Paper Trading Engine -- simulated order execution with real-time P&L tracking.

All orders are logged but never sent to an exchange. The engine tracks:
- Open positions with live P&L
- Order history (fills, cancels)
- Portfolio value over time
- Win rate, Sharpe ratio, max drawdown
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.feature_flags import is_enabled

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PaperOrder:
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None  # limit/stop price
    status: OrderStatus = OrderStatus.PENDING
    created_at: str = ""
    filled_at: Optional[str] = None
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None
    reason: Optional[str] = None  # rejection reason

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "portfolio_id": "default",
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.type.value,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "created_at": self.created_at,
            "filled_at": self.filled_at,
            "fill_price": self.fill_price,
            "fill_quantity": self.fill_quantity,
            "reason": self.reason,
        }


@dataclass
class PaperPosition:
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float = 0.0
    sector: str = ""

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_entry_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100.0


# ---------------------------------------------------------------------------
# Risk limits
# ---------------------------------------------------------------------------

MAX_POSITION_SIZE_PCT = 0.20   # 20% of portfolio per position
MAX_TOTAL_EXPOSURE_PCT = 0.90  # 90% max exposure (keep 10% cash)


# ---------------------------------------------------------------------------
# Price lookup
# ---------------------------------------------------------------------------

def _get_live_price(symbol: str) -> Optional[float]:
    """Fetch latest price from price_ticks table."""
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT price FROM price_ticks WHERE symbol = ? ORDER BY ts DESC LIMIT 1",
                (symbol,),
            )
            row = cur.fetchone()
            return row[0] if row else (row["price"] if row and isinstance(row, dict) else None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class PaperPortfolio:
    """In-memory paper trading portfolio with DB persistence."""

    def __init__(self, initial_cash: float = 100_000.0, portfolio_id: str = "default"):
        self._lock = threading.Lock()
        self._portfolio_id = portfolio_id
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._positions: dict[str, PaperPosition] = {}
        self._order_history: list[PaperOrder] = []
        self._high_water_mark = initial_cash
        self._closed_trades: list[dict] = []  # for win rate / metrics

        # Try loading from DB
        self._load_from_db()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> dict[str, PaperPosition]:
        return dict(self._positions)

    @property
    def total_value(self) -> float:
        pos_value = sum(p.market_value for p in self._positions.values())
        return self._cash + pos_value

    @property
    def order_history(self) -> list[PaperOrder]:
        return list(self._order_history)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
    ) -> PaperOrder:
        """Validate and execute a paper order.

        Market orders fill immediately at the current price.
        Limit/stop orders are stored as pending (simplified: we fill them immediately
        if the price condition is met, otherwise they stay pending).
        """
        # Safety: ensure live trading is OFF
        if is_enabled("trading_live"):
            raise RuntimeError(
                "Paper trading disabled: trading_live flag is ON. "
                "Disable trading_live before using paper trading."
            )

        now = datetime.now(timezone.utc).isoformat()
        order = PaperOrder(
            id=str(uuid.uuid4()),
            symbol=symbol.upper(),
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
            created_at=now,
        )

        with self._lock:
            # Get execution price
            exec_price = self._resolve_price(order)
            if exec_price is None:
                order.status = OrderStatus.REJECTED
                order.reason = f"No price available for {order.symbol}"
                self._order_history.append(order)
                self._persist_order(order)
                self._audit_order(order)
                return order

            # Pre-trade risk checks
            rejection = self._pre_trade_check(order, exec_price)
            if rejection:
                order.status = OrderStatus.REJECTED
                order.reason = rejection
                self._order_history.append(order)
                self._persist_order(order)
                self._audit_order(order)
                return order

            # Execute
            if order_type == OrderType.MARKET:
                self._fill_order(order, exec_price)
            elif order_type == OrderType.LIMIT:
                if side == OrderSide.BUY and price is not None and exec_price <= price:
                    self._fill_order(order, exec_price)
                elif side == OrderSide.SELL and price is not None and exec_price >= price:
                    self._fill_order(order, exec_price)
                else:
                    # Price condition not met -- stays pending
                    self._order_history.append(order)
                    self._persist_order(order)
                    self._audit_order(order)
                    return order
            elif order_type == OrderType.STOP_LOSS:
                if side == OrderSide.SELL and price is not None and exec_price <= price:
                    self._fill_order(order, exec_price)
                else:
                    self._order_history.append(order)
                    self._persist_order(order)
                    self._audit_order(order)
                    return order

            self._order_history.append(order)
            self._persist_order(order)
            self._persist_state()
            self._audit_order(order)

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if cancelled, False otherwise."""
        with self._lock:
            for order in self._order_history:
                if order.id == order_id:
                    if order.status != OrderStatus.PENDING:
                        return False
                    order.status = OrderStatus.CANCELLED
                    self._persist_order(order)
                    return True
        return False

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update mark-to-market for all positions."""
        with self._lock:
            for symbol, price in prices.items():
                sym = symbol.upper()
                if sym in self._positions:
                    self._positions[sym].current_price = price

            # Update high water mark
            tv = self.total_value
            if tv > self._high_water_mark:
                self._high_water_mark = tv
                self._persist_state()

    def close_position(self, symbol: str) -> PaperOrder:
        """Market sell entire position for a symbol."""
        sym = symbol.upper()
        if sym not in self._positions or self._positions[sym].quantity <= 0:
            order = PaperOrder(
                id=str(uuid.uuid4()),
                symbol=sym,
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                quantity=0,
                status=OrderStatus.REJECTED,
                reason=f"No open position for {sym}",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._order_history.append(order)
            self._persist_order(order)
            return order

        qty = self._positions[sym].quantity
        return self.submit_order(sym, OrderSide.SELL, OrderType.MARKET, qty)

    def get_performance(self) -> dict:
        """Calculate trading performance metrics."""
        total_return_pct = ((self.total_value - self._initial_cash) / self._initial_cash) * 100.0

        # Win rate from closed trades
        wins = [t for t in self._closed_trades if t["pnl"] > 0]
        losses = [t for t in self._closed_trades if t["pnl"] <= 0]
        total_trades = len(self._closed_trades)
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        # Max drawdown
        max_drawdown = 0.0
        if self._high_water_mark > 0:
            max_drawdown = ((self._high_water_mark - self.total_value) / self._high_water_mark) * 100.0
            max_drawdown = max(0.0, max_drawdown)

        # Simplified Sharpe ratio from closed trades
        sharpe_ratio = 0.0
        if total_trades >= 2:
            returns = [t["pnl_pct"] for t in self._closed_trades]
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 0.0
            if std_dev > 0:
                sharpe_ratio = (avg_return / std_dev) * math.sqrt(252)  # annualized

        return {
            "total_value": round(self.total_value, 2),
            "initial_cash": round(self._initial_cash, 2),
            "current_cash": round(self._cash, 2),
            "total_return_pct": round(total_return_pct, 4),
            "win_rate": round(win_rate, 2),
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "max_drawdown": round(max_drawdown, 4),
            "high_water_mark": round(self._high_water_mark, 2),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "open_positions": len(self._positions),
        }

    def get_portfolio_snapshot(self) -> dict:
        """Current state for API/frontend."""
        positions_list = []
        for sym, pos in self._positions.items():
            positions_list.append({
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_entry_price": round(pos.avg_entry_price, 2),
                "current_price": round(pos.current_price, 2),
                "market_value": round(pos.market_value, 2),
                "unrealized_pnl": round(pos.unrealized_pnl, 2),
                "unrealized_pnl_pct": round(pos.unrealized_pnl_pct, 4),
                "sector": pos.sector,
            })

        return {
            "portfolio_id": self._portfolio_id,
            "cash": round(self._cash, 2),
            "total_value": round(self.total_value, 2),
            "positions": positions_list,
            "position_count": len(self._positions),
            "high_water_mark": round(self._high_water_mark, 2),
        }

    def reset(self) -> None:
        """Clear all positions and orders, reset to initial cash."""
        with self._lock:
            self._cash = self._initial_cash
            self._positions.clear()
            self._order_history.clear()
            self._closed_trades.clear()
            self._high_water_mark = self._initial_cash

            # Clear DB
            try:
                from app.trading.paper_db import delete_portfolio_data
                delete_portfolio_data(self._portfolio_id)
            except Exception as exc:
                logger.warning("Failed to clear paper trading DB: %s", exc)

            # Re-save initial state
            self._persist_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_price(self, order: PaperOrder) -> Optional[float]:
        """Get the execution price for an order."""
        # Try live price first
        live = _get_live_price(order.symbol)
        if live is not None:
            return live

        # For limit/stop orders, use the specified price as fallback
        if order.price is not None:
            return order.price

        # Check if we have a position with a known price
        if order.symbol in self._positions:
            return self._positions[order.symbol].current_price or None

        return None

    def _pre_trade_check(self, order: PaperOrder, exec_price: float) -> Optional[str]:
        """Run pre-trade risk checks. Returns rejection reason or None."""
        total_val = self.total_value
        if total_val <= 0:
            return "Portfolio value is zero"

        order_value = order.quantity * exec_price

        if order.side == OrderSide.BUY:
            # Check sufficient cash
            if order_value > self._cash:
                return f"Insufficient cash: need ${order_value:.2f}, have ${self._cash:.2f}"

            # Max position size check (20% of portfolio)
            existing_value = 0.0
            if order.symbol in self._positions:
                existing_value = self._positions[order.symbol].market_value
            new_position_value = existing_value + order_value
            max_allowed = total_val * MAX_POSITION_SIZE_PCT
            if new_position_value > max_allowed:
                return (
                    f"Position size limit: {order.symbol} would be "
                    f"${new_position_value:.2f} ({new_position_value / total_val * 100:.1f}%), "
                    f"max allowed ${max_allowed:.2f} ({MAX_POSITION_SIZE_PCT * 100:.0f}%)"
                )

            # Max total exposure check (90%)
            total_exposure = sum(p.market_value for p in self._positions.values())
            new_exposure = total_exposure + order_value
            max_exposure = total_val * MAX_TOTAL_EXPOSURE_PCT
            if new_exposure > max_exposure:
                return (
                    f"Total exposure limit: would be ${new_exposure:.2f} "
                    f"({new_exposure / total_val * 100:.1f}%), "
                    f"max allowed ${max_exposure:.2f} ({MAX_TOTAL_EXPOSURE_PCT * 100:.0f}%)"
                )

        elif order.side == OrderSide.SELL:
            # Check we have sufficient position
            if order.symbol not in self._positions:
                return f"No position in {order.symbol} to sell"
            held = self._positions[order.symbol].quantity
            if order.quantity > held:
                return f"Insufficient position: want to sell {order.quantity}, hold {held}"

        return None

    def _fill_order(self, order: PaperOrder, exec_price: float) -> None:
        """Fill an order at the given price. Updates cash and positions."""
        now = datetime.now(timezone.utc).isoformat()
        order.status = OrderStatus.FILLED
        order.fill_price = exec_price
        order.fill_quantity = order.quantity
        order.filled_at = now

        if order.side == OrderSide.BUY:
            cost = order.quantity * exec_price
            self._cash -= cost

            if order.symbol in self._positions:
                pos = self._positions[order.symbol]
                # Weighted average entry price
                total_qty = pos.quantity + order.quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * pos.quantity + exec_price * order.quantity) / total_qty
                )
                pos.quantity = total_qty
                pos.current_price = exec_price
            else:
                self._positions[order.symbol] = PaperPosition(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_entry_price=exec_price,
                    current_price=exec_price,
                )

            # Persist position
            pos = self._positions[order.symbol]
            self._persist_position(pos)

        elif order.side == OrderSide.SELL:
            revenue = order.quantity * exec_price
            self._cash += revenue

            if order.symbol in self._positions:
                pos = self._positions[order.symbol]
                # Record closed trade for metrics
                pnl = (exec_price - pos.avg_entry_price) * order.quantity
                pnl_pct = ((exec_price / pos.avg_entry_price) - 1.0) * 100.0 if pos.avg_entry_price > 0 else 0.0
                self._closed_trades.append({
                    "symbol": order.symbol,
                    "quantity": order.quantity,
                    "entry_price": pos.avg_entry_price,
                    "exit_price": exec_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "closed_at": now,
                })

                pos.quantity -= order.quantity
                pos.current_price = exec_price
                if pos.quantity <= 0:
                    del self._positions[order.symbol]
                    self._persist_position_delete(order.symbol)
                else:
                    self._persist_position(pos)

        # Update high water mark
        tv = self.total_value
        if tv > self._high_water_mark:
            self._high_water_mark = tv

    def _persist_order(self, order: PaperOrder) -> None:
        """Persist order to DB (fire-and-forget)."""
        try:
            from app.trading.paper_db import save_order
            save_order(order.to_dict())
        except Exception as exc:
            logger.debug("Failed to persist paper order: %s", exc)

    def _persist_position(self, pos: PaperPosition) -> None:
        """Persist position to DB."""
        try:
            from app.trading.paper_db import save_position
            save_position(self._portfolio_id, pos.symbol, pos.quantity, pos.avg_entry_price)
        except Exception as exc:
            logger.debug("Failed to persist paper position: %s", exc)

    def _persist_position_delete(self, symbol: str) -> None:
        """Remove closed position from DB."""
        try:
            from app.trading.paper_db import save_position
            save_position(self._portfolio_id, symbol, 0.0, 0.0)
        except Exception as exc:
            logger.debug("Failed to delete paper position: %s", exc)

    def _persist_state(self) -> None:
        """Persist portfolio state to DB."""
        try:
            from app.trading.paper_db import save_portfolio_state
            save_portfolio_state(
                self._portfolio_id,
                self._initial_cash,
                self._cash,
                self._high_water_mark,
            )
        except Exception as exc:
            logger.debug("Failed to persist portfolio state: %s", exc)

    def _audit_order(self, order: PaperOrder) -> None:
        """Log order to audit trail."""
        try:
            from app.audit import log_fund
            log_fund("paper_order", detail={
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.type.value,
                "quantity": order.quantity,
                "price": order.price,
                "status": order.status.value,
                "fill_price": order.fill_price,
                "reason": order.reason,
            })
        except Exception:
            pass

    def _load_from_db(self) -> None:
        """Load persisted state from DB on startup."""
        try:
            from app.trading.paper_db import load_portfolio_state, load_positions, load_orders

            state = load_portfolio_state(self._portfolio_id)
            if state:
                self._initial_cash = state.get("initial_cash", self._initial_cash)
                self._cash = state.get("current_cash", self._cash)
                self._high_water_mark = state.get("high_water_mark", self._high_water_mark)

            positions = load_positions(self._portfolio_id)
            for p in positions:
                sym = p["symbol"]
                qty = p["quantity"]
                avg = p["avg_entry_price"]
                # Try to get current price
                current = _get_live_price(sym) or avg
                self._positions[sym] = PaperPosition(
                    symbol=sym,
                    quantity=qty,
                    avg_entry_price=avg,
                    current_price=current,
                )

            orders = load_orders(self._portfolio_id, limit=500)
            for o in orders:
                self._order_history.append(PaperOrder(
                    id=o["id"],
                    symbol=o["symbol"],
                    side=OrderSide(o["side"]),
                    type=OrderType(o["order_type"]),
                    quantity=o["quantity"],
                    price=o.get("price"),
                    status=OrderStatus(o["status"]),
                    created_at=o.get("created_at", ""),
                    filled_at=o.get("filled_at"),
                    fill_price=o.get("fill_price"),
                    fill_quantity=o.get("fill_quantity"),
                    reason=o.get("reason"),
                ))

        except Exception as exc:
            logger.debug("Could not load paper trading state from DB: %s", exc)


# ---------------------------------------------------------------------------
# Singleton portfolio instance
# ---------------------------------------------------------------------------

_default_portfolio: Optional[PaperPortfolio] = None
_portfolio_lock = threading.Lock()


def get_paper_portfolio() -> PaperPortfolio:
    """Get or create the default paper portfolio singleton."""
    global _default_portfolio
    if _default_portfolio is not None:
        return _default_portfolio
    with _portfolio_lock:
        if _default_portfolio is not None:
            return _default_portfolio
        _default_portfolio = PaperPortfolio()
    return _default_portfolio


def reset_paper_portfolio() -> None:
    """Reset the singleton (used by tests and admin reset)."""
    global _default_portfolio
    with _portfolio_lock:
        if _default_portfolio is not None:
            _default_portfolio.reset()
        _default_portfolio = None
