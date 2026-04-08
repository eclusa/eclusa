# Phase 2: Executor and Cascade - Research

**Researched:** 2026-04-04
**Domain:** Stateless async Python executor loop, Postgres SKIP LOCKED dispatch, LISTEN/NOTIFY wake-hint, cascade graph traversal, cascade migration, error and retry policy
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Executor main loop uses `SELECT ... FOR UPDATE SKIP LOCKED` to claim ready stages — the exact query pattern from eclusa.md 5.1
- **D-02:** LISTEN/NOTIFY is a wake-hint layered on top of polling — executor polls on a ~1s interval, NOTIFY shortcuts the wait but is never the sole dispatch trigger
- **D-03:** Exponential backoff when no ready stages found (1s → 2s → 4s, cap at 5s), reset to 1s on NOTIFY or successful dispatch
- **D-04:** Executor is a single async Python process (~300-500 lines) using asyncpg for the hot path
- **D-05:** Stage type determines dispatch: `narrowing` → dispatch to compute backend (stub in Phase 2, real in Phase 3), `gate` → check auto-resolvability then surface
- **D-06:** Stage dispatch is a function call, not a message queue — executor calls dispatch_narrowing(stage) or surface_gate(stage) directly
- **D-07:** In Phase 2, dispatch_narrowing is a stub that marks the stage resolved immediately (real dispatch in Phase 3)
- **D-08:** surface_gate is a stub that logs the gate (real surfacing via adapters in Phase 5); auto-resolvable gates resolve immediately
- **D-09:** Cascade graph edges are `stage.depends_on: ulid[]` — a stage is ready when all depends_on stages are in terminal state (resolved/skipped)
- **D-10:** Branching is implicit: stages with no dependency on each other can dispatch in parallel
- **D-11:** Sub-cascades are regular cascades with a parent_stage_id linking back — the executor treats them identically
- **D-12:** A stage in state `blocked` is not ready until unblocked (e.g., gate resolution); sibling branches continue independently
- **D-13:** Migration is proposed by writing a pending migration record to the DB (new shape, reason, proposed_by actor)
- **D-14:** Executor checks for pending migrations at the start of each dispatch cycle — applies them before dispatching new stages
- **D-15:** Migration never interrupts a running work session — it applies on the next dispatch cycle after the current dispatch completes
- **D-16:** Migration is a ledger entry recording: cascade_id, old shape (snapshot), new shape (snapshot), reason, applied_at
- **D-17:** Stage failure policy is set at the cascade level: `on_stage_failure: retry | skip | fail_cascade`
- **D-18:** Default policy is `fail_cascade` — conservative; explicit opt-in for retry/skip
- **D-19:** Retry has a max count per stage (default 3); each retry is a new ledger entry
- **D-20:** When cascade fails, all pending stages are marked `skipped`, active stages are allowed to complete
- **D-21:** No application-level locking — SKIP LOCKED is the only coordination mechanism
- **D-22:** Multiple executor instances are fully independent; they share nothing except the DB
- **D-23:** LISTEN/NOTIFY channel names include cascade_id for selective wakeup (not a global channel)

### Claude's Discretion

- Exact asyncio event loop structure (single-task vs task-per-dispatch)
- Connection pool size and configuration
- Logging strategy (structured JSON vs plain text)
- Exact retry backoff for stage retries
- How to structure the executor as a Python module (single file vs package)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXEC-01 | Stateless executor loop polls ready stages via SKIP LOCKED and dispatches them | Core of this phase; SKIP LOCKED query, asyncpg transaction pattern documented below |
| EXEC-02 | LISTEN/NOTIFY used as wake-hint layered on top of SKIP LOCKED polling (not sole dispatch mechanism) | psycopg3 async notifies() iterator confirmed as correct interface; asyncpg add_listener also usable |
| EXEC-03 | Multiple executor instances can run concurrently without double-dispatch | SKIP LOCKED provides atomicity; confirmed in Postgres docs and Phase 1 research |
| EXEC-04 | Executor crash-restart recovers cleanly from DB state (no in-memory state lost) | Zero in-memory state principle — all state in stage/ledger rows; stage.state='active' rows with no active executor are claimed by next poll |
| EXEC-05 | Executor dispatches narrowing stages to work sessions or judgment passes based on stage config | Phase 2: dispatch_narrowing is a stub (marks resolved); real dispatch is Phase 3 |
| EXEC-06 | Executor surfaces gate stages to appropriate channels (Slack, email, webhook, back office) | Phase 2: surface_gate is a stub (logs); real surfacing is Phase 5 |
| EXEC-07 | Gate resolution callbacks write to DB and fire NOTIFY to unblock downstream stages | Phase 2: gate resolution is manual (INSERT into ledger); NOTIFY mechanism proven via LISTEN/NOTIFY research |
| CASC-01 | Cascade is a directed graph of stages with typed edges (depends_on) | stage.depends_on: UUID[] column exists in Phase 1 schema; readiness check is NOT EXISTS over depends_on |
| CASC-02 | Cascade supports branching (parallel work) — ambiguity in one branch doesn't block siblings | Branching is implicit in depends_on graph; SKIP LOCKED lets multiple executors claim parallel-ready stages |
| CASC-03 | Cascade supports nesting (sub-cascades spawned from stages) | Sub-cascades are regular cascades; parent_stage_id is tracked in cascade.shape JSONB per D-11 |
| CASC-04 | Cascade migration changes shape via data migration — running work sessions not interrupted mid-execution | Migration table/record pattern; executor checks for pending migrations per dispatch cycle |
| CASC-05 | Cascade migration is a ledger entry with old shape, new shape, and reason | ledger_type.cascade_migration exists in Phase 1 schema; content JSONB carries old_shape/new_shape/reason |
| CASC-06 | Cascade states: active, paused, completed, failed, evergreen | cascade_state enum is in Phase 1 schema: active/paused/completed/failed/evergreen |
| CASC-07 | Stage states: pending, active, blocked, resolved, skipped | stage_state enum is in Phase 1 schema: pending/active/blocked/resolved/skipped |
</phase_requirements>

