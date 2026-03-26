"""CRUD endpoints for Activity Log."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import ActivityLog, Routine, StateCheckin, Task
from app.schemas.activity import (
    ActivityLogCreate,
    ActivityLogDetailResponse,
    ActivityLogResponse,
    ActivityLogUpdate,
)

router = APIRouter()


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

    entry = ActivityLog(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/", response_model=list[ActivityLogResponse])
def list_activity(
    action_type: str | None = Query(None),
    task_id: UUID | None = Query(None),
    routine_id: UUID | None = Query(None),
    logged_after: datetime | None = Query(None),
    logged_before: datetime | None = Query(None),
    has_task: bool | None = Query(None),
    has_routine: bool | None = Query(None),
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

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

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
