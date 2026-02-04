"""
Pydantic models – chains feature
---------------------------------
Naming convention that already exists in the project:
    *Base   – mirrors the DB row  (used internally / as a base)
    *Create – POST body
    *Update – PATCH body  (all fields Optional)
    *Response / *Out – what the API returns

The "graph" response at the bottom is the single payload the
frontend editor needs to reconstruct the full visual graph.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# enums  (single source of truth – match the DB CHECK constraints)
# ---------------------------------------------------------------------------
class ChainStatus(str, Enum):
    draft    = "draft"
    active   = "active"
    paused   = "paused"
    archived = "archived"


class NodeType(str, Enum):
    text    = "text"       # plain text message
    photo   = "photo"      # photo + optional caption
    buttons = "buttons"    # text + inline keyboard buttons


class ConditionType(str, Enum):
    button_press   = "button_press"    # user tapped a specific button
    text_contains  = "text_contains"   # message contains substring
    text_regex     = "text_regex"      # message matches regex
    timeout        = "timeout"         # user did not reply in N seconds
    any_reply      = "any_reply"       # catch-all – any user message


# ---------------------------------------------------------------------------
# chains
# ---------------------------------------------------------------------------
class ChainBase(BaseModel):
    name:        str
    description: Optional[str] = None
    status:      ChainStatus   = ChainStatus.draft


class ChainCreate(ChainBase):
    """POST /chains/"""
    pass                                # tenant_id injected server-side from auth


class ChainUpdate(BaseModel):
    """PATCH /chains/{id}"""
    name:        Optional[str]         = None
    description: Optional[str]         = None
    status:      Optional[ChainStatus] = None


class ChainOut(ChainBase):
    """Single chain row – used in list responses."""
    id:            int
    tenant_id:     int
    start_node_id: Optional[int] = None
    created_at:    datetime
    updated_at:    datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# chain_nodes
# ---------------------------------------------------------------------------
class NodeBase(BaseModel):
    node_type:     NodeType
    payload:       dict[str, Any]
    delay_seconds: int = Field(default=0, ge=0)
    pos_x:         float = 0.0
    pos_y:         float = 0.0


class NodeCreate(NodeBase):
    """POST /chains/{chain_id}/nodes/"""
    pass


class NodeUpdate(BaseModel):
    """PATCH /chains/{chain_id}/nodes/{id}"""
    node_type:     Optional[NodeType]       = None
    payload:       Optional[dict[str, Any]] = None
    delay_seconds: Optional[int]            = Field(default=None, ge=0)
    pos_x:         Optional[float]          = None
    pos_y:         Optional[float]          = None


class NodeOut(NodeBase):
    id:         int
    chain_id:   int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# chain_edges
# ---------------------------------------------------------------------------
class EdgeBase(BaseModel):
    source_node_id: int
    target_node_id: int
    priority:       int = 0


class EdgeCreate(EdgeBase):
    """POST /chains/{chain_id}/edges/"""
    pass


class EdgeUpdate(BaseModel):
    """PATCH /chains/{chain_id}/edges/{id}"""
    source_node_id: Optional[int] = None
    target_node_id: Optional[int] = None
    priority:       Optional[int] = None


class EdgeOut(EdgeBase):
    id:         int
    chain_id:   int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# chain_conditions
# ---------------------------------------------------------------------------
class ConditionBase(BaseModel):
    condition_type: ConditionType
    params:         dict[str, Any] = {}


class ConditionCreate(ConditionBase):
    """POST /chains/{chain_id}/edges/{edge_id}/conditions/"""
    pass


class ConditionOut(ConditionBase):
    id:         int
    edge_id:    int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# graph  –  the single "give me everything" response
# ---------------------------------------------------------------------------
class EdgeWithConditions(EdgeOut):
    """Edge enriched with its conditions – used in the graph response."""
    conditions: List[ConditionOut] = []


class ChainGraphOut(BaseModel):
    """
    Full graph payload.  The frontend editor fetches this once on open
    and uses it to render the entire visual tree.
    """
    chain:  ChainOut
    nodes:  List[NodeOut]
    edges:  List[EdgeWithConditions]

    model_config = {"from_attributes": True}
