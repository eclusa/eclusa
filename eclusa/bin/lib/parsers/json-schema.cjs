'use strict';

/**
 * JSON Schema parser → Normalized IR
 *
 * Extracts: schema objects (→ entities), properties (→ fields),
 * $ref (→ relations), definitions/$defs (→ additional entities).
 */

const { createIR, addEntity } = require('../ir.cjs');

/**
 * Parse a JSON Schema string into IR.
 * @param {string} content - JSON content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  let schema;
  try {
    schema = JSON.parse(content);
  } catch {
    throw new Error(`Invalid JSON in ${origin}`);
  }

  const ir = createIR(origin, 'json_schema', schema.$schema || null);

  // Process definitions/$defs first (they are reusable entities)
  const defs = schema.definitions || schema.$defs || {};
  for (const [name, def] of Object.entries(defs)) {
    processSchemaObject(ir, name, def, defs);
  }

  // Process top-level schema if it has properties (it's an entity itself)
  const topName = schema.title || extractNameFromOrigin(origin);
  if (schema.type === 'object' && schema.properties) {
    processSchemaObject(ir, topName, schema, defs);
  }

  // Handle array of schemas (e.g., oneOf/anyOf at top level with named items)
  for (const combiner of ['oneOf', 'anyOf', 'allOf']) {
    if (Array.isArray(schema[combiner])) {
      for (const subSchema of schema[combiner]) {
        if (subSchema.title && subSchema.properties) {
          processSchemaObject(ir, subSchema.title, subSchema, defs);
        }
      }
    }
  }

  return ir;
}

/**
 * Process a single schema object into an entity.
 */
function processSchemaObject(ir, name, schema, defs) {
  if (!schema || typeof schema !== 'object') return;

  // Handle enum types
  if (schema.enum) {
    addEntity(ir, name, {
      value: { type: 'enum', values: schema.enum },
    });
    return;
  }

  // Only process objects with properties
  if (schema.type !== 'object' && !schema.properties) {
    // Could still be a simple type alias
    if (schema.type) {
      addEntity(ir, name, {
        value: { type: mapJsonSchemaType(schema), constraint: null },
      });
    }
    return;
  }

  const fields = {};
  const relations = {};
  const requiredFields = new Set(schema.required || []);

  for (const [propName, propSchema] of Object.entries(schema.properties || {})) {
    if (!propSchema || typeof propSchema !== 'object') continue;

    // Handle $ref
    if (propSchema.$ref) {
      const refName = extractRefName(propSchema.$ref);
      relations[propName] = {
        target: refName,
        cardinality: 'many_to_one',
      };
      continue;
    }

    // Handle array with $ref items
    if (propSchema.type === 'array' && propSchema.items) {
      if (propSchema.items.$ref) {
        const refName = extractRefName(propSchema.items.$ref);
        relations[propName] = {
          target: refName,
          cardinality: 'one_to_many',
        };
        continue;
      }
      fields[propName] = {
        type: 'array',
        constraint: requiredFields.has(propName) ? 'required' : 'nullable',
      };
      continue;
    }

    // Handle nested object without $ref
    if (propSchema.type === 'object' && propSchema.properties) {
      // Inline nested object → create as a separate entity and add relation
      const nestedName = name + capitalize(propName);
      processSchemaObject(ir, nestedName, propSchema, defs);
      relations[propName] = {
        target: nestedName,
        cardinality: 'many_to_one',
      };
      continue;
    }

    // Handle enum property
    if (propSchema.enum) {
      fields[propName] = {
        type: 'enum',
        values: propSchema.enum,
        constraint: requiredFields.has(propName) ? 'required' : 'nullable',
      };
      continue;
    }

    // Handle oneOf/anyOf (treat as union → any, but check for $ref)
    if (propSchema.oneOf || propSchema.anyOf) {
      const variants = propSchema.oneOf || propSchema.anyOf;
      const refs = variants.filter(v => v.$ref).map(v => extractRefName(v.$ref));
      if (refs.length > 0) {
        // Polymorphic reference
        relations[propName] = {
          target: refs[0], // Primary target
          cardinality: 'many_to_one',
        };
        continue;
      }
    }

    // Regular scalar field
    const constraint = [];
    if (requiredFields.has(propName)) constraint.push('required');
    else constraint.push('nullable');
    if (propSchema.minLength || propSchema.minimum !== undefined || propSchema.pattern) constraint.push('validated');

    fields[propName] = {
      type: mapJsonSchemaType(propSchema),
      constraint: constraint.length > 0 ? constraint.join(',') : null,
    };

    if (propSchema.default !== undefined) {
      fields[propName].default_value = propSchema.default;
    }
  }

  // Handle allOf (merge schemas)
  if (schema.allOf) {
    for (const subSchema of schema.allOf) {
      if (subSchema.$ref) {
        const refName = extractRefName(subSchema.$ref);
        relations[refName.charAt(0).toLowerCase() + refName.slice(1)] = {
          target: refName,
          cardinality: 'one_to_one',
        };
      }
    }
  }

  addEntity(ir, name, fields, relations);
}

function extractRefName(ref) {
  return ref.split('/').pop();
}

function extractNameFromOrigin(origin) {
  // Try to extract a meaningful name from origin path
  const parts = origin.split(/[/\\]/);
  const filename = parts.pop() || 'Root';
  return capitalize(filename.replace(/\.(json|schema)$/gi, ''));
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function mapJsonSchemaType(schema) {
  if (!schema) return 'any';
  if (schema.type === 'integer') return 'number';
  if (schema.type === 'number') return 'number';
  if (schema.type === 'string' && schema.format === 'date-time') return 'timestamp';
  if (schema.type === 'string' && schema.format === 'date') return 'date';
  if (schema.type === 'string') return 'string';
  if (schema.type === 'boolean') return 'boolean';
  if (schema.type === 'array') return 'array';
  if (schema.type === 'object') return 'object';
  if (schema.type === 'null') return 'any';
  return schema.type || 'any';
}

/** Check if content looks like a JSON Schema file. */
function canParse(content, filename) {
  if (filename && /\.schema\.json$/i.test(filename)) return true;
  // Check for JSON Schema indicators
  try {
    const parsed = JSON.parse(content);
    if (parsed.$schema) return true;
    if (parsed.type === 'object' && parsed.properties) return true;
    if (parsed.definitions || parsed.$defs) return true;
  } catch {
    return false;
  }
  return false;
}

module.exports = { parse, canParse };
