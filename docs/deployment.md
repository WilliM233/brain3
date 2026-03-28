# Production Deployment Guide

Deploy BRAIN 3.0 to TrueNAS or any Docker-capable Linux server. This guide covers initial setup, verification, backups, MCP connection, and ongoing maintenance.

---

## Prerequisites

- **Docker Engine** and **Docker Compose V2** — TrueNAS SCALE includes both. For other Linux servers, install [Docker Engine](https://docs.docker.com/engine/install/).
- **Git** — for cloning and updating the repository.
- **`jq`** — required by the smoke test script. Install with your package manager (`apt install jq`, `apk add jq`, etc.).
- **Network access** — the API port (default 8000) must be reachable from client machines on your local network.

---

## Environment Configuration

### 1. Clone the repository

```bash
git clone https://github.com/WilliM233/brain3.git
cd brain3
git checkout develop
```

### 2. Create the environment file

```bash
cp .env.production.example .env
```

### 3. Edit `.env` with production values

```bash
nano .env
```

**Required changes:**

| Variable | What to set | Why |
|----------|------------|-----|
| `POSTGRES_PASSWORD` | A strong, unique password | The dev default is not safe for production. Generate one: `openssl rand -base64 24` |
| `CORS_ORIGINS` | `http://TRUENAS_IP:8000` | Replace `TRUENAS_IP` with your server's actual IP address |
| `BACKUP_PATH` | Your TrueNAS backup dataset path | Default is `/mnt/pool/backups/brain3` — adjust to match your pool layout |

**Do not change:**

| Variable | Production value | Why |
|----------|-----------------|-----|
| `POSTGRES_HOST` | `db` | Must match the Docker Compose service name — not `localhost` |
| `API_HOST` | `0.0.0.0` | Binds to all interfaces so the API is reachable over the network |

For the full variable reference, see [environment-variables.md](environment-variables.md).

> **Note:** `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` have no defaults in the application code. If any of these are missing from `.env`, the API will fail to start with a validation error. This is intentional — production credentials must be set explicitly.

---

## Deploy the Stack

### 1. Create the backup directory

```bash
mkdir -p /mnt/pool/backups/brain3
```

### 2. Build and start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This will:

1. Pull the PostgreSQL 16 Alpine image (first run only)
2. Build the API container from the `Dockerfile`
3. Start PostgreSQL and wait for it to pass the health check
4. The API container runs `entrypoint.sh`, which applies Alembic migrations automatically, then starts uvicorn

The production compose runs **both** PostgreSQL and the API as containers on a private bridge network (`brain3-net`). Only the API port is exposed to the host.

### 3. Verify

```bash
docker compose -f docker-compose.prod.yml ps
```

Both `brain3-db` and `brain3-api` should show as running.

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status": "healthy", "database": "connected"}
```

From another machine on the network:

```bash
curl http://TRUENAS_IP:8000/health
```

### 4. Run the smoke test

```bash
chmod +x scripts/smoke-test.sh
./scripts/smoke-test.sh http://localhost:8000
```

The smoke test creates and deletes test entities across the full API surface: domains, goals, projects, tasks, activity logging, and reporting. All test data is cleaned up automatically. Exit code 0 means all tests passed.

---

## Configure Backups

### What the backup script does

`scripts/backup.sh` runs `pg_dump` inside the `brain3-db` container, compresses the output with gzip, and stores it in `BACKUP_PATH`. It then deletes backups older than `BACKUP_RETENTION_DAYS` (default: 30).

Backup files are created with restrictive permissions (mode 600, owner-only readable) via `umask 077`. The script logs every run to `BACKUP_PATH/backup.log`.

### Manual backup

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

Verify:

```bash
ls -la /mnt/pool/backups/brain3/
```

You should see a file like `brain3_2026-03-28_020000.sql.gz`.

### Set up the TrueNAS cron job

1. Open the TrueNAS web UI
2. Navigate to **System > Advanced > Cron Jobs**
3. Click **Add**
4. Configure:
   - **Description:** BRAIN 3.0 Database Backup
   - **Command:** `/path/to/brain3/scripts/backup.sh`
   - **Run As User:** root (or a user with Docker access)
   - **Schedule:** `0 2 * * *` (daily at 2:00 AM)
5. Save

Verify the next day that a backup file appeared and the log shows success:

```bash
tail -5 /mnt/pool/backups/brain3/backup.log
```

### Restore from backup

```bash
gunzip < /mnt/pool/backups/brain3/brain3_2026-03-28_020000.sql.gz \
  | docker exec -i brain3-db psql -U brain3 brain3
```

This restores into the existing database. For a clean restore, remove the data volume and let Alembic recreate the schema on next startup:

```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
gunzip < /mnt/pool/backups/brain3/brain3_TIMESTAMP.sql.gz \
  | docker exec -i brain3-db psql -U brain3 brain3
```

---

## Connecting the MCP

The MCP server ([brain3-mcp](https://github.com/WilliM233/brain3-mcp)) runs as a Claude subprocess on your **client machine**, not on TrueNAS. It connects to the BRAIN 3.0 API over the network.

### Configure Claude Desktop

In your Claude Desktop MCP configuration, point `BRAIN3_API_URL` at your TrueNAS server:

```json
{
  "mcpServers": {
    "brain3": {
      "command": "python",
      "args": ["/path/to/brain3-mcp/mcp/server.py"],
      "env": {
        "BRAIN3_API_URL": "http://TRUENAS_IP:8000"
      }
    }
  }
}
```

Replace `TRUENAS_IP` with your server's actual IP address and `/path/to/brain3-mcp` with the path to your local clone.

### Verify MCP connectivity

Use the `health_check` MCP tool through Claude to confirm the connection. If it reports healthy, Claude has full access to the BRAIN 3.0 API.

See the [brain3-mcp README](https://github.com/WilliM233/brain3-mcp) for full setup instructions.

---

## CORS Configuration

BRAIN 3.0 uses the `CORS_ORIGINS` environment variable to control which origins are allowed to make cross-origin requests to the API.

Set this to the origin(s) that will access the API. For a TrueNAS deployment accessed by its IP:

```
CORS_ORIGINS=http://192.168.1.100:8000
```

Multiple origins are comma-separated:

```
CORS_ORIGINS=http://192.168.1.100:8000,http://192.168.1.100:3000
```

In Phase 1 (no web UI), the primary consumer is the MCP server, which makes server-side requests and is not affected by CORS. CORS configuration becomes important in Phase 3 when the web UI is added.

---

## Updating

To deploy a new version:

```bash
cd /path/to/brain3
git pull origin develop
docker compose -f docker-compose.prod.yml up -d --build
```

The API container runs Alembic migrations automatically on startup (`scripts/entrypoint.sh`), so database schema updates are applied with each deploy. Data is preserved — the PostgreSQL volume persists across container rebuilds.

If a migration fails, the API container will exit. Check the logs:

```bash
docker compose -f docker-compose.prod.yml logs api
```

---

## Troubleshooting

### Containers won't start

```bash
docker compose -f docker-compose.prod.yml logs
```

Common causes:
- **Missing `.env` file** — `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` are required with no defaults. The app will fail with a Pydantic validation error if they're missing.
- **Port conflict** — Another service on port 8000. Change `API_PORT` in `.env`.
- **Docker daemon not running** — Start Docker or verify the service is active.

### Migration fails on startup

```bash
docker compose -f docker-compose.prod.yml logs api
```

Look for Alembic error output. Common causes:
- **Database not ready** — The compose file uses a health check dependency, but if the database is slow to start, the API may attempt to migrate before it's ready. Restart the API container: `docker compose -f docker-compose.prod.yml restart api`
- **Migration conflict** — If the database schema was modified manually outside of Alembic, migration state may be inconsistent. Check `alembic current` inside the container.

### API can't reach the database

Verify `POSTGRES_HOST=db` in your `.env` — this must match the Docker Compose service name. In production, the API container connects to PostgreSQL over the `brain3-net` bridge network, not `localhost`.

### Backup script fails

- Is the database container running? `docker ps | grep brain3-db`
- Does the backup path exist and is it writable? `ls -la /mnt/pool/backups/brain3/`
- Check the backup log: `cat /mnt/pool/backups/brain3/backup.log`
- Is the container name correct? The script defaults to `brain3-db` (from `DB_CONTAINER_NAME` or the compose file's `container_name`).

### MCP can't connect to the API

1. Is the API reachable from the client machine? `curl http://TRUENAS_IP:8000/health`
2. Is port 8000 open on TrueNAS? Check firewall rules.
3. Is `BRAIN3_API_URL` set correctly in your MCP server configuration?
4. Is the MCP server running? Check Claude Desktop's MCP server status.
