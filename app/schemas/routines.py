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

"""Pydantic schemas for Routine and RoutineSchedule CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

RoutineFrequency = Literal["daily", "weekdays", "weekends", "weekly", "custom"]
RoutineStatus = Literal["active", "paused", "retired"]

# ---------------------------------------------------------------------------
# Routine schemas
# ---------------------------------------------------------------------------


class RoutineCreate(BaseModel):
    """Fields required to create a routine."""

    domain_id: UUID
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    frequency: RoutineFrequency
    status: RoutineStatus = "active"
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
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    frequency: RoutineFrequency | None = None
    status: RoutineStatus | None = None
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
    frequency: RoutineFrequency
    status: RoutineStatus
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


class RoutineListResponse(BaseModel):
    """Envelope for GET /api/routines/ — wraps the item list with a count."""

    items: list[RoutineResponse]
    count: int


# ---------------------------------------------------------------------------
# RoutineSchedule schemas
# ---------------------------------------------------------------------------


class RoutineScheduleCreate(BaseModel):
    """Fields required to add a schedule entry to a routine."""

    day_of_week: str = Field(max_length=50)
    time_of_day: str = Field(max_length=50)
    preferred_window: str | None = Field(default=None, max_length=50)


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


CompletionStatus = Literal["all_done", "partial", "skipped"]


class RoutineCompleteRequest(BaseModel):
    """Optional payload for the completion endpoint."""

    completed_date: date | None = None
    status: CompletionStatus = "all_done"
    freeform_note: str | None = Field(default=None, max_length=5000)


class RoutineCompleteResponse(BaseModel):
    """Result of recording a routine completion."""

    routine_id: UUID
    completed_date: date
    current_streak: int
    best_streak: int
    streak_was_broken: bool
    completion_id: UUID | None = None
    status: str | None = None
    habits_completed: list[UUID] | None = None
