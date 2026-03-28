"""Pydantic schemas for Goal CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

GoalStatus = Literal["active", "paused", "achieved", "abandoned"]


class GoalCreate(BaseModel):
    """Fields required to create a goal."""

    domain_id: UUID
    title: str
    description: str | None = None
    status: GoalStatus = "active"


class GoalUpdate(BaseModel):
    """All fields optional — supports partial PATCH updates."""

    domain_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    status: GoalStatus | None = None


class GoalResponse(BaseModel):
    """Goal returned from API — includes id and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain_id: UUID
    title: str
    description: str | None = None
    status: GoalStatus
    created_at: datetime
    updated_at: datetime


class GoalDetailResponse(GoalResponse):
    """Goal with nested projects — returned by GET /api/goals/{id}."""

    projects: list[ProjectResponse] = []


from app.schemas.projects import ProjectResponse  # noqa: E402

GoalDetailResponse.model_rebuild()
