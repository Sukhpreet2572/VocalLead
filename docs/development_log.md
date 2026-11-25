# Development log

## Phase 3 continuation

Created six fictional inventory entries, six generated brochures and three policy/FAQ documents. Migration `0002_property_knowledge` and repeatable seeding were run: six properties after both first and second seed. Added Gemini/local embedding adapters, persistent Chroma service, document ingestion CLI, strict unit-price filtering, retrieval API, voice tools and the Knowledge Base page. Actual local-model ingestion indexed 10 files and 14 chunks; repeat ingestion skipped all 10. The 15-query semantic evaluation gave Hit Rate 0.3846, Recall@K 0.30, MRR 0.2308, zero budget violations and two of two no-evidence detections. Backend: 17 tests passed, pip check passed, Alembic at 0002_property_knowledge. Frontend lint, typecheck and build passed with the existing bundle-size warning. A real API query returned three eligible 3 BHK units under INR 1.2 crore and a sourced brochure passage. Live voice use remains unverified. Phase 3 was completed locally before its separate commit.

## 2026-11-26 — Phase 2 voice implementation

Added a minimal voice session migration, local-only consented session API, LiveKit room-scoped tokens and explicit worker dispatch, a separate Python AgentServer worker with Deepgram Nova-3, Gemini 2.5 Flash, ElevenLabs multilingual TTS and Silero VAD, and a React Live Voice Agent page with microphone permission, LiveKit audio, activity state and text stream transcription. Within-call context and interruptions use AgentSession. No transcript or raw audio storage was added. The frontend retains Phase 1 pages.

Installed matching LiveKit Python 1.4.6 Agents/Deepgram/Google/ElevenLabs/Silero plugins and livekit-api 1.2.3, plus @livekit/components-react 2.9.26, components-styles 1.2.0 and livekit-client 2.25.0; exact versions are in lockfiles. SDK signatures and worker CLI commands were inspected locally; `download-files` completed successfully. The backend suite passed 13 tests, including mocked voice token/session tests, Alembic reached `0001_voice_sessions`, and `pip check` passed. Frontend lint, TypeScript and production build passed; Vite reported a >500 kB bundle size warning. Real voice integration, English/Hindi/Hinglish accuracy, barge-in, latency and browser playback remain unverified because all provider credentials are absent. Docker and browser visual QA remain unverified. Further details and manual steps are in setup.md.

## 2026-11-26 (Asia/Kolkata) — Phase 1 foundation

**Status:** Phase 1 implementation complete; local API/SQLite and frontend checks verified. Browser visual QA and Docker/PostgreSQL runtime verification are explicitly blocked. Phase 2 has not been started. No remote repository, publication or paid service was created.

### Environment inspected

- Empty project workspace on Windows 11 (NT 10.0.26300), Windows PowerShell 5.1.
- Python launcher and WindowsApps aliases did not resolve an installed interpreter. Found and used Python 3.11.9 under `%LOCALAPPDATA%/Programs/Python/Python311/python.exe`.
- Node 23.1.0, npm 10.9.0, Git 2.47.0.windows.2, Docker 28.5.1 and Compose v2.40.3 were present.
- Docker engine was unavailable even outside sandbox: the Docker Desktop Linux engine named pipe did not exist. No Docker installation or system reconfiguration was attempted.
- An unrelated `Microsoft/` directory appeared during environment inspection; it was preserved and ignored.
- Host process inherited `DEBUG=release`. Boolean settings correctly rejected this; shell-local `DEBUG=false` resolves it, and tests isolate inherited app settings.

### Implementation decisions

