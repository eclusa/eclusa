'use strict';

/**
 * project.eclusa — machine-readable project file for the eclusa pipeline.
 *
 * Lives at project root. Created during questioning phase (eclusa:new-project).
 * Read by pipeline stages (match, cohere, constrain, derive, generate).
 * Human-editable YAML with well-defined schema.
 */

const fs = require('fs');
const path = require('path');
const { parseYaml, dumpYaml } = require('./yaml.cjs');

// ─── Schema Defaults ────────────────────────────────────────────────────────

const DEFAULT_PROJECT_FILE = {
  version: 5,
  identity: {
    name: '',
    description: '',
    tags: [],
  },
  sources: {
    matched: [],
    novel: [],
  },
  constraints: {
    file: null,
  },
  stances: [],
  provenance: {
    governance_level: 'full',
    storage: 'git-trailers',
  },
  agents: {
    models: {
      frontier: { model: 'claude-opus-4-6', parameters: { thinking: 'extended' } },
      standard: { model: 'claude-sonnet-4-6', parameters: { thinking: 'standard' } },
      fast: { model: 'claude-sonnet-4-6', parameters: { thinking: 'off' } },
      verify: { model: 'claude-sonnet-4-6', parameters: { temperature: 0 } },
    },
    stage_bindings: {
      refine: 'frontier',
      coherence: 'standard',
      formalize: 'standard',
      derive: 'fast',
      generate: 'fast',
    },
    topology: 'delegating',
  },
};

const DEFAULT_STANCES = [
  {
    name: 'Reviewed Commits',
    premise: 'AI-generated diffs require human eyes.',
    rule: 'Present diff grouped by concern. Wait for approval.',
    enforcement: 'require(diff.approved_by_human)',
    materialization: {
      paths: [
        { type: 'git_hook', hook: 'pre-commit: check approval marker' },
      ],
    },
  },
  {
    name: 'Model Provenance',
    premise: 'Every AI-touched commit must be traceable.',
    rule: 'Co-Authored-By with model-id.',
    enforcement: 'require(ai_commit.has_model_provenance)',
    materialization: {
      paths: [
        { type: 'git_hook', hook: 'commit-msg: validate Co-Authored-By' },
      ],
    },
  },
  {
    name: 'Conservative Default',
    premise: 'Silence is not consent.',
    rule: 'Surface gaps. Don\'t guess.',
    enforcement: 'require(gaps.resolved_or_explicitly_deferred)',
  },
];

// ─── Validation ─────────────────────────────────────────────────────────────

const VALID_GOVERNANCE_LEVELS = ['full', 'light', 'none'];
const VALID_STORAGE_TYPES = ['git-trailers', 'file'];
const VALID_TOPOLOGIES = ['delegating', 'flat'];
const VALID_STAGE_NAMES = ['refine', 'coherence', 'formalize', 'derive', 'generate'];

function validate(project) {
  const errors = [];

  if (!project || typeof project !== 'object') {
    return [{ path: '', message: 'Project file must be a YAML object' }];
  }

  // version
  if (project.version !== 5) {
    errors.push({ path: 'version', message: `Expected version 5, got ${project.version}` });
  }

  // identity
  if (!project.identity || typeof project.identity !== 'object') {
    errors.push({ path: 'identity', message: 'Missing identity section' });
  } else {
    if (!project.identity.name || typeof project.identity.name !== 'string') {
      errors.push({ path: 'identity.name', message: 'identity.name must be a non-empty string' });
    }
    if (project.identity.tags && !Array.isArray(project.identity.tags)) {
      errors.push({ path: 'identity.tags', message: 'identity.tags must be an array' });
    }
  }

  // sources (optional until match stage runs)
  if (project.sources) {
    if (project.sources.matched && !Array.isArray(project.sources.matched)) {
      errors.push({ path: 'sources.matched', message: 'sources.matched must be an array' });
    }
    if (project.sources.novel && !Array.isArray(project.sources.novel)) {
      errors.push({ path: 'sources.novel', message: 'sources.novel must be an array' });
    }
  }

  // constraints (optional until constrain stage runs)
  if (project.constraints && project.constraints.file) {
    if (typeof project.constraints.file !== 'string') {
      errors.push({ path: 'constraints.file', message: 'constraints.file must be a string path' });
    }
  }

  // stances
  if (project.stances) {
    if (!Array.isArray(project.stances)) {
      errors.push({ path: 'stances', message: 'stances must be an array' });
    } else {
      project.stances.forEach((s, idx) => {
        if (!s.name) errors.push({ path: `stances[${idx}].name`, message: 'Stance must have a name' });
        if (!s.rule) errors.push({ path: `stances[${idx}].rule`, message: 'Stance must have a rule' });
      });
    }
  }

  // provenance
  if (project.provenance) {
    if (project.provenance.governance_level && !VALID_GOVERNANCE_LEVELS.includes(project.provenance.governance_level)) {
      errors.push({ path: 'provenance.governance_level', message: `Must be one of: ${VALID_GOVERNANCE_LEVELS.join(', ')}` });
    }
    if (project.provenance.storage && !VALID_STORAGE_TYPES.includes(project.provenance.storage)) {
      errors.push({ path: 'provenance.storage', message: `Must be one of: ${VALID_STORAGE_TYPES.join(', ')}` });
    }
  }

  // agents
  if (project.agents) {
    if (project.agents.stage_bindings) {
      for (const stage of Object.keys(project.agents.stage_bindings)) {
        if (!VALID_STAGE_NAMES.includes(stage)) {
          errors.push({ path: `agents.stage_bindings.${stage}`, message: `Unknown stage: ${stage}` });
        }
      }
    }
    if (project.agents.topology && !VALID_TOPOLOGIES.includes(project.agents.topology)) {
      errors.push({ path: 'agents.topology', message: `Must be one of: ${VALID_TOPOLOGIES.join(', ')}` });
    }
  }

  return errors;
}

