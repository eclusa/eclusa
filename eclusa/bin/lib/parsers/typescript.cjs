'use strict';

/**
 * TypeScript (.d.ts) and Zod schema parser → Normalized IR
 *
 * Extracts: interfaces/types (→ entities), enums (→ entities),
 * Zod schemas (z.object) (→ entities with fields).
 */

const { createIR, addEntity } = require('../ir.cjs');

/**
 * Parse TypeScript declarations or Zod schemas into IR.
 * @param {string} content - .d.ts or .ts file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'typescript', null);

  // Remove comments
  const cleaned = content
    .replace(/\/\/[^\n]*/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');

  // Extract enums
  const enumRegex = /(?:export\s+)?enum\s+(\w+)\s*\{([^}]*)\}/g;
  let match;
  const knownEnums = {};

  while ((match = enumRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];
    const values = [];

    // Enum members: Name, Name = 'value', Name = 0
    const memberRegex = /(\w+)\s*(?:=\s*(?:'[^']*'|"[^"]*"|\d+))?\s*[,}]?/g;
    let mMatch;
    while ((mMatch = memberRegex.exec(body)) !== null) {
      if (mMatch[1]) values.push(mMatch[1]);
    }

    if (values.length > 0) {
      knownEnums[name] = values;
      addEntity(ir, name, {
        value: { type: 'enum', values },
      });
    }
  }

  // Extract interfaces
  const ifaceRegex = /(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([\w\s,<>]+))?\s*\{/g;
  while ((match = ifaceRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const extendsStr = match[2] || '';
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(cleaned, startIdx);
    if (body === null) continue;

    const { fields, relations } = parseTsFields(body, knownEnums);

    // Record extends as relations
    if (extendsStr) {
      const parents = extendsStr.split(',').map(s => s.trim().replace(/<.*>/, '')).filter(Boolean);
      for (const parent of parents) {
        relations[parent.charAt(0).toLowerCase() + parent.slice(1)] = {
          target: parent,
          cardinality: 'one_to_one',
        };
      }
    }

    addEntity(ir, name, fields, relations);
  }

  // Extract type aliases with object shapes
  const typeRegex = /(?:export\s+)?type\s+(\w+)(?:<[^>]*>)?\s*=\s*\{/g;
  while ((match = typeRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(cleaned, startIdx);
    if (body === null) continue;

    const { fields, relations } = parseTsFields(body, knownEnums);
    addEntity(ir, name, fields, relations);
  }

  // Extract union type aliases (string literal unions → enum)
  const unionRegex = /(?:export\s+)?type\s+(\w+)\s*=\s*((?:'[^']*'|"[^"]*")(?:\s*\|\s*(?:'[^']*'|"[^"]*"))+)\s*;/g;
  while ((match = unionRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const values = match[2].split('|').map(s => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
    if (values.length > 0) {
      knownEnums[name] = values;
      addEntity(ir, name, {
        value: { type: 'enum', values },
      });
    }
  }

  // Extract Zod schemas: const XSchema = z.object({ ... })
  const zodRegex = /(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*z\.object\s*\(\s*\{/g;
  while ((match = zodRegex.exec(cleaned)) !== null) {
    let name = match[1];
    // Clean up common naming: UserSchema → User
    name = name.replace(/Schema$/, '');

    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(cleaned, startIdx);
    if (body === null) continue;

    const { fields, relations } = parseZodFields(body, knownEnums);
    addEntity(ir, name, fields, relations);
  }

  return ir;
}

/**
 * Parse TypeScript object fields.
 */
function parseTsFields(body, knownEnums) {
  const fields = {};
  const relations = {};

  const lines = body.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('[')) continue;

    // Match: fieldName: Type; or fieldName?: Type;
    const fieldMatch = trimmed.match(/^(?:readonly\s+)?(\w+)(\?)?:\s*(.+?)\s*[;,]?\s*$/);
    if (!fieldMatch) continue;

    const fieldName = fieldMatch[1];
    const isOptional = !!fieldMatch[2];
    let rawType = fieldMatch[3].trim();

    // Remove trailing semicolons/commas
    rawType = rawType.replace(/[;,]\s*$/, '').trim();

    if (knownEnums[rawType]) {
      fields[fieldName] = {
        type: 'enum',
        values: knownEnums[rawType],
        constraint: isOptional ? 'nullable' : null,
      };
    } else if (isTsScalar(rawType)) {
      fields[fieldName] = {
        type: mapTsType(rawType),
        constraint: isOptional ? 'nullable' : null,
      };
    } else if (rawType.endsWith('[]')) {
      const baseType = rawType.slice(0, -2);
      if (isTsScalar(baseType)) {
        fields[fieldName] = {
          type: 'array',
          constraint: isOptional ? 'nullable' : null,
        };
      } else {
        relations[fieldName] = {
          target: baseType,
          cardinality: 'one_to_many',
        };
      }
    } else if (rawType.startsWith('Array<')) {
      const inner = rawType.match(/Array<(.+)>/);
      if (inner) {
        const baseType = inner[1].trim();
        if (isTsScalar(baseType)) {
          fields[fieldName] = {
            type: 'array',
            constraint: isOptional ? 'nullable' : null,
          };
        } else {
          relations[fieldName] = {
            target: baseType,
            cardinality: 'one_to_many',
          };
        }
      }
    } else if (rawType.includes('|')) {
      // Union types — check if it's nullable union (Type | null | undefined)
      const parts = rawType.split('|').map(s => s.trim()).filter(s => s !== 'null' && s !== 'undefined');
      if (parts.length === 1 && isTsScalar(parts[0])) {
        fields[fieldName] = {
          type: mapTsType(parts[0]),
          constraint: 'nullable',
        };
      } else if (parts.every(p => p.startsWith("'") || p.startsWith('"'))) {
        // String literal union → enum
        const values = parts.map(p => p.replace(/^['"]|['"]$/g, ''));
        fields[fieldName] = {
          type: 'enum',
          values,
          constraint: isOptional ? 'nullable' : null,
        };
      } else {
        fields[fieldName] = {
          type: 'any',
          constraint: isOptional ? 'nullable' : null,
        };
      }
    } else {
      // Non-scalar type → relation
      const cleanType = rawType.replace(/<.*>/, '').trim();
      if (cleanType && /^[A-Z]/.test(cleanType)) {
        relations[fieldName] = {
          target: cleanType,
          cardinality: 'many_to_one',
        };
      } else {
        fields[fieldName] = {
          type: mapTsType(rawType),
          constraint: isOptional ? 'nullable' : null,
        };
      }
    }
  }

  return { fields, relations };
}

/**
 * Parse Zod schema fields.
 */
function parseZodFields(body, knownEnums) {
  const fields = {};
  const relations = {};

  const lines = body.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('//')) continue;

    // Match: fieldName: z.string(), z.number(), etc.
    const fieldMatch = trimmed.match(/^(\w+)\s*:\s*z\.(.+?)\s*[,}]?\s*$/);
    if (!fieldMatch) continue;

    const fieldName = fieldMatch[1];
    const zodChain = fieldMatch[2];

    const isOptional = zodChain.includes('.optional()') || zodChain.includes('.nullable()');
    const isArray = zodChain.startsWith('array(');

    let type = 'any';
    if (zodChain.startsWith('string')) type = 'string';
    else if (zodChain.startsWith('number') || zodChain.startsWith('int')) type = 'number';
    else if (zodChain.startsWith('boolean')) type = 'boolean';
    else if (zodChain.startsWith('date')) type = 'timestamp';
    else if (zodChain.startsWith('object')) type = 'object';
    else if (zodChain.startsWith('record')) type = 'object';
    else if (isArray) type = 'array';
    else if (zodChain.startsWith('enum')) {
      type = 'enum';
      const enumMatch = zodChain.match(/enum\(\[([^\]]+)\]/);
      if (enumMatch) {
        const values = enumMatch[1].split(',').map(s => s.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
        fields[fieldName] = {
          type: 'enum',
          values,
          constraint: isOptional ? 'nullable' : null,
        };
        continue;
      }
    } else if (zodChain.startsWith('nativeEnum')) {
      type = 'enum';
      const refMatch = zodChain.match(/nativeEnum\((\w+)\)/);
      if (refMatch && knownEnums[refMatch[1]]) {
        fields[fieldName] = {
          type: 'enum',
          values: knownEnums[refMatch[1]],
          constraint: isOptional ? 'nullable' : null,
        };
        continue;
      }
    } else if (zodChain.startsWith('literal')) {
      type = 'any';
    }

    fields[fieldName] = {
      type,
      constraint: isOptional ? 'nullable' : null,
    };
  }

  return { fields, relations };
}

/**
 * Extract text inside braces starting from a position (after the opening brace).
 */
function extractBraceBlock(content, startIdx) {
  let depth = 1;
  let i = startIdx;
  while (i < content.length && depth > 0) {
    if (content[i] === '{') depth++;
    else if (content[i] === '}') depth--;
    i++;
  }
  if (depth !== 0) return null;
  return content.slice(startIdx, i - 1);
}

const TS_SCALARS = ['string', 'number', 'boolean', 'bigint', 'symbol', 'void', 'never', 'any', 'unknown', 'Date', 'Buffer'];

function isTsScalar(type) {
  return TS_SCALARS.includes(type);
}

function mapTsType(type) {
  if (type === 'string') return 'string';
  if (type === 'number' || type === 'bigint') return 'number';
  if (type === 'boolean') return 'boolean';
  if (type === 'Date') return 'timestamp';
  if (type === 'Buffer') return 'binary';
  if (type === 'any' || type === 'unknown') return 'any';
  if (type === 'object' || type === 'Record') return 'object';
  return 'any';
}

/** Check if content looks like TypeScript declarations or Zod schemas. */
function canParse(content, filename) {
  if (filename && filename.endsWith('.d.ts')) return true;
  if (/export\s+(interface|type|enum)\s+\w+/.test(content)) return true;
  if (/z\.object\s*\(/.test(content)) return true;
  return false;
}

module.exports = { parse, canParse };
