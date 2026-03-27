# BRAIN 3.0 — Deployment Guide

Production deployment of BRAIN 3.0 on TrueNAS (or any Docker-capable host).

## Prerequisites

- Docker Engine and Docker Compose V2 (TrueNAS SCALE includes these)
- Git (to clone/update the repository)
- `jq` (for the smoke test script)
- Network access: API port (default 8000) must be reachable from client machines

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/WilliM233/brain3.git
cd brain3
git checkout develop
```

### 2. Configure Environment

```bash
cp .env.production.example .env
```

Edit `.env` and set:
- **`POSTGRES_PASSWORD`** — use a strong, unique password
- **`BACKUP_PATH`** — TrueNAS dataset for backups (e.g., `/mnt/pool/backups/brain3`)
- Adjust `API_PORT` if 8000 conflicts with another service

### 3. Create the Backup Directory

```bash
mkdir -p /mnt/pool/backups/brain3
```

## Starting the Stack

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This will:
1. Pull the PostgreSQL 16 image (first run only)
2. Build the API container from the Dockerfile
3. Start PostgreSQL and wait for it to be healthy
4. Run Alembic migrations automatically
5. Start the uvicorn API server

### Verify

```bash
# Check both containers are running and healthy
docker compose -f docker-compose.prod.yml ps

# Check API health
curl http://localhost:8000/health

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

## Stopping the Stack

```bash
# Stop containers (preserves database data)
docker compose -f docker-compose.prod.yml down

# Stop and DELETE all data (destructive — use with caution)
docker compose -f docker-compose.prod.yml down -v
```

## Updating the Application

```bash
git pull origin develop
docker compose -f docker-compose.prod.yml up -d --build
```

Alembic migrations run automatically on API container startup, so database schema updates are applied with each deploy.

## Backup Configuration

### Manual Backup

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

The script will:
- Dump the PostgreSQL database from the `brain3-db` container
- Compress it as `brain3_YYYY-MM-DD_HHMMSS.sql.gz`
- Store it in `BACKUP_PATH` (from `.env`)
- Delete backups older than `BACKUP_RETENTION_DAYS` (default: 30)
- Log results to `BACKUP_PATH/backup.log`

### TrueNAS Cron Setup

1. Open TrueNAS web UI
2. Navigate to **System → Advanced → Cron Jobs**
3. Click **Add**
4. Configure:
   - **Description:** BRAIN 3.0 Database Backup
   - **Command:** `/path/to/brain3/scripts/backup.sh`
   - **Run As User:** root (or a user with Docker access)
   - **Schedule:** `0 2 * * *` (daily at 2:00 AM)
5. Save and verify the next day that a backup file appears in your backup path

### Restore from Backup

```bash
gunzip < /mnt/pool/backups/brain3/brain3_2026-03-27_020000.sql.gz \
  | docker exec -i brain3-db psql -U brain3 brain3
```

> **Note:** This restores into the existing database. For a clean restore, drop and
> recreate the database first, or let Alembic handle schema creation on a fresh volume.

## Smoke Testing

Run the automated smoke test to validate the full API surface:

```bash
chmod +x scripts/smoke-test.sh
./scripts/smoke-test.sh http://localhost:8000
```

The script tests: health check, domain CRUD, goal creation, project creation, task creation, activity logging, activity summary report, and cleanup of all test entities.

Exit code 0 means all tests passed. Exit code 1 means a failure occurred.

## MCP Server Connectivity

The MCP server (`brain3-mcp`) runs as a Claude subprocess on your **client machine**, not on TrueNAS. It connects to the API over the network.

### Configure the MCP Server

Set the `BRAIN3_API_URL` environment variable to point at your TrueNAS host:

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

Replace `TRUENAS_IP` with the actual IP address of your TrueNAS server.

### Verify MCP Connectivity

Use the `health_check` MCP tool through Claude to confirm the MCP server can reach the API.

## Troubleshooting

### Containers won't start

```bash
docker compose -f docker-compose.prod.yml logs
```

Check for:
- Missing `.env` file or unconfigured variables
- Port conflicts (another service on port 8000)
- Docker daemon not running

### Migration fails on startup

```bash
docker compose -f docker-compose.prod.yml logs api
```

Look for Alembic error output. Common causes:
- Database not ready yet (should be handled by health check dependency, but check)
- Migration conflict from manual schema changes

### API can't reach database

Verify `POSTGRES_HOST=db` in `.env` — this must match the Docker Compose service name, not `localhost`.

### Backup script fails

- Verify the `brain3-db` container is running: `docker ps`
- Verify backup path exists and is writable: `ls -la /mnt/pool/backups/brain3/`
- Check the backup log: `cat /mnt/pool/backups/brain3/backup.log`

### MCP can't connect to API

- Verify the API is reachable from the client machine: `curl http://TRUENAS_IP:8000/health`
- Check firewall rules — port 8000 must be open on TrueNAS
- Verify `BRAIN3_API_URL` is set correctly in your MCP configuration
