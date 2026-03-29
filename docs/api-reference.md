# BRAIN 3.0 API Reference

**Version:** 1.0.0
**Base URL:** `http://localhost:8000` (development) or `http://<truenas-ip>:8000` (production)
**Authentication:** None (Phase 1). All endpoints are unauthenticated. Auth middleware will be added in Phase 3.
**Content-Type:** `application/json` for all request and response bodies.
**Interactive docs:** Swagger UI available at `/docs` when the API is running.

---

## Conventions

### IDs

All entity IDs are UUIDs (v4). Supply them as strings in path parameters and request bodies.

### Timestamps

All timestamps are ISO 8601 with timezone (`TIMESTAMPTZ`). The server stores and returns UTC.

### PATCH semantics

All update endpoints use `PATCH` with partial update semantics. Only include the fields you want to change. Omitted fields are left unchanged.

### Error responses

Error responses follow this structure:

```json
{"detail": "Human-readable error message"}
```

Standard status codes:
- **200** -- Success (read, update, idempotent create)
- **201** -- Created (new resource)
- **204** -- No Content (delete)
- **400** -- Bad Request (referenced entity not found, e.g., invalid `domain_id`)
- **404** -- Not Found (entity with given ID does not exist)
- **409** -- Conflict (operation not valid in current state, e.g., completing a non-active routine)
- **422** -- Validation Error (request body fails Pydantic validation)

> **Note:** The auto-generated OpenAPI spec at `/docs` does not document 400, 404, or 409 responses. This is a known FastAPI limitation -- `HTTPException` responses are not reflected in the auto-generated spec. The documentation below is authoritative.

### Enum values

Enum fields are validated at both the Pydantic schema level and the database level via check constraints. Invalid enum values return a 422 Validation Error.

---

## Health Check

### `GET /health`

Check API and database connectivity.

**Parameters:** None

**Response:**

| Status | Body |
|--------|------|
| 200 | `{"status": "healthy", "database": "connected"}` |
| 503 | `{"status": "unhealthy", "database": "disconnected"}` |

**Example:**

```bash
curl http://localhost:8000/health
```

---

## Domains

Life areas that organize the entire system. Every goal and routine belongs to a domain. Domains are broad and stable -- they rarely change.

### `POST /api/domains`

Create a new domain.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | string | yes | max 200 chars | Domain name (e.g., "House", "Network", "Finances") |
| `description` | string | no | max 5000 chars | What this life area encompasses |
| `color` | string | no | max 7 chars | Hex color code for display (e.g., "#4A90D9") |
| `sort_order` | integer | no | default: 0 | Display ordering preference |

**Response:** `201 Created` -- `DomainResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `name` | string | Domain name |
| `description` | string or null | Description |
| `color` | string or null | Hex color |
| `sort_order` | integer or null | Sort order |
| `created_at` | datetime | Creation timestamp (UTC) |

**Example:**

```bash
curl -X POST http://localhost:8000/api/domains \
  -H "Content-Type: application/json" \
  -d '{"name": "House", "description": "Home maintenance and improvement", "color": "#4A90D9", "sort_order": 1}'
```

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "House",
  "description": "Home maintenance and improvement",
  "color": "#4A90D9",
  "sort_order": 1,
  "created_at": "2026-03-29T14:00:00+00:00"
}
```

### `GET /api/domains`

List all domains, ordered by `sort_order` then `name`.

**Query parameters:** None

**Response:** `200 OK` -- `list[DomainResponse]`

**Example:**

```bash
curl http://localhost:8000/api/domains
```

### `GET /api/domains/{domain_id}`

Get a single domain with its nested goals.

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `domain_id` | UUID | Domain identifier |

**Response:** `200 OK` -- `DomainDetailResponse`

Extends `DomainResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `goals` | list[GoalResponse] | All goals in this domain |

**Error:** `404` if domain not found.

**Example:**

```bash
curl http://localhost:8000/api/domains/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### `PATCH /api/domains/{domain_id}`

Partial update of a domain. Only include fields to change.

**Path parameters:** `domain_id` (UUID)

**Request body:** Same fields as `DomainCreate`, all optional.

**Response:** `200 OK` -- `DomainResponse`

**Error:** `404` if domain not found.

**Example:**

```bash
curl -X PATCH http://localhost:8000/api/domains/a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
  -H "Content-Type: application/json" \
  -d '{"sort_order": 2}'
```

### `DELETE /api/domains/{domain_id}`

Delete a domain. Cascades to all goals, projects, tasks, and routines under this domain.

**Path parameters:** `domain_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if domain not found.

**Example:**

```bash
curl -X DELETE http://localhost:8000/api/domains/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Goals

Enduring outcomes that give everything else meaning. Goals are nested under domains and rarely change.

### `POST /api/goals`

Create a new goal. The referenced `domain_id` must exist.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `domain_id` | UUID | yes | must reference existing domain | Parent domain |
| `title` | string | yes | max 200 chars | Goal name |
| `description` | string | no | max 5000 chars | Why this goal matters, what success looks like |
| `status` | string | no | default: `"active"` | One of: `active`, `paused`, `achieved`, `abandoned` |

**Response:** `201 Created` -- `GoalResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `domain_id` | UUID | Parent domain ID |
| `title` | string | Goal name |
| `description` | string or null | Description |
| `status` | string | Goal status |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

**Error:** `400` if `domain_id` does not reference an existing domain.

**Example:**

```bash
curl -X POST http://localhost:8000/api/goals \
  -H "Content-Type: application/json" \
  -d '{"domain_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "title": "Maintain the house", "description": "Keep the home in good repair and continuously improving"}'
```

```json
{
  "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "domain_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Maintain the house",
  "description": "Keep the home in good repair and continuously improving",
  "status": "active",
  "created_at": "2026-03-29T14:00:00+00:00",
  "updated_at": "2026-03-29T14:00:00+00:00"
}
```

### `GET /api/goals`

List goals with optional filters. Ordered by `created_at`.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain_id` | UUID | no | Filter by parent domain |
| `status` | string | no | Filter by status: `active`, `paused`, `achieved`, `abandoned` |

**Response:** `200 OK` -- `list[GoalResponse]`

**Example:**

```bash
# All active goals
curl "http://localhost:8000/api/goals?status=active"

# Goals in a specific domain
curl "http://localhost:8000/api/goals?domain_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

### `GET /api/goals/{goal_id}`

Get a single goal with its nested projects.

**Path parameters:** `goal_id` (UUID)

**Response:** `200 OK` -- `GoalDetailResponse`

Extends `GoalResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `projects` | list[ProjectResponse] | All projects under this goal |

