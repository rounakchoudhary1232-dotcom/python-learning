# ULTRON

ULTRON is a secure, local-first personal AI operating assistant. Phase 2+3 adds account-scoped sessions, protected conversations and message persistence, and a provider-neutral server-side AI conversation boundary.

## Quick start

1. Copy `.env.example` to `.env` and set non-production local values.
2. Start the API from `apps/api`: `python -m venv .venv && .venv\\Scripts\\activate && pip install -e ".[dev]" && uvicorn app.main:app --reload --port 8000`
3. Start the web app from the repository root: `npm install && npm run dev:web`

The dashboard is available at `http://localhost:3000`; API documentation at `http://localhost:8000/docs`. SQLite is the default local database, so Docker is optional. To use PostgreSQL/Redis later, start `docker compose -f infrastructure/docker-compose.yml up -d` and switch `DATABASE_URL` in `.env`.

On startup, the API runs an append-only schema bootstrap that creates only missing tables and records schema version `1`; it never resets or drops data. Future schema revisions must add an explicit numbered upgrade before model changes.

## Authentication and AI configuration

Register from the dashboard to establish an HttpOnly, SameSite session cookie. Every conversation API endpoint validates that session server-side and scopes records to its owner. Logout invalidates the account's active sessions.

For live conversations, configure the API process with `GEMINI_API_KEY`, `AI_PROVIDER=gemini`, and `AI_MODEL=gemini-2.5-flash` (or a Gemini model your account can use). Gemini is the development default. ULTRON calls the provider only from FastAPI; the browser never receives the key. Without a key or during an upstream outage, the chat stores a clear, retryable configuration/error state instead of fabricating an answer. OpenAI remains available by setting `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and a compatible `AI_MODEL`.

Run checks with `npm run lint`, `npm run test -- --run`, and `npm run build` in `apps/web`; run `pytest` in `apps/api` after installing `.[dev]`.

## Safety model

ULTRON executes only registered, schema-validated safe tools. Read-only actions can run immediately; external actions create a pending approval record; destructive actions are intentionally not implemented. Security assessment requests require an explicit authorization confirmation and only queue defensive hygiene checks—no scanning or exploitation adapter is enabled by default.

## AI provider

Chat persistence works now. Responses require a configured server-side provider adapter; when no API key is configured, the API returns a clear configuration state without exposing a secret or pretending to have generated an answer. Phase 4 should introduce an explicit long-term memory policy and retrieval layer; agent orchestration and tool execution remain out of scope.

See [docs/architecture.md](docs/architecture.md) for Phase 1 boundaries and expansion points.
