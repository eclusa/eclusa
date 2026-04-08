"""E2E test — judgment pass returns structured verdict stored in DB (COMP-E2E-01).

Proves:
1. run_judgment_pass calls live GLM model and returns a validated VerdictModel
2. create_judgment_pass_record persists the verdict in judgment_pass + ledger_entry tables

Requires: docker compose up -d db (live Postgres), GLM API reachable at api.z.ai.
"""

import asyncio
import json
import os
import uuid

import pytest

# Ensure LLM env vars are set for the test process (host-side, not container)
os.environ.setdefault("OPENAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
os.environ.setdefault(
    "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "test-key-not-set")
)

from judgment.context_prep import prepare_context
from judgment.pass_ import (
    VerdictModel,
    create_judgment_pass_record,
    hash_context,
    run_judgment_pass,
)
from tests.e2e.conftest import cleanup_cascade

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYNTHETIC_HISTORY = [
    {"kind": "request", "content": "Build a user authentication system"},
    {
        "kind": "response",
        "content": "I will implement JWT auth with bcrypt password hashing",
    },
]

MODEL = "openai:glm-5.1"
JUDGMENT_PROMPT = (
    "Evaluate whether this implementation plan is sound. Return your verdict."
)


async def seed_single_stage(conn, actor_id: str) -> dict:
    """Seed a minimal cascade with one narrowing stage for judgment testing."""
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'Judgment E2E test', $2::uuid)
            """,
            intent_id,
            actor_id,
        )
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test": true}'::jsonb, 'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state,
                    '{}'::uuid[], '{}'::jsonb)
            """,
            stage_id,
            cascade_id,
        )

    return {
        "intent_id": intent_id,
        "cascade_id": cascade_id,
        "stage_id": stage_id,
    }


# ---------------------------------------------------------------------------
# Test 1: Judgment pass returns validated verdict from live GLM
# ---------------------------------------------------------------------------


async def test_judgment_pass_returns_validated_verdict(db_conn, seed_actor):
    """COMP-E2E-01: run_judgment_pass calls GLM and returns VerdictModel."""
    ctx = prepare_context(SYNTHETIC_HISTORY)
    assert len(ctx) > 0, "Prepared context should be non-empty"

    ctx_hash = hash_context(ctx)
    assert isinstance(ctx_hash, str) and len(ctx_hash) > 0

    try:
        verdict = await asyncio.wait_for(
            run_judgment_pass(MODEL, ctx, JUDGMENT_PROMPT),
            timeout=60,
        )
    except (asyncio.TimeoutError, TimeoutError):
        pytest.skip("GLM API timeout — api.z.ai unreachable or slow")
    except Exception as exc:
        if "timeout" in str(exc).lower() or "connect" in str(exc).lower():
            pytest.skip(f"GLM API connection issue: {exc}")
        raise

    # Validate verdict structure
    assert isinstance(verdict, VerdictModel), f"Expected VerdictModel, got {type(verdict)}"
    assert isinstance(verdict.decision, str) and len(verdict.decision) > 0, (
        "decision must be a non-empty string"
    )
    assert 0.0 <= verdict.confidence <= 1.0, (
        f"confidence must be in [0, 1], got {verdict.confidence}"
    )
    assert isinstance(verdict.rationale, str) and len(verdict.rationale) > 0, (
        "rationale must be a non-empty string"
    )
    assert isinstance(verdict.conditions, list), "conditions must be a list"


# ---------------------------------------------------------------------------
# Test 2: Judgment pass record stored in DB (judgment_pass + ledger_entry)
# ---------------------------------------------------------------------------


async def test_judgment_pass_record_stored_in_db(db_conn, seed_actor):
    """COMP-E2E-01: verdict persisted in judgment_pass table + ledger_entry."""
    actor_id = seed_actor
    seed = await seed_single_stage(db_conn, actor_id)
    stage_id = seed["stage_id"]
    cascade_id = seed["cascade_id"]

    ctx = prepare_context(SYNTHETIC_HISTORY)
    ctx_hash = hash_context(ctx)
    prompt = "Evaluate this plan."

    try:
        verdict = await asyncio.wait_for(
            run_judgment_pass(MODEL, ctx, prompt),
            timeout=60,
        )
    except (asyncio.TimeoutError, TimeoutError):
        # Clean up seeded data before skipping
        await cleanup_cascade(db_conn, cascade_id)
        pytest.skip("GLM API timeout — api.z.ai unreachable or slow")
    except Exception as exc:
        await cleanup_cascade(db_conn, cascade_id)
        if "timeout" in str(exc).lower() or "connect" in str(exc).lower():
            pytest.skip(f"GLM API connection issue: {exc}")
        raise

    # Persist verdict to DB
    pass_id = await create_judgment_pass_record(
        db_conn,
        stage_id,
        MODEL,
        f"inline:{ctx_hash}",
        ctx_hash,
        prompt,
        verdict,
        actor_id,
    )

    try:
        # Verify judgment_pass row
        row = await db_conn.fetchrow(
            "SELECT * FROM judgment_pass WHERE id = $1::uuid", pass_id
        )
        assert row is not None, f"judgment_pass row not found for id={pass_id}"
        assert row["model"] == MODEL
        assert row["context_hash"] == ctx_hash

        # Parse response JSONB
        response_data = row["response"]
        if isinstance(response_data, str):
            response_data = json.loads(response_data)
        assert "decision" in response_data
        assert "confidence" in response_data
        assert "rationale" in response_data
        assert "conditions" in response_data

        # Verify ledger entry
        ledger_row = await db_conn.fetchrow(
            """
            SELECT * FROM ledger_entry
            WHERE type = 'judgment_pass_completed'
              AND content->>'judgment_pass_id' = $1
            """,
            pass_id,
        )
        assert ledger_row is not None, (
            f"ledger_entry not found for judgment_pass_id={pass_id}"
        )

    finally:
        # Cleanup: disable immutability trigger, delete judgment_pass + ledger + cascade
        await db_conn.execute(
            "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
        )
        try:
            async with db_conn.transaction():
                await db_conn.execute(
                    "DELETE FROM ledger_entry WHERE content->>'judgment_pass_id' = $1",
                    pass_id,
                )
                await db_conn.execute(
                    "DELETE FROM judgment_pass WHERE id = $1::uuid", pass_id
                )
            await cleanup_cascade(db_conn, cascade_id)
        finally:
            await db_conn.execute(
                "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
            )
