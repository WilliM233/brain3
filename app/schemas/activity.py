"""Pydantic schemas for Activity Log CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ActionType = Literal[
    "completed", "skipped", "deferred", "started", "reflected", "checked_in"
]


class ActivityLogCreate(BaseModel):
    """Fields required to create an activity log entry."""

    task_id: UUID | None = None
    routine_id: UUID | None = None
    checkin_id: UUID | None = None
    action_type: ActionType
    notes: str | None = Field(default=None, max_length=5000)
    energy_before: int | None = None
    energy_after: int | None = None
    mood_rating: int | None = None
    friction_actual: int | None = None
    duration_minutes: int | None = None

    @field_validator("energy_before", "energy_after", "mood_rating", "friction_actual")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def at_most_one_reference(self) -> "ActivityLogCreate":
        refs = sum(v is not None for v in [self.task_id, self.routine_id, self.checkin_id])
        if refs > 1:
            msg = "At most one of task_id, routine_id, or checkin_id may be provided"
            raise ValueError(msg)
        return self


class ActivityLogUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    task_id: UUID | None = None
    routine_id: UUID | None = None
    checkin_id: UUID | None = None
    action_type: ActionType | None = None
    notes: str | None = Field(default=None, max_length=5000)
    energy_before: int | None = None
    energy_after: int | None = None
    mood_rating: int | None = None
    friction_actual: int | None = None
    duration_minutes: int | None = None

    @field_validator("energy_before", "energy_after", "mood_rating", "friction_actual")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class ActivityLogResponse(BaseModel):
    """Activity log entry returned from API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID | None = None
    routine_id: UUID | None = None
    checkin_id: UUID | None = None
    action_type: ActionType
    notes: str | None = None
    energy_before: int | None = None
    energy_after: int | None = None
    mood_rating: int | None = None
    friction_actual: int | None = None
    duration_minutes: int | None = None
    logged_at: datetime


class ActivityLogDetailResponse(ActivityLogResponse):
    """Activity log entry with resolved task/routine/checkin references."""

    task: "TaskResponse | None" = None
    routine: "RoutineResponse | None" = None
    checkin: "CheckinResponse | None" = None


from app.schemas.checkins import CheckinResponse  # noqa: E402
from app.schemas.routines import RoutineResponse  # noqa: E402
from app.schemas.tasks import TaskResponse  # noqa: E402

ActivityLogDetailResponse.model_rebuild()
