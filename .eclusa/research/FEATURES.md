# Feature Research

**Domain:** Organizational coordination / AI orchestration platform (company operating system)
**Competitive frame:** Jira, Linear, Notion — not LangGraph, CrewAI, Cursor
**Researched:** 2026-04-04
**Confidence:** MEDIUM-HIGH (competitive landscape well-documented; novel AI coordination features have fewer analogues to verify against)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that every coordination platform must have. Missing any of these means the product feels
incomplete relative to Jira/Linear/Notion, regardless of how differentiated the AI layer is.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Work item creation and assignment | Foundational unit of coordination — users assume any platform has this | LOW | In Eclusa, this is intent + cascade stage, not a free-form ticket |
| Status tracking (in progress, blocked, done) | Teams need to know where work stands at a glance | LOW | Stage lifecycle covers this; needs to be surfaced clearly in back office UI |
| Prioritization and ordering | Every PM tool supports backlog ordering and priority labels | LOW | Maps to cascade graph ordering and stage priority fields |
| Dependency mapping | Jira and Linear both show what's blocked by what | MEDIUM | Cascade graph edges are dependencies by nature; needs visual representation |
| Activity feed / audit log | Users expect a changelog on any item | LOW | Append-only ledger provides this structurally; needs a query/render layer |
| Search across work | Users search for items, decisions, artifacts | MEDIUM | Hybrid search (cosine + BM25 + BFS) covers this at the schema commons level |
| Notifications (in-platform and external) | Users expect to be alerted when something requires their attention | LOW | Gates surfaced via Slack/email/WhatsApp adapters fulfill this; in-platform notification still needed for back office |
| RBAC / access control | Teams have different people who can see/do different things | MEDIUM | Documented as "decision delegation" — who resolves which gates, spawns cascades, sees costs |
| Commenting / annotation on work items | Stakeholders expect to discuss items in context | LOW | Judgment pass transcripts partially cover this; explicit comment thread on artifacts is distinct |
| Integrations with development tools (GitHub, etc.) | Software teams expect PR/commit linkage | MEDIUM | Out of scope for v1 but users coming from Linear/Jira will miss this |
| Roadmap / timeline view | Planning horizon visibility expected by PMs | MEDIUM | Cascade graph can render as timeline; not trivial to implement well |
| Reporting and dashboards | Managers expect status rollups and throughput metrics | MEDIUM | Cost dashboard and self-calibration metrics partially cover this; general reporting is separate |
| API / webhooks | Technical teams expect programmatic access and event streams | MEDIUM | Proxy layer intercepts outbound; inbound webhook adapter needed for external triggers |
| Single-command local deployment | Developer-operated tools must boot easily | LOW | `docker-compose up` is already the target |
| Mobile-accessible interface | Users expect to action gates from a phone | LOW | 80% of users are in Slack/WhatsApp anyway; back office doesn't need native app |

---

### Differentiators (Competitive Advantage)

Features that no existing coordination platform offers at this level of rigor. These are where Eclusa
competes — not on UI polish or integration breadth, but on structural correctness.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cascade (directed graph of work) | Work evolves its structure without losing history — impossible in ticket-based systems | HIGH | Core entity; branching, nesting, migration all need to be implemented before most other features are useful |
| Append-only ledger + AS OF queries | Any artifact traces back to the root intent at any point in time — full temporal accountability | HIGH | No coordination platform offers this; regulatory and audit use cases immediately unlock; Postgres append-only with no UPDATE/DELETE grants |
| Ambiguity cascade (escalation by design) | Unresolvable items escalate upward structurally, not via informal Slack messages | MEDIUM | Gate surfacing via adapters is the user-facing expression of this; requires executor + gate dispatch |
| Three compute types (work / judgment / fan-out) | Right compute for each task — cheap models for work, frontier for judgment, no model for graph traversal | HIGH | Topological enforcement that no agent evaluates its own work is the key invariant; this is what distinguishes Eclusa from LangGraph-style pipelines |
| Fan-out evaluation with convergence detection | Model disagreement IS the ambiguity detector — auto-resolve when models agree, gate when they diverge | HIGH | Unique in the coordination space; most platforms use single-model outputs with human review |
| Schema commons (typed domain knowledge index) | Intent arrives as ambiguity; schema commons is the substrate that reduces it to structure | HIGH | pgvector-backed; parsers for OpenAPI, Prisma, SQL DDL, GraphQL, protobuf; no equivalent in Jira/Linear/Notion |
| Temporal knowledge graph (bi-temporal facts) | Facts have validity windows — "what was true on date X" is always answerable | HIGH | Episode → entity → fact → community tier hierarchy; edge invalidation with t_valid/t_invalid; Graphiti (Zep) is closest analogue but not a coordination platform |
| Self-calibration metrics (8 feedback signals) | The system measures its own gate quality and model selection over time | HIGH | Gate necessity, orchestrator absorption, resolution latency, decision durability, cascade rework, model convergence, minority model accuracy, fan-out necessity — feeds back into dispatch policy |
| Integration layer as primary UX | 80% of users never open the back office — Slack/WhatsApp/email IS the product surface | MEDIUM | Adapter pattern with intent ingestion + gate surfacing; no other coordination platform treats integrations as the primary interface |
| Model hot-swap between pause/resume | Portable message history means you can resume a session with a different model | MEDIUM | Enables cost optimization (start expensive, finish cheap) and model continuity across model updates |
| Proxy layer for artifact capture | All outbound tool calls intercepted and recorded — nothing escapes the ledger | MEDIUM | Harness-level proxy; work session artifacts are captured automatically without agent cooperation |
| Context preparation as a staged operation | Stripping noise and foregrounding decisions is a discrete local stage, not an afterthought | MEDIUM | Reduces token waste and improves judgment quality; most platforms pass raw context |
| Haskell constraints verified by GHC | Formal verification of structural constraints — GHC doesn't hallucinate | HIGH | Humans never see Haskell; LLM drafts, compiler verifies; unique in the space |
| Software construction cascade template | Six-stage narrowing pipeline (Refine → Match → Cohere → Formalize → Derive → Generate) as a reusable cascade shape | MEDIUM | Opinionated template for the most common cascade type; reduces setup for software projects |
| Cost dashboard per cascade/session | See exactly what each cascade, stage, and model selection costs | MEDIUM | Per-session LLM cost attribution is technically feasible (token counts per run); no PM tool offers this |

