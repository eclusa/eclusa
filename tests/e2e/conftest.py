"""E2E test fixtures for the executor against the live docker-compose stack.

Connects to the real Postgres instance at localhost:5432 (docker-compose mapped port).
Does NOT use testcontainers — requires `docker compose up -d db` to be running.

Exports:
    e2e_pool          — asyncpg pool (per-test, avoids event loop issues with pytest-asyncio)
    db_conn           — per-test asyncpg connection from pool
    seed_actor        — creates a test actor, cleans up after test
    seed_cascade_with_deps — seeds 5-stage A->B->C, A->D->E topology
    cleanup_cascade   — FK-ordered deletion of cascade and related rows

Note: The pool is function-scoped rather than session-scoped because
pytest-asyncio 1.3.0 creates a new event loop per test function, which
causes 'attached to a different loop' errors with session-scoped async fixtures.
"""

import uuid

import asyncpg
import pytest

pytestmark = pytest.mark.asyncio

E2E_DSN = "postgresql://eclusa:eclusa@localhost:5432/eclusa"

# Track all cascade IDs seeded during a test so cleanup can happen in the right order.
# Actor cleanup must happen AFTER all cascade data is removed.
_test_cascade_ids: list[str] = []


@pytest.fixture
async def e2e_pool():
    """Per-test asyncpg pool connected to the live docker-compose DB."""
    try:
        pool = await asyncpg.create_pool(E2E_DSN, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"docker-compose db not running: {exc}")
        return  # unreachable but keeps type checkers happy

    yield pool

    await pool.close()


@pytest.fixture
async def db_conn(e2e_pool):
    """Per-test asyncpg connection acquired from the pool."""
    async with e2e_pool.acquire() as conn:
        yield conn


@pytest.fixture
async def seed_actor(db_conn):
    """Create a disposable test actor and clean up after the test.

    Cleanup removes all intents created by this actor (and their cascades,
    stages, ledger entries) before deleting the actor itself, avoiding FK
    violations.
    """
    actor_id = str(uuid.uuid4())
    await db_conn.execute(
        """
        INSERT INTO actor (id, type, identity, permissions)
        VALUES ($1::uuid, 'system'::actor_type, $2, $3::jsonb)
        """,
        actor_id,
        f"e2e-test-executor-{actor_id[:8]}",
        '{"resolve_gates":["*"],"view_costs":true}',
    )

    yield actor_id

    # Cleanup: remove all data referencing this actor, then the actor itself.
    # Must remove cascades/intents first due to FK constraints.
    # Find all intents created by this actor
    intent_rows = await db_conn.fetch(
        "SELECT id FROM intent WHERE created_by = $1::uuid", actor_id
    )
    for irow in intent_rows:
        intent_id = str(irow["id"])
        # Find cascades for this intent
        cascade_rows = await db_conn.fetch(
            "SELECT id FROM cascade WHERE intent_id = $1::uuid", intent_id
        )
        for crow in cascade_rows:
            await cleanup_cascade(db_conn, str(crow["id"]))
        # Delete the intent itself (cascade cleanup already handled it if
        # it was part of a cascade, but the intent might still exist if
        # cleanup_cascade didn't find it)
        await db_conn.execute(
            "DELETE FROM intent WHERE id = $1::uuid", intent_id
        )

    # Now safe to delete the actor
    await db_conn.execute("DELETE FROM actor WHERE id = $1::uuid", actor_id)


async def seed_cascade_with_deps(conn: asyncpg.Connection, actor_id: str) -> dict:
    """Seed a 5-stage cascade with topology A -> B -> C, A -> D -> E.

    All stages are type='narrowing', state='pending', input='{}' (no scc_stage key).
    This means dispatch_narrowing falls through to _resolve_stage_immediately.

    Returns:
        {
            "intent_id": str,
            "cascade_id": str,
            "stages": {"A": str, "B": str, "C": str, "D": str, "E": str},
        }
    """
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())

    stage_ids = {name: str(uuid.uuid4()) for name in ("A", "B", "C", "D", "E")}

    async with conn.transaction():
        # Intent
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'E2E test cascade', $2::uuid)
            """,
            intent_id,
            actor_id,
        )

        # Cascade
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test": true}'::jsonb, 'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )

        # Stage A: no dependencies
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state, '{}'::uuid[], '{}'::jsonb)
            """,
            stage_ids["A"],
            cascade_id,
        )

        # Stage B: depends on A
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state, ARRAY[$3::uuid], '{}'::jsonb)
            """,
            stage_ids["B"],
            cascade_id,
            stage_ids["A"],
        )

        # Stage C: depends on B
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state, ARRAY[$3::uuid], '{}'::jsonb)
            """,
            stage_ids["C"],
            cascade_id,
            stage_ids["B"],
        )

        # Stage D: depends on A
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state, ARRAY[$3::uuid], '{}'::jsonb)
            """,
            stage_ids["D"],
            cascade_id,
            stage_ids["A"],
        )

        # Stage E: depends on D
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state, ARRAY[$3::uuid], '{}'::jsonb)
            """,
            stage_ids["E"],
            cascade_id,
            stage_ids["D"],
        )

    return {
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stages": stage_ids,
    }


async def cleanup_cascade(conn: asyncpg.Connection, cascade_id: str) -> None:
    """Delete a cascade and all related rows in correct FK order.

    Order: ledger_entry (with trigger bypass) -> work_session -> stage -> cascade -> intent.

    The ledger_entry table has an append-only immutability trigger. For test cleanup,
    we temporarily disable it, delete, then re-enable.
    """
    # Get the intent_id before we delete the cascade
    row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid", cascade_id
    )
    if row is None:
        return  # cascade already gone
    intent_id = str(row["intent_id"])

    # Get all stage IDs for this cascade (needed for work_session cleanup)
    stage_rows = await conn.fetch(
        "SELECT id FROM stage WHERE cascade_id = $1::uuid", cascade_id
    )
    stage_ids = [r["id"] for r in stage_rows]

    # Disable the immutability trigger for cleanup
    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )

    try:
        async with conn.transaction():
            # 1. Ledger entries referencing this cascade
            await conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )

            # 2. Work sessions referencing any of these stages
            if stage_ids:
                await conn.execute(
                    "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                    stage_ids,
                )

            # 3. Stages
            await conn.execute(
                "DELETE FROM stage WHERE cascade_id = $1::uuid", cascade_id
            )

            # 4. Cascade
            await conn.execute(
                "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
            )

            # 5. Intent
            await conn.execute(
                "DELETE FROM intent WHERE id = $1::uuid", intent_id
            )
    finally:
        # Always re-enable the trigger
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )
