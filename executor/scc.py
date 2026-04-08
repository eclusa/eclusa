"""executor/scc.py — SCC cascade template creation (SCC-01, D-01, D-02).

create_scc_cascade(intent_id, actor_id, conn): creates a 7-stage cascade.
7 stages: refine → intent_validation_fanout → match → cohere → formalize → derive → generate.
All stages are type='narrowing', state='pending'.
Each stage input JSONB has a stage routing key plus stage-specific keys.
The fanout stage input includes 'refine_stage_id' for the dispatch handler to read (Pitfall 2).
"""

from __future__ import annotations

import json
import uuid

import asyncpg


async def create_scc_cascade(
    intent_id: str, actor_id: str, conn: asyncpg.Connection
) -> str:
    """Create the SCC cascade template and return the new cascade ID."""
    cascade_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{}', 'active')
        """,
            cascade_id,
            intent_id,
        )

        async def insert_stage(depends_on: list[str], payload: dict) -> str:
            if depends_on:
                row = await conn.fetchrow(
                    """
                    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
                    VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid], $3::jsonb)
                    RETURNING id
                """,
                    cascade_id,
                    depends_on[0],
                    json.dumps(payload),
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
                    VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}', $2::jsonb)
                    RETURNING id
                """,
                    cascade_id,
                    json.dumps(payload),
                )
            return str(row["id"])

        refine_id = await insert_stage([], {"scc_stage": "refine"})
        fanout_id = await insert_stage(
            [refine_id],
            {
                "scc_stage": "intent_validation_fanout",
                "refine_stage_id": refine_id,
            },
        )
        match_id = await insert_stage([fanout_id], {"scc_stage": "match"})
        cohere_id = await insert_stage([match_id], {"scc_stage": "cohere"})
        formalize_id = await insert_stage([cohere_id], {"scc_stage": "formalize"})
        derive_id = await insert_stage([formalize_id], {"scc_stage": "derive"})
        generate_id = await insert_stage([derive_id], {"scc_stage": "generate"})
        await insert_stage([generate_id], {"scc_stage": "ship"})

    return cascade_id


async def create_scc_cascade_from_refine(
    intent_id: str,
    actor_id: str,
    conn: asyncpg.Connection,
    *,
    scope_doc: str,
    session_id: str | None = None,
) -> str:
    """Create a 6-stage SCC cascade (stages 2-7) after Refine completed as a conversation.

    The Refine stage already happened as the chat session. This creates:
    fanout → match → cohere → formalize → derive → generate

    The fanout stage receives scope_doc directly in its input (not a refine_stage_id pointer).
    """
    cascade_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, $3::jsonb, 'active')
            """,
            cascade_id,
            intent_id,
            json.dumps({"scc_template": "v2", "refine_session_id": session_id}),
        )

        async def insert_stage(depends_on: list[str], payload: dict) -> str:
            if depends_on:
                row = await conn.fetchrow(
                    """
                    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
                    VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', ARRAY[$2::uuid], $3::jsonb)
                    RETURNING id
                    """,
                    cascade_id,
                    depends_on[0],
                    json.dumps(payload),
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
                    VALUES (gen_random_uuid(), $1::uuid, 'narrowing', 'pending', '{}', $2::jsonb)
                    RETURNING id
                    """,
                    cascade_id,
                    json.dumps(payload),
                )
            return str(row["id"])

        # Fanout gets scope_doc directly (Refine was the conversation)
        fanout_id = await insert_stage(
            [],
            {
                "scc_stage": "intent_validation_fanout",
                "scope_doc": scope_doc,
                "raw_intent": scope_doc,
            },
        )
        match_id = await insert_stage([fanout_id], {"scc_stage": "match"})
        cohere_id = await insert_stage([match_id], {"scc_stage": "cohere"})
        formalize_id = await insert_stage([cohere_id], {"scc_stage": "formalize"})
        derive_id = await insert_stage([formalize_id], {"scc_stage": "derive"})
        generate_id = await insert_stage([derive_id], {"scc_stage": "generate"})
        await insert_stage([generate_id], {"scc_stage": "ship"})

    return cascade_id
