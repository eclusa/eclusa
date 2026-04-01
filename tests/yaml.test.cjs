'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');
const { parseYaml, dumpYaml } = require('../eclusa/bin/lib/yaml.cjs');

describe('YAML parser', () => {

  test('parses simple key-value pairs', () => {
    const result = parseYaml('name: hello\nversion: 5\nenabled: true');
    assert.deepStrictEqual(result, { name: 'hello', version: 5, enabled: true });
  });

  test('parses nested objects', () => {
    const result = parseYaml('identity:\n  name: test\n  description: a thing');
    assert.deepStrictEqual(result, { identity: { name: 'test', description: 'a thing' } });
  });

  test('parses flow sequences', () => {
    const result = parseYaml('tags: [payments, lending, api]');
    assert.deepStrictEqual(result, { tags: ['payments', 'lending', 'api'] });
  });

  test('parses empty flow sequences', () => {
    const result = parseYaml('items: []');
    assert.deepStrictEqual(result, { items: [] });
  });

  test('parses block sequences', () => {
    const result = parseYaml('items:\n  - one\n  - two\n  - three');
    assert.deepStrictEqual(result, { items: ['one', 'two', 'three'] });
  });

  test('parses block sequences with mapping items', () => {
    const yaml = `stances:
  - name: Reviewed Commits
    rule: Wait for approval
  - name: Conservative Default
    rule: Surface gaps`;
    const result = parseYaml(yaml);
    assert.strictEqual(result.stances.length, 2);
    assert.strictEqual(result.stances[0].name, 'Reviewed Commits');
    assert.strictEqual(result.stances[0].rule, 'Wait for approval');
    assert.strictEqual(result.stances[1].name, 'Conservative Default');
  });

  test('parses flow mappings', () => {
    const result = parseYaml('frontier: { model: claude-opus-4-6, parameters: { thinking: extended } }');
    assert.deepStrictEqual(result, {
      frontier: { model: 'claude-opus-4-6', parameters: { thinking: 'extended' } }
    });
  });

  test('parses quoted strings', () => {
    const result = parseYaml('name: "hello world"\ndesc: \'single quoted\'');
    assert.strictEqual(result.name, 'hello world');
    assert.strictEqual(result.desc, 'single quoted');
  });

  test('parses null values', () => {
    const result = parseYaml('file: null\nempty: ~\nblank:');
    assert.strictEqual(result.file, null);
    assert.strictEqual(result.empty, null);
    assert.strictEqual(result.blank, null);
  });

  test('parses booleans', () => {
    const result = parseYaml('yes: true\nno: false');
    assert.strictEqual(result.yes, true);
    assert.strictEqual(result.no, false);
  });

  test('parses numbers', () => {
    const result = parseYaml('int: 42\nfloat: 3.14\nneg: -1');
    assert.strictEqual(result.int, 42);
    assert.strictEqual(result.float, 3.14);
    assert.strictEqual(result.neg, -1);
  });

  test('ignores comments', () => {
    const result = parseYaml('name: test # this is a comment\n# full line comment\nversion: 1');
    assert.strictEqual(result.name, 'test');
    assert.strictEqual(result.version, 1);
  });

  test('handles document separator', () => {
    const result = parseYaml('---\nname: test\nversion: 1');
    assert.strictEqual(result.name, 'test');
    assert.strictEqual(result.version, 1);
  });

  test('parses deeply nested structures', () => {
    const yaml = `agents:
  models:
    frontier:
      model: claude-opus-4-6
      parameters:
        thinking: extended
  stage_bindings:
    refine: frontier
    generate: fast
  topology: delegating`;
    const result = parseYaml(yaml);
    assert.strictEqual(result.agents.models.frontier.model, 'claude-opus-4-6');
    assert.strictEqual(result.agents.models.frontier.parameters.thinking, 'extended');
    assert.strictEqual(result.agents.stage_bindings.refine, 'frontier');
    assert.strictEqual(result.agents.topology, 'delegating');
  });

  test('parses a full project.eclusa file', () => {
    const yaml = `# project.eclusa — eclusa pipeline project file
---
version: 5
identity:
  name: my-project
  description: "A test project for payments."
  tags: [payments, lending]
sources:
  matched: []
  novel: []
constraints:
  file: null
stances:
  - name: Reviewed Commits
    premise: "AI-generated diffs require human eyes."
    rule: "Present diff grouped by concern. Wait for approval."
provenance:
  governance_level: full
  storage: git-trailers
agents:
  models:
    frontier: { model: claude-opus-4-6, parameters: { thinking: extended } }
  stage_bindings:
    refine: frontier
    generate: fast
  topology: delegating`;

    const result = parseYaml(yaml);
    assert.strictEqual(result.version, 5);
    assert.strictEqual(result.identity.name, 'my-project');
    assert.strictEqual(result.identity.description, 'A test project for payments.');
    assert.deepStrictEqual(result.identity.tags, ['payments', 'lending']);
    assert.deepStrictEqual(result.sources.matched, []);
    assert.strictEqual(result.constraints.file, null);
    assert.strictEqual(result.stances.length, 1);
    assert.strictEqual(result.stances[0].name, 'Reviewed Commits');
    assert.strictEqual(result.provenance.governance_level, 'full');
    assert.strictEqual(result.agents.topology, 'delegating');
  });
});

describe('YAML dumper', () => {

  test('dumps simple object', () => {
    const yaml = dumpYaml({ name: 'test', version: 5, enabled: true });
    assert.ok(yaml.includes('name: test'));
    assert.ok(yaml.includes('version: 5'));
    assert.ok(yaml.includes('enabled: true'));
  });

  test('dumps nested objects', () => {
    const yaml = dumpYaml({ identity: { name: 'test', tags: ['a', 'b'] } });
    assert.ok(yaml.includes('identity:'));
    assert.ok(yaml.includes('  name: test'));
    assert.ok(yaml.includes('  tags: [a, b]'));
  });

  test('dumps null values', () => {
    const yaml = dumpYaml({ file: null });
    assert.ok(yaml.includes('file: null'));
  });

  test('roundtrips simple structures', () => {
    const original = { version: 5, name: 'test', tags: ['a', 'b'], enabled: true };
    const yaml = dumpYaml(original);
    const parsed = parseYaml(yaml);
    assert.deepStrictEqual(parsed, original);
  });
});
