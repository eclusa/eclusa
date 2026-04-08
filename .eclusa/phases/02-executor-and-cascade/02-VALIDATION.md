---
phase: 2
slug: executor-and-cascade
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pytest.ini (from Phase 1) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~20 seconds (testcontainers + concurrent executor tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/eclusa:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 0 | SCHEMA gap | migration | `uv run pytest tests/test_schema.py` | ✅ | pending |
| TBD | 02 | 1 | EXEC-01,02 | integration | `uv run pytest tests/test_executor.py -k poll` | ❌ W0 | pending |
| TBD | 02 | 1 | EXEC-03 | integration | `uv run pytest tests/test_executor.py -k concurrent` | ❌ W0 | pending |
| TBD | 02 | 1 | EXEC-04 | integration | `uv run pytest tests/test_executor.py -k crash` | ❌ W0 | pending |
| TBD | 03 | 2 | CASC-01,02,03 | integration | `uv run pytest tests/test_cascade.py` | ❌ W0 | pending |
| TBD | 03 | 2 | CASC-04,05 | integration | `uv run pytest tests/test_cascade.py -k migration` | ❌ W0 | pending |
| TBD | 04 | 3 | EXEC-05,06,07 | integration | `uv run pytest tests/test_dispatch.py` | ❌ W0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_executor.py` — stubs for executor poll loop, concurrent dispatch, crash recovery
- [ ] `tests/test_cascade.py` — stubs for graph traversal, branching, migration
- [ ] `tests/test_dispatch.py` — stubs for narrowing dispatch, gate surfacing
- [ ] `tests/helpers/topology.py` — cascade topology seeding helper

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LISTEN/NOTIFY wake-hint reduces poll latency | EXEC-02 | Timing-sensitive | Start executor, INSERT stage, measure dispatch latency vs poll interval |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
