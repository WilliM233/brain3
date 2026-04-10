# BRAIN 3.0 — AI-powered personal operating system for ADHD
# Copyright (C) 2026 L (WilliM233)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""CRUD endpoints for Activity Log."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import ActivityLog, ActivityTag, Routine, StateCheckin, Tag, Task
from app.schemas.activity import (
    ActivityLogCreate,
    ActivityLogDetailResponse,
    ActivityLogResponse,
    ActivityLogUpdate,
)
from app.schemas.batch import (
    BatchActivityCreate,
    BatchActivityCreateResponse,
    BatchTagAttachRequest,
)
from app.schemas.tags import TagResponse

router = APIRouter()
activity_tags_router = APIRouter()


@router.post("/", response_model=ActivityLogResponse, status_code=status.HTTP_201_CREATED)
def create_activity(payload: ActivityLogCreate, db: Session = Depends(get_db)) -> ActivityLog:
    """Create a new activity log entry. Validates referenced IDs if provided."""
    if payload.task_id is not None:
        if not db.query(Task).filter(Task.id == payload.task_id).first():
            raise HTTPException(status_code=400, detail="Task not found")
    if payload.routine_id is not None:
        if not db.query(Routine).filter(Routine.id == payload.routine_id).first():
            raise HTTPException(status_code=400, detail="Routine not found")
    if payload.checkin_id is not None:
        if not db.query(StateCheckin).filter(StateCheckin.id == payload.checkin_id).first():
            raise HTTPException(status_code=400, detail="Check-in not found")

    # Validate tag_ids if provided
    tags = []
    if payload.tag_ids:
        for tid in payload.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tid).first()
            if not tag:
                raise HTTPException(status_code=400, detail=f"Tag {tid} not found")
            tags.append(tag)

    entry = ActivityLog(**payload.model_dump(exclude={"tag_ids"}))
    db.add(entry)
    db.flush()

    for tag in tags:
        db.add(ActivityTag(activity_id=entry.id, tag_id=tag.id))

    db.commit()
    db.refresh(entry)
    return entry


@router.post(
    "/batch", response_model=BatchActivityCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def batch_create_activity(
    payload: BatchActivityCreate, db: Session = Depends(get_db)
) -> dict:
    """Batch create activity log entries. Atomic — all succeed or all fail."""
    created = []
    try:
        for idx, item in enumerate(payload.items):
            if item.task_id is not None:
                if not db.query(Task).filter(Task.id == item.task_id).first():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Batch item {idx}: Task not found"
                        f" (task_id: {item.task_id})",
                    )
            if item.routine_id is not None:
                if not db.query(Routine).filter(Routine.id == item.routine_id).first():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Batch item {idx}: Routine not found"
                        f" (routine_id: {item.routine_id})",
                    )
            if item.checkin_id is not None:
                if not db.query(StateCheckin).filter(StateCheckin.id == item.checkin_id).first():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Batch item {idx}: Check-in not found"
                        f" (checkin_id: {item.checkin_id})",
                    )

            tags = []
            if item.tag_ids:
                for tid in item.tag_ids:
                    tag = db.query(Tag).filter(Tag.id == tid).first()
                    if not tag:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Batch item {idx}: Tag {tid} not found",
                        )
                    tags.append(tag)

            entry = ActivityLog(**item.model_dump(exclude={"tag_ids"}))
            db.add(entry)
            db.flush()

            for tag in tags:
                db.add(ActivityTag(activity_id=entry.id, tag_id=tag.id))

            created.append(entry)
    except HTTPException:
        db.rollback()
        raise

    db.commit()
    for entry in created:
        db.refresh(entry)
    return {"created": created, "count": len(created)}


@router.get("/", response_model=list[ActivityLogResponse])
def list_activity(
    action_type: str | None = Query(None),
    task_id: UUID | None = Query(None),
    routine_id: UUID | None = Query(None),
    logged_after: datetime | None = Query(None),
    logged_before: datetime | None = Query(None),
    has_task: bool | None = Query(None),
    has_routine: bool | None = Query(None),
    tag: str | None = Query(None, description="Comma-separated tag names (AND logic)"),
    db: Session = Depends(get_db),
) -> list[ActivityLog]:
    """List activity log entries with optional filters. Descending by logged_at."""
    query = db.query(ActivityLog)

    if action_type is not None:
        query = query.filter(ActivityLog.action_type == action_type)
    if task_id is not None:
        query = query.filter(ActivityLog.task_id == task_id)
    if routine_id is not None:
        query = query.filter(ActivityLog.routine_id == routine_id)
    if logged_after is not None:
        query = query.filter(ActivityLog.logged_at >= logged_after)
    if logged_before is not None:
        query = query.filter(ActivityLog.logged_at <= logged_before)
    if has_task is True:
        query = query.filter(ActivityLog.task_id.isnot(None))
    elif has_task is False:
        query = query.filter(ActivityLog.task_id.is_(None))
    if has_routine is True:
        query = query.filter(ActivityLog.routine_id.isnot(None))
    elif has_routine is False:
        query = query.filter(ActivityLog.routine_id.is_(None))
    if tag is not None:
        tag_names = [t.strip().lower() for t in tag.split(",") if t.strip()]
        for tag_name in tag_names:
            query = query.filter(
                ActivityLog.tags.any(Tag.name == tag_name)
            )

    return query.order_by(ActivityLog.logged_at.desc()).all()


