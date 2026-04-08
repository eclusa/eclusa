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

**No agent evaluates its own output.** This is topology, not policy.
Work sessions produce artifacts inside harnesses with tools. Judgment
passes evaluate artifacts outside harnesses with no tools. The evaluator
physically cannot modify the work it's judging. Trust and cost decrease
down the pipeline. The most expensive model does the least work.
Structural gates (compilers, tests, type checkers) replace consensus
voting.

**The application is its data.** State is in the DB. The DB is queryable.
The UI is a view over the DB. Multiple agents and harnesses read-write
against the same governance state. The database is the execution engine.
No workflow framework dependency. The executor is a stateless loop that
reads the graph and dispatches. If it crashes, restart it — all state
survives in Postgres.

**Code is the last output, not the objective.** Code is only written
after the test cases are fully solved between LLMs and humans. The
pipeline's purpose is narrowing ambiguity into verified constraints.
Code generation is the mechanical final step — the least interesting
stage, served by the cheapest model.

**Three compute types.** Work sessions do the work (tools, artifacts,
managed lifecycle). Judgment passes judge the work (single completion,
no tools, stateless). The executor moves the data (graph traversal,
dispatch, read/write). The cheapest model that can hold a tool loop
does the work. The best model available does the thinking. The executor
has no model.

**Migration, not mutation.** Cascade shape evolution is a data
migration, not runtime mutation. Like ALTER TABLE. Running cascades
either complete on their original shape or migrate to the new one.
The migration is a ledger entry and an artifact. If it's not in the
ledger, it didn't happen.

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
entities. The cascade logic lives in durable execution — Postgres state
+ a stateless executor — not in a document an LLM interprets per-session.
The part where the LLM reads intent and exercises judgment about what
the project means — that lives in the orchestrator's context, fed by
the platform from the DB.

## 3. Domain model

Nine core entities. Every relationship explicit. The trace chain is the
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

Cascades can branch (parallel work), nest (sub-cascades), and evolve
via migration (the orchestrator proposes a new shape, the executor
applies it on next dispatch, the ledger records the transition).
An ambiguity in one branch doesn't block siblings.

Cascade migration is a data migration, not runtime mutation.
A running cascade either completes on its original shape or migrates
to a new one. The migration itself is a ledger entry:
`cascade_migration: cascade X, stage 4, shape v1 → v2, reason`.
Running work sessions are not affected mid-execution — the migration
applies on the next dispatch. When a paused session completes and the
executor dispatches the next stage, it uses the migrated shape. The
old shape is preserved in the ledger for trace chain integrity.

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
  output:       jsonb | null
  depends_on:   ulid[]            -- graph edges
  served_by:    ulid[]            -- work_session or judgment_pass ids
  created_at:   timestamptz
  resolved_at:  timestamptz | null
  resolved_by:  actor.id | null
```

### 3.5 Three compute types

Stages are served by one of three compute types. The split is the
platform's core architectural invariant.

#### 3.5.1 Work session

An agent running inside a harness with tools, producing artifacts.
Managed lifecycle: start, proxy, pause, resume, swap, transfer.

```
work_session
  id:           ulid
  stage_ids:    ulid[]
  harness_type: text              -- native | claude_code | codex | opencode | custom
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

Work sessions are expensive to orchestrate (proxy, workspace snapshots,
tool call management) but can run on cheaper models for routine work.
The platform manages their full lifecycle. The harness never knows it
was paused — from its perspective, ambiguityUp returned an answer.
Could have been 200ms or 48 hours.

The harness is a compute backend, not a domain concept. `native` means
model API + Pydantic AI tools + direct DB writes — no container, no
proxy, no PTY. The executor calls the model API, the model uses tools,
results write to Postgres. Claude Code, Codex, OpenCode are other
backends with their own UX and tool ecosystems. The platform doesn't
care which backend serves a stage — it cares about the trace.

