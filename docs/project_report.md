# VocaLead AI — Phase 1 project report

**Context:** Fortivex Advanced AI Project Challenge · real-estate sales · Phase 1 foundation.

**Problem.** Sales teams repeatedly capture buyer requirements, miss enquiries outside business hours and lose context between calls and CRM follow-up.

**Proposed solution.** An autonomous multilingual voice assistant will capture requirements, retrieve suitable property information, qualify enquiries and coordinate site visits, CRM updates and call insights. English, Hindi and Hinglish are target languages. These business capabilities are future work.

**Delivered foundation.** A React/Vite/TypeScript/Tailwind enterprise shell connects to versioned FastAPI health, readiness and development diagnostics. SQLAlchemy supports PostgreSQL and an explicit SQLite development choice. Pydantic Settings loads a predictable root environment. Structured logs, sanitized errors, CORS, Alembic, development Docker configuration and tests establish maintainable boundaries. The dashboard displays actual status without invented customers or sales metrics.

**Architecture.** Browser → FastAPI modular monolith → SQLAlchemy → PostgreSQL (SQLite for explicit local development). A separately executable LiveKit worker will later integrate STT/VAD, Gemini and a verified multilingual TTS provider. Chroma, Calendar and HubSpot remain planned.

**Quality and evaluation.** Backend tests cover root, health, docs, readiness failure, configuration, production diagnostics, CORS and secret exclusion. Frontend verification includes TypeScript, ESLint and production build; actual results are in development_log.md. External integration connectivity is always marked unverified in this phase. Docker/PostgreSQL execution depends on a running Docker engine.

**Feasibility and scale.** Pilot value should be measured through lead quality, follow-up coverage, visit conversion and cost per qualified lead. Capacity planning assumes 100,000 registered users, 1,000 simultaneously active browsers and 100 concurrent voice calls; these are assumptions requiring load tests. Costs depend on voice minutes, provider token rates, compute and storage, with no paid integrations required for this foundation.

**Security and next step.** Secrets stay on the backend; development diagnostics expose only configuration presence. Add authentication, consent, retention and deployment hardening before handling real customer data. Phase 2 begins only on explicit instruction after provider compatibility, credentials and voice acceptance criteria are established.
