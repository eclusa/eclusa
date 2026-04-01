---
description: Scaffold Haskell type modules from matched sources, draft constraint functions, iterate until GHC compiles
subagent_type: general-purpose
---

# eclusa:constrain

Stage 4. Scaffolds `constraints.hs` and supporting Haskell type modules auto-generated from matched source schemas. An LLM drafts constraint functions that encode business rules. Iterates compilation with `ghc -fno-code` until the constraint module type-checks.

## Usage

```
/eclusa:constrain          # scaffold, generate, and verify constraints
```

## Behavior

1. **Check prerequisites** — Verify coherence stage is complete (no unresolved blocking issues). Fail otherwise.

2. **Scaffold types** — Generate Haskell type modules from matched source schemas:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline formalize
   ```
   This creates `Types.hs` modules representing each matched source's data model.

3. **Draft constraints** — Using the source specs, coherence report, and scaffolded types as context, draft constraint functions in `constraints.hs`. Constraints encode:
   - Invariants from source specs (e.g., "order total must equal sum of line items")
   - Cross-source boundary rules surfaced during coherence
   - Domain rules from requirements

4. **Compile check** — Verify the constraint module type-checks:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline check-constraints
   ```
   This runs `ghc -fno-code` on the constraint module.

5. **Iterate on failure** — If compilation fails:
   - Parse GHC error output
   - Fix type errors in constraints or type modules
   - Re-run `pipeline check-constraints`
   - Repeat until clean compilation (max 5 iterations, then escalate to human)

6. **Human review** — Present the final constraint set to the human. Each constraint shows: name, source rule, Haskell signature, and plain-English description.

## Gates

- Coherence stage complete with no unresolved blockers.
- All type modules compile individually.
- `constraints.hs` compiles with `ghc -fno-code` (zero errors).
- Human has reviewed and approved the constraint set.
