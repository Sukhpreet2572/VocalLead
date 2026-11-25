# Development setup

## Phase 3 knowledge demo

All inventory is synthetic. Apply migration `0002_property_knowledge`, then run the idempotent seed and ingestion from the repository root:

```powershell
$env:DEBUG='false'
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe scripts/seed_properties.py
# If GOOGLE_API_KEY is absent, set EMBEDDING_PROVIDER=local and RAG_COLLECTION_NAME=vocalead_local_multilingual in root .env first.
backend/.venv/Scripts/python.exe scripts/ingest_documents.py
```

Gemini uses `gemini-embedding-001`; local uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Chroma persists under `data/chroma`. Never change the model in an existing collection; select a new `RAG_COLLECTION_NAME` and reingest. Open `http://localhost:5173/#knowledge` to inspect real counts, inventory and the retrieval playground. Unit-specific prices and availability are filtered in SQLite before vector passages are included. Reported cosine distance is not a confidence percentage. The local model download may be large. No provider credentials are placed in the frontend.

## Phase 2 voice setup

Use a LiveKit Cloud project, a Deepgram API key, a Google Gemini API key and an ElevenLabs API key/voice. These services can incur charges; review each provider's plan before entering credentials. Add these variables to the existing root `.env` without replacing the SQLite `DATABASE_URL`: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `GOOGLE_API_KEY`, `TTS_PROVIDER=elevenlabs`, `TTS_API_KEY`, `TTS_MODEL=eleven_multilingual_v2`, and a Hindi/English-capable `TTS_VOICE_ID`. Optional defaults are `LIVEKIT_AGENT_NAME=vocalead-sales-agent`, `DEEPGRAM_STT_MODEL=nova-3`, `DEEPGRAM_STT_LANGUAGE=multi`, `GEMINI_MODEL=gemini-2.5-flash`, `VOICE_MAX_SESSION_SECONDS=600`, `VOICE_TOKEN_TTL_SECONDS=300`, `VOICE_TRANSCRIPT_RETENTION_ENABLED=false`. Confirm provider model and voice availability in your own account. Do not put keys in frontend `.env`.

Apply the migration with `$env:DEBUG='false'; backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head` from the root. The three processes are:

```powershell
# Terminal 1, repository root
$env:DEBUG='false'
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1 -Reload

# Terminal 2, repository root
$env:DEBUG='false'
Set-Location backend
.venv/Scripts/python.exe -m app.voice.worker download-files
.venv/Scripts/python.exe -m app.voice.worker dev

# Terminal 3, repository root
Set-Location frontend
npm.cmd run dev
```

The `download-files` command is supplied by the installed LiveKit Agents CLI and prepares local VAD assets. Leave the three processes running while testing. Open http://localhost:5173/#voice, read/acknowledge consent, select a language and click Start Call. Grant microphone permission. Verify the browser and agent join, speak an English property request, then Hindi (`मुझे गुरुग्राम में तीन बीएचके का फ्लैट चाहिए।`) and Hinglish (`Mera budget 1.2 crore hai...`). Ask it to repeat your details; interrupt a spoken response; end the call and check the microphone indicator disappears. Compare final transcripts and audible replies. These manual tests await real credentials and user microphone interaction; none has been marked passed.

The API limits this demo to local development, one active session per browser owner key and a ten-minute worker room limit. Phase 4 owner keys live in browser local storage to support returning demo customers. Audio and transcript text are not persisted. `VOICE_TRANSCRIPT_RETENTION_ENABLED` reserves a future policy switch; this phase does not persist transcripts even when enabled. Do not expose this demo publicly without authentication, HTTPS, provider quotas and an audited consent/retention policy.

Run commands from the repository root in Windows PowerShell unless stated otherwise. This repository lives directly in `VocalLead`; no extra nested checkout is required.

## Prerequisites

Python 3.11 or 3.12 and Node 22 (22.13+) or Node 24 LTS are recommended. This machine has Python 3.11.9 at the path below even though `python` and `py` do not resolve it. Node 23.1.0 is present and is not a supported LTS baseline. Docker/Compose CLIs are installed but the engine was unavailable during initial inspection.

If installing prerequisites is necessary, run these yourself (no global installation is performed by this project):

```powershell
winget install --exact --id Python.Python.3.11
winget install --exact --id OpenJS.NodeJS.LTS
winget install --exact --id Git.Git
winget install --exact --id Docker.DockerDesktop
```

Restart the terminal after installation. Start Docker Desktop and enable Linux containers; follow its WSL2 setup prompts if shown.

```powershell
python --version
node --version
npm --version
git --version
docker compose version
docker info
```

## Backend with explicit SQLite fallback

```powershell
Copy-Item .env.example .env
$env:DEBUG = 'false'
# Use py -3.11 when the launcher works; this full path works on the inspected machine:
& "$env:LOCALAPPDATA/Programs/Python/Python311/python.exe" -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1 -Reload
```

Leave `DATABASE_URL=sqlite:///./data/vocalead.db` for the explicit SQLite development choice. Paths resolve against the repository root, independent of launch directory. Settings always load root `.env`; environment variables override it. Blank database URLs fail validation. SQLite is for single-machine development, not production load testing. No business tables or initial business migration are necessary in Phase 1; `upgrade head` initializes Alembic bookkeeping only.

