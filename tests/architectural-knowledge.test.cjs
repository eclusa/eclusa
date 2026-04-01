'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');

const {
  curatedDecisions,
} = require('../eclusa/bin/lib/architectural-knowledge.cjs');

const { irToPoints, validateIR, VALID_NOVELTY_LEVELS, VALID_SPECTRUM_LEVELS } = require('../eclusa/bin/lib/ir.cjs');

describe('curated architectural decisions', () => {
  const ir = curatedDecisions();

  test('produces valid IR', () => {
    const errors = validateIR(ir);
    assert.deepStrictEqual(errors, []);
  });

  test('has decisions', () => {
    assert.ok(ir.decisions.length >= 15, `Expected 15+ decisions, got ${ir.decisions.length}`);
  });

  test('has behaviors (best practices)', () => {
    assert.ok(ir.behaviors.length >= 5, `Expected 5+ behaviors, got ${ir.behaviors.length}`);
  });

  test('every decision has required fields', () => {
    for (const d of ir.decisions) {
      assert.ok(d.given, `Decision missing given: ${JSON.stringify(d)}`);
      assert.ok(d.prefer, `Decision missing prefer: ${JSON.stringify(d)}`);
      assert.ok(d.because, `Decision missing because: ${JSON.stringify(d)}`);
      assert.ok(d.tags.length > 0, `Decision missing tags: ${JSON.stringify(d)}`);
    }
  });

  test('novelty levels are valid', () => {
    for (const d of ir.decisions) {
      assert.ok(VALID_NOVELTY_LEVELS.includes(d.novelty), `Invalid novelty: ${d.novelty}`);
    }
  });

  test('spectrum levels are valid', () => {
    for (const d of ir.decisions) {
      assert.ok(VALID_SPECTRUM_LEVELS.includes(d.spectrum), `Invalid spectrum: ${d.spectrum}`);
    }
  });

  test('covers key domains', () => {
    const allTags = ir.decisions.flatMap(d => d.tags);
    for (const domain of ['infrastructure', 'database', 'messaging', 'architecture', 'data', 'toolchain', 'embedded', 'observability']) {
      assert.ok(allTags.includes(domain), `Missing domain: ${domain}`);
    }
  });

  test('generates Qdrant points', () => {
    const points = irToPoints(ir);
    assert.ok(points.length >= 20, `Expected 20+ points, got ${points.length}`);

    const decisionPoints = points.filter(p => p.payload.entry_type === 'decision');
    assert.ok(decisionPoints.length >= 15);
    assert.ok(decisionPoints[0].payload.given);
    assert.ok(decisionPoints[0].payload.prefer);
    assert.ok(decisionPoints[0].payload.because);

    const behaviorPoints = points.filter(p => p.payload.entry_type === 'behavior');
    assert.ok(behaviorPoints.length >= 5);
  });

  test('decisions span the simplicity spectrum', () => {
    const spectrums = new Set(ir.decisions.map(d => d.spectrum));
    assert.ok(spectrums.has('simplicity'), 'Missing simplicity decisions');
    assert.ok(spectrums.has('balanced'), 'Missing balanced decisions');
    assert.ok(spectrums.has('enterprise'), 'Missing enterprise decisions');
  });
});
