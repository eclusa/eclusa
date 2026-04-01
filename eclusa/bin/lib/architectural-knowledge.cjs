'use strict';

/**
 * Architectural knowledge — curated decision patterns for the schema commons.
 *
 * Three responsibilities:
 * 1. Novelty classification: is this a well-known pattern, similar to known, or novel?
 * 2. Curated decisions: the "tech radar" of architectural patterns
 * 3. Complexity spectrum: simplicity-first → balanced → enterprise
 *
 * This module produces IR documents that get ingested into Qdrant alongside
 * typed schemas and behavioral specs. The MATCH stage searches these when
 * a project touches infrastructure, architecture, or tooling decisions.
 */

const { createIR, addDecision, addBehavior } = require('./ir.cjs');
const { QdrantClient, embedSync } = require('./qdrant.cjs');

// ─── Novelty Classification ─────────────────────────────────────────────────

/**
 * Classify the novelty of a concept/decision by checking the schema commons.
 * Returns { level, confidence, closest_match }.
 *
 * Gate levels:
 *   well_known     — >0.7 match score, established pattern
 *   similar_to_known — 0.4-0.7 match, variation of known pattern
 *   novel          — <0.4 match, genuinely new territory
 */
async function classifyNovelty(concept) {
  const client = new QdrantClient();
  try {
    await client.ensureCollection();
    const results = await client.searchByText(concept, 3);
    const bestScore = results.length > 0 ? results[0].score : 0;

    let level, confidence;
    if (bestScore >= 0.7) {
      level = 'well_known';
      confidence = bestScore;
    } else if (bestScore >= 0.4) {
      level = 'similar_to_known';
      confidence = bestScore;
    } else {
      level = 'novel';
      confidence = 1 - bestScore; // Higher confidence it's novel when score is lower
    }

    return {
      level,
      confidence,
      closest_match: results[0] ? {
        name: results[0].payload.entity_name,
        origin: results[0].payload.source_origin,
        score: results[0].score,
        type: results[0].payload.entry_type,
      } : null,
    };
  } catch {
    // Qdrant not available — can't classify
    return { level: 'unknown', confidence: 0, closest_match: null, error: 'Qdrant not available' };
  }
}

/**
 * Batch classify multiple concepts.
 */
async function classifyNoveltyBatch(concepts) {
  const results = {};
  for (const concept of concepts) {
    results[concept] = await classifyNovelty(concept);
  }
  return results;
}

// ─── Curated Architectural Decisions ────────────────────────────────────────

/**
 * Generate an IR document containing curated architectural decisions.
 * These are the "tech radar" entries — well-known patterns and when to use them.
 */
