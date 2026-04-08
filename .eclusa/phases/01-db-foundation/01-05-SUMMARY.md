---
phase: 01-db-foundation
plan: "05"
subsystem: testing
tags: [pytest, testcontainers, docker-compose, paradedb, pgvector, pg_search, alembic]

# Dependency graph
requires:
  - phase: 01-db-foundation/01-03
    provides: "All 13 SQLAlchemy models and initial Alembic migration (0001)"
  - phase: 01-db-foundation/01-04
    provides: "Full test suite (5 test files covering all 9 SCHEMA requirements)"
provides:
  - "Verified green test suite — all 41 tests pass (0 failures, 0 errors)"
  - "docker-compose.yml boots paradedb/paradedb:latest (PG18) with pgvector + pg_search healthy"
  - "Alembic migration verified at head (0001) against live docker-compose postgres"
  - "All three day-one correctness invariants confirmed: schema_version present, append-only enforced, all 8 metrics computable"
  - "Phase 1 gate passed — schema frozen, ready for Phase 2 executor"
affects: [02-executor, 03-compute-primitives, 04-knowledge-layer, 05-adapters, 06-ui, 07-constraints]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "testcontainers fixture uses paradedb/paradedb:latest for consistent pgvector + pg_search in CI"
    - "docker-compose.yml volume mount at /var/lib/postgresql (not /var/lib/postgresql/data) for PG18+"

key-files:
  created: []
  modified:
    - docker-compose.yml

key-decisions:
  - "paradedb/paradedb:latest is now PostgreSQL 18 — volume mount must use /var/lib/postgresql (PG18 major-version-specific data directories)"
  - "alembic current requires a live DB connection — verification done via DATABASE_URL env override pointing to docker-compose postgres"

patterns-established:
  - "Phase gate: run uv run pytest tests/ -v --tb=short and verify all three day-one invariants before marking phase complete"
  - "docker-compose volume path: /var/lib/postgresql for paradedb/paradedb PG18+"

requirements-completed: [SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, SCHEMA-06, SCHEMA-07, SCHEMA-08, INFRA-02, INFRA-04]

# Metrics
duration: 2min
completed: "2026-04-04"
---

# Phase 01 Plan 05: Phase 1 Gate — Test Suite Green + Docker-Compose Verified Summary

**41-test pytest suite fully green with paradedb/paradedb (PG18) booting clean via docker-compose and all three day-one correctness invariants passing**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-04T22:22:51Z
- **Completed:** 2026-04-04T22:25:01Z
- **Tasks:** 3 (2 auto + 1 checkpoint auto-approved)
- **Files modified:** 1

## Accomplishments

- All 41 pytest tests pass: schema, ledger, trace chain, as-of timestamp, and all 8 metrics computable
- docker-compose.yml fixed for PG18 image (volume mount path changed) — db service boots healthy with both extensions
- Three day-one correctness invariants confirmed: `schema_version_present` PASSED, `ledger_entry_is_append_only` PASSED, all 8 `test_metric_is_computable` PASSED
- Alembic migration at head (0001) verified against live postgres via DATABASE_URL env override
- Phase 1 gate checkpoint auto-approved (auto mode active)

## Task Commits

Each task was committed atomically:

1. **Task 1: Run full test suite and capture output** — no file changes (verification only)
2. **Task 2: Verify docker-compose boots and extensions are available** — `4b529cb` (fix)
3. **Task 3: checkpoint:human-verify** — Auto-approved: Phase 1 DB Foundation complete

**Plan metadata:** (see final commit)

## Files Created/Modified

- `docker-compose.yml` — Fixed volume mount from `/var/lib/postgresql/data` to `/var/lib/postgresql` for paradedb/paradedb PG18 image

## Decisions Made

- paradedb/paradedb:latest upgraded to PG18. PG18 images store data in major-version-specific directories (`/var/lib/postgresql/18/docker`) requiring the volume mount at `/var/lib/postgresql` (parent path). The old `/var/lib/postgresql/data` mount path caused the container to exit immediately with an error about incompatible data directory format.
- `alembic current` cannot run without a live DB connection (env.py has `run_migrations_online()`). Verified via `DATABASE_URL=postgresql+asyncpg://eclusa:eclusa@localhost:5432/eclusa uv run alembic current` against the running docker-compose container. Showed `0001 (head)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed docker-compose.yml volume mount for paradedb/paradedb PG18**
- **Found during:** Task 2 (Verify docker-compose boots)
- **Issue:** `docker compose up --wait` exited with code 1. Logs showed: "PG18+ images store data in `/var/lib/postgresql/18/docker` and require mount at `/var/lib/postgresql` not `/var/lib/postgresql/data`"
- **Fix:** Changed `pg_data:/var/lib/postgresql/data` to `pg_data:/var/lib/postgresql` in docker-compose.yml
- **Files modified:** `docker-compose.yml`
- **Verification:** `docker compose up -d --wait` completed with `Container eclusa-db-1 Healthy`; both extensions confirmed via `SELECT extname FROM pg_extension`; migration applied successfully
- **Committed in:** `4b529cb` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Image was silently upgraded from PG17 to PG18 upstream. One-line volume path fix restores boot. No scope creep.

## Issues Encountered

- `uv run alembic current` fails without a live DB (asyncpg connection to localhost:5432 times out). Resolved by using `DATABASE_URL` env override pointing to docker-compose postgres. This is expected behavior for async Alembic env.py.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 1 DB foundation is complete and frozen. All 9 domain entities + 4 KG tables exist in a single migration (0001).
- Phase 2 (executor) can begin: models, enums, ledger enforcement, and all SQL query files are in place.
- Phase 3 (compute primitives) and Phase 4 (knowledge layer) can run in parallel per the established plan order.
- Blockers documented in STATE.md: Phase 3, 4, 5, 7 each need research phases before planning.

---
*Phase: 01-db-foundation*
*Completed: 2026-04-04*

## Self-Check: PASSED

- FOUND: `.eclusa/phases/01-db-foundation/01-05-SUMMARY.md`
- FOUND: `docker-compose.yml`
- FOUND: commit `4b529cb` (Task 2 fix)
- FOUND: commit `9648ed8` (plan metadata)
