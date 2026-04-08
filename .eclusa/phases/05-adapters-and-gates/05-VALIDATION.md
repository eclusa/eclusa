---
phase: 5
slug: adapters-and-gates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 5 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~25 seconds |

## Wave 0 Requirements

- [ ] aioimaplib, aiosmtplib, fastapi installed via uv add
- [ ] `tests/test_email_adapter.py` — stubs
- [ ] `tests/test_gate_surfacing.py` — stubs
- [ ] `tests/test_rbac.py` — stubs
- [ ] `tests/test_sanitize.py` — stubs

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Feedback latency < 25s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
