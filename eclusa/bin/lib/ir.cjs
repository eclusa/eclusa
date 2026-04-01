'use strict';

/**
 * Normalized Intermediate Representation (IR) for the schema commons.
 *
 * Regardless of source format (OpenAPI, Prisma, SQL DDL, etc.),
 * everything becomes this unified structure: entities with typed fields,
 * relations, operations, constraints, auth, and behaviors.
 *
 * Each IR document represents one parsed source.
 */

// ─── IR Schema ──────────────────────────────────────────────────────────────

/**
 * @typedef {Object} IRSource
 * @property {string} origin - Where this came from (e.g., "github:stripe/openapi/billing.yaml")
 * @property {string} format - Source format (openapi, prisma, sql_ddl, graphql, etc.)
 * @property {string} [version] - Source version
 * @property {string} parsed_at - ISO timestamp
 */

/**
 * @typedef {Object} IRField
 * @property {string} type - Field type (string, number, boolean, timestamp, etc.)
 * @property {string} [constraint] - unique, nullable, required, etc.
 * @property {string[]} [values] - For enum types
 * @property {*} [default_value] - Default value
 */

/**
 * @typedef {Object} IRRelation
 * @property {string} target - Target entity name
 * @property {string} cardinality - one_to_one, one_to_many, many_to_one, many_to_many
 * @property {string} [through] - Join table for many_to_many
 */

/**
 * @typedef {Object} IREntity
 * @property {Object<string, IRField>} fields
 * @property {Object<string, IRRelation>} [relations]
 */

/**
 * @typedef {Object} IROperation
 * @property {string} name
 * @property {Object<string, string>} [input] - Field name → type
 * @property {string} [output] - Return type/entity name
 * @property {string[]} [side_effects]
 * @property {string[]} [constraints]
 * @property {string} [method] - HTTP method for API operations
 * @property {string} [path] - API path
 * @property {number[]} [status_codes]
 */

/**
 * @typedef {Object} IRAuth
 * @property {string} model - bearer_token, api_key, oauth2, basic, none
 * @property {string[]} [scopes]
 */

/**
 * @typedef {Object} IRDocument
 * @property {IRSource} source
 * @property {Object<string, IREntity>} entities
 * @property {IROperation[]} [operations]
 * @property {IRAuth} [auth]
 * @property {IRBehavior[]} [behaviors]
 * @property {IRDecision[]} [decisions]
 */

/**
 * @typedef {Object} IRDecision
 * @property {string} given - Context/situation: "stateless HTTP service, < 100 RPS, single region"
 * @property {string} prefer - Recommended choice: "Fly.io or Railway over Kubernetes"
 * @property {string} because - Rationale: "operational overhead of k8s exceeds value below this scale"
 * @property {string} [unless] - Exception: "team already operates k8s clusters"
 * @property {string} [when] - Alternative condition: "Redis Streams sufficient if single consumer"
 * @property {string[]} tags - Domain tags: ["infrastructure", "deployment", "scale"]
 * @property {string} novelty - well_known | similar_to_known | novel
 * @property {string} spectrum - simplicity | balanced | enterprise
 */

/**
 * @typedef {Object} IRBehavior
 * @property {string} statement - Structured English: "For any X where P(X): Q(X)"
 * @property {string} source - Where this was extracted from
 * @property {string[]} entities - Entity names this behavior references
 * @property {string} type - invariant | state_transition | constraint | workflow | precondition | postcondition
 */

// ─── IR Builder ─────────────────────────────────────────────────────────────

function createIR(origin, format, version) {
  return {
    source: {
      origin,
      format,
      version: version || null,
      parsed_at: new Date().toISOString(),
    },
    entities: {},
    operations: [],
    auth: null,
    behaviors: [],
    decisions: [],
  };
}

function addEntity(ir, name, fields, relations) {
  ir.entities[name] = {
    fields: fields || {},
    relations: relations || {},
  };
  return ir;
}

function addOperation(ir, op) {
  ir.operations.push(op);
  return ir;
}

function addAuth(ir, model, scopes) {
  ir.auth = { model, scopes: scopes || [] };
  return ir;
}

/**
 * Add a behavior to the IR.
 * @param {object} ir
 * @param {object} behavior - { statement, source, entities, type }
 *   statement: Structured English, reads like mathematical prose
 *   source: Where extracted from (doc section, file, etc.)
 *   entities: Entity names this behavior references
 *   type: invariant | state_transition | constraint | workflow | precondition | postcondition
 */
function addBehavior(ir, behavior) {
  if (typeof behavior === 'string') {
    // Legacy: plain string behaviors
    ir.behaviors.push({ statement: behavior, source: ir.source.origin, entities: [], type: 'constraint' });
  } else {
    ir.behaviors.push({
      statement: behavior.statement,
      source: behavior.source || ir.source.origin,
      entities: behavior.entities || [],
      type: behavior.type || 'constraint',
    });
  }
  return ir;
}

const VALID_BEHAVIOR_TYPES = ['invariant', 'state_transition', 'constraint', 'workflow', 'precondition', 'postcondition'];
const VALID_NOVELTY_LEVELS = ['well_known', 'similar_to_known', 'novel'];
const VALID_SPECTRUM_LEVELS = ['simplicity', 'balanced', 'enterprise'];

