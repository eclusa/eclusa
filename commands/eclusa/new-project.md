---
name: eclusa:new-project
description: Initialize a new project with deep context gathering and PROJECT.md
argument-hint: "[--auto]"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
**Flags:**
- `--auto` — Automatic mode. After config questions, runs research → requirements → roadmap without further interaction. Expects idea document via @ reference.
</context>

<objective>
Initialize a new project through unified flow: questioning → research (optional) → requirements → roadmap.

**Creates:**
- `.eclusa/PROJECT.md` — project context
- `.eclusa/config.json` — workflow preferences
- `.eclusa/research/` — domain research (optional)
- `.eclusa/REQUIREMENTS.md` — scoped requirements
- `.eclusa/ROADMAP.md` — phase structure
- `.eclusa/STATE.md` — project memory

**After this command:** Run `/eclusa:plan-phase 1` to start execution.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/new-project.md
@~/.claude/eclusa/references/questioning.md
@~/.claude/eclusa/references/ui-brand.md
@~/.claude/eclusa/templates/project.md
@~/.claude/eclusa/templates/requirements.md
</execution_context>

<process>
Execute the new-project workflow from @~/.claude/eclusa/workflows/new-project.md end-to-end.
Preserve all workflow gates (validation, approvals, commits, routing).
</process>
