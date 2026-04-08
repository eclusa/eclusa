---
phase: 26-dynamic-agent-tooling
plan: 01
subsystem: harness, executor
tags: [workspace-tools, pydantic-ai, agents, derive, generate, multi-turn]
key_files:
  created:
    - harness/workspace_tools.py
  modified:
    - executor/scc_handlers.py
    - executor/propagation.py
    - tests/e2e/test_24_dogfood_scc_journey.py
requirements-completed: [AGENT-01, AGENT-02, AGENT-03, AGENT-04]
completed: 2026-04-07
---

# Phase 26 Plan 01: Dynamic Agent Tooling Summary

**Replaced blind single-turn LLM calls in Derive/Generate stages with pydantic-ai agents that have real workspace tools (write_file, read_file, run_command, list_files). Agents iterate autonomously — write code, run tests, fix errors, repeat.**

## Accomplishments

- Created `harness/workspace_tools.py` (203 lines) — workspace tool definitions for pydantic-ai agents
  - `WorkspaceContext` dataclass: workspace_dir, cascade_id, stage_name, upstream_context
  - `_safe_path()`: security guard — rejects paths that escape workspace via `../` or absolute paths
  - `_register_workspace_tools()`: registers 4 tools on any agent:
    - `write_file(path, content)` — create/overwrite files in workspace
    - `read_file(path)` — read files from workspace
    - `run_command(command)` — execute shell commands in workspace dir (60s timeout, venv-aware)
    - `list_files(path)` — tree-like directory listing (max depth 3)
  - `build_derive_agent(model)` — test specification agent with system prompt for BDD/E2E test generation
  - `build_generate_agent(model)` — code generation agent with system prompt including deployment context ("bind to 0.0.0.0")
- Rewrote `handle_derive` in `executor/scc_handlers.py`:
  - Creates workspace at `workspaces/{cascade_id}/`
  - Builds derive agent with workspace tools via `build_derive_agent(model)`
  - Calls `agent.run()` for multi-turn tool iteration (agent writes tests, validates, fixes)
  - Persists cost + message history to work_session
  - Resolves with workspace_dir in output
- Rewrote `handle_generate` in `executor/scc_handlers.py`:
  - Same workspace pattern — agent sees existing test files from derive
  - Agent writes implementation code, installs deps, runs tests, iterates until passing
  - Deployment context in system prompt ensures correct binding for Docker
- Updated `executor/ship.py` — primary path reads files from workspace (`_read_workspace_files()`), fallback parses text blob
- Updated `executor/propagation.py` — workspace_dir propagated from generate to ship via key map
- Updated E2E tests — 8 stages (added ship), timeout 300→600s, asyncio.timeout 350→700s
- Fixed path resolution bug in `_walk_tree` — `relative_to()` mismatch between resolved/unresolved paths

## User-Facing Changes

- Derive and Generate stages now produce real files in a workspace directory, not text blobs
- Agents iterate with tools — write code, run commands, see errors, fix issues, repeat
- The full pipeline is autonomous: intent → scope → validate → match → cohere → formalize → derive tests → generate code → deploy
- Dogfood proof: "I want a simple blog" → GLM agent writes Flask app with CRUD, templates, validation → Ship deploys at http://localhost:9000
- Pipeline takes ~7-12 minutes (agent multi-turn iteration with rate-limited GLM model)