@router.get("/{entry_id}", response_model=ActivityLogDetailResponse)
def get_activity(entry_id: UUID, db: Session = Depends(get_db)) -> ActivityLog:
    """Get a single activity log entry with resolved task/routine/checkin."""
    entry = (
        db.query(ActivityLog)
        .options(
            joinedload(ActivityLog.task),
            joinedload(ActivityLog.routine),
            joinedload(ActivityLog.checkin),
            joinedload(ActivityLog.tags),
        )
        .filter(ActivityLog.id == entry_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")
    return entry


@router.patch("/{entry_id}", response_model=ActivityLogResponse)
def update_activity(
    entry_id: UUID, payload: ActivityLogUpdate, db: Session = Depends(get_db)
) -> ActivityLog:
    """Partial update of an activity log entry."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")

    # Validate referenced entities exist (only for fields in the payload)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("task_id") is not None:
        if not db.query(Task).filter(Task.id == updates["task_id"]).first():
            raise HTTPException(status_code=400, detail="Task not found")
    if updates.get("routine_id") is not None:
        if not db.query(Routine).filter(Routine.id == updates["routine_id"]).first():
            raise HTTPException(status_code=400, detail="Routine not found")
    if updates.get("checkin_id") is not None:
        if not db.query(StateCheckin).filter(StateCheckin.id == updates["checkin_id"]).first():
            raise HTTPException(status_code=400, detail="Check-in not found")

    for field, value in updates.items():
        setattr(entry, field, value)

    # Enforce at-most-one-reference on the post-merge state
    refs = sum(v is not None for v in [entry.task_id, entry.routine_id, entry.checkin_id])
    if refs > 1:
        raise HTTPException(
            status_code=422,
            detail="At most one of task_id, routine_id, or checkin_id may be set",
        )

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(entry_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete an activity log entry."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")
    db.delete(entry)
    db.commit()


# ---------------------------------------------------------------------------
# Activity-Tag attachment — /api/activity/{activity_id}/tags
# ---------------------------------------------------------------------------


@activity_tags_router.post(
    "/{activity_id}/tags/batch", response_model=list[TagResponse],
)
def batch_attach_tags_to_activity(
    activity_id: UUID,
    payload: BatchTagAttachRequest,
    db: Session = Depends(get_db),
) -> list[Tag]:
    """Attach multiple tags to an activity log entry. Idempotent."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")

    tags = []
    for tid in payload.tag_ids:
        tag = db.query(Tag).filter(Tag.id == tid).first()
        if not tag:
            raise HTTPException(status_code=400, detail=f"Tag {tid} not found")
        tags.append(tag)

    for tag in tags:
        existing = (
            db.query(ActivityTag)
            .filter(ActivityTag.activity_id == activity_id, ActivityTag.tag_id == tag.id)
            .first()
        )
        if not existing:
            db.add(ActivityTag(activity_id=activity_id, tag_id=tag.id))

    db.commit()
    db.refresh(entry)
    return entry.tags


@activity_tags_router.get("/{activity_id}/tags", response_model=list[TagResponse])
def list_tags_on_activity(
    activity_id: UUID, db: Session = Depends(get_db)
) -> list[Tag]:
    """List all tags attached to an activity log entry."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")
    return entry.tags


@activity_tags_router.post(
    "/{activity_id}/tags/{tag_id}", response_model=TagResponse,
)
def attach_tag_to_activity(
    activity_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> Tag:
    """Attach a tag to an activity log entry. Idempotent."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing = (
        db.query(ActivityTag)
        .filter(ActivityTag.activity_id == activity_id, ActivityTag.tag_id == tag_id)
        .first()
    )
    if not existing:
        db.add(ActivityTag(activity_id=activity_id, tag_id=tag_id))
        db.commit()

    return tag


@activity_tags_router.delete(
    "/{activity_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag_from_activity(
    activity_id: UUID, tag_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a tag from an activity log entry."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity log entry not found")
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    link = (
        db.query(ActivityTag)
        .filter(ActivityTag.activity_id == activity_id, ActivityTag.tag_id == tag_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Tag is not attached to this activity")
    db.delete(link)
    db.commit()
