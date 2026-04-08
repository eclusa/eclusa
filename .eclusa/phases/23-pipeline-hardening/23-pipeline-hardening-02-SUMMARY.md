---
phase: 23-pipeline-hardening
plan: "02"
subsystem: harness
tags: [ambiguity, gate, work-session, pydantic-ai, tool-injection]
dependency_graph:
  requires:
    - harness/native.py (pause_work_session)
    - executor/dispatch.py (surface_gate)
  provides:
    - harness/ambiguity.py (make_ambiguity_up_tool, AmbiguityContext)
  affects:
    - any work session harness that injects the ambiguityUp tool
tech_stack:
  added: []
  patterns:
    - pydantic-ai Agent.tool decorator for tool injection
    - Direct tool function extraction via agent._function_toolset.tools[name].function
    - AmbiguityContext dataclass as RunContext deps_type
key_files:
  created:
    - harness/ambiguity.py
    - tests/test_ambiguity_up.py
  modified: []
decisions:
  - "snapshot_store is optional in AmbiguityContext — None triggers direct UPDATE path, not a crash"
  - "Tool returns 'gate:<uuid>' string so the agent knows the gate ID after call"
  - "surface_gate called on in-memory stage dict (same pattern as dispatch.py) — no second DB fetch needed"
  - "Gate stage inserted with state='pending' first, surface_gate then sets it to 'blocked'"
metrics:
  duration: "~2 minutes"
  completed_date: "2026-04-07"
  tasks_completed: 1
  files_changed: 2
---

# Phase 23 Plan 02: ambiguityUp Tool for Work Session Agents Summary

**One-liner:** Pydantic-ai tool factory (`make_ambiguity_up_tool`) that inserts a gate stage, calls `surface_gate`, and pauses the work session when an agent hits an unresolvable ambiguity.

## Objective

Implement `harness/ambiguity.py` — the "ambiguity up, decisions down" governance primitive at the agent level (RFC §5.2). Any work session agent can call `make_ambiguity_up_tool(agent)` to register the `ambiguityUp` tool, which creates a gate, surfaces it, and pauses the session transparently.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing tests for ambiguityUp | a9d6c1d | tests/test_ambiguity_up.py |
| 1 (GREEN) | Implement ambiguityUp tool and AmbiguityContext | c6d0920 | harness/ambiguity.py |

## Implementation Details

### harness/ambiguity.py

**`AmbiguityContext` dataclass** — deps injected into the tool:
- `conn: asyncpg.Connection` — for all DB writes
- `session_id: str` — UUID of the running work_session
- `cascade_id: str` — UUID of the cascade this session belongs to
- `actor_id: str` — UUID of the actor owning this session
- `snapshot_store: Any = None` — optional SnapshotStore; if None, session paused via direct UPDATE

**`make_ambiguity_up_tool(agent)` factory** — injects `ambiguityUp` tool:
1. Inserts a gate-type stage (`state='pending'`, `input` contains `gate_description`, `channel_type='email'`, `raised_by_session`)
2. Calls `surface_gate(conn, gate_stage, actor_id)` which marks `state='blocked'`, writes `gate_surfaced` ledger entry, dispatches to adapter
3. Pauses the work session: `pause_work_session()` if snapshot_store provided, otherwise direct `UPDATE work_session SET state='paused', paused_at=NOW()`
4. Returns `"gate:<uuid>"` so the agent's tool result contains the gate ID

### tests/test_ambiguity_up.py

5 tests covering all behavior requirements:
- `test_ambiguity_up_creates_gate_stage` — gate row with `type='gate'`, `state='blocked'`, correct `gate_description`
- `test_ambiguity_up_pauses_session` — `work_session.state='paused'`, `paused_at` is set
- `test_ambiguity_up_surfaces_gate` — `ledger_entry` of type `'gate_surfaced'` exists for gate
- `test_ambiguity_up_returns_gate_id` — return value is `'gate:<uuid>'`, UUID exists in stage table
- `test_ambiguity_up_no_snapshot_store` — session paused without crash when `snapshot_store=None`

Test pattern: direct tool function extraction via `agent._function_toolset.tools["ambiguityUp"].function`, called with a constructed `RunContext[AmbiguityContext]`. Surface gate adapter patched to no-op to avoid missing adapter warnings.

## Verification

```
tests/test_ambiguity_up.py::test_ambiguity_up_creates_gate_stage PASSED
tests/test_ambiguity_up.py::test_ambiguity_up_pauses_session PASSED
tests/test_ambiguity_up.py::test_ambiguity_up_surfaces_gate PASSED
tests/test_ambiguity_up.py::test_ambiguity_up_returns_gate_id PASSED
tests/test_ambiguity_up.py::test_ambiguity_up_no_snapshot_store PASSED
5 passed in 7.61s
```

Import check: `python -c "from harness.ambiguity import AmbiguityContext, make_ambiguity_up_tool; print('ok')"` → ok

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all behavior is fully wired. Gate stage is created in DB, surface_gate marks it blocked and writes ledger, work_session is paused. No placeholder values.

## Self-Check: PASSED
