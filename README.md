# BRAIN 3.0

**AI-Powered Personal Operating System for ADHD**

[![CI](https://github.com/willim233/brain3/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/willim233/brain3/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

---
   
## What Is BRAIN 3.0?

BRAIN 3.0 is a personal life management system designed to work with how an ADHD brain actually functions. It pairs a structured data model with Claude as an AI partner that has full context about your goals, projects, tasks, routines, energy patterns, and behavioral history.

Most task managers treat you like a filing cabinet with legs: store things, sort things, check things off. BRAIN 3.0 is different. It tracks *how* you work — your energy cost, cognitive type, activation friction, and context requirements — so that the right task surfaces at the right time, matched to your current capacity. The system has initiative, not just memory.

This is Phase 1: the core data layer and API. Claude connects through the [Model Context Protocol (MCP)](https://github.com/willim233/brain3-mcp) and acts as a partner — not an assistant. It reads your patterns, notices neglected areas of life, pushes back when you're overloading yourself, and reasons about what actually makes sense right now. For the full design rationale, see the [System Design Document](docs/BRAIN_3_0_Design_Document.md).

## Architecture — The Seven Pillars

The data model is organized around seven core concepts that give the system a complete picture of your life:

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

## Production Deployment

To deploy BRAIN 3.0 on a home server (TrueNAS or any Docker-capable host):
```bash
git clone -b main https://github.com/WilliM233/brain3.git
cd brain3
cp .env.production.example .env
# Edit .env with strong credentials — do not use dev defaults
docker compose -f docker-compose.prod.yml up -d --build
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

You should see `brain3-postgres-dev` with status `healthy`.

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

This creates all seven pillar tables and their relationships.

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

The MCP server translates Claude's tool calls into BRAIN 3.0 API requests, giving Claude full CRUD access to all seven pillars plus filtered queries, activity logging, and reporting endpoints. See the brain3-mcp README for setup instructions.

Once connected, Claude can manage your goals, create tasks matched to your energy level, track routine streaks, log activities, and surface patterns in how you work and feel over time.

## Project Status

**v1.0.0 — Phase 1 Complete**

Phase 1 delivers the core data loop: database, API, and MCP integration. All seven pillar entities have full CRUD, filtered queries, and reporting endpoints. The system is stable — 293 tests passing, lint clean, CI green.

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Core loop — Database, FastAPI, MCP. Claude conversation only. | **Complete** |
| **Phase 2** | Proactive — Scheduler, Home Assistant integration, push notifications | Planned |
| **Phase 3** | Web UI — Mobile-first dashboard, quick entry, visual reporting | Planned |
| **Phase 4+** | Expand — New domains, voice, calendar, deeper HA automations | Planned |

**What's not here yet:** No web UI, no authentication (single-user behind firewall), no scheduler or push notifications. Those are Phase 2 and 3.

## Contributing

BRAIN 3.0 follows a ticket-driven workflow with strict branching and PR conventions. See [CLAUDE.md](CLAUDE.md) for the full developer guide, including:

- Branch strategy (`develop` -> feature branches -> PR)
- Conventional commit format
- PR template and review process
- Code standards (PEP 8, type hints, testing requirements)

## License

AGPL-3.0 — see [LICENSE](LICENSE).
