---
phase: 23
plan: "03"
subsystem: harness
tags: [refine-agent, system-prompt, questioning-philosophy, integration-tests, error-handling]
dependency_graph:
  requires: [23-01, 23-02]
  provides: [PIPE-01]
  affects: [harness/refine_agent.py, tests/test_refine_agent_integration.py]
tech_stack:
  added: []
  patterns: [pydantic-ai RunContext tool extraction, pytest unittest.mock.patch for module-level imports]
key_files:
  created:
    - tests/test_refine_agent_integration.py
  modified:
    - harness/refine_agent.py
decisions:
  - "System prompt expanded from 2-line stub to full questioning philosophy (~250 words) embedding questioning.md principles"
  - "patch target for search_fn failure is harness.refine_agent.hybrid_search (module-level import), not knowledge.search.hybrid_search"
  - "Pre-existing test_scc_refine model-name assertion failure deferred — env-dependent, not caused by this plan"
metrics:
  duration: "3m 12s"
  completed_date: "2026-04-07"
  tasks_completed: 2
  files_changed: 2
---

# Phase 23 Plan 03: Refine Agent Hardening Summary

Hardened the Refine agent system prompt with the full questioning philosophy from `questioning.md` and proved search tools query the live DB via 5 integration tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Refine system prompt with questioning philosophy | 828281f | harness/refine_agent.py |
| 2 | Integration tests — live DB search and error paths | c7cf3ca | tests/test_refine_agent_integration.py |

## What Was Built

**Task 1 — System prompt overhaul:**
The previous system prompt was a 2-line stub that mentioned "Start open" and "Follow energy" but lacked structure. Replaced with a ~250-word prompt that embeds all six principles from `questioning.md`:
- Start open (let them dump their mental model first)
- Follow energy (dig into what they emphasized)
- Challenge vagueness (never accept fuzzy answers)
- Make the abstract concrete (walk me through using this)
- Clarify ambiguity (when you say Z, do you mean A or B?)
- Know when to stop (propose cascade when scope is clear)

Added explicit guidance on when to call `create_scc_cascade` (only after what/why/who/done are clear), anti-patterns to avoid (checklist walking, canned questions, corporate speak), and proactive tool usage instructions.

**Task 2 — Integration tests:**
Created 5 integration tests using the real `conn` fixture (testcontainer):
1. `test_search_knowledge_tool_queries_db` — seeds entity, calls tool, asserts entity in results
2. `test_search_schemas_tool_queries_db` — same pattern for search_schemas
3. `test_tool_embed_failure_returns_empty_results` — embed exception → empty-results JSON with "Embedding failed" summary
4. `test_refine_agent_system_prompt_contains_philosophy` — asserts all 6 philosophy phrases present
5. `test_tool_search_failure_returns_empty_results` — search fn exception → empty-results JSON

All 5 pass. The existing error handling in `_search_tool` was already correct — the tests prove it.

## Deviations from Plan

### Out-of-Scope Pre-existing Failure (Not Fixed)

**test_dispatch_scc_refine_calls_work_session_lifecycle** in `tests/test_scc_refine.py` has a pre-existing failure (env-dependent model name `openai:glm-5.1` vs hardcoded `anthropic:claude-3-5-haiku-latest`). Confirmed pre-existing on commits before this plan. Logged to `deferred-items.md`. Not caused by changes here.

### Patch Target Correction (Rule 1 — Bug Fix During Test Writing)

Initial Test 5 patched `knowledge.search.hybrid_search`. This doesn't intercept calls because `harness/refine_agent.py` uses `from knowledge.search import hybrid_search` (module-level binding). Correct patch target is `harness.refine_agent.hybrid_search`. Fixed inline.

## Success Criteria Verification

- [x] System prompt contains "Start open", "Follow energy", "Challenge vagueness", "Know when to stop" — verified
- [x] search_knowledge and search_schemas tools make real DB queries — proven by tests 1 and 2
- [x] Tool errors (embed failure, search failure) return empty-results JSON — proven by tests 3 and 5
- [x] `python -m pytest tests/test_refine_agent_integration.py` exits 0 — 5 passed
- [x] `python -m pytest tests/test_scc_refine.py` — 3/4 pass; 1 pre-existing env-dependent failure unrelated to this plan

## Known Stubs

None. The Refine agent system prompt is substantive, tools are wired to the live DB, and error paths are handled.

## Self-Check: PASSED

- harness/refine_agent.py: FOUND
- tests/test_refine_agent_integration.py: FOUND
- commit 828281f: FOUND (feat(23-03): update Refine agent system prompt)
- commit c7cf3ca: FOUND (test(23-03): add Refine agent integration tests)
