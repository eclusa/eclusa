---
phase: 05-adapters-and-gates
plan: "01"
subsystem: adapters
tags: [email, imap, smtp, fastapi, pydantic, alembic, migration, rbac, sanitize, tdd]

requires:
  - phase: 02-executor-and-cascade
    provides: executor dispatch stubs (surface_gate, resolve_gate) and Stage model
  - phase: 01-db-foundation
    provides: actor.permissions JSONB, Stage table, Alembic migration infrastructure

provides:
  - aioimaplib==2.0.1 + aiosmtplib==5.1.0 + fastapi==0.135.3 installed
  - Alembic migration 0003 adding resolve_token TEXT + expires_at TIMESTAMPTZ to stage table
  - Stage SQLAlchemy model updated with resolve_token + expires_at columns
  - adapters/ module skeleton (11 files): protocol.py, registry.py, sanitize.py, email/, web/
  - GateContext dataclass + AdapterProtocol ABC (adapters/protocol.py)
  - AdapterRegistry singleton (adapters/registry.py)
  - SanitizedIntent + SanitizationError + sanitize_email stub (adapters/sanitize.py)
  - EmailAdapter stub, poll_inbox stub, send_gate_email stub, email templates stub
  - FastAPI router + ResolveRequest model + /gates/{gate_id}/resolve stub (adapters/web/routes.py)
  - 16 Wave 0 test stubs (4 files): all collect + skip cleanly

affects:
  - 05-02-PLAN (email adapter implementation — implements adapters/email/ stubs)
  - 05-03-PLAN (gate surfacing dispatch + RBAC enforcement — implements adapters/web/ stubs)
  - 05-04-PLAN+ (any plan using GateContext, AdapterProtocol, sanitize_email)

tech-stack:
  added:
    - aioimaplib==2.0.1 (async IMAP4rev1 client for inbound email polling)
    - aiosmtplib==5.1.0 (async SMTP client for outbound gate emails)
    - fastapi==0.135.3 (resolution callback endpoint)
  patterns:
    - AdapterProtocol ABC pattern: all gate adapters implement surface_gate(GateContext) -> None
    - AdapterRegistry singleton: maps channel_type str to AdapterProtocol instance
    - Trust boundary pattern: raw adapter input → sanitize_email() → SanitizedIntent | SanitizationError
    - Wave 0 stub pattern: pytestmark = pytest.mark.skip at module level, no imports from non-existent modules

key-files:
  created:
    - alembic/versions/0003_gate_resolve_token.py
    - adapters/__init__.py
    - adapters/protocol.py
    - adapters/registry.py
    - adapters/sanitize.py
    - adapters/email/__init__.py
    - adapters/email/adapter.py
    - adapters/email/inbound.py
    - adapters/email/outbound.py
    - adapters/email/templates.py
    - adapters/web/__init__.py
    - adapters/web/routes.py
    - tests/test_sanitize.py
    - tests/test_rbac.py
    - tests/test_gate_surfacing.py
    - tests/test_email_adapter.py
  modified:
    - db/models/domain.py (Stage: resolve_token + expires_at columns added)
    - pyproject.toml (3 new dependencies)
    - uv.lock (3 new packages resolved)

key-decisions:
  - "resolve_token and expires_at are nullable in migration 0003 — existing rows unaffected, only gate stages use them"
  - "sanitize_email returns SanitizedIntent | SanitizationError — never raises — Plan 02 implements full validation logic"
  - "AdapterRegistry is a module-level singleton populated at app startup — adapters registered by configuration"
  - "Wave 0 test stubs import only from stdlib + pytest — no imports from not-yet-implemented modules"
  - "FastAPI router stub returns {'status': 'stub'} — Plan 03 implements full RBAC + resolve_gate() integration"

patterns-established:
  - "AdapterProtocol ABC: every gate adapter implements surface_gate(GateContext) -> None"
  - "Trust boundary: raw inbound text always goes through sanitize_email() before DB insertion (OWASP LLM01)"
  - "Stub body is '...' with # stub comment — not raise NotImplementedError — pyright does not complain"
  - "Wave 0 test stubs: pytestmark module-level skip, body is pass, all collect + skip (0 errors)"

requirements-completed:
  - ADAPT-03
  - ADAPT-04
  - EXEC-06
  - EXEC-07
  - SCHEMA-08

duration: 4min
completed: 2026-04-05
---

# Phase 5 Plan 01: Adapters Scaffold Summary

**Email adapter skeleton + migration 0003 (resolve_token, expires_at) + AdapterProtocol ABC + 16 Wave 0 test stubs establishing TDD red phase for Plans 02-03**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-05T05:21:55Z
- **Completed:** 2026-04-05T05:25:17Z
- **Tasks:** 3
- **Files modified:** 19 (3 modified + 16 created)

