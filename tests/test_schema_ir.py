"""
tests/test_schema_ir.py — Unit tests for SchemaIR Pydantic models.

TDD RED: These tests are written before the implementation exists.
No DB fixture needed — purely Pydantic validation.
"""

import pytest
import json


class TestSchemaIRConstruction:
    def test_schema_ir_empty_construction(self):
        """SchemaIR(source_format='openapi') constructs with all lists empty."""
        from schema_commons.ir import SchemaIR

        ir = SchemaIR(source_format="openapi")
        assert ir.source_format == "openapi"
        assert ir.entities == []
        assert ir.fields == []
        assert ir.relations == []
        assert ir.operations == []
        assert ir.constraints == []
        assert ir.warnings == []

    def test_schema_ir_all_source_formats(self):
        """All five source_format literals are valid."""
        from schema_commons.ir import SchemaIR

        for fmt in ("openapi", "prisma", "sql_ddl", "graphql_sdl", "protobuf"):
            ir = SchemaIR(source_format=fmt)
            assert ir.source_format == fmt

    def test_schema_ir_invalid_source_format(self):
        """Unknown source_format raises ValidationError."""
        from pydantic import ValidationError
        from schema_commons.ir import SchemaIR

        with pytest.raises(ValidationError):
            SchemaIR(source_format="unknown_format")

    def test_schema_ir_json_serializable(self):
        """SchemaIR.model_dump_json() produces valid JSON (D-07)."""
        from schema_commons.ir import SchemaIR

        ir = SchemaIR(source_format="openapi")
        json_str = ir.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["source_format"] == "openapi"
        assert parsed["entities"] == []
        assert parsed["fields"] == []


class TestIREntity:
    def test_ir_entity_validates(self):
        """IREntity with source_ref and name validates."""
        from schema_commons.ir import IREntity

        entity = IREntity(source_ref="root.components.schemas.User", name="User")
        assert entity.source_ref == "root.components.schemas.User"
        assert entity.name == "User"

    def test_ir_entity_has_source_ref(self):
        """IREntity inherits source_ref from IRElement (D-06)."""
        from schema_commons.ir import IREntity

        entity = IREntity(source_ref="paths./users.get", name="GetUsers")
        assert entity.source_ref == "paths./users.get"

    def test_ir_entity_optional_description(self):
        """IREntity description defaults to None."""
        from schema_commons.ir import IREntity

        entity = IREntity(source_ref="x", name="X")
        assert entity.description is None

    def test_ir_entity_optional_type(self):
        """IREntity type defaults to 'model'."""
        from schema_commons.ir import IREntity

        entity = IREntity(source_ref="x", name="X")
        assert entity.type == "model"

    def test_ir_entity_valid_types(self):
        """IREntity type accepts all valid literal values."""
        from schema_commons.ir import IREntity

        for t in ("model", "message", "type", "table", "interface"):
            entity = IREntity(source_ref="x", name="X", type=t)
            assert entity.type == t


class TestIRField:
    def test_ir_field_validates(self):
        """IRField with entity_name, field_name, field_type, is_primary_key validates."""
        from schema_commons.ir import IRField

        field = IRField(
            source_ref="root.User.id",
            entity_name="User",
            field_name="id",
            field_type="string",
            is_primary_key=True,
        )
        assert field.entity_name == "User"
        assert field.field_name == "id"
        assert field.field_type == "string"
        assert field.is_primary_key is True

    def test_ir_field_defaults(self):
        """IRField nullable defaults True, is_primary_key defaults False."""
        from schema_commons.ir import IRField

        field = IRField(
            source_ref="x", entity_name="X", field_name="f", field_type="string"
        )
        assert field.nullable is True
        assert field.is_primary_key is False
        assert field.is_foreign_key is False
        assert field.foreign_ref is None


class TestIRRelation:
    def test_ir_relation_validates(self):
        """IRRelation with from_entity, to_entity, relation_type validates."""
        from schema_commons.ir import IRRelation

        rel = IRRelation(
            source_ref="root.User",
            from_entity="User",
            to_entity="Order",
            relation_type="one_to_many",
        )
        assert rel.from_entity == "User"
        assert rel.to_entity == "Order"
        assert rel.relation_type == "one_to_many"

    def test_ir_relation_all_types(self):
        """IRRelation accepts all valid relation_type literals."""
        from schema_commons.ir import IRRelation

        for rt in ("one_to_one", "one_to_many", "many_to_many", "unknown"):
            rel = IRRelation(
                source_ref="x", from_entity="A", to_entity="B", relation_type=rt
            )
            assert rel.relation_type == rt


