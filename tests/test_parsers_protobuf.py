"""
Tests for schema_commons/parsers/protobuf.py — parse_protobuf() function.

TDD RED phase: written against behavior spec before implementation.
Uses tests/fixtures/sample.proto as canonical input.

sample.proto contains:
  - message User { string id = 1; string name = 2; }
  - message GetUserRequest { string id = 1; }
  - message ListUsersResponse { repeated User users = 1; }
  - service UserService { rpc GetUser(...); rpc ListUsers(...); }
"""

from pathlib import Path


from schema_commons.parsers.protobuf import parse_protobuf
from schema_commons.ir import SchemaIR

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PROTO = (FIXTURES_DIR / "sample.proto").read_text()


# ── Basic structure ────────────────────────────────────────────────────────────


def test_parse_protobuf_returns_schema_ir():
    result = parse_protobuf(SAMPLE_PROTO)
    assert isinstance(result, SchemaIR)
    assert result.source_format == "protobuf"


def test_parse_protobuf_no_warnings_on_valid():
    result = parse_protobuf(SAMPLE_PROTO)
    assert result.warnings == []


# ── Entities ──────────────────────────────────────────────────────────────────


def test_parse_protobuf_entities_present():
    result = parse_protobuf(SAMPLE_PROTO)
    entity_names = {e.name for e in result.entities}
    assert "User" in entity_names


def test_parse_protobuf_entity_type_is_message():
    result = parse_protobuf(SAMPLE_PROTO)
    for entity in result.entities:
        assert entity.type == "message"


def test_parse_protobuf_entity_source_ref():
    result = parse_protobuf(SAMPLE_PROTO)
    refs = {e.source_ref for e in result.entities}
    assert "message.User" in refs


def test_parse_protobuf_all_messages_found():
    result = parse_protobuf(SAMPLE_PROTO)
    entity_names = {e.name for e in result.entities}
    assert "User" in entity_names
    assert "GetUserRequest" in entity_names
    assert "ListUsersResponse" in entity_names


# ── Fields ─────────────────────────────────────────────────────────────────────


def test_parse_protobuf_user_fields():
    result = parse_protobuf(SAMPLE_PROTO)
    user_fields = {f.field_name: f for f in result.fields if f.entity_name == "User"}
    assert "id" in user_fields
    assert "name" in user_fields


def test_parse_protobuf_field_types():
    result = parse_protobuf(SAMPLE_PROTO)
    user_fields = {f.field_name: f for f in result.fields if f.entity_name == "User"}
    assert user_fields["id"].field_type == "string"
    assert user_fields["name"].field_type == "string"


def test_parse_protobuf_field_source_ref():
    result = parse_protobuf(SAMPLE_PROTO)
    refs = {f.source_ref for f in result.fields}
    # source_ref format: "message.User.field.id"
    assert any("User" in ref and "id" in ref for ref in refs)


def test_parse_protobuf_repeated_field_type():
    # ListUsersResponse has: repeated User users = 1;
    result = parse_protobuf(SAMPLE_PROTO)
    response_fields = {
        f.field_name: f for f in result.fields if f.entity_name == "ListUsersResponse"
    }
    assert "users" in response_fields
    # field_type should indicate repeated nature
    assert (
        "repeated" in response_fields["users"].field_type.lower()
        or response_fields["users"].field_type == "User"
    )


# ── Operations (services/rpcs) ─────────────────────────────────────────────────


def test_parse_protobuf_operations_present():
    result = parse_protobuf(SAMPLE_PROTO)
    assert len(result.operations) >= 1


def test_parse_protobuf_operation_names():
    result = parse_protobuf(SAMPLE_PROTO)
    op_names = {op.name for op in result.operations}
    assert "GetUser" in op_names
    assert "ListUsers" in op_names


def test_parse_protobuf_operation_method():
    result = parse_protobuf(SAMPLE_PROTO)
    for op in result.operations:
        assert op.method == "rpc"


def test_parse_protobuf_operation_source_ref():
    result = parse_protobuf(SAMPLE_PROTO)
    refs = {op.source_ref for op in result.operations}
    assert "service.UserService.rpc.GetUser" in refs
    assert "service.UserService.rpc.ListUsers" in refs


# ── Error handling ─────────────────────────────────────────────────────────────


def test_parse_protobuf_empty_string():
    result = parse_protobuf("")
    assert isinstance(result, SchemaIR)
    assert result.entities == []
    assert result.fields == []
    assert result.operations == []


def test_parse_protobuf_malformed_no_exception():
    result = parse_protobuf("message Broken {")
    assert isinstance(result, SchemaIR)
    # Should either return partial results or warnings, never raise
    # (The parser may succeed partially or emit a warning depending on the parser)


def test_parse_protobuf_no_exception_on_garbage():
    result = parse_protobuf("this is not valid proto syntax !!!")
    assert isinstance(result, SchemaIR)
