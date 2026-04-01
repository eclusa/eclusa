# Eclusa Agent Reference

> All 18 specialized agents — roles, tools, spawn patterns, and relationships. For architecture context, see [Architecture](ARCHITECTURE.md).

---

## Overview

Eclusa uses a multi-agent architecture where thin orchestrators (workflow files) spawn specialized agents with fresh context windows. Each agent has a focused role, limited tool access, and produces specific artifacts.

### Agent Categories

| Category | Count | Agents |
|----------|-------|--------|
| Researchers | 3 | project-researcher, phase-researcher, ui-researcher |
| Analyzers | 2 | assumptions-analyzer, advisor-researcher |
| Synthesizers | 1 | research-synthesizer |
| Planners | 1 | planner |
| Roadmappers | 1 | roadmapper |
| Executors | 1 | executor |
| Checkers | 3 | plan-checker, integration-checker, ui-checker |
| Verifiers | 1 | verifier |
| Auditors | 2 | nyquist-auditor, ui-auditor |
| Mappers | 1 | codebase-mapper |
| Debuggers | 1 | debugger |

---

## Agent Details

### eclusa-project-researcher

**Role:** Researches domain ecosystem before roadmap creation.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:new-project`, `/eclusa:new-milestone` |
| **Parallelism** | 4 instances (stack, features, architecture, pitfalls) |
| **Tools** | Read, Write, Bash, Grep, Glob, WebSearch, WebFetch, mcp (context7) |
| **Model (balanced)** | Sonnet |
| **Produces** | `.eclusa/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` |

**Capabilities:**
- Web search for current ecosystem information
- Context7 MCP integration for library documentation
- Writes research documents directly to disk (reduces orchestrator context load)

---

### eclusa-phase-researcher

**Role:** Researches how to implement a specific phase before planning.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:plan-phase` |
| **Parallelism** | 4 instances (same focus areas as project researcher) |
| **Tools** | Read, Write, Bash, Grep, Glob, WebSearch, WebFetch, mcp (context7) |
| **Model (balanced)** | Sonnet |
| **Produces** | `{phase}-RESEARCH.md` |

**Capabilities:**
- Reads CONTEXT.md to focus research on user's decisions
- Investigates implementation patterns for the specific phase domain
- Detects test infrastructure for Nyquist validation mapping

---

### eclusa-ui-researcher

**Role:** Produces UI design contracts for frontend phases.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:ui-phase` |
| **Parallelism** | Single instance |
| **Tools** | Read, Write, Bash, Grep, Glob, WebSearch, WebFetch, mcp (context7) |
| **Model (balanced)** | Sonnet |
| **Color** | `#E879F9` (fuchsia) |
| **Produces** | `{phase}-UI-SPEC.md` |

**Capabilities:**
- Detects design system state (shadcn components.json, Tailwind config, existing tokens)
- Offers shadcn initialization for React/Next.js/Vite projects
- Asks only unanswered design contract questions
- Enforces registry safety gate for third-party components

---

### eclusa-assumptions-analyzer

**Role:** Deeply analyzes codebase for a phase and returns structured assumptions with evidence, confidence levels, and consequences if wrong.

| Property | Value |
|----------|-------|
| **Spawned by** | `discuss-phase-assumptions` workflow (when `workflow.discuss_mode = 'assumptions'`) |
| **Parallelism** | Single instance |
| **Tools** | Read, Bash, Grep, Glob |
| **Model (balanced)** | Sonnet |
| **Color** | Cyan |
| **Produces** | Structured assumptions with decision statements, evidence file paths, confidence levels |

**Key behaviors:**
- Reads ROADMAP.md phase description and prior CONTEXT.md files
- Searches codebase for files related to the phase (components, patterns, similar features)
- Reads 5-15 most relevant source files to form evidence-based assumptions
- Classifies confidence: Confident (clear from code), Likely (reasonable inference), Unclear (could go multiple ways)
- Flags topics that need external research (library compatibility, ecosystem best practices)
- Output calibrated by tier: full_maturity (3-5 areas), standard (3-4), minimal_decisive (2-3)

---

### eclusa-advisor-researcher

**Role:** Researches a single gray area decision during discuss-phase advisor mode and returns a structured comparison table.

| Property | Value |
|----------|-------|
| **Spawned by** | `discuss-phase` workflow (when ADVISOR_MODE = true) |
| **Parallelism** | Multiple instances (one per gray area) |
| **Tools** | Read, Bash, Grep, Glob, WebSearch, WebFetch, mcp (context7) |
| **Model (balanced)** | Sonnet |
| **Color** | Cyan |
| **Produces** | 5-column comparison table (Option / Pros / Cons / Complexity / Recommendation) with rationale paragraph |

