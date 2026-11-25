# Requirement traceability

Status describes implementation, not promises. Phase 1 validation evidence is recorded in development_log.md. Later-phase numbering is a proposed roadmap.

| ID | Fortivex requirement | Proposed implementation | Responsible module | Phase | Current status | Acceptance criteria |
|---|---|---|---|---|---|---|
| F01 | Real-time streaming voice | WebRTC, LiveKit worker, STT/VAD and TTS | app/voice, app/agents | 2 | Implemented; live integration blocked by credentials | Interrupted and uninterrupted calls stream with measured latency |
| F02 | Context and persistent memory | Bounded call context and owner-bound structured memory | app/intelligence, models | 4 | Local persistence and isolation tested; live return call unverified | Returning user context is retrieved with consent |
| F03 | English, Hindi and Hinglish | Selector, multilingual STT/TTS and language prompt | app/voice | 2 | Implemented; speech quality unverified | Scripted and free-form language tests pass |
| F04 | Lead qualification | Structured updates and deterministic inventory-based score | app/intelligence | 4 | Local 90-point example tested; Gemini extraction unverified | Fixture inputs produce explainable reproducible scores |
| F05 | Sentiment-aware behaviour | Typed Gemini adapter and phrase fallback | app/intelligence | 4 | Fallback tested; live behaviour unverified | Negative sentiment prompts tested appropriate handling |
| F06 | Semantic RAG | Gemini/local embeddings, Chroma and SQL unit filters | app/rag, knowledge_base | 3 | Implemented; genuine local semantic retrieval measured, multilingual quality limited | Retrieval benchmark and grounded answers pass |
| F07 | Appointment automation | Owner-bound local slots, proposals, confirmation, cancellation; Google adapter | app/automation | 5 | Local workflow verified; Google live operation unverified | One confirmed request yields one reservation and persisted record |
| F08 | External CRM | Local lifecycle record plus consent-gated HubSpot upsert adapter | app/automation | 5 | Local CRM verified; HubSpot live operation unverified | Lead and visit outcomes persist; external sync status is visible |
| F09 | AI call summary | Structured record-grounded summary with optional Gemini narrative | app/summaries | 6 | Local demo and mock adapter verified; live voice/LLM unverified | Summary preserves recorded facts and flags uncertainty |
| F10 | Business intelligence | Owner/date-scoped aggregates from persisted records and accessible UI charts | app/analytics, frontend | 6 | Local workflow verified; production scale unverified | Counts reconcile to persisted records |
| P01 | Functional foundation | FastAPI, React and honest status dashboard | app/api, frontend | 1 | Implemented | Live servers, health, readiness and dashboard verified |
| P02 | Configuration and security | Typed root environment, secret-safe errors, CORS | app/core | 1 | Implemented | Optional keys absent; secrets excluded; diagnostics dev-only |
| P03 | Database and migrations | SQLAlchemy/PostgreSQL, explicit SQLite, Alembic | app/database, migrations | 1 | Implemented; PostgreSQL runtime verification pending | SQLite health and migration pass; PostgreSQL verified with Docker available |
| P04 | Tests and evaluation | Pytest failure cases plus frontend checks | tests, frontend | 1+ | Foundation suite implemented | pytest, tsc, ESLint and build pass; later AI benchmarks versioned |
| D01 | Source and interview debugging | Modular source and readable boundaries | repository | 1 | Implemented | Developer can trace UI → endpoint → session |
| D02 | Architecture and technical docs | Mermaid, setup and log | docs | 1 | Implemented | Instructions reproduce foundation and distinguish future work |
| D03 | End-to-end business workflow | Voice → qualification → booking → CRM → summary | worker + monolith | 4 | Planned | Complete consented sales workflow verified against integrations |
| D04 | Business problem and solution | Real-estate enquiry and follow-up proposal | README | 1 | Documented | Problem and planned outcomes clearly stated |
| D05 | Commercial feasibility | Pilot ROI and unit economics | docs/architecture | 1 draft, final later | Planning assumptions documented | Validate conversion gains and provider-inclusive costs |
| D06 | 100,000-user scalability | Explicit concurrency and resource benchmarks | docs/architecture | 1 draft, final later | Assumptions documented | Load test 1,000 active browsers / 100 concurrent calls before claim |
| D07 | Security and privacy | Consent, access control, retention, encryption | core + deployment | 1 foundation, later hardening | Local safeguards implemented | Public pilot passes authorization/privacy review |
| D08 | Infrastructure/deployment | Development Compose, later managed services | infrastructure | 1+ | Configured; runtime verification pending | Containers build and PostgreSQL readiness passes |
| D09 | Cost analysis | Usage formula and measured pilot costs | docs/architecture | 1 draft, final later | Illustrative model documented | Verified provider rates plus actual usage measurements |
| D10 | One-page report | Phase summary with honest scope | docs/project_report | 1 draft | Documented | Final report updated after full MVP |

## Evaluation methodology

Foundation tests isolate databases under pytest temporary paths, use no paid services and test both success and database failure. Health must remain available during database failure. Provider secrets must never appear in diagnostic output. Production diagnostics must be hidden. Browser checks cover real HTTP data, manual refresh, offline recovery and responsive placeholders.

Later phases require a versioned consented/synthetic language corpus, STT accuracy and code-switching checks, interruption/latency measurements, retrieval precision, grounded-answer review, deterministic scoring fixtures, appointment collision and integration idempotency tests. Define thresholds and human review protocol before claiming AI quality. Do not score unimplemented functions as passing.

## Phase 4 traceability update

| ID | Phase 4 implementation | Verification / limitation |
|---|---|---|
| F02 | Context and persistent memory | Bounded call context and owner-bound structured memory | app/intelligence, models | 4 | Local persistence and isolation tested; live return call unverified | Returning user context is retrieved with consent |
| F04 | Lead qualification | Structured updates and deterministic inventory-based score | app/intelligence | 4 | Local 90-point example tested; Gemini extraction unverified | Fixture inputs produce explainable reproducible scores |
| F05 | Sentiment-aware behaviour | Typed Gemini adapter and phrase fallback | app/intelligence | 4 | Fallback tested; live behaviour unverified | Negative sentiment prompts tested appropriate handling |
| F06 | Gurgaon alias and exact eligible-property rank boost | Original benchmark unchanged at 0.3846 Hit Rate@K; Hindi/Hinglish weak |
| D07 | Local owner-hash access checks and no default transcript persistence | Production authentication and retention review still required |

## Phase 5 traceability update

| ID | Phase 5 implementation | Verification / limitation |
|---|---|---|
| F07 | Local availability, short-lived proposals, explicit browser confirmation, unique reservations, cancellation and Google adapter | SQLite workflow and mock adapter verified; live Google event unverified |
| F08 | Internal CRM lifecycle, consent-gated HubSpot email upsert and durable sync status | Local CRM and mock adapter verified; live HubSpot write unverified |
| D03 | Customer to qualified lead to local appointment to CRM lifecycle | API-level local flow verified; live voice and external services unverified |

## Phase 6 traceability update

| ID | Phase 6 implementation | Verification / limitation |
|---|---|---|
| F09 | Unique interaction source, typed structured summary, deterministic record snapshot, optional Gemini narrative, lifecycle hook and retry | SQLite workflow and mocked Gemini contract verified; live model and voice call unverified |
| F10 | Owner-scoped lead, interaction, appointment, property-demand and integration aggregates; History, Analytics and Overview pages | API tests and local workflow verified; browser visual QA pending |
| D03 | Lead through booking, local CRM, summary and analytics | Synthetic SQLite workflow verified; external providers unverified |
