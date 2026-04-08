"""Cascade topology seeders for executor tests.

Each function seeds a complete, self-contained cascade shape into the DB.
Returns a dict of IDs so tests can reference specific rows.

All functions require an asyncpg connection with migrations applied.
"""

import asyncpg


async def seed_system_actor(conn: asyncpg.Connection) -> str:
    """Seed a system actor and return its ID. Idempotent by identity."""
    row = await conn.fetchrow(
        "SELECT id FROM actor WHERE identity = 'system-test-executor' LIMIT 1"
    )
    if row:
        return str(row["id"])
    row = await conn.fetchrow("""
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'system-test-executor')
        RETURNING id
    """)
    return str(row["id"])


async def seed_linear_cascade(conn: asyncpg.Connection) -> dict:
    """Seed a 3-stage linear cascade: A -> B -> C.

    Returns: {cascade_id, intent_id, actor_id, stage_ids: [A, B, C]}
    """
    actor_row = await conn.fetchrow("""
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'system-test-linear')
        RETURNING id
    """)
    actor_id = str(actor_row["id"])

    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'test intent linear', $1::uuid)
        RETURNING id
    """,
        actor_id,
    )
    intent_id = str(intent_row["id"])

    cascade_row = await conn.fetchrow(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
        RETURNING id
    """,
        intent_id,
    )
    cascade_id = str(cascade_row["id"])

    stage_a_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}')
        RETURNING id
    """,
        cascade_id,
    )
    stage_a_id = str(stage_a_row["id"])

    stage_b_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid])
        RETURNING id
    """,
        cascade_id,
        stage_a_id,
    )
    stage_b_id = str(stage_b_row["id"])

    stage_c_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid])
        RETURNING id
    """,
        cascade_id,
        stage_b_id,
    )
    stage_c_id = str(stage_c_row["id"])

    return {
        "cascade_id": cascade_id,
        "intent_id": intent_id,
        "actor_id": actor_id,
        "stage_ids": [stage_a_id, stage_b_id, stage_c_id],
    }


async def seed_branching_cascade(conn: asyncpg.Connection) -> dict:
    """Seed a branching cascade: root -> [branch_a, branch_b] -> join.

    Returns: {cascade_id, intent_id, actor_id, stage_ids: {root, branch_a, branch_b, join}}
    """
    actor_row = await conn.fetchrow("""
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'system-test-branching')
        RETURNING id
    """)
    actor_id = str(actor_row["id"])

    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'test intent branching', $1::uuid)
        RETURNING id
    """,
        actor_id,
    )
    intent_id = str(intent_row["id"])

    cascade_row = await conn.fetchrow(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
        RETURNING id
    """,
        intent_id,
    )
    cascade_id = str(cascade_row["id"])

    root_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}')
        RETURNING id
    """,
        cascade_id,
    )
    root_id = str(root_row["id"])

    branch_a_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid])
        RETURNING id
    """,
        cascade_id,
        root_id,
    )
    branch_a_id = str(branch_a_row["id"])

    branch_b_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid])
        RETURNING id
    """,
        cascade_id,
        root_id,
    )
    branch_b_id = str(branch_b_row["id"])

    join_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid, $3::uuid])
        RETURNING id
    """,
        cascade_id,
        branch_a_id,
        branch_b_id,
    )
    join_id = str(join_row["id"])

    return {
        "cascade_id": cascade_id,
        "intent_id": intent_id,
        "actor_id": actor_id,
        "stage_ids": {
            "root": root_id,
            "branch_a": branch_a_id,
            "branch_b": branch_b_id,
            "join": join_id,
        },
    }


async def seed_nested_cascade(conn: asyncpg.Connection) -> dict:
    """Seed a parent cascade with one stage that spawns a sub-cascade.

    The child cascade has parent_stage_id set to the parent stage id.
    Returns: {parent_cascade_id, child_cascade_id, parent_stage_id, actor_id}

    Note: cascade table has no parent_stage_id column in schema v0001.
    The nesting relationship is represented by the intent hierarchy (parent_id)
    and the child cascade's intent tracing back to the parent stage via ledger.
    This seeder seeds two cascades under the same intent to simulate nesting.
    """
    actor_row = await conn.fetchrow("""
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'system-test-nested')
        RETURNING id
    """)
    actor_id = str(actor_row["id"])

    parent_intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'test intent nested parent', $1::uuid)
        RETURNING id
    """,
        actor_id,
    )
    parent_intent_id = str(parent_intent_row["id"])

    parent_cascade_row = await conn.fetchrow(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
        RETURNING id
    """,
        parent_intent_id,
    )
    parent_cascade_id = str(parent_cascade_row["id"])

    parent_stage_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'active', '{}')
        RETURNING id
    """,
        parent_cascade_id,
    )
    parent_stage_id = str(parent_stage_row["id"])

    # Child intent traces back to parent via parent_id
    child_intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, parent_id, source, raw, created_by)
        VALUES (gen_random_uuid(), $1::uuid, 'manual', 'test intent nested child', $2::uuid)
        RETURNING id
    """,
        parent_intent_id,
        actor_id,
    )
    child_intent_id = str(child_intent_row["id"])

    child_cascade_row = await conn.fetchrow(
        """
        INSERT INTO cascade (id, intent_id, shape, state)
        VALUES (gen_random_uuid(), $1::uuid, '{}', 'active')
        RETURNING id
    """,
        child_intent_id,
    )
    child_cascade_id = str(child_cascade_row["id"])

    return {
        "parent_cascade_id": parent_cascade_id,
        "child_cascade_id": child_cascade_id,
        "parent_stage_id": parent_stage_id,
        "actor_id": actor_id,
    }
