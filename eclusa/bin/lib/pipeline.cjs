'use strict';

/**
 * Pipeline stages for eclusa's six-stage narrowing pipeline.
 *
 * Stage 1 (REFINE): Handled by the existing questioning phase (eclusa:new-project / eclusa:discuss-phase)
 * Stage 2 (MATCH): Query Qdrant for domain concept matches
 * Stage 3 (COHERENCE): Check matched sources compose
 * Stage 4 (FORMALIZE): Generate Haskell constraints, GHC type-check
 * Stage 5 (DERIVE): Derive tests from specs + constraints
 * Stage 6 (GENERATE): Generate code that passes tests
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { QdrantClient, embed, embedSync } = require('./qdrant.cjs');
const { loadProjectFile, saveProjectFile } = require('./project-file.cjs');
const { output, error } = require('./core.cjs');

// ─── Stage 2: MATCH ─────────────────────────────────────────────────────────

/**
 * Extract domain concepts from requirements/project docs,
 * query Qdrant, return ranked matches.
 */
async function stageMatch(cwd, concepts) {
  const client = new QdrantClient();
  const alive = await client.ping();
  if (!alive) {
    return { error: 'Qdrant not running. Start with: docker compose up -d' };
  }

  await client.ensureCollection();

  const results = [];
  for (const concept of concepts) {
    const vector = await embed(concept);
    const matches = await client.search(vector, 5);
    results.push({
      concept,
      matches: matches.map(m => ({
        score: m.score,
        entity_name: m.payload.entity_name,
        source_origin: m.payload.source_origin,
        source_format: m.payload.source_format,
        entry_type: m.payload.entry_type,
        field_names: m.payload.field_names || [],
      })),
    });
  }

  // Detect gaps — concepts with no strong matches
  const MATCH_THRESHOLD = 0.3;
  const gaps = [];
  for (const r of results) {
    const bestScore = r.matches.length > 0 ? r.matches[0].score : 0;
    if (bestScore < MATCH_THRESHOLD) {
      gaps.push({
        concept: r.concept,
        best_score: bestScore,
        suggestion: `No strong match for "${r.concept}" in the schema commons.`,
      });
    }
  }

  return {
    stage: 'match',
    concepts_queried: concepts.length,
    results,
    gaps,
    research_needed: gaps.length > 0,
    research_instruction: gaps.length > 0 ? buildResearchInstruction(gaps) : null,
  };
}

/**
 * Build research instructions for unmatched concepts.
 * Tells the agent to use web search to find typed schemas/specs,
 * then ingest them into the commons.
 */
function buildResearchInstruction(gaps) {
  const conceptList = gaps.map(g => `"${g.concept}"`).join(', ');
  return {
    action: 'research_and_ingest',
    concepts: gaps.map(g => g.concept),
    instruction: `The following concepts had no strong matches in the schema commons: ${conceptList}.

For each unmatched concept:
1. Search the web for typed schemas, API specs, or formal standards related to this concept.
   - Look for OpenAPI specs, Protobuf definitions, GraphQL SDL, TypeScript types, JSON Schema, XSD, or any typed interface.
   - Prefer official/canonical sources: GitHub repos of the standard body or major implementation.
   - Also look for behavioral specifications: RFC-style docs, state machine descriptions, business rule documentation.

2. When you find a relevant source:
   - If it's a URL to a raw file (spec, schema): ingest it directly:
     node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest url <url>
   - If it's a GitHub repo with relevant files: ingest the repo:
     node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" ingest file <path>
   - Report what you found and what you ingested.

3. After ingesting, re-run the match query to verify the concept now has matches.

If web search is not available, ask the user to provide URLs or file paths for these domains.`,
  };
}

/**
 * Write match results to the project file's sources.matched section.
 */
function commitMatches(cwd, matches) {
  const projectResult = loadProjectFile(cwd);
  if (!projectResult.found || !projectResult.data) {
    return { error: 'No project.eclusa found. Run eclusa:new-project first.' };
  }

  const project = projectResult.data;
  if (!project.sources) project.sources = { matched: [], novel: [] };

  // Group matches by source origin
  const byOrigin = {};
  for (const result of matches) {
    for (const match of result.matches) {
      if (match.score < 0.3) continue; // Skip low-confidence matches
      if (!byOrigin[match.source_origin]) {
        byOrigin[match.source_origin] = {
          origin: match.source_origin,
          format: match.source_format,
          entities: new Set(),
        };
      }
      if (match.entity_name) {
        byOrigin[match.source_origin].entities.add(match.entity_name);
      }
    }
  }

  project.sources.matched = Object.values(byOrigin).map(src => ({
    origin: src.origin,
    format: src.format,
    entities: Array.from(src.entities),
  }));

  saveProjectFile(cwd, project);
  return { sources_matched: project.sources.matched.length };
}

