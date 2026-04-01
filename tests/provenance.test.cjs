'use strict';

const { describe, test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { createTempDir, cleanup } = require('./helpers.cjs');

const {
  hashFile,
  hashDirectory,
  computeProvenance,
  formatTrailers,
  parseTrailers,
  verifyProvenance,
  diagnose,
} = require('../eclusa/bin/lib/provenance.cjs');

describe('provenance hashing', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-prov-');
  });

  afterEach(() => { cleanup(tmpDir); });

  test('hashes a file deterministically', () => {
    const file = path.join(tmpDir, 'test.txt');
    fs.writeFileSync(file, 'hello world');
    const hash1 = hashFile(file);
    const hash2 = hashFile(file);
    assert.strictEqual(hash1, hash2);
    assert.strictEqual(hash1.length, 16); // 16 hex chars
  });

  test('different content produces different hashes', () => {
    const file1 = path.join(tmpDir, 'a.txt');
    const file2 = path.join(tmpDir, 'b.txt');
    fs.writeFileSync(file1, 'hello');
    fs.writeFileSync(file2, 'world');
    assert.notStrictEqual(hashFile(file1), hashFile(file2));
  });

  test('returns null for missing file', () => {
    assert.strictEqual(hashFile(path.join(tmpDir, 'missing.txt')), null);
  });

  test('hashes a directory deterministically', () => {
    const dir = path.join(tmpDir, 'src');
    fs.mkdirSync(dir);
    fs.writeFileSync(path.join(dir, 'a.txt'), 'aaa');
    fs.writeFileSync(path.join(dir, 'b.txt'), 'bbb');
    const hash1 = hashDirectory(dir);
    const hash2 = hashDirectory(dir);
    assert.strictEqual(hash1, hash2);
  });

  test('returns null for missing directory', () => {
    assert.strictEqual(hashDirectory(path.join(tmpDir, 'missing')), null);
  });
});

describe('provenance trailers', () => {
  test('formats trailers from provenance', () => {
    const trailers = formatTrailers({
      sources_hash: 'abc123def456',
      constraints_hash: 'fedcba987654',
      test_suite_hash: null,
      project_hash: '1122334455667788',
    });
    assert.ok(trailers.includes('Eclusa-Sources-Hash: abc123def456'));
    assert.ok(trailers.includes('Eclusa-Constraints-Hash: fedcba987654'));
    assert.ok(trailers.includes('Eclusa-Project-Hash: 1122334455667788'));
    assert.ok(!trailers.includes('Test-Suite')); // null should be skipped
  });

  test('parses trailers from commit message', () => {
    const msg = `feat: add user model

Implements the user entity with auth.

Eclusa-Sources-Hash: abc123def456
Eclusa-Constraints-Hash: fedcba987654
Eclusa-Project-Hash: 1122334455667788`;

    const parsed = parseTrailers(msg);
    assert.strictEqual(parsed.sources_hash, 'abc123def456');
    assert.strictEqual(parsed.constraints_hash, 'fedcba987654');
    assert.strictEqual(parsed.project_hash, '1122334455667788');
  });

  test('returns empty object for no trailers', () => {
    const parsed = parseTrailers('just a normal commit message');
    assert.deepStrictEqual(parsed, {});
  });
});

describe('provenance computation', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-provcomp-');
  });

  afterEach(() => { cleanup(tmpDir); });

  test('computes provenance for a project', () => {
    // Create project file
    fs.writeFileSync(path.join(tmpDir, 'project.eclusa'), 'version: 5\nsources:\n  matched: []');

    const prov = computeProvenance(tmpDir);
    assert.ok(prov.project_hash);
    assert.ok(prov.computed_at);
    assert.strictEqual(prov.constraints_hash, null); // No constraints yet
    assert.strictEqual(prov.test_suite_hash, null); // No tests yet
  });

  test('project hash changes when file changes', () => {
    const file = path.join(tmpDir, 'project.eclusa');
    fs.writeFileSync(file, 'version: 5\nsources:\n  matched: []');
    const hash1 = computeProvenance(tmpDir).project_hash;

    fs.writeFileSync(file, 'version: 5\nsources:\n  matched:\n    - origin: test');
    const hash2 = computeProvenance(tmpDir).project_hash;

    assert.notStrictEqual(hash1, hash2);
  });
});

describe('provenance verification', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-provver-');
    execSync('git init', { cwd: tmpDir, stdio: 'pipe' });
    execSync('git config user.email "test@test.com"', { cwd: tmpDir, stdio: 'pipe' });
    execSync('git config user.name "Test"', { cwd: tmpDir, stdio: 'pipe' });
    execSync('git config commit.gpgsign false', { cwd: tmpDir, stdio: 'pipe' });
    fs.writeFileSync(path.join(tmpDir, 'init.txt'), 'init');
    execSync('git add -A && git commit -m "init"', { cwd: tmpDir, stdio: 'pipe' });
  });

  afterEach(() => { cleanup(tmpDir); });

  test('reports no trailers when chain not started', () => {
    const result = verifyProvenance(tmpDir);
    assert.ok(result.verified);
    assert.ok(result.issues.some(i => i.type === 'info'));
  });

  test('detects changed hashes after provenance commit', () => {
    // Create project and commit with trailers
    fs.writeFileSync(path.join(tmpDir, 'project.eclusa'), 'version: 5\nsources:\n  matched: []');
    const prov = computeProvenance(tmpDir);
    const trailers = formatTrailers(prov);
    execSync('git add -A', { cwd: tmpDir, stdio: 'pipe' });
    execSync(`git commit -m "feat: initial\n\n${trailers}"`, { cwd: tmpDir, stdio: 'pipe' });

    // Modify the project file
    fs.writeFileSync(path.join(tmpDir, 'project.eclusa'), 'version: 5\nsources:\n  matched:\n    - origin: changed');
    const result = verifyProvenance(tmpDir);
    assert.ok(result.issues.some(i => i.type === 'warning'));
  });
});

describe('diagnose', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempDir('eclusa-diag-');
    fs.mkdirSync(path.join(tmpDir, '.eclusa'), { recursive: true });
    execSync('git init', { cwd: tmpDir, stdio: 'pipe' });
    execSync('git config user.email "test@test.com"', { cwd: tmpDir, stdio: 'pipe' });
    execSync('git config user.name "Test"', { cwd: tmpDir, stdio: 'pipe' });
    execSync('git config commit.gpgsign false', { cwd: tmpDir, stdio: 'pipe' });
    fs.writeFileSync(path.join(tmpDir, 'init.txt'), 'init');
    execSync('git add -A && git commit -m "init"', { cwd: tmpDir, stdio: 'pipe' });
  });

  afterEach(() => { cleanup(tmpDir); });

  test('reports diagnostic overview', () => {
    const result = diagnose(tmpDir);
    assert.ok('provenance' in result);
    assert.ok('project_file' in result);
    assert.ok('constraints' in result);
    assert.ok('pipeline_state' in result);
    assert.strictEqual(result.project_file.exists, false);
    assert.strictEqual(result.constraints.exists, false);
  });
});
