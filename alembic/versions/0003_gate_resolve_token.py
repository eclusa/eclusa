"""Gate resolve_token and expires_at columns on stage table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-05
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Add resolve_token and expires_at to stage table (Phase 5 gate surfacing)
    # resolve_token: opaque signed token embedded in gate resolution URLs (D-08)
    # expires_at: optional gate expiry — NULL means no expiry
    # Both nullable — existing rows unaffected; only gate stages use them.
    # =========================================================================
    op.execute("ALTER TABLE stage ADD COLUMN IF NOT EXISTS resolve_token TEXT")
    op.execute("ALTER TABLE stage ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE stage DROP COLUMN IF EXISTS expires_at")
    op.execute("ALTER TABLE stage DROP COLUMN IF EXISTS resolve_token")