// ─── Stage 3: COHERENCE ─────────────────────────────────────────────────────

/**
 * Check that matched sources compose.
 * Produces a coherence report with warnings.
 * This is an LLM-assisted stage — output is a prompt for the agent.
 */
function stageCoherence(cwd) {
  const projectResult = loadProjectFile(cwd);
  if (!projectResult.found || !projectResult.data) {
    return { error: 'No project.eclusa found.' };
  }

  const project = projectResult.data;
  const matched = project.sources?.matched || [];
  const novel = project.sources?.novel || [];

  if (matched.length === 0 && novel.length === 0) {
    return { error: 'No matched or novel sources. Run eclusa:match first.' };
  }

  // Build the coherence check prompt context
  return {
    stage: 'coherence',
    matched_sources: matched,
    novel_sources: novel,
    checks: [
      'Type boundary compatibility — do entity types align across sources?',
      'Auth model consistency — is there one auth model or conflicting ones?',
      'Data model friction — are there naming conflicts, type mismatches?',
      'Missing links — are there entities referenced but not matched?',
      'Cardinality conflicts — do relation cardinalities agree?',
    ],
    instruction: 'Analyze the matched source set for composition issues. Report warnings and blocking incompatibilities. If no blockers, output a clean coherence report.',
  };
}

// ─── Stage 4: FORMALIZE ─────────────────────────────────────────────────────

/**
 * Scaffold constraints.hs from matched sources.
 * Auto-generates Haskell type modules from IR.
 * Returns context for the LLM to draft constraint functions.
 */
function stageFormalize(cwd) {
  const projectResult = loadProjectFile(cwd);
  if (!projectResult.found || !projectResult.data) {
    return { error: 'No project.eclusa found.' };
  }

  const project = projectResult.data;
  const matched = project.sources?.matched || [];

  if (matched.length === 0) {
    return { error: 'No matched sources. Run eclusa:match first.' };
  }

  // Generate Haskell type stubs from matched source entities
  const modules = [];
  for (const source of matched) {
    const moduleName = sourceToModuleName(source.origin);
    const entities = source.entities || [];

    let haskell = `-- Generated from ${source.origin}\nmodule Sources.${moduleName} where\n\nimport Data.Text (Text)\nimport Data.Time (UTCTime)\n\n`;

    for (const entityName of entities) {
      haskell += `data ${entityName} = ${entityName}\n  { -- Fields to be filled from IR\n  } deriving (Show, Eq)\n\n`;
    }

    modules.push({
      module_name: `Sources.${moduleName}`,
      file_path: `constraints/Sources/${moduleName}.hs`,
      content: haskell,
      entities,
    });
  }

  // Scaffold constraints.hs
  const constraintsHs = `module Constraints where\n\n${modules.map(m => `import ${m.module_name}`).join('\n')}\n\n-- Business rule constraints go here.\n-- Each constraint is a function over source types.\n-- GHC type-checks: ghc -fno-code Constraints.hs\n`;

  return {
    stage: 'formalize',
    modules,
    constraints_scaffold: constraintsHs,
    instruction: [
      'Write type modules to constraints/Sources/*.hs with fields from matched IR.',
      'Draft constraint functions in Constraints.hs from business rules.',
      'Run: ghc -fno-code -iconstraints Constraints.hs',
      'Iterate until GHC accepts. Escalate to human if business rule conflicts with API surface.',
    ],
  };
}

/**
 * Run GHC type-check on constraints.hs.
 * Uses Docker (ghc service) if available, falls back to system ghc.
 */