---

## Summary

Phase 2 builds the execution engine for the cascade graph. The core algorithm is a single SQL query (`SELECT ... FOR UPDATE SKIP LOCKED`) wrapped in a polling loop that claims ready stages, dispatches them by type, and writes all state transitions to the append-only ledger. The design is deliberately minimal: no in-memory coordination state, no external queue, no workflow framework — Postgres IS the durable execution engine.

The SKIP LOCKED pattern provides multi-executor safety without application-level locking. A claimed stage row is locked for the duration of the executor's transaction window; other executor instances skip it and move on. A crashed executor's claimed rows become orphaned in `active` state; a recovery mechanism (see Pitfall 3 below) returns them to `pending` on the next dispatch cycle.

LISTEN/NOTIFY is a latency optimization, not a dispatch guarantee. The executor uses psycopg3's `AsyncConnection.notifies()` async iterator on a dedicated connection to receive wake signals from gate resolutions and stage completions. The canonical pattern (confirmed in Phase 1 research and PITFALLS.md) is: poll at interval → on NOTIFY arrive, skip the wait and poll immediately → on empty poll result, apply exponential backoff. A missed notification causes a delay of at most one backoff interval, not lost work.

Cascade migration in Phase 2 is a lightweight pattern: any code path (orchestrator, test fixture, manual INSERT) can write a pending migration record. The executor checks for pending migrations at the top of each dispatch cycle, applies the first approved one, writes a ledger entry, and continues. Running stages complete on their original shape. This is the data-migration model from eclusa.md §3.3 made concrete.

**Primary recommendation:** Build the executor as a Python package under `executor/` with four modules: `loop.py` (main loop + backoff), `dispatch.py` (type routing + stubs), `cascade.py` (graph readiness + migration), and `recovery.py` (stale active stage reclaim). Keep the total under 500 lines by keeping stubs minimal and deferring real compute backends to Phase 3.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncpg | 0.31.0 | Executor hot path: SKIP LOCKED poll, stage state writes | Fastest Python Postgres driver; binary protocol; established in Phase 1 (D-06 from Phase 1 CONTEXT.md) |
| psycopg | 3.3.3 | LISTEN/NOTIFY async notify iterator on dedicated connection | Native async notifies() generator; LISTEN on a connection that auto-reconnects; psycopg3 is richer for event-driven patterns |
| Python | 3.12+ | Executor runtime | Already established in pyproject.toml |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Async event loop, backoff via asyncio.wait_for, asyncio.sleep | All async coordination within the executor |
| python-ulid | 3.1.0+ | ULID generation for new ledger entries | Consistent with Phase 1 ID scheme (all IDs are ULIDs stored as UUIDs) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpg (hot path) + psycopg (LISTEN) | asyncpg only with add_listener | asyncpg's add_listener is connection-level but doesn't provide a clean async generator; psycopg3's notifies() is cleaner for the dedicated LISTEN connection |
| asyncpg (hot path) + psycopg (LISTEN) | psycopg only | asyncpg is marginally faster for the tight SKIP LOCKED loop where throughput matters |
| Hand-rolled executor module | pgqueuer library | pgqueuer provides SKIP LOCKED semantics out of the box but adds a dependency; the target is ~300-500 lines total which is achievable without it (D-04 decision locked) |

**Version verification:** asyncpg 0.31.0 and psycopg 3.3.3 are both already pinned in `pyproject.toml`. No additional packages are needed for Phase 2.

---

## Architecture Patterns

### Recommended Project Structure

```
executor/
├── __init__.py          # exports: run_executor()
├── loop.py              # main async loop, backoff, LISTEN/NOTIFY wake
├── dispatch.py          # type routing: dispatch_narrowing (stub), surface_gate (stub)
├── cascade.py           # graph readiness query, migration check/apply
└── recovery.py          # stale active stage reclaim (crash recovery)

tests/
├── conftest.py          # existing: testcontainers + Alembic (reuse as-is)
├── test_executor_loop.py
├── test_dispatch.py
├── test_cascade_graph.py
└── test_cascade_migration.py
```

**Why a package, not a single file:** The executor pseudocode is ~50 lines but the edge cases (recovery, migration, backoff, LISTEN setup) add ~300 more. Splitting into four coherent modules keeps each under 150 lines and makes the dispatch stub/real boundary obvious for Phase 3 replacement. The single-file alternative becomes hard to navigate when Phase 3 replaces the stubs.

### Pattern 1: SKIP LOCKED Stage Claim

**What:** Claim one or more ready stages atomically inside a transaction. Other executor instances skip locked rows and move on.

