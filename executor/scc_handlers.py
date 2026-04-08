"""SCC stage handlers for narrowing dispatch.

Implements the first three SCC stages used by phase 07-02:
- refine: open a native work session and distill noisy intent into a scope doc
- match: query schema commons and persist ranked matches
- cohere: run a judgment pass over matched sources and persist the verdict

The remaining SCC stage entry points are present as compatibility shims so the
router can import and branch on all expected `scc_stage` values.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from pydantic_ai import Agent

from harness.native import complete_work_session, run_session_turn, start_work_session
from judgment.pass_ import create_judgment_pass_record, hash_context, run_judgment_pass
from fan_out.db import run_fan_out_with_db
from knowledge.search import search_schema_commons
from schema_commons.embed import embed_texts

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"
WORKSPACES_DIR = os.environ.get("ECLUSA_WORKSPACES_DIR", "./workspaces")
_SCC_MODEL_FALLBACK = "openai:glm-5.1"

# Per-stage env var names. Fallback chain: stage-specific -> default -> hardcoded fallback.
_STAGE_MODEL_ENV: dict[str, str] = {
    "refine": "SCC_MODEL_REFINE",
    "fanout": "SCC_MODEL_FANOUT",
    "match": "SCC_MODEL_MATCH",
    "cohere": "SCC_MODEL_COHERE",
    "formalize": "SCC_MODEL_FORMALIZE",
    "derive": "SCC_MODEL_DERIVE",
    "generate": "SCC_MODEL_GENERATE",
}


def _resolve_model(stage_name: str) -> str:
    """Return model identifier for a stage.

    Resolution order:
    1. SCC_MODEL_{STAGE} env var (e.g. SCC_MODEL_REFINE)
    2. SCC_MODEL_DEFAULT env var
    3. _SCC_MODEL_FALLBACK constant
    """

    default = os.environ.get("SCC_MODEL_DEFAULT", _SCC_MODEL_FALLBACK)
    stage_env = _STAGE_MODEL_ENV.get(stage_name)
    if stage_env:
        return os.environ.get(stage_env, default)
    return default


def _normalize_stage_input(stage: dict) -> dict[str, Any]:
    stage_input = stage.get("input") or {}
    if isinstance(stage_input, str):
        return json.loads(stage_input)
    return dict(stage_input)


def _stage_input_value(
    stage_input: dict[str, Any], *keys: str, default: Any = None
) -> Any:
    for key in keys:
        value = stage_input.get(key)
        if value is not None and value != "":
            return value
    return default


def _json_or_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _jsonb_dumps(value: Any) -> str:
    """Serialize Python data into an asyncpg-safe JSONB payload."""
    return json.dumps(value, default=str)


def _session_output_to_text(output: Any) -> str:
    if hasattr(output, "model_dump"):
        output = output.model_dump()
    if isinstance(output, (dict, list)):
        return json.dumps(output, default=str)
    return str(output)


def _normalize_model_list(models: Any) -> list[str]:
    if isinstance(models, str):
        return [models]
    if models is None:
        return [_resolve_model("fanout")]
    return list(models)


async def _resolve_stage_immediately(
    conn: asyncpg.Connection,
    stage: dict,
    actor_id: str,
    *,
    note: str,
    output_payload: Any | None = None,
) -> None:
    async with conn.transaction():
        if output_payload is not None:
            await conn.execute(
                """
                UPDATE stage
                SET output = $1::jsonb
                WHERE id = $2::uuid
                """,
                _jsonb_dumps(output_payload),
                stage["id"],
            )

        await conn.execute(
            """
            UPDATE stage
            SET state = 'resolved', resolved_at = NOW(), resolved_by = $1::uuid
            WHERE id = $2::uuid
            """,
            actor_id,
            stage["id"],
        )

        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'stage_state_changed',
                   jsonb_build_object(
                       'old_state', 'active',
                       'new_state', 'resolved',
                       'note', $2::text
                   ),
                   $3
            FROM stage s WHERE s.id = $4::uuid
            """,
            actor_id,
            note,
            SYSTEM_SCHEMA_VERSION,
            stage["id"],
        )


