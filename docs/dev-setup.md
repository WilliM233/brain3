# Developer Setup Guide

Everything you need to go from a fresh clone to a running BRAIN 3.0 development environment. This is the reference you come back to when something breaks — for the quick version, see the [README](../README.md).

---

## Prerequisites

| Requirement | Version | Why |
|-------------|---------|-----|
| [Python](https://www.python.org/downloads/) | 3.12+ | Runtime for FastAPI and Alembic |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Latest stable | Runs PostgreSQL in a container |
| [Git](https://git-scm.com/) | Latest stable | Version control |

Verify your installations:

```bash
python --version
docker --version
docker compose version
git --version
```

Python must report 3.12 or higher. Docker Compose must be V2 (the `docker compose` plugin, not the legacy `docker-compose` binary).

---

## Clone and Configure

```bash
git clone https://github.com/WilliM233/brain3.git
cd brain3
```

Copy the environment template:

```bash
cp .env.example .env
```

The defaults in `.env.example` are ready for local development — no changes needed. They configure:

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_USER` | `brain3` | Database user |
| `POSTGRES_PASSWORD` | `brain3_dev` | Database password |
| `POSTGRES_DB` | `brain3_dev` | Database name |
| `POSTGRES_HOST` | `localhost` | Database host (localhost because Postgres exposes a port to the host) |
| `POSTGRES_PORT` | `5432` | Database port |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API listen port |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Allowed CORS origins |

For the full variable reference, see [environment-variables.md](environment-variables.md).

---

## Start PostgreSQL

```bash
docker compose -f docker-compose.dev.yml up -d
```

This starts a single container: PostgreSQL 16 with a persistent named volume (`brain3_dev_data`). The dev compose file does **not** containerize the API — you run that natively for hot-reload.

Verify it's healthy:

```bash
docker compose -f docker-compose.dev.yml ps
```

You should see `brain3-postgres-dev` with status `healthy`. If it shows `starting`, wait a few seconds and check again — the health check runs every 10 seconds.

### Connecting directly to the database

```bash
docker compose -f docker-compose.dev.yml exec postgres psql -U brain3 -d brain3_dev
```

Connection string for tools (pgAdmin, DBeaver, etc.):

```
postgresql://brain3:brain3_dev@localhost:5432/brain3_dev
```

---

## Install Python Dependencies

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

Install both runtime and dev dependencies:

```bash
pip install -r requirements-dev.txt
```

This pulls in the application dependencies (`requirements.txt`) plus testing and linting tools (pytest, httpx, ruff).

---

## Run Database Migrations

```bash
alembic upgrade head
```

This applies all migration scripts in `alembic/versions/`, creating the seven pillar tables and their relationships. Alembic reads the database URL from your `.env` file via `app/config.py`.

If you see a connection error, make sure PostgreSQL is running and your `.env` values match the `docker-compose.dev.yml` configuration.

---

## Start the API

```bash
uvicorn app.main:app --reload
```

The `--reload` flag watches for file changes and restarts automatically. The API binds to `http://localhost:8000` by default.

### Verify

Open [http://localhost:8000/health](http://localhost:8000/health) in a browser or:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy", "database": "connected"}
```

The interactive API docs (Swagger UI) are at [http://localhost:8000/docs](http://localhost:8000/docs). Every endpoint is testable directly from this page.

---

## Daily Workflow

### Start your environment

```bash
docker compose -f docker-compose.dev.yml up -d
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Stop (preserves data)

```bash
docker compose -f docker-compose.dev.yml down
```

### Reset the database (wipe all data)

```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
alembic upgrade head
```

The `-v` flag removes the `brain3_dev_data` volume, destroying all database contents. You'll need to re-run migrations after.

### Apply new migrations

If someone (or you) added a new Alembic migration:

```bash
alembic upgrade head
```

Alembic tracks which migrations have already been applied — it only runs new ones.

---

## Running Tests

Tests use an in-memory SQLite database, so they don't touch your development PostgreSQL instance. No setup needed beyond installing `requirements-dev.txt`.

### Run the full suite

```bash
pytest -v
```

### Run tests for a specific entity

```bash
pytest tests/test_tasks.py -v
```

### Run a single test

```bash
pytest tests/test_tasks.py::TestCreateTask::test_create_task_happy_path -v
```

### Lint

```bash
ruff check .
```

### What CI checks

The CI pipeline (`.github/workflows/ci.yml`) runs two parallel jobs on every push and PR to `develop`:

1. **Test** — Spins up a PostgreSQL 16 service container, runs Alembic migrations, then runs `pytest -v`
2. **Lint** — Runs `ruff check .`

Both must pass for CI to be green. Run them locally before opening a PR.

---

## Troubleshooting

### Database connection refused

**Symptom:** `psycopg2.OperationalError: could not connect to server: Connection refused`

**Check:**
1. Is Docker running? `docker ps` should list containers.
2. Is the Postgres container healthy? `docker compose -f docker-compose.dev.yml ps`
3. Do your `.env` values match? `POSTGRES_HOST` should be `localhost` for dev (not `db` — that's the production service name).

### Migration error

**Symptom:** `alembic upgrade head` fails with a migration error.

**Check:**
1. Is the database running and reachable?
2. Did you reset the database volume? If so, `alembic upgrade head` should work on a clean database.
3. If you see "Target database is not up to date" or a revision conflict, you may have a dirty migration state. Reset: `docker compose -f docker-compose.dev.yml down -v`, then start fresh.

### Port 5432 already in use

**Symptom:** Docker can't bind to port 5432.

**Fix:** Another PostgreSQL instance (or another Docker container) is using that port. Either stop the other instance or change `POSTGRES_PORT` in your `.env` and restart the container.

### Port 8000 already in use

**Symptom:** `uvicorn` fails to start with "address already in use."

**Fix:** Another process is on port 8000. Find it with `lsof -i :8000` (macOS/Linux) or `netstat -ano | findstr :8000` (Windows), then stop it — or change `API_PORT` in `.env` and start uvicorn with `--port <new-port>`.

### Docker Desktop not starting

**Symptom:** `docker` commands fail with "Cannot connect to the Docker daemon."

**Fix:** Open Docker Desktop and wait for it to finish starting. On Windows, check that WSL 2 is installed and enabled.

### Tests fail with import errors

**Symptom:** `ModuleNotFoundError: No module named 'app'`

**Fix:** Make sure you activated your virtual environment (`source .venv/bin/activate`) and installed dependencies (`pip install -r requirements-dev.txt`). Run tests from the project root directory.
