# Curated Knowledge Sources Research

**Researched:** 2026-04-01
**Purpose:** Machine-readable and documentation sources for software architecture patterns, tech radars, awesome lists, stack archetypes, and domain-specific knowledge across 12 categories.

---

## 1. Tech Radars

### ThoughtWorks Tech Radar (Machine-Readable)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/setchy/thoughtworks-tech-radar-volumes |
| **Format** | JSON, CSV, Google Sheets |
| **Typed Schema** | Yes -- structured JSON with quadrants (techniques, tools, platforms, languages-and-frameworks), rings (adopt, trial, assess, hold), and blip metadata |
| **Description** | Complete historical collection of all ThoughtWorks Technology Radar volumes in machine-readable formats. Auto-checked for updates weekly. |
| **Update cadence** | Twice yearly (new volumes), weekly data checks |

### ThoughtWorks Build Your Own Radar

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/thoughtworks/build-your-own-radar |
| **Format** | Accepts JSON arrays or CSV via public URL |
| **Typed Schema** | Yes -- documented input format (name, ring, quadrant, isNew, description) |
| **Description** | Library to generate interactive radar visualizations from your own data. The canonical radar framework. |

### AOE Technology Radar

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/AOEpeople/aoe_technology_radar |
| **Format** | Markdown frontmatter per item, rendered to static site via Next.js |
| **Typed Schema** | Partial -- each item is a Markdown file with typed YAML frontmatter (title, ring, quadrant, tags, featured) |
| **Description** | Static site generator for technology radars. v4.0 rewrite on Next.js. Adopted by Porsche Digital, Inventage, and others. |

### Zalando Tech Radar

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/zalando/tech-radar |
| **Format** | JavaScript data structures for D3 rendering |
| **Typed Schema** | No -- data embedded in JS |
| **Description** | Zalando's public technology radar for engineering alignment, based on ThoughtWorks' pioneering work. |

---

## 2. System Design

### System Design Primer (Original)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/donnemartin/system-design-primer |
| **Stars** | ~333k |
| **Format** | Markdown, PNG diagrams, Anki flashcards |
| **Typed Schema** | No -- documentation-only, Markdown with embedded images |
| **Description** | The most-starred system design resource. Covers scalability, caching, load balancing, databases, async patterns. Note: maintenance has slowed significantly; content is pre-2023. |

### System Design Primer Update

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/ido777/system-design-primer-update |
| **Format** | Markdown, structured as MkDocs site |
| **Typed Schema** | No -- documentation-only |
| **Description** | Actively maintained fork of the original, refreshed for 2025+ era with modern cloud-native and AI-augmented system design content. |

### ByteByteGo System Design 101

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/ByteByteGoHq/system-design-101 |
| **Stars** | ~78k |
| **Format** | Markdown with visual diagrams (PNG/SVG) |
| **Typed Schema** | No -- documentation with embedded visuals |
| **Description** | Visual-first system design explanations. Covers communication protocols, CI/CD, architectural patterns, microservices, databases. High-quality diagrams paired with concise text. |

### Karan Pratap Singh - System Design

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/karanpratapsingh/system-design |
| **Stars** | ~39k |
| **Format** | Markdown chapters |
| **Typed Schema** | No -- pure documentation |
| **Description** | Comprehensive system design course covering IP, DNS, load balancing, CQRS, event sourcing, API gateways, rate limiting, geohashing, and more. Well-organized chapter structure. |

---

## 3. Awesome Lists (Use-Case Categorized)

### awesome-selfhosted

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/awesome-selfhosted/awesome-selfhosted |
| **Stars** | ~220k+ |
| **Format** | Markdown (rendered from YAML data source) |
| **Typed Schema** | **Yes -- via companion data repo** |
| **Description** | Free Software network services and web apps for self-hosting. Categorized by use case (analytics, automation, blogging, communication, etc.). |