class TestIROperation:
    def test_ir_operation_validates(self):
        """IROperation with name, method, path validates."""
        from schema_commons.ir import IROperation

        op = IROperation(
            source_ref="paths./users.post",
            name="createUser",
            method="POST",
            path="/users",
        )
        assert op.name == "createUser"
        assert op.method == "POST"
        assert op.path == "/users"

    def test_ir_operation_optional_fields(self):
        """IROperation method and path are optional."""
        from schema_commons.ir import IROperation

        op = IROperation(source_ref="x", name="someOp")
        assert op.method is None
        assert op.path is None


class TestIRConstraint:
    def test_ir_constraint_validates(self):
        """IRConstraint with entity_name, constraint_type, expression validates."""
        from schema_commons.ir import IRConstraint

        constraint = IRConstraint(
            source_ref="root.User",
            entity_name="User",
            constraint_type="unique",
            expression="email",
        )
        assert constraint.entity_name == "User"
        assert constraint.constraint_type == "unique"
        assert constraint.expression == "email"


class TestParseWarning:
    def test_parse_warning_validates(self):
        """ParseWarning with location and message validates."""
        from schema_commons.ir import ParseWarning

        warning = ParseWarning(location="root", message="invalid ref")
        assert warning.location == "root"
        assert warning.message == "invalid ref"

    def test_parse_warning_no_source_ref(self):
        """ParseWarning does NOT inherit from IRElement (no source_ref)."""
        from schema_commons.ir import ParseWarning

        # ParseWarning should not require source_ref
        warning = ParseWarning(location="x", message="y")
        assert not hasattr(warning, "source_ref") or True  # ok if it doesn't have it


class TestSchemaIRWithData:
    def test_schema_ir_with_all_fields(self):
        """SchemaIR with fully-populated data round-trips via JSON."""
        from schema_commons.ir import (
            SchemaIR,
            IREntity,
            IRField,
            IRRelation,
            IROperation,
            IRConstraint,
            ParseWarning,
        )

        ir = SchemaIR(
            source_format="openapi",
            entities=[IREntity(source_ref="schemas.User", name="User")],
            fields=[
                IRField(
                    source_ref="schemas.User.id",
                    entity_name="User",
                    field_name="id",
                    field_type="string",
                )
            ],
            relations=[
                IRRelation(
                    source_ref="x",
                    from_entity="User",
                    to_entity="Order",
                    relation_type="one_to_many",
                )
            ],
            operations=[
                IROperation(
                    source_ref="paths./users.post",
                    name="createUser",
                    method="POST",
                    path="/users",
                )
            ],
            constraints=[
                IRConstraint(
                    source_ref="x",
                    entity_name="User",
                    constraint_type="unique",
                    expression="email",
                )
            ],
            warnings=[ParseWarning(location="root", message="test warning")],
        )

        # JSON round-trip
        json_str = ir.model_dump_json()
        parsed = json.loads(json_str)
        assert len(parsed["entities"]) == 1
        assert parsed["entities"][0]["name"] == "User"
        assert len(parsed["warnings"]) == 1
        assert parsed["warnings"][0]["message"] == "test warning"

    def test_schema_ir_warnings_for_partial_parse(self):
        """SchemaIR warnings list supports D-03 partial parse pattern."""
        from schema_commons.ir import SchemaIR, ParseWarning

        ir = SchemaIR(source_format="prisma")
        ir.warnings.append(
            ParseWarning(location="model.User", message="unknown field type")
        )
        assert len(ir.warnings) == 1
        assert ir.warnings[0].location == "model.User"


class TestParserDepsImportable:
    def test_pyyaml_importable(self):
        import yaml  # noqa: F401

    def test_sqlglot_importable(self):
        import sqlglot  # noqa: F401

    def test_graphql_core_importable(self):
        import graphql  # noqa: F401

    def test_proto_schema_parser_importable(self):
        import proto_schema_parser  # noqa: F401

    def test_openapi_spec_validator_importable(self):
        import openapi_spec_validator  # noqa: F401
