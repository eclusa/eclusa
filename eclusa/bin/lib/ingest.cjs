'use strict';

/**
 * Ingestion pipeline for the schema commons.
 *
 * Flow: detect format → parse to IR → embed → store in Qdrant.
 * Supports: OpenAPI, Prisma, SQL DDL (MVP parsers).
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { QdrantClient } = require('./qdrant.cjs');
const { irToPoints, validateIR } = require('./ir.cjs');

// Parsers
const openapi = require('./parsers/openapi.cjs');
const prisma = require('./parsers/prisma.cjs');
const sqlDdl = require('./parsers/sql-ddl.cjs');
const protobuf = require('./parsers/protobuf.cjs');
const graphql = require('./parsers/graphql.cjs');
const typescript = require('./parsers/typescript.cjs');
const jsonSchema = require('./parsers/json-schema.cjs');
const xsd = require('./parsers/xsd.cjs');
const rust = require('./parsers/rust.cjs');
const go = require('./parsers/go.cjs');

const PARSERS = [openapi, prisma, sqlDdl, protobuf, graphql, typescript, jsonSchema, xsd, rust, go];

// ─── Format Detection ───────────────────────────────────────────────────────

/**
 * Detect the format of a file and return the appropriate parser.
 */
function detectParser(content, filename) {
  for (const parser of PARSERS) {
    if (parser.canParse(content, filename)) return parser;
  }
  return null;
}

/**
 * Detect format from file extension alone.
 */
function detectFormat(filename) {
  const ext = path.extname(filename).toLowerCase();
  if (ext === '.prisma') return 'prisma';
  if (ext === '.sql' || ext === '.ddl') return 'sql_ddl';
  if (ext === '.proto') return 'protobuf';
  if (ext === '.graphql' || ext === '.gql') return 'graphql';
  if (ext === '.xsd') return 'xsd';
  if (ext === '.rs') return 'rust';
  if (ext === '.go') return 'go';
  if (filename.endsWith('.d.ts')) return 'typescript';
  if (['.yaml', '.yml', '.json'].includes(ext)) return 'openapi'; // Might be, check content
  return null;
}

// ─── Fetch ──────────────────────────────────────────────────────────────────

/**
 * Fetch content from a URL.
 */
function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { headers: { 'User-Agent': 'eclusa/5.0' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return fetchUrl(res.headers.location).then(resolve, reject);
      }
      if (res.statusCode >= 400) {
        return reject(new Error(`HTTP ${res.statusCode} fetching ${url}`));
      }
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve(data));
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error(`Timeout fetching ${url}`)); });
  });
}

// ─── Ingest Operations ──────────────────────────────────────────────────────

/**
 * Ingest a single file.
 * @param {string} content - File content
 * @param {string} origin - Origin identifier
 * @param {string} [filename] - Original filename (for format detection)
 * @returns {object} { entities: number, operations: number, points: number }
 */
async function ingestContent(content, origin, filename) {
  const parser = detectParser(content, filename);
  if (!parser) {
    throw new Error(`Cannot detect format for ${filename || origin}. Supported: OpenAPI, Prisma, SQL DDL, Protobuf, GraphQL, TypeScript, JSON Schema, XSD, Rust, Go.`);
  }

  const ir = parser.parse(content, origin);
  const errors = validateIR(ir);
  if (errors.length > 0) {
    throw new Error(`IR validation failed: ${errors.join(', ')}`);
  }

  const points = irToPoints(ir);
  if (points.length === 0) {
    return { entities: 0, operations: 0, points: 0, format: ir.source.format };
  }

  const client = new QdrantClient();
  await client.ensureCollection();
  await client.upsert(points);

  return {
    entities: Object.keys(ir.entities).length,
    operations: ir.operations.length,
    points: points.length,
    format: ir.source.format,
  };
}

/**
 * Ingest a local file.
 */
async function ingestFile(filePath) {
  const fullPath = path.resolve(filePath);
  if (!fs.existsSync(fullPath)) {
    throw new Error(`File not found: ${fullPath}`);
  }
  const content = fs.readFileSync(fullPath, 'utf-8');
  const origin = `local:${path.relative(process.cwd(), fullPath)}`;
  return ingestContent(content, origin, path.basename(fullPath));
}

