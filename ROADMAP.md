# BRAIN 3.0 — Roadmap

> *An AI-powered personal operating system for ADHD.*
> *Project Flux Meridian · AGPL-3.0*

This document tracks the release plan for BRAIN 3.0, from the shipped Core Loop through the proactive future. Each release has a clear identity, a bounded scope, and a reason it comes in the order it does.

For individual issue details, see the [GitHub Issues](https://github.com/WilliM233/brain3/issues) page. For the original system design, see the [Design Document](docs/wiki/Architecture.md).

---

## Release Timeline

| Version | Name | Focus | Status |
|---------|------|-------|--------|
| **v1.0.0** | The Core Loop | Seven-pillar data model, full CRUD API, MCP integration, TrueNAS deployment | ✅ Shipped |
| **v1.0.1** | Patch | Bug fix + license housekeeping | ✅ Shipped |
| **v1.1.0** | Activity Tags | Tagging on activity log entries | ✅ Shipped |
| **v1.2.0** | The Knowledge Layer | Artifacts, Protocols, Directives, Skills, Batch API, seed framework | ✅ Shipped |
| **v1.3.0** | Graduated Scaffolding | Routines that phase out support as habits solidify | 📐 Needs Design |
| **v2.0.0** | The System Gets Proactive | Scheduler, Home Assistant integration, push notifications | 🔭 Planned |
| **v3.0.0** | Browse and Manage Directly | Mobile-first web UI, dashboard, visual reporting | 🔭 Planned |
| **v4.0.0+** | Expand and Integrate | Finances, health, voice, calendar, deeper HA | 🔭 Future |

---

## v1.0.0 — The Core Loop ✅

**Shipped:** March 29, 2026

The foundation. PostgreSQL + FastAPI + MCP. All seven pillars deployed: Domains, Goals, Projects, Tasks (with ADHD-specific metadata), Routines, Check-ins, and Activity Log. 53 API endpoints, 53 MCP tools, composable task filters, routine streak tracking, four reporting endpoints, Docker deployment, CI pipeline, automated backups.

Quality: 293 unit tests, 131 UAT tests (128 pass, 0 fail, 3 partial — natural language variance, not bugs). Full QA review (13 findings, all resolved). Full security review (9 findings, all resolved).

**Remaining ceremony:** Regina Meridian release pass to formally close v1.0.0 (develop → main promotion, version tag, release notes).

---

## v1.0.1 — Patch ✅

**Shipped**

Bug fix + license housekeeping. Progress percentage fix and AGPL-3.0 header notices.

---

## v1.1.0 — Activity Tags ✅

**Shipped**

Tags on activity log entries. Mirrors the `task_tags` pattern — `activity_tags` association table, tag/untag endpoints, tag filter on `list_activity`, reverse lookup. Unlocked session handoff filtering, FluxNook media reviews, and flexible life logging.

---

## v1.2.0 — The Knowledge Layer ✅

**Shipped:** April 2026

**Scope:** Persistent knowledge entities, batch API, and seed framework. The release that gives the system memory across sessions.

**What shipped:**
- **Artifacts** — versioned reference documents with content storage (512KB), parent/child hierarchy, 7 type categories, tagging
- **Protocols** — structured step-by-step procedures (JSON steps, max 50), linked to optional source artifacts, auto-versioned
- **Directives** — behavioral rules with scoped priority (global/skill/agent), priority 1-10, directive resolution endpoint
- **Skills** — named operating modes with many-to-many links to domains, protocols, and directives; `get_skill_full` bootstrap endpoint
- **Batch API** — atomic bulk create for 6 entity types, batch tag attachment for 3 entity types
- **Seed framework** — idempotent JSON-based data loading with cross-reference resolution, CLI tooling
- **Content migration** — script for migrating existing reference documents into Artifacts
- **109 API endpoints**, 621 tests, QA and security reviews complete

---

## v1.3.0 — Graduated Scaffolding 📐

**Scope:** Routines that phase out support as habits solidify.

| Issue | Title | Type |
|-------|-------|------|
| [#76](https://github.com/WilliM233/brain3/issues/76) | Graduated scaffolding — routines that phase out support as habits solidify | Feature |

**The model:**
1. **Tracking only** — User reports completion. BRAIN logs it. The streak builds silently.
2. **Gentle accountability** — If the streak breaks, BRAIN notices and asks what happened. Not guilt — curiosity.
3. **Autonomy** — Once the streak hits a configurable threshold, the routine enters "graduated" status. The habit lives in the body now, not the system.

**Core principle:** BRAIN's job is to make itself unnecessary for each individual habit. Success is measured by what doesn't need tracking anymore.

**Why between 1.2 and 2.0:** Graduated scaffolding is a behavioral design that bridges the current routine system and the Phase 2 proactive scheduler. It can be implemented with the existing routine infrastructure (new status, threshold logic, streak evaluation) but its full expression — BRAIN *noticing* a break and reaching out — depends on the scheduler. v1.3.0 delivers the data model and Phase 1 behavior; v2.0.0 completes the loop.

**Open design work:** Graduation threshold defaults, "one habit at a time" enforcement, Phase 2 integration points.

---

## v2.0.0 — The System Gets Proactive 🔭

**Scope:** Internal scheduler, Home Assistant integration, push notifications.

BRAIN transitions from responsive to proactive. Instead of waiting to be asked, the system reaches out: morning briefings, accountability nudges, deadline alerts, streak break notices, and routine reminders delivered through Home Assistant push notifications.

**Key components:**
- **Scheduler** (APScheduler or cron) — evaluates routines, deadlines, and patterns on a configurable cadence
- **Home Assistant integration** — push notifications via companion app, voice via Assist, webhook-driven automations
- **Remote MCP** — persistent SSE/HTTP service on TrueNAS for cross-device access (currently stdio/desktop only)
- **Graduated scaffolding completion** — Phase 2 behavior (proactive streak break detection) built on v1.3.0's data model

**Depends on:** v1.3.0 (graduated scaffolding data model), Home Assistant environment setup.

---

## v3.0.0 — Browse and Manage Directly 🔭

**Scope:** Lightweight mobile-first web UI.

Dashboard view of goals, projects, and tasks. Quick entry for logging without a conversation. Reporting visualizations for pattern recognition. Authentication layer (API key, OAuth, or basic auth) added at this phase since the system is exposed beyond localhost.

---

## v4.0.0+ — Expand and Integrate 🔭

**Scope:** New life domains and deeper integrations.

Finances, health tracking, voice interface through Home Assistant Assist, deeper HA automations (ambient reminders via lights, display panels), calendar integration. The system grows one domain at a time.

---

## Design Principles

These guide every release decision:

- **Friction awareness** — If a feature creates friction, it doesn't ship until the friction is designed out.
- **Workarounds are feature requests** — Any time the data model requires a workaround, file a feature request instead of implementing the hack.
- **Graduated scaffolding** — The system builds capacity, not dependency. Success is autonomy.
- **Batch-first** — Every new entity gets batch operations designed alongside it from day one.
- **One thing at a time** — Releases are small, bounded, and shippable. Scope creep is the enemy.
- **Low friction weeks exist** — Sustainable pace is a project value. The roadmap accommodates energy, not just ambition.

---

## How Releases Work

1. **Issues** live in [GitHub Issues](https://github.com/WilliM233/brain3/issues) with labels and milestone assignments.
2. **Milestones** in GitHub track progress per release (percentage complete, open/closed issues).
3. **Backlog** items without a milestone assignment live in the BRAIN backlog project, waiting to be pulled into a release.
4. **Branch workflow:** feature branches → `develop` → `main` (deploys only). PRs at every stage.
5. **Release pipeline:** Pre-hardening → QA → Security → Bug resolution → Documentation → Release prep. Scaled to release size.
6. **Versioning:** Semantic versioning via git tags. Patch (x.x.1) for fixes, minor (x.1.0) for features, major (x.0.0) for phase transitions.

---

*Last updated: April 10, 2026*
*BRAIN 3.0 · Project Flux Meridian*
