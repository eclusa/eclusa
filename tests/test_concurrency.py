"""Model concurrency controller unit tests.

Tests the semaphore pool logic without needing a database or LLM calls.
"""

import asyncio
import os

import pytest

pytestmark = pytest.mark.asyncio


async def test_default_glm_limit():
    """GLM models get limit=2 by default."""
    from executor.concurrency import ModelConcurrencyController

    ctrl = ModelConcurrencyController()
    assert ctrl._resolve_limit("openai:glm-5.1") == 2
    assert ctrl._resolve_limit("openai:glm-4") == 2


async def test_default_anthropic_limit():
    """Anthropic models get limit=5 by default."""
    from executor.concurrency import ModelConcurrencyController

    ctrl = ModelConcurrencyController()
    assert ctrl._resolve_limit("anthropic:claude-sonnet-4-6") == 5


async def test_unknown_model_gets_global_default():
    """Unknown model identifiers get the global default (3)."""
    from executor.concurrency import ModelConcurrencyController

    ctrl = ModelConcurrencyController()
    assert ctrl._resolve_limit("some-other-model") == 3


async def test_env_override():
    """MODEL_CONCURRENCY_<NORMALIZED> env var overrides defaults."""
    from executor.concurrency import ModelConcurrencyController

    os.environ["MODEL_CONCURRENCY_OPENAI_GLM_5_1"] = "10"
    try:
        ctrl = ModelConcurrencyController()
        assert ctrl._resolve_limit("openai:glm-5.1") == 10
    finally:
        del os.environ["MODEL_CONCURRENCY_OPENAI_GLM_5_1"]


async def test_semaphore_limits_concurrency():
    """Only N tasks run concurrently for a model with limit=N."""
    from executor.concurrency import ModelConcurrencyController

    ctrl = ModelConcurrencyController()
    # Force limit to 2 via env
    os.environ["MODEL_CONCURRENCY_TEST_MODEL"] = "2"
    try:
        model = "test-model"
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def simulated_llm_call(task_id: int):
            nonlocal max_concurrent, current_concurrent
            await ctrl.acquire(model)
            try:
                async with lock:
                    current_concurrent += 1
                    max_concurrent = max(max_concurrent, current_concurrent)
                await asyncio.sleep(0.05)
            finally:
                async with lock:
                    current_concurrent -= 1
                ctrl.release(model)

        tasks = [asyncio.create_task(simulated_llm_call(i)) for i in range(6)]
        await asyncio.gather(*tasks)

        assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}, expected ≤2"
        assert max_concurrent == 2, f"Max concurrent was {max_concurrent}, expected exactly 2"
    finally:
        del os.environ["MODEL_CONCURRENCY_TEST_MODEL"]


async def test_different_models_independent_semaphores():
    """Different models have independent semaphore pools."""
    from executor.concurrency import ModelConcurrencyController

    ctrl = ModelConcurrencyController()
    os.environ["MODEL_CONCURRENCY_MODEL_A"] = "1"
    os.environ["MODEL_CONCURRENCY_MODEL_B"] = "1"
    try:
        results: list[str] = []
        lock = asyncio.Lock()

        async def call_model(model: str, label: str):
            await ctrl.acquire(model)
            try:
                async with lock:
                    results.append(f"{label}_start")
                await asyncio.sleep(0.05)
                async with lock:
                    results.append(f"{label}_end")
            finally:
                ctrl.release(model)

        # Both should start immediately since they use different models
        t1 = asyncio.create_task(call_model("model-a", "a"))
        t2 = asyncio.create_task(call_model("model-b", "b"))
        await asyncio.gather(t1, t2)

        # Both should have started before either ended
        a_start = results.index("a_start")
        b_start = results.index("b_start")
        a_end = results.index("a_end")
        b_end = results.index("b_end")
        assert a_start < a_end
        assert b_start < b_end
        # Both started before the first one ended (parallel)
        assert max(a_start, b_start) < min(a_end, b_end)
    finally:
        del os.environ["MODEL_CONCURRENCY_MODEL_A"]
        del os.environ["MODEL_CONCURRENCY_MODEL_B"]


async def test_status_reports_usage():
    """status() reports limit, available, and in_use counts."""
    from executor.concurrency import ModelConcurrencyController

    ctrl = ModelConcurrencyController()
    os.environ["MODEL_CONCURRENCY_STATUS_MODEL"] = "3"
    try:
        model = "status-model"
        await ctrl.acquire(model)
        await ctrl.acquire(model)

        status = ctrl.status()
        assert model in status
        assert status[model]["limit"] == 3
        assert status[model]["in_use"] == 2
        assert status[model]["available"] == 1

        ctrl.release(model)
        ctrl.release(model)

        status = ctrl.status()
        assert status[model]["in_use"] == 0
        assert status[model]["available"] == 3
    finally:
        del os.environ["MODEL_CONCURRENCY_STATUS_MODEL"]