Without the helper, the equivalent default server command is:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload --reload-dir backend --no-access-log
```

The helper reads `API_HOST` and `API_PORT`; direct Uvicorn commands use their command-line flags. Debug configuration never enables traceback exposure in HTTP responses.

This machine inherits a non-boolean `DEBUG=release` from its environment. Pydantic correctly rejects it. Set `$env:DEBUG = 'false'` in each backend/Alembic terminal as shown above; this changes only that shell session and preserves type validation. A `.env` value cannot override an existing process environment variable. Tests explicitly isolate inherited application settings.

## Frontend

In a second PowerShell terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Only `VITE_API_BASE_URL` belongs in the browser environment. Restart Vite after environment edits. Vite environment selection determines the DEV/BUILD badge; the diagnostic response identifies backend development mode. Port 5173 is strict so an unexpected port will not silently break CORS.

If the npm PowerShell wrapper reports a prefix permission error on this machine, use `npm.cmd`, or:

```powershell
node 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' ci
node 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run dev
```

## PostgreSQL

Set `POSTGRES_PASSWORD` in root `.env` to a local password you choose. Use URL-safe characters or percent-encode reserved characters in a manually supplied `DATABASE_URL`.

For database only:

```powershell
docker compose up -d db
```

Edit root `.env` to `DATABASE_URL=postgresql+psycopg://vocalead:<your-password>@localhost:5432/vocalead`, restart the backend, and run Alembic. For the complete container stack use `docker compose up --build`; Compose overrides the database hostname with `db`. Persisted PostgreSQL passwords are established on first volume initialization: changing the variable does not change an existing database user's password. Do not delete volumes to solve this without backing up data.

To stop containers while preserving data: `docker compose down`. Docker setup has to be verified once the engine is running.

## Verify

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ready
Invoke-RestMethod http://127.0.0.1:8000/api/v1/system/status
backend/.venv/Scripts/python.exe -m pytest backend
Set-Location frontend
npm run typecheck
npm run lint
npm run build
```

Open http://localhost:5173 and http://127.0.0.1:8000/docs. Refresh status; check connected API and database, plus honest integration configuration. Stop the backend and refresh to see unavailable states. Restart it and refresh to recover. Choose every sidebar page; future features should show explicit placeholders. Test at a narrow viewport and navigate by Tab. Set `APP_ENV=production`, restart, and verify diagnostics returns 404; this alone does not make the application production ready. Do not put real credentials in test reports or screenshots.

With the backend running in development mode, run `node --experimental-vm-modules scripts/smoke-api-client.mjs` from the repository root to exercise the actual frontend client against the API without a browser. The VM-module flag is for this test harness only. It does not replace manual browser rendering and interaction checks. Use `npm run format` inside frontend for readable source formatting.


## Phase 4 local demo

From `backend`, run `.venv/Scripts/python.exe -m alembic upgrade head` and `.venv/Scripts/python.exe -m uvicorn app.main:app --reload`. From `frontend`, run `npm run dev`. Open `http://localhost:5173/#leads`, create a demo customer, and submit a final sample message. For the verified 90-point example, use restricted `PATCH /api/v1/leads/{lead_id}` with location `Gurugram`, configuration `3 BHK`, max budget `12000000`, purchase intent `STRONG`, timeline months `2`, and site visit interest `true`. Supply the same 64-character `X-Voice-Owner` header used at creation. Clearing browser local storage loses access to that demo profile. Do not enter real customer data into this local demo.

## Phase 5 local appointment demo

From the repository root in PowerShell, set `$env:DEBUG='false'` and run `backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head`. Then run `backend/.venv/Scripts/python.exe scripts/verify_automation.py` to exercise the configured SQLite database end to end. Start the API from `backend` with `.venv/Scripts/python.exe -m uvicorn app.main:app --reload`; start the UI from `frontend` with `npm run dev`. Open `http://localhost:5173/#leads` to create an owned demo lead, then `http://localhost:5173/#appointments` to select that lead, property, date and actual available slot. Review the short-lived proposal and click the explicit confirmation button. Pending voice proposals can also be refreshed and confirmed here. Calendar and CRM status are displayed separately. The demo script creates and cancels a synthetic appointment, leaving audit records.

Local mode needs no external credentials: `CALENDAR_PROVIDER=local`, `CRM_PROVIDER=local`. Scheduling settings are `APPOINTMENT_TIMEZONE=Asia/Kolkata`, `APPOINTMENT_DURATION_MINUTES=30`, `APPOINTMENT_BOOKING_HORIZON_DAYS=14`, `APPOINTMENT_MIN_NOTICE_MINUTES=120`, and `BOOKING_PROPOSAL_TTL_SECONDS=300`. For Google Calendar, configure `CALENDAR_PROVIDER=google`, a dedicated test `GOOGLE_CALENDAR_ID`, and a service-account JSON file path in `GOOGLE_APPLICATION_CREDENTIALS`. Share that dedicated calendar with the service account with event write permission; free/busy permission alone is insufficient. Never point this demo at a personal calendar without explicit authorisation. For HubSpot, configure `CRM_PROVIDER=hubspot` and a test portal `HUBSPOT_ACCESS_TOKEN` with contact write access. Only consented email contacts are upserted. No external provider was exercised here; use dedicated test resources before claiming live verification.