**When to use:** Every dispatch cycle — this is the only concurrency coordination mechanism (D-21).

**Critical detail:** The `FOR UPDATE SKIP LOCKED` must occur inside an explicit transaction. asyncpg's default autocommit mode will NOT hold the row lock across multiple statements. Use `conn.transaction()` context manager.

```python
# Source: eclusa.md §5.1 + asyncpg docs (connection.transaction())
# NOTE: stage.depends_on is UUID[] — the NOT EXISTS subquery uses = ANY()
async with pool.acquire() as conn:
    async with conn.transaction():
        rows = await conn.fetch("""
            SELECT s.id, s.type, s.cascade_id, s.depends_on, s.input
            FROM stage s
            JOIN cascade c ON s.cascade_id = c.id
            WHERE s.state = 'pending'
              AND c.state IN ('active', 'evergreen')
              AND NOT EXISTS (
                  SELECT 1 FROM stage dep
                  WHERE dep.id = ANY(s.depends_on)
                    AND dep.state NOT IN ('resolved', 'skipped')
              )
            FOR UPDATE OF s SKIP LOCKED
            LIMIT 10
        """)
        if rows:
            # Mark all claimed stages active inside the same transaction
            stage_ids = [r['id'] for r in rows]
            await conn.execute("""
                UPDATE stage SET state = 'active' WHERE id = ANY($1)
            """, stage_ids)
        # Transaction commits here; rows are now owned
```

**Why LIMIT 10:** Claims a batch per cycle to keep dispatch responsive. Adjust based on measured throughput; start at 10.

### Pattern 2: LISTEN/NOTIFY Wake-Hint on Dedicated Connection

**What:** A second asyncio task holds a dedicated psycopg3 AsyncConnection with LISTEN active. When a NOTIFY arrives, it sets an event that the main loop checks before sleeping its backoff interval.

**When to use:** As a latency optimization alongside polling. NEVER as the sole dispatch trigger (D-02, PITFALLS.md Pitfall 1).

```python
# Source: psycopg3 docs (AsyncConnection.notifies) + PITFALLS.md Pitfall 1
import asyncio
import psycopg

wake_event = asyncio.Event()

async def listen_task(db_url: str):
    """Dedicated LISTEN connection. Sets wake_event on any NOTIFY."""
    async with await psycopg.AsyncConnection.connect(db_url, autocommit=True) as conn:
        await conn.execute("LISTEN stage_changed")
        async for notify in conn.notifies():
            wake_event.set()   # wake the main loop early

async def poll_loop(pool, backoff_s: float = 1.0):
    while True:
        stages = await claim_ready_stages(pool)
        if stages:
            backoff_s = 1.0          # reset on successful dispatch
            await dispatch_batch(stages, pool)
        else:
            # Wait for NOTIFY or timeout — whichever comes first
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=backoff_s)
                backoff_s = 1.0      # NOTIFY arrived: reset backoff
            except asyncio.TimeoutError:
                backoff_s = min(backoff_s * 2, 5.0)   # D-03: cap at 5s
            finally:
                wake_event.clear()
```

**Channel naming per D-23:** The NOTIFY should include cascade_id to allow selective wakeup. The LISTEN in Phase 2 subscribes to a general `stage_changed` channel; selective channels are a Phase 5 optimization.

### Pattern 3: Stage State Transition with Ledger Write

**What:** Every stage state change writes two rows: UPDATE on `stage` table, INSERT on `ledger_entry`. Both happen in the same transaction.

**When to use:** Every stage transition (pending → active, active → resolved, active → skipped, etc.).

```python
# Source: eclusa.md §3.7 (ledger) + D-07/D-08/D-09 from Phase 1 CONTEXT.md
async def resolve_stage(conn, stage_id: str, output: dict, actor_id: str):
    """Mark stage resolved and write ledger entry — atomically."""
    async with conn.transaction():
        await conn.execute("""
            UPDATE stage
            SET state = 'resolved',
                output = $1::jsonb,
                resolved_at = NOW(),
                resolved_by = $2::uuid
            WHERE id = $3::uuid
        """, json.dumps(output), actor_id, stage_id)

        await conn.execute("""
            INSERT INTO ledger_entry
                (id, stage_id, cascade_id, actor_id, type, content, schema_version)
            SELECT
                gen_random_uuid(),
                s.id,
                s.cascade_id,
                $1::uuid,
                'stage_state_changed',
                jsonb_build_object(
                    'old_state', 'active',
                    'new_state', 'resolved',
                    'stage_id',  s.id::text
                ),
                '0001'
            FROM stage s WHERE s.id = $2::uuid
        """, actor_id, stage_id)
```

**Why gen_random_uuid() not Python ULID:** asyncpg does not pass Python-side defaults; must generate ID inside SQL. Phase 1 established this pattern (`[Phase 01-db-foundation]: SQLAlchemy Python-side default=new_id() doesn't apply to raw asyncpg SQL inserts`).

### Pattern 4: Cascade Migration Check/Apply

**What:** At the start of each dispatch cycle, query for pending migration records. Apply the first approved one: snapshot old shape, write new shape to cascade, write ledger entry with both shapes.

**When to use:** Top of every dispatch cycle, before the SKIP LOCKED claim (D-14).

