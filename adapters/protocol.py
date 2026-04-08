"""Adapter protocol — shared interface for all gate surfacing adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

__all__ = ["GateContext", "AdapterProtocol"]


@dataclass
class GateContext:
    """Context passed to adapters when surfacing a gate to humans.

    Carries all information needed to describe the gate and provide the
    resolution URL. D-04: includes model_recommendation if fan-out ran.
    """

    cascade_id: str
    stage_id: str
    gate_description: str
    model_recommendation: str | None  # D-04: present if fan-out ran
    eligible_actor_ids: list[str]
    resolve_url: str  # signed URL for resolution callback


class AdapterProtocol(ABC):
    """Abstract base class for all gate surfacing adapters.

    Every adapter (email, Slack, webhook, etc.) must implement surface_gate.
    The executor calls this without knowing the underlying channel — D-02.
    """

    @abstractmethod
    async def surface_gate(self, context: GateContext) -> None:
        """Surface a gate to humans via this channel. Must be idempotent."""
        ...
