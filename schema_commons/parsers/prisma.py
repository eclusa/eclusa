"""
schema_commons/parsers/prisma.py — Hand-rolled Prisma DSL parser.

Parses Prisma schema language into SchemaIR without any external library.
Prisma's DSL is a simple block-structured format suitable for a targeted parser.

Decisions:
- D-03: Errors collected as ParseWarnings, not raised — partial parse is valid
- D-06: Each IR element carries source_ref pointing to original spec location
"""

from __future__ import annotations

import re

from schema_commons.ir import (
    IREntity,
    IRField,
    IRRelation,
    ParseWarning,
    SchemaIR,
)

# Regex: matches start of a model block: "model ModelName {"
_MODEL_START = re.compile(r"^\s*model\s+(\w+)\s*\{")

# Regex: matches end of a model block: closing brace at start of a line (optionally indented)
_BLOCK_END = re.compile(r"^\s*\}\s*$")

# Regex: matches a field line: "fieldName FieldType [attributes...]"
_FIELD_LINE = re.compile(r"^\s*(\w+)\s+([\w\[\]?]+)\s*(.*)?$")

# Regex: matches @relation attribute anywhere in a line
_RELATION_ATTR = re.compile(r"@relation\s*\(")


def _strip_comments(line: str) -> str:
    """Remove inline and full-line // comments from a Prisma line."""
    idx = line.find("//")
    if idx != -1:
        return line[:idx]
    return line


def _parse_field_type(raw_type: str) -> tuple[str, bool]:
    """
    Extract base type and nullability from a raw Prisma field type token.

    Examples:
      "String"   -> ("String", False)
      "String?"  -> ("String", True)
      "Post[]"   -> ("Post", False)   # array = non-nullable in the list sense
    """
    is_array = raw_type.endswith("[]")
    if is_array:
        raw_type = raw_type[:-2]

    nullable = raw_type.endswith("?")
    if nullable:
        raw_type = raw_type[:-1]

    return raw_type, nullable


def _infer_relation_type(raw_type: str) -> str:
    """Infer relation type from raw field type token."""
    if raw_type.endswith("[]"):
        return "one_to_many"
    if raw_type.endswith("?"):
        return "one_to_one"
    return "unknown"


def _extract_relation_target(attrs: str, field_type_base: str) -> str:
    """
    For a @relation field, the to_entity is the base field type (e.g., "User" from "User @relation(...)").
    This is already the model name extracted from the field declaration.
    """
    return field_type_base


def parse_prisma(text: str) -> SchemaIR:
    """
    Parse a Prisma schema string and return a SchemaIR.

    - Each `model X {}` block becomes an IREntity
    - Each field in a model block becomes an IRField
    - Fields with @relation become IRRelation entries (no exception raised on malformed input)
    - Malformed input produces ParseWarnings, never raises

    Args:
        text: Raw Prisma schema text

    Returns:
        SchemaIR with source_format="prisma"
    """
    ir = SchemaIR(source_format="prisma")

    if not text.strip():
        return ir

    lines = text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = _strip_comments(lines[i])
        model_match = _MODEL_START.match(line)

        if model_match:
            model_name = model_match.group(1)
            entity_ref = f"model.{model_name}"
            ir.entities.append(
                IREntity(
                    source_ref=entity_ref,
                    name=model_name,
                    type="model",
                )
            )
            i += 1
            # Collect field lines until closing brace
            block_open = True
            while i < n:
                field_line_raw = lines[i]
                field_line = _strip_comments(field_line_raw)

                # Check for closing brace
                if _BLOCK_END.match(field_line):
                    block_open = False
                    i += 1
                    break

                # Skip blank lines
                stripped = field_line.strip()
                if not stripped:
                    i += 1
                    continue

                # Skip block-level attributes (@@)
                if stripped.startswith("@@"):
                    i += 1
                    continue

                # Parse field line
                field_match = _FIELD_LINE.match(field_line)
                if field_match:
                    field_name = field_match.group(1)
                    raw_type = field_match.group(2)
                    attrs = field_match.group(3) or ""

                    # Skip Prisma keywords that appear inside blocks
                    if field_name in (
                        "model",
                        "enum",
                        "type",
                        "generator",
                        "datasource",
                    ):
                        i += 1
                        continue

                    base_type, nullable = _parse_field_type(raw_type)
                    is_primary = "@id" in attrs
                    # @id fields are never nullable in Prisma
                    if is_primary:
                        nullable = False

                    field_ref = f"{entity_ref}.{field_name}"

                    has_relation = _RELATION_ATTR.search(attrs)
                    is_array_field = raw_type.endswith("[]")

                    # Create IRField (including relation fields — they still have type info)
                    ir.fields.append(
                        IRField(
                            source_ref=field_ref,
                            entity_name=model_name,
                            field_name=field_name,
                            field_type=base_type,
                            nullable=nullable,
                            is_primary_key=is_primary,
                        )
                    )

                    # Create IRRelation for fields with @relation or array relation fields
                    if has_relation:
                        relation_type = _infer_relation_type(raw_type)
                        ir.relations.append(
                            IRRelation(
                                source_ref=field_ref,
                                from_entity=model_name,
                                to_entity=base_type,
                                relation_type=relation_type,
                            )
                        )
                    elif is_array_field:
                        # Array fields without explicit @relation (like Post[]) are still relations
                        ir.relations.append(
                            IRRelation(
                                source_ref=field_ref,
                                from_entity=model_name,
                                to_entity=base_type,
                                relation_type="one_to_many",
                            )
                        )

                i += 1

            # If we hit EOF without closing brace, it's malformed
            if block_open:
                ir.warnings.append(
                    ParseWarning(
                        location=f"model.{model_name}",
                        message=f"Unclosed model block for '{model_name}' — missing closing brace",
                    )
                )
        else:
            i += 1

    return ir
