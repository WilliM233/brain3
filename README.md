# BRAIN 3.0

**AI-Powered Personal Operating System for ADHD**

BRAIN 3.0 is a personal life management system designed to work with how an ADHD brain actually functions. It pairs a structured data model with Claude as an AI partner that has full context about your goals, projects, tasks, routines, energy patterns, and behavioral history.

The system has initiative, not just memory. It proactively surfaces the right task at the right time, matches work to your current capacity, tracks routines as behavioral commitments, and learns your patterns over time.

## Version History

| Version | Description |
|---------|-------------|
| 1.0 | Static HTML page with a data.js file |
| 2.0 | SQLite + Flask with Claude MCP access. Work-focused note-taking and task management. |
| **3.0** | PostgreSQL + FastAPI + Claude MCP. Full personal life operating system with ADHD-aware design. |

## Architecture

- **Database**: PostgreSQL 16+ in Docker on TrueNAS
- **API**: FastAPI (Python 3.12+) with auto-generated OpenAPI spec
- **AI Partner**: Claude via MCP with full CRUD and reasoning access
- **Notifications**: Home Assistant push notifications and voice via Assist
- **Scheduling**: APScheduler for proactive behaviors

## The Seven Pillars

The data model is organized around seven core concepts:

1. **Domains** — Life areas (House, Network, Finances, Health) as a filtering layer
2. **Goals** — Enduring outcomes that give everything else meaning
3. **Projects** — Bounded efforts with a start, end, and progress tracking
4. **Tasks** — Atoms of action with ADHD-aware metadata (energy cost, cognitive type, activation friction, context)
5. **Routines** — Behavioral patterns with streak tracking and pattern break detection
6. **Mindfulness & State** — Continuous self-awareness layer (check-ins, energy, mood, focus)
7. **Activity Log** — Record of what happened and how it felt, powering pattern recognition

## Phased Delivery

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Core loop — Database, FastAPI, MCP. Claude conversation only. | 🔨 In Progress |
| **Phase 2** | Proactive — Scheduler, HA integration, push notifications | Planned |
| **Phase 3** | Web UI — Mobile-first dashboard, quick entry, visual reporting | Planned |
| **Phase 4+** | Expand — New domains, voice, deeper HA automations, calendar | Planned |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | PostgreSQL | Concurrent access, LISTEN/NOTIFY, JSON columns, full-text search |
| API | FastAPI | OpenAPI spec maps 1:1 to MCP tools, async native |
| Recurrence | RRULE | iCalendar standard via python-dateutil, handles all edge cases |
| Auth | Deferred to Phase 3 | Single-user behind firewall; middleware pattern ready for future |
| Backups | Nightly pg_dump | 30-day retention to TrueNAS dataset |
| Migration | None | BRAIN 2.0 stays work-focused. 3.0 is a clean start. |

## Documentation

- [System Design Document](docs/BRAIN_3.0_Design_Document.md) — Full architecture, data model, schema, ADHD design principles, and resolved decisions

## License

MIT — see [LICENSE](LICENSE)
