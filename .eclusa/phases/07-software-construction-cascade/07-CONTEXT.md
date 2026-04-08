# Phase 7: Software Construction Cascade - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Six-stage Software Construction Cascade (SCC) template: Refine → Match → Cohere → Formalize → Derive → Generate. Each stage is a cascade stage dispatched by the executor. Formalize uses GHC as a structural gate (LLM drafts Haskell constraints, GHC verifies via `ghc -fno-code`). Fan-out evaluation fires between Refine and Match for intent validation. Claude Code backend harness type for external work sessions. This exercises the full platform end-to-end.

</domain>

<decisions>
## Implementation Decisions

### SCC template
- **D-01:** `create_scc_cascade(intent_id, actor_id, conn)` creates a cascade with 6 stages in dependency order
- **D-02:** Each stage has `stage_type='narrowing'` and `input` JSONB specifying the SCC stage type (refine/match/cohere/formalize/derive/generate)
- **D-03:** The executor's dispatch_narrowing reads `input.scc_stage` and routes to the appropriate handler
- **D-04:** Between Refine and Match, a fan-out stage is inserted for intent validation — divergence creates a gate

### Stage handlers
- **D-05:** Stage 1 (Refine): pydantic-ai work session — multi-turn conversation narrows intent to structured scope doc
- **D-06:** Stage 2 (Match): embedding lookup against schema commons via `search_schema_commons()` — returns matched source set
- **D-07:** Stage 3 (Cohere): pydantic-ai judgment pass — checks matched sources for composition issues (type boundaries, auth models, data friction)
- **D-08:** Stage 4 (Formalize): LLM drafts Haskell constraints, writes to tempfile, async subprocess calls `ghc -fno-code`, retries on type errors
- **D-09:** Stage 5 (Derive): pydantic-ai work session — generates BDD/E2E test specs from structure + compiled constraints
- **D-10:** Stage 6 (Generate): cheapest capable model — generates code that satisfies derived tests

### GHC sidecar
- **D-11:** GHC 9.10.x Docker container added to docker-compose.yml — not started per-invocation, runs as a persistent sidecar
- **D-12:** Executor calls GHC via `docker exec ghc ghc -fno-code /workspace/constraints.hs` (or similar subprocess pattern)
- **D-13:** Async subprocess — executor is not blocked during compilation; uses asyncio.create_subprocess_exec
- **D-14:** GHC type errors returned verbatim to the LLM for retry (max 5 iterations per research)
- **D-15:** Compiled constraints stored as artifacts linked to the cascade

### Claude Code harness
- **D-16:** Claude Code harness type: external backend process (not managed by executor)
- **D-17:** Proxy intercepts all Claude Code outbound calls — same proxy addon from Phase 3
- **D-18:** Message history captured in platform format via proxy → portable for hot-swap
- **D-19:** Claude Code sessions use the existing work_session table with `harness_type='claude_code'`

### Claude's Discretion
- Exact Haskell constraint template structure
- GHC container image tag and workspace mount path
- Retry backoff for GHC compilation failures
- BDD test format (Gherkin vs custom DSL vs plain pytest)
- How to determine "cheapest capable model" for Generate stage
- Claude Code backend process management (start/stop lifecycle)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SCC specification
- `eclusa.md` §7 — Software construction cascade: 6 stages, stage behaviors, fan-out placement
- `eclusa.md` §7.4 — Formalize stage: Haskell constraints, GHC verification
- `eclusa.md` §7.5 — Derive stage: BDD/E2E test derivation from structure + constraints
- `eclusa.md` §3.5.1 — Claude Code harness type specification

### Existing platform code
- `executor/dispatch.py` — dispatch_narrowing (extend for SCC routing)
- `executor/cascade.py` — cascade creation, stage management
- `harness/native.py` — Native harness (reference for Claude Code harness)
- `fan_out/dispatcher.py` — Fan-out evaluation (reuse for intent validation)
- `knowledge/search.py` — search_schema_commons (Match stage backend)
- `judgment/pass_.py` — Judgment pass (Cohere stage backend)
- `proxy/addon.py` — Artifact capture (reuse for Claude Code)

### Research findings
- `.eclusa/research/STACK.md` — GHC 9.10.x Docker sidecar, `-fno-code` flag
- `.eclusa/research/PITFALLS.md` — GHC cold-start overhead, LLM first-pass compile rate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `executor/dispatch.py:dispatch_narrowing()` — extend with SCC stage routing
- `harness/native.py` — work session lifecycle (Refine, Derive, Generate stages)
- `judgment/pass_.py` — single completion (Cohere stage)
- `fan_out/dispatcher.py` — parallel passes (intent validation fan-out)
- `knowledge/search.py:search_schema_commons()` — Match stage
- `proxy/addon.py` — artifact capture for Claude Code harness

### Established Patterns
- asyncpg for DB, Pydantic models, TDD, ledger entries for all state changes
- pydantic-ai Agent for work sessions and judgment passes

### Integration Points
- `executor/dispatch.py` — SCC routing added to existing dispatch
- `docker-compose.yml` — GHC sidecar service added
- `db/models/compute.py` — WorkSession.harness_type for Claude Code sessions

</code_context>

<specifics>
## Specific Ideas

- The SCC template is the most opinionated cascade shape — it exercises every platform primitive
- GHC doesn't hallucinate — the compiler IS the structural gate, not a model judging model output
- "Code is the last output" — 5 stages of narrowing before any code is generated
- The Claude Code harness proves the platform is harness-agnostic — not coupled to pydantic-ai

</specifics>

<deferred>
## Deferred Ideas

None — this is the final phase

</deferred>

---

*Phase: 07-software-construction-cascade*
*Context gathered: 2026-04-05*
