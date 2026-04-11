# Roadmap

BRAIN 3.0 is built in phases. Each phase adds a capability layer to the system without requiring changes to previous phases.

---

## Phase 1 — The Core Loop ✓

**Status: Complete** (v1.0.0, March 2026)

The data foundation and conversational interface. Claude has full read/write access to all seven pillar entities through the MCP.

### What's Delivered

- **PostgreSQL database** on Docker with all seven pillar tables and relationships
- **FastAPI REST API** with full CRUD, composable query filters, and four reporting endpoints
- **Claude MCP integration** via [brain3-mcp](https://github.com/WilliM233/brain3-mcp) — 57 tools covering all entities
- **ADHD-aware task metadata** — energy cost, cognitive type, activation friction, context requirements
- **Routine system** with streak tracking, flexible scheduling, and pattern break detection
- **Activity logging** with subjective metadata (energy before/after, actual friction, mood)
- **Reporting** — activity summaries, domain balance, routine adherence, friction analysis
- **Production deployment** on TrueNAS with Docker Compose, automated migrations, nightly backups
- **CI pipeline** — 293 tests, Ruff lint, GitHub Actions
- **Documentation** — README, developer setup, deployment guide, environment reference, wiki

---

## v1.1.0 — Activity Tags ✓

**Status: Complete**

Tagging on activity log entries. Mirrors the existing task tags pattern — `activity_tags` association table, tag/untag endpoints, tag filter on `list_activity`, and reverse lookup via `list_tagged_activities`.

---

## v1.2.0 — The Knowledge Layer ✓

**Status: Complete** (April 2026)

Persistent knowledge entities, batch API, and seed framework. The system gains memory that persists across sessions.

### What's Delivered

- **Artifacts** — versioned reference documents with content storage (512KB), parent/child hierarchy, tagging, and 7 type categories
- **Protocols** — structured step-by-step procedures (JSON steps, max 50), linked to optional source artifacts, versioned on update
- **Directives** — behavioral rules with scoped priority (global/skill/agent), priority 1-10, and directive resolution endpoint
- **Skills** — named operating modes with many-to-many links to domains, protocols, and directives; `get_skill_full` bootstrap endpoint
- **Batch API** — atomic bulk create for 6 entity types (tasks, activity, artifacts, protocols, directives, skills) and batch tag attachment for 3 entity types
- **Seed framework** — idempotent JSON-based data loading with cross-reference resolution, CLI flags for dry-run and entity filtering
- **Content migration** — script for migrating existing reference documents into the Artifacts entity
- **Expanded tagging** — tags on artifacts, protocols, and directives with reverse lookups from tag to entity
- **MCP coverage** — 109 tools (52 new) covering all new entities and batch operations
- **Quality** — 621 tests passing, lint clean, CI green, QA and security reviews complete

### What's Not Here

- No web UI — interaction is through Claude conversation only
- No authentication — single-user system behind a firewall
- No scheduler — the system responds but doesn't initiate
- No push notifications or voice interface
- No Home Assistant integration

---

## Phase 2 — The System Gets Proactive

**Status: Planned**

The system transitions from responsive to proactive. Claude reaches out rather than waiting to be asked.

### Planned Capabilities

- **Internal scheduler** (APScheduler or cron-based) for time-triggered behaviors
- **Home Assistant integration** — push notifications via the companion app, voice interface via Assist
- **Morning briefings** — daily summary of what's on deck, routine status, and relevant context
- **Accountability nudges** — missed routine alerts, deadline warnings, neglected domain flags
- **MCP composite tools** — higher-level operations that combine multiple API calls (e.g., "complete routine + log activity + check in" as a single tool)

### What This Changes

Phase 1 BRAIN waits to be asked. Phase 2 BRAIN notices things and reaches out — a missed routine, an approaching deadline, an area of life that hasn't gotten attention in weeks. The ADHD brain struggles with object permanence; Phase 2 addresses this by making the system visible through the channels you already check.

---

## Phase 3 — Browse and Manage Directly

**Status: Planned**

A lightweight web UI for when you want to see your world at a glance without having a conversation.

### Planned Capabilities

- **Mobile-first web dashboard** — goals, projects, tasks, routines at a glance
- **Quick entry** — add tasks and log activities without a full conversation
- **Visual reporting** — charts and trend lines for pattern recognition (energy cycles, routine adherence, friction analysis)
- **Authentication** — API key, OAuth, or basic auth middleware (required once the UI exposes the system beyond localhost)

### What This Changes

Phase 3 adds a visual layer that complements the conversational interface. Claude remains the richer interface for reasoning and pattern interpretation; the UI provides at-a-glance awareness and low-friction data entry.

---

## Phase 4+ — Expand and Integrate

**Status: Vision**

Everything beyond Phase 3 is speculative. These are directions, not commitments.

### Possible Directions

- **New life domains** — finances (budget tracking, bill management), health (medication, exercise, sleep)
- **Voice interface** — deeper Home Assistant Assist integration for hands-free interaction
- **Calendar integration** — sync with external calendars for deadline awareness and scheduling
- **Ambient reminders** — Home Assistant automations (lights, display panels) for non-intrusive nudges
- **Multi-device sync** — consistent experience across devices
- **Pattern learning** — the system improves its friction and energy predictions over time based on activity log history

### What's Speculative Here

All of it. Phase 4+ items are ideas that emerged from the design process and represent where the system *could* go. They will be scoped and prioritized based on what actually matters once Phases 1-3 are stable and in daily use.

---

## How Phases Build on Each Other

```
Phase 1 (v1.0–1.2): Data + API + Knowledge layer + Claude conversation
Phase 2:            + Scheduler + Notifications + Home Assistant
Phase 3:            + Web UI + Auth + Visual reporting
Phase 4+:           + New domains + Voice + Calendar + Ambient
```

Each phase adds a capability layer without modifying the previous one. The API and data model from Phase 1 serve all future phases. The MCP contract extends in Phase 2 with composite tools. The reporting gets a visual representation in Phase 3.
