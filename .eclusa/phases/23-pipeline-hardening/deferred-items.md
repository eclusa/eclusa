# Deferred Items — Phase 23 Pipeline Hardening

## Out-of-scope findings logged during plan execution

### test_dispatch_scc_fanout_calls_run_fan_out_with_db_and_uses_raw_intent_fallback

**Discovered during:** Plan 23-01, Task 1 (GREEN phase)
**File:** tests/test_scc_fanout.py line 88
**Issue:** Test hardcodes `assert kwargs["models"] == ["anthropic:claude-3-5-haiku-latest"]` but the current environment resolves `SCC_FANOUT_MODELS` (or equivalent) to `['openai:glm-5.1']`. Pre-existing failure confirmed — fails on commits prior to 23-01 changes.
**Impact:** Test suite always fails on this env. The behavior under test (model list resolution) is correct; the assertion is stale.
**Resolution:** Update test to use `_normalize_model_list(...)` against the current env default, or parameterize. Not a correctness bug in handler code.
**Priority:** Low — does not affect pipeline correctness.

### test_dispatch_scc_refine_calls_work_session_lifecycle

**Discovered during:** Plan 23-03, Task 2 verification
**File:** tests/test_scc_refine.py line 55
**Issue:** Test hardcodes `assert session_row["model"] == "anthropic:claude-3-5-haiku-latest"` but current environment resolves `SCC_MODEL_DEFAULT` (or `SCC_MODEL_REFINE`) to `openai:glm-5.1`. Pre-existing failure confirmed — fails on commits prior to 23-03 changes.
**Impact:** Test assertion is stale. Refine handler behavior is correct.
**Resolution:** Update assertion to compare against `_resolve_model("refine")` dynamically.
**Priority:** Low — does not affect pipeline correctness.
