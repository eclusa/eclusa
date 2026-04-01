'use strict';

/**
 * Rust source file parser → Normalized IR
 *
 * Extracts: structs (→ entities), enums (→ entities with variants),
 * impl blocks (→ detect relations/methods).
 */

const { createIR, addEntity, addOperation } = require('../ir.cjs');

/**
 * Parse a Rust source file string into IR.
 * @param {string} content - .rs file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'rust', null);

  // Remove comments
  const cleaned = content
    .replace(/\/\/[^\n]*/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');

  // Extract enums first
  const knownEnums = {};
  parseRustEnums(cleaned, ir, knownEnums);

  // Extract structs
  parseRustStructs(cleaned, ir, knownEnums);

  // Extract impl blocks for operations
  parseRustImpls(cleaned, ir);

  return ir;
}

/**
 * Parse Rust enum definitions.
 */
function parseRustEnums(content, ir, knownEnums) {
  const enumStartRegex = /(?:pub(?:\([\w:]+\))?\s+)?enum\s+(\w+)(?:<[^>]*>)?\s*\{/g;
  let match;

  while ((match = enumStartRegex.exec(content)) !== null) {
    const name = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(content, startIdx);
    if (body === null) continue;

    const values = [];
    const fields = {};
    const relations = {};
    let hasStructVariants = false;

    // Parse variants
    const lines = body.split(',');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Simple variant: Name
      const simpleMatch = trimmed.match(/^#\[.*?\]\s*(\w+)$|^(\w+)$/);
      if (simpleMatch) {
        values.push(simpleMatch[1] || simpleMatch[2]);
        continue;
      }

      // Tuple variant: Name(Type, Type)
      const tupleMatch = trimmed.match(/^(?:#\[.*?\]\s*)?(\w+)\s*\([^)]+\)/);
      if (tupleMatch) {
        values.push(tupleMatch[1]);
        continue;
      }

      // Struct variant: Name { field: Type, ... }
      const structMatch = trimmed.match(/^(?:#\[.*?\]\s*)?(\w+)\s*\{/);
      if (structMatch) {
        values.push(structMatch[1]);
        hasStructVariants = true;
        continue;
      }
    }

    if (values.length > 0) {
      if (hasStructVariants) {
        // Complex enum — treat as entity with enum values plus fields
        knownEnums[name] = values;
        addEntity(ir, name, {
          value: { type: 'enum', values },
        });
      } else {
        knownEnums[name] = values;
        addEntity(ir, name, {
          value: { type: 'enum', values },
        });
      }
    }
  }
}

/**
 * Parse Rust struct definitions.
 */
function parseRustStructs(content, ir, knownEnums) {
  // Named structs: pub struct Name { ... }
  const structStartRegex = /(?:pub(?:\([\w:]+\))?\s+)?struct\s+(\w+)(?:<[^>]*>)?\s*\{/g;
  let match;

  while ((match = structStartRegex.exec(content)) !== null) {
    const name = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(content, startIdx);
    if (body === null) continue;

    const fields = {};
    const relations = {};

    // Parse fields
    const lines = body.split(',');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#[')) continue;

      // Remove attributes on the same line
      const cleaned = trimmed.replace(/#\[.*?\]\s*/g, '').trim();
      if (!cleaned) continue;

      // Match: pub field_name: Type or field_name: Type
      const fieldMatch = cleaned.match(/^(?:pub(?:\([\w:]+\))?\s+)?(\w+)\s*:\s*(.+)$/);
      if (!fieldMatch) continue;

      const fieldName = fieldMatch[1];
      const rawType = fieldMatch[2].trim();

      const { baseType, isOption, isVec, isBox } = parseRustType(rawType);

      if (knownEnums[baseType]) {
        fields[fieldName] = {
          type: 'enum',
          values: knownEnums[baseType],
          constraint: isOption ? 'nullable' : null,
        };
      } else if (isRustScalar(baseType)) {
        fields[fieldName] = {
          type: isVec ? 'array' : mapRustType(baseType),
          constraint: isOption ? 'nullable' : null,
        };
      } else if (isVec) {
        relations[fieldName] = {
          target: baseType,
          cardinality: 'one_to_many',
        };
      } else if (isBox || isOption) {
        if (isRustScalar(baseType)) {
          fields[fieldName] = {
            type: mapRustType(baseType),
            constraint: 'nullable',
          };
        } else {
          relations[fieldName] = {
            target: baseType,
            cardinality: 'many_to_one',
          };
        }
      } else {
        // Non-scalar, non-wrapper type → relation
        relations[fieldName] = {
          target: baseType,
          cardinality: 'many_to_one',
        };
      }
    }

    addEntity(ir, name, fields, relations);
  }

  // Tuple structs: pub struct Name(Type);
  const tupleStructRegex = /(?:pub(?:\([\w:]+\))?\s+)?struct\s+(\w+)(?:<[^>]*>)?\s*\(([^)]+)\)\s*;/g;
  while ((match = tupleStructRegex.exec(content)) !== null) {
    const name = match[1];
    const innerTypes = match[2].split(',').map(s => s.trim().replace(/pub\s+/, ''));

    const fields = {};
    innerTypes.forEach((rawType, idx) => {
      const { baseType, isVec } = parseRustType(rawType);
      fields[`_${idx}`] = {
        type: isVec ? 'array' : mapRustType(baseType),
        constraint: null,
      };
    });

    addEntity(ir, name, fields);
  }
}

/**
 * Parse impl blocks for method signatures.
 */
function parseRustImpls(content, ir) {
  const implRegex = /impl(?:<[^>]*>)?\s+(\w+)(?:<[^>]*>)?\s*\{/g;
  let match;

  while ((match = implRegex.exec(content)) !== null) {
    const typeName = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(content, startIdx);
    if (body === null) continue;

    // Extract pub fn signatures
    const fnRegex = /pub\s+(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)(?:\s*->\s*([^\n{]+))?/g;
    let fnMatch;
    while ((fnMatch = fnRegex.exec(body)) !== null) {
      const fnName = fnMatch[1];
      const params = fnMatch[2];
      const returnType = fnMatch[3] ? fnMatch[3].trim() : null;

      // Skip getters/setters and standard trait methods
      if (['new', 'default', 'clone', 'fmt', 'eq', 'hash'].includes(fnName)) continue;

      const input = {};
      // Parse parameters (skip &self, &mut self)
      const paramParts = params.split(',');
      for (const p of paramParts) {
        const trimmed = p.trim();
        if (trimmed === '&self' || trimmed === '&mut self' || trimmed === 'self' || trimmed === 'mut self') continue;
        const paramMatch = trimmed.match(/(\w+)\s*:\s*(.+)/);
        if (paramMatch) {
          const { baseType } = parseRustType(paramMatch[2].trim());
          input[paramMatch[1]] = mapRustType(baseType);
        }
      }

      let output = null;
      if (returnType) {
        const { baseType } = parseRustType(returnType.replace(/\s*\{?\s*$/, ''));
        output = isRustScalar(baseType) ? mapRustType(baseType) : baseType;
      }

      addOperation(ir, {
        name: `${typeName}::${fnName}`,
        method: 'FN',
        input,
        output,
        constraints: [],
      });
    }
  }
}

/**
 * Parse a Rust type expression, unwrapping Option, Vec, Box, etc.
 */
function parseRustType(rawType) {
  let type = rawType.trim();
  let isOption = false;
  let isVec = false;
  let isBox = false;

  // Unwrap Option<T>
  const optionMatch = type.match(/^Option\s*<\s*(.+)\s*>$/);
  if (optionMatch) {
    isOption = true;
    type = optionMatch[1].trim();
  }

  // Unwrap Vec<T>
  const vecMatch = type.match(/^Vec\s*<\s*(.+)\s*>$/);
  if (vecMatch) {
    isVec = true;
    type = vecMatch[1].trim();
  }

  // Unwrap Box<T>
  const boxMatch = type.match(/^Box\s*<\s*(.+)\s*>$/);
  if (boxMatch) {
    isBox = true;
    type = boxMatch[1].trim();
  }

  // Unwrap Arc<T>, Rc<T>, Mutex<T>, RwLock<T>
  const wrapperMatch = type.match(/^(?:Arc|Rc|Mutex|RwLock)\s*<\s*(.+)\s*>$/);
  if (wrapperMatch) {
    type = wrapperMatch[1].trim();
  }

  // Handle references: &T, &mut T, &'a T
  type = type.replace(/^&(?:'[\w]+\s+)?(?:mut\s+)?/, '');

  // Handle HashMap<K, V>
  const hashMapMatch = type.match(/^HashMap\s*<\s*.+\s*,\s*(.+)\s*>$/);
  if (hashMapMatch) {
    return { baseType: hashMapMatch[1].trim(), isOption, isVec: false, isBox: false };
  }

  // Strip remaining generics for base type name
  const baseType = type.replace(/<.*>/, '').trim();

  return { baseType, isOption, isVec, isBox };
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

const RUST_SCALARS = [
  'String', '&str', 'str',
  'i8', 'i16', 'i32', 'i64', 'i128', 'isize',
  'u8', 'u16', 'u32', 'u64', 'u128', 'usize',
  'f32', 'f64',
  'bool',
  'char',
];

function isRustScalar(type) {
  return RUST_SCALARS.includes(type);
}

function mapRustType(type) {
  if (['String', '&str', 'str', 'char'].includes(type)) return 'string';
  if (['i8', 'i16', 'i32', 'i64', 'i128', 'isize',
       'u8', 'u16', 'u32', 'u64', 'u128', 'usize',
       'f32', 'f64'].includes(type)) return 'number';
  if (type === 'bool') return 'boolean';
  return 'any';
}

/** Check if content looks like a Rust source file. */
function canParse(content, filename) {
  if (filename && filename.endsWith('.rs')) return true;
  return /pub\s+struct\s+\w+/.test(content);
}

module.exports = { parse, canParse };
