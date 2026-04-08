---
phase: 4
slug: knowledge-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pytest.ini |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Max feedback latency:** 30 seconds

---

## Wave 0 Requirements

- [ ] Parser dependencies installed (pyyaml, openapi-spec-validator, sqlglot, graphql-core, proto-schema-parser)
- [ ] `tests/test_parsers.py` — stubs for 5 parser formats
- [ ] `tests/test_knowledge_graph.py` — stubs for KG ingestion, entity resolution, edge invalidation
- [ ] `tests/test_hybrid_search.py` — stubs for cosine + BM25 + BFS + RRF
- [ ] `tests/fixtures/` — sample schema files for each format

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
