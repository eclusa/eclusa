"""harness/formalize.py — GHC async subprocess for Haskell constraint verification.

Drafts Haskell constraints with pydantic-ai, verifies them with an async
`docker exec ghc-sidecar ghc -fno-code` subprocess, and retries with verbatim
GHC feedback up to GHC_MAX_RETRIES.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

import asyncpg
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

GHC_CONTAINER_NAME = "ghc-sidecar"
GHC_WORKSPACE = "/workspace"
GHC_TIMEOUT_SECONDS = 10
GHC_MAX_RETRIES = 5
import os as _os
DEFAULT_FORMALIZE_MODEL = _os.environ.get("SCC_MODEL_FORMALIZE", _os.environ.get("SCC_MODEL_DEFAULT", "openai:glm-5.1"))
SYSTEM_SCHEMA_VERSION = "0002"

_GHC_SEMAPHORE = asyncio.Semaphore(3)


class FormalizeError(RuntimeError):
    """Raised when GHC rejects formalized constraints after retries."""


def _stage_input(stage: dict[str, Any]) -> dict[str, Any]:
    stage_input = stage.get("input") or {}
    if isinstance(stage_input, str):
        return json.loads(stage_input)
    return stage_input


def _workspace_dir() -> str:
    """Prefer /workspace, but fall back to the local temp dir when unavailable."""
    workspace = Path(GHC_WORKSPACE)
    if workspace.exists():
        return GHC_WORKSPACE
    return tempfile.gettempdir()


def _build_prompt(stage: dict[str, Any]) -> str:
    stage_input = _stage_input(stage)
    matched_sources = stage_input.get("matched_sources", [])
    cohere_context = stage_input.get("cohere_context", "")
    ghc_feedback = stage_input.get("ghc_feedback", "")
    previous_haskell = stage_input.get("previous_haskell", "")

    parts = [
        "Translate the following SCC formalization context into valid Haskell constraints.",
        "Use only Prelude unless the prompt explicitly states otherwise.",
        "Return only Haskell source code.",
        "",
        "Matched sources:",
        json.dumps(matched_sources, indent=2),
        "",
        "Cohere analysis:",
        cohere_context,
    ]
    if ghc_feedback:
        parts.extend(
            [
                "",
                "Previous GHC feedback:",
                ghc_feedback,
            ]
        )
    if previous_haskell:
        parts.extend(
            [
                "",
                "Previous Haskell:",
                previous_haskell,
            ]
        )
    return "\n".join(parts).strip()


async def draft_constraints(conn: asyncpg.Connection, stage: dict[str, Any]) -> str:
    """Use pydantic-ai to draft Haskell constraints from the formalize stage."""
    del conn
    model = (
        stage.get("model")
        or _stage_input(stage).get("model")
        or DEFAULT_FORMALIZE_MODEL
    )
    agent = Agent(
        model,
        system_prompt=(
            "You are a Haskell type system expert. Translate business constraints "
            "into valid Haskell declarations and type-level constraints. Output only "
            "plain Haskell source code with no markdown."
        ),
    )
    prompt = _build_prompt(stage)
    result = await agent.run(prompt)
    return str(result.output).strip()


async def verify_with_ghc(haskell_source: str) -> tuple[bool, str]:
    """Write Haskell to a workspace tempfile and type-check it with GHC.

    The subprocess is launched with asyncio.create_subprocess_exec so the event
    loop stays unblocked. Output combines stdout and stderr verbatim, then
    normalizes the tempfile path to `constraints.hs` for retry prompts.
    """
    async with _GHC_SEMAPHORE:
        fd, local_path = tempfile.mkstemp(
            suffix=".hs",
            prefix="constraints_",
            dir=_workspace_dir(),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(haskell_source)

            proc = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                GHC_CONTAINER_NAME,
                "ghc",
                "-fno-code",
                local_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=GHC_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                with suppress(Exception):
                    proc.kill()
                return False, "GHC compilation timed out"

            output = (stdout + stderr).decode("utf-8", errors="replace")
            output = output.replace(local_path, "constraints.hs")
            output = output.replace(os.path.basename(local_path), "constraints.hs")
            return proc.returncode == 0, output
        finally:
            with suppress(FileNotFoundError):
                Path(local_path).unlink()


async def _persist_success(
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str,
    haskell_source: str,
    ghc_output: str,
) -> None:
    stage_id = stage["id"]
    cascade_id = stage["cascade_id"]
    cascade_row = await conn.fetchrow(
        "SELECT intent_id FROM cascade WHERE id = $1::uuid",
        cascade_id,
    )
    intent_id = (
        str(cascade_row["intent_id"])
        if cascade_row
        else str(stage.get("intent_id") or _stage_input(stage).get("intent_id") or "")
    )

    async with conn.transaction():
        if intent_id:
            await conn.execute(
                """
                INSERT INTO artifact (
                    id, intent_id, cascade_id, stage_id, type, payload
                )
                VALUES (
                    gen_random_uuid(),
                    $1::uuid,
                    $2::uuid,
                    $3::uuid,
                    'file_created',
                    jsonb_build_object(
                        'content', $4::text,
                        'filename', 'constraints.hs',
                        'ghc_output', $5::text
                    )
                )
                """,
                intent_id,
                cascade_id,
                stage_id,
                haskell_source,
                ghc_output,
            )

        await conn.execute(
            """
            UPDATE stage
            SET output = $1::jsonb,
                state = 'resolved',
                resolved_at = NOW(),
                resolved_by = $2::uuid
            WHERE id = $3::uuid
            """,
            json.dumps({"haskell_source": haskell_source, "ghc_output": ghc_output}),
            actor_id,
            stage_id,
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'stage_state_changed',
                   jsonb_build_object(
                       'old_state', 'active',
                       'new_state', 'resolved',
                       'scc_stage', 'formalize'
                   ),
                   $2
            FROM stage s
            WHERE s.id = $3::uuid
            """,
            actor_id,
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )


async def _persist_failure(
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str,
    reason: str,
) -> None:
    stage_id = stage["id"]
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE stage
            SET state = 'failed',
                resolved_at = NOW(),
                resolved_by = $1::uuid
            WHERE id = $2::uuid
            """,
            actor_id,
            stage_id,
        )
        await conn.execute(
            """
            INSERT INTO ledger_entry (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'stage_state_changed',
                   jsonb_build_object(
                       'old_state', 'active',
                       'new_state', 'failed',
                       'reason', $2::text,
                       'scc_stage', 'formalize'
                   ),
                   $3
            FROM stage s
            WHERE s.id = $4::uuid
            """,
            actor_id,
            reason[:500],
            SYSTEM_SCHEMA_VERSION,
            stage_id,
        )


async def handle_formalize(
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str | None = None,
) -> tuple[bool, str, str]:
    """Drive draft -> verify retries and persist the resolved or failed state."""
    working_stage = dict(stage)
    last_output = ""

    for attempt in range(GHC_MAX_RETRIES):
        haskell_source = await draft_constraints(conn, working_stage)
        success, ghc_output = await verify_with_ghc(haskell_source)
        last_output = ghc_output
        if success:
            if conn is not None and actor_id:
                await _persist_success(
                    conn, stage, actor_id, haskell_source, ghc_output
                )
            return True, haskell_source, ghc_output

        if attempt >= GHC_MAX_RETRIES - 1:
            break

        next_stage_input = dict(_stage_input(stage))
        next_stage_input["ghc_feedback"] = ghc_output
        next_stage_input["previous_haskell"] = haskell_source
        working_stage = dict(stage)
        working_stage["input"] = next_stage_input

    if conn is not None and actor_id:
        await _persist_failure(
            conn,
            stage,
            actor_id,
            f"GHC rejected constraints after {GHC_MAX_RETRIES} attempts.\n{last_output}",
        )
    raise FormalizeError(
        f"GHC rejected constraints after {GHC_MAX_RETRIES} attempts.\n{last_output}"
    )