Sessions are portable across models. Between pause and resume, the
platform can swap to a cheaper model or a newer one. The message
history is the platform's format — harness-specific adapters translate
on ingress/egress. For native sessions, no adapter needed — the
platform format IS the session format.

#### 3.5.2 Judgment pass

A single API completion. No harness. No tools. No agent loop. The
model receives a prepared context document and renders a verdict.
One request, one response.

```
judgment_pass
  id:           ulid
  stage_ids:    ulid[]
  model:        text
  context_ref:  text              -- object storage path to prepared context
  context_hash: text              -- blake3 hash, dedup identical evaluations
  prompt:       text              -- the evaluation question
  response:     jsonb             -- model's verdict, structured
  confidence:   numeric | null    -- model's self-reported confidence
  cost:         jsonb             -- tokens_in, tokens_out, estimated_usd
  created_at:   timestamptz
  completed_at: timestamptz
```

Zero orchestration overhead. One API call. The cost is in the model,
not the infrastructure. This is where you spend on frontier reasoning.

The context is not the raw session history. It is a **prepared
document** — the platform transforms the portable session data before
it becomes context. Strip tool call noise. Summarize long middles.
Foreground decisions and artifacts. Context preparation is itself a
stage in the cascade (a cheap narrowing that runs locally).

Judgment passes cannot modify the work. They can only read and
evaluate. This is the topological enforcement of "no agent evaluates
its own output."

#### 3.5.3 Fan-out evaluation

At any point in a cascade the platform can fan out the portable
session to n models simultaneously as judgment passes. Each model
reasons against the same prepared context independently.

```
fan_out
  id:           ulid
  stage_id:     stage.id
  context_ref:  text              -- shared prepared context
  prompt:       text              -- shared evaluation question
  passes:       ulid[]            -- judgment_pass.ids
  convergence:  jsonb             -- agreement matrix
  verdict:      converged | diverged | partial
  created_at:   timestamptz
  completed_at: timestamptz
```

Where models converge, confidence is high — auto-resolve. Where they
diverge, the divergence points are the genuine ambiguity. Model
disagreement IS the ambiguity detector. Divergence triggers a gate
that surfaces to the human with each model's reasoning and where
they split.

Fan-out is cheap. Each pass is a single API call. Context preparation
is shared across all n passes. Running 5 judgment passes against the
same prepared context costs 5x the token cost and zero additional
orchestration.

**Fan-out use cases:**

- **Intent validation.** After Stage 1 Refine, hand refined + raw
  intent to n models: "does this faithfully represent what the human
  wanted?" Convergence = proceed. Divergence = the questions Stage 1
  missed.

- **Gate pre-evaluation.** Before surfacing a gate, fan out: "what
  should the decision be and why?" Convergence = auto-resolve, human
  never sees it. Divergence = human gets n perspectives instead of
  one recommendation.

- **Cascade review.** At completion, fan out the full trace: "was
  this the right decomposition?" Agreement = template is sound.
  Disagreement = template needs revision.

- **Drift detection.** Periodically fan out knowledge graph state:
  "contradictions? stale facts? missing entities?" Multi-model audit
  replaces scheduled self-bootstrap.

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
judgment pass response, every Slack message, every intent submission.
Non-lossy. The episode is preserved exactly as received, with a
reference timestamp.

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
drill down to entities and facts.

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
The nine domain entities live in Postgres with their explicit
relationships and trace chains. The knowledge graph lives alongside,
extracting higher-order patterns from the same data.

The orchestrator queries both: the relational model for "what cascades
are active?" and the knowledge graph for "what does this organization
know about payment processing?" or "the last time we deployed on a
Friday, what happened?"

Storage: Postgres + pgvector for everything. The knowledge graph entities
(episodes, semantic entities, facts, communities) are additional Postgres
tables with pgvector HNSW indexes. Graph traversal via recursive CTEs or
materialized adjacency. No external vector DB dependency.

## 5. The execution substrate

