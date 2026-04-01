---
description: Run full eclusa pipeline (stages 1-6) in sequence with human checkpoints between each stage
subagent_type: eclusa-planner
---

# eclusa:pipeline

Orchestrates the full six-stage eclusa pipeline in sequence. Each stage runs to completion, presents results for human review, and only advances after explicit approval. Any stage can cascade decisions up to `/eclusa:decide`.

## Usage

```
/eclusa:pipeline                    # start from stage 1 (or resume from last completed)
/eclusa:pipeline --from=cohere      # resume from a specific stage
/eclusa:pipeline --dry-run          # show what would run without executing
```

## Behavior

1. **Check state** — Read the project file to determine which stages are complete. If resuming, validate all prerequisite stages are satisfied.

2. **Stage 1+2: Match** — Invoke `/eclusa:match`. Wait for human confirmation of source set.

3. **Checkpoint** — Confirm with human: "Match complete. Proceed to coherence? [y/n]"

4. **Stage 3: Cohere** — Invoke `/eclusa:cohere`. Wait for all blocking issues to be resolved.

5. **Checkpoint** — Confirm with human: "Coherence verified. Proceed to constraints? [y/n]"

6. **Stage 4: Constrain** — Invoke `/eclusa:constrain`. Wait for GHC compilation and human review.

7. **Checkpoint** — Confirm with human: "Constraints compiled. Proceed to test derivation? [y/n]"

8. **Stage 5: Derive** — Invoke `/eclusa:derive`. Wait for coverage verification and human review.

9. **Checkpoint** — Confirm with human: "Test suite derived. Proceed to code generation? [y/n]"

10. **Stage 6: Generate** — Invoke `/eclusa:generate`. Wait for all tests to pass.

11. **Pipeline complete** — Report final summary: stages completed, decisions made, artifacts produced.

## Gates

- Each stage must pass its own gates before the pipeline advances.
- Human must explicitly approve at each checkpoint.
- Any pending decisions from `/eclusa:decide` must be resolved before the pipeline can complete.
- Project file records completion status of each stage for resumability.