- Keep the repository directly in the supplied VocalLead workspace.
- FastAPI application factory/lifespan; app-scoped engine, request-scoped sessions, sync database routes, explicit CORS, sanitized exception handling and JSON application logs.
- Root .env resolved from config.py location; process environment wins; secret fields masked; raw validation inputs hidden. Optional integration values remain empty.
- Explicit SQLite development configuration, no automatic database switching. PostgreSQL target with psycopg, bounded connection timeout and pool pre-ping. Alembic configured without premature business entities.
- React hash navigation avoids an extra routing library. Typed client concurrently fetches three diagnostic endpoints, with six-second timeout, cancellation and manual refresh. Configuration is distinguished from external reachability. Future pages are honest placeholders.
- Tailwind 4 Vite plugin; indigo/teal dark shell, responsive CSS, keyboard skip link, focus indicators and reduced-motion support. Visual rendering remains unverified because Computer Use stopped.
- Install only foundation dependencies. Keep top-level Python requirements plus a complete resolved lock, and npm lockfile. Prettier formats readable TypeScript, JSX and CSS for live interview edits.
- Development Compose uses loopback port publishing, persistent PostgreSQL, health dependencies and internal `db` hostname. Password is supplied by developer, never hardcoded.

### Files created

Root: README.md, AGENTS.md, .gitignore, .dockerignore, .env.example, docker-compose.yml and Git metadata.

Backend: app/main.py, database.py, core/config.py, core/logging.py, api/routes/system.py, schemas/system.py, package initializers, requirements.txt, requirements.lock.txt, pytest.ini, tests/conftest.py, tests/test_foundation.py, alembic.ini and migrations/{env.py,script.py.mako,versions}. Future module directories contain only reservations.

Frontend: package.json/package-lock.json, TypeScript/Vite/ESLint config, public environment example, HTML entry, src/App.tsx, main.tsx, index.css, components/{common/Badge,layout/Sidebar,layout/navigation}, pages/Overview, hooks/useSystemStatus, services/api and types/api.

Infrastructure and documentation: backend/frontend Dockerfiles; scripts/start-backend.ps1 and smoke-api-client.mjs; knowledge_base directory reservations; docs/{setup,architecture,requirements,project_report,development_log}. Ignored local .env files, .venv, node_modules and SQLite data are development artifacts.

### Dependencies installed

Backend isolated `.venv`: FastAPI 0.115.12, Uvicorn 0.34.2, SQLAlchemy 2.0.40, Pydantic 2.11.4, Pydantic Settings 2.9.1, Alembic 1.15.2, psycopg/binary 3.2.9, pytest 8.3.5 and httpx 0.28.1 with resolved transitive versions in requirements.lock.txt.

Frontend: React/React DOM, Vite (resolved 6.4.6), TypeScript 5.8, Tailwind 4 and its Vite plugin, Lucide, ESLint/typescript-eslint/hooks/refresh tooling, type definitions and Prettier. Exact versions are preserved in package-lock.json. No LiveKit, Deepgram, Gemini, Chroma, Recharts or other future integration packages installed.

### Executed verification and actual results

| Check | Actual result |
|---|---|
| `python -m pytest backend -q` | 10 passed; one upstream Starlette/AnyIO deprecation warning |
| `python -m pip check` | No broken requirements found |
| `alembic -c backend/alembic.ini upgrade head` | Exit 0 against explicit SQLite configuration |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed with no remaining code warnings |
| `npm run build` | Passed; Vite 6.4.6 produced dist assets |
| Live Uvicorn startup | Passed without optional provider credentials |
| Live `/api/v1/health` | HTTP 200; healthy, vocalead-api, 0.1.0 |
| Live `/api/v1/ready` | HTTP 200; ready, database connected |
| Live `/api/v1/system/status` | HTTP 200; all six integrations unconfigured and connectivity not_verified |
| Live Swagger `/docs` | HTTP 200 |
| Vite dev server and HTML | Started; HTTP 200 with React app root |
| Fresh Vite dependency serving | Entry, App.tsx, React and React DOM modules all HTTP 200 after a forced optimization restart |
| PowerShell start-backend helper | Started API successfully with shell-local DEBUG=false |
| Actual frontend API-client smoke | Passed against live backend for health, readiness and diagnostics using Node VM + TypeScript transpilation |
| Actual HTTP CORS header | Allowed origin `http://127.0.0.1:5173` returned |
| `docker compose config --quiet` | Passed using a transient validation-only password, without printing resolved secrets |
| Git ignore checks | Root/frontend .env, virtualenv, node_modules and SQLite file correctly excluded |
| Browser visual/rendering interaction QA | Blocked: browser access host unavailable; native Computer Use stopped because current Chrome URL could not be verified confidently |
| Docker images and PostgreSQL execution | Blocked: Docker engine not running |

