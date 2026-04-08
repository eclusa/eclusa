"""E2E test -- fan-out convergence and divergence against live docker-compose (COMP-E2E-02).

Proves:
1. run_fan_out_with_db fires 3 parallel judgment passes, stores convergence matrix,
   and routes to auto-resolve (converged) or gate (diverged/partial).
2. Forced divergence (mocked verdicts) creates a gate_surfaced ledger entry with
   per-model reasoning.
3. Live parallel firing returns 3 VerdictModel instances from the same GLM model.

Requires: docker compose up -d db (live Postgres), GLM API reachable at api.z.ai.
"""

import asyncio
import json
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest

# Ensure LLM env vars are set for the test process (host-side, not container)
os.environ.setdefault("OPENAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
os.environ.setdefault(
    "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "test-key-not-set")
)

from fan_out.convergence import compute_convergence
from fan_out.db import run_fan_out_with_db
from fan_out.dispatcher import run_fan_out
from judgment.context_prep import prepare_context
from judgment.pass_ import VerdictModel, hash_context
from tests.e2e.conftest import cleanup_cascade

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

MODELS = ["openai:glm-5.1", "openai:glm-5.1", "openai:glm-5.1"]

SYNTHETIC_HISTORY = [
    {
        "kind": "request",
        "content": "Build a simple REST API for user management",
    },
    {
        "kind": "response",
        "content": (
            "I will create GET/POST/PUT/DELETE endpoints for users "
            "with input validation"
        ),
    },
]

JUDGMENT_PROMPT = (
    "Evaluate whether this implementation approach is reasonable. "
    "Consider the scope and feasibility."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def seed_fan_out_stage(conn, actor_id: str) -> dict:
    """Seed a minimal cascade with one gate-type stage for fan-out evaluation.

    Creates: intent -> cascade (active) -> stage (gate, active).
    Returns dict with intent_id, cascade_id, stage_id.
    """
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    stage_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'Fan-out E2E test', $2::uuid)
            """,
            intent_id,
            actor_id,
        )
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test": true}'::jsonb,
                    'active'::cascade_state)
            """,
            cascade_id,
            intent_id,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'gate'::stage_type, 'active'::stage_state,
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


async def cleanup_fan_out(conn, seed: dict) -> None:
    """Clean up fan-out test data in correct FK order.

    Disables ledger immutability trigger, removes all related rows,
    then re-enables the trigger.
    """
    stage_id = seed["stage_id"]
    cascade_id = seed["cascade_id"]
    intent_id = seed["intent_id"]

    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )
    try:
        async with conn.transaction():
            # 1. Ledger entries by cascade_id (fan_out/db.py sets cascade_id via subselect)
            await conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid",
                cascade_id,
            )
            # 2. Ledger entries by stage_id (some entries only have stage_id)
            await conn.execute(
                "DELETE FROM ledger_entry WHERE stage_id = $1::uuid",
                stage_id,
            )
            # 3. Ledger entries for judgment_pass_completed (pass_.py sets only actor_id)
            #    Match by content->>'stage_id' for this stage
            await conn.execute(
                """DELETE FROM ledger_entry
                   WHERE type = 'judgment_pass_completed'
                     AND content->>'stage_id' = $1""",
                stage_id,
            )
            # 4. Judgment passes referencing this stage
            await conn.execute(
                "DELETE FROM judgment_pass WHERE stage_ids && ARRAY[$1::uuid]",
                stage_id,
            )
            # 5. Fan-out records for this stage
            await conn.execute(
                "DELETE FROM fan_out WHERE stage_id = $1::uuid",
                stage_id,
            )
            # 6. Work sessions (if any)
            await conn.execute(
                "DELETE FROM work_session WHERE stage_ids && ARRAY[$1::uuid]",
                stage_id,
            )
            # 7. Stages
            await conn.execute(
                "DELETE FROM stage WHERE cascade_id = $1::uuid",
                cascade_id,
            )
            # 8. Cascade
            await conn.execute(
                "DELETE FROM cascade WHERE id = $1::uuid",
                cascade_id,
            )
            # 9. Intent
            await conn.execute(
                "DELETE FROM intent WHERE id = $1::uuid",
                intent_id,
            )
    finally:
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )


# ---------------------------------------------------------------------------
# Test 1: Fan-out convergence auto-resolves stage (COMP-E2E-02 convergence)
# ---------------------------------------------------------------------------


