# Eclusa

An evergreen company operating system. Not an AI coding tool. Not a workflow engine. The nervous system of an organization — where intents enter as ambiguity and exit as traced artifacts.

Competitive frame: Jira, Linear, Notion — not LangGraph, CrewAI, or Cursor.

80% of users never open Eclusa directly. They interact through Slack, WhatsApp, email, Figma, webhooks. The integration layer is the product surface.

## What it does

Someone types _"I want a simple blog where I can write posts and people can read them"_ into Slack (or the API, or WhatsApp). Eclusa:

1. **Refines** the intent — an AI asks clarifying questions until scope is clear
2. **Validates** — multiple models independently check if the refined scope matches the original ask
3. **Matches** against existing knowledge — do we already have something related?
4. **Checks coherence** — does this contradict anything we know?
5. **Formalizes** constraints into verifiable specifications (Haskell types, checked by GHC — the compiler doesn't hallucinate)
6. **Derives** test cases — an agent with workspace tools writes real pytest files
7. **Generates** implementation — an agent writes code, runs tests, fixes errors, iterates
8. **Ships** — commits to git, builds a Docker image, deploys a running container

Every step is traced. Every decision is in the ledger. The artifact chain goes from the running container all the way back to the original Slack message.

## Design philosophy

- **Ambiguity up, decisions down.** What can't be resolved at a given level cascades upward until someone (human or smarter model) resolves it. Decisions flow back down as constraints.
- **No agent evaluates its own output.** Work sessions produce. Judgment passes evaluate. The evaluator physically cannot modify the work it's judging. This is topology, not policy.
- **The application is its data.** State lives in Postgres. The executor is a stateless loop. If it crashes, restart it — all state survives.
- **Code is the last output, not the objective.** The pipeline narrows ambiguity into verified constraints. Code generation is the mechanical final step.
- **Three compute types.** Work sessions (tools, cheapest model). Judgment passes (single API call, frontier model). Fan-out (N parallel passes, convergence = auto-resolve, divergence = human gate).

## Architecture

```
                    ┌─────────────┐
  Slack / WhatsApp  │             │  Back Office UI
  Email / Webhooks ─┤   Eclusa    ├─ (React SPA)
  CLI / API         │             │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────┴────┐  ┌───┴────┐  ┌───┴────┐
         │Executor │  │  API   │  │  Proxy  │
         │(loop)   │  │(FastAPI│  │(mitmprxy│
         └────┬────┘  └───┬────┘  └───┬────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────┴──────┐
                    │  PostgreSQL  │
                    │  + pgvector  │
                    │  + pg_search │
                    └─────────────┘
```

**9 domain entities:** Intent, Actor, Cascade, Stage, Work Session, Judgment Pass, Fan-out, Artifact, Ledger Entry.

**Single Postgres** for everything — relational data, vectors, full-text search, job queue (SKIP LOCKED), event dispatch (LISTEN/NOTIFY). No Redis, no Kafka, no external vector DB.

## Quick start

```bash
# Clone and configure
git clone <repo> && cd eclusa
cp .env.example .env
# Edit .env — set your OPENAI_API_KEY

# Start everything
docker compose up -d

# Services:
#   http://localhost:8000  — UI (back office)
#   http://localhost:8800  — API
#   localhost:5432         — PostgreSQL
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Executor | Python 3.12, asyncpg, SKIP LOCKED poll loop |
| Agent harness | pydantic-ai (workspace tools, multi-turn) |
| API | FastAPI, JWT auth, WebSocket |
| Database | PostgreSQL 17, pgvector, pg_search (ParadeDB) |
| Proxy | mitmproxy (captures all outbound LLM calls) |
| UI | React 19, Vite, shadcn/ui, TanStack Query |
| Formalize | GHC 9.10 sidecar (type-checks LLM-drafted Haskell) |
| Deploy | Docker Compose — single command bootstrap |

## Project structure

```
executor/       — Stateless dispatch loop, stage handlers, concurrency control
harness/        — Agent harnesses (native pydantic-ai, workspace tools, formalize)
adapters/       — Web API, Slack, WhatsApp, email adapters
judgment/       — Judgment pass execution, context preparation
fan_out/        — Parallel evaluation, convergence detection
knowledge/      — Temporal knowledge graph (entities, facts, episodes)
storage/        — Content-addressed object store (blake3)
proxy/          — mitmproxy addon for outbound call capture
ui/             — React SPA (back office)
.eclusa/        — Project governance (roadmap, phases, plans, state)
```

## The cascade

A cascade is a living directed graph of work, spawned from an intent. Not a workflow (implies start/finish). Not a pipeline (implies linear). Cascades branch, nest, and evolve.

The first cascade template is the **Software Construction Cascade (SCC)** — 8 stages from intent to deployment. But the platform is general. A cascade could be: onboarding a new hire, launching a marketing campaign, investigating a production incident. Same primitives, same trace, same governance.

## Status

**v2.2** — 26 phases complete. Full SCC pipeline running end-to-end with workspace-equipped agents. Dogfood proof: natural language intent produces a deployed web application.

Built by Nathan + Claude (orchestrator) + GPT-5.4-mini (planner) + GLM (agent worker). Eclusa was built using itself.