### awesome-selfhosted-data (MACHINE-READABLE)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/awesome-selfhosted/awesome-selfhosted-data |
| **Format** | YAML files per software entry + per tag |
| **Typed Schema** | Yes -- structured YAML with fields: name, URL, description, tags, license, language, source_code_url. Tags in `tags/tag-name.yml` |
| **Description** | Machine-readable YAML data powering awesome-selfhosted.net. Supports export to Markdown and HTML. Tags require minimum 3 referencing projects. The gold standard for structured awesome-list data. |

### awesome-python

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/vinta/awesome-python |
| **Stars** | ~262k |
| **Format** | Markdown, recently migrated to custom Python site generator with Jinja2 |
| **Typed Schema** | Partial -- has GitHub stars data integration and search functionality in the site build |
| **Description** | Opinionated list of Python frameworks, libraries, tools. Categorized by use case: admin panels, AI, async, audio, caching, CLI, CMS, databases, data validation, DevOps, etc. |

### awesome-go

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/avelino/awesome-go |
| **Stars** | ~138k+ |
| **Format** | Markdown |
| **Typed Schema** | No -- but companion repo `amanbolat/awesome-go-with-stars` adds star counts |
| **Description** | Curated Go frameworks, libraries, software. Categorized by use case: authentication, blockchain, bot building, CLI, configuration, databases, DevOps, email, etc. |

### awesome-rust

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/rust-unofficial/awesome-rust |
| **Stars** | ~56k |
| **Format** | Markdown with CI validation |
| **Typed Schema** | Partial -- inclusion criteria enforced algorithmically (50+ stars OR 2000+ crate downloads). Categories: Applications, Development Tools, Libraries |
| **Description** | 3500+ Rust projects with automated quality validation. Categorized by domain: audio, blockchain, CLI, compression, database, email, encoding, filesystem, games, graphics, GUI, etc. |

### awesome-typescript

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/dzharii/awesome-typescript |
| **Stars** | ~5k |
| **Format** | Markdown |
| **Typed Schema** | No -- documentation-only |
| **Description** | TypeScript resources for client-side and server-side development. Covers starters, tools, frameworks, IDEs, boilerplate. Less use-case-focused than language-specific alternatives. |

---

## 4. Stack Archetypes

### create-t3-app (T3 Stack)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/t3-oss/create-t3-app |
| **Stars** | ~26k+ |
| **Format** | TypeScript project scaffolding CLI |
| **Typed Schema** | Yes -- TypeScript throughout (Next.js + tRPC + Prisma + Tailwind + NextAuth). Strongly typed API layer via tRPC |
| **Description** | The canonical typesafe full-stack Next.js starter. Opinionated stack: Next.js, tRPC, Prisma, Tailwind CSS. Defines a "stack archetype" pattern. |

### RedwoodJS

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/redwoodjs/redwood |
| **Stars** | ~17.6k |
| **Format** | Full framework with CLI, generators, conventions |
| **Typed Schema** | Yes -- TypeScript, GraphQL SDL for API definitions, Cell pattern for data fetching |
| **Description** | Full-stack React framework. Uses GraphQL (not tRPC). Note: development winding down, fork at cedarjs.com is actively maintained. |

### Blitz.js

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/blitz-js/blitz |
| **Stars** | ~13.9k |
| **Format** | Next.js toolkit/framework |
| **Typed Schema** | Yes -- TypeScript, zero-API data layer inspired by Ruby on Rails |
| **Description** | "The Missing Fullstack Toolkit for Next.js." Similar architecture to T3 but with different API approach. Actively maintained. |

---

## 5. Orchestration (Typed Workflow Definitions)

### Temporal TypeScript SDK

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/temporalio/sdk-typescript |
| **Format** | TypeScript packages (`@temporalio/workflow`, `@temporalio/activity`, `@temporalio/worker`) |
| **Typed Schema** | Yes -- strongly typed workflow definitions. Workflows are TypeScript async functions with typed inputs/outputs. Activities decorated with `@activity.defn` |
| **Description** | Stateful workflow engine SDK. Workflows last seconds to days. Built-in retries, checkpoints, resumability. SDKs also for Go, Java, Python, .NET. |

