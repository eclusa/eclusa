# Phase 7: Software Construction Cascade - Research

**Researched:** 2026-04-05
**Domain:** Six-stage SCC template, GHC sidecar, Claude Code harness, fan-out intent validation
**Confidence:** HIGH (all platform code read directly; GHC tested via Docker exec; all patterns verified against existing codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SCC template:**
- D-01: `create_scc_cascade(intent_id, actor_id, conn)` creates a cascade with 6 stages in dependency order
- D-02: Each stage has `stage_type='narrowing'` and `input` JSONB specifying the SCC stage type (refine/match/cohere/formalize/derive/generate)
- D-03: The executor's dispatch_narrowing reads `input.scc_stage` and routes to the appropriate handler
- D-04: Between Refine and Match, a fan-out stage is inserted for intent validation — divergence creates a gate

**Stage handlers:**
- D-05: Stage 1 (Refine): pydantic-ai work session — multi-turn conversation narrows intent to structured scope doc
- D-06: Stage 2 (Match): embedding lookup against schema commons via `search_schema_commons()` — returns matched source set
- D-07: Stage 3 (Cohere): pydantic-ai judgment pass — checks matched sources for composition issues (type boundaries, auth models, data friction)
- D-08: Stage 4 (Formalize): LLM drafts Haskell constraints, writes to tempfile, async subprocess calls `ghc -fno-code`, retries on type errors
- D-09: Stage 5 (Derive): pydantic-ai work session — generates BDD/E2E test specs from structure + compiled constraints
- D-10: Stage 6 (Generate): cheapest capable model — generates code that satisfies derived tests

**GHC sidecar:**
- D-11: GHC 9.10.x Docker container added to docker-compose.yml — not started per-invocation, runs as a persistent sidecar
- D-12: Executor calls GHC via `docker exec ghc ghc -fno-code /workspace/constraints.hs` (or similar subprocess pattern)
- D-13: Async subprocess — executor is not blocked during compilation; uses asyncio.create_subprocess_exec
- D-14: GHC type errors returned verbatim to the LLM for retry (max 5 iterations per research)
- D-15: Compiled constraints stored as artifacts linked to the cascade

**Claude Code harness:**
- D-16: Claude Code harness type: external backend process (not managed by executor)
- D-17: Proxy intercepts all Claude Code outbound calls — same proxy addon from Phase 3
- D-18: Message history captured in platform format via proxy — portable for hot-swap
- D-19: Claude Code sessions use the existing work_session table with `harness_type='claude_code'`

### Claude's Discretion
- Exact Haskell constraint template structure
- GHC container image tag and workspace mount path
- Retry backoff for GHC compilation failures
- BDD test format (Gherkin vs custom DSL vs plain pytest)
- How to determine "cheapest capable model" for Generate stage
- Claude Code backend process management (start/stop lifecycle)

### Deferred Ideas (OUT OF SCOPE)
None — this is the final phase.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCC-01 | Six-stage cascade template: Refine → Match → Cohere → Formalize → Derive → Generate | `create_scc_cascade()` creates stages in dependency order using existing `cascade.py` patterns |
| SCC-02 | Stage 1 (Refine): multi-turn conversation narrows noisy intent to refined scope doc | `start_work_session()` + `run_session_turn()` from `harness/native.py` — same pattern as Phase 3 |
| SCC-03 | Stage 2 (Match): embedding lookup against schema commons returns matched source set | `search_schema_commons()` in `knowledge/search.py` is already implemented and ready to call |
| SCC-04 | Stage 3 (Cohere): check matched sources for composition issues | `run_judgment_pass()` + `create_judgment_pass_record()` from `judgment/pass_.py` — same pattern as Phase 3 |
| SCC-05 | Stage 4 (Formalize): LLM drafts Haskell constraints, GHC verifies via `ghc -fno-code` | New: `harness/formalize.py` — async subprocess calling `docker exec ghc-sidecar ghc -fno-code` |
| SCC-06 | Stage 5 (Derive): derive BDD/E2E tests from structure + compiled constraints | `start_work_session()` + `run_session_turn()` from `harness/native.py` — Derive is a work session |
| SCC-07 | Stage 6 (Generate): cheapest capable model generates code that passes all derived tests | `start_work_session()` + `run_session_turn()` from `harness/native.py` — Generate is also a work session |
| SCC-08 | Fan-out evaluation between stages (intent validation after Refine) | `run_fan_out_with_db()` from `fan_out/db.py` — already handles full fan-out lifecycle |
| WORK-07 | Claude Code harness type: external backend with proxy and history capture | New: `harness/claude_code.py` — `start_claude_code_session()` creates `work_session` with `harness_type='claude_code'` |
</phase_requirements>

---

## Summary

Phase 7 is the final platform phase. It assembles a six-stage Software Construction Cascade (SCC) template using exclusively the platform primitives built in Phases 1–6. The only genuinely new infrastructure is the GHC sidecar (Docker container for Haskell constraint verification) and the Claude Code harness type. Everything else — work sessions, judgment passes, fan-out evaluation, schema commons search — is already implemented and callable.

**The architecture is an integration problem, not a construction problem.** The Refine, Match, Cohere, Derive, and Generate stages wire together existing platform code. The Formalize stage is the only stage requiring new logic: async subprocess dispatch to GHC via `docker exec`. The Claude Code harness (WORK-07) creates a `work_session` record with `harness_type='claude_code'` — no new DB schema required, `harness_type` is already a free-text column.

The primary risk in this phase is the GHC retry loop in the Formalize stage. Research verified the retry behavior first-hand: GHC 9.10.1 via `docker exec` on a persistent sidecar compiles in ~190ms (not the 500ms–3s warning in PITFALLS.md — that figure applied to cold `docker run` invocations, not persistent sidecars). The LLM-first-pass compile failure rate is the unknown that must be measured during implementation.

**Primary recommendation:** Build in the dependency order the executor enforces — stage template first, then SCC routing in dispatch_narrowing, then each stage handler, then GHC sidecar, then Claude Code harness. Test each handler independently before wiring the full cascade.

---

## Standard Stack

### Core (all from CLAUDE.md — already in pyproject.toml)

| Library | Version | Purpose | Phase 7 Use |
|---------|---------|---------|-------------|
| pydantic-ai | 1.77.0 | Agent harness for Refine, Derive, Generate, Cohere | Already used in harness/native.py and judgment/pass_.py |
| asyncpg | 0.31.0 | Async Postgres driver | All DB writes in handlers |
| Python asyncio | stdlib 3.12 | Async subprocess for GHC | `asyncio.create_subprocess_exec` for `docker exec ghc` |
| mitmproxy | 11.x | Proxy addon for artifact capture | Claude Code sessions route through existing proxy/addon.py |

### New (no new packages required)

All Phase 7 functionality is achievable with the existing dependency set. No new `uv add` calls needed.

**Key confirmation:** `harness_type` in `work_session` is `sa.Text` (not an enum) — `'claude_code'` value works without a migration. Verified in `alembic/versions/0001_initial_schema.py` line 190.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
executor/
└── scc.py             # create_scc_cascade() + SCC routing in dispatch_narrowing
harness/
├── formalize.py       # GHC sidecar async dispatch (Formalize stage)
└── claude_code.py     # Claude Code work session start/lifecycle (WORK-07)
tests/
├── test_scc_template.py     # SCC-01: create_scc_cascade creates 6 stages
├── test_scc_refine.py       # SCC-02: Refine stage handler
├── test_scc_match.py        # SCC-03: Match stage (search_schema_commons)
├── test_scc_cohere.py       # SCC-04: Cohere stage (judgment pass)
├── test_scc_formalize.py    # SCC-05: GHC subprocess dispatch
├── test_scc_derive.py       # SCC-06: Derive stage handler
├── test_scc_generate.py     # SCC-07: Generate stage handler
├── test_scc_fanout.py       # SCC-08: Fan-out after Refine
└── test_claude_code_harness.py  # WORK-07: Claude Code session lifecycle
docker-compose.yml     # add ghc sidecar service
```

### Pattern 1: SCC Cascade Creation (D-01, D-02)

The cascade creation function inserts 6 stages with `input.scc_stage` routing keys and `depends_on` edges in dependency order. The fan-out stage (D-04) sits between Refine and Match — it is stage type `narrowing` with `input.scc_stage = 'intent_validation_fanout'`.

```python
# Source: executor/scc.py (new file), pattern from executor/cascade.py
async def create_scc_cascade(intent_id: str, actor_id: str, conn: asyncpg.Connection) -> str:
    cascade_id = str(uuid.uuid4())

    # Stage input JSONB per D-02: 'scc_stage' is the routing key for D-03
    # Dependency order: refine -> fanout -> match -> cohere -> formalize -> derive -> generate
    # (7 stages total: 6 SCC + 1 fan-out stage)

    async with conn.transaction():
        await conn.execute("""
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{}', 'active')
        """, cascade_id, intent_id)
        # Insert stages with correct depends_on arrays
        # Returns cascade_id
    return cascade_id
```

**Stage count clarification:** The spec says "6 stages" (Refine, Match, Cohere, Formalize, Derive, Generate). D-04 inserts a fan-out stage between Refine and Match. The cascade has 7 DB stage records: 6 SCC stages + 1 intent validation fan-out stage. All are `stage_type='narrowing'`.

### Pattern 2: SCC Routing in dispatch_narrowing (D-03)

`dispatch_narrowing` in `executor/dispatch.py` is currently a Phase 2 stub that resolves immediately. Phase 7 replaces this with an SCC router that reads `input.scc_stage` from the stage record.

```python
# Source: executor/dispatch.py — extend existing dispatch_narrowing
async def dispatch_narrowing(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    stage_input = stage.get("input") or {}
    scc_stage = stage_input.get("scc_stage")

    if scc_stage == "refine":
        await dispatch_scc_refine(conn, stage, actor_id)
    elif scc_stage == "intent_validation_fanout":
        await dispatch_scc_fanout(conn, stage, actor_id)
    elif scc_stage == "match":
        await dispatch_scc_match(conn, stage, actor_id)
    elif scc_stage == "cohere":
        await dispatch_scc_cohere(conn, stage, actor_id)
    elif scc_stage == "formalize":
        await dispatch_scc_formalize(conn, stage, actor_id)
    elif scc_stage == "derive":
        await dispatch_scc_derive(conn, stage, actor_id)
    elif scc_stage == "generate":
        await dispatch_scc_generate(conn, stage, actor_id)
    else:
        # Non-SCC narrowing stages — mark resolved immediately (legacy behavior)
        await _resolve_stage_immediately(conn, stage, actor_id)
```

### Pattern 3: GHC Sidecar Async Dispatch (D-11, D-12, D-13)

**Verified behavior:** `docker exec` on a persistent GHC container compiles `ghc -fno-code` in ~190ms (measured in research). The container is volume-mounted to a shared `/workspace` directory. The executor writes the LLM-generated `.hs` file to a tempfile in that volume, then calls `docker exec`.

```python
# Source: harness/formalize.py (new file)
# D-13: asyncio.create_subprocess_exec — non-blocking
import asyncio
import tempfile
import os
from pathlib import Path

GHC_CONTAINER_NAME = "ghc-sidecar"
GHC_WORKSPACE = "/workspace"  # mounted volume path inside container
GHC_TIMEOUT_SECONDS = 10       # D-13 enforcement: fail fast, not hang
GHC_MAX_RETRIES = 5            # D-14: max 5 iterations per formalize attempt

async def verify_constraints_with_ghc(haskell_source: str) -> tuple[bool, str]:
    """Write haskell_source to tempfile, call ghc -fno-code via docker exec.

    Returns (success: bool, output: str).
    output contains stdout+stderr — pass verbatim to LLM on failure (D-14).
    """
    # Write to shared volume
    with tempfile.NamedTemporaryFile(
        dir="/path/to/shared/workspace",
        suffix=".hs",
        delete=False,
        mode="w",
    ) as f:
        f.write(haskell_source)
        local_path = f.name

    container_path = os.path.join(GHC_WORKSPACE, os.path.basename(local_path))

    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", GHC_CONTAINER_NAME,
            "ghc", "-fno-code", container_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=GHC_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            return False, "GHC compilation timed out"

        output = (stdout + stderr).decode("utf-8", errors="replace")
        return proc.returncode == 0, output
    finally:
        Path(local_path).unlink(missing_ok=True)
```

**Critical: workspace mount strategy.** The `ghc-sidecar` service in docker-compose.yml needs a volume mount that the Python executor can also write to. Use a named Docker volume (e.g., `ghc_workspace`) mounted at the same path in both the sidecar and executor containers. This is the simplest cross-container file sharing approach with no network boundary.

### Pattern 4: Claude Code Harness (WORK-07, D-16..D-19)

The `work_session` table's `harness_type` column is free-text (not an enum). No migration needed. The Claude Code harness follows the same `start_work_session` → `run_session_turn` → `complete_work_session` lifecycle as the native harness, but with `harness_type='claude_code'`.

```python
# Source: harness/claude_code.py (new file)
# D-19: same work_session table, harness_type='claude_code'
async def start_claude_code_session(
    conn: asyncpg.Connection,
    stage_id: str,
    intent_id: str,
    cascade_id: str,
    model: str,
    actor_id: str,
    addon: Any = None,
) -> str:
    """Create work_session with harness_type='claude_code'.

    Identical to start_work_session() except harness_type value.
    Proxy registration is the same (D-17): same addon.register_session().
    """
    session_id = str(uuid.uuid4())
    async with conn.transaction():
        await conn.execute("""
            INSERT INTO work_session (id, stage_ids, harness_type, model, state, cost)
            VALUES ($1::uuid, ARRAY[$2::uuid], 'claude_code', $3, 'running', '{}')
        """, session_id, stage_id, model)
        # ledger entry same as native...
    if addon is not None:
        addon.register_session(session_id, {"intent_id": intent_id, ...})
    return session_id
```

**Claude Code process management** (Claude's Discretion): The decision says Claude Code is an "external backend process (not managed by executor)." For Phase 7, the simplest correct implementation is: the Claude Code session is tracked in the DB but the executor does not start/stop the Claude Code process directly. The session record in `work_session` captures history written by the Claude Code process via the proxy. If Claude Code isn't running, the stage stays `active` until it connects.

### Pattern 5: Fan-out Intent Validation (SCC-08, D-04)

The fan-out stage between Refine and Match uses `run_fan_out_with_db()` from `fan_out/db.py` — already fully implemented. The Refine stage writes its output (refined scope doc) to `stage.output` JSONB. The fan-out stage reads this, prepares context, and fires n judgment passes asking "does this faithfully represent the original intent?"

```python
# Source: fan_out/db.py — run_fan_out_with_db() already handles everything
# The SCC fan-out handler just needs to:
#   1. Read Refine stage output from DB
#   2. Prepare context: refined_doc + original raw intent
#   3. Call run_fan_out_with_db() with the intent_validation prompt
async def dispatch_scc_fanout(conn: asyncpg.Connection, stage: dict, actor_id: str) -> None:
    stage_input = stage.get("input") or {}
    refine_stage_id = stage_input.get("refine_stage_id")
    raw_intent = stage_input.get("raw_intent", "")

    refine_output = await conn.fetchval(
        "SELECT output FROM stage WHERE id = $1::uuid", refine_stage_id
    )
    prepared_context = f"Original intent:\n{raw_intent}\n\nRefined scope doc:\n{refine_output}"
    context_hash = hash_context(prepared_context)

    models = stage_input.get("fanout_models", ["anthropic:claude-3-5-haiku-latest"])
    prompt = "Does the refined scope doc faithfully represent the original intent? List any missed requirements."

    await run_fan_out_with_db(
        conn=conn,
        stage_id=str(stage["id"]),
        models=models,
        prepared_context=prepared_context,
        prompt=prompt,
        context_hash=context_hash,
        actor_id=actor_id,
    )
```

### Pattern 6: GHC Docker Compose Service (D-11)

```yaml
# Source: docker-compose.yml — add to existing services
  ghc:
    image: haskell:9.10.1
    container_name: ghc-sidecar      # named for docker exec -t ghc-sidecar
    command: ["sleep", "infinity"]   # persistent sidecar
    volumes:
      - ghc_workspace:/workspace     # shared with executor
    restart: unless-stopped

# In executor service, add volume mount:
    volumes:
      - ghc_workspace:/workspace

volumes:
  pg_data:
  ghc_workspace:                     # new shared volume
```

### Anti-Patterns to Avoid

- **Using `docker run` per invocation instead of `docker exec`:** Cold `docker run` adds 600ms overhead. The persistent sidecar with `docker exec` is ~190ms (verified). D-11 specifies persistent sidecar for this reason.
- **Blocking the executor on GHC compilation:** `asyncio.create_subprocess_exec` + `asyncio.wait_for` with a 10s timeout is the correct pattern. Never `subprocess.run()` (blocks event loop).
- **Storing harness_type as a new enum:** The column is free-text. No migration needed for `'claude_code'`.
- **Building a new fan-out implementation for intent validation:** `run_fan_out_with_db()` already handles all fan-out logic including DB persistence, convergence detection, and gate surfacing. Use it directly.
- **Putting cascade creation logic in dispatch_narrowing:** `create_scc_cascade()` is called by the application layer (API endpoint or orchestrator) when an intent needs an SCC cascade. It is not called by the executor.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fan-out evaluation after Refine | Custom parallel pass logic | `run_fan_out_with_db()` in `fan_out/db.py` | Full lifecycle: passes, convergence, gate surfacing — already implemented |
| Schema commons matching in Match stage | Custom embedding search | `search_schema_commons()` in `knowledge/search.py` | Hybrid cosine + BM25 + BFS already wired |
| Judgment pass for Cohere stage | Custom API call | `run_judgment_pass()` + `create_judgment_pass_record()` in `judgment/pass_.py` | Structured verdict, ledger entry, context hash — done |
| Work session lifecycle for Refine/Derive/Generate | Custom harness loop | `start_work_session()`, `run_session_turn()`, `complete_work_session()` in `harness/native.py` | Proxy registration, cost tracking, pause/resume — done |
| Cascade stage dependency graph | Custom stage creation | Pattern from `tests/helpers/topology.py` `seed_linear_cascade()` | Use `depends_on` ARRAY — already tested against the schema |
| Haskell type-checking | Custom Haskell interpreter or alternative language | `ghc -fno-code` via Docker exec | GHC doesn't hallucinate — the compiler IS the structural gate |
| GHC error parsing | Structured error extraction | Pass verbatim GHC output to LLM (D-14) | PITFALLS.md §Pitfall 7: LLMs handle raw GHC errors better than parsed summaries |

---

## Common Pitfalls

### Pitfall 1: GHC Workspace Mount Not Shared with Executor Container

**What goes wrong:** The executor writes a `.hs` tempfile to a local path, but the path is not the Docker volume mounted into the GHC container. GHC `docker exec` cannot find the file. Error: `Can't find /workspace/constraints.hs` (reproduced during research).

**Why it happens:** The executor runs inside a Docker container. The GHC sidecar is a separate Docker container. File sharing requires a named Docker volume, not a host-path temp directory.

**How to avoid:** Use a Docker named volume (`ghc_workspace`) mounted at `/workspace` in both the GHC sidecar and the executor service. Executor writes `.hs` files to `/workspace/` which is the shared volume. GHC sidecar reads from `/workspace/`.

**Warning signs:** `Can't find` error in GHC output. Tempfile created in `/tmp` on executor host.

### Pitfall 2: Fan-out Stage Dependencies Incorrect in `create_scc_cascade()`

**What goes wrong:** If the fan-out stage depends on the wrong upstream stage (or has no `depends_on`), the executor may fire intent validation before Refine completes, or the fan-out stage's `stage_input` won't have the Refine output to read.

**How to avoid:** The dependency chain must be: `refine_stage_id → fanout_stage_id → match_stage_id`. The fanout stage's `input` JSONB must include `refine_stage_id` so the handler knows where to read the Refine output from.

**Warning signs:** Fan-out fires with empty or null Refine output. Match stage starts before intent validation completes.

### Pitfall 3: GHC Type Errors Contain Tempfile Paths in Output

**What goes wrong:** GHC error messages include the file path (`/workspace/tmp_abc123.hs:6:26: error...`). The LLM retry prompt should strip or replace this path with a stable name to avoid confusing the model with changing paths across retries.

**How to avoid:** Normalize the file path in GHC error output before passing to LLM. Replace the tempfile path with `constraints.hs` (or simply strip it). The error content (line/column, type message) is what matters.

### Pitfall 4: SCC Routing Falls Through to Phase 2 Stub

**What goes wrong:** `dispatch_narrowing` currently resolves ALL narrowing stages immediately (Phase 2 stub). If the `scc_stage` routing condition is not exhaustive, any unrecognized `scc_stage` value silently auto-resolves, making the SCC appear to complete instantly without doing any work.

**How to avoid:** After adding SCC routing, include a fallback branch that handles non-SCC narrowing stages (for backward compatibility with test fixtures) AND an explicit error/warning for unrecognized `scc_stage` values. Tests for each stage handler must verify that the stage does NOT resolve immediately but performs actual work.

### Pitfall 5: GHC Concurrent Invocations Without Semaphore

**What goes wrong:** If multiple Formalize stages run simultaneously (multiple SCC cascades), multiple GHC processes run inside the sidecar container simultaneously. GHC is memory-heavy. Without a semaphore, concurrent compilation requests can OOM the sidecar.

**How to avoid:** Use `asyncio.Semaphore(max_concurrent=3)` at the `dispatch_scc_formalize` level. Queue excess Formalize dispatches to wait for a semaphore slot. This is per-executor-process; in a multi-executor setup the effective limit is `3 × executor_count`.

### Pitfall 6: Claude Code Harness Has No Active History Capture Without Proxy

**What goes wrong:** The Claude Code session's `message_history` in `work_session` only captures what the proxy intercepts. If Claude Code is running with `NO_PROXY` set or the proxy isn't intercepting the correct endpoint, message history is empty. WORK-07 requires that history be captured in platform format — this only works if the proxy is correctly configured for Claude Code's outbound calls.

**How to avoid:** Verify that the Claude Code process routes through the mitmproxy (check `HTTP_PROXY`/`HTTPS_PROXY` env vars are set for the Claude Code process). The existing `proxy/addon.py` handles capture once sessions are registered.

---

## GHC Sidecar: Verified Facts

All GHC behavior was verified directly in this research session.

### Verified: GHC Version

| Version | Docker Image | Status |
|---------|-------------|--------|
| GHC 9.8.4 | `haskell:9.8-slim` | Available locally |
| GHC 9.10.1 | `haskell:9.10.1` | Pulled and verified |

**Decision D-11 specifies 9.10.x — use `haskell:9.10.1`.**

### Verified: Compilation Performance

| Invocation Pattern | Time | Notes |
|-------------------|------|-------|
| `docker run --rm haskell:9.10.1 ghc -fno-code` | ~625ms | Cold container creation overhead |
| `docker exec ghc-sidecar ghc -fno-code` (persistent) | ~190ms | D-12 persistent sidecar pattern |

**Implication:** The persistent sidecar pattern (D-11) reduces compilation latency from ~625ms to ~190ms. The Formalize stage retry loop of up to 5 iterations (D-14) takes at most ~1 second total for GHC verification alone.

### Verified: Error Output Format

GHC type errors are structured and machine-readable:
```
/workspace/constraints.hs:6:26: error: [GHC-83865]
    • Couldn't match type '[Char]' with 'Int'
      Expected: Int
        Actual: String
    • In the expression: s
      In an equation for 'badFunction': badFunction (UserId s) = s
  |
6 | badFunction (UserId s) = s
  |                          ^
```

**Implication:** Pass verbatim to LLM (D-14). The error code `[GHC-83865]`, the type mismatch explanation, and the source location are all present. LLMs handle this format well without parsing.

### Verified: `ghc -fno-code` Behavior

- **Exit code 0:** Compilation successful (type-checks). No object files written.
- **Exit code 1:** Compilation failed. Errors on stderr.
- **The flag:** `-fno-code` performs type-checking without emitting object code or interface files. This is the correct flag for constraint verification.

### Verified: File Transport Pattern

`docker cp` is NOT the right approach for the persistent sidecar. The shared volume mount is the correct approach:

```
Executor container: writes /workspace/tmp_XXXX.hs
GHC sidecar: reads /workspace/tmp_XXXX.hs via docker exec
```

Both containers mount the same named Docker volume at `/workspace`.

---

## Claude Code Harness: Architecture

### WORK-07 Implementation Scope

The WORK-07 requirement is: "Claude Code harness type: external backend with proxy and history capture." The minimal complete implementation:

1. `harness/claude_code.py` — `start_claude_code_session()` function that creates `work_session` with `harness_type='claude_code'`
2. The proxy intercepts Claude Code outbound calls the same way it does for native sessions (D-17) — no proxy changes needed
3. Message history is written to `work_session.message_history` by the proxy capture path (D-18)
4. No new DB schema — `harness_type` is free-text, `'claude_code'` is a valid value without migration (verified)

### What "External Backend" Means for Phase 7

Per D-16: "Claude Code harness type: external backend process (not managed by executor)." This means:

- The executor creates the DB record (`work_session` row) and registers it with the proxy
- The executor does NOT launch/stop the Claude Code process
- The Claude Code process connects and works; proxy captures all calls
- The executor marks the session complete when the stage completes externally

For the purposes of Phase 7 testing, `harness_type='claude_code'` sessions can be tested using the same `TestModel` pattern as native sessions — the harness type is metadata for traceability (WORK-07's core requirement), not a process management difference.

---

## Code Examples

### Create SCC Cascade (SCC-01)

```python
# Source: executor/scc.py (new) — follows pattern from tests/helpers/topology.py
import uuid
import asyncpg

async def create_scc_cascade(
    intent_id: str,
    actor_id: str,
    conn: asyncpg.Connection,
    raw_intent: str = "",
    fanout_models: list[str] | None = None,
) -> dict:
    """Create a 7-stage SCC cascade (6 SCC + 1 fan-out) and return stage IDs.

    Stages in dependency order:
      1. refine       — Stage 1: Refine (work session)
      2. fanout       — Intent validation fan-out (between Refine and Match) [D-04]
      3. match        — Stage 2: Match (schema commons search)
      4. cohere       — Stage 3: Cohere (judgment pass)
      5. formalize    — Stage 4: Formalize (GHC verification)
      6. derive       — Stage 5: Derive (work session)
      7. generate     — Stage 6: Generate (work session, cheapest model)
    """
    cascade_id = str(uuid.uuid4())
    if fanout_models is None:
        fanout_models = ["anthropic:claude-3-5-haiku-latest"]

    async with conn.transaction():
        await conn.execute("""
            INSERT INTO cascade (id, intent_id, shape, state)
            VALUES ($1::uuid, $2::uuid, '{}', 'active')
        """, cascade_id, intent_id)

        # Stage 1: Refine
        refine_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending', '{}',
                    $3::jsonb)
        """, refine_id, cascade_id,
            json.dumps({"scc_stage": "refine", "raw_intent": raw_intent}))

        # Fan-out stage (intent validation, D-04)
        fanout_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending',
                    ARRAY[$3::uuid], $4::jsonb)
        """, fanout_id, cascade_id, refine_id,
            json.dumps({
                "scc_stage": "intent_validation_fanout",
                "refine_stage_id": refine_id,
                "raw_intent": raw_intent,
                "fanout_models": fanout_models,
            }))

        # Stage 2: Match
        match_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending',
                    ARRAY[$3::uuid], $4::jsonb)
        """, match_id, cascade_id, fanout_id,
            json.dumps({"scc_stage": "match", "refine_stage_id": refine_id}))

        # Stage 3: Cohere
        cohere_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending',
                    ARRAY[$3::uuid], $4::jsonb)
        """, cohere_id, cascade_id, match_id,
            json.dumps({"scc_stage": "cohere", "match_stage_id": match_id}))

        # Stage 4: Formalize
        formalize_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending',
                    ARRAY[$3::uuid], $4::jsonb)
        """, formalize_id, cascade_id, cohere_id,
            json.dumps({"scc_stage": "formalize", "cohere_stage_id": cohere_id}))

        # Stage 5: Derive
        derive_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending',
                    ARRAY[$3::uuid], $4::jsonb)
        """, derive_id, cascade_id, formalize_id,
            json.dumps({"scc_stage": "derive", "formalize_stage_id": formalize_id}))

        # Stage 6: Generate
        generate_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO stage (id, cascade_id, type, state, depends_on, input)
            VALUES ($1::uuid, $2::uuid, 'narrowing', 'pending',
                    ARRAY[$3::uuid], $4::jsonb)
        """, generate_id, cascade_id, derive_id,
            json.dumps({"scc_stage": "generate", "derive_stage_id": derive_id}))

    return {
        "cascade_id": cascade_id,
        "stage_ids": {
            "refine": refine_id,
            "intent_validation_fanout": fanout_id,
            "match": match_id,
            "cohere": cohere_id,
            "formalize": formalize_id,
            "derive": derive_id,
            "generate": generate_id,
        },
    }
```

### GHC Formalize Stage Handler (SCC-05)

```python
# Source: harness/formalize.py (new file)
# asyncio.create_subprocess_exec per D-13; verbatim errors per D-14; max 5 retries per D-14
import asyncio
import json
import tempfile
import uuid
from pathlib import Path

import asyncpg
from pydantic_ai import Agent

GHC_CONTAINER_NAME = "ghc-sidecar"
GHC_WORKSPACE_HOST = "/workspace"   # host path to Docker named volume
GHC_WORKSPACE_CONTAINER = "/workspace"  # same path inside GHC container
GHC_TIMEOUT_SECONDS = 10
GHC_MAX_RETRIES = 5
GHC_SEMAPHORE = asyncio.Semaphore(3)  # max 3 concurrent GHC invocations

CONSTRAINT_DRAFT_PROMPT = """
You are a Haskell type system expert. Given the following source schema definitions and business rules,
draft a Haskell module named 'Constraints' that encodes the constraints as types and functions.
Use -fno-code-compatible Haskell only (no TemplateHaskell, no external packages beyond base).

Source schemas:
{cohere_output}

Business rules:
{business_rules}

Return ONLY the Haskell module source code, starting with 'module Constraints where'.
"""

async def run_formalize_stage(
    conn: asyncpg.Connection,
    stage: dict,
    actor_id: str,
    llm_model: str = "anthropic:claude-sonnet-4-5",
) -> None:
    """Formalize stage: LLM drafts Haskell, GHC verifies, retry up to 5 times.

    On success: writes constraint source to stage.output, marks resolved.
    On failure after max retries: marks stage failed.
    """
    stage_input = stage.get("input") or {}
    cohere_stage_id = stage_input.get("cohere_stage_id")

    cohere_output = await conn.fetchval(
        "SELECT output FROM stage WHERE id = $1::uuid", cohere_stage_id
    )

    agent = Agent(llm_model)
    last_error = ""
    haskell_source = ""

    for attempt in range(GHC_MAX_RETRIES):
        if attempt == 0:
            prompt = CONSTRAINT_DRAFT_PROMPT.format(
                cohere_output=cohere_output or "",
                business_rules=stage_input.get("business_rules", ""),
            )
        else:
            # D-14: pass verbatim GHC errors back to LLM
            prompt = (
                f"The previous Haskell constraints failed to compile:\n\n"
                f"```haskell\n{haskell_source}\n```\n\n"
                f"GHC error output:\n```\n{last_error}\n```\n\n"
                f"Fix the type errors and return the corrected module."
            )

        result = await agent.run(prompt)
        haskell_source = result.output.strip()

        async with GHC_SEMAPHORE:
            success, ghc_output = await _invoke_ghc(haskell_source)

        if success:
            # D-15: store compiled constraints as artifact + mark stage resolved
            await _store_constraint_artifact(conn, stage, haskell_source, actor_id)
            await conn.execute("""
                UPDATE stage SET state = 'resolved', resolved_at = NOW(),
                    resolved_by = $1::uuid,
                    output = $2::jsonb
                WHERE id = $3::uuid
            """, actor_id,
                json.dumps({"haskell_source": haskell_source, "attempts": attempt + 1}),
                str(stage["id"]))
            return

        last_error = ghc_output

    # Max retries exhausted — mark stage failed
    await conn.execute("""
        UPDATE stage SET state = 'failed' WHERE id = $1::uuid
    """, str(stage["id"]))


async def _invoke_ghc(haskell_source: str) -> tuple[bool, str]:
    """Write haskell_source to shared volume, invoke GHC via docker exec."""
    fname = f"constraints_{uuid.uuid4().hex[:8]}.hs"
    host_path = Path(GHC_WORKSPACE_HOST) / fname
    container_path = f"{GHC_WORKSPACE_CONTAINER}/{fname}"

    host_path.write_text(haskell_source, encoding="utf-8")
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", GHC_CONTAINER_NAME,
            "ghc", "-fno-code", container_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=GHC_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            return False, "GHC compilation timed out after 10s"

        combined = (stdout + stderr).decode("utf-8", errors="replace")
        # Normalize tempfile path in error output (Pitfall 3)
        normalized = combined.replace(container_path, "constraints.hs")
        return proc.returncode == 0, normalized
    finally:
        host_path.unlink(missing_ok=True)
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | GHC sidecar, `docker exec` | Yes | Docker 29.2.1 | No fallback — GHC sidecar is the gate |
| Python 3.12 | asyncio.create_subprocess_exec | Yes | 3.12.8 | — |
| GHC 9.10.1 Docker image | Formalize stage | Yes (pulled) | haskell:9.10.1, GHC 9.10.1 | — |
| pydantic-ai 1.77.0 | Refine, Cohere, Derive, Generate stages | Yes (pyproject.toml) | 1.77.0 | — |
| asyncpg 0.31.0 | All DB writes | Yes (pyproject.toml) | 0.31.0 | — |
| Postgres (testcontainers) | Tests | Yes (paradedb/paradedb:latest) | PG18 via ParadeDB | — |

**No missing dependencies.** All required tools are available.

**GHC sidecar timing note:** `docker exec` on a persistent container = ~190ms per compilation. `docker run --rm` per invocation = ~625ms. The persistent sidecar pattern (D-11) is the correct choice, verified.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-asyncio |
| Config file | `pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `uv run pytest tests/test_scc_template.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCC-01 | `create_scc_cascade()` creates 7 stages with correct dependencies | unit | `uv run pytest tests/test_scc_template.py -x` | No — Wave 0 |
| SCC-02 | Refine stage handler calls native work session, writes output | unit | `uv run pytest tests/test_scc_refine.py -x` | No — Wave 0 |
| SCC-03 | Match stage handler calls `search_schema_commons()`, writes output | unit | `uv run pytest tests/test_scc_match.py -x` | No — Wave 0 |
| SCC-04 | Cohere stage handler calls `run_judgment_pass()`, writes verdict | unit | `uv run pytest tests/test_scc_cohere.py -x` | No — Wave 0 |
| SCC-05 | Formalize stage: LLM draft → GHC verify → retry on failure | unit (mock GHC subprocess) | `uv run pytest tests/test_scc_formalize.py -x` | No — Wave 0 |
| SCC-06 | Derive stage handler calls native work session with constraint input | unit | `uv run pytest tests/test_scc_derive.py -x` | No — Wave 0 |
| SCC-07 | Generate stage handler runs cheapest capable model, writes code | unit | `uv run pytest tests/test_scc_generate.py -x` | No — Wave 0 |
| SCC-08 | Fan-out fires after Refine, convergence auto-resolves, divergence gates | unit | `uv run pytest tests/test_scc_fanout.py -x` | No — Wave 0 |
| WORK-07 | `start_claude_code_session()` creates `work_session` with `harness_type='claude_code'` | unit | `uv run pytest tests/test_claude_code_harness.py -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_scc_template.py tests/test_scc_refine.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/eclusa:verify-work`

### Wave 0 Gaps

- `tests/test_scc_template.py` — covers SCC-01 (cascade creation, stage count, dependency order)
- `tests/test_scc_refine.py` — covers SCC-02
- `tests/test_scc_match.py` — covers SCC-03
- `tests/test_scc_cohere.py` — covers SCC-04
- `tests/test_scc_formalize.py` — covers SCC-05 (mock `asyncio.create_subprocess_exec`)
- `tests/test_scc_derive.py` — covers SCC-06
- `tests/test_scc_generate.py` — covers SCC-07
- `tests/test_scc_fanout.py` — covers SCC-08
- `tests/test_claude_code_harness.py` — covers WORK-07

**No new framework install needed** — pytest + pytest-asyncio + testcontainers are already in `pyproject.toml`.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 7 |
|-----------|-------------------|
| Python 3.12+ | Already in use — no action |
| `uv add` not `pip install` | If new packages needed — none are for this phase |
| asyncpg for executor hot path | All stage handler DB writes use asyncpg |
| pydantic-ai for harness | Refine, Cohere, Derive, Generate all use `Agent` from pydantic-ai |
| No LangChain/LangGraph | Not applicable |
| Single Postgres instance | All state in existing DB — no new services |
| `docker-compose up` bootstrap | GHC sidecar added to docker-compose.yml as a service |
| `ruff check . && ruff format .` | Apply to all new files |
| `pyright` strict mode | Type annotations required on all new functions |
| `asyncio_mode = "auto"` | Already in pytest.ini — all test coroutines auto-detected |

---

## Open Questions

1. **LLM first-pass Haskell compile success rate**
   - What we know: PITFALLS.md flags this as LOW-confidence. Haskell discourse community reports vary widely.
   - What's unclear: What is the actual first-pass compile rate for an LLM given a clear type-annotated prompt? Below 70% would suggest the constraint template needs work before the gate is useful.
   - Recommendation: Measure during implementation. Track `attempts` in stage output JSONB. If first-pass rate is below 70% after 10 real SCC runs, revisit the Haskell prompt template.

2. **Cheapest capable model for Generate stage (D-10, Claude's Discretion)**
   - What we know: The stage input JSONB `input.model` can carry the model selection. If absent, fall back to a default.
   - What's unclear: Which specific model is "cheapest capable" as of April 2026? For Anthropic: `claude-3-5-haiku-latest` is the cheapest capable model with tool support.
   - Recommendation: Default to `anthropic:claude-3-5-haiku-latest` for Generate stage. Make it configurable via `input.model` so it can be overridden without code changes.

3. **BDD test format for Derive stage (D-09, Claude's Discretion)**
   - What we know: The output is a test suite derived from structure + compiled constraints.
   - What's unclear: Gherkin (Feature/Scenario/Given-When-Then) vs. plain pytest test functions.
   - Recommendation: Plain pytest format. Gherkin requires an additional parsing layer (pytest-bdd). Plain pytest functions are immediately runnable and maintainable. The Derive stage outputs pytest test stubs that the Generate stage fills in.

4. **Claude Code process lifecycle in production (D-16, Claude's Discretion)**
   - What we know: Executor does not manage Claude Code process. Session is created in DB, proxy captures calls.
   - What's unclear: How does the Claude Code process know which `session_id` to associate its calls with? Does it read from a DB record? Is the session_id passed via env var?
   - Recommendation: Claude Code process reads `ECLUSA_SESSION_ID` env var on startup. The executor writes this env var when creating the session record. The proxy addon maps this session_id via the existing `register_session()` mechanism.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `dispatch_narrowing` resolves immediately (Phase 2 stub) | SCC routing based on `input.scc_stage` | Phase 7 replaces the stub with real stage handlers |
| No GHC sidecar | `haskell:9.10.1` persistent container via docker-compose | ~190ms compile time; compiler as structural gate |
| Only `harness_type='native'` sessions | `harness_type='claude_code'` added | WORK-07 fulfilled; platform harness-agnostic |
| `create_scc_cascade()` does not exist | New function in `executor/scc.py` | SCC-01 template entry point |

---

## Sources

### Primary (HIGH confidence)

- `/home/lynxnathan/code/eclusa/executor/dispatch.py` — dispatch_narrowing stub to extend; dispatch_stage router
- `/home/lynxnathan/code/eclusa/executor/cascade.py` — stage creation patterns, `claim_ready_stages`, `check_cascade_completion`
- `/home/lynxnathan/code/eclusa/harness/native.py` — `start_work_session`, `run_session_turn`, `complete_work_session` — Claude Code harness mirrors this
- `/home/lynxnathan/code/eclusa/fan_out/db.py` — `run_fan_out_with_db()` — intent validation fan-out calls this directly
- `/home/lynxnathan/code/eclusa/knowledge/search.py` — `search_schema_commons()` — Match stage backend
- `/home/lynxnathan/code/eclusa/judgment/pass_.py` — `run_judgment_pass()`, `create_judgment_pass_record()` — Cohere stage backend
- `/home/lynxnathan/code/eclusa/proxy/addon.py` — `ArtifactCaptureAddon` — unchanged for Claude Code sessions
- `/home/lynxnathan/code/eclusa/db/models/compute.py` — `harness_type` is `sa.Text` (not enum) — no migration needed
- `/home/lynxnathan/code/eclusa/alembic/versions/0001_initial_schema.py` — confirmed `harness_type` is free-text column
- `/home/lynxnathan/code/eclusa/tests/helpers/topology.py` — stage insertion patterns for `create_scc_cascade`
- Direct GHC verification: `docker exec` on `haskell:9.10.1` sidecar, measured ~190ms, exit codes confirmed
- `/home/lynxnathan/code/eclusa/.eclusa/research/PITFALLS.md` — §Pitfall 7 (GHC async gate), §Pitfall 5 (fan-out convergence)

### Secondary (MEDIUM confidence)

- `eclusa.md §7` — Six-stage SCC specification with stage types and gate conditions
- `eclusa.md §3.5.1` — Claude Code harness type specification
- CLAUDE.md — GHC 9.10.x as recommended version; confirmed available as `haskell:9.10.1`

---

## Metadata

**Confidence breakdown:**
- SCC template (cascade creation, stage routing): HIGH — direct code reading confirms all patterns
- GHC sidecar: HIGH — compiled and timed directly in this session
- Claude Code harness: HIGH — `harness_type` is free-text confirmed in migration; pattern identical to native
- Fan-out intent validation: HIGH — `run_fan_out_with_db()` is implemented and tested
- Match/Cohere handlers: HIGH — calling existing implemented functions
- LLM first-pass Haskell compile rate: LOW — community data only; must measure

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable platform; GHC API is stable; no fast-moving dependencies)
