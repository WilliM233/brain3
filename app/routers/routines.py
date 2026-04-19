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
from app.models import Domain, HabitCompletion, Routine, RoutineCompletion, RoutineSchedule
from app.schemas.routines import (
    RoutineCompleteRequest,
    RoutineCompleteResponse,
    RoutineCreate,
    RoutineDetailResponse,
    RoutineListResponse,
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


@router.get("/", response_model=RoutineListResponse)
def list_routines(
    domain_id: UUID | None = Query(None),
    routine_status: str | None = Query(None, alias="status"),
    frequency: str | None = Query(None),
    streak_broken: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> RoutineListResponse:
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

    results = query.order_by(Routine.created_at).all()
    return RoutineListResponse(
        items=[RoutineResponse.model_validate(r) for r in results],
        count=len(results),
    )


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
    """Record a routine completion and evaluate the streak.

    Freeform routines (no child habits) keep the original v1 behaviour.
    Scripted routines branch on ``status``: *all_done* cascades completion
    to active non-graduated child habits, *partial* logs a freeform note
    for later reconciliation, and *skipped* freezes the streak.
    """
    routine = (
        db.query(Routine)
        .options(
            joinedload(Routine.schedules),
            joinedload(Routine.habits),
        )
        .filter(Routine.id == routine_id)
        .first()
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    if routine.status != "active":
        raise HTTPException(status_code=409, detail="Cannot complete a non-active routine")

    completed_date = date.today()
    completion_status = "all_done"
    freeform_note = None
    if payload:
        if payload.completed_date:
            completed_date = payload.completed_date
        completion_status = payload.status
        freeform_note = payload.freeform_note

    # Build scheduled_days list for custom frequency
    scheduled_days = None
    if routine.frequency == "custom":
        scheduled_days = [
            DAY_MAP[s.day_of_week.lower()]
            for s in routine.schedules
            if s.day_of_week and s.day_of_week.lower() in DAY_MAP
        ]

    has_habits = len(routine.habits) > 0

    # --- Freeform path (no child habits) — unchanged v1 behaviour ----------
    if not has_habits:
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
            "completion_id": None,
            "status": None,
            "habits_completed": None,
        }

    # --- Scripted path (has child habits) ----------------------------------

    habits_completed: list[UUID] = []

    if completion_status == "skipped":
        # Freeze streak — no evaluate, no last_completed update
        streak_was_broken = False
    else:
        # Both all_done and partial get routine-level streak credit
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
        if routine.last_completed is None or completed_date >= routine.last_completed:
            routine.last_completed = completed_date
        streak_was_broken = result.streak_was_broken

    # Cascade to child habits only on all_done
    if completion_status == "all_done":
        habits_completed = _cascade_habits(
            routine=routine,
            completed_date=completed_date,
            scheduled_days=scheduled_days,
            db=db,
        )

    # Create the RoutineCompletion record
    completion = RoutineCompletion(
        routine_id=routine.id,
        completed_at=completed_date,
        status=completion_status,
        freeform_note=freeform_note,
        reconciled=completion_status != "partial",
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)

    return {
        "routine_id": routine.id,
        "completed_date": completed_date,
        "current_streak": routine.current_streak,
        "best_streak": routine.best_streak,
        "streak_was_broken": streak_was_broken,
        "completion_id": completion.id,
        "status": completion_status,
        "habits_completed": habits_completed,
    }


def _cascade_habits(
    routine: Routine,
    completed_date: date,
    scheduled_days: list[int] | None,
    db: Session,
) -> list[UUID]:
    """Cascade completion to all active, non-graduated child habits.

    Respects idempotency: habits already completed for ``completed_date``
    are silently skipped.  Returns the list of habit IDs that received a
    new completion record.
    """
    completed_ids: list[UUID] = []

    active_habits = [
        h for h in routine.habits
        if h.status == "active" and h.scaffolding_status != "graduated"
    ]

    for habit in active_habits:
        # Idempotency — skip if already completed today
        existing = (
            db.query(HabitCompletion)
            .filter(
                HabitCompletion.habit_id == habit.id,
                HabitCompletion.completed_at == completed_date,
            )
            .first()
        )
        if existing:
            continue

        # Resolve frequency: habit's own, then parent routine's
        frequency = habit.frequency or routine.frequency

        # Build per-habit scheduled_days for custom frequency
        habit_scheduled_days = scheduled_days
        if frequency == "custom" and habit.frequency and habit.frequency != routine.frequency:
            # If the habit has its own custom frequency distinct from the
            # routine, we'd need its own schedule — but habits inherit
            # the routine's schedule, so reuse scheduled_days.
            habit_scheduled_days = scheduled_days

        result = evaluate_streak(
            frequency=frequency,
            current_streak=habit.current_streak,
            best_streak=habit.best_streak,
            last_completed=habit.last_completed,
            completed_date=completed_date,
            scheduled_days=habit_scheduled_days,
        )

        habit.current_streak = result.current_streak
        habit.best_streak = result.best_streak
        if habit.last_completed is None or completed_date >= habit.last_completed:
            habit.last_completed = completed_date

        completion = HabitCompletion(
            habit_id=habit.id,
            completed_at=completed_date,
            source="routine_cascade",
        )
        db.add(completion)
        completed_ids.append(habit.id)

    return completed_ids


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
