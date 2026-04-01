'use strict';

/**
 * Go source file parser → Normalized IR
 *
 * Extracts: structs (→ entities), interfaces (→ operations),
 * type aliases, and struct tags for field naming.
 */

const { createIR, addEntity, addOperation } = require('../ir.cjs');

/**
 * Parse a Go source file string into IR.
 * @param {string} content - .go file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'go', null);

  // Remove comments
  const cleaned = content
    .replace(/\/\/[^\n]*/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '');

  // Extract const blocks for iota-style enums
  const knownEnums = {};
  parseGoEnums(cleaned, ir, knownEnums);

  // Extract structs
  parseGoStructs(cleaned, ir, knownEnums);

  // Extract interfaces → operations
  parseGoInterfaces(cleaned, ir);

  return ir;
}

/**
 * Parse Go "enum" patterns (const blocks with iota or string constants).
 */
function parseGoEnums(content, ir, knownEnums) {
  // Pattern 1: type Name string/int followed by const block
  const typeAliasRegex = /type\s+(\w+)\s+(string|int|int64|uint)\s*\n/g;
  let match;
  const enumTypes = {};

  while ((match = typeAliasRegex.exec(content)) !== null) {
    enumTypes[match[1]] = match[2];
  }

  // Pattern 2: const block with typed constants
  const constBlockRegex = /const\s*\(\s*\n([\s\S]*?)\)/g;
  while ((match = constBlockRegex.exec(content)) !== null) {
    const body = match[1];
    const lines = body.split('\n');
    let currentType = null;
    const groupedValues = {};

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Match: Name Type = value  or  Name = iota  or  Name
      const constMatch = trimmed.match(/^(\w+)\s+(\w+)\s*=\s*(.+)$/);
      if (constMatch) {
        const constName = constMatch[1];
        currentType = constMatch[2];
        if (enumTypes[currentType]) {
          if (!groupedValues[currentType]) groupedValues[currentType] = [];
          groupedValues[currentType].push(constName);
        }
        continue;
      }

      // Continuation with same type: Name = "value" or just Name
      if (currentType && enumTypes[currentType]) {
        const contMatch = trimmed.match(/^(\w+)(?:\s*=\s*.+)?$/);
        if (contMatch && contMatch[1] !== '_') {
          if (!groupedValues[currentType]) groupedValues[currentType] = [];
          groupedValues[currentType].push(contMatch[1]);
        }
      }
    }

    for (const [typeName, values] of Object.entries(groupedValues)) {
      if (values.length > 0) {
        knownEnums[typeName] = values;
        addEntity(ir, typeName, {
          value: { type: 'enum', values },
        });
      }
    }
  }
}

/**
 * Parse Go struct definitions.
 */
function parseGoStructs(content, ir, knownEnums) {
  const structRegex = /type\s+(\w+)\s+struct\s*\{/g;
  let match;

  while ((match = structRegex.exec(content)) !== null) {
    const name = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(content, startIdx);
    if (body === null) continue;

    const fields = {};
    const relations = {};

    const lines = body.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Embedded struct (no field name): TypeName or *TypeName
      const embedMatch = trimmed.match(/^\*?(\w+)(?:\s+`[^`]*`)?$/);
      if (embedMatch && /^[A-Z]/.test(embedMatch[1]) && !trimmed.includes(' ')) {
        const embeddedType = embedMatch[1];
        relations[embeddedType.charAt(0).toLowerCase() + embeddedType.slice(1)] = {
          target: embeddedType,
          cardinality: 'one_to_one',
        };
        continue;
      }

      // Regular field: FieldName Type `json:"name"`
      const fieldMatch = trimmed.match(/^(\w+)\s+(.+?)(?:\s+`([^`]*)`)?$/);
      if (!fieldMatch) continue;

      const fieldName = fieldMatch[1];
      const rawType = fieldMatch[2].trim();
      const tags = fieldMatch[3] || '';

      // Skip unexported fields (lowercase first letter)
      if (/^[a-z]/.test(fieldName)) continue;

      // Extract json tag for field naming
      let jsonName = null;
      const jsonTag = tags.match(/json:"([^"]+)"/);
      if (jsonTag) {
        const jsonParts = jsonTag[1].split(',');
        jsonName = jsonParts[0];
        if (jsonName === '-') continue; // Field is explicitly excluded
      }

      const displayName = jsonName || camelCase(fieldName);
      const { baseType, isPointer, isSlice, isMap } = parseGoType(rawType);

      if (knownEnums[baseType]) {
        fields[displayName] = {
          type: 'enum',
          values: knownEnums[baseType],
          constraint: isPointer ? 'nullable' : null,
        };
      } else if (isGoScalar(baseType)) {
        fields[displayName] = {
          type: isSlice ? 'array' : (isMap ? 'object' : mapGoType(baseType)),
          constraint: isPointer ? 'nullable' : null,
        };
      } else if (isSlice) {
        relations[displayName] = {
          target: baseType,
          cardinality: 'one_to_many',
        };
      } else if (isMap) {
        fields[displayName] = {
          type: 'object',
          constraint: isPointer ? 'nullable' : null,
        };
      } else {
        // Non-scalar type → relation
        relations[displayName] = {
          target: baseType,
          cardinality: isPointer ? 'many_to_one' : 'one_to_one',
        };
      }
    }

    addEntity(ir, name, fields, relations);
  }
}

