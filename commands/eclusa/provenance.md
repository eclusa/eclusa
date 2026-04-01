---
description: Verify the provenance chain — hashes from human intent to shipped code
subagent_type: general-purpose
---

# eclusa:provenance

Verify the provenance chain. Each pipeline stage produces artifacts with content hashes stored as git trailers. This command walks the chain and checks all hashes match.

## Usage

```
/eclusa:provenance
```

## Behavior

1. Compute current provenance hashes:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" provenance compute
```

2. Verify against last committed hashes:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" provenance verify
```

3. Display:
   - Current hashes: project, sources, constraints, test suite
   - Last committed hashes (from git trailers)
   - Mismatches (files changed since last provenance commit)

4. If mismatches found, suggest:
   - Re-run the affected pipeline stage
   - Or commit with updated provenance trailers

## Adding Provenance to Commits

When committing pipeline artifacts, append trailers:
```bash
TRAILERS=$(node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" provenance trailers)
git commit -m "feat: description

$TRAILERS"
```

## Trailer Format

```
Eclusa-Sources-Hash: <16-hex-chars>
Eclusa-Constraints-Hash: <16-hex-chars>
Eclusa-Test-Suite-Hash: <16-hex-chars>
Eclusa-Project-Hash: <16-hex-chars>
```