function curatedDecisions() {
  const ir = createIR('eclusa:architectural-knowledge', 'curated', '1.0');

  // ─── Infrastructure / Deployment ────────────────────────────────────

  addDecision(ir, {
    given: 'stateless HTTP service, < 100 RPS, single region, small team',
    prefer: 'Fly.io, Railway, or Render over Kubernetes',
    because: 'operational overhead of k8s exceeds value below this scale; PaaS handles TLS, deploys, health checks',
    unless: 'team already operates k8s clusters or needs multi-region from day one',
    tags: ['infrastructure', 'deployment', 'scale'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  addDecision(ir, {
    given: 'multiple services, >1000 RPS, need autoscaling, multi-region',
    prefer: 'Kubernetes (EKS/GKE/AKS) with ArgoCD or Flux for GitOps',
    because: 'k8s ecosystem handles service mesh, autoscaling, observability at scale',
    unless: 'purely serverless architecture (Lambda/CloudRun) handles the workload shape',
    tags: ['infrastructure', 'kubernetes', 'scale', 'orchestration'],
    novelty: 'well_known', spectrum: 'enterprise',
  });

  addDecision(ir, {
    given: 'serverless functions, event-driven, variable load with idle periods',
    prefer: 'AWS Lambda or Google Cloud Run over always-on containers',
    because: 'pay-per-invocation eliminates idle cost; cold starts acceptable for async work',
    unless: 'latency-sensitive (<50ms p99) or needs persistent connections (WebSocket)',
    tags: ['infrastructure', 'serverless', 'cost'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  // ─── Databases ──────────────────────────────────────────────────────

  addDecision(ir, {
    given: 'relational data, ACID needed, single application, < 1TB',
    prefer: 'PostgreSQL over MySQL or proprietary databases',
    because: 'best balance of features (JSONB, CTEs, window functions, extensions), open source, massive ecosystem',
    unless: 'MySQL-specific features needed (e.g., existing large MySQL deployment)',
    tags: ['database', 'relational', 'postgresql'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  addDecision(ir, {
    given: 'cache, session store, rate limiting, leaderboards, pub/sub',
    prefer: 'Redis (or Valkey/DragonflyDB) over Memcached',
    because: 'data structures (sorted sets, streams, HyperLogLog) handle 90% of caching + real-time patterns',
    when: 'ZSET for leaderboards, Streams for event log, pub/sub for notifications',
    tags: ['database', 'cache', 'redis', 'real-time'],
    novelty: 'well_known', spectrum: 'balanced',
  });

  addDecision(ir, {
    given: 'single-process application, <100GB data, embedded database needed',
    prefer: 'SQLite (or libSQL/Turso) over client-server database',
    because: 'zero-config, zero-network-hop, WAL mode handles concurrent reads; sufficient for most single-node apps',
    unless: 'multiple processes need write access or data exceeds single disk',
    tags: ['database', 'embedded', 'sqlite', 'simplicity'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  // ─── Data Engineering ───────────────────────────────────────────────

  addDecision(ir, {
    given: 'analytical workload, append-only data, schema evolution needed, multi-engine',
    prefer: 'Apache Iceberg over Delta Lake or Hudi',
    because: 'vendor-neutral, broadest engine support (Spark, Trino, DuckDB, Flink, Dremio)',
    unless: 'already in Databricks ecosystem (Delta native) or AWS-heavy (Hudi on EMR)',
    tags: ['data', 'lakehouse', 'iceberg', 'analytics'],
    novelty: 'well_known', spectrum: 'enterprise',
  });

  addDecision(ir, {
    given: 'data pipeline, need lineage tracking, asset-oriented mental model',
    prefer: 'Dagster over Airflow for new projects',
    because: 'software-defined assets, built-in lineage, type-checking, better local dev; Airflow for existing DAG estates',
    when: 'Prefect if you prefer imperative Python over declarative asset definitions',
    tags: ['data', 'orchestration', 'dagster', 'pipeline'],
    novelty: 'well_known', spectrum: 'balanced',
  });

  addDecision(ir, {
    given: 'medallion architecture (bronze/silver/gold), data quality gates',
    prefer: 'WAP branching (Write-Audit-Publish) with Iceberg or Delta table branches',
    because: 'prevents bad data from reaching gold layer; audit step catches schema drift and quality issues before promotion',
    tags: ['data', 'quality', 'medallion', 'lakehouse'],
    novelty: 'similar_to_known', spectrum: 'enterprise',
  });

  // ─── Messaging / Events ─────────────────────────────────────────────

  addDecision(ir, {
    given: 'event-driven, ordering matters, multiple consumers, high throughput',
    prefer: 'Kafka or Redpanda over SQS/SNS',
    because: 'log-based ordering, consumer groups, replay capability; SQS FIFO caps at 300 msg/s per group',
    when: 'NATS JetStream if simpler ops desired; Redis Streams if single consumer and < 10k msg/s',
    tags: ['messaging', 'events', 'kafka', 'streaming'],
    novelty: 'well_known', spectrum: 'enterprise',
  });

  addDecision(ir, {
    given: 'simple task queue, at-least-once delivery, no ordering requirement',
    prefer: 'SQS, BullMQ (Redis-backed), or pg-boss (Postgres-backed) over Kafka',
    because: 'Kafka is overkill for simple job queues; SQS/BullMQ/pg-boss handle this with zero operational overhead',
    tags: ['messaging', 'queue', 'tasks', 'simplicity'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  // ─── Architecture Patterns ──────────────────────────────────────────

  addDecision(ir, {
    given: 'monolith becoming painful, need to extract services incrementally',
    prefer: 'Strangler Fig pattern over big-bang rewrite',
    because: 'progressive migration, parallel running, rollback at each step; big-bang rewrites fail 70%+ of the time (Fowler)',
    tags: ['architecture', 'migration', 'strangler-fig', 'incremental'],
    novelty: 'well_known', spectrum: 'balanced',
  });

  addDecision(ir, {
    given: 'complex domain, many business rules, long-lived project',
    prefer: 'Domain-Driven Design (bounded contexts, aggregates, value objects)',
    because: 'explicit boundaries prevent coupling; ubiquitous language aligns code with business; aggregates enforce invariants',
    unless: 'CRUD-heavy app with simple business logic (DDD overhead not justified)',
    tags: ['architecture', 'ddd', 'domain', 'bounded-context'],
    novelty: 'well_known', spectrum: 'enterprise',
  });

  addDecision(ir, {
    given: 'read-heavy, different read/write models needed, audit trail required',
    prefer: 'CQRS + Event Sourcing over CRUD',
    because: 'separate read optimization from write consistency; event log is the audit trail; replay enables projections',
    unless: 'simple read/write ratio or team lacks event sourcing experience (high complexity cost)',
    tags: ['architecture', 'cqrs', 'event-sourcing', 'audit'],
    novelty: 'well_known', spectrum: 'enterprise',
  });

  addDecision(ir, {
    given: 'new project, unclear domain boundaries, small team',
    prefer: 'modular monolith over microservices',
    because: 'module boundaries without network boundaries; extract to services when proven stable; Shopify runs a modular monolith at scale',
    tags: ['architecture', 'monolith', 'modularity', 'simplicity'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  // ─── Workflow Orchestration ─────────────────────────────────────────

  addDecision(ir, {
    given: 'long-running workflows, retries, human-in-the-loop steps, saga pattern',
    prefer: 'Temporal.io over hand-rolled state machines',
    because: 'durable execution handles crashes, retries, timeouts; workflow-as-code in Go/TypeScript/Python/Java',
    when: 'Inngest for serverless-native event-driven workflows; Hatchet for simpler Temporal alternative',
    tags: ['orchestration', 'workflow', 'temporal', 'saga'],
    novelty: 'well_known', spectrum: 'balanced',
  });

  // ─── Frontend / Mobile ──────────────────────────────────────────────

  addDecision(ir, {
    given: 'cross-platform mobile app, same codebase for iOS and Android',
    prefer: 'Flutter (Dart) for performance-critical, React Native for web-team familiarity',
    because: 'Flutter: own rendering engine, consistent UI, Dart AOT compilation; RN: leverage existing React skills, larger npm ecosystem',
    unless: 'platform-specific features dominate (then native: Jetpack Compose / SwiftUI)',
    tags: ['mobile', 'cross-platform', 'flutter', 'react-native'],
    novelty: 'well_known', spectrum: 'balanced',
  });

  addDecision(ir, {
    given: 'CLI tool, terminal UI needed, developer-facing',
    prefer: 'Ratatui (Rust), Bubbletea (Go), Ink (Node.js), or Textual (Python) — match your backend language',
    because: 'modern TUI frameworks handle layout, styling, events without ncurses; ship as single binary (Rust/Go) or via npm/pip',
    tags: ['frontend', 'tui', 'cli', 'developer-tools'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  // ─── Toolchain ──────────────────────────────────────────────────────

  addDecision(ir, {
    given: 'Python project, need package manager + linter + formatter',
    prefer: 'uv (Astral) for packages, ruff for lint+format over pip+flake8+black',
    because: '10-100x faster, single tool replaces pip+pip-tools+virtualenv; ruff replaces flake8+isort+black in one Rust binary',
    tags: ['toolchain', 'python', 'uv', 'ruff', 'astral'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  addDecision(ir, {
    given: 'TypeScript/JavaScript project, need bundler + dev server',
    prefer: 'Vite over webpack for new projects',
    because: 'native ESM, instant HMR, Rollup-based builds; webpack only if complex legacy config needs migration',
    tags: ['toolchain', 'javascript', 'typescript', 'vite', 'bundler'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  // ─── Embedded / IoT ─────────────────────────────────────────────────

  addDecision(ir, {
    given: 'IoT device, WiFi/BLE needed, cost-sensitive, prototyping',
    prefer: 'ESP32 (ESP-IDF or Arduino framework) over Raspberry Pi',
    because: '$3-5/unit, deep sleep <10uA, built-in WiFi+BLE, sufficient for sensor/actuator workloads',
    unless: 'need Linux (camera processing, ML inference) — then RPi or similar SBC',
    tags: ['embedded', 'iot', 'esp32', 'microcontroller'],
    novelty: 'well_known', spectrum: 'simplicity',
  });

  addDecision(ir, {
    given: 'real-time signal processing, custom hardware interface, FPGA needed',
    prefer: 'Lattice iCE40 (open toolchain: Yosys+nextpnr) for learning/small projects; Xilinx/Intel for production',
    because: 'fully open source synthesis toolchain; fast iteration; sufficient for SPI/I2C/UART bridges and DSP prototyping',
    tags: ['embedded', 'fpga', 'hardware', 'real-time'],
    novelty: 'similar_to_known', spectrum: 'enterprise',
  });

  // ─── Observability ──────────────────────────────────────────────────

  addDecision(ir, {
    given: 'distributed system, need traces + metrics + logs correlated',
    prefer: 'OpenTelemetry SDK → vendor-agnostic collector → backend of choice',
    because: 'instrument once, send anywhere (Grafana, Datadog, Honeycomb); avoid vendor lock-in on instrumentation',
    tags: ['observability', 'opentelemetry', 'tracing', 'metrics'],
    novelty: 'well_known', spectrum: 'balanced',
  });

  // ─── Best practices as behaviors ────────────────────────────────────

  addBehavior(ir, {
    statement: 'For any module M: M SHALL depend on abstractions, not concretions (Dependency Inversion).',
    source: 'SOLID principles — Robert C. Martin',
    entities: ['Module', 'Interface'],
    type: 'invariant',
  });

  addBehavior(ir, {
    statement: 'For any class C: C SHALL have exactly one reason to change (Single Responsibility).',
    source: 'SOLID principles — Robert C. Martin',
    entities: ['Class'],
    type: 'invariant',
  });

  addBehavior(ir, {
    statement: 'For any service S in production: S MUST export health check, readiness probe, and structured logs.',
    source: 'Twelve-Factor App — factor XI (Logs), Kubernetes best practices',
    entities: ['Service'],
    type: 'precondition',
  });

  addBehavior(ir, {
    statement: 'For any user input I: I MUST be validated at the system boundary before processing.',
    source: 'OWASP Top 10 — A03:2021 Injection',
    entities: ['Input', 'Validation'],
    type: 'precondition',
  });

  addBehavior(ir, {
    statement: 'For any secret S: S MUST NOT appear in source code, logs, or error messages.',
    source: 'OWASP Top 10 — A07:2021 Security Misconfiguration',
    entities: ['Secret', 'Configuration'],
    type: 'invariant',
  });

  addBehavior(ir, {
    statement: 'For any database migration M: M MUST be backward-compatible (expand-contract pattern) in zero-downtime deployments.',
    source: 'Evolutionary Database Design — Martin Fowler / Pramod Sadalage',
    entities: ['Migration', 'Database'],
    type: 'constraint',
  });

  return ir;
}

// ─── CLI Commands ───────────────────────────────────────────────────────────

let _core;
function getCore() { if (!_core) _core = require('./core.cjs'); return _core; }

async function cmdClassifyNovelty(conceptsJson) {
  const concepts = JSON.parse(conceptsJson || '[]');
  const results = await classifyNoveltyBatch(concepts);
  getCore().output(results);
}

function cmdCuratedDecisions() {
  const ir = curatedDecisions();
  getCore().output({
    decisions: ir.decisions.length,
    behaviors: ir.behaviors.length,
    total_points: ir.decisions.length + ir.behaviors.length,
  });
}

module.exports = {
  classifyNovelty,
  classifyNoveltyBatch,
  curatedDecisions,
  cmdClassifyNovelty,
  cmdCuratedDecisions,
};
