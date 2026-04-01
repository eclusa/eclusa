'use strict';

const { describe, test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { runEclusaTools, createTempDir, cleanup } = require('./helpers.cjs');

const {
  DEFAULT_PROJECT_FILE,
  DEFAULT_STANCES,
  validate,
  findProjectFile,
  loadProjectFile,
  saveProjectFile,
  scaffoldProjectFile,
} = require('../eclusa/bin/lib/project-file.cjs');

describe('project.eclusa schema defaults', () => {
  test('has version 5', () => {
    assert.strictEqual(DEFAULT_PROJECT_FILE.version, 5);
  });

  test('has identity section', () => {
    assert.ok(DEFAULT_PROJECT_FILE.identity);
    assert.strictEqual(typeof DEFAULT_PROJECT_FILE.identity.name, 'string');
    assert.ok(Array.isArray(DEFAULT_PROJECT_FILE.identity.tags));
  });

  test('has sources section', () => {
    assert.ok(Array.isArray(DEFAULT_PROJECT_FILE.sources.matched));
    assert.ok(Array.isArray(DEFAULT_PROJECT_FILE.sources.novel));
  });

  test('has agent section with stage bindings', () => {
    const bindings = DEFAULT_PROJECT_FILE.agents.stage_bindings;
    assert.ok(bindings.refine);
    assert.ok(bindings.coherence);
    assert.ok(bindings.formalize);
    assert.ok(bindings.derive);
    assert.ok(bindings.generate);
  });

  test('default stances include required three', () => {
    const names = DEFAULT_STANCES.map(s => s.name);
    assert.ok(names.includes('Reviewed Commits'));
    assert.ok(names.includes('Model Provenance'));
    assert.ok(names.includes('Conservative Default'));
  });
});

describe('project file validation', () => {
  test('valid project file passes', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));
    data.identity.name = 'test-project';
    const errors = validate(data);
    assert.strictEqual(errors.length, 0);
  });

  test('rejects missing identity', () => {
    const data = { version: 5 };
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'identity'));
  });

  test('rejects empty identity name', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));
    data.identity.name = '';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'identity.name'));
  });

  test('rejects wrong version', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));
    data.identity.name = 'test';
    data.version = 4;
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'version'));
  });

  test('rejects invalid governance level', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));
    data.identity.name = 'test';
    data.provenance.governance_level = 'maximum';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'provenance.governance_level'));
  });

  test('rejects invalid stage name', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));
    data.identity.name = 'test';
    data.agents.stage_bindings.compile = 'fast';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path.includes('compile')));
  });

  test('validates stance structure', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_PROJECT_FILE));
    data.identity.name = 'test';
    data.stances = [{ name: 'Test' }]; // missing rule
    const errors = validate(data);
    assert.ok(errors.some(e => e.path.includes('stances')));
  });
});

describe('project file scaffold', () => {
  test('creates project with given identity', () => {
    const result = scaffoldProjectFile({
      name: 'mixdown',
      description: 'Internal platform for music company',
      tags: ['payments', 'music', 'internal'],
    }, null);
    assert.strictEqual(result.version, 5);
    assert.strictEqual(result.identity.name, 'mixdown');
    assert.strictEqual(result.identity.description, 'Internal platform for music company');
    assert.deepStrictEqual(result.identity.tags, ['payments', 'music', 'internal']);
  });

  test('includes default stances', () => {
    const result = scaffoldProjectFile({ name: 'test' }, null);
    assert.strictEqual(result.stances.length, 3);
    const names = result.stances.map(s => s.name);
    assert.ok(names.includes('Reviewed Commits'));
    assert.ok(names.includes('Model Provenance'));
    assert.ok(names.includes('Conservative Default'));
  });

  test('inherits vestibular stances without duplicating', () => {
    const vestibular = {
      stances: [
        { name: 'No Force Push', rule: 'Never force push to main' },
        { name: 'Reviewed Commits', rule: 'Custom override' }, // same name as default
      ],
    };
    const result = scaffoldProjectFile({ name: 'test' }, vestibular);
    // Should have 3 defaults + 1 new (No Force Push), not duplicate Reviewed Commits
    assert.strictEqual(result.stances.length, 4);
    const names = result.stances.map(s => s.name);
    assert.ok(names.includes('No Force Push'));
    // Reviewed Commits should appear once (the default, not overridden by vestibular)
    assert.strictEqual(names.filter(n => n === 'Reviewed Commits').length, 1);
  });
});

