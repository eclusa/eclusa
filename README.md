```
   ███████╗ ██████╗██╗     ██╗   ██╗███████╗ █████╗
   ██╔════╝██╔════╝██║     ██║   ██║██╔════╝██╔══██╗
   █████╗  ██║     ██║     ██║   ██║███████╗███████║
   ██╔══╝  ██║     ██║     ██║   ██║╚════██║██╔══██║
   ███████╗╚██████╗███████╗╚██████╔╝███████║██║  ██║
   ╚══════╝ ╚═════╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
   ━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━
```

**From noisy intent to constrained, test-backed code.**

Eclusa is a pipeline that narrows ambiguity at every stage before an LLM writes a single line of implementation code. Domain schemas are matched from a curated knowledge base. Source composition is verified. Business rules are formalized as Haskell types and compiled by GHC. Tests are derived from the compiled constraints. Code is generated against tests it didn't write, constrained by types it didn't define, over domain knowledge it didn't invent.

What can't be resolved at any stage cascades upward until it reaches a human.

## How It Works

Eclusa has two systems that are now one flow: a **coordination layer** that breaks work into phases and plans, and a **narrowing pipeline** that type-checks the domain before planning begins. The pipeline runs inline — when you plan a phase, the pipeline runs first.

```
new-project → discuss-phase → [pipeline] → plan-phase → execute-phase → verify
                                  │
                    match → cohere → constrain → derive → generate
```

### The Coordination Layer

Multi-turn questioning extracts what you actually want to build. Research agents investigate the ecosystem. Phases are scoped, planned with atomic tasks, executed by parallel agents, and verified against the original goal.

Each phase goes through: **discuss** (surface decisions) → **plan** (atomic plans with acceptance criteria) → **execute** (parallel agents, wave-based) → **verify** (goal-backward checking). The orchestrator stays lean — subagents do the heavy work with fresh context windows.

### The Narrowing Pipeline

Six stages. Each narrows what the next stage can do. Each has a structural gate. No agent evaluates its own output. The pipeline runs automatically before planning when the schema commons is enabled (the default).

```
REFINE → MATCH → COHERENCE → FORMALIZE → DERIVE → GENERATE
```

| Stage | What happens | Gate |
|-------|-------------|------|
| **Refine** | Multi-turn questioning narrows a fuzzy idea into precise scope. Research agents investigate the ecosystem. | Human confirms scope |
| **Match** | Domain concepts extracted from phase context, matched against the Schema Commons — a Qdrant-backed index of typed domain knowledge. Unmatched concepts trigger web research and ingestion on demand. | Human confirms matches |
| **Coherence** | Matched sources checked for composition issues — type boundaries, auth model conflicts, data friction, missing relational links. | No blocking incompatibilities |
| **Formalize** | Haskell type modules auto-generated from matched sources. LLM drafts constraint functions from business rules. `ghc -fno-code` type-checks. The compiler doesn't hallucinate. | GHC accepts |
| **Derive** | Tests derived from source specs + compiled constraints. Template-driven where patterns are standard, LLM-generated for edge cases. | Tests internally consistent |
| **Generate** | Cheapest capable model generates code against tests it didn't write. | All tests pass |

Pipeline outputs (matched sources, compiled constraints, derived tests, generated stubs) feed directly into the planner. Plans reference derived tests as acceptance criteria and generated code as starting points.

## The Schema Commons

A Qdrant vector database of typed domain knowledge. Three layers:

**Interfaces** — Typed schemas from real industry standards. OpenAPI, Protobuf, GraphQL, SQL DDL, Prisma, TypeScript, JSON Schema, XSD. 45 curated sources across 25 industries: payments (Stripe, Moov), healthcare (HL7 FHIR, HAPI), music (DDEX, MusicBrainz), finance (ISO 20022, Open Banking UK), ecommerce (Medusa, Saleor), identity (Ory Kratos, Keycloak), cloud (Kubernetes, CloudEvents, Terraform), messaging (Twilio, Discord), observability (OpenTelemetry), and more.

**Behaviors** — Business rules extracted as structured English: *"For any Subscription s where days_past_due(s) >= 30: transition(s, canceled)."* Declarative statements about how the domain works, extracted from documentation and industry standards.

**Decisions** — Architectural knowledge: when to use what, and why. *"Given: stateless HTTP, <100 RPS, small team. Prefer: Fly.io over Kubernetes. Because: operational overhead exceeds value below this scale."*

The schema commons is enabled by default. On first project init, eclusa offers to seed it with the 45 curated industry sources. For brownfield projects, `map-codebase` auto-ingests existing typed schemas (Prisma, SQL DDL, OpenAPI) from your codebase into Qdrant.

