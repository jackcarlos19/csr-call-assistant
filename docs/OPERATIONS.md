# Operations

## Docker Compose Startup
- Run `docker compose up --build`.
- Wait for all services to report healthy/running.

## Run Migrations
- Run `cd apps/api && alembic upgrade head`.

## Run Tests
- Run `cd apps/api && python -m pytest tests/ -v`.
- Run `cd apps/web && npm run lint && npm run build`.

## View Logs
- Run `docker compose logs -f`.
- Run `docker compose logs -f api` for API only.
- Run `docker compose logs -f web` for web only.

## Troubleshooting
- If health checks fail, verify `POSTGRES_PASSWORD` and service readiness.
- If API cannot connect to DB, ensure `DATABASE_URL` points to `postgres` host.
- If web cannot call API, verify `NEXT_PUBLIC_API_URL`.
