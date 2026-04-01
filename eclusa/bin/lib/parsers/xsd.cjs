'use strict';

/**
 * XML Schema (XSD) parser → Normalized IR
 *
 * Extracts: complexTypes (→ entities), elements (→ fields),
 * simpleTypes with enumerations (→ enums), sequences/choices (→ field ordering).
 */

const { createIR, addEntity } = require('../ir.cjs');

/**
 * Parse an XSD file string into IR.
 * @param {string} content - .xsd file content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'xsd', null);

  // Detect namespace prefix (xs: or xsd: or no prefix)
  const nsMatch = content.match(/<(\w+):schema\b/);
  const ns = nsMatch ? nsMatch[1] + ':' : '';

  // Remove XML comments
  const cleaned = content.replace(/<!--[\s\S]*?-->/g, '');

  // Extract simpleTypes with enumerations first
  const knownEnums = {};
  const simpleTypeRegex = new RegExp(`<${ns}simpleType\\s+name="(\\w+)"[^>]*>([\\s\\S]*?)</${ns}simpleType>`, 'g');
  let match;

  while ((match = simpleTypeRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];

    // Check for enumeration restrictions
    const enumRegex = new RegExp(`<${ns}enumeration\\s+value="([^"]*)"`, 'g');
    const values = [];
    let enumMatch;
    while ((enumMatch = enumRegex.exec(body)) !== null) {
      values.push(enumMatch[1]);
    }

    if (values.length > 0) {
      knownEnums[name] = values;
      addEntity(ir, name, {
        value: { type: 'enum', values },
      });
    }
  }

  // Extract complexTypes
  const complexTypeRegex = new RegExp(`<${ns}complexType\\s+name="(\\w+)"[^>]*>([\\s\\S]*?)</${ns}complexType>`, 'g');
  while ((match = complexTypeRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];
    const { fields, relations } = parseComplexTypeBody(body, ns, knownEnums);
    addEntity(ir, name, fields, relations);
  }

  // Extract top-level elements with inline complexType
  const elementRegex = new RegExp(`<${ns}element\\s+name="(\\w+)"[^/>]*>([\\s\\S]*?)</${ns}element>`, 'g');
  while ((match = elementRegex.exec(cleaned)) !== null) {
    const name = match[1];
    const body = match[2];

    // Check for inline complexType
    const inlineComplex = new RegExp(`<${ns}complexType[^>]*>([\\s\\S]*?)</${ns}complexType>`);
    const inlineMatch = body.match(inlineComplex);
    if (inlineMatch) {
      const { fields, relations } = parseComplexTypeBody(inlineMatch[1], ns, knownEnums);
      addEntity(ir, name, fields, relations);
    }
  }

  return ir;
}

/**
 * Parse the body of a complexType into fields and relations.
 */
