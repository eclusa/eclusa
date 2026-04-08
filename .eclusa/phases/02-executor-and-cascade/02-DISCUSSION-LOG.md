# Phase 2: Executor and Cascade - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 02-executor-and-cascade
**Areas discussed:** Polling strategy, Dispatch routing, Cascade migration, Error handling, Concurrency model
**Mode:** Auto (all decisions auto-selected from recommended defaults)

---

## Polling Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| SKIP LOCKED + NOTIFY wake-hint (Recommended) | Hybrid: poll ~1s, NOTIFY shortcuts wait | ✓ |
| LISTEN/NOTIFY only | Event-driven, no polling — causes global PG lock contention | |
| Pure polling | Simple, no NOTIFY — wastes cycles on idle | |

**User's choice:** [auto] Hybrid — per research pitfall about NOTIFY-only dispatch
**Notes:** Exponential backoff 1s→5s when idle, reset on NOTIFY or dispatch

---

## Dispatch Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Stage type + config (Recommended) | Type determines compute backend, config refines | ✓ |
| Message queue | Decouple dispatch via queue — adds external dependency | |
| Direct function call | Simplest, executor calls dispatch directly | ✓ (same as recommended) |

**User's choice:** [auto] Stage type determines routing; function call dispatch, not message queue

---

## Cascade Migration

| Option | Description | Selected |
|--------|-------------|----------|
| Next dispatch cycle (Recommended) | Migration applies on next cycle, never interrupts running work | ✓ |
| Immediate | Interrupt and migrate mid-dispatch — risky | |
| Manual trigger | Human must trigger migration application | |

**User's choice:** [auto] Next dispatch cycle — consistent with RFC §3.3 migration semantics

---

## Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Cascade-level policy (Recommended) | on_stage_failure: retry/skip/fail_cascade per cascade config | ✓ |
| Always fail cascade | Conservative but inflexible | |
| Always retry | Risky for non-idempotent stages | |

**User's choice:** [auto] Cascade-level policy with fail_cascade as default

---

## Concurrency Model

| Option | Description | Selected |
|--------|-------------|----------|
| SKIP LOCKED only (Recommended) | No app-level locking, PG handles coordination | ✓ |
| Advisory locks | Application-level locking on top of SKIP LOCKED | |
| Single executor | No concurrency, simplest — doesn't scale | |

**User's choice:** [auto] SKIP LOCKED only — per RFC design

## Claude's Discretion

- asyncio event loop structure
- Connection pool sizing
- Logging strategy
- Module structure

## Deferred Ideas

None