**Error:** `404` if goal not found.

### `PATCH /api/goals/{goal_id}`

Partial update of a goal.

**Path parameters:** `goal_id` (UUID)

**Request body:** Same fields as `GoalCreate`, all optional. Includes `domain_id` for re-parenting.

**Response:** `200 OK` -- `GoalResponse`

**Error:** `404` if goal not found.

### `DELETE /api/goals/{goal_id}`

Delete a goal. Cascades to all projects and tasks under this goal.

**Path parameters:** `goal_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if goal not found.

---

## Projects

Bounded efforts with a beginning and an end, nested under goals.

### `POST /api/projects`

Create a new project. The referenced `goal_id` must exist.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `goal_id` | UUID | yes | must reference existing goal | Parent goal |
| `title` | string | yes | max 200 chars | Project name |
| `description` | string | no | max 5000 chars | Scope, context, and notes |
| `status` | string | no | default: `"not_started"` | One of: `not_started`, `active`, `blocked`, `completed`, `abandoned` |
| `deadline` | date | no | ISO 8601 date | Target completion date |

**Response:** `201 Created` -- `ProjectResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `goal_id` | UUID | Parent goal ID |
| `title` | string | Project name |
| `description` | string or null | Description |
| `status` | string | Project status |
| `deadline` | date or null | Target completion date |
| `progress_pct` | integer | 0-100, progress percentage |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

**Error:** `400` if `goal_id` does not reference an existing goal.

**Example:**

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"goal_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "title": "Remodel bathroom", "status": "active", "deadline": "2026-06-15"}'
```

```json
{
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "goal_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "title": "Remodel bathroom",
  "description": null,
  "status": "active",
  "deadline": "2026-06-15",
  "progress_pct": 0,
  "created_at": "2026-03-29T14:00:00+00:00",
  "updated_at": "2026-03-29T14:00:00+00:00"
}
```

### `GET /api/projects`

List projects with optional filters. Ordered by `created_at`.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `goal_id` | UUID | no | Filter by parent goal |
| `status` | string | no | Filter by status: `not_started`, `active`, `blocked`, `completed`, `abandoned` |
| `has_deadline` | boolean | no | `true` to show only projects with a deadline set |
| `overdue` | boolean | no | `true` to show projects past deadline and not completed/abandoned |

**Response:** `200 OK` -- `list[ProjectResponse]`

**Example:**

```bash
# Active projects with deadlines
curl "http://localhost:8000/api/projects?status=active&has_deadline=true"

# Overdue projects
curl "http://localhost:8000/api/projects?overdue=true"
```

### `GET /api/projects/{project_id}`

Get a single project with its nested tasks.

**Path parameters:** `project_id` (UUID)

**Response:** `200 OK` -- `ProjectDetailResponse`

Extends `ProjectResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `tasks` | list[TaskResponse] | All tasks in this project |

**Error:** `404` if project not found.

### `PATCH /api/projects/{project_id}`

Partial update of a project.

**Path parameters:** `project_id` (UUID)

**Request body:** Same fields as `ProjectCreate`, all optional. Includes `goal_id` for re-parenting.

**Response:** `200 OK` -- `ProjectResponse`

**Error:** `404` if project not found.

### `DELETE /api/projects/{project_id}`

Delete a project. Cascades to all tasks under this project.

**Path parameters:** `project_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if project not found.

---

## Tasks

The atoms of action. Tasks carry ADHD-aware metadata: energy cost, cognitive type, context requirements, and activation friction.

### `POST /api/tasks`

Create a new task. Tasks can be standalone (no project) or nested under a project.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `project_id` | UUID | no | must reference existing project if provided | Parent project. Null for standalone tasks. |
| `title` | string | yes | max 200 chars | Task name |
| `description` | string | no | max 5000 chars | Details, notes, context |
| `status` | string | no | default: `"pending"` | One of: `pending`, `active`, `completed`, `skipped`, `deferred` |
| `cognitive_type` | string | no | | One of: `hands_on`, `communication`, `decision`, `errand`, `admin`, `focus_work` |
| `energy_cost` | integer | no | 1-5 | How draining the task is, independent of time |
| `activation_friction` | integer | no | 1-5 | How hard the task is to start, not how hard it is to do |
| `context_required` | string | no | max 100 chars | Where/what is needed (e.g., `at_home`, `at_computer`, `at_store`, `needs_tools`) |
| `due_date` | date | no | ISO 8601 date | Deadline |
| `recurrence_rule` | string | no | max 500 chars | iCalendar RRULE string for repeating tasks |

**Response:** `201 Created` -- `TaskResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `project_id` | UUID or null | Parent project ID |
| `title` | string | Task name |
| `description` | string or null | Description |
| `status` | string | Task status |
| `cognitive_type` | string or null | Cognitive type |
| `energy_cost` | integer or null | Energy cost (1-5) |
| `activation_friction` | integer or null | Activation friction (1-5) |
| `context_required` | string or null | Context requirement |
| `due_date` | date or null | Deadline |
| `recurrence_rule` | string or null | RRULE recurrence string |
| `completed_at` | datetime or null | When the task was completed |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

**Error:** `400` if `project_id` does not reference an existing project.

**Example:**

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "title": "Research tile options",
    "cognitive_type": "focus_work",
    "energy_cost": 2,
    "activation_friction": 3,
    "context_required": "at_computer",
    "due_date": "2026-04-15"
  }'
