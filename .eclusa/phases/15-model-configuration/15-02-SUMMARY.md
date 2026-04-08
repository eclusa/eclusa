---
phase: 15-model-configuration
plan: 02
subsystem: api, ui
tags: [model-config, cascade, migration, chat-ui, pydantic]
requirements-completed: [MODEL-03]
duration: 10min
completed: 2026-04-06
---

# Phase 15 Plan 02: Model Config Plumbing Summary

**Migration + API wiring + UI panel for operator model selection on SCC cascades**

## Accomplishments

### Task 1: Migration 0004
- Added nullable JSONB `model_config` column to cascade table
- Alembic revision chain: 0001 → 0002 → 0003 → 0004

### Task 2: API Wiring
- `ChatRequest` accepts `model_config` via Pydantic alias (avoids v2 reserved name collision)
- `create_chat_cascade` persists `model_config` to cascade record when provided
- `useChat` hook forwards `modelConfig` in POST /chat body
- `SccModelConfig` and `SccStage` types exported from chat.ts

### Task 3: UI Panel
- Collapsible "Advanced SCC model config" panel in ChatPage
- Default SCC model selector + 7 per-stage override selectors
- Empty selectors = "inherit" (not included in payload)
- Panel hidden by default, toggled via text button

## Key Files
- `alembic/versions/0004_cascade_model_config.py` — migration
- `adapters/web/api/chat.py` — ChatRequest with model_config field
- `adapters/web/chat_bridge.py` — cascade.model_config persistence
- `ui/src/api/chat.ts` — SccModelConfig types + hook wiring
- `ui/src/pages/ChatPage.tsx` — collapsible config panel

## Self-Check: PASSED
- [x] Migration 0004 in Alembic chain
- [x] API accepts and persists model_config
- [x] TypeScript compiles clean
- [x] UI panel renders with all 8 selectors
