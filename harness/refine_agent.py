"""harness/refine_agent.py — Refine conversation agent with search and cascade tools."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import asyncpg
import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from adapters.web.chat_bridge import DEFAULT_CHAT_MODEL
from knowledge.search import hybrid_search, search_schema_commons
from schema_commons.embed import embed_texts

logger = logging.getLogger(__name__)


def _resolve_model(stage_name: str) -> str:
    default = os.environ.get("SCC_MODEL_DEFAULT", DEFAULT_CHAT_MODEL)
    stage_env = {"refine": "SCC_MODEL_REFINE"}.get(stage_name)
    if stage_env:
        return os.environ.get(stage_env, default)
    return default


DEFAULT_REFINE_MODEL = _resolve_model("refine")


@dataclass
class RefineContext:
    conn: asyncpg.Connection | None  # None when streaming (AUTH-03); tools use pool instead
    actor_id: str
    intent_id: str
    pool: asyncpg.Pool | None = None  # For tool calls during streaming


class RefineToolResult(BaseModel):
    tool: str
    results: list[dict[str, Any]]
    summary: str


def _format_results(tool: str, results: list[dict[str, Any]], summary: str) -> str:
    payload = RefineToolResult(tool=tool, results=results, summary=summary)
    return payload.model_dump_json(indent=2)


def _scope_title(scope_doc: str) -> str:
    lines = [line.strip() for line in scope_doc.splitlines() if line.strip()]
    if lines:
        return lines[0][:120]
    compact = " ".join(scope_doc.split())
    return compact[:120] or "Build scope"


async def _embed_query(query: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        embeddings = await embed_texts([query], client)
    return embeddings[0] if embeddings else []


async def _search_tool(
    *,
    tool: str,
    query: str,
    conn: asyncpg.Connection,
    search_fn: Callable[[str, list[float], asyncpg.Connection, int], Any],
    summary_prefix: str,
) -> str:
    if not query.strip():
        return _format_results(tool, [], f"No query provided for {summary_prefix}.")

    try:
        query_embedding = await _embed_query(query)
    except Exception as exc:  # pragma: no cover - embedding API failure path
        logger.warning("%s embedding failed for query %r: %s", tool, query, exc)
        return _format_results(tool, [], f"Embedding failed for {summary_prefix}.")

    try:
        results = await search_fn(query, query_embedding, conn, 8)
    except Exception as exc:  # pragma: no cover - search failure path
        logger.exception("%s search failed for query %r", tool, query)
        return _format_results(tool, [], f"Search failed for {summary_prefix}: {exc}")

    payload = [result.model_dump() for result in results]
    return _format_results(tool, payload, f"Found {len(payload)} {summary_prefix}.")


async def _create_scc_cascade_from_refine(
    conn: asyncpg.Connection,
    scope_doc: str,
    actor_id: str,
    intent_id: str,
) -> str:
    cascade_id = str(uuid.uuid4())
    stage_ids = [str(uuid.uuid4()) for _ in range(6)]
    title = _scope_title(scope_doc)
    scope_doc_text = scope_doc.strip()

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO cascade (id, intent_id, shape, narrative, state)
            VALUES ($1::uuid, $2::uuid, $3::jsonb, $4, 'active')
            """,
            cascade_id,
            intent_id,
            json.dumps({"mode": "build", "title": title}),
            scope_doc_text or title,
        )

        async def insert_stage(
            stage_id: str,
            depends_on: list[str],
            payload: dict[str, Any],
        ) -> None:
            if depends_on:
                await conn.execute(
                    """
                    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
                    VALUES (
                        $1::uuid,
                        $2::uuid,
                        'narrowing',
                        'pending',
                        ARRAY[$3::uuid],
                        $4::jsonb
                    )
                    """,
                    stage_id,
                    cascade_id,
                    depends_on[0],
                    json.dumps(payload),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
                    VALUES (
                        $1::uuid,
                        $2::uuid,
                        'narrowing',
                        'pending',
                        '{}'::uuid[],
                        $3::jsonb
                    )
                    """,
                    stage_id,
                    cascade_id,
                    json.dumps(payload),
                )

        fanout_id, match_id, cohere_id, formalize_id, derive_id, generate_id = stage_ids
        await insert_stage(
            fanout_id,
            [],
            {
                "scc_stage": "intent_validation_fanout",
                "scope_doc": scope_doc_text,
            },
        )
        await insert_stage(match_id, [fanout_id], {"scc_stage": "match"})
        await insert_stage(cohere_id, [match_id], {"scc_stage": "cohere"})
        await insert_stage(formalize_id, [cohere_id], {"scc_stage": "formalize"})
        await insert_stage(derive_id, [formalize_id], {"scc_stage": "derive"})
        await insert_stage(generate_id, [derive_id], {"scc_stage": "generate"})

    logger.debug(
        "Created refine-derived SCC cascade: %s (intent=%s actor=%s)",
        cascade_id,
        intent_id,
        actor_id,
    )
    return cascade_id


def build_refine_agent(model: str | None = None) -> Agent[RefineContext, str]:
    agent = Agent(
        model or DEFAULT_REFINE_MODEL,
        system_prompt=(
            "You are a thinking partner, not an interviewer. The operator has a fuzzy idea — "
            "your job is to help them sharpen it. Ask questions that make them think "
            "'I hadn't considered that' or 'yes, that's exactly what I mean.'\n\n"
            "How to question:\n"
            "- Start open: let them dump their mental model first. Don't interrupt with structure.\n"
            "- Follow energy: dig into what they emphasized or what excited them.\n"
            "- Challenge vagueness: never accept fuzzy answers. 'Good' means what? "
            "'Users' means who? 'Simple' means how?\n"
            "- Make the abstract concrete: 'walk me through using this,' "
            "'what does that actually look like?'\n"
            "- Clarify ambiguity: 'when you say Z, do you mean A or B?'\n"
            "- Know when to stop: when you understand what they want, why they want it, "
            "who it's for, and what done looks like — propose creating the cascade.\n\n"
            "When to call create_scc_cascade:\n"
            "Only after you have: what they're building (concrete), why it needs to exist, "
            "who it's for, and what done looks like. Do not create the cascade prematurely — "
            "a vague scope doc forces every downstream stage to guess, compounding cost.\n"
            "Before creating, confirm: 'I think I have what I need. Here's my understanding: "
            "[summary]. Shall I create the cascade?'\n\n"
            "Tools:\n"
            "- Use search_knowledge to look up relevant organizational context and past decisions. "
            "Search proactively when the operator mentions a domain concept.\n"
            "- Use search_schemas to find typed API specs and type definitions that might match "
            "what they're building.\n\n"
            "Anti-patterns to avoid: checklist walking, canned questions, corporate speak, "
            "firing questions without building on answers, accepting vague answers without probing."
        ),
        deps_type=RefineContext,
    )

    async def _get_conn(ctx: RunContext[RefineContext]):
        """Get a DB connection — from deps.conn if available, or acquire from pool."""
        if ctx.deps.conn is not None:
            return ctx.deps.conn
        if ctx.deps.pool is not None:
            return await ctx.deps.pool.acquire()
        raise RuntimeError("RefineContext has no conn or pool — cannot access DB")

    async def _release_conn(ctx: RunContext[RefineContext], conn):
        """Release connection back to pool if it was acquired (not from deps.conn)."""
        if ctx.deps.conn is None and ctx.deps.pool is not None:
            await ctx.deps.pool.release(conn)

    @agent.tool
    async def search_knowledge(ctx: RunContext[RefineContext], query: str) -> str:
        """Search the organizational knowledge graph for relevant context."""
        conn = await _get_conn(ctx)
        try:
            return await _search_tool(
                tool="search_knowledge",
                query=query,
                conn=conn,
                search_fn=hybrid_search,
                summary_prefix="knowledge graph entities",
            )
        finally:
            await _release_conn(ctx, conn)

    @agent.tool
    async def search_schemas(ctx: RunContext[RefineContext], query: str) -> str:
        """Search the schema commons for matching API specs and type definitions."""
        conn = await _get_conn(ctx)
        try:
            return await _search_tool(
                tool="search_schemas",
                query=query,
                conn=conn,
                search_fn=search_schema_commons,
                summary_prefix="schema commons matches",
            )
        finally:
            await _release_conn(ctx, conn)

    @agent.tool
    async def create_scc_cascade(ctx: RunContext[RefineContext], scope_doc: str) -> str:
        """Call this when you have enough context and the scope is clear. Provide a complete scope document. Returns the cascade ID."""
        conn = await _get_conn(ctx)
        try:
            try:
                from executor.scc import create_scc_cascade_from_refine as factory
            except ImportError:
                factory = None

            if factory is not None:
                return await factory(
                    ctx.deps.intent_id, ctx.deps.actor_id, conn, scope_doc=scope_doc
                )

            return await _create_scc_cascade_from_refine(
                conn, scope_doc, ctx.deps.actor_id, ctx.deps.intent_id,
            )
        finally:
            await _release_conn(ctx, conn)

    return agent