When the pipeline hits a concept not in the commons, it tells the agent to research it via web search, ingest what it finds, and re-match.

## Why Haskell?

Stage 4 uses GHC as a gate. TypeScript's type system is intentionally unsound — `any`, type assertions, structural subtyping with escape hatches. When an LLM drafts a constraint, it can accidentally use an escape hatch, and `tsc --noEmit` will say "looks fine" when it isn't.

GHC's type system is sound. If it compiles, the types are correct. There's no `any`. If the LLM writes a constraint that references a field that doesn't exist on the matched source type, it won't compile. That's a real signal.

`ghc -fno-code`: one binary, one flag, no ecosystem. The constraint files never run. They're specifications that GHC verifies. Ships in the eclusa Docker Compose stack.

## Install

```bash
npx eclusa
```

Installs eclusa into your AI coding agent. Supports Claude Code, OpenCode, Gemini CLI, Codex, GitHub Copilot, Cursor, Windsurf, and Antigravity.

Run `/eclusa:new-project` to start.

For the full pipeline infrastructure (Qdrant + embeddings + GHC):

```bash
docker compose up -d                          # Qdrant + embedder
docker compose --profile constrain up -d      # + GHC 9.8 for type-checking
```

## Commands

68 commands across four areas. Run `/eclusa:help` for the full list.

### Pipeline
| Command | What it does |
|---------|-------------|
| `/eclusa:match` | Extract domain concepts, query Schema Commons, confirm matches |
| `/eclusa:cohere` | Check matched sources compose without conflicts |
| `/eclusa:constrain` | Scaffold Haskell types + constraints, iterate until GHC accepts |
| `/eclusa:derive` | Derive test suite from specs + constraints |
| `/eclusa:generate` | Generate code against derived tests |
| `/eclusa:pipeline` | Run all stages in sequence (also runs inline during plan-phase) |
| `/eclusa:ingest` | Manage Schema Commons: `url`, `file`, `scan`, `seed`, `status`, `prune` |

### Coordination
| Command | What it does |
|---------|-------------|
| `/eclusa:new-project` | Deep questioning, research, requirements, roadmap |
| `/eclusa:discuss-phase` | Surface assumptions and lock decisions before planning |
| `/eclusa:plan-phase` | Research, run pipeline, create atomic plans with verification |
| `/eclusa:execute-phase` | Wave-based parallel execution with atomic commits |
| `/eclusa:verify-work` | Conversational user acceptance testing |
| `/eclusa:autonomous` | Drive all remaining phases end-to-end |
| `/eclusa:progress` | Status, routing, pipeline state, next action |

### Operations
| Command | What it does |
|---------|-------------|
| `/eclusa:debug` | Systematic debugging with persistent state across sessions |
| `/eclusa:ship` | Create PR, run cross-AI review, prepare for merge |
| `/eclusa:map-codebase` | Parallel analysis of existing codebases (auto-ingests schemas) |
| `/eclusa:ui-phase` | Generate UI design contract for frontend phases |
| `/eclusa:review` | Cross-AI peer review from external AI CLIs |

### Governance
| Command | What it does |
|---------|-------------|
| `/eclusa:decide` | List and resolve pending human decisions |
| `/eclusa:provenance` | Verify hashes from intent to shipped code |
| `/eclusa:diagnose` | Full diagnostic: validation, provenance, enforcement |

## SDK

`@eclusa/sdk` provides a programmatic interface for running eclusa phases and workflows from application code, built on the Claude Agent SDK. Supports CLI and WebSocket transports.

```typescript
import { SessionRunner } from '@eclusa/sdk';

const session = new SessionRunner({ projectDir: '.' });
await session.runPhase(1);
```

## Architecture

- **68 command definitions** — User-facing skills (markdown)
- **48 workflows** — Orchestration logic (markdown)
- **18 specialized agents** — Researcher, planner, executor, verifier, debugger, UI auditor, etc.
- **65 CLI commands** — `eclusa-tools.cjs` backend dispatch
- **5 hooks** — Context monitor, workflow guard, prompt guard, version check, statusline
- **Zero runtime dependencies** — Node >= 20, that's it

## Provenance

Every commit carries content hashes as git trailers linking back to pipeline stage outputs: `Eclusa-Sources-Hash`, `Eclusa-Constraints-Hash`, `Eclusa-Test-Suite-Hash`. The chain is walkable. `/eclusa:provenance` verifies it.

## Acknowledgments

Eclusa is a hard fork of [GSD](https://github.com/gsd-build/get-shit-done) by TACHES. GSD's coordination infrastructure — agent delegation, phased delivery, context window management, questioning phase, researcher swarm — is the foundation on which eclusa's pipeline is built.

## License

MIT
