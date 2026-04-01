---
description: Generate implementation code against the derived test suite using the cheapest capable model
subagent_type: general-purpose
---

# eclusa:generate

Stage 6. Generates implementation code that passes the full derived test suite. Uses the cheapest capable model for code generation. Iterates until all tests pass.

## Usage

```
/eclusa:generate          # generate code against test suite
```

## Behavior

1. **Check prerequisites** — Verify derive stage is complete (test suite exists and was approved). Fail otherwise.

2. **Plan generation** — Analyze the test suite to determine:
   - Which modules/files need to be created
   - Dependency order for generation
   - Which model tier is appropriate (default: cheapest capable)

3. **Generate code** — Invoke the generation pipeline:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline generate
   ```
   The generator:
   - Creates implementation files module-by-module
   - Runs the test suite after each module
   - Tracks which tests are passing/failing

4. **Iterate on failures** — For each failing test:
   - Feed the test, error output, and current implementation to the model
   - Generate a fix
   - Re-run the failing test
   - Repeat (max 10 iterations per test, then escalate to human)

5. **Final verification** — Run the complete test suite end-to-end. All tests must pass.

6. **Report** — Present generation summary: files created, test results, model used, iteration count, any tests that required human escalation.

## Gates

- Derive stage complete (approved test suite exists).
- All derived tests pass against generated code.
- No test required more than 10 fix iterations without human input.
- Generated code has no lint/type errors in the target language.
