'use strict';

/**
 * Protocol Buffers (.proto) parser → Normalized IR
 *
 * Extracts: messages (→ entities), services (→ operations),
 * enums (→ entities with enum values), nested messages (→ relations).
 */

const { createIR, addEntity, addOperation } = require('../ir.cjs');

/**
 * Parse a .proto file string into IR.
 * @param {string} content - .proto file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'protobuf', null);

  // Remove comments
  const cleaned = content
    .replace(/\/\/[^\n]*/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');

  // Extract package name for context
  const pkgMatch = cleaned.match(/package\s+([\w.]+)\s*;/);
  const pkg = pkgMatch ? pkgMatch[1] : null;

  // Extract enums (top-level)
  const enumRegex = /enum\s+(\w+)\s*\{([^}]*)\}/g;
  let match;
  const knownEnums = {};

  while ((match = enumRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];
    const values = [];

    const valueRegex = /(\w+)\s*=\s*\d+/g;
    let vMatch;
    while ((vMatch = valueRegex.exec(body)) !== null) {
      values.push(vMatch[1]);
    }

    knownEnums[name] = values;
    addEntity(ir, name, {
      value: { type: 'enum', values },
    });
  }

  // Extract messages
  parseMessages(cleaned, ir, knownEnums);

  // Extract services → operations
  const serviceRegex = /service\s+(\w+)\s*\{([^}]*)\}/g;
  while ((match = serviceRegex.exec(cleaned)) !== null) {
    const serviceName = match[1];
    const body = match[2];

    const rpcRegex = /rpc\s+(\w+)\s*\(\s*(stream\s+)?(\w+)\s*\)\s*returns\s*\(\s*(stream\s+)?(\w+)\s*\)/g;
    let rpcMatch;
    while ((rpcMatch = rpcRegex.exec(body)) !== null) {
      const methodName = rpcMatch[1];
      const inputStreaming = !!rpcMatch[2];
      const inputType = rpcMatch[3];
      const outputStreaming = !!rpcMatch[4];
      const outputType = rpcMatch[5];

      addOperation(ir, {
        name: `${serviceName}.${methodName}`,
        method: 'RPC',
        input: { _body: inputType, _streaming: inputStreaming ? 'true' : 'false' },
        output: outputType,
        constraints: outputStreaming ? ['server_streaming'] : [],
      });
    }
  }

  return ir;
}

/**
 * Parse message definitions (handles nesting by processing outermost first).
 */