```

```json
{
  "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "project_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "title": "Research tile options",
  "description": null,
  "status": "pending",
  "cognitive_type": "focus_work",
  "energy_cost": 2,
  "activation_friction": 3,
  "context_required": "at_computer",
  "due_date": "2026-04-15",
  "recurrence_rule": null,
  "completed_at": null,
  "created_at": "2026-03-29T14:00:00+00:00",
  "updated_at": "2026-03-29T14:00:00+00:00"
}
```

### `GET /api/tasks`

List tasks with composable filters. All filters are optional and combine with AND logic. Ordered by `created_at`.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | UUID | no | Tasks in a specific project |
| `standalone` | boolean | no | `true` for tasks with no project, `false` is not implemented (use `project_id` instead) |
| `status` | string | no | Filter by status: `pending`, `active`, `completed`, `skipped`, `deferred` |
| `cognitive_type` | string | no | Filter by cognitive type: `hands_on`, `communication`, `decision`, `errand`, `admin`, `focus_work` |
| `energy_cost_min` | integer | no | Minimum energy cost (inclusive, 1-5) |
| `energy_cost_max` | integer | no | Maximum energy cost (inclusive, 1-5) |
| `friction_min` | integer | no | Minimum activation friction (inclusive, 1-5) |
| `friction_max` | integer | no | Maximum activation friction (inclusive, 1-5) |
| `context_required` | string | no | Exact match on context requirement |
| `due_before` | date | no | Tasks due on or before this date |
| `due_after` | date | no | Tasks due on or after this date |
| `overdue` | boolean | no | `true` for tasks past due date and not completed/skipped |

**Response:** `200 OK` -- `list[TaskResponse]`

See the [Composable Filter Reference](#composable-filter-reference) section for detailed filter behavior and example combinations.

**Example:**

```bash
# Low-energy tasks I can do at home
curl "http://localhost:8000/api/tasks?energy_cost_max=2&context_required=at_home&status=pending"

# Overdue tasks
curl "http://localhost:8000/api/tasks?overdue=true"
```

### `GET /api/tasks/{task_id}`

Get a single task with its nested tags.

**Path parameters:** `task_id` (UUID)

**Response:** `200 OK` -- `TaskDetailResponse`

Extends `TaskResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `tags` | list[TagResponse] | All tags attached to this task |

**Error:** `404` if task not found.

### `PATCH /api/tasks/{task_id}`

Partial update of a task.

**Path parameters:** `task_id` (UUID)

**Request body:** Same fields as `TaskCreate`, all optional.

**Automatic behaviors:**
- Setting `status` to `"completed"` auto-sets `completed_at` to the current UTC timestamp (if not already set).
- Changing `status` away from `"completed"` clears `completed_at` to null.
- An explicitly provided `completed_at` value is preserved.

**Re-parenting:** Set `project_id` to a different project UUID to move the task. Set `project_id` to `null` to make it standalone.

**Response:** `200 OK` -- `TaskResponse`

**Error:** `404` if task not found.

**Example:**

```bash
# Complete a task
curl -X PATCH http://localhost:8000/api/tasks/d4e5f6a7-b8c9-0123-defa-234567890123 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### `DELETE /api/tasks/{task_id}`

Delete a task. Also removes all tag associations.

**Path parameters:** `task_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if task not found.

---

## Tags

Cross-cutting labels for tasks. Tags have globally unique names (case-insensitive) with get-or-create behavior.

### `POST /api/tags`

Create a tag, or return the existing one if a tag with the same name already exists (case-insensitive).

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | string | yes | max 100 chars | Tag name. Stored lowercase. |
| `color` | string | no | max 7 chars | Hex color for display |

**Response:**
- `201 Created` -- new tag was created
- `200 OK` -- existing tag with matching name was returned

Response body: `TagResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Tag identifier |
| `name` | string | Tag name (lowercase) |
| `color` | string or null | Hex color |

> **Note:** The dynamic 200/201 status code is not reflected in the auto-generated OpenAPI spec, which only shows 200. Both codes are valid responses from this endpoint.

**Example:**

```bash
curl -X POST http://localhost:8000/api/tags \
  -H "Content-Type: application/json" \
  -d '{"name": "home-depot", "color": "#F96302"}'
```

### `GET /api/tags`

List all tags with optional name search. Ordered by `name`.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | no | Case-insensitive substring match on tag name |

**Response:** `200 OK` -- `list[TagResponse]`

**Example:**

```bash
# Search for tags containing "home"
curl "http://localhost:8000/api/tags?search=home"
```

### `GET /api/tags/{tag_id}`

Get a single tag by ID.

**Path parameters:** `tag_id` (UUID)

**Response:** `200 OK` -- `TagResponse`

**Error:** `404` if tag not found.

### `PATCH /api/tags/{tag_id}`

Partial update of a tag. Names are normalized to lowercase on update.

**Path parameters:** `tag_id` (UUID)

**Request body:** Same fields as `TagCreate`, all optional.

**Response:** `200 OK` -- `TagResponse`

**Error:** `404` if tag not found.

### `DELETE /api/tags/{tag_id}`

Delete a tag. Cascades removal of all task-tag associations.

**Path parameters:** `tag_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if tag not found.

### `GET /api/tags/{tag_id}/tasks`

List all tasks that have a given tag attached.

**Path parameters:** `tag_id` (UUID)

**Response:** `200 OK` -- `list[TaskResponse]`

**Error:** `404` if tag not found.

**Example:**

```bash
curl http://localhost:8000/api/tags/e5f6a7b8-c9d0-1234-efab-345678901234/tasks
```

---

## Task-Tag Associations

Attach and detach tags on tasks. These endpoints are under the `/api/tasks` prefix.

### `GET /api/tasks/{task_id}/tags`

List all tags attached to a task.

**Path parameters:** `task_id` (UUID)

**Response:** `200 OK` -- `list[TagResponse]`

**Error:** `404` if task not found.

### `POST /api/tasks/{task_id}/tags/{tag_id}`

Attach a tag to a task. Idempotent -- attaching the same tag twice is a no-op.

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | UUID | Task to tag |
| `tag_id` | UUID | Tag to attach |

**Response:** `200 OK` -- `TagResponse` (the attached tag)

**Error:** `404` if task or tag not found.

**Example:**

```bash
curl -X POST http://localhost:8000/api/tasks/d4e5f6a7-b8c9-0123-defa-234567890123/tags/e5f6a7b8-c9d0-1234-efab-345678901234
```

### `DELETE /api/tasks/{task_id}/tags/{tag_id}`

Detach a tag from a task.

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | UUID | Task to untag |
| `tag_id` | UUID | Tag to detach |

**Response:** `204 No Content`

**Errors:**
- `404` if task or tag not found
- `404` if the tag is not currently attached to the task

---

## Routines

Behavioral patterns with streak tracking. Routines are commitments to patterns, modeled separately from recurring tasks.

### `POST /api/routines`

Create a new routine. The referenced `domain_id` must exist.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `domain_id` | UUID | yes | must reference existing domain | Parent domain |
| `title` | string | yes | max 200 chars | Routine name |
| `description` | string | no | max 5000 chars | What this routine involves and why it matters |
| `frequency` | string | yes | | One of: `daily`, `weekdays`, `weekends`, `weekly`, `custom` |
| `status` | string | no | default: `"active"` | One of: `active`, `paused`, `retired` |
| `energy_cost` | integer | no | 1-5 | How draining |
| `activation_friction` | integer | no | 1-5 | How hard to start |

