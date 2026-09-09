# Phase 1 architecture

## Current delivery

The web app is a responsive, accessible dashboard shell. Its command and capability controls preserve user input locally only long enough to display an explicit **not connected** message; they do not call an AI provider, upload files, start recording, or execute tools. Status values are presentation states for this phase.

The API exposes only a non-sensitive health endpoint. It centralizes runtime configuration and has no OpenAI, database, Redis, or tool implementation wired into request handling.

## Intended service flow

`Web client → API routes → application services → AI/agent services → permissioned tools → data/external services`

Future capabilities must enter through typed, provider-neutral service contracts. The frontend receives no service credentials. Tool calls will require a registered schema, permission level, input validation, authorization, audit log, and an explicit confirmation policy for consequential actions.

## Security baselines established now

- Environment variables are documented in `.env.example`; real `.env` files are ignored.
- API CORS uses explicit configured origins and only exposes the health read route.
- Configuration avoids logging secrets; the health response is intentionally non-sensitive.
- OpenAI credentials are reserved for server-side configuration only and are not referenced by the web application.
- The dashboard does not misrepresent unavailable capabilities as running services.

## Deferred deliberately

Authentication, persistence, rate limiting, WebSockets, AI provider calls, uploads, background jobs, and any operational tool execution belong to later phases. PostgreSQL and Redis are present only as local infrastructure dependencies, not as fake active features.
