"""
judgment/pass_.py — Single pydantic-ai completion with structured output.

VerdictModel: JSON-schema-validated verdict (JUDG-04).
hash_context: blake3 with sha256 fallback (D-17).
run_judgment_pass: single API call, no tools (JUDG-01, JUDG-05).
create_judgment_pass_record: DB write with ledger entry (JUDG-01, JUDG-02).
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg
from pydantic import BaseModel
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context hashing — blake3 with sha256 fallback (D-17)
# ---------------------------------------------------------------------------

try:
    import blake3 as _blake3

    def hash_context(content: str) -> str:
        """Return a hex digest of content using blake3."""
        return _blake3.blake3(content.encode()).hexdigest()

except ImportError:
    import hashlib

    def hash_context(content: str) -> str:  # type: ignore[misc]
        """Return a hex digest of content using sha256 (blake3 not installed)."""
        return hashlib.sha256(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Structured verdict model (JUDG-04, JUDG-15)
# ---------------------------------------------------------------------------


class VerdictModel(BaseModel):
    """Structured verdict returned by a judgment pass.

    decision: "approve" | "reject" | "needs_clarification"
    confidence: 0.0–1.0
    rationale: plain text explanation
    conditions: list of conditions or caveats (may be empty)
    """

    decision: str
    confidence: float
    rationale: str
    conditions: list[str]


# ---------------------------------------------------------------------------
# Judgment pass execution (JUDG-01, JUDG-05)
# ---------------------------------------------------------------------------


async def run_judgment_pass(
    model: str,
    prepared_context: str,
    prompt: str,
) -> VerdictModel:
    """Execute a single judgment pass against prepared context.

    Creates a pydantic-ai Agent with output_type=VerdictModel.
    NO tools are registered — topological enforcement (JUDG-05).
    Makes a single agent.run() call and returns the validated VerdictModel.
    """
    agent = Agent(model, output_type=VerdictModel)
    # NO tools registered — judgment passes are read-only (JUDG-05)
    result = await agent.run(f"{prepared_context}\n\n{prompt}")
    return result.output  # validated by pydantic-ai


# ---------------------------------------------------------------------------
# DB record creation (JUDG-01, JUDG-02, JUDG-06)
# ---------------------------------------------------------------------------


async def create_judgment_pass_record(
    conn: asyncpg.Connection,
    stage_id: str,
    model: str,
    context_ref: str,
    context_hash: str,
    prompt: str,
    verdict: VerdictModel,
    actor_id: str,
) -> str:
    """Insert a judgment_pass record and a ledger entry, return the judgment_pass.id.

    Writes:
    - judgment_pass row with context_ref, context_hash, response JSONB, confidence, completed_at
    - ledger_entry row: type='judgment_pass_completed', stage_id referenced in content
    """
    pass_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    response_json = json.dumps(verdict.model_dump())
    cost_json = json.dumps({})  # Fan-out plan (03-04) fills real token costs

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO judgment_pass (
                id, stage_ids, model, context_ref, context_hash,
                prompt, response, confidence, cost, created_at, completed_at
            ) VALUES (
                $1::uuid, ARRAY[$2::uuid], $3, $4, $5,
                $6, $7::jsonb, $8, $9::jsonb, $10, $10
            )
            """,
            pass_id,
            stage_id,
            model,
            context_ref,
            context_hash,
            prompt,
            response_json,
            verdict.confidence,
            cost_json,
            now,
        )

        await conn.execute(
            """
            INSERT INTO ledger_entry (
                id, type, actor_id, content, timestamp
            ) VALUES (
                gen_random_uuid(), 'judgment_pass_completed', $1::uuid,
                jsonb_build_object(
                    'judgment_pass_id', $2::text,
                    'stage_id', $3::text,
                    'decision', $4::text,
                    'confidence', $5::float8
                ),
                $6
            )
            """,
            actor_id,
            pass_id,
            stage_id,
            verdict.decision,
            float(verdict.confidence),
            now,
        )

    return pass_id
