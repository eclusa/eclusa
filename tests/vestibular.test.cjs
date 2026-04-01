'use strict';

const { describe, test, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');

const {
  DEFAULT_VESTIBULAR,
  VALID_AUTONOMY_LEVELS,
  VALID_COLLABORATION_STYLES,
  VALID_DECISION_MODELS,
  validate,
  scaffoldVestibular,
  mergeWithProject,
} = require('../eclusa/bin/lib/vestibular.cjs');

describe('vestibular schema defaults', () => {
  test('has version 1', () => {
    assert.strictEqual(DEFAULT_VESTIBULAR.version, 1);
  });

  test('has register section', () => {
    assert.ok(DEFAULT_VESTIBULAR.register);
    assert.strictEqual(typeof DEFAULT_VESTIBULAR.register.name, 'string');
    assert.strictEqual(typeof DEFAULT_VESTIBULAR.register.role, 'string');
  });

  test('has autonomy section with collaborative default', () => {
    assert.strictEqual(DEFAULT_VESTIBULAR.autonomy.level, 'collaborative');
    assert.ok(DEFAULT_VESTIBULAR.autonomy.gates);
    assert.strictEqual(DEFAULT_VESTIBULAR.autonomy.gates.confirm_scope, true);
  });

  test('has collaboration section', () => {
    assert.strictEqual(DEFAULT_VESTIBULAR.collaboration.style, 'iterative');
    assert.strictEqual(DEFAULT_VESTIBULAR.collaboration.decision_model, 'human-final');
  });

  test('has escalation section', () => {
    assert.strictEqual(DEFAULT_VESTIBULAR.escalation.on_ambiguity, 'ask');
    assert.strictEqual(DEFAULT_VESTIBULAR.escalation.on_blocked, 'notify');
  });

  test('has environment section', () => {
    assert.strictEqual(DEFAULT_VESTIBULAR.environment.harness, 'auto');
    assert.strictEqual(DEFAULT_VESTIBULAR.environment.multi_select, true);
  });
});

describe('vestibular validation', () => {
  test('valid vestibular passes', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    const errors = validate(data);
    assert.strictEqual(errors.length, 0);
  });

  test('rejects wrong version', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    data.version = 2;
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'version'));
  });

  test('rejects invalid autonomy level', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    data.autonomy.level = 'reckless';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'autonomy.level'));
  });

  test('rejects invalid collaboration style', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    data.collaboration.style = 'chaotic';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'collaboration.style'));
  });

  test('rejects invalid decision model', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    data.collaboration.decision_model = 'coin-flip';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'collaboration.decision_model'));
  });

  test('rejects invalid escalation action', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    data.escalation.on_ambiguity = 'panic';
    const errors = validate(data);
    assert.ok(errors.some(e => e.path === 'escalation.on_ambiguity'));
  });

  test('validates stance structure', () => {
    const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    data.stances = [{ name: 'Test' }]; // missing rule
    const errors = validate(data);
    assert.ok(errors.some(e => e.path.includes('stances')));
  });

  test('accepts valid autonomy levels', () => {
    for (const level of VALID_AUTONOMY_LEVELS) {
      const data = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
      data.autonomy.level = level;
      const errors = validate(data);
      assert.strictEqual(errors.length, 0, `Level "${level}" should be valid`);
    }
  });
});

describe('vestibular scaffold', () => {
  test('creates vestibular with given values', () => {
    const result = scaffoldVestibular({
      name: 'Nathan',
      role: 'Senior Engineer',
      autonomy_level: 'autonomous',
      communication_style: 'concise',
    });
    assert.strictEqual(result.version, 1);
    assert.strictEqual(result.register.name, 'Nathan');
    assert.strictEqual(result.register.role, 'Senior Engineer');
    assert.strictEqual(result.autonomy.level, 'autonomous');
    assert.strictEqual(result.style.communication, 'concise');
  });

  test('uses defaults for unspecified values', () => {
    const result = scaffoldVestibular({});
    assert.strictEqual(result.autonomy.level, 'collaborative');
    assert.strictEqual(result.style.communication, 'concise');
    assert.strictEqual(result.register.name, '');
  });

  test('adds notification channel', () => {
    const result = scaffoldVestibular({
      notification_script: '~/scripts/notify.sh',
    });
    assert.strictEqual(result.escalation.channels.length, 1);
    assert.strictEqual(result.escalation.channels[0].type, 'script');
    assert.strictEqual(result.escalation.channels[0].path, '~/scripts/notify.sh');
    assert.ok(result.environment.notifications.includes('~/scripts/notify.sh'));
  });
});

describe('vestibular merge with project', () => {
  test('merges stances from project', () => {
    const v = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    v.stances = [
      { name: 'Global Stance', rule: 'Always apply' },
    ];
    const projectStances = [
      { name: 'Project Stance', rule: 'Only this project' },
    ];
    const merged = mergeWithProject(v, projectStances);
    assert.strictEqual(merged.stances.length, 2);
    assert.ok(merged.stances.some(s => s.name === 'Global Stance'));
    assert.ok(merged.stances.some(s => s.name === 'Project Stance'));
  });

  test('project stance overrides vestibular stance with same name', () => {
    const v = JSON.parse(JSON.stringify(DEFAULT_VESTIBULAR));
    v.stances = [
      { name: 'Shared', rule: 'vestibular rule' },
    ];
    const projectStances = [
      { name: 'Shared', rule: 'project override' },
    ];
    const merged = mergeWithProject(v, projectStances);
    assert.strictEqual(merged.stances.length, 1);
    assert.strictEqual(merged.stances[0].rule, 'project override');
  });

  test('handles null vestibular', () => {
    const projectStances = [
      { name: 'Test', rule: 'test rule' },
    ];
    const merged = mergeWithProject(null, projectStances);
    assert.ok(merged.stances.length >= 1);
    assert.ok(merged.stances.some(s => s.name === 'Test'));
  });
});