### Temporal Samples

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/temporalio/samples-typescript |
| **Format** | TypeScript example projects |
| **Typed Schema** | Yes -- each sample demonstrates typed workflow + activity patterns |
| **Description** | Official Temporal TypeScript SDK samples showing typed workflow definitions in practice. |

### Dagster

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/dagster-io/dagster |
| **Stars** | ~12k+ |
| **Format** | Python with type annotations |
| **Typed Schema** | Yes -- Assets as first-class typed primitives. `@asset`, `@op`, `@job` decorators with typed inputs/outputs. `AssetCheckSpec` with partition definitions. `Definitions` object for grouping. |
| **Description** | Data orchestration platform. "Software-defined assets" model. Graph/dependency structure is a first-class object. Rich type system for data assets. |

### Prefect

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/PrefectHQ/prefect |
| **Stars** | ~18k+ |
| **Format** | Python with type annotations |
| **Typed Schema** | Partial -- `@flow` and `@task` decorators on regular Python functions. Types via Python type hints. Imperative model (not declarative graph). |
| **Description** | Python-native workflow orchestration. Flows and tasks are ordinary Python functions. Runtime builds dependency/state as code executes. |

### Apache Airflow

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/apache/airflow |
| **Stars** | ~39k+ |
| **Format** | Python DAG definitions |
| **Typed Schema** | Partial -- DAGs defined in Python with operator classes. Connection and variable schemas. Provider packages add typed integrations. |
| **Description** | The original workflow orchestrator. Huge ecosystem of providers/operators. Moving toward TaskFlow API with decorators. |

---

## 6. Modern Tooling

### Ruff (Python Linter/Formatter)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/astral-sh/ruff |
| **Stars** | ~40k+ |
| **Format** | TOML config (`ruff.toml`, `pyproject.toml [tool.ruff]`) + JSON Schema |
| **Typed Schema** | **Yes -- `ruff.schema.json`** at repo root. Full JSON Schema for all configuration options. Published to SchemaStore. |
| **Description** | Extremely fast Python linter and formatter in Rust. Config schema enables IDE validation. |
| **Schema URL** | `https://github.com/astral-sh/ruff/blob/main/ruff.schema.json` |

### uv (Python Package Manager)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/astral-sh/uv |
| **Stars** | ~55k+ |
| **Format** | TOML config (`uv.toml`, `pyproject.toml [tool.uv]`) + JSON Schema |
| **Typed Schema** | **Yes -- `uv.schema.json`** at repo root. Full JSON Schema for all settings. |
| **Description** | Blazing-fast Python package manager in Rust. Replaces pip, pip-tools, virtualenv, pyenv. |
| **Schema URL** | `https://github.com/astral-sh/uv/blob/main/uv.schema.json` |

### Biome (JS/TS Linter + Formatter)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/biomejs/biome |
| **Stars** | ~17k+ |
| **Format** | JSON config (`biome.json` / `biome.jsonc`) |
| **Typed Schema** | **Yes -- versioned JSON Schema** at `https://biomejs.dev/schemas/{version}/schema.json`. Also bundled in npm package at `node_modules/@biomejs/biome/configuration_schema.json` |
| **Description** | Unified formatter + linter for JS/TS/JSON/CSS. Biome 2.0+ has type-aware linting (~85% of typescript-eslint coverage). Replaces ESLint + Prettier. |

### Oxlint (JS/TS Linter)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/oxc-project/oxc |
| **Stars** | ~13k+ |
| **Format** | JSON config (`.oxlintrc.json`) |
| **Typed Schema** | **Yes -- `configuration_schema.json`** bundled in oxlint npm package at `node_modules/oxlint/configuration_schema.json` |
| **Description** | 50-100x faster than ESLint. Part of the Oxc Rust toolchain. ESLint v8 compatible config format. Linting only (no formatting). |

---

## 7. TUI Frameworks (Typed Component Models)

