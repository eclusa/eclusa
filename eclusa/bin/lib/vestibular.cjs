'use strict';

/**
 * Vestibular — the human orientation file.
 *
 * Lives at ~/.vestibular. Travels with the human, not the project.
 * Describes who the human is, how they work, what they care about.
 * Projects inherit stances from the vestibular.
 *
 * Environment discovery focuses on harness UX capabilities
 * (multi-select support, TUI availability, notification channels).
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { parseYaml, dumpYaml } = require('./yaml.cjs');

// ─── Schema Defaults ────────────────────────────────────────────────────────

const DEFAULT_VESTIBULAR = {
  version: 1,

  register: {
    name: '',
    role: '',
    context: '',
  },

  autonomy: {
    level: 'collaborative',
    gates: {
      confirm_scope: true,
      confirm_plan: true,
      confirm_destructive: true,
      confirm_external: true,
    },
    auto_advance: false,
  },

  collaboration: {
    style: 'iterative',
    feedback_mode: 'inline',
    decision_model: 'human-final',
  },

  style: {
    communication: 'concise',
    code_comments: 'minimal',
    commit_messages: 'conventional',
  },

  stances: [],

  escalation: {
    channels: [],
    on_ambiguity: 'ask',
    on_blocked: 'notify',
  },

  environment: {
    harness: 'auto',
    multi_select: true,
    tui: false,
    notifications: [],
  },
};

// ─── Validation ─────────────────────────────────────────────────────────────

const VALID_AUTONOMY_LEVELS = ['autonomous', 'collaborative', 'supervised'];
const VALID_COLLABORATION_STYLES = ['iterative', 'batch', 'async'];
const VALID_FEEDBACK_MODES = ['inline', 'summary', 'minimal'];
const VALID_DECISION_MODELS = ['human-final', 'ai-suggest', 'ai-decide'];
const VALID_COMMUNICATION_STYLES = ['concise', 'detailed', 'verbose'];
const VALID_ESCALATION_ACTIONS = ['ask', 'notify', 'defer', 'block'];

function validate(vestibular) {
  const errors = [];

  if (!vestibular || typeof vestibular !== 'object') {
    return [{ path: '', message: 'Vestibular must be a YAML object' }];
  }

  if (vestibular.version !== 1) {
    errors.push({ path: 'version', message: `Expected version 1, got ${vestibular.version}` });
  }

  // register
  if (vestibular.register && typeof vestibular.register !== 'object') {
    errors.push({ path: 'register', message: 'register must be an object' });
  }

  // autonomy
  if (vestibular.autonomy) {
    if (vestibular.autonomy.level && !VALID_AUTONOMY_LEVELS.includes(vestibular.autonomy.level)) {
      errors.push({ path: 'autonomy.level', message: `Must be one of: ${VALID_AUTONOMY_LEVELS.join(', ')}` });
    }
  }

  // collaboration
  if (vestibular.collaboration) {
    if (vestibular.collaboration.style && !VALID_COLLABORATION_STYLES.includes(vestibular.collaboration.style)) {
      errors.push({ path: 'collaboration.style', message: `Must be one of: ${VALID_COLLABORATION_STYLES.join(', ')}` });
    }
    if (vestibular.collaboration.feedback_mode && !VALID_FEEDBACK_MODES.includes(vestibular.collaboration.feedback_mode)) {
      errors.push({ path: 'collaboration.feedback_mode', message: `Must be one of: ${VALID_FEEDBACK_MODES.join(', ')}` });
    }
    if (vestibular.collaboration.decision_model && !VALID_DECISION_MODELS.includes(vestibular.collaboration.decision_model)) {
      errors.push({ path: 'collaboration.decision_model', message: `Must be one of: ${VALID_DECISION_MODELS.join(', ')}` });
    }
  }

  // style
  if (vestibular.style) {
    if (vestibular.style.communication && !VALID_COMMUNICATION_STYLES.includes(vestibular.style.communication)) {
      errors.push({ path: 'style.communication', message: `Must be one of: ${VALID_COMMUNICATION_STYLES.join(', ')}` });
    }
  }

  // stances
  if (vestibular.stances) {
    if (!Array.isArray(vestibular.stances)) {
      errors.push({ path: 'stances', message: 'stances must be an array' });
    } else {
      vestibular.stances.forEach((s, idx) => {
        if (!s.name) errors.push({ path: `stances[${idx}].name`, message: 'Stance must have a name' });
        if (!s.rule) errors.push({ path: `stances[${idx}].rule`, message: 'Stance must have a rule' });
      });
    }
  }

  // escalation
  if (vestibular.escalation) {
    if (vestibular.escalation.on_ambiguity && !VALID_ESCALATION_ACTIONS.includes(vestibular.escalation.on_ambiguity)) {
      errors.push({ path: 'escalation.on_ambiguity', message: `Must be one of: ${VALID_ESCALATION_ACTIONS.join(', ')}` });
    }
    if (vestibular.escalation.on_blocked && !VALID_ESCALATION_ACTIONS.includes(vestibular.escalation.on_blocked)) {
      errors.push({ path: 'escalation.on_blocked', message: `Must be one of: ${VALID_ESCALATION_ACTIONS.join(', ')}` });
    }
  }

  return errors;
}

// ─── Load / Save ────────────────────────────────────────────────────────────

function vestibularPath() {
  return path.join(os.homedir(), '.vestibular');
}

function loadVestibular() {
  const filePath = vestibularPath();
  if (!fs.existsSync(filePath)) {
    return { found: false, path: filePath, data: null, errors: ['No ~/.vestibular file found'] };
  }

  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    const data = parseYaml(raw);
    const errors = validate(data);
    return { found: true, path: filePath, data, errors };
  } catch (err) {
    return { found: true, path: filePath, data: null, errors: [`Parse error: ${err.message}`] };
  }
}

function saveVestibular(data) {
  const filePath = vestibularPath();
  const header = '# ~/.vestibular — human orientation for eclusa\n# This file travels with you, not the project.\n# https://eclusa.dev\n---\n';
  const yaml = dumpYaml(data);
  fs.writeFileSync(filePath, header + yaml + '\n', 'utf-8');
  return filePath;
}

/**
 * Scaffold a new vestibular from interactive input.
 * @param {object} opts - { name, role, context, autonomy_level, communication_style }
 * @returns {object} The scaffolded vestibular data
 */
