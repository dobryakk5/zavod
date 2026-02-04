"""
Pydantic models – chain sessions
---------------------------------
These models extend the Phase 1 chain models with session tracking.
Add these to your existing models.py file.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# enums
# ---------------------------------------------------------------------------
class SessionStatus(str, Enum):
    active    = "active"      # currently running
    completed = "completed"   # user reached an end node
    paused    = "paused"      # manually paused by admin or timeout
    failed    = "failed"      # error during execution


# ---------------------------------------------------------------------------
# chain_sessions
# ---------------------------------------------------------------------------
class SessionBase(BaseModel):
    user_id:    int
    chain_id:   int
    status:     SessionStatus = SessionStatus.active
    context:    dict[str, Any] = {}


class SessionCreate(BaseModel):
    """
    Start a new session.
    tenant_id and chain_id come from the API route/context.
    user_id is the Telegram user starting the chain.
    """
    user_id:  int
    chain_id: int


class SessionUpdate(BaseModel):
    """
    Update session state (used internally by executor).
    """
    current_node_id: Optional[int]            = None
    status:          Optional[SessionStatus]  = None
    context:         Optional[dict[str, Any]] = None
    completed_at:    Optional[datetime]       = None


class SessionOut(SessionBase):
    """Single session row – returned by list/get endpoints."""
    id:                int
    tenant_id:         int
    current_node_id:   Optional[int] = None
    started_at:        datetime
    last_activity_at:  datetime
    completed_at:      Optional[datetime] = None
    created_at:        datetime
    updated_at:        datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# executor request/response models
# ---------------------------------------------------------------------------
class StartChainRequest(BaseModel):
    """API request to start a chain for a user."""
    user_id:  int
    chain_id: int


class ProcessMessageRequest(BaseModel):
    """
    API request to process an incoming user message.
    The executor will find the active session and evaluate transitions.
    """
    user_id:    int
    tenant_id:  int
    message:    dict[str, Any]  # { "text": "...", "button": "...", etc. }


class BotAction(BaseModel):
    """
    A single bot action to perform (send message, delay, etc.).
    Returned by the executor after processing.
    """
    action_type: str  # "send_text" | "send_photo" | "send_buttons" | "delay"
    payload:     dict[str, Any]
    delay_seconds: int = 0


class ProcessMessageResponse(BaseModel):
    """
    Response from process_message.
    Contains the actions the bot should perform.
    """
    session_id:     int
    actions:        list[BotAction]
    session_status: SessionStatus
