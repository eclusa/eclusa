# Phase 4: Knowledge Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-05
**Phase:** 04-knowledge-layer
**Areas discussed:** Parser architecture, IR format, Embedding pipeline, Temporal KG ingestion, Hybrid search, Object storage
**Mode:** Auto (all decisions auto-selected from recommended defaults)

---

## Parser Architecture
**User's choice:** [auto] One module per format, shared IR output — pure functions, partial parse with warnings

## IR Format
**User's choice:** [auto] Pydantic model (entities, fields, relations, operations, constraints) — JSON-serializable, stored as JSONB

## Embedding Pipeline
**User's choice:** [auto] Inline API call during ingestion — entity-level granularity, text-embedding-3-small default

## Temporal KG Ingestion
**User's choice:** [auto] Episode → LLM extraction → entity resolution → fact creation with bi-temporal timestamps

## Hybrid Search
**User's choice:** [auto] SQL-based RRF fusion (cosine + BM25 + BFS) — no external reranker

## Object Storage
**User's choice:** [auto] Local filesystem with S3-compatible interface — blake3 content hash keys

## Claude's Discretion
- IR field types, embedding batch size, label propagation params, RRF k tuning, parser library choices

## Deferred Ideas
None
