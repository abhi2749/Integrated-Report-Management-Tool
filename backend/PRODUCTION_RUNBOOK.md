# ReportingTool Production Runbook

## Required environment

Set these values outside source control:

- `APP_ENV=production`
- `APP_DEBUG=false`
- `SECRET_KEY` — at least 32 characters
- `ENCRYPTION_KEY` — required in production
- `CORS_ORIGINS` — explicit trusted frontend origins
- `CORS_ALLOW_CREDENTIALS=true` only when required
- `SECURE_COOKIES=true`

Do not commit `.env`, database passwords, tokens, or encryption keys.

## Probes

- `GET /health` — liveness
- `GET /ready` — readiness; returns HTTP 503 when the data/result-store paths are unavailable

## Graceful shutdown

Application shutdown waits for in-flight report workers before exiting so persisted results are not intentionally abandoned mid-operation.

## Data limits

The application does not impose an artificial report-row or export-size ceiling when the corresponding setting is `0`. Operational capacity should instead be controlled through concurrency, memory/spill settings, database capacity, and infrastructure resources.

## Backups

Use the authenticated admin backup endpoints and configure external backup storage for production deployments. Test recovery periodically.
