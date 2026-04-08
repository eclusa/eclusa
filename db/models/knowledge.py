import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector

from .base import Base, new_id


class Episode(Base):
    """Raw ingested data — non-lossy, preserved exactly as received."""

    __tablename__ = "episode"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    source = sa.Column(sa.Text, nullable=False)
    raw_data = sa.Column(JSONB, nullable=False)
    reference_ts = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False)
    ingested_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    schema_version = sa.Column(sa.String(10), nullable=False, server_default="0001")


class Entity(Base):
    """Extracted from episodes via LLM — durable concepts that survive across sessions."""

    __tablename__ = "entity"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name = sa.Column(sa.Text, nullable=False)
    type = sa.Column(sa.Text, nullable=True)
    summary = sa.Column(sa.Text, nullable=True)
    embedding = sa.Column(Vector(1024), nullable=True)
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )


class Fact(Base):
    """Edges between entities — bi-temporal model per D-10.

    Four explicit timestamptz columns (no range types per D-12):
    - t_valid / t_invalid: event timeline (when fact was true in the world)
    - t_created / t_expired: transactional timeline (when system learned/superseded it)
    """

    __tablename__ = "fact"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    source_entity = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("entity.id"), nullable=False
    )
    target_entity = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("entity.id"), nullable=False
    )
    predicate = sa.Column(sa.Text, nullable=False)
    embedding = sa.Column(Vector(1024), nullable=True)
    t_valid = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False)
    t_invalid = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
    t_created = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    t_expired = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)
    source_episodes = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    schema_version = sa.Column(sa.String(10), nullable=False, server_default="0001")


class Community(Base):
    """Clusters of strongly connected entities with summarized descriptions."""

    __tablename__ = "community"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name = sa.Column(sa.Text, nullable=False)
    summary = sa.Column(sa.Text, nullable=True)
    entity_ids = sa.Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=sa.text("'{}'")
    )
    created_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
    )
