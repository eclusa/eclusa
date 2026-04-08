# Phase 1: DB Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 01-db-foundation
**Areas discussed:** ID strategy, Migration approach, Ledger enforcement, Temporal column design, Testing strategy
**Mode:** Auto (all decisions auto-selected from recommended defaults)

---

## ID Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| ULID (Recommended) | Sortable by creation time, UUID-compatible, no coordination for generation | ✓ |
| UUID v7 | Time-ordered UUID, native PG type, newer standard | |
| Sequential bigint | Simplest, best index performance, leaks ordering info | |

**User's choice:** [auto] ULID — recommended default; RFC specifies `id: ulid` on all entities
**Notes:** Stored as native UUID type for index efficiency, generated as ULID for sortability

---

## Migration Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic async + SQLAlchemy 2.0 (Recommended) | Industry standard, declarative models, async support | ✓ |
| Raw SQL migrations | Full control, no ORM dependency, manual version tracking | |
| Prisma Migrate | TypeScript ecosystem, simpler API, less Python-native | |

**User's choice:** [auto] Alembic async + SQLAlchemy 2.0 — recommended by research; ORM for declaration only, direct SQL in executor
**Notes:** Every migration populates schema_version on ledger entries

---

## Ledger Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Application role + trigger (Recommended) | No UPDATE/DELETE grants + defense-in-depth trigger | ✓ |
| Application role only | Simpler, relies on role-based access control alone | |
| Row-level security | More granular, more complex to manage | |

**User's choice:** [auto] Application role + trigger — defense-in-depth per RFC's "sacred record" language
**Notes:** Corrections are new entries referencing superseded entries, never mutations

---

## Temporal Column Design

| Option | Description | Selected |
|--------|-------------|----------|
| Four separate timestamptz columns (Recommended) | Clear, portable, explicit semantics | ✓ |
| Range types (tstzrange) | Postgres-native, built-in overlap operators | |
| PG17 WITHOUT OVERLAPS only | Leverage new PG17 feature, limited to uni-temporal | |

**User's choice:** [auto] Four separate columns — PG17 WITHOUT OVERLAPS is uni-temporal only; full bi-temporal needs explicit columns
**Notes:** Range types considered for future optimization

---

## Testing Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| pytest + testcontainers (Recommended) | Real Postgres, no mocks, production-equivalent tests | ✓ |
| pgTAP | SQL-native testing, runs inside Postgres | |
| pytest + SQLite mock | Faster, less realistic, misses Postgres-specific features | |

**User's choice:** [auto] pytest + testcontainers — integration tests against real DB, no mocks
**Notes:** Metric formulas verified as SQL queries against seeded test data

---

## Claude's Discretion

- Column naming conventions
- Index strategy beyond HNSW
- Constraint naming conventions
- Test fixture generation
- Alembic migration naming

## Deferred Ideas

None