**Key behaviors:**
- Researches a single assigned gray area using Claude's knowledge, Context7, and web search
- Produces genuinely viable options — no padding with filler alternatives
- Complexity column uses impact surface + risk (never time estimates)
- Recommendations are conditional ("Rec if X", "Rec if Y") — never single-winner ranking
- Output calibrated by tier: full_maturity (3-5 options with maturity signals), standard (2-4), minimal_decisive (2 options, decisive recommendation)

---

### eclusa-research-synthesizer

**Role:** Combines outputs from parallel researchers into a unified summary.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:new-project` (after 4 researchers complete) |
| **Parallelism** | Single instance (sequential after researchers) |
| **Tools** | Read, Write, Bash |
| **Model (balanced)** | Sonnet |
| **Color** | Purple |
| **Produces** | `.eclusa/research/SUMMARY.md` |

---

### eclusa-planner

**Role:** Creates executable phase plans with task breakdown, dependency analysis, and goal-backward verification.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:plan-phase`, `/eclusa:quick` |
| **Parallelism** | Single instance |
| **Tools** | Read, Write, Bash, Glob, Grep, WebFetch, mcp (context7) |
| **Model (balanced)** | Opus |
| **Color** | Green |
| **Produces** | `{phase}-{N}-PLAN.md` files |

**Key behaviors:**
- Reads PROJECT.md, REQUIREMENTS.md, CONTEXT.md, RESEARCH.md
- Creates 2-3 atomic task plans sized for single context windows
- Uses XML structure with `<task>` elements
- Includes `read_first` and `acceptance_criteria` sections
- Groups plans into dependency waves

---

### eclusa-roadmapper

**Role:** Creates project roadmaps with phase breakdown and requirement mapping.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:new-project` |
| **Parallelism** | Single instance |
| **Tools** | Read, Write, Bash, Glob, Grep |
| **Model (balanced)** | Sonnet |
| **Color** | Purple |
| **Produces** | `ROADMAP.md` |

**Key behaviors:**
- Maps requirements to phases (traceability)
- Derives success criteria from requirements
- Respects granularity setting for phase count
- Validates coverage (every v1 requirement mapped to a phase)

---

### eclusa-executor

**Role:** Executes Eclusa plans with atomic commits, deviation handling, and checkpoint protocols.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:execute-phase`, `/eclusa:quick` |
| **Parallelism** | Multiple (parallel within waves, sequential across waves) |
| **Tools** | Read, Write, Edit, Bash, Grep, Glob |
| **Model (balanced)** | Sonnet |
| **Color** | Yellow |
| **Produces** | Code changes, git commits, `{phase}-{N}-SUMMARY.md` |

**Key behaviors:**
- Fresh 200K context window per plan
- Follows XML task instructions precisely
- Atomic git commit per completed task
- Handles checkpoint types: auto, human-verify, decision, human-action
- Reports deviations from plan in SUMMARY.md
- Invokes node repair on verification failure

---

### eclusa-plan-checker

**Role:** Verifies plans will achieve phase goals before execution.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:plan-phase` (verification loop, max 3 iterations) |
| **Parallelism** | Single instance (iterative) |
| **Tools** | Read, Bash, Glob, Grep |
| **Model (balanced)** | Sonnet |
| **Color** | Green |
| **Produces** | PASS/FAIL verdict with specific feedback |

**8 Verification Dimensions:**
1. Requirement coverage
2. Task atomicity
3. Dependency ordering
4. File scope
5. Verification commands
6. Context fit
7. Gap detection
8. Nyquist compliance (when enabled)

---

### eclusa-integration-checker

**Role:** Verifies cross-phase integration and end-to-end flows.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:audit-milestone` |
| **Parallelism** | Single instance |
| **Tools** | Read, Bash, Grep, Glob |
| **Model (balanced)** | Sonnet |
| **Color** | Blue |
| **Produces** | Integration verification report |

---

### eclusa-ui-checker

**Role:** Validates UI-SPEC.md design contracts against quality dimensions.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:ui-phase` (validation loop, max 2 iterations) |
| **Parallelism** | Single instance |
| **Tools** | Read, Bash, Glob, Grep |
| **Model (balanced)** | Sonnet |
| **Color** | `#22D3EE` (cyan) |
| **Produces** | BLOCK/FLAG/PASS verdict |

---

### eclusa-verifier

**Role:** Verifies phase goal achievement through goal-backward analysis.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:execute-phase` (after all executors complete) |
| **Parallelism** | Single instance |
| **Tools** | Read, Write, Bash, Grep, Glob |
| **Model (balanced)** | Sonnet |
| **Color** | Green |
| **Produces** | `{phase}-VERIFICATION.md` |

**Key behaviors:**
- Checks codebase against phase goals, not just task completion
- PASS/FAIL with specific evidence
- Logs issues for `/eclusa:verify-work` to address

---

### eclusa-nyquist-auditor

**Role:** Fills Nyquist validation gaps by generating tests.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:validate-phase` |
| **Parallelism** | Single instance |
| **Tools** | Read, Write, Edit, Bash, Grep, Glob |
| **Model (balanced)** | Sonnet |
| **Produces** | Test files, updated `VALIDATION.md` |

