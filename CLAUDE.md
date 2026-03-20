# CLAUDE.md — Claude Code Developer Guide

You are a developer on BRAIN 3.0, an AI-powered personal operating system designed for ADHD. This document is your onboarding guide — read it before writing any code.

## Project Overview

BRAIN 3.0 is a personal life management system that pairs a structured data model with Claude as an AI partner. It tracks goals, projects, tasks, routines, mindfulness check-ins, and activity patterns — all with ADHD-specific metadata like energy cost, cognitive type, and activation friction.

The system is built in phases. You are working on **Phase 1: The Core Loop** — database, FastAPI API, and MCP server. No UI, no scheduler, no push notifications yet.

### Key Resources

- **System Design Document:** `docs/BRAIN_3.0_Design_Document.docx` — the north star. Architecture, data model, schema, design decisions.
- **Ticket Specs:** `docs/tickets/TICKET-XX-*.md` — detailed specs with acceptance criteria for each ticket.
- **README:** `README.md` — project overview and architecture summary.

Always read the relevant ticket spec before starting work. If anything in the ticket is ambiguous, flag it rather than guessing.

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Database | PostgreSQL | 16+ |
| API Framework | FastAPI | Latest stable |
| ORM | SQLAlchemy | 2.0+ (DeclarativeBase, Mapped, mapped_column) |
| Migrations | Alembic | Latest stable |
| Validation | Pydantic | 2.x |
| Settings | pydantic-settings | Latest stable |
| Runtime | Python | 3.12+ |
| Testing | pytest + FastAPI TestClient | Latest stable |
| MCP | Anthropic Python MCP SDK | Latest stable |

## Git Workflow

### Branching Strategy

```
main          ← production deploys only
  └── develop ← integration branch, all features merge here
        └── feature/TICKET-XX-short-description ← one branch per ticket
```

- **Never commit directly to `main` or `develop`.**
- Create a feature branch from `develop` for each ticket.
- Open a PR from the feature branch into `develop` when complete.
- `main` is updated from `develop` only for deployment milestones.

### Branch Naming

Format: `feature/TICKET-XX-short-description`

Examples:
- `feature/TICKET-01-docker-postgres`
- `feature/TICKET-04-crud-domains-goals`
- `feature/TICKET-11-mcp-server`

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/). Reference the ticket number.

Format: `type(scope): description (#XX)`

Types:
- `feat` — new feature or endpoint
- `fix` — bug fix
- `docs` — documentation only
- `test` — adding or updating tests
- `chore` — configuration, dependencies, tooling
- `refactor` — code change that neither fixes a bug nor adds a feature

Examples:
```
feat(api): add domain CRUD endpoints (#4)
test(api): add tests for goal filtering (#4)
fix(db): correct cascade delete on projects (#5)
docs: update README with setup instructions (#1)
chore: add pytest to requirements.txt (#2)
```

### Pull Request Process

1. Ensure all tests pass before opening the PR.
2. PR targets `develop`, not `main`.
3. Title format: `TICKET-XX: Short description`
4. Fill out all sections of the PR template below.
5. Link the PR to the GitHub issue.

### PR Description Template

Every PR must include these sections:

```markdown
## Summary
[What was built, in plain language. Not a restatement of the ticket — describe the actual implementation.]

## Changes
[Files created or modified and why. Narrative, not a diff.]

## How to Verify
[Step-by-step instructions to confirm the changes work.]

## Deviations
[Anything that differs from the ticket spec and why. Write "None" if fully aligned.]

## Test Results
[Confirmation that tests pass. Include the command and summary output.]

## Acceptance Checklist
[Copy the acceptance criteria from the ticket spec. Check off each item.]
- [ ] Criteria 1
- [ ] Criteria 2
```

## GitHub Issue Management

When you start a ticket:
- Move the issue to "In Progress" on the project board (if possible via CLI)
- Create the feature branch from `develop`

When you finish a ticket:
- Ensure all acceptance criteria from the ticket spec are met
- All tests pass
- PR is opened with the full template filled out
- Reference the issue in the PR: `Closes #XX`

## Code Standards

### Python Style

- Follow PEP 8.
- Use type hints on all function signatures.
- Maximum line length: 100 characters.
- Use `pathlib` over `os.path` where applicable.
- Prefer f-strings over `.format()` or `%` formatting.

### Project Structure

