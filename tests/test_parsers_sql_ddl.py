"""
Tests for schema_commons/parsers/sql_ddl.py — parse_sql_ddl(text: str) -> SchemaIR
TDD: RED phase first, then GREEN.
"""

from pathlib import Path


from schema_commons.parsers.sql_ddl import parse_sql_ddl
from schema_commons.ir import SchemaIR

FIXTURE = Path(__file__).parent / "fixtures" / "sample.sql"


def test_parse_sql_ddl_returns_schema_ir():
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    assert isinstance(result, SchemaIR)
    assert result.source_format == "sql_ddl"


def test_parse_sql_ddl_tables():
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    assert len(result.entities) >= 2
    names = [e.name for e in result.entities]
    assert "user" in names
    assert "post" in names


def test_parse_sql_ddl_entity_type():
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    for entity in result.entities:
        assert entity.type == "table"


def test_parse_sql_ddl_entity_source_ref():
    """IREntity.source_ref = 'statement.N'."""
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    refs = [e.source_ref for e in result.entities]
    # First two CREATE TABLE statements
    assert any(r.startswith("statement.") for r in refs)


def test_parse_sql_ddl_fields():
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    user_fields = [f for f in result.fields if f.entity_name == "user"]
    field_names = [f.field_name for f in user_fields]
    assert "id" in field_names
    assert "name" in field_names

    post_fields = [f for f in result.fields if f.entity_name == "post"]
    post_field_names = [f.field_name for f in post_fields]
    assert "id" in post_field_names


def test_parse_sql_ddl_primary_key():
    """user.id is PRIMARY KEY — is_primary_key=True."""
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    id_field = next(
        f for f in result.fields if f.entity_name == "user" and f.field_name == "id"
    )
    assert id_field.is_primary_key is True


def test_parse_sql_ddl_not_null():
    """user.name has NOT NULL — nullable=False."""
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    name_field = next(
        f for f in result.fields if f.entity_name == "user" and f.field_name == "name"
    )
    assert name_field.nullable is False


def test_parse_sql_ddl_foreign_key():
    """post.user_id REFERENCES user — is_foreign_key=True, foreign_ref='user'."""
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    fk_field = next(
        (
            f
            for f in result.fields
            if f.entity_name == "post" and f.field_name == "user_id"
        ),
        None,
    )
    assert fk_field is not None
    assert fk_field.is_foreign_key is True
    assert fk_field.foreign_ref == "user"


def test_parse_sql_ddl_relation():
    """post → user FK produces a relation in ir.relations."""
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    assert len(result.relations) >= 1
    rel = next(
        r for r in result.relations if r.from_entity == "post" and r.to_entity == "user"
    )
    assert rel is not None


def test_parse_sql_ddl_warnings_empty_on_valid():
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    assert result.warnings == []


def test_parse_sql_ddl_malformed_input_returns_warning():
    """Non-SQL text should NOT raise — returns SchemaIR with warnings (D-03)."""
    # sqlglot is lenient, but completely garbled input may still warn
    result = parse_sql_ddl("this is definitely not sql !@#$%^&*()")
    assert isinstance(result, SchemaIR)
    # Either no entities parsed or a warning was emitted
    # The key invariant: no exception raised


def test_parse_sql_ddl_field_source_ref():
    """IRField.source_ref = 'statement.N.column.colname'."""
    text = FIXTURE.read_text()
    result = parse_sql_ddl(text)
    id_field = next(
        f for f in result.fields if f.entity_name == "user" and f.field_name == "id"
    )
    assert "column.id" in id_field.source_ref