async def dispatch_scc_refine(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    stage_input = _normalize_stage_input(stage)
    raw_intent = _stage_input_value(
        stage_input,
        "raw_intent",
        "intent",
        default="Refine this intent into a scope document.",
    )

    intent_row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid",
        stage["cascade_id"],
    )
    if intent_row is None:
        raise ValueError(f"No cascade found for stage {stage['id']}")

    session_id = await start_work_session(
        conn=conn,
        stage_id=str(stage["id"]),
        intent_id=str(intent_row["intent_id"]),
        cascade_id=str(stage["cascade_id"]),
        model=_resolve_model("refine"),
        actor_id=actor_id,
    )

    agent = Agent(
        _resolve_model("refine"),
        system_prompt=(
            "You are a requirements analyst. Narrow the user's noisy intent into "
            "a structured scope document with: goals, non-goals, constraints, open questions."
        ),
    )
    scope_doc, _messages = await run_session_turn(
        conn=conn,
        session_id=session_id,
        agent=agent,
        user_message=raw_intent,
    )

    await complete_work_session(conn, session_id, actor_id)

    scope_doc_payload = (
        scope_doc.model_dump() if hasattr(scope_doc, "model_dump") else scope_doc
    )
    await _resolve_stage_immediately(
        conn,
        stage,
        actor_id,
        note="scc_refine",
        output_payload={"scope_doc": scope_doc_payload, "session_id": session_id},
    )