```python
# Source: eclusa.md §3.3 (migration semantics) + D-13..D-16
async def apply_pending_migration(conn, system_actor_id: str) -> bool:
    """Apply one pending migration. Returns True if a migration was applied."""
    async with conn.transaction():
        # A 'cascade_migration' ledger entry with content->>'status'='pending'
        # represents a migration proposal not yet applied.
        # This uses a single table pattern: pending migrations are ledger entries
        # with a special pending status in content.
        row = await conn.fetchrow("""
            SELECT le.id, le.cascade_id, le.content
            FROM ledger_entry le
            WHERE le.type = 'cascade_migration'
              AND le.content->>'status' = 'pending'
            ORDER BY le.timestamp ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        if not row:
            return False

        cascade_id = row['cascade_id']
        new_shape = row['content']['new_shape']
        reason = row['content'].get('reason', '')

        # Snapshot old shape
        old_cascade = await conn.fetchrow(
            "SELECT shape FROM cascade WHERE id = $1::uuid", cascade_id
        )
        old_shape = old_cascade['shape']

        # Apply new shape
        await conn.execute("""
            UPDATE cascade SET shape = $1::jsonb WHERE id = $2::uuid
        """, json.dumps(new_shape), cascade_id)

        # Write completion ledger entry
        await conn.execute("""
            INSERT INTO ledger_entry
                (id, cascade_id, actor_id, type, content, schema_version)
            VALUES (
                gen_random_uuid(), $1::uuid, $2::uuid,
                'cascade_migration',
                jsonb_build_object(
                    'status', 'applied',
                    'old_shape', $3::jsonb,
                    'new_shape', $4::jsonb,
                    'reason', $5::text,
                    'applied_at', NOW()::text
                ),
                '0001'
            )
        """, cascade_id, system_actor_id,
             json.dumps(old_shape), json.dumps(new_shape), reason)

        # Mark original pending entry as applied
        await conn.execute("""
            UPDATE ledger_entry
            SET content = content || '{"status": "applied"}'::jsonb
            WHERE id = $1::uuid
        """, row['id'])

        return True
```

**Note:** The UPDATE on ledger_entry for the pending→applied transition violates strict append-only semantics. An alternative is to write a separate `applied` record and query for `pending` entries that lack a corresponding `applied` entry. The simpler pattern is used above; if strict append-only is required for migration records too, use the alternative pattern. Research finding: the existing ledger_type enum includes `cascade_migration` which is meant for completed migrations; Phase 2 needs a convention for pending migration proposals — either a separate table or a `content->>'status'` field. Recommend a dedicated `cascade_migration_proposal` table (see Open Questions).

### Pattern 5: Stale Active Stage Recovery

**What:** On executor startup, and periodically, scan for stages stuck in `active` state with no active dispatch (orphaned by a crashed executor). Return them to `pending` so the next dispatch cycle can reclaim them.

**When to use:** Executor startup, and every N cycles as a background check (D-04: crash-restart recovery).

```python
# Source: eclusa.md §5.1 (crash recovery note)
async def recover_stale_active_stages(conn, stale_threshold_seconds: int = 30):
    """Return orphaned 'active' stages to 'pending'.
    Stages stuck active > threshold with no heartbeat are assumed orphaned."""
    async with conn.transaction():
        recovered = await conn.fetch("""
            UPDATE stage
            SET state = 'pending'
            WHERE state = 'active'
              AND resolved_at IS NULL
              AND created_at < NOW() - ($1 || ' seconds')::interval
            RETURNING id, cascade_id
        """, stale_threshold_seconds)
    return recovered
```

**Caveats:** This pattern requires that legitimate active stages (dispatched by stubs in Phase 2) either resolve quickly or carry a heartbeat timestamp. In Phase 2 the stubs resolve immediately, so any truly orphaned `active` stage is provably from a crash. In Phase 3 (real work sessions, which are long-running), the threshold must be tuned to not reclaim legitimately running sessions — this is a Phase 3 concern, not Phase 2.

### Anti-Patterns to Avoid

- **In-memory pending gate list:** Never hold a list of surfaced gates in executor memory. Check the DB on each cycle. A restarted executor must discover gate state from the DB, not rebuild it.
- **NOTIFY inside the SKIP LOCKED transaction:** The SKIP LOCKED query and state update transaction should not contain a NOTIFY. NOTIFY inside a transaction fires on commit, which is fine, but the risk is that high-frequency commits cause global lock contention (PITFALLS.md Pitfall 1). Emit NOTIFY via a separate lightweight connection after the transaction commits.
- **Executing stage graph traversal as application code instead of SQL:** The depends_on readiness check must happen inside the SKIP LOCKED query. Moving it to application code means two round-trips to the DB and a TOCTOU race: another executor can claim the same stage between the readiness check and the claim.
- **Cascade state transitions not written to ledger:** Every cascade state change (active → completed, active → failed) must produce a ledger entry. The eclusa.md §3.7 guarantee is that the trace chain is always reconstructable from the ledger.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent stage claim without double-dispatch | Custom distributed lock, Redis SETNX | `SELECT ... FOR UPDATE SKIP LOCKED` | Postgres native; zero dependencies; atomic claim and state transition in one transaction |
| Async wake notification | Custom polling-only loop or custom TCP channel | psycopg3 `AsyncConnection.notifies()` | Native async generator; handles reconnect; one dedicated connection; no protocol to maintain |
| ULID generation inside SQL | Custom PL/pgSQL function | `gen_random_uuid()` | Phase 1 established pattern; asyncpg doesn't pass Python-side defaults to raw SQL; gen_random_uuid() is fast and sufficient |
| Cascade graph cycle detection | Application-level visited-set tracking | Postgres `CYCLE` clause on recursive CTEs | Native SQL:1999 syntax supported in PG14+; depth limit as secondary guard; trace_chain.sql already uses this pattern |
| Exponential backoff timer | asyncio.sleep() in a while loop | `asyncio.wait_for(event.wait(), timeout=backoff_s)` | Allows backoff to be interrupted by NOTIFY early; pure sleep cannot be interrupted |

