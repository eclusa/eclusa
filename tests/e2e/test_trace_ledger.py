"""TRACE-E2E-01 + TRACE-E2E-02: Trace chain provenance and AS OF temporal ledger queries.

Proves:
  - Trace chain walks from artifact -> session -> stage -> cascade -> intent
    in a single recursive CTE query with CYCLE guard.
  - AS OF TIMESTAMP query at two different timestamps returns two different
    correct ledger states.

Requires: docker-compose db running at localhost:5432.
"""

import json
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

# SQL files live at repo root: db/queries/
_REPO_ROOT = Path(__file__).parent.parent.parent
_TRACE_CHAIN_SQL = _REPO_ROOT / "db" / "queries" / "trace_chain.sql"
_AS_OF_SQL = _REPO_ROOT / "db" / "queries" / "as_of.sql"


async def test_trace_chain_artifact_to_intent(e2e_pool, db_conn, seed_actor):
    """TRACE-E2E-01: Full provenance walk from artifact back to root intent.

    Seeds: actor -> intent -> cascade -> stage -> work_session -> artifact.
    Runs trace_chain.sql with the artifact UUID.
    Asserts every link in the chain matches seeded IDs.
    """
    actor_id = seed_actor

    # Generate UUIDs for the full chain
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    try:
        # -- Seed the provenance chain --

        # 1. Intent
        await db_conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'E2E trace chain test', $2::uuid)
            """,
            intent_id,
            actor_id,
        )

        # 2. Cascade
        await db_conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test":"trace"}'::jsonb, 'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )

        # 3. Stage
        await db_conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'resolved'::stage_state,
                    '{}'::uuid[], '{}'::jsonb)
            """,
            stage_id,
            cascade_id,
        )

        # 4. Work session (correct column names per compute.py schema)
        await db_conn.execute(
            """
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, message_history, cost)
            VALUES ($1::uuid, ARRAY[$2::uuid], 'native', 'test-model',
                    'completed'::work_session_state, '[]'::jsonb, '{}'::jsonb)
            """,
            session_id,
            stage_id,
        )

        # 5. Artifact
        await db_conn.execute(
            """
            INSERT INTO artifact (id, intent_id, cascade_id, stage_id, session_id, type, payload)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                    'api_response'::artifact_type, '{"test":"trace_chain"}'::jsonb)
            """,
            artifact_id,
            intent_id,
            cascade_id,
            stage_id,
            session_id,
        )

        # -- Run trace_chain.sql --
        trace_sql = _TRACE_CHAIN_SQL.read_text()
        row = await db_conn.fetchrow(trace_sql, artifact_id)

        assert row is not None, "trace_chain query returned no rows"

        # Assert every link in the provenance chain
        assert str(row["artifact_id"]) == artifact_id, (
            f"artifact_id mismatch: {row['artifact_id']} != {artifact_id}"
        )
        assert str(row["session_id"]) == session_id, (
            f"session_id mismatch: {row['session_id']} != {session_id}"
        )
        assert str(row["stage_id"]) == stage_id, (
            f"stage_id mismatch: {row['stage_id']} != {stage_id}"
        )
        assert str(row["cascade_id"]) == cascade_id, (
            f"cascade_id mismatch: {row['cascade_id']} != {cascade_id}"
        )
        assert str(row["intent_id"]) == intent_id, (
            f"intent_id mismatch: {row['intent_id']} != {intent_id}"
        )

        # Enriched fields from LEFT JOINs
        assert row["stage_type"] == "narrowing"
        assert row["stage_state"] == "resolved"
        assert row["cascade_state"] == "active"
        assert row["intent_raw"] == "E2E trace chain test"
        assert row["intent_source"] == "api"

    finally:
        # Cleanup in FK-safe order: artifact -> work_session -> ledger (with trigger bypass) -> stage -> cascade -> intent
        # (seed_actor fixture handles actor deletion)
        await db_conn.execute(
            "DELETE FROM artifact WHERE id = $1::uuid", artifact_id
        )
        await db_conn.execute(
            "DELETE FROM work_session WHERE id = $1::uuid", session_id
        )
        await db_conn.execute(
            "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
        )
        try:
            await db_conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )
        finally:
            await db_conn.execute(
                "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
            )
        await db_conn.execute(
            "DELETE FROM stage WHERE id = $1::uuid", stage_id
        )
        await db_conn.execute(
            "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
        )
        await db_conn.execute(
            "DELETE FROM intent WHERE id = $1::uuid", intent_id
        )


