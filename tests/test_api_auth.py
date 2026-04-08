from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient

from adapters.web.api.auth import verify_token
from adapters.web.app import create_app

pytestmark = pytest.mark.asyncio


async def test_auth_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "unit-test-secret-for-eclusa-auth-0123456789"
    monkeypatch.setenv("JWT_SECRET", secret)

    app = create_app()
    app.state.pool = object()
    app.state._owns_pool = False

    @app.get("/whoami")
    async def whoami(payload: dict = Depends(verify_token)) -> dict:
        return payload

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.post("/api/auth/token", json={"secret": secret})
        assert ok.status_code == 200
        token = ok.json()["access_token"]
        assert ok.json()["token_type"] == "bearer"

        bad = await client.post("/api/auth/token", json={"secret": "wrong"})
        assert bad.status_code == 401

        payload_resp = await client.get(
            "/whoami",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert payload_resp.status_code == 200
        payload = payload_resp.json()
        assert payload["actor_id"] == "operator"
        assert "exp" in payload

        expired = jwt.encode(
            {
                "actor_id": "operator",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            secret,
            algorithm="HS256",
        )
        expired_resp = await client.get(
            "/whoami",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert expired_resp.status_code == 401


async def test_create_app_registers_api_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "another-secret-for-eclusa-auth-0123456789")
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/api/auth/token" in paths
    assert "/api/cascades" in paths
    assert "/api/cascades/{cascade_id}" in paths
    assert "/api/gates" in paths
    assert "/api/gates/{gate_id}/resolve" in paths
    assert "/api/sessions" in paths
    assert "/api/sessions/{session_id}/messages" in paths
    assert "/api/costs" in paths
    assert "/api/ledger" in paths
    assert "/api/knowledge/entities" in paths
    assert "/api/knowledge/facts" in paths
    assert "/api/knowledge/communities" in paths
    assert "/api/metrics" in paths
    assert "/ws/sessions/{session_id}" in paths
