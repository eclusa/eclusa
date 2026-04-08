"""
Tests for schema_commons/parsers/prisma.py — parse_prisma() function.

TDD RED phase: these tests are written against the behavior spec before implementation.
Uses tests/fixtures/sample.prisma as canonical input.
"""

from pathlib import Path


from schema_commons.parsers.prisma import parse_prisma
from schema_commons.ir import SchemaIR

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PRISMA = (FIXTURES_DIR / "sample.prisma").read_text()


# ── Entities ──────────────────────────────────────────────────────────────────


def test_parse_prisma_returns_schema_ir():
    result = parse_prisma(SAMPLE_PRISMA)
    assert isinstance(result, SchemaIR)
    assert result.source_format == "prisma"


def test_parse_prisma_entities_count():
    result = parse_prisma(SAMPLE_PRISMA)
    entity_names = {e.name for e in result.entities}
    assert "User" in entity_names
    assert "Post" in entity_names


def test_parse_prisma_entity_type():
    result = parse_prisma(SAMPLE_PRISMA)
    for entity in result.entities:
        assert entity.type == "model"


def test_parse_prisma_entity_source_ref():
    result = parse_prisma(SAMPLE_PRISMA)
    refs = {e.source_ref for e in result.entities}
    assert "model.User" in refs
    assert "model.Post" in refs


# ── Fields ─────────────────────────────────────────────────────────────────────


def test_parse_prisma_fields_user():
    result = parse_prisma(SAMPLE_PRISMA)
    user_fields = {f.field_name: f for f in result.fields if f.entity_name == "User"}
    assert "id" in user_fields
    assert "name" in user_fields


def test_parse_prisma_fields_post():
    result = parse_prisma(SAMPLE_PRISMA)
    post_fields = {f.field_name: f for f in result.fields if f.entity_name == "Post"}
    assert "id" in post_fields
    assert "title" in post_fields
    assert "userId" in post_fields


def test_parse_prisma_field_primary_key():
    result = parse_prisma(SAMPLE_PRISMA)
    user_fields = {f.field_name: f for f in result.fields if f.entity_name == "User"}
    assert user_fields["id"].is_primary_key is True


def test_parse_prisma_field_nullability():
    # In Prisma, String (no ?) is non-nullable
    result = parse_prisma(SAMPLE_PRISMA)
    user_fields = {f.field_name: f for f in result.fields if f.entity_name == "User"}
    assert user_fields["name"].nullable is False


def test_parse_prisma_field_source_ref():
    result = parse_prisma(SAMPLE_PRISMA)
    refs = {f.source_ref for f in result.fields}
    assert "model.User.id" in refs
    assert "model.Post.title" in refs


def test_parse_prisma_field_type_stripped():
    # posts Post[] — base_type should be "Post", not "Post[]"
    result = parse_prisma(SAMPLE_PRISMA)
    user_fields = {f.field_name: f for f in result.fields if f.entity_name == "User"}
    assert user_fields["id"].field_type == "String"


# ── Relations ─────────────────────────────────────────────────────────────────


def test_parse_prisma_relations_present():
    result = parse_prisma(SAMPLE_PRISMA)
    assert len(result.relations) >= 1


def test_parse_prisma_relation_entities():
    result = parse_prisma(SAMPLE_PRISMA)
    # Post has user User @relation(...) — creates Post->User or User->Post relation
    relation_pairs = {(r.from_entity, r.to_entity) for r in result.relations}
    # The @relation is on Post.user (type User) — from_entity=Post, to_entity=User
    assert ("Post", "User") in relation_pairs


def test_parse_prisma_relation_type_for_array():
    result = parse_prisma(SAMPLE_PRISMA)
    # User.posts Post[] — one_to_many
    array_relations = [
        r for r in result.relations if r.from_entity == "User" and r.to_entity == "Post"
    ]
    if array_relations:
        assert array_relations[0].relation_type == "one_to_many"


# ── Error handling ─────────────────────────────────────────────────────────────


def test_parse_prisma_empty_string():
    result = parse_prisma("")
    assert isinstance(result, SchemaIR)
    assert result.entities == []
    assert result.fields == []
    assert result.relations == []
    assert result.warnings == []


def test_parse_prisma_malformed_input_no_exception():
    result = parse_prisma("model Broken {")
    assert isinstance(result, SchemaIR)
    assert len(result.warnings) >= 1


def test_parse_prisma_no_exception_on_garbage():
    result = parse_prisma("this is not valid prisma syntax at all!!!")
    assert isinstance(result, SchemaIR)
