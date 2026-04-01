'use strict';

const { describe, test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { createTempDir, cleanup } = require('./helpers.cjs');
const { scaffoldProjectFile, saveProjectFile, loadProjectFile } = require('../eclusa/bin/lib/project-file.cjs');
const {
  stageCoherence,
  stageFormalize,
  stageDerive,
  stageGenerate,
  commitMatches,
  sourceToModuleName,
  checkConstraints,
} = require('../eclusa/bin/lib/pipeline.cjs');

describe('pipeline stage 2: match — commit results', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-pipeline-');
    const project = scaffoldProjectFile({ name: 'test-project', tags: ['test'] }, null);
    saveProjectFile(tmpDir, project);
  });

  afterEach(() => { cleanup(tmpDir); });

  test('writes matched sources to project file', () => {
    const matches = [
      {
        concept: 'user authentication',
        matches: [
          { score: 0.8, entity_name: 'User', source_origin: 'qdrant:auth/api', source_format: 'openapi', entry_type: 'entity' },
          { score: 0.6, entity_name: 'Session', source_origin: 'qdrant:auth/api', source_format: 'openapi', entry_type: 'entity' },
        ],
      },
      {
        concept: 'billing',
        matches: [
          { score: 0.7, entity_name: 'Invoice', source_origin: 'qdrant:stripe/billing', source_format: 'openapi', entry_type: 'entity' },
        ],
      },
    ];

    const result = commitMatches(tmpDir, matches);
    assert.strictEqual(result.sources_matched, 2);

    const loaded = loadProjectFile(tmpDir);
    assert.strictEqual(loaded.data.sources.matched.length, 2);
    assert.ok(loaded.data.sources.matched.some(s => s.origin === 'qdrant:auth/api'));
    assert.ok(loaded.data.sources.matched.some(s => s.origin === 'qdrant:stripe/billing'));
  });

  test('skips low-confidence matches', () => {
    const matches = [
      {
        concept: 'something obscure',
        matches: [
          { score: 0.1, entity_name: 'Unrelated', source_origin: 'noise', source_format: 'openapi', entry_type: 'entity' },
        ],
      },
    ];

    const result = commitMatches(tmpDir, matches);
    assert.strictEqual(result.sources_matched, 0);
  });

  test('returns error when no project file', () => {
    const emptyDir = createTempDir('eclusa-empty-');
    const result = commitMatches(emptyDir, []);
    assert.ok(result.error);
    cleanup(emptyDir);
  });
});

describe('pipeline stage 3: coherence', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-cohere-');
    const project = scaffoldProjectFile({ name: 'test' }, null);
    project.sources.matched = [
      { origin: 'qdrant:auth/api', entities: ['User', 'Session'] },
      { origin: 'qdrant:stripe/billing', entities: ['Customer', 'Invoice'] },
    ];
    saveProjectFile(tmpDir, project);
  });

  afterEach(() => { cleanup(tmpDir); });

  test('produces coherence check context', () => {
    const result = stageCoherence(tmpDir);
    assert.strictEqual(result.stage, 'coherence');
    assert.strictEqual(result.matched_sources.length, 2);
    assert.ok(Array.isArray(result.checks));
    assert.ok(result.checks.length > 0);
    assert.ok(result.instruction);
  });

  test('returns error with no sources', () => {
    const emptyDir = createTempDir('eclusa-empty-');
    const project = scaffoldProjectFile({ name: 'test' }, null);
    saveProjectFile(emptyDir, project);
    const result = stageCoherence(emptyDir);
    assert.ok(result.error);
    cleanup(emptyDir);
  });
});

describe('pipeline stage 4: formalize', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-formal-');
    const project = scaffoldProjectFile({ name: 'test' }, null);
    project.sources.matched = [
      { origin: 'qdrant:stripe/billing', format: 'openapi', entities: ['Customer', 'Subscription'] },
    ];
    saveProjectFile(tmpDir, project);
  });

  afterEach(() => { cleanup(tmpDir); });

  test('generates Haskell module scaffolds', () => {
    const result = stageFormalize(tmpDir);
    assert.strictEqual(result.stage, 'formalize');
    assert.ok(result.modules.length > 0);
    assert.ok(result.modules[0].content.includes('module Sources.'));
    assert.ok(result.modules[0].content.includes('data Customer'));
    assert.ok(result.constraints_scaffold.includes('module Constraints'));
  });

  test('check-constraints reports missing file', () => {
    const result = checkConstraints(tmpDir);
    assert.strictEqual(result.compiled, false);
    assert.ok(result.error);
  });
});

describe('pipeline stage 5: derive', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-derive-');
    const project = scaffoldProjectFile({ name: 'test' }, null);
    project.sources.matched = [
      { origin: 'qdrant:stripe/billing', entities: ['Customer'] },
    ];
    saveProjectFile(tmpDir, project);
  });

  afterEach(() => { cleanup(tmpDir); });

  test('produces derive context with instructions', () => {
    const result = stageDerive(tmpDir);
    assert.strictEqual(result.stage, 'derive');
    assert.ok(Array.isArray(result.instruction));
    assert.ok(result.instruction.length > 0);
    assert.ok(result.matched_sources.length > 0);
  });
});

describe('pipeline stage 6: generate', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-gen-');
    const project = scaffoldProjectFile({ name: 'test' }, null);
    project.sources.matched = [
      { origin: 'qdrant:stripe/billing', entities: ['Customer'] },
    ];
    saveProjectFile(tmpDir, project);
  });

  afterEach(() => { cleanup(tmpDir); });

  test('produces generate context', () => {
    const result = stageGenerate(tmpDir);
    assert.strictEqual(result.stage, 'generate');
    assert.ok(Array.isArray(result.instruction));
    assert.ok(result.matched_sources.length > 0);
  });
});

describe('pipeline helpers', () => {
  test('converts source origins to module names', () => {
    assert.strictEqual(sourceToModuleName('qdrant:stripe/billing'), 'StripeBilling');
    assert.strictEqual(sourceToModuleName('local:schema.prisma'), 'SchemaPrisma');
    assert.strictEqual(sourceToModuleName('github:acme/api/v2'), 'AcmeApiV2');
  });
});
