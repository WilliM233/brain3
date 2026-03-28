# API Overview

BRAIN 3.0 exposes a RESTful API via FastAPI. All endpoints are under the `/api` prefix, with a standalone `/health` endpoint at the root. The full interactive documentation (Swagger UI) is available at `/docs` when the API is running.

This page orients you to what's available. For endpoint-level detail — request/response schemas, status codes, and parameter types — use the `/docs` page.

---

## Health Check

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Returns API status and database connectivity |

Returns `{"status": "healthy", "database": "connected"}` when everything is working, or a 503 with `"unhealthy"` if the database is unreachable.

---

## Entity CRUD

Standard create, read, update, delete operations for all seven pillar entities. Each entity follows the same pattern:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/{entity}` | Create |
| `GET` | `/api/{entity}` | List (with filters) |
| `GET` | `/api/{entity}/{id}` | Get by ID (detail view with nested children) |
| `PATCH` | `/api/{entity}/{id}` | Partial update |
| `DELETE` | `/api/{entity}/{id}` | Delete |

### Domains — `/api/domains`

Life areas. CRUD only — domains are a simple organizational layer.

### Goals — `/api/goals`

Enduring outcomes nested under domains.

**List filters:** `domain_id`, `status` (active, paused, achieved, abandoned)

### Projects — `/api/projects`

Bounded efforts nested under goals.

**List filters:** `goal_id`, `status` (not_started, active, blocked, completed, abandoned)

### Tasks — `/api/tasks`

Atoms of action with ADHD-aware metadata. Tasks have the richest filtering of any entity — all filters are composable (combine any subset in a single request):

| Filter | Type | What It Does |
|--------|------|-------------|
| `project_id` | UUID | Tasks in a specific project |
| `standalone` | bool | Tasks with no project (`true`) or with a project (`false`) |
| `status` | string | Filter by status (pending, active, completed, skipped, deferred) |
| `cognitive_type` | string | Filter by cognitive type |
| `energy_cost_min` / `energy_cost_max` | int | Energy cost range (1-5) |
| `friction_min` / `friction_max` | int | Activation friction range (1-5) |
| `context_required` | string | Filter by context (at_home, at_computer, etc.) |
| `due_before` / `due_after` | date | Due date range |
| `overdue` | bool | Tasks past due date and not completed/skipped |

These filters are how Claude matches tasks to your current capacity — filtering by energy, friction, cognitive type, and context to surface what makes sense right now.

### Tags — `/api/tags`

Cross-cutting labels for tasks. Tags have globally unique names (case-insensitive) with get-or-create behavior on POST.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/tags` | Create or retrieve an existing tag |
| `GET` | `/api/tags` | List all tags |
| `GET` | `/api/tags/{id}` | Get a tag |
| `PATCH` | `/api/tags/{id}` | Update a tag |
| `DELETE` | `/api/tags/{id}` | Delete a tag |
| `GET` | `/api/tags/{id}/tasks` | List all tasks with this tag |

**Task-tag associations:**

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/tasks/{task_id}/tags` | List tags on a task |
| `POST` | `/api/tasks/{task_id}/tags/{tag_id}` | Attach a tag to a task |
| `DELETE` | `/api/tasks/{task_id}/tags/{tag_id}` | Detach a tag from a task |

### Routines — `/api/routines`

Behavioral patterns with streak tracking. Routines have additional endpoints beyond standard CRUD:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/routines/{id}/complete` | Mark a routine as completed (updates streak counters) |
| `POST` | `/api/routines/{id}/schedules` | Add a schedule entry (day, time, preferred window) |
| `GET` | `/api/routines/{id}/schedules` | List schedule entries |
| `DELETE` | `/api/routines/{id}/schedules/{schedule_id}` | Remove a schedule entry |

**List filters:** `domain_id`, `status` (active, paused, retired), `frequency`

> **Note:** Completing a routine via `/complete` updates the streak counter but does **not** create an activity log entry. See [Architecture — Explicit Activity Logging](Architecture.md#explicit-activity-logging) for why this is intentional and what it means for reporting.

### Check-ins — `/api/checkins`

State snapshots (energy, mood, focus). CRUD with list filtering.

**List filters:** `checkin_type` (morning, midday, evening, micro, freeform), `after`, `before` (date range)

### Activity Log — `/api/activity`

Record of what happened and how it felt. Each entry can reference a task, routine, and/or check-in.

**List filters:** `task_id`, `routine_id`, `checkin_id`, `action_type`, `after`, `before` (date range)

---

## Reports

Four read-only aggregation endpoints that power pattern recognition. All are under `/api/reports`.

| Endpoint | What It Answers |
|----------|----------------|
| `GET /api/reports/activity-summary` | How productive was this period? Total completions, skips, deferrals, duration, average energy delta, average mood. |
| `GET /api/reports/domain-balance` | Which life areas are getting attention and which are being neglected? Active goals, projects, pending tasks, overdue tasks, and days since last activity per domain. |
| `GET /api/reports/routine-adherence` | How consistently am I maintaining my routines? Completions vs. expected, adherence percentage, streak health, broken streak flags. |
| `GET /api/reports/friction-analysis` | Am I overestimating or underestimating friction? Predicted vs. actual friction by cognitive type, completion rates, energy impact. |

**Activity summary** and **routine adherence** require `after` and `before` query parameters (datetime range). **Friction analysis** defaults to the last 30 days if no range is specified. **Domain balance** has no parameters — it reports current state.

These endpoints are designed for Claude to consume and interpret conversationally. Claude reads the numbers; you get the insight in plain language.
