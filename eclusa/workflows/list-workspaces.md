<purpose>
List all Eclusa workspaces found in ~/eclusa-workspaces/ with their status.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

## 1. Setup

```bash
INIT=$(node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" init list-workspaces)
if [[ "$INIT" == @file:* ]]; then INIT=$(cat "${INIT#@file:}"); fi
```

Parse JSON for: `workspace_base`, `workspaces`, `workspace_count`.

## 2. Display

**If `workspace_count` is 0:**

```
No workspaces found in ~/eclusa-workspaces/

Create one with:
  /eclusa:new-workspace --name my-workspace --repos repo1,repo2
```

Done.

**If workspaces exist:**

Display a table:

```
Eclusa Workspaces (~/eclusa-workspaces/)

| Name | Repos | Strategy | Eclusa Project |
|------|-------|----------|-------------|
| feature-a | 3 | worktree | Yes |
| feature-b | 2 | clone | No |

Manage:
  cd ~/eclusa-workspaces/<name>     # Enter a workspace
  /eclusa:remove-workspace <name>   # Remove a workspace
```

For each workspace, show:
- **Name** — directory name
- **Repos** — count from init data
- **Strategy** — from WORKSPACE.md
- **Eclusa Project** — whether `.eclusa/PROJECT.md` exists (Yes/No)

</process>
