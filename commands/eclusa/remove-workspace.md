---
name: eclusa:remove-workspace
description: Remove a Eclusa workspace and clean up worktrees
argument-hint: "<workspace-name>"
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---
<context>
**Arguments:**
- `<workspace-name>` (required) — Name of the workspace to remove
</context>

<objective>
Remove a workspace directory after confirmation. For worktree strategy, runs `git worktree remove` for each member repo first. Refuses if any repo has uncommitted changes.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/remove-workspace.md
@~/.claude/eclusa/references/ui-brand.md
</execution_context>

<process>
Execute the remove-workspace workflow from @~/.claude/eclusa/workflows/remove-workspace.md end-to-end.
</process>
