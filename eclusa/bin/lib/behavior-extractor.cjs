'use strict';

/**
 * Behavior extractor — parse documentation and specs into structured English.
 *
 * Produces behavioral specifications that read like mathematical prose:
 *   "For any Subscription s where status(s) = active:
 *    If days_past_due(s) >= 30, then transition(s, canceled)."
 *
 * Two modes:
 * 1. Rule-based: extract from structured docs (state machines, constraint lists, RFC-style)
 * 2. LLM-assisted: extract from free-form documentation (README, API guides)
 *
 * Extracted behaviors are first-class IR citizens, embedded in Qdrant alongside
 * entities and operations.
 */

const { addBehavior } = require('./ir.cjs');

// ─── Rule-based Extraction ──────────────────────────────────────────────────

/**
 * Extract behaviors from structured text patterns.
 * Recognizes common documentation patterns for business rules.
 */
function extractBehaviorsFromText(text, source) {
  const behaviors = [];

  // Pattern 1: "MUST" / "SHALL" / "MUST NOT" statements (RFC 2119 style)
  const rfcPattern = /(?:^|\n)\s*[-*]?\s*(?:The\s+)?(\w[\w\s]*?)\s+(MUST\s+NOT|SHALL\s+NOT|SHOULD\s+NOT|MUST|SHALL|SHOULD|MAY)\s+(.+?)(?:\.|$)/gim;
  let match;
  while ((match = rfcPattern.exec(text)) !== null) {
    const subject = match[1].trim();
    const modal = match[2].toUpperCase();
    const predicate = match[3].trim();
    const entities = extractEntityNames(subject + ' ' + predicate);
    const type = modal.includes('NOT') ? 'constraint' : 'invariant';

    behaviors.push({
      statement: `${subject} ${modal} ${predicate}.`,
      source,
      entities,
      type,
    });
  }

  // Pattern 2: "When X, then Y" / "If X, then Y" conditional rules
  const conditionalPattern = /(?:^|\n)\s*[-*]?\s*(?:When|If)\s+(.+?),\s*(?:then\s+)?(.+?)(?:\.|$)/gim;
  while ((match = conditionalPattern.exec(text)) !== null) {
    const condition = match[1].trim();
    const action = match[2].trim();
    const entities = extractEntityNames(condition + ' ' + action);

    behaviors.push({
      statement: `If ${condition}, then ${action}.`,
      source,
      entities,
      type: detectBehaviorType(condition, action),
    });
  }

  // Pattern 3: State transitions "X transitions from A to B" / "status changes from A to B"
  const transitionPattern = /(\w+)\s+(?:transitions?|changes?|moves?)\s+(?:from\s+)?(\w+)\s+to\s+(\w+)/gi;
  while ((match = transitionPattern.exec(text)) !== null) {
    const entity = match[1];
    const fromState = match[2];
    const toState = match[3];

    behaviors.push({
      statement: `For any ${entity} e: transition(e, ${fromState}, ${toState}) is valid.`,
      source,
      entities: [entity],
      type: 'state_transition',
    });
  }

  // Pattern 4: Uniqueness / cardinality constraints "X must be unique" / "each X has exactly one Y"
  const uniquePattern = /(\w+)\s+(?:must be|is|are)\s+unique/gi;
  while ((match = uniquePattern.exec(text)) !== null) {
    behaviors.push({
      statement: `For any two ${match[1]} a, b: if a ≠ b, then ${match[1].toLowerCase()}(a) ≠ ${match[1].toLowerCase()}(b).`,
      source,
      entities: [match[1]],
      type: 'invariant',
    });
  }

  // Pattern 5: Validation rules "X requires Y" / "X is required when Y"
  const validationPattern = /(\w[\w\s]*?)\s+(?:requires?|is required|is mandatory)\s+(?:when\s+)?(.+?)(?:\.|$)/gi;
  while ((match = validationPattern.exec(text)) !== null) {
    const subject = match[1].trim();
    const condition = match[2].trim();
    behaviors.push({
      statement: `${subject} requires ${condition}.`,
      source,
      entities: extractEntityNames(subject),
      type: 'precondition',
    });
  }

  return behaviors;
}

/**
 * Generate an LLM prompt for extracting behaviors from unstructured text.
 * The LLM is given the text and asked to produce structured English behaviors.
 */
function generateBehaviorExtractionPrompt(text, source, entityNames) {
  return {
    role: 'behavior_extractor',
    instruction: `Extract behavioral specifications from the following documentation.

For each behavior, produce structured English that reads like mathematical prose:
- "For any X where P(X): Q(X)"
- "If condition, then consequence."
- "X MUST/SHALL Y."
- "For any X transitioning from state A: allowed next states are {B, C}."

Each behavior should specify:
1. statement: The behavioral rule in structured English
2. entities: Which domain entities this references (from: ${entityNames.join(', ')})
3. type: One of: invariant, state_transition, constraint, workflow, precondition, postcondition

Focus on:
- Business rules and constraints (not implementation details)
- State machines and valid transitions
- Required fields and validation rules
- Relationships and cardinality constraints
- Temporal rules (deadlines, windows, sequences)

Source: ${source}

---
${text.slice(0, 8000)}
---

Respond with a JSON array of behaviors:
[{"statement": "...", "entities": ["..."], "type": "..."}]`,
  };
}

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Extract likely entity names from text (PascalCase words). */
function extractEntityNames(text) {
  const names = text.match(/\b[A-Z][a-z]+(?:[A-Z][a-z]+)*/g) || [];
  return [...new Set(names)];
}

/** Detect behavior type from condition/action text. */
function detectBehaviorType(condition, action) {
  const lower = (condition + ' ' + action).toLowerCase();
  if (lower.includes('transition') || lower.includes('status') || lower.includes('state')) return 'state_transition';
  if (lower.includes('before') || lower.includes('prior') || lower.includes('requires')) return 'precondition';
  if (lower.includes('after') || lower.includes('result') || lower.includes('produces')) return 'postcondition';
  if (lower.includes('always') || lower.includes('never') || lower.includes('invariant')) return 'invariant';
  if (lower.includes('step') || lower.includes('then') || lower.includes('flow')) return 'workflow';
  return 'constraint';
}

/**
 * Apply extracted behaviors to an IR document.
 */
function applyBehaviors(ir, behaviors) {
  for (const b of behaviors) {
    addBehavior(ir, b);
  }
  return ir;
}

/**
 * Extract behaviors from multiple text sections.
 * Useful for processing README sections, API doc pages, etc.
 */
function extractFromSections(sections, source) {
  const all = [];
  for (const section of sections) {
    const behaviors = extractBehaviorsFromText(section.text, `${source}#${section.heading || 'body'}`);
    all.push(...behaviors);
  }
  return all;
}

module.exports = {
  extractBehaviorsFromText,
  generateBehaviorExtractionPrompt,
  extractEntityNames,
  detectBehaviorType,
  applyBehaviors,
  extractFromSections,
};
