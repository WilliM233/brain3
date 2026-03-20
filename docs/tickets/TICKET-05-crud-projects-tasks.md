## Summary

Build the CRUD API endpoints for Projects and Tasks — the middle and bottom of the BRAIN 3.0 hierarchy. Tasks are the core entity of the system and carry all ADHD-specific metadata. The task list endpoint supports rich composable filtering so Claude can query by energy, cognitive type, friction, context, and status.

## Context

- **Scope:** Projects and Tasks CRUD with composable task filters. Follows the patterns established in ticket #4.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model: Pillars 3-4) and 5 (Database Schema: projects, tasks tables)

## Deliverables

- `app/schemas/projects.py` — Pydantic schemas for Project
- `app/schemas/tasks.py` — Pydantic schemas for Task
- `app/routers/projects.py` — Project CRUD endpoints
- `app/routers/tasks.py` — Task CRUD endpoints
- Router registration in `app/main.py`

## Pydantic Schemas

### Project Schemas

**ProjectCreate:**
- `goal_id` (UUID, required)
- `title` (str, required)
- `description` (str, optional)
- `status` (str, optional — default "not_started". Valid: not_started, active, blocked, completed, abandoned)
- `deadline` (date, optional)

**ProjectUpdate:**
- All fields from ProjectCreate, all optional

**ProjectResponse:**
- All fields plus `id` (UUID), `progress_pct` (int), `created_at`, `updated_at`

**ProjectDetailResponse:**
- Extends ProjectResponse with `tasks` (list of TaskResponse)

### Task Schemas

**TaskCreate:**
- `project_id` (UUID, optional — nullable for standalone tasks)
- `title` (str, required)
- `description` (str, optional)
- `status` (str, optional — default "pending". Valid: pending, active, completed, skipped, deferred)
- `cognitive_type` (str, optional. Valid: hands_on, communication, decision, errand, admin, focus_work)
- `energy_cost` (int, optional — 1-5 scale)
- `activation_friction` (int, optional — 1-5 scale)
- `context_required` (str, optional. Examples: at_home, at_computer, at_store, needs_tools, phone, anywhere)
- `due_date` (date, optional)
- `recurrence_rule` (str, optional — RRULE string)

**TaskUpdate:**
- All fields from TaskCreate, all optional

**TaskResponse:**
- All fields plus `id` (UUID), `completed_at` (datetime, nullable), `created_at`, `updated_at`

**TaskDetailResponse:**
- Extends TaskResponse with `tags` (list of TagResponse — will be empty until ticket #6 adds tag endpoints, but schema should be ready)

## API Endpoints

### Projects — `/api/projects`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/projects` | Create a project | ProjectResponse |
| GET | `/api/projects` | List projects (with filters) | list[ProjectResponse] |
| GET | `/api/projects/{id}` | Get project with tasks | ProjectDetailResponse |
| PATCH | `/api/projects/{id}` | Partial update | ProjectResponse |
| DELETE | `/api/projects/{id}` | Delete project | 204 No Content |

**Project list filters:**
- `?goal_id=UUID` — filter by parent goal
- `?status=active` — filter by status
- `?has_deadline=true` — only projects with deadlines set
- `?overdue=true` — projects past their deadline that aren't completed/abandoned

### Tasks — `/api/tasks`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/tasks` | Create a task | TaskResponse |
| GET | `/api/tasks` | List tasks (with filters) | list[TaskResponse] |
| GET | `/api/tasks/{id}` | Get task with tags | TaskDetailResponse |
| PATCH | `/api/tasks/{id}` | Partial update | TaskResponse |
| DELETE | `/api/tasks/{id}` | Delete task | 204 No Content |

**Task list filters — all optional, composable:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | UUID | Tasks belonging to a specific project |
| `standalone` | bool | Tasks with no project (project_id is null) |
| `status` | str | Filter by status (pending, active, completed, skipped, deferred) |
| `cognitive_type` | str | Filter by cognitive type |
| `energy_cost_min` | int | Minimum energy cost (inclusive) |
| `energy_cost_max` | int | Maximum energy cost (inclusive) |
| `friction_min` | int | Minimum activation friction (inclusive) |
| `friction_max` | int | Maximum activation friction (inclusive) |
| `context_required` | str | Filter by context |
| `due_before` | date | Tasks due on or before this date |
| `due_after` | date | Tasks due on or after this date |
| `overdue` | bool | Tasks past due_date that aren't completed/skipped |

**Example composed queries Claude would make:**
- `GET /api/tasks?energy_cost_max=2&context_required=at_home&status=pending` — "low energy tasks I can do at home"
- `GET /api/tasks?cognitive_type=hands_on&friction_max=2` — "easy to start hands-on work"
- `GET /api/tasks?overdue=true` — "what have I let slip?"
- `GET /api/tasks?project_id=UUID&status=pending` — "what's left on this project?"

## Acceptance Criteria

- [ ] Pydantic schemas defined for Project (Create, Update, Response, DetailResponse)
- [ ] Pydantic schemas defined for Task (Create, Update, Response, DetailResponse)
- [ ] All five Project endpoints working and returning correct response schemas
- [ ] All five Task endpoints working and returning correct response schemas
- [ ] `GET /api/projects/{id}` returns project with nested tasks list
- [ ] `GET /api/tasks/{id}` returns task with nested tags list (empty until ticket #6)
- [ ] Project list filters working: goal_id, status, has_deadline, overdue
- [ ] Task list filters working: all parameters from the filter table above
- [ ] Task filters are composable — multiple filters combine with AND logic
- [ ] Range filters work correctly: `energy_cost_min=1&energy_cost_max=2` returns tasks with energy cost 1 or 2
- [ ] `overdue` filter correctly compares due_date against current date and excludes completed/skipped tasks
- [ ] Tasks with null `project_id` are valid (standalone tasks)
- [ ] `standalone=true` filter returns only tasks where project_id is null
- [ ] `PATCH` endpoints accept partial updates
- [ ] `DELETE` returns 204 on success, 404 for invalid UUIDs
- [ ] Validation: energy_cost and activation_friction reject values outside 1-5 range
- [ ] Validation: status fields reject invalid values
- [ ] All endpoints visible and testable at `/docs`

## Technical Notes

- `progress_pct` on projects should be auto-calculated from task completion ratio, but can be a simple stored field for now that gets updated when tasks change status — auto-calculation can be refined later
- The `overdue` filter needs date comparison logic: `due_date < today AND status NOT IN ('completed', 'skipped', 'abandoned')`
- `recurrence_rule` is stored as a string — no parsing or evaluation needed in this ticket. That logic comes with the scheduler in Phase 2.
- Consider adding `order_by` query parameter for task list (by due_date, energy_cost, activation_friction, created_at)

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models and database tables)
- Ticket #4 (establishes the schema and router patterns)
