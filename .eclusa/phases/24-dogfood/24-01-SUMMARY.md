---
phase: 24-dogfood
plan: "01"
subsystem: tests/e2e
tags: [dogfood, e2e, scc, pipe-04, trace, polling]
dependency_graph:
  requires: [executor/scc_handlers.py, adapters/web/api/auth.py, adapters/web/api/scc.py, adapters/web/api/cascades.py, adapters/web/api/trace.py]
  provides: [tests/e2e/test_24_dogfood_scc_journey.py]
  affects: []
tech_stack:
  added: []
  patterns: [asyncio.timeout for bounded async tests, httpx.AsyncClient for API calls, asyncpg direct for DB seeding/cleanup, module-level skipif guard]
key_files:
  created:
    - tests/e2e/test_24_dogfood_scc_journey.py
  modified: []
decisions:
  - "Used asyncio.timeout(350) instead of @pytest.mark.timeout — pytest-timeout not in dev dependencies; asyncio.timeout is stdlib and integrates cleanly with asyncio_mode=auto"
  - "Inlined _cleanup_scc_cascade logic rather than importing from conftest — avoids module import path complexity and keeps the file self-contained"
  - "Cleanup opens a second asyncpg connection rather than reusing the test client connection — allows cleanup to run after the httpx client context manager exits"
  - "test_scc_journey_structure_only accepts 'active' stage state in addition to 'pending' — executor may start picking up stages before the assertion runs"
metrics:
  duration: "~4 minutes"
  completed: "2026-04-07T05:47:50Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 24 Plan 01: SCC Dogfood Journey Test Summary

**One-liner:** pytest E2E test proving intent-to-code pipeline via polling, Generate output verification, and 5-hop artifact trace chain for PIPE-04.

## What Was Built

`tests/e2e/test_24_dogfood_scc_journey.py` — 498-line pytest E2E test file implementing the full PIPE-04 dogfood scenario.

### test_blog_scc_full_journey

Steps:
1. Registers a unique user via `POST /api/auth/register` (returns JWT)
2. Creates a 7-stage SCC cascade via `POST /api/scc/create` with blog intent
3. Polls `GET /api/cascades/{cascade_id}/stages` every 5s for up to 5 minutes until all stages reach a terminal state (`resolved`, `failed`, or `skipped`)
4. On timeout: emits a diagnostic table showing each stage's `scc_stage` name and current state, then calls `pytest.fail()`
5. Verifies: no non-formalize failures; at least 5 stages resolved
6. Fetches `GET /api/cascades/{cascade_id}/stages/{generate_stage_id}/output` and asserts output is non-None, >50 chars, and does not start with `Error`/`Exception`/`Traceback`
7. Seeds a `work_session` and `artifact` row via direct asyncpg connection
8. Calls `GET /api/trace/{artifact_id}` and asserts 5 hops in order: `["artifact", "session", "stage", "cascade", "intent"]` with correct IDs
9. Cleans up seeded rows and full actor/cascade tree in `finally` blocks

### test_scc_journey_structure_only

Fast structural check (no LLM execution wait):
- Registers user, creates cascade, immediately fetches stages
- Asserts exactly 7 stages with `scc_stage` names matching the expected set
- Asserts no stage in `failed` state at creation time
- Cleans up

### Module-level skip guard

```python
def _api_available() -> bool:
    try:
        urllib.request.urlopen("http://localhost:8000/healthz", timeout=5)
        return True
    except Exception:
        return False

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _api_available(), reason="docker-compose API not running"),
]
```

Collection exits with code 0 (tests listed) when API is up, or 5 (skipped) when API is unreachable — no ERROR lines in either case.

## Decisions Made

1. **asyncio.timeout instead of pytest-timeout marker** — `pytest-timeout` is not in dev dependencies. `asyncio.timeout(350)` is stdlib (Python 3.11+) and works cleanly with `asyncio_mode = auto`. The plan's Task 2 explicitly anticipated this deviation and described exactly this fallback.

2. **Inlined cleanup helpers** — `_cleanup_scc_cascade` and `_cleanup_actor_by_email` are copied from `test_v20_production_e2e.py` / `conftest.py` rather than imported. This keeps the file self-contained and avoids `sys.path` manipulation that would be required for cross-module conftest imports.

3. **Separate asyncpg connection for artifact seeding** — The artifact seeding in Step 6 uses a direct `asyncpg.connect()` rather than the pool, which allows precise cleanup sequencing before cascade deletion.

4. **Cleanup uses cascade-level deletion** — `_cleanup_actor_by_email` calls `_cleanup_scc_cascade` which includes artifact deletion. The test also explicitly deletes the seeded artifact and session before the cascade cleanup runs to avoid FK violations.

5. **test_scc_journey_structure_only accepts `active` state** — The executor may start dispatching stages within milliseconds of creation. The structural test accepts `pending | active | resolved | failed | skipped` to avoid flakiness on fast executors, but still fails if any stage is `failed` immediately after creation.

## Deviations from Plan

### Auto-fixed Issues

None.

### Clarifications Applied

**1. [Plan task 2 - asyncio.timeout] Used stdlib timeout instead of pytest.mark.timeout**
- **Found during:** Task 2 verification step
- **Issue:** `pytest-timeout` not listed in `pyproject.toml` dev dependencies
- **Fix:** Wrapped test body in `async with asyncio.timeout(350)` instead of using `@pytest.mark.timeout(360)` decorator. Plan's Task 2 explicitly described this exact fallback.
- **Files modified:** `tests/e2e/test_24_dogfood_scc_journey.py` (written this way from the start)
- **Commit:** fef1ff1

## Verification Results

- Syntax check: `python -c "import ast; ast.parse(...)"` exits 0
- Collection dry-run: `pytest --collect-only -q` exits 0, lists both test names, no ERROR lines
- File line count: 498 lines (min_lines requirement: 150 — satisfied)

## Key Links Implemented

| from | to | via | pattern |
|------|-----|-----|---------|
| test_24_dogfood_scc_journey.py | POST /api/auth/register | httpx.AsyncClient | `client.post("/api/auth/register", ...)` |
| test_24_dogfood_scc_journey.py | POST /api/scc/create | httpx.AsyncClient | `client.post("/api/scc/create", ...)` |
| test_24_dogfood_scc_journey.py | GET /api/cascades/{id}/stages | polling loop every 5s | `client.get(f"/api/cascades/{cascade_id}/stages", ...)` |
| test_24_dogfood_scc_journey.py | GET /api/trace/{artifact_id} | httpx.AsyncClient | `client.get(f"/api/trace/{artifact_id}", ...)` |

## Known Stubs

None. The test file contains no hardcoded empty data that flows to the tested surface. All assertions target real API responses.

## Self-Check: PASSED

- `tests/e2e/test_24_dogfood_scc_journey.py` exists: FOUND
- Commit fef1ff1 exists: FOUND
- pytest --collect-only exits 0 with 2 tests listed and no ERROR lines: PASSED
