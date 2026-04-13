"""Paper Trading API -- simulated order execution endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_role
from app.audit import log_fund
from app.trading.paper_engine import (
    OrderSide,
    OrderType,
    get_paper_portfolio,
    reset_paper_portfolio,
)
from app.trading.kill_switch import (
    activate_kill_switch,
    deactivate_kill_switch,
    is_kill_switch_active,
    get_kill_switch_status,
)
from app.trading.nav_calculator import (
    calculate_nav,
    record_nav_snapshot,
    get_nav_history,
    calculate_all_fees,
)

router = APIRouter(prefix="/api/paper", tags=["paper-trading"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class OrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading pair, e.g. BTC/USDT")
    side: str = Field(..., pattern="^(buy|sell)$", description="Order side: buy or sell")
    type: str = Field("market", pattern="^(market|limit|stop_loss)$", description="Order type")
    quantity: float = Field(..., gt=0, description="Quantity to trade")
    price: Optional[float] = Field(None, gt=0, description="Limit/stop price (required for limit/stop_loss)")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/order", dependencies=[Depends(get_current_user)])
async def submit_order(req: OrderRequest):
    """Submit a paper trading order."""
    # Kill switch check -- reject all orders when active
    if is_kill_switch_active():
        status = get_kill_switch_status()
        raise HTTPException(
            status_code=403,
            detail=f"Trading halted: kill switch active. Reason: {status.get('reason', 'Unknown')}",
        )

    portfolio = get_paper_portfolio()

    try:
        side = OrderSide(req.side)
        order_type = OrderType(req.type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid order parameter: {exc}")

    if order_type in (OrderType.LIMIT, OrderType.STOP_LOSS) and req.price is None:
        raise HTTPException(status_code=400, detail=f"Price is required for {order_type.value} orders")

    try:
        order = portfolio.submit_order(
            symbol=req.symbol,
            side=side,
            order_type=order_type,
            quantity=req.quantity,
            price=req.price,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return order.to_dict()


@router.get("/orders", dependencies=[Depends(get_current_user)])
async def list_orders(
    status: Optional[str] = Query(None, pattern="^(pending|filled|cancelled|rejected|expired)$"),
    symbol: Optional[str] = Query(None, max_length=20),
    limit: int = Query(50, ge=1, le=500),
):
    """Get paper order history with optional filters."""
    portfolio = get_paper_portfolio()
    orders = portfolio.order_history

    if status:
        orders = [o for o in orders if o.status.value == status]
    if symbol:
        sym = symbol.upper()
        orders = [o for o in orders if o.symbol == sym]

    # Most recent first, apply limit
    orders = orders[-limit:][::-1] if len(orders) > limit else list(reversed(orders))

    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders),
    }


@router.delete("/order/{order_id}", dependencies=[Depends(get_current_user)])
async def cancel_order(order_id: str):
    """Cancel a pending paper order."""
    portfolio = get_paper_portfolio()
    cancelled = portfolio.cancel_order(order_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Order not found or not in pending status")
    return {"status": "cancelled", "order_id": order_id}


@router.get("/portfolio", dependencies=[Depends(get_current_user)])
async def get_portfolio():
    """Get current paper portfolio snapshot (positions, cash, total value, P&L)."""
    portfolio = get_paper_portfolio()
    return portfolio.get_portfolio_snapshot()


@router.get("/performance", dependencies=[Depends(get_current_user)])
async def get_performance():
    """Get paper trading performance metrics (return, win_rate, sharpe, drawdown)."""
    portfolio = get_paper_portfolio()
    return portfolio.get_performance()


@router.post("/reset", dependencies=[Depends(require_role("admin"))])
async def reset_portfolio():
    """Reset paper portfolio to initial state (admin only)."""
    reset_paper_portfolio()
    log_fund("paper_reset", detail={"action": "portfolio_reset"})
    return {"status": "reset", "message": "Paper portfolio reset to initial state"}


@router.post("/close/{symbol}", dependencies=[Depends(get_current_user)])
async def close_position(symbol: str):
    """Close an entire position by market selling."""
    portfolio = get_paper_portfolio()
    order = portfolio.close_position(symbol)
    return order.to_dict()


# ---------------------------------------------------------------------------
# Kill Switch endpoints
# ---------------------------------------------------------------------------


@router.post("/kill-switch/activate", dependencies=[Depends(require_role("admin"))])
async def activate_kill(reason: str = Query("Manual activation")):
    """Activate kill switch -- halt all trading."""
    state = activate_kill_switch(user_id="admin", reason=reason)
    return {
        "status": "activated",
        "active": state.active,
        "activated_at": state.activated_at,
        "reason": state.reason,
    }


@router.post("/kill-switch/deactivate", dependencies=[Depends(require_role("admin"))])
async def deactivate_kill():
    """Deactivate kill switch -- resume trading."""
    state = deactivate_kill_switch(user_id="admin")
    return {
        "status": "deactivated",
        "active": state.active,
    }


@router.get("/kill-switch/status", dependencies=[Depends(get_current_user)])
async def kill_switch_status_endpoint():
    """Get kill switch status."""
    return get_kill_switch_status()


# ---------------------------------------------------------------------------
# NAV & Fees endpoints
# ---------------------------------------------------------------------------


@router.get("/nav", dependencies=[Depends(get_current_user)])
async def get_nav():
    """Calculate current NAV."""
    return calculate_nav()


@router.get("/nav/history", dependencies=[Depends(get_current_user)])
async def get_nav_history_endpoint(days: int = Query(30, ge=1, le=365)):
    """Get historical NAV snapshots."""
    return get_nav_history(days=days)


@router.get("/fees", dependencies=[Depends(get_current_user)])
async def get_fees():
    """Calculate current fee structure."""
    return calculate_all_fees()


@router.post("/nav/snapshot", dependencies=[Depends(require_role("admin"))])
async def take_nav_snapshot():
    """Record a NAV snapshot (normally done daily by scheduler)."""
    snapshot = record_nav_snapshot()
    return snapshot
