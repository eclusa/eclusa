---
phase: 04-knowledge-layer
plan: "03"
subsystem: schema_commons/parsers
tags: [parser, prisma, protobuf, schema-ir, tdd]
dependency_graph:
  requires: [04-01]
  provides: [parse_prisma, parse_protobuf]
  affects: [schema_commons.parsers, COMMONS-02, COMMONS-03]
tech_stack:
  added: []
  patterns: [hand-rolled-tokenizer, proto-schema-parser-ast, tdd-red-green]
key_files:
  created:
    - schema_commons/parsers/prisma.py
    - schema_commons/parsers/protobuf.py
  modified:
    - tests/test_parsers_prisma.py
    - tests/test_parsers_protobuf.py
decisions:
  - proto-schema-parser uses Method (not RPC) for service methods — ast.Method.name is the RPC name
  - Prisma array fields (Post[]) without explicit @relation still produce IRRelation (one_to_many) since they represent the back-reference side of a relation
  - antlr4-based proto parser recovers from malformed input without raising — partial AST returned with stderr output, fits D-03 without needing explicit try/except wrapping for most malformed inputs
metrics:
  duration: "4min"
  completed: "2026-04-05T04:39:26Z"
  tasks: 2
  files: 4
---

# Phase 04 Plan 03: Prisma and Protobuf Parsers Summary

**One-liner:** Prisma hand-rolled regex/tokenizer parser and proto-schema-parser-backed Protobuf parser, both returning SchemaIR with 33 green TDD tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Prisma parser failing tests | 8e44ea1 | tests/test_parsers_prisma.py |
| 1 (GREEN) | parse_prisma() implementation | 9582c09 | schema_commons/parsers/prisma.py |
| 2 (RED) | Protobuf parser failing tests | ff9cb60 | tests/test_parsers_protobuf.py |
| 2 (GREEN) | parse_protobuf() implementation | 42b0adf | schema_commons/parsers/protobuf.py |

## What Was Built

### Task 1: parse_prisma() — Hand-rolled Prisma DSL Parser

`schema_commons/parsers/prisma.py` (~160 lines):

- Line-by-line tokenizer with `_MODEL_START` regex to detect `model X {}` blocks
- `_strip_comments()` removes `//` inline and full-line comments before tokenization
- `_parse_field_type()` strips `?` (nullable) and `[]` (array) to extract base type
- `@id` attribute sets `is_primary_key=True` and forces `nullable=False`
- `@relation` fields produce IRRelation (from_entity=current model, to_entity=field base type)
- Array fields (`Post[]`) without explicit `@relation` also produce IRRelation(one_to_many)
- Unclosed model blocks (EOF before `}`) emit ParseWarning without raising
- Empty input returns empty SchemaIR with no warnings

**source_ref format:**
- IREntity: `model.User`
- IRField: `model.User.id`
- IRRelation: `model.Post.user` (same as the field that triggered the relation)

### Task 2: parse_protobuf() — Protobuf Parser via proto-schema-parser

`schema_commons/parsers/protobuf.py` (~130 lines):

- Uses `proto_schema_parser.parser.Parser().parse(text)` to get `ast.File`
- `_walk_elements()` recursively processes `ast.Message`, `ast.Field`, `ast.Service`, `ast.Method`
- Message → IREntity(type="message", source_ref="message.Name")
- Field → IRField(field_type includes "repeated " prefix for REPEATED cardinality)
- Service + Method → IROperation(method="rpc", source_ref="service.S.rpc.M")
- Try/except wraps the top-level parse call; antlr4 recovers internally for most malformed input

**source_ref format:**
- IREntity: `message.User`
- IRField: `message.User.field.id`
- IROperation: `service.UserService.rpc.GetUser`

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as specified.

**Adjustment noted (not a deviation):** The plan's action block referred to service methods as `RPC` but the proto-schema-parser library uses `ast.Method` for service methods (not `RPC`). The plan's action block already acknowledged this possibility ("Read the actual installed version's source"). The implementation correctly uses `isinstance(service_element, Method)`.

## Verification Results

```
tests/test_parsers_prisma.py   — 16 passed
tests/test_parsers_protobuf.py — 17 passed
Total: 33 passed
Full suite: 215 passed, 15 skipped (Wave 0 stubs), 0 failed
```

Clean import check: `python -c "from schema_commons.parsers.prisma import parse_prisma; from schema_commons.parsers.protobuf import parse_protobuf; print('ok')"` → `ok`

## Known Stubs

None — both parsers are fully wired against real fixture inputs.

## Self-Check: PASSED
