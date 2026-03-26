"""Pydantic schemas for Routine and RoutineSchedule CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

# ---------------------------------------------------------------------------
# Routine schemas
# ---------------------------------------------------------------------------


class RoutineCreate(BaseModel):
    """Fields required to create a routine."""

    domain_id: UUID
    title: str
    description: str | None = None
    frequency: str
    status: str = "active"
    energy_cost: int | None = None
    activation_friction: int | None = None

    @field_validator("energy_cost", "activation_friction")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class RoutineUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    domain_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    frequency: str | None = None
    status: str | None = None
    energy_cost: int | None = None
    activation_friction: int | None = None

    @field_validator("energy_cost", "activation_friction")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class RoutineResponse(BaseModel):
    """Routine returned from API — includes id and streak data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain_id: UUID
    title: str
    description: str | None = None
    frequency: str
    status: str
    energy_cost: int | None = None
    activation_friction: int | None = None
    current_streak: int
    best_streak: int
    last_completed: date | None = None
    created_at: datetime
    updated_at: datetime


class RoutineDetailResponse(RoutineResponse):
    """Routine with nested schedules — returned by GET /api/routines/{id}."""

    schedules: list["RoutineScheduleResponse"] = []


# ---------------------------------------------------------------------------
# RoutineSchedule schemas
# ---------------------------------------------------------------------------


class RoutineScheduleCreate(BaseModel):
    """Fields required to add a schedule entry to a routine."""

    day_of_week: str
    time_of_day: str
    preferred_window: str | None = None


class RoutineScheduleResponse(BaseModel):
    """RoutineSchedule returned from API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    routine_id: UUID
    day_of_week: str | None = None
    time_of_day: str | None = None
    preferred_window: str | None = None


RoutineDetailResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Completion schemas
# ---------------------------------------------------------------------------


class RoutineCompleteRequest(BaseModel):
    """Optional payload for the completion endpoint."""

    completed_date: date | None = None


class RoutineCompleteResponse(BaseModel):
    """Result of recording a routine completion."""

    routine_id: UUID
    completed_date: date
    current_streak: int
    best_streak: int
    streak_was_broken: bool
