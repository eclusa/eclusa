# Eclusa Schema Commons Starter Pack -- Industry Research

**Researched:** 2026-04-01
**Scope:** 20 industries, formal standards, OSS implementations, behavioral specifications
**Focus:** Publicly available typed schemas on GitHub, actively maintained (2024-2026)

---

## Table of Contents

1. [Music](#1-music)
2. [Healthcare](#2-healthcare)
3. [Finance / Banking](#3-finance--banking)
4. [Payments](#4-payments)
5. [E-commerce](#5-e-commerce)
6. [Identity / Auth](#6-identity--auth)
7. [Travel](#7-travel)
8. [Logistics / Supply Chain](#8-logistics--supply-chain)
9. [Insurance](#9-insurance)
10. [Real Estate](#10-real-estate)
11. [Telecommunications](#11-telecommunications)
12. [Cloud / Infrastructure](#12-cloud--infrastructure)
13. [Messaging / Communication](#13-messaging--communication)
14. [Analytics / Observability](#14-analytics--observability)
15. [CRM / Sales](#15-crm--sales)
16. [DevOps / CI](#16-devops--ci)
17. [IoT](#17-iot)
18. [Education](#18-education)
19. [Energy](#19-energy)
20. [Legal](#20-legal)
21. [Cross-Industry Meta-Resources](#21-cross-industry-meta-resources)

---

## 1. Music

### Formal Standards

#### DDEX (Digital Data Exchange)
- **Standard:** Electronic Release Notification (ERN), Musical Works Notification (MWN), MEAD, PIE
- **Schema format:** XSD (canonical), Protobuf (community)
- **Where:** https://ddex.net/standards/ (official), schemas embedded in OSS repos below
- **Status:** ERN v4.3+ current; all v3.x and v4.0 deprecated as of March 2025
- **Behavioral specs:** YES -- message choreographies, allowed value sets (AVS), business validation rules defined per standard

#### Best OSS Implementations

| Repository | Format | Notes |
|------------|--------|-------|
| [sshaw/ddex](https://github.com/sshaw/ddex) | XSD | Ruby gem; ships XSD files for ERN v3.3-3.7 in `/etc/schemas/ern/` |
| [OpenAudio/ddex-proto](https://github.com/OpenAudio/ddex-proto) | **Protobuf** | Go package; Protobuf definitions with XML tags for ERN v3.81-v4.32, MEAD v1.1, PIE v1.0 |
| [miqwit/dedex](https://github.com/miqwit/dedex) | PHP classes | Parser that transforms ERN into typed PHP objects; listed on official DDEX OSS page |

### MusicBrainz

- **Standard:** MusicBrainz Database Schema v30 (Q2 2025) + REST/JSON API
- **Schema format:** SQL DDL (canonical), TypeScript types (community)
- **Where:** https://musicbrainz.org/doc/MusicBrainz_Database/Schema
- **Behavioral specs:** YES -- extensive editing guidelines, entity relationships, merge/redirect rules

| Repository | Format | Notes |
|------------|--------|-------|
| [metabrainz/musicbrainz-server](https://github.com/metabrainz/musicbrainz-server) | SQL DDL, Perl | Canonical schema; `/admin/sql/` contains all DDL |
| [Borewit/musicbrainz-api](https://github.com/Borewit/musicbrainz-api) | **TypeScript** | Fully typed TS client with built-in type definitions for all MusicBrainz entities |

---

## 2. Healthcare

### HL7 FHIR (Fast Healthcare Interoperability Resources)

- **Standard:** FHIR R4, R4B, R5
- **Schema format:** JSON Schema, StructureDefinition (FHIR-native), XSD, TypeScript (generated), Python (Pydantic)
- **Where:** https://hl7.org/fhir/ (official spec), schemas in repos below
- **Behavioral specs:** YES -- SearchParameters, CapabilityStatements, OperationDefinitions, invariants (FHIRPath expressions), state machines for workflow resources (Task, MedicationRequest)

| Repository | Format | Notes |
|------------|--------|-------|
| [HL7/fhir](https://github.com/HL7/fhir) | JSON Schema, XSD | Official source for the FHIR specification |
| [fhir-schema/fhir-schema](https://github.com/fhir-schema/fhir-schema) | **JSON Schema** (developer-friendly) | Simplified representation of FHIR StructureDefinitions, inspired by JSON Schema design |
| [fhir-schema/fhir-schema-codegen](https://github.com/fhir-schema/fhir-schema-codegen) | TypeScript, C#, Python generators | Generates strongly-typed code from FHIR schemas |
| [nazrulworld/fhir.resources](https://github.com/nazrulworld/fhir.resources) | **Python Pydantic** | FHIR resources as Pydantic classes with built-in validation; supports R4, R4B, R5 |
| [microsoft/fhir-server](https://github.com/microsoft/fhir-server) | C# | Full FHIR server implementation |

### DICOM

- **Standard:** DICOM (medical imaging)
- **Schema format:** JSON (parsed from HTML), Protobuf (community)
- **Where:** https://www.dicomstandard.org/
- **Behavioral specs:** YES -- Service-Object Pair (SOP) classes, DIMSE services, IOD modules, conformance statements

| Repository | Format | Notes |
|------------|--------|-------|
| [innolitics/dicom-standard](https://github.com/innolitics/dicom-standard) | **JSON** | Complete DICOM standard parsed into JSON; auto-regenerated monthly via GitHub Actions |
| [gradienthealth/dicom-protos](https://github.com/gradienthealth/dicom-protos) | **Protobuf** | Generated protobuf representations of every DICOM attribute and module |

---

## 3. Finance / Banking

### FIX Protocol

- **Standard:** FIX (Financial Information eXchange) -- FIX Orchestra (machine-readable rules of engagement)
- **Schema format:** XML/XSD (Orchestra repository format), Protobuf/Avro (generated)
- **Where:** https://www.fixtrading.org/standards/
- **Behavioral specs:** YES -- FIX Orchestra encodes message workflows, validation rules, state machines, and conditional logic as machine-readable XML

| Repository | Format | Notes |
|------------|--------|-------|
| [FIXTradingCommunity/fix-orchestra](https://github.com/FIXTradingCommunity/fix-orchestra) | **XML (Orchestra)** | Machine-readable rules of engagement; canonical source |
| [FIXTradingCommunity/fix-orchestra-quickfix](https://github.com/FIXTradingCommunity/fix-orchestra-quickfix) | Java | Generates QuickFIX data dictionaries from Orchestra; tools for Avro + Protobuf conversion |
| [quickfix-j](https://github.com/quickfix-j) | Java | QuickFIX/J -- generates type-safe Java message/field classes from Orchestra specs |
| [fix8/fix8](https://github.com/fix8/fix8) | C++ | Modern C++ FIX framework with complete schema customization |

### ISO 20022

- **Standard:** ISO 20022 financial messaging (payments, securities, trade finance)
- **Schema format:** XSD (canonical), JSON Schema (Draft 2020-12), Go structs
- **Where:** https://www.iso20022.org/iso-20022-message-definitions
- **Behavioral specs:** YES -- message definitions include business process models (UML activity diagrams), message choreographies, and validation rules

| Repository | Format | Notes |
|------------|--------|-------|
| [moov-io/iso20022](https://github.com/moov-io/iso20022) | **Go structs** | Reader/writer with HTTP API for creating, parsing, validating ISO 20022 messages |
| [issettled/iso20022-issettled](https://github.com/issettled/iso20022-issettled) | **XSD, XML templates** | Financial XML message templates, schemas, sample messages, UML diagrams |

### Open Banking

- **Standard:** Open Banking UK (Read/Write API), Mastercard Open Banking (US), PSD2
- **Schema format:** **OpenAPI 3.x** (canonical)
- **Where:** https://standards.openbanking.org.uk/api-specifications/
- **Behavioral specs:** YES -- consent lifecycle, payment initiation flows, strong customer authentication (SCA) requirements

| Repository | Format | Notes |
|------------|--------|-------|
| [OpenBankingUK/read-write-api-specs](https://github.com/OpenBankingUK/read-write-api-specs) | **OpenAPI** | Canonical R/W API specifications; actively updated (Nov 2025) |
| [Mastercard/open-banking-us-openapi](https://github.com/Mastercard/open-banking-us-openapi) | **OpenAPI** | US Open Banking specs with generated test suites |
| [OpenBankProject/OBP-API](https://github.com/OpenBankProject/OBP-API) | Scala/REST | Open-source RESTful API platform supporting Open Banking, PSD2, XS2A |

---

## 4. Payments

### Stripe

- **Schema format:** **OpenAPI 3.0** (canonical)
- **Where:** https://github.com/stripe/openapi
- **Behavioral specs:** YES -- webhook event types, payment intent state machine, idempotency rules documented; vendor extensions (x-expandableFields, x-stripeBypassValidation) encode business rules

| Repository | Format | Notes |
|------------|--------|-------|
| [stripe/openapi](https://github.com/stripe/openapi) | **OpenAPI 3.0** (JSON + YAML) | Canonical spec; `spec3.sdk.json` includes annotations for SDK generation |

### Square

- **Schema format:** **OpenAPI** (canonical)
- **Where:** https://github.com/square/connect-api-specification
- **Behavioral specs:** YES -- payment flow state machines, webhook catalog documented

| Repository | Format | Notes |
|------------|--------|-------|
| [square/connect-api-specification](https://github.com/square/connect-api-specification) | **OpenAPI** (JSON) | Canonical `api.json`; used for SDK generation via Swagger Codegen |

### Adyen

- **Schema format:** **OpenAPI 3.1** (canonical)
- **Where:** https://github.com/Adyen/adyen-openapi
- **Behavioral specs:** YES -- payment lifecycle, recurring payment flows; custom vendor extensions for API grouping

| Repository | Format | Notes |
|------------|--------|-------|
| [Adyen/adyen-openapi](https://github.com/Adyen/adyen-openapi) | **OpenAPI 3.1** (JSON + YAML) | Generates services, models, docs, and code snippets; GA within 2 weeks of platform releases |

---

## 5. E-commerce

### Shopify

- **Schema format:** **GraphQL SDL** (canonical)
- **Where:** https://shopify.dev/docs/api/admin-graphql/latest
- **Behavioral specs:** YES -- order lifecycle, fulfillment state machine, inventory rules, Shopify Functions (discount/shipping/payment customization) with typed input/output schemas

| Repository | Format | Notes |
|------------|--------|-------|
| [Shopify/graphql-js-schema](https://github.com/Shopify/graphql-js-schema) | **GraphQL -> ES6 type modules** | Transforms GraphQL JSON schema into typed JS modules |
| [Shopify/function-examples](https://github.com/Shopify/function-examples) | **GraphQL SDL** | Typed input/output schemas for Shopify Functions (e.g., `schema.graphql` for cart transforms) |

**Note:** As of April 2025, all new Shopify App Store apps must use GraphQL (REST deprecated).

### Medusa

- **Schema format:** **OpenAPI** (OAS), TypeScript types
- **Where:** https://docs.medusajs.com/api/admin
- **Behavioral specs:** YES -- cart/order workflows, payment/fulfillment providers lifecycle, event-driven architecture

| Repository | Format | Notes |
|------------|--------|-------|
| [medusajs/medusa](https://github.com/medusajs/medusa) | **OpenAPI + TypeScript** | OAS files + CLI for generating TypeScript client types (`@medusajs/client-types`) |

### Saleor

- **Schema format:** **GraphQL SDL** (canonical)
- **Where:** https://docs.saleor.io/api-reference/
- **Behavioral specs:** YES -- checkout flow, payment gateway integration, webhook event subscriptions

| Repository | Format | Notes |
|------------|--------|-------|
| [saleor/saleor](https://github.com/saleor/saleor) | **GraphQL SDL** | `saleor/graphql/schema.graphql` -- complete commerce schema |
| [saleor/saleor-sdk](https://github.com/saleor/saleor-sdk) | TypeScript + GraphQL | JS/TS SDK with typed GraphQL operations |

---

## 6. Identity / Auth

### SCIM (System for Cross-domain Identity Management)

- **Standard:** SCIM 2.0 (RFC 7643 Core Schema, RFC 7644 Protocol)
- **Schema format:** JSON (canonical, self-describing via `/Schemas` endpoint)
- **Where:** https://datatracker.ietf.org/doc/html/rfc7643
- **Behavioral specs:** YES -- CRUD operations, filtering (SCIM filter syntax), bulk operations, patch semantics, attribute mutability/returnability rules

| Repository | Format | Notes |
|------------|--------|-------|
| RFC 7643/7644 | **JSON** | Schema is self-describing; attribute metadata includes cardinality, mutability, uniqueness, case-exactness |

### OpenID Connect

- **Standard:** OpenID Connect Core 1.0, Discovery, Dynamic Registration
- **Schema format:** JSON (JWT claims, Discovery document), JSON Schema (OIDC4IDA)
- **Where:** https://openid.net/specs/
- **Behavioral specs:** YES -- authorization code flow, implicit flow, hybrid flow, token lifecycle, consent

### Keycloak

- **Schema format:** **OpenAPI** (auto-generated from Keycloak 23+)
- **Where:** Auto-generated from Keycloak source; community extracts below
- **Behavioral specs:** YES -- realm configuration, authentication flows, client scopes, user federation

| Repository | Format | Notes |
|------------|--------|-------|
| [ccouzens/keycloak-openapi](https://github.com/ccouzens/keycloak-openapi) | **OpenAPI** (JSON) | Admin API specs for multiple Keycloak versions; generated from HTML docs |
| [dahag-ag/keycloak-openapi](https://github.com/dahag-ag/keycloak-openapi) | **OpenAPI** | Alternative extraction; Keycloak 23+ generates natively |

### Ory (Kratos + Hydra)

- **Schema format:** **OpenAPI 3.x** (canonical, ships with source)
- **Where:** In-repo at `.schema/openapi.json` and `.schema/api.openapi.json`
- **Behavioral specs:** YES -- identity lifecycle (registration, login, recovery, verification), OAuth2 consent flow, session management

| Repository | Format | Notes |
|------------|--------|-------|
| [ory/kratos](https://github.com/ory/kratos) | **OpenAPI 3.x** | `.schema/openapi.json` -- identity management; Go source with generated clients |
| [ory/hydra](https://github.com/ory/hydra) | **OpenAPI 3.x** | OAuth2/OIDC provider; certified OpenID Connect |

---

## 7. Travel

### OpenTravel Alliance (OTA)

- **Standard:** OpenTravel XML Message Suite, OTM (OpenTravel Model)
- **Schema format:** XSD (canonical), OTM model files (compiled to XSD + WSDL + Swagger)
- **Where:** https://github.com/OpenTravel
- **Behavioral specs:** YES -- message choreographies, booking workflows, cancellation policies

| Repository | Format | Notes |
|------------|--------|-------|
| [OpenTravel/OTM-DE-Compiler](https://github.com/OpenTravel/OTM-DE-Compiler) | OTM -> **XSD, WSDL, Swagger** | Compiler that transforms OTM models into schemas and web service interfaces |
| [OpenTravel/OTM-DE](https://github.com/OpenTravel/OTM-DE) | OTM model files | Eclipse-based IDE for designing information models (maintenance mode; DEX is current) |

### IATA NDC (New Distribution Capability)

- **Standard:** NDC, ONE Order
- **Schema format:** XSD (canonical), JSON (emerging)
- **Where:** https://developer.iata.org/en/ndc/
- **Behavioral specs:** YES -- offer/order lifecycle, shopping, booking, servicing workflows

| Repository | Format | Notes |
|------------|--------|-------|
| [open-ndc](https://github.com/open-ndc) | XSD, SDKs (Python, Ruby, Elixir) | Open-source NDC sandbox and SDKs; 11 repositories |

### Amadeus

- **Schema format:** **OpenAPI 3.0** (canonical)
- **Where:** https://github.com/amadeus4dev/amadeus-open-api-specification
- **Behavioral specs:** YES -- flight booking, hotel reservation, transfer workflows; GitHub Actions validates contract compliance

| Repository | Format | Notes |
|------------|--------|-------|
| [amadeus4dev/amadeus-open-api-specification](https://github.com/amadeus4dev/amadeus-open-api-specification) | **OpenAPI 3.0** | Central source of truth for Amadeus Self-Service APIs; auto-generates SDKs |

---

## 8. Logistics / Supply Chain

### GS1 EPCIS (Electronic Product Code Information Services)

- **Standard:** EPCIS 2.0 / CBV (Core Business Vocabulary) 2.0
- **Schema format:** JSON Schema, JSON-LD, XSD, RDF SHACL shapes
- **Where:** https://ref.gs1.org/docs/epcis/examples
- **Behavioral specs:** YES -- event types (ObjectEvent, AggregationEvent, TransactionEvent, TransformationEvent), business steps, dispositions, EPCIS query interface

| Repository | Format | Notes |
|------------|--------|-------|
| [gs1/EPCIS](https://github.com/gs1/EPCIS) | **JSON Schema**, XSD | Official GS1 repo; `EPCIS-JSON-Schema.json` is the key file |
| [openepcis](https://github.com/openepcis) | Java, JSON/JSON-LD | Fully open-source GS1-compliant EPCIS 2.0 implementation; includes document converter (XML <-> JSON-LD) |

---

## 9. Insurance

### ACORD

- **Standard:** ACORD XML Standards (P&C, Life & Annuity, Reinsurance)
- **Schema format:** XSD (canonical)
- **Where:** https://www.acord.org/standards-architecture/acord-data-standards (member access required for full schemas)
- **Behavioral specs:** YES -- NDR (Naming and Design Rules) specifies XML architectural functionality, naming conventions, data types; business process models

| Repository | Format | Notes |
|------------|--------|-------|
| [jasonjanofsky/Acord60Mins](https://github.com/jasonjanofsky/Acord60Mins) | XSD (TXLife2.36.00.xsd) | ACORD Life Insurance Standard integration starter; rendered XSD.exe schema |

**Note:** ACORD schemas are primarily available through membership. Limited public availability on GitHub. The XSD files that do exist on GitHub are older versions. For eclusa starter pack, this is LOW extractability unless member access is obtained.

---

## 10. Real Estate

### RESO (Real Estate Standards Organization)

- **Standard:** RESO Data Dictionary 2.x, RESO Web API, RESO Common Format
- **Schema format:** JSON Schema (generated from Data Dictionary), OData metadata
- **Where:** https://www.reso.org/reso-web-api/ and https://github.com/resostandards
- **Behavioral specs:** YES -- field validation rules (type matching, synonym detection), certification test plans, data dictionary versioning

| Repository | Format | Notes |
|------------|--------|-------|
| [RESOStandards/transport](https://github.com/RESOStandards/transport) | **JSON Schema**, OData | Web API Core spec + RESO Common Format proposal |
| [arcticleo/reso](https://github.com/arcticleo/reso) | Ruby | Implementation of RESO Data Dictionary |

---

## 11. Telecommunications

### TM Forum Open APIs

- **Standard:** TM Forum Open Digital Architecture (ODA) APIs -- 56+ REST APIs
- **Schema format:** **OpenAPI 3.0** (canonical), **JSON Schema** (entity definitions)
- **Where:** https://www.tmforum.org/oda/open-apis/
- **Behavioral specs:** YES -- lifecycle management, SLA management, trouble ticket workflows, order management state machines; each API has a conformance profile

| Repository | Format | Notes |
|------------|--------|-------|
| [tmforum-apis/Open_Api_And_Data_Model](https://github.com/tmforum-apis/Open_Api_And_Data_Model) | **OpenAPI 3.0** | Comprehensive collection; TMF620 (Product Catalog), TMF622 (Product Ordering), TMF641 (Service Ordering), etc. |
| [tmforum-rand/schemas](https://github.com/tmforum-rand/schemas) | **JSON Schema** | Entity definitions organized by TMF API number |

**License:** Apache 2.0. 94 repositories available. Applicable beyond telecom -- IoT, healthcare, energy.

---

## 12. Cloud / Infrastructure

### Terraform

- **Schema format:** JSON Schema (Provider Code Spec), Go structs (terraform-json)
- **Where:** https://developer.hashicorp.com/terraform/plugin/code-generation/specification
- **Behavioral specs:** YES -- resource lifecycle (Create, Read, Update, Delete), plan/apply semantics, state management

| Repository | Format | Notes |
|------------|--------|-------|
| [hashicorp/terraform-json](https://github.com/hashicorp/terraform-json) | **Go structs** | Helper types for `terraform show -json` and `terraform providers schema -json` output |
| [hashicorp/terraform-plugin-codegen-spec](https://github.com/hashicorp/terraform-plugin-codegen-spec) | **JSON Schema** | Provider Code Generation Specification; IR (intermediate representation) |
| [hashicorp/terraform-plugin-codegen-openapi](https://github.com/hashicorp/terraform-plugin-codegen-openapi) | OpenAPI -> IR | Transforms OpenAPI specs into Terraform provider code specs |

### Kubernetes

- **Schema format:** **OpenAPI v2/v3** (canonical), Go structs, JSON Schema (derived)
- **Where:** https://github.com/kubernetes/kubernetes/blob/master/api/openapi-spec/swagger.json
- **Behavioral specs:** YES -- controller reconciliation loops, admission webhooks, resource lifecycle, CRD structural schemas with CEL validation (Kubernetes 1.35+: validation ratcheting)

| Repository | Format | Notes |
|------------|--------|-------|
| [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) | **OpenAPI** (`api/openapi-spec/swagger.json`) | Complete K8s API as OpenAPI |
| [kubernetes/api](https://github.com/kubernetes/api) | **Go structs** | Canonical location of all K8s API type definitions (`core/v1/types.go`, etc.) |
| [kubernetes/client-go](https://github.com/kubernetes/client-go) | **Go** (typed clients) | Pre-generated typed client for every core resource type |

### CloudEvents

- **Standard:** CloudEvents 1.0 (CNCF graduated project)
- **Schema format:** **JSON Schema**, **Protobuf**, JSON, Avro
- **Where:** https://github.com/cloudevents/spec
- **Behavioral specs:** YES -- event envelope structure, required/optional attributes, protocol bindings (HTTP, AMQP, Kafka, NATS, MQTT), content type negotiation

| Repository | Format | Notes |
|------------|--------|-------|
| [cloudevents/spec](https://github.com/cloudevents/spec) | **JSON Schema, Protobuf** | Core CloudEvents specification |
| [googleapis/google-cloudevents](https://github.com/googleapis/google-cloudevents) | **Protobuf** (source of truth), JSON Schema (generated) | Google's CloudEvent types; machine-readable JSON Schema catalog |

---

## 13. Messaging / Communication

### Twilio

- **Schema format:** **OpenAPI 3.0** (canonical)
- **Where:** https://github.com/twilio/twilio-oai
- **Behavioral specs:** YES -- message delivery states, call lifecycle, webhook signatures

| Repository | Format | Notes |
|------------|--------|-------|
| [twilio/twilio-oai](https://github.com/twilio/twilio-oai) | **OpenAPI 3.0** (JSON + YAML) | GA status; covers all Twilio APIs; generates all official SDKs |
| [twilio/twilio-oai-generator](https://github.com/twilio/twilio-oai-generator) | Mustache templates | Client library generator from Twilio's OpenAPI specs |

### SendGrid

- **Schema format:** **OpenAPI** (JSON + YAML)
- **Where:** https://github.com/twilio/sendgrid-oai
- **Behavioral specs:** YES -- email delivery pipeline, event webhook types, suppression management

| Repository | Format | Notes |
|------------|--------|-------|
| [twilio/sendgrid-oai](https://github.com/twilio/sendgrid-oai) | **OpenAPI** | Beta; spec in `json/` and `yaml/` directories |

### Resend

- **Schema format:** **OpenAPI** (canonical)
- **Where:** https://github.com/resend/resend-openapi
- **Behavioral specs:** LIMITED -- email sending, domain verification, webhook events

| Repository | Format | Notes |
|------------|--------|-------|
| [resend/resend-openapi](https://github.com/resend/resend-openapi) | **OpenAPI** | Enables typed SDK generation (e.g., Rust, TypeScript) |

### Slack

- **Schema format:** **OpenAPI 2.0** (Web API), **AsyncAPI 1.0** (Events API)
- **Where:** https://github.com/slackapi/slack-api-specs
- **Behavioral specs:** YES -- interactive message flows, event subscriptions, socket mode lifecycle

| Repository | Format | Notes |
|------------|--------|-------|
| [slackapi/slack-api-specs](https://github.com/slackapi/slack-api-specs) | **OpenAPI 2.0, AsyncAPI** | Web API + Events API specs |

### Discord

- **Schema format:** **OpenAPI 3.1** (canonical, auto-generated)
- **Where:** https://github.com/discord/discord-api-spec
- **Behavioral specs:** YES -- gateway lifecycle, interaction response types, rate limiting; custom extension `x-discord-union: oneOf`

| Repository | Format | Notes |
|------------|--------|-------|
| [discord/discord-api-spec](https://github.com/discord/discord-api-spec) | **OpenAPI 3.1** | Preview; auto-generated from internal definitions |

### AsyncAPI (cross-cutting)

- **Standard:** AsyncAPI 3.0 (event-driven API specification)
- **Schema format:** **JSON Schema** (specification schema), YAML (document format)
- **Where:** https://github.com/asyncapi/spec
- **Behavioral specs:** YES -- channel bindings, operation bindings, message correlation, server bindings for MQTT/Kafka/AMQP/WebSocket

| Repository | Format | Notes |
|------------|--------|-------|
| [asyncapi/spec](https://github.com/asyncapi/spec) | **JSON Schema** | Specification for describing async APIs |
| [asyncapi/spec-json-schemas](https://github.com/asyncapi/spec-json-schemas) | **JSON Schema** | Validation schemas for all AsyncAPI versions |

---

## 14. Analytics / Observability

### OpenTelemetry

- **Standard:** OTLP (OpenTelemetry Protocol)
- **Schema format:** **Protobuf** (canonical)
- **Where:** https://github.com/open-telemetry/opentelemetry-proto
- **Behavioral specs:** YES -- trace/metric/log data model, sampling semantics, resource semantic conventions, span status codes, metric aggregation temporality

| Repository | Format | Notes |
|------------|--------|-------|
| [open-telemetry/opentelemetry-proto](https://github.com/open-telemetry/opentelemetry-proto) | **Protobuf** | Canonical OTLP protocol + data model; traces, metrics, logs, profiles |

### Prometheus / OpenMetrics

- **Standard:** OpenMetrics (evolved from Prometheus exposition format)
- **Schema format:** **Protobuf** (proto3), text exposition format
- **Where:** https://github.com/prometheus/OpenMetrics
- **Behavioral specs:** YES -- metric types (counter, gauge, histogram, summary), exposition rules, label naming conventions, staleness handling

| Repository | Format | Notes |
|------------|--------|-------|
| [prometheus/OpenMetrics](https://github.com/prometheus/OpenMetrics) | **Protobuf**, text spec | OpenMetrics specification + proto schema |
| [prometheus/client_model](https://github.com/prometheus/client_model) | **Protobuf** | Data model + exposition format for Prometheus metrics |

---

## 15. CRM / Sales

### HubSpot

- **Schema format:** **OpenAPI 3.0** (canonical)
- **Where:** https://github.com/HubSpot/HubSpot-public-api-spec-collection + `https://api.hubspot.com/api-catalog-public/v1/apis`
- **Behavioral specs:** YES -- contact/deal lifecycle stages, workflow automation triggers, association types

| Repository | Format | Notes |
|------------|--------|-------|
| [HubSpot/HubSpot-public-api-spec-collection](https://github.com/HubSpot/HubSpot-public-api-spec-collection) | **OpenAPI 3.0** | Official but labeled "for internal use" (Postman integration); specs are public |
| [clarkmcc/go-hubspot](https://github.com/clarkmcc/go-hubspot) | Go (generated) | Fully typed Go client generated from HubSpot's OpenAPI specs |

### Salesforce

- **Schema format:** XSD (Metadata API), WSDL (SOAP), REST/JSON (described but not formally OpenAPI)
- **Where:** https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_types_list.htm
- **Behavioral specs:** YES -- record lifecycle, approval processes, trigger order-of-execution, sharing rules

| Repository | Format | Notes |
|------------|--------|-------|
| [forcedotcom/idecore](https://github.com/forcedotcom/idecore) | **XSD** (`metadata.xsd`) | Salesforce Metadata API schema |
| [jongpie/SimpleMetadata](https://github.com/jongpie/SimpleMetadata) | Apex classes | Lightweight metadata access for frontend/backend developers |

**Note:** Salesforce does not publish a comprehensive public OpenAPI spec. The XSD/WSDL files are the most extractable typed schemas available.

---

## 16. DevOps / CI

### GitHub Actions

- **Schema format:** **JSON Schema** (Draft-07)
- **Where:** https://github.com/SchemaStore/schemastore/blob/master/src/schemas/json/github-workflow.json
- **Behavioral specs:** YES -- job dependency DAG, matrix strategy expansion, conditional execution (`if` expressions), concurrency groups, environment protection rules

| Repository | Format | Notes |
|------------|--------|-------|
| [SchemaStore/schemastore](https://github.com/SchemaStore/schemastore) | **JSON Schema** | `github-workflow.json` + `github-action.json`; serves >1TB of schemas daily |
| [github/rest-api-description](https://github.com/github/rest-api-description) | **OpenAPI 3.0/3.1** | GitHub's complete REST API as OpenAPI; includes Actions API |

### GitLab CI

- **Schema format:** **JSON Schema** (Draft-07)
- **Where:** Within GitLab source (used by pipeline editor + Monaco YAML plugin)
- **Behavioral specs:** YES -- stage ordering, DAG dependencies, rules/workflow evaluation, include resolution, artifact passing

**Note:** GitLab's CI schema lives within the GitLab monorepo and is used for frontend validation. It follows JSON Schema Draft-07. The CI Lint API provides runtime validation.

### SchemaStore (meta-resource for DevOps)

The [SchemaStore](https://github.com/SchemaStore/schemastore) project is the world's largest collection of JSON schemas, including schemas for: `github-workflow`, `github-action`, `gitlab-ci`, `azure-pipelines`, `bitbucket-pipelines`, `circleci`, `travis`, `docker-compose`, `Dockerfile`, `kubernetes`, `helm`, `kustomization`, and hundreds more.

---

## 17. IoT

### Matter (formerly Project CHIP)

- **Standard:** Matter 1.5 (Nov 2025) -- unified smart home protocol
- **Schema format:** **TypeScript** (typed cluster definitions), C++ (reference), IDL (data model)
- **Where:** https://github.com/project-chip/connectedhomeip
- **Behavioral specs:** YES -- device type definitions, cluster specifications (OnOff, LevelControl, DoorLock, etc.), commissioning flow, secure channel establishment

| Repository | Format | Notes |
|------------|--------|-------|
| [project-chip/connectedhomeip](https://github.com/project-chip/connectedhomeip) | C++, IDL | Reference implementation; Apache 2.0 |
| [project-chip/matter.js](https://github.com/project-chip/matter.js) | **TypeScript** | Complete TS implementation with full typed support for device types, cluster definitions; extensive typing facilitates schema extraction |

### OPC UA (Unified Architecture)

- **Standard:** OPC UA (IEC 62541) -- industrial interoperability
- **Schema format:** XML (NodeSet2 information models), JSON (OPC UA PubSub), Binary
- **Where:** https://github.com/OPCFoundation
- **Behavioral specs:** YES -- information model inheritance, method calls, subscription/monitoring, security policies, session lifecycle

| Repository | Format | Notes |
|------------|--------|-------|
| [OPCFoundation (GitHub org)](https://github.com/OPCFoundation) | XML NodeSet2, C#, Java, C | Official reference implementations and information models |
| [OPCFoundation/UA-EdgeTranslator](https://github.com/OPCFoundation/UA-EdgeTranslator) | JSON-LD (W3C WoT Thing Description) | Translates proprietary interfaces to OPC UA using WoT TD schema |

---

## 18. Education

### xAPI (Experience API)

- **Standard:** xAPI 2.0 (IEEE 9274.1.1)
- **Schema format:** **JSON** (canonical), JSON-LD (profiles), JSON Schema (validation)
- **Where:** https://github.com/adlnet/xAPI-Spec
- **Behavioral specs:** YES -- statement structure (Actor-Verb-Object-Result-Context), LRS (Learning Record Store) conformance requirements, voiding semantics, statement immutability

| Repository | Format | Notes |
|------------|--------|-------|
| [adlnet/xAPI-Spec](https://github.com/adlnet/xAPI-Spec) | **JSON** | Canonical spec; `xAPI-Data.md` defines the complete data model |
| [yetanalytics/xapi-schema](https://github.com/yetanalytics/xapi-schema) | **Clojure(Script) schema** | Programmatic schema for Experience API validation |

### IMS Caliper Analytics

- **Standard:** Caliper Analytics 1.2 (1EdTech)
- **Schema format:** **JSON-LD** (canonical)
- **Where:** https://github.com/1EdTech/caliper-spec
- **Behavioral specs:** YES -- metric profiles (Assessment, Session, Grading, Reading, etc.), sensor API for event marshalling, entity/event lifecycle

| Repository | Format | Notes |
|------------|--------|-------|
| [1EdTech/caliper-spec](https://github.com/1EdTech/caliper-spec) | **JSON-LD** | Spec defines events + entities using JSON-LD; Caliper 1.2 current |

---

## 19. Energy

### OpenADR (Open Automated Demand Response)

- **Standard:** OpenADR 2.0b (XSD/SOAP), OpenADR 3.0/3.1 (REST/JSON)
- **Schema format:** XSD (2.0b), **OpenAPI/JSON** (3.x)
- **Where:** https://www.openadr.org/specification-download
- **Behavioral specs:** YES -- demand response event lifecycle, VTN/VEN communication patterns, opt-in/opt-out semantics, report creation

| Repository | Format | Notes |
|------------|--------|-------|
| [clean-energy-tools/openadr-3-ts-types](https://github.com/clean-energy-tools/openadr-3-ts-types) | **TypeScript types** | TS type declarations + Zod validation for OpenADR v3 |
| [OpenLEADR/openleadr-rs](https://github.com/OpenLEADR/openleadr-rs) | **Rust** | OpenADR 3.1 VTN/VEN implementation; LF Energy project |
| [OpenLEADR/openleadr-python](https://github.com/OpenLEADR/openleadr-python) | Python | OpenADR 2.0b implementation |

### CIM (Common Information Model for Power Systems)

- **Standard:** IEC 61970/61968 CIM, CGMES (Common Grid Model Exchange Standard)
- **Schema format:** UML (canonical), RDF/XML (profiles), XSD (derived)
- **Where:** https://www.entsoe.eu/digital/common-information-model/
- **Behavioral specs:** YES -- power flow modeling, topology processing, equipment lifecycle

| Repository | Format | Notes |
|------------|--------|-------|
| [smart-data-models/dataModel.EnergyCIM](https://github.com/smart-data-models/dataModel.EnergyCIM) | **JSON Schema** (NGSI-LD adapted) | CIM data models adapted from IEC 61970; Smart Data Models initiative |
| [GRIDAPPSD/Powergrid-Models](https://github.com/GRIDAPPSD/Powergrid-Models) | CIM/RDF | CIM interfaces for power grid simulation (GridLAB-D, OpenDSS) |

---

## 20. Legal

### Akoma Ntoso / LegalDocML

- **Standard:** Akoma Ntoso 3.0 (OASIS LegalDocML TC), ratified 2018-2019
- **Schema format:** **XSD** (canonical)
- **Where:** https://github.com/oasis-open/legaldocml-akomantoso
- **Behavioral specs:** YES -- document lifecycle (draft, enacted, consolidated), temporal versioning, amendment tracking, cross-reference resolution

| Repository | Format | Notes |
|------------|--------|-------|
| [oasis-open/legaldocml-akomantoso](https://github.com/oasis-open/legaldocml-akomantoso) | **XSD** | Official OASIS TC Open Repository; schema files + examples + documentation |
| [bungenix/akomantoso-lib](https://github.com/bungenix/akomantoso-lib) | Java API | Java API for the Akoma Ntoso XML Schema |

---

## 21. Cross-Industry Meta-Resources

These repositories aggregate schemas across industries and are valuable for the eclusa starter pack as one-stop sources.

### APIs-guru/openapi-directory

- **What:** "Wikipedia for Web APIs" -- 2700+ REST API definitions in OpenAPI 2.0/3.x
- **Where:** https://github.com/APIs-guru/openapi-directory
- **License:** CC0 1.0 (author-contributed), Fair Use (public sources)
- **Extractability:** HIGH -- every API is a ready-to-consume OpenAPI spec

### SchemaStore

- **What:** World's largest collection of JSON schemas (600+ schemas)
- **Where:** https://github.com/SchemaStore/schemastore
- **Serves:** >1TB of schemas daily
- **Includes:** CI/CD configs, package managers, config files, linters, bundlers, cloud services
- **Extractability:** HIGH -- each schema is standalone JSON Schema Draft-07

### AsyncAPI

- **What:** Specification for event-driven/async APIs (complement to OpenAPI for sync APIs)
- **Where:** https://github.com/asyncapi/spec
- **Extractability:** HIGH -- JSON Schema definitions for the spec itself; typed code generation tools available

---

## Summary: Schema Format Distribution by Industry

| Industry | Primary Schema Format | Extractability |
|----------|----------------------|----------------|
| Music (DDEX) | XSD, Protobuf | HIGH |
| Music (MusicBrainz) | SQL DDL, TypeScript | MEDIUM |
| Healthcare (FHIR) | JSON Schema, Pydantic, TypeScript | **VERY HIGH** |
| Healthcare (DICOM) | JSON, Protobuf | HIGH |
| Finance (FIX) | XML (Orchestra), Protobuf/Avro | HIGH |
| Finance (ISO 20022) | XSD, Go structs | HIGH |
| Finance (Open Banking) | OpenAPI | **VERY HIGH** |
| Payments (Stripe/Square/Adyen) | OpenAPI | **VERY HIGH** |
| E-commerce (Shopify/Saleor) | GraphQL SDL | HIGH |
| E-commerce (Medusa) | OpenAPI + TypeScript | **VERY HIGH** |
| Identity (SCIM) | JSON (self-describing) | HIGH |
| Identity (Ory) | OpenAPI | **VERY HIGH** |
| Identity (Keycloak) | OpenAPI | HIGH |
| Travel (Amadeus) | OpenAPI | **VERY HIGH** |
| Travel (NDC/OpenTravel) | XSD | MEDIUM |
| Logistics (GS1 EPCIS) | JSON Schema, JSON-LD | HIGH |
| Insurance (ACORD) | XSD (members only) | **LOW** |
| Real Estate (RESO) | JSON Schema, OData | MEDIUM |
| Telecom (TM Forum) | OpenAPI, JSON Schema | **VERY HIGH** |
| Cloud (Terraform) | JSON Schema, Go structs | HIGH |
| Cloud (Kubernetes) | OpenAPI, Go structs | **VERY HIGH** |
| Cloud (CloudEvents) | JSON Schema, Protobuf | **VERY HIGH** |
| Messaging (Twilio) | OpenAPI | **VERY HIGH** |
| Messaging (Slack) | OpenAPI + AsyncAPI | HIGH |
| Messaging (Discord) | OpenAPI 3.1 | HIGH |
| Observability (OTel) | Protobuf | **VERY HIGH** |
| Observability (Prometheus) | Protobuf | HIGH |
| CRM (HubSpot) | OpenAPI | HIGH |
| CRM (Salesforce) | XSD, WSDL | MEDIUM |
| DevOps (GitHub Actions) | JSON Schema | **VERY HIGH** |
| IoT (Matter) | TypeScript | HIGH |
| IoT (OPC UA) | XML NodeSet2 | MEDIUM |
| Education (xAPI) | JSON, JSON-LD | HIGH |
| Education (Caliper) | JSON-LD | MEDIUM |
| Energy (OpenADR) | TypeScript, Rust, OpenAPI | HIGH |
| Energy (CIM) | JSON Schema, RDF | MEDIUM |
| Legal (Akoma Ntoso) | XSD | HIGH |

---

## Recommended Priority for Starter Pack Extraction

Based on **extractability**, **breadth of domain modeling**, and **active maintenance**:

### Tier 1: Immediate Extraction (OpenAPI/GraphQL/Protobuf -- machine-readable, typed)

1. **Stripe** (`stripe/openapi`) -- payments domain model, gold standard OpenAPI
2. **FHIR** (`fhir-schema/fhir-schema`, `nazrulworld/fhir.resources`) -- healthcare domain model
3. **Kubernetes** (`kubernetes/api`) -- infrastructure domain model in Go structs
4. **OpenTelemetry** (`open-telemetry/opentelemetry-proto`) -- observability domain in Protobuf
5. **CloudEvents** (`cloudevents/spec`) -- event envelope standard
6. **Twilio** (`twilio/twilio-oai`) -- communications domain
7. **Saleor** (`saleor/saleor`) -- e-commerce domain in GraphQL
8. **Medusa** (`medusajs/medusa`) -- e-commerce domain in OpenAPI + TS
9. **Ory Kratos** (`ory/kratos`) -- identity domain in OpenAPI
10. **TM Forum** (`tmforum-apis/Open_Api_And_Data_Model`) -- telecom domain in OpenAPI
11. **Amadeus** (`amadeus4dev/amadeus-open-api-specification`) -- travel domain
12. **Open Banking UK** (`OpenBankingUK/read-write-api-specs`) -- banking domain
13. **Adyen** (`Adyen/adyen-openapi`) -- payments domain
14. **HubSpot** (`HubSpot/HubSpot-public-api-spec-collection`) -- CRM domain
15. **GitHub Actions** (`SchemaStore/schemastore`) -- DevOps domain

### Tier 2: High Value, Moderate Extraction Effort

16. **GS1 EPCIS** (`gs1/EPCIS`) -- supply chain (JSON Schema)
17. **DDEX** (`OpenAudio/ddex-proto`) -- music (Protobuf)
18. **FIX Orchestra** (`FIXTradingCommunity/fix-orchestra`) -- financial trading (XML)
19. **ISO 20022** (`moov-io/iso20022`) -- financial messaging (Go)
20. **Matter** (`project-chip/matter.js`) -- IoT (TypeScript)
21. **Slack** (`slackapi/slack-api-specs`) -- messaging (OpenAPI + AsyncAPI)
22. **Discord** (`discord/discord-api-spec`) -- messaging (OpenAPI 3.1)
23. **OpenADR** (`clean-energy-tools/openadr-3-ts-types`) -- energy (TypeScript)
24. **Akoma Ntoso** (`oasis-open/legaldocml-akomantoso`) -- legal (XSD)
25. **xAPI** (`adlnet/xAPI-Spec`) -- education (JSON)

### Tier 3: Useful but Limited Public Availability

26. **RESO** (`RESOStandards/transport`) -- real estate
27. **Salesforce** (`forcedotcom/idecore`) -- CRM (XSD)
28. **ACORD** -- insurance (member-gated)
29. **IATA NDC** (`open-ndc`) -- travel (XSD, limited OSS)
30. **OPC UA** (`OPCFoundation`) -- industrial IoT
31. **CIM** (`smart-data-models/dataModel.EnergyCIM`) -- energy grid

---

## Schema Format Parsing Strategy for Eclusa

For the eclusa commons to consume these schemas programmatically, the following parsers/extractors will be needed:

| Schema Format | Count | Parser/Tooling |
|---------------|-------|----------------|
| **OpenAPI 3.x** | ~15 | `@apidevtools/swagger-parser`, `openapi-typescript` |
| **Protobuf** | ~5 | `protobufjs`, `buf` CLI |
| **GraphQL SDL** | ~3 | `graphql` (reference JS parser), `@graphql-codegen/*` |
| **JSON Schema** | ~8 | `ajv`, `json-schema-to-typescript` |
| **XSD** | ~6 | `xsd2json`, or pre-converted JSON (many repos ship both) |
| **Go structs** | ~3 | AST parsing or use pre-generated OpenAPI/JSON Schema |
| **TypeScript** | ~3 | `ts-morph` for AST extraction |
| **SQL DDL** | ~1 | `sql-ddl-to-json-schema` or manual |
| **JSON-LD** | ~2 | `jsonld` library, context resolution |
