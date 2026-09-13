# Architecture

## Phase 1 boundary

Phase 1 delivers a responsive ULTRON application shell and a small operational API. The displayed assistant, memory, voice, vision, and tool states are presentation-only indicators; no AI requests, uploads, microphone capture, or tool execution occurs.

## Request path

`Web client → FastAPI API → application services → provider/tool adapters → database or external service`

The web client contains no secret credentials. Future integrations are represented by server-side service protocols in `apps/api/app/services/contracts.py`, making provider implementations replaceable.

## Security baseline

- Environment-derived configuration is validated by Pydantic and secrets remain server-side.
- FastAPI requests carry or receive an `X-Request-ID`; structured logs do not include secrets.
- CORS is allow-list based.
- Future tools must declare schemas, permission level, validation, error handling, and audit events before registration.
- PostgreSQL and Redis are private Compose services, not published outside the local Docker network.

## Module ownership

- `apps/web`: UI and browser-safe API clients only.
- `apps/api`: HTTP boundary, services, service contracts, configuration, and security middleware.
- `packages/ui`: reusable UI primitives (reserved for shared components as features expand).
- `packages/shared`: cross-runtime, non-secret types/constants.
- `infrastructure`: local runtime infrastructure and deployment inputs.
- `tests`: test strategy and integration suites as they expand.