async def test_as_of_ledger_two_timestamps(e2e_pool, db_conn, seed_actor):
    """TRACE-E2E-02: AS OF TIMESTAMP returns different states at different moments.

    Seeds two ledger entries with explicit timestamps 10s and 2s in the past.
    Queries AS OF between them (sees first state) and after both (sees second state).
    """
    actor_id = seed_actor

    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())

    try:
        # -- Seed domain objects --

        await db_conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'E2E as-of test', $2::uuid)
            """,
            intent_id,
            actor_id,
        )

        await db_conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test":"as_of"}'::jsonb, 'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )

        await db_conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state,
                    '{}'::uuid[], '{}'::jsonb)
            """,
            stage_id,
            cascade_id,
        )

        # -- Bypass immutability trigger for direct ledger inserts --
        await db_conn.execute(
            "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
        )

        try:
            # First ledger entry: 10 seconds ago (state change pending -> active)
            row1 = await db_conn.fetchrow(
                """
                INSERT INTO ledger_entry
                    (id, intent_id, cascade_id, stage_id, actor_id, type, content, timestamp, schema_version)
                VALUES (gen_random_uuid(), $1::uuid, $2::uuid, $3::uuid, $4::uuid,
                        'stage_state_changed'::ledger_type,
                        '{"old_state":"pending","new_state":"active"}'::jsonb,
                        NOW() - interval '10 seconds', '0001')
                RETURNING id::text, timestamp
                """,
                intent_id,
                cascade_id,
                stage_id,
                actor_id,
            )
            t1 = row1["timestamp"]

            # Second ledger entry: 2 seconds ago (state change active -> resolved)
            row2 = await db_conn.fetchrow(
                """
                INSERT INTO ledger_entry
                    (id, intent_id, cascade_id, stage_id, actor_id, type, content, timestamp, schema_version)
                VALUES (gen_random_uuid(), $1::uuid, $2::uuid, $3::uuid, $4::uuid,
                        'stage_state_changed'::ledger_type,
                        '{"old_state":"active","new_state":"resolved"}'::jsonb,
                        NOW() - interval '2 seconds', '0001')
                RETURNING id::text, timestamp
                """,
                intent_id,
                cascade_id,
                stage_id,
                actor_id,
            )
            t2 = row2["timestamp"]

        finally:
            await db_conn.execute(
                "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
            )

        # -- Run AS OF queries --
        as_of_sql = _AS_OF_SQL.read_text()

        # Query 1: AS OF between t1 and t2 (t1 + 1 second)
        # Should return the FIRST entry (new_state = "active")
        query_time_1 = t1 + timedelta(seconds=1)
        result_1 = await db_conn.fetchrow(as_of_sql, stage_id, query_time_1)

        assert result_1 is not None, (
            f"AS OF query at {query_time_1} returned no rows (t1={t1}, t2={t2})"
        )
        content_1_raw = result_1["content"]
        content_1 = json.loads(content_1_raw) if isinstance(content_1_raw, str) else content_1_raw
        assert content_1["new_state"] == "active", (
            f"Expected new_state='active' at t1+1s, got {content_1}"
        )
        assert result_1["type"] == "stage_state_changed"

        # Query 2: AS OF after t2 (t2 + 1 second)
        # Should return the SECOND entry (new_state = "resolved")
        query_time_2 = t2 + timedelta(seconds=1)
        result_2 = await db_conn.fetchrow(as_of_sql, stage_id, query_time_2)

        assert result_2 is not None, (
            f"AS OF query at {query_time_2} returned no rows (t1={t1}, t2={t2})"
        )
        content_2_raw = result_2["content"]
        content_2 = json.loads(content_2_raw) if isinstance(content_2_raw, str) else content_2_raw
        assert content_2["new_state"] == "resolved", (
            f"Expected new_state='resolved' at t2+1s, got {content_2}"
        )
        assert result_2["type"] == "stage_state_changed"

        # The two results must be different entries
        assert str(result_1["id"]) != str(result_2["id"]), (
            "AS OF queries at different timestamps returned the same ledger entry"
        )

    finally:
        # Cleanup: ledger entries (trigger bypass), stage, cascade, intent
        await db_conn.execute(
            "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
        )
        try:
            await db_conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )
        finally:
            await db_conn.execute(
                "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
            )
        await db_conn.execute(
            "DELETE FROM stage WHERE id = $1::uuid", stage_id
        )
        await db_conn.execute(
            "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
        )
        await db_conn.execute(
            "DELETE FROM intent WHERE id = $1::uuid", intent_id
        )
