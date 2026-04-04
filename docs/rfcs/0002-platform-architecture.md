# RFC-0002: Eclusa — Unified Platform Architecture

Status: DRAFT
Author: Nathan
Date: 2026-04-04

## 0. What eclusa is

Eclusa is an evergreen company operating system. Not an AI coding tool.
Not a workflow engine. Not a developer platform. The nervous system of an
organization — where intents enter as ambiguity and exit as artifacts,
with every decision traced, every gate resolved, and the full history
queryable at any timestamp.

Competitive frame: Jira, Linear, Notion — not LangGraph, CrewAI, or
Cursor. 80% of users never open eclusa directly. They interact through
Slack, WhatsApp, email, Figma, webhooks. Eclusa is invisible to most
people. The integration layer is the product surface.

The metaphor: a canal lock (eclusa) equalizes water levels between two
stretches of river. Ambiguity flows in at one level, decisions flow out
at another. The lock is the well — the chamber where the equalization
happens. Gates (comportas) control flow.

## 1. Design philosophy

**The delta, always.** Only genuinely novel information moves through
the system. Everything else resolves against existing indexed knowledge.
This principle applies recursively at file, architecture, human meaning,
and organizational coordination scales.

**Ambiguity up, decisions down.** The fundamental governance primitive.
What can't be resolved at a given level cascades upward until it reaches
someone (human or smarter model) who can resolve it. Decisions flow back
down as constraints. The system discovers where the novel edge is by
hitting it, not by predicting it in advance.

**No agent evaluates its own output.** Trust and cost decrease down the
pipeline. The most expensive model does the least work. Structural gates
(compilers, tests, type checkers) replace consensus voting.

**The application is its data.** State is in the DB. The DB is queryable.
The UI is a view over the DB. Multiple agents and harnesses read-write
against the same governance state. No file-sync gymnastics.

## 2. Ancestry

### The .cog file (v1–v4)

Proved that governance-as-spec works. A single YAML file — no formal
grammar — readable by humans AND machines with the same document. The
LLM's ability to interpret an unformalized spec was the capability test.
Five models bootstrapped correctly from the same file with zero training
data.

The .cog validated: stances (named rules with enforcement levels),
the ambiguity cascade, the vestibular (human orientation file), phase-gate
methodology, entity/behavior/infrastructure as the three pillars, and
git history of the .cog as the intent ledger.

The .cog hit its ceiling when eclusa needed to be more than one harness
talking to one file. Multiple agents, multiple harnesses, queryable state,
a UI — the .cog couldn't carry these.

### The pipeline spec (v5)

Fork GSD. Six-stage narrowing pipeline: Refine → Match → Cohere →
Formalize → Derive → Generate. Qdrant schema commons for typed domain
knowledge. Haskell constraints verified by GHC. The compiler doesn't
hallucinate.

