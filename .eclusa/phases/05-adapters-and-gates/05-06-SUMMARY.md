---
phase: 05-adapters-and-gates
plan: "06"
subsystem: adapters/web
tags: [rbac, fastapi, gate-resolution, permission-check, tdd]
dependency_graph:
  requires:
    - "05-03 (resolve_gate in executor/dispatch.py)"
    - "05-01 (actor.permissions JSONB schema)"
  provides:
    - "check_resolve_permission() — RBAC check at API boundary (D-12, D-14)"
    - "has_cost_view_permission() — cost view access helper"
    - "POST /gates/{gate_id}/resolve FastAPI endpoint"
  affects:
    - "adapters/web/routes.py (full implementation replacing stub)"
tech_stack:
  added: []
  patterns:
    - "asyncpg JSONB permissions read with json.loads fallback"
    - "httpx.AsyncClient + ASGITransport for async FastAPI endpoint testing"
    - "pool.acquire() for connection pooling in FastAPI dependency injection"
key_files:
  created: []
  modified:
    - "adapters/web/routes.py"
    - "tests/test_rbac.py"
    - "tests/test_email_adapter.py"
decisions:
  - "Use httpx.AsyncClient + ASGITransport instead of TestClient for async endpoint tests — keeps asyncpg pool bound to the same event loop as the test; TestClient creates a new thread event loop which breaks asyncpg pool association"
  - "resolve_token check is conditional (nullable) — gate stages from Plan 03 may not have tokens; NULL resolve_token skips token validation (safe for v1)"
  - "json.loads fallback on permissions JSONB — asyncpg returns JSONB as dict in some contexts and str in others depending on codec registration"
metrics:
  duration: "4 minutes"
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_modified: 3
  tests_added: 5
---

# Phase 05 Plan 06: RBAC Resolve Endpoint Summary

RBAC permission check and FastAPI resolve endpoint — check_resolve_permission() enforces permission delegation at the API boundary with wildcard and type-specific gate access control.

## Objective

Implement `check_resolve_permission()` and `has_cost_view_permission()` helpers in `adapters/web/routes.py`, replace the stub `POST /gates/{gate_id}/resolve` endpoint with full RBAC enforcement and `resolve_gate()` integration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | test_rbac failing tests | 06490b7 | tests/test_rbac.py |
| 1 (GREEN) | check_resolve_permission + resolve endpoint | 1e380b9 | adapters/web/routes.py |
| 2 (RED+GREEN) | test_resolve_endpoint_rbac | b0cbc19 | tests/test_email_adapter.py |

## What Was Built

### `check_resolve_permission(conn, actor_id, gate_type) -> bool`

Reads `actor.permissions` JSONB and checks `resolve_gates` key:
- `["*"]` → True for any gate_type (wildcard)
- `["approval"]` → True only for "approval", False for "review"
- `[]` or `{}` or `None` → False for any gate_type
- Actor not in DB → False

### `has_cost_view_permission(conn, actor_id) -> bool`

Reads `view_costs` bool from `actor.permissions` JSONB. False for missing actors or absent key.

### `POST /gates/{gate_id}/resolve`

Full implementation replacing the stub:
1. Fetch gate stage (404 if not found)
2. Validate state == 'blocked' (409 otherwise)
3. Token check (conditional — skipped if `resolve_token` is NULL in DB)
4. RBAC check via `check_resolve_permission()` (403 if denied)
5. Call `resolve_gate(conn, gate_id, actor_id)` — writes DB + fires both NOTIFY channels
6. Return `{"status": "resolved", "gate_id": gate_id}`

## Tests

### tests/test_rbac.py (4 tests — all pass)
- `test_resolve_permission_allowed` — specific gate type match → True
- `test_resolve_permission_denied` — type mismatch → False
- `test_resolve_permission_wildcard` — `["*"]` → True for any type
- `test_cost_view_permission` — view_costs True/False/absent

### tests/test_email_adapter.py::test_resolve_endpoint_rbac (1 test — passes)
- Denied actor → 403
- Non-existent gate → 404
- Permitted actor → 200 + `{"status": "resolved"}`
- Already-resolved gate → 409
- Stage state verified as 'resolved' in DB after successful call

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed asyncpg pool + TestClient event loop mismatch**
- **Found during:** Task 2 (integration test)
- **Issue:** `TestClient` runs an internal sync/thread event loop; `asyncpg.Pool` created in the async test event loop cannot be used from a different loop. Produced 500 Internal Server Error.
- **Fix:** Replaced `TestClient` with `httpx.AsyncClient(transport=ASGITransport(app=app))` — keeps pool and HTTP calls in the same async event loop.
- **Files modified:** tests/test_email_adapter.py
- **Commit:** b0cbc19

## Known Stubs

None — all stub patterns removed. The endpoint returns real data and calls real DB functions.

## Verification Results

```
uv run pytest tests/test_rbac.py -v
# 4 passed

uv run pytest tests/test_email_adapter.py::test_resolve_endpoint_rbac -v
# 1 passed

grep -n "check_resolve_permission|resolve_gate" adapters/web/routes.py
# both appear in the endpoint

uv run pytest tests/ -x -q
# 258 passed
```

## Self-Check: PASSED

- [x] `adapters/web/routes.py` exists with `check_resolve_permission` and `has_cost_view_permission`
- [x] `tests/test_rbac.py` exists with 4 passing tests
- [x] `tests/test_email_adapter.py` exists with `test_resolve_endpoint_rbac` passing
- [x] Commits 06490b7, 1e380b9, b0cbc19 exist in git log
- [x] Full test suite: 258 passed, 0 failed
