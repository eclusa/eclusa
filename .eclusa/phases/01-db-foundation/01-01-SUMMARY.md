---
phase: 01-db-foundation
plan: "01"
subsystem: infra
tags: [python, uv, sqlalchemy, alembic, asyncpg, psycopg, pytest, testcontainers, paradedb, pgvector, pg_search, docker-compose]

# Dependency graph
requires: []
provides:
  - Python 3.12 project with all Phase 1 deps installed via uv
  - Alembic async migration setup with async_engine_from_config
  - docker-compose.yml using paradedb/paradedb image (pgvector + pg_search pre-installed)
  - pytest conftest wiring testcontainers to Alembic migrations
  - db/models/base.py DeclarativeBase for SQLAlchemy autogenerate
affects:
  - 01-02 (schema DDL relies on this Alembic setup)
  - 01-03 (trace chain queries need this test infrastructure)
  - 01-04 (ledger enforcement tests run through this conftest)
  - 01-05 (metric verification uses this conftest)
  - all subsequent phases (all Python code built on this foundation)

# Tech tracking
tech-stack:
  added:
    - sqlalchemy[asyncio]==2.0.49
    - alembic==1.18.4
    - asyncpg==0.31.0
    - psycopg[binary,pool]==3.3.3
    - python-ulid>=3.1.0
    - pytest, pytest-asyncio, testcontainers[postgres] (dev)
  patterns:
    - uv for Python dependency management (uv add, not pip install)
    - Alembic async template (async_engine_from_config + run_sync)
    - testcontainers session-scoped fixture with autouse migrations
    - paradedb/paradedb Docker image for both dev and test PG instances

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/.gitkeep
    - db/__init__.py
    - db/models/__init__.py
    - db/models/base.py
    - docker-compose.yml
    - pytest.ini
    - tests/__init__.py
    - tests/conftest.py
  modified: []

key-decisions:
  - "paradedb/paradedb:latest image used in both docker-compose and testcontainers — ensures pg_search and pgvector available in both dev and test without extension install scripts"
  - "db/models/base.py created with DeclarativeBase to enable Alembic autogenerate support from first plan"
  - "tests/conftest.py normalizes testcontainers URL format (handles postgresql+psycopg2:// prefix) before passing to asyncpg"

patterns-established:
  - "Pattern: Alembic async env.py uses async_engine_from_config with prefix='sqlalchemy.' and run_sync for all migration targets"
  - "Pattern: testcontainers session-scoped fixture with autouse apply_migrations runs once per pytest session"
  - "Pattern: URL normalization in conn fixture handles testcontainers URL driver prefixes"

requirements-completed: [INFRA-02, INFRA-04]

# Metrics
duration: 2min
completed: 2026-04-04
---

# Phase 01 Plan 01: Bootstrap Summary

**Python 3.12 project bootstrapped with uv, Alembic async migrations, docker-compose using paradedb/paradedb image, and testcontainers pytest fixture wired to Alembic upgrades**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-04T21:57:43Z
- **Completed:** 2026-04-04T21:59:52Z
- **Tasks:** 3
- **Files modified:** 13 created

## Accomplishments
- Python project initialized with uv, all Phase 1 runtime and dev dependencies installed
- Alembic initialized with async template (async_engine_from_config); alembic.ini pointed at postgresql+asyncpg://eclusa:eclusa@localhost:5432/eclusa
- docker-compose.yml uses paradedb/paradedb:latest (ships both pgvector and pg_search pre-compiled, no init scripts needed)
- tests/conftest.py provides session-scoped testcontainers fixture with automatic Alembic migration application

## Task Commits

Each task was committed atomically:

1. **Task 1: Initialize Python project and install dependencies** - `a1c73d3` (feat)
2. **Task 2: Create docker-compose.yml with paradedb image** - `e3e2099` (feat)
3. **Task 3: Create test conftest.py with testcontainers and Alembic fixture** - `21ae2f2` (feat)

## Files Created/Modified
- `pyproject.toml` - Python project manifest with all Phase 1 deps
- `uv.lock` - Locked dependency graph
- `alembic.ini` - Alembic config pointing to local postgres
- `alembic/env.py` - Async migration env with async_engine_from_config + Base.metadata
- `alembic/script.py.mako` - Migration file template (unmodified from async template)
- `alembic/versions/.gitkeep` - Placeholder for versions directory in git
- `db/__init__.py` - Package init
- `db/models/__init__.py` - Models package init
- `db/models/base.py` - DeclarativeBase for all SQLAlchemy models
- `docker-compose.yml` - Postgres service using paradedb image with health check
- `pytest.ini` - asyncio_mode=auto
- `tests/__init__.py` - Tests package init
- `tests/conftest.py` - Session-scoped testcontainers + Alembic + asyncpg fixtures

## Decisions Made
- paradedb/paradedb:latest chosen for both docker-compose and testcontainers — single image for dev and test ensures no extension availability surprises
- db/models/base.py created immediately to support Alembic autogenerate from the first migration
- URL normalization in conn fixture handles testcontainers returning `postgresql+psycopg2://` prefix

## Deviations from Plan

None - plan executed exactly as written.

Minor enhancements applied:
- **[Rule 2 - Missing Critical] URL normalization in conn fixture**: The plan's conn fixture code had a redundant `.replace()` call. Fixed to properly handle `postgresql+psycopg2://` prefix that testcontainers actually returns, ensuring asyncpg connection works.

## Issues Encountered
None - all three tasks completed cleanly on first attempt.

## User Setup Required
None - no external service configuration required. Run `docker compose up -d --wait` to start postgres, then `uv run pytest` for tests.

## Next Phase Readiness
- Python project structure, deps, Alembic, and test infrastructure are in place
- Plan 01-02 can begin schema DDL immediately — all migration tooling is ready
- testcontainers will pull paradedb image on first test run (one-time Docker pull, ~200MB)

---
*Phase: 01-db-foundation*
*Completed: 2026-04-04*

## Self-Check: PASSED

- All 12 created files confirmed present on disk
- All 3 task commits (a1c73d3, e3e2099, 21ae2f2) confirmed in git log