async def dispatch_scc_match(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    stage_input = _normalize_stage_input(stage)
    query_text = _stage_input_value(stage_input, "query_text", "query", default="")

    if query_text:
        try:
            async with httpx.AsyncClient(verify=False) as client:
                query_embeddings = await embed_texts([query_text], client)
            query_embedding = query_embeddings[0] if query_embeddings else []
            results = await search_schema_commons(
                query_text, query_embedding, conn, limit=10
            )
        except Exception:
            logger.warning("Match stage embedding/search failed — resolving with empty results")
            results = []
    else:
        results = []

    results_payload = [result.model_dump() for result in results]
    await _resolve_stage_immediately(
        conn,
        stage,
        actor_id,
        note="scc_match",
        output_payload=results_payload,
    )


async def dispatch_scc_cohere(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    stage_input = _normalize_stage_input(stage)
    matched_sources = _stage_input_value(
        stage_input, "matched_sources", "sources", default=[]
    )
    cohere_model = _resolve_model("cohere")
    prompt = (
        "Identify composition issues: type boundary conflicts, auth model mismatches, "
        "data friction points between these matched sources."
    )
    prepared_context = (
        f"Matched schema sources:\n{json.dumps(matched_sources, indent=2)}"
    )
    context_hash = hash_context(prepared_context)

    verdict = await run_judgment_pass(
        model=cohere_model,
        prepared_context=prepared_context,
        prompt=prompt,
    )

    await create_judgment_pass_record(
        conn=conn,
        stage_id=str(stage["id"]),
        model=cohere_model,
        context_ref=f"inline:{context_hash}",
        context_hash=context_hash,
        prompt=prompt,
        verdict=verdict,
        actor_id=actor_id,
    )

    verdict_payload = (
        verdict.model_dump() if hasattr(verdict, "model_dump") else verdict
    )
    await _resolve_stage_immediately(
        conn,
        stage,
        actor_id,
        note="scc_cohere",
        output_payload=verdict_payload,
    )


async def dispatch_scc_fanout(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    await handle_intent_validation_fanout(conn, stage, actor_id)


async def dispatch_scc_formalize(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    from harness.formalize import handle_formalize, FormalizeError
    try:
        await handle_formalize(conn, stage, actor_id=actor_id)
    except (FormalizeError, FileNotFoundError, OSError) as exc:
        logger.warning("Formalize stage %s failed: %s — resolving with skip note", stage["id"], exc)
        await _resolve_stage_immediately(
            conn, stage, actor_id,
            note="scc_formalize_skipped",
            output_payload={"skipped": True, "reason": str(exc)},
        )


async def dispatch_scc_derive(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    await handle_derive(conn, stage, actor_id)


async def dispatch_scc_generate(
    conn: asyncpg.Connection, stage: dict, actor_id: str
) -> None:
    await handle_generate(conn, stage, actor_id)


async def handle_intent_validation_fanout(
    conn: asyncpg.Connection,
    stage: dict,
    actor_id: str,
) -> None:
    stage_input = _normalize_stage_input(stage)

    # Build-mode v2 path: scope_doc embedded directly in stage input (create_scc_cascade_from_refine)
    scope_doc = stage_input.get("scope_doc")
    if scope_doc:
        scope_doc = str(scope_doc)
    else:
        # Legacy v1 path: fetch scope_doc from the upstream refine stage's output
        refine_stage_id = stage_input.get("refine_stage_id")
        if not refine_stage_id:
            logger.error(
                "Fan-out stage %s has neither scope_doc nor refine_stage_id",
                stage["id"],
            )
            return

        refine_row = await conn.fetchrow(
            """
            SELECT output
            FROM stage
            WHERE id = $1::uuid
            """,
            refine_stage_id,
        )
        refine_output = _json_or_value(refine_row["output"]) if refine_row else {}
        if isinstance(refine_output, dict):
            scope_doc = str(refine_output.get("scope_doc") or "")
        else:
            scope_doc = str(refine_output or "")

    raw_intent = _stage_input_value(stage_input, "raw_intent", "intent", default=None)
    if not raw_intent:
        intent_row = await conn.fetchrow(
            """
            SELECT i.raw
            FROM intent i
            JOIN cascade c ON c.intent_id = i.id
            WHERE c.id = $1::uuid
            """,
            stage["cascade_id"],
        )
        raw_intent = (
            str(intent_row["raw"])
            if intent_row and intent_row["raw"] is not None
            else ""
        )

    prepared_context = (
        f"Original intent:\n{raw_intent}\n\nRefined scope doc:\n{scope_doc}"
    )
    context_hash = hash_context(prepared_context)
    models = _normalize_model_list(stage_input.get("fanout_models"))
    prompt = (
        "Does the refined scope doc faithfully represent the original intent? "
        "List any missed requirements."
    )

    await run_fan_out_with_db(
        conn=conn,
        stage_id=str(stage["id"]),
        models=models,
        prepared_context=prepared_context,
        prompt=prompt,
        context_hash=context_hash,
        actor_id=actor_id,
    )


async def handle_derive(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    """Derive stage: workspace-equipped agent writes test files and validates them."""
    from harness.workspace_tools import build_derive_agent, WorkspaceContext
    import time

    stage_input = _normalize_stage_input(stage)
    derive_model = _resolve_model("derive")
    cascade_id = str(stage["cascade_id"])

    workspace_dir = str(Path(WORKSPACES_DIR) / cascade_id)
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    intent_row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid",
        stage["cascade_id"],
    )
    if intent_row is None:
        raise ValueError(f"No cascade found for stage {stage['id']}")

    # Fetch the original intent text for context
    intent_raw = await conn.fetchval(
        "SELECT raw FROM intent WHERE id = $1::uuid",
        intent_row["intent_id"],
    )

    session_id = await start_work_session(
        conn=conn,
        stage_id=str(stage["id"]),
        intent_id=str(intent_row["intent_id"]),
        cascade_id=cascade_id,
        model=derive_model,
        actor_id=actor_id,
    )

    upstream = {
        "scope_doc": _stage_input_value(stage_input, "query_text", "scope_doc", default=""),
        "haskell_source": _stage_input_value(stage_input, "haskell_source", default=""),
        "cohere_output": _json_or_value(
            _stage_input_value(stage_input, "cohere_output", default={}) or {}
        ),
        "matched_sources": _stage_input_value(stage_input, "matched_sources", default=[]),
        "original_intent": str(intent_raw or ""),
    }

    workspace_ctx = WorkspaceContext(
        workspace_dir=workspace_dir,
        cascade_id=cascade_id,
        stage_name="derive",
        upstream_context=upstream,
    )

    agent = build_derive_agent(derive_model)

    user_message = (
        f"## Original Intent\n{upstream['original_intent']}\n\n"
        f"## Scope Document\n{upstream['scope_doc']}\n\n"
        f"## Constraints\n{upstream['haskell_source']}\n\n"
        f"## Matched Sources\n{json.dumps(upstream['matched_sources'], indent=2, default=str)}\n\n"
        "Write test files to the workspace and verify they collect cleanly."
    )

    t0 = time.monotonic()
    result = await agent.run(user_message, deps=workspace_ctx)
    wall_time_ms = int((time.monotonic() - t0) * 1000)

    # Persist cost to work session
    usage = result.usage()
    cost = {
        "tokens_in": usage.request_tokens or 0,
        "tokens_out": usage.response_tokens or 0,
        "api_calls": 1,
        "wall_time_ms": wall_time_ms,
    }
    await conn.execute(
        "UPDATE work_session SET cost = $1::jsonb WHERE id = $2::uuid",
        json.dumps(cost),
        session_id,
    )
    await complete_work_session(conn, session_id, actor_id)

    await _resolve_stage_immediately(
        conn, stage, actor_id,
        note="scc_derive",
        output_payload={
            "workspace_dir": workspace_dir,
            "session_id": session_id,
            "summary": str(result.output),
        },
    )


async def handle_generate(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    """Generate stage: workspace-equipped agent writes code, runs tests, iterates."""
    from harness.workspace_tools import build_generate_agent, WorkspaceContext
    import time

    stage_input = _normalize_stage_input(stage)
    generate_model = _resolve_model("generate")
    cascade_id = str(stage["cascade_id"])

    workspace_dir = str(Path(WORKSPACES_DIR) / cascade_id)
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    intent_row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid",
        stage["cascade_id"],
    )
    if intent_row is None:
        raise ValueError(f"No cascade found for stage {stage['id']}")

    intent_raw = await conn.fetchval(
        "SELECT raw FROM intent WHERE id = $1::uuid",
        intent_row["intent_id"],
    )

    session_id = await start_work_session(
        conn=conn,
        stage_id=str(stage["id"]),
        intent_id=str(intent_row["intent_id"]),
        cascade_id=cascade_id,
        model=generate_model,
        actor_id=actor_id,
    )

    upstream = {
        "scope_doc": _stage_input_value(stage_input, "query_text", "scope_doc", default=""),
        "haskell_source": _stage_input_value(stage_input, "haskell_source", default=""),
        "matched_sources": _stage_input_value(stage_input, "matched_sources", default=[]),
        "original_intent": str(intent_raw or ""),
    }

    workspace_ctx = WorkspaceContext(
        workspace_dir=workspace_dir,
        cascade_id=cascade_id,
        stage_name="generate",
        upstream_context=upstream,
    )

    agent = build_generate_agent(generate_model)

    user_message = (
        f"## Original Intent\n{upstream['original_intent']}\n\n"
        f"## Scope Document\n{upstream['scope_doc']}\n\n"
        "The test files from the derive stage should already be in the workspace. "
        "List files to see them. Write implementation code that satisfies the intent "
        "and passes any existing tests. Install dependencies. Run and verify everything works. "
        "If building a web app, make sure it can be started and serves content.\n\n"
        "Build the application described in the original intent."
    )

    t0 = time.monotonic()
    result = await agent.run(user_message, deps=workspace_ctx)
    wall_time_ms = int((time.monotonic() - t0) * 1000)

    usage = result.usage()
    cost = {
        "tokens_in": usage.request_tokens or 0,
        "tokens_out": usage.response_tokens or 0,
        "api_calls": 1,
        "wall_time_ms": wall_time_ms,
    }
    await conn.execute(
        "UPDATE work_session SET cost = $1::jsonb WHERE id = $2::uuid",
        json.dumps(cost),
        session_id,
    )
    await complete_work_session(conn, session_id, actor_id)

    await _resolve_stage_immediately(
        conn, stage, actor_id,
        note="scc_generate",
        output_payload={
            "workspace_dir": workspace_dir,
            "session_id": session_id,
            "summary": str(result.output),
        },
    )


async def handle_refine(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    await dispatch_scc_refine(conn, stage, actor_id)


async def handle_match(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    await dispatch_scc_match(conn, stage, actor_id)


async def handle_cohere(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    await dispatch_scc_cohere(conn, stage, actor_id)
