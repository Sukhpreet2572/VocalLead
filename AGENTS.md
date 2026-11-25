# VocaLead AI repository instructions

Inspect existing code, documentation, git status and environment before editing. Preserve working functionality and unrelated files. Implement only the phase explicitly requested; never advance to a future phase automatically.

Objective: explainable, modular real-estate sales voice MVP for the Fortivex challenge. Mandatory target capabilities: streaming voice; persistent and contextual memory; English/Hindi/Hinglish; structured qualification plus deterministic scoring; sentiment-aware behaviour; semantic RAG; appointments; external CRM; call summaries; analytics. Phase 1 implements infrastructure only.

Architecture: React/Vite/TypeScript/Tailwind browser, FastAPI modular monolith, SQLAlchemy/PostgreSQL and Alembic; explicit SQLite local fallback. Future separately executable LiveKit worker with STT/VAD/Gemini/streaming TTS. Future Chroma, Calendar and HubSpot modules. Do not add microservices, Kafka, Redis, Kubernetes or LangGraph without a concrete approved requirement.

Keep code small, typed and interview-friendly. Use synchronous route functions for synchronous SQLAlchemy work. Keep business rules out of routes as they grow. Use UTC internally and zoneinfo Asia/Kolkata for customer-facing appointments. Verify official SDK compatibility before adding integrations. Install only current-phase dependencies; retain npm and Python locks.

Never commit .env, credentials, customer audio, private transcripts or provider keys. Provider secrets belong exclusively on the backend. Never print settings, database URLs, SQL exceptions or raw validation inputs. Diagnostic endpoints are development-only, expose booleans rather than secrets, and distinguish configured from verified. Use explicit CORS. No automatic database switching after connection errors.

For each phase: inspect, plan briefly, implement, test, update docs, report evidence and limitations. Run backend pytest; frontend typecheck, lint and build. Test failure paths and secret exclusion; no paid services in automated foundation tests. Keep docs/requirements.md traceability, setup, architecture and development log current. Report unverified functionality honestly. Do not push, publish or create remote repositories without explicit instruction.
