# Environment Variable Reference

Every environment variable used by BRAIN 3.0, documented in one place. Variables are read by `app/config.py` (via Pydantic Settings) and by the Docker Compose files and scripts.

---

## Database

| Variable | Required | Default | Description | Example |
|----------|----------|---------|-------------|---------|
| `POSTGRES_USER` | **Yes** | *none* | PostgreSQL username. Used by both the database container and the API connection string. | `brain3` |
| `POSTGRES_PASSWORD` | **Yes** | *none* | PostgreSQL password. **No default — the app will fail to start if unset.** Use a strong, unique password in production. | `brain3_dev` (dev) / `openssl rand -base64 24` (prod) |
| `POSTGRES_DB` | **Yes** | *none* | PostgreSQL database name. Created automatically by the Postgres container on first run. | `brain3_dev` (dev) / `brain3` (prod) |
| `POSTGRES_HOST` | No | `localhost` | Database hostname. Use `localhost` in dev (Postgres port is exposed to the host). Use `db` in production (Docker Compose service name on the bridge network). | `localhost` (dev) / `db` (prod) |
| `POSTGRES_PORT` | No | `5432` | Database port. Both the Postgres container and the API connection use this value. | `5432` |

> **Important:** `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` have no defaults in the application code (`app/config.py`). If any of these are missing, the app raises a Pydantic validation error at startup. This is by design — database credentials must be set explicitly, especially in production.

**Used by:** `app/config.py` (API connection), `docker-compose.dev.yml`, `docker-compose.prod.yml`, `scripts/backup.sh`

---

## API

| Variable | Required | Default | Description | Example |
|----------|----------|---------|-------------|---------|
| `API_HOST` | No | `0.0.0.0` | Address the uvicorn server binds to. `0.0.0.0` makes the API accessible on all network interfaces. | `0.0.0.0` |
| `API_PORT` | No | `8000` | Port the uvicorn server listens on. Also used in the Docker Compose port mapping. | `8000` |

**Used by:** `app/config.py`, `scripts/entrypoint.sh`, `docker-compose.prod.yml`

---

## CORS

| Variable | Required | Default | Description | Example |
|----------|----------|---------|-------------|---------|
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:8000` | Comma-separated list of allowed CORS origins. Controls which browser origins can make cross-origin requests to the API. | `http://localhost:3000,http://localhost:8000` (dev) / `http://192.168.1.100:8000` (prod) |

In Phase 1 (no web UI), the primary API consumer is the MCP server, which makes server-side HTTP requests not subject to CORS. This variable becomes important in Phase 3 when the browser-based UI is added. Set it to your TrueNAS IP in production so the API is ready for future UI work.

**Used by:** `app/config.py` (via `app/main.py` CORS middleware)

---

## Backup

| Variable | Required | Default | Description | Example |
|----------|----------|---------|-------------|---------|
| `BACKUP_PATH` | No | `/mnt/pool/backups/brain3` | Directory where database backups are stored. Should point to a TrueNAS dataset or any persistent storage path. | `/mnt/pool/backups/brain3` |
| `BACKUP_RETENTION_DAYS` | No | `30` | Number of days to retain backups. Backups older than this are deleted automatically by the backup script. | `30` |
| `DB_CONTAINER_NAME` | No | `brain3-db` | Name of the PostgreSQL Docker container. The backup script uses this to execute `pg_dump` inside the container. | `brain3-db` |

**Used by:** `scripts/backup.sh`

---

## Environment Templates

Two example files are provided in the repository root:

### `.env.example` (development)

```
POSTGRES_USER=brain3
POSTGRES_PASSWORD=brain3_dev
POSTGRES_DB=brain3_dev
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

Copy to `.env` and use as-is for local development.

### `.env.production.example` (production)

```
POSTGRES_USER=brain3
POSTGRES_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD
POSTGRES_DB=brain3
POSTGRES_HOST=db
POSTGRES_PORT=5432
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://TRUENAS_IP:8000
BACKUP_PATH=/mnt/pool/backups/brain3
BACKUP_RETENTION_DAYS=30
```

Copy to `.env` and replace `CHANGE_ME_TO_A_STRONG_PASSWORD` and `TRUENAS_IP` with real values before deploying.

---

## How Variables Are Loaded

The API reads environment variables through Pydantic Settings (`app/config.py`), which checks:

1. Environment variables set in the shell
2. Values in the `.env` file in the project root

Shell environment variables take precedence over `.env` file values.

Docker Compose files reference `.env` via the `env_file: .env` directive, which passes variables to containers. The Postgres container uses `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` directly to initialize the database on first run.

The backup script sources `.env` from the project root as a shell file, then falls back to its own defaults for backup-specific variables.
