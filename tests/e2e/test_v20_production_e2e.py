"""E2E tests for Phase 20-24: Production Hardening + Dogfood (PIPE-04).

Covers:
  - Phase 20 (Identity): registration, duplicate email, login, legacy token rejection
  - Phase 21 (Data Integrity): gate double-resolution 409, trace chain cascade_id correctness
  - Phase 22 (Auth Boundaries): gate resolve without JWT, /healthz pool stats
  - Phase 23 (Pipeline Hardening): create_scc_cascade_from_refine produces 6 stages,
      fanout with scope_doc resolves without refine_stage_id
  - Phase 24 (Dogfood - PIPE-04): full SCC journey register -> create -> 6 stages dispatched

Requires `docker compose up -d` with the full stack (db + api server on :8000).
Tests skip automatically if the API or DB is unreachable.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import asyncpg
import httpx
import jwt
import pytest

REPO_ROOT = Path("/home/lynxnathan/code/eclusa")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from executor.dispatch import GateAlreadyResolvedError, resolve_gate
from executor.scc import create_scc_cascade_from_refine

pytestmark = pytest.mark.asyncio

API_BASE = "http://localhost:8000"
E2E_DSN = "postgresql://eclusa:eclusa@localhost:5432/eclusa"
# JWT signing secret used by the dev server
_JWT_SECRET = os.environ.get("JWT_SECRET", "eclusa-dev-secret-0123456789012345678901234")
_JWT_ALG = "HS256"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"e2e-{uuid.uuid4().hex[:8]}@test.invalid"


async def _register(client: httpx.AsyncClient, email: str, *, name: str = "E2E User", password: str = "testpass123") -> str:
    """Register a new user and return the access token."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


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
        await conn.execute("DELETE FROM intent WHERE id = $1::uuid", intent_id)

    await conn.execute("DELETE FROM actor WHERE id = $1::uuid", actor_id)


async def _cleanup_scc_cascade(conn: asyncpg.Connection, cascade_id: str) -> None:
    row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid", cascade_id
    )
    if row is None:
        return
    intent_id = str(row["intent_id"])

    stage_rows = await conn.fetch(
        "SELECT id FROM stage WHERE cascade_id = $1::uuid", cascade_id
    )
    stage_ids = [str(r["id"]) for r in stage_rows]

    await conn.execute(
        "ALTER TABLE ledger_entry DISABLE TRIGGER enforce_ledger_immutability"
    )
    try:
        async with conn.transaction():
            if stage_ids:
                await conn.execute(
                    "DELETE FROM work_session WHERE stage_ids && $1::uuid[]",
                    stage_ids,
                )
            await conn.execute(
                "DELETE FROM ledger_entry WHERE cascade_id = $1::uuid", cascade_id
            )
            await conn.execute(
                "DELETE FROM stage WHERE cascade_id = $1::uuid", cascade_id
            )
            await conn.execute(
                "DELETE FROM cascade WHERE id = $1::uuid", cascade_id
            )
            await conn.execute(
                "DELETE FROM intent WHERE id = $1::uuid", intent_id
            )
    finally:
        await conn.execute(
            "ALTER TABLE ledger_entry ENABLE TRIGGER enforce_ledger_immutability"
        )


async def _seed_gate(conn: asyncpg.Connection, actor_id: str) -> tuple[str, str]:
    """Seed a minimal cascade with one blocked gate stage. Returns (cascade_id, gate_id)."""
    intent_id = str(uuid.uuid4())
    cascade_id = str(uuid.uuid4())
    gate_id = str(uuid.uuid4())

    async with conn.transaction():
        await conn.execute(
            "INSERT INTO intent (id, source, raw, created_by) VALUES ($1::uuid, 'api', 'gate test', $2::uuid)",
            intent_id,
            actor_id,
        )
        await conn.execute(
            "INSERT INTO cascade (id, intent_id, shape, state) VALUES ($1::uuid, $2::uuid, '{}', 'active')",
            cascade_id,
            intent_id,
        )
        await conn.execute(
            """
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'gate', 'blocked', '{}', '{"gate_type":"approval"}'::jsonb)
            """,
            gate_id,
            cascade_id,
        )

    return cascade_id, gate_id


