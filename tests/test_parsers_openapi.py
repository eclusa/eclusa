"""
Tests for schema_commons/parsers/openapi.py — parse_openapi(text: str) -> SchemaIR
TDD: RED phase first, then GREEN.
"""

from pathlib import Path


from schema_commons.parsers.openapi import parse_openapi
from schema_commons.ir import SchemaIR

FIXTURE = Path(__file__).parent / "fixtures" / "sample.openapi.yaml"


def test_parse_openapi_returns_schema_ir():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    assert isinstance(result, SchemaIR)
    assert result.source_format == "openapi"


def test_parse_openapi_entities():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    assert len(result.entities) >= 1
    names = [e.name for e in result.entities]
    assert "User" in names


def test_parse_openapi_entity_source_ref():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    user_entity = next(e for e in result.entities if e.name == "User")
    assert user_entity.source_ref == "components.schemas.User"
    assert user_entity.type == "model"


def test_parse_openapi_fields():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    field_names = [f.field_name for f in result.fields if f.entity_name == "User"]
    assert "id" in field_names
    assert "name" in field_names


def test_parse_openapi_field_nullable():
    """Fields in 'required' list should have nullable=False."""
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    id_field = next(
        f for f in result.fields if f.entity_name == "User" and f.field_name == "id"
    )
    name_field = next(
        f for f in result.fields if f.entity_name == "User" and f.field_name == "name"
    )
    # Both id and name are in 'required' in sample.openapi.yaml
    assert id_field.nullable is False
    assert name_field.nullable is False


def test_parse_openapi_operations():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    assert len(result.operations) >= 1
    methods = [op.method for op in result.operations]
    assert "GET" in methods


def test_parse_openapi_operation_path():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    get_op = next(op for op in result.operations if op.method == "GET")
    assert get_op.path == "/users"
    assert get_op.source_ref == "paths./users.get"


def test_parse_openapi_warnings_empty_on_valid():
    text = FIXTURE.read_text()
    result = parse_openapi(text)
    assert result.warnings == []


def test_parse_openapi_malformed_yaml_returns_warning():
    """Malformed input must NOT raise — returns SchemaIR with warnings (D-03)."""
    result = parse_openapi("not yaml at all {{{")
    assert isinstance(result, SchemaIR)
    assert len(result.warnings) >= 1
    assert result.entities == []
    assert result.operations == []


def test_parse_openapi_empty_dict_returns_warning():
    """Empty spec returns SchemaIR with warnings."""
    result = parse_openapi("{}")
    assert isinstance(result, SchemaIR)
    # No entities and no operations from empty spec
    assert result.entities == []
    assert result.operations == []
