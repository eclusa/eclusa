"""
schema_commons/parsers/graphql_sdl.py — Parse GraphQL SDL to SchemaIR via graphql-core.

Decisions:
- D-01: Pure function, no side effects
- D-02: Input = raw text (str), output = SchemaIR
- D-03: Collects warnings rather than raising — partial parse is valid
- D-06: source_ref points to original spec location (e.g. "type.User.id")
"""

from graphql import build_ast_schema
from graphql import parse as gql_parse
from graphql import GraphQLNonNull, GraphQLObjectType
from graphql.error import GraphQLSyntaxError

from schema_commons.ir import (
    IREntity,
    IRField,
    IROperation,
    ParseWarning,
    SchemaIR,
)

# Built-in scalar types — do not become entities
_BUILTIN_SCALARS = frozenset({"String", "Int", "Float", "Boolean", "ID"})

# Root operation types — become operations, not entities
_OPERATION_ROOT_TYPES = frozenset({"Query", "Mutation", "Subscription"})


def parse_graphql_sdl(text: str) -> SchemaIR:
    """Parse a GraphQL SDL string into SchemaIR.

    - Object types → IREntity (type="type") + IRField entries
    - Query/Mutation/Subscription root types → IROperation entries
    - Introspection types (__Schema, etc.) are excluded
    - Built-in scalars (String, Int, Float, Boolean, ID) are excluded
    - Collects warnings rather than raising (D-03)
    - Never throws — malformed input produces SchemaIR with warnings
    """
    ir = SchemaIR(source_format="graphql_sdl")

    try:
        doc = gql_parse(text)
        schema = build_ast_schema(doc)
    except (GraphQLSyntaxError, Exception) as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir

    for type_name, type_def in schema.type_map.items():
        # Skip introspection types
        if type_name.startswith("__"):
            continue

        # Skip built-in scalars
        if type_name in _BUILTIN_SCALARS:
            continue

        # Only handle object types
        if not isinstance(type_def, GraphQLObjectType):
            continue

        if type_name in _OPERATION_ROOT_TYPES:
            # Root operation types → IROperation entries
            method = type_name.lower()  # "query", "mutation", "subscription"
            for field_name in type_def.fields:
                ir.operations.append(
                    IROperation(
                        source_ref=f"type.{type_name}.{field_name}",
                        name=field_name,
                        method=method,
                        path=None,
                    )
                )
        else:
            # Regular object type → IREntity + IRField entries
            ir.entities.append(
                IREntity(
                    source_ref=f"type.{type_name}",
                    name=type_name,
                    type="type",
                )
            )
            for field_name, field_def in type_def.fields.items():
                type_str = str(field_def.type)
                nullable = not isinstance(field_def.type, GraphQLNonNull)
                ir.fields.append(
                    IRField(
                        source_ref=f"type.{type_name}.{field_name}",
                        entity_name=type_name,
                        field_name=field_name,
                        field_type=type_str,
                        nullable=nullable,
                    )
                )

    return ir
