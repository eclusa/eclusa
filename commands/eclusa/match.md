---
description: Extract domain concepts from requirements, query schema commons, return ranked matches for human confirmation
subagent_type: general-purpose
---

# eclusa:match

Runs pipeline stages 1+2. Extracts domain concepts from the current project requirements, queries Qdrant schema commons for matching source schemas, and presents ranked results for human confirmation. On approval, writes `sources.matched` to the project file.

## Usage

```
/eclusa:match                   # interactive — extracts concepts, searches, confirms
/eclusa:match "auth,billing"    # skip extraction, search these concepts directly
```

## Prerequisite

Schema commons must be enabled. Check before proceeding:

```bash
SCHEMA_ENABLED=$(node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" config-get schema_commons.enabled 2>/dev/null || echo "true")
```

**If not enabled:**
```
Schema commons is disabled for this project. The match command requires Qdrant.

Re-enable: node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" config-set schema_commons.enabled true
Then run: docker compose up -d

The schema commons is enabled by default — it powers the eclusa pipeline for type-checked constraints and derived tests.
```
Exit. Do not proceed with Qdrant calls.

## Behavior

1. **Extract concepts** — Read the project requirements file. Identify domain concepts (nouns, bounded contexts, data entities). Present the extracted list to the human for review.

2. **Search schema commons** — For each confirmed concept, query Qdrant:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline match '["concept1","concept2","concept3"]'
   ```
   Parse the JSON response. Each result includes source name, similarity score, and schema summary.

3. **Rank and present** — Sort results by relevance. Group by source. Present a table: source name, matched concepts, score. Ask the human to confirm which sources to include.

4. **Commit matches** — Write the confirmed set:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline match-commit '{"sources":["source1","source2"],"concepts":["concept1","concept2"]}'
   ```

5. **Verify** — Read back the project file to confirm `sources.matched` was written correctly.

3. **Handle gaps — research on demand** — The match response includes a `gaps` array for concepts with no strong matches. If `research_needed` is true:

   Present gaps to the human:
   ```
   AskUserQuestion([{
     question: "These concepts have no strong matches in the schema commons. Research them?",
     header: "Gaps Found",
     multiSelect: true,
     options: [
       // One option per gap concept, plus:
       { label: "Research All", description: "Search the web for schemas/specs for all unmatched concepts" },
       { label: "Skip", description: "Mark as novel — no existing schema to match against" }
     ]
   }])
   ```

   If researching: follow the `research_instruction` from the match response. For each gap:
   - Use WebSearch to find official specs, GitHub repos with typed schemas, API documentation
   - Look for OpenAPI, Protobuf, GraphQL, TypeScript, JSON Schema, XSD — any typed interface
   - Also look for behavioral specs: RFC-style rules, state machines, constraint documentation
   - Ingest what you find:
     ```bash
     node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest url <found-url>
     ```
   - Re-run the match query to verify the concept now has matches

   If skipping: add the unmatched concepts to `sources.novel` in the project file — these are genuinely new domain concepts that will need more work in the formalize stage.

   **If web search is not available:** Ask the user to provide URLs or file paths for these domains. The user may know where the relevant specs live.

4. **Rank and present** — Sort results by relevance. Group by source. Present a table: source name, matched concepts, score. Ask the human to confirm which sources to include.

5. **Commit matches** — Write the confirmed set:
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" pipeline match-commit '{"sources":["source1","source2"],"concepts":["concept1","concept2"]}'
   ```

6. **Verify** — Read back the project file to confirm `sources.matched` was written correctly.

## Gates

- At least one concept was extracted and confirmed by the human.
- Gaps were either researched (and re-matched) or explicitly marked as novel.
- At least one source matched with score above threshold, or all concepts are novel.
- Human explicitly confirmed the source set before commit.
- `sources.matched` is present in the project file after commit.
