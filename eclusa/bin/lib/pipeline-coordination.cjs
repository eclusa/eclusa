'use strict';

/**
 * Pipeline ↔ Coordination integration.
 *
 * Makes pipeline stages expressible as plan units that the existing
 * coordination system (plan-phase, execute-phase, milestones) can manage.
 * Tracks pipeline artifacts in state management.
 */

const fs = require('fs');
const path = require('path');
// Lazy-load core.cjs to avoid pulling in the entire module tree during tests
let _core;
function getCore() {
  if (!_core) _core = require('./core.cjs');
  return _core;
}
function output(data) { getCore().output(data); }
function error(msg) { getCore().error(msg); }

// ─── Pipeline State ─────────────────────────────────────────────────────────

const PIPELINE_STAGES = ['refine', 'match', 'coherence', 'formalize', 'derive', 'generate'];

/**
 * Get the current pipeline state for a project.
 * Reads from .eclusa/PIPELINE.md if it exists.
 */
function getPipelineState(cwd) {
  const pipelinePath = path.join(cwd, '.eclusa', 'PIPELINE.md');
  if (!fs.existsSync(pipelinePath)) {
    return {
      exists: false,
      stages: PIPELINE_STAGES.map(name => ({
        name,
        status: 'pending',
        started_at: null,
        completed_at: null,
        artifacts: [],
      })),
    };
  }

  try {
    const content = fs.readFileSync(pipelinePath, 'utf-8');
    return parsePipelineState(content);
  } catch {
    return { exists: true, stages: [], error: 'Failed to parse PIPELINE.md' };
  }
}

/**
 * Update a pipeline stage's status and artifacts.
 */
function updatePipelineStage(cwd, stageName, update) {
  const state = getPipelineState(cwd);
  const stage = state.stages.find(s => s.name === stageName);
  if (!stage) {
    return { error: `Unknown stage: ${stageName}` };
  }

  if (update.status) stage.status = update.status;
  if (update.status === 'in_progress' && !stage.started_at) {
    stage.started_at = new Date().toISOString();
  }
  if (update.status === 'completed') {
    stage.completed_at = new Date().toISOString();
  }
  if (update.artifacts) {
    stage.artifacts = [...(stage.artifacts || []), ...update.artifacts];
  }

  writePipelineState(cwd, state);
  return { updated: stageName, status: stage.status };
}

/**
 * Write pipeline state to .eclusa/PIPELINE.md.
 */
function writePipelineState(cwd, state) {
  const eclusaDir = path.join(cwd, '.eclusa');
  if (!fs.existsSync(eclusaDir)) {
    fs.mkdirSync(eclusaDir, { recursive: true });
  }

  const lines = ['# Pipeline State\n'];
  lines.push(`Last updated: ${new Date().toISOString()}\n`);

  for (const stage of state.stages) {
    const icon = stage.status === 'completed' ? '✓' : stage.status === 'in_progress' ? '→' : '○';
    lines.push(`## ${icon} ${stage.name.charAt(0).toUpperCase() + stage.name.slice(1)}\n`);
    lines.push(`- **Status:** ${stage.status}`);
    if (stage.started_at) lines.push(`- **Started:** ${stage.started_at}`);
    if (stage.completed_at) lines.push(`- **Completed:** ${stage.completed_at}`);
    if (stage.artifacts && stage.artifacts.length > 0) {
      lines.push('- **Artifacts:**');
      for (const a of stage.artifacts) {
        lines.push(`  - ${a.type}: \`${a.path}\``);
      }
    }
    lines.push('');
  }

  const pipelinePath = path.join(eclusaDir, 'PIPELINE.md');
  fs.writeFileSync(pipelinePath, lines.join('\n'), 'utf-8');
}

