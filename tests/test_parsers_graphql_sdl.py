"""
Tests for schema_commons/parsers/graphql_sdl.py — parse_graphql_sdl(text: str) -> SchemaIR
TDD: RED phase first, then GREEN.
"""

from pathlib import Path


from schema_commons.parsers.graphql_sdl import parse_graphql_sdl
from schema_commons.ir import SchemaIR

FIXTURE = Path(__file__).parent / "fixtures" / "sample.graphql"


def test_parse_graphql_returns_schema_ir():
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    assert isinstance(result, SchemaIR)
    assert result.source_format == "graphql_sdl"


def test_parse_graphql_types():
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    assert len(result.entities) >= 1
    names = [e.name for e in result.entities]
    assert "User" in names


def test_parse_graphql_entity_type():
    """GraphQL object types become IREntity with type='type'."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    user_entity = next(e for e in result.entities if e.name == "User")
    assert user_entity.type == "type"
    assert user_entity.source_ref == "type.User"


def test_parse_graphql_entity_fields():
    """Fields under User type become IRField entries with entity_name='User'."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    user_fields = [f for f in result.fields if f.entity_name == "User"]
    field_names = [f.field_name for f in user_fields]
    assert "id" in field_names
    assert "name" in field_names


def test_parse_graphql_field_type_string():
    """IRField.field_type reflects the GraphQL type string."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    id_field = next(
        f for f in result.fields if f.entity_name == "User" and f.field_name == "id"
    )
    # ID! is non-null ID
    assert "ID" in id_field.field_type


def test_parse_graphql_field_nullable():
    """Non-null fields (ending in !) should have nullable=False."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    # id: ID! — non-null
    id_field = next(
        f for f in result.fields if f.entity_name == "User" and f.field_name == "id"
    )
    assert id_field.nullable is False


def test_parse_graphql_mutations():
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    assert len(result.operations) >= 1
    methods = [op.method for op in result.operations]
    assert "query" in methods


def test_parse_graphql_mutation_operations():
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    methods = [op.method for op in result.operations]
    assert "mutation" in methods


def test_parse_graphql_query_operation_names():
    """Query.users and Query.user(id) become operations with method='query'."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    query_ops = [op for op in result.operations if op.method == "query"]
    op_names = [op.name for op in query_ops]
    assert "users" in op_names


def test_parse_graphql_operation_source_ref():
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    users_op = next(op for op in result.operations if op.name == "users")
    assert users_op.source_ref == "type.Query.users"


def test_parse_graphql_introspection_types_excluded():
    """__Schema, __Type, etc. must not become entities."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    names = [e.name for e in result.entities]
    assert not any(n.startswith("__") for n in names)


def test_parse_graphql_builtin_scalars_excluded():
    """String, Int, Boolean, ID, Float must not become entities."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    names = [e.name for e in result.entities]
    for scalar in ("String", "Int", "Float", "Boolean", "ID"):
        assert scalar not in names


def test_parse_graphql_query_mutation_not_entities():
    """Query and Mutation root types must not be entities — they become operations."""
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    names = [e.name for e in result.entities]
    assert "Query" not in names
    assert "Mutation" not in names


def test_parse_graphql_malformed_returns_warning():
    """Malformed SDL must NOT raise — returns SchemaIR with warnings (D-03)."""
    result = parse_graphql_sdl("type Broken {")
    assert isinstance(result, SchemaIR)
    assert len(result.warnings) >= 1
    assert result.entities == []
    assert result.operations == []


def test_parse_graphql_warnings_empty_on_valid():
    text = FIXTURE.read_text()
    result = parse_graphql_sdl(text)
    assert result.warnings == []