**Key insight:** The executor's simplicity is its correctness guarantee. Every "clever" optimization that bypasses the DB round-trip introduces a window where the DB and executor state diverge. Postgres's transaction semantics ARE the coordination mechanism.

---

## Runtime State Inventory

> Phase 2 is a greenfield addition (executor/ directory does not yet exist). No rename or refactor. Omitting this section.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| asyncpg | Executor hot path | Already in pyproject.toml | 0.31.0 | — |
| psycopg[binary] | LISTEN/NOTIFY connection | Already in pyproject.toml | 3.3.3 | asyncpg add_listener (less ergonomic) |
| python-ulid | ULID generation in Python stubs | Already in pyproject.toml | 3.1.0+ | gen_random_uuid() for DB-generated IDs |
| testcontainers[postgres] | Executor integration tests | Already in dev dependencies | 4.14.2+ | — |
| paradedb/paradedb:latest (Docker) | Test container | Available (Phase 1 confirmed) | PG18 base | — |

**Missing dependencies with no fallback:** None — all executor dependencies are already declared.

**Missing dependencies with fallback:** None.

---

## Common Pitfalls

### Pitfall 1: SKIP LOCKED Without Explicit Transaction Loses the Lock

**What goes wrong:** asyncpg defaults to autocommit. A `FOR UPDATE SKIP LOCKED` query executed without an explicit transaction boundary holds the row lock only for the duration of that single statement. By the time the executor updates `stage.state = 'active'`, the lock is released, and another executor can claim the same row — causing double-dispatch.

**Why it happens:** The connection.transaction() context manager is easy to forget when writing the poll loop. Tests often work because the test executor is single-instance; double-dispatch only manifests under concurrent executor load.

**How to avoid:** Always wrap the SKIP LOCKED query AND the subsequent state UPDATE inside the same `async with conn.transaction():` block. The state transition must be atomic with the claim.

**Warning signs:** Staging rows appearing as `active` more than once across concurrent executors. Test with a 3-executor concurrency fixture explicitly.

---

### Pitfall 2: NOTIFY Emitted Inside the SKIP LOCKED Transaction

**What goes wrong:** If the executor fires `pg_notify('stage_changed', ...)` inside the same transaction that holds the SKIP LOCKED row, the NOTIFY fires on commit. Under concurrent write pressure (multiple executors dispatching simultaneously), many NOTIFYs in rapid succession cause lock contention on Postgres's notification queue. This is the PITFALLS.md Pitfall 1 scenario.

**Why it happens:** It is tempting to notify "stage became active" inside the dispatch transaction because it is conveniently co-located with the state change.

**How to avoid:** Emit NOTIFY after the transaction commits, using a separate short-lived connection or a fire-and-forget asyncio task. Phase 2's stubs resolve stages immediately — this means NOTIFY will be frequent. Keep NOTIFY out of the main dispatch transaction.

**Warning signs:** `pg_stat_activity` showing sessions waiting on lock during load test with 3+ executors.

---

### Pitfall 3: Orphaned Active Stages After Crash — Recovery Window

**What goes wrong:** An executor crashes while stages are in `active` state (claimed but not yet resolved). Those stages are stuck in `active` indefinitely unless the recovery mechanism reclaims them. The threshold for reclaim must be short enough that cascades do not stall, but long enough that legitimately running (Phase 3) work sessions are not prematurely reclaimed.

**Why it happens:** Phase 2 stubs resolve immediately, so this is not observable in Phase 2 testing. It becomes a real operational issue in Phase 3 when work sessions can run for minutes.

**How to avoid:** Set the Phase 2 stale threshold low (e.g., 30 seconds — stubs resolve in milliseconds). Document the threshold as a configurable parameter that Phase 3 must tune to match actual work session durations.

**Warning signs:** Stages stuck in `active` state more than 2× the expected dispatch-and-resolve time.

---

### Pitfall 4: Cascade Completion Not Computed Correctly

**What goes wrong:** A cascade is complete when ALL its stages are in terminal state (resolved or skipped). If the executor checks for "any stage pending" rather than "all stages terminal", a cascade with a failed branch may incorrectly remain `active` indefinitely.

**Why it happens:** The completion condition is a universal quantifier over a set — subtly different from checking for any pending work.

**How to avoid:** The cascade completion query must use `NOT EXISTS (SELECT 1 FROM stage WHERE cascade_id = $1 AND state NOT IN ('resolved', 'skipped', 'failed'))`. Write a dedicated test with a multi-branch cascade where one branch fails.

**Warning signs:** A cascade in `active` state whose stage list shows all rows in terminal states.

---

### Pitfall 5: Migration Proposal Table vs Ledger Append-Only Conflict

