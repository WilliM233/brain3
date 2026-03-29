# BRAIN 3.0 — User Acceptance Test Script
### v1.0.0 · Phase 5 · Human Testing

---

## Purpose

This script validates that every v1.0.0 feature works correctly through the MCP interface — the way real users will interact with BRAIN 3.0. It covers all seven pillars of the data model, all CRUD operations, composable filters, ADHD-specific metadata, reporting endpoints, and edge cases identified during QA.

**This is not a unit test.** Unit tests verify code paths. This script verifies that a human using BRAIN through Claude gets correct, useful results. If something passes the unit tests but fails here, it's a product bug.

## Prerequisites

- [ ] BRAIN 3.0 API running and accessible (test instance or production)
- [ ] MCP server connected and healthy (`health_check` returns `{"status": "healthy", "database": "connected"}`)
- [ ] Database is empty or test data has been cleared from previous runs
- [ ] Tester has read the BRAIN 3.0 partner instructions

## How to Use This Script

Work through each section in order. Each test has:
- **Action** — what to do or ask BRAIN to do
- **Expected** — what should happen
- **Result** — ✅ Pass, ❌ Fail, or ⚠️ Partial (note what went wrong)

Record results inline. When complete, file the results as a GitHub issue with label `uat-complete` (or `uat-blocked` if there are failures).

---

## Test 0: System Health

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 0.1 | Run `health_check` | Returns status: healthy, database: connected | |

---

## Test 1: Domains (Pillar 1)

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 1.1 | Create domain: "Health" with color "#22c55e" and description | Returns domain with UUID, name, color, timestamps | |
| 1.2 | Create domain: "House" with color "#3b82f6" | Returns domain with UUID | |
| 1.3 | Create domain: "Career" with color "#a855f7" | Returns domain with UUID | |
| 1.4 | `list_domains` | Returns all 3 domains | |
| 1.5 | `get_domain` on Health domain | Returns domain with empty goals list | |
| 1.6 | `update_domain` — rename "House" to "Home" | Returns updated domain with new name | |
| 1.7 | Create domain: "Temp" then `delete_domain` | Domain created, then deleted successfully | |
| 1.8 | `list_domains` after delete | Returns exactly 3 domains (Temp is gone) | |

---

## Test 2: Goals (Pillar 2)

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 2.1 | Create goal under Health: "Improve physical fitness" | Returns goal with UUID, domain_id matches Health | |
| 2.2 | Create goal under Home: "Keep the house maintained" | Returns goal with UUID | |
| 2.3 | Create goal under Career: "Transition to full stack development" | Returns goal with UUID | |
| 2.4 | `list_goals` with no filters | Returns all 3 goals | |
| 2.5 | `list_goals` filtered by Health domain_id | Returns only the Health goal | |
| 2.6 | `list_goals` filtered by status "active" | Returns all 3 (default status is active) | |
| 2.7 | `get_goal` on Health goal | Returns goal with empty projects list | |
| 2.8 | `update_goal` — pause the Career goal | Returns goal with status "paused" | |
| 2.9 | `list_goals` filtered by status "paused" | Returns only the Career goal | |
| 2.10 | `update_goal` — reactivate Career goal | Returns goal with status "active" | |
| 2.11 | `get_domain` on Health | Returns domain with nested Health goal | |

---

## Test 3: Projects (Pillar 3)

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 3.1 | Create project under fitness goal: "Complete C25K program" with deadline 2026-06-30 | Returns project with UUID, status "not_started" | |
| 3.2 | Create project under house goal: "Spring cleaning" with status "active" | Returns project with UUID, status "active" | |
| 3.3 | `list_projects` with no filters | Returns both projects | |
| 3.4 | `list_projects` filtered by status "active" | Returns only Spring cleaning | |
| 3.5 | `list_projects` filtered by has_deadline=true | Returns only C25K | |
| 3.6 | `get_project` on C25K | Returns project with empty tasks list | |
| 3.7 | `update_project` — set C25K to "active" | Returns project with status "active" | |
| 3.8 | `get_goal` on fitness goal | Returns goal with nested C25K project | |

---

## Test 4: Tasks (Pillar 4) — Core ADHD Metadata

