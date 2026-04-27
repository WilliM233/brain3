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

"""CRUD endpoints for Habits."""

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Habit, HabitCompletion, Routine
from app.schemas.habits import (
    HabitCompleteRequest,
    HabitCompleteResponse,
    HabitCompletionResponse,
    HabitCreate,
    HabitDetailResponse,
    HabitListResponse,
    HabitResponse,
    HabitUpdate,
)
from app.services.streak import evaluate_streak

router = APIRouter()


@router.post("/", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
def create_habit(payload: HabitCreate, db: Session = Depends(get_db)) -> Habit:
    """Create a new habit. Validates routine_id if provided."""
    if payload.routine_id is not None:
        routine = db.query(Routine).filter(Routine.id == payload.routine_id).first()
        if not routine:
            raise HTTPException(status_code=400, detail="Routine not found")

    fields = payload.model_dump()

    # [2G-Gap-01] Auto-populate accountable_since when creating an accountable
    # habit without an explicit date. Graduation needs a start anchor.
    if (
        fields.get("scaffolding_status") == "accountable"
        and fields.get("accountable_since") is None
    ):
        fields["accountable_since"] = date.today()

    habit = Habit(**fields)
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


@router.get("/", response_model=HabitListResponse)
def list_habits(
    routine_id: UUID | None = Query(None),
    habit_status: str | None = Query(None, alias="status"),
    scaffolding_status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> HabitListResponse:
    """List habits with composable filters."""
    query = db.query(Habit)

    if routine_id is not None:
        query = query.filter(Habit.routine_id == routine_id)
    if habit_status is not None:
        query = query.filter(Habit.status == habit_status)
    if scaffolding_status is not None:
        query = query.filter(Habit.scaffolding_status == scaffolding_status)

    results = query.order_by(Habit.created_at).all()
    return HabitListResponse(
        items=[HabitResponse.model_validate(h) for h in results],
        count=len(results),
    )


@router.get("/{habit_id}", response_model=HabitDetailResponse)
def get_habit(habit_id: UUID, db: Session = Depends(get_db)) -> Habit:
    """Get a single habit with its nested parent routine."""
    habit = (
        db.query(Habit)
        .options(joinedload(Habit.routine))
        .filter(Habit.id == habit_id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit


@router.patch("/{habit_id}", response_model=HabitResponse)
def update_habit(
    habit_id: UUID, payload: HabitUpdate, db: Session = Depends(get_db)
) -> Habit:
    """Partial update of a habit."""
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    updates = payload.model_dump(exclude_unset=True)

    # If detaching from routine (routine_id → None), ensure frequency is set
    # either in the request payload or already on the habit.
    if "routine_id" in updates and updates["routine_id"] is None:
        new_frequency = updates.get("frequency", habit.frequency)
        if new_frequency is None:
            raise HTTPException(
                status_code=422,
                detail="frequency is required when detaching from a routine",
            )

    # If changing routine_id to a new value, validate it exists
    if "routine_id" in updates and updates["routine_id"] is not None:
        routine = (
            db.query(Routine).filter(Routine.id == updates["routine_id"]).first()
        )
        if not routine:
            raise HTTPException(status_code=400, detail="Routine not found")

    # [2G-03] Manual override hook: if notification_frequency is changing,
    # reset the cooldown timer so step-down evaluation respects the change.
    if (
        "notification_frequency" in updates
        and updates["notification_frequency"] != habit.notification_frequency
    ):
        updates["last_frequency_changed_at"] = datetime.now(tz=UTC)

    # [2G-Gap-01] Auto-populate accountable_since on transition to accountable.
    # Graduation evaluation reads accountable_since to compute days_accountable;
    # without an anchor date it cannot produce a correct result.
    if (
        updates.get("scaffolding_status") == "accountable"
        and "accountable_since" not in updates
        and habit.accountable_since is None
    ):
        updates["accountable_since"] = date.today()

    for field, value in updates.items():
        setattr(habit, field, value)

    db.commit()
    db.refresh(habit)
    return habit


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_habit(habit_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a habit."""
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    db.delete(habit)
    db.commit()


# ---------------------------------------------------------------------------
# Completion — /api/habits/{habit_id}/complete
# ---------------------------------------------------------------------------

DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


@router.post("/{habit_id}/complete", response_model=HabitCompleteResponse)
def complete_habit(
    habit_id: UUID,
    payload: HabitCompleteRequest | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Record a habit completion and evaluate the streak."""
    habit = (
        db.query(Habit)
        .options(
            joinedload(Habit.routine).joinedload(Routine.schedules),
        )
        .filter(Habit.id == habit_id)
        .first()
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    if habit.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete a habit with status '{habit.status}'. "
            "Only active habits can be completed.",
        )

    completed_date = date.today()
    if payload and payload.completed_date:
        completed_date = payload.completed_date

    notes = payload.notes if payload else None

    # Idempotency check — return existing completion if one exists for this date
    existing = (
        db.query(HabitCompletion)
        .filter(
            HabitCompletion.habit_id == habit_id,
            HabitCompletion.completed_at == completed_date,
        )
        .first()
    )
    if existing:
        return {
            "habit_id": habit.id,
            "completion_id": existing.id,
            "completed_date": existing.completed_at,
            "current_streak": habit.current_streak,
            "best_streak": habit.best_streak,
            "streak_was_broken": False,
            "source": existing.source,
        }

    # Resolve frequency: habit's own, then parent routine's, then error
    frequency = habit.frequency
    if frequency is None and habit.routine:
        frequency = habit.routine.frequency
    if frequency is None:
        raise HTTPException(
            status_code=422,
            detail="Cannot determine frequency for this habit. "
            "Set frequency on the habit or assign it to a routine.",
        )

    # Build scheduled_days for custom frequency
    scheduled_days = None
    if frequency == "custom" and habit.routine:
        scheduled_days = [
            DAY_MAP[s.day_of_week.lower()]
            for s in habit.routine.schedules
            if s.day_of_week and s.day_of_week.lower() in DAY_MAP
        ]

    result = evaluate_streak(
        frequency=frequency,
        current_streak=habit.current_streak,
        best_streak=habit.best_streak,
        last_completed=habit.last_completed,
        completed_date=completed_date,
        scheduled_days=scheduled_days,
    )

    # Update streak fields on the habit
    habit.current_streak = result.current_streak
    habit.best_streak = result.best_streak
    if habit.last_completed is None or completed_date >= habit.last_completed:
        habit.last_completed = completed_date

    # Create the completion record
    completion = HabitCompletion(
        habit_id=habit.id,
        completed_at=completed_date,
        source="individual",
        notes=notes,
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)

    return {
        "habit_id": habit.id,
        "completion_id": completion.id,
        "completed_date": completed_date,
        "current_streak": result.current_streak,
        "best_streak": result.best_streak,
        "streak_was_broken": result.streak_was_broken,
        "source": "individual",
    }


# ---------------------------------------------------------------------------
# Completion history — /api/habits/{habit_id}/completions
# ---------------------------------------------------------------------------


@router.get(
    "/{habit_id}/completions", response_model=list[HabitCompletionResponse],
)
def list_habit_completions(
    habit_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    completed_after: date | None = Query(None),
    db: Session = Depends(get_db),
) -> list[HabitCompletion]:
    """Return recent completion records for a habit, newest first."""
    habit = db.query(Habit).filter(Habit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    query = db.query(HabitCompletion).filter(HabitCompletion.habit_id == habit_id)
    if completed_after is not None:
        query = query.filter(HabitCompletion.completed_at > completed_after)

    return (
        query.order_by(
            HabitCompletion.completed_at.desc(),
            HabitCompletion.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
