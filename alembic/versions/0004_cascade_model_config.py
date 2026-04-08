"""Add model_config to cascade table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cascade",
        sa.Column("model_config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cascade", "model_config")
