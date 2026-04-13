"""Entity Knowledge Graph API.

Query entity relationships, networks, and top entities.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.ai.knowledge_graph import get_entity_connections, get_entity_network, get_top_entities

router = APIRouter(prefix="/api/graph", tags=["knowledge-graph"])


@router.get("/connections")
async def entity_connections(
    entity: str = Query(..., description="Entity name, e.g. BTC, BaFin, Binance"),
    entity_type: Optional[str] = Query(None, description="Filter by type: token, company, regulator"),
    min_weight: float = Query(1.0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Get all entities connected to a given entity."""
    return get_entity_connections(entity, entity_type=entity_type, min_weight=min_weight, limit=limit)


@router.get("/network")
async def entity_network(
    entity: str = Query(..., description="Center entity for network exploration"),
    depth: int = Query(2, ge=1, le=3),
    min_weight: float = Query(2.0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Get multi-hop entity network for visualization."""
    return get_entity_network(entity, depth=depth, min_weight=min_weight, limit=limit)


@router.get("/top")
async def top_entities(
    entity_type: Optional[str] = Query(None, description="Filter: token, company, regulator"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
):
    """Get the most connected/mentioned entities."""
    return get_top_entities(entity_type=entity_type, days=days, limit=limit)
