# JARVIS — Phase 1

JARVIS is a security-minded personal AI assistant platform. This repository currently delivers **Phase 1 only**: a responsive application shell and dashboard plus a minimal, health-checkable API foundation. The dashboard intentionally does not perform AI, voice, file, or tool actions yet.

## Layout

- `apps/web` — Next.js TypeScript dashboard.
- `apps/api` — FastAPI service boundary and future service contracts.
- `packages/ui` — reserved for shared UI primitives.
- `packages/shared` — reserved for cross-service contracts.
- `infrastructure` — local Docker Compose stack.
- `docs` — architecture and Phase 1 decisions.
- `tests` — repository-level test assets (reserved).

## Local development

```bash
cp .env.example .env
cd apps/web && npm install && npm run dev
```

Open `http://localhost:3000`. In a second terminal, start the API:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

Or run the infrastructure dependencies and services with Docker:

```bash
docker compose -f infrastructure/docker-compose.yml --env-file .env up --build
```

## Verification

```bash
cd apps/web && npm run lint && npm run test && npm run build
cd ../api && pytest
```

See [docs/architecture.md](docs/architecture.md) for the service boundaries and security posture.
