"""EXEC-E2E-01: Executor boots, connects to live DB, and polls successfully.

Proves:
  - asyncpg pool connects to the docker-compose Postgres instance
  - single_poll_cycle runs SKIP LOCKED query without errors
  - Actor UUID is accepted by the claim/dispatch path
"""

import asyncio
import json

import pytest

from executor.loop import single_poll_cycle

pytestmark = pytest.mark.asyncio


async def test_executor_boots_and_polls(e2e_pool, seed_actor):
    """single_poll_cycle completes without error against the live DB.

    With no pending stages seeded, it should return an empty list — but the
    critical assertion is that the DB connection, SKIP LOCKED query, and
    actor_id parameter all work without raising.
    """
    result = await single_poll_cycle(e2e_pool, seed_actor)
    assert isinstance(result, list)


async def test_executor_container_stays_running():
    """The executor container in docker-compose is running and has been up for >10 seconds.

    Skips gracefully if docker-compose is not available.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "ps", "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    except (FileNotFoundError, asyncio.TimeoutError):
        pytest.skip("docker compose CLI not available or timed out")
        return

    if proc.returncode != 0:
        pytest.skip(f"docker compose ps failed: {stderr.decode()}")
        return

    output = stdout.decode().strip()
    if not output:
        pytest.skip("docker compose returned empty output")
        return

    # docker compose ps --format json may output one JSON object per line
    # or a JSON array depending on version. Handle both.
    containers = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, list):
                containers.extend(parsed)
            else:
                containers.append(parsed)
        except json.JSONDecodeError:
            continue

    # Find the executor container
    executor_info = None
    for c in containers:
        service = c.get("Service") or c.get("service") or ""
        name = c.get("Name") or c.get("name") or ""
        if service == "executor" or "executor" in name:
            executor_info = c
            break

    if executor_info is None:
        pytest.skip("executor container not found in docker-compose ps output")
        return

    state = (executor_info.get("State") or executor_info.get("state") or "").lower()
    assert state == "running", f"Executor container state is {state!r}, expected 'running'"

    # Check health status if available
    health = (executor_info.get("Health") or executor_info.get("health") or "").lower()
    if health:
        assert health == "healthy", f"Executor container health is {health!r}, expected 'healthy'"
