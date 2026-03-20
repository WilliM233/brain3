## Summary

Build the CRUD API endpoints for State Check-ins — the mindfulness and self-awareness layer of BRAIN 3.0. Check-ins capture how the user is doing at a point in time: energy, mood, focus, context, and freeform observations. The design prioritizes low friction — only the check-in type is required, everything else is optional.

## Context

- **Scope:** State check-in CRUD with date-range filtering. Standalone entities with no parent/child hierarchy. Follows patterns from ticket #4.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model: Pillar 6) and 5 (Database Schema: state_checkins table)

## Deliverables

- `app/schemas/checkins.py` — Pydantic schemas for StateCheckin
- `app/routers/checkins.py` — Check-in CRUD endpoints
- Router registration in `app/main.py`

## Pydantic Schemas

**CheckinCreate:**
- `checkin_type` (str, required. Valid: morning, midday, evening, micro, freeform)
- `energy_level` (int, optional — 1-5 scale)
- `mood` (int, optional — 1-5 scale)
- `focus_level` (int, optional — 1-5 scale)
- `freeform_note` (text, optional)
- `context` (str, optional. Examples: work_day, day_off, chaotic, travel, recovery)

**CheckinUpdate:**
- All fields optional

**CheckinResponse:**
- All fields plus `id` (UUID), `logged_at` (datetime)

## API Endpoints

### State Check-ins — `/api/checkins`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/checkins` | Log a check-in | CheckinResponse |
| GET | `/api/checkins` | List check-ins (with filters) | list[CheckinResponse] |
| GET | `/api/checkins/{id}` | Get check-in by ID | CheckinResponse |
| PATCH | `/api/checkins/{id}` | Update a check-in | CheckinResponse |
| DELETE | `/api/checkins/{id}` | Delete a check-in | 204 No Content |

### Check-in List Filters

| Parameter | Type | Description |
|-----------|------|-------------|
| `checkin_type` | str | Filter by type (morning, midday, evening, micro, freeform) |
| `context` | str | Filter by context (work_day, day_off, etc.) |
| `logged_after` | datetime | Check-ins logged after this timestamp |
| `logged_before` | datetime | Check-ins logged before this timestamp |

**Example queries Claude would make:**
- `GET /api/checkins?checkin_type=morning&logged_after=2026-03-01` — "morning check-ins this month"
- `GET /api/checkins?logged_after=2026-03-19T00:00:00&logged_before=2026-03-19T23:59:59` — "how have you been doing today?"
- `GET /api/checkins?context=chaotic` — "let's look at patterns on your chaotic days"

## Acceptance Criteria

- [ ] Pydantic schemas defined for CheckIn (Create, Update, Response)
- [ ] All five check-in endpoints working and returning correct response schemas
- [ ] Only `checkin_type` is required — all other fields are optional
- [ ] A check-in with only `checkin_type` and a `freeform_note` is valid
- [ ] A check-in with only `checkin_type` and numeric scales (no note) is valid
- [ ] `logged_at` is auto-set to current timestamp on creation (server-side)
- [ ] List filters working: checkin_type, context, logged_after, logged_before
- [ ] Date range filters are composable (both logged_after and logged_before can be used together)
- [ ] Results ordered by `logged_at` descending by default (most recent first)
- [ ] Validation: energy_level, mood, and focus_level reject values outside 1-5 range
- [ ] Validation: checkin_type rejects invalid values
- [ ] PATCH allows updating any field after creation
- [ ] DELETE returns 204 on success, 404 for invalid UUIDs
- [ ] All endpoints visible and testable at `/docs`

## Technical Notes

- Check-ins are intentionally low-friction. The system should accept whatever data the user provides — a fully structured morning check-in with all five fields or a quick freeform note with nothing else. Both are equally valid.
- `logged_at` defaults to server timestamp on creation but could be overridable in a future iteration (for backdating). For Phase 1, server timestamp is fine.
- The numeric scales (1-5) should be consistent across the system — same meaning as energy_cost and activation_friction on tasks and routines. This lets Claude compare "you said your energy was 2 this morning, so here are tasks that match that level."
- Consider returning check-ins in reverse chronological order by default — the most recent state is usually the most relevant.

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models — StateCheckin model)
- Ticket #4 (establishes schema and router patterns)
