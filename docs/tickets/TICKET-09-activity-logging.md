## Summary

Build the CRUD API endpoints for the Activity Log — the record of what actually happened in BRAIN 3.0. Activity log entries capture task completions, routine executions, state reflections, and how the user felt during each activity. This is the data layer that powers pattern recognition and self-awareness reporting.

## Context

- **Scope:** Activity log CRUD with filtered listing. Log entries are created explicitly (by Claude or the user), not automatically as side effects of other actions. Heavier aggregation and pattern queries come in ticket #10.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model: Pillar 7) and 5 (Database Schema: activity_log table)

## Deliverables

- `app/schemas/activity.py` — Pydantic schemas for ActivityLog
- `app/routers/activity.py` — Activity log CRUD endpoints
- Router registration in `app/main.py`

## Pydantic Schemas

**ActivityLogCreate:**
- `task_id` (UUID, optional — references a task this entry is about)
- `routine_id` (UUID, optional — references a routine this entry is about)
- `checkin_id` (UUID, optional — references a check-in this entry is about)
- `action_type` (str, required. Valid: completed, skipped, deferred, started, reflected, checked_in)
- `notes` (text, optional — freeform observations about the activity)
- `energy_before` (int, optional — 1-5 scale)
- `energy_after` (int, optional — 1-5 scale)
- `mood_rating` (int, optional — 1-5 scale)
- `friction_actual` (int, optional — 1-5, actual experienced friction vs predicted)
- `duration_minutes` (int, optional — how long the activity actually took)

**ActivityLogUpdate:**
- All fields optional

**ActivityLogResponse:**
- All fields plus `id` (UUID), `logged_at` (datetime)

**ActivityLogDetailResponse:**
- Extends ActivityLogResponse with resolved references: `task` (TaskResponse, nullable), `routine` (RoutineResponse, nullable), `checkin` (CheckinResponse, nullable)

## API Endpoints

### Activity Log — `/api/activity`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/activity` | Create a log entry | ActivityLogResponse |
| GET | `/api/activity` | List log entries (with filters) | list[ActivityLogResponse] |
| GET | `/api/activity/{id}` | Get log entry with resolved references | ActivityLogDetailResponse |
| PATCH | `/api/activity/{id}` | Update a log entry | ActivityLogResponse |
| DELETE | `/api/activity/{id}` | Delete a log entry | 204 No Content |

### Activity Log List Filters

| Parameter | Type | Description |
|-----------|------|-------------|
| `action_type` | str | Filter by action type (completed, skipped, deferred, etc.) |
| `task_id` | UUID | Entries about a specific task |
| `routine_id` | UUID | Entries about a specific routine |
| `logged_after` | datetime | Entries logged after this timestamp |
| `logged_before` | datetime | Entries logged before this timestamp |
| `has_task` | bool | Entries that reference any task (true) or no task (false) |
| `has_routine` | bool | Entries that reference any routine (true) or no routine (false) |

**Example queries Claude would make:**
- `GET /api/activity?action_type=completed&logged_after=2026-03-19T00:00:00` — "what did you get done today?"
- `GET /api/activity?task_id=UUID` — "history for this specific task"
- `GET /api/activity?routine_id=UUID&action_type=completed` — "completion history for this routine"
- `GET /api/activity?action_type=skipped&logged_after=2026-03-01` — "what have you been skipping this month?"
- `GET /api/activity?logged_after=2026-03-13&logged_before=2026-03-20` — "this week's activity"

## Acceptance Criteria

- [ ] Pydantic schemas defined for ActivityLog (Create, Update, Response, DetailResponse)
- [ ] All five activity log endpoints working and returning correct response schemas
- [ ] Only `action_type` is required — all other fields are optional
- [ ] An entry can reference a task, a routine, a check-in, or none of them (standalone reflection)
- [ ] An entry should reference at most one of task_id, routine_id, or checkin_id — validate that no more than one is provided
- [ ] `logged_at` is auto-set to current timestamp on creation (server-side)
- [ ] `GET /api/activity/{id}` returns the log entry with resolved task/routine/checkin objects (not just IDs)
- [ ] List filters working: action_type, task_id, routine_id, logged_after, logged_before, has_task, has_routine
- [ ] Date range filters are composable
- [ ] Results ordered by `logged_at` descending by default (most recent first)
- [ ] Validation: energy_before, energy_after, mood_rating, friction_actual reject values outside 1-5 range
- [ ] Validation: action_type rejects invalid values
- [ ] Validation: referenced task_id, routine_id, checkin_id must exist if provided (return 400 for invalid references)
- [ ] PATCH allows updating any field after creation
- [ ] DELETE returns 204 on success, 404 for invalid UUIDs
- [ ] All endpoints visible and testable at `/docs`

## Technical Notes

- Activity log entries are created explicitly by Claude or the user. There are no automatic side effects from other endpoints (e.g. completing a task does not auto-create a log entry). Claude is responsible for orchestrating: complete the task via PATCH, then log the activity via POST.
- The `friction_actual` field is designed to be compared against `activation_friction` on the referenced task. This comparison powers insights like "you consistently overestimate how hard phone calls are."
- The `energy_before` / `energy_after` pair tracks energy delta across an activity. Over time, this reveals which activities are energizing vs draining.
- Consider: should `duration_minutes` accept null (not tracked) vs 0 (instantaneous)? Null is safer — not every activity has a meaningful duration.
- The detail endpoint resolving references (returning full task/routine/checkin objects) is important for Claude's reasoning — it can see the full context without making additional API calls.

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models — ActivityLog model)
- Ticket #4 (establishes schema and router patterns)
- Ticket #5 (Task endpoints — for resolved references)
- Ticket #7 (Routine endpoints — for resolved references)
- Ticket #8 (Check-in endpoints — for resolved references)