### Ratatui (Rust)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/ratatui/ratatui |
| **Stars** | ~12k+ |
| **Format** | Rust crate with strongly typed widget API |
| **Typed Schema** | Yes -- Rust type system. Immediate-mode rendering: each frame describes entire UI via typed Widget trait implementations. Layout, Block, Paragraph, Table, Chart, etc. all strongly typed. |
| **Description** | Rust TUI framework. Immediate-mode rendering. 30-40% less memory than BubbleTea equivalent. Zero-cost abstractions. |

### Awesome Ratatui

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/ratatui/awesome-ratatui |
| **Format** | Markdown |
| **Typed Schema** | No |
| **Description** | Curated list of TUI apps and libraries built with Ratatui. |

### Bubbletea (Go)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/charmbracelet/bubbletea |
| **Stars** | ~40k |
| **Format** | Go package with typed Model interface |
| **Typed Schema** | Yes -- Elm Architecture: `Model` interface with `Init() Cmd`, `Update(Msg) (Model, Cmd)`, `View() View` (v2). All components implement this typed interface. |
| **Description** | Go TUI framework based on The Elm Architecture. v2 changed View return type from `string` to `View` type. Companion libs: Bubbles (components), Lip Gloss (styling). |

### Textual (Python)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/Textualize/textual |
| **Stars** | ~26k+ |
| **Format** | Python framework with typed Widget classes |
| **Typed Schema** | Yes -- Python class hierarchy. Widget base class with COMPONENT_CLASSES, CSS-like styling, typed message system. Full type annotations. Runs in terminal AND web browser. |
| **Description** | Lean Python TUI framework. Sophisticated UIs with typed widget components: Button, Input, DataTable, Tree, TextArea. CSS-like layouts. |

### Ink (React/Node.js)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/vadimdemedes/ink |
| **Stars** | ~28k+ |
| **Format** | React components (JSX/TSX) |
| **Typed Schema** | Yes -- Full TypeScript types. React component model with Flexbox layout (via Yoga engine). Typed props: `TextProps`, `BoxProps`, etc. |
| **Description** | React for interactive CLI apps. Used by GitHub Copilot CLI, Gatsby, Prisma, Shopify. Companion: `@inkjs/ui` for pre-built components. |

---

## 8. Mobile UI (Typed Component Models)

### Flutter Widget Catalog (Typed Metadata)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/flutter/tools_metadata |
| **Specific file** | `resources/catalog/widgets.json` |
| **Format** | JSON |
| **Typed Schema** | **Yes -- JSON catalog of all Flutter widgets with metadata** (name, category, subcategory, description, link). Machine-readable widget taxonomy. |
| **Description** | Official Flutter tools metadata including the full widget catalog in JSON. This is the extractable source for Flutter's widget taxonomy. |

### Flutter Gems

| Property | Value |
|----------|-------|
| **URL** | https://fluttergems.dev/ |
| **Format** | Web catalog (not a Git repo) |
| **Typed Schema** | No -- curated web directory |
| **Description** | Curated list of top Dart/Flutter packages categorized by use case. Community-driven alternative to pub.dev browsing. |

### Jetpack Compose / SwiftUI Comparison

| Property | Value |
|----------|-------|
| **URL** | https://www.jetpackcompose.app/compare-declarative-frameworks/JetpackCompose-vs-SwiftUI-vs-Flutter |
| **Format** | Web documentation |
| **Typed Schema** | No -- comparison documentation |
| **Description** | Side-by-side component comparison across Flutter, Jetpack Compose, and SwiftUI. Useful for understanding typed component equivalences across frameworks. |

---

## 9. Embedded

### Arduino Library Registry

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/arduino/library-registry |
| **Format** | Text file (list of repo URLs) + generated `library_index.json` |
| **Typed Schema** | Partial -- the registry itself is a simple URL list; the generated index (`library_index.json`) has structured JSON with name, version, author, maintainer, sentence, paragraph, category, architectures, types, dependencies |
| **Description** | Official Arduino Library Manager registry. Libraries registered by adding repo URL. Index engine at `arduino/libraries-repository-engine` generates the structured JSON index. |