function scaffoldVestibular(opts) {
  const v = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));

  if (opts.name) v.register.name = opts.name;
  if (opts.role) v.register.role = opts.role;
  if (opts.context) v.register.context = opts.context;
  if (opts.autonomy_level) v.autonomy.level = opts.autonomy_level;
  if (opts.communication_style) v.style.communication = opts.communication_style;

  // Add notification channels if provided
  if (opts.notification_script) {
    v.escalation.channels.push({
      type: 'script',
      path: opts.notification_script,
    });
    v.environment.notifications.push(opts.notification_script);
  }

  return v;
}

/**
 * Deep merge vestibular with project-level overrides.
 * Vestibular provides defaults; project stances can tighten but not loosen.
 */
function mergeWithProject(vestibular, projectStances) {
  const result = JSON.parse(JSON.stringify(vestibular || DEFAULT_VESTIBULAR));

  if (projectStances && Array.isArray(projectStances)) {
    if (!result.stances) result.stances = [];
    for (const stance of projectStances) {
      const existing = result.stances.findIndex(s => s.name === stance.name);
      if (existing >= 0) {
        // Project stance overrides vestibular stance (tightening)
        result.stances[existing] = { ...result.stances[existing], ...stance };
      } else {
        result.stances.push(JSON.parse(JSON.stringify(stance)));
      }
    }
  }

  return result;
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

function cmdVestibularLoad() {
  const result = loadVestibular();
  process.stdout.write(JSON.stringify(result));
}

function cmdVestibularScaffold(optsJson) {
  const opts = JSON.parse(optsJson || '{}');
  const data = scaffoldVestibular(opts);
  const filePath = saveVestibular(data);
  process.stdout.write(JSON.stringify({ path: filePath, valid: validate(data).length === 0 }));
}

function cmdVestibularValidate() {
  const result = loadVestibular();
  const output = {
    found: result.found,
    valid: result.errors.length === 0,
    errors: result.errors,
  };
  process.stdout.write(JSON.stringify(output));
}

module.exports = {
  DEFAULT_VESTIBULAR,
  VALID_AUTONOMY_LEVELS,
  VALID_COLLABORATION_STYLES,
  VALID_DECISION_MODELS,
  validate,
  vestibularPath,
  loadVestibular,
  saveVestibular,
  scaffoldVestibular,
  mergeWithProject,
  cmdVestibularLoad,
  cmdVestibularScaffold,
  cmdVestibularValidate,
};
