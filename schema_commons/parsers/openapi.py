"""
schema_commons/parsers/openapi.py — Parse OpenAPI 3.x/2.0 specs to SchemaIR.

Decisions:
- D-01: Pure function, no side effects
- D-02: Input = raw text (str), output = SchemaIR
- D-03: Collects warnings rather than raising — partial parse is valid
- D-06: source_ref points to original spec location (e.g. "components.schemas.User")
"""

import yaml

from schema_commons.ir import (
    IREntity,
    IRField,
    IROperation,
    ParseWarning,
    SchemaIR,
)


def parse_openapi(text: str) -> SchemaIR:
    """Parse an OpenAPI 3.x YAML or JSON spec into SchemaIR.

    Collects warnings rather than raising (D-03).
    Never throws — malformed input produces SchemaIR with warnings and empty collections.
    """
    ir = SchemaIR(source_format="openapi")

    # Step 1: Parse YAML
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        ir.warnings.append(
            ParseWarning(location="root", message=f"YAML parse error: {exc}")
        )
        return ir

    if not isinstance(spec, dict):
        ir.warnings.append(
            ParseWarning(location="root", message="Spec is not a YAML mapping")
        )
        return ir

    # Step 2: Walk components.schemas → IREntity + IRField
    schemas = (spec.get("components") or {}).get("schemas", {}) or {}
    for schema_name, schema_def in schemas.items():
        if not isinstance(schema_def, dict):
            ir.warnings.append(
                ParseWarning(
                    location=f"components.schemas.{schema_name}",
                    message="Schema definition is not a mapping — skipped",
                )
            )
            continue

        ir.entities.append(
            IREntity(
                source_ref=f"components.schemas.{schema_name}",
                name=schema_name,
                description=schema_def.get("description"),
                type="model",
            )
        )

        required_fields: list[str] = schema_def.get("required") or []
        properties: dict = schema_def.get("properties") or {}
        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                prop_def = {}
            is_pk = prop_name in (schema_def.get("x-primary-keys") or [])
            ir.fields.append(
                IRField(
                    source_ref=f"components.schemas.{schema_name}.properties.{prop_name}",
                    entity_name=schema_name,
                    field_name=prop_name,
                    field_type=prop_def.get("type", "unknown"),
                    nullable=prop_name not in required_fields,
                    is_primary_key=is_pk,
                )
            )

    # Step 3: Walk paths → IROperation
    paths: dict = spec.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not op:
                continue
            if not isinstance(op, dict):
                continue
            op_id = (
                op.get("operationId")
                or f"{method.upper()}_{path.replace('/', '_').strip('_')}"
            )
            ir.operations.append(
                IROperation(
                    source_ref=f"paths.{path}.{method}",
                    name=op_id,
                    method=method.upper(),
                    path=path,
                )
            )

    return ir