---

### Anti-Features (Deliberately Not Building)

Features that look good on a marketing checklist but would undermine Eclusa's core model.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time collaborative document editing | Users see Notion and expect rich co-editing | Eclusa is not a document editor — adding real-time CRDT sync would consume engineering capacity with no coordination value | Judgment pass transcripts and artifact storage cover the content capture need |
| Free-form ticket creation (Jira-style) | It's the default mental model for work tracking | Bypasses ambiguity resolution — tickets created without cascade structure lose traceability | Intent ingestion via adapters funnels all work through the cascade graph |
| External workflow framework dependency (Temporal, Dagster) | Temporal offers durable execution; Dagster offers orchestration UI | Adds an external runtime that becomes the real execution engine, making Postgres a secondary store | DB is the execution engine — Postgres + SKIP LOCKED + LISTEN/NOTIFY replaces these |
| Multi-tenant SaaS | Most B2B software is SaaS | Multi-tenancy requires namespace isolation, billing, customer onboarding — distinct product problems | Single-tenant per instance; customers run their own instance |
| Custom LLM training / fine-tuning | Companies want models trained on their data | Training infrastructure is a separate product problem; off-the-shelf models with structured prompts are sufficient | Schema commons + context preparation achieves most of the benefit without training |
| Native mobile apps | Users want mobile | Back office is not the primary surface; adapters (Slack, WhatsApp) already run on mobile | Slack/WhatsApp adapters provide mobile access to gates and intent ingestion |
| "AI autopilot" mode (no human gates) | Users imagine fully autonomous execution | Removes the structural check that validates AI output quality; gates exist because ambiguity is real | Gates are the product — the goal is fewer unnecessary gates, not no gates (self-calibration metrics handle this) |
| Inline mutation of ledger entries | Users want to "fix" historical records | Destroys the immutability guarantee — the entire value of AS OF queries depends on the ledger being append-only | Migration cascades + new ledger entries are the correct mutation pattern |
| Built-in sprint ceremonies (standups, retros) | Agile teams expect this from PM tools | Adds meeting management scope; distracts from the coordination substrate mission | Gate surfacing and session transcripts provide the factual basis for any ceremony; ceremony tooling is a separate concern |
| Visual no-code workflow builder | Low-code tools (Zapier, n8n) have popularized this pattern | Cascade structure is a typed graph, not a flowchart — a visual builder would hide the structural model and create a secondary representation that could diverge | Schema commons + cascade templates are the correct abstraction for reusable shapes |

---

## Feature Dependencies

