---
description: Full diagnostic — validation, provenance, decisions, enforcement
subagent_type: general-purpose
---

# eclusa:diagnose

Run a full diagnostic on the project. Checks provenance chain, project file validity, pipeline state, constraints compilation, and enforcement of stances.

## Usage

```
/eclusa:diagnose
```

## Behavior

1. Run diagnostic:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" diagnose
```

2. Display results for each area:
   - **Provenance:** Chain integrity, hash mismatches
   - **Project file:** Exists, valid, schema version
   - **Constraints:** Exists, compiled status
   - **Pipeline state:** Stage progress, pending/in-progress count
   - **Decisions:** Any unresolved human decisions

3. For each issue found, provide an actionable fix command.
