## Summary

Build the CRUD API endpoints for Tags and the task-tag attachment system. Tags provide the cross-cutting connection layer that lets Claude batch related tasks across projects (e.g. "everything I need from Home Depot" or "all quick wins").

## Context

- **Scope:** Tag CRUD plus dedicated endpoints for attaching/detaching tags to tasks. Follows patterns from ticket #4.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Sections 4 (Data Model) and 5 (Database Schema: tags, task_tags tables)

## Deliverables

- `app/schemas/tags.py` — Pydantic schemas for Tag
- `app/routers/tags.py` — Tag CRUD and task-tag attachment endpoints
- Router registration in `app/main.py`

## Pydantic Schemas

**TagCreate:**
- `name` (str, required)
- `color` (str, optional — hex color)

**TagUpdate:**
- All fields optional

**TagResponse:**
- All fields plus `id` (UUID)

## API Endpoints

### Tags — `/api/tags`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/tags` | Create a tag (or return existing if name matches) | TagResponse |
| GET | `/api/tags` | List all tags | list[TagResponse] |
| GET | `/api/tags/{id}` | Get tag by ID | TagResponse |
| PATCH | `/api/tags/{id}` | Update tag | TagResponse |
| DELETE | `/api/tags/{id}` | Delete tag (removes all task associations) | 204 No Content |

### Task-Tag Attachment — `/api/tasks/{task_id}/tags`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/tasks/{task_id}/tags` | List tags on a task | list[TagResponse] |
| POST | `/api/tasks/{task_id}/tags/{tag_id}` | Attach a tag to a task | 200 with TagResponse |
| DELETE | `/api/tasks/{task_id}/tags/{tag_id}` | Remove a tag from a task | 204 No Content |

### Tag List Filters

- `GET /api/tags?search=depot` — search tags by name (case-insensitive contains)

### Reverse Lookup

- `GET /api/tags/{id}/tasks` — list all tasks with this tag (returns list[TaskResponse])

## Acceptance Criteria

- [ ] Pydantic schemas defined for Tag (Create, Update, Response)
- [ ] All five Tag CRUD endpoints working
- [ ] Tag names are globally unique (case-insensitive)
- [ ] `POST /api/tags` with an existing name returns the existing tag instead of creating a duplicate
- [ ] Attach endpoint (`POST /api/tasks/{task_id}/tags/{tag_id}`) works correctly
- [ ] Detach endpoint (`DELETE /api/tasks/{task_id}/tags/{tag_id}`) works correctly
- [ ] Attaching the same tag twice is idempotent (no error, no duplicate)
- [ ] `GET /api/tasks/{task_id}/tags` returns all tags on a task
- [ ] `GET /api/tags/{id}/tasks` returns all tasks with a given tag
- [ ] Deleting a tag removes it from all task associations (cascade on junction table)
- [ ] `GET /api/tags?search=X` filters tags by name substring
- [ ] `GET /api/tasks/{id}` (from ticket #5) now returns populated tags list in TaskDetailResponse
- [ ] 404 returned for invalid task_id or tag_id on attachment endpoints
- [ ] All endpoints visible and testable at `/docs`

## Technical Notes

- Tag name uniqueness should be case-insensitive — "Home-Depot" and "home-depot" are the same tag. Store normalized (lowercase) or use a case-insensitive unique constraint.
- The `POST /api/tags` "get or create" behavior keeps things simple for Claude — it can just say "tag this as home-depot" without checking if the tag exists first.
- The reverse lookup (`/api/tags/{id}/tasks`) is what lets Claude answer "what else needs to happen at Home Depot?" across all projects.
- The task-tag attachment endpoints can live in the tags router or a dedicated router — developer's choice, as long as the URL structure is consistent.

## Dependencies

- Ticket #2 (FastAPI scaffolding)
- Ticket #3 (ORM models — Tag, TaskTag models and task_tags junction table)
- Ticket #5 (Task endpoints and TaskDetailResponse schema)
