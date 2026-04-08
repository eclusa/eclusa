# Phase 5: Adapters and Gates - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Gate mechanism: gate stages suspend cascade execution, surface to humans via email (only external adapter in v1), and unblock downstream on resolution. RBAC defines who resolves which gates. Adapter layer treats all inbound messages as untrusted raw text (trust boundary) before executor ingestion. Replaces the surface_gate() stub from Phase 2. Slack and WhatsApp adapters deferred to a future milestone.

</domain>

<decisions>
## Implementation Decisions

### Gate mechanism
- **D-01:** Gate stages suspend their cascade branch; sibling branches continue independently (already implemented in executor/cascade.py)
- **D-02:** Gate surfacing replaces the stub in executor/dispatch.py:surface_gate() — real dispatch to adapters
- **D-03:** Gate resolution writes to DB and fires NOTIFY (already stubbed in executor/dispatch.py:resolve_gate())
- **D-04:** Gate context includes: cascade_id, stage_id, gate description, model recommendation (if fan-out ran), actors eligible to resolve
- **D-05:** Cascade-id-scoped NOTIFY channels (D-23 from Phase 2, deferred to here): `pg_notify('stage_changed:{cascade_id}', ...)`

### Email adapter (only external adapter in v1)
- **D-06:** aioimaplib for async IMAP polling (inbound) + aiosmtplib for outbound notifications
- **D-07:** Inbound: poll IMAP inbox → parse email → create intent
- **D-08:** Gate surfacing: email thread with gate context + reply-to-resolve pattern
- **D-09:** Idempotent deduplication: Message-ID header as idempotency key
- **D-10:** Email DKIM/SPF verification informational (not blocking) — log but don't reject

### RBAC enforcement
- **D-11:** actor.permissions JSONB column (exists from Phase 1) stores permission grants: `{"resolve_gates": ["gate_type_a", "gate_type_b"], "view_costs": true, "spawn_cascades": true}`
- **D-12:** Permission check in resolve_gate() path: actor must have resolve permission for the gate's type
- **D-13:** Cost visibility restricted to actors with `view_costs: true` permission
- **D-14:** RBAC is checked at the API/adapter boundary, not in the executor — executor trusts that callers are authorized

### Trust boundary
- **D-15:** All inbound adapter messages are raw untrusted text — never passed directly to judgment passes or the executor
- **D-16:** Structured sanitization: strip control characters, validate length limits, extract structured fields (intent type, priority, description)
- **D-17:** Sanitized intent is a Pydantic model validated before DB insertion

### Claude's Discretion
- Email HTML template design for gate surfacing
- IMAP polling interval
- Rate limiting strategy
- Exactly which fields are stripped during sanitization
- Reply parsing strategy (plain text vs structured)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Adapter specifications
- `eclusa.md` §6 — Adapter layer: intent ingestion, gate surfacing, channel types
- `eclusa.md` §6.3 — Email adapter: IMAP/SMTP, threading (only external adapter in v1)

### Gate mechanism
- `eclusa.md` §3.4 — Gate stage type, auto-resolvability, resolution callbacks
- `eclusa.md` §8 — RBAC: decision delegation, permission model

### Existing code
- `executor/dispatch.py` — `surface_gate()` and `resolve_gate()` stubs to replace
- `executor/cascade.py` — Gate blocking behavior already implemented
- `db/models/domain.py` — Actor model with permissions JSONB, Intent model

### Research findings
- `.eclusa/research/STACK.md` — aioimaplib, aiosmtplib (Slack/WhatsApp deferred)
- `.eclusa/research/PITFALLS.md` — Adapter layer is widest prompt injection surface

### Prior phase context
- `.eclusa/phases/02-executor-and-cascade/02-CONTEXT.md` — D-23 deferred: cascade_id-scoped NOTIFY

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `executor/dispatch.py` — surface_gate() stub + resolve_gate() stub to replace
- `executor/loop.py` — LISTEN/NOTIFY infrastructure (needs cascade_id scoping)
- `db/models/domain.py` — Actor.permissions JSONB, Intent model
- `tests/conftest.py` — Testcontainers Postgres fixture

### Established Patterns
- asyncpg for direct SQL (Phases 1-4)
- Ledger entries for all state changes
- TDD: stubs → red → implement → green

### Integration Points
- `executor/dispatch.py:surface_gate()` — replace stub with adapter dispatch
- `executor/dispatch.py:resolve_gate()` — add RBAC check before resolution
- `executor/loop.py` — update LISTEN channel to cascade_id-scoped
- FastAPI endpoints for webhook receivers (Twilio, email relay)

</code_context>

<specifics>
## Specific Ideas

- 80% of users never open eclusa directly — adapters ARE the product surface (email first, Slack/WhatsApp in future milestone)
- Gate surfacing must include enough context for the human to make a decision without opening the back office
- The trust boundary is not optional — raw email messages are a significant attack surface
- The adapter interface should be generic enough that adding Slack/WhatsApp later doesn't require refactoring the gate mechanism

</specifics>

<deferred>
## Deferred Ideas

- **Slack adapter** — Bolt framework + Socket Mode / Events API. Deferred to future milestone per user decision.
- **WhatsApp adapter** — Twilio webhook + X-Twilio-Signature verification. Deferred to future milestone per user decision.

</deferred>

---

*Phase: 05-adapters-and-gates*
*Context gathered: 2026-04-05*
