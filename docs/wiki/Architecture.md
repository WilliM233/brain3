# Architecture

BRAIN 3.0's data model is organized around **seven pillars** — core concepts that together give the system a complete picture of what matters in your life, what needs doing, how you're maintaining your patterns, how you're feeling, and what actually happened.

For the full schema-level detail and technology rationale, see the [System Design Document](../BRAIN_3_0_Design_Document.md).

---

## The Seven Pillars

### 1. Domains

Life areas that cut across the entire system. Examples: House, Health, Finances, Network.

Domains are a **filtering and reporting layer** — every goal and routine belongs to a domain, and everything beneath them inherits that categorization. They're intentionally broad and stable; you might have 4-8 of them and they rarely change. The [domain balance report](API-Overview.md#reports) uses domains to show which areas of life are getting attention and which are being neglected.

### 2. Goals

Enduring outcomes that give everything else meaning. Goals answer the question: *why does this matter?*

Goals sit at the top of the hierarchy under domains. They rarely change. Examples: maintain the house, achieve financial stability, keep the network secure. When Claude acts as a partner, goals are the layer it uses to reason about priorities and notice neglected areas of life.

### 3. Projects

Bounded efforts with a beginning and an end, nested under goals. Projects have deadlines, progress tracking, and status. They represent the chunks of work that move a goal forward. Examples: remodel the bathroom, file 2026 taxes, segment VLANs.

A project's progress is tracked as a percentage, calculated from the completion state of its tasks.

### 4. Tasks

The atoms of action — and where BRAIN 3.0 diverges most from a generic task manager. Every task carries **ADHD-aware metadata**:

| Field | What It Captures | Scale |
|-------|-----------------|-------|
| `energy_cost` | How draining the task is, independent of time | 1-5 |
| `cognitive_type` | What kind of thinking it requires | hands_on, communication, decision, errand, admin, focus_work |
| `activation_friction` | How hard it is to *start*, regardless of how easy it is once going | 1-5 |
| `context_required` | Where you need to be or what you need | at_home, at_computer, at_store, needs_tools, etc. |

These fields let Claude match tasks to your current capacity. Low energy? Surface low-friction tasks. At the hardware store? Show everything tagged for that context across all projects. In a focus window? Offer the decision and admin tasks that benefit from that state.

Tasks can be standalone or belong to a project. They support recurrence via RRULE strings (iCalendar standard), and can be tagged for cross-cutting connections.

### 5. Routines

Behavioral patterns the user is actively building or maintaining — modeled as a **first-class concept separate from recurring tasks**.

A routine is not just a task that repeats. It's a commitment to a pattern of behavior. The system tracks streaks (current and best), monitors for pattern breaks, and responds differently when a routine is missed (encouragement, redesign suggestions) versus when a one-off task is overdue (simple rescheduling).

Routines have their own schedule system: each routine can have multiple schedule entries specifying day of week, time of day, and preferred time windows. This supports complex patterns like "weekday mornings and Saturday afternoons."

**Frequency options:** daily, weekdays, weekends, weekly, custom (with explicit schedule entries).

### 6. Check-ins (Mindfulness & State)

A continuous, low-friction layer for capturing internal state. Check-ins record:

- **Energy level** (1-5)
- **Mood** (1-5)
- **Focus level** (1-5)
- **Context** (work_day, day_off, chaotic, travel, etc.)
- **Freeform notes** for open-ended mindfulness observations

**Check-in types:** morning, midday, evening, micro (quick capture), freeform.

This data serves two purposes: it lets Claude match tasks to current capacity in real time, and it feeds the reporting layer so you can see correlations between internal state and productivity over time.

### 7. Activity Log

The record of what actually happened. Every task completion, routine execution, and state change generates a log entry. The log captures not just *what* was done but *how it felt*:

- Energy before and after
- Actual friction experienced (vs. predicted)
- Mood rating
- Duration
- Freeform notes

This is what makes BRAIN a learning system. Claude uses the log to recognize patterns — you avoid phone calls, you're most productive Saturday mornings, you overestimate evening capacity. You use it through reporting to build self-awareness and identify recurring friction points.

---

## How the Pillars Relate

