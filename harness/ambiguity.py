"""harness/ambiguity.py — ambiguityUp tool for work session agents.

Provides make_ambiguity_up_tool(agent) which injects an ambiguityUp tool into
a pydantic-ai Agent. When called by the agent, it:
  1. Creates a gate-type stage in the current cascade
  2. Surfaces the gate (marks blocked, writes ledger, dispatches to adapter)
  3. Pauses the work session

The session harness transparently resumes when the gate is resolved — from the
agent's perspective, ambiguityUp returned an answer eventually.

Per RFC §5.2: "ambiguity up, decisions down" governance primitive at the agent level.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import asyncpg
from pydantic_ai import Agent, RunContext

from executor.dispatch import surface_gate

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"


@dataclass
class AmbiguityContext:
    """Dependency context injected into the ambiguityUp tool.

    Attributes:
        conn: asyncpg connection for all DB writes.
        session_id: UUID of the running work_session row.
        cascade_id: UUID of the cascade this session belongs to.
        actor_id: UUID of the actor who owns this session.
        snapshot_store: Optional SnapshotStore for full pause lifecycle.
            If None, the session is paused via direct UPDATE (no snapshot saved).
    """

    conn: asyncpg.Connection
    session_id: str
    cascade_id: str
    actor_id: str
    snapshot_store: Any = None  # harness.snapshot.SnapshotStore, optional


def make_ambiguity_up_tool(agent: Agent) -> Agent:
    """Inject the ambiguityUp tool into a pydantic-ai Agent.

    Registers an `ambiguityUp` tool on the given agent that:
      - Inserts a gate-type stage into the cascade
      - Calls surface_gate() to mark blocked + write ledger + dispatch adapter
      - Pauses the work session (with or without a snapshot)

    The same agent is returned so this function can be used in a fluent chain.

    Example:
        agent = Agent(model, deps_type=AmbiguityContext)
        make_ambiguity_up_tool(agent)
        # or chained:
        agent = make_ambiguity_up_tool(Agent(model, deps_type=AmbiguityContext))

    Args:
        agent: A pydantic-ai Agent whose deps_type includes AmbiguityContext fields.

    Returns:
        The same agent with the ambiguityUp tool registered.
    """

    @agent.tool
    async def ambiguityUp(ctx: RunContext[AmbiguityContext], reason: str) -> str:
        """Surface an ambiguity as a gate and pause this session.

        Call this when you encounter a requirement, constraint, or decision
        that cannot be resolved without human input. Provide a clear description
        of what is ambiguous and why it blocks progress.

        Returns a string of the form 'gate:<uuid>' once the gate is created and
        the session is paused. The harness will resume this session transparently
        when the gate is resolved — from your perspective, this call returned
        an answer.

        Args:
            reason: A concise description of the ambiguity, readable by a human
                    who will resolve it.
        """
        gate_id = str(uuid.uuid4())
        conn = ctx.deps.conn
        cascade_id = ctx.deps.cascade_id
        actor_id = ctx.deps.actor_id
        session_id = ctx.deps.session_id

        # 1. Insert the gate stage row
        gate_input = json.dumps({
            "gate_description": reason,
            "channel_type": "email",
            "raised_by_session": session_id,
        })
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'gate', 'pending', '{}'::uuid[], $3::jsonb)
            """,
            gate_id,
            cascade_id,
            gate_input,
        )

        # Build the stage dict expected by surface_gate
        gate_stage = {
            "id": gate_id,
            "cascade_id": cascade_id,
            "type": "gate",
            "input": {
                "gate_description": reason,
                "channel_type": "email",
                "raised_by_session": session_id,
            },
        }

        # 2. Surface the gate (marks blocked, writes gate_surfaced ledger, dispatches adapter)
        await surface_gate(conn, gate_stage, actor_id)

        # 3. Pause the work session
        snapshot_store = ctx.deps.snapshot_store
        if snapshot_store is not None:
            from harness.native import pause_work_session
            await pause_work_session(
                conn=conn,
                session_id=session_id,
                snapshot_store=snapshot_store,
                actor_id=actor_id,
            )
        else:
            # No snapshot store — mark paused without saving a snapshot
            await conn.execute(
                """
                UPDATE work_session
                SET state = 'paused', paused_at = NOW()
                WHERE id = $1::uuid
                """,
                session_id,
            )
            logger.debug(
                "ambiguityUp: session %s paused (no snapshot store)",
                session_id,
            )

        logger.info(
            "ambiguityUp: gate %s created and surfaced, session %s paused (reason=%r)",
            gate_id,
            session_id,
            reason,
        )
        return f"gate:{gate_id}"

    return agent
