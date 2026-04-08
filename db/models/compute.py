import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from .base import Base, new_id
from .domain import work_session_state_enum, fan_out_verdict_enum


class WorkSession(Base):
    """An agent running inside a harness with tools, producing artifacts."""

    __tablename__ = "work_session"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    stage_ids = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    harness_type = sa.Column(sa.Text, nullable=False)
    model = sa.Column(sa.Text, nullable=False)
    model_swaps = sa.Column(JSONB, nullable=False, server_default=sa.text("'[]'"))
    message_history = sa.Column(JSONB, nullable=False, server_default=sa.text("'[]'"))
    workspace_ref = sa.Column(sa.Text, nullable=True)
    state = sa.Column(work_session_state_enum, nullable=False)
    cost = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    paused_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
    resumed_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
    completed_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)


class JudgmentPass(Base):
    """A single API completion. No harness. No tools. No agent loop."""

    __tablename__ = "judgment_pass"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    stage_ids = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    model = sa.Column(sa.Text, nullable=False)
    context_ref = sa.Column(sa.Text, nullable=False)
    context_hash = sa.Column(sa.Text, nullable=False)
    prompt = sa.Column(sa.Text, nullable=False)
    response = sa.Column(JSONB, nullable=True)
    confidence = sa.Column(sa.Numeric, nullable=True)
    cost = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    completed_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)


class FanOut(Base):
    """Fan-out evaluation: n models in parallel against shared prepared context."""

    __tablename__ = "fan_out"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    stage_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=False)
    context_ref = sa.Column(sa.Text, nullable=False)
    prompt = sa.Column(sa.Text, nullable=False)
    passes = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    convergence = sa.Column(JSONB, nullable=True)
    verdict = sa.Column(fan_out_verdict_enum, nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    completed_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