The pipeline proved: schema-as-coordinate-space works (content is a
coordinate in a space that already exists, not something created),
structural gates replace model consensus, and the questioning phase
(GSD's iterative multi-turn refinement) is stage 1.

### The platform (current)

The .cog dissolves into the DB. Governance primitives become platform
entities. The cascade logic lives in durable execution, not in a
document an LLM interprets per-session. The part where the LLM reads
intent and exercises judgment about what the project means — that lives
in the orchestrator's context, fed by the platform from the DB.

## 3. Domain model

Eight entities. Every relationship explicit. The trace chain is the
fundamental invariant: every artifact links all the way back to the
root intent.

### 3.1 Intent

The root. Everything traces here. Intents are a tree (parent_id).

```
intent
  id:           ulid
  parent_id:    intent.id | null
  source:       intent_source
  raw:          text              -- original human words, untouched
  context:      jsonb             -- surrounding conversation, metadata
  embedding:    vector(1024)      -- for historical matching
  created_at:   timestamptz
  created_by:   actor.id
```

```
intent_source: enum
  slack_message | email | voice | chat | webhook | api
  | cli | figma_comment | notion_page | lark_message
  | github_issue | manual
```

Intents arrive from anywhere. The CEO's Slack message, a webhook from
iFood, a developer typing in Claude Code. The platform doesn't care
about the source — it cares about the trace.

### 3.2 Actor

Any participating entity. Not "user" — agents aren't users.

```
actor
  id:           ulid
  type:         human | agent | system | webhook
  identity:     text              -- email, model name, service name
  permissions:  jsonb             -- who can resolve which gates
  created_at:   timestamptz
```

RBAC is decision delegation, not file permissions. Who can resolve
which gates, who can spawn cascades, who can modify cascade shapes,
who can see costs. The permission structure is the org chart made
operational.

### 3.3 Cascade

A living directed graph of work, spawned from an intent. Not a workflow
(implies start/finish). Not a pipeline (implies linear). Cascade carries
the product metaphor: flows through gates, branches, can be evergreen.

```
cascade
  id:           ulid
  intent_id:    intent.id
  shape:        jsonb             -- pydantic_graph definition
  annotations:  jsonb             -- natural language per stage
  narrative:    text              -- overall description
  state:        active | paused | completed | failed | evergreen
  embedding:    vector(1024)      -- for historical pattern matching
  created_at:   timestamptz
  completed_at: timestamptz | null
```

Some cascades terminate (build me a presentation). Some never do
(production deployment is a running cascade — canary, A/B testing,
rollout, monitoring, weekly comms, all branches in the same graph).
"Stable" means all current gates pass automatically.

Cascades can branch (parallel work), nest (sub-cascades), and mutate
at runtime (the orchestrator adds stages as it learns more). An
ambiguity in one branch doesn't block siblings.

There is no distinction between "technical" and "human" work. Deploying
a canary and drafting a blog post about it are both narrowings in the
same cascade, governed by the same primitives, traceable to the same
intent.

### 3.4 Stage

A node in the cascade graph. Two types:

**Narrowing** — reduces ambiguity. An LLM asking questions. A type
checker finding contradictions. A schema match against existing code.
A human picking between options.

**Gate** — a decision point that survived the system's own ability to
resolve it. Arrives to the human with context, a recommendation, and
the implications of each option. Most are one-tap confirmations. Novel
ones get full context.

```
stage
  id:           ulid
  cascade_id:   cascade.id
  type:         narrowing | gate
  state:        pending | active | blocked | resolved | skipped
  input:        jsonb
  output:        jsonb | null
  depends_on:   ulid[]            -- graph edges
  served_by:    ulid[]            -- session_ids
  created_at:   timestamptz
  resolved_at:  timestamptz | null
  resolved_by:  actor.id | null
```

### 3.5 Session

A harness execution. The runtime envelope for agent work.

```
session
  id:           ulid
  stage_ids:    ulid[]
  harness_type: text              -- claude_code | codex | opencode | custom
  model:        text
  model_swaps:  jsonb             -- [{from, to, reason, swapped_at}]
  message_history: jsonb          -- platform format, not harness-native
  workspace_ref: text | null      -- object storage path when paused
  state:        running | paused | completed | failed
  cost:         jsonb             -- tokens_in, tokens_out, api_calls,
                                  -- tool_calls, wall_time_ms, estimated_usd
  created_at:   timestamptz
  paused_at:    timestamptz | null
  resumed_at:   timestamptz | null
  completed_at: timestamptz | null
```

Sessions are portable across models. Between pause and resume, the
platform can swap to a cheaper model or a newer one. The message
history is the platform's format — harness-specific adapters translate
on ingress/egress.

### 3.6 Artifact

The bridge between eclusa and the outside world.

```
artifact
  id:           ulid
  intent_id:    intent.id         -- root trace, always
  cascade_id:   cascade.id
  stage_id:     stage.id
  session_id:   session.id | null
  type:         artifact_type
  external_ref: text              -- commit SHA, API response id, URL
  external_sys: text              -- github, aws, slack, linear, etc.
  payload:      jsonb | null      -- captured request/response (redacted)
  created_at:   timestamptz
```

```
artifact_type: enum
  git_commit | git_branch | git_pr | api_request | api_response
  | deployment | file_created | message_sent | webhook_out
  | config_change | external_state
```

The platform proxy layer automatically creates artifact records for
every outbound call from a harness. The harness doesn't explicitly
register artifacts — the proxy sees everything.

### 3.7 Ledger entry

The sacred record. Append-only. Never deleted, never mutated. The
table has no UPDATE/DELETE grants for application roles.

```
ledger_entry
  id:           ulid
  intent_id:    intent.id | null
  cascade_id:   cascade.id | null
  stage_id:     stage.id | null
  session_id:   session.id | null
  actor_id:     actor.id
  type:         ledger_type
  content:      jsonb
  confidence:   numeric | null
  reversible:   boolean
  artifact_ids: ulid[]
  timestamp:    timestamptz
```

AS OF TIMESTAMP: the ledger is queryable at any historical moment.
"What was running at 3am Tuesday?" is a query, not forensics.
Rollback is "resume cascade from this ledger timestamp," not a
panic operation.

### 3.8 Tool

An external capability. MCP server, API, code execution environment,
deployment pipeline, CMS, Slack channel.

```
tool
  id:           ulid
  name:         text
  interface:    jsonb             -- typed schema
  auth_ref:     text              -- secret manager reference
  cost_profile: jsonb | null
  registered_by: actor.id
  created_at:   timestamptz
```

## 4. Temporal knowledge layer

Informed by Zep/Graphiti (arXiv:2501.13956). The platform maintains a
temporal knowledge graph alongside the relational domain model.

### 4.1 Three-tier knowledge graph

**Episode tier.** Raw ingested data. Every session transcript, every
Slack message, every intent submission. Non-lossy. The episode is
preserved exactly as received, with a reference timestamp. This is the
equivalent of Zep's episodic subgraph — raw data from which higher-order
knowledge is extracted.

**Entity tier.** Extracted from episodes via LLM. Entities are durable
concepts that survive across sessions: people, projects, APIs, business
rules, deployment targets, recurring decisions. Entity resolution merges
duplicates. Entities carry embeddings for semantic search and summaries
for retrieval.

Facts are edges between entities. Each fact carries four timestamps
(bi-temporal model):

```
fact
  id:           ulid
  source_entity: entity.id
  target_entity: entity.id
  predicate:    text              -- natural language fact
  embedding:    vector(1024)
  t_valid:      timestamptz       -- when the fact became true in the world
  t_invalid:    timestamptz | null -- when the fact stopped being true
  t_created:    timestamptz       -- when the system learned it
  t_expired:    timestamptz | null -- when a newer fact superseded it
  source_episodes: ulid[]         -- provenance back to raw data
```

The bi-temporal model is the intent ledger formalized. t_created/t_expired
track what the system knew and when (transactional timeline). t_valid/
t_invalid track what was actually true in the world (event timeline).
Together they answer: "what did we believe about X at time T?" and
"what was actually true about X at time T?"

**Community tier.** Clusters of strongly connected entities with
summarized descriptions. Built via label propagation with dynamic
extension (new entities join the plurality community of their neighbors).
Communities are the retrieval accelerator — search community names first,
drill down to entities and facts. This is the high-level "what domains
does this organization operate in?" view.

### 4.2 Edge invalidation

When a new fact contradicts an existing one, the old fact is not deleted.
Its t_invalid is set to the new fact's t_valid. The old fact remains
queryable for historical analysis. The LLM compares new facts against
semantically similar existing facts (constrained to the same entity
pairs) to identify contradictions.

This is the mechanized version of what the .cog never had. When a stance
was superseded, the old one just disappeared from the file. Now the
knowledge layer preserves the full history of what was believed and when,
with explicit invalidation chains.

### 4.3 Hybrid search

Three search methods, each targeting different similarity:

- **Cosine semantic similarity** over embeddings (what means the same)
- **BM25 full-text search** over predicates and entity names (what uses
  the same words)
- **Breadth-first graph traversal** from seed entities (what appears in
  the same context)

Results are reranked (RRF, MMR, or cross-encoder for high-stakes queries)
and formatted into context strings for the orchestrator or any agent that
needs institutional memory.

### 4.4 Integration with domain model

The knowledge graph is not a replacement for the relational domain model.
The eight domain entities (intent, actor, cascade, stage, session,
artifact, ledger entry, tool) live in Postgres with their explicit
relationships and trace chains. The knowledge graph lives alongside,
extracting higher-order patterns from the same data.

The orchestrator queries both: the relational model for "what cascades
are active?" and the knowledge graph for "what does this organization
know about payment processing?" or "the last time we deployed on a
Friday, what happened?"

Storage: Postgres + pgvector for the relational model and embeddings.
The knowledge graph entities (episodes, semantic entities, facts,
communities) are additional Postgres tables with pgvector HNSW indexes.
No Neo4j dependency. Graph traversal via recursive CTEs or materialized
adjacency.

## 5. The platform

The platform IS the durable execution engine. It manages harness
containers and owns the lifecycle of every agent session.

For each harness container, the platform:
- Starts it with input (intent, sub-task, cascade context)
- Proxies ALL external calls through itself (inspectable, loggable)
- Captures full message history to DB in real time
- Can pause (gate hit, budget exceeded, human offline)
- Can resume (gate resolved, budget replenished)
- Can restart (crash recovery, same state from DB)
- Can hot-swap the model (same message history, different model)
- Can transfer to a different harness type entirely
- Logs token consumption, cost, errors, tool calls

The harness never knows it was paused. From its perspective,
ambiguityUp returned an answer. Could have been 200ms or 48 hours.

### 5.1 The orchestrator

The orchestrator is just a harness running a smart model. Not
architecturally special. What makes it "the orchestrator" is what
the platform feeds it: full cascade state, intent history, knowledge
graph context, available tools/harnesses, budget constraints.

If it crashes, the platform restarts it from DB state. If the routing
decision is routine, the platform restarts it on a cheaper model with
the same history. The orchestrator is expensive only when the decision
is hard.

### 5.2 Visibility layers

**Back office** — eclusa's own UI. Active cascades, pending gates,
session transcripts, token/cost dashboard, ledger queries, cascade
configuration, knowledge graph explorer. For product people, leads,
engineers, ops.

**Front office** — Slack, WhatsApp, email, Figma, Lark, Notion,
webhooks. For everyone else. The system meets people where they are
and only asks the minimum question needed to keep the cascade moving.
The CEO never logs into eclusa. The delivery person never logs into
eclusa.

80% of users interact through the front office. The integration layer
is the actual product surface for most people.

## 6. The narrowing pipeline

The software construction pipeline from v5 survives as a cascade
template — the default shape for "build software" intents. It is not
the only cascade shape. Release engineering, content production,
onboarding, build-vs-buy evaluation — all are cascade shapes with
their own stage topologies.

### Software construction cascade (default template)

```
STAGE 1: REFINE
  Type:     narrowing
  Input:    noisy human intent
  Agent:    frontier model, multi-turn conversation
  Method:   GSD's questioning phase — iterative, interactive,
            multi-select UI, researcher sub-agents for context
  Output:   refined intent doc + domain concepts for matching
  Gate:     human confirms scope

STAGE 2: MATCH
  Type:     narrowing
  Input:    domain concepts from stage 1
  Agent:    embedding model + Qdrant/pgvector lookup
  Method:   query the schema commons, return ranked matches
  Output:   matched source set
  Gate:     human confirms matches

STAGE 3: COHERE
  Type:     narrowing
  Input:    matched source set
  Agent:    Sonnet-class model
  Method:   check composition — type boundaries, auth models,
            data model friction, missing links
  Output:   coherence report
  Gate:     no blocking incompatibilities, or human override

STAGE 4: FORMALIZE
  Type:     narrowing
  Input:    coherent sources + human business rules
  Agent:    LLM drafts Haskell, GHC verifies
  Method:   auto-generate Haskell types from matched sources,
            LLM drafts constraint functions, ghc -fno-code
  Output:   constraints.hs — compiles or doesn't
  Gate:     GHC accepts it

STAGE 5: DERIVE
  Type:     narrowing
  Input:    source specs + compiled constraints
  Agent:    mechanical derivation + light LLM
  Method:   derive BDD/E2E tests from structure + constraints
  Output:   test suite
  Gate:     tests internally consistent

STAGE 6: GENERATE
  Type:     narrowing
  Input:    test suite + sources + constraints
  Agent:    cheapest capable model
  Method:   code gen against known typed interfaces
  Output:   code that passes all tests
  Gate:     ALL TESTS PASS
```

The pipeline doesn't end at code generation. It flows into the release
cascade: build → deploy → canary → A/B → continuous monitoring. One
cascade, many phases, no terminal state.

## 7. The schema commons

A pgvector-backed index of typed domain knowledge. Anything with
recoverable structure is a valid source: OpenAPI specs, Prisma schemas,
SQL DDL, GraphQL SDL, protobuf definitions, TypeScript type files,
Gherkin features, structured English, entire git repos.

The parser layer normalizes all sources into the same intermediate
representation: entities with typed fields, relations, operations,
constraints. This IR is embedded and stored. The matching stage queries
against it.

The schema commons is also where the knowledge graph's entity tier
draws its initial vocabulary. Matched API types become entities in the
graph. Business rules formalized as Haskell constraints become facts.
The commons feeds the graph; the graph enriches the commons with
organizational usage patterns.

## 8. Infrastructure

`docker-compose up`, done.

```
services:
  db:         postgres + pgvector
  qdrant:     schema commons + knowledge graph search
  execution:  temporal / dbos (durable workflows)
  proxy:      outbound call interception + logging
  web:        back office UI
  adapters:   slack, lark, notion, email, webhook receivers
```

Single Postgres instance. All domain entities in one database. pgvector
HNSW indexes on embeddings. Ledger entries append-only. Object storage
for workspace snapshots (keyed by session_id, created on pause, read
on resume).

Single tenant. One eclusa instance per company. `docker-compose up`
gives you your own coordination substrate.

## 9. Decision quality (self-calibration)

The ledger enables measuring decision quality without defining it
a priori. Derived metrics:

- **Gate necessity rate** — percentage of gates where the human chose
  something other than the system's recommendation. High rate = system
  under-resolves. Low rate = gates are rubber stamps (remove them).
- **Orchestrator absorption rate** — percentage of ambiguityUp that the
  orchestrator resolves without escalating to human. Tracks whether the
  orchestrator is learning from past resolutions.
- **Resolution latency** — time from gate creation to resolution. High
  latency = wrong person, wrong channel, or wrong question.
- **Decision durability** — how often a gate resolution leads to rework
  within the same cascade. Frequent rework = the gate didn't surface
  enough context.
- **Cascade rework rate** — how often completed cascades are reopened.
  Tracks systemic pattern quality.

These metrics feed back as proposed adjustments to cascade templates,
gate thresholds, and routing rules. The system recalibrates from its
own history.

## 10. What survived from the .cog

The .cog dissolved into the platform, but its concepts live on:

| .cog concept | platform equivalent |
|---|---|
| stances | gate enforcement rules in cascade templates |
| vestibular | actor preferences + escalation config |
| entities | schema commons entries + knowledge graph entities |
| behaviors | Haskell constraints + test suites |
| cascade section | cascade entity + stage graph |
| methodology phases | cascade template with stage ordering |
| provenance | trace chain (intent → cascade → stage → session → artifact) |
| intent ledger | ledger_entry table (append-only, AS OF TIMESTAMP) |
| .cog git history | knowledge graph's bi-temporal fact model |
| conservative default | type checker as gate (GHC, test suite) |

The vestibular file (~/.vestibular) may survive as a portable human
orientation artifact — register, autonomy mode, model trust tiers,
escalation channels. It describes the human, not the project. Whether
it remains a file or becomes actor configuration in the DB is an open
question that doesn't need to be resolved before building.

## 11. Open questions

- **Vestibular: file or DB?** The vestibular proved valuable as a
  portable file across harnesses. In the platform world, actor
  preferences could live in the DB. Both could coexist (file for
  bootstrapping standalone harnesses, DB for platform-connected work).

- **Graph DB vs recursive CTEs.** The knowledge graph's BFS traversal
  is natural in Neo4j but feasible in Postgres via recursive CTEs or
  materialized adjacency lists. Neo4j adds operational complexity.
  Decision deferred until query patterns stabilize.

- **Qdrant vs pgvector.** Qdrant ships in the compose stack for the
  schema commons. pgvector handles domain model embeddings. Two vector
  search systems is one too many. Consolidation direction TBD — likely
  pgvector absorbs everything once HNSW performance is validated at
  the scale of the schema commons.

- **Community refresh cadence.** Label propagation with dynamic
  extension delays full recomputation but gradually diverges. What
  triggers a full refresh? Time-based? Drift-based? Ledger-event-based?

## 12. Implementation path

### Phase 1: Domain skeleton
Postgres schema for the eight entities. Ledger append-only enforcement.
Basic trace chain queries. `docker-compose up` boots DB + placeholder
web UI showing pending gates.

### Phase 2: Durable execution
Temporal/DBOS integration. Cascades as workflows. Gates as signals.
Session pause/resume with workspace snapshots. One harness type
(Claude Code) connected.

### Phase 3: Schema commons
Qdrant container. Parser layer (OpenAPI → IR, Prisma → IR, SQL DDL →
IR). Embedding pipeline. `eclusa:ingest` commands. Starter pack of
~50 common SaaS API specs.

### Phase 4: Software construction cascade
Six-stage pipeline as the default cascade template. Haskell constraint
workflow. GHC as gate. Test derivation. Code generation.

### Phase 5: Knowledge graph
Episode ingestion from session transcripts. Entity extraction and
resolution. Fact extraction with bi-temporal timestamps. Edge
invalidation. Community detection. Hybrid search (cosine + BM25 + BFS).

### Phase 6: Front office
Slack adapter. WhatsApp adapter. Email adapter. Gate surfacing through
integration channels. Intent ingestion from external platforms.

### Phase 7: Self-calibration
Decision quality metrics derived from ledger. Feedback loop to cascade
templates. Gate necessity analysis. Orchestrator absorption tracking.

## 13. Success criteria

1. `docker-compose up` boots a working eclusa instance
2. Intent submitted via Slack → cascade created → gates surface in Slack
3. Software construction cascade: intent → matched sources → Haskell
   constraints → tests → generated code → all tests pass
4. Full trace chain: any artifact → session → stage → cascade → intent
5. AS OF TIMESTAMP: ledger queryable at any historical moment
6. Knowledge graph: "why does the red carpet workflow work this way?"
   answered from the ledger without documentation
7. Session hot-swap: pause on Opus, resume on Sonnet, same history
8. Gate resolution latency < 5 minutes for one-tap confirmations
9. Front office handles 80% of human interactions without back office
10. Self-calibration produces actionable cascade template adjustments
    from the first 100 resolved gates
