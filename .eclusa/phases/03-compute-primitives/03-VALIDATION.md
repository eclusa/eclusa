---
phase: 3
slug: compute-primitives
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pytest.ini (from Phase 1) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/eclusa:verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Wave 0 Requirements

- [ ] `pydantic-ai==1.77.0` installed via uv add
- [ ] `mitmproxy`, `httpx`, `blake3` installed via uv add
- [ ] `tests/test_work_session.py` — stubs for session lifecycle
- [ ] `tests/test_proxy.py` — stubs for artifact capture
- [ ] `tests/test_judgment.py` — stubs for judgment pass
- [ ] `tests/test_fanout.py` — stubs for fan-out convergence

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] Feedback latency < 25s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
