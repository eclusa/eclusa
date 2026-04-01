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

## The Problem

LLMs write code. Sometimes good code. Sometimes code that looks good until you realize the auth model doesn't match the API you're composing against, the business rule contradicts the data model, and the tests were written by the same model that wrote the implementation.

The issue isn't that LLMs can't code. It's that they skip the work that makes code *correct*: understanding the domain, checking that the pieces fit together, formalizing the business rules, and testing against constraints they didn't invent.

Eclusa makes that work structural. Not by asking the LLM to try harder, but by building a pipeline where each stage *narrows what the next stage can do*. The compiler catches type errors. The test suite was derived from formal constraints. The constraints were type-checked by GHC. The types were generated from matched domain schemas. The schemas came from a curated knowledge base. The knowledge base was populated from real industry standards.

At every stage: what can't be resolved cascades upward until it reaches a human. The system discovers where the novel edge is by hitting it, not by predicting it in advance.

## The Pipeline

Six stages. Each narrows ambiguity. Each has a structural gate. No agent evaluates its own output.

```
REFINE → MATCH → COHERENCE → FORMALIZE → DERIVE → GENERATE
```

| Stage | What happens | Gate |
|-------|-------------|------|
| **Refine** | Multi-turn questioning narrows a fuzzy idea into precise scope. Researcher sub-agents investigate the ecosystem. | Human confirms scope |
| **Match** | Domain concepts are extracted and matched against the Schema Commons — a Qdrant-backed index of typed domain knowledge from 45+ industry sources. Unmatched concepts trigger web research on demand. | Human confirms matches |
| **Coherence** | Matched sources are checked for composition issues — type boundaries, auth model conflicts, data model friction, missing links. | No blocking incompatibilities |
| **Formalize** | Haskell type modules are auto-generated from matched sources. The LLM drafts constraint functions from business rules. `ghc -fno-code` type-checks. The compiler doesn't hallucinate. | GHC accepts |
| **Derive** | Tests are derived from the source specs + compiled constraints. Template-driven where possible. The LLM fills edge cases, but doesn't decide what to test. | Tests internally consistent |
| **Generate** | The cheapest capable model generates code against tests it didn't write, constrained by types it didn't define, over domain knowledge it didn't invent. | All tests pass |

## The Schema Commons

A vector database of typed domain knowledge. Not just API schemas — three layers:

**Interfaces** — Typed schemas from real industry standards. OpenAPI, Protobuf, GraphQL, SQL DDL, Prisma, TypeScript, JSON Schema, XSD, Rust structs, Go interfaces. 45 curated sources across 25 industries: payments (Stripe), healthcare (HL7 FHIR), music (DDEX), cloud (Kubernetes, Terraform), observability (OpenTelemetry), and more.

**Behaviors** — Business rules extracted as structured English that reads like mathematical prose: *"For any Subscription s where days_past_due(s) >= 30: transition(s, canceled)."* Not Gherkin ceremony — declarative statements about how the domain works. Extracted from documentation, RFC-style specs, and industry standards.

**Decisions** — Architectural knowledge: when to use what, and why. *"Given: stateless HTTP, <100 RPS, small team. Prefer: Fly.io over Kubernetes. Because: operational overhead exceeds value below this scale. Unless: team already operates k8s."* 18 curated decisions across infrastructure, databases, data engineering, messaging, architecture patterns, toolchain, embedded, and observability.

When the pipeline hits a concept not in the commons, it doesn't guess — it tells the agent to research it (via web search), ingest what it finds, and re-match.

## Why Haskell?

Stage 4 uses GHC as a gate. The question is: can the gate be trusted?

TypeScript's type system is intentionally unsound — `any`, type assertions, structural subtyping with escape hatches. When an LLM drafts a constraint, it can accidentally use an escape hatch, and `tsc --noEmit` will say "looks fine" when it isn't.

GHC's type system is sound. If it compiles, the types are correct. There's no `any`. If the LLM writes a constraint that references a field that doesn't exist on the matched source type, it won't compile. That's a real signal — it means the business rule doesn't match the API surface.

`ghc -fno-code`: one binary, one flag, no ecosystem. The constraint files never run. They're specifications that GHC verifies.

GHC ships in the eclusa Docker Compose stack. No system install needed.

## Install

```bash
npx eclusa
```

This installs eclusa commands into your AI coding agent (Claude Code, Codex, Copilot, Cursor, Windsurf, and others). Run `/eclusa:new-project` to start.

For the full infrastructure (Qdrant + embeddings + GHC):

```bash
docker compose up -d
```

On first project init, eclusa offers to seed the Schema Commons with 45 curated industry sources from GitHub.

## Commands

### Pipeline
| Command | What it does |
|---------|-------------|
| `/eclusa:match` | Extract domain concepts, query Schema Commons, confirm matches. Research gaps on demand. |
| `/eclusa:cohere` | Check matched sources compose without conflicts. |
| `/eclusa:constrain` | Scaffold Haskell types + constraints. Iterate until GHC accepts. |
| `/eclusa:derive` | Derive test suite from specs + constraints. |
| `/eclusa:generate` | Code gen against test suite. All tests must pass. |
| `/eclusa:pipeline` | Run all stages in sequence with human checkpoints. |
| `/eclusa:ingest` | Manage the Schema Commons: `url`, `file`, `scan`, `seed`, `status`, `prune`. |

### Coordination
| Command | What it does |
|---------|-------------|
| `/eclusa:new-project` | Deep questioning phase — dream extraction, not requirements gathering. |
| `/eclusa:plan-phase` | Break work into atomic plans with research and verification. |
| `/eclusa:execute-phase` | Execute plans with parallel agents and atomic commits. |
| `/eclusa:discuss-phase` | Surface assumptions before planning. Interactive or auto mode. |
| `/eclusa:progress` | Check where you are. Route to the next action. |
| `/eclusa:autonomous` | Run all remaining phases: discuss, plan, execute. |
| `/eclusa:debug` | Systematic debugging with persistent state across sessions. |
| `/eclusa:ship` | Create PR, run review, prepare for merge. |

### Governance
| Command | What it does |
|---------|-------------|
| `/eclusa:decide` | List and resolve pending human decisions. |
| `/eclusa:provenance` | Verify the provenance chain — hashes from intent to code. |
| `/eclusa:diagnose` | Full diagnostic: validation, provenance, decisions, enforcement. |
| `/eclusa:config` | Edit vestibular (human orientation) or project file. |

Run `/eclusa:help` for the full command list.

## The Vestibular

A file at `~/.vestibular` that describes *you* — your role, how much autonomy to grant the system, your collaboration style, governance stances that apply to all your projects. It travels with you, not with the project. Projects inherit your stances but can tighten them.

## Provenance

Every commit in the pipeline carries content hashes as git trailers linking back to the pipeline stage outputs: `Eclusa-Sources-Hash`, `Eclusa-Constraints-Hash`, `Eclusa-Test-Suite-Hash`. The chain is walkable. `/eclusa:provenance` verifies it.

## Acknowledgments

Eclusa is a hard fork of [GSD](https://github.com/gsd-build/get-shit-done) by TACHES. GSD's coordination infrastructure — agent delegation, harness compatibility, phased delivery, context window management, questioning phase, researcher swarm, command materialization — is the foundation on which eclusa's pipeline is built.

## License

MIT