**Response:** `201 Created` -- `RoutineResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `domain_id` | UUID | Parent domain ID |
| `title` | string | Routine name |
| `description` | string or null | Description |
| `frequency` | string | Frequency type |
| `status` | string | Routine status |
| `energy_cost` | integer or null | Energy cost (1-5) |
| `activation_friction` | integer or null | Activation friction (1-5) |
| `current_streak` | integer | Consecutive completions without a miss (starts at 0) |
| `best_streak` | integer | All-time best streak (starts at 0) |
| `last_completed` | date or null | Date of most recent completion |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modification timestamp |

**Error:** `400` if `domain_id` does not reference an existing domain.

**Example:**

```bash
curl -X POST http://localhost:8000/api/routines \
  -H "Content-Type: application/json" \
  -d '{
    "domain_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Saturday morning house maintenance",
    "description": "Walk through the house, identify and address small maintenance items",
    "frequency": "weekly",
    "energy_cost": 3,
    "activation_friction": 2
  }'
```

### `GET /api/routines`

List routines with optional filters. Ordered by `created_at`.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain_id` | UUID | no | Filter by parent domain |
| `status` | string | no | Filter by status: `active`, `paused`, `retired` |
| `frequency` | string | no | Filter by frequency: `daily`, `weekdays`, `weekends`, `weekly`, `custom` |
| `streak_broken` | boolean | no | `true` for active routines with current_streak = 0 |

**Response:** `200 OK` -- `list[RoutineResponse]`

**Example:**

```bash
# Active routines with broken streaks
curl "http://localhost:8000/api/routines?status=active&streak_broken=true"
```

### `GET /api/routines/{routine_id}`

Get a single routine with its nested schedules.

**Path parameters:** `routine_id` (UUID)

**Response:** `200 OK` -- `RoutineDetailResponse`

Extends `RoutineResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `schedules` | list[RoutineScheduleResponse] | Schedule entries for this routine |

Each `RoutineScheduleResponse`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Schedule entry identifier |
| `routine_id` | UUID | Parent routine ID |
| `day_of_week` | string or null | Day name (e.g., "monday", "saturday") or "any" |
| `time_of_day` | string or null | Time label (e.g., "morning", "evening") or specific "HH:MM" |
| `preferred_window` | string or null | Ideal time range (e.g., "06:00-08:00") |

**Error:** `404` if routine not found.

### `PATCH /api/routines/{routine_id}`

Partial update of a routine.

**Path parameters:** `routine_id` (UUID)

**Request body:** Same fields as `RoutineCreate`, all optional. Includes `domain_id` for re-parenting.

**Response:** `200 OK` -- `RoutineResponse`

**Error:** `404` if routine not found.

### `DELETE /api/routines/{routine_id}`

Delete a routine. Cascades to all schedule entries.

**Path parameters:** `routine_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if routine not found.

### `POST /api/routines/{routine_id}/complete`

Record a routine completion and evaluate the streak.

**Path parameters:** `routine_id` (UUID)

**Request body (optional):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `completed_date` | date | no | Date to record the completion for. Defaults to today. Supports backdating. |

**Response:** `200 OK` -- `RoutineCompleteResponse`

| Field | Type | Description |
|-------|------|-------------|
| `routine_id` | UUID | The routine that was completed |
| `completed_date` | date | The date recorded for this completion |
| `current_streak` | integer | Updated current streak |
| `best_streak` | integer | Updated best streak |
| `streak_was_broken` | boolean | Whether this completion was after a streak break |

**Errors:**
- `404` if routine not found
- `409` if routine is not in `"active"` status

**Streak evaluation behavior:**
- The streak engine (`app/services/streak.py`) determines whether the completion continues or resets the streak based on the routine's `frequency` and `scheduled_days`.
- `last_completed` only advances forward -- backdating a completion does not regress `last_completed` if a later date was already recorded.
- This endpoint does **not** create an activity log entry. Activity logging is explicit -- call `POST /api/activity` separately to record the completion in the activity log.

**Example:**

```bash
# Complete for today
curl -X POST http://localhost:8000/api/routines/f6a7b8c9-d0e1-2345-fabcd-456789012345/complete

# Backdate a completion
curl -X POST http://localhost:8000/api/routines/f6a7b8c9-d0e1-2345-fabcd-456789012345/complete \
  -H "Content-Type: application/json" \
  -d '{"completed_date": "2026-03-28"}'
```

```json
{
  "routine_id": "f6a7b8c9-d0e1-2345-fabcd-456789012345",
  "completed_date": "2026-03-29",
  "current_streak": 5,
  "best_streak": 12,
  "streak_was_broken": false
}
```

### `POST /api/routines/{routine_id}/schedules`

Add a schedule entry to a routine.

**Path parameters:** `routine_id` (UUID)

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `day_of_week` | string | yes | max 50 chars | Day name (e.g., "monday") or "any" |
| `time_of_day` | string | yes | max 50 chars | Time label (e.g., "morning") or "HH:MM" |
| `preferred_window` | string | no | max 50 chars | Time range (e.g., "06:00-08:00") |

**Response:** `201 Created` -- `RoutineScheduleResponse`

**Error:** `404` if routine not found.

**Example:**

```bash
curl -X POST http://localhost:8000/api/routines/f6a7b8c9-d0e1-2345-fabcd-456789012345/schedules \
  -H "Content-Type: application/json" \
  -d '{"day_of_week": "saturday", "time_of_day": "morning", "preferred_window": "08:00-10:00"}'
```

### `GET /api/routines/{routine_id}/schedules`

List all schedule entries for a routine.

**Path parameters:** `routine_id` (UUID)

**Response:** `200 OK` -- `list[RoutineScheduleResponse]`

**Error:** `404` if routine not found.

### `DELETE /api/routines/{routine_id}/schedules/{schedule_id}`

Remove a schedule entry from a routine.

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `routine_id` | UUID | Parent routine |
| `schedule_id` | UUID | Schedule entry to remove |

**Response:** `204 No Content`

**Error:** `404` if schedule entry not found (must match both `routine_id` and `schedule_id`).

---

## Check-ins

Point-in-time self-assessments of energy, mood, and focus. Used to capture internal state and match tasks to current capacity.

### `POST /api/checkins`