**Key behaviors:**
- Never modifies implementation code — only test files
- Max 3 attempts per gap
- Flags implementation bugs as escalations for user

---

### eclusa-ui-auditor

**Role:** Retroactive 6-pillar visual audit of implemented frontend code.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:ui-review` |
| **Parallelism** | Single instance |
| **Tools** | Read, Write, Bash, Grep, Glob |
| **Model (balanced)** | Sonnet |
| **Color** | `#F472B6` (pink) |
| **Produces** | `{phase}-UI-REVIEW.md` with scores |

**6 Audit Pillars (scored 1-4):**
1. Copywriting
2. Visuals
3. Color
4. Typography
5. Spacing
6. Experience Design

---

### eclusa-codebase-mapper

**Role:** Explores codebase and writes structured analysis documents.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:map-codebase` |
| **Parallelism** | 4 instances (tech, architecture, quality, concerns) |
| **Tools** | Read, Bash, Grep, Glob, Write |
| **Model (balanced)** | Haiku |
| **Color** | Cyan |
| **Produces** | `.eclusa/codebase/*.md` (7 documents) |

**Key behaviors:**
- Read-only exploration + structured output
- Writes documents directly to disk
- No reasoning required — pattern extraction from file contents

---

### eclusa-debugger

**Role:** Investigates bugs using scientific method with persistent state.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:debug`, `/eclusa:verify-work` (for failures) |
| **Parallelism** | Single instance (interactive) |
| **Tools** | Read, Write, Edit, Bash, Grep, Glob, WebSearch |
| **Model (balanced)** | Sonnet |
| **Color** | Orange |
| **Produces** | `.eclusa/debug/*.md`, knowledge-base updates |

**Debug Session Lifecycle:**
`gathering` → `investigating` → `fixing` → `verifying` → `awaiting_human_verify` → `resolved`

**Key behaviors:**
- Tracks hypotheses, evidence, and eliminated theories
- State persists across context resets
- Requires human verification before marking resolved
- Appends to persistent knowledge base on resolution
- Consults knowledge base on new sessions

---

### eclusa-user-profiler

**Role:** Analyzes session messages across 8 behavioral dimensions to produce a scored developer profile.

| Property | Value |
|----------|-------|
| **Spawned by** | `/eclusa:profile-user` |
| **Parallelism** | Single instance |
| **Tools** | Read |
| **Model (balanced)** | Sonnet |
| **Color** | Magenta |
| **Produces** | `USER-PROFILE.md`, `/eclusa:dev-preferences`, `CLAUDE.md` profile section |

**Behavioral Dimensions:**
Communication style, decision patterns, debugging approach, UX preferences, vendor choices, frustration triggers, learning style, explanation depth.

**Key behaviors:**
- Read-only agent — analyzes extracted session data, does not modify files
- Produces scored dimensions with confidence levels and evidence citations
- Questionnaire fallback when session history is unavailable

---

## Agent Tool Permissions Summary

| Agent | Read | Write | Edit | Bash | Grep | Glob | WebSearch | WebFetch | MCP |
|-------|------|-------|------|------|------|------|-----------|----------|-----|
| project-researcher | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| phase-researcher | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ui-researcher | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| assumptions-analyzer | ✓ | | | ✓ | ✓ | ✓ | | | |
| advisor-researcher | ✓ | | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| research-synthesizer | ✓ | ✓ | | ✓ | | | | | |
| planner | ✓ | ✓ | | ✓ | ✓ | ✓ | | ✓ | ✓ |
| roadmapper | ✓ | ✓ | | ✓ | ✓ | ✓ | | | |
| executor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| plan-checker | ✓ | | | ✓ | ✓ | ✓ | | | |
| integration-checker | ✓ | | | ✓ | ✓ | ✓ | | | |
| ui-checker | ✓ | | | ✓ | ✓ | ✓ | | | |
| verifier | ✓ | ✓ | | ✓ | ✓ | ✓ | | | |
| nyquist-auditor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| ui-auditor | ✓ | ✓ | | ✓ | ✓ | ✓ | | | |
| codebase-mapper | ✓ | ✓ | | ✓ | ✓ | ✓ | | | |
| debugger | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| user-profiler | ✓ | | | | | | | | |

**Principle of Least Privilege:**
- Checkers are read-only (no Write/Edit) — they evaluate, never modify
- Researchers have web access — they need current ecosystem information
- Executors have Edit — they modify code but not web access
- Mappers have Write — they write analysis documents but not Edit (no code changes)
