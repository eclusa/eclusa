---
description: Check matched source set for composition issues — type boundaries, auth models, data friction, missing links
subagent_type: general-purpose
---

# eclusa:cohere

Stage 3. Analyzes the matched source set for coherence issues that would block downstream constraint formalization or code generation. Surfaces type boundary mismatches, conflicting auth models, data model friction, and missing relational links.

## Usage

```
/eclusa:cohere          # run coherence analysis on current matched sources
```

## Prerequisite

Requires schema commons to be enabled (`schema_commons.enabled: true` in config). If not enabled, display:
```
Schema commons is not enabled. The cohere command requires matched sources from eclusa:match.
Enable with: node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" config-set schema_commons.enabled true
```
Exit without proceeding.

## Behavior

1. **Load matched sources** — Read `sources.matched` from the project file. Fail if match stage has not been completed.

2. **Run coherence check** — Invoke the pipeline coherence analyzer:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline coherence
   ```
   This returns a structured report of composition issues.

3. **Analyze with Sonnet** — The coherence output is context for a Sonnet-class model to perform deeper analysis. Feed the report plus the matched source schemas to the model. Ask it to identify:
   - Type boundary conflicts (e.g., `userId: string` vs `userId: int`)
   - Auth model incompatibilities (e.g., JWT vs session-based across sources)
   - Data model friction (e.g., missing foreign keys, naming collisions)
   - Missing links (e.g., source A references entity from source B, but B is not matched)

4. **Present findings** — Show the human a prioritized list of issues. Each issue includes: severity (blocking/warning), affected sources, description, and suggested resolution.

5. **Resolve or accept** — For each blocking issue, the human must either:
   - Go back to match stage to add/remove sources
   - Accept with an explicit rationale (recorded in project file)
   - Escalate to `/eclusa:decide`

## Gates

- `sources.matched` exists and is non-empty.
- Zero blocking coherence issues remain (all resolved or accepted with rationale).
- Coherence report is persisted to project file for downstream stages.
