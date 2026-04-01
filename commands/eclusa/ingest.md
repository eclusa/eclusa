---
description: Manage the schema commons — ingest, search, and prune typed domain knowledge
subagent_type: general-purpose
---

# eclusa:ingest

Manage the Qdrant-backed schema commons. Ingest typed domain knowledge from OpenAPI specs, Prisma schemas, SQL DDL, and other structured sources.

## Prerequisite

Schema commons must be enabled and Qdrant must be running. Check:
```bash
SCHEMA_ENABLED=$(node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" config-get schema_commons.enabled 2>/dev/null || echo "false")
```

If not enabled, display:
```
Schema commons is not enabled for this project.

To enable: node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" config-set schema_commons.enabled true
Then start Qdrant: docker compose up -d

Most projects don't need the schema commons — the standard discuss → plan → execute
workflow works without it. Enable only if your project integrates with typed external
APIs/schemas and you want automated source matching.
```
Exit without proceeding.

## Subcommands

### `eclusa:ingest url <url>`

Fetch and index a spec/schema from a URL. Auto-detects format.

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest url <url>
```

### `eclusa:ingest file <path>`

Index a local file.

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest file <path>
```

### `eclusa:ingest scan <directory>`

Recursively scan a directory for indexable files (OpenAPI, Prisma, SQL DDL). Index everything found.

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest scan <directory>
```

### `eclusa:ingest status`

Show index stats: total entries, sources, coverage by domain.

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest status
```

### `eclusa:ingest prune <source>`

Remove a source from the index by its origin identifier.

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest prune <source-origin>
```

## Supported Formats

| Format | File Extensions | What's Extracted |
|--------|----------------|------------------|
| OpenAPI 3.x | `.yaml`, `.yml`, `.json` | Endpoints, schemas, auth, status codes |
| Prisma | `.prisma` | Models, fields, relations, enums |
| SQL DDL | `.sql`, `.ddl` | Tables, columns, types, constraints, foreign keys |

Additional parsers (GraphQL, Protobuf, TypeScript, Gherkin) will be added incrementally.

## Prerequisites

Qdrant must be running. Start it with:

```bash
docker compose up -d
```

Or it starts automatically with `npx eclusa`.