/**
 * Parse Go interface definitions → operations.
 */
function parseGoInterfaces(content, ir) {
  const ifaceRegex = /type\s+(\w+)\s+interface\s*\{/g;
  let match;

  while ((match = ifaceRegex.exec(content)) !== null) {
    const name = match[1];
    const startIdx = match.index + match[0].length;
    const body = extractBraceBlock(content, startIdx);
    if (body === null) continue;

    const lines = body.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Embedded interface
      if (/^\w+$/.test(trimmed)) continue;

      // Method: MethodName(params) (returns)  or  MethodName(params) return
      const methodMatch = trimmed.match(/^(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]*)\)|(\S+))?/);
      if (!methodMatch) continue;

      const methodName = methodMatch[1];
      const params = methodMatch[2];
      const multiReturn = methodMatch[3];
      const singleReturn = methodMatch[4];

      const input = {};
      if (params) {
        const paramParts = splitGoParams(params);
        for (const p of paramParts) {
          const pMatch = p.trim().match(/(\w+)\s+(.+)/);
          if (pMatch) {
            const { baseType } = parseGoType(pMatch[2].trim());
            input[pMatch[1]] = isGoScalar(baseType) ? mapGoType(baseType) : baseType;
          }
        }
      }

      let output = null;
      if (singleReturn && singleReturn !== 'error') {
        const { baseType } = parseGoType(singleReturn);
        output = isGoScalar(baseType) ? mapGoType(baseType) : baseType;
      } else if (multiReturn) {
        // First non-error return type
        const returns = multiReturn.split(',').map(s => s.trim()).filter(s => s !== 'error');
        if (returns.length > 0) {
          const { baseType } = parseGoType(returns[0]);
          output = isGoScalar(baseType) ? mapGoType(baseType) : baseType;
        }
      }

      addOperation(ir, {
        name: `${name}.${methodName}`,
        method: 'FN',
        input,
        output,
        constraints: [],
      });
    }
  }
}

/**
 * Split Go function parameters, handling nested types.
 */
function splitGoParams(params) {
  const parts = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < params.length; i++) {
    if (params[i] === '(' || params[i] === '[') depth++;
    else if (params[i] === ')' || params[i] === ']') depth--;
    else if (params[i] === ',' && depth === 0) {
      parts.push(params.slice(start, i));
      start = i + 1;
    }
  }
  parts.push(params.slice(start));
  return parts.filter(s => s.trim());
}

/**
 * Parse a Go type expression, unwrapping *, [], map.
 */
function parseGoType(rawType) {
  let type = rawType.trim();
  let isPointer = false;
  let isSlice = false;
  let isMap = false;

  // Handle pointer: *Type
  if (type.startsWith('*')) {
    isPointer = true;
    type = type.slice(1).trim();
  }

  // Handle slice: []Type
  if (type.startsWith('[]')) {
    isSlice = true;
    type = type.slice(2).trim();
    // Handle pointer inside slice: []*Type
    if (type.startsWith('*')) {
      type = type.slice(1).trim();
    }
  }

  // Handle map: map[Key]Value
  const mapMatch = type.match(/^map\[.+?\](.+)$/);
  if (mapMatch) {
    isMap = true;
    type = mapMatch[1].trim();
    if (type.startsWith('*')) type = type.slice(1).trim();
  }

  // Strip package prefix: pkg.Type → Type
  if (type.includes('.')) {
    type = type.split('.').pop();
  }

  return { baseType: type, isPointer, isSlice, isMap };
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

/**
 * Convert PascalCase to camelCase.
 */
function camelCase(str) {
  return str.charAt(0).toLowerCase() + str.slice(1);
}

const GO_SCALARS = [
  'string',
  'int', 'int8', 'int16', 'int32', 'int64',
  'uint', 'uint8', 'uint16', 'uint32', 'uint64',
  'float32', 'float64',
  'bool',
  'byte', 'rune',
  'complex64', 'complex128',
  'error',
  'interface{}', 'any',
];

function isGoScalar(type) {
  return GO_SCALARS.includes(type);
}

function mapGoType(type) {
  if (type === 'string') return 'string';
  if (['int', 'int8', 'int16', 'int32', 'int64',
       'uint', 'uint8', 'uint16', 'uint32', 'uint64',
       'float32', 'float64', 'byte', 'rune',
       'complex64', 'complex128'].includes(type)) return 'number';
  if (type === 'bool') return 'boolean';
  if (type === 'error') return 'string';
  if (type === 'interface{}' || type === 'any') return 'any';
  return 'any';
}

/** Check if content looks like a Go source file. */
function canParse(content, filename) {
  if (filename && filename.endsWith('.go')) return true;
  return /type\s+\w+\s+struct\s*\{/.test(content);
}

module.exports = { parse, canParse };
