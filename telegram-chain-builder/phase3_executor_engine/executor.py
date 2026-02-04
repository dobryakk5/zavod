"""
Chain Executor
--------------
The state machine that executes chains for users.

Usage:
    executor = ChainExecutor(db)
    
    # Start a chain for a user
    await executor.start_chain(user_id=12345, chain_id=1, tenant_id=1)
    
    # Process an incoming user message
    actions = await executor.process_user_message(
        user_id=12345,
        tenant_id=1,
        user_message={"text": "да"}
    )
    
    # Actions tell the bot what to do:
    # [
    #   {"action_type": "send_text", "payload": {"text": "..."}, "delay_seconds": 0},
    #   {"action_type": "send_photo", "payload": {...}, "delay_seconds": 3},
    # ]
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from .conditions import evaluate_conditions

logger = logging.getLogger(__name__)


class ChainExecutor:
    """
    Executes chains by advancing users through nodes based on conditions.
    """

    def __init__(self, db):
        """
        Args:
            db: Async database connection/session (asyncpg or SQLAlchemy).
                Must support: fetchrow, fetch, execute.
        """
        self.db = db

    # =======================================================================
    # START CHAIN
    # =======================================================================

    async def start_chain(
        self,
        user_id: int,
        chain_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        """
        Starts a new chain session for a user.

        Returns:
            dict with session_id and initial actions to perform.
        """
        # ── load chain ──────────────────────────────────────────────────
        chain_row = await self.db.fetchrow(
            "SELECT * FROM chains.chains WHERE id = $1 AND tenant_id = $2",
            chain_id, tenant_id,
        )
        if not chain_row:
            raise ValueError(f"Chain {chain_id} not found for tenant {tenant_id}")

        chain = dict(chain_row)

        if not chain["start_node_id"]:
            raise ValueError(f"Chain {chain_id} has no start node")

        # ── check for existing active session ──────────────────────────
        existing = await self.db.fetchrow(
            """
            SELECT id FROM chains.chain_sessions
            WHERE user_id = $1 AND chain_id = $2 AND status = 'active'
            """,
            user_id, chain_id,
        )
        if existing:
            # Resume existing session
            session_id = existing["id"]
            logger.info(f"Resuming existing session {session_id} for user {user_id}")
        else:
            # ── create new session ──────────────────────────────────────
            session_row = await self.db.fetchrow(
                """
                INSERT INTO chains.chain_sessions
                    (user_id, tenant_id, chain_id, current_node_id, status, context)
                VALUES ($1, $2, $3, $4, 'active', '{}')
                RETURNING *
                """,
                user_id, tenant_id, chain_id, chain["start_node_id"],
            )
            session_id = session_row["id"]
            logger.info(f"Started new session {session_id} for user {user_id} in chain {chain_id}")

        # ── advance to start node ───────────────────────────────────────
        actions = await self._advance_to_node(session_id, chain["start_node_id"])

        return {
            "session_id": session_id,
            "actions": actions,
        }

    # =======================================================================
    # PROCESS USER MESSAGE
    # =======================================================================

    async def process_user_message(
        self,
        user_id: int,
        tenant_id: int,
        user_message: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Processes an incoming user message and transitions to the next node.

        Args:
            user_id:      Telegram user ID
            tenant_id:    Tenant ID (for multi-tenancy isolation)
            user_message: Normalized message dict, e.g.:
                          {"text": "да"} or {"button": "Продукт"}

        Returns:
            dict with:
              - session_id: int
              - actions: list of BotAction dicts
              - session_status: str (active / completed / etc.)
        """
        # ── find active session ─────────────────────────────────────────
        session_row = await self.db.fetchrow(
            """
            SELECT * FROM chains.chain_sessions
            WHERE user_id = $1 AND tenant_id = $2 AND status = 'active'
            ORDER BY last_activity_at DESC
            LIMIT 1
            """,
            user_id, tenant_id,
        )

        if not session_row:
            # No active session → user is not in any chain
            logger.warning(f"No active session for user {user_id}")
            return {
                "session_id": None,
                "actions": [],
                "session_status": "none",
            }

        session = dict(session_row)
        session_id = session["id"]
        current_node_id = session["current_node_id"]

        if not current_node_id:
            logger.error(f"Session {session_id} has no current_node_id")
            return {"session_id": session_id, "actions": [], "session_status": session["status"]}

        # ── load outgoing edges from current node ───────────────────────
        edges = await self._get_edges_with_conditions(current_node_id)

        # ── evaluate conditions & pick the first matching edge ──────────
        matching_edge = None
        for edge in edges:
            if evaluate_conditions(edge["conditions"], user_message, session.get("context", {})):
                matching_edge = edge
                break

        if not matching_edge:
            # No edge matched → user is stuck (or reached a leaf node)
            logger.warning(f"No matching edge from node {current_node_id} for user {user_id}")
            # Optionally mark session as completed
            await self.db.execute(
                """
                UPDATE chains.chain_sessions
                SET status = 'completed', completed_at = now()
                WHERE id = $1
                """,
                session_id,
            )
            return {
                "session_id": session_id,
                "actions": [],
                "session_status": "completed",
            }

        # ── save user answer in context ─────────────────────────────────
        context = session.get("context", {})
        if "answers" not in context:
            context["answers"] = {}
        context["answers"][str(current_node_id)] = user_message
        context["last_message_at"] = datetime.utcnow().isoformat()

        await self.db.execute(
            "UPDATE chains.chain_sessions SET context = $1, last_activity_at = now() WHERE id = $2",
            context, session_id,
        )

        # ── advance to target node ──────────────────────────────────────
        target_node_id = matching_edge["target_node_id"]
        actions = await self._advance_to_node(session_id, target_node_id)

        return {
            "session_id": session_id,
            "actions": actions,
            "session_status": "active",
        }

    # =======================================================================
    # ADVANCE TO NODE (internal)
    # =======================================================================

    async def _advance_to_node(
        self,
        session_id: int,
        node_id: int,
    ) -> list[dict[str, Any]]:
        """
        Moves the session to a new node and generates actions (send message, delay, etc.).

        Returns:
            List of BotAction dicts to perform.
        """
        # ── load node ───────────────────────────────────────────────────
        node_row = await self.db.fetchrow(
            "SELECT * FROM chains.chain_nodes WHERE id = $1",
            node_id,
        )
        if not node_row:
            logger.error(f"Node {node_id} not found")
            return []

        node = dict(node_row)

        # ── update session ──────────────────────────────────────────────
        await self.db.execute(
            """
            UPDATE chains.chain_sessions
            SET current_node_id = $1, last_activity_at = now()
            WHERE id = $2
            """,
            node_id, session_id,
        )

        # ── generate bot actions ────────────────────────────────────────
        actions = []

        # Add the message action based on node type
        if node["node_type"] == "text":
            actions.append({
                "action_type": "send_text",
                "payload": node["payload"],
                "delay_seconds": node["delay_seconds"],
            })

        elif node["node_type"] == "photo":
            actions.append({
                "action_type": "send_photo",
                "payload": node["payload"],
                "delay_seconds": node["delay_seconds"],
            })

        elif node["node_type"] == "buttons":
            actions.append({
                "action_type": "send_buttons",
                "payload": node["payload"],
                "delay_seconds": node["delay_seconds"],
            })

        # ── check for timeout edges (schedule timeout tasks) ────────────
        # If any outgoing edge has a timeout condition, schedule a timeout task
        edges = await self._get_edges_with_conditions(node_id)
        for edge in edges:
            for cond in edge.get("conditions", []):
                if cond["condition_type"] == "timeout":
                    timeout_seconds = cond["params"].get("timeout_seconds", 300)
                    # Here you would schedule a task to fire after timeout_seconds
                    # Example (pseudocode):
                    #   tasks.check_timeout.apply_async(
                    #       args=[session_id, edge["id"]],
                    #       countdown=timeout_seconds
                    #   )
                    actions.append({
                        "action_type": "schedule_timeout",
                        "payload": {
                            "session_id": session_id,
                            "edge_id": edge["id"],
                            "timeout_seconds": timeout_seconds,
                        },
                        "delay_seconds": 0,
                    })

        logger.info(f"Advanced session {session_id} to node {node_id}, actions: {len(actions)}")
        return actions

    # =======================================================================
    # HELPERS
    # =======================================================================

    async def _get_edges_with_conditions(self, source_node_id: int) -> list[dict[str, Any]]:
        """
        Loads all outgoing edges from a node, ordered by priority, with conditions.
        """
        edge_rows = await self.db.fetch(
            """
            SELECT * FROM chains.chain_edges
            WHERE source_node_id = $1
            ORDER BY priority
            """,
            source_node_id,
        )

        edges = [dict(e) for e in edge_rows]
        edge_ids = [e["id"] for e in edges]

        # Load all conditions for these edges
        if not edge_ids:
            return []

        cond_rows = await self.db.fetch(
            """
            SELECT * FROM chains.chain_conditions
            WHERE edge_id = ANY($1)
            ORDER BY created_at
            """,
            edge_ids,
        )

        # Group conditions by edge_id
        conditions_by_edge = {eid: [] for eid in edge_ids}
        for c in cond_rows:
            conditions_by_edge[c["edge_id"]].append(dict(c))

        # Attach conditions to edges
        for edge in edges:
            edge["conditions"] = conditions_by_edge.get(edge["id"], [])

        return edges

    # =======================================================================
    # TIMEOUT HANDLER
    # =======================================================================

    async def process_timeout(
        self,
        session_id: int,
        edge_id: int,
    ) -> dict[str, Any]:
        """
        Called when a timeout task fires.
        Advances the session to the target node of the timeout edge.

        Args:
            session_id: The session that timed out
            edge_id:    The edge with the timeout condition

        Returns:
            dict with actions to perform
        """
        # ── load edge ───────────────────────────────────────────────────
        edge_row = await self.db.fetchrow(
            "SELECT * FROM chains.chain_edges WHERE id = $1",
            edge_id,
        )
        if not edge_row:
            logger.error(f"Edge {edge_id} not found")
            return {"actions": []}

        edge = dict(edge_row)

        # ── verify session is still active and on the source node ───────
        session_row = await self.db.fetchrow(
            "SELECT * FROM chains.chain_sessions WHERE id = $1",
            session_id,
        )
        if not session_row:
            logger.warning(f"Session {session_id} not found")
            return {"actions": []}

        session = dict(session_row)

        if session["status"] != "active":
            logger.info(f"Session {session_id} is not active (status={session['status']})")
            return {"actions": []}

        if session["current_node_id"] != edge["source_node_id"]:
            logger.info(f"Session {session_id} has moved away from node {edge['source_node_id']}")
            return {"actions": []}

        # ── advance to timeout target node ──────────────────────────────
        target_node_id = edge["target_node_id"]
        actions = await self._advance_to_node(session_id, target_node_id)

        logger.info(f"Timeout fired for session {session_id}, advanced to node {target_node_id}")
        return {"actions": actions}
