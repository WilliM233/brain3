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

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Habit, Routine
from app.schemas.habits import (
    HabitCreate,
    HabitDetailResponse,
    HabitResponse,
    HabitUpdate,
)

router = APIRouter()


@router.post("/", response_model=HabitResponse, status_code=status.HTTP_201_CREATED)
def create_habit(payload: HabitCreate, db: Session = Depends(get_db)) -> Habit:
    """Create a new habit. Validates routine_id if provided."""
    if payload.routine_id is not None:
        routine = db.query(Routine).filter(Routine.id == payload.routine_id).first()
        if not routine:
            raise HTTPException(status_code=400, detail="Routine not found")

    habit = Habit(**payload.model_dump())
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


@router.get("/", response_model=list[HabitResponse])
def list_habits(
    routine_id: UUID | None = Query(None),
    habit_status: str | None = Query(None, alias="status"),
    scaffolding_status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Habit]:
    """List habits with composable filters."""
    query = db.query(Habit)

    if routine_id is not None:
        query = query.filter(Habit.routine_id == routine_id)
    if habit_status is not None:
        query = query.filter(Habit.status == habit_status)
    if scaffolding_status is not None:
        query = query.filter(Habit.scaffolding_status == scaffolding_status)

    return query.order_by(Habit.created_at).all()


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
