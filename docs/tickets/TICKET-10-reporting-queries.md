## Summary

Build the aggregation and pattern-recognition endpoints that power Claude's reasoning as a partner. These are the queries that let Claude move beyond "what tasks do you have?" to "how are you actually doing?" — weekly summaries, domain balance monitoring, routine health, and friction pattern analysis.

## Context

- **Scope:** Four dedicated aggregation endpoints that require cross-table queries. Claude composes simpler insights from the existing CRUD filters (tickets #4-9). This ticket fills the gap for queries that would be painful to assemble from basic CRUD.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 6 (MCP Tool Contract: Reporting and Patterns) and 7 (ADHD-Specific Design Principles: Pattern Visibility)

## Deliverables

- `app/schemas/reports.py` — Pydantic response schemas for each report
- `app/routers/reports.py` — Aggregation query endpoints
- Router registration in `app/main.py`

## API Endpoints

### Reports — `/api/reports`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/reports/activity-summary` | Aggregated activity stats for a date range |
| GET | `/api/reports/domain-balance` | Per-domain counts of active items and recency |
| GET | `/api/reports/routine-adherence` | Per-routine completion rates and streak health |
| GET | `/api/reports/friction-analysis` | Predicted vs actual friction by cognitive type |

---

### 1. Activity Summary

`GET /api/reports/activity-summary?after=DATETIME&before=DATETIME`

**Purpose:** "How did my week go?" — the endpoint Claude uses for daily and weekly reflections.

**Parameters:**
- `after` (datetime, required) — start of date range
- `before` (datetime, required) — end of date range

**Response schema — `ActivitySummaryResponse`:**
- `period_start` (datetime)
- `period_end` (datetime)
- `total_completed` (int — count of action_type=completed)
- `total_skipped` (int — count of action_type=skipped)
- `total_deferred` (int — count of action_type=deferred)
- `total_duration_minutes` (int — sum of duration_minutes where not null)
- `avg_energy_delta` (float — average of energy_after minus energy_before, where both are present)
- `avg_mood` (float — average mood_rating where not null)
- `entries_count` (int — total log entries in the period)

---

### 2. Domain Balance

`GET /api/reports/domain-balance`

**Purpose:** "What areas of my life am I neglecting?" — lets Claude detect imbalance and surface forgotten domains.

**Parameters:** None required. Returns all domains.

**Response schema — list of `DomainBalanceResponse`:**
- `domain_id` (UUID)
- `domain_name` (str)
- `active_goals` (int — goals with status=active in this domain)
- `active_projects` (int — projects with status=active under this domain's goals)
- `pending_tasks` (int — tasks with status=pending under this domain's projects)
- `overdue_tasks` (int — tasks past due_date, not completed/skipped, under this domain)
- `days_since_last_activity` (int, nullable — days since the most recent activity log entry referencing a task or routine in this domain. Null if no activity ever recorded.)

---

### 3. Routine Adherence

`GET /api/reports/routine-adherence?after=DATETIME&before=DATETIME`

**Purpose:** "Which routines are holding and which are slipping?" — powers Claude's routine health monitoring and redesign suggestions.

**Parameters:**
- `after` (datetime, required) — start of date range
- `before` (datetime, required) — end of date range

**Response schema — list of `RoutineAdherenceResponse`:**
- `routine_id` (UUID)
- `routine_title` (str)
- `domain_name` (str)
- `frequency` (str)
- `completions_in_period` (int — count of activity log entries with action_type=completed for this routine in the date range)
- `expected_in_period` (int — calculated from frequency and date range. E.g. a daily routine over 7 days expects 7.)
- `adherence_pct` (float — completions / expected * 100, capped at 100)
- `current_streak` (int — from the routine record)
- `best_streak` (int — from the routine record)
- `streak_is_broken` (bool — current_streak is 0 and status is active)

---

### 4. Friction Analysis

`GET /api/reports/friction-analysis`

**Purpose:** "What am I avoiding, and is my avoidance justified?" — the self-awareness engine that surfaces ADHD friction patterns.

**Parameters:**
- `after` (datetime, optional — defaults to 30 days ago)
- `before` (datetime, optional — defaults to now)

**Response schema — list of `FrictionAnalysisResponse`:**
- `cognitive_type` (str)
- `task_count` (int — total tasks of this type with activity in the period)
- `avg_predicted_friction` (float — average activation_friction from the referenced tasks)
- `avg_actual_friction` (float — average friction_actual from the activity log entries)
- `friction_gap` (float — avg_predicted minus avg_actual. Positive means you overestimate difficulty.)
- `completion_rate` (float — completed / (completed + skipped + deferred) * 100)
- `avg_energy_cost` (float — average energy_cost from the referenced tasks)
- `avg_energy_delta` (float — average energy_after minus energy_before)

## Acceptance Criteria

- [ ] Pydantic response schemas defined for all four reports
- [ ] Activity summary endpoint returns correct aggregations for a date range
- [ ] Activity summary handles empty date ranges gracefully (returns zeros)
- [ ] Domain balance returns all domains with accurate counts
- [ ] Domain balance correctly calculates days_since_last_activity across the domain hierarchy (domain → goals → projects → tasks → activity log)
- [ ] Domain balance returns null for days_since_last_activity when no activity exists for a domain
- [ ] Routine adherence calculates expected completions correctly for each frequency type (daily, weekdays, weekends, weekly)
- [ ] Routine adherence caps adherence_pct at 100 (completing extra doesn't exceed 100%)
- [ ] Friction analysis groups by cognitive_type and calculates averages correctly
- [ ] Friction analysis only includes cognitive types that have activity log entries in the period
- [ ] All endpoints return well-structured JSON matching the defined schemas
- [ ] All endpoints handle edge cases: no data in period, no activity log entries, routines with no completions
- [ ] Date range parameters use consistent datetime format across all endpoints
- [ ] All endpoints visible and testable at `/docs`

## Technical Notes

- These endpoints are read-only — no POST, PATCH, or DELETE.
- The domain balance query is the most complex join: domains → goals → projects → tasks → activity_log. Consider using SQLAlchemy subqueries or CTEs to keep it manageable.
- For routine adherence expected count calculation:
  - `daily` = number of days in the period
  - `weekdays` = number of weekdays (Mon-Fri) in the period
  - `weekends` = number of weekend days (Sat-Sun) in the period
  - `weekly` = number of weeks in the period (rounded up)
  - `custom` = count of scheduled days that fall within the period (using routine_schedule entries)
- The friction analysis needs to join activity_log → tasks to compare predicted vs actual. Only include entries where both friction values exist.
- Consider caching or query optimization if these endpoints become slow as data grows — but premature optimization isn't needed for Phase 1.
- These are the endpoints Claude will call most frequently during reflective conversations. Response time matters for conversational flow.

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models and database tables)
- Ticket #5 (Task model with cognitive_type, energy_cost, activation_friction)
- Ticket #7 (Routine model with frequency, streaks)
- Ticket #9 (Activity log entries with friction_actual, energy_before/after, mood_rating)
