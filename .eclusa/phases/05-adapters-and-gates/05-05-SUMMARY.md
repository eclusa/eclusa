---
phase: 05-adapters-and-gates
plan: "05"
subsystem: adapters
tags: [email, smtp, aiosmtplib, EmailAdapter, gate-surfacing, multipart]

# Dependency graph
requires:
  - phase: 05-01
    provides: AdapterProtocol ABC, GateContext dataclass, adapter registry skeleton
  - phase: 05-03
    provides: gate dispatch routing, surface_gate call in executor dispatch

provides:
  - gate_email_plain() — plain-text gate notification with resolve URL and gate context
  - gate_email_html() — HTML email with inline-styled resolve button and blockquote recommendation
  - send_gate_email() — multipart SMTP send via aiosmtplib with STARTTLS
  - EmailAdapter.surface_gate() — calls send_gate_email for all eligible_actor_ids

affects:
  - 05-06 (RBAC resolve endpoint wires through the same email gate flow)
  - 06 (back office UI will display gate resolution status)

# Tech tracking
tech-stack:
  added: [aiosmtplib (send_gate_email SMTP send), email.message.EmailMessage (multipart build)]
  patterns:
    - "EmailAdapter treats eligible_actor_ids as email addresses in v1 — actor.identity holds email"
    - "send_gate_email accepts to_addresses: list[str] — single SMTP call for all actors"
    - "Multipart email: set_content(plain) + add_alternative(html, subtype='html')"
    - "aiosmtplib.send() with start_tls=True — STARTTLS on port 587"

key-files:
  created: []
  modified:
    - adapters/email/templates.py
    - adapters/email/outbound.py
    - adapters/email/adapter.py
    - tests/test_email_adapter.py

key-decisions:
  - "send_gate_email signature uses to_addresses: list[str] (not single 'to') — enables single SMTP call to all eligible actors"
  - "EmailAdapter stores from_addr as constructor param (not in stub) — allows custom sender per deployment"
  - "eligible_actor_ids are treated as email addresses in v1 — actor.identity column holds email"

patterns-established:
  - "Template functions take GateContext, not individual fields — consistent pattern across all email templates"
  - "EmailAdapter.surface_gate logs warning on empty eligible_actor_ids rather than raising"

requirements-completed:
  - ADAPT-03

# Metrics
duration: 4min
completed: 2026-04-05
---

# Phase 05 Plan 05: Email Outbound — SMTP Gate Notification Summary

**EmailAdapter.surface_gate() wires gate context to aiosmtplib multipart SMTP with plain+HTML templates and signed resolve URL**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-05T05:32:29Z
- **Completed:** 2026-04-05T05:36:47Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented `gate_email_plain()` and `gate_email_html()` rendering GateContext into plain-text and inline-styled HTML email bodies
- Implemented `send_gate_email()` using `aiosmtplib.send()` with STARTTLS — builds multipart `EmailMessage` with correct headers
- Implemented `EmailAdapter.surface_gate()` — gets eligible_actor_ids as email addresses, delegates to `send_gate_email`, logs on empty list
- `test_smtp_gate_email_sent` passes with mocked `aiosmtplib.send` — verifies To, Subject, plain body resolve_url and gate_description
- Full test suite: 258 passed (up from 257 + 1 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: templates + outbound + EmailAdapter.surface_gate** - `d642258` (feat)
2. **Task 2: test_smtp_gate_email_sent** - `aec95f8` (feat)

## Files Created/Modified

- `adapters/email/templates.py` — `gate_email_plain()` and `gate_email_html()` with GateContext rendering
- `adapters/email/outbound.py` — `send_gate_email()` via aiosmtplib with STARTTLS, imports templates
- `adapters/email/adapter.py` — `EmailAdapter` with `from_addr` param, full `surface_gate()` with logging
- `tests/test_email_adapter.py` — `test_smtp_gate_email_sent` implemented; `test_resolve_endpoint_rbac` expanded by linter with async-safe httpx approach (all 4 tests now pass)

## Decisions Made

- `send_gate_email` accepts `to_addresses: list[str]` (not single string) — single SMTP call covers all eligible actors
- `EmailAdapter` adds `from_addr: str = "eclusa@localhost"` constructor parameter (was missing from stub) — deployment-configurable sender
- `eligible_actor_ids` treated as email addresses in v1 per plan spec — actor.identity column holds email

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `from_addr` parameter to EmailAdapter constructor**
- **Found during:** Task 1 (adapter.py implementation)
- **Issue:** Stub `EmailAdapter.__init__` lacked `from_addr` parameter; plan spec explicitly included it but stub omitted it
- **Fix:** Added `from_addr: str = "eclusa@localhost"` to constructor and passed it through to `send_gate_email`
- **Files modified:** adapters/email/adapter.py
- **Verification:** Import check passes; EmailAdapter(smtp_host="localhost") works with default from_addr
- **Committed in:** d642258 (Task 1)

**2. [Rule 1 - Linter auto-expansion] test_resolve_endpoint_rbac expanded by linter with async implementation**
- **Found during:** Task 2 (test file implementation)
- **Issue:** Linter replaced `@pytest.mark.skip` stub with full implementation using `httpx.AsyncClient + ASGITransport` — avoids asyncpg event-loop mismatch with TestClient
- **Fix:** Accepted the expansion — all 4 tests pass; `adapters/web/routes.py` already exists from Plan 05-03/04
- **Files modified:** tests/test_email_adapter.py
- **Verification:** 258 passed, 0 skipped
- **Committed in:** aec95f8 (Task 2)

---

**Total deviations:** 2 (1 missing param, 1 linter-driven test expansion)
**Impact on plan:** Both beneficial — from_addr enables deployment flexibility; test_resolve_endpoint_rbac advancing to pass is net improvement.

## Issues Encountered

None — implementation was straightforward.

## User Setup Required

None — no external service configuration required. SMTP credentials are passed at runtime.

## Next Phase Readiness

- EmailAdapter fully wired: templates → outbound → adapter → executor dispatch
- ADAPT-03 (email gate surfacing) complete
- Plan 05-06: RBAC resolve endpoint (`POST /gates/{stage_id}/resolve`) — `adapters/web/routes.py` exists, test_resolve_endpoint_rbac already passes
- Full suite green at 258 passed

---
*Phase: 05-adapters-and-gates*
*Completed: 2026-04-05*