```
Append-only Ledger
    └──required by──> Trace Chain Queries
    └──required by──> AS OF Timestamp Queries
    └──required by──> Activity Feed / Audit Log

Cascade (Directed Graph)
    └──required by──> Stage Lifecycle
                          └──required by──> Work Session Dispatch
                          └──required by──> Judgment Pass Dispatch
                          └──required by──> Fan-out Evaluation

Executor (Stateless Poll Loop)
    └──required by──> Work Session Dispatch
    └──required by──> Gate Surfacing
    └──required by──> Fan-out Convergence Detection

Gate Surfacing
    └──required by──> Slack Adapter (intent ingestion + gate response)
    └──required by──> WhatsApp Adapter
    └──required by──> Email Adapter
    └──required by──> Back Office UI (pending gates view)

Schema Commons (pgvector)
    └──required by──> Hybrid Search
    └──required by──> Context Preparation Stage
    └──enhanced by──> Temporal Knowledge Graph

Proxy Layer
    └──required by──> Artifact Capture
    └──required by──> Work Session Lifecycle (pause/resume snapshots)

Self-Calibration Metrics
    └──requires──> Ledger (historical run data)
    └──requires──> Fan-out Evaluation (convergence/divergence data)
    └──requires──> Gate Surfacing (gate necessity data)
    └──feeds back into──> Dispatch Policy

RBAC / Decision Delegation
    └──required by──> Gate Surfacing (who resolves which gates)
    └──required by──> Back Office UI (cost visibility, cascade spawning)

Cost Dashboard
    └──requires──> Work Session Lifecycle (token counts per session)
    └──requires──> Fan-out Evaluation (n-model cost attribution)
```

### Dependency Notes

- **Cascade requires Ledger:** A cascade without an append-only ledger is just a workflow engine — the trace chain is what makes the coordination auditable.
- **Fan-out requires Executor:** Fan-out dispatches n parallel judgment passes; the executor must exist before fan-out can be wired.
- **Self-calibration requires multiple prior features:** This is a late-phase feature — it needs ledger history, fan-out data, and gate history to compute meaningful signals.
- **Adapters require Gate Surfacing:** The Slack/WhatsApp/email adapters are delivery mechanisms for gates; they cannot function without the gate dispatch mechanism.
- **Schema commons enhances but does not block most features:** Schema commons can be added incrementally; cascades and ledger are functional without it, just with less semantic grounding.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate that the coordination substrate works end-to-end.

- [ ] Append-only ledger with trace chain queries — core invariant, validates the fundamental value proposition
- [ ] Cascade as directed graph (branching, nesting, migration) — without this, there's no structural work
- [ ] Stage lifecycle (work session, judgment pass, fan-out) — the three compute types need to be dispatchable
- [ ] Stateless executor loop (poll ready stages, dispatch, surface gates) — execution backbone
- [ ] Gate surfacing via Slack adapter — 80% of users are in Slack; this is the primary interface
- [ ] Back office UI (active cascades, pending gates, ledger queries) — operators need visibility
- [ ] RBAC as decision delegation — gates are useless without routing to the right human
- [ ] `docker-compose up` bootstrap — operators must be able to run their own instance

### Add After Validation (v1.x)

Features to add once the coordination substrate is proven.

- [ ] WhatsApp and email adapters — extend the integration surface beyond Slack
- [ ] Schema commons with parsers (OpenAPI, Prisma, SQL DDL, GraphQL, protobuf) — unlocks semantic grounding for intents
- [ ] Temporal knowledge graph (bi-temporal facts, edge invalidation) — deeper memory for recurring work
- [ ] Cost dashboard per cascade/session — organizations need to understand AI spend
- [ ] Self-calibration metrics (all 8) — only meaningful once there's historical run data
- [ ] Model hot-swap between pause/resume — optimization feature, not core to correctness
- [ ] Software construction cascade template — the primary dogfood use case for Eclusa itself
- [ ] Haskell constraint workflow — high-value for structural correctness but narrow use case initially

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] GitHub/GitLab integration for PR linkage — expected by software teams but not core to coordination semantics
- [ ] Roadmap / timeline view — planning horizon visualization; useful but not blocking
- [ ] General reporting and dashboards beyond cost — manager analytics layer
- [ ] Webhook inbound triggers — allows external systems to originate intents programmatically
- [ ] Additional harness types beyond Pydantic AI and Claude Code backend — ecosystem expansion

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Append-only ledger | HIGH | MEDIUM | P1 |
| Cascade directed graph | HIGH | HIGH | P1 |
| Stateless executor loop | HIGH | MEDIUM | P1 |
| Gate surfacing (Slack adapter) | HIGH | MEDIUM | P1 |
| Back office UI (cascades, gates, ledger) | HIGH | MEDIUM | P1 |
| RBAC / decision delegation | HIGH | MEDIUM | P1 |
| `docker-compose up` bootstrap | HIGH | LOW | P1 |
| Work session lifecycle | HIGH | MEDIUM | P1 |
| Judgment pass dispatch | HIGH | LOW | P1 |
| Fan-out evaluation | HIGH | HIGH | P1 |
| Proxy layer + artifact capture | MEDIUM | MEDIUM | P2 |
| Schema commons (pgvector + parsers) | HIGH | HIGH | P2 |
| WhatsApp / email adapters | MEDIUM | MEDIUM | P2 |
| Cost dashboard | MEDIUM | LOW | P2 |
| Context preparation stage | MEDIUM | LOW | P2 |
| Temporal knowledge graph | MEDIUM | HIGH | P2 |
| Self-calibration metrics | HIGH | HIGH | P2 |
| Model hot-swap | MEDIUM | MEDIUM | P2 |
| Software construction cascade template | MEDIUM | MEDIUM | P2 |
| Haskell constraint verification | LOW | HIGH | P3 |
| Roadmap / timeline view | MEDIUM | MEDIUM | P3 |
| GitHub integration | MEDIUM | MEDIUM | P3 |
| Inbound webhook triggers | LOW | LOW | P3 |
| General analytics dashboards | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch — core coordination substrate
- P2: Should have, add when core is validated
- P3: Nice to have, expand after product-market fit