The database is the execution engine. All state lives in Postgres. The
executor is a stateless loop that reads the cascade graph, dispatches
whatever is ready, and writes results back. If it crashes, restart it.
Durable execution is not a framework — it's the fact that the DB already
has everything.

### 5.1 The executor

```python
# Pseudocode. The real thing is ~300-500 lines.

while True:
    # 1. Find ready stages
    ready = db.query("""
        SELECT s.* FROM stage s
        JOIN cascade c ON s.cascade_id = c.id
        WHERE s.state = 'pending'
          AND c.state IN ('active', 'evergreen')
          AND NOT EXISTS (
              SELECT 1 FROM stage dep
              WHERE dep.id = ANY(s.depends_on)
                AND dep.state NOT IN ('resolved', 'skipped')
          )
        FOR UPDATE SKIP LOCKED
    """)

    for stage in ready:
        stage.state = 'active'

        if stage.type == 'narrowing':
            dispatch_narrowing(stage)
        elif stage.type == 'gate':
            if stage.auto_resolvable():
                resolve_gate(stage)
            else:
                surface_gate(stage)  # Slack, email, webhook
                # gate stays active until external resolution

    # 2. Check for pending cascade migrations
    #    (orchestrator may have proposed new shapes)

    # 3. Wait for change notification
    db.wait_for_notify('stage_changed', timeout=5)
```

Postgres SKIP LOCKED handles concurrency — multiple executor instances
can run without double-dispatch. LISTEN/NOTIFY avoids polling. Gate
resolutions arrive via adapter callbacks (Slack button tap, webhook,
API call) which write to the DB and fire NOTIFY.

This pseudocode is deliberately naive. The real implementation will
need edge cases: cascade migration queued during dispatch (migration
never interrupts a dispatch in progress — it enqueues and applies on
the next cycle), concurrent gate resolution (two humans resolve the
same gate simultaneously), executor restart recovery (incomplete
dispatch from a crashed executor), and stage timeout handling. But the
pseudocode proves the point: the core scheduling algorithm is one SQL
query. Edge cases are error handling around that query, not a different
architecture.

### 5.2 Stage dispatch

The executor dispatches stages based on compute type:

**Narrowing served by work session:**
1. Start harness container with stage input
2. Register proxy for outbound call interception
3. Stream message history to DB in real time
4. On ambiguityUp (gate hit): pause container, create gate stage
5. On completion: write output, mark stage resolved
6. On failure: mark stage failed, cascade decides (retry/skip/fail)

**Narrowing served by judgment pass:**
1. Prepare context from upstream stage outputs
2. Single API call — no harness, no tools, no proxy
3. Parse structured response
4. Write verdict, mark stage resolved

**Narrowing served by fan-out:**
1. Prepare shared context (once, reused across all passes)
2. Fire n judgment passes in parallel
3. Collect verdicts, compute convergence
4. If converged: auto-resolve with consensus verdict
5. If diverged: create gate with full divergence context

**Gate resolution:**
1. Surface to human via appropriate channel
2. Wait for callback (adapter writes resolution to DB, fires NOTIFY)
3. Mark gate resolved
4. If resolution changes cascade shape: orchestrator proposes migration,
   ledger records it, executor applies on next dispatch

### 5.3 The orchestrator

The orchestrator is just a harness running a smart model. Not
architecturally special. What makes it "the orchestrator" is what
the platform feeds it: full cascade state, intent history, knowledge
graph context, available tools/harnesses, budget constraints.

If it crashes, the platform restarts it from DB state. If the routing
decision is routine, the platform runs it on a cheaper model with
the same history. The orchestrator is expensive only when the decision
is hard. When the orchestrator determines a cascade needs a different
shape, it proposes a cascade migration — a new shape written to the DB
as a pending migration. The migration is a gate: a human approves it,
or the system flags it via self-calibration metrics for human review,
or a fan-out evaluates whether the migration improves the cascade.
Making migration automatic is itself a human decision, not a system
default. The executor applies approved migrations on the next dispatch
cycle.

