---
description: Derive BDD/E2E test suite from source specs and compiled constraints
subagent_type: general-purpose
---

# eclusa:derive

Stage 5. Derives a BDD/E2E test suite from the matched source specs combined with the compiled Haskell constraints. Uses templates where patterns are standard, LLM generation for edge cases and domain-specific scenarios.

## Usage

```
/eclusa:derive          # derive test suite from specs + constraints
```

## Behavior

1. **Check prerequisites** — Verify constrain stage is complete (`constraints.hs` compiles). Fail otherwise.

2. **Load context** — Gather:
   - Matched source specs
   - Compiled constraint functions (names, signatures, descriptions)
   - Coherence report (for boundary test cases)
   - Project requirements

3. **Derive tests** — Invoke the derivation pipeline:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline derive
   ```
   This produces a test suite structured as:
   - **Template-driven tests** — CRUD operations, auth flows, standard validations derived from source specs
   - **Constraint-driven tests** — One or more tests per constraint function, ensuring each business rule is exercised
   - **Edge case tests** — LLM-generated scenarios for boundary conditions, error paths, and cross-source interactions identified during coherence

4. **Coverage check** — Verify every constraint has at least one corresponding test. Verify every matched source has at least one integration test. Report coverage summary.

5. **Human review** — Present the test suite summary: total tests, breakdown by category, any constraints lacking coverage. Human may request additional tests or approve.

## Gates

- Constrain stage complete (`constraints.hs` compiles cleanly).
- Every constraint function has at least one corresponding test.
- Every matched source has at least one integration test.
- Human has reviewed and approved the test suite.
