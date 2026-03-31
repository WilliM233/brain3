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

"""CRUD endpoints for Routines, RoutineSchedules, and routine completion."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Domain, Routine, RoutineSchedule
from app.schemas.routines import (
    RoutineCompleteRequest,
    RoutineCompleteResponse,
    RoutineCreate,
    RoutineDetailResponse,
    RoutineResponse,
    RoutineScheduleCreate,
    RoutineScheduleResponse,
    RoutineUpdate,
)
from app.services.streak import evaluate_streak

router = APIRouter()

DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# ---------------------------------------------------------------------------
# Routine CRUD — /api/routines
# ---------------------------------------------------------------------------


@router.post("/", response_model=RoutineResponse, status_code=status.HTTP_201_CREATED)
def create_routine(payload: RoutineCreate, db: Session = Depends(get_db)) -> Routine:
    """Create a new routine. Validates that domain_id references an existing domain."""
    domain = db.query(Domain).filter(Domain.id == payload.domain_id).first()
    if not domain:
        raise HTTPException(status_code=400, detail="Domain not found")

    routine = Routine(**payload.model_dump())
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


@router.get("/", response_model=list[RoutineResponse])
def list_routines(
    domain_id: UUID | None = Query(None),
    routine_status: str | None = Query(None, alias="status"),
    frequency: str | None = Query(None),
    streak_broken: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Routine]:
    """List routines with optional filters."""
    query = db.query(Routine)

    if domain_id is not None:
        query = query.filter(Routine.domain_id == domain_id)
    if routine_status is not None:
        query = query.filter(Routine.status == routine_status)
    if frequency is not None:
        query = query.filter(Routine.frequency == frequency)
    if streak_broken is True:
        query = query.filter(Routine.current_streak == 0, Routine.status == "active")

    return query.order_by(Routine.created_at).all()


@router.get("/{routine_id}", response_model=RoutineDetailResponse)
def get_routine(routine_id: UUID, db: Session = Depends(get_db)) -> Routine:
    """Get a single routine with its nested schedules."""
    routine = (
        db.query(Routine)
        .options(joinedload(Routine.schedules))
        .filter(Routine.id == routine_id)
        .first()
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return routine


@router.patch("/{routine_id}", response_model=RoutineResponse)
def update_routine(
    routine_id: UUID, payload: RoutineUpdate, db: Session = Depends(get_db)
) -> Routine:
    """Partial update of a routine."""
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(routine, field, value)

    db.commit()
    db.refresh(routine)
    return routine


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(routine_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a routine and cascade to its schedules."""
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    db.delete(routine)
    db.commit()


# ---------------------------------------------------------------------------
# Completion — /api/routines/{routine_id}/complete
# ---------------------------------------------------------------------------


@router.post("/{routine_id}/complete", response_model=RoutineCompleteResponse)
def complete_routine(
    routine_id: UUID,
    payload: RoutineCompleteRequest | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Record a routine completion and evaluate the streak."""
    routine = (
        db.query(Routine)
        .options(joinedload(Routine.schedules))
        .filter(Routine.id == routine_id)
        .first()
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    if routine.status != "active":
        raise HTTPException(status_code=409, detail="Cannot complete a non-active routine")

    completed_date = date.today()
    if payload and payload.completed_date:
        completed_date = payload.completed_date

    # Build scheduled_days list for custom frequency
    scheduled_days = None
    if routine.frequency == "custom":
        scheduled_days = [
            DAY_MAP[s.day_of_week.lower()]
            for s in routine.schedules
            if s.day_of_week and s.day_of_week.lower() in DAY_MAP
        ]

    result = evaluate_streak(
        frequency=routine.frequency,
        current_streak=routine.current_streak,
        best_streak=routine.best_streak,
        last_completed=routine.last_completed,
        completed_date=completed_date,
        scheduled_days=scheduled_days,
    )

    routine.current_streak = result.current_streak
    routine.best_streak = result.best_streak
    # Only advance last_completed forward, never regress on backdate
    if routine.last_completed is None or completed_date >= routine.last_completed:
        routine.last_completed = completed_date

    db.commit()
    db.refresh(routine)

    return {
        "routine_id": routine.id,
        "completed_date": completed_date,
        "current_streak": result.current_streak,
        "best_streak": result.best_streak,
        "streak_was_broken": result.streak_was_broken,
    }


# ---------------------------------------------------------------------------
# Schedule management — /api/routines/{routine_id}/schedules
# ---------------------------------------------------------------------------


@router.post(
    "/{routine_id}/schedules",
    response_model=RoutineScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_schedule(
    routine_id: UUID, payload: RoutineScheduleCreate, db: Session = Depends(get_db)
) -> RoutineSchedule:
    """Add a schedule entry to a routine."""
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    schedule = RoutineSchedule(routine_id=routine_id, **payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/{routine_id}/schedules", response_model=list[RoutineScheduleResponse])
def list_schedules(routine_id: UUID, db: Session = Depends(get_db)) -> list[RoutineSchedule]:
    """List all schedule entries for a routine."""
    routine = db.query(Routine).filter(Routine.id == routine_id).first()
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return db.query(RoutineSchedule).filter(RoutineSchedule.routine_id == routine_id).all()


@router.delete(
    "/{routine_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def delete_schedule(
    routine_id: UUID, schedule_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a schedule entry from a routine."""
    schedule = (
        db.query(RoutineSchedule)
        .filter(RoutineSchedule.id == schedule_id, RoutineSchedule.routine_id == routine_id)
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    db.delete(schedule)
    db.commit()
