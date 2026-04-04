'use strict';

/**
 * Qdrant client for the schema commons.
 * Uses Qdrant REST API via Node.js built-in http module.
 * No external dependencies.
 */

const http = require('http');

const DEFAULT_HOST = 'localhost';
const DEFAULT_PORT = 6333;
const EMBEDDER_HOST = 'localhost';
const EMBEDDER_PORT = 8081;
const COLLECTION = 'schema_commons';
const VECTOR_DIM = 384; // BAAI/bge-small-en-v1.5 produces 384d vectors

class QdrantClient {
  constructor(host = DEFAULT_HOST, port = DEFAULT_PORT) {
    this.host = host;
    this.port = port;
    this.baseUrl = `http://${host}:${port}`;
  }

  /**
   * Make an HTTP request to Qdrant REST API.
   */
  async request(method, path, body = null) {
    return new Promise((resolve, reject) => {
      const url = new URL(path, this.baseUrl);
      const options = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        method,
        headers: { 'Content-Type': 'application/json' },
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            if (res.statusCode >= 200 && res.statusCode < 300) {
              resolve(parsed);
            } else {
              reject(new Error(`Qdrant ${method} ${path}: ${res.statusCode} — ${JSON.stringify(parsed)}`));
            }
          } catch {
            reject(new Error(`Qdrant ${method} ${path}: ${res.statusCode} — ${data}`));
          }
        });
      });

      req.on('error', (err) => {
        if (err.code === 'ECONNREFUSED') {
          reject(new Error(`Cannot connect to Qdrant at ${this.baseUrl}. Is it running? Start with: docker compose up -d`));
        } else {
          reject(err);
        }
      });

      req.setTimeout(10000, () => {
        req.destroy();
        reject(new Error(`Qdrant request timed out: ${method} ${path}`));
      });

      if (body) req.write(JSON.stringify(body));
      req.end();
    });
  }

  /** Check if Qdrant is reachable. */
  async ping() {
    try {
      // /healthz returns plain text, not JSON — use raw HTTP check instead of this.request()
      return new Promise((resolve) => {
        const url = new URL('/healthz', this.baseUrl);
        const req = http.get({ hostname: url.hostname, port: url.port, path: url.pathname, timeout: 5000 }, (res) => {
          res.resume(); // drain response
          resolve(res.statusCode >= 200 && res.statusCode < 300);
        });
        req.on('error', () => resolve(false));
        req.on('timeout', () => { req.destroy(); resolve(false); });
      });
    } catch {
      return false;
    }
  }

  /** Ensure the schema_commons collection exists. */
  async ensureCollection() {
    try {
      await this.request('GET', `/collections/${COLLECTION}`);
      return { created: false };
    } catch {
      await this.request('PUT', `/collections/${COLLECTION}`, {
        vectors: {
          size: VECTOR_DIM,
          distance: 'Cosine',
        },
      });
      // Create payload indices for fast filtering
      await this.request('PUT', `/collections/${COLLECTION}/index`, {
        field_name: 'source_origin',
        field_schema: 'keyword',
      });
      await this.request('PUT', `/collections/${COLLECTION}/index`, {
        field_name: 'entity_name',
        field_schema: 'keyword',
      });
      await this.request('PUT', `/collections/${COLLECTION}/index`, {
        field_name: 'source_format',
        field_schema: 'keyword',
      });
      await this.request('PUT', `/collections/${COLLECTION}/index`, {
        field_name: 'entry_type',
        field_schema: 'keyword',
      });
      return { created: true };
    }
  }

  /**
   * Upsert points into the collection.
   * @param {Array<{id: string, vector: number[], payload: object}>} points
   */
  async upsert(points) {
    return this.request('PUT', `/collections/${COLLECTION}/points`, {
      points: points.map(p => ({
        id: p.id,
        vector: p.vector,
        payload: p.payload,
      })),
    });
  }

  /**
   * Search for similar vectors with optional filters.
   * @param {number[]} vector - Query vector
   * @param {number} limit - Max results
   * @param {object} [filter] - Qdrant filter conditions
   */
  async search(vector, limit = 10, filter = null) {
    const body = { vector, limit, with_payload: true };
    if (filter) body.filter = filter;
    const result = await this.request('POST', `/collections/${COLLECTION}/points/search`, body);
    return result.result || [];
  }

  /**
   * Search by text — embed the query then search.
   * @param {string} text - Natural language query
   * @param {number} limit - Max results
   * @param {object} [filter] - Optional filter
   */
  async searchByText(text, limit = 10, filter = null) {
    const vector = await embed(text);
    return this.search(vector, limit, filter);
  }

  /**
   * Scroll through all points with optional filter.
   */
  async scroll(filter = null, limit = 100, offset = null) {
    const body = { limit, with_payload: true };
    if (filter) body.filter = filter;
    if (offset) body.offset = offset;
    const result = await this.request('POST', `/collections/${COLLECTION}/points/scroll`, body);
    return result.result || { points: [], next_page_offset: null };
  }

  /**
   * Delete points by filter.
   */
  async deleteByFilter(filter) {
    return this.request('POST', `/collections/${COLLECTION}/points/delete`, {
      filter,
    });
  }

  /** Get collection info (point count, etc). */
  async collectionInfo() {
    const result = await this.request('GET', `/collections/${COLLECTION}`);
    return result.result;
  }
}

