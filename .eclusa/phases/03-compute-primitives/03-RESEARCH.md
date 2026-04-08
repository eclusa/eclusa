# Phase 3: Compute Primitives - Research

**Researched:** 2026-04-04
**Domain:** pydantic-ai harness, mitmproxy addon, asyncio fan-out, object storage, context hashing
**Confidence:** HIGH (primary sources: pydantic-ai official docs, mitmproxy official docs, existing codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Work session lifecycle**
- D-01: Native harness type: model API + pydantic-ai tools + direct DB writes — no container, no PTY
- D-02: Work session lifecycle: start → running → (pause → paused → resume → running) → completed/failed
- D-03: Message history stored in platform format (JSONB) on work_session.message_history — updated in real-time during session
- D-04: Workspace snapshot on pause: serialize session state to object storage (keyed by session_id), read on resume
- D-05: On pause, the harness doesn't know it was paused — from its perspective, ambiguityUp returned an answer (could be 200ms or 48 hours)
- D-06: pydantic-ai 1.77.0 as the harness layer — type-safe, model-agnostic, supports pause/resume via message history

**Proxy layer**
- D-07: mitmproxy Python addon (~30 lines) running as a local sidecar process — not a container
- D-08: Proxy intercepts all outbound HTTP calls from harness, creates artifact records automatically
- D-09: Artifact write path is async with circuit-breaker fallback — proxy never blocks the request
- D-10: Each artifact record links to intent_id, cascade_id, stage_id, session_id (full trace chain)
- D-11: Proxy registers with the executor on session start, deregisters on session end

**Judgment pass contract**
- D-12: Single API completion — one request, one response, no agent loop, no tools
- D-13: Prepared context document — not raw session history; platform transforms before judgment
- D-14: Context preparation is itself a local stage in the cascade (cheap narrowing, runs locally)
- D-15: Response must be JSON-schema-validated — structured verdict, not prose
- D-16: Judgment passes cannot modify work outputs — topological enforcement, read-only access
- D-17: context_hash (blake3) enables dedup of identical evaluations

**Fan-out evaluation**
- D-18: Fan-out fires n judgment passes in parallel against shared prepared context (prepared once, reused)
- D-19: Convergence detection via field-by-field comparison of structured JSON verdicts
- D-20: Where all models agree on all fields → converged → auto-resolve with consensus verdict
- D-21: Where models disagree on any field → diverged → create gate with each model's reasoning and divergence points
- D-22: Fan-out verdict states: converged, diverged, partial (some fields agree, some don't)

**Model hot-swap**
- D-23: Between pause and resume, platform can swap to a different model
- D-24: Message history is in platform format — harness-specific adapters translate on ingress/egress
- D-25: For native sessions, platform format IS the session format (no adapter needed)
- D-26: Model swaps recorded in work_session.model_swaps JSONB array: [{from, to, reason, swapped_at}]

**Cost tracking**
- D-27: work_session.cost JSONB updated on each API call: tokens_in, tokens_out, api_calls, tool_calls, wall_time_ms, estimated_usd
- D-28: judgment_pass.cost JSONB: tokens_in, tokens_out, estimated_usd (single call, simpler)
- D-29: Cost queryable by cascade: SUM across all sessions/passes linked to a cascade

### Claude's Discretion
- mitmproxy addon implementation details (request/response hooks)
- Circuit-breaker thresholds and fallback behavior
- Object storage backend for workspace snapshots (local filesystem vs S3-compatible)
- Exact pydantic-ai tool registration patterns
- Context preparation algorithm (what to strip, what to summarize)
- Convergence comparison algorithm (exact match vs semantic similarity threshold)
- blake3 vs sha256 for context_hash

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WORK-01 | Work session starts a harness with stage input and registered proxy | pydantic-ai Agent init + mitmproxy sidecar registration pattern |
| WORK-02 | Message history streams to DB in real time (platform format, not harness-native) | ModelMessagesTypeAdapter serialization; asyncpg JSONB write per turn |
| WORK-03 | Work session can be paused (workspace snapshot to object storage) | JSON snapshot via ModelMessagesTypeAdapter + local fs or S3 write |
| WORK-04 | Work session can be resumed from snapshot (harness doesn't know it was paused) | pydantic-ai `message_history` parameter restores context transparently |
| WORK-05 | Model hot-swap between pause and resume — different model, same portable history | Platform format is model-agnostic; pydantic-ai accepts history independent of model |
| WORK-06 | Native harness type: model API + Pydantic AI tools + direct DB writes (no container) | pydantic-ai Agent with psycopg tool injection; no PTY/container needed |
| WORK-07 | Claude Code harness type: external backend with proxy and history capture | DEFERRED to Phase 7 per REQUIREMENTS.md traceability table |
| WORK-08 | Cost tracking per session: tokens_in, tokens_out, api_calls, tool_calls, wall_time_ms, estimated_usd | pydantic-ai `result.usage()` exposes token counts; asyncpg JSONB update per call |
| PROXY-01 | Proxy intercepts all outbound calls from harnesses | mitmproxy addon `request`/`response` async hooks via HTTP_PROXY env |
| PROXY-02 | Proxy automatically creates artifact records for every intercepted call | async DB write in `response` hook via psycopg |
| PROXY-03 | Artifact records link to intent_id, cascade_id, stage_id, session_id (full trace chain) | Context passed to proxy at session start via addon state |
| PROXY-04 | Proxy write path is async with circuit-breaker fallback (not synchronous bottleneck) | Async hook + asyncio.Queue for backpressure; skip on overflow |
| JUDG-01 | Judgment pass is a single API completion — no harness, no tools, no agent loop | pydantic-ai `Agent.run()` with `output_type` Pydantic model; terminates on first structured response |
| JUDG-02 | Judgment pass receives prepared context document (not raw session history) | Context stored in object storage; loaded by reference (context_ref) |
| JUDG-03 | Context preparation is itself a stage in the cascade (strip noise, summarize, foreground decisions) | Local Python function — no model call; runs as a narrowing stage before fan-out or judgment |
| JUDG-04 | Judgment pass response is structured (JSON schema enforced for convergence detection) | pydantic-ai `output_type=VerdictModel` enforces schema at framework level |
| JUDG-05 | Judgment pass cannot modify work — read and evaluate only (topological enforcement) | No write tools registered; psycopg connection in read-only mode for judgment harness |
| JUDG-06 | Context preparation shared across fan-out passes (prepared once, reused) | context_ref + context_hash written once; all fan-out passes reference same object |
| FAN-01 | Fan-out fires n judgment passes in parallel against shared prepared context | `asyncio.gather(*[run_judgment_pass(...) for model in models])` |
| FAN-02 | Fan-out computes convergence matrix from structured verdicts | Field-by-field dict comparison after all passes complete |
| FAN-03 | Where models converge, auto-resolve with consensus verdict | All decision fields match → write fan_out.verdict='converged', mark stage resolved |
| FAN-04 | Where models diverge, create gate with each model's reasoning and divergence points | Write fan_out.verdict='diverged', surface gate stage with divergence context |
| FAN-05 | Fan-out verdict states: converged, diverged, partial | fan_out_verdict_enum already defined in db/models/domain.py |
</phase_requirements>

---

## Summary

Phase 3 replaces the Phase 2 stub in `executor/dispatch.py:dispatch_narrowing()` with three real compute primitives: the native work session harness (pydantic-ai), the judgment pass (single pydantic-ai completion with structured output), and fan-out evaluation (n parallel judgment passes with convergence detection). The mitmproxy sidecar handles artifact capture transparently. All DB tables and enum types are already in place from Phase 1.

The critical integration insight: `dispatch_stage()` in `executor/dispatch.py` is the single entry point. It already routes by `stage["type"]` — Phase 3 replaces the body of `dispatch_narrowing()` with a router that inspects `stage["input"]` for `compute_type` (work_session / judgment_pass / fan_out) and delegates to the corresponding primitive. The loop in `executor/loop.py` requires no changes.

The phase has four well-bounded subdomains: (1) work session lifecycle (pydantic-ai + DB writes + pause/resume), (2) proxy sidecar (mitmproxy addon + artifact creation), (3) judgment pass (single pydantic-ai call + structured output), (4) fan-out (asyncio.gather + convergence matrix). Each subdomain is independently testable.

**Primary recommendation:** Implement in wave order: proxy addon first (it blocks work session testing), then work session lifecycle, then judgment pass, then fan-out. Context preparation (JUDG-03) is a local Python function — implement it alongside judgment pass, not as a separate wave.

---

## Standard Stack

### Core (new additions for Phase 3)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-ai | 1.77.0 | Native harness layer + judgment pass | Locked D-06; type-safe, model-agnostic, `output_type` enforces JSON schema, `message_history` enables pause/resume |
| mitmproxy | 11.x | Outbound LLM call proxy + artifact capture | Locked D-07; ~30-line addon handles TLS, streaming, and connection reuse that a custom proxy would need 300+ lines for |
| blake3 | latest | context_hash for judgment pass dedup | D-17; 4-10x faster than SHA-256, equivalent security; `pip install blake3` (C extension wheel); falls back to hashlib.sha256 if unavailable |
| httpx | 0.28.1 | Async HTTP client inside harness | Outbound calls from native harness route through mitmproxy via HTTP_PROXY env var |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | 0.31.0 | DB writes from executor + proxy | Artifact INSERT, work_session UPDATE in hot path |
| psycopg | 3.3.3 | DB writes from within harness tools | Tool-registered DB writes during work session |
| pydantic | 2.x | VerdictModel schema for judgment pass | Transitive dep of pydantic-ai; define verdict schema here |

### Object Storage (Claude's Discretion — recommendation)

Use local filesystem for workspace snapshots in Phase 3. Reason: Phase 3 has no docker-compose deployment target (Phase 6 adds INFRA-01). A `pathlib.Path`-based storage class with a swappable interface (`save_snapshot(session_id, data)` / `load_snapshot(session_id)`) is the right abstraction. The interface can be backed by S3 in Phase 6 without changing calling code.

| Backend | When to Use |
|---------|-------------|
| Local filesystem (`/tmp/eclusa/snapshots/`) | Phase 3 dev/test — zero dependencies |
| boto3 + MinIO (docker-compose) | Phase 6 deployment target |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-ai | Direct Anthropic/OpenAI SDK | pydantic-ai is locked; direct SDK requires custom tool management, history serialization |
| mitmproxy addon | Custom aiohttp proxy | ~300 lines of TLS handling vs ~30 lines mitmproxy addon; mitmproxy handles SSE streaming with one-line fix |
| blake3 | hashlib.sha256 | SHA-256 is in stdlib (zero deps); blake3 is 4-10x faster but requires C extension. Use sha256 as fallback if blake3 wheel unavailable in CI |
| asyncio.gather (fan-out) | asyncio.TaskGroup | TaskGroup is Python 3.11+; project requires 3.12+ so either works. asyncio.gather is more familiar and handles partial failures the same way |

**Installation (new for Phase 3):**

```bash
uv add "pydantic-ai==1.77.0" mitmproxy httpx blake3
```

---

## Architecture Patterns

### Recommended Module Structure for Phase 3

```
executor/
├── dispatch.py         # REPLACE dispatch_narrowing() body — route to compute type
harness/
├── __init__.py
├── native.py           # pydantic-ai Agent setup, run, pause, resume, cost tracking
├── snapshot.py         # workspace snapshot save/load (local fs interface)
└── message_format.py   # ModelMessagesTypeAdapter serialization helpers
proxy/
├── __init__.py
└── addon.py            # mitmproxy addon — ~30 lines, async response hook
judgment/
├── __init__.py
├── pass_.py            # run_judgment_pass(): single pydantic-ai run with output_type
└── context_prep.py     # prepare_context(): local stage, no model call
fan_out/
├── __init__.py
├── dispatcher.py       # run_fan_out(): asyncio.gather over judgment passes
└── convergence.py      # compute_convergence(): field-by-field comparison
tests/
├── test_work_session.py
├── test_proxy_addon.py
├── test_judgment_pass.py
└── test_fan_out.py
```

### Pattern 1: Work Session Lifecycle

**What:** pydantic-ai Agent runs with tool injection. Message history written to DB after each turn. On pause: serialize `all_messages()`, write to snapshot storage, update `work_session.state='paused'`. On resume: load snapshot, call `Agent.run()` with `message_history=restored_messages`.

**The "harness doesn't know it was paused" invariant (D-05):** From the harness perspective, a tool call that triggers `ambiguityUp` simply returns a value. The executor pauses the session (writes snapshot), a human resolves the gate (could be days later), and the executor resumes by re-calling `Agent.run()` with the prior history plus the resolution value as a new user message. The Agent processes this as if it were a normal tool result.

**Example:**

```python
# Source: https://ai.pydantic.dev/message-history/
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python

agent = Agent("anthropic:claude-3-5-haiku-latest")

# Initial run
result = await agent.run("Analyze this codebase for security issues.")
# Write history to DB (platform format)
history_json = to_jsonable_python(result.all_messages())
# await conn.execute("UPDATE work_session SET message_history=$1 WHERE id=$2", ...)

# Resume after pause/model-swap (D-23, D-24, D-25)
restored = ModelMessagesTypeAdapter.validate_python(history_from_db)
result2 = await agent.run(
    "The gate was resolved: proceed with analysis",
    message_history=restored  # harness sees this as a continuation
)
```

**Cost tracking (D-27, D-28):**

```python
# pydantic-ai exposes usage after each run
usage = result.usage()
cost_delta = {
    "tokens_in": usage.request_tokens or 0,
    "tokens_out": usage.response_tokens or 0,
    "api_calls": 1,
}
# Merge into work_session.cost JSONB with += semantics
```

### Pattern 2: mitmproxy Addon (Async, Non-Blocking)

**What:** ~30-line mitmproxy Python addon that intercepts every `response` event, writes an artifact record asynchronously, and never blocks the proxied response.

**SSE streaming fix (critical — Pitfall 6):** LLM APIs use SSE for streaming responses. mitmproxy buffers SSE by default, breaking streaming. Fix with one line in `responseheaders` hook:

```python
# Source: https://github.com/mitmproxy/mitmproxy/issues/4469
def responseheaders(self, flow):
    ct = flow.response.headers.get("content-type", "")
    if "text/event-stream" in ct:
        flow.response.stream = True  # pass through without buffering
```

**Full addon pattern:**

```python
# proxy/addon.py — ~30 lines
import asyncio
import asyncpg

class ArtifactCaptureAddon:
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._session_context: dict = {}  # session_id → {intent_id, cascade_id, stage_id}
        self._writer_task = None

    def register_session(self, session_id: str, context: dict):
        self._session_context[session_id] = context

    def deregister_session(self, session_id: str):
        self._session_context.pop(session_id, None)

    def responseheaders(self, flow):
        ct = flow.response.headers.get("content-type", "")
        if "text/event-stream" in ct:
            flow.response.stream = True  # D-09: never block streaming

    async def response(self, flow):
        # Circuit-breaker: skip if queue full (D-09 fallback)
        if self._queue.full():
            return  # drop artifact, never block request
        ctx = self._session_context.get(flow.metadata.get("session_id", ""))
        if ctx:
            await self._queue.put({
                "request": flow.request.pretty_url,
                "response_status": flow.response.status_code,
                "context": ctx,
            })
```

**Circuit-breaker threshold:** Queue maxsize=500 with non-blocking put (skip if full). This is the correct pattern: artifact capture is best-effort, not required for correctness. A lost artifact is logged; a blocked request is a correctness failure.

### Pattern 3: Judgment Pass (Single Completion, Structured Output)

**What:** One `Agent.run()` call with `output_type=VerdictModel`. No tools. No agent loop. pydantic-ai terminates the run when the model returns a value matching the schema.

**Topological enforcement (D-16):** No tools means no write path. Pass a read-only asyncpg connection in deps if context loading requires DB access, but no write methods exposed.

```python
# Source: https://ai.pydantic.dev/output/
from pydantic import BaseModel
from pydantic_ai import Agent

class VerdictModel(BaseModel):
    decision: str          # "approve" | "reject" | "needs_clarification"
    confidence: float      # 0.0–1.0
    rationale: str
    conditions: list[str]  # empty if no conditions

async def run_judgment_pass(
    model: str,
    prepared_context: str,
    prompt: str,
    context_hash: str,
) -> VerdictModel:
    agent = Agent(model, output_type=VerdictModel)
    result = await agent.run(
        f"{prepared_context}\n\n{prompt}"
    )
    return result.output  # type: VerdictModel, validated by pydantic-ai
```

**context_hash (D-17):** Compute before storing context, used for dedup:

```python
try:
    import blake3
    def hash_context(content: str) -> str:
        return blake3.blake3(content.encode()).hexdigest()
except ImportError:
    import hashlib
    def hash_context(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
```

### Pattern 4: Fan-Out Evaluation (Parallel + Convergence)

**What:** `asyncio.gather()` fires n judgment passes in parallel against the same prepared context. After all complete, convergence detection compares structured verdict fields.

```python
# fan_out/dispatcher.py
async def run_fan_out(
    models: list[str],
    prepared_context: str,
    prompt: str,
    context_hash: str,
) -> tuple[list[VerdictModel], str]:  # verdicts, verdict state
    results = await asyncio.gather(
        *[run_judgment_pass(m, prepared_context, prompt, context_hash) for m in models],
        return_exceptions=False,  # let exceptions propagate
    )
    verdict_state = compute_convergence(results)
    return results, verdict_state
```

**Convergence detection (D-19, D-20, D-21, D-22):**

```python
# fan_out/convergence.py
def compute_convergence(verdicts: list[VerdictModel]) -> tuple[str, dict]:
    """
    Returns: (verdict_state, convergence_matrix)
    verdict_state: "converged" | "diverged" | "partial"
    """
    fields = ["decision", "confidence"]  # fields to compare
    matrix = {}
    all_agree = True
    any_agree = False

    for field in fields:
        values = [getattr(v, field) for v in verdicts]
        # confidence: treat as converged if within 0.15 threshold
        if field == "confidence":
            spread = max(values) - min(values)
            agrees = spread <= 0.15
        else:
            agrees = len(set(values)) == 1  # exact match for categorical fields
        matrix[field] = {"values": values, "converged": agrees}
        if agrees:
            any_agree = True
        else:
            all_agree = False

    if all_agree:
        return "converged", matrix
    elif any_agree:
        return "partial", matrix
    else:
        return "diverged", matrix
```

### Anti-Patterns to Avoid

- **Judgment pass with tool access:** Tools create side effects. Fan-out with n passes would create n×side effects. No tools in judgment passes — structural rule, not convention.
- **Synchronous artifact write in proxy:** Makes proxy a latency bottleneck. The proxy should fire and forget via asyncio queue; never await the DB write in the request path.
- **Storing message history in provider-native format:** Breaks hot-swap. Use `ModelMessagesTypeAdapter` to serialize to JSONB — this is the platform-neutral format (D-03, D-24, D-25).
- **mitmproxy default SSE handling:** mitmproxy buffers SSE without `flow.response.stream = True`. Always set this for `text/event-stream` content-type or streaming responses will block until the model closes the connection.
- **Computing convergence on full verdict text (prose):** High false positive rate. Compare only structured fields (`decision`, `conditions`) — not `rationale`. Rationale is narrative; categorical fields are signals.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured output validation from LLM | JSON parser + regex schema check | pydantic-ai `output_type=VerdictModel` | Handles retry on invalid output, schema negotiation with model, tool-calling path |
| Message history serialization for pause/resume | Custom JSON format | `ModelMessagesTypeAdapter.validate_python()` + `to_jsonable_python()` | Platform format is already what pydantic-ai uses — no translation layer needed for native harness |
| HTTP interception for artifact capture | aiohttp reverse proxy (~300 lines) | mitmproxy addon (~30 lines) | TLS termination, connection reuse, chunked encoding, and SSE handling are solved problems in mitmproxy |
| Parallel model calls with error handling | asyncio.create_task + manual result collection | `asyncio.gather()` | Handles cancellation, exception propagation, and result ordering correctly |
| Context deduplication hash | Rolling hash over content fields | blake3 (or hashlib.sha256) over serialized context string | One-line hash; blake3 is 4-10x faster, SHA-256 is stdlib fallback |

**Key insight:** The three compute primitives are not "build vs. buy" — pydantic-ai IS the harness. The work is wiring: instantiate Agent with correct model string, register tools, write history to DB, manage state transitions. The complexity is in the lifecycle state machine and proxy integration, not in the model calls themselves.

---

## Common Pitfalls

### Pitfall 1: mitmproxy SSE Buffering Breaks Streaming LLMs

**What goes wrong:** mitmproxy buffers SSE responses (`text/event-stream`) until the connection closes. A work session calling Claude or GPT-4o in streaming mode will appear to hang — the harness receives no tokens until the model finishes the entire response, then gets them all at once. This makes sessions with long responses appear to stall.

**Why it happens:** mitmproxy's default is forensic-safe: capture everything before forwarding. This is wrong for streaming.

**How to avoid:** Add `responseheaders` hook to addon:

```python
def responseheaders(self, flow):
    if "text/event-stream" in flow.response.headers.get("content-type", ""):
        flow.response.stream = True
```

**Warning signs:** Work session hangs on first tool call that calls a streaming LLM. Proxy logs show no response bytes until session completes.

---

### Pitfall 2: Proxy Queue Starvation Blocks Work Session

**What goes wrong:** Proxy artifact queue fills up (e.g., very fast session with many tool calls, slow DB writes). Next queue.put() blocks the `response` hook, which blocks the proxied response back to the harness. Session latency grows with each call.

**Why it happens:** Using `await queue.put()` (blocking) instead of `queue.put_nowait()` (non-blocking, raises if full).

**How to avoid:** Use `queue.put_nowait()` with try/except QueueFull — log and skip rather than block:

```python
async def response(self, flow):
    try:
        self._queue.put_nowait(artifact_data)
    except asyncio.QueueFull:
        logger.warning("Artifact queue full — dropping capture for %s", flow.request.pretty_url)
```

**Warning signs:** Work session p99 latency increases over time; proxy logs show increasing queue depth.

---

### Pitfall 3: Message History Portability Breaks on Model Hot-Swap

**What goes wrong:** Native harness stores pydantic-ai's internal `ModelMessage` objects. On model hot-swap (e.g., Claude → GPT-4o), tool call schema in the stored history is provider-specific. New model receives history with Anthropic tool call format and misinterprets it.

**Why it happens:** `to_jsonable_python(result.all_messages())` produces a provider-neutral representation. Skipping this step and storing a provider-specific format breaks portability.

**How to avoid (D-24, D-25):** Always serialize via `ModelMessagesTypeAdapter`:

```python
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python

# On every DB write:
history_for_db = to_jsonable_python(result.all_messages())

# On resume:
restored = ModelMessagesTypeAdapter.validate_python(history_from_db)
result = await agent.run("continue", message_history=restored)
```

**Warning signs:** Resume works with same model, fails with different model. Tool call response messages have unexpected structure in the new model's first turn.

---

### Pitfall 4: Fan-Out Convergence False Positives on Prose Fields

**What goes wrong:** Two models return semantically identical `rationale` text with different phrasing. Convergence detector treats this as divergence and surfaces a gate. Human opens gate, sees two versions of the same recommendation, resolves immediately — gate was noise.

**Why it happens:** Applying exact-match comparison to prose fields instead of categorical fields.

**How to avoid (D-19):** Convergence detection runs on `decision` field (categorical) only. `rationale` and `conditions` are surfaced in the divergence context for human review, but do not drive the converged/diverged determination. Confidence compared within a threshold band (±0.15).

**Warning signs:** Gate resolution latency is consistently <60 seconds (gates trivial). Self-calibration metric CAL-01 (gate necessity rate) is high.

---

### Pitfall 5: dispatch_narrowing Signature Mismatch Breaks Loop

**What goes wrong:** The executor loop calls `dispatch_stage(conn, stage, actor_id)` which routes to `dispatch_narrowing(conn, stage, actor_id)`. Phase 3 replaces the stub body. If the new `dispatch_narrowing` is async and the loop doesn't await it, or if it changes the signature, loop.py silently swallows the work.

**Why it happens:** `loop.py:_dispatch_and_check()` uses `asyncio.create_task()` — if dispatch raises and the exception isn't caught, it's logged but swallowed. The stage stays in `active` state indefinitely.

**How to avoid:** Keep the exact signature `async def dispatch_narrowing(conn, stage, actor_id)`. Any exception from the new body must either (a) be caught and trigger `retry_stage()` or (b) propagate to the existing `except Exception: logger.exception(...)` in `_dispatch_and_check`. Write a test that verifies a failed dispatch does NOT leave the stage in `active` state.

---

### Pitfall 6: Judgment Pass Read-Only Enforcement is Convention, Not Structure

**What goes wrong:** "No write tools in judgment pass" is enforced by not registering write tools. A future developer adds a tool "just for testing." The topology constraint evaporates.

**How to avoid:** Make it structural:
1. Judgment pass Agent is constructed with no tools parameter (or only read tools from a whitelist)
2. The asyncpg/psycopg connection passed into judgment pass dependencies is opened in a read-only transaction: `BEGIN READ ONLY`
3. Add a test that verifies a judgment pass attempt to write raises an error at the DB level

---

## Code Examples

### Work Session: Create and Write Initial Record

```python
# Source: pydantic-ai docs + existing asyncpg patterns in executor/dispatch.py
import asyncpg
import json
from datetime import datetime, timezone

SCHEMA_VERSION = "0003"

async def start_work_session(
    conn: asyncpg.Connection,
    stage: dict,
    actor_id: str,
    model: str,
) -> str:
    """Create work_session record, transition stage to running."""
    async with conn.transaction():
        row = await conn.fetchrow("""
            INSERT INTO work_session
                (id, stage_ids, harness_type, model, state, cost)
            VALUES (
                gen_random_uuid(),
                ARRAY[$1::uuid],
                'native',
                $2,
                'running',
                '{"tokens_in": 0, "tokens_out": 0, "api_calls": 0, "tool_calls": 0,
                  "wall_time_ms": 0, "estimated_usd": 0.0}'::jsonb
            )
            RETURNING id
        """, stage["id"], model)
        session_id = str(row["id"])

        await conn.execute("""
            INSERT INTO ledger_entry
                (id, stage_id, cascade_id, session_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid, $2::uuid,
                   'work_session_started',
                   jsonb_build_object('session_id', $1::text, 'model', $3),
                   $4
            FROM stage s WHERE s.id = $5::uuid
        """, session_id, actor_id, model, SCHEMA_VERSION, stage["id"])

    return session_id
```

### Work Session: Pause and Snapshot

```python
# harness/snapshot.py
import json
from pathlib import Path
from pydantic_core import to_jsonable_python

SNAPSHOT_DIR = Path("/tmp/eclusa/snapshots")

def save_snapshot(session_id: str, messages: list) -> str:
    """Write message history to local fs. Returns path (workspace_ref)."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{session_id}.json"
    path.write_text(json.dumps(to_jsonable_python(messages)))
    return str(path)

def load_snapshot(workspace_ref: str) -> list:
    """Load and deserialize message history from snapshot."""
    from pydantic_ai.messages import ModelMessagesTypeAdapter
    data = json.loads(Path(workspace_ref).read_text())
    return ModelMessagesTypeAdapter.validate_python(data)
```

### Judgment Pass: Single Structured Completion

```python
# Source: https://ai.pydantic.dev/output/
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_core import to_jsonable_python
import asyncpg

class VerdictModel(BaseModel):
    decision: str = Field(description="approve | reject | needs_clarification")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    conditions: list[str] = Field(default_factory=list)

async def run_judgment_pass(
    conn: asyncpg.Connection,
    stage: dict,
    actor_id: str,
    model: str,
    prepared_context: str,
    prompt: str,
    context_ref: str,
    context_hash: str,
) -> VerdictModel:
    agent = Agent(model, output_type=VerdictModel)
    result = await agent.run(f"{prepared_context}\n\n{prompt}")
    verdict = result.output

    usage = result.usage()
    cost = {
        "tokens_in": usage.request_tokens or 0,
        "tokens_out": usage.response_tokens or 0,
        "estimated_usd": 0.0,  # compute from model pricing table
    }

    async with conn.transaction():
        row = await conn.fetchrow("""
            INSERT INTO judgment_pass
                (id, stage_ids, model, context_ref, context_hash, prompt, response, cost, completed_at)
            VALUES (
                gen_random_uuid(), ARRAY[$1::uuid], $2, $3, $4, $5,
                $6::jsonb, $7::jsonb, NOW()
            )
            RETURNING id
        """,
            stage["id"], model, context_ref, context_hash, prompt,
            json.dumps(to_jsonable_python(verdict)), json.dumps(cost)
        )
        pass_id = str(row["id"])

        await conn.execute("""
            INSERT INTO ledger_entry
                (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT gen_random_uuid(), s.id, s.cascade_id, $1::uuid,
                   'judgment_pass_completed',
                   jsonb_build_object('pass_id', $2, 'verdict', $3, 'model', $4),
                   $5
            FROM stage s WHERE s.id = $6::uuid
        """, actor_id, pass_id, verdict.decision, model, SCHEMA_VERSION, stage["id"])

    return verdict
```

### Fan-Out: Parallel Dispatch + Convergence Write

```python
# fan_out/dispatcher.py
import asyncio
import asyncpg

async def run_fan_out(
    pool: asyncpg.Pool,
    stage: dict,
    actor_id: str,
    models: list[str],
    prepared_context: str,
    prompt: str,
    context_ref: str,
    context_hash: str,
) -> None:
    verdicts = await asyncio.gather(
        *[run_judgment_pass(pool, stage, actor_id, m, prepared_context,
                           prompt, context_ref, context_hash) for m in models]
    )

    verdict_state, matrix = compute_convergence(verdicts)

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                INSERT INTO fan_out
                    (id, stage_id, context_ref, prompt, passes, convergence, verdict, completed_at)
                VALUES (gen_random_uuid(), $1::uuid, $2, $3, $4::uuid[], $5::jsonb, $6, NOW())
                RETURNING id
            """,
                stage["id"], context_ref, prompt,
                [],  # pass IDs populated via join on stage_id in production
                json.dumps(matrix),
                verdict_state,
            )
            fan_out_id = str(row["id"])

        if verdict_state == "converged":
            # Auto-resolve stage
            await conn.execute("""
                UPDATE stage SET state='resolved', resolved_at=NOW(), resolved_by=$1::uuid
                WHERE id=$2::uuid
            """, actor_id, stage["id"])
        else:
            # Create gate with divergence context
            await conn.execute("""
                UPDATE stage SET state='blocked' WHERE id=$1::uuid
            """, stage["id"])
            # ledger_entry: gate_surfaced with fan_out_id in content
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Store LLM history in provider format | Platform-neutral `ModelMessage` format via `ModelMessagesTypeAdapter` | pydantic-ai 0.0.x → 1.x | Enables model hot-swap without history corruption |
| Custom HTTP proxy for LLM interception | mitmproxy Python addon (~30 lines) | mitmproxy 8+ (async hooks) | Reduces custom code; TLS + streaming handled by library |
| Convergence detection on free-text verdicts | Structured `output_type` Pydantic model, field-by-field comparison | pydantic-ai 1.x (output_type) | Near-zero false-positive rate on categorical fields |
| Blocking GHC gate (Phase 7 concern) | Async subprocess with semaphore | N/A for Phase 3 | Document here; implement in Phase 7 |

**Deprecated/outdated:**
- `dispatch_narrowing()` stub in `executor/dispatch.py`: the Phase 2 stub resolves stage immediately. Phase 3 replaces the body with real dispatch routing.
- `result_type` parameter name: older pydantic-ai used `result_type`; 1.77.0 uses `output_type`. Use `output_type`.

---

## Open Questions

1. **mitmproxy sidecar process management**
   - What we know: mitmproxy addon runs as a sidecar (`mitmdump -s proxy/addon.py`), harness sets `HTTP_PROXY=http://localhost:8080`
   - What's unclear: how the executor starts/stops the proxy per session vs. once per executor process (D-11 says "register on session start, deregister on session end")
   - Recommendation: Start one mitmdump process per executor process (not per session). Register/deregister via a shared dict keyed by session_id. This avoids process start overhead per session.

2. **context_ref object storage path convention**
   - What we know: `context_ref` is a text field storing the object storage path; `workspace_ref` is the same for snapshots
   - What's unclear: path convention (UUID-keyed? session_id-keyed? hash-keyed?)
   - Recommendation: Key by `blake3_hash` of context content (not session_id) — enables natural dedup across fan-out passes that share the same prepared context

3. **Fan-out pass_ids tracking in fan_out.passes column**
   - What we know: `fan_out.passes` is `ulid[]` — judgment_pass.ids for the fan-out
   - What's unclear: The judgment_pass inserts happen before fan_out insert in current pattern; requires collecting IDs and updating fan_out.passes after the fact
   - Recommendation: Insert fan_out record first (with empty passes array), collect judgment_pass IDs from asyncio.gather results, then UPDATE fan_out SET passes=ARRAY[...] after all passes complete

4. **Confidence field on JudgmentPass table**
   - What we know: `judgment_pass.confidence` column exists (numeric); VerdictModel has confidence field
   - What's unclear: whether to copy VerdictModel.confidence to the top-level column or leave it in response JSONB only
   - Recommendation: Write VerdictModel.confidence to both — the column enables fast SQL-level filtering (e.g., WHERE confidence < 0.5) without JSONB extraction

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pydantic-ai | WORK-01, WORK-06, JUDG-01, FAN-01 | ✗ | — | None — must install via `uv add pydantic-ai==1.77.0` |
| mitmproxy | PROXY-01, PROXY-02, PROXY-03, PROXY-04 | ✗ | — | None — must install via `uv add mitmproxy` |
| httpx | WORK-01 (outbound calls routed through proxy) | ✗ | — | None — must install via `uv add httpx` |
| blake3 | JUDG-06 (context_hash) | ✗ | — | hashlib.sha256 (stdlib, available) |
| asyncpg | All DB writes | ✓ | 0.31.0 | — |
| psycopg | LISTEN/NOTIFY, harness tool DB access | ✓ | 3.3.3 | — |
| pytest + pytest-asyncio | All tests | ✓ | 9.0.2 / 1.3.0 | — |
| testcontainers[postgres] | Integration tests | ✓ | 4.14.2+ | — |
| Python | All | ✓ | 3.12+ | — |

**Missing dependencies with no fallback:**
- `pydantic-ai==1.77.0` — blocks all work session, judgment pass, and fan-out implementation
- `mitmproxy` — blocks all proxy tests
- `httpx` — blocks work session outbound call routing

**Missing dependencies with fallback:**
- `blake3` — SHA-256 from stdlib is a valid fallback; blake3 is a performance optimization, not a correctness requirement

**Wave 0 install command:**

```bash
uv add "pydantic-ai==1.77.0" mitmproxy httpx blake3
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` — `asyncio_mode = auto` |
| Quick run command | `uv run pytest tests/test_work_session.py tests/test_judgment_pass.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WORK-01 | Work session record created, proxy registered | integration | `pytest tests/test_work_session.py::test_start_work_session -x` | ❌ Wave 0 |
| WORK-02 | message_history JSONB updated after each turn | integration | `pytest tests/test_work_session.py::test_message_history_streaming -x` | ❌ Wave 0 |
| WORK-03 | Snapshot written to object storage on pause | unit | `pytest tests/test_work_session.py::test_pause_snapshot -x` | ❌ Wave 0 |
| WORK-04 | Resume restores history; new run continues seamlessly | unit | `pytest tests/test_work_session.py::test_resume_from_snapshot -x` | ❌ Wave 0 |
| WORK-05 | Hot-swap: pause with model A, resume with model B, history intact | unit | `pytest tests/test_work_session.py::test_model_hot_swap -x` | ❌ Wave 0 |
| WORK-06 | Native harness (no container) runs tool call and writes result | integration | `pytest tests/test_work_session.py::test_native_harness_tool_call -x` | ❌ Wave 0 |
| WORK-08 | Cost JSONB updated per API call with correct field names | integration | `pytest tests/test_work_session.py::test_cost_tracking -x` | ❌ Wave 0 |
| PROXY-01 | Proxy intercepts outbound HTTP call from harness | integration | `pytest tests/test_proxy_addon.py::test_intercept -x` | ❌ Wave 0 |
| PROXY-02 | Artifact record created in DB for every intercepted call | integration | `pytest tests/test_proxy_addon.py::test_artifact_created -x` | ❌ Wave 0 |
| PROXY-03 | Artifact record has all four FK fields populated | integration | `pytest tests/test_proxy_addon.py::test_artifact_trace_chain -x` | ❌ Wave 0 |
| PROXY-04 | Proxy drops artifact on queue full, does not block request | unit | `pytest tests/test_proxy_addon.py::test_circuit_breaker -x` | ❌ Wave 0 |
| JUDG-01 | Judgment pass returns structured output (no tool calls) | unit | `pytest tests/test_judgment_pass.py::test_single_completion -x` | ❌ Wave 0 |
| JUDG-02 | Judgment pass receives prepared_context (not raw history) | unit | `pytest tests/test_judgment_pass.py::test_prepared_context_input -x` | ❌ Wave 0 |
| JUDG-03 | Context prep strips tool noise, produces clean context doc | unit | `pytest tests/test_judgment_pass.py::test_context_preparation -x` | ❌ Wave 0 |
| JUDG-04 | Judgment pass response validated against VerdictModel schema | unit | `pytest tests/test_judgment_pass.py::test_structured_output_schema -x` | ❌ Wave 0 |
| JUDG-05 | Judgment pass write attempt raises DB error (read-only connection) | unit | `pytest tests/test_judgment_pass.py::test_read_only_enforcement -x` | ❌ Wave 0 |
| JUDG-06 | Same context_hash → same context_ref; not duplicated | unit | `pytest tests/test_judgment_pass.py::test_context_dedup -x` | ❌ Wave 0 |
| FAN-01 | n judgment passes fire in parallel | integration | `pytest tests/test_fan_out.py::test_parallel_dispatch -x` | ❌ Wave 0 |
| FAN-02 | Convergence matrix computed from structured verdicts | unit | `pytest tests/test_fan_out.py::test_convergence_matrix -x` | ❌ Wave 0 |
| FAN-03 | Converged fan-out auto-resolves stage | integration | `pytest tests/test_fan_out.py::test_auto_resolve_on_convergence -x` | ❌ Wave 0 |
| FAN-04 | Diverged fan-out creates gate with divergence context | integration | `pytest tests/test_fan_out.py::test_gate_on_divergence -x` | ❌ Wave 0 |
| FAN-05 | partial verdict state fires when some fields agree | unit | `pytest tests/test_fan_out.py::test_partial_verdict -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_work_session.py tests/test_judgment_pass.py tests/test_fan_out.py tests/test_proxy_addon.py -x --tb=short`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/eclusa:verify-work`

### Wave 0 Gaps

All test files are missing — none existed before Phase 3. Wave 0 creates:

- [ ] `tests/test_work_session.py` — covers WORK-01 through WORK-06, WORK-08
- [ ] `tests/test_proxy_addon.py` — covers PROXY-01 through PROXY-04
- [ ] `tests/test_judgment_pass.py` — covers JUDG-01 through JUDG-06
- [ ] `tests/test_fan_out.py` — covers FAN-01 through FAN-05
- [ ] New module installs: `uv add "pydantic-ai==1.77.0" mitmproxy httpx blake3`

The existing `tests/conftest.py` (testcontainers postgres + Alembic) and `tests/helpers/topology.py` (cascade seeders) are reused without modification.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Impact on Phase 3 |
|------------|--------|-------------------|
| Single Postgres instance — no external vector DB | CLAUDE.md Infrastructure | Artifact records go to the existing `artifact` table in Postgres; no separate datastore |
| Stateless executor, all state in DB | CLAUDE.md Execution | Work session state (running/paused/completed) must be in DB row, not executor memory; proxy session context dict is ephemeral and acceptable (process-local) |
| Postgres SKIP LOCKED for multi-executor | CLAUDE.md Concurrency | Not directly impacted — Phase 3 compute primitives are called after SKIP LOCKED claim |
| Object storage for workspace snapshots | CLAUDE.md Storage | Confirmed: `workspace_ref` on work_session, snapshots to local fs in Phase 3, S3 in Phase 6 |
| `docker-compose up` — single command bootstrap | CLAUDE.md Deployment | mitmproxy sidecar should be in docker-compose.yml (Phase 6 fully assembles; Phase 3 documents the intent) |
| Python executor ~300-500 lines | CLAUDE.md Stack | Phase 3 adds harness/ proxy/ judgment/ fan_out/ modules outside the executor — executor itself stays within the line budget |
| pydantic-ai for native harness | CLAUDE.md Stack | Locked — confirmed as D-06 |
| `uv add` not `uv pip install` | Memory: feedback_tooling | Install command: `uv add "pydantic-ai==1.77.0" mitmproxy httpx blake3` |

---

## Sources

### Primary (HIGH confidence)

- `eclusa.md` §3.5.1, §3.5.2, §3.5.3, §3.6 — canonical work session, judgment pass, fan-out, artifact specs (read directly)
- `executor/dispatch.py` — stub signatures to replace (read directly)
- `db/models/compute.py` — WorkSession, JudgmentPass, FanOut column definitions (read directly)
- `db/models/domain.py` — Artifact model, ledger_type enum with all Phase 3 event types (read directly)
- `https://ai.pydantic.dev/message-history/` — ModelMessagesTypeAdapter, message_history parameter, history_processors
- `https://ai.pydantic.dev/output/` — output_type, structured output, asyncio.gather pattern

### Secondary (MEDIUM confidence)

- `https://docs.mitmproxy.org/stable/addons/examples/` — async hooks confirmed; SSE streaming via `flow.response.stream = True` confirmed via GitHub issue #4469
- `.eclusa/research/STACK.md` — pydantic-ai 1.77.0, mitmproxy 11.x versions verified (researched 2026-04-04)
- `.eclusa/research/PITFALLS.md` — Pitfall 6 (proxy bottleneck), Pitfall 5 (fan-out convergence on prose), Pitfall 8 (message history portability)

### Tertiary (LOW confidence)

- `https://devtoolspro.org/articles/sha256-alternatives-faster-hash-functions-2025/` — blake3 4-10x faster than SHA-256 (single benchmark site; claim consistent with official blake3 benchmarks)

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — pydantic-ai docs verified; mitmproxy docs verified; existing asyncpg/psycopg confirmed installed
- Architecture: HIGH — directly derived from eclusa.md spec + existing Phase 2 code patterns
- Pitfalls: HIGH — Pitfalls 5, 6, 8 from PITFALLS.md were verified against official sources; proxy SSE issue confirmed via mitmproxy GitHub

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (pydantic-ai fast-moving; verify 1.77.0 is still current before planning)