function checkConstraints(cwd) {
  const constraintsDir = path.join(cwd, 'constraints');
  const constraintsFile = path.join(constraintsDir, 'Constraints.hs');

  if (!fs.existsSync(constraintsFile)) {
    return { compiled: false, error: 'constraints/Constraints.hs not found. Run eclusa:constrain first.' };
  }

  // Try Docker first (ghc service from eclusa compose stack)
  try {
    execSync(
      'docker compose --profile constrain exec -T ghc ghc -fno-code -i/workspace/constraints /workspace/constraints/Constraints.hs',
      { cwd, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return { compiled: true, errors: [], via: 'docker' };
  } catch (dockerErr) {
    // If Docker fails, try system GHC
    const dockerStderr = dockerErr.stderr?.toString() || '';
    if (dockerStderr.includes('no such service') || dockerStderr.includes('not found') || dockerStderr.includes('Cannot connect')) {
      try {
        execSync(`ghc -fno-code -i${constraintsDir} ${constraintsFile}`, {
          cwd, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'],
        });
        return { compiled: true, errors: [], via: 'system' };
      } catch (sysErr) {
        const stderr = sysErr.stderr?.toString() || sysErr.message;
        if (stderr.includes('not found') || stderr.includes('No such file')) {
          return {
            compiled: false,
            error: 'GHC not available. Start with: docker compose --profile constrain up -d ghc',
          };
        }
        return { compiled: false, errors: parseGhcErrors(stderr), via: 'system' };
      }
    }
    // Docker ran but GHC rejected the code — this is the expected failure path
    return { compiled: false, errors: parseGhcErrors(dockerStderr), via: 'docker' };
  }
}

function parseGhcErrors(stderr) {
  return stderr
    .split('\n')
    .filter(line => line.includes(':') && (line.includes('error') || line.includes('warning')))
    .map(line => line.trim());
}

// ─── Stage 5: DERIVE ────────────────────────────────────────────────────────

/**
 * Derive test suite from source specs + compiled constraints.
 * Returns context for the LLM to generate tests.
 */
function stageDerive(cwd) {
  const projectResult = loadProjectFile(cwd);
  if (!projectResult.found || !projectResult.data) {
    return { error: 'No project.eclusa found.' };
  }

  const project = projectResult.data;

  // Check constraints compiled
  const constraintsResult = checkConstraints(cwd);

  return {
    stage: 'derive',
    constraints_compiled: constraintsResult.compiled,
    constraints_errors: constraintsResult.errors || [],
    matched_sources: project.sources?.matched || [],
    novel_sources: project.sources?.novel || [],
    stances: project.stances || [],
    instruction: [
      'Derive BDD/E2E tests from matched source structure + formal constraints.',
      'For each matched entity: test CRUD operations against source spec.',
      'For each constraint: test the business rule it encodes.',
      'For each novel concept: test the interface described in the project file.',
      'Tests must be internally consistent — no test contradicts another.',
      'Template-driven where possible. LLM for edge cases only.',
    ],
  };
}

// ─── Stage 6: GENERATE ──────────────────────────────────────────────────────

/**
 * Generate code that passes the derived test suite.
 * Returns context for the cheapest capable model.
 */
function stageGenerate(cwd) {
  const projectResult = loadProjectFile(cwd);
  if (!projectResult.found || !projectResult.data) {
    return { error: 'No project.eclusa found.' };
  }

  const project = projectResult.data;

  return {
    stage: 'generate',
    matched_sources: project.sources?.matched || [],
    novel_sources: project.sources?.novel || [],
    constraints_file: project.constraints?.file || 'constraints/Constraints.hs',
    instruction: [
      'Generate code against known typed interfaces.',
      'Code must pass ALL tests from the derive stage.',
      'Use cheapest model that can handle the complexity.',
      'Compose against matched source libraries where possible.',
      'Novel concepts require more creativity but are still test-constrained.',
      'Do not evaluate your own output — tests are the gate.',
    ],
  };
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function sourceToModuleName(origin) {
  return origin
    .replace(/^(qdrant|local|url|github):/, '')
    .replace(/[^a-zA-Z0-9]/g, '_')
    .split('_')
    .filter(Boolean)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join('');
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

async function cmdMatch(cwd, conceptsJson) {
  try {
    const concepts = JSON.parse(conceptsJson || '[]');
    if (concepts.length === 0) {
      error('Usage: pipeline match \'["concept1","concept2"]\'');
      return;
    }
    const result = await stageMatch(cwd, concepts);
    output(result);
  } catch (err) {
    error(err.message);
  }
}

function cmdMatchCommit(cwd, matchesJson) {
  try {
    const matches = JSON.parse(matchesJson || '[]');
    const result = commitMatches(cwd, matches);
    output(result);
  } catch (err) {
    error(err.message);
  }
}

function cmdCoherence(cwd) {
  output(stageCoherence(cwd));
}

function cmdFormalize(cwd) {
  output(stageFormalize(cwd));
}

function cmdCheckConstraints(cwd) {
  output(checkConstraints(cwd));
}

function cmdDerive(cwd) {
  output(stageDerive(cwd));
}

function cmdGenerate(cwd) {
  output(stageGenerate(cwd));
}

module.exports = {
  stageMatch,
  commitMatches,
  stageCoherence,
  stageFormalize,
  checkConstraints,
  stageDerive,
  stageGenerate,
  sourceToModuleName,
  cmdMatch,
  cmdMatchCommit,
  cmdCoherence,
  cmdFormalize,
  cmdCheckConstraints,
  cmdDerive,
  cmdGenerate,
};