describe('project file load/save', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-project-test-');
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('finds project.eclusa file', () => {
    const data = scaffoldProjectFile({ name: 'test-find' }, null);
    saveProjectFile(tmpDir, data);
    const found = findProjectFile(tmpDir);
    assert.ok(found);
    assert.ok(found.endsWith('project.eclusa'));
  });

  test('returns not found when missing', () => {
    const found = findProjectFile(tmpDir);
    assert.strictEqual(found, null);
  });

  test('roundtrips project file through save/load', () => {
    const data = scaffoldProjectFile({
      name: 'roundtrip-test',
      description: 'Testing save and load',
      tags: ['test'],
    }, null);
    saveProjectFile(tmpDir, data);
    const loaded = loadProjectFile(tmpDir);
    assert.ok(loaded.found);
    assert.strictEqual(loaded.errors.length, 0, `Validation errors: ${JSON.stringify(loaded.errors)}`);
    assert.strictEqual(loaded.data.version, 5);
    assert.strictEqual(loaded.data.identity.name, 'roundtrip-test');
    assert.strictEqual(loaded.data.identity.description, 'Testing save and load');
    assert.deepStrictEqual(loaded.data.identity.tags, ['test']);
  });

  test('saved file has YAML header comment', () => {
    const data = scaffoldProjectFile({ name: 'test' }, null);
    saveProjectFile(tmpDir, data);
    const content = fs.readFileSync(path.join(tmpDir, 'project.eclusa'), 'utf-8');
    assert.ok(content.startsWith('# project.eclusa'));
  });
});

describe('project-file CLI commands', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-project-cli-');
    fs.mkdirSync(path.join(tmpDir, '.eclusa'), { recursive: true });
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('scaffold command creates project.eclusa', () => {
    const result = runEclusaTools(
      ['project-file', 'scaffold', '{"name":"cli-test","description":"Test project","tags":["test"]}'],
      tmpDir
    );
    assert.ok(result.success, `Failed: ${result.error}`);
    const output = JSON.parse(result.output);
    assert.ok(output.path.endsWith('project.eclusa'));
    assert.ok(output.valid);
    assert.ok(fs.existsSync(path.join(tmpDir, 'project.eclusa')));
  });

  test('load command returns project data', () => {
    // First scaffold
    runEclusaTools(
      ['project-file', 'scaffold', '{"name":"load-test"}'],
      tmpDir
    );
    const result = runEclusaTools(['project-file', 'load'], tmpDir);
    assert.ok(result.success, `Failed: ${result.error}`);
    const output = JSON.parse(result.output);
    assert.ok(output.found);
    assert.strictEqual(output.data.identity.name, 'load-test');
  });

  test('validate command reports valid file', () => {
    runEclusaTools(
      ['project-file', 'scaffold', '{"name":"valid-test"}'],
      tmpDir
    );
    const result = runEclusaTools(['project-file', 'validate'], tmpDir);
    assert.ok(result.success, `Failed: ${result.error}`);
    const output = JSON.parse(result.output);
    assert.ok(output.valid);
    assert.strictEqual(output.errors.length, 0);
  });

  test('validate command reports missing file', () => {
    const result = runEclusaTools(['project-file', 'validate'], tmpDir);
    assert.ok(result.success, `Failed: ${result.error}`);
    const output = JSON.parse(result.output);
    assert.ok(!output.found);
    assert.ok(!output.valid);
  });
});
