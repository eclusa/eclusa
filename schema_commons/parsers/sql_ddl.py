"""
schema_commons/parsers/sql_ddl.py — Parse SQL DDL statements to SchemaIR via sqlglot.

Decisions:
- D-01: Pure function, no side effects
- D-02: Input = raw text (str), output = SchemaIR
- D-03: Collects warnings rather than raising — partial parse is valid
- D-06: source_ref points to original spec location (e.g. "statement.0.column.id")
"""

import sqlglot
import sqlglot.expressions as exp

from schema_commons.ir import (
    IREntity,
    IRField,
    IRRelation,
    ParseWarning,
    SchemaIR,
)


def parse_sql_ddl(text: str) -> SchemaIR:
    """Parse SQL DDL text into SchemaIR.

    Handles CREATE TABLE statements, PRIMARY KEY, NOT NULL, and REFERENCES constraints.
    Collects warnings rather than raising (D-03).
    Never throws — malformed or empty input produces SchemaIR with optional warnings.
    """
    ir = SchemaIR(source_format="sql_ddl")

    try:
        statements = sqlglot.parse(text)
    except Exception as exc:
        ir.warnings.append(ParseWarning(location="root", message=str(exc)))
        return ir

    for stmt_idx, stmt in enumerate(statements):
        if stmt is None:
            continue
        if not isinstance(stmt, exp.Create):
            continue

        table_node = stmt.find(exp.Table)
        if not table_node:
            continue

        table_name = table_node.name
        ir.entities.append(
            IREntity(
                source_ref=f"statement.{stmt_idx}",
                name=table_name,
                type="table",
            )
        )

        for col in stmt.find_all(exp.ColumnDef):
            col_name = col.name

            # Collect column constraints (PK, NOT NULL, DEFAULT, REFERENCES)
            constraints = list(col.find_all(exp.ColumnConstraint))
            is_pk = any(
                isinstance(c.kind, exp.PrimaryKeyColumnConstraint) for c in constraints
            )
            is_nn = any(
                isinstance(c.kind, exp.NotNullColumnConstraint) for c in constraints
            )

            # Foreign key: column-level REFERENCES clause
            fk_ref: str | None = None
            is_fk = False
            ref_node = col.find(exp.Reference)
            if ref_node:
                is_fk = True
                ref_table = ref_node.find(exp.Table)
                fk_ref = ref_table.name if ref_table else None
                if fk_ref:
                    ir.relations.append(
                        IRRelation(
                            source_ref=f"statement.{stmt_idx}.column.{col_name}",
                            from_entity=table_name,
                            to_entity=fk_ref,
                            relation_type="unknown",
                        )
                    )

            # Column type
            col_type_node = col.args.get("kind")
            col_type_str = str(col_type_node) if col_type_node else "unknown"

            ir.fields.append(
                IRField(
                    source_ref=f"statement.{stmt_idx}.column.{col_name}",
                    entity_name=table_name,
                    field_name=col_name,
                    field_type=col_type_str,
                    nullable=not is_nn and not is_pk,
                    is_primary_key=is_pk,
                    is_foreign_key=is_fk,
                    foreign_ref=fk_ref,
                )
            )

    return ir
