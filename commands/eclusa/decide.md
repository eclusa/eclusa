---
description: List and resolve pending human decisions that cascaded up from pipeline stages
subagent_type: general-purpose
---

# eclusa:decide

Governance command. Pipeline stages escalate ambiguities and blocking decisions to this command. Lists all pending decisions, provides context for each, and records human resolutions back to the project file so the originating stage can proceed.

## Usage

```
/eclusa:decide              # list all pending decisions
/eclusa:decide --stage=cohere   # filter to decisions from a specific stage
```

## Behavior

1. **Load pending decisions** — Read the project file for all unresolved decisions. Each decision record includes:
   - Originating stage
   - Description of the ambiguity or conflict
   - Options identified by the stage
   - Impact assessment (what blocks if unresolved)

2. **Present decisions** — Show a numbered list. For each decision, display:
   - `[stage] description`
   - Options with trade-offs
   - What is currently blocked

3. **Resolve** — For each decision the human wants to resolve:
   - Record the chosen option
   - Record rationale (human provides or confirms generated rationale)
   - Write resolution to project file
   - Notify the originating stage that the decision is resolved

4. **Defer** — Decisions can be deferred with a reason. Deferred decisions do not block the pipeline unless they are marked as blocking.

5. **Audit trail** — All decisions and resolutions are appended to the project decision log with timestamps.

## Gates

- Decision list is accurately loaded from project file.
- Each resolution includes a rationale.
- Resolved decisions are written back to project file.
- Blocking decisions that remain unresolved are clearly surfaced.
