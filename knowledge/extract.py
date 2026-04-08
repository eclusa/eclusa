"""knowledge/extract.py — Entity extraction + persistence (KG-02, D-13).

extract_entities_from_episode:
1. Calls pydantic-ai Agent with output_type=EntityList to extract structured entities
2. For each entity: calls resolve_entity() to check for existing match
3. If None (no match): INSERTs new entity row (KG-02 durable persistence)
4. If existing id: skips INSERT (deduplication)

Embedding is NOT set during extraction — the embedding pipeline (04-04) handles that.
"""

import logging

import asyncpg
from pydantic import BaseModel
from pydantic_ai import Agent

from knowledge.resolve import resolve_entity

logger = logging.getLogger(__name__)


class ExtractedEntity(BaseModel):
    """Structured entity extracted from episode content by LLM."""

    name: str
    type: str  # "person", "project", "api", "decision", "rule", "concept"
    summary: str


class EntityList(BaseModel):
    """Structured output from the entity extraction agent."""

    entities: list[ExtractedEntity]


_agent = Agent("anthropic:claude-haiku-4-5", output_type=EntityList)


async def extract_entities_from_episode(
    raw_text: str,
    conn: asyncpg.Connection,
) -> list[ExtractedEntity]:
    """Extract entities from episode text and persist new entities to entity table.

    For each ExtractedEntity:
    - Calls resolve_entity() to check for existing match (name-exact or cosine)
    - If None: INSERTs a new row into entity table (KG-02 durable persistence)
    - If existing id: skips INSERT (deduplication)

    Embedding is not set here — the embedding pipeline (04-04) handles that separately.
    """
    result = await _agent.run(
        f"Extract all named entities (people, projects, APIs, business rules, "
        f"decisions) from the following content. Be concise in summaries.\n\n{raw_text}"
    )
    entities = result.output.entities

    # Persist new entities (KG-02: durable entity persistence)
    for entity in entities:
        existing_id = await resolve_entity(entity.name, [], conn)
        if existing_id is None:
            await conn.execute(
                """
                INSERT INTO entity (id, name, type, summary, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, NOW(), NOW())
                """,
                entity.name,
                entity.type,
                entity.summary,
            )
            logger.debug(
                "Persisted new entity '%s' (type=%s)", entity.name, entity.type
            )
        else:
            logger.debug(
                "Entity '%s' already exists as %s — skipping INSERT",
                entity.name,
                existing_id,
            )

    return entities
