# Chat UI Integration Research

**Researched:** 2026-04-05
**Domain:** React chat interface / AI streaming UI for existing SPA
**Confidence:** HIGH

---

## Summary

Eclusa needs a chat interface embedded in its React 19 + Vite 8 + shadcn/ui (zinc, CSS variables) back office, where operators type intents that create work cascades. The backend is FastAPI + pydantic-ai with SSE streaming.

The research found a clean, native integration path that was not obvious from the initial option list: **pydantic-ai ships a `VercelAIAdapter` that emits the Vercel AI Data Stream Protocol directly from FastAPI**. The frontend side of that protocol is `@ai-sdk/react` `useChat`. On top of `useChat`, **`assistant-ui`** provides production-grade React primitives (tool call display, streaming text, thread management) that theme directly off shadcn/ui CSS variables. The combination of these three — pydantic-ai `VercelAIAdapter` + Vercel AI SDK `useChat` + assistant-ui components — is the fastest, most aligned path to the stated goal.

Open WebUI is ruled out: it has no React embedding path and the GitHub discussion thread from Jan 2025 confirms no roadmap item exists. CopilotKit adds a cloud MAU pricing model that conflicts with single-tenant self-hosted deployment. chatscope is a generic chat component kit with no AI-specific primitives. LlamaIndex chat-ui is shadcn-based and Vercel AI SDK compatible but less composable than assistant-ui at 574 stars vs 400k+ monthly downloads.

**Primary recommendation:** pydantic-ai `VercelAIAdapter` (backend) + `@ai-sdk/react` `useChat` (hook) + `@assistant-ui/react` with `ExternalStoreRuntime` + Zustand (UI layer). All layers align with existing Eclusa stack choices.

---

## Option Evaluations

### Option 1: Open WebUI

**Verdict: ELIMINATED.**

Open WebUI is a Svelte/SvelteKit SPA. It cannot be imported as React components. The only embedding path is an iframe, which has documented authentication/CORS issues in their own GitHub discussions (multiple unresolved threads from 2025–2026). The maintainers have not acknowledged a React embedding API on their roadmap as of April 2026.

Using Open WebUI's OpenAI-compatible API (`/v1/chat/completions`) as a sidecar to talk to is architecturally wrong: it would add another service, another auth layer, and another database for conversation state — directly violating Eclusa's single-Postgres, minimal-services constraint.

| Criterion | Assessment |
|-----------|-----------|
| React 19 + Vite compatibility | No - Svelte native |
| Custom FastAPI backend | No path (sidecar only) |
| Streaming | SSE internally, not exposable |
| Theming to zinc dark | No |
| License | MIT |
| Embed into existing React app | Impossible without iframe |

**Do not use.**

---

### Option 2: Vercel AI SDK (`ai` + `@ai-sdk/react`)

**Verdict: REQUIRED FOUNDATION — use as the streaming layer, not the UI layer.**

Current stable: `ai@6.0.146`, `@ai-sdk/react@3.0.148` (verified 2026-04-05).

The AI SDK is framework-agnostic. `@ai-sdk/react` peer-deps are `react: '^18 || ~19.0.1 || ~19.1.2 || ^19.2.1'` — the project's `react@19.2.4` satisfies `^19.2.1`. Works with Vite (no Next.js requirement). Points to any backend URL.

**Critical finding:** pydantic-ai ships `VercelAIAdapter` that emits the exact stream format `useChat` expects. The backend becomes a single endpoint:

```python
# FastAPI backend — complete streaming endpoint
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

agent = Agent('anthropic:claude-sonnet-4-6')
app = FastAPI()

@app.post('/api/chat')
async def chat(request: Request) -> Response:
    return await VercelAIAdapter.dispatch_request(
        request, agent=agent, sdk_version=6
    )
```

The frontend `useChat` hook wires to this endpoint:

```typescript
import { useChat } from '@ai-sdk/react'

const { messages, sendMessage, status } = useChat({
  api: '/api/chat',
  headers: { Authorization: `Bearer ${token}` },
})
```

**Streaming protocol:** AI SDK 6 uses SSE as the wire format. The `x-vercel-ai-ui-message-stream: v1` header identifies the protocol. pydantic-ai's adapter handles this automatically. Debug with DevTools Network tab — no custom tooling needed.

**Tool call display:** `useChat` exposes `onToolCall` callback and tool invocation parts in `message.parts`. Each tool call has `type: 'tool-call'` with `toolName`, `args`, and `state` (partial/result).

**Custom data streaming (intent ID, tokens):** The protocol supports `data-*` custom parts streamed alongside text:

```python
# In the advanced adapter pattern, emit custom data
writer.write({'type': 'data-intentId', 'data': {'intentId': str(intent.id)}})
writer.write({'type': 'data-usage', 'data': {'inputTokens': usage.input, 'outputTokens': usage.output}})
```

