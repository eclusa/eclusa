"""Executor package — stateless dispatch loop for the cascade graph.

Entry point: run_executor()
"""

from executor.loop import run_executor
from executor.cascade import (
    claim_ready_stages,
    apply_pending_migration,
    check_cascade_completion,
    retry_stage,
    MaxRetriesExceeded,
)


__all__ = [
    "run_executor",
    "claim_ready_stages",
    "apply_pending_migration",
    "check_cascade_completion",
    "retry_stage",
    "MaxRetriesExceeded",
]