async def test_fan_out_convergence_auto_resolves(db_conn, seed_actor):
    """COMP-E2E-02 convergence path: fan-out fires 3 passes, stores matrix,
    routes to auto-resolve or gate based on verdict."""
    actor_id = seed_actor
    seed = await seed_fan_out_stage(db_conn, actor_id)
    stage_id = seed["stage_id"]

    ctx = prepare_context(SYNTHETIC_HISTORY)
    assert len(ctx) > 0, "Prepared context should be non-empty"
    ctx_hash = hash_context(ctx)

    try:
        fan_out_id = await asyncio.wait_for(
            run_fan_out_with_db(
                conn=db_conn,
                stage_id=stage_id,
                models=MODELS,
                prepared_context=ctx,
                prompt=JUDGMENT_PROMPT,
                context_hash=ctx_hash,
                actor_id=actor_id,
            ),
            timeout=60,
        )
    except (asyncio.TimeoutError, TimeoutError):
        await cleanup_fan_out(db_conn, seed)
        pytest.skip("GLM API timeout -- api.z.ai unreachable or slow")
    except Exception as exc:
        await cleanup_fan_out(db_conn, seed)
        if "timeout" in str(exc).lower() or "connect" in str(exc).lower():
            pytest.skip(f"GLM API connection issue: {exc}")
        raise

    try:
        # Verify fan_out row
        row = await db_conn.fetchrow(
            "SELECT * FROM fan_out WHERE id = $1::uuid", fan_out_id
        )
        assert row is not None, f"fan_out row not found for id={fan_out_id}"
        assert row["verdict"] in ("converged", "diverged", "partial"), (
            f"Unexpected verdict: {row['verdict']}"
        )

        # Parse convergence matrix
        convergence = row["convergence"]
        if isinstance(convergence, str):
            convergence = json.loads(convergence)
        assert "decision" in convergence, "convergence matrix missing 'decision' key"
        assert "confidence" in convergence, (
            "convergence matrix missing 'confidence' key"
        )
        for field in ("decision", "confidence"):
            assert "values" in convergence[field], (
                f"convergence[{field}] missing 'values'"
            )
            assert "converged" in convergence[field], (
                f"convergence[{field}] missing 'converged'"
            )

        # Verify 3 pass UUIDs
        assert len(row["passes"]) == 3, (
            f"Expected 3 passes, got {len(row['passes'])}"
        )

        # Route verification: check stage state matches verdict
        stage_row = await db_conn.fetchrow(
            "SELECT state FROM stage WHERE id = $1::uuid", stage_id
        )
        assert stage_row is not None

        if row["verdict"] == "converged":
            assert stage_row["state"] == "resolved", (
                "Converged verdict should auto-resolve stage"
            )
        else:
            assert stage_row["state"] == "blocked", (
                f"Diverged/partial verdict should block stage, got {stage_row['state']}"
            )

        # Verify 3 judgment_pass records
        jp_count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM judgment_pass WHERE stage_ids && ARRAY[$1::uuid]",
            stage_id,
        )
        assert jp_count == 3, f"Expected 3 judgment_pass records, got {jp_count}"

    finally:
        await cleanup_fan_out(db_conn, seed)


# ---------------------------------------------------------------------------
# Test 2: Fan-out divergence creates gate (COMP-E2E-02 divergence path)
# ---------------------------------------------------------------------------


