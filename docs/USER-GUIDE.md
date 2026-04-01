# Eclusa User Guide

A detailed reference for workflows, troubleshooting, and configuration. For quick-start setup, see the [README](../README.md).

---

## Table of Contents

- [Workflow Diagrams](#workflow-diagrams)
- [UI Design Contract](#ui-design-contract)
- [Backlog & Threads](#backlog--threads)
- [Workstreams](#workstreams)
- [Security](#security)
- [Command Reference](#command-reference)
- [Configuration Reference](#configuration-reference)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [Recovery Quick Reference](#recovery-quick-reference)

---

## Workflow Diagrams

### Full Project Lifecycle

```
  ┌──────────────────────────────────────────────────┐
  │                   NEW PROJECT                    │
  │  /eclusa:new-project                                │
  │  Questions -> Research -> Requirements -> Roadmap│
  └─────────────────────────┬────────────────────────┘
                            │
             ┌──────────────▼─────────────┐
             │      FOR EACH PHASE:       │
             │                            │
             │  ┌────────────────────┐    │
             │  │ /eclusa:discuss-phase │    │  <- Lock in preferences
             │  └──────────┬─────────┘    │
             │             │              │
             │  ┌──────────▼─────────┐    │
             │  │ /eclusa:ui-phase      │    │  <- Design contract (frontend)
             │  └──────────┬─────────┘    │
             │             │              │
             │  ┌──────────▼─────────┐    │
             │  │ /eclusa:plan-phase    │    │  <- Research + Plan + Verify
             │  └──────────┬─────────┘    │
             │             │              │
             │  ┌──────────▼─────────┐    │
             │  │ /eclusa:execute-phase │    │  <- Parallel execution
             │  └──────────┬─────────┘    │
             │             │              │
             │  ┌──────────▼─────────┐    │
             │  │ /eclusa:verify-work   │    │  <- Manual UAT
             │  └──────────┬─────────┘    │
             │             │              │
             │  ┌──────────▼─────────┐    │
             │  │ /eclusa:ship          │    │  <- Create PR (optional)
             │  └──────────┬─────────┘    │
             │             │              │
             │     Next Phase?────────────┘
             │             │ No
             └─────────────┼──────────────┘
                            │
            ┌───────────────▼──────────────┐
            │  /eclusa:audit-milestone        │
            │  /eclusa:complete-milestone     │
            └───────────────┬──────────────┘
                            │
                   Another milestone?
                       │          │
                      Yes         No -> Done!
                       │
               ┌───────▼──────────────┐
               │  /eclusa:new-milestone  │
               └──────────────────────┘
```

### Planning Agent Coordination

```
  /eclusa:plan-phase N
         │
         ├── Phase Researcher (x4 parallel)
         │     ├── Stack researcher
         │     ├── Features researcher
         │     ├── Architecture researcher
         │     └── Pitfalls researcher
         │           │
         │     ┌──────▼──────┐
         │     │ RESEARCH.md │
         │     └──────┬──────┘
         │            │
         │     ┌──────▼──────┐
         │     │   Planner   │  <- Reads PROJECT.md, REQUIREMENTS.md,
         │     │             │     CONTEXT.md, RESEARCH.md
         │     └──────┬──────┘
         │            │
         │     ┌──────▼───────────┐     ┌────────┐
         │     │   Plan Checker   │────>│ PASS?  │
         │     └──────────────────┘     └───┬────┘
         │                                  │
         │                             Yes  │  No
         │                              │   │   │
         │                              │   └───┘  (loop, up to 3x)
         │                              │
         │                        ┌─────▼──────┐
         │                        │ PLAN files │
         │                        └────────────┘
         └── Done
```

### Validation Architecture (Nyquist Layer)

During plan-phase research, Eclusa now maps automated test coverage to each phase
requirement before any code is written. This ensures that when Claude's executor
commits a task, a feedback mechanism already exists to verify it within seconds.

The researcher detects your existing test infrastructure, maps each requirement to
a specific test command, and identifies any test scaffolding that must be created
before implementation begins (Wave 0 tasks).

The plan-checker enforces this as an 8th verification dimension: plans where tasks
lack automated verify commands will not be approved.

**Output:** `{phase}-VALIDATION.md` -- the feedback contract for the phase.

**Disable:** Set `workflow.nyquist_validation: false` in `/eclusa:settings` for
rapid prototyping phases where test infrastructure isn't the focus.

### Retroactive Validation (`/eclusa:validate-phase`)

For phases executed before Nyquist validation existed, or for existing codebases
with only traditional test suites, retroactively audit and fill coverage gaps:

```
  /eclusa:validate-phase N
         |
         +-- Detect state (VALIDATION.md exists? SUMMARY.md exists?)
         |
         +-- Discover: scan implementation, map requirements to tests
         |
         +-- Analyze gaps: which requirements lack automated verification?
         |
         +-- Present gap plan for approval
         |
         +-- Spawn auditor: generate tests, run, debug (max 3 attempts)
         |
         +-- Update VALIDATION.md
               |
               +-- COMPLIANT -> all requirements have automated checks
               +-- PARTIAL -> some gaps escalated to manual-only
```

The auditor never modifies implementation code — only test files and
VALIDATION.md. If a test reveals an implementation bug, it's flagged as an
escalation for you to address.

**When to use:** After executing phases that were planned before Nyquist was
enabled, or after `/eclusa:audit-milestone` surfaces Nyquist compliance gaps.

### Assumptions Discussion Mode

By default, `/eclusa:discuss-phase` asks open-ended questions about your implementation preferences. Assumptions mode inverts this: Eclusa reads your codebase first, surfaces structured assumptions about how it would build the phase, and asks only for corrections.

**Enable:** Set `workflow.discuss_mode` to `'assumptions'` via `/eclusa:settings`.

**How it works:**
1. Reads PROJECT.md, codebase mapping, and existing conventions
2. Generates a structured list of assumptions (tech choices, patterns, file locations)
3. Presents assumptions for you to confirm, correct, or expand
4. Writes CONTEXT.md from confirmed assumptions

**When to use:**
- Experienced developers who already know their codebase well
- Rapid iteration where open-ended questions slow you down
- Projects where patterns are well-established and predictable

See [docs/workflow-discuss-mode.md](workflow-discuss-mode.md) for the full discuss-mode reference.

---

## UI Design Contract

### Why

AI-generated frontends are visually inconsistent not because Claude Code is bad at UI but because no design contract existed before execution. Five components built without a shared spacing scale, color contract, or copywriting standard produce five slightly different visual decisions.

`/eclusa:ui-phase` locks the design contract before planning. `/eclusa:ui-review` audits the result after execution.

### Commands

| Command | Description |
|---------|-------------|
| `/eclusa:ui-phase [N]` | Generate UI-SPEC.md design contract for a frontend phase |
| `/eclusa:ui-review [N]` | Retroactive 6-pillar visual audit of implemented UI |

### Workflow: `/eclusa:ui-phase`

**When to run:** After `/eclusa:discuss-phase`, before `/eclusa:plan-phase` — for phases with frontend/UI work.

**Flow:**
1. Reads CONTEXT.md, RESEARCH.md, REQUIREMENTS.md for existing decisions
2. Detects design system state (shadcn components.json, Tailwind config, existing tokens)
3. shadcn initialization gate — offers to initialize if React/Next.js/Vite project has none
4. Asks only unanswered design contract questions (spacing, typography, color, copywriting, registry safety)
5. Writes `{phase}-UI-SPEC.md` to phase directory
6. Validates against 6 dimensions (Copywriting, Visuals, Color, Typography, Spacing, Registry Safety)
7. Revision loop if BLOCKED (max 2 iterations)

**Output:** `{padded_phase}-UI-SPEC.md` in `.eclusa/phases/{phase-dir}/`

### Workflow: `/eclusa:ui-review`

**When to run:** After `/eclusa:execute-phase` or `/eclusa:verify-work` — for any project with frontend code.

**Standalone:** Works on any project, not just Eclusa-managed ones. If no UI-SPEC.md exists, audits against abstract 6-pillar standards.

**6 Pillars (scored 1-4 each):**
1. Copywriting — CTA labels, empty states, error states
2. Visuals — focal points, visual hierarchy, icon accessibility
3. Color — accent usage discipline, 60/30/10 compliance
4. Typography — font size/weight constraint adherence
5. Spacing — grid alignment, token consistency
6. Experience Design — loading/error/empty state coverage

**Output:** `{padded_phase}-UI-REVIEW.md` in phase directory with scores and top 3 priority fixes.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `workflow.ui_phase` | `true` | Generate UI design contracts for frontend phases |
| `workflow.ui_safety_gate` | `true` | plan-phase prompts to run /eclusa:ui-phase for frontend phases |

Both follow the absent=enabled pattern. Disable via `/eclusa:settings`.

### shadcn Initialization

For React/Next.js/Vite projects, the UI researcher offers to initialize shadcn if no `components.json` is found. The flow:

1. Visit `ui.shadcn.com/create` and configure your preset
2. Copy the preset string
3. Run `npx shadcn init --preset {paste}`
4. Preset encodes the entire design system — colors, border radius, fonts

The preset string becomes a first-class Eclusa planning artifact, reproducible across phases and milestones.

### Registry Safety Gate

Third-party shadcn registries can inject arbitrary code. The safety gate requires:
- `npx shadcn view {component}` — inspect before installing
- `npx shadcn diff {component}` — compare against official

Controlled by `workflow.ui_safety_gate` config toggle.

### Screenshot Storage

`/eclusa:ui-review` captures screenshots via Playwright CLI to `.eclusa/ui-reviews/`. A `.gitignore` is created automatically to prevent binary files from reaching git. Screenshots are cleaned up during `/eclusa:complete-milestone`.

---

## Backlog & Threads

### Backlog Parking Lot

Ideas that aren't ready for active planning go into the backlog using 999.x numbering, keeping them outside the active phase sequence.

```
/eclusa:add-backlog "GraphQL API layer"     # Creates 999.1-graphql-api-layer/
/eclusa:add-backlog "Mobile responsive"     # Creates 999.2-mobile-responsive/
```

Backlog items get full phase directories, so you can use `/eclusa:discuss-phase 999.1` to explore an idea further or `/eclusa:plan-phase 999.1` when it's ready.

**Review and promote** with `/eclusa:review-backlog` — it shows all backlog items and lets you promote (move to active sequence), keep (leave in backlog), or remove (delete).

### Seeds

Seeds are forward-looking ideas with trigger conditions. Unlike backlog items, seeds surface automatically when the right milestone arrives.

```
/eclusa:plant-seed "Add real-time collab when WebSocket infra is in place"
```

Seeds preserve the full WHY and WHEN to surface. `/eclusa:new-milestone` scans all seeds and presents matches.

**Storage:** `.eclusa/seeds/SEED-NNN-slug.md`

### Persistent Context Threads

Threads are lightweight cross-session knowledge stores for work that spans multiple sessions but doesn't belong to any specific phase.

```
/eclusa:thread                              # List all threads
/eclusa:thread fix-deploy-key-auth          # Resume existing thread
/eclusa:thread "Investigate TCP timeout"    # Create new thread
```

Threads are lighter weight than `/eclusa:pause-work` — no phase state, no plan context. Each thread file includes Goal, Context, References, and Next Steps sections.

Threads can be promoted to phases (`/eclusa:add-phase`) or backlog items (`/eclusa:add-backlog`) when they mature.

**Storage:** `.eclusa/threads/{slug}.md`

---

## Workstreams

Workstreams let you work on multiple milestone areas concurrently without state collisions. Each workstream gets its own isolated `.eclusa/` state, so switching between them doesn't clobber progress.

**When to use:** You're working on milestone features that span different concern areas (e.g., backend API and frontend dashboard) and want to plan, execute, or discuss them independently without context bleed.

### Commands

| Command | Purpose |
|---------|---------|
| `/eclusa:workstreams create <name>` | Create a new workstream with isolated planning state |
| `/eclusa:workstreams switch <name>` | Switch active context to a different workstream |
| `/eclusa:workstreams list` | Show all workstreams and which is active |
| `/eclusa:workstreams complete <name>` | Mark a workstream as done and archive its state |

### How It Works

Each workstream maintains its own `.eclusa/` directory subtree. When you switch workstreams, Eclusa swaps the active planning context so that `/eclusa:progress`, `/eclusa:discuss-phase`, `/eclusa:plan-phase`, and other commands operate on that workstream's state.

This is lighter weight than `/eclusa:new-workspace` (which creates separate repo worktrees). Workstreams share the same codebase and git history but isolate planning artifacts.

---

## Security

### Defense-in-Depth (v1.27)

Eclusa generates markdown files that become LLM system prompts. This means any user-controlled text flowing into planning artifacts is a potential indirect prompt injection vector. v1.27 introduced centralized security hardening:

**Path Traversal Prevention:**
All user-supplied file paths (`--text-file`, `--prd`) are validated to resolve within the project directory. macOS `/var` → `/private/var` symlink resolution is handled.

**Prompt Injection Detection:**
The `security.cjs` module scans for known injection patterns (role overrides, instruction bypasses, system tag injections) in user-supplied text before it enters planning artifacts.

**Runtime Hooks:**
- `eclusa-prompt-guard.js` — Scans Write/Edit calls to `.eclusa/` for injection patterns (always active, advisory-only)
- `eclusa-workflow-guard.js` — Warns on file edits outside Eclusa workflow context (opt-in via `hooks.workflow_guard`)

**CI Scanner:**
`prompt-injection-scan.test.cjs` scans all agent, workflow, and command files for embedded injection vectors. Run as part of the test suite.

---

### Execution Wave Coordination

```
  /eclusa:execute-phase N
         │
         ├── Analyze plan dependencies
         │
         ├── Wave 1 (independent plans):
         │     ├── Executor A (fresh 200K context) -> commit
         │     └── Executor B (fresh 200K context) -> commit
         │
         ├── Wave 2 (depends on Wave 1):
         │     └── Executor C (fresh 200K context) -> commit
         │
         └── Verifier
               └── Check codebase against phase goals
                     │
                     ├── PASS -> VERIFICATION.md (success)
                     └── FAIL -> Issues logged for /eclusa:verify-work
```

### Brownfield Workflow (Existing Codebase)

```
  /eclusa:map-codebase
         │
         ├── Stack Mapper     -> codebase/STACK.md
         ├── Arch Mapper      -> codebase/ARCHITECTURE.md
         ├── Convention Mapper -> codebase/CONVENTIONS.md
         └── Concern Mapper   -> codebase/CONCERNS.md
                │
        ┌───────▼──────────┐
        │ /eclusa:new-project │  <- Questions focus on what you're ADDING
        └──────────────────┘
```

---

## Command Reference

### Core Workflow

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eclusa:new-project` | Full project init: questions, research, requirements, roadmap | Start of a new project |
| `/eclusa:new-project --auto @idea.md` | Automated init from document | Have a PRD or idea doc ready |
| `/eclusa:discuss-phase [N]` | Capture implementation decisions | Before planning, to shape how it gets built |
| `/eclusa:ui-phase [N]` | Generate UI design contract | After discuss-phase, before plan-phase (frontend phases) |
| `/eclusa:plan-phase [N]` | Research + plan + verify | Before executing a phase |
| `/eclusa:execute-phase <N>` | Execute all plans in parallel waves | After planning is complete |
| `/eclusa:verify-work [N]` | Manual UAT with auto-diagnosis | After execution completes |
| `/eclusa:ship [N]` | Create PR from verified work | After verification passes |
| `/eclusa:fast <text>` | Inline trivial tasks — skips planning entirely | Typo fixes, config changes, small refactors |
| `/eclusa:next` | Auto-detect state and run next step | Anytime — "what should I do next?" |
| `/eclusa:ui-review [N]` | Retroactive 6-pillar visual audit | After execution or verify-work (frontend projects) |
| `/eclusa:audit-milestone` | Verify milestone met its definition of done | Before completing milestone |
| `/eclusa:complete-milestone` | Archive milestone, tag release | All phases verified |
| `/eclusa:new-milestone [name]` | Start next version cycle | After completing a milestone |

### Navigation

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eclusa:progress` | Show status and next steps | Anytime -- "where am I?" |
| `/eclusa:resume-work` | Restore full context from last session | Starting a new session |
| `/eclusa:pause-work` | Save structured handoff (HANDOFF.json + continue-here.md) | Stopping mid-phase |
| `/eclusa:session-report` | Generate session summary with work and outcomes | End of session, stakeholder sharing |
| `/eclusa:help` | Show all commands | Quick reference |
| `/eclusa:update` | Update Eclusa with changelog preview | Check for new versions |
| `/eclusa:join-discord` | Open Discord community invite | Questions or community |

### Phase Management

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eclusa:add-phase` | Append new phase to roadmap | Scope grows after initial planning |
| `/eclusa:insert-phase [N]` | Insert urgent work (decimal numbering) | Urgent fix mid-milestone |
| `/eclusa:remove-phase [N]` | Remove future phase and renumber | Descoping a feature |
| `/eclusa:list-phase-assumptions [N]` | Preview Claude's intended approach | Before planning, to validate direction |
| `/eclusa:plan-milestone-gaps` | Create phases for audit gaps | After audit finds missing items |
| `/eclusa:research-phase [N]` | Deep ecosystem research only | Complex or unfamiliar domain |

### Brownfield & Utilities

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eclusa:map-codebase` | Analyze existing codebase | Before `/eclusa:new-project` on existing code |
| `/eclusa:quick` | Ad-hoc task with Eclusa guarantees | Bug fixes, small features, config changes |
| `/eclusa:debug [desc]` | Systematic debugging with persistent state | When something breaks |
| `/eclusa:forensics` | Diagnostic report for workflow failures | When state, artifacts, or git history seem corrupted |
| `/eclusa:add-todo [desc]` | Capture an idea for later | Think of something during a session |
| `/eclusa:check-todos` | List pending todos | Review captured ideas |
| `/eclusa:settings` | Configure workflow toggles and model profile | Change model, toggle agents |
| `/eclusa:set-profile <profile>` | Quick profile switch | Change cost/quality tradeoff |
| `/eclusa:reapply-patches` | Restore local modifications after update | After `/eclusa:update` if you had local edits |

### Code Quality & Review

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eclusa:review --phase N` | Cross-AI peer review from external CLIs | Before executing, to validate plans |
| `/eclusa:pr-branch` | Clean PR branch filtering `.eclusa/` commits | Before creating PR with planning-free diff |
| `/eclusa:audit-uat` | Audit verification debt across all phases | Before milestone completion |

### Backlog & Threads

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/eclusa:add-backlog <desc>` | Add idea to backlog parking lot (999.x) | Ideas not ready for active planning |
| `/eclusa:review-backlog` | Promote/keep/remove backlog items | Before new milestone, to prioritize |
| `/eclusa:plant-seed <idea>` | Forward-looking idea with trigger conditions | Ideas that should surface at a future milestone |
| `/eclusa:thread [name]` | Persistent context threads | Cross-session work outside the phase structure |

---

## Configuration Reference

Eclusa stores project settings in `.eclusa/config.json`. Configure during `/eclusa:new-project` or update later with `/eclusa:settings`.

### Full config.json Schema

```json
{
  "mode": "interactive",
  "granularity": "standard",
  "model_profile": "balanced",
  "planning": {
    "commit_docs": true,
    "search_gitignored": false
  },
  "workflow": {
    "research": true,
    "plan_check": true,
    "verifier": true,
    "nyquist_validation": true,
    "ui_phase": true,
    "ui_safety_gate": true,
    "research_before_questions": false,
    "discuss_mode": "standard",
    "skip_discuss": false
  },
  "resolve_model_ids": "anthropic",
  "hooks": {
    "context_warnings": true,
    "workflow_guard": false
  },
  "git": {
    "branching_strategy": "none",
    "phase_branch_template": "eclusa/phase-{phase}-{slug}",
    "milestone_branch_template": "eclusa/{milestone}-{slug}",
    "quick_branch_template": null
  }
}
```

### Core Settings

| Setting | Options | Default | What it Controls |
|---------|---------|---------|------------------|
| `mode` | `interactive`, `yolo` | `interactive` | `yolo` auto-approves decisions; `interactive` confirms at each step |
| `granularity` | `coarse`, `standard`, `fine` | `standard` | Phase granularity: how finely scope is sliced (3-5, 5-8, or 8-12 phases) |
| `model_profile` | `quality`, `balanced`, `budget`, `inherit` | `balanced` | Model tier for each agent (see table below) |

### Planning Settings

| Setting | Options | Default | What it Controls |
|---------|---------|---------|------------------|
| `planning.commit_docs` | `true`, `false` | `true` | Whether `.eclusa/` files are committed to git |
| `planning.search_gitignored` | `true`, `false` | `false` | Add `--no-ignore` to broad searches to include `.eclusa/` |

> **Note:** If `.eclusa/` is in `.gitignore`, `commit_docs` is automatically `false` regardless of the config value.

### Workflow Toggles

| Setting | Options | Default | What it Controls |
|---------|---------|---------|------------------|
| `workflow.research` | `true`, `false` | `true` | Domain investigation before planning |
| `workflow.plan_check` | `true`, `false` | `true` | Plan verification loop (up to 3 iterations) |
| `workflow.verifier` | `true`, `false` | `true` | Post-execution verification against phase goals |
| `workflow.nyquist_validation` | `true`, `false` | `true` | Validation architecture research during plan-phase; 8th plan-check dimension |
| `workflow.ui_phase` | `true`, `false` | `true` | Generate UI design contracts for frontend phases |
| `workflow.ui_safety_gate` | `true`, `false` | `true` | plan-phase prompts to run /eclusa:ui-phase for frontend phases |
| `workflow.research_before_questions` | `true`, `false` | `false` | Run research before discussion questions instead of after |
| `workflow.discuss_mode` | `standard`, `assumptions` | `standard` | Discussion style: open-ended questions vs. codebase-driven assumptions |
| `workflow.skip_discuss` | `true`, `false` | `false` | Skip discuss-phase entirely in autonomous mode; writes minimal CONTEXT.md from ROADMAP phase goal |

### Hook Settings

| Setting | Options | Default | What it Controls |
|---------|---------|---------|------------------|
| `hooks.context_warnings` | `true`, `false` | `true` | Context window usage warnings |
| `hooks.workflow_guard` | `true`, `false` | `false` | Warn on file edits outside Eclusa workflow context |

Disable workflow toggles to speed up phases in familiar domains or when conserving tokens.

### Git Branching

| Setting | Options | Default | What it Controls |
|---------|---------|---------|------------------|
| `git.branching_strategy` | `none`, `phase`, `milestone` | `none` | When and how branches are created |
| `git.phase_branch_template` | Template string | `eclusa/phase-{phase}-{slug}` | Branch name for phase strategy |
| `git.milestone_branch_template` | Template string | `eclusa/{milestone}-{slug}` | Branch name for milestone strategy |
| `git.quick_branch_template` | Template string or `null` | `null` | Optional branch name for `/eclusa:quick` tasks |

**Branching strategies explained:**

| Strategy | Creates Branch | Scope | Best For |
|----------|---------------|-------|----------|
| `none` | Never | N/A | Solo development, simple projects |
| `phase` | At each `execute-phase` | One phase per branch | Code review per phase, granular rollback |
| `milestone` | At first `execute-phase` | All phases share one branch | Release branches, PR per version |

**Template variables:** `{phase}` = zero-padded number (e.g., "03"), `{slug}` = lowercase hyphenated name, `{milestone}` = version (e.g., "v1.0"), `{num}` / `{quick}` = quick task ID (e.g., "260317-abc").

Example quick-task branching:

```json
"git": {
  "quick_branch_template": "eclusa/quick-{num}-{slug}"
}
```

### Model Profiles (Per-Agent Breakdown)

| Agent | `quality` | `balanced` | `budget` | `inherit` |
|-------|-----------|------------|----------|-----------|
| eclusa-planner | Opus | Opus | Sonnet | Inherit |
| eclusa-roadmapper | Opus | Sonnet | Sonnet | Inherit |
| eclusa-executor | Opus | Sonnet | Sonnet | Inherit |
| eclusa-phase-researcher | Opus | Sonnet | Haiku | Inherit |
| eclusa-project-researcher | Opus | Sonnet | Haiku | Inherit |
| eclusa-research-synthesizer | Sonnet | Sonnet | Haiku | Inherit |
| eclusa-debugger | Opus | Sonnet | Sonnet | Inherit |
| eclusa-codebase-mapper | Sonnet | Haiku | Haiku | Inherit |
| eclusa-verifier | Sonnet | Sonnet | Haiku | Inherit |
| eclusa-plan-checker | Sonnet | Sonnet | Haiku | Inherit |
| eclusa-integration-checker | Sonnet | Sonnet | Haiku | Inherit |

**Profile philosophy:**
- **quality** -- Opus for all decision-making agents, Sonnet for read-only verification. Use when quota is available and the work is critical.
- **balanced** -- Opus only for planning (where architecture decisions happen), Sonnet for everything else. The default for good reason.
- **budget** -- Sonnet for anything that writes code, Haiku for research and verification. Use for high-volume work or less critical phases.
- **inherit** -- All agents use the current session model. Best when switching models dynamically (e.g. OpenCode `/model`), or when using Claude Code with non-Anthropic providers (OpenRouter, local models) to avoid unexpected API costs. For non-Claude runtimes (Codex, OpenCode, Gemini CLI), the installer sets `resolve_model_ids: "omit"` automatically -- see [Non-Claude Runtimes](#using-non-claude-runtimes-codex-opencode-gemini-cli).

---

## Usage Examples

### New Project (Full Cycle)

```bash
claude --dangerously-skip-permissions
/eclusa:new-project            # Answer questions, configure, approve roadmap
/clear
/eclusa:discuss-phase 1        # Lock in your preferences
/eclusa:ui-phase 1             # Design contract (frontend phases)
/eclusa:plan-phase 1           # Research + plan + verify
/eclusa:execute-phase 1        # Parallel execution
/eclusa:verify-work 1          # Manual UAT
/eclusa:ship 1                 # Create PR from verified work
/eclusa:ui-review 1            # Visual audit (frontend phases)
/clear
/eclusa:next                   # Auto-detect and run next step
...
/eclusa:audit-milestone        # Check everything shipped
/eclusa:complete-milestone     # Archive, tag, done
/eclusa:session-report         # Generate session summary
```

### New Project from Existing Document

```bash
/eclusa:new-project --auto @prd.md   # Auto-runs research/requirements/roadmap from your doc
/clear
/eclusa:discuss-phase 1               # Normal flow from here
```

### Existing Codebase

```bash
/eclusa:map-codebase           # Analyze what exists (parallel agents)
/eclusa:new-project            # Questions focus on what you're ADDING
# (normal phase workflow from here)
```

### Quick Bug Fix

```bash
/eclusa:quick
> "Fix the login button not responding on mobile Safari"
```

### Resuming After a Break

```bash
/eclusa:progress               # See where you left off and what's next
# or
/eclusa:resume-work            # Full context restoration from last session
```

### Preparing for Release

```bash
/eclusa:audit-milestone        # Check requirements coverage, detect stubs
/eclusa:plan-milestone-gaps    # If audit found gaps, create phases to close them
/eclusa:complete-milestone     # Archive, tag, done
```

### Speed vs Quality Presets

| Scenario | Mode | Granularity | Profile | Research | Plan Check | Verifier |
|----------|------|-------|---------|----------|------------|----------|
| Prototyping | `yolo` | `coarse` | `budget` | off | off | off |
| Normal dev | `interactive` | `standard` | `balanced` | on | on | on |
| Production | `interactive` | `fine` | `quality` | on | on | on |

**Skipping discuss-phase in autonomous mode:** When running in `yolo` mode with well-established preferences already captured in PROJECT.md, set `workflow.skip_discuss: true` via `/eclusa:settings`. This bypasses the discuss-phase entirely and writes a minimal CONTEXT.md derived from the ROADMAP phase goal. Useful when your PROJECT.md and conventions are comprehensive enough that discussion adds no new information.

### Mid-Milestone Scope Changes

```bash
/eclusa:add-phase              # Append a new phase to the roadmap
# or
/eclusa:insert-phase 3         # Insert urgent work between phases 3 and 4
# or
/eclusa:remove-phase 7         # Descope phase 7 and renumber
```

### Multi-Project Workspaces

Work on multiple repos or features in parallel with isolated Eclusa state.

```bash
# Create a workspace with repos from your monorepo
/eclusa:new-workspace --name feature-b --repos hr-ui,ZeymoAPI

# Feature branch isolation — worktree of current repo with its own .eclusa/
/eclusa:new-workspace --name feature-b --repos .

# Then cd into the workspace and initialize Eclusa
cd ~/eclusa-workspaces/feature-b
/eclusa:new-project

# List and manage workspaces
/eclusa:list-workspaces
/eclusa:remove-workspace feature-b
```

Each workspace gets:
- Its own `.eclusa/` directory (fully independent from source repos)
- Git worktrees (default) or clones of specified repos
- A `WORKSPACE.md` manifest tracking member repos

---

## Troubleshooting

### "Project already initialized"

You ran `/eclusa:new-project` but `.eclusa/PROJECT.md` already exists. This is a safety check. If you want to start over, delete the `.eclusa/` directory first.

### Context Degradation During Long Sessions

Clear your context window between major commands: `/clear` in Claude Code. Eclusa is designed around fresh contexts -- every subagent gets a clean 200K window. If quality is dropping in the main session, clear and use `/eclusa:resume-work` or `/eclusa:progress` to restore state.

### Plans Seem Wrong or Misaligned

Run `/eclusa:discuss-phase [N]` before planning. Most plan quality issues come from Claude making assumptions that `CONTEXT.md` would have prevented. You can also run `/eclusa:list-phase-assumptions [N]` to see what Claude intends to do before committing to a plan.

### Execution Fails or Produces Stubs

Check that the plan was not too ambitious. Plans should have 2-3 tasks maximum. If tasks are too large, they exceed what a single context window can produce reliably. Re-plan with smaller scope.

### Lost Track of Where You Are

Run `/eclusa:progress`. It reads all state files and tells you exactly where you are and what to do next.

### Need to Change Something After Execution

Do not re-run `/eclusa:execute-phase`. Use `/eclusa:quick` for targeted fixes, or `/eclusa:verify-work` to systematically identify and fix issues through UAT.

### Model Costs Too High

Switch to budget profile: `/eclusa:set-profile budget`. Disable research and plan-check agents via `/eclusa:settings` if the domain is familiar to you (or to Claude).

### Using Non-Claude Runtimes (Codex, OpenCode, Gemini CLI)

If you installed Eclusa for a non-Claude runtime, the installer already configured model resolution so all agents use the runtime's default model. No manual setup is needed. Specifically, the installer sets `resolve_model_ids: "omit"` in your config, which tells Eclusa to skip Anthropic model ID resolution and let the runtime choose its own default model.

To assign different models to different agents on a non-Claude runtime, add `model_overrides` to `.eclusa/config.json` with fully-qualified model IDs that your runtime recognizes:

```json
{
  "resolve_model_ids": "omit",
  "model_overrides": {
    "eclusa-planner": "o3",
    "eclusa-executor": "o4-mini",
    "eclusa-debugger": "o3"
  }
}
```

The installer auto-configures `resolve_model_ids: "omit"` for Gemini CLI, OpenCode, and Codex. If you're manually setting up a non-Claude runtime, add it to `.eclusa/config.json` yourself.

See the [Configuration Reference](CONFIGURATION.md#non-claude-runtimes-codex-opencode-gemini-cli) for the full explanation.

### Using Claude Code with Non-Anthropic Providers (OpenRouter, Local)

If Eclusa subagents call Anthropic models and you're paying through OpenRouter or a local provider, switch to the `inherit` profile: `/eclusa:set-profile inherit`. This makes all agents use your current session model instead of specific Anthropic models. See also `/eclusa:settings` → Model Profile → Inherit.

### Working on a Sensitive/Private Project

Set `commit_docs: false` during `/eclusa:new-project` or via `/eclusa:settings`. Add `.eclusa/` to your `.gitignore`. Planning artifacts stay local and never touch git.

### Eclusa Update Overwrote My Local Changes

Since v1.17, the installer backs up locally modified files to `eclusa-local-patches/`. Run `/eclusa:reapply-patches` to merge your changes back.

### Workflow Diagnostics (`/eclusa:forensics`)

When a workflow fails in a way that isn't obvious -- plans reference nonexistent files, execution produces unexpected results, or state seems corrupted -- run `/eclusa:forensics` to generate a diagnostic report.

**What it checks:**
- Git history anomalies (orphaned commits, unexpected branch state, rebase artifacts)
- Artifact integrity (missing or malformed planning files, broken cross-references)
- State inconsistencies (ROADMAP status vs. actual file presence, config drift)

**Output:** A diagnostic report written to `.eclusa/forensics/` with findings and suggested remediation steps.

### Subagent Appears to Fail but Work Was Done

A known workaround exists for a Claude Code classification bug. Eclusa's orchestrators (execute-phase, quick) spot-check actual output before reporting failure. If you see a failure message but commits were made, check `git log` -- the work may have succeeded.

### Parallel Execution Causes Build Lock Errors

If you see pre-commit hook failures, cargo lock contention, or 30+ minute execution times during parallel wave execution, this is caused by multiple agents triggering build tools simultaneously. Eclusa handles this automatically since v1.26 — parallel agents use `--no-verify` on commits and the orchestrator runs hooks once after each wave. If you're on an older version, add this to your project's `CLAUDE.md`:

```markdown
## Git Commit Rules for Agents
All subagent/executor commits MUST use `--no-verify`.
```

To disable parallel execution entirely: `/eclusa:settings` → set `parallelization.enabled` to `false`.

### Windows: Installation Crashes on Protected Directories

If the installer crashes with `EPERM: operation not permitted, scandir` on Windows, this is caused by OS-protected directories (e.g., Chromium browser profiles). Fixed since v1.24 — update to the latest version. As a workaround, temporarily rename the problematic directory before running the installer.

---

## Recovery Quick Reference

| Problem | Solution |
|---------|----------|
| Lost context / new session | `/eclusa:resume-work` or `/eclusa:progress` |
| Phase went wrong | `git revert` the phase commits, then re-plan |
| Need to change scope | `/eclusa:add-phase`, `/eclusa:insert-phase`, or `/eclusa:remove-phase` |
| Milestone audit found gaps | `/eclusa:plan-milestone-gaps` |
| Something broke | `/eclusa:debug "description"` |
| Workflow state seems corrupted | `/eclusa:forensics` |
| Quick targeted fix | `/eclusa:quick` |
| Plan doesn't match your vision | `/eclusa:discuss-phase [N]` then re-plan |
| Costs running high | `/eclusa:set-profile budget` and `/eclusa:settings` to toggle agents off |
| Update broke local changes | `/eclusa:reapply-patches` |
| Want session summary for stakeholder | `/eclusa:session-report` |
| Don't know what step is next | `/eclusa:next` |
| Parallel execution build errors | Update Eclusa or set `parallelization.enabled: false` |

---

## Project File Structure

For reference, here is what Eclusa creates in your project:

```
.eclusa/
  PROJECT.md              # Project vision and context (always loaded)
  REQUIREMENTS.md         # Scoped v1/v2 requirements with IDs
  ROADMAP.md              # Phase breakdown with status tracking
  STATE.md                # Decisions, blockers, session memory
  config.json             # Workflow configuration
  MILESTONES.md           # Completed milestone archive
  HANDOFF.json            # Structured session handoff (from /eclusa:pause-work)
  research/               # Domain research from /eclusa:new-project
  reports/                # Session reports (from /eclusa:session-report)
  todos/
    pending/              # Captured ideas awaiting work
    done/                 # Completed todos
  debug/                  # Active debug sessions
    resolved/             # Archived debug sessions
  codebase/               # Brownfield codebase mapping (from /eclusa:map-codebase)
  phases/
    XX-phase-name/
      XX-YY-PLAN.md       # Atomic execution plans
      XX-YY-SUMMARY.md    # Execution outcomes and decisions
      CONTEXT.md          # Your implementation preferences
      RESEARCH.md         # Ecosystem research findings
      VERIFICATION.md     # Post-execution verification results
      XX-UI-SPEC.md       # UI design contract (from /eclusa:ui-phase)
      XX-UI-REVIEW.md     # Visual audit scores (from /eclusa:ui-review)
  ui-reviews/             # Screenshots from /eclusa:ui-review (gitignored)
```
