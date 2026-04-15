# Changelog

All notable changes to BRAIN 3.0 will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [v1.3.0] — Rules Engine (Phase 2 Stream F)

### Added
- Rules table model, migration, enum definitions (RuleEntityType, RuleMetric, RuleOperator, RuleAction), FK on notification_queue.rule_id with SET NULL cascade, Pydantic schemas with template placeholder validation (#140)
- Rules CRUD endpoints — create, list (composable filters: entity_type, enabled, notification_type, entity_id), get, update, delete (#141)

## [v1.2.0] — The Knowledge Layer

### Added
- Artifact model, migration, CRUD endpoints with content storage (512KB), versioning, parent/child hierarchy, and tagging (#94)
- Protocol model, migration, CRUD endpoints with structured JSON steps (max 50), optional artifact linking, and tagging (#95)
- Directive model, migration, CRUD endpoints with scoped priority (global/skill/agent), priority 1-10, and tagging (#96)
- Directive resolution endpoint — merges global + skill + agent directives into ordered set (#96)
- Skill model, migration, CRUD endpoints with many-to-many linking to domains, protocols, and directives (#97)
- Skill full bootstrap endpoint (`get_skill_full`) — loads complete operating context in one call (#97)
- Batch create endpoints for tasks, activity, artifacts, protocols, directives, and skills (#98)
- Batch tag attachment endpoints for tasks, activity, and artifacts (#98)
- Content migration script (`scripts/migrate_to_artifacts.py`) with --dry-run, --tag, and --api-url flags (#99)
- Seed data loading script (`scripts/seed_data.py`) with idempotent batch loading, --only and --dry-run flags (#99)
- Seed data files in `scripts/seeds/` — starter protocols, directives, and skills (#99)
- Seed data validation tests covering JSON parsing, schema compliance, cross-references, and script logic (#99)

### Fixed
- Protocol steps field type corrected from dict to list (#107)
- Protocol steps database type updated to JSON with PostgreSQL JSONB variant (#109)
- Artifact content byte-length validation at schema level for UTF-8 safety (#111)
- Batch artifact create limit reduced from 100 to 25 for content-heavy entities (#112)
- Batch task create transaction robustness — explicit rollback and per-item flush (#113)
- Protocol steps max length validation (max 50 items) (#110)
- Missing seed data — added starter protocols, directives, and skill links (#108)

## [v1.1.0] — Activity Tags

### Added
- Activity tags — `activity_tags` association table, tag/untag endpoints, tag filter on `list_activity`, reverse lookup via `list_tagged_activities` (#73)

## [v1.0.1] — Patch

### Fixed
- `progress_pct` returns 0% when completed tasks exist in project (#69)

### Changed
- Added AGPL-3.0 header notices to source files (#58)

## [v1.0.0] — The Core Loop

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
