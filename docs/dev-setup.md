# Developer Setup Guide

## Prerequisites

- **Docker Desktop** — [Install](https://docs.docker.com/desktop/install/windows-install/) and ensure it is running.
- **Git** — For cloning the repository.
- **Python 3.12+** — For running the FastAPI app locally (later tickets).

## Initial Setup

1. Clone the repository:

   ```bash
   git clone <repo-url> brain3
   cd brain3
   ```

2. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` if you need to change the default values (port, credentials, etc.).

## Database — Start / Stop / Reset

### Start

```bash
docker compose -f docker-compose.dev.yml up -d
```

### Verify

```bash
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U brain3
```

You should see: `/var/run/postgresql:5432 - accepting connections`

### Stop (preserves data)

```bash
docker compose -f docker-compose.dev.yml down
```

### Reset (wipe all data)

```bash
docker compose -f docker-compose.dev.yml down -v
```

The `-v` flag removes the `brain3_dev_data` volume, deleting all database contents.

## Connecting to the Database

| Setting  | Value           |
|----------|-----------------|
| Host     | `localhost`     |
| Port     | `5432`          |
| Database | `brain3_dev`    |
| User     | `brain3`        |
| Password | `brain3_dev`    |

### psql (from inside the container)

```bash
docker compose -f docker-compose.dev.yml exec postgres psql -U brain3 -d brain3_dev
```

### Connection string

```
postgresql://brain3:brain3_dev@localhost:5432/brain3_dev
```

Use this in `.env` for the FastAPI app (added in a later ticket).
