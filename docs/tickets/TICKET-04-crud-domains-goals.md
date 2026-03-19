## Summary

Build the CRUD API endpoints for Domains and Goals — the top two levels of the BRAIN 3.0 hierarchy. This is the first real API surface and establishes the patterns (Pydantic schemas, router structure, response format) that all subsequent entity tickets will follow.

## Context

- **Scope:** Domains and Goals only. Projects and Tasks come in ticket #5.
- **Pattern established here:** Create/Update/Response Pydantic schemas, router-per-entity structure, lightweight list vs detailed get-by-ID with nested children. All future CRUD tickets follow this pattern.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model: Pillars 1-2) and 5 (Database Schema: domains, goals tables)

## Deliverables

- `app/schemas/domains.py` — Pydantic schemas for Domain
- `app/schemas/goals.py` — Pydantic schemas for Goal
- `app/schemas/__init__.py`
- `app/routers/domains.py` — Domain CRUD endpoints
- `app/routers/goals.py` — Goal CRUD endpoints
- `app/routers/__init__.py`
- Router registration in `app/main.py`

## Pydantic Schema Pattern

Each entity gets three schemas. This pattern applies to all future CRUD tickets.

**Create** — fields required to create the entity. No id, no timestamps.
**Update** — all fields optional. Only send what's changing (supports PATCH).
**Response** — full entity including id and timestamps. Detail endpoint adds nested children.

### Domain Schemas

**DomainCreate:**
- `name` (str, required)
- `description` (str, optional)
- `color` (str, optional — hex color)
- `sort_order` (int, optional — default 0)

**DomainUpdate:**
- All fields from DomainCreate, all optional

**DomainResponse:**
- All fields plus `id` (UUID) and `created_at` (datetime)

**DomainDetailResponse:**
- Extends DomainResponse with `goals` (list of GoalResponse)

### Goal Schemas

**GoalCreate:**
- `domain_id` (UUID, required)
- `title` (str, required)
- `description` (str, optional)
- `status` (str, optional — default "active". Valid: active, paused, achieved, abandoned)

**GoalUpdate:**
- All fields from GoalCreate, all optional

**GoalResponse:**
- All fields plus `id` (UUID), `created_at`, `updated_at`

**GoalDetailResponse:**
- Extends GoalResponse with `projects` (list of ProjectResponse — will be empty until ticket #5 adds projects, but the schema should be ready)

## API Endpoints

### Domains — `/api/domains`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/domains` | Create a domain | DomainResponse |
| GET | `/api/domains` | List all domains | list[DomainResponse] |
| GET | `/api/domains/{id}` | Get domain with goals | DomainDetailResponse |
| PATCH | `/api/domains/{id}` | Partial update | DomainResponse |
| DELETE | `/api/domains/{id}` | Delete domain | 204 No Content |

### Goals — `/api/goals`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/goals` | Create a goal | GoalResponse |
| GET | `/api/goals` | List all goals | list[GoalResponse] |
| GET | `/api/goals/{id}` | Get goal with projects | GoalDetailResponse |
| PATCH | `/api/goals/{id}` | Partial update | GoalResponse |
| DELETE | `/api/goals/{id}` | Delete goal | 204 No Content |

### List Endpoint Filters

- `GET /api/goals` should support optional query parameter: `?domain_id=UUID` to filter goals by domain
- `GET /api/goals` should support optional query parameter: `?status=active` to filter by status

## Acceptance Criteria

- [ ] Pydantic schemas defined for Domain (Create, Update, Response, DetailResponse)
- [ ] Pydantic schemas defined for Goal (Create, Update, Response, DetailResponse)
- [ ] All five Domain endpoints working and returning correct response schemas
- [ ] All five Goal endpoints working and returning correct response schemas
- [ ] `GET /api/domains/{id}` returns domain with nested goals list
- [ ] `GET /api/goals/{id}` returns goal with nested projects list (empty until ticket #5)
- [ ] `GET /api/goals?domain_id=X` filters goals by domain
- [ ] `GET /api/goals?status=active` filters goals by status
- [ ] `PATCH` endpoints accept partial updates (only provided fields are changed)
- [ ] `DELETE` returns 204 on success
- [ ] All endpoints return 404 for invalid UUIDs
- [ ] Routers registered in `app/main.py` under `/api` prefix
- [ ] All endpoints visible and testable in FastAPI auto-docs at `/docs`

## Technical Notes

- Use `app/schemas/` as a package (not a single `schemas.py` file) — one file per entity keeps things manageable as we add more
- Same for `app/routers/` — one file per entity
- Pydantic `model_config = {"from_attributes": True}` on Response schemas for ORM compatibility
- Use FastAPI's `Depends(get_db)` for database sessions
- PATCH implementation: use `model.model_dump(exclude_unset=True)` to only update provided fields
- Consider a 400 response if GoalCreate references a nonexistent domain_id
- Cascade delete behavior: deleting a domain should cascade to its goals (configured in ORM model from ticket #3)

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models and database tables)