// ─── Load / Save ────────────────────────────────────────────────────────────

function findProjectFile(cwd) {
  const candidates = ['project.eclusa', 'project.eclusa.yaml', 'project.eclusa.yml'];
  for (const name of candidates) {
    const p = path.join(cwd, name);
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function loadProjectFile(cwd) {
  const filePath = findProjectFile(cwd);
  if (!filePath) return { found: false, path: null, data: null, errors: ['No project.eclusa file found'] };

  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    const data = parseYaml(raw);
    const errors = validate(data);
    return { found: true, path: filePath, data, errors };
  } catch (err) {
    return { found: true, path: filePath, data: null, errors: [`Parse error: ${err.message}`] };
  }
}

function saveProjectFile(cwd, data) {
  const filePath = path.join(cwd, 'project.eclusa');
  const header = '# project.eclusa — eclusa pipeline project file\n# https://eclusa.dev\n---\n';
  const yaml = dumpYaml(data);
  fs.writeFileSync(filePath, header + yaml + '\n', 'utf-8');
  return filePath;
}

// ─── Scaffold ───────────────────────────────────────────────────────────────

/**
 * Create a new project.eclusa from questioning phase output.
 * @param {object} opts - { name, description, tags }
 * @param {object} vestibular - Loaded vestibular (if any), for inheriting stances
 * @returns {object} The scaffolded project data
 */
function scaffoldProjectFile(opts, vestibular) {
  const project = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));

  project.identity.name = opts.name || '';
  project.identity.description = opts.description || '';
  project.identity.tags = opts.tags || [];

  // Start with default stances
  project.stances = JSON.parse(JSON.stringify(DEFAULT_STANCES));

  // Inherit additional stances from vestibular if present
  if (vestibular && Array.isArray(vestibular.stances)) {
    for (const stance of vestibular.stances) {
      const exists = project.stances.some(s => s.name === stance.name);
      if (!exists) {
        project.stances.push(JSON.parse(JSON.stringify(stance)));
      }
    }
  }

  return project;
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

function cmdProjectLoad(cwd) {
  const result = loadProjectFile(cwd);
  process.stdout.write(JSON.stringify(result));
}

function cmdProjectScaffold(cwd, optsJson) {
  const opts = JSON.parse(optsJson || '{}');
  const vestibular = loadVestibularSafe();
  const data = scaffoldProjectFile(opts, vestibular);
  const filePath = saveProjectFile(cwd, data);
  process.stdout.write(JSON.stringify({ path: filePath, valid: validate(data).length === 0 }));
}

function cmdProjectValidate(cwd) {
  const result = loadProjectFile(cwd);
  const output = {
    found: result.found,
    valid: result.errors.length === 0,
    errors: result.errors,
  };
  process.stdout.write(JSON.stringify(output));
}

function loadVestibularSafe() {
  try {
    const vestibularPath = path.join(require('os').homedir(), '.vestibular');
    if (!fs.existsSync(vestibularPath)) return null;
    const raw = fs.readFileSync(vestibularPath, 'utf-8');
    return parseYaml(raw);
  } catch {
    return null;
  }
}

module.exports = {
  DEFAULT_PROJECT_FILE,
  DEFAULT_STANCES,
  validate,
  findProjectFile,
  loadProjectFile,
  saveProjectFile,
  scaffoldProjectFile,
  cmdProjectLoad,
  cmdProjectScaffold,
  cmdProjectValidate,
};
