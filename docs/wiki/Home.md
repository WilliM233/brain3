# BRAIN 3.0 Wiki

**AI-Powered Personal Operating System for ADHD**

BRAIN 3.0 is a personal life management system designed to work with how an ADHD brain actually functions. It pairs a structured data model — organized around seven pillars that capture what matters, what needs doing, and how you're doing — with Claude as an AI partner that has full context to reason about priorities, spot avoidance patterns, and match work to your current capacity.

This is not a task manager. It's a system that has initiative, not just memory.

**Version:** 1.0.0 (Phase 1 complete)
**Status:** Core data loop — database, API, and MCP integration — is stable and deployed. 283+ tests passing, CI green, production running on TrueNAS.

---

## Wiki Pages

| Page | What's There |
|------|-------------|
| [Architecture](Architecture.md) | The seven pillars, how they relate, ADHD-specific design principles, and key design decisions |
| [API Overview](API-Overview.md) | Endpoint groups, what each covers, query filters, reporting endpoints |
| [MCP Setup](MCP-Setup.md) | How to connect Claude to BRAIN 3.0 via the Model Context Protocol |
| [Development Guide](Development-Guide.md) | Developer workflow, git conventions, PR process, testing |
| [Roadmap](Roadmap.md) | Phase 1 (complete) through Phase 4+ (vision) — what's built, what's planned, what's speculative |

## Key Resources

| Resource | Location |
|----------|----------|
| [System Design Document](../BRAIN_3_0_Design_Document.md) | Full architecture, data model, schema, and design rationale |
| [Developer Setup Guide](../dev-setup.md) | From clone to running API |
| [Deployment Guide](../deployment.md) | Production deployment on TrueNAS or any Docker host |
| [Environment Variables](../environment-variables.md) | Every env var documented |
| [CLAUDE.md](../../CLAUDE.md) | Developer standards and conventions |
| [README](../../README.md) | Project overview and quick start |

## What's Not Here Yet

Phase 1 delivers the core data loop: Claude can manage your goals, tasks, routines, and patterns through conversation. What's **not** in v1.0.0:

- No web UI (Phase 3)
- No authentication — single-user system behind a firewall (Phase 3)
- No scheduler or push notifications (Phase 2)
- No Home Assistant integration (Phase 2)
- No calendar sync (Phase 4+)

See the [Roadmap](Roadmap.md) for what's coming and when.