function parsePipelineState(content) {
  const stages = [];
  const stageRegex = /## [✓→○] (\w+)/g;
  let match;

  while ((match = stageRegex.exec(content)) !== null) {
    const name = match[1].toLowerCase();
    const nextMatch = stageRegex.exec(content);
    const section = nextMatch
      ? content.slice(match.index, nextMatch.index)
      : content.slice(match.index);
    // Reset regex position if we peeked ahead
    if (nextMatch) stageRegex.lastIndex = nextMatch.index;

    const statusMatch = section.match(/\*\*Status:\*\*\s*(\w+)/);
    const startedMatch = section.match(/\*\*Started:\*\*\s*(.+)/);
    const completedMatch = section.match(/\*\*Completed:\*\*\s*(.+)/);

    stages.push({
      name,
      status: statusMatch ? statusMatch[1] : 'pending',
      started_at: startedMatch ? startedMatch[1].trim() : null,
      completed_at: completedMatch ? completedMatch[1].trim() : null,
      artifacts: [],
    });
  }

  // Ensure all stages present
  for (const name of PIPELINE_STAGES) {
    if (!stages.find(s => s.name === name)) {
      stages.push({ name, status: 'pending', started_at: null, completed_at: null, artifacts: [] });
    }
  }

  return { exists: true, stages };
}

// ─── Pipeline as Plan Units ─────────────────────────────────────────────────

/**
 * Generate plan units from pipeline stages.
 * These can be used by the planner to create atomic plan units
 * for each pipeline stage.
 */
function pipelineToPlanUnits(cwd) {
  const state = getPipelineState(cwd);
  const units = [];

  for (const stage of state.stages) {
    if (stage.status === 'completed') continue;

    units.push({
      type: 'pipeline_stage',
      stage: stage.name,
      command: stageToCommand(stage.name),
      description: stageDescription(stage.name),
      depends_on: stageDependencies(stage.name),
      gate: stageGate(stage.name),
    });
  }

  return units;
}

function stageToCommand(name) {
  const map = {
    refine: '/eclusa:new-project or /eclusa:discuss-phase',
    match: '/eclusa:match',
    coherence: '/eclusa:cohere',
    formalize: '/eclusa:constrain',
    derive: '/eclusa:derive',
    generate: '/eclusa:generate',
  };
  return map[name] || name;
}

function stageDescription(name) {
  const map = {
    refine: 'Multi-turn questioning to narrow scope. Human confirms.',
    match: 'Query schema commons for domain concept matches. Human confirms.',
    coherence: 'Check matched sources compose without conflicts.',
    formalize: 'Generate Haskell types + constraints. GHC must accept.',
    derive: 'Derive test suite from specs + compiled constraints.',
    generate: 'Generate code that passes all derived tests.',
  };
  return map[name] || '';
}

function stageDependencies(name) {
  const map = {
    refine: [],
    match: ['refine'],
    coherence: ['match'],
    formalize: ['coherence'],
    derive: ['formalize'],
    generate: ['derive'],
  };
  return map[name] || [];
}

function stageGate(name) {
  const map = {
    refine: 'Human confirms scope',
    match: 'Human confirms matches',
    coherence: 'No blocking incompatibilities (or human override)',
    formalize: 'ghc -fno-code accepts',
    derive: 'Tests internally consistent',
    generate: 'ALL tests pass',
  };
  return map[name] || '';
}

// ─── Artifact Tracking ──────────────────────────────────────────────────────

/**
 * Register a pipeline artifact.
 * @param {string} cwd
 * @param {string} stage - Pipeline stage name
 * @param {string} type - Artifact type (sources, coherence_report, constraints, test_suite, code)
 * @param {string} artifactPath - Path to the artifact
 */
function registerArtifact(cwd, stage, type, artifactPath) {
  return updatePipelineStage(cwd, stage, {
    artifacts: [{ type, path: artifactPath }],
  });
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

function cmdPipelineState(cwd) {
  output(getPipelineState(cwd));
}

function cmdPipelineUpdate(cwd, stageName, statusJson) {
  if (!stageName) {
    error('Usage: pipeline update <stage> \'{"status":"completed"}\'');
    return;
  }
  let update;
  try {
    update = JSON.parse(statusJson || '{}');
  } catch (e) {
    error(`Invalid JSON for pipeline update: ${e.message}`);
    return;
  }
  const result = updatePipelineStage(cwd, stageName, update);
  output(result);
}

function cmdPipelinePlanUnits(cwd) {
  output(pipelineToPlanUnits(cwd));
}

module.exports = {
  PIPELINE_STAGES,
  getPipelineState,
  updatePipelineStage,
  writePipelineState,
  pipelineToPlanUnits,
  registerArtifact,
  cmdPipelineState,
  cmdPipelineUpdate,
  cmdPipelinePlanUnits,
};
