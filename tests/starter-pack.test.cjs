'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const { loadStarterPack } = require('../eclusa/bin/lib/starter-pack.cjs');

describe('starter pack manifest', () => {
  test('loads starter-pack.json', () => {
    const pack = loadStarterPack();
    assert.ok(pack.sources);
    assert.ok(pack.sources.length >= 20, `Expected 20+ sources, got ${pack.sources.length}`);
  });

  test('each source has required fields', () => {
    const pack = loadStarterPack();
    for (const source of pack.sources) {
      assert.ok(source.industry, `Source missing industry: ${JSON.stringify(source)}`);
      assert.ok(source.name, `Source missing name: ${JSON.stringify(source)}`);
      assert.ok(source.repo, `Source missing repo: ${JSON.stringify(source)}`);
      assert.ok(source.path, `Source missing path: ${JSON.stringify(source)}`);
      assert.ok(source.format, `Source missing format: ${JSON.stringify(source)}`);
    }
  });

  test('covers multiple industries', () => {
    const pack = loadStarterPack();
    const industries = new Set(pack.sources.map(s => s.industry));
    assert.ok(industries.size >= 10, `Expected 10+ industries, got ${industries.size}: ${[...industries].join(', ')}`);
  });

  test('includes key industries', () => {
    const pack = loadStarterPack();
    const industries = new Set(pack.sources.map(s => s.industry));
    for (const expected of ['payments', 'healthcare', 'identity', 'cloud', 'observability']) {
      assert.ok(industries.has(expected), `Missing industry: ${expected}`);
    }
  });

  test('repos follow owner/name format', () => {
    const pack = loadStarterPack();
    for (const source of pack.sources) {
      assert.ok(/^[\w-]+\/[\w.-]+$/.test(source.repo),
        `Invalid repo format: ${source.repo} (expected owner/name)`);
    }
  });
});
