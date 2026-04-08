"""Tests for harness.formalize."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import harness.formalize as formalize

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
def pg_container():
    return SimpleNamespace(get_connection_url=lambda: "postgresql://localhost/test")


@pytest.fixture(scope="session")
def db_url(pg_container):
    return pg_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(pg_container, db_url):
    del pg_container, db_url
    yield


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self):
        self.executed = []
        self.fetchrow_calls = []

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "OK"

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return {"intent_id": "11111111-1111-1111-1111-111111111111"}


def _process(stdout=b"", stderr=b"", returncode=0, communicate_side_effect=None):
    proc = SimpleNamespace()
    proc.returncode = returncode
    proc.kill = MagicMock()
    if communicate_side_effect is None:
        proc.communicate = AsyncMock(return_value=(stdout, stderr))
    else:
        proc.communicate = AsyncMock(side_effect=communicate_side_effect)
    return proc


async def test_draft_constraints_uses_agent_and_stage_context(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, model, system_prompt=None):
            captured["model"] = model
            captured["system_prompt"] = system_prompt

        async def run(self, prompt):
            captured["prompt"] = prompt
            return SimpleNamespace(output="data Foo = Foo")

    monkeypatch.setattr(formalize, "Agent", FakeAgent)
    stage = {
        "id": "stage-1",
        "cascade_id": "cascade-1",
        "input": {
            "matched_sources": [{"id": "s1", "name": "source"}],
            "cohere_context": "cohere says yes",
        },
    }

    source = await formalize.draft_constraints(None, stage)

    assert source == "data Foo = Foo"
    assert captured["model"] == formalize.DEFAULT_FORMALIZE_MODEL
    assert "Matched sources:" in captured["prompt"]
    assert "cohere says yes" in captured["prompt"]


async def test_verify_with_ghc_success_first_try(monkeypatch, tmp_path):
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _process(stdout=b"compiled\n", stderr=b"")

    monkeypatch.setattr(formalize, "GHC_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        formalize.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
    )

    ok, output = await formalize.verify_with_ghc("module Foo where\n")

    assert ok is True
    assert output == "compiled\n"
    assert captured["args"][:5] == (
        "docker",
        "exec",
        formalize.GHC_CONTAINER_NAME,
        "ghc",
        "-fno-code",
    )
    assert captured["args"][5].endswith(".hs")
    assert captured["kwargs"]["stdout"] is asyncio.subprocess.PIPE
    assert captured["kwargs"]["stderr"] is asyncio.subprocess.PIPE


async def test_verify_with_ghc_failure_normalizes_temp_path(monkeypatch, tmp_path):
    captured = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["path"] = args[-1]
        text = f"{args[-1]}:1:1: error: boom".encode()
        return _process(stdout=b"", stderr=text, returncode=1)

    monkeypatch.setattr(formalize, "GHC_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        formalize.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
    )

    ok, output = await formalize.verify_with_ghc("module Foo where\n")

    assert ok is False
    assert "constraints.hs:1:1: error: boom" in output
    assert captured["path"].endswith(".hs")


async def test_verify_with_ghc_timeout_returns_message(monkeypatch, tmp_path):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return _process(communicate_side_effect=asyncio.TimeoutError())

    monkeypatch.setattr(formalize, "GHC_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        formalize.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
    )

    ok, output = await formalize.verify_with_ghc("module Foo where\n")

    assert ok is False
    assert output == "GHC compilation timed out"


async def test_handle_formalize_happy_path_persists_success(monkeypatch):
    conn = _FakeConn()
    stage = {
        "id": "stage-1",
        "cascade_id": "cascade-1",
        "input": {"matched_sources": [], "cohere_context": "ok"},
    }
    draft_calls = []
    verify_calls = []

    async def fake_draft_constraints(conn_arg, stage_arg):
        draft_calls.append(stage_arg["input"].copy())
        return "module Foo where\n"

    async def fake_verify_with_ghc(source):
        verify_calls.append(source)
        return True, "ghc ok"

    monkeypatch.setattr(formalize, "draft_constraints", fake_draft_constraints)
    monkeypatch.setattr(formalize, "verify_with_ghc", fake_verify_with_ghc)

    success, source, ghc_output = await formalize.handle_formalize(
        conn, stage, actor_id="22222222-2222-2222-2222-222222222222"
    )

    assert success is True
    assert source == "module Foo where\n"
    assert ghc_output == "ghc ok"
    assert draft_calls == [{"matched_sources": [], "cohere_context": "ok"}]
    assert verify_calls == ["module Foo where\n"]
    assert any("INSERT INTO artifact" in query for query, _ in conn.executed)
    assert any(
        "UPDATE stage" in query and "resolved" in query for query, _ in conn.executed
    )


async def test_handle_formalize_retries_with_verbatim_feedback(monkeypatch):
    conn = _FakeConn()
    stage = {
        "id": "stage-1",
        "cascade_id": "cascade-1",
        "input": {"matched_sources": ["a"], "cohere_context": "ctx"},
    }
    draft_inputs = []
    verify_inputs = []
    drafted = ["module Foo where\n", "module Foo where\n", "module Foo where\n"]
    ghc_outputs = ["stage-1.hs:1:1: type error 1", "stage-1.hs:1:1: type error 2"]

    async def fake_draft_constraints(conn_arg, stage_arg):
        draft_inputs.append(stage_arg["input"].copy())
        return drafted[len(draft_inputs) - 1]

    async def fake_verify_with_ghc(source):
        verify_inputs.append(source)
        if len(verify_inputs) <= 2:
            return False, ghc_outputs[len(verify_inputs) - 1]
        return True, "ok"

    monkeypatch.setattr(formalize, "draft_constraints", fake_draft_constraints)
    monkeypatch.setattr(formalize, "verify_with_ghc", fake_verify_with_ghc)

    success, source, ghc_output = await formalize.handle_formalize(
        conn, stage, actor_id="22222222-2222-2222-2222-222222222222"
    )

    assert success is True
    assert source == "module Foo where\n"
    assert ghc_output == "ok"
    assert len(draft_inputs) == 3
    assert draft_inputs[1]["ghc_feedback"] == ghc_outputs[0]
    assert draft_inputs[1]["previous_haskell"] == "module Foo where\n"
    assert draft_inputs[2]["ghc_feedback"] == ghc_outputs[1]
    assert verify_inputs == drafted[:3]


async def test_handle_formalize_raises_after_max_retries(monkeypatch):
    conn = _FakeConn()
    stage = {
        "id": "stage-1",
        "cascade_id": "cascade-1",
        "input": {"matched_sources": [], "cohere_context": "ctx"},
    }
    draft_calls = 0

    async def fake_draft_constraints(conn_arg, stage_arg):
        nonlocal draft_calls
        draft_calls += 1
        return "module Foo where\n"

    async def fake_verify_with_ghc(source):
        return False, "type error"

    monkeypatch.setattr(formalize, "draft_constraints", fake_draft_constraints)
    monkeypatch.setattr(formalize, "verify_with_ghc", fake_verify_with_ghc)

    with pytest.raises(formalize.FormalizeError):
        await formalize.handle_formalize(
            conn, stage, actor_id="22222222-2222-2222-2222-222222222222"
        )

    assert draft_calls == formalize.GHC_MAX_RETRIES
    assert any(
        "UPDATE stage" in query and "failed" in query for query, _ in conn.executed
    )


async def test_verify_with_ghc_limits_concurrency_to_three(monkeypatch, tmp_path):
    started = 0
    max_started = 0
    reached_three = asyncio.Event()
    release = asyncio.Event()

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal started, max_started
        started += 1
        max_started = max(max_started, started)
        if started == 3:
            reached_three.set()
        await release.wait()
        started -= 1
        return _process(stdout=b"ok", stderr=b"")

    monkeypatch.setattr(formalize, "GHC_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(
        formalize.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
    )

    tasks = [
        asyncio.create_task(formalize.verify_with_ghc(f"module A{i} where\n"))
        for i in range(5)
    ]
    await asyncio.wait_for(reached_three.wait(), timeout=1)
    assert max_started == 3
    release.set()
    results = await asyncio.gather(*tasks)

    assert all(ok for ok, _ in results)