**What goes wrong:** D-13 says "write a pending migration record to the DB." If this pending record is a ledger_entry with `type='cascade_migration'`, and later the executor marks it `status='applied'` by updating that row, it violates the ledger's append-only guarantee. The trigger in Phase 1 schema will raise an exception.

**Why it happens:** The migration proposal needs a "pending / applied" lifecycle. Ledger entries are append-only and cannot be updated.

**How to avoid:** Two options:
1. **Separate table:** Add a `cascade_migration_proposal` table (not append-only) with `status: pending | applied | rejected`. The executor reads this table, applies the migration, then writes a `cascade_migration` ledger entry as the immutable record of what happened.
2. **Double ledger entry:** Write a `cascade_migration_proposal_created` ledger entry when the proposal is submitted, and a `cascade_migration` ledger entry when it is applied. The executor checks that no `cascade_migration` ledger entry exists for a given proposal before applying.

**Recommendation:** Option 1 (separate proposal table) is cleaner and avoids querying the ledger by content. Add `cascade_migration_proposal` as a new table in this phase via a new Alembic migration (0002).

**Warning signs:** Any `UPDATE` on `ledger_entry` in executor code — the Phase 1 trigger will reject it.

---

### Pitfall 6: depends_on Contains Stages from a Different Cascade

**What goes wrong:** If a cascade migration introduces new stages with depends_on edges pointing to stages from the old shape that have been logically removed, the readiness query never returns those stages as ready (their dependencies are in a non-existent or terminal-but-removed state). The cascade stalls.

**Why it happens:** Migration shape validation is not enforced at write time.

**How to avoid:** Migration application should validate that all stage IDs in every `depends_on` array belong to the same cascade. Write this as an assertion inside `apply_pending_migration`. The error should fail the migration, not the cascade.

**Warning signs:** Stages whose `depends_on` contains IDs that do not exist in the `stage` table.

---

## Code Examples

### Full Executor Loop (condensed)

```python
# Source: eclusa.md §5.1 (pseudocode elaboration)
# executor/loop.py

import asyncio
import asyncpg
import psycopg
import logging

logger = logging.getLogger(__name__)

async def run_executor(asyncpg_dsn: str, psycopg_dsn: str):
    pool = await asyncpg.create_pool(asyncpg_dsn, min_size=2, max_size=10)
    wake_event = asyncio.Event()

    listen_task = asyncio.create_task(
        _listen_for_changes(psycopg_dsn, wake_event)
    )
    poll_task = asyncio.create_task(
        _poll_loop(pool, wake_event)
    )

    try:
        await asyncio.gather(listen_task, poll_task)
    finally:
        await pool.close()

async def _listen_for_changes(psycopg_dsn: str, wake_event: asyncio.Event):
    """Dedicated LISTEN connection — sets wake_event on any NOTIFY."""
    async with await psycopg.AsyncConnection.connect(
        psycopg_dsn, autocommit=True
    ) as conn:
        await conn.execute("LISTEN stage_changed")
        async for _ in conn.notifies():
            wake_event.set()

async def _poll_loop(pool: asyncpg.Pool, wake_event: asyncio.Event):
    backoff = 1.0
    from .recovery import recover_stale_active_stages
    from .cascade import apply_pending_migration, claim_ready_stages
    from .dispatch import dispatch_stage

    # Startup recovery
    async with pool.acquire() as conn:
        recovered = await recover_stale_active_stages(conn)
        if recovered:
            logger.info(f"Recovered {len(recovered)} stale active stages on startup")

    while True:
        async with pool.acquire() as conn:
            await apply_pending_migration(conn)
            stages = await claim_ready_stages(conn)

        if stages:
            backoff = 1.0
            for stage in stages:
                asyncio.create_task(dispatch_stage(pool, stage))
        else:
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=backoff)
                backoff = 1.0
            except asyncio.TimeoutError:
                backoff = min(backoff * 2, 5.0)
            finally:
                wake_event.clear()
```

### Readiness Query (exact SQL)

```sql
-- Source: eclusa.md §5.1 — exact query pattern (decision D-01)
-- Claim up to 10 ready stages atomically.
-- A stage is ready when:
--   1. It is in 'pending' state
--   2. Its cascade is active or evergreen
--   3. All depends_on stages are in terminal state (resolved or skipped)
--   4. Row is not locked by another executor (SKIP LOCKED)

SELECT s.id, s.type, s.cascade_id, s.depends_on, s.input
FROM stage s
JOIN cascade c ON s.cascade_id = c.id
WHERE s.state = 'pending'
  AND c.state IN ('active', 'evergreen')
  AND NOT EXISTS (
      SELECT 1 FROM stage dep
      WHERE dep.id = ANY(s.depends_on)
        AND dep.state NOT IN ('resolved', 'skipped')
  )
FOR UPDATE OF s SKIP LOCKED
LIMIT 10
```

### Cascade Completion Check

```sql
-- Source: eclusa.md §3.3 (cascade completion semantics)
-- Mark cascade completed when all stages are terminal.

UPDATE cascade
SET state = 'completed', completed_at = NOW()
WHERE id = $1
  AND NOT EXISTS (
      SELECT 1 FROM stage
      WHERE cascade_id = $1
        AND state NOT IN ('resolved', 'skipped', 'failed')
  )
  AND state = 'active'
RETURNING id
```

### cascade_migration_proposal Table (new Alembic migration)