### Arduino Libraries Repository Engine

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/arduino/libraries-repository-engine |
| **Format** | Go tool that generates JSON library index |
| **Typed Schema** | Yes -- generates structured `library_index.json` with typed fields per library release |
| **Description** | The tool that crawls registered libraries and produces the Library Manager index. Source of truth for the JSON schema. |

### ESP-IDF Component Manager

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/espressif/idf-component-manager |
| **Format** | YAML manifest (`idf_component.yml`) |
| **Typed Schema** | Yes -- documented YAML schema with fields: dependencies (with version constraints, registry URL, git source, local path), optional dependencies with conditional rules (`if` clauses based on `idf_version`), targets, public flag |
| **Description** | Tool for managing ESP-IDF components. Manifest format supports ESP Component Registry, git repos, and local sources. |
| **Schema docs** | https://docs.espressif.com/projects/idf-component-manager/en/latest/reference/manifest_file.html |

### PlatformIO Registry

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/platformio/platformio-registry |
| **Format** | JSON manifest (`library.json`) |
| **Typed Schema** | **Yes -- JSON Schema** at `https://raw.githubusercontent.com/platformio/platformio-core/develop/platformio/assets/schema/library.json`. Validated in IDE. Registry API v1/v2/v3 at `api.registry.platformio.org` |
| **Description** | World's first embedded package/dependency management. JSON Schema for library manifests. Multi-version API. |

---

## 10. Data Engineering

### Apache Iceberg Spec

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/apache/iceberg |
| **Spec file** | `format/spec.md` |
| **Format** | Markdown spec + Avro schemas for manifest files + JSON for table metadata |
| **Typed Schema** | **Yes -- Avro IDL for manifest schemas, JSON for table metadata (`metadata.json`), typed schema definitions for all data types (primitives + nested: map, list, struct). Field IDs for column pruning.** |
| **Description** | Open table format for huge analytic datasets. v1/v2/v3 specs complete. Latest stable: 1.8.0 (Feb 2025). ACID writes, snapshot isolation, billion-partition scale. |
| **Spec URL** | https://iceberg.apache.org/spec/ |

### Delta Lake Protocol

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/delta-io/delta |
| **Spec file** | `PROTOCOL.md` |
| **Format** | Markdown protocol specification |
| **Typed Schema** | Partial -- protocol is in Markdown but defines JSON action types (add, remove, metaData, txn, protocol, commitInfo). Schema serialization defined in spec. Delta Lake 4.0 (Sep 2025) adds coordinated commits and variant data type. |
| **Description** | Open storage framework for Lakehouse architecture. ACID transactions on data lakes. PROTOCOL.md defines the transaction log format. |

### Delta Lake Rust

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/delta-io/delta-rs |
| **Format** | Rust library with Python bindings |
| **Typed Schema** | Yes -- Rust type system enforces protocol types |
| **Description** | Native Rust implementation of Delta Lake with Python bindings. Strongly typed protocol implementation. |

### OpenLineage Spec

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/OpenLineage/OpenLineage |
| **Spec file** | `spec/OpenLineage.md` + `spec/OpenLineage.json` |
| **Format** | **JSON Schema + OpenAPI spec** |
| **Typed Schema** | **Yes -- formalized as JSON Schema (`OpenLineage.json`). OpenAPI spec for HTTP implementations. Facet-based extensibility model.** |
| **Description** | Open standard for data lineage. JSON Schema defines Run, Job, Dataset events with facets. Recently added subset dataset facets for representing dataset relationships. |

### Dagster (also in Orchestration section)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/dagster-io/dagster |
| **Format** | Python with type annotations |
| **Typed Schema** | Yes -- `@asset`, `AssetKey`, `AssetCheckSpec`, `PartitionDefinition`, `DagsterType`, `IOManager` all strongly typed |
| **Description** | Software-defined assets with rich type system. First-class data lineage, dependency graphs, and partition management. |

