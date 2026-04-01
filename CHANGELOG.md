# Changelog

## 0.1.0

Initial release. Hard fork of GSD (Get Shit Done), renamed to eclusa.

### Added
- Six-stage narrowing pipeline: Refine, Match, Coherence, Formalize, Derive, Generate
- Schema commons (Qdrant-backed index of typed domain knowledge)
- Normalized intermediate representation for source types
- Haskell constraint workflow with GHC type-checking
- Project file schema (project.eclusa)
- Vestibular (human orientation file)
- Provenance chain with pipeline stage hashes
- Governance commands: decide, provenance, diagnose, config
- Ingestion commands: url, repo, file, scan, search, status, prune

### Changed
- All GSD references renamed to eclusa
- Planning directory: `.planning/` to `.eclusa/`
- Command prefix: `/gsd:` to `/eclusa:`
- Agent prefix: `gsd-*` to `eclusa-*`
- Package: `get-shit-done-cc` to `eclusa`

### Acknowledgments
Built on GSD's coordination infrastructure by TACHES.
