'use strict';

/**
 * Starter pack — seed the schema commons with curated industry standards.
 *
 * On first project init, checks if the schema commons is empty.
 * If empty, offers to download and ingest ~30 curated sources across
 * 15+ industries from GitHub.
 *
 * Flow:
 * 1. Check Qdrant collection state
 * 2. If empty, read starter-pack.json for the curated list
 * 3. For each source: fetch from GitHub, detect format, parse, embed, store
 * 4. Report results
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { QdrantClient, embedderHealthy } = require('./qdrant.cjs');
const { ingestContent } = require('./ingest.cjs');

const STARTER_PACK_PATH = path.join(__dirname, '..', '..', 'starter-pack.json');
const GITHUB_RAW_BASE = 'https://raw.githubusercontent.com';

// ─── Schema Commons Gate ────────────────────────────────────────────────────

/**
 * Check if schema commons (Qdrant) is enabled for this project.
 * Defaults to false — the human must opt in during /eclusa:new-project.
 * Checks .eclusa/config.json > schema_commons.enabled
 */
function isSchemaCommonsEnabled() {
  try {
    // Check project-level config first
    const configPath = path.join(process.cwd(), '.eclusa', 'config.json');
    if (fs.existsSync(configPath)) {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (config.schema_commons && config.schema_commons.enabled === true) return true;
    }
    // Check global config
    const globalPath = path.join(require('os').homedir(), '.eclusa', 'config.json');
    if (fs.existsSync(globalPath)) {
      const config = JSON.parse(fs.readFileSync(globalPath, 'utf-8'));
      if (config.schema_commons && config.schema_commons.enabled === true) return true;
    }
  } catch (_) {}
  return false;
}

// ─── Environment Check ──────────────────────────────────────────────────────

/**
 * Check that the eclusa infrastructure is ready.
 * Returns { ready, issues[] }.
 * Schema commons (Qdrant) is opt-in — only checked if enabled in config.
 */
async function checkEnvironment() {
  const issues = [];

  // Check Docker / Qdrant — only if schema commons is enabled
  // Schema commons is opt-in: the human decides during /eclusa:new-project
  // Pipeline stages (match, cohere, ingest) degrade gracefully when disabled
  const schemaCommonsEnabled = isSchemaCommonsEnabled();
  if (schemaCommonsEnabled) {
    const qdrant = new QdrantClient();
    const qdrantAlive = await qdrant.ping();
    if (!qdrantAlive) {
      issues.push({
        component: 'qdrant',
        severity: 'warning',
        message: 'Qdrant not running — schema commons features (match, cohere, ingest) unavailable',
        fix: 'docker compose up -d (or disable schema commons in config)',
      });
    }

    // Check embedder
    const embedderAlive = await embedderHealthy();
    if (!embedderAlive) {
      issues.push({
        component: 'embedder',
        severity: 'warning',
        message: 'Text Embeddings Inference service not running (will use fallback embeddings)',
        fix: 'docker compose up -d embedder',
      });
    }
  }

  // Check starter pack file exists
  if (!fs.existsSync(STARTER_PACK_PATH)) {
    issues.push({
      component: 'starter-pack',
      message: 'Starter pack manifest not found',
      fix: 'Reinstall eclusa',
    });
  }

  const blocking = issues.filter(i => i.severity !== 'warning');
  return {
    ready: blocking.length === 0,
    issues,
  };
}

/**
 * Check if the schema commons has been seeded.
 */
async function isSeeded() {
  try {
    const qdrant = new QdrantClient();
    const info = await qdrant.collectionInfo();
    return (info.points_count || 0) > 0;
  } catch {
    return false;
  }
}

// ─── GitHub Fetch ───────────────────────────────────────────────────────────

/**
 * Fetch a file from GitHub via raw.githubusercontent.com.
 */