---

## 11. Cloud Architecture Patterns

### AWS Well-Architected Custom Lens Hub

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/aws-samples/custom-lens-wa-hub |
| **Format** | **JSON templates** per lens |
| **Typed Schema** | **Yes -- JSON template with typed structure: pillars, questions, choices, risks, bestPractices, helpfulResources. Machine-readable assessment framework.** |
| **Description** | JSON templates for creating custom Well-Architected reviews. Includes ECS Lens, ORR Lens, and more. The JSON schema defines the complete assessment structure. |

### AWS Well-Architected Labs

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/awslabs/aws-well-architected-labs |
| **Format** | Markdown labs + CloudFormation/Terraform templates |
| **Typed Schema** | Partial -- labs are documentation but include IaC templates (typed CloudFormation/Terraform) |
| **Description** | Hands-on labs for learning, measuring, and building with AWS architectural best practices across all 6 pillars. |

### AWS ML Lens for Well-Architected

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/aws-samples/aws-machine-learning-lens-well-architected |
| **Format** | JSON file |
| **Typed Schema** | Yes -- same custom lens JSON format |
| **Description** | Machine Learning specific lens as JSON for upload to AWS Well-Architected Tool. |

### Azure Architecture Center

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/MicrosoftDocs/architecture-center |
| **Format** | Markdown documentation with YAML metadata |
| **Typed Schema** | Partial -- Markdown with YAML frontmatter (title, description, ms.topic, ms.service). Patterns in `docs/patterns/`. Architecture styles in `docs/guide/architecture-styles/` |
| **Description** | Open-source docs for Azure Architecture Center. Cloud design patterns, architecture styles (N-tier, microservices, event-driven, big data, big compute), and reference architectures. |

### GCP Architecture Guides

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/GCP-Architecture-Guides |
| **Format** | Markdown + Terraform modules |
| **Typed Schema** | Partial -- Terraform definitions are typed; architecture guides are Markdown |
| **Description** | Google Cloud architecture patterns and reference implementations. Includes Terraform for deployable patterns. |

### GCP Cloud Solutions

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/GoogleCloudPlatform (org) |
| **URL** | https://googlecloudplatform.github.io/cloud-solutions/ |
| **Format** | Mixed (Terraform, Python, docs) |
| **Typed Schema** | Varies per solution |
| **Description** | Tools, demos, and reference architectures from Google Cloud Solutions Architects. |

---

## 12. Design Patterns

### Awesome Design Patterns (Meta-Collection)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/DovAmir/awesome-design-patterns |
| **Stars** | ~42k |
| **Format** | Markdown with categorized links |
| **Typed Schema** | No -- curated link collection |
| **Description** | Comprehensive meta-list of software and architecture design patterns. Covers GoF, CQRS, microservices, cloud, serverless, distributed systems, DevOps, and more. Best starting point for pattern discovery. |

### Java Design Patterns

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/iluwatar/java-design-patterns |
| **Stars** | ~93k |
| **Format** | Java source code with categorization metadata |
| **Typed Schema** | Yes -- each pattern is a Java project with typed implementation. Categorized by tags (Performance, Gang of Four, Data access) and categories (Creational, Structural, Behavioral, Concurrency). Searchable web interface. |
| **Description** | The definitive design patterns implementation repo. Each pattern has: intent, explanation, applicability, known uses, related patterns. Fully typed Java code. |

### Python Design Patterns

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/faif/python-patterns |
| **Stars** | ~42k |
| **Format** | Python source files organized by category |
| **Typed Schema** | Partial -- Python implementations with type hints in modern versions. Categories: creational, structural, behavioral, fundamental |
| **Description** | Design patterns and idioms in Python. Each pattern is a standalone `.py` file with docstring explanation. |