Log a new state check-in.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `checkin_type` | string | yes | | One of: `morning`, `midday`, `evening`, `micro`, `freeform` |
| `energy_level` | integer | no | 1-5 | Current energy level |
| `mood` | integer | no | 1-5 | Current emotional state |
| `focus_level` | integer | no | 1-5 | Ability to concentrate |
| `freeform_note` | string | no | max 5000 chars | Open-ended mindfulness observation |
| `context` | string | no | max 100 chars | Situation context (e.g., `work_day`, `day_off`, `chaotic`, `travel`) |

**Response:** `201 Created` -- `CheckinResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `checkin_type` | string | Type of check-in |
| `energy_level` | integer or null | Energy (1-5) |
| `mood` | integer or null | Mood (1-5) |
| `focus_level` | integer or null | Focus (1-5) |
| `freeform_note` | string or null | Freeform note |
| `context` | string or null | Situation context |
| `logged_at` | datetime | When this check-in was recorded |

**Example:**

```bash
curl -X POST http://localhost:8000/api/checkins \
  -H "Content-Type: application/json" \
  -d '{
    "checkin_type": "morning",
    "energy_level": 3,
    "mood": 4,
    "focus_level": 2,
    "context": "work_day"
  }'
```

```json
{
  "id": "a7b8c9d0-e1f2-3456-abcd-567890123456",
  "checkin_type": "morning",
  "energy_level": 3,
  "mood": 4,
  "focus_level": 2,
  "freeform_note": null,
  "context": "work_day",
  "logged_at": "2026-03-29T08:30:00+00:00"
}
```

### `GET /api/checkins`

List check-ins with optional filters. Ordered by `logged_at` descending (most recent first).

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `checkin_type` | string | no | Filter by type: `morning`, `midday`, `evening`, `micro`, `freeform` |
| `context` | string | no | Exact match on context |
| `logged_after` | datetime | no | Check-ins logged on or after this timestamp |
| `logged_before` | datetime | no | Check-ins logged on or before this timestamp |

**Response:** `200 OK` -- `list[CheckinResponse]`

**Example:**

```bash
# Morning check-ins from the last week
curl "http://localhost:8000/api/checkins?checkin_type=morning&logged_after=2026-03-22T00:00:00Z"
```

### `GET /api/checkins/{checkin_id}`

Get a single check-in by ID.

**Path parameters:** `checkin_id` (UUID)

**Response:** `200 OK` -- `CheckinResponse`

**Error:** `404` if check-in not found.

### `PATCH /api/checkins/{checkin_id}`

Partial update of a check-in.

**Path parameters:** `checkin_id` (UUID)

**Request body:** Same fields as `CheckinCreate`, all optional.

**Response:** `200 OK` -- `CheckinResponse`

**Error:** `404` if check-in not found.

### `DELETE /api/checkins/{checkin_id}`

Delete a check-in.

**Path parameters:** `checkin_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if check-in not found.

---

## Activity Log

The record of what actually happened -- task completions, routine executions, reflections, and how they felt. Each entry can reference at most one of: a task, a routine, or a check-in.

### `POST /api/activity`

Create a new activity log entry.

**Request body:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `task_id` | UUID | no | must reference existing task | Associated task |
| `routine_id` | UUID | no | must reference existing routine | Associated routine |
| `checkin_id` | UUID | no | must reference existing check-in | Associated check-in |
| `action_type` | string | yes | | One of: `completed`, `skipped`, `deferred`, `started`, `reflected`, `checked_in` |
| `notes` | string | no | max 5000 chars | Freeform observations about the activity |
| `energy_before` | integer | no | 1-5 | Energy before starting |
| `energy_after` | integer | no | 1-5 | Energy after completing |
| `mood_rating` | integer | no | 1-5 | How the user felt during/after |
| `friction_actual` | integer | no | 1-5 | Actual experienced friction (vs. predicted on the task) |
| `duration_minutes` | integer | no | | How long the activity took |

**Constraint:** At most one of `task_id`, `routine_id`, `checkin_id` may be set. Providing more than one returns a 422 Validation Error.

**Response:** `201 Created` -- `ActivityLogResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Generated unique identifier |
| `task_id` | UUID or null | Referenced task |
| `routine_id` | UUID or null | Referenced routine |
| `checkin_id` | UUID or null | Referenced check-in |
| `action_type` | string | What happened |
| `notes` | string or null | Observations |
| `energy_before` | integer or null | Energy before (1-5) |
| `energy_after` | integer or null | Energy after (1-5) |
| `mood_rating` | integer or null | Mood (1-5) |
| `friction_actual` | integer or null | Actual friction (1-5) |
| `duration_minutes` | integer or null | Duration in minutes |
| `logged_at` | datetime | When this entry was recorded |

**Errors:**
- `400` if a referenced entity (task, routine, or check-in) does not exist
- `422` if more than one reference ID is provided

**Example:**

```bash
curl -X POST http://localhost:8000/api/activity \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "d4e5f6a7-b8c9-0123-defa-234567890123",
    "action_type": "completed",
    "energy_before": 3,
    "energy_after": 2,
    "friction_actual": 2,
    "duration_minutes": 45,
    "notes": "Easier than expected once I got started"
  }'
```

### `GET /api/activity`

List activity log entries with optional filters. Ordered by `logged_at` descending (most recent first).

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action_type` | string | no | Filter by action type: `completed`, `skipped`, `deferred`, `started`, `reflected`, `checked_in` |
| `task_id` | UUID | no | Filter by associated task |
| `routine_id` | UUID | no | Filter by associated routine |
| `logged_after` | datetime | no | Entries logged on or after this timestamp |
| `logged_before` | datetime | no | Entries logged on or before this timestamp |
| `has_task` | boolean | no | `true` for entries with a task reference, `false` for entries without |
| `has_routine` | boolean | no | `true` for entries with a routine reference, `false` for entries without |

**Response:** `200 OK` -- `list[ActivityLogResponse]`

**Example:**

```bash
# Completed activities in the last 7 days
curl "http://localhost:8000/api/activity?action_type=completed&logged_after=2026-03-22T00:00:00Z"

# All routine activity
curl "http://localhost:8000/api/activity?has_routine=true"
```

### `GET /api/activity/{entry_id}`

Get a single activity log entry with resolved references. Returns the full task, routine, and/or check-in objects inline.

**Path parameters:** `entry_id` (UUID)

**Response:** `200 OK` -- `ActivityLogDetailResponse`

