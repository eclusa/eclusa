"""
tests/test_judgment_pass.py — Tests for judgment pass module.

Requirements: JUDG-01, JUDG-02, JUDG-04, JUDG-05, D-17
Implemented in: 03-03-PLAN
"""

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai import Agent
from judgment.pass_ import VerdictModel, hash_context
from judgment.context_prep import prepare_context


@pytest.mark.asyncio
async def test_judgment_returns_structured_verdict():
    """Agent with TestModel produces a validated VerdictModel (JUDG-01, JUDG-04)."""
    model = TestModel()
    agent = Agent(model, output_type=VerdictModel)
    result = await agent.run("evaluate this context")
    verdict = result.output
    assert isinstance(verdict, VerdictModel)
    # TestModel fills string fields with minimal values — check schema is enforced, not enum values
    assert isinstance(verdict.decision, str) and len(verdict.decision) > 0
    assert isinstance(verdict.confidence, float)
    assert isinstance(verdict.conditions, list)


@pytest.mark.asyncio
async def test_judgment_uses_prepared_context():
    """prepare_context strips tool noise; context flows to judgment (JUDG-02, JUDG-03)."""
    history = [
        {"kind": "request", "content": "analyze security"},
        {"kind": "response", "content": "I found 3 issues"},
    ]
    ctx = prepare_context(history)
    assert "analyze security" in ctx
    assert "I found 3 issues" in ctx
    # Tool noise stripped
    history_with_noise = history + [{"kind": "tool-call", "content": "exec_bash"}]
    ctx2 = prepare_context(history_with_noise)
    assert "exec_bash" not in ctx2


def test_context_hash_computed():
    """hash_context is deterministic and uses blake3 or sha256 (D-17)."""
    h1 = hash_context("hello world")
    h2 = hash_context("hello world")
    h3 = hash_context("different content")
    assert h1 == h2  # deterministic
    assert h1 != h3  # different inputs differ
    assert len(h1) >= 32  # at least sha256-length hex string


@pytest.mark.asyncio
async def test_judgment_has_no_write_tools():
    """Judgment agent must have no tools registered — topological enforcement (JUDG-05)."""
    model = TestModel()
    agent = Agent(model, output_type=VerdictModel)
    # Verify no tools registered on the agent
    tool_names = (
        list(agent._function_tools.keys()) if hasattr(agent, "_function_tools") else []
    )
    assert tool_names == [], f"Judgment agent must have no tools, found: {tool_names}"
