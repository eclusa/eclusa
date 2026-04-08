"""E2E test -- self-calibration metrics against live docker-compose (CAL-E2E-01).

Proves all 8 self-calibration metric SQL queries return computable non-null
values when run against the live Postgres instance with properly seeded data.

Metrics tested:
  1. gate_necessity_rate (CAL-01)
  2. orchestrator_absorption_rate (CAL-02)
  3. resolution_latency (CAL-03)
  4. decision_durability_rework_rate (CAL-04)
  5. cascade_rework_rate (CAL-05)
  6. model_convergence_rate (CAL-06)
  7. minority_model_accuracy (CAL-07)
  8. fanout_necessity_rate (CAL-08)

Requires: docker compose up (db, web services running).
"""

import json
import uuid

import asyncpg
import httpx
import pytest

pytestmark = pytest.mark.asyncio

E2E_DSN = "postgresql://eclusa:eclusa@localhost:5432/eclusa"
API_BASE = "http://localhost:8000"
JWT_SECRET = "eclusa-dev-secret-0123456789012345678901234"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_auth_token() -> str:
    """Obtain a JWT token from the running web API."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.post("/api/auth/token", json={"secret": JWT_SECRET})
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _fetch_metrics(token: str) -> dict:
    """Call GET /api/metrics with Bearer auth and return the JSON body."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=15) as client:
        resp = await client.get(
            "/api/metrics", headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


async def _seed_metric_data(conn: asyncpg.Connection) -> dict:
    """Seed all data required by the 8 self-calibration metric SQL queries.

    Returns a dict of IDs for cleanup.
    """
    # Generate fresh UUIDs for all entities
    actor_id = str(uuid.uuid4())
    intent_ids = [str(uuid.uuid4()) for _ in range(3)]
    cascade_ids = [str(uuid.uuid4()) for _ in range(3)]
    # 6 stages: 2 per cascade (one gate, one narrowing)
    stage_ids = [str(uuid.uuid4()) for _ in range(6)]
    # 3 fan_out rows
    fan_out_ids = [str(uuid.uuid4()) for _ in range(3)]
    # Ledger entry IDs (we need many)
    ledger_ids = [str(uuid.uuid4()) for _ in range(20)]

    # --- Actor ---
    await conn.execute(
        """
        INSERT INTO actor (id, type, identity, permissions)
        VALUES ($1::uuid, 'system'::actor_type, $2, $3::jsonb)
        """,
        actor_id,
        f"e2e-metrics-{actor_id[:8]}",
        '{"resolve_gates":["*"],"view_costs":true}',
    )

    # --- Intents ---
    for iid in intent_ids:
        await conn.execute(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES ($1::uuid, 'api'::intent_source, 'E2E metrics test', $2::uuid)
            """,
            iid,
            actor_id,
        )

    # --- Cascades ---
    for idx, cid in enumerate(cascade_ids):
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{"test": true}'::jsonb, 'active'::cascade_state)
            """,
            cid,
            intent_ids[idx],
        )

    # --- Stages (2 per cascade: gate + narrowing) ---
    for idx, cid in enumerate(cascade_ids):
        gate_sid = stage_ids[idx * 2]
        narrowing_sid = stage_ids[idx * 2 + 1]
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'gate'::stage_type, 'pending'::stage_state,
                    '{}'::uuid[], '{}'::jsonb)
            """,
            gate_sid,
            cid,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing'::stage_type, 'pending'::stage_state,
                    ARRAY[$3::uuid], '{}'::jsonb)
            """,
            narrowing_sid,
            cid,
            gate_sid,
        )

    # Shorthand references
    gate_stage_0 = stage_ids[0]  # cascade 0, gate
    gate_stage_1 = stage_ids[2]  # cascade 1, gate
    gate_stage_2 = stage_ids[4]  # cascade 2, gate

    li = 0  # ledger index counter

    # ===================================================================
    # (a) gate_necessity (CAL-01): gate_surfaced + gate_resolved pairs
    # ===================================================================

    # Pair 1: human != system (contributes to gate_necessity > 0)
    # gate_surfaced for gate_stage_0, 10 minutes ago
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'gate_surfaced',
                '{"reason": "divergence"}'::jsonb, NOW() - interval '10 minutes')
        """,
        ledger_ids[li],
        cascade_ids[0],
        gate_stage_0,
        actor_id,
    )
    li += 1

    # gate_resolved for gate_stage_0, 5 minutes ago (human_choice != system_recommendation)
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'gate_resolved',
                '{"human_choice": "reject", "system_recommendation": "approve"}'::jsonb,
                NOW() - interval '5 minutes')
        """,
        ledger_ids[li],
        cascade_ids[0],
        gate_stage_0,
        actor_id,
    )
    li += 1

    # Pair 2: human == system (gate_necessity contribution = 0 for this pair)
    # gate_surfaced for gate_stage_1, 10 minutes ago
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'gate_surfaced',
                '{"reason": "review"}'::jsonb, NOW() - interval '10 minutes')
        """,
        ledger_ids[li],
        cascade_ids[1],
        gate_stage_1,
        actor_id,
    )
    li += 1

    # gate_resolved for gate_stage_1, 7 minutes ago (human_choice == system_recommendation)
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'gate_resolved',
                '{"human_choice": "approve", "system_recommendation": "approve"}'::jsonb,
                NOW() - interval '7 minutes')
        """,
        ledger_ids[li],
        cascade_ids[1],
        gate_stage_1,
        actor_id,
    )
    li += 1

    # ===================================================================
    # (b) orchestrator_absorption (CAL-02): gate_auto_resolved entries
    # ===================================================================
    # We already have 2x gate_surfaced from (a). Add 2x gate_auto_resolved.
    # Use gate_stage_2 and a new stage for the auto-resolved ones.
    # Actually, orchestrator_absorption counts types globally, so we just need
    # gate_auto_resolved entries with recent timestamps.

    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'gate_auto_resolved',
                '{"reason": "converged"}'::jsonb, NOW() - interval '8 minutes')
        """,
        ledger_ids[li],
        cascade_ids[2],
        gate_stage_2,
        actor_id,
    )
    li += 1

    # Second gate_auto_resolved on a different stage context
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'gate_auto_resolved',
                '{"reason": "converged"}'::jsonb, NOW() - interval '6 minutes')
        """,
        ledger_ids[li],
        cascade_ids[2],
        stage_ids[5],  # narrowing stage from cascade 2
        actor_id,
    )
    li += 1

    # ===================================================================
    # (c) resolution_latency (CAL-03): already covered by (a)
    # The gate_surfaced/gate_resolved pairs have a ~5 min gap (10min - 5min)
    # and ~3 min gap (10min - 7min) respectively. p50 should be ~240s.
    # ===================================================================

    # ===================================================================
    # (d) decision_durability (CAL-04): cascade_migration after gate_resolved
    # ===================================================================
    # For cascade_ids[0], insert a cascade_migration entry after the gate_resolved
    # timestamp (which was NOW() - 5 minutes). Use NOW() - 2 minutes.
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'cascade_migration',
                '{"old_shape": {}, "new_shape": {"migrated": true}}'::jsonb,
                NOW() - interval '2 minutes')
        """,
        ledger_ids[li],
        cascade_ids[0],
        gate_stage_0,
        actor_id,
    )
    li += 1
    # Now: 2 gate_resolved entries. 1 has a later cascade_migration in its cascade.
    # decision_durability_rework_rate = 1/2 = 0.5

    # ===================================================================
    # (e) cascade_rework (CAL-05): cascade_state_changed + cascade_reopened
    # ===================================================================
    # cascade_state_changed with new_state=completed for cascade 0 and 1
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, NULL, $3::uuid, 'cascade_state_changed',
                '{"new_state": "completed"}'::jsonb, NOW() - interval '15 minutes')
        """,
        ledger_ids[li],
        cascade_ids[0],
        actor_id,
    )
    li += 1

    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, NULL, $3::uuid, 'cascade_state_changed',
                '{"new_state": "completed"}'::jsonb, NOW() - interval '14 minutes')
        """,
        ledger_ids[li],
        cascade_ids[1],
        actor_id,
    )
    li += 1

    # cascade_reopened for cascade 0 only (after its completed timestamp)
    await conn.execute(
        """
        INSERT INTO ledger_entry (id, cascade_id, stage_id, actor_id, type, content, "timestamp")
        VALUES ($1::uuid, $2::uuid, NULL, $3::uuid, 'cascade_reopened',
                '{"reason": "new requirements"}'::jsonb, NOW() - interval '12 minutes')
        """,
        ledger_ids[li],
        cascade_ids[0],
        actor_id,
    )
    li += 1
    # cascade_rework_rate = 1/2 = 0.5

    # ===================================================================
    # (f) model_convergence (CAL-06): fan_out rows with verdicts
    # ===================================================================
    # Fan-out 0: converged, linked to gate_stage_0 (for minority_accuracy too)
    await conn.execute(
        """
        INSERT INTO fan_out (id, stage_id, context_ref, prompt, passes, convergence, verdict,
                             created_at, completed_at)
        VALUES ($1::uuid, $2::uuid, 'ref-metrics-0', 'evaluate scope',
                '{}'::uuid[],
                $3::jsonb,
                'converged'::fan_out_verdict,
                NOW() - interval '20 minutes',
                NOW() - interval '18 minutes')
        """,
        fan_out_ids[0],
        gate_stage_0,
        json.dumps(
            {
                "majority_verdict": "approve",
                "passes": [
                    {"model": "model-A", "verdict": "approve"},
                    {"model": "model-B", "verdict": "approve"},
                    {"model": "model-C", "verdict": "reject"},
                ],
            }
        ),
    )

    # Fan-out 1: converged, linked to gate_stage_1
    await conn.execute(
        """
        INSERT INTO fan_out (id, stage_id, context_ref, prompt, passes, convergence, verdict,
                             created_at, completed_at)
        VALUES ($1::uuid, $2::uuid, 'ref-metrics-1', 'evaluate design',
                '{}'::uuid[],
                '{"majority_verdict": "approve", "passes": [{"model": "model-A", "verdict": "approve"}, {"model": "model-B", "verdict": "approve"}]}'::jsonb,
                'converged'::fan_out_verdict,
                NOW() - interval '20 minutes',
                NOW() - interval '17 minutes')
        """,
        fan_out_ids[1],
        gate_stage_1,
    )

    # Fan-out 2: diverged, linked to gate_stage_2
    await conn.execute(
        """
        INSERT INTO fan_out (id, stage_id, context_ref, prompt, passes, convergence, verdict,
                             created_at, completed_at)
        VALUES ($1::uuid, $2::uuid, 'ref-metrics-2', 'evaluate approach',
                '{}'::uuid[],
                '{"majority_verdict": "reject", "passes": [{"model": "model-A", "verdict": "approve"}, {"model": "model-B", "verdict": "reject"}, {"model": "model-C", "verdict": "reject"}]}'::jsonb,
                'diverged'::fan_out_verdict,
                NOW() - interval '20 minutes',
                NOW() - interval '16 minutes')
        """,
        fan_out_ids[2],
        gate_stage_2,
    )
    # model_convergence_rate = 2/3 = 0.667
    # fanout_necessity_rate = 1/3 = 0.333

    # ===================================================================
    # (g) minority_accuracy (CAL-07):
    # Needs: fan_out.stage_id matches gate_resolved.stage_id
    # fan_out.convergence has majority_verdict and passes with model/verdict
    # gate_resolved.content->>'human_choice' matches a minority verdict
    # that differs from majority_verdict.
    #
    # Fan-out 0 (gate_stage_0):
    #   majority_verdict = "approve"
    #   model-C verdict = "reject" (minority)
    #   gate_resolved for gate_stage_0: human_choice = "reject"
    #   => human picked minority (model-C's "reject"), so model-C gets 1 count.
    #
    # This is already correctly seeded by the combination of fan_out_ids[0]
    # and the gate_resolved ledger entry for gate_stage_0 from step (a).
    # ===================================================================

    used_ledger_count = li
    return {
        "actor_id": actor_id,
        "intent_ids": intent_ids,
        "cascade_ids": cascade_ids,
        "stage_ids": stage_ids,
        "fan_out_ids": fan_out_ids,
        "ledger_ids": ledger_ids[:used_ledger_count],
    }


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


async def _cleanup_metric_data(conn: asyncpg.Connection, ids: dict) -> None:
    """Remove all seeded data in FK-safe order with ledger trigger bypass."""
    # Disable the immutability trigger for cleanup
    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )
    try:
        async with conn.transaction():
            # 1. Fan-out rows (FK to stage)
            for fid in ids["fan_out_ids"]:
                await conn.execute(
                    "DELETE FROM fan_out WHERE id = $1::uuid", fid
                )

            # 2. Ledger entries by cascade_id (covers most)
            for cid in ids["cascade_ids"]:
                await conn.execute(
                    "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cid
                )

            # 3. Work sessions referencing any stages (if any)
            if ids["stage_ids"]:
                stage_uuids = [
                    uuid.UUID(sid) for sid in ids["stage_ids"]
                ]
                await conn.execute(
                    "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                    stage_uuids,
                )

            # 4. Stages
            for cid in ids["cascade_ids"]:
                await conn.execute(
                    "DELETE FROM stage WHERE cascade_id = $1::uuid", cid
                )

            # 5. Cascades
            for cid in ids["cascade_ids"]:
                await conn.execute(
                    "DELETE FROM cascade WHERE id = $1::uuid", cid
                )

            # 6. Intents
            for iid in ids["intent_ids"]:
                await conn.execute(
                    "DELETE FROM intent WHERE id = $1::uuid", iid
                )

            # 7. Actor
            await conn.execute(
                "DELETE FROM actor WHERE id = $1::uuid", ids["actor_id"]
            )
    finally:
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


async def test_all_metrics_return_non_null():
    """Seed metric data, call GET /api/metrics, assert all 8 values are non-null floats."""
    # Connect to DB
    try:
        pool = await asyncpg.create_pool(E2E_DSN, min_size=1, max_size=3)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"docker-compose db not running: {exc}")
        return

    ids = None
    try:
        async with pool.acquire() as conn:
            ids = await _seed_metric_data(conn)

        # Obtain JWT token
        token = await _get_auth_token()

        # Fetch metrics
        metrics = await _fetch_metrics(token)

        # --- Assertions: all 8 fields non-null and float ---
        metric_keys = [
            "gate_necessity",
            "orchestrator_absorption",
            "resolution_latency",
            "decision_durability",
            "cascade_rework",
            "model_convergence",
            "minority_accuracy",
            "fanout_necessity",
        ]

        for key in metric_keys:
            value = metrics[key]
            assert value is not None, f"{key} is None -- SQL query returned no data"
            assert isinstance(value, (int, float)), (
                f"{key} is {type(value).__name__}, expected float"
            )

        # --- Value range checks (non-null + numeric already verified above) ---
        # Metrics run against the full DB, so exact values depend on accumulated data.
        # CAL-E2E-01 requires non-null numeric — verified above. These are sanity bounds.
        for key in metric_keys:
            assert metrics[key] >= 0, f"{key} should be non-negative, got {metrics[key]}"

    finally:
        # Cleanup all seeded data
        if ids is not None:
            async with pool.acquire() as conn:
                await _cleanup_metric_data(conn, ids)
        await pool.close()
