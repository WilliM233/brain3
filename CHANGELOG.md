# Changelog

All notable changes to BRAIN 3.0 will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — Phase 1: The Core Loop

### Added
- System design document — seven-pillar data model, full schema, architecture, ADHD design principles, phased delivery plan, and resolved design decisions
- Project repository with README and documentation structure
- Docker Compose dev environment with PostgreSQL 16-alpine (#1)
- Developer setup guide with start/stop/reset procedures (#1)
- FastAPI application scaffold with config, database layer, and health check (#2)
- Requirements.txt with pinned Phase 1 dependencies (#2)
- GitHub Actions CI workflow with test and lint jobs (#13)
- Ruff linter configuration with project standards (#13)
- SQLAlchemy ORM models for all seven-pillar tables (#3)
- Alembic migration configuration with app settings integration (#3)
- Initial migration creating full BRAIN 3.0 schema (#3)
- Domain CRUD endpoints with list, detail, create, update, delete (#4)
- Goal CRUD endpoints with domain_id and status filters (#4)
- Pydantic schema pattern: Create, Update, Response, DetailResponse (#4)
- Test suite with 29 tests using SQLite in-memory database (#4)
- Project CRUD endpoints with goal_id, status, has_deadline, and overdue filters (#5)
- Task CRUD endpoints with composable ADHD-aware filters (#5)
- Task filters: energy cost range, friction range, cognitive type, context, due dates, overdue, standalone (#5)
- Pydantic validators for 1-5 scale fields (energy_cost, activation_friction) (#5)
