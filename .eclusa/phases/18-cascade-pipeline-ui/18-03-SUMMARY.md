# 18-03 Summary

Files changed:
- `adapters/web/api/trace.py` - Adds `GET /api/trace/{artifact_id}` and returns the full artifact → session → stage → cascade → intent hop chain as JSON.
- `adapters/web/app.py` - Registers the new trace router under `/api`.
- `db/queries/trace_chain.sql` - Canonical trace SQL used by the API and tests.
- `sql/trace_chain.sql` - Compatibility copy for the path referenced by the plan.
- `ui/src/api/trace.ts` - Adds `TraceHop`, `TraceChain`, `fetchTraceChain`, and `useTraceChain` with TanStack Query v5.
- `ui/src/components/cascade/TraceChainViewer.tsx` - Renders the clickable trace hop list and routes session/cascade hops to their detail pages.
- `ui/src/pages/CascadeDetailPage.tsx` - Reads `artifact_id` from the query string and renders the trace viewer below the pipeline.
- `adapters/web/api/cascades.py` - Adds `session_id` to stage output payloads so the UI can attach to the active session stream.
- `ui/src/api/cascades.ts` - Mirrors the new `session_id` field in the frontend type.
- `ui/src/components/cascade/StageOutputPanel.tsx` - Streams live assistant output for active stages via the existing session websocket and shows it inline.

Deviations from the plan:
- The plan described a stage-based trace route, but the delivered implementation follows the task requirement and exposes `/api/trace/{artifact_id}`.
- The plan called for a new stage websocket route, but the delivered streaming path reuses the existing `/ws/sessions/{session_id}` endpoint, which matches the task requirement to use the existing websocket protocol.
- `sql/trace_chain.sql` did not exist in the checkout, so I added a compatibility copy and kept the canonical query in `db/queries/trace_chain.sql`.

Commit SHAs:
- `09960f9` - Add artifact trace chain endpoint
- `067599e` - Add trace chain query hook
- `34a00dd` - Add trace chain viewer
- `8283d0c` - Wire trace chain into cascade detail
- `0c4eeca` - Add active stage live streaming