### 5.4 Visibility layers

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
  Fan-out:  intent validation — n models check refined vs raw
            intent for faithfulness. Divergence = missed questions.

STAGE 2: MATCH
  Type:     narrowing
  Input:    domain concepts from stage 1
  Agent:    embedding model + pgvector lookup
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

  Haskell is the compile-time gate. Humans never see it. The human
  interface to this stage is natural language chat — the LLM translates
  business rules into Haskell and translates Haskell back into english.
  Humans can ask "what happens if I change X?" and the LLM runs the
  hypothetical against the compiled constraints. The LLM writes Haskell
  from english and reads Haskell back to english — same translation
  capability, both directions.

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

  Code is the last output, not the objective. By the time generation
  starts, all ambiguity is resolved — the constraints compile, the
  tests are derived, the interfaces are typed. This stage is mechanical.
  The cheapest model that can pass the tests does the work. If a future
  model can generate from constraints without an intermediate code step,
  this stage disappears.
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
  executor:   stateless python process (~300-500 lines)
  proxy:      outbound call interception + logging
  web:        back office UI
  adapters:   slack, lark, notion, email, webhook receivers
```

Single Postgres instance. All domain entities, all embeddings, all
knowledge graph data in one database. pgvector HNSW indexes on
embeddings. Ledger entries append-only. Object storage for workspace
snapshots (keyed by session_id, created on pause, read on resume).

Single tenant. One eclusa instance per company. `docker-compose up`
gives you your own coordination substrate.

Multiple executor instances can run concurrently — Postgres SKIP LOCKED
prevents double-dispatch. Horizontal scaling is "run more executor
processes."

## 9. Decision quality (self-calibration)

The ledger enables measuring decision quality without defining it
a priori. Eight metrics, five from governance outcomes, three from
fan-out evaluation:

**Gate necessity rate** — percentage of gates where the human chose
something other than the system's recommendation. High rate = system
under-resolves. Low rate = gates are rubber stamps (remove them).

**Orchestrator absorption rate** — percentage of ambiguityUp that the
orchestrator resolves without escalating to human. Tracks whether the
orchestrator is learning from past resolutions.

**Resolution latency** — time from gate creation to resolution. High
latency = wrong person, wrong channel, or wrong question.

**Decision durability** — how often a gate resolution leads to rework
within the same cascade. Frequent rework = the gate didn't surface
enough context.

**Cascade rework rate** — how often completed cascades are reopened.
Tracks systemic pattern quality.

**Model convergence rate** — percentage of fan-outs where all n models
agree. Trending up = routine decisions or improving models. Trending
down = harder work or messier domain.

**Minority model accuracy** — when the human picks the minority verdict,
track which model. Over time reveals per-model judgment strengths by
decision type. Feeds model selection policy.

**Fan-out necessity rate** — of all fan-outs, how often did the
multi-model verdict differ from a single-model evaluation? Below 10% =
fan-out is wasting tokens on this stage type. Above 30% = catching real
blind spots.

```
Metric                       Measures                  Feeds back to
─────────────────────────    ─────────────────────     ──────────────────────
Gate necessity rate          Human override frequency  Gate threshold tuning
Orchestrator absorption      Self-resolution rate      Orchestrator capability
Resolution latency           Surfacing effectiveness   Channel/routing config
Decision durability          Resolution quality        Context preparation
Cascade rework rate          Decomposition quality     Cascade template design
Model convergence rate       Ambiguity detection       Fan-out trigger policy
Minority model accuracy      Per-model judgment        Model selection policy
Fan-out necessity rate       Fan-out ROI               Fan-out scope tuning
```

These metrics feed back as proposed adjustments to cascade templates,
gate thresholds, routing rules, fan-out policy, and model selection.
The system recalibrates from its own history.

## 10. Open questions

- **Graph DB vs recursive CTEs.** The knowledge graph's BFS traversal
  is natural in Neo4j but feasible in Postgres via recursive CTEs or
  materialized adjacency lists. Neo4j adds operational complexity.
  Decision deferred until query patterns stabilize.
- **Community refresh cadence.** Label propagation with dynamic
  extension delays full recomputation but gradually diverges. What
  triggers a full refresh? Time-based? Drift-based? Ledger-event-based?
- **Fan-out model roster.** Fixed set (always same 3-5 models) or
  dynamic per decision type? Start fixed, let minority model accuracy
  data drive roster evolution.
- **Context preparation granularity.** How much to transform raw
  session history before judgment passes? Minimal (full history) vs
  aggressive (summarize, strip, restructure). Likely task-dependent —
  intent validation wants the raw exchange, code review wants a
  structured diff summary. Context prep strategies per cascade template,
  not global.
- **Fan-out cost control.** Starting heuristic: fan out only at gates,
  only when orchestrator confidence is below threshold, only for
  cascades above a cost floor. Let fan-out necessity rate refine the
  policy.

## 11. Implementation path

### Phase 1: Domain skeleton

Postgres schema for all entities including work_session, judgment_pass,
fan_out. Ledger append-only enforcement. Trace chain queries. Executor:
simplest possible version — poll loop, no LISTEN/NOTIFY yet.
`docker-compose up` boots DB + executor + placeholder web UI showing
pending stages.

First test: manually insert an intent and a two-stage cascade (one
narrowing + one gate). Executor dispatches the narrowing. Gate surfaces
as a log line. Resolve it by hand (INSERT into ledger). Executor
unblocks the downstream. Trace chain query returns the full path.

### Phase 2: Work sessions

Proxy layer. One harness type (Claude Code). Executor starts harness
container, proxies calls, captures history. Pause/resume via workspace
snapshots. Model hot-swap.

### Phase 3: Judgment passes and fan-out

Judgment pass dispatch (single API call, structured response). Context
preparation as a local stage. Fan-out: shared context, n parallel
passes, convergence computation. First fan-out use case: intent
validation after Stage 1 Refine.

### Phase 4: Schema commons

pgvector HNSW indexes. Parser layer (OpenAPI → IR, Prisma → IR, SQL
DDL → IR). Embedding pipeline. `eclusa:ingest` commands. Starter pack
of ~50 common SaaS API specs.

### Phase 5: Software construction cascade

Six-stage pipeline as cascade template. Haskell constraint workflow.
GHC as structural gate. Test derivation. Code generation. Fan-out
evaluations between stages.

### Phase 6: Knowledge graph

Episode ingestion from session transcripts and judgment pass responses.
Entity extraction and resolution. Fact extraction with bi-temporal
timestamps. Edge invalidation. Community detection. Hybrid search.

### Phase 7: Front office

Slack adapter. WhatsApp adapter. Email adapter. Gate surfacing through
integration channels. Intent ingestion from external platforms.

### Phase 8: Self-calibration

Eight metrics derived from ledger. Feedback loops to cascade templates,
gate thresholds, fan-out policy, model selection. Periodic calibration
as an evergreen cascade.

## 12. Success criteria

1. `docker-compose up` boots a working eclusa instance
2. Intent submitted via Slack → cascade created → gates surface in Slack
3. Software construction cascade: intent → matched sources → Haskell
   constraints → tests → generated code → all tests pass
4. Full trace chain: any artifact → session → stage → cascade → intent
5. AS OF TIMESTAMP: ledger queryable at any historical moment
6. Knowledge graph: "why does the red carpet workflow work this way?"
   answered from the ledger without documentation
7. Session hot-swap: pause on Opus, resume on Sonnet, same history
8. Judgment pass: single-completion evaluation outside harness with
   prepared context, structured verdict in the ledger
9. Fan-out: n models evaluate same context, convergence auto-resolves,
   divergence surfaces as gate with full reasoning
10. Gate resolution latency < 5 minutes for one-tap confirmations
11. Front office handles 80% of human interactions without back office
12. Self-calibration produces actionable adjustments from first 100
    resolved gates