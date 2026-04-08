# Phase 04 — Deferred Items

## DI-04-01: Add UNIQUE constraint on entity.name

**Found during:** Plan 04-04 (embed pipeline)
**Severity:** Low (single-tenant, no real concurrency risk)

The `entity` table created in Phase 1 migration `0001_initial_schema.py` has no
UNIQUE constraint on the `name` column. The embed pipeline uses a
SELECT-then-INSERT/UPDATE upsert pattern instead of `ON CONFLICT (name) DO UPDATE`.

Under concurrent executor invocations with overlapping schemas, this could produce
duplicate entity rows for the same name.

**Recommended fix:** Add a migration:
```sql
CREATE UNIQUE INDEX CONCURRENTLY idx_entity_name_unique ON entity(name);
```
Then update embed.py to use `ON CONFLICT (name) DO UPDATE SET embedding = EXCLUDED.embedding, updated_at = EXCLUDED.updated_at`.

**Impact:** Until fixed, duplicate entity rows for the same name are possible under
concurrent embed calls. Safe for single-tenant single-executor deployment.
