"""API v1 router — groups all versioned endpoints under /api/v1/.

All existing endpoints continue to work at their original paths (backward compat).
New integrations should use /api/v1/ prefixed routes.
"""

from fastapi import APIRouter

from app.routers.market_data import router as market_data_router
from app.routers.entity_graph import router as entity_graph_router
from app.routers.signals import router as signals_router
from app.routers.portfolio import router as portfolio_router
from app.routers.chat import router as chat_router
from app.routers.scorecard import router as scorecard_router
from app.routers.fund import router as fund_router
from app.routers.audit_router import router as audit_router
from app.routers.auth_router import router as auth_router
from app.routers.paper_trading import router as paper_trading_router

# v1 API router — all endpoints get /api/v1 prefix
v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

# Auth (original: /auth/*)
v1_router.include_router(auth_router)

# Market data (original: /api/market/*)
v1_router.include_router(market_data_router)

# Signals (original: /api/signals/*)
v1_router.include_router(signals_router)

# Portfolio (original: /api/portfolio/*)
v1_router.include_router(portfolio_router)

# Chat (original: /api/chat/*)
v1_router.include_router(chat_router)

# Scorecard (original: /api/scorecard/*)
v1_router.include_router(scorecard_router)

# Fund (original: /api/fund/*)
v1_router.include_router(fund_router)

# Audit (original: /api/audit/*)
v1_router.include_router(audit_router)

# Knowledge graph (original: /api/graph/*)
v1_router.include_router(entity_graph_router)

# Paper trading (original: /api/paper/*)
v1_router.include_router(paper_trading_router)
