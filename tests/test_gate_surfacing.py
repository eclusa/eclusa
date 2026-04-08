"""Gate surfacing and resolution tests (EXEC-06, EXEC-07).

Plan 05-03: real adapter dispatch via AdapterRegistry + scoped pg_notify.
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
import psycopg
import pytest
from tests.helpers.topology import seed_linear_cascade

from adapters.protocol import AdapterProtocol, GateContext
from adapters.registry import AdapterRegistry
from executor.dispatch import resolve_gate, surface_gate

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockAdapter(AdapterProtocol):
    """Test double that records surface_gate calls."""

    def __init__(self) -> None:
        self.calls: list[GateContext] = []

    async def surface_gate(self, context: GateContext) -> None:
        self.calls.append(context)


async def _seed_gate_stage(
    conn: asyncpg.Connection,
    cascade_id: str,
    *,
    input_data: dict | None = None,
) -> str:
    """Insert a gate stage in 'active' state and return its id."""
    input_json = json.dumps(input_data or {})
    row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'active', '{}', $2::jsonb)
        RETURNING id
        """,
        cascade_id,
        input_json,
    )
    return str(row["id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_surface_gate_real_dispatch(conn, pg_container) -> None:
    """EXEC-06: surface_gate() dispatches to the registered adapter, not a stub."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]

    # Seed gate stage with adapter-specific input
    gate_id = await _seed_gate_stage(
        conn,
        cascade_id,
        input_data={
            "channel_type": "mock",
            "gate_description": "Human review required",
            "eligible_actor_ids": ["actor-1", "actor-2"],
            "model_recommendation": "approve",
        },
    )

    # Register fresh mock adapter under "mock" channel
    local_registry = AdapterRegistry()
    mock_adapter = MockAdapter()
    local_registry.register("mock", mock_adapter)

    # Patch the module-level registry in adapters.registry (used by dispatch.py via import)
    import adapters.registry as reg_module

    orig = reg_module.registry
    reg_module.registry = local_registry
    # Also rebind what dispatch.py imported at module load time
    import executor.dispatch as dispatch_module

    dispatch_module.registry = local_registry

    try:
        stage_row = {
            "id": gate_id,
            "type": "gate",
            "cascade_id": cascade_id,
            "input": {
                "channel_type": "mock",
                "gate_description": "Human review required",
                "eligible_actor_ids": ["actor-1", "actor-2"],
                "model_recommendation": "approve",
            },
        }
        await surface_gate(conn, stage_row, actor_id)
    finally:
        dispatch_module.registry = orig
        reg_module.registry = orig

    # Stage must be blocked in DB
    row = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", gate_id)
    assert row["state"] == "blocked", f"Expected blocked, got {row['state']}"

    # gate_surfaced ledger entry must exist
    ledger = await conn.fetchrow(
        "SELECT type FROM ledger_entry WHERE stage_id = $1::uuid AND type = 'gate_surfaced'",
        gate_id,
    )
    assert ledger is not None, "Expected gate_surfaced ledger entry"

    # Mock adapter must have been called with correct context
    assert len(mock_adapter.calls) == 1, (
        f"Expected 1 adapter call, got {len(mock_adapter.calls)}"
    )
    ctx = mock_adapter.calls[0]
    assert ctx.cascade_id == cascade_id
    assert ctx.stage_id == gate_id
    assert ctx.gate_description == "Human review required"
    assert ctx.eligible_actor_ids == ["actor-1", "actor-2"]
    assert ctx.model_recommendation == "approve"
    assert f"/gates/{gate_id}/resolve" in ctx.resolve_url


async def test_resolve_gate_fires_notify(conn, pg_container) -> None:
    """EXEC-07: resolve_gate() fires NOTIFY on 'stage_changed' after resolving the gate."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]

    # Seed a blocked gate
    gate_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'blocked', '{}', '{}'::jsonb)
        RETURNING id
        """,
        cascade_id,
    )
    gate_id = str(gate_row["id"])

    # Build a psycopg3 LISTEN connection on stage_changed
    url = pg_container.get_connection_url()
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)

    notified_channel: list[str] = []
    notified_payload: list[str] = []

    async with await psycopg.AsyncConnection.connect(
        url, autocommit=True
    ) as listen_conn:
        await listen_conn.execute("LISTEN stage_changed")

        async def collect_one() -> None:
            async for notify in listen_conn.notifies():
                notified_channel.append(notify.channel)
                notified_payload.append(notify.payload)
                return

        listen_task = asyncio.create_task(collect_one())
        await asyncio.sleep(0.05)  # let LISTEN register

        await resolve_gate(conn, gate_id, actor_id)

        try:
            await asyncio.wait_for(listen_task, timeout=3.0)
        except asyncio.TimeoutError:
            listen_task.cancel()

    assert len(notified_channel) >= 1, "Expected NOTIFY on stage_changed"
    assert "stage_changed" in notified_channel
    payload = json.loads(notified_payload[0])
    assert payload["stage_id"] == gate_id
    assert payload["cascade_id"] == cascade_id


async def test_resolve_gate_fires_scoped_notify(conn, pg_container) -> None:
    """EXEC-07: resolve_gate fires scoped NOTIFY on 'stage_changed:{cascade_id}' (D-05)."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]

    gate_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'blocked', '{}', '{}'::jsonb)
        RETURNING id
        """,
        cascade_id,
    )
    gate_id = str(gate_row["id"])

    url = pg_container.get_connection_url()
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)

    scoped_channel = f"stage_changed:{cascade_id}"
    notified_payload: list[str] = []

    async with await psycopg.AsyncConnection.connect(
        url, autocommit=True
    ) as listen_conn:
        # pg_notify channel names with hyphens need quoting in LISTEN
        await listen_conn.execute(f'LISTEN "{scoped_channel}"')

        async def collect_scoped() -> None:
            async for notify in listen_conn.notifies():
                if notify.channel == scoped_channel:
                    notified_payload.append(notify.payload)
                    return

        listen_task = asyncio.create_task(collect_scoped())
        await asyncio.sleep(0.05)

        await resolve_gate(conn, gate_id, actor_id)

        try:
            await asyncio.wait_for(listen_task, timeout=3.0)
        except asyncio.TimeoutError:
            listen_task.cancel()

    assert len(notified_payload) >= 1, f"Expected NOTIFY on {scoped_channel}"
    payload = json.loads(notified_payload[0])
    assert payload["cascade_id"] == cascade_id
    assert payload["stage_id"] == gate_id


async def test_gate_sibling_branch_continues(conn) -> None:
    """EXEC-06: Surfacing one gate does not block sibling stages in the cascade."""
    topo = await seed_linear_cascade(conn)
    cascade_id = topo["cascade_id"]
    actor_id = topo["actor_id"]

    # Insert two parallel gate stages (root-level siblings, no shared deps)
    gate1_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'active', '{}', '{}'::jsonb)
        RETURNING id
        """,
        cascade_id,
    )
    gate1_id = str(gate1_row["id"])

    gate2_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'pending', '{}', '{}'::jsonb)
        RETURNING id
        """,
        cascade_id,
    )
    gate2_id = str(gate2_row["id"])

    stage_row = {
        "id": gate1_id,
        "type": "gate",
        "cascade_id": cascade_id,
        "input": {},
    }
    await surface_gate(conn, stage_row, actor_id)

    # Gate 1 must be blocked
    row1 = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", gate1_id)
    assert row1["state"] == "blocked"

    # Gate 2 (sibling) must remain unaffected — still 'pending'
    row2 = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", gate2_id)
    assert row2["state"] == "pending", f"Sibling stage affected: state={row2['state']}"
