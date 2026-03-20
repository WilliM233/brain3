## Summary

Configure the production deployment of BRAIN 3.0 on TrueNAS. This ticket covers the production Docker Compose, backup automation, environment configuration, deployment documentation, and smoke testing to validate the full stack works outside of the dev environment.

## Context

- **Scope:** Production deployment infrastructure. This is the dev-to-test bridge — verifying that everything built in tickets #1-11 runs correctly in the target environment.
- **Environment:** TrueNAS server running Docker. PostgreSQL and FastAPI both run as containers. MCP runs on the client machine connecting to the API over the home network.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 2 (Architecture), 3 (Technology Stack), and 9 (Design Decisions: Backup Strategy)

## Deliverables

- `docker-compose.prod.yml` — Production Compose file (PostgreSQL + API containers)
- `Dockerfile` — API container build (if not already created)
- `.env.production.example` — Production environment variable template
- `scripts/backup.sh` — PostgreSQL backup script for TrueNAS cron
- `scripts/smoke-test.sh` — Automated smoke test script
- `docs/deployment.md` — Full deployment guide for TrueNAS
- `docs/first-deploy-checklist.md` — Manual checklist for initial deployment

## Production Docker Compose

### Differences from dev:
- **Both** PostgreSQL and the API run as containers (dev runs API natively)
- Restart policies: `restart: unless-stopped` on both services
- API container depends on database health check
- API runs Alembic migrations on startup before starting uvicorn
- No port exposure for PostgreSQL — only the API container can reach it via Docker networking
- API exposes its port to the host network (configurable, default 8000)

### Services:
- `db` — PostgreSQL 16-alpine with named volume, health check, restart policy
- `api` — FastAPI built from Dockerfile, depends on db, runs migrations + uvicorn

## Backup Configuration

### `scripts/backup.sh`
- Runs `pg_dump` against the PostgreSQL container
- Writes timestamped SQL dump to a configurable TrueNAS dataset path (e.g. `/mnt/pool/backups/brain3/`)
- Filename format: `brain3_YYYY-MM-DD_HHMMSS.sql.gz` (compressed)
- Deletes backups older than 30 days
- Logs success/failure to a log file
- Exit code reflects success/failure (for TrueNAS cron alerting)

### TrueNAS Cron Setup
- Documented in deployment guide: how to add the cron job via TrueNAS UI
- Recommended schedule: daily at 2:00 AM
- The backup script should be executable and self-contained (no dependency on the repo being cloned to a specific path — configurable via variables at the top of the script)

## Environment Configuration

### `.env.production.example`
- `POSTGRES_USER` — production database user
- `POSTGRES_PASSWORD` — strong production password (not the dev default)
- `POSTGRES_DB` — production database name
- `POSTGRES_HOST` — `db` (Docker service name, not localhost)
- `POSTGRES_PORT` — 5432
- `API_HOST` — 0.0.0.0
- `API_PORT` — 8000 (or custom)
- `BACKUP_PATH` — TrueNAS dataset path for backups
- `BACKUP_RETENTION_DAYS` — 30

## Smoke Test

### `scripts/smoke-test.sh` (automated, for ongoing use)
- Accepts API base URL as parameter (default `http://localhost:8000`)
- Tests in sequence, stops on first failure:
  1. Health check — `GET /health` returns healthy with database connected
  2. Create a domain — `POST /api/domains` with test data
  3. Read it back — `GET /api/domains/{id}` returns the created domain
  4. Create a goal under the domain
  5. Create a task under a project under the goal
  6. Log an activity entry
  7. Get activity summary — `GET /api/reports/activity-summary`
  8. Clean up — delete test entities
- Prints pass/fail for each step
- Exit code 0 if all pass, 1 if any fail

### `docs/first-deploy-checklist.md` (manual, for initial deployment)
- [ ] TrueNAS Docker environment is running
- [ ] Production `.env` file created with strong credentials
- [ ] `docker compose -f docker-compose.prod.yml up -d` starts both containers
- [ ] `docker compose -f docker-compose.prod.yml ps` shows both services healthy
- [ ] API docs accessible at `http://TRUENAS_IP:8000/docs`
- [ ] Health endpoint returns healthy
- [ ] Run `scripts/smoke-test.sh http://TRUENAS_IP:8000` — all pass
- [ ] Backup script runs manually without errors
- [ ] Backup file appears in the configured backup path
- [ ] Cron job scheduled in TrueNAS UI
- [ ] MCP server on client machine can connect to `http://TRUENAS_IP:8000`
- [ ] End-to-end test: Claude creates a domain through MCP conversation
- [ ] Verify container restart: `docker restart brain3-api` — API recovers and reconnects

## Acceptance Criteria

- [ ] `docker-compose.prod.yml` starts both PostgreSQL and API containers
- [ ] API container runs Alembic migrations on startup
- [ ] API container restarts automatically if it crashes
- [ ] PostgreSQL is not exposed to the host network — only reachable by the API container
- [ ] `.env.production.example` documents all required environment variables
- [ ] `scripts/backup.sh` successfully dumps, compresses, and stores the database
- [ ] Backup script cleans up files older than retention period
- [ ] Backup script logs success/failure
- [ ] Smoke test script validates the full API surface
- [ ] Smoke test cleans up after itself (no leftover test data)
- [ ] `docs/deployment.md` covers: prerequisites, setup steps, starting/stopping, updating, backup configuration, troubleshooting
- [ ] `docs/first-deploy-checklist.md` covers the complete first-time deployment flow
- [ ] Full stack verified on TrueNAS: database, API, migrations, backups, and MCP connectivity

## Technical Notes

- The API Dockerfile should use a multi-stage build or slim base image to keep the image size small
- Consider adding a `docker-compose.prod.yml` override for log rotation on containers
- The backup script connects to PostgreSQL via `docker exec` on the database container — no need to expose Postgres ports
- For the MCP connection from a client machine to the TrueNAS API: this works over the home network in Phase 1. Phase 3 (auth) will secure this connection.
- If TrueNAS uses a non-standard Docker path, document how to adjust the compose file

## Dependencies

- Tickets #1-11 (the full Phase 1 application must be built and working in dev)
