import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector

from .base import Base, new_id


# Enum type definitions — exact names match SQL type names
intent_source_enum = sa.Enum(
    "slack_message",
    "email",
    "voice",
    "chat",
    "webhook",
    "api",
    "cli",
    "figma_comment",
    "notion_page",
    "lark_message",
    "github_issue",
    "manual",
    name="intent_source",
)

actor_type_enum = sa.Enum("human", "agent", "system", "webhook", name="actor_type")

cascade_state_enum = sa.Enum(
    "active", "paused", "completed", "failed", "evergreen", name="cascade_state"
)

stage_type_enum = sa.Enum("narrowing", "gate", name="stage_type")

stage_state_enum = sa.Enum(
    "pending", "active", "blocked", "resolved", "skipped", "failed", name="stage_state"
)

work_session_state_enum = sa.Enum(
    "running", "paused", "completed", "failed", name="work_session_state"
)

artifact_type_enum = sa.Enum(
    "git_commit",
    "git_branch",
    "git_pr",
    "api_request",
    "api_response",
    "deployment",
    "file_created",
    "message_sent",
    "webhook_out",
    "config_change",
    "external_state",
    name="artifact_type",
)

fan_out_verdict_enum = sa.Enum(
    "converged", "diverged", "partial", name="fan_out_verdict"
)

ledger_type_enum = sa.Enum(
    "intent_created",
    "cascade_created",
    "cascade_state_changed",
    "cascade_migration",
    "stage_created",
    "stage_state_changed",
    "work_session_started",
    "work_session_paused",
    "work_session_resumed",
    "work_session_completed",
    "work_session_failed",
    "judgment_pass_created",
    "judgment_pass_completed",
    "fan_out_created",
    "fan_out_completed",
    "artifact_created",
    "gate_surfaced",
    "gate_resolved",
    "gate_auto_resolved",
    "cascade_reopened",
    "orchestrator_absorbed",
    "schema_migration",
    name="ledger_type",
)


class Actor(Base):
    """Any participating entity — human, agent, system, or webhook."""

    __tablename__ = "actor"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    type = sa.Column(actor_type_enum, nullable=False)
    identity = sa.Column(sa.Text, nullable=False)
    permissions = sa.Column(JSONB, nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )


class Intent(Base):
    """The root. Everything traces here. Intents are a tree (parent_id)."""

    __tablename__ = "intent"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    parent_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=True)
    source = sa.Column(intent_source_enum, nullable=False)
    raw = sa.Column(sa.Text, nullable=False)
    context = sa.Column(JSONB, nullable=True)
    embedding = sa.Column(Vector(1024), nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    created_by = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False
    )


class Cascade(Base):
    """A living directed graph of work, spawned from an intent."""

    __tablename__ = "cascade"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    intent_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=False
    )
    shape = sa.Column(JSONB, nullable=False)
    annotations = sa.Column(JSONB, nullable=True)
    narrative = sa.Column(sa.Text, nullable=True)
    state = sa.Column(cascade_state_enum, nullable=False)
    embedding = sa.Column(Vector(1024), nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    completed_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
    failure_policy = sa.Column(sa.Text, nullable=False, server_default="fail_cascade")
    parent_stage_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=True
    )


class Stage(Base):
    """A node in the cascade graph — narrowing or gate."""

    __tablename__ = "stage"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    cascade_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("cascade.id"), nullable=False
    )
    type = sa.Column(stage_type_enum, nullable=False)
    state = sa.Column(stage_state_enum, nullable=False)
    input = sa.Column(JSONB, nullable=True)
    output = sa.Column(JSONB, nullable=True)
    depends_on = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    served_by = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    resolved_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
    resolved_by = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=True
    )
    retry_count = sa.Column(sa.Integer, nullable=False, server_default=sa.text("0"))
    resolve_token = sa.Column(sa.Text, nullable=True)
    expires_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)


class Artifact(Base):
    """The bridge between eclusa and the outside world."""

    __tablename__ = "artifact"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    intent_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=False
    )
    cascade_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("cascade.id"), nullable=False
    )
    stage_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=False)
    session_id = sa.Column(
        UUID(as_uuid=True), nullable=True
    )  # FK to work_session — defined in compute.py
    type = sa.Column(artifact_type_enum, nullable=False)
    external_ref = sa.Column(sa.Text, nullable=True)
    external_sys = sa.Column(sa.Text, nullable=True)
    payload = sa.Column(JSONB, nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )


class LedgerEntry(Base):
    """The sacred record. Append-only. Never deleted, never mutated."""

    __tablename__ = "ledger_entry"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    intent_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("intent.id"), nullable=True)
    cascade_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("cascade.id"), nullable=True
    )
    stage_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("stage.id"), nullable=True)
    session_id = sa.Column(
        UUID(as_uuid=True), nullable=True
    )  # FK to work_session — defined in compute.py
    actor_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False)
    type = sa.Column(ledger_type_enum, nullable=False)
    content = sa.Column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    confidence = sa.Column(sa.Numeric, nullable=True)
    reversible = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    artifact_ids = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    timestamp = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    # CRITICAL (SCHEMA-03): schema_version must be present from the first migration.
    # Adding it later requires mutating immutable ledger rows, violating the append-only guarantee.
    schema_version = sa.Column(sa.String(10), nullable=False, server_default="0001")


class Tool(Base):
    """An external capability — MCP server, API, code execution environment, etc."""

    __tablename__ = "tool"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name = sa.Column(sa.Text, nullable=False)
    interface = sa.Column(JSONB, nullable=False)
    auth_ref = sa.Column(sa.Text, nullable=True)
    cost_profile = sa.Column(JSONB, nullable=True)
    registered_by = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False
    )
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )


class CascadeMigrationProposal(Base):
    """Mutable migration proposal — separate from append-only ledger (Pitfall 5)."""

    __tablename__ = "cascade_migration_proposal"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    cascade_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("cascade.id"), nullable=False
    )
    proposed_by = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("actor.id"), nullable=False
    )
    new_shape = sa.Column(JSONB, nullable=False)
    reason = sa.Column(sa.Text, nullable=True)
    status = sa.Column(sa.Text, nullable=False, server_default="pending")
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    applied_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
