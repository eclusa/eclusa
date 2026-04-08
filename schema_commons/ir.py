"""
schema_commons/ir.py — Canonical Intermediate Representation (IR) for all schema parsers.

Decisions:
- D-05: SchemaIR has entities, fields, relations, operations, constraints
- D-06: Each IR element has source_ref pointing to original spec location
- D-07: IR is JSON-serializable (Pydantic BaseModel, no UUID/datetime fields)
- D-03: Errors collected as ParseWarnings, not thrown — partial parse is valid output
"""

from typing import Literal

from pydantic import BaseModel


class IRElement(BaseModel):
    """Base class for all IR elements. Carries source_ref (D-06)."""

    source_ref: str  # Points back to the original spec location (e.g. "root.components.schemas.User")


class IREntity(IRElement):
    """A named domain concept (model, table, message type, etc.)."""

    name: str
    description: str | None = None
    type: Literal["model", "message", "type", "table", "interface"] = "model"


class IRField(IRElement):
    """A field/column/attribute belonging to an IREntity."""

    entity_name: str
    field_name: str
    field_type: str
    nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_ref: str | None = None  # e.g. "Order.id"


class IRRelation(IRElement):
    """A relationship between two IREntities."""

    from_entity: str
    to_entity: str
    relation_type: Literal["one_to_one", "one_to_many", "many_to_many", "unknown"]


class IROperation(IRElement):
    """An operation exposed by the schema (REST endpoint, GraphQL query/mutation, RPC call)."""

    name: str
    method: str | None = (
        None  # GET/POST/PUT/DELETE for REST; query/mutation/subscription for GraphQL
    )
    path: str | None = None  # /users, /orders/{id}, etc.


class IRConstraint(IRElement):
    """A structural constraint on an IREntity (unique, check, not-null, etc.)."""

    entity_name: str
    constraint_type: str  # "unique", "check", "not_null", "primary_key", etc.
    expression: str  # e.g. "email", "price > 0"


class ParseWarning(BaseModel):
    """A non-fatal issue encountered during parsing (D-03: partial parse with warnings)."""

    location: str  # Where in the source spec this warning arose
    message: str


class SchemaIR(BaseModel):
    """
    Canonical Intermediate Representation — the contract all parsers return.

    JSON-serializable (D-07): stored as JSONB in the embedding row alongside the vector.
    Errors are collected, not thrown (D-03): a partial parse with warnings is better than a crash.
    """

    source_format: Literal["openapi", "prisma", "sql_ddl", "graphql_sdl", "protobuf"]
    entities: list[IREntity] = []
    fields: list[IRField] = []
    relations: list[IRRelation] = []
    operations: list[IROperation] = []
    constraints: list[IRConstraint] = []
    warnings: list[ParseWarning] = []  # D-03: warnings from partial parse
