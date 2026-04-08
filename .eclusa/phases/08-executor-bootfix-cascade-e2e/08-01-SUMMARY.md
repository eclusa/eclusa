---
phase: 08-executor-bootfix-cascade-e2e
plan: 01
subsystem: infra
tags: [asyncpg, docker-compose, executor, actor-resolution, heartbeat]

# Dependency graph
requires:
  - phase: 02-executor-and-cascade
    provides: "Stateless executor loop with SKIP LOCKED + LISTEN/NOTIFY"
  - phase: 06-back-office-ui-and-self-calibration
    provides: "docker-compose full bootstrap with 5 services"
provides:
  - "Executor container starts and stays alive with correct actor UUID resolution"
  - "Heartbeat logging for liveness monitoring in docker-compose logs"
  - "restart: unless-stopped policy for crash recovery"
affects: [08-02-cascade-e2e, executor, docker-compose]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Actor identity-to-UUID resolution at startup before pool creation"
    - "Heartbeat logging every N poll cycles for liveness monitoring"
    - "PYTHONUNBUFFERED=1 for immediate log visibility in containers"

key-files:
  created: []
  modified:
    - executor/loop.py
    - docker-compose.yml

key-decisions:
  - "Actor resolution uses single asyncpg connection before pool creation (pool not available yet)"
  - "System actor created with type='system' and full resolve_gates permissions"
  - "Heartbeat every 10 poll cycles (not every cycle) to avoid log flooding"

patterns-established:
  - "_resolve_actor_id pattern: identity string -> UUID lookup/create before any $1::uuid cast"
  - "logging.basicConfig in docker-compose command for visible executor logs"

requirements-completed: [EXEC-E2E-01]

# Metrics
duration: 2min
completed: 2026-04-06
---

# Phase 08 Plan 01: Executor Boot Fix Summary

**Actor identity-to-UUID resolution at startup, restart policy, and heartbeat logging for executor container stability**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-06T15:15:35Z
- **Completed:** 2026-04-06T15:17:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Executor resolves "system-executor" identity string to actual UUID before entering poll loop, eliminating the $1::uuid cast failure
- Added `_resolve_actor_id()` helper that creates the system actor if it does not exist (mirrors chat_bridge.ensure_actor pattern)
- Heartbeat logging every 10 poll cycles for liveness monitoring
- Executor container has restart: unless-stopped policy and PYTHONUNBUFFERED=1 for immediate log visibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix executor startup -- actor UUID resolution and heartbeat logging** - `2319451` (feat)
2. **Task 2: Fix docker-compose executor config -- restart policy and DSN separation** - `deb4b9e` (fix)

## Files Created/Modified
- `executor/loop.py` - Added _resolve_actor_id() helper, changed run_executor to accept actor_identity and resolve to UUID, added heartbeat logging every 10 cycles, added startup log line
- `docker-compose.yml` - Added restart: unless-stopped to executor service, added logging.basicConfig to command, added PYTHONUNBUFFERED=1 to environment

## Decisions Made
- Actor resolution uses a single asyncpg connection (not the pool) because the pool has not been created yet at resolution time
- System actor is created with type='system' (not 'human') and full permissions matching the chat_bridge pattern
- Heartbeat logs every 10 cycles to balance visibility vs log noise

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Executor container should now start, connect to db:5432, resolve the system-executor actor, and enter the poll loop with heartbeat logging
- Plan 08-02 (cascade E2E) can now build on a running executor service

## Self-Check: PASSED

- All created/modified files exist on disk
- All task commits verified in git log (2319451, deb4b9e)
- No stubs or placeholders found in modified files

---
*Phase: 08-executor-bootfix-cascade-e2e*
*Completed: 2026-04-06*
