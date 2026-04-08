---
phase: 1
slug: db-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds (testcontainers Postgres startup dominates) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/eclusa:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | SCHEMA-01 | integration | `uv run pytest tests/test_schema.py -k entities` | ❌ W0 | pending |
| TBD | 01 | 1 | SCHEMA-02 | integration | `uv run pytest tests/test_ledger.py -k append_only` | ❌ W0 | pending |
| TBD | 01 | 1 | SCHEMA-03 | integration | `uv run pytest tests/test_ledger.py -k schema_version` | ❌ W0 | pending |
| TBD | 01 | 1 | SCHEMA-04 | integration | `uv run pytest tests/test_trace_chain.py` | ❌ W0 | pending |
| TBD | 01 | 1 | SCHEMA-05 | integration | `uv run pytest tests/test_ledger.py -k as_of_timestamp` | ❌ W0 | pending |
| TBD | 01 | 1 | SCHEMA-06 | integration | `uv run pytest tests/test_metrics.py` | ❌ W0 | pending |
| TBD | 01 | 1 | SCHEMA-07 | integration | `uv run pytest tests/test_schema.py -k pgvector` | ❌ W0 | pending |
| TBD | 01 | 1 | INFRA-02 | integration | `docker compose up -d && uv run pytest tests/test_docker.py` | ❌ W0 | pending |
| TBD | 01 | 1 | INFRA-04 | integration | `uv run pytest tests/test_schema.py -k pg_search` | ❌ W0 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — testcontainers Postgres fixture with pgvector + pg_search
- [ ] `tests/test_schema.py` — stubs for entity existence, pgvector, pg_search
- [ ] `tests/test_ledger.py` — stubs for append-only, schema_version, AS OF TIMESTAMP
- [ ] `tests/test_trace_chain.py` — stubs for recursive CTE trace chain
- [ ] `tests/test_metrics.py` — stubs for 8 self-calibration metric SQL computability
- [ ] pytest + pytest-asyncio + testcontainers[postgres] installed via uv

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| docker-compose up boots clean DB | INFRA-02 | Requires full Docker environment | Run `docker compose up -d`, verify all services healthy |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
