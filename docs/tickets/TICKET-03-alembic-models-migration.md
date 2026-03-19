## Summary

Configure Alembic for database migrations, define all SQLAlchemy ORM models matching the seven-pillar data model, and generate the initial migration that creates the full BRAIN 3.0 schema.

## Context

- **Scope:** ORM models + Alembic configuration + one initial migration creating all tables. This is the foundation pour — one atomic schema definition. All future schema changes get individual migrations.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model) and 5 (Database Schema)

## Deliverables

- `alembic.ini` — Alembic configuration (reads database URL from environment)
- `alembic/` directory with `env.py` configured to use app settings and models
- `app/models.py` — SQLAlchemy ORM models for all seven-pillar tables
- `alembic/versions/001_seven_pillars.py` — Initial migration creating the full schema

## Acceptance Criteria

### Alembic Configuration
- [ ] `alembic.ini` present at project root
- [ ] `alembic/env.py` imports `Base` from `app.database` and reads database URL from `app.config.settings`
- [ ] Alembic autogenerate is configured to detect model changes

### ORM Models (`app/models.py`)
All models use UUID primary keys, timestamps where specified, and explicit foreign key relationships.

- [ ] `Domain` — id, name, description, color, sort_order, created_at
- [ ] `Goal` — id, domain_id (FK → domains), title, description, status, created_at, updated_at
- [ ] `Project` — id, goal_id (FK → goals), title, description, status, deadline, progress_pct, created_at, updated_at
- [ ] `Task` — id, project_id (FK → projects, nullable), title, description, status, cognitive_type, energy_cost, activation_friction, context_required, due_date, recurrence_rule, completed_at, created_at, updated_at
- [ ] `Tag` — id, name, color
- [ ] `TaskTag` — task_id (FK → tasks), tag_id (FK → tags), composite primary key
- [ ] `Routine` — id, domain_id (FK → domains), title, description, frequency, current_streak, best_streak, last_completed, status, energy_cost, activation_friction, created_at, updated_at
- [ ] `RoutineSchedule` — id, routine_id (FK → routines), day_of_week, time_of_day, preferred_window
- [ ] `StateCheckin` — id, checkin_type, energy_level, mood, focus_level, freeform_note, context, logged_at
- [ ] `ActivityLog` — id, task_id (FK → tasks, nullable), routine_id (FK → routines, nullable), checkin_id (FK → state_checkins, nullable), action_type, notes, energy_before, energy_after, mood_rating, friction_actual, duration_minutes, logged_at

### Column Type Details
- UUID primary keys: use `postgresql.UUID(as_uuid=True)` with `uuid4` default
- Status fields: VARCHAR — use Python enums or constants to define valid values, but store as strings for flexibility
- Integer scales (energy_cost, activation_friction, mood, etc.): INTEGER with CHECK constraints for 1-5 range
- Timestamps: `TIMESTAMPTZ` — use `func.now()` for server-side defaults on created_at
- updated_at: server-side default AND `onupdate=func.now()`

### Relationships
- [ ] SQLAlchemy relationships defined for navigation (e.g. `goal.projects`, `task.tags`, `routine.schedules`)
- [ ] Cascade deletes configured appropriately (e.g. deleting a project cascades to its tasks)

### Migration
- [ ] Single initial migration creates all tables in dependency order
- [ ] `alembic upgrade head` creates the full schema successfully
- [ ] `alembic downgrade base` drops all tables cleanly
- [ ] Migration is reversible — upgrade and downgrade both work

## Technical Notes

- SQLAlchemy 2.0 style: use `DeclarativeBase`, `Mapped`, `mapped_column` (not legacy `Column()` syntax)
- Table names should be lowercase plural: `domains`, `goals`, `projects`, `tasks`, `tags`, `task_tags`, `routines`, `routine_schedule`, `state_checkins`, `activity_log`
- The `task_tags` association table can use SQLAlchemy's `Table` construct or a full model — either is fine as long as the composite PK is correct
- `recurrence_rule` on tasks stores RRULE strings (e.g. `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR`) — just a VARCHAR column, parsing happens in application logic
- Consider adding indexes on frequently queried columns: `tasks.status`, `tasks.cognitive_type`, `tasks.energy_cost`, `activity_log.logged_at`, `routines.status`

## Dependencies

- Ticket #1 (PostgreSQL running)
- Ticket #2 (FastAPI scaffolding with database connection layer and Base class)
