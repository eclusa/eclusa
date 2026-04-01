'use strict';

/**
 * GraphQL SDL parser → Normalized IR
 *
 * Extracts: types (→ entities), inputs (→ entities), enums (→ entities),
 * interfaces (→ entities), Query/Mutation fields (→ operations).
 */

const { createIR, addEntity, addOperation } = require('../ir.cjs');

/**
 * Parse a GraphQL SDL string into IR.
 * @param {string} content - .graphql/.gql file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'graphql', null);

  // Remove comments
  const cleaned = content
    .replace(/#[^\n]*/g, '')
    .replace(/"""[\s\S]*?"""/g, '')
    .replace(/"[^"]*"/g, '""'); // Preserve string positions but clear content

  // Extract enums first
  const knownEnums = {};
  const enumRegex = /enum\s+(\w+)\s*\{([^}]*)\}/g;
  let match;

  while ((match = enumRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const values = match[2].trim().split(/\s+/).filter(v => v && v !== '');
    knownEnums[name] = values;
    addEntity(ir, name, {
      value: { type: 'enum', values },
    });
  }

  // Extract interfaces
  const interfaceRegex = /interface\s+(\w+)\s*(?:@[^{]*)?\{([^}]*)\}/g;
  const interfaces = {};
  while ((match = interfaceRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];
    const { fields, relations } = parseGraphQLFields(body, knownEnums);
    interfaces[name] = { fields, relations };
    addEntity(ir, name, fields, relations);
  }

  // Extract types (including Query, Mutation, Subscription)
  const typeRegex = /type\s+(\w+)\s*(?:implements\s+[\w\s&]+)?\s*(?:@[^{]*)?\{([^}]*)\}/g;
  while ((match = typeRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];

    if (name === 'Query' || name === 'Mutation' || name === 'Subscription') {
      // Extract operations
      parseOperations(ir, name, body, knownEnums);
    } else {
      const { fields, relations } = parseGraphQLFields(body, knownEnums);

      // Inherit interface fields
      const implMatch = cleaned.match(new RegExp(`type\\s+${name}\\s+implements\\s+([\\w\\s&]+)`));
      if (implMatch) {
        const implNames = implMatch[1].split(/\s*&\s*/).map(s => s.trim()).filter(Boolean);
        for (const ifName of implNames) {
          if (interfaces[ifName]) {
            // Add interface fields not already defined
            for (const [fName, fDef] of Object.entries(interfaces[ifName].fields)) {
              if (!fields[fName]) fields[fName] = fDef;
            }
            for (const [rName, rDef] of Object.entries(interfaces[ifName].relations)) {
              if (!relations[rName]) relations[rName] = rDef;
            }
          }
        }
      }

      addEntity(ir, name, fields, relations);
    }
  }

  // Extract input types
  const inputRegex = /input\s+(\w+)\s*(?:@[^{]*)?\{([^}]*)\}/g;
  while ((match = inputRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];
    const { fields, relations } = parseGraphQLFields(body, knownEnums);
    addEntity(ir, name, fields, relations);
  }

  // Extract scalar declarations (as simple entities)
  const scalarRegex = /scalar\s+(\w+)/g;
  while ((match = scalarRegex.exec(cleaned)) !== null) {
    const name = match[1];
    addEntity(ir, name, {
      value: { type: mapGraphQLType(name), constraint: null },
    });
  }

  // Extract union types
  const unionRegex = /union\s+(\w+)\s*=\s*([^;\n]+)/g;
  while ((match = unionRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const members = match[2].split('|').map(s => s.trim()).filter(Boolean);
    const relations = {};
    for (const member of members) {
      relations[member.charAt(0).toLowerCase() + member.slice(1)] = {
        target: member,
        cardinality: 'one_to_one',
      };
    }
    addEntity(ir, name, {}, relations);
  }

  return ir;
}

/**
 * Parse fields from a GraphQL type body.
 */
function parseGraphQLFields(body, knownEnums) {
  const fields = {};
  const relations = {};

  const lines = body.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Match: fieldName(args): Type or fieldName: Type
    const fieldMatch = trimmed.match(/^(\w+)(?:\([^)]*\))?\s*:\s*(.+?)(?:\s*@.*)?$/);
    if (!fieldMatch) continue;

    const fieldName = fieldMatch[1];
    const rawType = fieldMatch[2].trim();

    const { baseType, isArray, isNullable } = parseGraphQLType(rawType);

    if (knownEnums[baseType]) {
      fields[fieldName] = {
        type: 'enum',
        values: knownEnums[baseType],
        constraint: isNullable ? 'nullable' : null,
      };
    } else if (isGraphQLScalar(baseType)) {
      fields[fieldName] = {
        type: isArray ? 'array' : mapGraphQLType(baseType),
        constraint: isNullable ? 'nullable' : 'required',
      };
    } else {
      // Reference to another type
      relations[fieldName] = {
        target: baseType,
        cardinality: isArray ? 'one_to_many' : 'many_to_one',
      };
    }
  }

  return { fields, relations };
}