// ─── Embedding ──────────────────────────────────────────────────────────────

/**
 * Embed text using the HuggingFace Text Embeddings Inference service.
 * Falls back to trigram hashing if the embedder is unavailable (testing/offline).
 *
 * Primary: BAAI/bge-small-en-v1.5 via TEI Docker service (384d, real semantics)
 * Fallback: Trigram hash (384d, lexical only — for tests and offline use)
 */
async function embed(text) {
  try {
    return await embedViaTEI(text);
  } catch {
    return embedFallback(text);
  }
}

/**
 * Synchronous embed — always uses fallback. For tests and non-async contexts.
 */
function embedSync(text) {
  return embedFallback(text);
}

/**
 * Call the HuggingFace Text Embeddings Inference service.
 */
function embedViaTEI(text) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ inputs: text, truncate: true });
    const req = http.request({
      hostname: EMBEDDER_HOST,
      port: EMBEDDER_PORT,
      path: '/embed',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (Array.isArray(parsed) && Array.isArray(parsed[0])) {
            resolve(parsed[0]); // TEI returns [[...vector...]]
          } else {
            reject(new Error('Unexpected TEI response format'));
          }
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(5000, () => { req.destroy(); reject(new Error('TEI timeout')); });
    req.write(body);
    req.end();
  });
}

/**
 * Batch embed multiple texts via TEI.
 * More efficient than calling embed() in a loop.
 */
async function embedBatch(texts) {
  try {
    return await embedBatchViaTEI(texts);
  } catch {
    return texts.map(t => embedFallback(t));
  }
}

function embedBatchViaTEI(texts) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ inputs: texts, truncate: true });
    const req = http.request({
      hostname: EMBEDDER_HOST,
      port: EMBEDDER_PORT,
      path: '/embed',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (Array.isArray(parsed) && parsed.length === texts.length) {
            resolve(parsed);
          } else {
            reject(new Error('Unexpected TEI batch response'));
          }
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('TEI batch timeout')); });
    req.write(body);
    req.end();
  });
}

/**
 * Trigram hash fallback — deterministic, zero-dependency, lexical similarity.
 * Used when TEI service is unavailable (tests, offline, CI).
 */
function embedFallback(text) {
  const normalized = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  const vector = new Float32Array(VECTOR_DIM);

  const words = normalized.split(' ');
  for (const word of words) {
    for (let i = 0; i <= word.length - 3; i++) {
      const trigram = word.slice(i, i + 3);
      const hash = trigramHash(trigram);
      vector[hash % VECTOR_DIM] += 1;
    }
    const wordHash = simpleHash(word);
    vector[wordHash % VECTOR_DIM] += 2;
  }

  let norm = 0;
  for (let i = 0; i < VECTOR_DIM; i++) norm += vector[i] * vector[i];
  norm = Math.sqrt(norm) || 1;
  for (let i = 0; i < VECTOR_DIM; i++) vector[i] /= norm;

  return Array.from(vector);
}

function trigramHash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function simpleHash(s) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

/**
 * Check if the TEI embedder service is available.
 */
async function embedderHealthy() {
  return new Promise((resolve) => {
    const req = http.get(`http://${EMBEDDER_HOST}:${EMBEDDER_PORT}/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

/**
 * Generate a deterministic UUID-like ID from a string.
 */
function deterministicId(source, name) {
  const input = `${source}::${name}`;
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < input.length; i++) {
    h1 = (h1 ^ input.charCodeAt(i)) * 0x01000193;
    h2 = (h2 ^ input.charCodeAt(i)) * 0x811c9dc5;
  }
  // Create a numeric ID from the hashes (Qdrant accepts unsigned 64-bit integers)
  return Math.abs((h1 << 16) | (h2 & 0xffff));
}

module.exports = {
  QdrantClient,
  embed,
  embedSync,
  embedBatch,
  embedFallback,
  embedderHealthy,
  deterministicId,
  COLLECTION,
  VECTOR_DIM,
  DEFAULT_HOST,
  DEFAULT_PORT,
  EMBEDDER_HOST,
  EMBEDDER_PORT,
};
