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

"""Pydantic schemas for Task CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["pending", "active", "completed", "skipped", "deferred"]
CognitiveType = Literal[
    "hands_on", "communication", "decision", "errand", "admin", "focus_work"
]


class TaskCreate(BaseModel):
    """Fields required to create a task."""

    project_id: UUID | None = None
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = "pending"
    cognitive_type: CognitiveType | None = None
    energy_cost: int | None = None
    activation_friction: int | None = None
    context_required: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    recurrence_rule: str | None = Field(default=None, max_length=500)

    @field_validator("energy_cost", "activation_friction")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class TaskUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    project_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    cognitive_type: CognitiveType | None = None
    energy_cost: int | None = None
    activation_friction: int | None = None
    context_required: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    recurrence_rule: str | None = Field(default=None, max_length=500)

    @field_validator("energy_cost", "activation_friction")
    @classmethod
    def validate_1_to_5(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            msg = "Value must be between 1 and 5"
            raise ValueError(msg)
        return v


class TaskResponse(BaseModel):
    """Task returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None = None
    title: str
    description: str | None = None
    status: TaskStatus
    cognitive_type: CognitiveType | None = None
    energy_cost: int | None = None
    activation_friction: int | None = None
    context_required: str | None = None
    due_date: date | None = None
    recurrence_rule: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskDetailResponse(TaskResponse):
    """Task with nested tags — returned by GET /api/tasks/{id}."""

    tags: list["TagResponse"] = []


from app.schemas.tags import TagResponse  # noqa: E402

TaskDetailResponse.model_rebuild()
