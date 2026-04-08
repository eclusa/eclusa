# Phase 6: Back Office UI and Self-Calibration - Research

**Researched:** 2026-04-05
**Domain:** React SPA (Vite 6 + shadcn/ui) + FastAPI REST/WebSocket extension + docker-compose bootstrap
**Confidence:** HIGH (stack locked by CLAUDE.md; agent interaction surface framework decision is MEDIUM, see below)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** React 19 + Vite 6 + shadcn/ui + Tailwind CSS 4 — locked by CLAUDE.md
- **D-02:** MercuryOS-like minimal aesthetic — clean, not cluttered, ambient information density
- **D-03:** TanStack Query 5 for all server state, Zustand 5 for local UI state (selected cascade, open panels)
- **D-04:** React Router 6 for SPA routing, no SSR needed
- **D-05:** Research must evaluate Open WebUI, Vercel AI SDK, and similar frameworks for the agent interaction parts (session transcripts, gate resolution, potentially live session steering)
- **D-06:** Forking an existing framework may be better than building from scratch or trying to iframe it — the framework MUST share the same frontend stack (React + Vite) or be adaptable to it
- **D-07:** The agent interaction surface is not a chat widget — it's the back office view of work sessions, judgment passes, and gate contexts. It needs structured data display, not just message bubbles
- **D-08:** Research should compare: (a) build custom with shadcn/ui components, (b) fork Open WebUI's React frontend, (c) use Vercel AI SDK's useChat/useCompletion hooks with custom UI, (d) other relevant frameworks
- **D-09:** The chosen approach must support: real-time transcript streaming (WebSocket), structured verdict display (not just text), gate resolution controls inline with context, cost attribution per message
- **D-10:** FastAPI REST endpoints extending the Phase 5 app (adapters/web/)
- **D-11:** WebSocket endpoint for live cascade updates and session transcript streaming
- **D-12:** All endpoints return Pydantic response models with explicit schemas
- **D-13:** JWT auth middleware (simple, single-tenant — no OAuth complexity)
- **D-14:** Active cascades: list view with stage status indicators, click-through to cascade detail
- **D-15:** Pending gates: context + model recommendation + resolve controls, filterable by gate type
- **D-16:** Session transcripts: message history with role indicators, tool call display, cost per message
- **D-17:** Cost dashboard: Recharts bar/line charts — cost per cascade, per session, per model
- **D-18:** TanStack Table with server-side pagination
- **D-19:** AS OF TIMESTAMP picker — date/time input that queries ledger state at that moment
- **D-20:** Pre-built timestamp templates: "now", "1 hour ago", "yesterday", "last week"
- **D-21:** Entity/fact/community list views with hybrid search integration
- **D-22:** Fact detail shows bi-temporal timestamps (valid from/until, created/expired)
- **D-23:** Graph visualization deferred — list-based browsing for v1, force-directed graph is v2
- **D-24:** All 8 metrics from db/queries/metrics/*.sql rendered in a single dashboard page
- **D-25:** Recharts for visualization — line charts for trends, bar charts for comparisons
- **D-26:** Metrics require 10+ gate resolutions to show meaningful values — empty state before that
- **D-27:** Extend existing docker-compose.yml with `ui` service (Vite dev server or nginx for built assets)
- **D-28:** `docker-compose up` boots everything: db, executor, proxy, web API, email adapter, UI
- **D-29:** Health checks on all services — UI waits for web API to be healthy

### Claude's Discretion

- Exact shadcn/ui component choices per view
- Recharts chart types and color scheme
- WebSocket message format for live updates
- JWT token lifetime and refresh strategy
- Exact routing structure (/cascades, /gates, /sessions, /costs, /ledger, /knowledge, /metrics)
- Which Open WebUI / Vercel AI SDK patterns to adopt vs build custom (informed by research)

### Deferred Ideas (OUT OF SCOPE)

- Force-directed graph visualization for knowledge graph — v2
- Real-time collaborative features (multiple operators on same cascade) — v2
- Custom theme editor for MercuryOS aesthetic — v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Dashboard showing active cascades with stage status | FastAPI `GET /cascades` + TanStack Query + shadcn/ui status badge components |
| UI-02 | Pending gates view with context, recommendation, and resolution controls | FastAPI `GET /gates?state=blocked` + `POST /gates/{id}/resolve` (already exists in routes.py) + inline resolve form |
| UI-03 | Session transcript viewer (work session message history) | WebSocket `ws://api/sessions/{id}/stream` + custom transcript renderer (NOT useChat — structured data, not chat bubbles) |
| UI-04 | Cost dashboard: token/cost per cascade, session, model | FastAPI `GET /costs` aggregation endpoint + Recharts BarChart/LineChart |
| UI-05 | Ledger query interface (AS OF TIMESTAMP explorer) | FastAPI `GET /ledger?as_of=` wrapping as_of.sql + TanStack Table server-side pagination |
| UI-06 | Knowledge graph explorer (entities, facts, communities) | FastAPI `GET /knowledge/entities|facts|communities` + search.py hybrid search endpoint |
| CAL-01 | Gate necessity rate metric | FastAPI `GET /metrics` executing db/queries/metrics/gate_necessity.sql |
| CAL-02 | Orchestrator absorption rate metric | db/queries/metrics/orchestrator_absorption.sql |
| CAL-03 | Resolution latency metric | db/queries/metrics/resolution_latency.sql |
| CAL-04 | Decision durability metric | db/queries/metrics/decision_durability.sql |
| CAL-05 | Cascade rework rate metric | db/queries/metrics/cascade_rework.sql |
| CAL-06 | Model convergence rate metric | db/queries/metrics/model_convergence.sql |
| CAL-07 | Minority model accuracy metric | db/queries/metrics/minority_accuracy.sql |
| CAL-08 | Fan-out necessity rate metric | db/queries/metrics/fanout_necessity.sql |
| INFRA-01 | `docker-compose up` boots full working instance | Extend docker-compose.yml with `ui` service (nginx multi-stage build) + health checks |
</phase_requirements>

---

## Summary

Phase 6 is the first user-facing surface of Eclusa. The backend is 5 phases deep with working FastAPI RBAC, 8 metric SQL queries, AS OF ledger explorer, and hybrid KG search. The work for this phase is two distinct tracks that run in parallel: (1) extend the FastAPI app with new REST/WebSocket endpoints for all UI views, and (2) build the React SPA that consumes them.

The critical load-bearing research question was the agent interaction surface (D-05 through D-09). The finding is clear: **build custom with shadcn/ui components**. Open WebUI is Svelte — not React, completely incompatible. LibreChat is React 18 + Tailwind 3 + Radix UI, not shadcn/ui, and the forking cost is high with no gain over building purpose-fit components. The Vercel AI SDK (`@ai-sdk/react`) is the most relevant external option, but its value proposition is SSE-based LLM streaming to a chat interface — not what Eclusa needs. The session transcript viewer is a structured data renderer (roles, tool calls, cost per message, judgment verdicts), not a chat widget. The WebSocket channel is push-only from server to client. Using `useChat` would mean fighting its assumptions about request/response flow.

The recommended approach for the agent interaction surface is: **custom shadcn/ui components + `react-use-websocket` for the WebSocket transport layer**. This gives full control over the structured display requirements (D-07, D-09) without framework adaptation overhead. The `react-use-websocket` library provides a stable useWebSocket hook (v4.13.0) that handles reconnection, readyState, and message buffering.

**Primary recommendation:** Build the entire UI with custom shadcn/ui components. Use `@ai-sdk/react` `useChat` only if a genuine chat-style interaction is added in a future phase. Wire the WebSocket transport with `react-use-websocket`. No framework forks.

---

## Agent Interaction Surface: Framework Evaluation

This section answers D-05 through D-08 directly. It is the load-bearing decision for the session transcript viewer, gate resolution panel, and future session steering.

### Option A: Build Custom with shadcn/ui

**Stack compatibility:** React 19 + Vite 6 + Tailwind 4 — perfect match. Zero adaptation cost.

**What you get for free:** Full shadcn/ui component library (cards, badges, tables, dialogs, forms, dropdowns, command palette). Copy-owned components — no version upgrade breaking changes. TanStack Query handles all async state. Zustand for open panel state.

**What you build yourself:**
- `TranscriptMessage` component: role badge + content + tool call tree + cost chip
- `JudgmentVerdictCard`: structured verdict display with model name, confidence, decision, rationale
- `GateContextPanel`: context document + divergence matrix + inline resolve form
- `CascadeTimeline`: stage graph with state indicators
- `WebSocketProvider`: wraps `react-use-websocket` with reconnect logic

**Effort:** ~3–4 waves for full UI. Each component is straightforward given the data shape from the backend.

**What you lose:** Nothing that matters. The "framework" value is in UI interaction patterns (message bubbles, input box, streaming cursors) — none of which apply to a back office structured transcript viewer.

**Licensing:** MIT (shadcn/ui copy-owned components, no license concern).

**Verdict: RECOMMENDED.** Highest alignment with D-07 and D-09.

---

### Option B: Fork Open WebUI Frontend

**Stack compatibility: INCOMPATIBLE.** Open WebUI is SvelteKit + Vite + Tailwind. Not React. Rewriting it in React would cost more than building from scratch. The "fork" path is a complete rewrite.

**Additional blocker:** Open WebUI's license requires preserving "Open WebUI" branding — not acceptable for a product-branded back office.

**Verdict: REJECTED.** Wrong framework (Svelte), wrong license terms.

---

### Option C: Vercel AI SDK `useChat` / `useCompletion`

**Stack compatibility:** `@ai-sdk/react` v3.0.148 (part of `ai` v6.0.146) works with React 18+ and Vite. The `'use client'` directive in examples is Next.js-specific and is simply not needed in a Vite project. Confirmed working with custom non-Vercel backends via the `transport` option pointing to any POST endpoint.

**What you get for free:**
- `useChat`: message state array, `sendMessage()`, `status` ('submitted'|'streaming'|'ready'|'error'), `stop()`, `setMessages()`
- SSE streaming parse — server emits `data:` events per the Data Stream Protocol (`x-vercel-ai-ui-message-stream: v1` header)
- `useCompletion`: single-turn text completion with streaming
- `useObject`: stream structured JSON objects

**Backend protocol (FastAPI side):**
```python
# FastAPI streaming endpoint compatible with useChat Data Stream Protocol
from fastapi.responses import StreamingResponse
import json

async def stream_generator():
    yield 'data: {"type":"start","messageId":"msg-1"}\n\n'
    yield 'data: {"type":"text-delta","textDelta":"Hello"}\n\n'
    yield 'data: [DONE]\n\n'

@app.post("/api/chat")
async def chat():
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"x-vercel-ai-ui-message-stream": "v1"}
    )
```

**What it doesn't cover:**
- WebSocket support — `useChat` is HTTP POST → SSE response only. Not WebSocket push. Eclusa needs server-initiated push for live cascade updates (stage state changes, new gates created). This is a structural mismatch.
- Structured data beyond messages — `useChat` message parts handle text and tool calls in a chat format. Displaying a convergence matrix, bi-temporal fact timestamps, or a cascade DAG requires custom rendering on top regardless.
- Gate resolution controls — nothing in the SDK handles inline form submission within a message thread.

**Licensing:** Apache 2.0 (verified via GitHub). No restriction on use.

**Verdict: PARTIAL FIT.** Useful if the session steering feature (future phase) requires a chat-style input box for directing live work sessions. Not appropriate as the primary pattern for Phase 6. The data shapes are wrong for a structured back office viewer, and the WebSocket requirement eliminates useChat as a drop-in.

**If adopted:** Import `useChat` from `@ai-sdk/react` only for the session steering input panel (if added). Do not use it for transcript display or gate resolution.

---

### Option D: LibreChat Fork

**Stack:** React 18 + Vite 7 + Tailwind 3 + Radix UI (not shadcn/ui). License: MIT.

**Stack compatibility:** Vite is compatible. React 18 vs 19 is manageable. The gap is Tailwind 3 vs 4 (breaking changes in utility class names) and Radix UI vs shadcn/ui (shadcn wraps Radix, but the component API differs). LibreChat's UI is deeply coupled to its multi-provider chat backend — the entire conversation management, model selection, plugin system, and Markdown rendering pipeline are intertwined.

**What you'd get from forking:** A working chat interface with message bubbles, code highlighting, file uploads, tool call display. None of this maps to Eclusa's structured transcript viewer.

**What you'd need to strip:** ~90% of the functionality. What remains would be simpler to build from scratch with shadcn/ui.

**Verdict: REJECTED.** Tailwind 3→4 migration cost + Radix→shadcn divergence + stripping 90% of features = more work than building custom. No meaningful gain over Option A.

---

### Agent Interaction Surface Decision Matrix

| Criterion | Custom shadcn/ui | Open WebUI Fork | Vercel AI SDK | LibreChat Fork |
|-----------|:---:|:---:|:---:|:---:|
| React 19 + Vite 6 compatible | YES | NO (Svelte) | YES | PARTIAL (React 18) |
| Tailwind 4 compatible | YES | NO | YES | NO (Tailwind 3) |
| WebSocket push support | YES (react-use-websocket) | N/A | NO (HTTP SSE only) | PARTIAL |
| Structured data display (not bubbles) | YES (full control) | N/A | PARTIAL (custom render) | PARTIAL |
| Inline gate resolution controls | YES | N/A | NO | NO |
| Cost per message display | YES | N/A | NO | NO |
| License | MIT | Requires branding | Apache 2.0 | MIT |
| Effort | BUILD | REWRITE | PARTIAL REUSE | STRIP+MIGRATE |
| **Recommendation** | **USE** | REJECT | USE selectively | REJECT |

---

## Standard Stack

### Core (locked by CLAUDE.md)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19 | UI rendering | Latest stable; shadcn/ui + Vite target React 18/19 |
| Vite | 6.x | Build tooling | Fastest HMR; standard SPA bundler in 2026 |
| TypeScript | 5.x | Type safety | Non-negotiable for data-dense admin panel |
| shadcn/ui | 4.1.2 (CLI) | UI component library | Copy-owned, Radix-based, Tailwind-styled |
| Tailwind CSS | 4.x | Utility CSS | Required by shadcn/ui v4 |
| TanStack Query | 5.96.2 | Server state | Standard for React data fetching in 2026 |
| TanStack Table | 8.21.3 | Data tables | Server-side pagination for ledger explorer |
| Recharts | 3.8.1 | Charts | shadcn chart pairing; sufficient for cost/metrics dashboards |
| React Router | 7.14.0 | SPA routing | `react-router-dom` v7; no SSR needed |
| Zustand | 5.0.12 | Local UI state | Lightweight; perfect for selected cascade, open panels |
| FastAPI | 0.135.3 | API (already installed) | Extend existing Phase 5 app |
| PyJWT | 2.12.1 | JWT auth (already installed) | Stateless token signing for single-tenant auth |

### Supporting (new additions for Phase 6)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| react-use-websocket | 4.13.0 | WebSocket hook | Session transcript streaming, live cascade updates |
| date-fns | latest | Date formatting | AS OF picker, timestamp display |
| @ai-sdk/react | 3.0.148 | Chat hooks (optional) | Reserve for session steering input panel (future phase) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-use-websocket | Native useRef + useEffect WebSocket | react-use-websocket adds reconnection, readyState, message filter — worth the 20KB |
| PyJWT (already installed) | python-jose | python-jose has better HMAC support but adds a dep; PyJWT is already in pyproject.toml |
| date-fns | dayjs | Both are fine; date-fns is tree-shakeable; dayjs is smaller but less tree-friendly with Vite |

**Installation (new UI directory):**
```bash
# Create UI workspace
cd ui && npm create vite@latest . -- --template react-ts
npm install

# Core stack (from CLAUDE.md)
npm install react-router-dom zustand @tanstack/react-query @tanstack/react-table recharts

# shadcn/ui init (requires Tailwind 4)
npx shadcn@latest init

# WebSocket transport
npm install react-use-websocket

# Date formatting
npm install date-fns
```

**Version verification (confirmed via npm registry, 2026-04-05):**
- `shadcn@4.1.2` — verified
- `@tanstack/react-query@5.96.2` — verified
- `@tanstack/react-table@8.21.3` — verified
- `recharts@3.8.1` — verified
- `zustand@5.0.12` — verified
- `react-router-dom@7.14.0` — verified
- `react-use-websocket@4.13.0` — verified

---

## Architecture Patterns

### Recommended Project Structure

```
ui/
├── src/
│   ├── api/              # TanStack Query hooks wrapping fetch calls
│   │   ├── cascades.ts   # useActiveCascades, useCascadeDetail
│   │   ├── gates.ts      # usePendingGates, useResolveGate
│   │   ├── sessions.ts   # useSessionTranscript, useSessionStream
│   │   ├── costs.ts      # useCostSummary, useCostByModel
│   │   ├── ledger.ts     # useLedgerAsOf
│   │   ├── knowledge.ts  # useEntities, useFacts, useCommunities, useSearch
│   │   └── metrics.ts    # useCalibrationMetrics
│   ├── components/
│   │   ├── ui/           # shadcn copy-owned components (generated by CLI)
│   │   ├── cascade/      # CascadeCard, StageStatusBadge, CascadeTimeline
│   │   ├── gate/         # GateContextPanel, GateResolveForm, DivergenceMatrix
│   │   ├── session/      # TranscriptMessage, ToolCallTree, CostChip, JudgmentVerdictCard
│   │   ├── ledger/       # LedgerTable, AsOfPicker, TimestampPresets
│   │   ├── knowledge/    # EntityRow, FactRow, BiTemporalBadge, SearchBar
│   │   ├── metrics/      # MetricCard, MetricChart, EmptyStateGuard
│   │   └── layout/       # AppShell, Sidebar, TopNav
│   ├── pages/
│   │   ├── DashboardPage.tsx      # UI-01: active cascades
│   │   ├── GatesPage.tsx          # UI-02: pending gates
│   │   ├── SessionPage.tsx        # UI-03: transcript viewer
│   │   ├── CostsPage.tsx          # UI-04: cost dashboard
│   │   ├── LedgerPage.tsx         # UI-05: AS OF explorer
│   │   ├── KnowledgePage.tsx      # UI-06: KG browser
│   │   └── MetricsPage.tsx        # CAL-01..08: calibration dashboard
│   ├── store/
│   │   └── ui.ts         # Zustand: selectedCascadeId, openPanels, authToken
│   ├── ws/
│   │   └── useSessionStream.ts   # react-use-websocket wrapper for session transcript
│   ├── auth/
│   │   ├── AuthProvider.tsx
│   │   └── useAuth.ts    # JWT token storage in localStorage, inject as Bearer header
│   └── main.tsx
├── Dockerfile            # Multi-stage: node build → nginx serve
├── nginx.conf            # SPA fallback: try_files $uri /index.html
├── vite.config.ts        # server: { host: true, hmr: { host: 'localhost' } } for Docker
└── package.json
```

### Pattern 1: TanStack Query wrapping FastAPI endpoints

**What:** All REST calls go through TanStack Query hooks in `src/api/`. Components never call `fetch` directly.

**When to use:** All server state that needs caching, refetching, loading/error states.

```typescript
// Source: TanStack Query v5 docs
// src/api/gates.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

export function usePendingGates() {
  return useQuery({
    queryKey: ['gates', 'pending'],
    queryFn: () => fetch('/api/gates?state=blocked', {
      headers: { Authorization: `Bearer ${getToken()}` }
    }).then(r => r.json()),
    refetchInterval: 10_000,  // poll every 10s as fallback
  })
}

export function useResolveGate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ gateId, decision, actorId, token }: ResolveParams) =>
      fetch(`/api/gates/${gateId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ token, decision, actor_id: actorId })
      }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gates'] })
  })
}
```

### Pattern 2: WebSocket for live transcript streaming

**What:** The session transcript viewer subscribes to a WebSocket channel that pushes new messages as they are written by the work session or judgment pass.

**When to use:** UI-03 session transcript, and live cascade state updates on the dashboard.

```typescript
// Source: react-use-websocket v4 docs
// src/ws/useSessionStream.ts
import useWebSocket, { ReadyState } from 'react-use-websocket'

export function useSessionStream(sessionId: string) {
  const { lastJsonMessage, readyState } = useWebSocket(
    `ws://localhost:8000/ws/sessions/${sessionId}`,
    {
      shouldReconnect: () => true,
      reconnectAttempts: 10,
      reconnectInterval: 3000,
      share: true,         // reuse connection if same sessionId
    }
  )
  return { message: lastJsonMessage, isConnected: readyState === ReadyState.OPEN }
}
```

**FastAPI WebSocket endpoint pattern:**
```python
# Source: FastAPI docs + established pattern from Phase 5 app structure
from fastapi import WebSocket
from typing import AsyncGenerator

@router.websocket("/ws/sessions/{session_id}")
async def session_stream(websocket: WebSocket, session_id: str, pool=Depends(get_pool)):
    await websocket.accept()
    async with pool.acquire() as conn:
        async for msg in poll_session_messages(conn, session_id):
            await websocket.send_json(msg)
```

### Pattern 3: Structured transcript message rendering

**What:** Session messages are not chat bubbles. Each message carries role, content parts (text, tool calls, tool results), cost attribution, and for judgment passes: a structured verdict.

**When to use:** UI-03 `TranscriptMessage` component.

```typescript
// Custom component — no framework needed
interface TranscriptMessageProps {
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: MessagePart[]
  cost?: { tokens_in: number; tokens_out: number; estimated_usd: number }
  model?: string
  verdict?: JudgmentVerdict
}

function TranscriptMessage({ role, content, cost, model, verdict }: TranscriptMessageProps) {
  return (
    <div className="flex gap-3 py-3 border-b border-border/30">
      <RoleBadge role={role} model={model} />
      <div className="flex-1 min-w-0">
        {content.map((part, i) =>
          part.type === 'text' ? <TextPart key={i} text={part.text} /> :
          part.type === 'tool-call' ? <ToolCallTree key={i} call={part} /> :
          null
        )}
        {verdict && <JudgmentVerdictCard verdict={verdict} />}
      </div>
      {cost && <CostChip cost={cost} />}
    </div>
  )
}
```

### Pattern 4: Self-calibration metrics — empty state before threshold

**What:** All 8 metric cards must render a clean empty state when fewer than 10 gate resolutions exist (D-26). The metric SQL queries return `null` values from `NULLIF(COUNT(*), 0)` divides when data is sparse.

**When to use:** `MetricCard` wrapping each of the 8 charts.

```typescript
function MetricCard({ title, value, description }: MetricCardProps) {
  if (value === null || value === undefined) {
    return (
      <Card className="opacity-50">
        <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Requires 10+ resolved gates to compute.
          </p>
        </CardContent>
      </Card>
    )
  }
  return <MetricChart title={title} value={value} description={description} />
}
```

### Pattern 5: FastAPI JWT middleware (single-tenant)

**What:** Simple PyJWT-based Bearer token middleware. Single operator identity — no user database, just a shared secret and actor_id in the token payload.

**When to use:** All API endpoints in the Phase 6 extension.

```python
# Source: FastAPI security docs + PyJWT 2.12 docs
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/cascades")
async def list_cascades(
    pool=Depends(get_pool),
    actor=Depends(verify_token)
):
    ...
```

### Pattern 6: AS OF ledger explorer with TanStack Table

**What:** The AS OF timestamp picker controls the query parameter. TanStack Table handles server-side pagination. Pre-built templates set the picker value.

```typescript
// src/pages/LedgerPage.tsx
const [asOf, setAsOf] = useState<string>(new Date().toISOString())
const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 50 })

const { data } = useQuery({
  queryKey: ['ledger', asOf, pagination],
  queryFn: () => fetch(
    `/api/ledger?as_of=${encodeURIComponent(asOf)}&page=${pagination.pageIndex}&size=${pagination.pageSize}`,
    { headers: authHeader() }
  ).then(r => r.json())
})

const table = useReactTable({
  data: data?.rows ?? [],
  columns,
  rowCount: data?.total ?? 0,
  manualPagination: true,
  onPaginationChange: setPagination,
  state: { pagination }
})
```

### Pattern 7: Docker Compose UI service (multi-stage build)

**What:** Dockerfile uses node:20-alpine for build stage, nginx:alpine for serve stage. SPA routing requires nginx `try_files $uri /index.html`.

**Vite Docker HMR pitfall:** In WSL2 environments, Vite's file watcher requires polling. The `vite.config.ts` must set `server.watch.usePolling: true` when running in Docker on WSL2.

```dockerfile
# ui/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

```nginx
# ui/nginx.conf
server {
  listen 80;
  root /usr/share/nginx/html;
  location / {
    try_files $uri $uri/ /index.html;
  }
  location /api {
    proxy_pass http://web:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```

```yaml
# docker-compose.yml additions
  web:
    build: .
    environment:
      - DATABASE_URL=postgresql://eclusa:eclusa@db:5432/eclusa
      - JWT_SECRET=${JWT_SECRET:-dev-secret-change-in-prod}
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 15s

  ui:
    build:
      context: ./ui
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      web:
        condition: service_healthy
```

### Anti-Patterns to Avoid

- **Using useChat for transcript display:** `useChat` assumes request→response flow where the UI sends messages. The session transcript is read-only streamed data. Wire WebSocket directly.
- **Querying metric SQL directly from React:** All 8 metric queries have lookback interval parameters. Expose a single `/api/metrics?lookback_days=30` endpoint; never embed SQL in the frontend.
- **TanStack Query for WebSocket state:** TanStack Query is for REST. WebSocket message state lives in local component state fed by `react-use-websocket`. Don't try to bridge them.
- **JWT in sessionStorage:** Use localStorage for the JWT — sessionStorage is cleared on tab close, breaking multi-tab back office use. Single-tenant means one operator; security risk is low.
- **Polling instead of WebSocket for transcript streaming:** Polling for session messages creates visible lag and hammers the DB. WebSocket push from FastAPI to React is the correct pattern. Use TanStack Query `refetchInterval` only for cascade list (coarse state, 10s interval is fine).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket reconnection logic | Custom useRef + useEffect + backoff | `react-use-websocket` | Reconnect, readyState, shared connections, message queue are all edge cases |
| Data table with server pagination | Custom table with cursor pagination | `@tanstack/react-table` v8 | `manualPagination: true` + `rowCount` is 3 lines |
| Date range arithmetic for AS OF templates | `new Date().getTime() - 3600000` | `date-fns` subHours/subDays | DST edge cases, formatting |
| Chart responsive container | Manual SVG resize observer | `<ResponsiveContainer>` from Recharts | Built-in; handles window resize |
| JWT decode on frontend | Custom base64 decode | `jwtDecode()` from `jwt-decode` package | Spec-correct, handles edge cases |
| SSE parsing in FastAPI | Manual `\n\n` flush logic | `fastapi.responses.StreamingResponse` with async generator | FastAPI handles flush semantics |

**Key insight:** The UI work in this phase is wiring existing backends to purpose-fit display components. The hand-rolling risk is in session transcript rendering — every custom "chat-like" display that tries to replicate message bubble UI patterns will be fighting the structured data model.

---

## Common Pitfalls

### Pitfall 1: Vite HMR broken inside Docker on WSL2

**What goes wrong:** Hot module replacement silently stops working — files change but the browser doesn't update.

**Why it happens:** inotify (Linux file events) doesn't propagate through WSL2's virtual filesystem layer. Vite's default file watcher relies on inotify.

**How to avoid:** Set in `vite.config.ts`:
```typescript
server: {
  host: true,
  watch: { usePolling: true, interval: 100 },
  hmr: { host: 'localhost' }
}
```

**Warning signs:** `vite dev` starts but changes to `.tsx` files don't reflect in browser without manual refresh.

---

### Pitfall 2: `asyncpg` JSON columns returned as strings

**What goes wrong:** `stage.input` and `ledger_entry.content` JSONB columns come back from asyncpg as Python strings, not dicts. FastAPI serializes these as escaped JSON-in-JSON strings to the frontend.

**Why it happens:** asyncpg returns JSONB as text by default. (Established in Phase 4 accumulated context.)

**How to avoid:** All new FastAPI endpoints that read JSONB columns must call `json.loads()` before populating Pydantic response models. This is already the pattern in `routes.py`.

**Warning signs:** Frontend receives `"{\"key\": \"value\"}"` (string) instead of `{"key": "value"}` (object).

---

### Pitfall 3: WebSocket disconnects during nginx proxy

**What goes wrong:** WebSocket connections to `/ws/` routes are dropped immediately by nginx.

**Why it happens:** nginx doesn't proxy WebSocket connections by default — it requires explicit `Upgrade` and `Connection` headers.

**How to avoid:** nginx.conf must include:
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```
On the `/api` proxy block (since the UI nginx proxies all `/api` traffic including `/api/ws/`).

**Warning signs:** WebSocket connection opens then immediately closes with code 1006.

---

### Pitfall 4: Metric SQL returns null — frontend must distinguish null from zero

**What goes wrong:** A metric chart shows "0%" when data is absent, misleading operators into thinking calibration is complete with 0% gate necessity.

**Why it happens:** The SQL queries use `NULLIF(COUNT(*), 0)` to avoid division by zero. They return `null` when no data exists — not `0`.

**How to avoid:** The `MetricCard` component must check `value === null` (not `!value`) and render the empty state. `value === 0` is a valid meaningful result (0% gate necessity = system recommendations are always accepted). Empty state only when `null`.

**Warning signs:** Charts showing 0% on a fresh install with no gate history.

---

### Pitfall 5: TanStack Query stale time vs WebSocket duplication

**What goes wrong:** Both a WebSocket subscription and a TanStack Query `refetchInterval` are active on the cascade list simultaneously. Gate resolution triggers both a WebSocket push AND a query refetch, causing double re-renders.

**Why it happens:** The architecture has two live update paths: WebSocket for transcript streaming (push) and TanStack Query refetch for coarse state polling (pull). Using both for the same data is redundant.

**How to avoid:** WebSocket push → update React state directly (not query cache). TanStack Query handles REST data. Do not use `useQueryClient().invalidateQueries()` from inside a WebSocket message handler for high-frequency events. Use `staleTime: Infinity` for data that only updates via WebSocket.

---

### Pitfall 6: shadcn/ui init requires Tailwind v4 config syntax

**What goes wrong:** Running `npx shadcn@latest init` fails or generates broken components because the project is using Tailwind v3 config syntax.

**Why it happens:** shadcn/ui v4+ targets Tailwind CSS v4 which changed from `tailwind.config.js` to CSS `@import "tailwindcss"` syntax.

**How to avoid:** Initialize the UI project with `npm create vite@latest` then run `npx shadcn@latest init` — it will scaffold the correct Tailwind v4 config. Do not manually copy Tailwind v3 config files.

**Warning signs:** CSS variable tokens (--primary, --background) not resolving; components appear unstyled.

---

### Pitfall 7: Docker Compose `depends_on` with health checks requires service_healthy condition

**What goes wrong:** `ui` service starts before `web` API is ready, gets connection refused on first requests, and React app shows error on initial load.

**Why it happens:** `depends_on: web` without `condition: service_healthy` only waits for container start, not application readiness.

**How to avoid:** The `web` service must have a `healthcheck` that hits `/health` (add this endpoint to FastAPI). The `ui` service must use `depends_on: web: condition: service_healthy`.

---

## Code Examples

### Self-calibration metrics endpoint (FastAPI)

```python
# Source: established pattern from Phase 5 routes.py; asyncpg interval pattern from Phase 1 state
from datetime import timedelta
import pathlib

METRIC_FILES = {
    f.stem: f.read_text()
    for f in sorted(pathlib.Path("db/queries/metrics").glob("*.sql"))
}

@router.get("/metrics")
async def get_metrics(
    lookback_days: int = 30,
    pool=Depends(get_pool),
    actor=Depends(verify_token)
):
    """Run all 8 calibration metric queries. Returns null values for insufficient data."""
    lookback = timedelta(days=lookback_days)
    results = {}
    async with pool.acquire() as conn:
        for name, sql in METRIC_FILES.items():
            if name == "minority_accuracy":
                rows = await conn.fetch(sql, lookback)
                results[name] = [dict(r) for r in rows]
            else:
                row = await conn.fetchrow(sql, lookback)
                results[name] = dict(row) if row else None
    return results
```

### Recharts metric chart with null guard

```typescript
// Source: Recharts 3.x docs — ResponsiveContainer + LineChart pattern
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function MetricLineChart({ data, dataKey, title }: MetricLineChartProps) {
  if (!data || data.length === 0) {
    return <MetricEmptyState title={title} />
  }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <XAxis dataKey="period" />
        <YAxis tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
        <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
        <Line type="monotone" dataKey={dataKey} stroke="hsl(var(--primary))" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

### TanStack Table ledger explorer (server-side pagination)

```typescript
// Source: TanStack Table v8 docs — manualPagination pattern
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table'

const table = useReactTable({
  data: data?.rows ?? [],
  columns: ledgerColumns,
  rowCount: data?.total ?? 0,
  manualPagination: true,
  getCoreRowModel: getCoreRowModel(),
  onPaginationChange: setPagination,
  state: { pagination },
})
```

---

## New FastAPI Endpoints Required

The Phase 5 app (`adapters/web/routes.py`) has only one endpoint: `POST /gates/{id}/resolve`. All of the following are new for Phase 6.

| Endpoint | Method | Purpose | Req |
|----------|--------|---------|-----|
| `GET /health` | GET | Docker health check | INFRA-01 |
| `POST /auth/login` | POST | Issue JWT token (actor_id + secret) | D-13 |
| `GET /cascades` | GET | Active cascade list with stage status | UI-01 |
| `GET /cascades/{id}` | GET | Cascade detail + stage graph | UI-01 |
| `GET /gates` | GET | Pending gates, filterable by state/type | UI-02 |
| `GET /sessions/{id}` | GET | Session metadata + message history | UI-03 |
| `WS /ws/sessions/{id}` | WS | Live session message stream | UI-03 |
| `WS /ws/cascades` | WS | Live cascade state updates | UI-01 |
| `GET /costs` | GET | Cost aggregation by cascade/session/model | UI-04 |
| `GET /ledger` | GET | Ledger entries with `as_of` + pagination | UI-05 |
| `GET /knowledge/entities` | GET | Entity list + search | UI-06 |
| `GET /knowledge/facts` | GET | Fact list + bi-temporal display | UI-06 |
| `GET /knowledge/communities` | GET | Community list | UI-06 |
| `GET /metrics` | GET | All 8 calibration metrics, `lookback_days` param | CAL-01..08 |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Create React App | Vite | 2022-2023 | CRA is deprecated; Vite is the default |
| TanStack Query v4 | TanStack Query v5 | 2023 | `useQuery({queryKey, queryFn})` shape changed; breaking |
| Tailwind CSS v3 config | Tailwind CSS v4 CSS-first config | 2024-2025 | `tailwind.config.js` replaced by `@import "tailwindcss"` |
| shadcn/ui with Tailwind v3 | shadcn/ui with Tailwind v4 CSS vars | 2025 | `--primary` etc. are CSS custom properties, not Tailwind classes |
| Vercel AI SDK v3/v4 (useChat) | AI SDK 6 (useChat from @ai-sdk/react) | Dec 2025 | Package split: core is `ai`, React hooks are `@ai-sdk/react` |
| React Router v6 | React Router v7 | 2024 | v7 is `react-router-dom` 7.x, backward compatible; new Data Router APIs |

**Deprecated:**
- `react-query` (pre-TanStack rename): replaced by `@tanstack/react-query`
- shadcn-chat (jakobhoeg/shadcn-chat): maintainer announced no longer maintained
- `create-react-app`: officially deprecated, not receiving security updates

---

## Open Questions

1. **WebSocket auth: how to pass JWT over WebSocket connection?**
   - What we know: HTTP Bearer header doesn't work for WebSocket upgrades in most browsers
   - What's unclear: Whether FastAPI's WebSocket accepts query param tokens (`ws://...?token=...`) or requires first message protocol
   - Recommendation: Use query parameter token for WebSocket handshake. `wss://api/ws/sessions/{id}?token={jwt}` is the standard pattern for FastAPI WebSocket auth. Treat query param token as equivalent to Bearer header for WebSocket-only connections.

2. **`react-router-dom` v7 vs v6 API compatibility**
   - What we know: v7 is the latest stable (7.14.0); v6 is `^6.x`; v7 has new Data Router APIs
   - What's unclear: Whether CLAUDE.md's "React Router 6.x" refers to v6 specifically or the v6-compatible API surface (which v7 preserves)
   - Recommendation: Use react-router-dom v7. The core `<Route>`, `<Link>`, `useNavigate()` API is backward compatible with v6. Pin to `^7.x` explicitly.

3. **CSS variables for MercuryOS aesthetic — dark mode defaults**
   - What we know: shadcn/ui v4 uses CSS custom properties for theming; MercuryOS is ambient/minimal
   - What's unclear: Whether to ship a dark-mode-first or light-mode-first theme
   - Recommendation: Dark-mode-first. Back office tools that operators stare at for hours benefit from dark default. shadcn/ui provides `dark:` Tailwind variants out of the box.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite build, npm | YES | v24.11.1 | — |
| npm | Package install | YES | 11.7.0 | — |
| Docker | Docker Compose services | YES | 29.2.1 | — |
| Docker Compose | `docker-compose up` (INFRA-01) | YES | v5.0.2 | — |
| Python 3.12+ | FastAPI extension | YES | 3.12.8 | — |
| uv | Python dep management | YES | 0.9.24 | — |
| PyJWT | JWT auth | YES | 2.12.1 (installed) | — |
| asyncpg | DB queries in endpoints | YES | 0.31.0 (installed) | — |
| FastAPI | API extension | YES | 0.135.3 (installed) | — |

**Missing dependencies with no fallback:** None. All required tools are present.

**Missing dependencies with fallback:** None blocking.

**New packages (add to pyproject.toml via `uv add`):**
- `pyjwt` is already installed (2.12.1). No new Python packages needed for auth.
- `passlib[bcrypt]` would be needed only if password hashing is added (not in scope for single-tenant — use a shared JWT secret).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio (asyncio_mode = auto) |
| Config file | `pytest.ini` (exists, `asyncio_mode = auto`) |
| Quick run command | `uv run pytest tests/test_web_api.py -x` |
| Full suite command | `uv run pytest tests/ -x` |
| Frontend test command | `cd ui && npm test` (vitest, Wave 0 setup) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | `GET /cascades` returns active cascades with stage status | integration | `uv run pytest tests/test_web_api.py::test_cascades_list -x` | No — Wave 0 |
| UI-02 | `GET /gates?state=blocked` returns pending gates | integration | `uv run pytest tests/test_web_api.py::test_gates_list -x` | No — Wave 0 |
| UI-03 | WebSocket `/ws/sessions/{id}` streams messages | integration | `uv run pytest tests/test_web_api.py::test_session_ws -x` | No — Wave 0 |
| UI-04 | `GET /costs` returns cost aggregation | integration | `uv run pytest tests/test_web_api.py::test_costs -x` | No — Wave 0 |
| UI-05 | `GET /ledger?as_of=` returns historical state | integration | `uv run pytest tests/test_web_api.py::test_ledger_as_of -x` | No — Wave 0 |
| UI-06 | `GET /knowledge/entities` returns entity list | integration | `uv run pytest tests/test_web_api.py::test_knowledge_entities -x` | No — Wave 0 |
| CAL-01..08 | `GET /metrics` returns all 8 metric values | integration | `uv run pytest tests/test_web_api.py::test_metrics_endpoint -x` | No — Wave 0 |
| INFRA-01 | `docker-compose up` boots all services | smoke | `docker compose up -d && sleep 15 && curl http://localhost:3000` | Manual |
| JWT auth | Endpoints reject requests without valid Bearer token | unit | `uv run pytest tests/test_web_api.py::test_jwt_required -x` | No — Wave 0 |

**Note on existing test infrastructure:** `tests/test_metrics.py` already tests that the 8 SQL queries execute against the DB schema. Phase 6 needs a new `tests/test_web_api.py` that tests the FastAPI endpoints serving those queries. Use the existing `httpx.AsyncClient + ASGITransport` pattern established in Phase 5 (`test_resolve.py`).

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_web_api.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green + docker-compose smoke test before `/eclusa:verify-work`

### Wave 0 Gaps

- `tests/test_web_api.py` — covers UI-01..06, CAL-01..08, JWT auth, WebSocket
- `ui/vite.config.ts` — Vite project config with Docker HMR fix
- `ui/package.json` — React 19 + locked stack dependencies
- Vitest setup for frontend unit tests (optional, after backend tests pass)

---

## Project Constraints (from CLAUDE.md)

All of the following apply to Phase 6 work:

- **Infrastructure:** Single Postgres instance only. No Redis, no separate cache.
- **Deployment:** `docker-compose up` — the UI service is a new entry in the existing file.
- **Python packaging:** `uv add` only, never `pip install` or `uv pip install`.
- **Python linting:** `ruff check . && ruff format .` before commit.
- **Python type checking:** `pyright` in strict mode on new API code.
- **Tests:** `pytest` + `pytest-asyncio` with `asyncio_mode = auto`. New endpoint tests use `httpx.AsyncClient + ASGITransport` (established Phase 5 pattern).
- **ORM:** SQLAlchemy 2.0 for schema definition; raw asyncpg for endpoint query hot paths.
- **Avoid:** LangChain, LangGraph, CrewAI, external vector DBs, separate graph DBs, Celery, Redis.
- **UI testing:** No SSR, no Next.js, no server components. Pure Vite SPA.
- **Workflow:** All changes through Eclusa workflow (`/eclusa:execute-phase`). No direct repo edits outside the workflow.

---

## Sources

### Primary (HIGH confidence)

- npm registry (`npm view [package] version`) — all version numbers verified 2026-04-05
- `adapters/web/routes.py` — existing RBAC endpoint structure confirmed
- `db/queries/metrics/*.sql` — 8 SQL files confirmed present and working (test_metrics.py passing)
- `pyproject.toml` — installed Python packages confirmed (PyJWT 2.12.1 present)
- `pytest.ini` — test framework configuration confirmed
- `docker-compose.yml` — existing structure confirmed (only `db` service currently)
- FastAPI WebSocket docs (`fastapi.tiangolo.com`) — WebSocket endpoint pattern confirmed

### Secondary (MEDIUM confidence)

- Open WebUI GitHub — Svelte stack confirmed via `svelte.config.js` and language breakdown
- LibreChat GitHub `client/package.json` — React 18, Vite 7, Tailwind 3 confirmed
- Vercel AI SDK docs (`ai-sdk.dev`) — `useChat` props, streaming protocol format confirmed
- `vercel.com/blog/ai-sdk-6` — AI SDK 6 stable, React/Svelte/Vue/Angular support confirmed
- Vercel Python streaming template — FastAPI + useChat Data Stream Protocol confirmed
- `react-use-websocket` GitHub — reconnection, readyState, shared connections confirmed
- Vite GitHub discussions — WSL2 HMR polling fix confirmed

### Tertiary (LOW confidence — flagged)

- MercuryOS aesthetic guidance: based on `feedback_ui_style.md` memory entry referencing `mercuryos-like-vibes.ts`. The actual MercuryOS reference file was not located in the repository during research. Planner should look for it at project root or `.claude/` directory.
- WebSocket JWT via query parameter: standard recommendation but not verified against FastAPI's specific security model. May need testing in Wave 0.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via npm registry; locked by CLAUDE.md
- Agent interaction surface evaluation: HIGH — Open WebUI confirmed Svelte (incompatible); Vercel AI SDK streaming protocol confirmed; LibreChat stack confirmed; custom build recommendation is evidence-based
- Architecture patterns: HIGH — based on existing Phase 5 code patterns (`routes.py`, asyncpg patterns from STATE.md)
- Pitfalls: HIGH for Docker/asyncpg pitfalls (established from prior phases); MEDIUM for WebSocket JWT auth (not tested in this project yet)

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (30 days — stable stack, no fast-moving dependencies except AI SDK patch versions)
