---
phase: 25-ship-stage
plan: 01
subsystem: executor
tags: [ship, object-store, git, docker, deployment, artifacts]
key_files:
  created:
    - executor/ship.py
    - tests/test_ship_handler.py
  modified:
    - executor/scc.py
    - executor/dispatch.py
    - executor/propagation.py
    - docker-compose.yml
    - Dockerfile
    - .dockerignore
    - adapters/web/api/cascades.py
requirements-completed: [SHIP-01, SHIP-02, SHIP-03, SHIP-04]
completed: 2026-04-07
---

# Phase 25 Plan 01: Ship Stage Summary

**Ship stage handler: parse generated code, store to object store, commit to git, build Docker image, run container, health-check, create deployment artifacts.**

## Accomplishments

- Created `executor/ship.py` (471 lines) — full Ship stage handler
  - `parse_generated_code()`: parses LLM output into `(filename, content)` pairs from fenced code blocks
  - `write_files_to_object_store()`: writes each file to LocalObjectStore (blake3 content-addressed), creates `file_created` artifacts
  - `init_and_commit_git()`: creates per-cascade git repo at `workspaces/{cascade_id}/`, commits all files, creates `git_commit` artifact
  - `build_and_run_container()`: auto-generates Dockerfile if missing, builds Docker image, runs container on dynamic port, health-checks, creates `deployment` artifact
  - `_read_workspace_files()`: reads real files from workspace directory (Phase 26 integration — primary path)
  - `dispatch_scc_ship()`: entry point — reads workspace, falls back to text blob parsing, orchestrates store→git→docker→resolve
- Created `tests/test_ship_handler.py` (10 unit tests) — parse fenced blocks, filename variations, language detection, dedup, port detection
- Added Ship as 8th stage in SCC cascade templates (`executor/scc.py`)
- Added ship dispatch routing (`executor/dispatch.py`)
- Added generate→ship propagation key map (`executor/propagation.py`) — workspace_dir + generated_code
- Added Docker socket mount + workspaces volume to `docker-compose.yml`
- Added git + Docker CLI static binary to executor `Dockerfile`
- Fixed `.dockerignore` — changed `storage/` to `storage/objects/` so Python module is included in Docker builds
- Added "Ship" to SCC display names in web API

## User-Facing Changes

- SCC pipeline now has 8 stages (was 7) — Ship is the final stage
- After Generate resolves, Ship automatically: stores files, commits to git, builds Docker image, runs container
- Deployed apps accessible at `http://localhost:{dynamic_port}` (port 9000+ range)
- Deployment artifact created with container name, image name, host port, health status
