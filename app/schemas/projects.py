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

"""Pydantic schemas for Project CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProjectStatus = Literal["not_started", "active", "blocked", "completed", "abandoned"]


class ProjectCreate(BaseModel):
    """Fields required to create a project."""

    goal_id: UUID
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus = "not_started"
    deadline: date | None = None


class ProjectUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    goal_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None
    deadline: date | None = None


class ProjectResponse(BaseModel):
    """Project returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal_id: UUID
    title: str
    description: str | None = None
    status: ProjectStatus
    deadline: date | None = None
    progress_pct: int
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(ProjectResponse):
    """Project with nested tasks — returned by GET /api/projects/{id}."""

    tasks: list[TaskResponse] = []


from app.schemas.tasks import TaskResponse  # noqa: E402

ProjectDetailResponse.model_rebuild()