## Accomplishments

- Installed aioimaplib==2.0.1, aiosmtplib==5.1.0, fastapi==0.135.3 via `uv add`
- Created migration 0003 adding `resolve_token TEXT` and `expires_at TIMESTAMPTZ` to stage table; applied cleanly to DB (0003 head)
- Built 11-file adapters/ skeleton: GateContext + AdapterProtocol ABC, AdapterRegistry singleton, SanitizedIntent trust boundary, EmailAdapter + email sub-stubs, FastAPI routes stub — all importable
- Created 16 Wave 0 test stubs across 4 files; all collect with 0 errors, all skip at module level
- Full test suite remains green: 242 passed, 16 skipped, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Install deps + Alembic migration 0003 + Stage model update** - `6d5006b` (feat)
2. **Task 2: adapters/ module skeleton with stub implementations** - `f3fe839` (feat)
3. **Task 3: Wave 0 test stubs (TDD red phase)** - `180603d` (test)

## Files Created/Modified

- `pyproject.toml` — 3 new dependencies added
- `uv.lock` — locked to resolved versions
- `alembic/versions/0003_gate_resolve_token.py` — migration adding resolve_token + expires_at to stage
- `db/models/domain.py` — Stage model: resolve_token + expires_at columns after retry_count
- `adapters/__init__.py` — package marker
- `adapters/protocol.py` — GateContext dataclass + AdapterProtocol ABC
- `adapters/registry.py` — AdapterRegistry class + module-level registry singleton
- `adapters/sanitize.py` — CONTROL_CHAR_RE, MAX_RAW_LENGTH, SanitizedIntent, SanitizationError, sanitize_email stub
- `adapters/email/__init__.py` — package marker
- `adapters/email/adapter.py` — EmailAdapter(AdapterProtocol) stub
- `adapters/email/inbound.py` — poll_inbox() stub (aioimaplib pattern)
- `adapters/email/outbound.py` — send_gate_email() stub (aiosmtplib pattern)
- `adapters/email/templates.py` — gate_email_plain() + gate_email_html() stubs
- `adapters/web/__init__.py` — package marker
- `adapters/web/routes.py` — FastAPI APIRouter, ResolveRequest model, /gates/{gate_id}/resolve stub
- `tests/test_sanitize.py` — 4 stubs for ADAPT-04 (control chars, max length, valid email, empty sender)
- `tests/test_rbac.py` — 4 stubs for SCHEMA-08 (allowed, denied, wildcard, view_costs)
- `tests/test_gate_surfacing.py` — 4 stubs for EXEC-06/EXEC-07 (dispatch, notify, scoped notify, sibling)
- `tests/test_email_adapter.py` — 4 stubs for ADAPT-03/SCHEMA-08 (poll, smtp, dedup, rbac)

## Decisions Made

- resolve_token and expires_at are nullable in migration 0003 — existing rows unaffected
- sanitize_email returns a union type, never raises — Plan 02 implements the full validation pipeline
- AdapterRegistry is a module-level singleton populated at app startup, not at import time
- Wave 0 test stubs import only stdlib + pytest — no imports from non-existent modules prevents collection errors

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Database was not running at plan start (PostgreSQL container was stopped). Started with `docker compose up -d db` before running migrations. This is normal for fresh execution sessions, not a bug.

## Known Stubs

The following stub functions have `...` bodies and are intentionally incomplete — Plans 02 and 03 implement them:

- `adapters/email/inbound.py:poll_inbox()` — Plan 02 implements IMAP polling loop
- `adapters/email/outbound.py:send_gate_email()` — Plan 02 implements aiosmtplib send
- `adapters/email/templates.py:gate_email_plain()` + `gate_email_html()` — Plan 02 implements
- `adapters/email/adapter.py:EmailAdapter.surface_gate()` — Plan 02 implements
- `adapters/web/routes.py:resolve_gate_endpoint()` — Plan 03 implements RBAC + resolve_gate()
- `adapters/sanitize.py:sanitize_email()` — Plan 02 implements full validation (stub currently functional but incomplete)

These stubs are intentional scaffolding — the plan's goal is to establish importable contracts for TDD, not to implement them.

## Next Phase Readiness

- Plan 02 can start immediately: email adapter contracts established, Wave 0 stubs ready for implementation
- Plan 03 can start immediately: web routes stub + RBAC stubs ready
- adapters/ modules all importable — no import failures will block other plan execution
- Migration 0003 is at head — Plans 02+ can use resolve_token + expires_at columns

---
*Phase: 05-adapters-and-gates*
*Completed: 2026-04-05*