Client reads via `message.parts` filtering or `onData` callback.

**Known issue (MEDIUM confidence):** GitHub issue #7496 in vercel/ai repo reports that AI SDK v5 data stream protocol had problems with FastAPI. AI SDK v6 redesigned around SSE which is simpler to implement. The pydantic-ai `VercelAIAdapter` with `sdk_version=6` is the supported path — avoid rolling a custom SSE encoder.

| Criterion | Assessment |
|-----------|-----------|
| React 19 + Vite | Yes — peer deps confirmed |
| Custom FastAPI backend | Yes — pydantic-ai VercelAIAdapter |
| Streaming | SSE, AI SDK v6 protocol |
| Model selection | Via request body param |
| Message history | `messages` array in hook state |
| Tool call display | `message.parts` with tool-call type |
| Cost display | Custom `data-usage` parts |
| Theming | Hook only — no UI, theme via component layer |
| License | Apache 2.0 |

**Use this as the streaming/data layer. Add a UI component layer on top.**

---

### Option 3: assistant-ui (`@assistant-ui/react`)

**Verdict: RECOMMENDED UI LAYER — pair with AI SDK.**

Current stable: `@assistant-ui/react@0.12.23`, `@assistant-ui/react-ai-sdk@1.3.17` (verified 2026-04-05). React peer deps: `'^18 || ^19'` — compatible.

assistant-ui is purpose-built React components for AI chat. 400k+ monthly npm downloads. Active development (latest release same day as this research, 2026-04-05). MIT license.

**Why it fits Eclusa specifically:**

1. **Themes off shadcn/ui CSS variables.** The project's `components.json` confirms `baseColor: "zinc"` with `cssVariables: true`. assistant-ui reads the same `--background`, `--foreground`, `--border`, `--muted` variables. Zero theming work.

2. **ExternalStoreRuntime owns the message state.** Eclusa stores conversations in Postgres, not in-memory. ExternalStoreRuntime is the correct runtime: "You own the state. Perfect for Redux, Zustand, or existing state management." Messages are fetched from the API, stored in Zustand, and the runtime bridges to assistant-ui's component tree.

3. **Tool call display is built-in.** The `Tool` component renders function calls with expandable inputs/outputs. No custom implementation needed.

4. **Thread list management.** Supports multi-thread with custom thread list (important if operators have multiple active cascades).

**Two runtime choices:**

**`LocalRuntime` (simpler):** assistant-ui manages all chat state internally. Implement one `ChatModelAdapter.run()` async generator. Best for a quick first implementation.

```typescript
import { LocalRuntime, useLocalRuntime, ChatModelAdapter } from '@assistant-ui/react'

const EclusaAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ messages }),
      signal: abortSignal,
    })
    // parse SSE stream, yield cumulative content
    const reader = response.body!.getReader()
    let text = ''
    for await (const chunk of parseSSEStream(reader)) {
      text += chunk.delta
      yield { content: [{ type: 'text', text }] }
    }
  }
}

// In component:
const runtime = useLocalRuntime(EclusaAdapter)
```

**`ExternalStoreRuntime` (recommended for production):** You own message state via Zustand. Messages load from Postgres via API. Supports `onNew`, `onEdit`, `onReload` handlers wired to your API.

```typescript
import { useExternalStoreRuntime, ExternalStoreAdapter } from '@assistant-ui/react'
import { useChatStore } from '@/store/chat'

const adapter: ExternalStoreAdapter<Message> = {
  messages: chatStore.messages,
  isRunning: chatStore.isRunning,
  setMessages: chatStore.setMessages,
  onNew: async (message) => {
    await chatStore.sendMessage(message)  // calls /api/chat, streams back
  },
  convertMessage: (msg) => ({
    id: msg.id,
    role: msg.role,
    content: [{ type: 'text', text: msg.content }],
    createdAt: new Date(msg.createdAt),
  }),
}

const runtime = useExternalStoreRuntime(adapter)
```

**Pairing with AI SDK:** The `@assistant-ui/react-ai-sdk` package provides `useChatRuntime` which wraps `useChat` from `@ai-sdk/react` and gives you assistant-ui components on top. This is the cleanest path when using pydantic-ai's VercelAIAdapter:

```typescript
import { useChatRuntime } from '@assistant-ui/react-ai-sdk'
import { AssistantRuntimeProvider, Thread } from '@assistant-ui/react'

function ChatPanel() {
  const runtime = useChatRuntime({ api: '/api/chat' })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />  // full chat UI, themes off your CSS vars
    </AssistantRuntimeProvider>
  )
}
```

`Thread` renders the full chat surface. Individual components (`ThreadMessages`, `Composer`, `AssistantMessage`, `UserMessage`) are composable for custom layouts.