---

## Competitor Feature Analysis

| Feature | Jira | Linear | Notion | Eclusa Approach |
|---------|------|--------|--------|-----------------|
| Work item model | Issue with custom fields | Issue with opinionated states | Database row | Intent → cascade stage (typed, not free-form) |
| Dependency tracking | Issue links, dependency graph | Issue relations | Relation property | Cascade graph edges — dependency is structural |
| Audit trail | Issue history / changelog | Activity log | Page history | Append-only ledger — immutable, queryable at any timestamp |
| AI assistance | Atlassian Intelligence (summary, generation) | Linear AI (duplicate detection, priority suggestions) | Notion AI (agents, autofill, summaries) | Judgment passes (frontier model, no tools, prepared context) — opinionated separation of evaluation from execution |
| Escalation / gates | No structural escalation — manual @ mentions | No structural escalation | No structural escalation | Gate is a first-class entity — unresolvable ambiguity escalates by design |
| Multi-agent evaluation | Not present | Not present | Not present | Fan-out with convergence detection — model disagreement is the signal |
| Knowledge / schema | Confluence (separate product) | None built-in | Databases + wiki | Schema commons (pgvector, typed domain knowledge, hybrid search) |
| Integration surface | 3000+ integrations, Jira is the primary UI | Integrations, Linear is primary UI | Integrations, Notion is primary UI | Adapters (Slack, WhatsApp, email) are the primary UI — back office is for operators only |
| Cost visibility | No model cost tracking | No model cost tracking | No model cost tracking | Cost dashboard per cascade/session/model |
| Temporal queries | No AS OF queries | No AS OF queries | No AS OF queries | AS OF TIMESTAMP on append-only ledger |
| Formal verification | Not present | Not present | Not present | Haskell constraints verified by GHC |
| Deployment | Atlassian Cloud / Data Center | Cloud only | Cloud only | Single-tenant `docker-compose up` |

---

## Sources

- [Linear Features](https://linear.app/features) — confirmed feature set (MEDIUM confidence — website, not docs)
- [Jira Software Features](https://www.atlassian.com/software/jira/features) — Atlassian official (HIGH confidence)
- [Notion Product Overview](https://www.notion.com/product/ai) — Notion official (HIGH confidence)
- [AI PM Tool Rankings 2026 — AgileGenesis](https://www.agilegenesis.com/post/ai-project-management-tool-rankings-2026) — comparative evaluation (MEDIUM confidence)
- [Multi-Agent Orchestration Enterprise Strategy 2025-2026](https://www.onabout.ai/p/mastering-multi-agent-orchestration-architectures-patterns-roi-benchmarks-for-2025-2026) — patterns survey (MEDIUM confidence)
- [Zep Temporal Knowledge Graph Architecture (arXiv 2501.13956)](https://arxiv.org/abs/2501.13956) — bi-temporal modeling reference (HIGH confidence)
- [Galileo AI Agent Metrics](https://galileo.ai/blog/ai-agent-metrics) — agent evaluation metrics survey (MEDIUM confidence)
- [Langfuse Token and Cost Tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking) — LLM cost attribution patterns (HIGH confidence)
- [AI Audit Trails for Regulatory Scrutiny — CX Today](https://www.cxtoday.com/security-privacy-compliance/ai-audit-trail-regulatory-scrutiny/) — enterprise audit requirements (MEDIUM confidence)
- [Linear vs Jira 2026 — eesel AI](https://www.eesel.ai/blog/linear-vs-jira) — competitive comparison (MEDIUM confidence)
- [Notion AI Review 2025 — Skywork](https://skywork.ai/blog/notion-ai-review-2025-features-pricing-workflows/) — Notion AI capability survey (MEDIUM confidence)

---
*Feature research for: Eclusa — organizational coordination / AI orchestration platform*
*Researched: 2026-04-04*