Extends `ActivityLogResponse` with:

| Field | Type | Description |
|-------|------|-------------|
| `task` | TaskResponse or null | Full task object if `task_id` is set |
| `routine` | RoutineResponse or null | Full routine object if `routine_id` is set |
| `checkin` | CheckinResponse or null | Full check-in object if `checkin_id` is set |

**Error:** `404` if activity log entry not found.

### `PATCH /api/activity/{entry_id}`

Partial update of an activity log entry.

**Path parameters:** `entry_id` (UUID)

**Request body:** Same fields as `ActivityLogCreate`, all optional.

**Constraint:** After applying the update, the entry must still have at most one reference (task_id, routine_id, or checkin_id). If the merged state violates this, returns 422.

**Response:** `200 OK` -- `ActivityLogResponse`

**Errors:**
- `400` if a referenced entity does not exist
- `404` if entry not found
- `422` if more than one reference ID would be set after the update

### `DELETE /api/activity/{entry_id}`

Delete an activity log entry.

**Path parameters:** `entry_id` (UUID)

**Response:** `204 No Content`

**Error:** `404` if entry not found.

---

## Reports

Four read-only aggregation endpoints for pattern recognition. All are under `/api/reports`.

### `GET /api/reports/activity-summary`

Aggregated activity statistics for a date range. Answers: "How productive was this period?"

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `after` | datetime | **yes** | Start of the reporting period (inclusive) |
| `before` | datetime | **yes** | End of the reporting period (inclusive) |

**Response:** `200 OK` -- `ActivitySummaryResponse`

| Field | Type | Description |
|-------|------|-------------|
| `period_start` | datetime | Start of reporting period (echo of `after`) |
| `period_end` | datetime | End of reporting period (echo of `before`) |
| `total_completed` | integer | Activity entries with `action_type = "completed"` |
| `total_skipped` | integer | Activity entries with `action_type = "skipped"` |
| `total_deferred` | integer | Activity entries with `action_type = "deferred"` |
| `total_duration_minutes` | integer | Sum of all `duration_minutes` across entries (0 if none recorded) |
| `avg_energy_delta` | float or null | Average of `(energy_after - energy_before)` across entries where both are present. Null if no entries have both values. |
| `avg_mood` | float or null | Average `mood_rating` across entries where set. Null if none. |
| `entries_count` | integer | Total activity entries in the period |

**Interpreting the results:**
- `avg_energy_delta` < 0 means activities are draining on average. A value of -1.5 means on average, energy drops 1.5 points per activity.
- `avg_energy_delta` > 0 means activities are energizing on average (rare but possible for well-matched tasks).
- Compare `total_completed` vs `total_skipped + total_deferred` for a completion ratio.
- `entries_count` includes all action types, not just completed/skipped/deferred.

**Example:**

```bash
curl "http://localhost:8000/api/reports/activity-summary?after=2026-03-01T00:00:00Z&before=2026-03-31T23:59:59Z"
```

```json
{
  "period_start": "2026-03-01T00:00:00+00:00",
  "period_end": "2026-03-31T23:59:59+00:00",
  "total_completed": 42,
  "total_skipped": 5,
  "total_deferred": 8,
  "total_duration_minutes": 1890,
  "avg_energy_delta": -0.5,
  "avg_mood": 3.7,
  "entries_count": 63
}
```

### `GET /api/reports/domain-balance`

Per-domain counts of active items and recency. Answers: "Which life areas are getting attention and which are being neglected?"

**Query parameters:** None

**Response:** `200 OK` -- `list[DomainBalanceResponse]`

One entry per domain, ordered by `sort_order` then `name`.

| Field | Type | Description |
|-------|------|-------------|
| `domain_id` | UUID | Domain identifier |
| `domain_name` | string | Domain name |
| `active_goals` | integer | Goals with `status = "active"` in this domain |
| `active_projects` | integer | Projects with `status = "active"` under this domain's goals |
| `pending_tasks` | integer | Tasks with `status = "pending"` under this domain's projects |
| `overdue_tasks` | integer | Tasks past `due_date` and not completed/skipped/abandoned, under this domain's projects |
| `days_since_last_activity` | integer or null | Days since the most recent activity log entry referencing a task or routine in this domain. Null if no activity exists. |

**Important:** `pending_tasks` and `overdue_tasks` only count tasks nested under projects in this domain. Standalone tasks (no project) are not included in domain balance.

**Interpreting the results:**
- High `days_since_last_activity` signals a neglected domain.
- `overdue_tasks` > 0 shows urgency within a domain.
- Domains with `active_goals` > 0 but `pending_tasks` = 0 may need new tasks created.

**Example:**

```bash
curl http://localhost:8000/api/reports/domain-balance
```

```json
[
  {
    "domain_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "domain_name": "House",
    "active_goals": 2,
    "active_projects": 3,
    "pending_tasks": 8,
    "overdue_tasks": 1,
    "days_since_last_activity": 3
  },
  {
    "domain_id": "b2c3d4e5-f6a7-8901-bcde-f12345678902",
    "domain_name": "Network",
    "active_goals": 1,
    "active_projects": 1,
    "pending_tasks": 4,
    "overdue_tasks": 0,
    "days_since_last_activity": 14
  }
]
```

### `GET /api/reports/routine-adherence`

Per-routine completion rates and streak health. Answers: "How consistently am I maintaining my routines?"

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `after` | datetime | **yes** | Start of the reporting period (inclusive) |
| `before` | datetime | **yes** | End of the reporting period (inclusive) |

**Response:** `200 OK` -- `list[RoutineAdherenceResponse]`

One entry per active or paused routine.

| Field | Type | Description |
|-------|------|-------------|
| `routine_id` | UUID | Routine identifier |
| `routine_title` | string | Routine name |
| `domain_name` | string | Parent domain name |
| `frequency` | string | Routine frequency |
| `completions_in_period` | integer | Activity log entries with `action_type = "completed"` for this routine in the period |
| `expected_in_period` | integer | Calculated expected completions based on frequency and date range |
| `adherence_pct` | float | `completions / expected * 100`, capped at 100.0. 0.0 if expected is 0. |
| `current_streak` | integer | Current consecutive completions (from the routine record) |
| `best_streak` | integer | All-time best streak |
| `streak_is_broken` | boolean | `true` if `current_streak = 0` and routine is active |

