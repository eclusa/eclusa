---
name: eclusa:new-milestone
description: Start a new milestone cycle — update PROJECT.md and route to requirements
argument-hint: "[milestone name, e.g., 'v1.1 Notifications']"
allowed-tools:
  - Read
  - Write
  - Bash
  - Task
  - AskUserQuestion
---
<objective>
Start a new milestone: questioning → research (optional) → requirements → roadmap.

Brownfield equivalent of new-project. Project exists, PROJECT.md has history. Gathers "what's next", updates PROJECT.md, then runs requirements → roadmap cycle.

**Creates/Updates:**
- `.eclusa/PROJECT.md` — updated with new milestone goals
- `.eclusa/research/` — domain research (optional, NEW features only)
- `.eclusa/REQUIREMENTS.md` — scoped requirements for this milestone
- `.eclusa/ROADMAP.md` — phase structure (continues numbering)
- `.eclusa/STATE.md` — reset for new milestone

**After:** `/eclusa:plan-phase [N]` to start execution.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/new-milestone.md
@~/.claude/eclusa/references/questioning.md
@~/.claude/eclusa/references/ui-brand.md
@~/.claude/eclusa/templates/project.md
@~/.claude/eclusa/templates/requirements.md
</execution_context>

<context>
Milestone name: $ARGUMENTS (optional - will prompt if not provided)

Project and milestone context files are resolved inside the workflow (`init new-milestone`) and delegated via `<files_to_read>` blocks where subagents are used.
</context>

<process>
Execute the new-milestone workflow from @~/.claude/eclusa/workflows/new-milestone.md end-to-end.
Preserve all workflow gates (validation, questioning, research, requirements, roadmap approval, commits).
</process>