/**
 * Ingest from a URL.
 */
async function ingestUrl(url) {
  const content = await fetchUrl(url);
  const filename = path.basename(new URL(url).pathname) || 'spec';
  const origin = `url:${url}`;
  return ingestContent(content, origin, filename);
}

/**
 * Recursively scan a directory for indexable files.
 */
async function ingestScan(dirPath) {
  const fullPath = path.resolve(dirPath);
  if (!fs.existsSync(fullPath)) {
    throw new Error(`Directory not found: ${fullPath}`);
  }

  const results = [];
  const files = scanDir(fullPath);

  for (const file of files) {
    try {
      const content = fs.readFileSync(file, 'utf-8');
      const parser = detectParser(content, path.basename(file));
      if (parser) {
        const origin = `local:${path.relative(process.cwd(), file)}`;
        const result = await ingestContent(content, origin, path.basename(file));
        results.push({ file: path.relative(process.cwd(), file), ...result });
      }
    } catch {
      // Skip files that can't be parsed
    }
  }

  return results;
}

function scanDir(dir) {
  const files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
    if (entry.isDirectory()) {
      files.push(...scanDir(fullPath));
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      const name = entry.name.toLowerCase();
      if (['.yaml', '.yml', '.json', '.prisma', '.sql', '.ddl', '.proto', '.graphql', '.gql', '.xsd', '.rs', '.go'].includes(ext) || name.endsWith('.d.ts')) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

/**
 * Get index status — total entries, sources, coverage.
 */
async function ingestStatus() {
  const client = new QdrantClient();
  try {
    const info = await client.collectionInfo();
    const pointCount = info.points_count || 0;

    // Get unique sources
    const scroll = await client.scroll(null, 100);
    const sources = new Set();
    const formats = {};
    const entityCount = { entity: 0, operation: 0, auth: 0 };

    for (const point of scroll.points) {
      if (point.payload.source_origin) sources.add(point.payload.source_origin);
      const fmt = point.payload.source_format || 'unknown';
      formats[fmt] = (formats[fmt] || 0) + 1;
      const type = point.payload.entry_type || 'unknown';
      entityCount[type] = (entityCount[type] || 0) + 1;
    }

    return {
      total_points: pointCount,
      sources: Array.from(sources),
      source_count: sources.size,
      formats,
      entry_types: entityCount,
    };
  } catch (err) {
    if (err.message.includes('Cannot connect')) {
      return { error: 'Qdrant not running', hint: 'Start with: docker compose up -d' };
    }
    throw err;
  }
}

/**
 * Remove a source from the index.
 */
async function ingestPrune(sourceOrigin) {
  const client = new QdrantClient();
  await client.deleteByFilter({
    must: [{ key: 'source_origin', match: { value: sourceOrigin } }],
  });
  return { pruned: sourceOrigin };
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

const { output, error } = require('./core.cjs');

async function cmdIngest(subcommand, args) {
  try {
    switch (subcommand) {
      case 'url': {
        const url = args[0];
        if (!url) { error('Usage: ingest url <url>'); return; }
        const result = await ingestUrl(url);
        output(result);
        break;
      }
      case 'file': {
        const filePath = args[0];
        if (!filePath) { error('Usage: ingest file <path>'); return; }
        const result = await ingestFile(filePath);
        output(result);
        break;
      }
      case 'scan': {
        const dir = args[0] || '.';
        const results = await ingestScan(dir);
        output({ scanned: results.length, results });
        break;
      }
      case 'status': {
        const result = await ingestStatus();
        output(result);
        break;
      }
      case 'prune': {
        const source = args[0];
        if (!source) { error('Usage: ingest prune <source-origin>'); return; }
        const result = await ingestPrune(source);
        output(result);
        break;
      }
      default:
        error(`Unknown ingest subcommand: ${subcommand}. Available: url, file, scan, status, prune`);
    }
  } catch (err) {
    error(err.message);
  }
}

module.exports = {
  detectParser,
  detectFormat,
  fetchUrl,
  ingestContent,
  ingestFile,
  ingestUrl,
  ingestScan,
  ingestStatus,
  ingestPrune,
  cmdIngest,
};
