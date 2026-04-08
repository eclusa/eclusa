"""Initial schema — all domain entities, knowledge graph tables, ledger enforcement.

Revision ID: 0001
Revises:
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# CRITICAL (per D-05, PITFALLS.md Pitfall 1): schema_version MUST be in the first migration.
# Adding it later requires mutating immutable ledger rows, which violates the append-only guarantee.
SCHEMA_VERSION = "0001"


def upgrade() -> None:
    # =========================================================================
    # Step 1 — Extensions
    # =========================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")

    # =========================================================================
    # Step 2 — All enum types (exact values per eclusa.md §3)
    # =========================================================================
    op.execute("""
    CREATE TYPE intent_source AS ENUM (
        'slack_message', 'email', 'voice', 'chat', 'webhook', 'api',
        'cli', 'figma_comment', 'notion_page', 'lark_message',
        'github_issue', 'manual'
    )
    """)

    op.execute("""
    CREATE TYPE actor_type AS ENUM (
        'human', 'agent', 'system', 'webhook'
    )
    """)

    op.execute("""
    CREATE TYPE cascade_state AS ENUM (
        'active', 'paused', 'completed', 'failed', 'evergreen'
    )
    """)

    op.execute("""
    CREATE TYPE stage_type AS ENUM (
        'narrowing', 'gate'
    )
    """)

    op.execute("""
    CREATE TYPE stage_state AS ENUM (
        'pending', 'active', 'blocked', 'resolved', 'skipped'
    )
    """)

    op.execute("""
    CREATE TYPE work_session_state AS ENUM (
        'running', 'paused', 'completed', 'failed'
    )
    """)

    op.execute("""
    CREATE TYPE artifact_type AS ENUM (
        'git_commit', 'git_branch', 'git_pr', 'api_request', 'api_response',
        'deployment', 'file_created', 'message_sent', 'webhook_out',
        'config_change', 'external_state'
    )
    """)

    op.execute("""
    CREATE TYPE fan_out_verdict AS ENUM (
        'converged', 'diverged', 'partial'
    )
    """)

    # CRITICAL (PITFALL 6): ledger_type must include ALL values needed for the
    # 8 self-calibration metrics: gate_surfaced, gate_resolved, gate_auto_resolved,
    # cascade_reopened, orchestrator_absorbed.
    op.execute("""
    CREATE TYPE ledger_type AS ENUM (
        'intent_created', 'cascade_created', 'cascade_state_changed', 'cascade_migration',
        'stage_created', 'stage_state_changed', 'work_session_started', 'work_session_paused',
        'work_session_resumed', 'work_session_completed', 'work_session_failed',
        'judgment_pass_created', 'judgment_pass_completed',
        'fan_out_created', 'fan_out_completed',
        'artifact_created',
        'gate_surfaced', 'gate_resolved', 'gate_auto_resolved',
        'cascade_reopened', 'orchestrator_absorbed', 'schema_migration'
    )
    """)

    # =========================================================================
    # Step 3 — Create application role (if not exists)
    # =========================================================================
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eclusa_app') THEN
        CREATE ROLE eclusa_app;
      END IF;
    END
    $$;
    """)

    # =========================================================================
    # Step 4 — Create all 13 tables in dependency order
    # =========================================================================
    # actor (no foreign key dependencies)
    op.create_table(
        "actor",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("identity", sa.Text, nullable=False),
        sa.Column("permissions", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    # Replace text type for actor.type with the enum
    op.execute(
        "ALTER TABLE actor ALTER COLUMN type TYPE actor_type USING type::actor_type"
    )

    # intent (depends on actor)
    op.create_table(
        "intent",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "parent_id", UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=True
        ),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("raw", sa.Text, nullable=False),
        sa.Column("context", JSONB, nullable=True),
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder — cast below
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_by", UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False
        ),
    )
    op.execute(
        "ALTER TABLE intent ALTER COLUMN source TYPE intent_source USING source::intent_source"
    )
    op.execute("ALTER TABLE intent DROP COLUMN embedding")
    op.execute("ALTER TABLE intent ADD COLUMN embedding vector(1024)")

    # cascade (depends on intent)
    op.create_table(
        "cascade",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intent_id", UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=False
        ),
        sa.Column("shape", JSONB, nullable=False),
        sa.Column("annotations", JSONB, nullable=True),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder — cast below
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "ALTER TABLE cascade ALTER COLUMN state TYPE cascade_state USING state::cascade_state"
    )
    op.execute("ALTER TABLE cascade DROP COLUMN embedding")
    op.execute("ALTER TABLE cascade ADD COLUMN embedding vector(1024)")

    # stage (depends on cascade, actor)
    op.create_table(
        "stage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cascade_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cascade.id"),
            nullable=False,
        ),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column(
            "depends_on",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "served_by",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "resolved_by", UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=True
        ),
    )
    op.execute(
        "ALTER TABLE stage ALTER COLUMN type TYPE stage_type USING type::stage_type"
    )
    op.execute(
        "ALTER TABLE stage ALTER COLUMN state TYPE stage_state USING state::stage_state"
    )

    # work_session (no FK dependencies to other new tables)
    op.create_table(
        "work_session",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stage_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("harness_type", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("model_swaps", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "message_history", JSONB, nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("workspace_ref", sa.Text, nullable=True),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("cost", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("paused_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resumed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "ALTER TABLE work_session ALTER COLUMN state TYPE work_session_state USING state::work_session_state"
    )

    # judgment_pass (no FK dependencies to other new tables)
    op.create_table(
        "judgment_pass",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stage_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("context_ref", sa.Text, nullable=False),
        sa.Column("context_hash", sa.Text, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response", JSONB, nullable=True),
        sa.Column("confidence", sa.Numeric, nullable=True),
        sa.Column("cost", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # fan_out (depends on stage)
    op.create_table(
        "fan_out",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stage_id", UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=False
        ),
        sa.Column("context_ref", sa.Text, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column(
            "passes",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("convergence", JSONB, nullable=True),
        sa.Column("verdict", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "ALTER TABLE fan_out ALTER COLUMN verdict TYPE fan_out_verdict USING verdict::fan_out_verdict"
    )

    # artifact (depends on intent, cascade, stage)
    op.create_table(
        "artifact",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intent_id", UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=False
        ),
        sa.Column(
            "cascade_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cascade.id"),
            nullable=False,
        ),
        sa.Column(
            "stage_id", UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=False
        ),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("external_ref", sa.Text, nullable=True),
        sa.Column("external_sys", sa.Text, nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.execute(
        "ALTER TABLE artifact ALTER COLUMN type TYPE artifact_type USING type::artifact_type"
    )

    # ledger_entry — THE CRITICAL TABLE (depends on intent, cascade, stage, actor)
    op.create_table(
        "ledger_entry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "intent_id", UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=True
        ),
        sa.Column(
            "cascade_id", UUID(as_uuid=True), sa.ForeignKey("cascade.id"), nullable=True
        ),
        sa.Column(
            "stage_id", UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=True
        ),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "actor_id", UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False
        ),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("content", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("confidence", sa.Numeric, nullable=True),
        sa.Column(
            "reversible", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "artifact_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # CRITICAL (SCHEMA-03): schema_version must be present from first migration.
        # Cannot be added retroactively without mutating immutable rows.
        sa.Column(
            "schema_version",
            sa.String(10),
            nullable=False,
            server_default=SCHEMA_VERSION,
        ),
    )
    op.execute(
        "ALTER TABLE ledger_entry ALTER COLUMN type TYPE ledger_type USING type::ledger_type"
    )

    # tool (depends on actor)
    op.create_table(
        "tool",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("interface", JSONB, nullable=False),
        sa.Column("auth_ref", sa.Text, nullable=True),
        sa.Column("cost_profile", JSONB, nullable=True),
        sa.Column(
            "registered_by",
            UUID(as_uuid=True),
            sa.ForeignKey("actor.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Knowledge Graph tables
    # episode (no FK dependencies)
    op.create_table(
        "episode",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("reference_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "schema_version",
            sa.String(10),
            nullable=False,
            server_default=SCHEMA_VERSION,
        ),
    )

    # entity (no FK dependencies)
    op.create_table(
        "entity",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder — cast below
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.execute("ALTER TABLE entity DROP COLUMN embedding")
    op.execute("ALTER TABLE entity ADD COLUMN embedding vector(1024)")

    # fact (depends on entity) — bi-temporal per D-10
    op.create_table(
        "fact",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_entity",
            UUID(as_uuid=True),
            sa.ForeignKey("entity.id"),
            nullable=False,
        ),
        sa.Column(
            "target_entity",
            UUID(as_uuid=True),
            sa.ForeignKey("entity.id"),
            nullable=False,
        ),
        sa.Column("predicate", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=True),  # placeholder — cast below
        sa.Column("t_valid", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("t_invalid", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "t_created",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("t_expired", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "source_episodes",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "schema_version",
            sa.String(10),
            nullable=False,
            server_default=SCHEMA_VERSION,
        ),
    )
    op.execute("ALTER TABLE fact DROP COLUMN embedding")
    op.execute("ALTER TABLE fact ADD COLUMN embedding vector(1024)")

    # community (no FK dependencies)
    op.create_table(
        "community",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "entity_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # =========================================================================
    # Step 5 — Ledger enforcement (Layer 1: REVOKE) per D-07
    # =========================================================================
    op.execute("REVOKE UPDATE, DELETE ON ledger_entry FROM eclusa_app")

    # =========================================================================
    # Step 6 — Ledger enforcement (Layer 2: trigger) per D-08
    # Defense-in-depth: catches misuse even from privileged connections
    # =========================================================================
    op.execute("""
    CREATE OR REPLACE FUNCTION ledger_entry_immutability_guard()
    RETURNS TRIGGER AS $$
    BEGIN
      RAISE EXCEPTION 'ledger_entry is append-only: UPDATE and DELETE are forbidden. '
                      'Create a new entry referencing the superseded entry instead.';
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER enforce_ledger_immutability
    BEFORE UPDATE OR DELETE ON ledger_entry
    FOR EACH ROW EXECUTE FUNCTION ledger_entry_immutability_guard();
    """)

    # =========================================================================
    # Step 7 — HNSW indexes on all vector(1024) columns per D-18
    # Create on empty tables — avoids expensive rebuild on populated tables (Pitfall 3)
    # =========================================================================
    op.execute("""
    CREATE INDEX idx_intent_embedding ON intent
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
    CREATE INDEX idx_cascade_embedding ON cascade
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
    CREATE INDEX idx_entity_embedding ON entity
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
    CREATE INDEX idx_fact_embedding ON fact
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64)
    """)

    # =========================================================================
    # Step 8 — pg_search BM25 index on entity text columns per INFRA-04
    # Uses pg_search 0.22+ USING bm25 API (paradedb.create_bm25 was removed)
    # =========================================================================
    op.execute("""
    CREATE INDEX entity_bm25
    ON entity
    USING bm25(id, name, summary)
    WITH (key_field='id', text_fields = '{"name": {}, "summary": {}}')
    """)

    # =========================================================================
    # Step 9 — B-tree indexes on high-cardinality FK and query columns
    # =========================================================================
    op.execute("CREATE INDEX idx_stage_cascade_id ON stage(cascade_id)")
    op.execute("CREATE INDEX idx_stage_state ON stage(state)")
    op.execute(
        "CREATE INDEX idx_ledger_entry_timestamp ON ledger_entry(timestamp DESC)"
    )
    op.execute("CREATE INDEX idx_ledger_entry_type ON ledger_entry(type)")
    op.execute("CREATE INDEX idx_ledger_entry_intent_id ON ledger_entry(intent_id)")
    op.execute("CREATE INDEX idx_artifact_intent_id ON artifact(intent_id)")

    # =========================================================================
    # Step 10 — GIN indexes on JSONB columns for future query performance
    # =========================================================================
    op.execute(
        "CREATE INDEX idx_ledger_entry_content ON ledger_entry USING gin(content)"
    )
    op.execute("CREATE INDEX idx_stage_input ON stage USING gin(input)")


def downgrade() -> None:
    # Drop in reverse order

    # Step 10 — GIN indexes
    op.execute("DROP INDEX IF EXISTS idx_stage_input")
    op.execute("DROP INDEX IF EXISTS idx_ledger_entry_content")

    # Step 9 — B-tree indexes
    op.execute("DROP INDEX IF EXISTS idx_artifact_intent_id")
    op.execute("DROP INDEX IF EXISTS idx_ledger_entry_intent_id")
    op.execute("DROP INDEX IF EXISTS idx_ledger_entry_type")
    op.execute("DROP INDEX IF EXISTS idx_ledger_entry_timestamp")
    op.execute("DROP INDEX IF EXISTS idx_stage_state")
    op.execute("DROP INDEX IF EXISTS idx_stage_cascade_id")

    # Step 8 — BM25 index (pg_search 0.22+ USING bm25 API)
    op.execute("DROP INDEX IF EXISTS entity_bm25")

    # Step 7 — HNSW indexes
    op.execute("DROP INDEX IF EXISTS idx_fact_embedding")
    op.execute("DROP INDEX IF EXISTS idx_entity_embedding")
    op.execute("DROP INDEX IF EXISTS idx_cascade_embedding")
    op.execute("DROP INDEX IF EXISTS idx_intent_embedding")

    # Step 6 — trigger and function
    op.execute("DROP TRIGGER IF EXISTS enforce_ledger_immutability ON ledger_entry")
    op.execute("DROP FUNCTION IF EXISTS ledger_entry_immutability_guard()")

    # Step 4 — tables in reverse dependency order
    op.drop_table("community")
    op.drop_table("fact")
    op.drop_table("entity")
    op.drop_table("episode")
    op.drop_table("tool")
    op.drop_table("ledger_entry")
    op.drop_table("artifact")
    op.drop_table("fan_out")
    op.drop_table("judgment_pass")
    op.drop_table("work_session")
    op.drop_table("stage")
    op.drop_table("cascade")
    op.drop_table("intent")
    op.drop_table("actor")

    # Step 2 — enum types
    op.execute("DROP TYPE IF EXISTS ledger_type")
    op.execute("DROP TYPE IF EXISTS fan_out_verdict")
    op.execute("DROP TYPE IF EXISTS artifact_type")
    op.execute("DROP TYPE IF EXISTS work_session_state")
    op.execute("DROP TYPE IF EXISTS stage_state")
    op.execute("DROP TYPE IF EXISTS stage_type")
    op.execute("DROP TYPE IF EXISTS cascade_state")
    op.execute("DROP TYPE IF EXISTS actor_type")
    op.execute("DROP TYPE IF EXISTS intent_source")

    # Step 1 — extensions
    op.execute("DROP EXTENSION IF EXISTS pg_search")
    op.execute("DROP EXTENSION IF EXISTS vector")
