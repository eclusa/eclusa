"""Tests for email adapters (ADAPT-03, ADAPT-04).

Plan 05-04: Real IMAP inbound adapter with Message-ID dedup and sanitization gate.
Plan 05-05: SMTP outbound gate surfacing via EmailAdapter.surface_gate().
Tests using conn fixture require testcontainer DB.
"""

from __future__ import annotations

import email
import email.policy
import json
import uuid
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from adapters.email.adapter import EmailAdapter
from adapters.email.inbound import process_message
from adapters.protocol import GateContext

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_raw_email(
    message_id: str,
    sender: str,
    subject: str,
    body: str,
) -> bytes:
    """Build a minimal RFC822 email as bytes."""
    msg = email.message.EmailMessage()
    msg["Message-ID"] = message_id
    msg["From"] = sender
    msg["To"] = "inbox@example.com"
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes(policy=email.policy.SMTP)


async def _seed_actor(
    conn: asyncpg.Connection, identity: str = "system-email-test"
) -> str:
    """Seed a system actor for email adapter tests. Idempotent by identity."""
    row = await conn.fetchrow(
        "SELECT id FROM actor WHERE identity = $1 LIMIT 1", identity
    )
    if row:
        return str(row["id"])
    row = await conn.fetchrow(
        """
        INSERT INTO actor (id, type, identity)
        VALUES (gen_random_uuid(), 'system', $1)
        RETURNING id
        """,
        identity,
    )
    return str(row["id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_imap_poll_creates_intent(conn: asyncpg.Connection) -> None:
    """ADAPT-03: process_message() creates an intent row in DB with source='email'."""
    actor_id = await _seed_actor(conn)
    message_id = f"<test-{uuid.uuid4()}@example.com>"
    raw_bytes = _build_raw_email(
        message_id=message_id,
        sender="alice@example.com",
        subject="Hello Eclusa",
        body="Please process this request.",
    )

    intent_id = await process_message(raw_bytes, actor_id, conn)

    assert intent_id is not None, "Expected intent_id to be returned on success"

    # Verify intent row exists in DB
    row = await conn.fetchrow(
        "SELECT source, context FROM intent WHERE id = $1::uuid",
        intent_id,
    )
    assert row is not None, f"No intent row found for id={intent_id}"
    assert row["source"] == "email"

    # context must contain message_id matching the Message-ID header
    ctx = (
        json.loads(row["context"])
        if isinstance(row["context"], str)
        else row["context"]
    )
    assert ctx.get("message_id") == message_id, (
        f"context.message_id mismatch: got {ctx.get('message_id')!r}, expected {message_id!r}"
    )


async def test_message_id_dedup(conn: asyncpg.Connection) -> None:
    """ADAPT-03: Duplicate Message-ID skipped silently — only 1 intent row created (D-09)."""
    actor_id = await _seed_actor(conn)
    message_id = f"<dedup-{uuid.uuid4()}@example.com>"
    raw_bytes = _build_raw_email(
        message_id=message_id,
        sender="bob@example.com",
        subject="Dedup test",
        body="This should only create one intent row.",
    )

    first_id = await process_message(raw_bytes, actor_id, conn)
    assert first_id is not None, "First call must return an intent_id"

    second_id = await process_message(raw_bytes, actor_id, conn)
    assert second_id is None, "Duplicate Message-ID must return None (skipped)"

    # Only 1 intent row must exist with this message_id
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM intent WHERE context->>'message_id' = $1 AND source = 'email'",
        message_id,
    )
    assert count == 1, f"Expected 1 intent row, got {count}"


async def test_smtp_gate_email_sent() -> None:
    """ADAPT-03: surface_gate() sends a gate surfacing email via SMTP (Plan 05-05)."""
    context = GateContext(
        cascade_id="cascade-abc",
        stage_id="stage-123",
        gate_description="Should we proceed with the refactoring?",
        model_recommendation="Yes, proceed — 3/3 models agree",
        eligible_actor_ids=["alice@example.com"],
        resolve_url="http://localhost:8000/gates/stage-123/resolve",
    )
    adapter = EmailAdapter(smtp_host="localhost", smtp_port=1025)

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await adapter.surface_gate(context)

    mock_send.assert_called_once()
    call_args = mock_send.call_args
    message = call_args.args[0]  # EmailMessage
    assert "alice@example.com" in message["To"]
    assert "stage-123"[:8] in message["Subject"]
    assert (
        "resolve" in message["Subject"].lower()
        or "decision" in message["Subject"].lower()
    )
    # Check plain text content contains resolve URL
    plain = message.get_body(preferencelist=("plain",))
    assert plain is not None
    content = plain.get_content()
    assert "http://localhost:8000/gates/stage-123/resolve" in content
    assert "Should we proceed" in content


async def test_resolve_endpoint_rbac(conn: asyncpg.Connection, pg_container) -> None:
    """SCHEMA-08: POST /gates/{gate_id}/resolve enforces RBAC before calling resolve_gate().

    Uses httpx.AsyncClient with ASGITransport to keep pool + HTTP calls in the same
    event loop — avoids asyncpg "pool bound to different loop" error with TestClient.
    """
    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport

    from adapters.web.routes import router as gates_router

    def _get_dsn() -> str:
        url = pg_container.get_connection_url()
        if "postgresql+psycopg2://" in url:
            url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
        elif "postgresql+asyncpg://" in url:
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url

    dsn = _get_dsn()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    try:
        # Seed: permitted actor (can resolve 'approval'), denied actor (empty resolve_gates)
        permitted_actor_id = await conn.fetchval(
            """
            INSERT INTO actor (id, type, identity, permissions)
            VALUES (gen_random_uuid(), 'human', 'alice@rbac-endpoint-test.com', $1::jsonb)
            RETURNING id::text
            """,
            json.dumps({"resolve_gates": ["approval"]}),
        )
        denied_actor_id = await conn.fetchval(
            """
            INSERT INTO actor (id, type, identity, permissions)
            VALUES (gen_random_uuid(), 'human', 'bob@rbac-endpoint-test.com', $1::jsonb)
            RETURNING id::text
            """,
            json.dumps({"resolve_gates": []}),
        )

        # Seed intent + cascade + blocked gate stage
        intent_id = await conn.fetchval(
            """
            INSERT INTO intent (id, source, raw, created_by)
            VALUES (gen_random_uuid(), 'api', 'rbac endpoint test intent', $1::uuid)
            RETURNING id::text
            """,
            permitted_actor_id,
        )
        cascade_id = await conn.fetchval(
            """
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES (gen_random_uuid(), $1::uuid, '{}'::jsonb, 'active')
            RETURNING id::text
            """,
            intent_id,
        )
        stage_id = await conn.fetchval(
            """
            INSERT INTO stage (id, cascade_id, type, state, input)
            VALUES (gen_random_uuid(), $1::uuid, 'gate', 'blocked', $2::jsonb)
            RETURNING id::text
            """,
            cascade_id,
            json.dumps({"gate_type": "approval"}),
        )

        # Build FastAPI app with pool injected into app state
        app = FastAPI()
        app.include_router(gates_router)
        app.state.pool = pool

        # Use httpx.AsyncClient with ASGITransport — keeps pool in same event loop
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # Denied actor → 403
            resp = await client.post(
                f"/gates/{stage_id}/resolve",
                json={"token": "", "decision": "approve", "actor_id": denied_actor_id},
            )
            assert resp.status_code == 403, (
                f"Expected 403 for denied actor, got {resp.status_code}: {resp.text}"
            )

            # Non-existent gate → 404
            resp = await client.post(
                "/gates/00000000-0000-0000-0000-000000000000/resolve",
                json={
                    "token": "",
                    "decision": "approve",
                    "actor_id": permitted_actor_id,
                },
            )
            assert resp.status_code == 404, (
                f"Expected 404 for missing gate, got {resp.status_code}: {resp.text}"
            )

            # Permitted actor → 200
            resp = await client.post(
                f"/gates/{stage_id}/resolve",
                json={
                    "token": "",
                    "decision": "approve",
                    "actor_id": permitted_actor_id,
                },
            )
            assert resp.status_code == 200, (
                f"Expected 200 for permitted actor, got {resp.status_code}: {resp.text}"
            )
            data = resp.json()
            assert data["status"] == "resolved"
            assert data["gate_id"] == stage_id

            # Already resolved → 409
            resp = await client.post(
                f"/gates/{stage_id}/resolve",
                json={
                    "token": "",
                    "decision": "approve",
                    "actor_id": permitted_actor_id,
                },
            )
            assert resp.status_code == 409, (
                f"Expected 409 for already-resolved gate, got {resp.status_code}: {resp.text}"
            )

        # Verify stage resolved in DB
        state = await conn.fetchval(
            "SELECT state FROM stage WHERE id = $1::uuid", stage_id
        )
        assert state == "resolved", f"Expected state='resolved' in DB, got {state!r}"
    finally:
        await pool.close()