This is the most critical section. Tasks carry the ADHD-specific metadata that makes BRAIN different from a generic task manager.

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 4.1 | Create task under C25K project: "Download C25K app" with energy_cost=1, activation_friction=1, cognitive_type="admin" | Returns task with all ADHD fields set, status "pending" | |
| 4.2 | Create task under C25K: "Run Week 1 Day 1" with energy_cost=4, activation_friction=3, cognitive_type="hands_on", context_required="outdoors" | Returns task with all fields | |
| 4.3 | Create task under Spring cleaning: "Clean out garage" with energy_cost=5, activation_friction=4, cognitive_type="hands_on", context_required="at_home" | Returns task with all fields | |
| 4.4 | Create task under Spring cleaning: "Order cleaning supplies" with energy_cost=1, activation_friction=2, cognitive_type="errand" | Returns task with all fields | |
| 4.5 | Create standalone task (no project): "Call dentist" with energy_cost=2, activation_friction=5, cognitive_type="communication" | Returns task with null project_id | |
| 4.6 | Create task with due_date: "File taxes" due 2026-04-15, energy_cost=4, activation_friction=5, cognitive_type="focus_work" | Returns task with due_date set | |
| 4.7 | `get_task` on "Call dentist" | Returns full task details including tags (empty) | |

---

## Test 5: Task Filters — Composable Queries

These filters are how BRAIN matches tasks to the user's current state. Every filter must work independently and in combination.

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 5.1 | `list_tasks` with no filters | Returns all 6 tasks | |
| 5.2 | `list_tasks` filtered by status "pending" | Returns all 6 (default status) | |
| 5.3 | `list_tasks` filtered by energy_cost_max=2 | Returns only low-energy tasks (Download app, Order supplies, Call dentist) | |
| 5.4 | `list_tasks` filtered by energy_cost_min=4 | Returns only high-energy tasks (Run W1D1, Clean garage, File taxes) | |
| 5.5 | `list_tasks` filtered by friction_max=2 | Returns low-friction tasks (Download app, Order supplies) | |
| 5.6 | `list_tasks` filtered by cognitive_type "hands_on" | Returns Run W1D1, Clean garage | |
| 5.7 | `list_tasks` filtered by cognitive_type "communication" | Returns only Call dentist | |
| 5.8 | `list_tasks` filtered by context_required "at_home" | Returns Clean garage | |
| 5.9 | `list_tasks` filtered by standalone=true | Returns Call dentist, File taxes (no project) | |
| 5.10 | `list_tasks` filtered by project_id (C25K) | Returns Download app, Run W1D1 | |
| 5.11 | Combined filter: energy_cost_max=2 AND friction_max=2 | Returns Download app, Order supplies | |
| 5.12 | `update_task` — mark "Download app" as completed | Returns task with status "completed", completed_at auto-set | |
| 5.13 | `list_tasks` filtered by status "completed" | Returns only Download app | |
| 5.14 | `list_tasks` filtered by status "pending" | Returns 5 tasks (Download app excluded) | |
| 5.15 | Set "File taxes" due_date to yesterday, then `list_tasks` with overdue=true | Returns File taxes as overdue | |

---

## Test 6: Tags — Cross-Cutting Organization

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 6.1 | `create_tag` name "quick-win" color "#22c55e" | Returns tag with UUID | |
| 6.2 | `create_tag` name "deep-focus" | Returns tag with UUID | |
| 6.3 | `create_tag` name "Quick-Win" (duplicate, different case) | Returns SAME tag as 6.1 (case-insensitive get-or-create) | |
| 6.4 | `list_tags` | Returns exactly 2 tags | |
| 6.5 | `list_tags` with search "quick" | Returns only quick-win tag | |
| 6.6 | `tag_task` — attach "quick-win" to "Order supplies" | Success | |
| 6.7 | `tag_task` — attach "quick-win" to "Download app" | Success | |
| 6.8 | `tag_task` — attach "deep-focus" to "File taxes" | Success | |
| 6.9 | `list_tagged_tasks` for "quick-win" tag | Returns Order supplies, Download app | |
| 6.10 | `list_task_tags` on "Order supplies" | Returns quick-win tag | |
| 6.11 | `tag_task` — attach "quick-win" to "Order supplies" again (idempotent) | No error, no duplicate | |
| 6.12 | `untag_task` — remove "quick-win" from "Download app" | Success | |
| 6.13 | `list_tagged_tasks` for "quick-win" | Returns only Order supplies now | |
| 6.14 | `update_tag` — rename "deep-focus" to "needs-focus" | Returns updated tag | |
| 6.15 | `get_tag` on renamed tag | Returns tag with name "needs-focus" | |

---

