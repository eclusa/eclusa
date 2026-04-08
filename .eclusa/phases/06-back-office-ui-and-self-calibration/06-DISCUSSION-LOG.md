# Phase 6: Back Office UI and Self-Calibration - Discussion Log

> **Audit trail only.**

**Date:** 2026-04-05
**Phase:** 06-back-office-ui-and-self-calibration
**Areas discussed:** UI framework, Agent interaction surface, API layer, Dashboard views, Ledger explorer, KG browser, Self-calibration, Docker-compose
**Mode:** Auto + user intervention on D-05 through D-09

---

## Agent Interaction Surface (USER-DIRECTED)

User explicitly requested research into Open WebUI, Vercel AI SDK, and similar frameworks before building the agent interaction parts. Key concern: forking an existing framework may be better than building custom or trying to iframe. The framework must share the React + Vite stack.

**User's exact words:** "research should include openwebui, vercel ai sdk, etc - when we get to the part of interacting with agents in the browser lets use existing stuff, this could be load bearing because forking one of those frameworks would be better than trying to iframe it (so it has at least to shared the same frontend stack)"

## All Other Areas
Auto-selected from recommended defaults per CLAUDE.md stack and MercuryOS aesthetic preference.

## Claude's Discretion
- Component choices, chart types, WebSocket format, JWT strategy, routing, which framework patterns to adopt

## Deferred Ideas
- Graph visualization, collaborative features, theme editor
