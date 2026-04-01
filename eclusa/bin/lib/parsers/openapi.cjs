'use strict';

/**
 * OpenAPI 3.x parser → Normalized IR
 *
 * Extracts: schemas (→ entities), paths (→ operations), security (→ auth).
 * Handles both JSON and YAML input.
 */

const { parseYaml } = require('../yaml.cjs');
const { createIR, addEntity, addOperation, addAuth } = require('../ir.cjs');

/**
 * Parse an OpenAPI 3.x spec string into IR.
 * @param {string} content - JSON or YAML content
 * @param {string} origin - Source identifier
 * @returns {object} IR document
 */
function parse(content, origin) {
  let spec;
  try {
    spec = JSON.parse(content);
  } catch {
    spec = parseYaml(content);
  }

  const version = spec.info?.version || null;
  const ir = createIR(origin, 'openapi', version);

  // Extract schemas → entities
  const schemas = spec.components?.schemas || spec.definitions || {};
  for (const [name, schema] of Object.entries(schemas)) {
    if (schema.type === 'object' || schema.properties) {
      const fields = {};
      const relations = {};

      for (const [fieldName, fieldSchema] of Object.entries(schema.properties || {})) {
        const isRequired = (schema.required || []).includes(fieldName);

        if (fieldSchema.$ref) {
          // Reference to another schema — treat as relation
          const refName = extractRefName(fieldSchema.$ref);
          relations[fieldName] = {
            target: refName,
            cardinality: 'many_to_one',
          };
        } else if (fieldSchema.type === 'array' && fieldSchema.items?.$ref) {
          const refName = extractRefName(fieldSchema.items.$ref);
          relations[fieldName] = {
            target: refName,
            cardinality: 'one_to_many',
          };
        } else {
          fields[fieldName] = {
            type: mapOpenApiType(fieldSchema),
            constraint: isRequired ? 'required' : (fieldSchema.nullable ? 'nullable' : null),
          };
          if (fieldSchema.enum) {
            fields[fieldName].type = 'enum';
            fields[fieldName].values = fieldSchema.enum;
          }
          if (fieldSchema.default !== undefined) {
            fields[fieldName].default_value = fieldSchema.default;
          }
        }
      }

      addEntity(ir, name, fields, relations);
    } else if (schema.enum) {
      // Standalone enum
      addEntity(ir, name, {
        value: { type: 'enum', values: schema.enum },
      });
    }
  }

  // Extract paths → operations
  const paths = spec.paths || {};
  for (const [pathStr, methods] of Object.entries(paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      if (['get', 'post', 'put', 'patch', 'delete'].includes(method)) {
        const opName = operation.operationId || `${method}_${pathStr.replace(/[^a-zA-Z0-9]/g, '_')}`;

        const input = {};
        for (const param of (operation.parameters || [])) {
          input[param.name] = mapOpenApiType(param.schema || param);
        }

        // Request body
        const reqBody = operation.requestBody?.content?.['application/json']?.schema;
        if (reqBody) {
          if (reqBody.$ref) {
            input._body = extractRefName(reqBody.$ref);
          } else if (reqBody.properties) {
            for (const [k, v] of Object.entries(reqBody.properties)) {
              input[k] = mapOpenApiType(v);
            }
          }
        }

        // Response
        const successResponse = operation.responses?.['200'] || operation.responses?.['201'];
        const responseSchema = successResponse?.content?.['application/json']?.schema;
        let output = null;
        if (responseSchema?.$ref) {
          output = extractRefName(responseSchema.$ref);
        } else if (responseSchema?.type) {
          output = mapOpenApiType(responseSchema);
        }

        const statusCodes = Object.keys(operation.responses || {})
          .filter(c => /^\d+$/.test(c))
          .map(Number);

        addOperation(ir, {
          name: opName,
          method: method.toUpperCase(),
          path: pathStr,
          input,
          output,
          status_codes: statusCodes,
          constraints: [],
        });
      }
    }
  }

  // Extract security → auth
  const securitySchemes = spec.components?.securitySchemes || {};
  const firstScheme = Object.values(securitySchemes)[0];
  if (firstScheme) {
    let model = 'none';
    if (firstScheme.type === 'http' && firstScheme.scheme === 'bearer') model = 'bearer_token';
    else if (firstScheme.type === 'apiKey') model = 'api_key';
    else if (firstScheme.type === 'oauth2') model = 'oauth2';
    else if (firstScheme.type === 'http' && firstScheme.scheme === 'basic') model = 'basic';

    const scopes = [];
    if (firstScheme.flows) {
      for (const flow of Object.values(firstScheme.flows)) {
        if (flow.scopes) scopes.push(...Object.keys(flow.scopes));
      }
    }
    addAuth(ir, model, scopes);
  }

  return ir;
}

function extractRefName(ref) {
  return ref.split('/').pop();
}

function mapOpenApiType(schema) {
  if (!schema) return 'any';
  if (schema.type === 'integer') return 'number';
  if (schema.type === 'number') return 'number';
  if (schema.type === 'string' && schema.format === 'date-time') return 'timestamp';
  if (schema.type === 'string' && schema.format === 'date') return 'date';
  if (schema.type === 'string') return 'string';
  if (schema.type === 'boolean') return 'boolean';
  if (schema.type === 'array') return 'array';
  if (schema.type === 'object') return 'object';
  return schema.type || 'any';
}

/** Check if content looks like an OpenAPI spec. */
function canParse(content, filename) {
  if (filename && /\.(yaml|yml|json)$/i.test(filename)) {
    return content.includes('openapi') || content.includes('swagger') || content.includes('"paths"');
  }
  return false;
}

module.exports = { parse, canParse };
