"""CRUD endpoints for Tags and task-tag attachments."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tag, Task, TaskTag
from app.schemas.tags import TagCreate, TagResponse, TagUpdate
from app.schemas.tasks import TaskResponse

router = APIRouter()
task_tags_router = APIRouter()


# ---------------------------------------------------------------------------
# Tag CRUD — /api/tags
# ---------------------------------------------------------------------------


@router.post("/", response_model=TagResponse)
def create_tag(
    payload: TagCreate, response: Response, db: Session = Depends(get_db)
) -> Tag:
    """Create a tag, or return the existing one if name already exists (case-insensitive)."""
    normalized = payload.name.strip().lower()
    existing = db.query(Tag).filter(Tag.name == normalized).first()
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing

    tag = Tag(name=normalized, color=payload.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    response.status_code = status.HTTP_201_CREATED
    return tag


@router.get("/", response_model=list[TagResponse])
def list_tags(
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Tag]:
    """List all tags with optional name search (case-insensitive contains)."""
    query = db.query(Tag)
    if search is not None:
        query = query.filter(Tag.name.ilike(f"%{search}%"))
    return query.order_by(Tag.name).all()


@router.get("/{tag_id}", response_model=TagResponse)
def get_tag(tag_id: UUID, db: Session = Depends(get_db)) -> Tag:
    """Get a single tag by ID."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.patch("/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: UUID, payload: TagUpdate, db: Session = Depends(get_db)
) -> Tag:
    """Partial update of a tag."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip().lower()
    for field, value in update_data.items():
        setattr(tag, field, value)

    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a tag (cascade removes all task associations)."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()


# ---------------------------------------------------------------------------
# Reverse lookup — /api/tags/{tag_id}/tasks
# ---------------------------------------------------------------------------


@router.get("/{tag_id}/tasks", response_model=list[TaskResponse])
def list_tasks_for_tag(tag_id: UUID, db: Session = Depends(get_db)) -> list[Task]:
    """List all tasks that have a given tag."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag.tasks


# ---------------------------------------------------------------------------
# Task-Tag attachment — /api/tasks/{task_id}/tags
# ---------------------------------------------------------------------------


@task_tags_router.get("/{task_id}/tags", response_model=list[TagResponse])
def list_tags_on_task(task_id: UUID, db: Session = Depends(get_db)) -> list[Tag]:
    """List all tags attached to a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.tags


@task_tags_router.post(
    "/{task_id}/tags/{tag_id}", response_model=TagResponse,
)
def attach_tag_to_task(
    task_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> Tag:
    """Attach a tag to a task. Idempotent — attaching twice is a no-op."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = (
        db.query(TaskTag)
        .filter(TaskTag.task_id == task_id, TaskTag.tag_id == tag_id)
        .first()
    )
    if not existing:
        db.add(TaskTag(task_id=task_id, tag_id=tag_id))
        db.commit()

    return tag


@task_tags_router.delete(
    "/{task_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag_from_task(
    task_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a tag from a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    link = (
        db.query(TaskTag)
        .filter(TaskTag.task_id == task_id, TaskTag.tag_id == tag_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Tag is not attached to this task")
    db.delete(link)
    db.commit()