| Criterion | Assessment |
|-----------|-----------|
| React 19 + Vite | Yes — peer deps `^18 \|\| ^19` confirmed |
| Custom FastAPI backend | Yes — via adapter or `useChatRuntime` |
| Streaming | Yes — built-in via LocalRuntime or AI SDK runtime |
| Model selection | Custom component, wire to state |
| Message history | ExternalStoreRuntime gives full control |
| Tool call display | Built-in `ToolUI` primitives |
| Cost display | Custom via data parts + `useMessage` hook |
| Theming | Reads shadcn CSS variables directly |
| License | MIT |

---

### Option 4: chatscope/chat-ui-kit-react

**Verdict: SKIP.**

Version 2.1.1, peer deps include React 19 (confirmed). MIT. Actively maintained (last release May 2025).

What it provides: `MessageList`, `Message`, `MessageInput`, `MainContainer`, `ChatContainer`. Generic chat components, not AI-specific. No streaming primitives, no tool call display, no built-in connection to any backend protocol. You'd need to build all streaming handling, typing indicators, tool visualization, and auto-scroll logic manually.

Compared to assistant-ui which has all of that built in, chatscope requires significantly more implementation for this use case. Only worth considering if you want the most minimal DOM surface with full control over every interaction detail. For Eclusa's requirements (tool calls, token display, streaming text), it adds more work than it saves.

---

### Option 5: CopilotKit

**Verdict: SKIP for Eclusa.**

Version 1.54.1. MIT license for the open-source SDK. React 19 peer deps confirmed. AG-UI protocol is well-designed.

The licensing issue: the free tier caps at **50 Monthly Active Users** before requiring $1,000/seat/month cloud plan. Eclusa is self-hosted, single-tenant. CopilotKit's value-add (Copilot Cloud) is irrelevant. The open-source self-hosted option exists but the company's monetization strategy creates maintenance risk — features may become cloud-only over time.

The AG-UI protocol itself is sound and pydantic-ai ships a native `AGUIAdapter`. But the React client SDK is CopilotKit, which carries the pricing model. Unless the operator counts stay permanently under 50 MAU, this is a financial risk.

The AG-UI protocol's actual value for Eclusa: zero. Eclusa's architecture already has real-time agent state in Postgres + LISTEN/NOTIFY. AG-UI shared state management replicates something that already exists at the DB layer. The extra protocol complexity adds no benefit.

---

### Option 6: shadcn/ui AI Components (Official Registry)

**Verdict: USE AS BUILDING BLOCKS, not as the complete solution.**

shadcn/ui launched an official AI component collection. Install via `npx shadcn@latest add [component]`. Components are copied into your project (copy-owned, not npm-installed). Tailwind 4 compatible. 25+ components covering: `Message`, `Conversation`, `PromptInput`, `ModelSelector`, `Reasoning`, `Tool`, `Sources`, `Branch`.

These understand Vercel AI SDK `message.parts` directly.

**The catch:** these are individual copy-paste components, not a wired-together chat surface. You still need the runtime wiring, state management, and scroll behavior. They serve as the leaf-level UI atoms.

**How they relate to assistant-ui:** assistant-ui's `Thread` component provides the wired-together surface; the shadcn AI registry provides the atoms. They can coexist — use assistant-ui's composable primitives styled like the official shadcn AI components.

**Recommended use:** Pull `PromptInput`, `ModelSelector` from the registry as-needed for specific Eclusa UI needs (e.g., the model selector for switching between Claude Sonnet and opus in the work session). Don't use the full shadcn AI chatbot block as a standalone solution.

---

### Option 7: Vercel AI Elements

**Verdict: PROMISING but requires Next.js setup for generator tooling.**

Vercel AI Elements is a shadcn-style registry for AI components. More opinionated than raw shadcn AI registry. The generator and CLI are Next.js-first. Since Eclusa is Vite-based, the CLI tooling may not work cleanly — the components themselves (once copied) should work fine, but the `npx ai-elements` scaffold workflow targets Next.js projects.

**Confidence:** LOW on Vite compatibility (not tested, no official Vite docs). The components themselves are shadcn primitives with Tailwind and should render correctly in Vite. The development workflow benefits (CLI generation) may not apply.

**Recommendation:** Pull specific components manually if needed. Do not depend on the AI Elements CLI workflow.

---

### Option 8: LlamaIndex chat-ui (`@llamaindex/chat-ui`)

**Verdict: VIABLE ALTERNATIVE to assistant-ui if you want less composition complexity.**

Version from 51 releases (latest Aug 2025). MIT. 574 stars. Built on shadcn/ui + Tailwind CSS. Connects via Vercel AI SDK `useChat` hook. Markdown rendering, code highlighting included.