```python
# Source: Pitfall 5 above + D-13..D-16
# New migration: alembic/versions/0002_cascade_migration_proposal.py

op.create_table(
    "cascade_migration_proposal",
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("cascade_id", UUID(as_uuid=True), sa.ForeignKey("cascade.id"), nullable=False),
    sa.Column("proposed_by", UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False),
    sa.Column("new_shape", JSONB, nullable=False),
    sa.Column("reason", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False, server_default="pending"),
    # status: pending | applied | rejected
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
              server_default=sa.text("NOW()")),
    sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
)
op.execute("CREATE INDEX idx_migration_proposal_cascade_id ON cascade_migration_proposal(cascade_id)")
op.execute("CREATE INDEX idx_migration_proposal_status ON cascade_migration_proposal(status)")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| External workflow engines (Temporal, Celery+Redis) for durable execution | Postgres SKIP LOCKED as the execution engine | 2023-2025 adoption | No external coordinator dependency; crash-restart trivially safe |
| LISTEN/NOTIFY as primary dispatch | LISTEN/NOTIFY as wake-hint only (polling primary) | After production incidents at scale | Eliminates global lock contention under concurrent write load |
| Global NOTIFY channel | Per-entity NOTIFY channels (include cascade_id/stage_id) | psycopg3 adoption | Reduces unnecessary wakeups; selective dispatch |
| Recursive CTEs without CYCLE guard | CYCLE clause standard (PG14+) | Postgres 14 release | Eliminates infinite loops on cyclic graphs |

**Deprecated/outdated:**
- `asyncpg add_listener` on a pool connection: pool connections are recycled; the listener is attached to a specific connection that may be returned. Use a dedicated non-pooled connection for LISTEN, or use `psycopg3 notifies()` which handles this correctly.
- psycopg2: synchronous-only, no native async. Project already uses psycopg3 (confirmed in pyproject.toml).

---

## Open Questions

1. **cascade_migration_proposal table or double-ledger-entry pattern?**
   - What we know: Pending migration records need a mutable `status` field (pending → applied). The ledger is append-only and protected by a trigger.
   - What's unclear: Whether a separate table is acceptable given the project's "ledger as single source of truth" philosophy, or whether a double-entry pattern (proposal entry + completion entry) is preferred.
   - Recommendation: Separate `cascade_migration_proposal` table. Keeps the migration lifecycle mutable while preserving the immutable ledger record of applied migrations. Add it as migration 0002.

2. **Sub-cascade parent_stage_id — where is it stored?**
   - What we know: D-11 says sub-cascades are regular cascades with a `parent_stage_id` linking back. The `cascade` table in Phase 1 schema does NOT have a `parent_stage_id` column — the relationship is described as living in `cascade.shape` JSONB.
   - What's unclear: Whether the planner should add `parent_stage_id` as a real FK column (cleaner for queries) or keep it in JSONB (more flexible). The executor needs to traverse sub-cascade relationships to determine cascade completion.
   - Recommendation: Add `parent_stage_id UUID FK → stage.id NULLABLE` as a real column in migration 0002. This makes sub-cascade queries explicit and avoids JSONB parsing in the executor hot path.

3. **Stage failure policy — where is `on_stage_failure` stored?**
   - What we know: D-17 says policy is set at the cascade level. The `cascade` table has a `shape` JSONB column — the policy is presumably in `cascade.shape`.
   - What's unclear: Whether to add a dedicated `failure_policy` column to `cascade` or keep it in `shape` JSONB.
   - Recommendation: Add `failure_policy TEXT NOT NULL DEFAULT 'fail_cascade'` to the `cascade` table in migration 0002. Makes the policy readable without parsing JSONB and queryable for monitoring.

4. **Retry count tracking — where is it stored?**
   - What we know: D-19 says retry has a max count per stage (default 3); each retry is a new ledger entry.
   - What's unclear: How does the executor know the current retry count without reading all ledger entries for a stage? A dedicated `retry_count INTEGER` column on `stage` would be more efficient than `COUNT(*) FROM ledger_entry WHERE type = 'stage_state_changed'`.
   - Recommendation: Add `retry_count INTEGER NOT NULL DEFAULT 0` to the `stage` table in migration 0002. Increment atomically with the retry ledger entry.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (exists: `asyncio_mode = auto`) |
| Quick run command | `pytest tests/test_executor_loop.py tests/test_cascade_graph.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXEC-01 | Executor claims ready stages via SKIP LOCKED | integration | `pytest tests/test_executor_loop.py::test_claims_ready_stages -x` | Wave 0 |
| EXEC-02 | LISTEN/NOTIFY wakes executor early | integration | `pytest tests/test_executor_loop.py::test_notify_shortens_wait -x` | Wave 0 |
| EXEC-03 | 3 concurrent executors, no double-dispatch | integration | `pytest tests/test_executor_loop.py::test_no_double_dispatch_concurrent -x` | Wave 0 |
| EXEC-04 | Crash-restart reclaims orphaned active stages | integration | `pytest tests/test_executor_loop.py::test_crash_recovery -x` | Wave 0 |
| EXEC-05 | dispatch_narrowing stub marks stage resolved | unit | `pytest tests/test_dispatch.py::test_dispatch_narrowing_stub -x` | Wave 0 |
| EXEC-06 | surface_gate stub logs and does not block | unit | `pytest tests/test_dispatch.py::test_surface_gate_stub -x` | Wave 0 |
| EXEC-07 | Manual gate resolution unblocks downstream | integration | `pytest tests/test_cascade_graph.py::test_gate_resolution_unblocks_downstream -x` | Wave 0 |
| CASC-01 | Stage readiness requires all depends_on terminal | integration | `pytest tests/test_cascade_graph.py::test_readiness_requires_dependencies_terminal -x` | Wave 0 |
| CASC-02 | Parallel branches dispatch independently | integration | `pytest tests/test_cascade_graph.py::test_parallel_branches_independent -x` | Wave 0 |
| CASC-03 | Sub-cascade dispatched identically to top-level | integration | `pytest tests/test_cascade_graph.py::test_sub_cascade_dispatch -x` | Wave 0 |
| CASC-04 | Migration applies on next cycle, running stages unaffected | integration | `pytest tests/test_cascade_migration.py::test_migration_not_mid_execution -x` | Wave 0 |
| CASC-05 | Migration ledger entry has old_shape, new_shape, reason | integration | `pytest tests/test_cascade_migration.py::test_migration_ledger_entry -x` | Wave 0 |
| CASC-06 | Cascade state transitions (active→completed, active→failed) | integration | `pytest tests/test_cascade_graph.py::test_cascade_state_transitions -x` | Wave 0 |
| CASC-07 | Stage state machine (pending→active→resolved/skipped) | unit | `pytest tests/test_dispatch.py::test_stage_state_machine -x` | Wave 0 |
| (bonus) | 3 executors, 20 parallel stages, no stage twice | integration | `pytest tests/test_executor_loop.py::test_20_parallel_stages_no_duplicates -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_executor_loop.py tests/test_dispatch.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/eclusa:verify-work`

