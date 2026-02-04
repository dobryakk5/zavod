"""
FastAPI router – /api/chains/
------------------------------
Every endpoint is tenant-scoped.  `get_tenant_id` is a dependency that
extracts the authenticated client's ID from the request (JWT claim or
session – plug in whatever your existing auth layer provides).

DB access uses `get_db` – an async session dependency.  The query helpers
live in a thin repository layer (see comments) so the router stays clean.

Adjust the import paths to match your project layout.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

# ---------------------------------------------------------------------------
# project-local imports  –  adjust paths to your layout
# ---------------------------------------------------------------------------
from .models import (
    ChainCreate, ChainUpdate, ChainOut, ChainGraphOut,
    NodeCreate,  NodeUpdate,  NodeOut,
    EdgeCreate,  EdgeUpdate,  EdgeOut,
    ConditionCreate,          ConditionOut,
)
# Your existing auth dependency – returns the tenant (client) id
# Example signature:  async def get_tenant_id(request: Request) -> int
from ..auth.dependencies import get_tenant_id

# Your existing DB session dependency
# Example signature:  async def get_db() -> AsyncGenerator[AsyncSession, None]
from ..db.dependencies import get_db


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/chains", tags=["chains"])


# ===========================================================================
# CHAINS  – top-level CRUD
# ===========================================================================

@router.get("/", response_model=List[ChainOut])
async def list_chains(
    status: Optional[str] = None,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    """Return all chains belonging to the current tenant.
    Optionally filter by status (draft | active | paused | archived).
    """
    query = (
        "SELECT * FROM chains.chains WHERE tenant_id = $1"
    )
    params: list = [tenant_id]

    if status:
        query += " AND status = $2"
        params.append(status)

    query += " ORDER BY created_at DESC"

    rows = await db.fetch(query, *params)
    return [ChainOut.model_validate(dict(r)) for r in rows]


@router.post("/", response_model=ChainOut, status_code=status.HTTP_201_CREATED)
async def create_chain(
    body: ChainCreate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    row = await db.fetchrow(
        """
        INSERT INTO chains.chains (tenant_id, name, description, status)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        tenant_id, body.name, body.description, body.status.value,
    )
    return ChainOut.model_validate(dict(row))


