'use strict';

const { describe, test } = require('node:test');
const assert = require('node:assert/strict');

const {
  extractBehaviorsFromText,
  extractEntityNames,
  detectBehaviorType,
  generateBehaviorExtractionPrompt,
  extractFromSections,
} = require('../eclusa/bin/lib/behavior-extractor.cjs');

describe('behavior extraction — RFC 2119 patterns', () => {
  test('extracts MUST statements', () => {
    const text = 'The Subscription MUST be in active state before renewal.';
    const behaviors = extractBehaviorsFromText(text, 'test');
    assert.ok(behaviors.length > 0);
    assert.ok(behaviors[0].statement.includes('MUST'));
    assert.ok(behaviors[0].entities.includes('Subscription'));
  });

  test('extracts MUST NOT statements', () => {
    const text = 'Refunds MUST NOT exceed the original charge amount.';
    const behaviors = extractBehaviorsFromText(text, 'test');
    assert.ok(behaviors.length > 0);
    assert.ok(behaviors[0].statement.includes('MUST NOT'));
    assert.strictEqual(behaviors[0].type, 'constraint');
  });

  test('extracts SHALL statements', () => {
    const text = 'The system SHALL notify the user within 24 hours.';
    const behaviors = extractBehaviorsFromText(text, 'test');
    assert.ok(behaviors.length > 0);
  });
});

describe('behavior extraction — conditional patterns', () => {
  test('extracts When/then rules', () => {
    const text = 'When a payment fails, then the subscription status changes to past_due.';
    const behaviors = extractBehaviorsFromText(text, 'test');
    assert.ok(behaviors.length > 0);
    assert.ok(behaviors[0].statement.includes('If'));
    assert.ok(behaviors[0].statement.includes('then'));
  });

  test('extracts If/then rules', () => {
    const text = 'If the advance is fully recouped, then disbursement is blocked.';
    const behaviors = extractBehaviorsFromText(text, 'test');
    assert.ok(behaviors.length > 0);
  });
});

describe('behavior extraction — state transitions', () => {
  test('extracts transition patterns', () => {
    const text = 'Order transitions from pending to confirmed after payment.';
    const behaviors = extractBehaviorsFromText(text, 'test');
    assert.ok(behaviors.some(b => b.type === 'state_transition'));
  });
});

describe('behavior extraction — entity names', () => {
  test('extracts PascalCase names', () => {
    const names = extractEntityNames('The Customer and their Subscription should be active');
    assert.ok(names.includes('Customer'));
    assert.ok(names.includes('Subscription'));
  });

  test('handles empty text', () => {
    const names = extractEntityNames('nothing special here');
    assert.deepStrictEqual(names, []);
  });
});

describe('behavior type detection', () => {
  test('detects state transitions', () => {
    assert.strictEqual(detectBehaviorType('status changes', 'new state'), 'state_transition');
  });

  test('detects preconditions', () => {
    assert.strictEqual(detectBehaviorType('requires authentication', 'proceed'), 'precondition');
  });

  test('defaults to constraint', () => {
    assert.strictEqual(detectBehaviorType('some condition', 'some action'), 'constraint');
  });
});

describe('LLM prompt generation', () => {
  test('generates structured prompt', () => {
    const prompt = generateBehaviorExtractionPrompt(
      'The API allows creating subscriptions. Subscriptions can be active, past_due, or canceled.',
      'test-api-docs',
      ['Subscription', 'Customer']
    );
    assert.strictEqual(prompt.role, 'behavior_extractor');
    assert.ok(prompt.instruction.includes('Subscription'));
    assert.ok(prompt.instruction.includes('Customer'));
    assert.ok(prompt.instruction.includes('mathematical prose'));
  });
});

describe('section-based extraction', () => {
  test('extracts from multiple sections', () => {
    const sections = [
      { heading: 'Billing', text: 'Invoices MUST be generated monthly.' },
      { heading: 'Auth', text: 'Users MUST authenticate before accessing resources.' },
    ];
    const behaviors = extractFromSections(sections, 'api-docs');
    assert.ok(behaviors.length >= 2);
    assert.ok(behaviors[0].source.includes('#Billing'));
  });
});
