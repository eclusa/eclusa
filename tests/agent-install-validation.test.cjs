/**
 * Eclusa Agent Installation Validation Tests (#1371)
 *
 * Validates that Eclusa detects missing or incomplete agent installations and
 * surfaces warnings through init commands and health checks. When agents are
 * not installed, Task(subagent_type="eclusa-*") silently falls back to
 * general-purpose, losing specialized instructions.
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { runEclusaTools, createTempProject, cleanup } = require('./helpers.cjs');

const AGENTS_DIR_NAME = 'agents';
const MODEL_PROFILES = require('../eclusa/bin/lib/model-profiles.cjs').MODEL_PROFILES;
const EXPECTED_AGENTS = Object.keys(MODEL_PROFILES);

/**
 * Create a fake Eclusa install directory structure that mirrors what the installer
 * produces. eclusa-tools.cjs lives at <configDir>/eclusa/bin/eclusa-tools.cjs,
 * so the agents dir is at <configDir>/agents/.
 *
 * We use --cwd to point at the project, and ECLUSA_INSTALL_DIR env to override
 * the agents directory location for testing.
 */
function createAgentsDir(configDir, agentNames = []) {
  const agentsDir = path.join(configDir, AGENTS_DIR_NAME);
  fs.mkdirSync(agentsDir, { recursive: true });
  for (const name of agentNames) {
    fs.writeFileSync(
      path.join(agentsDir, `${name}.md`),
      `---\nname: ${name}\ndescription: Test agent\ntools: Read, Bash\ncolor: cyan\n---\nAgent content.\n`
    );
  }
  return agentsDir;
}

// ─── Init command agent validation ──────────────────────────────────────────

describe('init commands: agents_installed field (#1371)', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('init execute-phase includes agents_installed=true when agents exist', () => {
    // Create phase dir for init
    const phaseDir = path.join(tmpDir, '.eclusa', 'phases', '01-setup');
    fs.mkdirSync(phaseDir, { recursive: true });

    // Create agents dir as sibling of eclusa/ (the installed layout)
    // eclusa-tools.cjs resolves agents from ECLUSA_INSTALL_DIR or __dirname/../../agents
    const eclusaInstallDir = path.resolve(__dirname, '..', 'eclusa', 'bin');
    const configDir = path.resolve(eclusaInstallDir, '..', '..');
    const agentsDir = path.join(configDir, 'agents');

    // Agents already exist in the repo root /agents/ dir which is sibling to eclusa/
    const result = runEclusaTools('init execute-phase 1 --raw', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(typeof output.agents_installed, 'boolean',
      'init execute-phase must include agents_installed field');
    // The repo has agents/ dir with all eclusa-*.md files, so this should be true
    assert.strictEqual(output.agents_installed, true,
      'agents_installed should be true when agents directory has eclusa-*.md files');
  });

  test('init plan-phase includes agents_installed=true when agents exist', () => {
    const phaseDir = path.join(tmpDir, '.eclusa', 'phases', '01-setup');
    fs.mkdirSync(phaseDir, { recursive: true });

    const result = runEclusaTools('init plan-phase 1 --raw', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(typeof output.agents_installed, 'boolean',
      'init plan-phase must include agents_installed field');
    assert.strictEqual(output.agents_installed, true);
  });

  test('init execute-phase includes missing_agents list when agents are missing', () => {
    const phaseDir = path.join(tmpDir, '.eclusa', 'phases', '01-setup');
    fs.mkdirSync(phaseDir, { recursive: true });

    const result = runEclusaTools('init execute-phase 1 --raw', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.ok(Array.isArray(output.missing_agents),
      'init execute-phase must include missing_agents array');
  });

  test('init quick includes agents_installed field', () => {
    const result = runEclusaTools(['init', 'quick', 'test description', '--raw'], tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(typeof output.agents_installed, 'boolean',
      'init quick must include agents_installed field');
  });
});

// ─── Health check: agent installation ───────────────────────────────────────

describe('validate health: agent installation check W010 (#1371)', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    // Write minimal project files so health check doesn't fail on E001-E005
    fs.writeFileSync(
      path.join(tmpDir, '.eclusa', 'PROJECT.md'),
      '# Project\n\n## What This Is\nTest\n\n## Core Value\nTest\n\n## Requirements\nTest\n'
    );
    fs.writeFileSync(
      path.join(tmpDir, '.eclusa', 'ROADMAP.md'),
      '# Roadmap\n\n### Phase 1: Setup\n'
    );
    fs.writeFileSync(
      path.join(tmpDir, '.eclusa', 'STATE.md'),
      '# Session State\n\n## Current Position\n\nPhase: 1\n'
    );
    fs.writeFileSync(
      path.join(tmpDir, '.eclusa', 'config.json'),
      JSON.stringify({
        model_profile: 'balanced',
        commit_docs: true,
        workflow: { nyquist_validation: true },
      }, null, 2)
    );
    fs.mkdirSync(path.join(tmpDir, '.eclusa', 'phases', '01-setup'), { recursive: true });
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('health check reports healthy when agents are installed (repo layout)', () => {
    // In the repo, agents/ exists as a sibling of eclusa/, so the
    // health check should find them via the eclusa-tools.cjs path resolution
    const result = runEclusaTools('validate health --raw', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    // Should not have W010 warning about missing agents
    const w010 = (output.warnings || []).find(w => w.code === 'W010');
    assert.ok(!w010, 'Should not warn about missing agents when agents/ dir exists with files');
  });
});

// ─── validate agents subcommand ─────────────────────────────────────────────

describe('validate agents subcommand (#1371)', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('validate agents returns status with agent list', () => {
    const result = runEclusaTools('validate agents --raw', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.ok('agents_dir' in output, 'Must include agents_dir path');
    assert.ok('installed' in output, 'Must include installed array');
    assert.ok('missing' in output, 'Must include missing array');
    assert.ok('agents_found' in output, 'Must include agents_found boolean');
  });

  test('validate agents lists all expected agent types', () => {
    const result = runEclusaTools('validate agents --raw', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    // The expected agents come from MODEL_PROFILES keys
    assert.ok(output.expected.length > 0, 'Must have expected agents');
  });
});
