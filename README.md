# VocaLead AI

Autonomous multilingual sales intelligence for real estate. Buyers often wait for follow-up while sales teams repeatedly collect the same requirements. VocaLead aims to qualify enquiries through natural English, Hindi and Hinglish conversations, retrieve relevant property knowledge and hand actionable context to sales teams.

**Current delivery: Phase 2 voice implementation, awaiting live provider verification.** The Phase 1 foundation remains. Voice adds a consent gate, LiveKit session API, dedicated worker, room audio, LiveKit transcripts, and SQLite session metadata. Missing provider credentials prevent a real call on this machine. RAG, persistent customer memory and sales operations remain planned.

## Run locally (Windows PowerShell)

Prerequisites: Python 3.11/3.12, Node 22 LTS (22.13+) or Node 24 LTS, npm and Git. Docker Desktop is optional for local SQLite and required for the provided PostgreSQL containers.

```powershell
Copy-Item .env.example .env
$env:DEBUG = 'false' # This machine inherits DEBUG=release; process settings override .env.
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1 -Reload
```

If `py` cannot find an installed Python, use its full executable path; see [setup](docs/setup.md). In another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Browser: http://localhost:5173. API: http://127.0.0.1:8000. Swagger: http://127.0.0.1:8000/docs. Health: `/api/v1/health`; database readiness: `/api/v1/ready`; development diagnostics: `/api/v1/system/status`.

The example explicitly selects SQLite at `data/vocalead.db`. PostgreSQL is the target database. No automatic fallback happens if a database fails. Optional AI credentials may stay empty.

## Docker

Copy `.env.example` to `.env` if necessary and set `POSTGRES_PASSWORD` to your own local password (URL-safe characters for the composed connection URL). Start Docker Desktop in Linux containers mode, then:

```powershell
docker compose up --build
```

Compose uses PostgreSQL at `db:5432` internally and publishes local-only ports. The frontend calls the browser-accessible API at `localhost:8000`. These containers are development services, not production hosting. Do not run a local backend and Compose backend on the same port.

## Checks

```powershell
backend/.venv/Scripts/python.exe -m pytest backend
$env:DEBUG = 'false'
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
# With the backend running, test the actual frontend API client:
node --experimental-vm-modules scripts/smoke-api-client.mjs
Set-Location frontend
npm run typecheck
npm run lint
npm run build
```

## Structure and stack

`frontend/src/{components,pages,hooks,services,types}` contains the React/TypeScript/Tailwind UI and API client. `backend/app/{api,core,schemas}` implements the FastAPI/Pydantic foundation; `database.py` owns SQLAlchemy engines and sessions. `backend/migrations` holds Alembic setup, with no business tables yet. `backend/tests`, `infrastructure`, `scripts`, `knowledge_base` and `docs` separate verification, deployment and project material.

Voice dependencies now installed: LiveKit React/Agents, Deepgram, Silero, Gemini LLM and ElevenLabs TTS. Future dependencies (not installed): Gemini embeddings, ChromaDB, Calendar, HubSpot and Recharts. React uses simple hash navigation.

## Roadmap and limitations

1. Foundation: configuration, liveness/readiness, UI, database, tests and docs.
2. Real-time voice worker: implemented and unit-tested; real provider and microphone validation pending.
3. Property knowledge, structured extraction, deterministic qualification and sentiment.
4. Calendar/CRM integrations, summaries and measured analytics.

Voice endpoints are restricted to local development and use a session-scoped owner key; this is not multi-tenant authentication. Keep diagnostics local; implement authentication/authorization before handling customer data or exposing the app publicly. External service reachability is not tested. Phase-wide commercial, scalability and deployment assumptions are outlined in [architecture](docs/architecture.md); they are not measured guarantees. Current verification evidence and environment blockers are in [development log](docs/development_log.md).

Read [setup](docs/setup.md), [architecture](docs/architecture.md), [requirements](docs/requirements.md) and [repository instructions](AGENTS.md) before extending the project.
