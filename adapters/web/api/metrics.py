from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from adapters.web.api.auth import verify_token

router = APIRouter(prefix="/metrics", dependencies=[Depends(verify_token)])

__all__ = ["router"]

METRICS_DIR = Path(__file__).resolve().parents[3] / "db/queries/metrics"
SQL = {
    "gate_necessity": (METRICS_DIR / "gate_necessity.sql").read_text(),
    "orchestrator_absorption": (
        METRICS_DIR / "orchestrator_absorption.sql"
    ).read_text(),
    "resolution_latency": (METRICS_DIR / "resolution_latency.sql").read_text(),
    "decision_durability": (METRICS_DIR / "decision_durability.sql").read_text(),
    "cascade_rework": (METRICS_DIR / "cascade_rework.sql").read_text(),
    "model_convergence": (METRICS_DIR / "model_convergence.sql").read_text(),
    "minority_accuracy": (METRICS_DIR / "minority_accuracy.sql").read_text(),
    "fanout_necessity": (METRICS_DIR / "fanout_necessity.sql").read_text(),
}


class MetricsResponse(BaseModel):
    gate_necessity: float | None
    orchestrator_absorption: float | None
    resolution_latency: float | None
    decision_durability: float | None
    cascade_rework: float | None
    model_convergence: float | None
    minority_accuracy: float | None
    fanout_necessity: float | None


def _numeric_value(row: Any) -> float | None:
    if row is None:
        return None
    for value in row.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float, Decimal)):
            return float(value)
    return None


@router.get("", response_model=MetricsResponse)
async def get_metrics(request: Request) -> MetricsResponse:
    pool = request.app.state.pool
    lookback = timedelta(days=30)

    results: dict[str, float | None] = {}
    for key, sql in SQL.items():
        row = await pool.fetchrow(sql, lookback)
        results[key] = _numeric_value(row)

    return MetricsResponse(**results)
