"""
tests/test_fan_out.py -- Tests for fan-out evaluation module.

Requirements: FAN-01, FAN-02, FAN-03, FAN-04, FAN-05
Implemented in: 03-04-PLAN (convergence + dispatcher) and 03-05-PLAN (DB persistence)
"""

import pytest
from unittest.mock import AsyncMock, patch

from fan_out.convergence import compute_convergence
from fan_out.dispatcher import run_fan_out
from fan_out.db import run_fan_out_with_db
from judgment.pass_ import VerdictModel

# Preset VerdictModel values for mocking
APPROVE_VERDICT = VerdictModel(
    decision="approve", confidence=0.9, rationale="looks good", conditions=[]
)
REJECT_VERDICT = VerdictModel(
    decision="reject",
    confidence=0.2,
    rationale="too risky",
    conditions=["review needed"],
)


@pytest.mark.asyncio
async def test_fanout_fires_n_passes_in_parallel():
    """run_fan_out fires n judgment passes in parallel via asyncio.gather. FAN-01."""
    with patch(
        "fan_out.dispatcher.run_judgment_pass",
        new=AsyncMock(return_value=APPROVE_VERDICT),
    ) as mock_pass:
        verdicts, verdict_state, matrix = await run_fan_out(
            models=["model-a", "model-b", "model-c"],
            prepared_context="some context",
            prompt="evaluate this",
            context_hash="abc123",
        )
    assert len(verdicts) == 3
    assert mock_pass.call_count == 3
    # All return APPROVE_VERDICT (same decision, same confidence) -> converged
    assert verdict_state == "converged"
    for v in verdicts:
        assert isinstance(v, VerdictModel)


def test_convergence_on_matching_decisions():
    """compute_convergence returns 'converged' when decision matches and confidence within 0.15 band. FAN-02, FAN-03."""
    v1 = VerdictModel(decision="approve", confidence=0.9, rationale="ok", conditions=[])
    v2 = VerdictModel(
        decision="approve",
        confidence=0.85,
        rationale="different text",
        conditions=["x"],
    )
    verdict_state, matrix = compute_convergence([v1, v2])
    assert verdict_state == "converged"
    assert matrix["decision"]["converged"] is True
    assert matrix["confidence"]["converged"] is True
    # Verify values are tracked in matrix
    assert "approve" in matrix["decision"]["values"]
    assert 0.9 in matrix["confidence"]["values"]
    assert 0.85 in matrix["confidence"]["values"]


@pytest.mark.asyncio
async def test_divergence_creates_gate(conn):
    """When models diverge, fan_out surfaces a gate with state='blocked'. FAN-04."""
    from tests.helpers.topology import seed_system_actor

    # Seed actor, intent, cascade, and a gate stage
    await seed_system_actor(conn)

    actor_row = await conn.fetchrow("""
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', 'fan-out-test-divergence')
        RETURNING id
    """)
    test_actor_id = str(actor_row["id"])

    intent_row = await conn.fetchrow(
        """
        INSERT INTO intent (id, source, raw, created_by)
        VALUES (gen_random_uuid(), 'manual', 'fan-out divergence test', $1::uuid)
        RETURNING id
    """,
        test_actor_id,
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

    stage_row = await conn.fetchrow(
        """
        INSERT INTO stage (id, cascade_id, type, state, depends_on)
        VALUES (gen_random_uuid(), $1::uuid, 'gate', 'active', '{}')
        RETURNING id
    """,
        cascade_id,
    )
    stage_id = str(stage_row["id"])

    # Mock run_judgment_pass to return diverging verdicts
    async def diverge_side_effect(model, prepared_context, prompt):
        if model == "model-a":
            return APPROVE_VERDICT
        else:
            return REJECT_VERDICT

    with patch(
        "fan_out.dispatcher.run_judgment_pass",
        new=AsyncMock(side_effect=diverge_side_effect),
    ):
        fan_out_id = await run_fan_out_with_db(
            conn=conn,
            stage_id=stage_id,
            models=["model-a", "model-b"],
            prepared_context="context for evaluation",
            prompt="should we proceed?",
            context_hash="abc456",
            actor_id=test_actor_id,
        )

    # Verify stage is blocked
    stage = await conn.fetchrow("SELECT state FROM stage WHERE id = $1::uuid", stage_id)
    assert stage["state"] == "blocked", f"Expected 'blocked', got '{stage['state']}'"

    # Verify gate_surfaced ledger entry exists with fan_out_id in content
    ledger = await conn.fetchrow(
        """
        SELECT type, content FROM ledger_entry
        WHERE stage_id = $1::uuid AND type = 'gate_surfaced'
        ORDER BY timestamp DESC LIMIT 1
    """,
        stage_id,
    )
    assert ledger is not None, "Expected gate_surfaced ledger entry"
    import json

    content = json.loads(ledger["content"])
    assert content.get("fan_out_id") == fan_out_id


def test_partial_verdict_state():
    """compute_convergence returns 'partial' when decision diverges but confidence converges. FAN-05."""
    # 2 agree on decision, 1 disagrees; all confidence within 0.15
    v1 = VerdictModel(
        decision="approve", confidence=0.88, rationale="yes", conditions=[]
    )
    v2 = VerdictModel(
        decision="approve", confidence=0.90, rationale="also yes", conditions=[]
    )
    v3 = VerdictModel(decision="reject", confidence=0.85, rationale="no", conditions=[])

    verdict_state, matrix = compute_convergence([v1, v2, v3])

    # decision diverges -> not converged
    # confidence spread: max(0.88, 0.90, 0.85) - min(...) = 0.90 - 0.85 = 0.05 <= 0.15 -> converged
    assert verdict_state == "partial", f"Expected 'partial', got '{verdict_state}'"
    assert matrix["decision"]["converged"] is False
    assert matrix["confidence"]["converged"] is True
