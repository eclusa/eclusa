# Eclusa Command Reference

> Complete command syntax, flags, options, and examples. For feature details, see [Feature Reference](FEATURES.md). For workflow walkthroughs, see [User Guide](USER-GUIDE.md).

---

## Command Syntax

- **Claude Code / Gemini / Copilot:** `/eclusa:command-name [args]`
- **OpenCode:** `/eclusa-command-name [args]`
- **Codex:** `$eclusa-command-name [args]`

---

## Core Workflow Commands

### `/eclusa:new-project`

Initialize a new project with deep context gathering.

| Flag | Description |
|------|-------------|
| `--auto @file.md` | Auto-extract from document, skip interactive questions |

**Prerequisites:** No existing `.eclusa/PROJECT.md`
**Produces:** `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `config.json`, `research/`, `CLAUDE.md`

```bash
/eclusa:new-project                    # Interactive mode
/eclusa:new-project --auto @prd.md     # Auto-extract from PRD
```

---

### `/eclusa:new-workspace`

Create an isolated workspace with repo copies and independent `.eclusa/` directory.

| Flag | Description |
|------|-------------|
| `--name <name>` | Workspace name (required) |
| `--repos repo1,repo2` | Comma-separated repo paths or names |
| `--path /target` | Target directory (default: `~/eclusa-workspaces/<name>`) |
| `--strategy worktree\|clone` | Copy strategy (default: `worktree`) |
| `--branch <name>` | Branch to checkout (default: `workspace/<name>`) |
| `--auto` | Skip interactive questions |

**Use cases:**
- Multi-repo: work on a subset of repos with isolated Eclusa state
- Feature isolation: `--repos .` creates a worktree of the current repo

**Produces:** `WORKSPACE.md`, `.eclusa/`, repo copies (worktrees or clones)

```bash
/eclusa:new-workspace --name feature-b --repos hr-ui,ZeymoAPI
/eclusa:new-workspace --name feature-b --repos . --strategy worktree  # Same-repo isolation
/eclusa:new-workspace --name spike --repos api,web --strategy clone   # Full clones
```

---

### `/eclusa:list-workspaces`

List active Eclusa workspaces and their status.

**Scans:** `~/eclusa-workspaces/` for `WORKSPACE.md` manifests
**Shows:** Name, repo count, strategy, Eclusa project status

```bash
/eclusa:list-workspaces
```

---

### `/eclusa:remove-workspace`

Remove a workspace and clean up git worktrees.

| Argument | Required | Description |
|----------|----------|-------------|
| `<name>` | Yes | Workspace name to remove |

**Safety:** Refuses removal if any repo has uncommitted changes. Requires name confirmation.

```bash
/eclusa:remove-workspace feature-b
```

---

### `/eclusa:discuss-phase`

Capture implementation decisions before planning.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number (defaults to current phase) |

| Flag | Description |
|------|-------------|
| `--auto` | Auto-select recommended defaults for all questions |
| `--batch` | Group questions for batch intake instead of one-by-one |
| `--analyze` | Add trade-off analysis during discussion |

**Prerequisites:** `.eclusa/ROADMAP.md` exists
**Produces:** `{phase}-CONTEXT.md`, `{phase}-DISCUSSION-LOG.md` (audit trail)

```bash
/eclusa:discuss-phase 1                # Interactive discussion for phase 1
/eclusa:discuss-phase 3 --auto         # Auto-select defaults for phase 3
/eclusa:discuss-phase --batch          # Batch mode for current phase
/eclusa:discuss-phase 2 --analyze      # Discussion with trade-off analysis
```

---

### `/eclusa:ui-phase`

Generate UI design contract for frontend phases.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number (defaults to current phase) |

**Prerequisites:** `.eclusa/ROADMAP.md` exists, phase has frontend/UI work
**Produces:** `{phase}-UI-SPEC.md`

```bash
/eclusa:ui-phase 2                     # Design contract for phase 2
```

---

### `/eclusa:plan-phase`

Research, plan, and verify a phase.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number (defaults to next unplanned phase) |

| Flag | Description |
|------|-------------|
| `--auto` | Skip interactive confirmations |
| `--research` | Force re-research even if RESEARCH.md exists |
| `--skip-research` | Skip domain research step |
| `--gaps` | Gap closure mode (reads VERIFICATION.md, skips research) |
| `--skip-verify` | Skip plan checker verification loop |
| `--prd <file>` | Use a PRD file instead of discuss-phase for context |
| `--reviews` | Replan with cross-AI review feedback from REVIEWS.md |

**Prerequisites:** `.eclusa/ROADMAP.md` exists
**Produces:** `{phase}-RESEARCH.md`, `{phase}-{N}-PLAN.md`, `{phase}-VALIDATION.md`

```bash
/eclusa:plan-phase 1                   # Research + plan + verify phase 1
/eclusa:plan-phase 3 --skip-research   # Plan without research (familiar domain)
/eclusa:plan-phase --auto              # Non-interactive planning
```

---

### `/eclusa:execute-phase`

Execute all plans in a phase with wave-based parallelization, or run a specific wave.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | **Yes** | Phase number to execute |
| `--wave N` | No | Execute only Wave `N` in the phase |

**Prerequisites:** Phase has PLAN.md files
**Produces:** per-plan `{phase}-{N}-SUMMARY.md`, git commits, and `{phase}-VERIFICATION.md` when the phase is fully complete

```bash
/eclusa:execute-phase 1                # Execute phase 1
/eclusa:execute-phase 1 --wave 2       # Execute only Wave 2
```

---

### `/eclusa:verify-work`

User acceptance testing with auto-diagnosis.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number (defaults to last executed phase) |

**Prerequisites:** Phase has been executed
**Produces:** `{phase}-UAT.md`, fix plans if issues found

```bash
/eclusa:verify-work 1                  # UAT for phase 1
```

---

### `/eclusa:next`

Automatically advance to the next logical workflow step. Reads project state and runs the appropriate command.

**Prerequisites:** `.eclusa/` directory exists
**Behavior:**
- No project → suggests `/eclusa:new-project`
- Phase needs discussion → runs `/eclusa:discuss-phase`
- Phase needs planning → runs `/eclusa:plan-phase`
- Phase needs execution → runs `/eclusa:execute-phase`
- Phase needs verification → runs `/eclusa:verify-work`
- All phases complete → suggests `/eclusa:complete-milestone`

```bash
/eclusa:next                           # Auto-detect and run next step
```

---

### `/eclusa:session-report`

Generate a session report with work summary, outcomes, and estimated resource usage.

**Prerequisites:** Active project with recent work
**Produces:** `.eclusa/reports/SESSION_REPORT.md`

```bash
/eclusa:session-report                 # Generate post-session summary
```

**Report includes:**
- Work performed (commits, plans executed, phases progressed)
- Outcomes and deliverables
- Blockers and decisions made
- Estimated token/cost usage
- Next steps recommendation

---

### `/eclusa:ship`

Create PR from completed phase work with auto-generated body.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number or milestone version (e.g., `4` or `v1.0`) |
| `--draft` | No | Create as draft PR |

**Prerequisites:** Phase verified (`/eclusa:verify-work` passed), `gh` CLI installed and authenticated
**Produces:** GitHub PR with rich body from planning artifacts, STATE.md updated

```bash
/eclusa:ship 4                         # Ship phase 4
/eclusa:ship 4 --draft                 # Ship as draft PR
```

**PR body includes:**
- Phase goal from ROADMAP.md
- Changes summary from SUMMARY.md files
- Requirements addressed (REQ-IDs)
- Verification status
- Key decisions

---

### `/eclusa:ui-review`

Retroactive 6-pillar visual audit of implemented frontend.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number (defaults to last executed phase) |

**Prerequisites:** Project has frontend code (works standalone, no Eclusa project needed)
**Produces:** `{phase}-UI-REVIEW.md`, screenshots in `.eclusa/ui-reviews/`

```bash
/eclusa:ui-review                      # Audit current phase
/eclusa:ui-review 3                    # Audit phase 3
```

---

### `/eclusa:audit-uat`

Cross-phase audit of all outstanding UAT and verification items.

**Prerequisites:** At least one phase has been executed with UAT or verification
**Produces:** Categorized audit report with human test plan

```bash
/eclusa:audit-uat
```

---

### `/eclusa:audit-milestone`

Verify milestone met its definition of done.

**Prerequisites:** All phases executed
**Produces:** Audit report with gap analysis

```bash
/eclusa:audit-milestone
```

---

### `/eclusa:complete-milestone`

Archive milestone, tag release.

**Prerequisites:** Milestone audit complete (recommended)
**Produces:** `MILESTONES.md` entry, git tag

```bash
/eclusa:complete-milestone
```

---

### `/eclusa:milestone-summary`

Generate comprehensive project summary from milestone artifacts for team onboarding and review.

| Argument | Required | Description |
|----------|----------|-------------|
| `version` | No | Milestone version (defaults to current/latest milestone) |

**Prerequisites:** At least one completed or in-progress milestone
**Produces:** `.eclusa/reports/MILESTONE_SUMMARY-v{version}.md`

**Summary includes:**
- Overview, architecture decisions, phase-by-phase breakdown
- Key decisions and trade-offs
- Requirements coverage
- Tech debt and deferred items
- Getting started guide for new team members
- Interactive Q&A offered after generation

```bash
/eclusa:milestone-summary                # Summarize current milestone
/eclusa:milestone-summary v1.0           # Summarize specific milestone
```

---

### `/eclusa:new-milestone`

Start next version cycle.

| Argument | Required | Description |
|----------|----------|-------------|
| `name` | No | Milestone name |
| `--reset-phase-numbers` | No | Restart the new milestone at Phase 1 and archive old phase dirs before roadmapping |

**Prerequisites:** Previous milestone completed
**Produces:** Updated `PROJECT.md`, new `REQUIREMENTS.md`, new `ROADMAP.md`

```bash
/eclusa:new-milestone                  # Interactive
/eclusa:new-milestone "v2.0 Mobile"    # Named milestone
/eclusa:new-milestone --reset-phase-numbers "v2.0 Mobile"  # Restart milestone numbering at 1
```

---

## Phase Management Commands

### `/eclusa:add-phase`

Append new phase to roadmap.

```bash
/eclusa:add-phase                      # Interactive — describe the phase
```

### `/eclusa:insert-phase`

Insert urgent work between phases using decimal numbering.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Insert after this phase number |

```bash
/eclusa:insert-phase 3                 # Insert between phase 3 and 4 → creates 3.1
```

### `/eclusa:remove-phase`

Remove future phase and renumber subsequent phases.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number to remove |

```bash
/eclusa:remove-phase 7                 # Remove phase 7, renumber 8→7, 9→8, etc.
```

### `/eclusa:list-phase-assumptions`

Preview Claude's intended approach before planning.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number |

```bash
/eclusa:list-phase-assumptions 2       # See assumptions for phase 2
```

### `/eclusa:plan-milestone-gaps`

Create phases to close gaps from milestone audit.

```bash
/eclusa:plan-milestone-gaps             # Creates phases for each audit gap
```

### `/eclusa:research-phase`

Deep ecosystem research only (standalone — usually use `/eclusa:plan-phase` instead).

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number |

```bash
/eclusa:research-phase 4               # Research phase 4 domain
```

### `/eclusa:validate-phase`

Retroactively audit and fill Nyquist validation gaps.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number |

```bash
/eclusa:validate-phase 2               # Audit test coverage for phase 2
```

---

## Navigation Commands

### `/eclusa:progress`

Show status and next steps.

```bash
/eclusa:progress                       # "Where am I? What's next?"
```

### `/eclusa:resume-work`

Restore full context from last session.

```bash
/eclusa:resume-work                    # After context reset or new session
```

### `/eclusa:pause-work`

Save context handoff when stopping mid-phase.

```bash
/eclusa:pause-work                     # Creates continue-here.md
```

### `/eclusa:manager`

Interactive command center for managing multiple phases from one terminal.

**Prerequisites:** `.eclusa/ROADMAP.md` exists
**Behavior:**
- Dashboard of all phases with visual status indicators
- Recommends optimal next actions based on dependencies and progress
- Dispatches work: discuss runs inline, plan/execute run as background agents
- Designed for power users parallelizing work across phases from one terminal

```bash
/eclusa:manager                        # Open command center dashboard
```

---

### `/eclusa:help`

Show all commands and usage guide.

```bash
/eclusa:help                           # Quick reference
```

---

## Utility Commands

### `/eclusa:quick`

Execute ad-hoc task with Eclusa guarantees.

| Flag | Description |
|------|-------------|
| `--full` | Enable plan checking (2 iterations) + post-execution verification |
| `--discuss` | Lightweight pre-planning discussion |
| `--research` | Spawn focused researcher before planning |

Flags are composable.

```bash
/eclusa:quick                          # Basic quick task
/eclusa:quick --discuss --research     # Discussion + research + planning
/eclusa:quick --full                   # With plan checking and verification
/eclusa:quick --discuss --research --full  # All optional stages
```

### `/eclusa:autonomous`

Run all remaining phases autonomously.

| Flag | Description |
|------|-------------|
| `--from N` | Start from a specific phase number |

```bash
/eclusa:autonomous                     # Run all remaining phases
/eclusa:autonomous --from 3            # Start from phase 3
```

### `/eclusa:do`

Route freeform text to the right Eclusa command.

```bash
/eclusa:do                             # Then describe what you want
```

### `/eclusa:note`

Zero-friction idea capture — append, list, or promote notes to todos.

| Argument | Required | Description |
|----------|----------|-------------|
| `text` | No | Note text to capture (default: append mode) |
| `list` | No | List all notes from project and global scopes |
| `promote N` | No | Convert note N into a structured todo |

| Flag | Description |
|------|-------------|
| `--global` | Use global scope for note operations |

```bash
/eclusa:note "Consider caching strategy for API responses"
/eclusa:note list
/eclusa:note promote 3
```

### `/eclusa:debug`

Systematic debugging with persistent state.

| Argument | Required | Description |
|----------|----------|-------------|
| `description` | No | Description of the bug |

```bash
/eclusa:debug "Login button not responding on mobile Safari"
```

### `/eclusa:add-todo`

Capture idea or task for later.

| Argument | Required | Description |
|----------|----------|-------------|
| `description` | No | Todo description |

```bash
/eclusa:add-todo "Consider adding dark mode support"
```

### `/eclusa:check-todos`

List pending todos and select one to work on.

```bash
/eclusa:check-todos
```

### `/eclusa:add-tests`

Generate tests for a completed phase.

| Argument | Required | Description |
|----------|----------|-------------|
| `N` | No | Phase number |

```bash
/eclusa:add-tests 2                    # Generate tests for phase 2
```

### `/eclusa:stats`

Display project statistics.

```bash
/eclusa:stats                          # Project metrics dashboard
```

### `/eclusa:profile-user`

Generate a developer behavioral profile from Claude Code session analysis across 8 dimensions (communication style, decision patterns, debugging approach, UX preferences, vendor choices, frustration triggers, learning style, explanation depth). Produces artifacts that personalize Claude's responses.

| Flag | Description |
|------|-------------|
| `--questionnaire` | Use interactive questionnaire instead of session analysis |
| `--refresh` | Re-analyze sessions and regenerate profile |

**Generated artifacts:**
- `USER-PROFILE.md` — Full behavioral profile
- `/eclusa:dev-preferences` command — Load preferences in any session
- `CLAUDE.md` profile section — Auto-discovered by Claude Code

```bash
/eclusa:profile-user                   # Analyze sessions and build profile
/eclusa:profile-user --questionnaire   # Interactive questionnaire fallback
/eclusa:profile-user --refresh         # Re-generate from fresh analysis
```

### `/eclusa:health`

Validate `.eclusa/` directory integrity.

| Flag | Description |
|------|-------------|
| `--repair` | Auto-fix recoverable issues |

```bash
/eclusa:health                         # Check integrity
/eclusa:health --repair                # Check and fix
```

### `/eclusa:cleanup`

Archive accumulated phase directories from completed milestones.

```bash
/eclusa:cleanup
```

---

## Diagnostics Commands

### `/eclusa:forensics`

Post-mortem investigation of failed or stuck Eclusa workflows.

| Argument | Required | Description |
|----------|----------|-------------|
| `description` | No | Problem description (prompted if omitted) |

**Prerequisites:** `.eclusa/` directory exists
**Produces:** `.eclusa/forensics/report-{timestamp}.md`

**Investigation covers:**
- Git history analysis (recent commits, stuck patterns, time gaps)
- Artifact integrity (expected files for completed phases)
- STATE.md anomalies and session history
- Uncommitted work, conflicts, abandoned changes
- At least 4 anomaly types checked (stuck loop, missing artifacts, abandoned work, crash/interruption)
- GitHub issue creation offered if actionable findings exist

```bash
/eclusa:forensics                              # Interactive — prompted for problem
/eclusa:forensics "Phase 3 execution stalled"  # With problem description
```

---

## Workstream Management

### `/eclusa:workstreams`

Manage parallel workstreams for concurrent work on different milestone areas.

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `list` | List all workstreams with status (default if no subcommand) |
| `create <name>` | Create a new workstream |
| `status <name>` | Detailed status for one workstream |
| `switch <name>` | Set active workstream |
| `progress` | Progress summary across all workstreams |
| `complete <name>` | Archive a completed workstream |
| `resume <name>` | Resume work in a workstream |

**Prerequisites:** Active Eclusa project
**Produces:** Workstream directories under `.eclusa/`, state tracking per workstream

```bash
/eclusa:workstreams                    # List all workstreams
/eclusa:workstreams create backend-api # Create new workstream
/eclusa:workstreams switch backend-api # Set active workstream
/eclusa:workstreams status backend-api # Detailed status
/eclusa:workstreams progress           # Cross-workstream progress overview
/eclusa:workstreams complete backend-api  # Archive completed workstream
/eclusa:workstreams resume backend-api    # Resume work in workstream
```

---

## Configuration Commands

### `/eclusa:settings`

Interactive configuration of workflow toggles and model profile.

```bash
/eclusa:settings                       # Interactive config
```

### `/eclusa:set-profile`

Quick profile switch.

| Argument | Required | Description |
|----------|----------|-------------|
| `profile` | **Yes** | `quality`, `balanced`, `budget`, or `inherit` |

```bash
/eclusa:set-profile budget             # Switch to budget profile
/eclusa:set-profile quality            # Switch to quality profile
```

---

## Brownfield Commands

### `/eclusa:map-codebase`

Analyze existing codebase with parallel mapper agents.

| Argument | Required | Description |
|----------|----------|-------------|
| `area` | No | Scope mapping to a specific area |

```bash
/eclusa:map-codebase                   # Full codebase analysis
/eclusa:map-codebase auth              # Focus on auth area
```

---

## Update Commands

### `/eclusa:update`

Update Eclusa with changelog preview.

```bash
/eclusa:update                         # Check for updates and install
```

### `/eclusa:reapply-patches`

Restore local modifications after a Eclusa update.

```bash
/eclusa:reapply-patches                # Merge back local changes
```

---

## Fast & Inline Commands

### `/eclusa:fast`

Execute a trivial task inline — no subagents, no planning overhead. For typo fixes, config changes, small refactors, forgotten commits.

| Argument | Required | Description |
|----------|----------|-------------|
| `task description` | No | What to do (prompted if omitted) |

**Not a replacement for `/eclusa:quick`** — use `/eclusa:quick` for anything needing research, multi-step planning, or verification.

```bash
/eclusa:fast "fix typo in README"
/eclusa:fast "add .env to gitignore"
```

---

## Code Quality Commands

### `/eclusa:review`

Cross-AI peer review of phase plans from external AI CLIs.

| Argument | Required | Description |
|----------|----------|-------------|
| `--phase N` | **Yes** | Phase number to review |

| Flag | Description |
|------|-------------|
| `--gemini` | Include Gemini CLI review |
| `--claude` | Include Claude CLI review (separate session) |
| `--codex` | Include Codex CLI review |
| `--all` | Include all available CLIs |

**Produces:** `{phase}-REVIEWS.md` — consumable by `/eclusa:plan-phase --reviews`

```bash
/eclusa:review --phase 3 --all
/eclusa:review --phase 2 --gemini
```

---

### `/eclusa:pr-branch`

Create a clean PR branch by filtering out `.eclusa/` commits.

| Argument | Required | Description |
|----------|----------|-------------|
| `target branch` | No | Base branch (default: `main`) |

**Purpose:** Reviewers see only code changes, not Eclusa planning artifacts.

```bash
/eclusa:pr-branch                     # Filter against main
/eclusa:pr-branch develop             # Filter against develop
```

---

### `/eclusa:audit-uat`

Cross-phase audit of all outstanding UAT and verification items.

**Prerequisites:** At least one phase has been executed with UAT or verification
**Produces:** Categorized audit report with human test plan

```bash
/eclusa:audit-uat
```

---

## Backlog & Thread Commands

### `/eclusa:add-backlog`

Add an idea to the backlog parking lot using 999.x numbering.

| Argument | Required | Description |
|----------|----------|-------------|
| `description` | **Yes** | Backlog item description |

**999.x numbering** keeps backlog items outside the active phase sequence. Phase directories are created immediately so `/eclusa:discuss-phase` and `/eclusa:plan-phase` work on them.

```bash
/eclusa:add-backlog "GraphQL API layer"
/eclusa:add-backlog "Mobile responsive redesign"
```

---

### `/eclusa:review-backlog`

Review and promote backlog items to active milestone.

**Actions per item:** Promote (move to active sequence), Keep (leave in backlog), Remove (delete).

```bash
/eclusa:review-backlog
```

---

### `/eclusa:plant-seed`

Capture a forward-looking idea with trigger conditions — surfaces automatically at the right milestone.

| Argument | Required | Description |
|----------|----------|-------------|
| `idea summary` | No | Seed description (prompted if omitted) |

Seeds solve context rot: instead of a one-liner in Deferred that nobody reads, a seed preserves the full WHY, WHEN to surface, and breadcrumbs to details.

**Produces:** `.eclusa/seeds/SEED-NNN-slug.md`
**Consumed by:** `/eclusa:new-milestone` (scans seeds and presents matches)

```bash
/eclusa:plant-seed "Add real-time collaboration when WebSocket infra is in place"
```

---

### `/eclusa:thread`

Manage persistent context threads for cross-session work.

| Argument | Required | Description |
|----------|----------|-------------|
| (none) | — | List all threads |
| `name` | — | Resume existing thread by name |
| `description` | — | Create new thread |

Threads are lightweight cross-session knowledge stores for work that spans multiple sessions but doesn't belong to any specific phase. Lighter weight than `/eclusa:pause-work`.

```bash
/eclusa:thread                         # List all threads
/eclusa:thread fix-deploy-key-auth     # Resume thread
/eclusa:thread "Investigate TCP timeout in pasta service"  # Create new
```

---

## Community Commands

### `/eclusa:join-discord`

Open Discord community invite.

```bash
/eclusa:join-discord
```
