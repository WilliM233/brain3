# BRAIN 3.0 — System Design Document

**AI-Powered Personal Operating System for ADHD**

Version 1.0 — March 2026 | Status: Architecture & Design Phase

---

## Table of Contents

1. [Vision & Philosophy](#1-vision--philosophy)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Data Model — The Seven Pillars](#4-data-model--the-seven-pillars)
5. [Database Schema](#5-database-schema)
6. [MCP Tool Contract](#6-mcp-tool-contract-phase-1)
7. [ADHD-Specific Design Principles](#7-adhd-specific-design-principles)
8. [Phased Delivery Plan](#8-phased-delivery-plan)
9. [Design Decisions](#9-design-decisions)

---

## 1. Vision & Philosophy

BRAIN 3.0 is a personal operating system designed to serve as an AI partner for managing life with ADHD. It is the third iteration of the BRAIN system, evolving from a static HTML page (1.0) through a SQLite-backed note-taking tool with Claude MCP access (2.0) into a fully autonomous, context-aware life management platform (3.0).

The core philosophy: the system has initiative, not just memory. Unlike a to-do app that waits to be checked, BRAIN 3.0 proactively surfaces the right task at the right time through the right channel. It understands energy, friction, cognitive type, and behavioral patterns — acting as a partner that does the executive function work so the user can focus on doing.

### Partner, Not Assistant

An assistant waits for instructions. A partner notices things, has opinions, pushes back when you are overloading yourself, and understands the bigger picture of what you are trying to accomplish. BRAIN 3.0 is designed as the latter. Claude, interfacing through the MCP, has full read/write access to the system and the context to reason about goals, current state, historical patterns, and what makes sense right now.

---

## 2. System Architecture

BRAIN 3.0 follows a layered architecture with clear separation of concerns. At its core is a PostgreSQL database running in Docker on a TrueNAS server. A FastAPI application provides the RESTful API layer, which is consumed by three primary interfaces: the Claude MCP (conversational partner), a mobile-first web UI (direct browse/manage), and Home Assistant (voice control and push notifications).

### Interaction Layers

**Claude MCP:** The primary conversational interface. Claude has full CRUD access to all entities and can reason about goals, projects, tasks, routines, state, and activity patterns. This is where the partner relationship lives.

**Mobile Web UI:** A lightweight, mobile-first interface for browsing, quick entry, and dashboard views. For when the user wants to see their world at a glance without having a conversation.

**Home Assistant:** Provides voice interface via Assist and push notifications via the companion app. The scheduler triggers notifications through HA webhooks. HA automations can respond to BRAIN events (lights, reminders, ambient alerts).

### Scheduler

An internal scheduler runs independently, evaluating routines, deadlines, and patterns on a configurable cadence. It generates push notifications through Home Assistant, morning briefings, and accountability nudges. This is what gives BRAIN its initiative — the ability to reach out rather than waiting to be asked.

---

## 3. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Database | PostgreSQL 16+ | Concurrent access, LISTEN/NOTIFY for real-time UI, JSON columns, full-text search |
| API Framework | FastAPI (Python) | Auto OpenAPI spec maps 1:1 to MCP tools, async native, type-safe |
| Runtime | Python 3.12+ | Matches existing BRAIN skills, broad library ecosystem |
| Deployment | Docker on TrueNAS | Containerized, easy backup/restore, persistent volumes |
| Notifications | Home Assistant | Push via companion app, voice via Assist, automations |
| Scheduling | APScheduler / cron | Internal job runner for proactive behaviors |
| Web UI | TBD (Phase 3) | Mobile-first, likely React or HTMX |

---

## 4. Data Model — The Seven Pillars

The BRAIN 3.0 data model is organized around seven core concepts. Together they give the system a complete picture of what matters (goals), what needs doing (projects and tasks), what patterns to maintain (routines), how the user is doing right now (state), what actually happened (activity log), and how to slice it all (domains and tags).

### Pillar 1: Domains

Life areas that cut across the entire system. Examples: House, Network, Finances, Health. Domains are a filtering and reporting layer — every goal and routine belongs to a domain, and everything beneath them inherits that categorization. Domains should be broad and stable; they rarely change.

### Pillar 2: Goals

Enduring outcomes that give everything else meaning. Goals answer the question: why does this matter? They sit at the top of the hierarchy and rarely change. Examples: maintain the house, achieve financial stability, keep the network secure and performant. When BRAIN acts as a partner, goals are the layer it uses to reason about priorities and notice neglected areas of life.

### Pillar 3: Projects

Bounded efforts with a beginning and an end, nested under goals. Projects have deadlines, progress tracking, and status. They represent the chunks of work that move a goal forward. Examples: remodel the bathroom, file 2026 taxes, segment VLANs. A project is done when its tasks are done.

### Pillar 4: Tasks

The atoms of action. Tasks carry ADHD-aware metadata that distinguishes BRAIN from a generic task manager. Each task has an energy cost (how much it drains you, independent of time), a cognitive type (hands-on, communication, decision, errand, admin, focus work), context requirements (where you need to be, what you need), and activation friction (how hard it is to start, regardless of how easy it is once going). Tasks can recur, belong to a project, and be tagged for cross-cutting connections.

### Pillar 5: Routines

Behavioral patterns the user is actively building or maintaining, modeled as a first-class concept separate from recurring tasks. A routine is not just a task that repeats — it is a commitment to a pattern of behavior. The system tracks streaks, monitors for pattern breaks, and responds differently when a routine is missed (encouragement, redesign suggestions) versus when a one-off task is overdue (simple rescheduling). Examples: Saturday morning house maintenance, evening kitchen reset, weekly finance review.

### Pillar 6: Mindfulness & State

A continuous, low-friction layer for capturing internal state. This includes structured daily check-ins (energy, mood, focus, type of day), micro check-ins tied to task completion, and freeform mindfulness logs at any time. This data serves two purposes: it allows Claude to match tasks to current capacity in real time, and it feeds the reporting layer so the user can see correlations between internal state and productivity patterns over time. The system meets the user where they are — if a check-in is skipped, it adapts rather than breaking.

### Pillar 7: Activity Log

The record of what actually happened. Every task completion, routine execution, and state check-in generates a log entry. The log captures not just what was done but how it felt — energy before and after, actual friction experienced, mood, duration, and freeform notes. This is what makes BRAIN a learning system. Claude uses the log to recognize patterns (you avoid phone calls, you are most productive Saturday mornings, you overestimate evening capacity). The user uses it through reporting to build self-awareness and identify recurring friction points.

---

## 5. Database Schema

The following tables implement the seven-pillar data model in PostgreSQL. All tables use UUID primary keys, timestamps for audit trails, and explicit foreign key relationships.

### domains

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| name | VARCHAR | Domain name (e.g. House, Network, Finances) |
| description | TEXT | What this life area encompasses |
| color | VARCHAR | Hex color for UI display and reporting |
| sort_order | INTEGER | Display ordering preference |
| created_at | TIMESTAMPTZ | Record creation timestamp |

### goals

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| domain_id | UUID FK | References domains.id |
| title | VARCHAR | Goal name |
| description | TEXT | Why this goal matters, what success looks like |
| status | VARCHAR | active, paused, achieved, abandoned |
| created_at | TIMESTAMPTZ | Record creation timestamp |
| updated_at | TIMESTAMPTZ | Last modification timestamp |

### projects

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| goal_id | UUID FK | References goals.id |
| title | VARCHAR | Project name |
| description | TEXT | Scope, context, and notes |
| status | VARCHAR | not_started, active, blocked, completed, abandoned |
| deadline | DATE | Target completion date (nullable) |
| progress_pct | INTEGER | 0-100, auto-calculated from task completion |
| created_at | TIMESTAMPTZ | Record creation timestamp |
| updated_at | TIMESTAMPTZ | Last modification timestamp |

### tasks

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| project_id | UUID FK | References projects.id (nullable for standalone tasks) |
| title | VARCHAR | Task name |
| description | TEXT | Details, notes, context |
| status | VARCHAR | pending, active, completed, skipped, deferred |
| cognitive_type | VARCHAR | hands_on, communication, decision, errand, admin, focus_work |
| energy_cost | INTEGER | 1-5 scale. How draining, independent of time |
| activation_friction | INTEGER | 1-5 scale. How hard to start, not how hard to do |
| context_required | VARCHAR | at_home, at_computer, at_store, needs_tools, etc. |
| due_date | DATE | Deadline (nullable) |
| recurrence_rule | VARCHAR | RRULE string for repeating tasks (nullable) |
| completed_at | TIMESTAMPTZ | When actually completed |
| created_at | TIMESTAMPTZ | Record creation timestamp |
| updated_at | TIMESTAMPTZ | Last modification timestamp |

### tags

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| name | VARCHAR | Tag name (e.g. home-depot, quick-win, blocked-by-weather) |
| color | VARCHAR | Hex color for display |

### task_tags

| Column | Type | Description |
|--------|------|-------------|
| task_id | UUID FK | References tasks.id |
| tag_id | UUID FK | References tags.id |

### routines

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| domain_id | UUID FK | References domains.id |
| title | VARCHAR | Routine name |
| description | TEXT | What this routine involves and why it matters |
| frequency | VARCHAR | daily, weekdays, weekends, weekly, custom |
| current_streak | INTEGER | Consecutive completions without a miss |
| best_streak | INTEGER | All-time best streak |
| last_completed | DATE | Date of most recent completion |
| status | VARCHAR | active, paused, retired |
| energy_cost | INTEGER | 1-5 scale, same as tasks |
| activation_friction | INTEGER | 1-5 scale, same as tasks |
| created_at | TIMESTAMPTZ | Record creation timestamp |
| updated_at | TIMESTAMPTZ | Last modification timestamp |

### routine_schedule

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| routine_id | UUID FK | References routines.id |
| day_of_week | VARCHAR | monday, tuesday, etc. or 'any' |
| time_of_day | VARCHAR | morning, afternoon, evening, or specific HH:MM |
| preferred_window | VARCHAR | Ideal time range (e.g. 06:00-08:00) |

### state_checkins

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| checkin_type | VARCHAR | morning, midday, evening, micro, freeform |
| energy_level | INTEGER | 1-5 scale. Current energy |
| mood | INTEGER | 1-5 scale. Current emotional state |
| focus_level | INTEGER | 1-5 scale. Ability to concentrate |
| freeform_note | TEXT | Open-ended mindfulness observation |
| context | VARCHAR | work_day, day_off, chaotic, travel, etc. |
| logged_at | TIMESTAMPTZ | When this check-in occurred |

### activity_log

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Primary key |
| task_id | UUID FK | References tasks.id (nullable) |
| routine_id | UUID FK | References routines.id (nullable) |
| checkin_id | UUID FK | References state_checkins.id (nullable) |
| action_type | VARCHAR | completed, skipped, deferred, started, reflected, checked_in |
| notes | TEXT | Freeform observations about the activity |
| energy_before | INTEGER | 1-5, self-reported before starting |
| energy_after | INTEGER | 1-5, self-reported after completing |
| mood_rating | INTEGER | 1-5, how the user felt during/after |
| friction_actual | INTEGER | 1-5, actual experienced friction vs predicted |
| duration_minutes | INTEGER | How long the activity actually took |
| logged_at | TIMESTAMPTZ | When this entry was recorded |

---

## 6. MCP Tool Contract (Phase 1)

The MCP exposes the following tool categories to Claude. Each maps directly to a FastAPI endpoint. The auto-generated OpenAPI specification from FastAPI serves as the canonical tool schema.

### Entity CRUD

Standard create, read, update, delete operations for all seven entities: domains, goals, projects, tasks, routines, tags, and state check-ins. Claude can manage the full lifecycle of any entity through these tools.

### Query and Reasoning

Filtered queries that support Claude's reasoning: get tasks by energy level, get tasks by cognitive type, get overdue items, get tasks for a specific context, get routines with broken streaks, get activity log for a date range. These are the tools that let Claude act as a partner — understanding what is happening and what needs attention.

### Activity Logging

Tools to record task completions, routine executions, state check-ins, and reflections. These feed the activity log and update streak counters, progress percentages, and status fields automatically.

### Reporting and Patterns

Aggregation queries for pattern recognition: completion rates by cognitive type, energy patterns by time of day, friction prediction accuracy, routine adherence trends, domain balance over time. These power both Claude's proactive suggestions and the user's self-reflection.

---

## 7. ADHD-Specific Design Principles

### Friction Awareness

Every task carries explicit activation friction and energy cost metrics. The system uses these to match tasks to current capacity rather than presenting a flat list ordered by due date. When energy is low, BRAIN surfaces low-friction tasks. When momentum is high, it offers the harder items that benefit from that window.

### Context Batching

Tags and context requirements allow the system to batch related tasks intelligently. If you are already at the hardware store, BRAIN knows what else you need from there across all projects. If you are at your computer in a focus window, it surfaces the admin and decision tasks that require that context.

### Routine Scaffolding

Routines are modeled as behavioral commitments with streak tracking and pattern break detection. The system distinguishes between a missed routine (a pattern to address) and a missed one-off task (something to reschedule). This reflects how ADHD brains relate to habits — routines are scaffolding that either holds or collapses, and the response to each is different.

### Proactive Initiative

The system does not wait to be checked. Through the scheduler and Home Assistant integration, BRAIN reaches out with morning briefings, accountability nudges, and timely reminders. The ADHD brain struggles with object permanence — if the system is not visible, it ceases to exist. BRAIN solves this by coming to the user through their preferred channels.

### Mindfulness Integration

State check-ins and micro-reflections build self-awareness over time. The system captures how the user feels before and after activities, creating a feedback loop that helps both Claude and the user understand patterns in energy, mood, and friction. This turns productivity data into a mindfulness practice.

### Pattern Visibility

Reporting surfaces recurring friction points, avoidance patterns, energy cycles, and routine adherence trends. This makes the invisible patterns of ADHD visible and concrete — not as judgment, but as self-knowledge that enables better decisions.

---

## 8. Phased Delivery Plan

### Phase 1 — The Core Loop

Database, FastAPI, and MCP. All seven pillar tables deployed. Claude has full CRUD and query access. Interaction is purely through Claude conversation. No UI, no voice, no push notifications. Deliverable: a working system where Claude knows your stuff, can remind you, and you can ask it anything.

### Phase 2 — The System Gets Proactive

Internal scheduler with Home Assistant integration. Morning briefings, accountability pings, and deadline alerts delivered as push notifications. The system transitions from responsive to proactive — Claude reaches out rather than waiting to be asked.

### Phase 3 — Browse and Manage Directly

Lightweight mobile-first web UI. Dashboard view of goals, projects, and tasks. Quick entry for logging without a conversation. Reporting visualizations for pattern recognition and self-reflection.

### Phase 4+ — Expand and Integrate

New life domains (finances, health tracking). Voice interface through Home Assistant Assist. Deeper HA automations (ambient reminders via lights, display panels). Calendar integration. The system grows to cover everything, one domain at a time.

---

## 9. Design Decisions

The following architectural and implementation decisions were evaluated during the design phase and have been resolved. Each is recorded here with the chosen approach and rationale.

### Recurrence Engine

**Decision:** RRULE (iCalendar standard) via the python-dateutil library.

RRULE handles all recurrence edge cases (month boundaries, leap years, complex schedules like every second Tuesday) through a well-tested standard. The python-dateutil library parses and evaluates RRULE strings natively. Claude generates and interprets the strings on behalf of the user — the user never touches the syntax directly. A custom system would inevitably evolve toward a worse version of RRULE as edge cases accumulate.

### Authentication

**Decision:** Deferred to Phase 3. API structured for future auth middleware.

BRAIN 3.0 is a single-user system running on a home network behind a firewall. In Phase 1, the API runs on a non-exposed port with no authentication layer. The API architecture uses a middleware pattern so that adding authentication (API key, OAuth, or basic auth) in Phase 3 is a single-layer addition, not a rewrite. Auth becomes necessary when the web UI exposes the system beyond localhost.

### Backup Strategy

**Decision:** Nightly pg_dump to TrueNAS with 30-day retention.

A cron job runs pg_dump nightly, writing timestamped SQL dumps to a TrueNAS dataset. Retention is 30 days with automatic cleanup of older files. This is simple, proven, and allows point-in-time restoration to any nightly snapshot. An optional weekly Docker volume snapshot provides a secondary safety net covering the full container state.

### Migration from BRAIN 2.0

**Decision:** No migration. Clean start.

BRAIN 2.0 continues to operate as the work-specific note-taking and task management tool. BRAIN 3.0 is a separate system dedicated to personal life management. There is no data overlap between the two, and no migration is required. This keeps the scope clean and avoids contaminating the new data model with legacy structures.

### Reporting Implementation

**Decision:** Dual-channel — conversational insights (Phase 1) and visual dashboards (Phase 3).

Both channels consume the same activity log and state check-in data. In Phase 1, Claude delivers pattern insights conversationally through the MCP — interpreting trends, identifying avoidance patterns, and surfacing correlations between energy, mood, and task completion. In Phase 3, the web UI adds visual dashboards with charts and trend lines for self-directed exploration. The conversational channel remains the richer interface; the visual channel provides at-a-glance pattern recognition.

### State Check-in Friction

**Decision:** Layered approach — push notifications for structured check-ins, conversation for deeper reflection.

Routine check-ins (energy, mood, focus) are delivered as push notifications through Home Assistant with quick-tap structured options (1-5 scales). These are designed to take under 10 seconds and require no typing. Deeper reflection and freeform mindfulness logging happen through conversational check-ins with Claude, where the interaction is natural and open-ended. The system works with whatever data it receives — a skipped push check-in does not break the system, it simply reduces data density for that window. This layered approach maximizes the chance of consistent engagement without creating friction that discourages use.