function fetchFromGitHub(repo, filePath, branch = 'main') {
  const url = `${GITHUB_RAW_BASE}/${repo}/${branch}/${filePath}`;
  return new Promise((resolve, reject) => {
    const tryBranch = (b) => {
      const tryUrl = `${GITHUB_RAW_BASE}/${repo}/${b}/${filePath}`;
      https.get(tryUrl, { headers: { 'User-Agent': 'eclusa/5.0' } }, (res) => {
        if (res.statusCode === 404 && b === 'main') {
          return tryBranch('master'); // Fallback to master
        }
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return https.get(res.headers.location, { headers: { 'User-Agent': 'eclusa/5.0' } }, (res2) => {
            let data = '';
            res2.on('data', c => data += c);
            res2.on('end', () => resolve(data));
          }).on('error', reject);
        }
        if (res.statusCode >= 400) {
          return reject(new Error(`GitHub ${res.statusCode}: ${tryUrl}`));
        }
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => resolve(data));
      }).on('error', reject);
    };
    tryBranch(branch);
  });
}

// ─── Seed Flow ──────────────────────────────────────────────────────────────

/**
 * Load the starter pack manifest.
 */
function loadStarterPack() {
  if (!fs.existsSync(STARTER_PACK_PATH)) {
    return { sources: [] };
  }
  return JSON.parse(fs.readFileSync(STARTER_PACK_PATH, 'utf-8'));
}

/**
 * Seed the schema commons with the starter pack.
 * Returns progress updates via callback.
 *
 * @param {object} [opts] - { industries: string[] } to filter by industry
 * @param {function} [onProgress] - Called with { current, total, source, status }
 */
async function seed(opts = {}, onProgress) {
  const pack = loadStarterPack();
  let sources = pack.sources || [];

  // Filter by industry if specified
  if (opts.industries && opts.industries.length > 0) {
    sources = sources.filter(s => opts.industries.includes(s.industry));
  }

  const qdrant = new QdrantClient();
  await qdrant.ensureCollection();

  const results = { total: sources.length, success: 0, failed: 0, skipped: 0, details: [] };

  for (let i = 0; i < sources.length; i++) {
    const source = sources[i];
    const progress = { current: i + 1, total: sources.length, source: source.name, status: 'fetching' };
    if (onProgress) onProgress(progress);

    try {
      const content = await fetchFromGitHub(source.repo, source.path);
      progress.status = 'ingesting';
      if (onProgress) onProgress(progress);

      const origin = `github:${source.repo}/${source.path}`;
      const filename = path.basename(source.path);
      const result = await ingestContent(content, origin, filename);

      results.success++;
      results.details.push({
        name: source.name,
        industry: source.industry,
        status: 'ok',
        entities: result.entities,
        operations: result.operations,
        points: result.points,
      });
    } catch (err) {
      results.failed++;
      results.details.push({
        name: source.name,
        industry: source.industry,
        status: 'failed',
        error: err.message,
      });
    }
  }

  return results;
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

let _core;
function getCore() { if (!_core) _core = require('./core.cjs'); return _core; }
function output(data) { getCore().output(data); }
function error(msg) { getCore().error(msg); }

async function cmdCheckEnvironment() {
  const result = await checkEnvironment();
  output(result);
}

async function cmdIsSeeded() {
  const seeded = await isSeeded();
  output({ seeded });
}

async function cmdSeed(industriesJson) {
  const industries = industriesJson ? JSON.parse(industriesJson) : [];
  const result = await seed(
    { industries: industries.length > 0 ? industries : undefined },
    (progress) => {
      process.stderr.write(`\r  [${progress.current}/${progress.total}] ${progress.status}: ${progress.source}   `);
    }
  );
  process.stderr.write('\n');
  output(result);
}

async function cmdListStarterPack() {
  const pack = loadStarterPack();
  const summary = {};
  for (const s of pack.sources) {
    if (!summary[s.industry]) summary[s.industry] = [];
    summary[s.industry].push({ name: s.name, format: s.format, repo: s.repo });
  }
  output({ total: pack.sources.length, by_industry: summary });
}

module.exports = {
  checkEnvironment,
  isSeeded,
  fetchFromGitHub,
  loadStarterPack,
  seed,
  cmdCheckEnvironment,
  cmdIsSeeded,
  cmdSeed,
  cmdListStarterPack,
};
