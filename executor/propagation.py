"""executor/propagation.py — upstream output injection before stage dispatch (PROP-01, PROP-02).

inject_upstream_context(conn, stage):
  1. Walk the full ancestor graph via recursive CTE on depends_on[]
  2. Collect output JSONB from all resolved ancestors (NULL outputs skipped)
  3. Apply key-mapping rules to translate output keys into the keys handlers expect
  4. Merge all mapped keys into stage.input (existing keys preserved, ancestors fill gaps)
  5. UPDATE stage SET input = merged_input WHERE id = stage_id
  6. Return the updated stage dict (with input mutated in place for the caller's copy)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Key mapping: ancestor scc_stage -> dict of {output_key -> injected_key}
# Special entries use "__self__" to inject the entire output under a key.
_KEY_MAP: dict[str, dict[str, str]] = {
    "refine": {"scope_doc": "query_text"},
    "match": {"__self__": "matched_sources"},
    "cohere": {"__self__": "cohere_output"},
    "formalize": {
        "haskell_source": "haskell_source",
        "__self__": "formalize_output",
    },
    "derive": {
        "test_suite": "test_suite",
        "derived_tests": "derived_tests",
    },
    "generate": {
        "generated_code": "generated_code",
        "workspace_dir": "workspace_dir",
    },
}

_ANCESTOR_CTE = """
WITH RECURSIVE ancestors AS (
  SELECT id, depends_on, input, output
  FROM stage
  WHERE id = ANY($1::uuid[])
  UNION ALL
  SELECT s.id, s.depends_on, s.input, s.output
  FROM stage s
  JOIN ancestors a ON s.id = ANY(a.depends_on)
)
SELECT id, input, output FROM ancestors WHERE output IS NOT NULL
"""


def _parse_jsonb(value: Any) -> dict | list | None:
    """Parse a JSONB value that may come as a string from asyncpg."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _extract_scc_stage(stage_input: Any) -> str | None:
    """Extract the scc_stage routing key from a stage's input."""
    parsed = _parse_jsonb(stage_input)
    if isinstance(parsed, dict):
        return parsed.get("scc_stage")
    return None


def _apply_key_mapping(scc_stage: str, output: Any) -> dict[str, Any]:
    """Apply key mapping rules for a given ancestor stage's output."""
    mapping = _KEY_MAP.get(scc_stage, {})
    if not mapping:
        return {}

    parsed_output = _parse_jsonb(output)
    if parsed_output is None:
        return {}

    result: dict[str, Any] = {}

    for output_key, inject_key in mapping.items():
        if output_key == "__self__":
            result[inject_key] = parsed_output
        elif isinstance(parsed_output, dict) and output_key in parsed_output:
            result[inject_key] = parsed_output[output_key]

    return result


async def inject_upstream_context(
    conn: asyncpg.Connection, stage: dict
) -> dict:
    """Inject all ancestor outputs into stage.input before dispatch.

    Walks the full dependency graph (not just direct parent) via recursive CTE.
    Applies SCC key mapping so downstream handlers find the keys they expect.
    Updates both the DB and the in-memory stage dict.

    Returns the (mutated) stage dict.
    """
    depends_on = stage.get("depends_on") or []
    if not depends_on:
        return stage

    # Convert depends_on to list of strings for the query
    parent_ids = [str(d) for d in depends_on]

    rows = await conn.fetch(_ANCESTOR_CTE, parent_ids)
    if not rows:
        return stage

    # Parse current input
    current_input = _parse_jsonb(stage.get("input")) or {}
    if not isinstance(current_input, dict):
        current_input = {}

    # Collect mapped keys from all ancestors
    injected: dict[str, Any] = {}
    for row in rows:
        ancestor_scc_stage = _extract_scc_stage(row["input"])
        if ancestor_scc_stage:
            mapped = _apply_key_mapping(ancestor_scc_stage, row["output"])
            for key, value in mapped.items():
                # Don't overwrite keys that already exist
                if key not in injected:
                    injected[key] = value

    if not injected:
        return stage

    # Merge: existing keys take priority (set at cascade creation)
    merged = {**injected, **current_input}

    # Update DB
    await conn.execute(
        "UPDATE stage SET input = $1::jsonb WHERE id = $2::uuid",
        json.dumps(merged, default=str),
        str(stage["id"]),
    )

    # Mutate in-memory dict
    stage["input"] = merged

    logger.debug(
        "Injected %d upstream keys into stage %s: %s",
        len(injected),
        stage["id"],
        list(injected.keys()),
    )

    return stage