Tests validate root, health/docs, readiness success/failure, SQL exception handling, configuration precedence/type rejection/path strategy, diagnostics/secret exclusion, production restriction and CORS. A mocked database failure preserves liveness. Temporary test databases require no external services. The API-client smoke exercises actual client code but does **not** verify browser rendering or browser CORS enforcement.

### Problems resolved and remaining limitations

Initial npm/pip downloads and Vite config loading hit sandbox network/filesystem restrictions; approved project-local dependency downloads and build/dev execution outside the sandbox succeeded. Initial Python tests failed on inherited DEBUG and were fixed through explicit environment isolation; the original failure is not counted as a passing run. The initial ESLint shared-export warning was fixed by moving navigation data into its own module.

A Vite dependency-cache rename reported EBUSY while source/configuration/lockfiles changed during hot reload in the OneDrive checkout. After stopping the temporary server, a fresh start with `--force` rebuilt optimization successfully; the entry, application and optimized React modules all returned HTTP 200. If this local file-lock issue recurs, stop Vite and run `npm run dev -- --force`; consider a non-synced checkout if OneDrive repeatedly locks generated files.

Node 23 triggers engine and experimental CommonJS/ESM warnings; use documented Node 22 LTS (at least 22.13 for the resolved lint dependency) or Node 24 LTS for supported development. ESLint 9 emits a registry lifecycle notice; upgrade the toolchain with compatibility verification in maintenance work. The current npm audit reported zero frontend vulnerabilities at installation time; no claim of a complete security audit is made. The Python dependency set has an upstream test-client deprecation warning, and a full dependency security audit was not performed.

Local servers are temporary verification processes and are stopped at final teardown. Setup instructions launch them again. Manual visual QA is still required. External credential validity, voice latency, business workflows, production security, model quality and load capacity are unverified and outside Phase 1.

### Next phase prerequisites

Explicit authorization for Phase 2; LiveKit project/runtime and worker connectivity; Gemini, STT and streaming TTS credentials; current official SDK compatibility verification; English/Hindi/Hinglish and code-switching provider evaluation; microphone-capable browser on localhost/HTTPS; audio consent, retention and interruption requirements; local secrets provisioning and a small consented/synthetic conversation evaluation set. Do not implement these automatically.


## Phase 4 local customer intelligence

Added owner-bound customers, leads, score history, and structured memory via Alembic `c19b882434ef`. Local demo API and Leads dashboard use the same deterministic scoring service as per-call agent tools. The seeded inventory example scores 90 (30 inventory + 25 intent + 20 timeline + 15 visit + 0 contact); a later budget correction persists and another owner receives 404. Backend tests passed 21 cases, including mocked Gemini structured contracts. Frontend typecheck, lint, and production build passed. Gemini structured extraction and sentiment adapters exist but have no credentials and are not live-verified. Text fallback detects limited phrases and returns UNKNOWN otherwise. No live voice call was possible. Phase 3 and Phase 4 were prepared as separate commits after local verification.

## Phase 5 local business automation

Migrations `f20474e3f1ed` and `6e6fe337bc14` add proposals, appointments, unique slot reservations, CRM records, durable sync operations and owner-bound business activity. The local policy follows the knowledge document: Tuesday–Sunday 10:00–17:00 IST, 30-minute visits, one resource per property, two-hour notice, 14-day horizon and five-minute proposal TTL. API-level integration on the existing SQLite database created a synthetic 90-point lead, selected an eligible property, booked an actual free slot after explicit confirmation, returned the same appointment for duplicate confirmation, created a VISIT_BOOKED local CRM record, denied a second owner, cancelled the visit and released the slot. Google Calendar and HubSpot contract tests are mocked only; no external account writes were made. Live voice remains unverified. The Appointments page uses these same services.

Final verification: 28 backend tests passed; Alembic reported no pending schema changes; pip check passed; frontend typecheck, ESLint and production build passed. Vite still reports a bundle-size warning. The local integration script passed against the configured SQLite database. Google timeout reconciliation was tested with mocks; external credentials and a real voice call remain unavailable.
