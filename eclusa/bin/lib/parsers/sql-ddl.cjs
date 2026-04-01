'use strict';

/**
 * SQL DDL parser → Normalized IR
 *
 * Extracts: CREATE TABLE → entities, columns → fields,
 * FOREIGN KEY → relations, constraints.
 * Handles PostgreSQL, MySQL, and SQLite dialects.
 */

const { createIR, addEntity } = require('../ir.cjs');

/**
 * Parse SQL DDL statements into IR.
 * @param {string} content - SQL DDL content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  const ir = createIR(origin, 'sql_ddl', null);

  // Normalize: collapse multi-line statements, remove comments
  const cleaned = content
    .replace(/--[^\n]*/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\r\n/g, '\n');

  // Extract CREATE TABLE statements
  const tableRegex = /CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["'`]?(\w+)["'`]?\s*\(([^;]*?)\)\s*;/gi;
  let match;

  while ((match = tableRegex.exec(cleaned)) !== null) {
    const tableName = toPascalCase(match[1]);
    const body = match[2];
    const fields = {};
    const relations = {};

    // Parse column definitions and constraints
    const parts = splitColumns(body);

    for (const part of parts) {
      const trimmed = part.trim();
      if (!trimmed) continue;

      // Table-level FOREIGN KEY
      const fkMatch = trimmed.match(/FOREIGN\s+KEY\s*\(["'`]?(\w+)["'`]?\)\s*REFERENCES\s+["'`]?(\w+)["'`]?/i);
      if (fkMatch) {
        const fkField = fkMatch[1];
        const refTable = toPascalCase(fkMatch[2]);
        relations[fkField.replace(/_id$/, '')] = {
          target: refTable,
          cardinality: 'many_to_one',
        };
        continue;
      }

      // Table-level PRIMARY KEY, UNIQUE, CHECK, INDEX — skip
      if (/^\s*(PRIMARY\s+KEY|UNIQUE|CHECK|INDEX|CONSTRAINT)/i.test(trimmed)) continue;

      // Column definition
      const colMatch = trimmed.match(/^["'`]?(\w+)["'`]?\s+(\w+(?:\([^)]*\))?)\s*(.*)/i);
      if (!colMatch) continue;

      const colName = colMatch[1];
      const colType = colMatch[2];
      const colAttrs = colMatch[3] || '';

      // Detect inline REFERENCES
      const inlineRef = colAttrs.match(/REFERENCES\s+["'`]?(\w+)["'`]?/i);
      if (inlineRef) {
        relations[colName.replace(/_id$/, '')] = {
          target: toPascalCase(inlineRef[1]),
          cardinality: 'many_to_one',
        };
      }

      const constraints = [];
      if (/PRIMARY\s+KEY/i.test(colAttrs)) constraints.push('unique');
      if (/UNIQUE/i.test(colAttrs)) constraints.push('unique');
      if (/NOT\s+NULL/i.test(colAttrs)) constraints.push('required');
      if (!/NOT\s+NULL/i.test(colAttrs) && !/PRIMARY\s+KEY/i.test(colAttrs)) constraints.push('nullable');
      if (/DEFAULT\s/i.test(colAttrs)) constraints.push('has_default');
      if (/AUTOINCREMENT|AUTO_INCREMENT|SERIAL|GENERATED/i.test(colType + ' ' + colAttrs)) constraints.push('auto');

      fields[colName] = {
        type: mapSqlType(colType),
        constraint: constraints.length > 0 ? constraints.join(',') : null,
      };
    }

    addEntity(ir, tableName, fields, relations);
  }

  // Extract CREATE TYPE ... AS ENUM (PostgreSQL)
  const enumRegex = /CREATE\s+TYPE\s+["'`]?(\w+)["'`]?\s+AS\s+ENUM\s*\(([^)]+)\)/gi;
  while ((match = enumRegex.exec(cleaned)) !== null) {
    const name = toPascalCase(match[1]);
    const values = match[2]
      .split(',')
      .map(v => v.trim().replace(/^['"]|['"]$/g, ''))
      .filter(Boolean);
    addEntity(ir, name, {
      value: { type: 'enum', values },
    });
  }

  return ir;
}

/**
 * Split column definitions, handling nested parentheses.
 */
function splitColumns(body) {
  const parts = [];
  let depth = 0, start = 0;
  for (let i = 0; i < body.length; i++) {
    if (body[i] === '(') depth++;
    else if (body[i] === ')') depth--;
    else if (body[i] === ',' && depth === 0) {
      parts.push(body.slice(start, i));
      start = i + 1;
    }
  }
  parts.push(body.slice(start));
  return parts;
}

function mapSqlType(type) {
  const upper = type.toUpperCase().replace(/\(.*\)/, '');
  if (['INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT', 'SERIAL', 'BIGSERIAL'].includes(upper)) return 'number';
  if (['FLOAT', 'DOUBLE', 'REAL', 'DECIMAL', 'NUMERIC'].includes(upper)) return 'number';
  if (['VARCHAR', 'CHAR', 'TEXT', 'CLOB', 'CITEXT'].includes(upper)) return 'string';
  if (['BOOLEAN', 'BOOL'].includes(upper)) return 'boolean';
  if (['TIMESTAMP', 'TIMESTAMPTZ', 'DATETIME'].includes(upper)) return 'timestamp';
  if (['DATE'].includes(upper)) return 'date';
  if (['TIME', 'TIMETZ'].includes(upper)) return 'time';
  if (['JSON', 'JSONB'].includes(upper)) return 'object';
  if (['UUID'].includes(upper)) return 'string';
  if (['BYTEA', 'BLOB', 'BINARY', 'VARBINARY'].includes(upper)) return 'binary';
  return 'any';
}

function toPascalCase(str) {
  return str
    .split(/[_\s-]+/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join('');
}

/** Check if content looks like SQL DDL. */
function canParse(content, filename) {
  if (filename && /\.(sql|ddl)$/i.test(filename)) return true;
  return /CREATE\s+TABLE/i.test(content);
}

module.exports = { parse, canParse };
