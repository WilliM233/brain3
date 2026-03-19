## Summary

Set up the local development environment with PostgreSQL 16 running in Docker Desktop. This is the foundation that all subsequent tickets build on.

## Context

- **Environment:** Local Windows machine with Docker Desktop
- **Scope:** Dev environment only. Production/TrueNAS deployment is ticket #12.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 2 (Architecture) and 3 (Technology Stack)

## Deliverables

- `docker-compose.dev.yml` — Dev-only Compose file for PostgreSQL
- `.env.example` — Environment variable template with database credentials
- `docs/dev-setup.md` — Developer setup guide

## Acceptance Criteria

- [ ] `docker-compose.dev.yml` defines a PostgreSQL 16-alpine service
- [ ] Named volume `brain3_dev_data` for persistent database storage across container restarts
- [ ] Health check configured on the Postgres container (`pg_isready`)
- [ ] Container exposes port 5432 to localhost (configurable via .env)
- [ ] `.env.example` includes: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`
- [ ] `docs/dev-setup.md` covers: prerequisites (Docker Desktop), setup steps, how to start/stop/reset the database, how to connect with a client
- [ ] Verification: `docker compose -f docker-compose.dev.yml up -d` starts Postgres and `pg_isready` returns success

## Technical Notes

- Use `docker-compose.dev.yml` (not `docker-compose.yml`) — production will use a separate `docker-compose.prod.yml` in ticket #12
- PostgreSQL 16-alpine for small image size
- Default dev credentials in `.env.example` should be obvious dev values (e.g. `brain3` / `brain3_dev`) — production credentials are a separate concern
- No API container in this file — in dev, FastAPI runs natively with hot reload

## Dependencies

None — this is the first ticket.
