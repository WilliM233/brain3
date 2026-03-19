## Summary

Scaffold the FastAPI application structure with configuration management, database connection layer, and a health check endpoint. This provides the skeleton that all subsequent endpoint tickets will build on.

## Context

- **Environment:** Local dev — FastAPI runs natively with `uvicorn --reload`, connects to PostgreSQL from ticket #1
- **Scope:** Framework and wiring only. No ORM models, no entity endpoints. Those come in tickets #3-8.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 2 (Architecture) and 3 (Technology Stack)

## Deliverables

- `app/` directory structure with `__init__.py` files
- `app/config.py` — Application settings via Pydantic Settings
- `app/database.py` — SQLAlchemy engine, session factory, `get_db` dependency
- `app/main.py` — FastAPI app instance with health check endpoint
- `requirements.txt` — Pinned Phase 1 Python dependencies
- `app/routers/` — Empty directory (endpoints added in tickets #4-8)

## Acceptance Criteria

- [ ] `app/config.py` uses Pydantic Settings to read from `.env`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `API_HOST`, `API_PORT`
- [ ] `app/config.py` constructs the `database_url` property from individual Postgres settings
- [ ] `app/database.py` creates a SQLAlchemy engine with `pool_pre_ping=True`
- [ ] `app/database.py` provides a `SessionLocal` factory and a `get_db` FastAPI dependency
- [ ] `app/database.py` defines a `Base` declarative base class for future ORM models
- [ ] `app/main.py` creates the FastAPI app instance with title "BRAIN 3.0" and appropriate description
- [ ] `app/main.py` includes CORS middleware (permissive for dev — restrict in production)
- [ ] `GET /health` returns `{"status": "healthy", "database": "connected"}` when Postgres is reachable
- [ ] `GET /health` returns `{"status": "unhealthy", "database": "disconnected"}` with a 503 when Postgres is unreachable
- [ ] `requirements.txt` includes pinned versions: fastapi, uvicorn[standard], sqlalchemy, psycopg2-binary, alembic, pydantic, pydantic-settings, python-dateutil, python-dotenv
- [ ] API starts with `uvicorn app.main:app --reload` and serves interactive docs at `/docs`
- [ ] `app/routers/` directory exists with an `__init__.py` (empty, ready for endpoint modules)

## Technical Notes

- Python 3.12+ target
- SQLAlchemy 2.0 style (DeclarativeBase, not legacy declarative_base())
- Sync sessions for Phase 1 simplicity — async can be added later if needed
- The health check should actually test the database connection (e.g. `SELECT 1`), not just assume it works
- FastAPI's auto-generated OpenAPI spec at `/docs` will eventually become the basis for the MCP tool contract

## Dependencies

- Ticket #1 (Docker Compose + PostgreSQL must be running)