/**
 * Parse operations from Query/Mutation/Subscription body.
 */
function parseOperations(ir, rootType, body, knownEnums) {
  const lines = body.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Match: operationName(args): ReturnType
    const opMatch = trimmed.match(/^(\w+)(\([^)]*\))?\s*:\s*(.+?)(?:\s*@.*)?$/);
    if (!opMatch) continue;

    const opName = opMatch[1];
    const argsStr = opMatch[2] || '';
    const returnType = opMatch[3].trim();

    const input = {};
    if (argsStr) {
      // Parse arguments: (name: Type!, other: Type)
      const argBody = argsStr.slice(1, -1); // Remove parens
      const argRegex = /(\w+)\s*:\s*([^,)]+)/g;
      let argMatch;
      while ((argMatch = argRegex.exec(argBody)) !== null) {
        const argName = argMatch[1];
        const argType = argMatch[2].trim();
        const { baseType } = parseGraphQLType(argType);
        input[argName] = isGraphQLScalar(baseType) ? mapGraphQLType(baseType) : baseType;
      }
    }

    const { baseType: outBase } = parseGraphQLType(returnType);
    const output = isGraphQLScalar(outBase) ? mapGraphQLType(outBase) : outBase;

    const method = rootType === 'Query' ? 'QUERY' : rootType === 'Mutation' ? 'MUTATION' : 'SUBSCRIPTION';

    addOperation(ir, {
      name: opName,
      method,
      input,
      output,
      constraints: [],
    });
  }
}

/**
 * Parse a GraphQL type expression like [User!]! into components.
 */
function parseGraphQLType(rawType) {
  let type = rawType.trim();
  const isNullable = !type.endsWith('!');
  type = type.replace(/!+/g, '');
  const isArray = type.startsWith('[');
  type = type.replace(/[\[\]]/g, '').trim();
  return { baseType: type, isArray, isNullable };
}

const GQL_SCALARS = ['String', 'Int', 'Float', 'Boolean', 'ID', 'DateTime', 'Date', 'JSON'];

function isGraphQLScalar(type) {
  return GQL_SCALARS.includes(type);
}

function mapGraphQLType(type) {
  if (type === 'Int' || type === 'Float') return 'number';
  if (type === 'String' || type === 'ID') return 'string';
  if (type === 'Boolean') return 'boolean';
  if (type === 'DateTime') return 'timestamp';
  if (type === 'Date') return 'date';
  if (type === 'JSON') return 'object';
  return 'any';
}

/** Check if content looks like a GraphQL SDL file. */
function canParse(content, filename) {
  if (filename && /\.(graphql|gql)$/i.test(filename)) return true;
  return /type\s+Query\s*\{/.test(content);
}

module.exports = { parse, canParse };
