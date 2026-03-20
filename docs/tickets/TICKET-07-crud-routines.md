## Summary

Build the CRUD API endpoints for Routines and Routine Schedules — the behavioral commitment layer of BRAIN 3.0. Routines are modeled separately from tasks because they represent patterns the user is actively building, not one-off actions. This ticket includes streak tracking logic and a dedicated completion endpoint.

## Context

- **Scope:** Routine and RoutineSchedule CRUD, plus a dedicated completion endpoint with streak evaluation logic. Follows patterns from ticket #4.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model: Pillar 5) and 5 (Database Schema: routines, routine_schedule tables)

## Deliverables

- `app/schemas/routines.py` — Pydantic schemas for Routine and RoutineSchedule
- `app/routers/routines.py` — Routine CRUD, schedule management, and completion endpoint
- Router registration in `app/main.py`

## Pydantic Schemas

### Routine Schemas

**RoutineCreate:**
- `domain_id` (UUID, required)
- `title` (str, required)
- `description` (str, optional)
- `frequency` (str, required. Valid: daily, weekdays, weekends, weekly, custom)
- `status` (str, optional — default "active". Valid: active, paused, retired)
- `energy_cost` (int, optional — 1-5 scale)
- `activation_friction` (int, optional — 1-5 scale)

**RoutineUpdate:**
- All fields optional

**RoutineResponse:**
- All fields plus `id` (UUID), `current_streak` (int), `best_streak` (int), `last_completed` (date, nullable), `created_at`, `updated_at`

**RoutineDetailResponse:**
- Extends RoutineResponse with `schedules` (list of RoutineScheduleResponse)

### RoutineSchedule Schemas

**RoutineScheduleCreate:**
- `day_of_week` (str, required. Valid: monday, tuesday, wednesday, thursday, friday, saturday, sunday, any)
- `time_of_day` (str, required. Valid: morning, afternoon, evening, or specific HH:MM)
- `preferred_window` (str, optional — e.g. "06:00-10:00")

**RoutineScheduleResponse:**
- All fields plus `id` (UUID), `routine_id` (UUID)

### Completion Schema

**RoutineCompleteRequest:**
- `completed_date` (date, optional — defaults to today. Allows backdating a missed log.)

**RoutineCompleteResponse:**
- `routine_id` (UUID)
- `completed_date` (date)
- `current_streak` (int — after this completion)
- `best_streak` (int — after this completion)
- `streak_was_broken` (bool — whether the streak had to reset before incrementing)

## API Endpoints

### Routines — `/api/routines`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/routines` | Create a routine | RoutineResponse |
| GET | `/api/routines` | List routines (with filters) | list[RoutineResponse] |
| GET | `/api/routines/{id}` | Get routine with schedules | RoutineDetailResponse |
| PATCH | `/api/routines/{id}` | Partial update | RoutineResponse |
| DELETE | `/api/routines/{id}` | Delete routine | 204 No Content |
| POST | `/api/routines/{id}/complete` | Record a completion with streak logic | RoutineCompleteResponse |

### Routine Schedules — `/api/routines/{routine_id}/schedules`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/routines/{routine_id}/schedules` | Add a schedule entry | RoutineScheduleResponse |
| GET | `/api/routines/{routine_id}/schedules` | List schedule entries for a routine | list[RoutineScheduleResponse] |
| DELETE | `/api/routines/{routine_id}/schedules/{id}` | Remove a schedule entry | 204 No Content |

### Routine List Filters

- `?domain_id=UUID` — filter by domain
- `?status=active` — filter by status
- `?frequency=daily` — filter by frequency
- `?streak_broken=true` — routines where current_streak is 0 and status is active (helps Claude find routines that need attention)

## Streak Logic — `/api/routines/{id}/complete`

When a completion is recorded, the endpoint evaluates the streak:

1. **Determine expected gap.** Based on the routine's `frequency`:
   - `daily` — expected every day (max gap = 1 day)
   - `weekdays` — expected Mon-Fri (max gap = 1 weekday, accounting for weekends)
   - `weekends` — expected Sat-Sun (max gap = 1 weekend day, accounting for weekdays)
   - `weekly` — expected once per week (max gap = 7 days)
   - `custom` — use the schedule entries to determine expected days

2. **Compare gap to last_completed.** If `last_completed` is null (first ever completion) or the gap since `last_completed` exceeds the expected gap:
   - Set `current_streak` to 1 (reset and start fresh)
   - Set `streak_was_broken` to true (unless it's the first completion)
   
3. **If the gap is within expected range:**
   - Increment `current_streak` by 1
   - Set `streak_was_broken` to false

4. **Update best_streak** if `current_streak` now exceeds it.

5. **Update `last_completed`** to the completion date.

## Acceptance Criteria

- [ ] Pydantic schemas defined for Routine (Create, Update, Response, DetailResponse)
- [ ] Pydantic schemas defined for RoutineSchedule (Create, Response)
- [ ] Pydantic schemas defined for completion (Request, Response)
- [ ] All five Routine CRUD endpoints working
- [ ] Schedule management endpoints working (add, list, remove)
- [ ] `GET /api/routines/{id}` returns routine with nested schedules
- [ ] Routine list filters working: domain_id, status, frequency, streak_broken
- [ ] `POST /api/routines/{id}/complete` correctly evaluates streak on completion
- [ ] Streak increments when completed within expected gap
- [ ] Streak resets to 1 when gap exceeds expected frequency
- [ ] `best_streak` updates when `current_streak` surpasses it
- [ ] `streak_was_broken` flag accurately reported in completion response
- [ ] First-ever completion sets streak to 1 without reporting as broken
- [ ] `completed_date` parameter allows backdating (e.g. logging yesterday's completion today)
- [ ] Duplicate completion for the same date is handled gracefully (idempotent or error — developer's choice, but document the behavior)
- [ ] Validation: energy_cost and activation_friction reject values outside 1-5 range
- [ ] Validation: status and frequency fields reject invalid values
- [ ] All endpoints visible and testable at `/docs`

## Technical Notes

- The streak logic doesn't need to be perfect for every edge case in Phase 1. The scheduler in Phase 2 will add proactive detection of missed routines. For now, evaluation on completion is sufficient.
- The `custom` frequency with schedule-based gap detection is the most complex path. If implementation is getting unwieldy, it's acceptable to simplify custom to "use the longest gap between any two scheduled days" and refine later.
- Consider: should completing a routine also create an activity log entry? That connection comes in ticket #9, but the completion endpoint could be designed to accept optional energy/mood fields that get passed through.
- A routine with `status: paused` should not appear in streak_broken filters — pausing is intentional, not a break.

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models — Routine, RoutineSchedule models)
- Ticket #4 (establishes schema and router patterns)