### Go Design Patterns

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/tmrts/go-patterns |
| **Format** | Go source + Markdown explanations |
| **Typed Schema** | Yes -- Go type system. Categories: creational, structural, behavioral, synchronization, concurrency, messaging, stability |
| **Description** | Idiomatic Go implementations of design patterns, recipes, and idioms. |

### Domain-Driven Hexagon (DDD + Hexagonal Architecture)

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/Sairyss/domain-driven-hexagon |
| **Stars** | ~14k |
| **Format** | TypeScript/NestJS source code + extensive README |
| **Typed Schema** | Yes -- Full TypeScript implementation. Ports, adapters, domain services, value objects, entities, aggregates all as typed classes/interfaces. |
| **Description** | Comprehensive DDD + hexagonal architecture example with NestJS. Framework-agnostic principles. Includes: bounded contexts, CQRS, domain events, repository pattern. Note: overkill for simple CRUD apps. |

### Awesome DDD

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/heynickc/awesome-ddd |
| **Format** | Markdown links |
| **Typed Schema** | No -- curated link collection |
| **Description** | Curated list of DDD, CQRS, Event Sourcing, and Event Storming resources. Books, talks, sample projects, libraries. |

### Game Programming Patterns

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/munificent/game-programming-patterns |
| **Stars** | ~4.4k |
| **Format** | HTML/Markdown (book source), C++ code examples |
| **Typed Schema** | No -- book content with embedded code samples |
| **Description** | Robert Nystrom's book, fully free online at gameprogrammingpatterns.com. Covers: Command, Flyweight, Observer, Prototype, Singleton, State, Double Buffer, Game Loop, Update Method, Bytecode, Subclass Sandbox, Type Object, Component, Event Queue, Service Locator, Data Locality, Dirty Flag, Object Pool, Spatial Partition. |

### DDD Library Example

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/ddd-by-examples/library |
| **Format** | Java source code |
| **Typed Schema** | Yes -- Java typed DDD implementation with strategic analysis |
| **Description** | Comprehensive DDD example with problem space strategic analysis and various tactical patterns. |

---

## Summary: Best Machine-Readable Sources (Typed/Structured Data)

These are the sources with actual extractable, typed data -- not just documentation:

| Source | Format | Why It Matters |
|--------|--------|----------------|
| `setchy/thoughtworks-tech-radar-volumes` | JSON/CSV | Complete historical tech radar data, machine-parseable |
| `awesome-selfhosted/awesome-selfhosted-data` | YAML | Structured software catalog with tags, categories, metadata |
| `flutter/tools_metadata` (widgets.json) | JSON | Official typed widget catalog |
| `astral-sh/ruff` (ruff.schema.json) | JSON Schema | Complete linter/formatter config schema |
| `astral-sh/uv` (uv.schema.json) | JSON Schema | Complete package manager config schema |
| `biomejs/biome` (schema.json) | JSON Schema | Versioned linter/formatter config schema |
| `oxc-project/oxc` (configuration_schema.json) | JSON Schema | Linter config schema |
| `platformio/platformio-core` (library.json schema) | JSON Schema | Embedded library manifest schema |
| `OpenLineage/OpenLineage` (OpenLineage.json) | JSON Schema + OpenAPI | Data lineage event schema |
| `apache/iceberg` (format/) | Avro IDL + JSON | Table format spec with typed schemas |
| `aws-samples/custom-lens-wa-hub` | JSON | Well-Architected assessment framework templates |
| `iluwatar/java-design-patterns` | Java + metadata | Categorized, tagged, typed pattern implementations |
| `Sairyss/domain-driven-hexagon` | TypeScript | Fully typed DDD/hex architecture reference |
| `temporalio/sdk-typescript` | TypeScript | Strongly typed workflow definitions |
| `dagster-io/dagster` | Python typed | Software-defined assets with type system |

---

## Appendix: Awesome TUI Meta-List

| Property | Value |
|----------|-------|
| **Repo** | https://github.com/rothgar/awesome-tuis |
| **Format** | Markdown |
| **Typed Schema** | No |
| **Description** | List of projects providing terminal user interfaces, cross-language. |