## Test 7: Routines (Pillar 5) — Behavioral Commitments

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 7.1 | Create routine under Health: "Morning walk" frequency "daily", energy_cost=2, activation_friction=2 | Returns routine with UUID, streak fields at 0 | |
| 7.2 | Create routine under Home: "Kitchen reset" frequency "daily", energy_cost=1, activation_friction=1 | Returns routine | |
| 7.3 | `list_routines` | Returns both routines | |
| 7.4 | `list_routines` filtered by domain_id (Health) | Returns only Morning walk | |
| 7.5 | `list_routines` filtered by frequency "daily" | Returns both | |
| 7.6 | `add_routine_schedule` — Morning walk: monday, 07:00, "morning" | Returns schedule entry | |
| 7.7 | `add_routine_schedule` — Morning walk: tuesday, 07:00, "morning" | Returns schedule entry | |
| 7.8 | `list_routine_schedules` for Morning walk | Returns 2 schedule entries | |
| 7.9 | `complete_routine` for Morning walk (today) | Returns updated streak: current_streak=1 | |
| 7.10 | `complete_routine` for Morning walk again (today) | Should handle gracefully (duplicate completion) | |
| 7.11 | `get_routine` for Morning walk | Shows current_streak, best_streak, last_completed | |
| 7.12 | `update_routine` — pause Kitchen reset | Returns routine with status "paused" | |
| 7.13 | `list_routines` filtered by status "active" | Returns only Morning walk | |
| 7.14 | `list_routines` filtered by streak_broken=true | Returns routines with broken streaks (if any) | |
| 7.15 | `delete_routine_schedule` — remove one Morning walk schedule | Success, `list_routine_schedules` returns 1 | |

---

## Test 8: Check-ins (Pillar 6) — Mindfulness & State

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 8.1 | `create_checkin` type "morning", energy=3, mood=4, focus=2, note "Slept okay, feeling decent" | Returns check-in with UUID and all fields | |
| 8.2 | `create_checkin` type "micro", energy=2, mood=3, context "after lunch" | Returns check-in | |
| 8.3 | `create_checkin` type "freeform", note only: "Feeling scattered today" | Returns check-in with only checkin_type and note (all numbers null) | |
| 8.4 | `list_checkins` | Returns all 3 check-ins | |
| 8.5 | `list_checkins` filtered by type "morning" | Returns only the morning check-in | |
| 8.6 | `list_checkins` filtered by date range (today) | Returns all 3 | |
| 8.7 | `get_checkin` on morning check-in | Returns full details | |
| 8.8 | `update_checkin` — change energy to 4 on morning check-in | Returns updated check-in | |
| 8.9 | `delete_checkin` on the freeform check-in | Success | |
| 8.10 | `list_checkins` | Returns 2 check-ins | |

---

## Test 9: Activity Log (Pillar 7) — What Actually Happened

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 9.1 | `log_activity` action "completed", task_id (Download app), energy_before=3, energy_after=3, friction_actual=1, duration=5, mood=4, notes "Easy win" | Returns activity entry with UUID | |
| 9.2 | `log_activity` action "completed", routine_id (Morning walk), energy_before=2, energy_after=4, duration=30, mood=4 | Returns activity entry | |
| 9.3 | `log_activity` action "skipped", task_id (Call dentist), notes "Phone anxiety, will try tomorrow" | Returns activity entry | |
| 9.4 | `log_activity` action "deferred", task_id (File taxes), notes "Too tired for focus work" | Returns activity entry | |
| 9.5 | `log_activity` action "reflected", notes "Good morning so far, energy better than expected" | Returns activity entry (no linked entity) | |
| 9.6 | `list_activity` | Returns all 5 entries, newest first | |
| 9.7 | `list_activity` filtered by action_type "completed" | Returns entries 9.1 and 9.2 | |
| 9.8 | `list_activity` filtered by has_task=true | Returns entries 9.1, 9.3, 9.4 | |
| 9.9 | `list_activity` filtered by has_routine=true | Returns entry 9.2 | |
| 9.10 | `list_activity` filtered by task_id (Call dentist) | Returns entry 9.3 | |
| 9.11 | `get_activity` on entry 9.1 | Returns full entry with resolved task details | |
| 9.12 | `update_activity` — add mood_rating=3 to entry 9.3 | Returns updated entry | |
| 9.13 | `delete_activity` on entry 9.5 | Success | |
| 9.14 | `list_activity` | Returns 4 entries | |

---

## Test 10: Reporting — Pattern Recognition

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 10.1 | `get_activity_summary` for today | Returns totals: completed count, skipped count, deferred count, total duration, avg energy delta, avg mood | |
| 10.2 | `get_domain_balance` | Returns all 3 domains with counts: active goals, projects, pending tasks, overdue tasks, days since last activity | |
| 10.3 | `get_routine_adherence` for the last 7 days | Returns Morning walk and Kitchen reset with completion rates and streak status | |
| 10.4 | `get_friction_analysis` | Returns predicted vs actual friction by cognitive type (should have data from activity logs) | |