function parseComplexTypeBody(body, ns, knownEnums) {
  const fields = {};
  const relations = {};

  // Extract elements from sequence, choice, or all
  const elementRegex = new RegExp(
    `<${ns}element\\s+([^>]*?)\\s*/?>`,
    'g'
  );
  let match;

  while ((match = elementRegex.exec(body)) !== null) {
    const attrs = match[1];

    const nameMatch = attrs.match(/name="(\w+)"/);
    if (!nameMatch) continue;
    const fieldName = nameMatch[1];

    const typeMatch = attrs.match(/type="([^"]+)"/);
    const minOccurs = attrs.match(/minOccurs="(\d+)"/);
    const maxOccurs = attrs.match(/maxOccurs="([^"]+)"/);

    const isOptional = minOccurs && minOccurs[1] === '0';
    const isArray = maxOccurs && (maxOccurs[1] === 'unbounded' || parseInt(maxOccurs[1], 10) > 1);

    if (typeMatch) {
      const rawType = typeMatch[1];
      // Strip namespace prefix from type
      const typeName = rawType.includes(':') ? rawType.split(':').pop() : rawType;

      if (knownEnums[typeName]) {
        fields[fieldName] = {
          type: 'enum',
          values: knownEnums[typeName],
          constraint: isOptional ? 'nullable' : null,
        };
      } else if (isXsdBuiltinType(typeName)) {
        fields[fieldName] = {
          type: isArray ? 'array' : mapXsdType(typeName),
          constraint: isOptional ? 'nullable' : (minOccurs ? null : 'required'),
        };
      } else {
        // Complex type reference → relation
        relations[fieldName] = {
          target: typeName,
          cardinality: isArray ? 'one_to_many' : 'many_to_one',
        };
      }
    } else {
      // Element without explicit type — may have inline simpleType or complexType
      fields[fieldName] = {
        type: 'any',
        constraint: isOptional ? 'nullable' : null,
      };
    }
  }

  // Extract attributes
  const attrRegex = new RegExp(`<${ns}attribute\\s+([^>]*?)\\s*/?>`, 'g');
  while ((match = attrRegex.exec(body)) !== null) {
    const attrs = match[1];
    const nameMatch = attrs.match(/name="(\w+)"/);
    const typeMatch = attrs.match(/type="([^"]+)"/);
    const useMatch = attrs.match(/use="(\w+)"/);

    if (nameMatch) {
      const attrName = nameMatch[1];
      const isRequired = useMatch && useMatch[1] === 'required';

      let type = 'any';
      if (typeMatch) {
        const typeName = typeMatch[1].includes(':') ? typeMatch[1].split(':').pop() : typeMatch[1];
        if (knownEnums[typeName]) {
          fields[attrName] = {
            type: 'enum',
            values: knownEnums[typeName],
            constraint: isRequired ? 'required' : 'nullable',
          };
          continue;
        }
        type = mapXsdType(typeName);
      }

      fields[attrName] = {
        type,
        constraint: isRequired ? 'required' : 'nullable',
      };
    }
  }

  // Handle extension (complexContent/extension)
  const extMatch = body.match(new RegExp(`<${ns}extension\\s+base="([^"]+)"`));
  if (extMatch) {
    const baseName = extMatch[1].includes(':') ? extMatch[1].split(':').pop() : extMatch[1];
    relations._extends = {
      target: baseName,
      cardinality: 'one_to_one',
    };
  }

  return { fields, relations };
}

const XSD_BUILTIN_TYPES = [
  'string', 'normalizedString', 'token',
  'integer', 'int', 'long', 'short', 'byte',
  'nonNegativeInteger', 'positiveInteger', 'nonPositiveInteger', 'negativeInteger',
  'unsignedInt', 'unsignedLong', 'unsignedShort', 'unsignedByte',
  'decimal', 'float', 'double',
  'boolean',
  'date', 'dateTime', 'time', 'duration',
  'gYear', 'gYearMonth', 'gMonth', 'gMonthDay', 'gDay',
  'base64Binary', 'hexBinary',
  'anyURI', 'QName', 'NOTATION', 'ID', 'IDREF', 'IDREFS',
  'NMTOKEN', 'NMTOKENS', 'ENTITY', 'ENTITIES',
  'anyType', 'anySimpleType',
];

function isXsdBuiltinType(type) {
  return XSD_BUILTIN_TYPES.includes(type);
}

function mapXsdType(type) {
  if (['string', 'normalizedString', 'token', 'anyURI', 'QName', 'ID', 'IDREF', 'NMTOKEN'].includes(type)) return 'string';
  if (['integer', 'int', 'long', 'short', 'byte', 'decimal', 'float', 'double',
       'nonNegativeInteger', 'positiveInteger', 'nonPositiveInteger', 'negativeInteger',
       'unsignedInt', 'unsignedLong', 'unsignedShort', 'unsignedByte'].includes(type)) return 'number';
  if (type === 'boolean') return 'boolean';
  if (type === 'dateTime') return 'timestamp';
  if (type === 'date') return 'date';
  if (type === 'time') return 'time';
  if (type === 'duration') return 'string'; // Duration as string
  if (['base64Binary', 'hexBinary'].includes(type)) return 'binary';
  return 'any';
}

/** Check if content looks like an XSD file. */
function canParse(content, filename) {
  if (filename && /\.xsd$/i.test(filename)) return true;
  return /xs:schema|xsd:schema/.test(content);
}

module.exports = { parse, canParse };
