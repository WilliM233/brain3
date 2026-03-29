"""CRUD endpoints for State Check-ins."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StateCheckin
from app.schemas.checkins import CheckinCreate, CheckinResponse, CheckinUpdate

router = APIRouter()


@router.post("/", response_model=CheckinResponse, status_code=status.HTTP_201_CREATED)
def create_checkin(payload: CheckinCreate, db: Session = Depends(get_db)) -> StateCheckin:
    """Log a new state check-in."""
    checkin = StateCheckin(**payload.model_dump())
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@router.get("/", response_model=list[CheckinResponse])
def list_checkins(
    checkin_type: str | None = Query(None),
    context: str | None = Query(None),
    logged_after: datetime | None = Query(None),
    logged_before: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> list[StateCheckin]:
    """List check-ins with optional filters. Ordered by logged_at descending."""
    query = db.query(StateCheckin)

    if checkin_type is not None:
        query = query.filter(StateCheckin.checkin_type == checkin_type)
    if context is not None:
        query = query.filter(StateCheckin.context == context)
    if logged_after is not None:
        query = query.filter(StateCheckin.logged_at >= logged_after)
    if logged_before is not None:
        query = query.filter(StateCheckin.logged_at <= logged_before)

    return query.order_by(StateCheckin.logged_at.desc()).all()


@router.get("/{checkin_id}", response_model=CheckinResponse)
def get_checkin(checkin_id: UUID, db: Session = Depends(get_db)) -> StateCheckin:
    """Get a single check-in by ID."""
    checkin = db.query(StateCheckin).filter(StateCheckin.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")
    return checkin


@router.patch("/{checkin_id}", response_model=CheckinResponse)
def update_checkin(
    checkin_id: UUID, payload: CheckinUpdate, db: Session = Depends(get_db)
) -> StateCheckin:
    """Partial update of a check-in."""
    checkin = db.query(StateCheckin).filter(StateCheckin.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(checkin, field, value)

    db.commit()
    db.refresh(checkin)
    return checkin


@router.delete("/{checkin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checkin(checkin_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a check-in."""
    checkin = db.query(StateCheckin).filter(StateCheckin.id == checkin_id).first()
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")
    db.delete(checkin)
    db.commit()
