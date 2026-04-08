"""
schema_commons/parsers/protobuf.py — Protobuf .proto to SchemaIR via proto-schema-parser.

Uses proto-schema-parser (antlr4-based) to parse proto2/proto3/editions files
into a typed AST, then maps that AST to SchemaIR.

Decisions:
- D-03: Errors collected as ParseWarnings, not raised — partial parse is valid
- D-06: Each IR element carries source_ref pointing to original spec location

proto-schema-parser AST key types (from ast.py):
  File.file_elements: List[FileElement]
  Message.name: str, Message.elements: List[MessageElement]
  Field.name: str, Field.type: str, Field.cardinality: FieldCardinality | None
  FieldCardinality.REPEATED = "REPEATED"
  Service.name: str, Service.elements: List[ServiceElement]
  Method.name: str, Method.input_type: MessageType, Method.output_type: MessageType
"""

from __future__ import annotations

from proto_schema_parser.parser import Parser as ProtoParser
from proto_schema_parser.ast import (
    Message,
    Field,
    Service,
    Method,
    FieldCardinality,
)

from schema_commons.ir import (
    IREntity,
    IRField,
    IROperation,
    ParseWarning,
    SchemaIR,
)


def _field_type_str(field: Field) -> str:
    """
    Extract type string from a proto Field AST node.

    For repeated fields, prefixes the type with "repeated ".
    For optional/required fields (proto2), just returns the base type.
    """
    base_type = field.type
    cardinality = field.cardinality
    if cardinality is FieldCardinality.REPEATED:
        return f"repeated {base_type}"
    return base_type


def _walk_elements(
    elements: list, ir: SchemaIR, service_name: str | None = None
) -> None:
    """
    Recursively walk proto AST file or message elements, populating the SchemaIR.

    Args:
        elements: List of AST elements (file-level or message-level)
        ir: SchemaIR to populate in-place
        service_name: Name of the enclosing service (for RPC source_ref)
    """
    for element in elements:
        if isinstance(element, Message):
            entity_ref = f"message.{element.name}"
            ir.entities.append(
                IREntity(
                    source_ref=entity_ref,
                    name=element.name,
                    type="message",
                )
            )
            # Walk message body for fields (nested messages handled recursively)
            for body_element in element.elements:
                if isinstance(body_element, Field):
                    ir.fields.append(
                        IRField(
                            source_ref=f"{entity_ref}.field.{body_element.name}",
                            entity_name=element.name,
                            field_name=body_element.name,
                            field_type=_field_type_str(body_element),
                            nullable=True,  # proto3: all fields are technically optional
                            is_primary_key=False,
                        )
                    )
                elif isinstance(body_element, Message):
                    # Nested message — recurse
                    _walk_elements([body_element], ir)

        elif isinstance(element, Service):
            for service_element in element.elements:
                if isinstance(service_element, Method):
                    ir.operations.append(
                        IROperation(
                            source_ref=f"service.{element.name}.rpc.{service_element.name}",
                            name=service_element.name,
                            method="rpc",
                            path=None,
                        )
                    )


def parse_protobuf(text: str) -> SchemaIR:
    """
    Parse a protobuf .proto schema string and return a SchemaIR.

    - Each `message X {}` block becomes an IREntity with type="message"
    - Message fields become IRField entries (repeated prefix included in field_type)
    - Service RPC methods become IROperation entries with method="rpc"
    - Malformed input produces ParseWarnings, never raises

    Args:
        text: Raw .proto schema text

    Returns:
        SchemaIR with source_format="protobuf"
    """
    ir = SchemaIR(source_format="protobuf")

    if not text.strip():
        return ir

    try:
        proto_file = ProtoParser().parse(text)
    except Exception as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir

    _walk_elements(proto_file.file_elements, ir)
    return ir
