"""
fan_out/dispatcher.py -- Parallel judgment pass firing for fan-out evaluation.

Fires n judgment passes in parallel using asyncio.gather against a shared
prepared context. Returns structured results for the DB layer (fan_out/db.py)
to persist and act on.

D-18: fan-out fires n passes in parallel against shared context.
FAN-01.
"""

import asyncio
import logging
from typing import Any

from judgment.pass_ import VerdictModel, run_judgment_pass
from fan_out.convergence import compute_convergence

logger = logging.getLogger(__name__)


async def run_fan_out(
    models: list[str],
    prepared_context: str,
    prompt: str,
    context_hash: str,
) -> tuple[list[VerdictModel], str, dict[str, Any]]:
    """Fire n judgment passes in parallel and compute convergence.

    Args:
        models: List of model identifiers. Each fires one judgment pass.
        prepared_context: Shared context string (prepared once, reused for all passes). D-18.
        prompt: Shared evaluation question (same for all passes). D-18.
        context_hash: blake3/sha256 hex digest of prepared_context. D-17.

    Returns:
        verdicts: list[VerdictModel] -- one per model, in input order
        verdict_state: "converged" | "diverged" | "partial"
        convergence_matrix: {field: {"values": [...], "converged": bool}}

    Exceptions propagate -- if any judgment pass fails, run_fan_out raises.
    Caller is responsible for retry logic.
    """
    if not models:
        raise ValueError("run_fan_out requires at least one model")

    logger.info(
        "Fan-out: firing %d judgment passes in parallel (context_hash=%s)",
        len(models),
        context_hash[:8],
    )

    # Fire all passes in parallel -- context prepared once, shared across all (D-18, JUDG-06)
    results = await asyncio.gather(
        *[run_judgment_pass(model, prepared_context, prompt) for model in models],
        return_exceptions=False,  # propagate failures; caller handles retry
    )

    verdicts: list[VerdictModel] = list(results)
    verdict_state, convergence_matrix = compute_convergence(verdicts)

    logger.info(
        "Fan-out complete: verdict=%s, models=%s",
        verdict_state,
        models,
    )

    return verdicts, verdict_state, convergence_matrix
