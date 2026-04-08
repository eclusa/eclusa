"""tests/test_refine_agent_integration.py — Integration tests for the Refine agent.

Requirements: PIPE-01

Tests:
- test_search_knowledge_tool_queries_db: search_knowledge returns results for a seeded entity
- test_search_schemas_tool_queries_db: search_schemas returns results for a seeded entity
- test_tool_embed_failure_returns_empty_results: embed failure returns empty-results JSON, no crash
- test_refine_agent_system_prompt_contains_philosophy: prompt has questioning philosophy phrases
- test_tool_search_failure_returns_empty_results: search fn failure returns empty-results JSON
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from harness.refine_agent import RefineContext, build_refine_agent

# asyncio_mode = auto in pytest.ini — no pytestmark needed for async functions

# Embedding dimension used by knowledge.search (1024-dim per knowledge/search.py)
_EMBED_DIM = 1024

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_entity(conn, name: str, summary: str | None = None) -> str:
    """Insert an entity row with a known 1024-dim embedding. Returns the inserted name."""
    embedding_str = "[" + ",".join(["0.1"] * _EMBED_DIM) + "]"
    await conn.execute(
        """
        INSERT INTO entity (id, name, type, summary, embedding)
        VALUES (gen_random_uuid(), $1, 'concept', $2, $3::vector)
        """,
        name,
        summary or f"Summary for {name}",
        embedding_str,
    )
    return name


def _make_refine_ctx(conn, pool=None) -> tuple[Agent, RunContext[RefineContext]]:
    """Build a Refine agent (TestModel) and a RunContext with the given conn."""
    agent = build_refine_agent(model=TestModel())
    ctx = RunContext(
        deps=RefineContext(
            conn=conn,
            actor_id="00000000-0000-0000-0000-000000000001",
            intent_id="00000000-0000-0000-0000-000000000002",
            pool=pool,
        ),
        model=TestModel(),
        usage=RunUsage(),
        agent=agent,
    )
    return agent, ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_search_knowledge_tool_queries_db(conn) -> None:
    """PIPE-01: search_knowledge tool returns at least one result for a seeded entity."""
    await _seed_entity(conn, "AuthService", summary="Handles JWT-based authentication")

    agent, ctx = _make_refine_ctx(conn)
    tool = agent._function_toolset.tools["search_knowledge"]

    # Mock _embed_query so we don't hit OpenAI — return matching 1024-dim vector
    with patch("harness.refine_agent._embed_query", return_value=[0.1] * _EMBED_DIM):
        result = await tool.function(ctx, query="AuthService")

    parsed = json.loads(result)
    assert isinstance(parsed["results"], list), "results must be a list"
    names = [r.get("name") for r in parsed["results"]]
    assert "AuthService" in names, (
        f"Expected 'AuthService' in search results, got: {names}"
    )


async def test_search_schemas_tool_queries_db(conn) -> None:
    """PIPE-01: search_schemas tool returns at least one result for a seeded entity."""
    await _seed_entity(conn, "UserSchema", summary="Pydantic model for user profile")

    agent, ctx = _make_refine_ctx(conn)
    tool = agent._function_toolset.tools["search_schemas"]

    with patch("harness.refine_agent._embed_query", return_value=[0.1] * _EMBED_DIM):
        result = await tool.function(ctx, query="UserSchema")

    parsed = json.loads(result)
    assert isinstance(parsed["results"], list), "results must be a list"
    names = [r.get("name") for r in parsed["results"]]
    assert "UserSchema" in names, (
        f"Expected 'UserSchema' in search results, got: {names}"
    )


async def test_tool_embed_failure_returns_empty_results(conn) -> None:
    """PIPE-01: when _embed_query raises, tool returns empty-results JSON — no propagated exception."""
    agent, ctx = _make_refine_ctx(conn)
    tool = agent._function_toolset.tools["search_knowledge"]

    with patch("harness.refine_agent._embed_query", side_effect=Exception("timeout")):
        result = await tool.function(ctx, query="anything")

    parsed = json.loads(result)
    assert parsed["results"] == [], f"Expected empty results, got: {parsed['results']}"
    assert "Embedding failed" in parsed["summary"], (
        f"Expected 'Embedding failed' in summary, got: {parsed['summary']!r}"
    )


def test_refine_agent_system_prompt_contains_philosophy() -> None:
    """PIPE-01: build_refine_agent() system prompt contains the questioning philosophy phrases."""
    agent = build_refine_agent(model=TestModel())
    # pydantic-ai stores static system prompts in agent._system_prompts tuple
    prompt_text = " ".join(str(p) for p in agent._system_prompts)

    assert "Start open" in prompt_text, "System prompt must contain 'Start open'"
    assert "Follow energy" in prompt_text, "System prompt must contain 'Follow energy'"
    assert "Challenge vagueness" in prompt_text, "System prompt must contain 'Challenge vagueness'"
    assert "Know when to stop" in prompt_text, "System prompt must contain 'Know when to stop'"
    assert "thinking partner" in prompt_text, "System prompt must contain 'thinking partner'"
    assert "create_scc_cascade" in prompt_text, "System prompt must reference 'create_scc_cascade'"


async def test_tool_search_failure_returns_empty_results(conn) -> None:
    """PIPE-01: when search_fn raises, tool returns empty-results JSON — no propagated exception."""
    agent, ctx = _make_refine_ctx(conn)
    tool = agent._function_toolset.tools["search_knowledge"]

    with (
        patch("harness.refine_agent._embed_query", return_value=[0.1] * _EMBED_DIM),
        patch("harness.refine_agent.hybrid_search", side_effect=Exception("DB error")),
    ):
        result = await tool.function(ctx, query="anything")

    parsed = json.loads(result)
    assert parsed["results"] == [], f"Expected empty results, got: {parsed['results']}"
    assert "Search failed" in parsed["summary"] or "search" in parsed["summary"].lower(), (
        f"Expected search failure message in summary, got: {parsed['summary']!r}"
    )
