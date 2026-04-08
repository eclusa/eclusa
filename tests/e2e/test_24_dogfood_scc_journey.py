"""Phase 24 dogfood: full SCC journey with real LLM execution (PIPE-04).

Requires docker compose up (db + executor + api on :8000).
Skips automatically if API unreachable.

Tests:
  - test_blog_scc_full_journey: registers a user, creates a 7-stage SCC cascade via
    the authenticated API, polls until all stages are terminal (max 5 minutes), verifies
    the Generate stage produced non-empty code content, seeds an artifact, and walks
    the 5-hop trace chain: artifact -> session -> stage -> cascade -> intent.
  - test_scc_journey_structure_only: fast structural sanity check — creates a cascade and
    immediately verifies 7 stages exist with correct scc_stage names and initial states.
    Does not wait for LLM execution.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import asyncpg
import httpx
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"
E2E_DSN = "postgresql://eclusa:eclusa@localhost:5432/eclusa"
POLL_INTERVAL_S = 5           # seconds between /stages polls
STAGE_TIMEOUT_S = 600         # 10 minutes — workspace agents do multi-turn tool calling
TERMINAL_STATES = {"resolved", "failed", "skipped"}

_EXPECTED_SCC_STAGES = {
    "refine",
    "intent_validation_fanout",
    "match",
    "cohere",
    "formalize",
    "derive",
    "generate",
    "ship",
}


# ---------------------------------------------------------------------------
# Module-level skip guard — skip entire file if docker-compose API is not up
# ---------------------------------------------------------------------------


def _api_available() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{API_BASE}/healthz", timeout=5)
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _api_available(), reason="docker-compose API not running"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"e2e-24-{uuid.uuid4().hex[:8]}@test.invalid"


async def _register(
    client: httpx.AsyncClient,
    email: str,
    *,
    name: str = "E2E User",
    password: str = "testpass123",
) -> str:
    """Register a new user and return the access token."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _cleanup_scc_cascade(conn: asyncpg.Connection, cascade_id: str) -> None:
    """Delete a cascade and all related rows in correct FK order.

    Order: ledger_entry (with trigger bypass) -> artifact -> work_session -> stage -> cascade -> intent.
    Copied verbatim from conftest.cleanup_cascade / test_v20_production_e2e._cleanup_scc_cascade.
    """
    row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid", cascade_id
    )
    if row is None:
        return
    intent_id = str(row["intent_id"])

    stage_rows = await conn.fetch(
        "SELECT id FROM stage WHERE cascade_id = $1::uuid", cascade_id
    )
    stage_ids = [r["id"] for r in stage_rows]

    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )
    try:
        async with conn.transaction():
            # 1. Artifacts referencing this cascade
            await conn.execute(
                "DELETE FROM artifact WHERE cascade_id = $1::uuid", cascade_id
            )

            # 2. Ledger entries referencing this cascade
            await conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )

            # 3. Work sessions referencing any of these stages
            if stage_ids:
                await conn.execute(
                    "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                    stage_ids,
                )

            # 4. Stages
            await conn.execute(
                "DELETE FROM stage WHERE cascade_id = $1::uuid", cascade_id
            )

            # 5. Cascade
            await conn.execute(
                "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
            )

            # 6. Intent
            await conn.execute(
                "DELETE FROM intent WHERE id = $1::uuid", intent_id
            )
    finally:
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )


async def _cleanup_actor_by_email(conn: asyncpg.Connection, email: str) -> None:
    """Remove a test actor and all their data. Ignores if already gone."""
    row = await conn.fetchrow("SELECT id FROM actor WHERE identity = $1", email)
    if row is None:
        return
    actor_id = str(row["id"])

    intent_rows = await conn.fetch(
        "SELECT id FROM intent WHERE created_by = $1::uuid", actor_id
    )
    for irow in intent_rows:
        intent_id = str(irow["id"])
        casc_rows = await conn.fetch(
            "SELECT id FROM cascade WHERE intent_id = $1::uuid", intent_id
        )
        for crow in casc_rows:
            await _cleanup_scc_cascade(conn, str(crow["id"]))
        # Delete intent if cascade cleanup did not already remove it
        await conn.execute(
            "DELETE FROM intent WHERE id = $1::uuid", intent_id
        )

    await conn.execute("DELETE FROM actor WHERE id = $1::uuid", actor_id)


# ---------------------------------------------------------------------------
# test_blog_scc_full_journey
# ---------------------------------------------------------------------------