**Compared to assistant-ui:**
- Simpler API: `ChatSection` wraps `ChatMessages` + `ChatInput`
- Less composable: fewer escape hatches for custom layouts
- Smaller community (574 stars vs 400k+ monthly downloads for assistant-ui)
- No ExternalStoreRuntime equivalent — harder to own message state

For Eclusa's multi-thread, Postgres-backed persistence requirement, assistant-ui's ExternalStoreRuntime is a clearer fit than LlamaIndex chat-ui's simpler model.

---

## Recommended Architecture

### The Stack

```
Frontend Layer          Backend Layer
──────────────────────  ─────────────────────────
@assistant-ui/react     pydantic-ai Agent
  └─ useChatRuntime       └─ VercelAIAdapter
  └─ ExternalStoreRuntime   └─ SSE → /api/chat
  └─ Thread, Composer     FastAPI endpoint
@ai-sdk/react (useChat)
Zustand (chat store)
shadcn/ui CSS variables (zinc, dark)
```

### Package Installation

```bash
# In /home/lynxnathan/code/eclusa/ui
pnpm add ai @ai-sdk/react @assistant-ui/react @assistant-ui/react-ai-sdk
```

Versions to pin:
- `ai@6.0.146`
- `@ai-sdk/react@3.0.148`
- `@assistant-ui/react@0.12.23`
- `@assistant-ui/react-ai-sdk@1.3.17`

No Python packages needed — pydantic-ai 1.77.0 already ships `pydantic_ai.ui.vercel_ai`.

### Wiring Diagram

```
Operator types intent
       │
       ▼
Composer (assistant-ui)
       │  sendMessage()
       ▼
useChat / useChatRuntime
       │  POST /api/chat   {"messages": [...], "sessionId": "..."}
       ▼
FastAPI /api/chat endpoint
       │  VercelAIAdapter.dispatch_request(request, agent=work_session_agent)
       ▼
pydantic-ai Agent.run_stream_events()
       │  streams SSE back
       ▼
AssistantMessage renders streaming text + tool calls
       │
       ▼
Intent created in Postgres → cascade begins
```

### State Architecture

The `ExternalStoreRuntime` pattern with Zustand is the correct model because Eclusa persists conversations in Postgres:

```typescript
// store/chat.ts
interface ChatState {
  threads: Record<string, Message[]>
  activeThreadId: string | null
  isRunning: boolean
  // actions
  loadThread: (threadId: string) => Promise<void>
  sendMessage: (threadId: string, content: string) => Promise<void>
}
```

The Zustand store calls `/api/chat/threads/{id}/messages` on load and `/api/chat` for new messages. The ExternalStoreRuntime bridges this to the assistant-ui component tree.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ai` | 6.0.146 | AI SDK core — stream protocol, types | The wire format that pydantic-ai VercelAIAdapter emits |
| `@ai-sdk/react` | 3.0.148 | `useChat` hook for React | React 19 peer dep satisfied; framework-agnostic hook |
| `@assistant-ui/react` | 0.12.23 | Chat UI components, ExternalStoreRuntime | MIT, shadcn CSS variable theming, tool call display built-in |
| `@assistant-ui/react-ai-sdk` | 1.3.17 | `useChatRuntime` bridge between AI SDK and assistant-ui | Thinnest adapter between the two layers |

### Python (already installed in pydantic-ai 1.77.0)

| Module | Location | Purpose |
|--------|----------|---------|
| `pydantic_ai.ui.vercel_ai` | pydantic-ai | `VercelAIAdapter` — SSE stream encoder |
| `pydantic_ai.ui` | pydantic-ai | `SSE_CONTENT_TYPE`, base `UIAdapter` |

No additional pip installs needed. The `pydantic-ai[ui]` extra may be needed — verify with `python -c "from pydantic_ai.ui.vercel_ai import VercelAIAdapter"`.

---

## Architecture Patterns

### Recommended Project Structure

```
ui/src/
├── components/
│   ├── ui/                    # existing shadcn components
│   └── chat/
│       ├── ChatPanel.tsx      # main chat surface
│       ├── ChatThread.tsx     # assistant-ui Thread wrapper
│       ├── ToolCallView.tsx   # custom tool call display
│       ├── TokenBadge.tsx     # cost display
│       └── ModelSelector.tsx  # model switcher
├── store/
│   └── chat.ts                # Zustand chat store
└── api/
    └── chat.ts                # fetch wrappers for /api/chat/*
```

### Pattern 1: Minimal Chat Surface (LocalRuntime, Day 1)

Start with LocalRuntime for the fastest first wire-up. Upgrade to ExternalStoreRuntime when persistence is needed.

```typescript
// components/chat/ChatPanel.tsx
import { useLocalRuntime, ChatModelAdapter } from '@assistant-ui/react'
import { AssistantRuntimeProvider, Thread } from '@assistant-ui/react'

const adapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }) {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-vercel-ai-ui-message-stream': 'v1',
      },
      body: JSON.stringify({ messages }),
      signal: abortSignal,
    })
    // assistant-ui's AI SDK runtime handles this for you via useChatRuntime
    // Only implement this manually if NOT using @assistant-ui/react-ai-sdk
  },
}
```

**Preferred:** use `useChatRuntime` from `@assistant-ui/react-ai-sdk` instead of implementing the adapter manually:

```typescript
// components/chat/ChatPanel.tsx
import { useChatRuntime } from '@assistant-ui/react-ai-sdk'
import { AssistantRuntimeProvider, Thread } from '@assistant-ui/react'

export function ChatPanel() {
  const runtime = useChatRuntime({
    api: '/api/chat',  // FastAPI endpoint with VercelAIAdapter
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex flex-col h-full bg-background">
        <Thread />
      </div>
    </AssistantRuntimeProvider>
  )
}
```

### Pattern 2: ExternalStoreRuntime with Postgres Persistence

```typescript
// store/chat.ts
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

export const useChatStore = create<ChatState>()(immer((set, get) => ({
  messages: [],
  isRunning: false,
  threadId: null,

  loadMessages: async (threadId: string) => {
    const msgs = await fetch(`/api/chat/threads/${threadId}/messages`).then(r => r.json())
    set(s => { s.messages = msgs; s.threadId = threadId })
  },

  sendMessage: async (content: string) => {
    set(s => { s.isRunning = true })
    // POST to /api/chat — streaming handled by runtime
    set(s => { s.isRunning = false })
  },
})))

// components/chat/ChatPanel.tsx
import { useExternalStoreRuntime } from '@assistant-ui/react'
import { useShallow } from 'zustand/react/shallow'

export function ChatPanel() {
  const { messages, isRunning, setMessages, sendMessage } = useChatStore(
    useShallow(s => ({ messages: s.messages, isRunning: s.isRunning, setMessages: s.setMessages, sendMessage: s.sendMessage }))
  )

  const runtime = useExternalStoreRuntime({
    messages,
    isRunning,
    setMessages,
    onNew: async (msg) => sendMessage(msg.content[0].text),
    convertMessage: (m) => ({
      id: m.id,
      role: m.role,
      content: [{ type: 'text', text: m.content }],
      createdAt: new Date(m.createdAt),
    }),
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />
    </AssistantRuntimeProvider>
  )
}
```

### Pattern 3: FastAPI Backend with VercelAIAdapter

```python
# In eclusa FastAPI app (e.g., adapters/web/routes.py or new chat.py)
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

# Work session agent — replace with actual Eclusa work session agent
work_agent = Agent('anthropic:claude-sonnet-4-6')

@router.post('/api/chat')
async def chat_endpoint(request: Request) -> Response:
    return await VercelAIAdapter.dispatch_request(
        request,
        agent=work_agent,
        sdk_version=6,
    )
```

For the intent creation side effect, intercept in the `onNew` handler (ExternalStoreRuntime) BEFORE streaming begins — create the intent record, attach the `intentId` to the request body, then stream.

### Pattern 4: Streaming Intent ID Back to Frontend

```python
# Advanced: stream the created intentId as a custom data part
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui import SSE_CONTENT_TYPE

@router.post('/api/chat')
async def chat_endpoint(request: Request) -> Response:
    body = await request.body()
    run_input = VercelAIAdapter.build_run_input(body)

    # Create intent BEFORE agent runs
    intent_id = await create_intent(run_input.messages[-1].content)

    # Inject intentId into custom data part header
    adapter = VercelAIAdapter(
        agent=work_agent,
        run_input=run_input,
        accept=request.headers.get('accept', SSE_CONTENT_TYPE),
    )
    event_stream = adapter.run_stream()
    sse_stream = adapter.encode_stream(event_stream)

    # Prepend intentId data event
    async def with_intent_id():
        yield f'data: {{"type":"data-intentId","data":{{"intentId":"{intent_id}"}}}}\n\n'
        async for chunk in sse_stream:
            yield chunk

    return StreamingResponse(with_intent_id(), media_type=SSE_CONTENT_TYPE)
```

### Anti-Patterns to Avoid

- **Do not iframe Open WebUI.** Authentication breaks on reload, CORS issues, no component integration.
- **Do not build a custom SSE parser.** Use pydantic-ai's VercelAIAdapter; it handles protocol compliance.
- **Do not use LangChain/LangGraph for the chat backend.** CLAUDE.md forbids it; pydantic-ai + VercelAIAdapter is the stack.
- **Do not use CopilotKit.** 50 MAU free tier cap; self-hosted Eclusa will hit this.
- **Do not mix pydantic-ai v1 models.** CLAUDE.md explicitly bans pydantic v1; VercelAIAdapter requires pydantic v2.
- **Do not call `uv pip install`.** Use `uv add` per CLAUDE.md and memory.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|------------|-------------|-----|
| SSE streaming from pydantic-ai | Custom SSE encoder | `VercelAIAdapter.dispatch_request()` | Protocol compliance, tool call serialization, error handling |
| Streaming text accumulation | Custom `ReadableStream` parser | `useChatRuntime` from `@assistant-ui/react-ai-sdk` | Handles chunking, reconnect, abort |
| Auto-scroll chat | `useEffect` + `scrollIntoView` | `Thread` from `@assistant-ui/react` | Battle-tested edge cases (streaming mid-scroll, user scrolled up) |
| Tool call rendering | `message.toolCalls.map(...)` | `ToolUI` primitives from `@assistant-ui/react` | Expandable inputs/outputs, loading states, approval UX |
| Typing indicator | CSS animation + state | Built into `Thread` | Matches streaming state automatically |
| Message branching / retry | Custom state machine | `onReload` handler in ExternalStoreRuntime | Handled by runtime, not UI logic |

**Key insight:** The streaming edge cases (abort mid-stream, reconnect after disconnect, partial JSON tool args) are subtle and well-handled by both pydantic-ai's adapter and assistant-ui's runtime. Rolling these from scratch in 2026 is a mistake.

---

## Common Pitfalls

### Pitfall 1: AI SDK v5 vs v6 Protocol Mismatch

**What goes wrong:** Frontend sends AI SDK v5 format; backend VercelAIAdapter responds with v6 SSE format. Streaming silently stops or shows garbled text.

**Why it happens:** pydantic-ai `VercelAIAdapter` defaults to `sdk_version=5` for backwards compatibility. AI SDK npm package is on v6.

**How to avoid:** Always set `sdk_version=6` on the `VercelAIAdapter`:
```python
VercelAIAdapter.dispatch_request(request, agent=agent, sdk_version=6)
```
Match the frontend `ai` package version: `ai@6.x` expects v6 protocol.

**Warning signs:** `useChat` shows no messages despite 200 responses; Network tab shows SSE events but `messages` array stays empty.

### Pitfall 2: pydantic-ai UI Module Not Installed

**What goes wrong:** `ImportError: cannot import name 'VercelAIAdapter' from 'pydantic_ai.ui.vercel_ai'`

**Why it happens:** The `pydantic-ai[ui]` extra may not be installed. The base `pydantic-ai` install may omit UI modules.

**How to avoid:**
```bash
uv add "pydantic-ai[ui]"
```
Verify: `python -c "from pydantic_ai.ui.vercel_ai import VercelAIAdapter; print('OK')`

### Pitfall 3: Message History Format Mismatch (ExternalStoreRuntime)

**What goes wrong:** Messages from Postgres have your domain shape; `convertMessage` returns an incompatible format; assistant-ui throws or renders nothing.

**Why it happens:** `ThreadMessageLike` requires specific `content` array format with typed parts.

**How to avoid:** Always implement `convertMessage` explicitly, even if your schema looks similar:
```typescript
convertMessage: (m: YourMessage) => ({
  id: m.id,
  role: m.role as 'user' | 'assistant',
  content: [{ type: 'text' as const, text: m.content }],
  createdAt: new Date(m.created_at),
})
```

### Pitfall 4: React 19 and `forwardRef` Deprecation

**What goes wrong:** Warnings about deprecated `forwardRef` usage from older chat libraries.

**Why it happens:** React 19 deprecated `forwardRef`. Libraries written for React 18 may trigger warnings.

**How to avoid:** assistant-ui 0.12.x is confirmed React 19 compatible and has updated ref handling. chatscope 2.1.1 added React 19 to peer deps but may still use `forwardRef`. Stick with assistant-ui to avoid this.

### Pitfall 5: Tailwind 4 CSS Variable Naming

**What goes wrong:** assistant-ui components don't pick up the project theme. Text is hard to read or colors are wrong.

**Why it happens:** Tailwind 4 moved from `@layer` declarations to `@theme inline {}` blocks. The variable names match between this project's `index.css` and assistant-ui's expectations, but the `@theme inline` mapping must exist.

**How to avoid:** The project's `index.css` already has `@theme inline` mapping `--color-background: var(--background)` etc. This is correct. No additional configuration needed. Verify by inspecting a `Thread` component in DevTools to confirm it resolves to your zinc colors.

### Pitfall 6: CORS on Streaming Endpoint

**What goes wrong:** SSE stream works in development (Vite proxy) but fails in production (direct FastAPI call).

**Why it happens:** SSE responses require `Access-Control-Allow-Origin` and `Access-Control-Expose-Headers: *` headers. Standard CORS middleware may not include SSE-specific headers.

**How to avoid:**
```python
# FastAPI CORS middleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
    expose_headers=["*"],  # Required for SSE
)
```

---

## Code Examples

### Full Minimal Integration (Day 1 target)

```typescript
// Source: assistant-ui docs + AI SDK docs (verified 2026-04-05)
// components/chat/ChatPanel.tsx
import { useChatRuntime } from '@assistant-ui/react-ai-sdk'
import { AssistantRuntimeProvider, Thread } from '@assistant-ui/react'
import '@assistant-ui/react/styles.css'

export function ChatPanel() {
  const runtime = useChatRuntime({ api: '/api/chat' })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="h-full flex flex-col">
        <Thread />
      </div>
    </AssistantRuntimeProvider>
  )
}
```

```python
# Source: pydantic-ai UI docs (verified 2026-04-05)
# adapters/web/chat.py
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response
from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter

router = APIRouter()
agent = Agent('anthropic:claude-sonnet-4-6')

@router.post('/chat')
async def chat(request: Request) -> Response:
    return await VercelAIAdapter.dispatch_request(
        request, agent=agent, sdk_version=6
    )
```

### Tool Call Display

```typescript
// Source: assistant-ui docs (verified 2026-04-05)
// assistant-ui renders tool calls automatically inside Thread
// For custom display, use makeAssistantToolUI:
import { makeAssistantToolUI } from '@assistant-ui/react'

const CreateCascadeTool = makeAssistantToolUI<
  { intentText: string },
  { cascadeId: string; status: string }
>({
  toolName: 'create_cascade',
  render: ({ args, result, status }) => (
    <div className="rounded border border-border p-2 text-sm">
      <span className="text-muted-foreground">Creating cascade for: </span>
      <span>{args.intentText}</span>
      {result && <span className="text-green-500 ml-2">→ {result.cascadeId}</span>}
    </div>
  ),
})
```

### Model Selector Integration

```typescript
// Wire model selection to useChat body param
const runtime = useChatRuntime({
  api: '/api/chat',
  body: { model: selectedModel },  // sent with every request
})
```

On the FastAPI side, read `model` from the request body before calling `VercelAIAdapter`:
```python
@router.post('/chat')
async def chat(request: Request) -> Response:
    data = await request.json()
    model_id = data.get('model', 'anthropic:claude-sonnet-4-6')
    agent = Agent(model_id)
    return await VercelAIAdapter.dispatch_request(request, agent=agent, sdk_version=6)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Build SSE parser manually | `VercelAIAdapter` (pydantic-ai) | 2025 Q1 | Eliminates ~200 lines of fragile protocol code |
| Custom chat components | `@assistant-ui/react` | 2024–2025 | Tool call display, auto-scroll, retry built-in |
| AI SDK requires Next.js API routes | `@ai-sdk/react` works with any backend | AI SDK v4+ | React SPA + FastAPI is first-class |
| SSE as text/event-stream | AI SDK v6 SSE with `x-vercel-ai-ui-message-stream: v1` | Dec 2025 | Standardized, browser DevTools debuggable |
| pydantic-ai + AI SDK manual glue | `VercelAIAdapter` official adapter | 2025 Q2 | Officially supported, maintained by Pydantic team |

**Deprecated/outdated:**
- `psycopg2`: Banned in CLAUDE.md; use `psycopg 3.3.x`
- AI SDK v4/v5 Data Stream Protocol for new FastAPI integrations: Use v6 SSE protocol
- Open WebUI iframe embedding: No viable path, confirmed stale feature request
- CopilotKit for self-hosted single-tenant: MAU pricing model misaligned

---

## Open Questions

1. **pydantic-ai `[ui]` extra in pyproject.toml**
   - What we know: `pydantic_ai.ui.vercel_ai.VercelAIAdapter` exists in pydantic-ai 1.77.0
   - What's unclear: Whether it requires `pydantic-ai[ui]` extra or is included in the base install
   - Recommendation: Verify by running `python -c "from pydantic_ai.ui.vercel_ai import VercelAIAdapter"` in the container. Add `[ui]` extra if it fails.

2. **assistant-ui CSS stylesheet import**
   - What we know: `@assistant-ui/react` ships a `styles.css`. The zinc CSS variable mapping in `index.css` uses `@theme inline` (Tailwind 4 syntax)
   - What's unclear: Whether assistant-ui's stylesheet conflicts with the project's existing `@theme inline` variable declarations
   - Recommendation: Import assistant-ui styles AFTER the project's `index.css`. Inspect output in DevTools. Override specifics in `index.css` if needed.

3. **Multiple models in same session**
   - What we know: `useChatRuntime({ body: { model } })` sends model per request; pydantic-ai `Agent` takes model at construction time
   - What's unclear: Eclusa may need dynamic model selection per-message (not per-session)
   - Recommendation: Create agent per request in the FastAPI handler (`Agent(model_id)` is cheap) rather than a singleton agent. Verify pydantic-ai supports this pattern without state leakage.

4. **Thread list for multiple active cascades**
   - What we know: assistant-ui supports multi-thread via `useAssistantInstructions` and custom thread list
   - What's unclear: How to map Eclusa cascade IDs to assistant-ui thread IDs in the ExternalStoreRuntime
   - Recommendation: Use cascade ID as thread ID. Store `Record<cascadeId, Message[]>` in Zustand. Mount a separate `AssistantRuntimeProvider` per active cascade panel, or use assistant-ui's built-in thread list with `CustomThreadList`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | pnpm install, Vite build | Check with `node --version` | — | — |
| pnpm | UI package management | Existing `pnpm-lock.yaml` found | — | npm (lock file mismatch) |
| pydantic-ai 1.77.0 | VercelAIAdapter | In `pyproject.toml` | 1.77.0 (from CLAUDE.md) | — |
| `pydantic_ai.ui` | VercelAIAdapter | Unverified — see Open Questions | — | fastapi-ai-sdk 0.1.0 (early) |

---

## Sources

### Primary (HIGH confidence)
- [assistant-ui GitHub](https://github.com/assistant-ui/assistant-ui) — features, runtime types, MIT license, version 0.12.23
- [assistant-ui LocalRuntime docs](https://www.assistant-ui.com/docs/runtimes/custom/local) — ChatModelAdapter interface, streaming example
- [assistant-ui ExternalStoreRuntime docs](https://www.assistant-ui.com/docs/runtimes/custom/external-store) — Zustand integration, full adapter interface
- [pydantic-ai VercelAIAdapter docs](https://ai.pydantic.dev/ui/vercel-ai/) — dispatch_request pattern, sdk_version param, FastAPI example
- [pydantic-ai UI overview](https://ai.pydantic.dev/ui/overview/) — adapter hierarchy, AGUIAdapter vs VercelAIAdapter
- [Vercel AI SDK useChat reference](https://ai-sdk.dev/docs/reference/ai-sdk-ui/use-chat) — transport architecture, callbacks, tool call handling
- [AI SDK stream protocol docs](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol) — SSE format, custom data parts, required headers
- [AI SDK 6 announcement](https://vercel.com/blog/ai-sdk-6) — breaking changes summary, DevTools, agent abstraction
- npm version verification (2026-04-05): `ai@6.0.146`, `@ai-sdk/react@3.0.148`, `@assistant-ui/react@0.12.23`, `@assistant-ui/react-ai-sdk@1.3.17`, `@copilotkit/react-core@1.54.1`, `@chatscope/chat-ui-kit-react@2.1.1`
- [Eclusa components.json](../../../ui/components.json) — zinc baseColor, cssVariables: true, confirmed shadcn setup

### Secondary (MEDIUM confidence)
- [pydantic-ai Vercel AI announcement article](https://pydantic.dev/articles/pydantic-ai-ui-vercel-ai) — integration overview, FastAPI code pattern
- [LlamaIndex chat-ui GitHub](https://github.com/run-llama/chat-ui) — shadcn/Tailwind foundation, useChat integration, MIT, 574 stars
- [pydantic-ai + FastAPI + React Vite example](https://github.com/mattlgroff/pydantic-ai-fastapi-react-vite-agent) — full-stack reference project
- [shadcn/ui AI components page](https://www.shadcn.io/ai) — 25+ AI components, `message.parts` integration
- [AI Elements GitHub](https://github.com/vercel/ai-elements) — Next.js-first CLI tooling
- [CopilotKit pricing page](https://www.copilotkit.ai/pricing) — 50 MAU free tier confirmed

### Tertiary (LOW confidence)
- [Open WebUI React integration discussion](https://github.com/open-webui/open-webui/discussions/7010) — no embedding solution confirmed, but thread may have progressed
- [Vercel AI SDK FastAPI issue #7496](https://github.com/vercel/ai/issues/7496) — v5 FastAPI data stream protocol issues; resolved by using v6 SSE protocol

---

## Metadata

**Confidence breakdown:**
- Recommended stack (pydantic-ai VercelAIAdapter + AI SDK + assistant-ui): HIGH — all three are official, version-pinned, and peer-dep verified
- ExternalStoreRuntime + Zustand pattern: HIGH — official assistant-ui docs, complete code examples found
- Theming compatibility (zinc CSS vars): HIGH — project's `components.json` confirms exact variable names assistant-ui expects
- pydantic-ai `[ui]` extra requirement: LOW — not explicitly tested, needs runtime verification
- Vite 8 + AI SDK 6 compatibility: MEDIUM — no Vite 8-specific docs found; Vite 8 is a minor version bump over Vite 7, AI SDK is bundler-agnostic

**Research date:** 2026-04-05
**Valid until:** 2026-07-05 (90 days — pydantic-ai and assistant-ui are both actively evolving)
