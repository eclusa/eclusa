'use strict';

/**
 * Prisma schema parser → Normalized IR
 *
 * Extracts: models (→ entities), fields, relations, enums.
 * Handles .prisma file format.
 */

const { createIR, addEntity } = require('../ir.cjs');

/**
 * Parse a Prisma schema string into IR.
 * @param {string} content - .prisma file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'prisma', null);

  // Extract enums first (needed for field type resolution)
  const enums = {};
  const enumRegex = /enum\s+(\w+)\s*\{([^}]+)\}/g;
  let match;
  while ((match = enumRegex.exec(content)) !== null) {
    const name = match[1];
    const values = match[2].trim().split(/\s+/).filter(v => v && !v.startsWith('//'));
    enums[name] = values;

    addEntity(ir, name, {
      value: { type: 'enum', values },
    });
  }

  // Extract models
  const modelRegex = /model\s+(\w+)\s*\{([^}]+)\}/g;
  while ((match = modelRegex.exec(content)) !== null) {
    const modelName = match[1];
    const body = match[2];
    const fields = {};
    const relations = {};

    const lines = body.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('@@')) continue;

      const fieldMatch = trimmed.match(/^(\w+)\s+(\S+)(\s+.*)?$/);
      if (!fieldMatch) continue;

      const fieldName = fieldMatch[1];
      let fieldType = fieldMatch[2];
      const attrs = fieldMatch[3] || '';

      // Skip Prisma-specific directives
      if (fieldName === 'id' && fieldType === 'String' && attrs.includes('@id')) {
        fields[fieldName] = { type: 'string', constraint: 'unique' };
        continue;
      }

      // Detect relations
      const isOptional = fieldType.endsWith('?');
      const isArray = fieldType.endsWith('[]');
      const baseType = fieldType.replace(/[?\[\]]/g, '');

      // Check if it's a relation (references another model or is an array of models)
      const relationMatch = attrs.match(/@relation\(([^)]*)\)/);
      if (relationMatch || (isArray && !isPrismaScalar(baseType))) {
        relations[fieldName] = {
          target: baseType,
          cardinality: isArray ? 'one_to_many' : 'many_to_one',
        };
        continue;
      }

      // Regular field
      if (isPrismaScalar(baseType)) {
        const constraint = [];
        if (attrs.includes('@id')) constraint.push('unique');
        if (attrs.includes('@unique')) constraint.push('unique');
        if (isOptional) constraint.push('nullable');
        if (attrs.includes('@default')) constraint.push('has_default');

        fields[fieldName] = {
          type: mapPrismaType(baseType),
          constraint: constraint.length > 0 ? constraint.join(',') : null,
        };
      } else if (enums[baseType]) {
        fields[fieldName] = {
          type: 'enum',
          values: enums[baseType],
          constraint: isOptional ? 'nullable' : null,
        };
      } else {
        // Unknown type — probably a relation to another model
        relations[fieldName] = {
          target: baseType,
          cardinality: isArray ? 'one_to_many' : 'many_to_one',
        };
      }
    }

    addEntity(ir, modelName, fields, relations);
  }

  return ir;
}

function isPrismaScalar(type) {
  return ['String', 'Int', 'Float', 'Boolean', 'DateTime', 'BigInt', 'Decimal', 'Bytes', 'Json'].includes(type);
}

function mapPrismaType(type) {
  const map = {
    String: 'string',
    Int: 'number',
    Float: 'number',
    Boolean: 'boolean',
    DateTime: 'timestamp',
    BigInt: 'number',
    Decimal: 'number',
    Bytes: 'binary',
    Json: 'object',
  };
  return map[type] || 'any';
}

/** Check if content looks like a Prisma schema. */
function canParse(content, filename) {
  if (filename && filename.endsWith('.prisma')) return true;
  return /^(model|datasource|generator|enum)\s+\w+\s*\{/m.test(content);
}

module.exports = { parse, canParse };