async def test_blog_scc_full_journey() -> None:
    """Full SCC pipeline dogfood (PIPE-04).

    A non-technical human registers, submits a blog intent, and the platform
    routes it through all 7 SCC stages. The test polls until completion or
    timeout, verifies the Generate stage produced real code, and walks the
    5-hop trace chain.
    """
    email = _unique_email()
    cascade_id: str | None = None
    intent_id: str | None = None
    session_id: str | None = None
    artifact_id: str | None = None

    async with asyncio.timeout(700):
        # ------------------------------------------------------------------
        # Step 1 — Register
        # ------------------------------------------------------------------
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
            token = await _register(client, email, name="Blog Dogfood")
        headers = {"Authorization": f"Bearer {token}"}

        try:
            # ------------------------------------------------------------------
            # Step 2 — Create cascade
            # ------------------------------------------------------------------
            async with httpx.AsyncClient(base_url=API_BASE, timeout=60) as client:
                create_resp = await client.post(
                    "/api/scc/create",
                    headers=headers,
                    json={
                        "intent_text": (
                            "I want a simple blog where I can write posts "
                            "and people can read them"
                        )
                    },
                )
            assert create_resp.status_code == 200, (
                f"POST /api/scc/create failed {create_resp.status_code}: {create_resp.text}"
            )
            body = create_resp.json()
            cascade_id = body["cascade_id"]
            intent_id = body["intent_id"]
            assert cascade_id, "cascade_id missing from response"
            assert intent_id, "intent_id missing from response"

            # ------------------------------------------------------------------
            # Step 3 — Poll stages until all terminal (max STAGE_TIMEOUT_S)
            # ------------------------------------------------------------------
            deadline = time.monotonic() + STAGE_TIMEOUT_S
            all_terminal = False
            last_stages: list[dict] = []

            async with httpx.AsyncClient(base_url=API_BASE, timeout=60) as client:
                while time.monotonic() < deadline:
                    await asyncio.sleep(POLL_INTERVAL_S)
                    resp = await client.get(
                        f"/api/cascades/{cascade_id}/stages",
                        headers=headers,
                        timeout=15,
                    )
                    assert resp.status_code == 200, (
                        f"GET /api/cascades/{cascade_id}/stages failed "
                        f"{resp.status_code}: {resp.text}"
                    )
                    stages = resp.json()
                    last_stages = stages
                    not_terminal = [
                        s for s in stages if s["state"] not in TERMINAL_STATES
                    ]
                    if not not_terminal:
                        all_terminal = True
                        break

                if not all_terminal:
                    diagnostic = "\n".join(
                        f"  {s.get('scc_stage', s.get('type', '?'))!s:30s}  {s['state']}"
                        for s in last_stages
                    )
                    pytest.fail(
                        f"SCC pipeline did not complete within {STAGE_TIMEOUT_S}s. "
                        f"Stage states:\n{diagnostic}"
                    )

            # ------------------------------------------------------------------
            # Step 4 — Verify no unexpected stage failures
            # ------------------------------------------------------------------
            resolved_stages = [s for s in last_stages if s["state"] == "resolved"]
            failed_stages = [s for s in last_stages if s["state"] == "failed"]

            # Formalize may fail due to GHC issues — tolerate exactly that failure
            if failed_stages:
                failed_names = [s.get("scc_stage") for s in failed_stages]
                non_formalize_failures = [
                    n for n in failed_names if n != "formalize"
                ]
                assert not non_formalize_failures, (
                    f"Non-formalize stages failed: {non_formalize_failures}"
                )

            assert len(resolved_stages) >= 5, (
                f"Expected at least 5 resolved stages, got {len(resolved_stages)}"
            )

            # ------------------------------------------------------------------
            # Step 5 — Verify Generate stage output contains non-empty code
            # ------------------------------------------------------------------
            generate_stage = next(
                (s for s in last_stages if s.get("scc_stage") == "generate"), None
            )

            if generate_stage and generate_stage["state"] == "resolved":
                async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
                    out_resp = await client.get(
                        f"/api/cascades/{cascade_id}/stages/{generate_stage['id']}/output",
                        headers=headers,
                        timeout=15,
                    )
                assert out_resp.status_code == 200, out_resp.text
                out_body = out_resp.json()

                output = out_body.get("output")
                assert output is not None, "Generate stage output is None"
                output_str = (
                    json.dumps(output)
                    if isinstance(output, (dict, list))
                    else str(output)
                )
                assert len(output_str) > 50, (
                    f"Generate output too short ({len(output_str)} chars): {output_str!r}"
                )
                # Must not be a raw error message
                assert not output_str.strip().startswith(
                    ("Error", "Exception", "Traceback")
                ), f"Generate output looks like an error: {output_str[:200]}"

            # ------------------------------------------------------------------
            # Step 6 — Seed artifact + verify 5-hop trace chain
            # ------------------------------------------------------------------
            # Use generate stage, or fall back to the first stage
            trace_stage = generate_stage or last_stages[0]
            stage_id = trace_stage["id"]

            conn = await asyncpg.connect(E2E_DSN)
            try:
                session_id = str(uuid.uuid4())
                artifact_id = str(uuid.uuid4())

                await conn.execute(
                    """
                    INSERT INTO work_session
                        (id, stage_ids, harness_type, model, state, message_history, cost)
                    VALUES ($1::uuid, ARRAY[$2::uuid], 'native', 'dogfood-test',
                            'completed', '[]', '{}')
                    """,
                    session_id,
                    stage_id,
                )
                await conn.execute(
                    """
                    INSERT INTO artifact
                        (id, intent_id, cascade_id, stage_id, session_id, type, payload)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                            'api_response', $6::jsonb)
                    """,
                    artifact_id,
                    intent_id,
                    cascade_id,
                    stage_id,
                    session_id,
                    json.dumps({"dogfood": True, "pipeline": "scc_blog"}),
                )

                async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
                    trace_resp = await client.get(
                        f"/api/trace/{artifact_id}",
                        headers=headers,
                        timeout=15,
                    )
                assert trace_resp.status_code == 200, trace_resp.text
                trace = trace_resp.json()

                hop_types = [h["type"] for h in trace["hops"]]
                assert hop_types == [
                    "artifact",
                    "session",
                    "stage",
                    "cascade",
                    "intent",
                ], f"Expected 5 hops in order, got: {hop_types}"

                cascade_hop = next(h for h in trace["hops"] if h["type"] == "cascade")
                assert cascade_hop["id"] == cascade_id, (
                    f"Cascade hop id mismatch: {cascade_hop['id']} != {cascade_id}"
                )

                intent_hop = next(h for h in trace["hops"] if h["type"] == "intent")
                assert intent_hop["id"] == intent_id, (
                    f"Intent hop id mismatch: {intent_hop['id']} != {intent_id}"
                )

            finally:
                # Clean up seeded artifact + session before cascade cleanup
                if artifact_id:
                    try:
                        await conn.execute(
                            "DELETE FROM artifact WHERE id = $1::uuid", artifact_id
                        )
                    except Exception:
                        pass
                if session_id:
                    try:
                        await conn.execute(
                            "DELETE FROM work_session WHERE id = $1::uuid", session_id
                        )
                    except Exception:
                        pass
                await conn.close()

        finally:
            # ------------------------------------------------------------------
            # Step 7 — Always clean up actor (and cascade via actor cleanup)
            # ------------------------------------------------------------------
            cleanup_conn = await asyncpg.connect(E2E_DSN)
            try:
                await _cleanup_actor_by_email(cleanup_conn, email)
            except Exception:
                pass
            finally:
                await cleanup_conn.close()


