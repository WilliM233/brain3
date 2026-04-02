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
    tag_ids: list[UUID] | None = None

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
    tags: list["TagResponse"] = []


class ActivityLogDetailResponse(ActivityLogResponse):
    """Activity log entry with resolved task/routine/checkin references."""

    task: "TaskResponse | None" = None
    routine: "RoutineResponse | None" = None
    checkin: "CheckinResponse | None" = None


from app.schemas.checkins import CheckinResponse  # noqa: E402
from app.schemas.routines import RoutineResponse  # noqa: E402
from app.schemas.tags import TagResponse  # noqa: E402
from app.schemas.tasks import TaskResponse  # noqa: E402

ActivityLogResponse.model_rebuild()
ActivityLogDetailResponse.model_rebuild()
