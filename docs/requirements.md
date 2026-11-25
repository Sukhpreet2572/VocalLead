# Requirement traceability

Status describes implementation, not promises. Phase 1 validation evidence is recorded in development_log.md. Later-phase numbering is a proposed roadmap.

| ID | Fortivex requirement | Proposed implementation | Responsible module | Phase | Current status | Acceptance criteria |
|---|---|---|---|---|---|---|
| F01 | Real-time streaming voice | WebRTC, LiveKit worker, STT/VAD and TTS | app/voice, app/agents | 2 | Implemented; live integration blocked by credentials | Interrupted and uninterrupted calls stream with measured latency |
| F02 | Context and persistent memory | Session history and durable customer preferences | app/memory, models | 2–3 | Planned | Returning user context is retrieved with consent |
| F03 | English, Hindi and Hinglish | Selector, multilingual STT/TTS and language prompt | app/voice | 2 | Implemented; speech quality unverified | Scripted and free-form language tests pass |
| F04 | Lead qualification | Structured extraction with deterministic score | app/intelligence | 3 | Planned | Fixture inputs produce explainable reproducible scores |
| F05 | Sentiment-aware behaviour | Evidence-based sentiment and response policy | app/intelligence | 3 | Planned | Negative sentiment prompts tested appropriate handling |
| F06 | Semantic RAG | Gemini embeddings, Chroma and metadata filters | app/rag, knowledge_base | 3 | Planned | Retrieval benchmark and grounded answers pass |
| F07 | Appointment automation | Confirm timezone/slot and idempotent Calendar write | app/tools, integrations | 4 | Planned | One confirmed request yields one event and persisted record |
| F08 | External CRM | HubSpot sync with retry/idempotency records | app/integrations | 4 | Planned | Lead updates sync once and failures are visible |
| F09 | AI call summary | Structured post-call summary with evidence | app/intelligence | 4 | Planned | Summary preserves facts and flags uncertainty |
| F10 | Business intelligence | Aggregates over actual calls/leads and Recharts | frontend/dashboard | 4 | Planned | Charts reconcile to persisted records |
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
