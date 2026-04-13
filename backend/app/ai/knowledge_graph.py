"""Entity Knowledge Graph — tracks relationships between entities.

Builds co-occurrence relationships when entities appear together in the same
news item. Enables graph queries like:
- "What entities are connected to BTC?"
- "What's the relationship between BaFin and MiCA?"
- "Show the entity network around Binance"

Uses SQL (entity_relationships table). Can be migrated to Neo4j later.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from itertools import combinations
from typing import Optional

from app.ai.entities import Entity, extract_entities
from app.database import get_db, USE_POSTGRES

logger = logging.getLogger(__name__)


def build_co_occurrences(entities: list[Entity], conn=None) -> int:
    """Build co-occurrence relationships between entities in the same item.

    For N entities, creates N*(N-1)/2 pairs. Updates weight for existing pairs.
    Returns number of relationships created/updated.
    """
    if len(entities) < 2:
        return 0

    # Sort to ensure consistent ordering (a < b)
    entity_pairs = []
    for e1, e2 in combinations(entities, 2):
        a, b = sorted([e1, e2], key=lambda e: (e.entity_type, e.normalized))
        entity_pairs.append((a, b))

    now = datetime.now(timezone.utc).isoformat()
    updated = 0

    def _do(conn):
        nonlocal updated
        cur = conn.cursor()
        for a, b in entity_pairs:
            if USE_POSTGRES:
                cur.execute(
                    """INSERT INTO entity_relationships
                       (entity_a, entity_a_type, entity_b, entity_b_type, relationship, weight, first_seen, last_seen, item_count)
                       VALUES (%s, %s, %s, %s, 'co_occurrence', 1.0, %s, %s, 1)
                       ON CONFLICT (entity_a, entity_a_type, entity_b, entity_b_type, relationship)
                       DO UPDATE SET
                           weight = entity_relationships.weight + 1.0,
                           last_seen = EXCLUDED.last_seen,
                           item_count = entity_relationships.item_count + 1
                    """,
                    (a.normalized, a.entity_type, b.normalized, b.entity_type, now, now),
                )
            else:
                cur.execute(
                    """INSERT INTO entity_relationships
                       (entity_a, entity_a_type, entity_b, entity_b_type, relationship, weight, first_seen, last_seen, item_count)
                       VALUES (?, ?, ?, ?, 'co_occurrence', 1.0, ?, ?, 1)
                       ON CONFLICT (entity_a, entity_a_type, entity_b, entity_b_type, relationship)
                       DO UPDATE SET
                           weight = entity_relationships.weight + 1.0,
                           last_seen = excluded.last_seen,
                           item_count = entity_relationships.item_count + 1
                    """,
                    (a.normalized, a.entity_type, b.normalized, b.entity_type, now, now),
                )
            updated += 1

    if conn:
        _do(conn)
    else:
        with get_db() as conn:
            _do(conn)

    return updated


def build_from_text(text: str, conn=None) -> int:
    """Extract entities from text and build co-occurrence graph."""
    entities = extract_entities(text)
    return build_co_occurrences(entities, conn=conn)


def get_entity_connections(
    entity_name: str,
    entity_type: Optional[str] = None,
    min_weight: float = 1.0,
    limit: int = 50,
) -> list[dict]:
    """Get all entities connected to a given entity.

    Returns list of {entity, entity_type, relationship, weight, item_count, last_seen}.
    """
    with get_db() as conn:
        cur = conn.cursor()
        params = []
        conditions_a = ["entity_a = ?"]
        conditions_b = ["entity_b = ?"]
        params_a = [entity_name]
        params_b = [entity_name]

        if entity_type:
            conditions_a.append("entity_a_type = ?")
            conditions_b.append("entity_b_type = ?")
            params_a.append(entity_type)
            params_b.append(entity_type)

        # Entity can be on either side of the relationship
        query = f"""
            SELECT entity_b AS entity, entity_b_type AS entity_type,
                   relationship, weight, item_count, last_seen
            FROM entity_relationships
            WHERE {' AND '.join(conditions_a)} AND weight >= ?
            UNION ALL
            SELECT entity_a AS entity, entity_a_type AS entity_type,
                   relationship, weight, item_count, last_seen
            FROM entity_relationships
            WHERE {' AND '.join(conditions_b)} AND weight >= ?
            ORDER BY weight DESC
            LIMIT ?
        """
        all_params = params_a + [min_weight] + params_b + [min_weight] + [limit]
        cur.execute(query, all_params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_entity_network(
    entity_name: str,
    depth: int = 2,
    min_weight: float = 2.0,
    limit: int = 100,
) -> dict:
    """Get a multi-hop network around an entity.

    Returns {nodes: [...], edges: [...]} for visualization.
    """
    nodes = set()
    edges = []
    visited = set()
    queue = [(entity_name, 0)]
    nodes.add(entity_name)

    while queue:
        current, current_depth = queue.pop(0)
        if current in visited or current_depth >= depth:
            continue
        visited.add(current)

        connections = get_entity_connections(current, min_weight=min_weight, limit=30)
        for conn in connections:
            target = conn["entity"]
            nodes.add(target)
            edges.append({
                "source": current,
                "target": target,
                "weight": conn["weight"],
                "relationship": conn["relationship"],
                "item_count": conn["item_count"],
            })
            if current_depth + 1 < depth and target not in visited:
                queue.append((target, current_depth + 1))

            if len(edges) >= limit:
                break

    return {
        "center": entity_name,
        "nodes": [{"id": n} for n in nodes],
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def get_top_entities(
    entity_type: Optional[str] = None,
    days: int = 7,
    limit: int = 20,
) -> list[dict]:
    """Get the most connected entities (highest total relationship weight)."""
    with get_db() as conn:
        cur = conn.cursor()

        type_filter = ""
        params = [limit]
        if entity_type:
            type_filter = "WHERE entity_a_type = ? OR entity_b_type = ?"
            params = [entity_type, entity_type, limit]

        query = f"""
            SELECT entity, entity_type, SUM(total_weight) as total_weight,
                   SUM(total_connections) as connections
            FROM (
                SELECT entity_a as entity, entity_a_type as entity_type,
                       SUM(weight) as total_weight, COUNT(*) as total_connections
                FROM entity_relationships
                {type_filter}
                GROUP BY entity_a, entity_a_type
                UNION ALL
                SELECT entity_b as entity, entity_b_type as entity_type,
                       SUM(weight) as total_weight, COUNT(*) as total_connections
                FROM entity_relationships
                {type_filter}
                GROUP BY entity_b, entity_b_type
            )
            GROUP BY entity, entity_type
            ORDER BY total_weight DESC
            LIMIT ?
        """
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