---

## Test 11: Hierarchy & Cascades

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 11.1 | `get_domain` on Health | Returns domain → goal → project → tasks nested correctly | |
| 11.2 | `get_goal` on fitness goal | Returns goal with C25K project nested, including task list | |
| 11.3 | `get_project` on C25K | Returns project with both tasks and progress_pct reflecting 1 completed / 2 total | |
| 11.4 | Create a temp domain, goal, project, and task. Delete the domain. | All nested entities cascade-deleted. `list_goals`, `list_projects`, `list_tasks` should not return any of them. | |

---

## Test 12: Validation & Edge Cases

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 12.1 | Create task with energy_cost=6 (out of range) | 422 validation error | |
| 12.2 | Create task with cognitive_type="invalid" | 422 validation error with valid options listed | |
| 12.3 | Create goal with non-existent domain_id | 404 or 422 error | |
| 12.4 | Create project with non-existent goal_id | 404 or 422 error | |
| 12.5 | `log_activity` with both task_id and routine_id set | 422 error (at-most-one-reference constraint) | |
| 12.6 | `log_activity` with action_type="invalid" | 422 error with valid action types listed | |
| 12.7 | `update_activity` — set task_id to non-existent UUID | 422 error (entity existence validation) | |
| 12.8 | Create checkin with type "invalid" | 422 validation error | |
| 12.9 | `update_task` — revert completed task back to "pending" | completed_at should be cleared (set to null) | |
| 12.10 | `create_tag` with very long name (200+ chars) | 422 validation error (string length limit) | |

---

## Test 13: Task Lifecycle — Full Flow

This test simulates a real usage pattern: check in → find matching tasks → work on one → log the result.

| # | Action | Expected | Result |
|---|--------|----------|--------|
| 13.1 | `create_checkin` morning: energy=2, mood=3, focus=2, note "Low energy start" | Check-in logged | |
| 13.2 | `list_tasks` with energy_cost_max=2, friction_max=2, status="pending" | Returns only tasks matching low-energy state | |
| 13.3 | Pick a task from the results, `update_task` status to "active" | Task now active | |
| 13.4 | After "completing" it, `update_task` status to "completed" | Task completed, completed_at auto-set | |
| 13.5 | `log_activity` action "completed" with task_id, energy_before=2, energy_after=3, friction_actual=1, duration=10 | Activity logged with state data | |
| 13.6 | `get_activity_summary` for today | Summary reflects the completion | |
| 13.7 | `get_domain_balance` | Domain of completed task shows recent activity | |

---

## Cleanup

After all tests are complete:

| # | Action | Expected | Result |
|---|--------|----------|--------|
| C.1 | Delete all test activity log entries | All deleted | |
| C.2 | Delete all test check-ins | All deleted | |
| C.3 | Delete all test tags | All deleted | |
| C.4 | Delete all test routines | All deleted (cascades schedules and completions) | |
| C.5 | Delete all test domains (cascades goals → projects → tasks) | Database is clean | |
| C.6 | `list_domains` | Returns empty list | |
| C.7 | `list_tasks` | Returns empty list | |
| C.8 | `list_activity` | Returns empty list | |

---

## Results Summary

| Section | Tests | Pass | Fail | Partial | Notes |
|---------|-------|------|------|---------|-------|
| 0 — Health | 1 | | | | |
| 1 — Domains | 8 | | | | |
| 2 — Goals | 11 | | | | |
| 3 — Projects | 8 | | | | |
| 4 — Tasks | 7 | | | | |
| 5 — Filters | 15 | | | | |
| 6 — Tags | 15 | | | | |
| 7 — Routines | 15 | | | | |
| 8 — Check-ins | 10 | | | | |
| 9 — Activity | 14 | | | | |
| 10 — Reporting | 4 | | | | |
| 11 — Hierarchy | 4 | | | | |
| 12 — Validation | 10 | | | | |
| 13 — Lifecycle | 7 | | | | |
| Cleanup | 8 | | | | |
| **TOTAL** | **131** | | | | |

---

## Sign-Off

**Tester:** _______________
**Date:** _______________
**MCP target:** _______________
**API version:** _______________

**Verdict:**

- [ ] **PASS** — All tests pass. Ready for release.
- [ ] **PASS WITH NOTES** — All critical tests pass. Minor issues documented.
- [ ] **FAIL** — Blocking issues found. Issues filed. Retest required after fixes.

**Issues filed during UAT:**
- (List issue numbers and titles, or "None")

---

*UAT Script · BRAIN 3.0 v1.0.0*
*Project Flux Meridian · March 2026*
