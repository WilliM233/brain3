"""Pydantic schemas for Project CRUD operations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ProjectStatus = Literal["not_started", "active", "blocked", "completed", "abandoned"]


class ProjectCreate(BaseModel):
    """Fields required to create a project."""

    goal_id: UUID
    title: str
    description: str | None = None
    status: ProjectStatus = "not_started"
    deadline: date | None = None


class ProjectUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    goal_id: UUID | None = None
    title: str | None = None
    description: str | None = None
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