**How expected completions are calculated:**
- `daily`: one per day in the range
- `weekdays`: one per Monday-Friday in the range
- `weekends`: one per Saturday-Sunday in the range
- `weekly`: `ceil(total_days / 7)`
- `custom`: counts days in range that match the routine's schedule entries' `day_of_week` values. Falls back to `ceil(total_days / 7)` if no schedule entries.

**Interpreting the results:**
- `adherence_pct` < 50% suggests the routine frequency may be too aggressive.
- `streak_is_broken: true` flags routines that need attention.
- Compare `completions_in_period` across routines to spot which ones are consistently skipped.

**Example:**

```bash
curl "http://localhost:8000/api/reports/routine-adherence?after=2026-03-01T00:00:00Z&before=2026-03-31T23:59:59Z"
```

```json
[
  {
    "routine_id": "f6a7b8c9-d0e1-2345-fabcd-456789012345",
    "routine_title": "Saturday morning house maintenance",
    "domain_name": "House",
    "frequency": "weekly",
    "completions_in_period": 3,
    "expected_in_period": 5,
    "adherence_pct": 60.0,
    "current_streak": 2,
    "best_streak": 8,
    "streak_is_broken": false
  },
  {
    "routine_id": "a0b1c2d3-e4f5-6789-abcd-012345678901",
    "routine_title": "Evening kitchen reset",
    "domain_name": "House",
    "frequency": "daily",
    "completions_in_period": 25,
    "expected_in_period": 31,
    "adherence_pct": 80.6,
    "current_streak": 5,
    "best_streak": 14,
    "streak_is_broken": false
  }
]
```

### `GET /api/reports/friction-analysis`

Predicted vs. actual friction by cognitive type. Answers: "Am I overestimating or underestimating how hard things are to start?"

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `after` | datetime | no | Start of analysis period. Defaults to 30 days ago. |
| `before` | datetime | no | End of analysis period. Defaults to now. |

**Response:** `200 OK` -- `list[FrictionAnalysisResponse]`

One entry per cognitive type that has activity in the period.

| Field | Type | Description |
|-------|------|-------------|
| `cognitive_type` | string | The cognitive type being analyzed |
| `task_count` | integer | Total activity entries involving tasks of this cognitive type |
| `avg_predicted_friction` | float | Average `activation_friction` from the task definitions |
| `avg_actual_friction` | float | Average `friction_actual` from the activity log entries |
| `friction_gap` | float | `avg_predicted - avg_actual`. Positive = overestimating friction. Negative = underestimating. |
| `completion_rate` | float | Percentage of entries that were completions (vs. skipped/deferred) |
| `avg_energy_cost` | float | Average `energy_cost` from the task definitions |
| `avg_energy_delta` | float or null | Average `(energy_after - energy_before)` from activity entries. Null if no entries have both. |

**Interpreting the results:**
- `friction_gap` > 0 means you're overestimating how hard tasks of this type are to start. The actual experience is easier than anticipated.
- `friction_gap` < 0 means you're underestimating -- these tasks are harder to start than you predict.
- Cognitive types with low `completion_rate` and high `avg_predicted_friction` are avoidance candidates.
- Compare `avg_energy_cost` with `avg_energy_delta` to see whether energy-expensive tasks actually drain as much as expected.

**Example:**

```bash
curl "http://localhost:8000/api/reports/friction-analysis?after=2026-03-01T00:00:00Z&before=2026-03-31T23:59:59Z"
```

```json
[
  {
    "cognitive_type": "admin",
    "task_count": 12,
    "avg_predicted_friction": 3.5,
    "avg_actual_friction": 2.1,
    "friction_gap": 1.4,
    "completion_rate": 75.0,
    "avg_energy_cost": 2.0,
    "avg_energy_delta": -0.3
  },
  {
    "cognitive_type": "communication",
    "task_count": 8,
    "avg_predicted_friction": 4.0,
    "avg_actual_friction": 4.2,
    "friction_gap": -0.2,
    "completion_rate": 50.0,
    "avg_energy_cost": 3.5,
    "avg_energy_delta": -1.5
  }
]
```

---

## Composable Filter Reference

### Task Filters

The `GET /api/tasks` endpoint has the richest query surface in the API. All filter parameters are optional and combine with AND logic -- supplying multiple filters narrows the result set.

#### Filter parameters

| Parameter | Type | Behavior |
|-----------|------|----------|
| `project_id` | UUID | Exact match on parent project |
| `standalone` | boolean | `true` returns only tasks with `project_id IS NULL`. The `false` value has no special behavior (all tasks are returned). |
| `status` | string | Exact match. Values: `pending`, `active`, `completed`, `skipped`, `deferred` |
| `cognitive_type` | string | Exact match. Values: `hands_on`, `communication`, `decision`, `errand`, `admin`, `focus_work` |
| `energy_cost_min` | integer | `energy_cost >= value` (inclusive lower bound) |
| `energy_cost_max` | integer | `energy_cost <= value` (inclusive upper bound) |
| `friction_min` | integer | `activation_friction >= value` (inclusive lower bound) |
| `friction_max` | integer | `activation_friction <= value` (inclusive upper bound) |
| `context_required` | string | Exact match on context string |
| `due_before` | date | `due_date <= value` (inclusive). Tasks without a due date are excluded. |
| `due_after` | date | `due_date >= value` (inclusive). Tasks without a due date are excluded. |
| `overdue` | boolean | `true` returns tasks where `due_date < today AND status NOT IN ('completed', 'skipped')`. |

#### Range queries

`energy_cost_min`/`energy_cost_max` and `friction_min`/`friction_max` can be used individually or together:

- `energy_cost_max=2` -- low-energy tasks only
- `energy_cost_min=4` -- high-energy tasks only
- `energy_cost_min=2&energy_cost_max=3` -- medium-energy tasks
- `friction_max=1` -- zero-friction tasks (easiest to start)

#### Date filtering

- `due_before=2026-04-01` -- tasks due on or before April 1st
- `due_after=2026-03-25&due_before=2026-04-01` -- tasks due within a specific window
- `overdue=true` -- tasks past their due date (excludes completed and skipped)

#### Example filter combinations

**"What can I do right now with low energy at home?"**

```bash
curl "http://localhost:8000/api/tasks?status=pending&energy_cost_max=2&friction_max=2&context_required=at_home"
```

**"Show me all focus work that's overdue"**

```bash
curl "http://localhost:8000/api/tasks?cognitive_type=focus_work&overdue=true"
```

**"What errands do I need to run this week?"**

