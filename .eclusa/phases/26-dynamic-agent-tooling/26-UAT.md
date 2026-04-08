---
status: testing
phase: 26-dynamic-agent-tooling
source: [24-01-SUMMARY.md, 24-02-SUMMARY.md, 25-01-SUMMARY.md, 26-01-SUMMARY.md]
started: 2026-04-07T20:00:00Z
updated: 2026-04-07T20:00:00Z
---

## Current Test

number: 1
name: Cold Start Smoke Test
expected: |
  Kill and restart the full stack (docker compose down && docker compose up -d). Wait for services to be healthy. The API at http://localhost:8000/healthz returns 200. The executor starts without errors.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Kill and restart the full stack (docker compose down && docker compose up -d). Wait for services to be healthy. The API at http://localhost:8000/healthz returns 200. The executor starts without errors.
result: [pending]

### 2. Submit Blog Intent via API
expected: POST /api/scc/create with intent "I want a simple blog where I can write posts and people can read them" returns 200 with cascade_id and intent_id. 8 stages are created (refine, intent_validation_fanout, match, cohere, formalize, derive, generate, ship).
result: [pending]

### 3. Pipeline Completes End-to-End
expected: All 8 stages reach terminal state within 10 minutes. At least 5 stages resolve. No unexpected failures (formalize may fail due to GHC — that's acceptable).
result: [pending]

### 4. Derive Agent Writes Real Tests
expected: After derive resolves, the workspace directory (workspaces/{cascade_id}/) contains test files written by the agent. Files should be real pytest tests, not placeholder text.
result: [pending]

### 5. Generate Agent Builds Working Code
expected: After generate resolves, the workspace contains implementation code (e.g., app.py, requirements.txt). The code should be a real Flask/web application, not a code blob in a JSON field.
result: [pending]

### 6. Blog Deploys and Serves HTTP
expected: After ship resolves, a Docker container is running (eclusa-ship-*) mapping a host port to the app. Visiting http://localhost:{port} returns HTML — a blog page with a title and ability to create/view posts.
result: [pending]

### 7. Blog CRUD Works
expected: Create a new blog post via the UI or API. The post appears in the post list. View the post detail page. The content is displayed correctly.
result: [pending]

### 8. Artifact Trace Chain
expected: GET /api/trace/{artifact_id} returns a 5-hop chain: artifact -> session -> stage -> cascade -> intent. Each hop has the correct ID linking back to the original blog intent.
result: [pending]

### 9. Pipeline Visible in Cascades UI
expected: Navigate to http://localhost:8000/cascades. The blog cascade appears in the list. Clicking it shows all 8 stages with their status (resolved/failed/skipped).
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps

[none yet]