```
Domains
  └── Goals
        └── Projects
              └── Tasks ←→ Tags (cross-cutting)
  └── Routines
        └── Routine Schedules

Check-ins (standalone — capture state at any time)

Activity Log (references tasks, routines, and/or check-ins)
```

Domains contain goals and routines. Goals contain projects. Projects contain tasks. Tasks can be tagged for connections that cut across the hierarchy (e.g., "home-depot" tags tasks in multiple projects).

Check-ins are standalone — they capture how you're feeling without being tied to a specific action.

The activity log ties everything together. Each entry can reference a task, a routine, and/or a check-in, recording what happened and how it felt. The four reporting endpoints aggregate this data to surface patterns.

---

## ADHD-Specific Design Principles

These aren't afterthought features. They're the reason the system exists.

### Friction Awareness

Every task carries explicit activation friction and energy cost. The system matches tasks to current capacity rather than presenting a flat list ordered by due date. When energy is low, BRAIN surfaces low-friction tasks. When momentum is high, it offers the harder items that benefit from that window.

### Context Batching

Tags and context requirements enable intelligent batching. Already at the hardware store? BRAIN knows what else you need from there across all projects. At your computer in a focus window? It surfaces the admin and decision tasks that require that context.

### Routine Scaffolding

Routines are modeled as behavioral commitments, not recurring tasks. The system distinguishes between a missed routine (a pattern to address) and a missed one-off task (something to reschedule). This reflects how ADHD brains relate to habits — routines are scaffolding that either holds or collapses, and the response to each is different.

### Pattern Visibility

Reporting surfaces recurring friction points, avoidance patterns, energy cycles, and routine adherence trends. This makes the invisible patterns of ADHD visible and concrete — not as judgment, but as self-knowledge that enables better decisions.

### Proactive Initiative (Phase 2+)

The system is designed to reach out rather than wait to be checked. The ADHD brain struggles with object permanence — if the system isn't visible, it ceases to exist. Phase 2 adds a scheduler and Home Assistant integration to deliver morning briefings, accountability nudges, and timely reminders through push notifications and voice.

---

## Design Decisions

Key architectural decisions that inform how the system works. These have been resolved and should not be revisited without discussion.

### Explicit Activity Logging

Activity log entries are created explicitly — there are no automatic side effects. When a routine is completed (via `POST /api/routines/{id}/complete`), the streak counter is updated, but **no activity log entry is created automatically**. The caller is responsible for creating a separate activity log entry (`POST /api/activity`) to record the completion with contextual data (energy, mood, friction, notes).

This is by design. The activity log captures *how it felt*, not just *that it happened*. Automatic logging would produce entries without the subjective metadata that makes the log valuable for pattern recognition. The MCP partner layer is responsible for pairing these calls — completing the routine and logging the activity together — so that the routine adherence report has the data it needs.

**Why this matters for reporting:** The [routine adherence report](API-Overview.md#reports) counts activity log entries with `action_type: "completed"` and a matching `routine_id` to calculate adherence percentages. If activity log entries aren't created alongside routine completions, the adherence report will show 0% even though the routine's streak counter is advancing.

### Recurrence via RRULE

Task recurrence uses RRULE strings (iCalendar standard) via the python-dateutil library. This handles all edge cases — month boundaries, leap years, complex schedules — through a well-tested standard. Claude generates and interprets the strings on behalf of the user; the user never touches the syntax directly.

### No Authentication (Phase 1)

BRAIN 3.0 is a single-user system running on a home network behind a firewall. The API runs with no authentication in Phase 1. The architecture uses a middleware pattern so that adding auth in Phase 3 (when the web UI exposes the system beyond localhost) is a single-layer addition.

### Tags Are Global

Tags have globally unique names (case-insensitive) and use a get-or-create pattern on POST. This means tagging a task with "home-depot" will reuse the existing tag rather than creating a duplicate. Tags connect tasks across projects and goals for cross-cutting queries.

### PostgreSQL Over SQLite

PostgreSQL was chosen for concurrent access support, LISTEN/NOTIFY (for future real-time UI), JSON columns, and full-text search. It runs in Docker on TrueNAS with nightly pg_dump backups and 30-day retention.
