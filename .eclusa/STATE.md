---
eclusa_state_version: 1.0
milestone: v1.1
milestone_name: Platform Verification
status: verifying
last_updated: "2026-04-07T05:48:49.749Z"
last_activity: 2026-04-07
progress:
  total_phases: 28
  completed_phases: 19
  total_plans: 82
  completed_plans: 73
---

# Project State

## Project Reference

See: .eclusa/PROJECT.md (updated 2026-04-06)

**Core value:** Every artifact traces back to the root intent through an append-only ledger, and every decision is structurally separated from the work it evaluates.
**Current focus:** Phase 24 — dogfood

## Current Position

Phase: 24 (dogfood) — EXECUTING
Plan: 2 of 2
Status: Phase complete — ready for verification
Last activity: 2026-04-07

## Accumulated Context

v1.0: 7 phases. All 9 domain entities, executor, harness, SCC template, knowledge layer, adapters, back office UI.

v1.1: 7 phases (8-14). E2E verification across all components. Chat front door. Sessions UI polish. 30+ E2E tests.

v1.2: 5 phases (15-18 complete, 19 blocked). Model config (env-var resolution), stage output propagation (recursive CTE injection), SCC trigger (build mode + API), cascade pipeline UI. Phase 19 dogfood blocked by production gaps.

Adversarial code review (2026-04-06): 10 findings across 6 severity layers.
RFC contrast audit (2026-04-06): Zero artifacts, zero real gates, zero completed SCC runs, one actor, empty knowledge graph. Infrastructure solid, product unproven.

Key insight: the current development workflow (Claude as agent, Nathan as human) IS an instance of Eclusa running. Scaling from 1+1 to N+N is the production target.

v2.0: 5 phases (20-24). Dependency order: identity -> data integrity -> auth boundaries -> pipeline hardening -> dogfood. Each phase unblocks the next.

### Decisions

- v2.0: Major version because this is the production-readiness boundary
- v2.0: Logical priority order (foundation up), not time priority
- v2.0: Quality over time pressure -- refactor properly, the leverage is enormous
- v2.0: This is going to production for a real 50-person startup
- v2.0 phases: Identity first because everything else depends on knowing WHO. Integrity before auth because auth checks need correct data. Pipeline after auth because interactive Refine needs protected endpoints. Dogfood last as the integration proof.
- [Phase 23-pipeline-hardening]: Branch on scope_doc presence first (v2 path), refine_stage_id DB lookup second (v1 path), error+return on neither — surgical handler fix, no schema changes
- [Phase 23-pipeline-hardening]: snapshot_store optional in AmbiguityContext — None triggers direct UPDATE path for session pause, not a crash
- [Phase 23-pipeline-hardening]: ambiguityUp returns 'gate:<uuid>' string so calling agent knows the gate ID created
- [Phase 23]: System prompt expanded from 2-line stub to full questioning philosophy (~250 words) embedding all 6 questioning.md principles
- [Phase 23]: patch target for search_fn failure in tests is harness.refine_agent.hybrid_search (module-level import binding), not knowledge.search.hybrid_search
- [Phase 24-dogfood]: RegisterPage redirects to /cascades not /chat — URL wait pattern updated to /(cascades|chat|$)/
- [Phase 24-dogfood]: Used asyncio.timeout(350) over pytest.mark.timeout — pytest-timeout not in dev deps; inlined cleanup helpers from conftest for self-contained test file

### Pending Todos

None.

### Blockers/Concerns

- ~~BLOCKER (Phase 24):~~ **RESOLVED** — Model concurrency controller implemented. Per-model semaphore pool (GLM=2, Anthropic=5, configurable via MODEL_CONCURRENCY_* env vars). Stage revert-to-pending on dispatch failure (max 3 retries, then mark failed). Full 7-stage pipeline completes in ~3 minutes.
- GHC sidecar formalize stage: Docker CLI not available inside executor container — resolved with graceful skip (Phase 23)
- trace_chain.sql recursive CTE bug — fixed in Phase 21 (INTEG-02)