@router.get("/{chain_id}", response_model=ChainOut)
async def get_chain(
    chain_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT * FROM chains.chains WHERE id = $1 AND tenant_id = $2",
        chain_id, tenant_id,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chain not found")
    return ChainOut.model_validate(dict(row))


@router.patch("/{chain_id}", response_model=ChainOut)
async def update_chain(
    chain_id: int,
    body: ChainUpdate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    # ownership check
    existing = await db.fetchrow(
        "SELECT id FROM chains.chains WHERE id = $1 AND tenant_id = $2",
        chain_id, tenant_id,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chain not found")

    # build SET clause dynamically (only fields that were sent)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

    set_parts, values, idx = [], [], 1
    for key, val in updates.items():
        if key == "status":
            val = val.value if hasattr(val, "value") else val
        set_parts.append(f"{key} = ${idx}")
        values.append(val)
        idx += 1

    values.append(chain_id)
    query = (
        f"UPDATE chains.chains SET {', '.join(set_parts)} "
        f"WHERE id = ${idx} RETURNING *"
    )
    row = await db.fetchrow(query, *values)
    return ChainOut.model_validate(dict(row))


@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain(
    chain_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    result = await db.execute(
        "DELETE FROM chains.chains WHERE id = $1 AND tenant_id = $2",
        chain_id, tenant_id,
    )
    # asyncpg returns "DELETE <n>"
    if result.split()[-1] == "0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chain not found")


# ===========================================================================
# NODES  – CRUD scoped to a chain
# ===========================================================================

async def _assert_chain_owner(db, chain_id: int, tenant_id: int):
    """Helper: raises 404 if chain does not belong to tenant."""
    row = await db.fetchrow(
        "SELECT id FROM chains.chains WHERE id = $1 AND tenant_id = $2",
        chain_id, tenant_id,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chain not found")


@router.get("/{chain_id}/nodes", response_model=List[NodeOut])
async def list_nodes(
    chain_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)
    rows = await db.fetch(
        "SELECT * FROM chains.chain_nodes WHERE chain_id = $1 ORDER BY created_at",
        chain_id,
    )
    return [NodeOut.model_validate(dict(r)) for r in rows]


@router.post("/{chain_id}/nodes", response_model=NodeOut, status_code=status.HTTP_201_CREATED)
async def create_node(
    chain_id: int,
    body: NodeCreate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)

    row = await db.fetchrow(
        """
        INSERT INTO chains.chain_nodes
            (chain_id, node_type, payload, delay_seconds, pos_x, pos_y)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        chain_id,
        body.node_type.value,
        body.payload,          # asyncpg serialises dicts to JSONB automatically
        body.delay_seconds,
        body.pos_x,
        body.pos_y,
    )
    return NodeOut.model_validate(dict(row))


@router.patch("/{chain_id}/nodes/{node_id}", response_model=NodeOut)
async def update_node(
    chain_id: int,
    node_id: int,
    body: NodeUpdate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)

    existing = await db.fetchrow(
        "SELECT id FROM chains.chain_nodes WHERE id = $1 AND chain_id = $2",
        node_id, chain_id,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

    set_parts, values, idx = [], [], 1
    for key, val in updates.items():
        if key == "node_type":
            val = val.value if hasattr(val, "value") else val
        set_parts.append(f"{key} = ${idx}")
        values.append(val)
        idx += 1

    values.append(node_id)
    query = (
        f"UPDATE chains.chain_nodes SET {', '.join(set_parts)} "
        f"WHERE id = ${idx} RETURNING *"
    )
    row = await db.fetchrow(query, *values)
    return NodeOut.model_validate(dict(row))


@router.delete("/{chain_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    chain_id: int,
    node_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)
    result = await db.execute(
        "DELETE FROM chains.chain_nodes WHERE id = $1 AND chain_id = $2",
        node_id, chain_id,
    )
    if result.split()[-1] == "0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node not found")


# ===========================================================================
# EDGES  – CRUD scoped to a chain
# ===========================================================================

@router.get("/{chain_id}/edges", response_model=List[EdgeOut])
async def list_edges(
    chain_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)
    rows = await db.fetch(
        "SELECT * FROM chains.chain_edges WHERE chain_id = $1 ORDER BY priority",
        chain_id,
    )
    return [EdgeOut.model_validate(dict(r)) for r in rows]


@router.post("/{chain_id}/edges", response_model=EdgeOut, status_code=status.HTTP_201_CREATED)
async def create_edge(
    chain_id: int,
    body: EdgeCreate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)

    # both nodes must belong to the same chain
    for node_id in (body.source_node_id, body.target_node_id):
        n = await db.fetchrow(
            "SELECT id FROM chains.chain_nodes WHERE id = $1 AND chain_id = $2",
            node_id, chain_id,
        )
        if not n:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Node {node_id} does not belong to chain {chain_id}",
            )

    try:
        row = await db.fetchrow(
            """
            INSERT INTO chains.chain_edges
                (chain_id, source_node_id, target_node_id, priority)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            chain_id, body.source_node_id, body.target_node_id, body.priority,
        )
    except Exception as exc:
        # UNIQUE (source, target) violation
        if "unique" in str(exc).lower():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Edge between these two nodes already exists",
            )
        raise

    return EdgeOut.model_validate(dict(row))


@router.patch("/{chain_id}/edges/{edge_id}", response_model=EdgeOut)
async def update_edge(
    chain_id: int,
    edge_id: int,
    body: EdgeUpdate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)

    existing = await db.fetchrow(
        "SELECT id FROM chains.chain_edges WHERE id = $1 AND chain_id = $2",
        edge_id, chain_id,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edge not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

    set_parts, values, idx = [], [], 1
    for key, val in updates.items():
        set_parts.append(f"{key} = ${idx}")
        values.append(val)
        idx += 1

    values.append(edge_id)
    query = (
        f"UPDATE chains.chain_edges SET {', '.join(set_parts)} "
        f"WHERE id = ${idx} RETURNING *"
    )
    row = await db.fetchrow(query, *values)
    return EdgeOut.model_validate(dict(row))


@router.delete("/{chain_id}/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(
    chain_id: int,
    edge_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_chain_owner(db, chain_id, tenant_id)
    result = await db.execute(
        "DELETE FROM chains.chain_edges WHERE id = $1 AND chain_id = $2",
        edge_id, chain_id,
    )
    if result.split()[-1] == "0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edge not found")


# ===========================================================================
# CONDITIONS  – CRUD scoped to an edge
# ===========================================================================

async def _assert_edge_owner(db, edge_id: int, chain_id: int, tenant_id: int):
    """Checks chain ownership AND that the edge belongs to that chain."""
    await _assert_chain_owner(db, chain_id, tenant_id)
    row = await db.fetchrow(
        "SELECT id FROM chains.chain_edges WHERE id = $1 AND chain_id = $2",
        edge_id, chain_id,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Edge not found")


@router.get("/{chain_id}/edges/{edge_id}/conditions", response_model=List[ConditionOut])
async def list_conditions(
    chain_id: int,
    edge_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_edge_owner(db, edge_id, chain_id, tenant_id)
    rows = await db.fetch(
        "SELECT * FROM chains.chain_conditions WHERE edge_id = $1 ORDER BY created_at",
        edge_id,
    )
    return [ConditionOut.model_validate(dict(r)) for r in rows]


@router.post(
    "/{chain_id}/edges/{edge_id}/conditions",
    response_model=ConditionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_condition(
    chain_id: int,
    edge_id: int,
    body: ConditionCreate,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_edge_owner(db, edge_id, chain_id, tenant_id)

    row = await db.fetchrow(
        """
        INSERT INTO chains.chain_conditions (edge_id, condition_type, params)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        edge_id, body.condition_type.value, body.params,
    )
    return ConditionOut.model_validate(dict(row))


@router.delete(
    "/{chain_id}/edges/{edge_id}/conditions/{condition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_condition(
    chain_id: int,
    edge_id: int,
    condition_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    await _assert_edge_owner(db, edge_id, chain_id, tenant_id)
    result = await db.execute(
        "DELETE FROM chains.chain_conditions WHERE id = $1 AND edge_id = $2",
        condition_id, edge_id,
    )
    if result.split()[-1] == "0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condition not found")


# ===========================================================================
# GRAPH  –  single endpoint that returns the full chain as a graph
# ===========================================================================

@router.get("/{chain_id}/graph", response_model=ChainGraphOut)
async def get_chain_graph(
    chain_id: int,
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    """
    Returns the complete chain (nodes + edges + conditions) in one shot.
    This is what the frontend editor calls when it opens a chain.
    """
    # ── chain ──
    chain_row = await db.fetchrow(
        "SELECT * FROM chains.chains WHERE id = $1 AND tenant_id = $2",
        chain_id, tenant_id,
    )
    if not chain_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chain not found")

    # ── nodes ──
    node_rows = await db.fetch(
        "SELECT * FROM chains.chain_nodes WHERE chain_id = $1 ORDER BY created_at",
        chain_id,
    )

    # ── edges ──
    edge_rows = await db.fetch(
        "SELECT * FROM chains.chain_edges WHERE chain_id = $1 ORDER BY priority",
        chain_id,
    )

    # ── conditions (all at once, then group in Python) ──
    edge_ids = [r["id"] for r in edge_rows]
    conditions_by_edge: dict[int, list] = {eid: [] for eid in edge_ids}

    if edge_ids:
        cond_rows = await db.fetch(
            "SELECT * FROM chains.chain_conditions WHERE edge_id = ANY($1) ORDER BY created_at",
            edge_ids,
        )
        for c in cond_rows:
            conditions_by_edge[c["edge_id"]].append(
                ConditionOut.model_validate(dict(c))
            )

    # ── assemble ──
    from .models import EdgeWithConditions   # local import to avoid circular

    edges_with_conds = []
    for e in edge_rows:
        edge_dict = dict(e)
        edge_obj  = EdgeWithConditions.model_validate(edge_dict)
        edge_obj.conditions = conditions_by_edge.get(e["id"], [])
        edges_with_conds.append(edge_obj)

    return ChainGraphOut(
        chain=ChainOut.model_validate(dict(chain_row)),
        nodes=[NodeOut.model_validate(dict(n)) for n in node_rows],
        edges=edges_with_conds,
    )


# ===========================================================================
# SET START NODE  –  convenience endpoint
# ===========================================================================

@router.patch("/{chain_id}/start-node", response_model=ChainOut)
async def set_start_node(
    chain_id: int,
    node_id: int,                          # ?node_id=<id>  as query param
    tenant_id: int = Depends(get_tenant_id),
    db=Depends(get_db),
):
    """Mark a node as the entry-point of the chain."""
    await _assert_chain_owner(db, chain_id, tenant_id)

    # verify node belongs to this chain
    n = await db.fetchrow(
        "SELECT id FROM chains.chain_nodes WHERE id = $1 AND chain_id = $2",
        node_id, chain_id,
    )
    if not n:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Node not in this chain")

    row = await db.fetchrow(
        "UPDATE chains.chains SET start_node_id = $1 WHERE id = $2 RETURNING *",
        node_id, chain_id,
    )
    return ChainOut.model_validate(dict(row))
