---
name: eclusa:list-workspaces
description: List active Eclusa workspaces and their status
allowed-tools:
  - Bash
  - Read
---
<objective>
Scan `~/eclusa-workspaces/` for workspace directories containing `WORKSPACE.md` manifests. Display a summary table with name, path, repo count, strategy, and Eclusa project status.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/list-workspaces.md
@~/.claude/eclusa/references/ui-brand.md
</execution_context>

<process>
Execute the list-workspaces workflow from @~/.claude/eclusa/workflows/list-workspaces.md end-to-end.
</process>