function parseMessages(content, ir, knownEnums) {
  // Match message blocks — use a manual brace-counting approach for nesting
  const messageStartRegex = /message\s+(\w+)\s*\{/g;
  let match;

  while ((match = messageStartRegex.exec(content)) !== null) {
    const name = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(content, startIdx);
    if (body === null) continue;

    const fields = {};
    const relations = {};

    // Extract nested messages (they become related entities)
    const nestedMsgRegex = /message\s+(\w+)\s*\{/g;
    let nestedMatch;
    while ((nestedMatch = nestedMsgRegex.exec(body)) !== null) {
      const nestedName = nestedMatch[1];
      relations[nestedName.charAt(0).toLowerCase() + nestedName.slice(1)] = {
        target: nestedName,
        cardinality: 'one_to_one',
      };
    }

    // Extract nested enums
    const nestedEnumRegex = /enum\s+(\w+)\s*\{([^}]*)\}/g;
    let nestedEnumMatch;
    while ((nestedEnumMatch = nestedEnumRegex.exec(body)) !== null) {
      const eName = nestedEnumMatch[1];
      const eBody = nestedEnumMatch[2];
      const values = [];
      const valueRegex = /(\w+)\s*=\s*\d+/g;
      let vMatch;
      while ((vMatch = valueRegex.exec(eBody)) !== null) {
        values.push(vMatch[1]);
      }
      knownEnums[eName] = values;
    }

    // Remove nested message/enum blocks from body before parsing fields
    const fieldBody = body
      .replace(/message\s+\w+\s*\{[^}]*\}/g, '')
      .replace(/enum\s+\w+\s*\{[^}]*\}/g, '');

    // Parse fields
    const fieldRegex = /(?:(repeated|optional|required)\s+)?(\w+(?:\.\w+)*)\s+(\w+)\s*=\s*(\d+)/g;
    let fieldMatch;
    while ((fieldMatch = fieldRegex.exec(fieldBody)) !== null) {
      const modifier = fieldMatch[1] || '';
      const fieldType = fieldMatch[2];
      const fieldName = fieldMatch[3];

      if (knownEnums[fieldType]) {
        fields[fieldName] = {
          type: 'enum',
          values: knownEnums[fieldType],
          constraint: modifier === 'optional' ? 'nullable' : null,
        };
      } else if (isProtoScalar(fieldType)) {
        fields[fieldName] = {
          type: modifier === 'repeated' ? 'array' : mapProtoType(fieldType),
          constraint: modifier === 'optional' ? 'nullable' : null,
        };
      } else {
        // Reference to another message type
        if (modifier === 'repeated') {
          relations[fieldName] = {
            target: fieldType,
            cardinality: 'one_to_many',
          };
        } else {
          relations[fieldName] = {
            target: fieldType,
            cardinality: 'many_to_one',
          };
        }
      }
    }

    // Parse map fields: map<KeyType, ValueType> field_name = N;
    const mapRegex = /map\s*<\s*(\w+)\s*,\s*(\w+)\s*>\s+(\w+)\s*=\s*\d+/g;
    let mapMatch;
    while ((mapMatch = mapRegex.exec(fieldBody)) !== null) {
      const valueType = mapMatch[2];
      const mapFieldName = mapMatch[3];
      fields[mapFieldName] = {
        type: 'object',
        constraint: null,
      };
      // If value is a message type, also record as relation
      if (!isProtoScalar(valueType) && !knownEnums[valueType]) {
        relations[mapFieldName] = {
          target: valueType,
          cardinality: 'one_to_many',
        };
      }
    }

    // Parse oneof fields
    const oneofRegex = /oneof\s+(\w+)\s*\{([^}]*)\}/g;
    let oneofMatch;
    while ((oneofMatch = oneofRegex.exec(fieldBody)) !== null) {
      const oneofBody = oneofMatch[2];
      const oneofFieldRegex = /(\w+(?:\.\w+)*)\s+(\w+)\s*=\s*\d+/g;
      let ofMatch;
      while ((ofMatch = oneofFieldRegex.exec(oneofBody)) !== null) {
        const ofType = ofMatch[1];
        const ofName = ofMatch[2];
        if (isProtoScalar(ofType)) {
          fields[ofName] = {
            type: mapProtoType(ofType),
            constraint: 'nullable',
          };
        } else {
          relations[ofName] = {
            target: ofType,
            cardinality: 'many_to_one',
          };
        }
      }
    }

    addEntity(ir, name, fields, relations);
  }
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

const PROTO_SCALARS = [
  'double', 'float', 'int32', 'int64', 'uint32', 'uint64',
  'sint32', 'sint64', 'fixed32', 'fixed64', 'sfixed32', 'sfixed64',
  'bool', 'string', 'bytes',
];

function isProtoScalar(type) {
  return PROTO_SCALARS.includes(type);
}

function mapProtoType(type) {
  if (['int32', 'int64', 'uint32', 'uint64', 'sint32', 'sint64',
       'fixed32', 'fixed64', 'sfixed32', 'sfixed64',
       'double', 'float'].includes(type)) return 'number';
  if (type === 'string') return 'string';
  if (type === 'bool') return 'boolean';
  if (type === 'bytes') return 'binary';
  return 'any';
}

/** Check if content looks like a Protocol Buffers file. */
function canParse(content, filename) {
  if (filename && filename.endsWith('.proto')) return true;
  return /syntax\s*=\s*"proto[23]"/.test(content);
}

module.exports = { parse, canParse };
