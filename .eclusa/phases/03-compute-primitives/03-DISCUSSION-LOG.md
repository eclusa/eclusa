# Phase 3: Compute Primitives - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-04
**Phase:** 03-compute-primitives
**Areas discussed:** Work session lifecycle, Proxy architecture, Judgment pass contract, Fan-out convergence, Model hot-swap, Cost tracking
**Mode:** Auto (all decisions auto-selected from recommended defaults)

---

## Work Session Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| pydantic-ai native harness (Recommended) | Model API + tools + direct DB writes | ✓ |
| Container-based harness | Docker container per session — heavy, complex lifecycle | |
| Raw API calls | No harness layer — manual tool management | |

**User's choice:** [auto] pydantic-ai native — per RFC §3.5.1

---

## Proxy Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| mitmproxy sidecar addon (Recommended) | ~30 lines, async artifact write, circuit-breaker | ✓ |
| Custom HTTP proxy | Full control, more code to maintain | |
| In-process middleware | No separate process, but couples proxy to harness | |

**User's choice:** [auto] mitmproxy addon — per research STACK.md

---

## Judgment Pass Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Single completion + JSON schema (Recommended) | One request, structured response, no tools | ✓ |
| Multi-turn with tools | More flexible but breaks topological independence | |
| Unstructured prose | Simpler but convergence detection is noise | |

**User's choice:** [auto] Single completion + JSON schema — per RFC §3.5.2

---

## Fan-out Convergence

| Option | Description | Selected |
|--------|-------------|----------|
| Field-by-field JSON comparison (Recommended) | Reliable with structured output | ✓ |
| Semantic similarity | More tolerant but less deterministic | |
| Majority vote | Loses minority model information | |

**User's choice:** [auto] Field-by-field — per research pitfall on prose convergence

---

## Model Hot-swap

| Option | Description | Selected |
|--------|-------------|----------|
| Platform-format history + adapters (Recommended) | Portable format, adapters on ingress/egress | ✓ |
| Provider-native format | Locked to one provider, no swap | |
| Full context replay | Re-run all turns on new model — expensive | |

**User's choice:** [auto] Platform format — per RFC §3.5.1

---

## Cost Tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Per-session JSONB column (Recommended) | Updated on each API call, queryable by cascade | ✓ |
| Separate cost table | Normalized, more complex queries | |
| Log-based | Append-only logs, requires aggregation | |

**User's choice:** [auto] JSONB column — per RFC entity definition

## Claude's Discretion

- mitmproxy addon details, circuit-breaker thresholds
- Object storage backend, context preparation algorithm
- Convergence comparison algorithm, hash function choice

## Deferred Ideas

None
