"""Executor schema gaps — failure_policy, parent_stage_id, retry_count, cascade_migration_proposal.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-04
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Step 0 — Add 'failed' to stage_state enum (required for cascade failure tracking)
    # The executor marks stages 'failed' when stage execution fails (D-17..D-19).
    # =========================================================================
    op.execute("ALTER TYPE stage_state ADD VALUE IF NOT EXISTS 'failed'")

    # =========================================================================
    # Step 1 — Add failure_policy to cascade table (D-17, D-18)
    # Conservative default: 'fail_cascade' per D-18.
    # Stores executor failure policy: 'retry' | 'skip' | 'fail_cascade'
    # =========================================================================
    op.execute(
        "ALTER TABLE cascade ADD COLUMN failure_policy TEXT NOT NULL DEFAULT 'fail_cascade'"
    )

    # =========================================================================
    # Step 2 — Add parent_stage_id to cascade table (D-11)
    # Sub-cascades link back to the stage that spawned them.
    # NULLABLE — root cascades have no parent stage.
    # =========================================================================
    op.execute(
        "ALTER TABLE cascade ADD COLUMN parent_stage_id UUID REFERENCES stage(id) ON DELETE SET NULL"
    )

    # =========================================================================
    # Step 3 — Add retry_count to stage table (D-19)
    # Tracks how many times this stage has been retried.
    # Incremented by executor on each retry ledger entry.
    # =========================================================================
    op.execute("ALTER TABLE stage ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")

    # =========================================================================
    # Step 4 — Create cascade_migration_proposal table (Pitfall 5 resolution)
    # Mutable proposal lifecycle — separate from the append-only ledger.
    # Allows shape changes to be proposed, reviewed, applied, or rejected
    # without touching immutable ledger rows.
    # status values: 'pending' | 'applied' | 'rejected'
    # =========================================================================
    op.execute("""
    CREATE TABLE cascade_migration_proposal (
        id UUID PRIMARY KEY,
        cascade_id UUID NOT NULL REFERENCES cascade(id),
        proposed_by UUID NOT NULL REFERENCES actor(id),
        new_shape JSONB NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        applied_at TIMESTAMPTZ
    )
    """)

    # =========================================================================
    # Step 5 — Indexes on cascade_migration_proposal for query performance
    # =========================================================================
    op.execute(
        "CREATE INDEX idx_migration_proposal_cascade_id ON cascade_migration_proposal(cascade_id)"
    )
    op.execute(
        "CREATE INDEX idx_migration_proposal_status ON cascade_migration_proposal(status)"
    )


def downgrade() -> None:
    # Reverse all changes in reverse order
    # Note: PostgreSQL does not support removing enum values — Step 0 cannot be reversed.

    # Step 5 — indexes
    op.execute("DROP INDEX IF EXISTS idx_migration_proposal_status")
    op.execute("DROP INDEX IF EXISTS idx_migration_proposal_cascade_id")

    # Step 4 — cascade_migration_proposal table
    op.execute("DROP TABLE IF EXISTS cascade_migration_proposal")

    # Step 3 — retry_count column
    op.execute("ALTER TABLE stage DROP COLUMN IF EXISTS retry_count")

    # Step 2 — parent_stage_id column
    op.execute("ALTER TABLE cascade DROP COLUMN IF EXISTS parent_stage_id")

    # Step 1 — failure_policy column
    op.execute("ALTER TABLE cascade DROP COLUMN IF EXISTS failure_policy")
