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

"""Pydantic schemas for Habit CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HabitStatus = Literal["active", "paused", "graduated", "abandoned"]
HabitFrequency = Literal["daily", "weekdays", "weekends", "weekly", "custom"]
NotificationFrequency = Literal[
    "daily", "every_other_day", "twice_week", "weekly", "graduated", "none"
]
ScaffoldingStatus = Literal["tracking", "accountable", "graduated"]


class HabitCreate(BaseModel):
    """Fields required to create a habit."""

    routine_id: UUID | None = None
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: HabitStatus = "active"
    frequency: HabitFrequency | None = None
    notification_frequency: NotificationFrequency = "none"
    scaffolding_status: ScaffoldingStatus = "tracking"
    introduced_at: date | None = None
    graduation_window: int | None = None
    graduation_target: float | None = None
    graduation_threshold: int | None = None

    @field_validator("graduation_target")
    @classmethod
    def validate_graduation_target(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            msg = "graduation_target must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def standalone_requires_frequency(self) -> HabitCreate:
        """Standalone habits (no routine_id) must specify a frequency."""
        if self.routine_id is None and self.frequency is None:
            raise ValueError(
                "frequency is required for standalone habits (no routine_id)"
            )
        return self


class HabitUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    routine_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: HabitStatus | None = None
    frequency: HabitFrequency | None = None
    notification_frequency: NotificationFrequency | None = None
    scaffolding_status: ScaffoldingStatus | None = None
    introduced_at: date | None = None
    graduation_window: int | None = None
    graduation_target: float | None = None
    graduation_threshold: int | None = None

    @field_validator("graduation_target")
    @classmethod
    def validate_graduation_target(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            msg = "graduation_target must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v


class HabitResponse(BaseModel):
    """Habit returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    routine_id: UUID | None = None
    title: str
    description: str | None = None
    status: HabitStatus
    frequency: HabitFrequency | None = None
    notification_frequency: NotificationFrequency
    scaffolding_status: ScaffoldingStatus
    introduced_at: date | None = None
    graduation_window: int | None = None
    graduation_target: float | None = None
    graduation_threshold: int | None = None
    current_streak: int
    best_streak: int
    last_completed: date | None = None
    created_at: datetime
    updated_at: datetime


class HabitDetailResponse(HabitResponse):
    """Habit with nested parent routine — returned by GET /api/habits/{id}."""

    routine: RoutineResponse | None = None


# ---------------------------------------------------------------------------
# Habit Completion — POST /api/habits/{id}/complete
# ---------------------------------------------------------------------------


class HabitCompleteRequest(BaseModel):
    """Optional payload for habit completion."""

    completed_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class HabitCompleteResponse(BaseModel):
    """Response from completing a habit."""

    model_config = ConfigDict(from_attributes=True)

    habit_id: UUID
    completion_id: UUID
    completed_date: date
    current_streak: int
    best_streak: int
    streak_was_broken: bool
    source: str


from app.schemas.routines import RoutineResponse  # noqa: E402

HabitDetailResponse.model_rebuild()