```
brain3/
├── app/                    # FastAPI application
│   ├── __init__.py
│   ├── main.py             # App instance, middleware, router registration
│   ├── config.py           # Pydantic Settings
│   ├── database.py         # Engine, session, Base, get_db dependency
│   ├── models.py           # All SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── domains.py
│   │   ├── goals.py
│   │   └── ...             # One file per entity
│   └── routers/            # API route modules
│       ├── __init__.py
│       ├── domains.py
│       ├── goals.py
│       └── ...             # One file per entity
├── alembic/                # Database migrations
├── mcp/                    # MCP server (separate from FastAPI app)
├── tests/                  # All tests
│   ├── conftest.py         # Shared fixtures (test database, client, factories)
│   ├── test_domains.py
│   ├── test_goals.py
│   └── ...                 # One file per entity/feature
├── scripts/                # Utility scripts (backup, smoke test)
├── docs/                   # Design documents and ticket specs
│   ├── tickets/
│   └── ...
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── CLAUDE.md               # This file
```

### FastAPI Conventions

- One router file per entity in `app/routers/`.
- All routers registered in `app/main.py` under the `/api` prefix.
- Use `Depends(get_db)` for database session injection.
- Return appropriate HTTP status codes: 200 for success, 201 for creation, 204 for deletion, 400 for validation errors, 404 for not found.
- All endpoints should be visible and testable at `/docs`.

### Pydantic Schema Conventions

- One schema file per entity in `app/schemas/`.
- Three schemas per entity: `Create`, `Update`, `Response`.
- `Update` schemas have all fields optional (supports PATCH).
- `Response` schemas use `model_config = {"from_attributes": True}` for ORM compatibility.
- Detail responses (get by ID) extend the base response with nested children.

### SQLAlchemy Conventions

- SQLAlchemy 2.0 style: `DeclarativeBase`, `Mapped`, `mapped_column`.
- All models in `app/models.py`.
- Table names: lowercase plural (`domains`, `goals`, `tasks`).
- UUID primary keys with `uuid4` default.
- Timestamps use `TIMESTAMPTZ` with `func.now()` server defaults.
- Relationships defined for navigation with appropriate cascade configuration.

### Testing Standards

- Use pytest with FastAPI's `TestClient`.
- Test database: use a separate test database or SQLite in-memory for speed. Configure in `tests/conftest.py`.
- Every API endpoint gets at minimum:
  - Happy path test (create, read, update, delete)
  - Validation test (invalid input returns appropriate error)
  - Not found test (invalid UUID returns 404)
  - Filter tests for list endpoints
- Use fixtures for test data setup — don't rely on test ordering.
- Tests must be independent — each test creates its own data and cleans up.
- Run tests with: `pytest -v`

### Documentation

- Add docstrings to all modules, classes, and non-trivial functions.
- Keep docstrings concise — one line for simple functions, a short paragraph for complex ones.
- Update `CHANGELOG.md` with each ticket completion.
- If a ticket adds new setup steps, update `docs/dev-setup.md`.

## Environment

### Dev Environment

- PostgreSQL runs in Docker Desktop via `docker-compose.dev.yml`
- FastAPI runs natively with `uvicorn app.main:app --reload`
- Connect to: `localhost:5432` (Postgres), `localhost:8000` (API)
- Environment variables loaded from `.env` file (copy `.env.example`)

### Production/Test Environment

- Both PostgreSQL and API run as Docker containers via `docker-compose.prod.yml`
- Deployed on TrueNAS server
- API runs Alembic migrations on container startup
- Backups via cron job running `scripts/backup.sh`

## Important Design Decisions

These have been resolved and should not be revisited without discussion:

- **Database:** PostgreSQL (not SQLite) — concurrent access, LISTEN/NOTIFY, JSON columns
- **Recurrence:** RRULE strings via python-dateutil — no custom recurrence system
- **Auth:** Deferred to Phase 3 — API runs behind firewall, no auth middleware in Phase 1
- **Backups:** Nightly pg_dump with 30-day retention on TrueNAS
- **Activity logging:** Explicit only — Claude creates log entries, no automatic side effects
- **Reporting:** Four dedicated aggregation endpoints + Claude composes from CRUD filters
- **Tags:** Globally unique names (case-insensitive), get-or-create on POST

## What To Do When Stuck

- Re-read the ticket spec in `docs/tickets/`.
- Check the design document in `docs/BRAIN_3.0_Design_Document.docx`.
- If the ticket spec is ambiguous, document the ambiguity and your chosen approach in the PR under "Deviations."
- If a dependency from a previous ticket is missing or broken, flag it — don't work around it silently.
