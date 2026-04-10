# BRAIN 3.0

**AI-Powered Personal Operating System for ADHD**

[![CI](https://github.com/willim233/brain3/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/willim233/brain3/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

---
   
## What Is BRAIN 3.0?

BRAIN 3.0 is a personal life management system designed to work with how an ADHD brain actually functions. It pairs a structured data model with Claude as an AI partner that has full context about your goals, projects, tasks, routines, energy patterns, and behavioral history.

Most task managers treat you like a filing cabinet with legs: store things, sort things, check things off. BRAIN 3.0 is different. It tracks *how* you work — your energy cost, cognitive type, activation friction, and context requirements — so that the right task surfaces at the right time, matched to your current capacity. The system has initiative, not just memory.

This is Phase 1: the core data layer and API. Claude connects through the [Model Context Protocol (MCP)](https://github.com/willim233/brain3-mcp) and acts as a partner — not an assistant. It reads your patterns, notices neglected areas of life, pushes back when you're overloading yourself, and reasons about what actually makes sense right now. For the full design rationale, see the [System Design Document](docs/BRAIN_3_0_Design_Document.md).

## Architecture

The data model is organized around core entities that give the system a complete picture of your life:

### The Seven Pillars

| Pillar | What It Captures |
|--------|-----------------|
| **Domains** | Life areas (House, Health, Finances, Network) as a filtering and reporting layer |
| **Goals** | Enduring outcomes that give everything else meaning |
| **Projects** | Bounded efforts with deadlines and progress tracking, nested under goals |
| **Tasks** | Atoms of action with ADHD-aware metadata: energy cost, cognitive type, activation friction, context |
| **Routines** | Behavioral commitments with streak tracking and pattern break detection |
| **Check-ins** | Energy, mood, and focus snapshots — the continuous self-awareness layer |
| **Activity Log** | What happened and how it felt, powering pattern recognition over time |

Everything flows from domains down through goals and projects to tasks, with routines running in parallel and the activity log recording what actually happened. Claude uses this full picture to reason about priorities, spot avoidance patterns, and match work to capacity.

### The Knowledge Layer (v1.2.0)

v1.2.0 adds four entities that give the system persistent knowledge — documents, procedures, behavioral rules, and operating modes that carry context across sessions.

| Entity | What It Captures |
|--------|-----------------|
| **Artifacts** | Living reference documents — briefs, templates, specs, prompts. Versioned, taggable, with parent/child hierarchy and 512KB content storage. |
| **Protocols** | Step-by-step procedures stored as structured JSON. Linked to an optional source artifact. Versioned on update. |
| **Directives** | Behavioral rules and guardrails with scoped priority (global, skill, or agent). The system's operating constraints. |
| **Skills** | Named operating modes that bundle domains, protocols, and directives into a loadable context. The `get_skill_full` endpoint bootstraps an entire working context in one call. |

Skills tie the knowledge layer together. A skill like "session-startup" links to the domains it covers, the protocols it follows, and the directives that constrain it — giving Claude a complete operating context loaded in a single request.

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12+ |
| API Framework | FastAPI | 0.135+ |
| Database | PostgreSQL | 16+ |
| ORM | SQLAlchemy | 2.0+ |
| Migrations | Alembic | latest stable |
| Validation | Pydantic | 2.x |
| MCP Transport | Anthropic Python MCP SDK | latest stable |
| Deployment | Docker on TrueNAS | Docker Compose v2 |

## Deployment

BRAIN 3.0 supports three environments. Each has its own compose file and can coexist on the same host:

| Environment | Compose File | API Port | Use Case |
|-------------|-------------|----------|----------|
| Dev | `docker-compose.dev.yml` | 8000 (native) | Local development — postgres only, uvicorn runs natively |
| Test | `docker-compose.test.yml` | 8100 | UAT — full stack in Docker from `develop` branch |
| Prod | `docker-compose.prod.yml` | 8000 | Production — full stack in Docker from `main` branch |

### Production

```bash
git clone -b main https://github.com/WilliM233/brain3.git
cd brain3
cp .env.production.example .env
# Edit .env with strong credentials — do not use dev defaults
docker compose -f docker-compose.prod.yml up -d --build
```

### Test Stack

```bash
git clone -b develop https://github.com/WilliM233/brain3.git brain3-test
cd brain3-test
cp .env.test.example .env
# Edit .env with credentials
docker compose -f docker-compose.test.yml up -d --build
# Verify: curl http://localhost:8100/health
```

## Quick Start (Development)

### Prerequisites

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- **Docker Desktop** — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL)
- **Git** — [git-scm.com](https://git-scm.com/)

### 1. Clone and configure

```bash
git clone https://github.com/willim233/brain3.git
cd brain3
cp .env.example .env
```

The default `.env` values work for local development — no changes needed.

### 2. Start PostgreSQL

```bash
docker compose -f docker-compose.dev.yml up -d
```

Verify it's running:

```bash
docker compose -f docker-compose.dev.yml ps
```

You should see the postgres service with status `healthy`.

### 3. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run database migrations

```bash
alembic upgrade head
```

This creates all tables — the seven pillars, knowledge layer entities, tagging associations, and skill link tables.

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

### 6. Verify

Open [http://localhost:8000/health](http://localhost:8000/health) — you should see:

```json
{"status": "healthy", "database": "connected"}
```

The interactive API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

## Connecting Claude (MCP)

BRAIN 3.0's primary interface is Claude, connected through the Model Context Protocol. The MCP server lives in a separate repository:

**[brain3-mcp](https://github.com/willim233/brain3-mcp)** — Claude MCP integration for BRAIN 3.0

The MCP server translates Claude's tool calls into BRAIN 3.0 API requests, giving Claude full access to all entities — the seven pillars, knowledge layer, batch operations, and reporting endpoints. 109 tools covering 109 API endpoints. See the brain3-mcp README for setup instructions.

Once connected, Claude can manage your goals, create tasks matched to your energy level, track routine streaks, log activities, load operating contexts via skills, and surface patterns in how you work and feel over time.

## Project Status

**v1.2.0 — The Knowledge Layer**

The latest release adds persistent knowledge entities (Artifacts, Protocols, Directives, Skills), a batch API for bulk operations, and a seed framework for reproducible data loading. 109 API endpoints, 621 tests passing, lint clean, CI green.

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Core loop — Database, FastAPI, MCP. Seven pillars, CRUD, reporting. | **Complete** (v1.0.0) |
| **v1.1.0** | Activity tags — tagging on activity log entries | **Complete** |
| **v1.2.0** | Knowledge layer — Artifacts, Protocols, Directives, Skills, Batch API, seed framework | **Complete** |
| **Phase 2** | Proactive — Scheduler, Home Assistant integration, push notifications | Planned |
| **Phase 3** | Web UI — Mobile-first dashboard, quick entry, visual reporting | Planned |
| **Phase 4+** | Expand — New domains, voice, calendar, deeper HA automations | Planned |

**What's not here yet:** No web UI, no authentication (single-user behind firewall), no scheduler or push notifications. Those are Phase 2 and 3.

## Batch API

v1.2.0 introduces batch endpoints for bulk operations. All batch creates are atomic — the entire batch succeeds or rolls back.

**Batch create** (`POST /api/{entity}/batch`): Tasks, Activity, Artifacts (max 25), Protocols, Directives, Skills (max 100 each unless noted).

**Batch tag** (`POST /api/{entity}/{id}/tags/batch`): Attach up to 100 tags in a single request. Supported on Tasks, Activity, and Artifacts.

## Seed Framework

Reproducible data seeding for bootstrapping new environments with starter protocols, directives, and skills.

```bash
# Load all seed data
python scripts/seed_data.py

# Preview without writing
python scripts/seed_data.py --dry-run

# Load a specific entity type
python scripts/seed_data.py --only protocols
```

Seed data lives in `scripts/seeds/` as JSON files. The loader is idempotent (checks by name before creating) and resolves cross-references — skills reference protocols and directives by name, resolved to IDs at load time. Loading order: protocols → directives → skills.

A content migration script (`scripts/migrate_to_artifacts.py`) is also available for migrating existing reference documents into the Artifacts entity.

## Contributing

BRAIN 3.0 follows a ticket-driven workflow with strict branching and PR conventions. See [CLAUDE.md](CLAUDE.md) for the full developer guide, including:

- Branch strategy (`develop` -> feature branches -> PR)
- Conventional commit format
- PR template and review process
- Code standards (PEP 8, type hints, testing requirements)

## License

AGPL-3.0 — see [LICENSE](LICENSE).