async def test_fan_out_divergence_creates_gate(db_conn, seed_actor):
    """COMP-E2E-02 divergence path: forced divergent verdicts create gate
    with per-model reasoning in ledger entry."""
    actor_id = seed_actor
    seed = await seed_fan_out_stage(db_conn, actor_id)
    stage_id = seed["stage_id"]
    cascade_id = seed["cascade_id"]

    # Create deterministic divergent verdicts
    approve = VerdictModel(
        decision="approve",
        confidence=0.85,
        rationale="Implementation is sound",
        conditions=[],
    )
    reject = VerdictModel(
        decision="reject",
        confidence=0.3,
        rationale="Too risky without tests",
        conditions=["Add unit tests"],
    )
    mixed = VerdictModel(
        decision="approve",
        confidence=0.4,
        rationale="Marginal",
        conditions=["Needs review"],
    )

    mock = AsyncMock(side_effect=[approve, reject, mixed])

    with patch("fan_out.dispatcher.run_judgment_pass", mock):
        fan_out_id = await run_fan_out_with_db(
            conn=db_conn,
            stage_id=stage_id,
            models=MODELS,
            prepared_context="test context",
            prompt="evaluate",
            context_hash=hash_context("test context"),
            actor_id=actor_id,
        )

    try:
        # Verify fan_out row -- decisions differ (approve, reject, approve) so diverged
        row = await db_conn.fetchrow(
            "SELECT * FROM fan_out WHERE id = $1::uuid", fan_out_id
        )
        assert row is not None, f"fan_out row not found for id={fan_out_id}"
        assert row["verdict"] == "diverged", (
            f"Expected 'diverged' verdict, got '{row['verdict']}'"
        )

        # Verify stage is blocked (divergence surfaces a gate)
        stage_row = await db_conn.fetchrow(
            "SELECT state FROM stage WHERE id = $1::uuid", stage_id
        )
        assert stage_row is not None
        assert stage_row["state"] == "blocked", (
            f"Diverged verdict should block stage, got '{stage_row['state']}'"
        )

        # Verify gate_surfaced ledger entry exists with divergence_context
        gate_entry = await db_conn.fetchrow(
            """
            SELECT * FROM ledger_entry
            WHERE type = 'gate_surfaced' AND cascade_id = $1::uuid
            """,
            cascade_id,
        )
        assert gate_entry is not None, "gate_surfaced ledger entry not found"

        gate_content = gate_entry["content"]
        if isinstance(gate_content, str):
            gate_content = json.loads(gate_content)
        assert "divergence_context" in gate_content, (
            "gate_surfaced content missing 'divergence_context'"
        )

        # Parse divergence_context -- should have per_model array
        div_ctx = gate_content["divergence_context"]
        if isinstance(div_ctx, str):
            div_ctx = json.loads(div_ctx)
        assert "per_model" in div_ctx, "divergence_context missing 'per_model'"
        assert len(div_ctx["per_model"]) == 3, (
            f"Expected 3 per_model entries, got {len(div_ctx['per_model'])}"
        )

        # Verify each per_model entry has the expected fields
        for entry in div_ctx["per_model"]:
            assert "decision" in entry, "per_model entry missing 'decision'"
            assert "confidence" in entry, "per_model entry missing 'confidence'"
            assert "rationale" in entry, "per_model entry missing 'rationale'"

        # Verify 3 judgment_pass records
        jp_count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM judgment_pass WHERE stage_ids && ARRAY[$1::uuid]",
            stage_id,
        )
        assert jp_count == 3, f"Expected 3 judgment_pass records, got {jp_count}"

    finally:
        await cleanup_fan_out(db_conn, seed)


# ---------------------------------------------------------------------------
# Test 3: Live parallel firing returns 3 VerdictModels (COMP-E2E-02 parallel)
# ---------------------------------------------------------------------------


async def test_fan_out_live_fires_three_parallel_passes(db_conn, seed_actor):
    """COMP-E2E-02 parallel path: run_fan_out fires 3 passes in parallel
    against live GLM API and returns 3 VerdictModels."""
    ctx = prepare_context(SYNTHETIC_HISTORY)
    ctx_hash = hash_context(ctx)

    try:
        verdicts, verdict_state, convergence_matrix = await asyncio.wait_for(
            run_fan_out(
                models=MODELS,
                prepared_context=ctx,
                prompt="Is this plan feasible?",
                context_hash=ctx_hash,
            ),
            timeout=60,
        )
    except (asyncio.TimeoutError, TimeoutError):
        pytest.skip("GLM API timeout -- api.z.ai unreachable or slow")
    except Exception as exc:
        if "timeout" in str(exc).lower() or "connect" in str(exc).lower():
            pytest.skip(f"GLM API connection issue: {exc}")
        raise

    # Verify 3 VerdictModels returned
    assert len(verdicts) == 3, f"Expected 3 verdicts, got {len(verdicts)}"
    for i, v in enumerate(verdicts):
        assert isinstance(v, VerdictModel), (
            f"Verdict {i} is {type(v)}, expected VerdictModel"
        )

    # Verify verdict_state is valid
    assert verdict_state in ("converged", "diverged", "partial"), (
        f"Unexpected verdict_state: {verdict_state}"
    )

    # Verify convergence matrix has required keys
    assert "decision" in convergence_matrix, (
        "convergence_matrix missing 'decision' key"
    )
    assert "confidence" in convergence_matrix, (
        "convergence_matrix missing 'confidence' key"
    )