### Wave 0 Gaps

The following test files do not yet exist and must be created in Wave 0:

- [ ] `tests/test_executor_loop.py` — covers EXEC-01, EXEC-02, EXEC-03, EXEC-04
- [ ] `tests/test_dispatch.py` — covers EXEC-05, EXEC-06, CASC-07
- [ ] `tests/test_cascade_graph.py` — covers EXEC-07, CASC-01, CASC-02, CASC-03, CASC-06
- [ ] `tests/test_cascade_migration.py` — covers CASC-04, CASC-05

Existing infrastructure (`tests/conftest.py` with testcontainers + Alembic) is fully reusable. No new fixtures are needed beyond:
- A fixture that seeds a test cascade + stages in various topologies (linear, branching, sub-cascade)
- A fixture that starts multiple executor instances concurrently (for EXEC-03 concurrency test)

---

## Project Constraints (from CLAUDE.md)

- **Workflow discipline:** Use `/eclusa:execute-phase` for all planned phase work. Direct repo edits outside a Eclusa workflow are not permitted unless explicitly requested.
- **Python packaging:** Use `uv add`, never `pip install` or `uv pip install`.
- **Executor target size:** ~300-500 lines (eclusa.md §5.1 + D-04). Growing beyond this is a signal that something is wrong.
- **No ORM in the executor hot path:** Raw asyncpg SQL for the SKIP LOCKED loop. No SQLAlchemy in executor code (confirmed in CLAUDE.md and STACK.md).
- **Single Postgres instance:** No external queue, no Redis, no Celery (explicitly excluded in REQUIREMENTS.md Out of Scope).
- **All state in DB:** The executor carries no in-memory state between loop iterations.

---

## Sources

### Primary (HIGH confidence)

- `eclusa.md` §5.1–5.2 — executor pseudocode, stage dispatch patterns
- `eclusa.md` §3.3–3.4 — cascade and stage entity specifications
- `db/models/domain.py` + `db/models/compute.py` — exact column names, enum values (verified by direct file read)
- `alembic/versions/0001_initial_schema.py` — actual DDL, index names, constraints (verified by direct file read)
- `.eclusa/research/PITFALLS.md` — LISTEN/NOTIFY scale limits, recursive CTE cycle detection (MEDIUM→HIGH: Phase 1 research)
- `.eclusa/research/ARCHITECTURE.md` — executor component boundaries, build order

### Secondary (MEDIUM confidence)

- asyncpg PyPI (pypi.org/project/asyncpg) — 0.31.0 confirmed in pyproject.toml; `connection.transaction()` pattern documented
- psycopg3 docs (psycopg.org) — `AsyncConnection.notifies()` async generator pattern confirmed (multiple search results pointing to official docs)
- Phase 1 CONTEXT.md decisions (D-06, D-13) — asyncpg for hot path, testcontainers for tests

### Tertiary (LOW confidence)

- asyncpg-listen PyPI library — available as an alternative for LISTEN/NOTIFY if psycopg3 proves awkward; not recommended (adds dependency)
- Stack Overflow thread on asyncpg pool listeners — confirms pool connections are recycled and should not be used for persistent LISTEN; recommendation is dedicated connection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in pyproject.toml, versions pinned
- Architecture: HIGH — executor pattern directly from eclusa.md pseudocode + Phase 1 research
- Pitfalls: HIGH — SKIP LOCKED transaction boundary and NOTIFY contention are well-documented; migration/append-only conflict is confirmed by reading the Phase 1 trigger implementation

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable domain; asyncpg/psycopg APIs unlikely to change materially)
