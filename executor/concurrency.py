"""Model concurrency controller — per-model semaphore pool.

Prevents rate-limit stalls by throttling concurrent LLM calls per model.
Default limits are conservative; override via MODEL_CONCURRENCY_<NORMALIZED> env vars.

Example: MODEL_CONCURRENCY_OPENAI_GLM_5_1=2 sets the limit for openai:glm-5.1
"""

from __future__ import annotations

import asyncio
import os
import logging

logger = logging.getLogger(__name__)

_DEFAULT_LIMITS: dict[str, int] = {
    "openai:glm": 2,
    "anthropic:": 5,
}
_GLOBAL_DEFAULT = 3


class ModelConcurrencyController:
    """Manages per-model asyncio.Semaphore instances.

    Thread-safe within a single event loop. Each executor process gets one instance.
    """

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._limits: dict[str, int] = {}

    def _resolve_limit(self, model: str) -> int:
        env_key = (
            "MODEL_CONCURRENCY_"
            + model.replace(":", "_").replace("-", "_").replace(".", "_").upper()
        )
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return int(env_val)
        for prefix, limit in _DEFAULT_LIMITS.items():
            if model.startswith(prefix):
                return limit
        return _GLOBAL_DEFAULT

    def _get_semaphore(self, model: str) -> asyncio.Semaphore:
        if model not in self._semaphores:
            limit = self._resolve_limit(model)
            self._semaphores[model] = asyncio.Semaphore(limit)
            self._limits[model] = limit
            logger.info("Model concurrency: %s → max %d", model, limit)
        return self._semaphores[model]

    async def acquire(self, model: str) -> None:
        sem = self._get_semaphore(model)
        await sem.acquire()
        logger.debug("Semaphore acquired: %s", model)

    def release(self, model: str) -> None:
        if model in self._semaphores:
            self._semaphores[model].release()
            logger.debug("Semaphore released: %s", model)

    def status(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for model, sem in self._semaphores.items():
            limit = self._limits[model]
            available: int = sem._value  # type: ignore[attr-defined]
            result[model] = {
                "limit": limit,
                "available": available,
                "in_use": limit - available,
            }
        return result


controller = ModelConcurrencyController()