```bash
curl "http://localhost:8000/api/tasks?cognitive_type=errand&status=pending&due_before=2026-04-04"
```

### Other list endpoint filters

#### Goals (`GET /api/goals`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `domain_id` | UUID | Filter by parent domain |
| `status` | string | `active`, `paused`, `achieved`, `abandoned` |

#### Projects (`GET /api/projects`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `goal_id` | UUID | Filter by parent goal |
| `status` | string | `not_started`, `active`, `blocked`, `completed`, `abandoned` |
| `has_deadline` | boolean | `true` for projects with a deadline set |
| `overdue` | boolean | `true` for projects past deadline, not completed/abandoned |

#### Routines (`GET /api/routines`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `domain_id` | UUID | Filter by parent domain |
| `status` | string | `active`, `paused`, `retired` |
| `frequency` | string | `daily`, `weekdays`, `weekends`, `weekly`, `custom` |
| `streak_broken` | boolean | `true` for active routines with `current_streak = 0` |

#### Tags (`GET /api/tags`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Case-insensitive substring match on tag name |

#### Check-ins (`GET /api/checkins`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `checkin_type` | string | `morning`, `midday`, `evening`, `micro`, `freeform` |
| `context` | string | Exact match on context |
| `logged_after` | datetime | Check-ins logged on or after this timestamp |
| `logged_before` | datetime | Check-ins logged on or before this timestamp |

#### Activity Log (`GET /api/activity`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `action_type` | string | `completed`, `skipped`, `deferred`, `started`, `reflected`, `checked_in` |
| `task_id` | UUID | Filter by associated task |
| `routine_id` | UUID | Filter by associated routine |
| `logged_after` | datetime | Entries logged on or after this timestamp |
| `logged_before` | datetime | Entries logged on or before this timestamp |
| `has_task` | boolean | `true`/`false` to filter by presence of task reference |
| `has_routine` | boolean | `true`/`false` to filter by presence of routine reference |

---

## Endpoint Index

Quick reference of all 53 endpoints.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| **Domains** | | |
| `POST` | `/api/domains` | Create domain |
| `GET` | `/api/domains` | List domains |
| `GET` | `/api/domains/{domain_id}` | Get domain with goals |
| `PATCH` | `/api/domains/{domain_id}` | Update domain |
| `DELETE` | `/api/domains/{domain_id}` | Delete domain (cascades) |
| **Goals** | | |
| `POST` | `/api/goals` | Create goal |
| `GET` | `/api/goals` | List goals (filter: domain_id, status) |
| `GET` | `/api/goals/{goal_id}` | Get goal with projects |
| `PATCH` | `/api/goals/{goal_id}` | Update goal |
| `DELETE` | `/api/goals/{goal_id}` | Delete goal (cascades) |
| **Projects** | | |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects` | List projects (filter: goal_id, status, has_deadline, overdue) |
| `GET` | `/api/projects/{project_id}` | Get project with tasks |
| `PATCH` | `/api/projects/{project_id}` | Update project |
| `DELETE` | `/api/projects/{project_id}` | Delete project (cascades) |
| **Tasks** | | |
| `POST` | `/api/tasks` | Create task |
| `GET` | `/api/tasks` | List tasks (12 composable filters) |
| `GET` | `/api/tasks/{task_id}` | Get task with tags |
| `PATCH` | `/api/tasks/{task_id}` | Update task (auto-manages completed_at) |
| `DELETE` | `/api/tasks/{task_id}` | Delete task |
| **Tags** | | |
| `POST` | `/api/tags` | Create or retrieve tag (get-or-create) |
| `GET` | `/api/tags` | List tags (filter: search) |
| `GET` | `/api/tags/{tag_id}` | Get tag |
| `PATCH` | `/api/tags/{tag_id}` | Update tag |
| `DELETE` | `/api/tags/{tag_id}` | Delete tag (cascades associations) |
| `GET` | `/api/tags/{tag_id}/tasks` | List tasks with this tag |
| **Task-Tag Associations** | | |
| `GET` | `/api/tasks/{task_id}/tags` | List tags on a task |
| `POST` | `/api/tasks/{task_id}/tags/{tag_id}` | Attach tag to task (idempotent) |
| `DELETE` | `/api/tasks/{task_id}/tags/{tag_id}` | Detach tag from task |
| **Routines** | | |
| `POST` | `/api/routines` | Create routine |
| `GET` | `/api/routines` | List routines (filter: domain_id, status, frequency, streak_broken) |
| `GET` | `/api/routines/{routine_id}` | Get routine with schedules |
| `PATCH` | `/api/routines/{routine_id}` | Update routine |
| `DELETE` | `/api/routines/{routine_id}` | Delete routine (cascades schedules) |
| `POST` | `/api/routines/{routine_id}/complete` | Record completion (evaluates streak) |
| `POST` | `/api/routines/{routine_id}/schedules` | Add schedule entry |
| `GET` | `/api/routines/{routine_id}/schedules` | List schedule entries |
| `DELETE` | `/api/routines/{routine_id}/schedules/{schedule_id}` | Delete schedule entry |
| **Check-ins** | | |
| `POST` | `/api/checkins` | Create check-in |
| `GET` | `/api/checkins` | List check-ins (filter: checkin_type, context, logged_after, logged_before) |
| `GET` | `/api/checkins/{checkin_id}` | Get check-in |
| `PATCH` | `/api/checkins/{checkin_id}` | Update check-in |
| `DELETE` | `/api/checkins/{checkin_id}` | Delete check-in |
| **Activity Log** | | |
| `POST` | `/api/activity` | Create activity entry |
| `GET` | `/api/activity` | List activity (filter: action_type, task_id, routine_id, logged_after, logged_before, has_task, has_routine) |
| `GET` | `/api/activity/{entry_id}` | Get activity with resolved references |
| `PATCH` | `/api/activity/{entry_id}` | Update activity entry |
| `DELETE` | `/api/activity/{entry_id}` | Delete activity entry |
| **Reports** | | |
| `GET` | `/api/reports/activity-summary` | Activity stats for period (required: after, before) |
| `GET` | `/api/reports/domain-balance` | Per-domain health snapshot (no params) |
| `GET` | `/api/reports/routine-adherence` | Routine completion rates (required: after, before) |
| `GET` | `/api/reports/friction-analysis` | Predicted vs actual friction (optional: after, before) |

---

*API Reference -- BRAIN 3.0 v1.0.0*
*Generated by Apollo Swagger -- Project Flux Meridian -- March 2026*