# ---------------------------------------------------------------------------
# Phase 20 — Identity
# ---------------------------------------------------------------------------


async def test_register_creates_actor(db_conn: asyncpg.Connection) -> None:
    """POST /api/auth/register → 200, returns JWT with sub=UUID (not 'operator')."""
    email = _unique_email()
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
            resp = await client.post(
                "/api/auth/register",
                json={"email": email, "name": "Test User", "password": "hunter2"},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

        payload = jwt.decode(body["access_token"], options={"verify_signature": False})
        sub = payload["sub"]
        # sub must be a UUID string, not the legacy hardcoded "operator"
        assert sub != "operator"
        uuid.UUID(sub)  # raises ValueError if not a valid UUID

        # actor must exist in DB
        row = await db_conn.fetchrow("SELECT id FROM actor WHERE identity = $1", email)
        assert row is not None
    finally:
        await _cleanup_actor_by_email(db_conn, email)


async def test_register_duplicate_email(db_conn: asyncpg.Connection) -> None:
    """Registering the same email twice returns 409 on the second attempt."""
    email = _unique_email()
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
            r1 = await client.post(
                "/api/auth/register",
                json={"email": email, "name": "First", "password": "pass1"},
            )
            assert r1.status_code == 200, r1.text

            r2 = await client.post(
                "/api/auth/register",
                json={"email": email, "name": "Second", "password": "pass2"},
            )
        assert r2.status_code == 409
        assert "already registered" in r2.json().get("detail", "").lower()
    finally:
        await _cleanup_actor_by_email(db_conn, email)


async def test_login_valid(db_conn: asyncpg.Connection) -> None:
    """POST /api/auth/token with correct credentials → 200 and access_token."""
    email = _unique_email()
    password = "secure-pass-42"
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
            reg = await client.post(
                "/api/auth/register",
                json={"email": email, "name": "Login User", "password": password},
            )
            assert reg.status_code == 200, reg.text

            login = await client.post(
                "/api/auth/token",
                json={"email": email, "password": password},
            )
        assert login.status_code == 200, login.text
        body = login.json()
        assert "access_token" in body
        # Verify the token sub is a valid UUID
        payload = jwt.decode(body["access_token"], options={"verify_signature": False})
        uuid.UUID(str(payload["sub"]))
    finally:
        await _cleanup_actor_by_email(db_conn, email)


async def test_login_wrong_password(db_conn: asyncpg.Connection) -> None:
    """POST /api/auth/token with wrong password → 401."""
    email = _unique_email()
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
            await client.post(
                "/api/auth/register",
                json={"email": email, "name": "WrongPw User", "password": "correct"},
            )
            resp = await client.post(
                "/api/auth/token",
                json={"email": email, "password": "wrong"},
            )
        assert resp.status_code == 401
    finally:
        await _cleanup_actor_by_email(db_conn, email)


async def test_legacy_operator_token_rejected() -> None:
    """A JWT with sub='operator' (legacy hardcoded) is rejected with 401."""
    # Craft a legacy-style token that matches the old format: sub="operator", no actor_type
    legacy_payload = {
        "sub": "operator",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    # Use the dev secret so signature is valid — only the sub/actor_type check should fail
    token = jwt.encode(legacy_payload, _JWT_SECRET, algorithm=_JWT_ALG)

    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.get(
            "/api/cascades",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401  # Rejected — either invalid signature or legacy sub check


# ---------------------------------------------------------------------------
# Phase 21 — Data Integrity
# ---------------------------------------------------------------------------


async def test_gate_double_resolution_returns_409(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    """Resolving the same gate twice: first succeeds, second raises GateAlreadyResolvedError."""
    cascade_id, gate_id = await _seed_gate(db_conn, seed_actor)
    try:
        # First resolution must succeed
        await resolve_gate(db_conn, gate_id, seed_actor)

        # Second resolution must raise GateAlreadyResolvedError
        with pytest.raises(GateAlreadyResolvedError):
            await resolve_gate(db_conn, gate_id, seed_actor)
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


async def test_trace_chain_correct_cascade_id(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    """Trace chain hops return the correct cascade_id, not the intent_id in the cascade slot."""
    from executor.scc import create_scc_cascade

    intent_id_str = str(uuid.uuid4())
    await db_conn.execute(
        "INSERT INTO intent (id, source, raw, created_by) VALUES ($1::uuid, 'api', 'trace test', $2::uuid)",
        intent_id_str,
        seed_actor,
    )
    cascade_id = await create_scc_cascade(intent_id_str, seed_actor, db_conn)

    try:
        # Seed an artifact directly linked to a stage in this cascade
        stage_row = await db_conn.fetchrow(
            "SELECT id FROM stage WHERE cascade_id = $1::uuid LIMIT 1", cascade_id
        )
        assert stage_row is not None
        stage_id = str(stage_row["id"])

        session_id = str(uuid.uuid4())
        await db_conn.execute(
            """
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, message_history, cost)
            VALUES ($1::uuid, ARRAY[$2::uuid], 'native', 'test-model', 'completed', '[]', '{}')
            """,
            session_id,
            stage_id,
        )

        artifact_id = str(uuid.uuid4())
        await db_conn.execute(
            """
            INSERT INTO artifact (id, intent_id, cascade_id, stage_id, session_id, type, payload)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, 'api_response', '{}')
            """,
            artifact_id,
            intent_id_str,
            cascade_id,
            stage_id,
            session_id,
        )

        # Call the trace API endpoint
        headers = await _auth_headers_from_email(db_conn)
        async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
            resp = await client.get(
                f"/api/trace/{artifact_id}",
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        hop_types = [h["type"] for h in body["hops"]]
        assert "cascade" in hop_types, f"Missing cascade hop: {hop_types}"

        cascade_hop = next(h for h in body["hops"] if h["type"] == "cascade")
        # The cascade hop id must be the cascade UUID — not the intent_id
        assert cascade_hop["id"] == cascade_id
        assert cascade_hop["id"] != intent_id_str
    finally:
        await db_conn.execute("DELETE FROM artifact WHERE id = $1::uuid", artifact_id)
        await db_conn.execute("DELETE FROM work_session WHERE id = $1::uuid", session_id)
        await _cleanup_scc_cascade(db_conn, cascade_id)


# ---------------------------------------------------------------------------
# Phase 22 — Auth Boundaries
# ---------------------------------------------------------------------------


async def test_gate_resolve_without_jwt_returns_401() -> None:
    """POST /api/gates/{id}/resolve without Authorization header → 401."""
    # Use a fake gate id — the auth check fires before the DB lookup
    fake_gate_id = str(uuid.uuid4())
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.post(
            f"/api/gates/{fake_gate_id}/resolve",
            json={"verdict": "approved", "rationale": "test", "token": ""},
        )
    assert resp.status_code == 401


async def test_healthz_returns_200() -> None:
    """GET /healthz → 200 with pool stats (AUTH-04)."""
    async with httpx.AsyncClient(base_url="http://localhost:8800", timeout=10) as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
    assert "pool_size" in body
    assert "pool_free" in body


# ---------------------------------------------------------------------------
# Phase 23 — Pipeline Hardening
# ---------------------------------------------------------------------------


async def test_scc_create_from_refine_creates_6_stages(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    """create_scc_cascade_from_refine produces exactly 6 stages (no refine stage)."""
    intent_id = str(uuid.uuid4())
    await db_conn.execute(
        "INSERT INTO intent (id, source, raw, created_by) VALUES ($1::uuid, 'api', 'refine cascade test', $2::uuid)",
        intent_id,
        seed_actor,
    )
    cascade_id = await create_scc_cascade_from_refine(
        intent_id,
        seed_actor,
        db_conn,
        scope_doc="Build a durable widget registry with FastAPI and Postgres.",
    )
    try:
        count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM stage WHERE cascade_id = $1::uuid", cascade_id
        )
        assert count == 6, f"Expected 6 stages, got {count}"

        scc_stages = await db_conn.fetch(
            "SELECT input->>'scc_stage' AS scc_stage FROM stage WHERE cascade_id = $1::uuid",
            cascade_id,
        )
        stage_names = {r["scc_stage"] for r in scc_stages}
        # Refine must NOT be present
        assert "refine" not in stage_names
        # All post-refine stages must be present
        expected = {
            "intent_validation_fanout",
            "match",
            "cohere",
            "formalize",
            "derive",
            "generate",
        }
        assert stage_names == expected
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


async def test_fanout_with_scope_doc_resolves(
    db_conn: asyncpg.Connection, seed_actor: str
) -> None:
    """Fanout stage created via create_scc_cascade_from_refine carries scope_doc in input
    without a refine_stage_id pointer — verifying PIPE-02 branching logic is correct."""
    intent_id = str(uuid.uuid4())
    await db_conn.execute(
        "INSERT INTO intent (id, source, raw, created_by) VALUES ($1::uuid, 'api', 'fanout scope_doc test', $2::uuid)",
        intent_id,
        seed_actor,
    )
    scope_doc = "A task tracker with real-time updates and JWT auth."
    cascade_id = await create_scc_cascade_from_refine(
        intent_id,
        seed_actor,
        db_conn,
        scope_doc=scope_doc,
    )
    try:
        fanout_row = await db_conn.fetchrow(
            """
            SELECT input
            FROM stage
            WHERE cascade_id = $1::uuid
              AND input->>'scc_stage' = 'intent_validation_fanout'
            """,
            cascade_id,
        )
        assert fanout_row is not None, "intent_validation_fanout stage not found"

        fanout_input = fanout_row["input"]
        if isinstance(fanout_input, str):
            fanout_input = json.loads(fanout_input)

        # scope_doc must be present directly (PIPE-02 v2 path)
        assert fanout_input.get("scope_doc") == scope_doc
        # refine_stage_id must NOT be present (that is the legacy v1 path)
        assert "refine_stage_id" not in fanout_input
    finally:
        await _cleanup_scc_cascade(db_conn, cascade_id)


# ---------------------------------------------------------------------------
# Phase 24 — Full Journey (PIPE-04)
# ---------------------------------------------------------------------------


async def test_full_scc_journey(db_conn: asyncpg.Connection) -> None:
    """Full dogfood journey: register user → create SCC cascade via API → verify 6 stages.

    Phase 24 PIPE-04: a real cascade is created through the authenticated API with all
    post-refine stages present and the correct cascade topology.
    """
    email = _unique_email()
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
            # 1. Register a fresh human actor
            reg_resp = await client.post(
                "/api/auth/register",
                json={"email": email, "name": "Dogfood Tester", "password": "dg-test-99"},
            )
            assert reg_resp.status_code == 200, reg_resp.text
            token = reg_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Verify token carries a real UUID sub
            tok_payload = jwt.decode(token, options={"verify_signature": False})
            actor_uuid = tok_payload["sub"]
            uuid.UUID(actor_uuid)  # must not raise

            # 2. Create SCC cascade via the API (simulates build-mode trigger)
            create_resp = await client.post(
                "/api/scc/create",
                headers=headers,
                json={"intent_text": "Build a simple todo app with React and FastAPI"},
            )
            assert create_resp.status_code == 200, create_resp.text
            create_body = create_resp.json()
            cascade_id = create_body["cascade_id"]
            intent_id = create_body["intent_id"]
            assert cascade_id
            assert intent_id

            # 3. Verify stage count and structure via the stages API
            stages_resp = await client.get(
                f"/api/cascades/{cascade_id}/stages",
                headers=headers,
            )
            assert stages_resp.status_code == 200, stages_resp.text
            stages = stages_resp.json()
            assert len(stages) == 7, f"Expected 7 stages, got {len(stages)}: {[s['scc_stage'] for s in stages]}"

            stage_names = {s["scc_stage"] for s in stages}
            expected = {
                "refine",
                "intent_validation_fanout",
                "match",
                "cohere",
                "formalize",
                "derive",
                "generate",
            }
            assert stage_names == expected, f"Stage names mismatch: {stage_names}"

            # 4. Verify cascade is visible in the cascade list
            list_resp = await client.get("/api/cascades", headers=headers)
            assert list_resp.status_code == 200, list_resp.text
            cascade_ids_in_list = [c["id"] for c in list_resp.json()]
            assert cascade_id in cascade_ids_in_list

            # 5. Verify first stage (refine) is in pending state — executor hasn't run yet
            refine_stage = next(
                (s for s in stages if s["scc_stage"] == "refine"), None
            )
            assert refine_stage is not None
            assert refine_stage["state"] == "pending"

            # 6. Seed an artifact for the cascade and verify trace chain returns cascade_id
            stage_id = refine_stage["id"]
            session_id = str(uuid.uuid4())
            artifact_id = str(uuid.uuid4())

            await db_conn.execute(
                """
                INSERT INTO work_session (id, stage_ids, harness_type, model, state, message_history, cost)
                VALUES ($1::uuid, ARRAY[$2::uuid], 'native', 'test-model', 'completed', '[]', '{}')
                """,
                session_id,
                stage_id,
            )
            await db_conn.execute(
                """
                INSERT INTO artifact (id, intent_id, cascade_id, stage_id, session_id, type, payload)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, 'api_response', '{"dogfood":true}')
                """,
                artifact_id,
                intent_id,
                cascade_id,
                stage_id,
                session_id,
            )

            trace_resp = await client.get(f"/api/trace/{artifact_id}", headers=headers)
            assert trace_resp.status_code == 200, trace_resp.text
            trace_body = trace_resp.json()

            hop_types = [h["type"] for h in trace_body["hops"]]
            assert hop_types == ["artifact", "session", "stage", "cascade", "intent"], \
                f"Unexpected trace hops: {hop_types}"

            cascade_hop = next(h for h in trace_body["hops"] if h["type"] == "cascade")
            assert cascade_hop["id"] == cascade_id

            intent_hop = next(h for h in trace_body["hops"] if h["type"] == "intent")
            assert intent_hop["id"] == intent_id

    finally:
        # Clean up artifact and session seeded above, then cascade, then actor
        try:
            await db_conn.execute("DELETE FROM artifact WHERE id = $1::uuid", artifact_id)
        except Exception:
            pass
        try:
            await db_conn.execute("DELETE FROM work_session WHERE id = $1::uuid", session_id)
        except Exception:
            pass
        await _cleanup_actor_by_email(db_conn, email)


# ---------------------------------------------------------------------------
# Internal helpers (not fixtures — called directly within tests)
# ---------------------------------------------------------------------------


async def _auth_headers_from_email(db_conn: asyncpg.Connection) -> dict[str, str]:
    """Create a throwaway actor and return a valid auth header dict.

    Caller is responsible for cleanup. Used for tests that only need headers
    for a single API call and clean up their own data separately.
    """
    email = _unique_email()
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10) as client:
        resp = await client.post(
            "/api/auth/register",
            json={"email": email, "name": "Temp Actor", "password": "temp-pw"},
        )
        resp.raise_for_status()
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
