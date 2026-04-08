"""
proxy/addon.py — mitmproxy ArtifactCaptureAddon

Intercepts every outbound LLM API response and enqueues an artifact
payload for async DB write. Never blocks the proxied response.

~40 lines. D-07, D-08, D-09, D-10, D-11.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ArtifactCaptureAddon:
    """mitmproxy addon. Registers with executor at session start (D-11)."""

    def __init__(self) -> None:
        # Circuit-breaker queue (D-09): maxsize=500, put_nowait drops on overflow
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        # session_id → {intent_id, cascade_id, stage_id} (D-10)
        self._session_context: dict[str, dict[str, str]] = {}

    # --- Session lifecycle registration (D-11) ---

    def register_session(self, session_id: str, context: dict[str, str]) -> None:
        """Called by executor when work session starts."""
        self._session_context[session_id] = context

    def deregister_session(self, session_id: str) -> None:
        """Called by executor when work session ends."""
        self._session_context.pop(session_id, None)

    # --- mitmproxy hooks ---

    def responseheaders(self, flow) -> None:  # type: ignore[no-untyped-def]
        """Pass SSE streaming through without buffering (Pitfall 1)."""
        ct = flow.response.headers.get("content-type", "")
        if "text/event-stream" in ct:
            flow.response.stream = True  # CRITICAL: prevents SSE hang

    async def response(self, flow) -> None:  # type: ignore[no-untyped-def]
        """Enqueue artifact payload after every intercepted response (D-08)."""
        session_id = flow.metadata.get("session_id", "")
        ctx = self._session_context.get(session_id)
        if ctx is None:
            return  # no registered session — skip

        payload: dict[str, Any] = {
            "url": flow.request.pretty_url,
            "status_code": flow.response.status_code,
            "session_id": session_id,
            "intent_id": ctx.get("intent_id"),
            "cascade_id": ctx.get("cascade_id"),
            "stage_id": ctx.get("stage_id"),
        }
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Circuit-breaker: drop artifact, never block the response (D-09, Pitfall 2)
            logger.warning(
                "Artifact queue full — dropping capture for %s", flow.request.pretty_url
            )

    @property
    def queue(self) -> asyncio.Queue:
        """Expose queue for executor writer task to drain."""
        return self._queue


addons = [ArtifactCaptureAddon()]