/**
 * Add an architectural decision to the IR.
 */
function addDecision(ir, decision) {
  ir.decisions.push({
    given: decision.given,
    prefer: decision.prefer,
    because: decision.because,
    unless: decision.unless || null,
    when: decision.when || null,
    tags: decision.tags || [],
    novelty: decision.novelty || 'well_known',
    spectrum: decision.spectrum || 'balanced',
  });
  return ir;
}

// ─── IR to Qdrant Points ───────────────────────────────────────────────────

const { embedSync, embedBatch, deterministicId } = require('./qdrant.cjs');

/**
 * Convert an IR document into Qdrant points.
 * Each entity and operation becomes a separate point for granular search.
 */
function irToPoints(ir) {
  const points = [];
  const origin = ir.source.origin;

  // One point per entity
  for (const [name, entity] of Object.entries(ir.entities)) {
    const fieldNames = Object.keys(entity.fields);
    const fieldTypes = Object.values(entity.fields).map(f => f.type);
    const relationTargets = Object.values(entity.relations || {}).map(r => r.target);

    // Build searchable text
    const text = [
      name,
      ...fieldNames,
      ...fieldTypes,
      ...relationTargets,
    ].join(' ');

    points.push({
      id: deterministicId(origin, `entity:${name}`),
      vector: embedSync(text),
      payload: {
        entry_type: 'entity',
        entity_name: name,
        source_origin: origin,
        source_format: ir.source.format,
        source_version: ir.source.version,
        field_names: fieldNames,
        field_types: fieldTypes,
        relation_targets: relationTargets,
        fields: entity.fields,
        relations: entity.relations || {},
      },
    });
  }

  // One point per operation
  for (const op of ir.operations) {
    const text = [
      op.name,
      op.method || '',
      op.path || '',
      op.output || '',
      ...(op.constraints || []),
    ].join(' ');

    points.push({
      id: deterministicId(origin, `op:${op.name}`),
      vector: embedSync(text),
      payload: {
        entry_type: 'operation',
        entity_name: op.name,
        source_origin: origin,
        source_format: ir.source.format,
        source_version: ir.source.version,
        operation: op,
      },
    });
  }

  // One point for auth model (if present)
  if (ir.auth) {
    points.push({
      id: deterministicId(origin, 'auth'),
      vector: embedSync(`auth ${ir.auth.model} ${(ir.auth.scopes || []).join(' ')}`),
      payload: {
        entry_type: 'auth',
        entity_name: 'auth',
        source_origin: origin,
        source_format: ir.source.format,
        auth: ir.auth,
      },
    });
  }

  // One point per behavior
  for (let i = 0; i < ir.behaviors.length; i++) {
    const b = ir.behaviors[i];
    const statement = typeof b === 'string' ? b : b.statement;
    const entities = typeof b === 'string' ? [] : (b.entities || []);
    const bType = typeof b === 'string' ? 'constraint' : (b.type || 'constraint');

    const text = [statement, ...entities, bType].join(' ');

    points.push({
      id: deterministicId(origin, `behavior:${i}:${statement.slice(0, 50)}`),
      vector: embedSync(text),
      payload: {
        entry_type: 'behavior',
        entity_name: entities[0] || 'system',
        source_origin: origin,
        source_format: ir.source.format,
        behavior_type: bType,
        statement,
        entities,
        source_ref: typeof b === 'string' ? origin : (b.source || origin),
      },
    });
  }

  // One point per decision
  for (let i = 0; i < (ir.decisions || []).length; i++) {
    const d = ir.decisions[i];
    const text = [
      'Given:', d.given,
      'Prefer:', d.prefer,
      'Because:', d.because,
      d.unless ? `Unless: ${d.unless}` : '',
      ...(d.tags || []),
    ].filter(Boolean).join(' ');

    points.push({
      id: deterministicId(origin, `decision:${i}:${d.prefer.slice(0, 40)}`),
      vector: embedSync(text),
      payload: {
        entry_type: 'decision',
        entity_name: d.tags?.[0] || 'architecture',
        source_origin: origin,
        source_format: ir.source.format,
        given: d.given,
        prefer: d.prefer,
        because: d.because,
        unless: d.unless,
        when: d.when,
        tags: d.tags || [],
        novelty: d.novelty,
        spectrum: d.spectrum,
      },
    });
  }

  return points;
}

// ─── IR Validation ──────────────────────────────────────────────────────────

function validateIR(ir) {
  const errors = [];
  if (!ir.source) errors.push('Missing source metadata');
  if (!ir.source?.origin) errors.push('Missing source.origin');
  if (!ir.source?.format) errors.push('Missing source.format');
  if (!ir.entities || typeof ir.entities !== 'object') errors.push('Missing entities');

  for (const [name, entity] of Object.entries(ir.entities || {})) {
    if (!entity.fields || typeof entity.fields !== 'object') {
      errors.push(`Entity ${name}: missing fields`);
    }
  }

  return errors;
}

module.exports = {
  createIR,
  addEntity,
  addOperation,
  addAuth,
  addBehavior,
  addDecision,
  VALID_BEHAVIOR_TYPES,
  VALID_NOVELTY_LEVELS,
  VALID_SPECTRUM_LEVELS,
  irToPoints,
  validateIR,
};