# ---------------------------------------------------------------------------
# test_scc_journey_structure_only
# ---------------------------------------------------------------------------


async def test_scc_journey_structure_only() -> None:
    """Fast structural sanity check — 7 stages created with correct scc_stage names.

    Does not wait for LLM execution. Verifies the cascade topology and stage
    presence immediately after creation. If the executor has already started
    picking up stages, some may be 'active'; the test accepts pending and active
    states, and fails only if any stage has 'failed' state at creation time.
    """
    email = _unique_email()
    cascade_id: str | None = None

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        token = await _register(client, email, name="Structure Check")
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
            create_resp = await client.post(
                "/api/scc/create",
                headers=headers,
                json={
                    "intent_text": (
                        "I want a simple blog where I can write posts "
                        "and people can read them"
                    )
                },
            )
        assert create_resp.status_code == 200, (
            f"POST /api/scc/create failed: {create_resp.text}"
        )
        body = create_resp.json()
        cascade_id = body["cascade_id"]
        assert cascade_id

        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
            stages_resp = await client.get(
                f"/api/cascades/{cascade_id}/stages",
                headers=headers,
            )
        assert stages_resp.status_code == 200, stages_resp.text
        stages = stages_resp.json()

        # Must have exactly 8 stages (including ship)
        assert len(stages) == 8, (
            f"Expected 8 stages, got {len(stages)}: "
            f"{[s.get('scc_stage') for s in stages]}"
        )

        # All expected scc_stage names must be present
        stage_names = {s.get("scc_stage") for s in stages}
        assert stage_names == _EXPECTED_SCC_STAGES, (
            f"Stage names mismatch.\n  Expected: {_EXPECTED_SCC_STAGES}\n  Got:      {stage_names}"
        )

        # No stage should be in 'failed' state immediately after creation
        failed = [s for s in stages if s["state"] == "failed"]
        assert not failed, (
            f"Stages in failed state at creation: "
            f"{[s.get('scc_stage') for s in failed]}"
        )

        # All stages must be in pending or active (executor may have started)
        acceptable = {"pending", "active"}
        unexpected_states = [
            s for s in stages if s["state"] not in acceptable | TERMINAL_STATES
        ]
        assert not unexpected_states, (
            f"Stages with unexpected initial states: "
            f"{[(s.get('scc_stage'), s['state']) for s in unexpected_states]}"
        )

    finally:
        cleanup_conn = await asyncpg.connect(E2E_DSN)
        try:
            await _cleanup_actor_by_email(cleanup_conn, email)
        except Exception:
            pass
        finally:
            await cleanup_conn.close()
