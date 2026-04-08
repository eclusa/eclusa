---
phase: 6
slug: back-office-ui-and-self-calibration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 6 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (frontend) + pytest (backend API endpoints) |
| **Quick run command** | `cd ui && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd ui && npx vitest run && cd .. && uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

## Wave 0 Requirements

- [ ] `ui/` directory scaffolded with Vite + React 19 + TypeScript
- [ ] shadcn/ui initialized with Tailwind CSS 4
- [ ] vitest configured
- [ ] react-use-websocket installed
- [ ] API endpoint stubs in adapters/web/

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
